// SHADOW COPY of forge-ai/src/main/java/forge/ai/simulation/OnePlaySafetyChecker.java (Card-Forge/forge).
// It sits ahead of Forge's original on the classpath; the original is never edited.
// Changes are marked FORGE-CAMPAIGN. If upstream changes the original, scripts/check_shadows.py
// fails: re-copy the new original and re-apply the marked blocks.
package forge.ai.simulation;

import forge.ai.simulation.GameStateEvaluator.Score;
import forge.game.card.Card;
import forge.game.player.Player;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;

public final class OnePlaySafetyChecker {
    private static final ThreadLocal<Boolean> CHECKING = ThreadLocal.withInitial(() -> false);

    public static boolean isAcceptable(Player player, SpellAbility sa) {
        // Forge keeps the parent ability on the stack while it resolves. Score actions offered
        // during that resolution incrementally; priority responses need two full stack-resolution
        // branches and are not supported yet.
        if (sa == null || CHECKING.get()
                || (!player.getGame().getStack().isEmpty() && !player.getGame().getStack().isResolving())) {
            return true;
        }

        CHECKING.set(true);
        try {
            SimulationController controller = new SimulationController(new Score(0), 0);
            GameSimulator simulator = new GameSimulator(controller, player.getGame(), player, null);
            Score originalScore = simulator.getScoreForOrigGame();
            Score resultScore = simulator.simulateSpellAbility(sa);

            // desperate plays are ok if next combat was already likely to kill AI
            // FORGE-CAMPAIGN: count vetoes for the benchmark (forge.campaign.ai.AiStats).
            boolean acceptable = resultScore.value == Integer.MIN_VALUE
                    || resultScore.value >= (long) originalScore.value - expectedCardScoreLoss(player, sa, simulator);
            if (!acceptable) {
                forge.campaign.ai.AiStats.VETOES.incrementAndGet();
            }
            return acceptable;
            // FORGE-CAMPAIGN end
        // FORGE-CAMPAIGN: copying the game can throw (GameCopier "Couldn't map <card>"), and this check
        // runs outside any error handling (land plays), so it ended the duel. A check that cannot
        // run vetoes nothing: the heuristic AI's choice stands.
        } catch (RuntimeException e) {
            System.err.println("[campaign] safety check skipped (" + e + ")");
            return true;
        // FORGE-CAMPAIGN end
        } finally {
            CHECKING.remove();
        }
    }

    // sometimes simulation might not see the effect of some heuristics directly, so at least negate any card disadvantage
    private static int expectedCardScoreLoss(Player player, SpellAbility sa, GameSimulator simulator) {
        Card source = sa.getHostCard();
        if (source == null || !source.isInZone(ZoneType.Hand)) {
            return 0;
        }
        Card simulatedSource = simulator.getGameCopier().find(source);
        if (simulatedSource.isInZone(ZoneType.Hand)) {
            return 0;
        }
        // Match GameStateEvaluator: excess cards are worth one point, other hand cards five.
        return !player.isUnlimitedHandSize() && player.getCardsIn(ZoneType.Hand).size() > player.getMaxHandSize() ? 1 : 5;
    }
}
