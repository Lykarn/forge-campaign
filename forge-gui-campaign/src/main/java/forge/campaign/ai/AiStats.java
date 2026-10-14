package forge.campaign.ai;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * Counters the benchmark reads per game, kept by our shadowed simulation classes.
 *
 * Win rate alone hides what the tiers are for: an Elite's safety check exists to stop visibly bad
 * plays, which a human notices even when the game is won anyway. So we also count how often it
 * vetoes a play, and how often a Boss's search failed and fell back to the heuristic AI.
 */
public final class AiStats {
    /** Plays the hybrid safety check rejected because they left the AI worse off. */
    public static final AtomicInteger VETOES = new AtomicInteger();
    /** Top-level full-simulation decisions that threw and used the heuristic AI instead. */
    public static final AtomicInteger FALLBACKS = new AtomicInteger();
    /** Top-level full-simulation decisions made. */
    public static final AtomicInteger SIM_DECISIONS = new AtomicInteger();
    /** Decisions made by the heuristic AI because the turn's search budget was spent. */
    public static final AtomicInteger TURN_CAPPED = new AtomicInteger();

    private AiStats() {
    }

    public static void reset() {
        VETOES.set(0);
        FALLBACKS.set(0);
        SIM_DECISIONS.set(0);
        TURN_CAPPED.set(0);
    }
}
