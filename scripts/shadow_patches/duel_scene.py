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
# Relics and bosses: each enemy's own effect in every map duel (forge.campaign.enemies.EnemyEffects),
# and the Oracle of the Alpha playing the player's Power 9 (forge.campaign.enemies.PowerNine).
rep("""        humanPlayer = RegisteredPlayer.forVariants(playerCount, appliedVariants, playerDeck, null, false, null, null);
""", """        // FORGE-CAMPAIGN: the Oracle of the Alpha plays the player's Power 9 for this duel only
        // (forge.campaign.enemies.PowerNine; playerDeck is this duel's copy).
        List<PaperCard> claimedPower = new ArrayList<>();
        if (eventData == null && forge.campaign.enemies.EnemyEffects.takesPower9(enemy.getData())) {
            claimedPower = forge.campaign.enemies.PowerNine.takeFrom(playerDeck);
        }
        // FORGE-CAMPAIGN end
        humanPlayer = RegisteredPlayer.forVariants(playerCount, appliedVariants, playerDeck, null, false, null, null);
""")
rep("""        //Collect and add dungeon-wide effects.
""", """        // FORGE-CAMPAIGN: the enemy's own effect in every map duel, wherever it is met
        // (plane/world/enemy_effects.json, forge.campaign.enemies.EnemyEffects).
        if (eventData == null) {
            EffectData campaignEffect = forge.campaign.enemies.EnemyEffects.effectOf(enemy.getData());
            if (campaignEffect != null) {
                oppEffects.add(campaignEffect);
                if (campaignEffect.opponent != null)
                    playerEffects.add(campaignEffect.opponent);
            }
        }
        // FORGE-CAMPAIGN end
        //Collect and add dungeon-wide effects.
""")
rep("""            RegisteredPlayer aiPlayer = RegisteredPlayer.forVariants(playerCount, appliedVariants, deck, null, false, null, null);
""", """            // FORGE-CAMPAIGN: the Power 9 taken from the player join the first enemy's deck.
            if (i == 0 && !claimedPower.isEmpty()) {
                deck = (Deck) deck.copyTo(deck.getName());
                forge.campaign.enemies.PowerNine.giveTo(deck, claimedPower);
            }
            // FORGE-CAMPAIGN end
            RegisteredPlayer aiPlayer = RegisteredPlayer.forVariants(playerCount, appliedVariants, deck, null, false, null, null);
""")
# Planar Rifts (forge.campaign.rift.RiftRun): the rift deck, rift enemies' decks and life, no relics or gear, the result.
rep("""            forge.campaign.shop.DuelRewards.duelEnded(winner && !isArena && eventData == null);
""", """            forge.campaign.shop.DuelRewards.duelEnded(winner && !isArena && eventData == null);
            // FORGE-CAMPAIGN: a rift run picks a card after a win, and ends on a loss or the boss's fall.
            if (!isArena && eventData == null)
                forge.campaign.rift.RiftRun.duelEnded(winner, enemy.getData());
            // FORGE-CAMPAIGN end
""")
rep("""        else
            this.playerDeck = (Deck) Current.player().getSelectedDeck().copyTo("PlayerDeckCopy");
""", """        else
            this.playerDeck = (Deck) Current.player().getSelectedDeck().copyTo("PlayerDeckCopy");
        // FORGE-CAMPAIGN: in a Planar Rift the player's deck stays behind; the rift deck plays.
        if (eventData == null && !isArena && forge.campaign.rift.RiftRun.inRift())
            this.playerDeck = forge.campaign.rift.RiftRun.playerDeck();
        // FORGE-CAMPAIGN end
""")
rep("""        if (eventData == null || eventData.eventRules.allowsItems) {
            //Collect and add items effects first.""", """        // FORGE-CAMPAIGN: relics and gear stay behind in a Planar Rift.
        if ((eventData == null && !forge.campaign.rift.RiftRun.inRift()) || (eventData != null && eventData.eventRules.allowsItems)) {
            //Collect and add items effects first.""")
rep("""            if (deck == null) {
                isDeckMissing = true;""", """            // FORGE-CAMPAIGN: rift enemies play sealed decks of the rift's sets.
            if (eventData == null && !arenaBattleChallenge && forge.campaign.rift.RiftRun.inRift()) {
                Deck riftDeck = forge.campaign.rift.RiftRun.enemyDeck(currentEnemy);
                if (riftDeck != null && !riftDeck.getMain().isEmpty())
                    deck = riftDeck;
            }
            // FORGE-CAMPAIGN end
            if (deck == null) {
                isDeckMissing = true;""")
rep("""                    + forge.campaign.ai.CampaignAi.regionLifeBonus());
""", """                    + forge.campaign.ai.CampaignAi.regionLifeBonus());
            // FORGE-CAMPAIGN: rift enemies' life is the rift's (the boss keeps its own).
            if (eventData == null && forge.campaign.rift.RiftRun.inRift())
                aiPlayer.setStartingLife(forge.campaign.rift.RiftRun.enemyLife(currentEnemy));
            // FORGE-CAMPAIGN end
""")
p.write_text(HEADER + t, encoding="utf-8", newline="\n")
print("DuelScene.java patched")
