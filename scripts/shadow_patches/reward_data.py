"""Re-apply the FORGE-CAMPAIGN changes to a fresh copy of Forge's RewardData.java (for rebases).

Copy the upstream original over the shadow, run this, then update its hash in shadows.tsv.
"""
from pathlib import Path

p = Path(__file__).resolve().parents[2] / "forge-gui-campaign/src/main/java/forge/adventure/data/RewardData.java"
t = p.read_text(encoding="utf-8").replace("\r\n", "\n")
HEADER = """// SHADOW COPY of forge-gui-mobile/src/forge/adventure/data/RewardData.java (Card-Forge/forge).
// It sits ahead of Forge's original on the classpath; the original is never edited.
// Changes are marked FORGE-CAMPAIGN. If upstream changes the original, scripts/check_shadows.py
// fails: re-copy the new original and re-apply the marked blocks.
"""


def rep(old, new):
    global t
    assert t.count(old) == 1, old[:80]
    t = t.replace(old, new)


rep("""    public String minDate;
""", """    public String minDate;
    // FORGE-CAMPAIGN: the card pool (plane/card_scores.json) a "campaignMerchant" reward sells from.
    public String pool;
    // FORGE-CAMPAIGN end
""")
rep("""        minDate          = rewardData.minDate;
""", """        minDate          = rewardData.minDate;
        pool             = rewardData.pool; // FORGE-CAMPAIGN
""")
rep("""                case "item":""", """                // FORGE-CAMPAIGN: a town's curated merchant (forge.campaign.shop.Merchant): offers
                // chosen for the player's deck from the region's pool. count = number of offers.
                case "campaignMerchant":
                    ret.addAll(forge.campaign.shop.Merchant.offers(this.pool, count, rewardRandom, isNoSell));
                    break;
                // FORGE-CAMPAIGN end
                case "item":""")
p.write_text(HEADER + t, encoding="utf-8", newline="\n")
print("RewardData.java patched")
