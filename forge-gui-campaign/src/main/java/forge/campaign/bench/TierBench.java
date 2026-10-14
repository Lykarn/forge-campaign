package forge.campaign.bench;

import com.badlogic.gdx.utils.Array;
import com.google.common.eventbus.Subscribe;
import forge.LobbyPlayer;
import forge.adventure.data.EnemyData;
import forge.adventure.data.WorldData;
import forge.adventure.util.CardUtil;
import forge.campaign.ai.AiStats;
import forge.campaign.ai.CampaignAi;
import forge.campaign.ai.EnemyTiers;
import forge.deck.Deck;
import forge.deck.io.DeckSerializer;
import forge.game.Game;
import forge.game.GameEndReason;
import forge.game.GameOutcome;
import forge.game.GameRules;
import forge.game.GameType;
import forge.game.Match;
import forge.game.event.GameEventTurnBegan;
import forge.game.player.RegisteredPlayer;
import forge.gui.GuiBase;
import forge.neo.NeoBoot;
import forge.neo.NeoPortable;
import forge.neo.platform.ConsoleUiDispatcher;
import forge.neo.platform.NeoGuiBase;
import forge.player.GamePlayerUtil;

import java.io.File;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * Headless benchmark for enemy tiers: plays Adventure enemies, with the exact AI the Adventure
 * gives them (CampaignAi), against reference player decks piloted by Forge's stock Default AI,
 * and writes one CSV row per game. scripts/bench.py runs several of these in parallel and
 * summarises win rate and seconds per turn by tier.
 *
 * The reference pilot is a fixed yardstick, not a human: a tier's win rate reads as "how it does
 * against stock Forge AI with this deck". Forge must run with the app folder as working directory
 * (Config finds ./res there), -Dforge.assetsDir and -Dneo.dataDir, like the packaged launcher.
 *
 * Usage:
 *   TierBench --list                       every enemy with its tier, tab-separated
 *   TierBench --enemies FILE --decks A.dck,B.dck --games N --out results.csv
 *             [--player-life 20] [--enemy-life-factor 1.0] [--timeout 900] [--stock]
 *
 * --stock plays every enemy as the Adventure does without tiers (Default profile, no simulation),
 * still grouped by tier: the baseline the tiers are measured against.
 */
public final class TierBench {
    /** Exit code asking scripts/bench.py to start this worker again (it resumes). */
    public static final int RESTART = 3;

    private static boolean stock;

    private TierBench() {
    }

