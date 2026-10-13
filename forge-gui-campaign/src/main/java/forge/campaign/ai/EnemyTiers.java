package forge.campaign.ai;

import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.utils.JsonReader;
import com.badlogic.gdx.utils.JsonValue;
import forge.ai.AIOption;
import forge.ai.AiProfileUtil;
import forge.adventure.data.EnemyData;
import forge.adventure.util.Config;

import java.util.EnumMap;
import java.util.HashMap;
import java.util.Map;

/**
 * Which tier each enemy plays at, and what each tier means, from world/enemy_tiers.json.
 *
 * The tier lives in its own file rather than in enemies.json so that we keep Forge's enemy list
 * as it is (it is shared by every plane) and need no shadow of EnemyData. An enemy's tier is, in
 * order: its entry under "enemies"; Boss if enemies.json marks it a boss; Elite if its life is at
 * least rules.eliteMinLife; otherwise Grunt.
 */
public final class EnemyTiers {
    public static final String FILE = "world/enemy_tiers.json";

    /** What a tier resolves to for one enemy. simulation is null for none. */
    public record Settings(Tier tier, String profile, AIOption simulation, int budgetMs) {
        @Override
        public String toString() {
            String sim = simulation == null ? "none"
                    : simulation == AIOption.USE_FULL_SIMULATION ? "full" : "hybrid";
            return tier.label() + " (profile " + profile + ", simulation " + sim
                    + (simulation == null ? "" : ", budget " + budgetMs + " ms") + ")";
        }
    }

    private static EnemyTiers instance;

    private final Map<Tier, Settings> tiers = new EnumMap<>(Tier.class);
    private final Map<String, Tier> enemies = new HashMap<>();
    private int eliteMinLife = 25;

    public static synchronized EnemyTiers get() {
        if (instance == null) {
            FileHandle file = Config.instance().getFile(FILE);
            instance = new EnemyTiers(file != null && file.exists() ? new JsonReader().parse(file) : null);
        }
        return instance;
    }

    /** For tools and tests: tiers from an already parsed file (null = built-in defaults). */
    public EnemyTiers(JsonValue root) {
        for (Tier t : Tier.values()) {
            tiers.put(t, new Settings(t, t.defaultProfile, t.defaultSimulation, t.defaultBudgetMs));
        }
        if (root == null) {
            System.out.println("[campaign] " + FILE + " not found: built-in tier defaults");
            return;
        }
        JsonValue rules = root.get("rules");
        if (rules != null) {
            eliteMinLife = rules.getInt("eliteMinLife", eliteMinLife);
        }
        JsonValue tierValues = root.get("tiers");
        if (tierValues != null) {
            for (JsonValue v = tierValues.child; v != null; v = v.next) {
                Tier t = Tier.parse(v.name);
                if (t == null) {
                    System.err.println("[campaign] " + FILE + ": unknown tier " + v.name);
                    continue;
                }
                Settings base = tiers.get(t);
                tiers.put(t, new Settings(t,
                        v.getString("profile", base.profile()),
                        v.has("simulation") ? parseSimulation(v.getString("simulation")) : base.simulation(),
                        v.getInt("budgetMs", base.budgetMs())));
            }
        }
        JsonValue enemyValues = root.get("enemies");
        if (enemyValues != null) {
            for (JsonValue v = enemyValues.child; v != null; v = v.next) {
                Tier t = Tier.parse(v.asString());
                if (t == null) {
                    System.err.println("[campaign] " + FILE + ": enemy " + v.name + " has unknown tier " + v.asString());
                } else {
                    enemies.put(v.name, t);
                }
            }
        }
    }

    private static AIOption parseSimulation(String value) {
        return switch (value == null ? "" : value.trim().toLowerCase()) {
            case "full" -> AIOption.USE_FULL_SIMULATION;
            case "hybrid" -> AIOption.USE_HYBRID_SIMULATION;
            default -> null;
        };
    }

    public Tier tierOf(EnemyData enemy) {
        Tier named = enemies.get(enemy.name);
        if (named == null && enemy.getName() != null) {
            named = enemies.get(enemy.getName());
        }
        if (named != null) {
            return named;
        }
        if (enemy.boss) {
            return Tier.BOSS;
        }
        return enemy.life >= eliteMinLife ? Tier.ELITE : Tier.GRUNT;
    }

    public Settings settingsOf(Tier tier) {
        return tiers.get(tier);
    }

    /** The tier's settings for this enemy, with a profile that is actually installed. */
    public Settings settingsFor(EnemyData enemy) {
        Settings s = settingsOf(tierOf(enemy));
        if (!AiProfileUtil.getAvailableProfiles().contains(s.profile())) {
            System.err.println("[campaign] AI profile " + s.profile() + " is not installed, using Default");
            s = new Settings(s.tier(), "Default", s.simulation(), s.budgetMs());
        }
        return s;
    }
}
