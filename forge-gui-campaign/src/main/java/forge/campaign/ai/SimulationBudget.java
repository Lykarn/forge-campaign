package forge.campaign.ai;

/**
 * The time an AI may spend searching one decision when simulation is on.
 *
 * Forge's simulation has no clock: it explores every candidate play to depth 3, which can take
 * minutes on a big board. Our shadowed SimulationController stops recursing deeper once a
 * decision has used this budget, so the AI picks the best line found so far. It is a soft limit:
 * each candidate already started is still scored at depth 0.
 *
 * One value for the whole process is enough: an Adventure duel has one simulating enemy at a
 * time, and the benchmark runs one game per process. 0 means no limit (upstream behaviour).
 */
public final class SimulationBudget {
    private static volatile long budgetNanos = 0;

    private SimulationBudget() {
    }

    public static void setMillis(long millis) {
        budgetNanos = Math.max(0, millis) * 1_000_000L;
    }

    /** The deadline for a decision starting now, or Long.MAX_VALUE without a budget. */
    public static long deadlineFromNow() {
        long budget = budgetNanos;
        return budget == 0 ? Long.MAX_VALUE : System.nanoTime() + budget;
    }

    public static boolean expired(long deadline) {
        return deadline != Long.MAX_VALUE && System.nanoTime() - deadline > 0;
    }
}
