package forge.campaign.ai;

import forge.LobbyPlayer;
import forge.adventure.data.EnemyData;
import forge.ai.AIOption;
import forge.gui.GuiBase;
import forge.player.GamePlayerUtil;
import forge.util.MyRandom;

import java.util.EnumSet;
import java.util.Set;

/** Creates Adventure enemies with their tier's AI. Called from our shadowed DuelScene. */
public final class CampaignAi {
    private CampaignAi() {
    }

    /**
     * The AI player for one enemy: its tier's profile and simulation, and the simulation budget.
     *
     * @param explicitProfile the profile enemies.json names for this enemy ("Reckless"...), already
     *                        mapped by DuelScene.selectAI; it wins over the tier's profile when set
     */
    public static LobbyPlayer createEnemyPlayer(EnemyData enemy, String explicitProfile) {
        forge.campaign.SelfCheck.maybeRun(); // only with -Dcampaign.selfcheck (scripts/test_package.py)
        EnemyTiers.Settings settings = EnemyTiers.get().settingsFor(enemy);
        String profile = explicitProfile != null && !explicitProfile.isEmpty() ? explicitProfile : settings.profile();
        System.out.println("[campaign] enemy " + enemy.getName() + ": " + settings
                + (profile.equals(settings.profile()) ? "" : ", profile " + profile + " from enemies.json"));
        return createAiPlayer(enemy.getName(), profile, settings);
    }

    /** Shared with the benchmark, so it plays exactly the AI the Adventure would. */
    public static LobbyPlayer createAiPlayer(String name, String profile, EnemyTiers.Settings settings) {
        Set<AIOption> options = settings.simulation() == null ? null : EnumSet.of(settings.simulation());
        if (settings.simulation() != null) {
            SimulationBudget.setMillis(settings.budgetMs());
            SimulationBudget.setTurnMillis(settings.turnBudgetMs());
        }
        int avatars = GuiBase.getInterface().getAvatarCount();
        int sleeves = GuiBase.getInterface().getSleevesCount();
        return GamePlayerUtil.createAiPlayer(name,
                avatars == 0 ? 0 : MyRandom.getRandom().nextInt(avatars),
                sleeves == 0 ? 0 : MyRandom.getRandom().nextInt(sleeves),
                options, profile);
    }
}
