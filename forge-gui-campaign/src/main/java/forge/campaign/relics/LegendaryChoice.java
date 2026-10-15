package forge.campaign.relics;

import com.badlogic.gdx.utils.Array;
import forge.StaticData;
import forge.adventure.data.ItemData;
import forge.adventure.player.AdventurePlayer;
import forge.adventure.util.Current;
import forge.adventure.data.ItemListData;
import forge.adventure.util.Reward;
import forge.campaign.enemies.PowerNine;
import forge.item.PaperCard;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Deque;
import java.util.List;
import java.util.Random;

/**
 * "Pick one" rewards for legendary loot: a relic after a castle or a champion, one of the Power 9
 * in a region's vault.
 *
 * Loot carries a marker item ("Choice: Relic", "Choice: Castle Relic", "Choice: Power 9";
 * plane/world/items.patch.json). Our RewardScene takes the markers out of the loot (queue), shows
 * the loot as usual, and when the player leaves it shows the choice instead of closing (next).
 * The options are drawn then, from what the player does not own yet, so two choices in a row
 * never offer the same thing twice.
 */
public final class LegendaryChoice {
    public static final String RELIC = "Choice: Relic";
    public static final String CASTLE_RELIC = "Choice: Castle Relic";
    public static final String POWER_9 = "Choice: Power 9";

    private static final Deque<String> PENDING = new ArrayDeque<>();

    private LegendaryChoice() {
    }

    public static boolean isMarker(Reward r) {
        return r != null && r.getType() == Reward.Type.Item && r.getItem() != null && isMarker(r.getItem().name);
    }

    public static boolean isMarker(String itemName) {
        return RELIC.equals(itemName) || CASTLE_RELIC.equals(itemName) || POWER_9.equals(itemName);
    }

    /** Takes the markers out of the loot and queues their choices; true if there were any. */
    public static synchronized boolean queue(Array<Reward> loot) {
        boolean any = false;
        for (int i = 0; i < loot.size; ) {
            Reward r = loot.get(i);
            if (isMarker(r)) {
                // In loot order: the choices come in the order the loot lists them.
                for (int n = 0; n < Math.max(1, r.getCount()); n++) {
                    PENDING.addLast(r.getItem().name);
                }
                loot.removeIndex(i);
                any = true;
            } else {
                i++;
            }
        }
        return any;
    }

    /** The next queued choice's options, or null when none is left (an empty choice is skipped). */
    public static synchronized Array<Reward> next() {
        while (!PENDING.isEmpty()) {
            Array<Reward> options = options(PENDING.removeFirst(), new Random());
            if (options.size > 0) {
                return options;
            }
        }
        return null;
    }

    static Array<Reward> options(String marker, Random random) {
        Array<Reward> out = new Array<>();
        AdventurePlayer player = Current.player();
        if (POWER_9.equals(marker)) {
            for (String name : PowerNine.NAMES) {
                PaperCard card = StaticData.instance().getCommonCards().getCard(name);
                if (card != null && (player == null || player.getCollectionCards(true).count(card) == 0)) {
                    out.add(new Reward(card));
                }
            }
            return out;
        }
        Relics.Tier tier = CASTLE_RELIC.equals(marker) ? Relics.Tier.CASTLE : Relics.Tier.CHAMPION;
        List<Relics.Relic> pool = new ArrayList<>();
        for (Relics.Relic relic : Relics.get().all()) {
            if (relic.tier() == tier && (player == null || player.countItem(relic.item()) == 0)) {
                pool.add(relic);
            }
        }
        // Three relics; at least one for the colours of the player's deck when there is one.
        Collections.shuffle(pool, random);
        String deckColours = player == null ? "" : Relics.deckColours(player);
        pool.sort((a, b) -> Boolean.compare(!a.fits(deckColours), !b.fits(deckColours)));
        List<Relics.Relic> picked = new ArrayList<>();
        if (!pool.isEmpty()) {
            picked.add(pool.remove(0));
        }
        Collections.shuffle(pool, random);
        while (picked.size() < 3 && !pool.isEmpty()) {
            picked.add(pool.remove(0));
        }
        for (Relics.Relic relic : picked) {
            ItemData item = ItemListData.getItem(relic.item());
            if (item != null) {
                out.add(new Reward(item));
            }
        }
        return out;
    }
}
