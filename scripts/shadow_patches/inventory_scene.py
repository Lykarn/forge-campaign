"""Re-apply the FORGE-CAMPAIGN changes to a fresh copy of Forge's InventoryScene.java (for rebases).

Copy the upstream original over the shadow, run this, then update its hash in shadows.tsv.
"""
from pathlib import Path

p = Path(__file__).resolve().parents[2] / "forge-gui-campaign/src/main/java/forge/adventure/scene/InventoryScene.java"
t = p.read_text(encoding="utf-8").replace("\r\n", "\n")
HEADER = """// SHADOW COPY of forge-gui-mobile/src/forge/adventure/scene/InventoryScene.java (Card-Forge/forge).
// It sits ahead of Forge's original on the classpath; the original is never edited.
// Changes are marked FORGE-CAMPAIGN. If upstream changes the original, scripts/check_shadows.py
// fails: re-copy the new original and re-apply the marked blocks.
"""


def rep(old, new):
    global t
    assert t.count(old) == 1, old[:80]
    t = t.replace(old, new)


# Relic slots that open with castles (forge.campaign.relics.RelicSlots): a relic family's items
# are listed under each of its slots, and equipping picks the slot.
rep("""            if (selectedSlot != null && !selectedSlot.equals(item.equipmentSlot)) {
                continue;
            }""", """            // FORGE-CAMPAIGN: Relic2 and Relic3 list the Relic family's items (forge.campaign.relics.RelicSlots).
            if (selectedSlot != null && !forge.campaign.relics.RelicSlots.family(selectedSlot).equals(item.equipmentSlot)) {
                continue;
            }
            // FORGE-CAMPAIGN end""")
rep("""                    Long id = Current.player().itemInSlot(data.equipmentSlot);
                    if (id != null && id.equals(data.longID) && data.isEquipped) {""",
    """                    // FORGE-CAMPAIGN: a relic may sit in any slot of its family.
                    Long id = Current.player().itemInSlot(forge.campaign.relics.RelicSlots.equippedSlot(Current.player(), data));
                    // FORGE-CAMPAIGN end
                    if (id != null && id.equals(data.longID) && data.isEquipped) {""")
rep("""        if (data == null) return;
        Current.player().equip(data);
        updateInventory();""", """        if (data == null) return;
        // FORGE-CAMPAIGN: equip into the slot RelicSlots picks (the item's own slot for other items),
        // then give the item back its family slot name.
        String family = data.equipmentSlot;
        data.equipmentSlot = forge.campaign.relics.RelicSlots.slotFor(Current.player(), data, selectedSlot);
        Current.player().equip(data);
        data.equipmentSlot = family;
        // FORGE-CAMPAIGN end
        updateInventory();""")
rep("""    public void enter() {
        selectedSlot = null;
        for (Button slot : equipmentSlots.values()) {
            removeSlotBorder(slot);
            slot.setChecked(false);
        }""", """    public void enter() {
        selectedSlot = null;
        for (Button slot : equipmentSlots.values()) {
            removeSlotBorder(slot);
            slot.setChecked(false);
        }
        // FORGE-CAMPAIGN: relic slots not yet opened by castles are hidden.
        for (Map.Entry<String, Button> slot : equipmentSlots.entrySet()) {
            slot.getValue().setVisible(forge.campaign.relics.RelicSlots.isOpen(Current.player(), slot.getKey()));
        }
        // FORGE-CAMPAIGN end""")
p.write_text(HEADER + t, encoding="utf-8", newline="\n")
print("InventoryScene.java patched")
