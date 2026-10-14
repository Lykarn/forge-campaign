package forge.campaign.shop;

import com.badlogic.gdx.utils.Array;
import forge.StaticData;
import forge.adventure.player.AdventurePlayer;
import forge.adventure.util.Current;
import forge.adventure.util.Reward;
import forge.card.ColorSet;
import forge.deck.Deck;
import forge.item.PaperCard;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * A town's curated merchant (plan, Fix 3): a short list of offers chosen for the player's deck
 * from the region's pool, instead of dozens of random cards.
 *
 *   3 for your deck   in your colours, for the roles your deck is thinnest on, and better than
 *                     your weakest card in that role (the shop shows which card each would replace)
 *   2 region specials strong cards from the region's pool, any colour
 *   1 wildcard        an off-colour bomb (score 75+)
 *   + extras          more region cards when the shop asks for more than 6 (capitals ask for 8)
 *
 * Called from the "campaignMerchant" reward type in our RewardData shadow. The offers are fixed
 * for the shop's current stock: the first roll after a (re)stock is remembered in MerchantLedger
 * (saved with the world), so the list does not shift when the deck changes between visits.
 */
public final class Merchant {
    /** The roles a deck needs, most important first. */
    private static final String[] ROLES = {"removal", "threat", "draw", "evasion", "ramp", "trick"};
    private Merchant() {
    }

    /**
     * The swap preview under an offer in the shop, from the deck as it is now: "Swap: X" (it beats
     * X, your weakest card in a role it fills), "Adds card draw" (your deck has none), "Off-colour",
     * or "Region pick". Null for cards outside our pools (Adventure's own shops).
     */
    public static String preview(String cardName) {
        CardScores scores = CardScores.get();
        CardScores.Card card = scores == null ? null : scores.card(cardName);
        if (card == null) {
            return null;
        }
        DeckProfile deck = DeckProfile.of(Current.player(), scores);
        if (!deck.inColours(card.colors())) {
            return "Off-colour";
        }
        int score = scores.score(cardName);
        for (String role : ROLES) {
            if (!card.hasRole(role)) {
                continue;
            }
            String weakest = deck.weakestName(role);
            if (weakest == null) {
                return "Adds " + label(role);
            }
            if (deck.weakest(role) < score && !weakest.equals(cardName)) {
                return "Swap: " + weakest;
            }
        }
        return "Region pick";
    }

    public static Array<Reward> offers(String poolId, int count, Random random, boolean noSell) {
        Array<Reward> out = new Array<>();
        CardScores scores = CardScores.get();
        if (scores == null) {
            return out;
        }
        // The shop's seed decides this first number, so it names the stock: same seed, same list.
        long stock = random.nextLong();
        List<String> names = MerchantLedger.get(stock);
        if (names == null) {
            names = choose(scores, poolId, Math.max(6, count), new Random(stock));
            MerchantLedger.put(stock, names);
        }
        for (String name : names) {
            PaperCard card = StaticData.instance().getCommonCards().getCard(name);
            if (card != null) {
                out.add(new Reward(card, noSell));
            }
        }
        return out;
    }

    private static List<String> choose(CardScores scores, String poolId, int count, Random random) {
        Map<String, Integer> pool = scores.pool(poolId);
        DeckProfile deck = DeckProfile.of(Current.player(), scores);
        Map<String, String> picked = new LinkedHashMap<>();

        // 3 for your deck: thinnest roles first, each better than your weakest card in that role.
        List<String> roles = new ArrayList<>(List.of(ROLES));
        roles.sort(Comparator.comparingInt(deck::count));
        for (String role : roles) {
            if (picked.size() >= 3) {
                break;
            }
            int bar = deck.weakest(role);
            List<String> fits = new ArrayList<>();
            for (Map.Entry<String, Integer> e : pool.entrySet()) {
                CardScores.Card c = scores.card(e.getKey());
                if (c != null && c.hasRole(role) && deck.inColours(c.colors()) && e.getValue() > bar
                        && !picked.containsKey(e.getKey()) && !deck.has(e.getKey())) {
                    fits.add(e.getKey());
                }
            }
            String card = pickTop(fits, 5, random);
            if (card != null) {
                String weakest = deck.weakestName(role);
                picked.put(card, weakest == null ? "Your deck has no " + label(role) + " yet"
                        : "Replaces " + weakest + ", your weakest " + label(role));
            }
        }
        // 2 region specials: from the best third of the pool, any colour.
        List<String> top = new ArrayList<>(pool.keySet()).subList(0, Math.max(1, pool.size() / 3));
        addRandom(picked, top, 2, random, "Special of this region", deck);
        // 1 wildcard: an off-colour bomb.
        List<String> bombs = new ArrayList<>();
        for (Map.Entry<String, Integer> e : pool.entrySet()) {
            CardScores.Card c = scores.card(e.getKey());
            if (e.getValue() >= 75 && c != null && !deck.inColours(c.colors())) {
                bombs.add(e.getKey());
            }
        }
        addRandom(picked, bombs, 1, random, "Wildcard: worth a splash or a new deck", deck);
        // Extras (capitals): more from the top half of the pool.
        List<String> half = new ArrayList<>(pool.keySet()).subList(0, Math.max(1, pool.size() / 2));
        addRandom(picked, half, count - picked.size(), random, "Special of this region", deck);
        return new ArrayList<>(picked.keySet());
    }

