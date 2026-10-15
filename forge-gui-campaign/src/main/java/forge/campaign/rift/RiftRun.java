package forge.campaign.rift;

import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.utils.Array;
import com.badlogic.gdx.utils.JsonReader;
import com.badlogic.gdx.utils.JsonValue;
import forge.StaticData;
import forge.adventure.data.EnemyData;
import forge.adventure.scene.TileMapScene;
import forge.adventure.stage.MapStage;
import forge.adventure.util.AdventureOverrides;
import forge.adventure.util.Config;
import forge.adventure.util.Current;
import forge.adventure.util.Reward;
import forge.card.CardRarity;
import forge.deck.CardPool;
import forge.deck.Deck;
import forge.gamemodes.limited.SealedDeckBuilder;
import forge.item.PaperCard;
import forge.item.SealedTemplate;
import forge.item.generation.UnOpenedProduct;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * Planar Rifts: roguelite trials inside the Adventure (Rory, 2026-10-15: "going into an alternate
 * plane and must win ... to unlock something in the main game").
 *
 * A rift is a dungeon on the map (plane/world/rifts.json, maps built by make_maps.py). Inside it
 * the player's deck, relics and gear stay behind: the first duel starts a run with a sealed deck
 * opened from the rift's sets, every enemy plays a sealed deck of the same sets, and each win
 * offers three cards (in the deck's colours) for the rift deck instead of the usual loot cards.
 * Adventure already throws the player out of a dungeon on any lost duel; a loss also ends the run
 * and resets the rift's enemies. Beating the rift boss sets the rift's flag (its loot holds the
 * rift's planar relic). The run is saved in the world save (our World shadow).
 *
 * Hooks: our DuelScene (decks, life, items, the result), DuelRewards and RewardScene (the picks),
 * DeckSize (40 cards in a rift), World (save), RelicSlots (Relic4 once every rift is won).
 */
public final class RiftRun {
    public static final String FILE = "world/rifts.json";

    /** One rift of the catalogue. */
    public record Rift(String name, List<String> packs, String landSet, String boss, String flag,
                       int enemyLife, int bossPacks) {
    }

    private static volatile Map<String, Rift> rifts;
    private static String riftName;
    private static Deck deck;
    private static boolean picking;

    private RiftRun() {
    }

    public static Map<String, Rift> rifts() {
        Map<String, Rift> r = rifts;
        if (r == null) {
            synchronized (RiftRun.class) {
                if (rifts == null) {
                    rifts = load();
                }
                r = rifts;
            }
        }
        return r;
    }

    private static Map<String, Rift> load() {
        Map<String, Rift> m = new LinkedHashMap<>();
        FileHandle file = Config.instance().getFile(FILE);
        if (file == null || !file.exists()) {
            return m;
        }
        for (JsonValue v = new JsonReader().parse(file).child; v != null; v = v.next) {
            if (v.name == null || v.name.startsWith("_")) {
                continue;
            }
            List<String> packs = new ArrayList<>(List.of(v.get("packs").asStringArray()));
            m.put(v.name, new Rift(v.name, packs, v.getString("landSet", packs.get(0)), v.getString("boss"),
                    v.getString("flag"), v.getInt("enemyLife", 16), v.getInt("bossPacks", 9)));
        }
        return m;
    }

    /** The rift the player is in, or null (not in a dungeon, or not in a rift). */
    public static Rift current() {
        try {
            if (!MapStage.getInstance().isInMap() || TileMapScene.instance().rootPoint == null) {
                return null;
            }
            return rifts().get(TileMapScene.instance().rootPoint.getData().name);
        } catch (RuntimeException e) {
            return null;
        }
    }

    public static boolean inRift() {
        return current() != null;
    }

    public static synchronized String activeRift() {
        return riftName;
    }

    /** The rift deck for this duel (a copy), starting a run if none is going in this rift. */
    public static synchronized Deck playerDeck() {
        Rift rift = current();
        if (rift == null) {
            return null;
        }
        if (deck == null || !rift.name().equals(riftName)) {
            start(rift, new Random());
        }
        return (Deck) deck.copyTo("Rift deck");
    }

    /** Starts a run in a rift (also SelfCheck's way in). */
    public static synchronized void start(Rift rift, Random random) {
        riftName = rift.name();
        deck = build(rift, rift.packs().size(), random);
        deck.setName(rift.name());
        picking = false;
        System.out.println("[campaign] rift run started in " + rift.name() + ": " + deck.getMain().countAll() + " cards");
    }

    /** A sealed deck from packs of the rift's sets (the first `packs` of its list, repeated). */
    public static Deck build(Rift rift, int packs, Random random) {
        CardPool pool = open(rift, packs);
        Deck built = new SealedDeckBuilder(pool.toFlatList()).buildDeck(rift.landSet());
        return built == null ? new Deck() : built;
    }

    public static CardPool open(Rift rift, int packs) {
        CardPool pool = new CardPool();
        for (int i = 0; i < packs; i++) {
            String set = rift.packs().get(i % rift.packs().size());
            SealedTemplate template = AdventureOverrides.instance().getBoosterTemplate(set);
            if (template == null) {
                template = StaticData.instance().getBoosters().get(set);
            }
            if (template != null) {
                pool.addAllFlat(new UnOpenedProduct(template).get());
            }
        }
        return pool;
    }

    /** A rift enemy's deck: sealed from the rift's sets; the boss opens more packs. */
    public static Deck enemyDeck(EnemyData enemy) {
        Rift rift = current();
        if (rift == null) {
            return null;
        }
        boolean boss = enemy != null && rift.boss().equals(enemy.name);
        return build(rift, boss ? rift.bossPacks() : rift.packs().size(), new Random());
    }

    public static int enemyLife(EnemyData enemy) {
        Rift rift = current();
        if (rift == null || enemy == null) {
            return enemy == null ? 20 : enemy.life;
        }
        return rift.boss().equals(enemy.name) ? enemy.life : rift.enemyLife();
    }

    /** From DuelScene when a map duel ends. */
    public static synchronized void duelEnded(boolean won, EnemyData enemy) {
        Rift rift = current();
        if (rift == null || deck == null) {
            return;
        }
        if (!won) {
            System.out.println("[campaign] rift run lost in " + rift.name());
            end();
            MapStage.getInstance().clearOnExit(); // the rift's enemies come back for the next attempt
        } else if (enemy != null && rift.boss().equals(enemy.name)) {
            System.out.println("[campaign] rift won: " + rift.name());
            Current.player().setQuestFlag(rift.flag(), 1);
            end();
        } else {
            picking = true;
        }
    }

    private static void end() {
        riftName = null;
        deck = null;
        picking = false;
    }

    /** After a won rift duel: three cards for the rift deck (null when there is no pick to make). */
    public static synchronized Array<Reward> choices() {
        Rift rift = current();
        if (!picking || rift == null || deck == null) {
            return null;
        }
        byte deckMask = colourMask(deck);
        List<PaperCard> offer = new ArrayList<>();
        for (PaperCard c : open(rift, 2).toFlatList()) {
            if (c.getRules().getType().isLand()) {
                continue;
            }
            // Colourless, or sharing a colour with the deck (a two-colour card needs only one of them).
            byte mask = c.getRules().getColor().getColor();
            boolean fits = mask == 0 || (mask & deckMask) != 0;
            if (fits && offer.stream().noneMatch(o -> o.getName().equals(c.getName()))) {
                offer.add(c);
            }
        }
        Collections.shuffle(offer);
        offer.sort((a, b) -> Integer.compare(rank(b.getRarity()), rank(a.getRarity())));
        Array<Reward> out = new Array<>();
        for (int i = 0; i < Math.min(3, offer.size()); i++) {
            out.add(new Reward(offer.get(i)));
        }
        return out;
    }

    private static int rank(CardRarity r) {
        return r == CardRarity.MythicRare ? 3 : r == CardRarity.Rare ? 2 : r == CardRarity.Uncommon ? 1 : 0;
    }

    /** The player's pick goes into the rift deck, not the collection; true if it was taken here. */
    public static synchronized boolean takePick(Reward reward) {
        if (!picking || deck == null || reward == null || reward.getCard() == null) {
            return false;
        }
        deck.getMain().add(reward.getCard());
        picking = false;
        System.out.println("[campaign] rift pick: " + reward.getCard().getName());
        return true;
    }

    static byte colourMask(Deck d) {
        byte mask = 0;
        for (Map.Entry<PaperCard, Integer> e : d.getMain()) {
            if (!e.getKey().getRules().getType().isLand()) {
                mask |= e.getKey().getRules().getColor().getColor();
            }
        }
        return mask;
    }

    /** True once every rift has been won (opens the Relic4 slot). */
    public static boolean allWon() {
        if (Current.player() == null || rifts().isEmpty()) {
            return false;
        }
        for (Rift r : rifts().values()) {
            if (Current.player().getQuestFlag(r.flag()) < 1) {
                return false;
            }
        }
        return true;
    }

    /** The run, for the world save: rift name and card names ("Name|SET"); null when none. */
    public static synchronized HashMap<String, ArrayList<String>> snapshot() {
        HashMap<String, ArrayList<String>> out = new HashMap<>();
        if (riftName == null || deck == null) {
            return out;
        }
        ArrayList<String> cards = new ArrayList<>();
        for (PaperCard c : deck.getMain().toFlatList()) {
            cards.add(c.getName() + "|" + c.getEdition());
        }
        out.put(riftName + (picking ? "#picking" : ""), cards);
        return out;
    }

    @SuppressWarnings("unchecked")
    public static synchronized void restore(Object saved) {
        end();
        if (!(saved instanceof Map<?, ?> map) || map.isEmpty()) {
            return;
        }
        Map.Entry<String, List<String>> e = ((Map<String, List<String>>) map).entrySet().iterator().next();
        String key = e.getKey();
        picking = key.endsWith("#picking");
        riftName = picking ? key.substring(0, key.length() - "#picking".length()) : key;
        deck = new Deck(riftName);
        for (String s : e.getValue()) {
            String[] parts = s.split("\\|", 2);
            PaperCard c = parts.length == 2 ? StaticData.instance().getCommonCards().getCard(parts[0], parts[1]) : null;
            if (c == null) {
                c = StaticData.instance().getCommonCards().getCard(parts[0]);
            }
            if (c != null) {
                deck.getMain().add(c);
            }
        }
    }
}
