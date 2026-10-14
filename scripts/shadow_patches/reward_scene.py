"""Re-apply the FORGE-CAMPAIGN changes to a fresh copy of Forge's RewardScene.java (for rebases).

Copy the upstream original over the shadow, run this, then update its hash in shadows.tsv.
"""
from pathlib import Path

p = Path(__file__).resolve().parents[2] / "forge-gui-campaign/src/main/java/forge/adventure/scene/RewardScene.java"
t = p.read_text(encoding="utf-8").replace("\r\n", "\n")
HEADER = """// SHADOW COPY of forge-gui-mobile/src/forge/adventure/scene/RewardScene.java (Card-Forge/forge).
// It sits ahead of Forge's original on the classpath; the original is never edited.
// Changes are marked FORGE-CAMPAIGN. If upstream changes the original, scripts/check_shadows.py
// fails: re-copy the new original and re-apply the marked blocks.
"""


def rep(old, new):
    global t
    assert t.count(old) == 1, old[:80]
    t = t.replace(old, new)


# A won map duel's loot becomes a pick of 1 from 3 (forge.campaign.shop.DuelRewards).
rep("""    public void loadRewards(Array<Reward> newRewards, Type type, ShopActor shopActor) {
        // Merge Gold and Shards rewards into single entries""",
    """    public void loadRewards(Array<Reward> newRewards, Type type, ShopActor shopActor) {
        // FORGE-CAMPAIGN: loot from a won map duel: gold, shards and items are granted now and the
        // cards become a choice of three (forge.campaign.shop.DuelRewards); chests stay as they are.
        if (type == Type.Loot && forge.campaign.shop.DuelRewards.takeDuelWin()) {
            Array<Reward> choices = forge.campaign.shop.DuelRewards.choose(newRewards);
            if (choices != null && choices.size > 0) {
                loadSelectableRewards(choices, Type.RewardChoice, 1);
                return;
            }
        }
        // FORGE-CAMPAIGN end
        // Merge Gold and Shards rewards into single entries""")
# The swap preview under each merchant offer (forge.campaign.shop.Merchant.preview).
rep("""            if (collectionPool != null && Reward.Type.Card.equals(reward.getType()))
                setText("[%75][+GoldCoin] " + price + "\\n" + Forge.getLocalizer().getMessage("lblOwned") + ": " + collectionPool.count(reward.getCard()));""",
    """            if (collectionPool != null && Reward.Type.Card.equals(reward.getType())) {
                // FORGE-CAMPAIGN: our merchants' offers say what they would do for the deck
                // ("Swap: X", "Adds card draw"...); other shops keep the owned count alone.
                String why = forge.campaign.shop.Merchant.preview(reward.getCard().getName());
                String owned = Forge.getLocalizer().getMessage("lblOwned") + ": " + collectionPool.count(reward.getCard());
                setText(why == null ? "[%75][+GoldCoin] " + price + "\\n" + owned
                        : "[%75][+GoldCoin] " + price + "  " + owned + "\\n[%65]" + why);
                // FORGE-CAMPAIGN end
            }""")
p.write_text(HEADER + t, encoding="utf-8", newline="\n")
print("RewardScene.java patched")