    public static void main(String[] args) throws Exception {
        NeoPortable.apply();
        GuiBase.setInterface(new NeoGuiBase(new ConsoleUiDispatcher()));
        NeoBoot.loadEngine(null);

        if (has(args, "--list")) {
            for (EnemyData e : new Array.ArrayIterator<>(WorldData.getAllEnemies())) {
                System.out.println("ENEMY\t" + e.name + "\t" + EnemyTiers.get().tierOf(e).label()
                        + "\t" + e.life + "\t" + e.deck.length);
            }
            System.exit(0);
        }

        List<String> names = Files.readAllLines(Path.of(opt(args, "--enemies", null)), StandardCharsets.UTF_8);
        List<String> refDecks = List.of(opt(args, "--decks", null).split(","));
        int games = Integer.parseInt(opt(args, "--games", "2"));
        int playerLife = Integer.parseInt(opt(args, "--player-life", "20"));
        float enemyLifeFactor = Float.parseFloat(opt(args, "--enemy-life-factor", "1.0"));
        int timeout = Integer.parseInt(opt(args, "--timeout", "900"));
        stock = has(args, "--stock");

        // Resumable: rows already in --out are skipped, so scripts/bench.py can restart a worker
        // that stopped (see RESTART below) and it carries on where it was.
        Path outPath = Path.of(opt(args, "--out", null));
        Set<String> done = new HashSet<>();
        boolean fresh = !Files.exists(outPath);
        if (!fresh) {
            // Each row ends with ",#<enemy>|<reference deck>|<game number>".
            for (String line : Files.readAllLines(outPath, StandardCharsets.UTF_8)) {
                int key = line.lastIndexOf(",#");
                if (key >= 0) {
                    done.add(line.substring(key + 2));
                }
            }
        }
        try (PrintWriter out = new PrintWriter(Files.newBufferedWriter(outPath, StandardCharsets.UTF_8,
                StandardOpenOption.CREATE, StandardOpenOption.APPEND))) {
            if (fresh) {
                out.println("enemy,tier,enemy_deck,ref_deck,winner,turns,seconds,mean_turn_s,max_turn_s,enemy_life,player_life,vetoes,sim_decisions,fallbacks,turn_capped,note,key");
                out.flush();
            }
            for (String name : names) {
                if (name.isBlank()) {
                    continue;
                }
                EnemyData enemy = WorldData.getEnemy(name.trim());
                if (enemy == null) {
                    System.err.println("[bench] unknown enemy " + name);
                    continue;
                }
                for (String refPath : refDecks) {
                    for (int g = 0; g < games; g++) {
                        // No commas in the key: it is the last CSV cell, unquoted.
                        String key = (enemy.name + "|" + refPath.trim() + "|" + g).replace(',', ';');
                        if (done.contains(key)) {
                            continue;
                        }
                        String row = playOne(enemy, g, refPath.trim(), playerLife, enemyLifeFactor, timeout);
                        out.println(row + ",#" + key);
                        out.flush();
                        System.out.println("[bench] " + row);
                        // A game that timed out may still be running in its thread, and an
                        // out-of-memory error leaves the heap in doubt: both poison the next
                        // games, so stop and let bench.py start a clean process.
                        if (row.contains(",timeout") || row.contains("OutOfMemoryError")) {
                            System.out.println("[bench] RESTART: stopping this worker after " + key);
                            System.exit(RESTART);
                        }
                    }
                }
            }
        }
        // Forge leaves non-daemon threads behind (image fetcher, executors).
        System.exit(0);
    }

    /** Turn start times, from the engine's own turn events. */
    public static final class TurnClock {
        final List<Long> starts = new ArrayList<>();

        @Subscribe
        public void turnBegan(GameEventTurnBegan e) {
            starts.add(System.nanoTime());
        }
    }

    /**
     * A reference deck: a .dck file on disk, or an Adventure deck path such as
     * decks/starter/red_n.json, which is generated afresh each game as for a new player.
     */
    private static Deck loadReference(String path) {
        if (path.endsWith(".json")) {
            return CardUtil.getDeck(path, false, false, "", false, false);
        }
        Deck d = DeckSerializer.fromFile(new File(path));
        if (d == null) {
            throw new IllegalArgumentException("cannot read deck " + path);
        }
        return d;
    }

