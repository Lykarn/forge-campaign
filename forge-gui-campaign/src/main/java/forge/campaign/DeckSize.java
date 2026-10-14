package forge.campaign;

import forge.adventure.util.Config;
import forge.deck.Deck;

/**
 * Deck size rules (plan, "Deck size progression"): a bigger deck is a choice, not a tax.
 *
 * Each full 10 cards above the current minimum add 2 starting life in duels, up to two
 * breakpoints (+4). The minimum is Adventure's own (config.json minDeckSize, 40); rising it at
 * castles comes with the later regions.
 */
public final class DeckSize {
    public static final int LIFE_PER_STEP = 2;
    public static final int MAX_STEPS = 2;

    private DeckSize() {
    }

    public static int minimum() {
        int min = Config.instance().getConfigData().minDeckSize;
        return min > 0 ? min : 40;
    }

    /** Extra starting life for this deck. */
    public static int lifeBonus(Deck deck) {
        if (deck == null) {
            return 0;
        }
        int size = deck.getMain().countAll();
        int steps = Math.min(MAX_STEPS, Math.max(0, (size - minimum()) / 10));
        return steps * LIFE_PER_STEP;
    }
}
