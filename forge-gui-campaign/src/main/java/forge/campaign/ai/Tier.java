package forge.campaign.ai;

import forge.ai.AIOption;

/**
 * How hard an enemy plays. Each tier picks an AI profile (res/ai/*.ai), a simulation mode and a
 * time budget per decision; the values below are defaults that world/enemy_tiers.json can override.
 *
 * Grunt plays Forge's normal heuristic AI. Elite adds hybrid simulation: the heuristic AI still
 * chooses, but every play is simulated once and vetoed if it leaves the AI worse off (Forge's
 * OnePlaySafetyChecker), which stops most "cast it because I can" plays. Boss uses full
 * simulation: it searches candidate plays a few steps deep and picks the best-scoring line.
 */
public enum Tier {
    GRUNT("Default", null, 0),
    ELITE("Elite", AIOption.USE_HYBRID_SIMULATION, 3000),
    BOSS("Boss", AIOption.USE_FULL_SIMULATION, 5000);

    public final String defaultProfile;
    public final AIOption defaultSimulation;
    public final int defaultBudgetMs;

    Tier(String defaultProfile, AIOption defaultSimulation, int defaultBudgetMs) {
        this.defaultProfile = defaultProfile;
        this.defaultSimulation = defaultSimulation;
        this.defaultBudgetMs = defaultBudgetMs;
    }

    /** "Grunt", "elite", "BOSS" all work; anything else is null. */
    public static Tier parse(String name) {
        if (name == null) {
            return null;
        }
        for (Tier t : values()) {
            if (t.name().equalsIgnoreCase(name.trim())) {
                return t;
            }
        }
        return null;
    }

    public String label() {
        return name().charAt(0) + name().substring(1).toLowerCase();
    }
}
