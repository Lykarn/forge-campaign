package forge.campaign.relics;

import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.utils.JsonReader;
import com.badlogic.gdx.utils.JsonValue;
import forge.adventure.player.AdventurePlayer;
import forge.adventure.util.Config;
import forge.card.ColorSet;
import forge.deck.Deck;
import forge.item.PaperCard;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * The relic catalogue (plane/world/relics.json): which equipment items are relics, how rare, and
 * for which colours.
 *
 * A relic is an Adventure item in the "Relic" slot (plane/ui/inventory*.json add the slot) whose
 * effect puts one of our custom cards (res/adventure/common/custom_cards/campaign_*.txt) in the
 * command zone. Relics are never sold: castles offer a pick of CASTLE relics, champions of
 * CHAMPION relics (LegendaryChoice).
 */
public final class Relics {
    /** PLANAR: a Planar Rift's own relic, never offered by a choice. */
    public enum Tier { CHAMPION, CASTLE, PLANAR }

    /** colours: "" for any deck, else the colours a deck needs one of ("WU"...). */
    public record Relic(String item, Tier tier, String colours, String card) {
        boolean fits(String deckColours) {
            if (colours.isEmpty()) {
                return true;
            }
            for (char c : colours.toCharArray()) {
                if (deckColours.indexOf(c) >= 0) {
                    return true;
                }
            }
            return false;
        }
    }

    public static final String FILE = "world/relics.json";
    private static volatile Relics instance;

    private final List<Relic> relics;

    private Relics(List<Relic> relics) {
        this.relics = Collections.unmodifiableList(relics);
    }

    public static Relics get() {
        Relics r = instance;
        if (r == null) {
            synchronized (Relics.class) {
                if (instance == null) {
                    instance = load();
                }
                r = instance;
            }
        }
        return r;
    }

    public List<Relic> all() {
        return relics;
    }

    private static Relics load() {
        List<Relic> list = new ArrayList<>();
        FileHandle file = Config.instance().getFile(FILE);
        if (file != null && file.exists()) {
            for (JsonValue v = new JsonReader().parse(file).child; v != null; v = v.next) {
                if (v.name == null || v.name.startsWith("_")) {
                    continue;
                }
                list.add(new Relic(v.name, Tier.valueOf(v.getString("tier").toUpperCase()),
                        v.getString("colors", ""), v.getString("card", "")));
            }
        }
        return new Relics(list);
    }

    /** The colours of the player's selected deck, as "WUBRG" letters. */
    static String deckColours(AdventurePlayer player) {
        Deck deck = player.getSelectedDeck();
        if (deck == null) {
            return "";
        }
        byte mask = 0;
        for (Map.Entry<PaperCard, Integer> e : deck.getMain()) {
            mask |= e.getKey().getRules().getColor().getColor();
        }
        ColorSet set = ColorSet.fromMask(mask);
        return (set.hasWhite() ? "W" : "") + (set.hasBlue() ? "U" : "") + (set.hasBlack() ? "B" : "")
                + (set.hasRed() ? "R" : "") + (set.hasGreen() ? "G" : "");
    }
}
