package forge.campaign.enemies;

import forge.StaticData;
import forge.deck.CardPool;
import forge.deck.Deck;
import forge.item.PaperCard;

import java.util.ArrayList;
import java.util.List;

/**
 * The Power 9, and the Oracle of the Alpha's claim on them.
 *
 * The player earns these one per colour region (a vault's pick, LegendaryChoice). Adventure's
 * config.json restrictedCards keeps them out of random loot and booster packs, so the vaults and
 * the Oracle are the only way in. Against an enemy with "takesPower9" (enemy_effects.json) our
 * DuelScene moves the player's copies into that enemy's deck for the duel: the duel's deck is
 * already a copy, so the collection and the saved deck keep them.
 */
public final class PowerNine {
    public static final List<String> NAMES = List.of(
            "Black Lotus", "Ancestral Recall", "Time Walk", "Timetwister",
            "Mox Pearl", "Mox Sapphire", "Mox Jet", "Mox Ruby", "Mox Emerald");

    /** What the player's deck is left with in place of each card taken. */
    public static final String REPLACEMENT = "Wastes";

    private PowerNine() {
    }

    public static boolean isPower(String name) {
        return NAMES.contains(name);
    }

    /** Removes the Power 9 from the deck's main section (each replaced by Wastes) and returns them. */
    public static List<PaperCard> takeFrom(Deck deck) {
        List<PaperCard> taken = new ArrayList<>();
        CardPool main = deck.getMain();
        for (PaperCard card : main.toFlatList()) {
            if (isPower(card.getName())) {
                taken.add(card);
                main.remove(card, 1);
            }
        }
        PaperCard wastes = StaticData.instance().getCommonCards().getCard(REPLACEMENT);
        if (wastes != null && !taken.isEmpty()) {
            main.add(wastes, taken.size());
        }
        return taken;
    }

    /** Adds cards to the deck's main section. */
    public static void giveTo(Deck deck, List<PaperCard> cards) {
        for (PaperCard c : cards) {
            deck.getMain().add(c);
        }
    }
}
