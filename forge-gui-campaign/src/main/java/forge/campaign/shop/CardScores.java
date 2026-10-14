package forge.campaign.shop;

import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.utils.JsonReader;
import com.badlogic.gdx.utils.JsonValue;
import forge.adventure.util.Config;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * plane/card_scores.json (built by scripts/card_scores.py): the cards each region sells, with a
 * 0-100 score within the pool, and each card's type, mana value, colours and roles.
 */
public final class CardScores {
    public static final String FILE = "card_scores.json";
    /** Cards outside every pool (an old card in your deck) count as middling. */
    public static final int UNSCORED = 40;

    public record Card(String name, String type, int cmc, String colors, List<String> roles) {
        public boolean hasRole(String role) {
            return roles.contains(role);
        }
    }

    private static CardScores instance;
    private static boolean loaded;

    private final Map<String, Map<String, Integer>> pools = new HashMap<>();
    private final Map<String, Card> cards = new HashMap<>();

    public static synchronized CardScores get() {
        if (!loaded) {
            loaded = true;
            FileHandle file = Config.instance().getFile(FILE);
            if (file != null && file.exists()) {
                instance = new CardScores(new JsonReader().parse(file));
            } else {
                System.err.println("[campaign] " + FILE + " not found: merchants fall back to nothing");
            }
        }
        return instance;
    }

    private CardScores(JsonValue root) {
        for (JsonValue pool = root.get("pools").child; pool != null; pool = pool.next) {
            Map<String, Integer> scores = new LinkedHashMap<>();
            for (JsonValue c = pool.get("cards").child; c != null; c = c.next) {
                scores.put(c.name, c.asInt());
            }
            pools.put(pool.name, scores);
        }
        for (JsonValue c = root.get("cards").child; c != null; c = c.next) {
            List<String> roles = new ArrayList<>();
            for (JsonValue r = c.get("roles").child; r != null; r = r.next) {
                roles.add(r.asString());
            }
            cards.put(c.name, new Card(c.name, c.getString("type", ""), c.getInt("cmc", 0),
                    c.getString("colors", ""), Collections.unmodifiableList(roles)));
        }
    }

    /** Card name -> score, best first; empty for an unknown pool. */
    public Map<String, Integer> pool(String id) {
        return pools.getOrDefault(id, Collections.emptyMap());
    }

    public Card card(String name) {
        return cards.get(name);
    }

    /** The best score this card has in any pool, or UNSCORED. */
    public int score(String name) {
        int best = -1;
        for (Map<String, Integer> p : pools.values()) {
            Integer s = p.get(name);
            if (s != null && s > best) {
                best = s;
            }
        }
        return best < 0 ? UNSCORED : best;
    }
}
