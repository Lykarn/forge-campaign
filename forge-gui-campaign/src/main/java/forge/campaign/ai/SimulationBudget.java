package forge.campaign.ai;

/**
 * The time an AI may spend searching one decision when simulation is on.
 *
 * Forge's simulation has no clock: it tries every candidate play, every choice of targets and
 * modes, three plays deep, and can take minutes on a big board (a Boss turn took 260 s in the
 * benchmark). With a budget, our shadowed SpellAbilityPicker opens a deadline for each top-level
 * decision, and every search inside that decision (the plan for this phase and the ones it tries
 * for combat, and every nested level) shares it. Once it passes, no new candidate, choice or
 * deeper level is started and the AI plays the best line found so far.
 *
 * One budget for the whole process is enough: an Adventure duel has one simulating enemy at a
 * time, and the benchmark plays one game at a time per process. 0 means no limit (upstream).
 */
public final class SimulationBudget {
    private static volatile long budgetNanos = 0;
    private static final ThreadLocal<Long> DECISION_DEADLINE = new ThreadLocal<>();

    private SimulationBudget() {
    }

    public static void setMillis(long millis) {
        budgetNanos = Math.max(0, millis) * 1_000_000L;
    }

    /** Opens the deadline for a top-level decision on this thread; pair with endDecision(). */
    public static void beginDecision() {
        long budget = budgetNanos;
        DECISION_DEADLINE.set(budget == 0 ? Long.MAX_VALUE : System.nanoTime() + budget);
    }

    public static void endDecision() {
        DECISION_DEADLINE.remove();
    }

    /** The deadline of the decision under way, or one starting now outside a decision. */
    public static long currentDeadline() {
        Long open = DECISION_DEADLINE.get();
        if (open != null) {
            return open;
        }
        long budget = budgetNanos;
        return budget == 0 ? Long.MAX_VALUE : System.nanoTime() + budget;
    }

    public static boolean expired(long deadline) {
        return deadline != Long.MAX_VALUE && System.nanoTime() - deadline > 0;
    }
}
