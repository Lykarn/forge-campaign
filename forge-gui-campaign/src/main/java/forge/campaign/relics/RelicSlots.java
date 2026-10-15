package forge.campaign.relics;

import forge.adventure.data.ItemData;
import forge.adventure.player.AdventurePlayer;
import forge.campaign.DeckSize;

import java.util.List;
import java.util.Map;

/**
 * Relic slots that grow with the campaign (Rory, 2026-10-15: Emrakul should take "multiple
 * synergistic relics"). A relic item names its family's first slot ("Relic" or "Trinket");
 * the family's other slots open with castles beaten:
 *   Relic, Trinket        from the start
 *   Relic2, Trinket2      after the second castle
 *   Relic3                after the fourth
 *   Relic4                once every Planar Rift is won (forge.campaign.rift.RiftRun)
 *
 * Adventure equips an item into the slot its data names, keyed by slot name (AdventurePlayer
 * keeps a slot -> item map, saved as is, and every duel applies all equipped items). So our
 * InventoryScene only chooses the slot: it sets the item's equipmentSlot to the slot to use just
 * for the equip call (slotFor), and lists a family's items under each of its slots.
 */
public final class RelicSlots {
    private static final Map<String, List<String>> FAMILIES = Map.of(
            "Relic", List.of("Relic", "Relic2", "Relic3", "Relic4"),
            "Trinket", List.of("Trinket", "Trinket2"));
    private static final Map<String, Integer> CASTLES_NEEDED = Map.of("Relic2", 2, "Trinket2", 2, "Relic3", 4);

    private RelicSlots() {
    }

    /** The family a slot belongs to ("Relic2" -> "Relic"); any other slot is its own. */
    public static String family(String slot) {
        if (slot == null) {
            return null;
        }
        for (Map.Entry<String, List<String>> e : FAMILIES.entrySet()) {
            if (e.getValue().contains(slot)) {
                return e.getKey();
            }
        }
        return slot;
    }

    public static boolean isOpen(AdventurePlayer player, String slot) {
        if ("Relic4".equals(slot)) {
            return forge.campaign.rift.RiftRun.allWon();
        }
        Integer castles = CASTLES_NEEDED.get(slot);
        return castles == null || (player != null && player.getQuestFlag(DeckSize.CASTLES_FLAG) >= castles);
    }

    /** The slot the item is equipped in (one of its family's), else its own slot name. */
    public static String equippedSlot(AdventurePlayer player, ItemData item) {
        for (String slot : FAMILIES.getOrDefault(item.equipmentSlot, List.of(item.equipmentSlot))) {
            Long id = player.itemInSlot(slot);
            if (id != null && id.equals(item.longID)) {
                return slot;
            }
        }
        return item.equipmentSlot;
    }

    /**
     * Where an equip click puts (or takes off) the item: its current slot if equipped; else the
     * selected slot when it is an open slot of the family; else the family's first open, empty
     * slot; else the first slot (replacing what is there).
     */
    public static String slotFor(AdventurePlayer player, ItemData item, String selectedSlot) {
        List<String> slots = FAMILIES.get(item.equipmentSlot);
        if (slots == null) {
            return item.equipmentSlot;
        }
        String current = equippedSlot(player, item);
        Long id = player.itemInSlot(current);
        if (id != null && id.equals(item.longID)) {
            return current;
        }
        if (selectedSlot != null && slots.contains(selectedSlot) && isOpen(player, selectedSlot)) {
            return selectedSlot;
        }
        for (String slot : slots) {
            if (isOpen(player, slot) && player.itemInSlot(slot) == null) {
                return slot;
            }
        }
        return slots.get(0);
    }
}
