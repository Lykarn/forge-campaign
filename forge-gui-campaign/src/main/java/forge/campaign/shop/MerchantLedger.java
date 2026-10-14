package forge.campaign.shop;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;

/**
 * The offers each merchant stock was given, so a shop's list stays put until it restocks.
 *
 * Adventure regenerates a shop's cards every time the town loads, from a seed it stores per shop,
 * and marks bought cards by slot number. Our offers depend on the player's deck, so without this
 * the list (and which slot is "sold") would shift whenever the deck changed. Keyed by the first
 * number the shop's seed produces; saved in the world save under our own key (vanilla readers
 * ignore it), as plain JDK types so the save does not depend on our classes.
 */
public final class MerchantLedger {
    private static final HashMap<Long, ArrayList<String>> STOCKS = new HashMap<>();

    private MerchantLedger() {
    }

    public static synchronized List<String> get(long stock) {
        return STOCKS.get(stock);
    }

    public static synchronized void put(long stock, List<String> names) {
        STOCKS.put(stock, new ArrayList<>(names));
    }

    /** For World.save. */
    public static synchronized HashMap<Long, ArrayList<String>> snapshot() {
        return new HashMap<>(STOCKS);
    }

    /** For World.load and a new world (null clears). */
    @SuppressWarnings("unchecked")
    public static synchronized void restore(Object saved) {
        STOCKS.clear();
        if (saved instanceof HashMap<?, ?> map) {
            STOCKS.putAll((HashMap<Long, ArrayList<String>>) map);
        }
    }
}
