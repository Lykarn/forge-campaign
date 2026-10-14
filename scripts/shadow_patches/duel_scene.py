"""Re-apply the FORGE-CAMPAIGN changes to a fresh copy of Neo Forge's DuelScene.java (for rebases).

Copy Neo Forge's forge-gui-neo/src/main/java/forge/adventure/scene/DuelScene.java over the shadow,
run this, then update its hash in shadows.tsv.
"""
from pathlib import Path

p = Path(__file__).resolve().parents[2] / "forge-gui-campaign/src/main/java/forge/adventure/scene/DuelScene.java"
t = p.read_text(encoding="utf-8").replace("\r\n", "\n")
HEADER = """// SHADOW COPY of Neo Forge's forge-gui-neo/src/main/java/forge/adventure/scene/DuelScene.java,
// itself Neo Forge's shadow of Forge's forge-gui-mobile/src/forge/adventure/scene/DuelScene.java.
// It sits ahead of both on the classpath; neither original is edited.
// Changes are marked FORGE-CAMPAIGN. If Neo Forge changes its copy, scripts/check_shadows.py
// fails: re-copy Neo Forge's new file and re-apply the marked blocks.
"""


def rep(old, new):
    global t
    assert t.count(old) == 1, old[:80]
    t = t.replace(old, new)


# Phase 1: enemy tiers.
rep("""            LobbyPlayer enemyPlayer = GamePlayerUtil.createAiPlayer(currentEnemy.getName(), selectAI(currentEnemy.ai));
""", """            // FORGE-CAMPAIGN: the enemy's tier picks its AI profile, simulation and time budget
            // (forge.campaign.ai.EnemyTiers). Was: GamePlayerUtil.createAiPlayer(currentEnemy.getName(), selectAI(currentEnemy.ai))
            LobbyPlayer enemyPlayer = forge.campaign.ai.CampaignAi.createEnemyPlayer(currentEnemy, selectAI(currentEnemy.ai));
            // FORGE-CAMPAIGN end
""")
# Phase 2: deck size bonus: +2 starting life per full 10 cards above the minimum (forge.campaign.DeckSize).
rep("""        humanPlayer.setStartingLife(eventData != null ? eventData.eventRules.startingLife : advPlayer.getLife());""",
    """        // FORGE-CAMPAIGN: + forge.campaign.DeckSize.lifeBonus (bigger decks start with more life).
        humanPlayer.setStartingLife(eventData != null ? eventData.eventRules.startingLife
                : advPlayer.getLife() + forge.campaign.DeckSize.lifeBonus(playerDeck));""")
# Phase 2: a won map duel's loot becomes a pick of 1 from 3 (forge.campaign.shop.DuelRewards).
rep("""            Current.player().getStatistic().setResult(enemyName, winner);
""", """            Current.player().getStatistic().setResult(enemyName, winner);
            // FORGE-CAMPAIGN: tell RewardScene this loot is a won map duel's (pick 1 of 3).
            forge.campaign.shop.DuelRewards.duelEnded(winner && !isArena && eventData == null);
""")
# Phase 3: enemies in later regions start with more life (RegionLayout enemyLifeBonus).
rep("""            aiPlayer.setStartingLife(eventData != null ? eventData.eventRules.startingLife : Math.round((float) currentEnemy.life * advPlayer.getDifficulty().enemyLifeFactor));""",
    """            // FORGE-CAMPAIGN: + the region's enemy life bonus (forge.campaign.ai.CampaignAi.regionLifeBonus).
            aiPlayer.setStartingLife(eventData != null ? eventData.eventRules.startingLife
                    : Math.round((float) currentEnemy.life * advPlayer.getDifficulty().enemyLifeFactor)
                    + forge.campaign.ai.CampaignAi.regionLifeBonus());""")
# Phase 3: the minimum deck size grows with the castles beaten (forge.campaign.DeckSize).
rep("""        int minDeckSize = format == DeckFormat.Adventure ? Config.instance().getConfigData().minDeckSize : format.getMainRange().getMinimum();""",
    """        // FORGE-CAMPAIGN: 40, then 50 after the first castle, 60 after the third (forge.campaign.DeckSize).
        int minDeckSize = format == DeckFormat.Adventure ? forge.campaign.DeckSize.minimum() : format.getMainRange().getMinimum();""")
p.write_text(HEADER + t, encoding="utf-8", newline="\n")
print("DuelScene.java patched")
