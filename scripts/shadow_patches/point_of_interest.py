"""Re-apply the FORGE-CAMPAIGN changes to a fresh copy of Forge's PointOfInterest.java (for rebases).

Copy the upstream original over the shadow, run this, then update its hash in shadows.tsv.
"""
from pathlib import Path

p = Path(__file__).resolve().parents[2] / "forge-gui-campaign/src/main/java/forge/adventure/pointofintrest/PointOfInterest.java"
t = p.read_text(encoding="utf-8").replace("\r\n", "\n")
HEADER = """// SHADOW COPY of forge-gui-mobile/src/forge/adventure/pointofintrest/PointOfInterest.java (Card-Forge/forge).
// It sits ahead of Forge's original on the classpath; the original is never edited.
// Changes are marked FORGE-CAMPAIGN. If upstream changes the original, scripts/check_shadows.py
// fails: re-copy the new original and re-apply the marked blocks.
"""
def rep(old, new):
    global t
    assert t.count(old) == 1, old[:80]
    t = t.replace(old, new)
rep("""        oldMapId="";
        Array<Sprite> textureAtlas = Config.instance().getPOISprites(this.data);""",
"""        oldMapId="";
        // FORGE-CAMPAIGN: upstream never restored questFlagsToActivate on load, so a point of
        // interest hidden behind a quest flag (a castle, one of our gates) showed up after any
        // reload. Take them from the data, so edits to points_of_interest.json also apply.
        questFlagsToActivate.clear();
        if (data != null && data.questFlagsToActivate != null) {
            questFlagsToActivate.addAll(Arrays.asList(data.questFlagsToActivate));
        }
        // FORGE-CAMPAIGN end
        Array<Sprite> textureAtlas = Config.instance().getPOISprites(this.data);""")
rep("""        for (DialogData.ActionData.QuestFlag flag : questFlagsToActivate) {
            if (Current.player().getQuestFlag(flag.key) < flag.val){
                return false;
            }
        }""",
"""        for (DialogData.ActionData.QuestFlag flag : questFlagsToActivate) {
            // FORGE-CAMPAIGN: a negative val means "active while the flag is below -val", so a gate
            // disappears once it is opened (upstream only has "active once the flag reaches val").
            int value = Current.player().getQuestFlag(flag.key);
            if (flag.val < 0 ? value >= -flag.val : value < flag.val) {
                return false;
            }
            // FORGE-CAMPAIGN end
        }""")
p.write_text(HEADER + t, encoding="utf-8", newline="\n")
print("PointOfInterest.java patched")