    /** One of the best n (they come sorted best first), at random so towns differ. */
    private static String pickTop(List<String> sortedBest, int n, Random random) {
        if (sortedBest.isEmpty()) {
            return null;
        }
        return sortedBest.get(random.nextInt(Math.min(n, sortedBest.size())));
    }

    private static void addRandom(Map<String, String> picked, List<String> from, int n, Random random,
                                  String why, DeckProfile deck) {
        List<String> left = new ArrayList<>();
        for (String name : from) {
            if (!picked.containsKey(name) && !deck.has(name)) {
                left.add(name);
            }
        }
        for (int i = 0; i < n && !left.isEmpty(); i++) {
            picked.put(left.remove(random.nextInt(left.size())), why);
        }
    }

    private static String label(String role) {
        return switch (role) {
            case "removal" -> "removal";
            case "threat" -> "threat";
            case "draw" -> "card draw";
            case "evasion" -> "evasive creature";
            case "ramp" -> "mana source";
            case "trick" -> "combat trick";
            default -> role;
        };
    }

    /** What the player's selected deck has: colours, cards, and its weakest card per role. */
    static final class DeckProfile {
        private final String colours;
        private final Map<String, Integer> counts = new HashMap<>();
        private final Map<String, String> weakest = new HashMap<>();
        private final Map<String, Integer> weakestScore = new HashMap<>();
        private final java.util.Set<String> names = new java.util.HashSet<>();

        private DeckProfile(String colours) {
            this.colours = colours;
        }

        static DeckProfile of(AdventurePlayer player, CardScores scores) {
            StringBuilder colours = new StringBuilder();
            Deck deck = player == null ? null : player.getSelectedDeck();
            List<PaperCard> cards = new ArrayList<>();
            if (deck != null) {
                for (Map.Entry<PaperCard, Integer> e : deck.getMain()) {
                    if (!e.getKey().getRules().getType().isBasicLand()) {
                        cards.add(e.getKey());
                    }
                }
            }
            byte mask = 0;
            for (PaperCard c : cards) {
                mask |= c.getRules().getColor().getColor();
            }
            ColorSet set = ColorSet.fromMask(mask);
            colours.append(set.hasWhite() ? "W" : "").append(set.hasBlue() ? "U" : "").append(set.hasBlack() ? "B" : "")
                    .append(set.hasRed() ? "R" : "").append(set.hasGreen() ? "G" : "");
            DeckProfile p = new DeckProfile(colours.toString());
            for (PaperCard c : cards) {
                String name = c.getName();
                p.names.add(name);
                CardScores.Card info = scores.card(name);
                int score = scores.score(name);
                if (info == null) {
                    continue;
                }
                for (String role : info.roles()) {
                    p.counts.merge(role, 1, Integer::sum);
                    if (score < p.weakestScore.getOrDefault(role, Integer.MAX_VALUE)) {
                        p.weakestScore.put(role, score);
                        p.weakest.put(role, name);
                    }
                }
            }
            return p;
        }

        int count(String role) {
            return counts.getOrDefault(role, 0);
        }

        /** The score an offer must beat for this role: the weakest such card, or 0 if none. */
        int weakest(String role) {
            return weakestScore.getOrDefault(role, 0);
        }

        String weakestName(String role) {
            return weakest.get(role);
        }

        boolean has(String name) {
            return names.contains(name);
        }

        /** Colourless cards fit any deck; an empty deck accepts everything. */
        boolean inColours(String cardColours) {
            if (colours.isEmpty()) {
                return true;
            }
            for (char c : cardColours.toCharArray()) {
                if (colours.indexOf(c) < 0) {
                    return false;
                }
            }
            return true;
        }
    }
}
