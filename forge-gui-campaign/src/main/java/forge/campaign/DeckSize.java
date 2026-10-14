package forge.campaign;

import forge.adventure.player.AdventurePlayer;
import forge.adventure.util.Current;
import forge.adventure.util.Config;
import forge.deck.Deck;

/**
 * Deck size rules (plan, "Deck size progression"): the minimum grows with the campaign, and a
 * bigger deck is a choice, not a tax.
 *
 *   minimum   40 at the start (Adventure's config.json minDeckSize), 50 after the first colour
 *             castle, 60 after the third (castle bosses advance the Ch1CastlesComplete flag).
 *             A deck below it gets Adventure's own padding of placeholder cards in duels.
 *   bonus     each full 10 cards above the minimum adds 2 starting life, up to two steps (+4).
 *
 * The current minimum is also written back into Adventure's config, so its deck checks agree.
 */
public final class DeckSize {
    public static final int LIFE_PER_STEP = 2;
    public static final int MAX_STEPS = 2;
    public static final String CASTLES_FLAG = "Ch1CastlesComplete";
    private static int base = -1;

    private DeckSize() {
    }

    public static synchronized int minimum() {
        if (base < 0) {
            int configured = Config.instance().getConfigData().minDeckSize;
            base = configured > 0 ? configured : 40;
        }
        AdventurePlayer player = Current.player();
        int castles = player == null ? 0 : player.getQuestFlag(CASTLES_FLAG);
        int min = base + (castles >= 3 ? 20 : castles >= 1 ? 10 : 0);
        Config.instance().getConfigData().minDeckSize = min;
        return min;
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