    private static String playOne(EnemyData enemy, int gameIndex, String refPath, int playerLife,
                                  float enemyLifeFactor, int timeout) {
        EnemyTiers.Settings settings = EnemyTiers.get().settingsFor(enemy);
        if (stock) {
            settings = new EnemyTiers.Settings(settings.tier(), "Default", null, 0, 0);
        }
        String deckPath = enemy.deck[gameIndex % enemy.deck.length];
        int enemyLife = Math.round(enemy.life * enemyLifeFactor);
        String refName = new File(refPath).getName();
        String note = "";
        try {
            Deck ref = loadReference(refPath);
            // As DuelScene: the enemy's deck as the Adventure builds it (not fantasy mode, no genetic AI).
            Deck enemyDeck = CardUtil.getDeck(deckPath, true, false, enemy.colors, enemy.life > 13, false);
            String profile = enemy.ai != null && !enemy.ai.isEmpty() ? capitalise(enemy.ai) : settings.profile();
            LobbyPlayer enemyPlayer = CampaignAi.createAiPlayer(enemy.getName(), profile, settings);
            LobbyPlayer refPlayer = GamePlayerUtil.createAiPlayer("Reference", 0, 0, null, "Default");

            RegisteredPlayer enemyRp = new RegisteredPlayer(enemyDeck);
            enemyRp.setPlayer(enemyPlayer);
            enemyRp.setStartingLife(enemyLife);
            RegisteredPlayer refRp = new RegisteredPlayer(ref);
            refRp.setPlayer(refPlayer);
            refRp.setStartingLife(playerLife);

            GameRules rules = new GameRules(GameType.Adventure);
            rules.setGamesPerMatch(1);
            rules.setManaBurn(false);
            rules.setWarnAboutAICards(false);
            Match match = new Match(rules, List.of(enemyRp, refRp), "TierBench");
            Game game = match.createGame();
            game.setNoGUIUser();
            TurnClock clock = new TurnClock();
            game.subscribeToEvents(clock);

            AiStats.reset();
            long start = System.nanoTime();
            ExecutorService runner = Executors.newSingleThreadExecutor(r -> {
                Thread t = new Thread(r, "bench-game");
                t.setDaemon(true);
                return t;
            });
            Future<?> run = runner.submit(() -> match.startGame(game));
            try {
                run.get(timeout, TimeUnit.SECONDS);
            } catch (TimeoutException e) {
                note = "timeout";
                run.cancel(true);
                game.setGameOver(GameEndReason.Draw);
            } finally {
                runner.shutdownNow();
            }
            long end = System.nanoTime();
            double seconds = (end - start) / 1e9;

            GameOutcome outcome = game.getOutcome();
            String winner;
            int turns = outcome == null ? clock.starts.size() : outcome.getLastTurnNumber();
            if (outcome == null || outcome.isDraw()) {
                winner = "draw";
            } else {
                winner = outcome.getWinningLobbyPlayer() == enemyPlayer ? "enemy" : "player";
            }
            double maxTurn = 0;
            for (int i = 0; i < clock.starts.size(); i++) {
                long next = i + 1 < clock.starts.size() ? clock.starts.get(i + 1) : end;
                maxTurn = Math.max(maxTurn, (next - clock.starts.get(i)) / 1e9);
            }
            double meanTurn = turns > 0 ? seconds / turns : 0;
            return csv(enemy.name, settings.tier().label(), deckPath, refName, winner,
                    String.valueOf(turns), fmt(seconds), fmt(meanTurn), fmt(maxTurn),
                    String.valueOf(enemyLife), String.valueOf(playerLife), String.valueOf(AiStats.VETOES.get()),
                    String.valueOf(AiStats.SIM_DECISIONS.get()), String.valueOf(AiStats.FALLBACKS.get()),
                    String.valueOf(AiStats.TURN_CAPPED.get()), note);
        } catch (Throwable t) {
            t.printStackTrace();
            return csv(enemy.name, settings.tier().label(), deckPath, refName, "error",
                    "0", "0", "0", "0", String.valueOf(enemyLife), String.valueOf(playerLife), "0", "0", "0", "0", t.toString());
        }
    }

    private static String capitalise(String s) {
        return s.substring(0, 1).toUpperCase(Locale.ROOT) + s.substring(1).toLowerCase(Locale.ROOT);
    }

    private static String fmt(double v) {
        return String.format(Locale.ROOT, "%.2f", v);
    }

    private static String csv(String... cells) {
        StringBuilder sb = new StringBuilder();
        for (String c : cells) {
            if (sb.length() > 0) {
                sb.append(',');
            }
            String v = c == null ? "" : c;
            sb.append(v.contains(",") || v.contains("\"") ? "\"" + v.replace("\"", "\"\"") + "\"" : v);
        }
        return sb.toString();
    }

    private static boolean has(String[] args, String flag) {
        for (String a : args) {
            if (a.equals(flag)) {
                return true;
            }
        }
        return false;
    }

    private static String opt(String[] args, String key, String def) {
        for (int i = 0; i < args.length - 1; i++) {
            if (args[i].equals(key)) {
                return args[i + 1];
            }
        }
        if (def == null) {
            throw new IllegalArgumentException("missing " + key);
        }
        return def;
    }
}
