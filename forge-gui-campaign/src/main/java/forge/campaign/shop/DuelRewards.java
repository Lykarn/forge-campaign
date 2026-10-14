package forge.campaign.shop;

import com.badlogic.gdx.utils.Array;
import forge.StaticData;
import forge.adventure.player.AdventurePlayer;
import forge.adventure.util.Current;
import forge.adventure.util.Reward;
import forge.adventure.world.World;
import forge.adventure.world.WorldSave;
import forge.campaign.world.RegionLayout;
import forge.item.PaperCard;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * Pick 1 of 3 after a won duel (plan, Fix 3: "instead of random card dumps").
 *
 * Our DuelScene shadow calls duelEnded() when a map duel ends; RewardScene (shadowed) asks
 * takeDuelWin() when loot arrives, and if that loot came from a won duel it calls choose():
 * gold, shards and items go to the player at once, and the cards become a choice of three: the
 * two best cards of the enemy's loot by card score, and one strong card from the pool of the
 * region the player is in. Treasure chests and quest rewards are not duels and stay as they are.
 */
public final class DuelRewards {
    /** When the last map duel was won (0 = none): the mark expires, so a later chest is not mistaken for it. */
    private static volatile long wonAt;
    private static final long VALID_MS = 20_000;

    private DuelRewards() {
    }

    /** From DuelScene: won is true only for a won map duel (not arenas or events). */
    public static void duelEnded(boolean won) {
        wonAt = won ? System.currentTimeMillis() : 0;
    }

    /** True once after a won duel; clears the mark. */
    public static boolean takeDuelWin() {
        boolean won = wonAt != 0 && System.currentTimeMillis() - wonAt < VALID_MS;
        wonAt = 0;
        return won;
    }

    /**
     * Grants the non-card loot now and returns the three cards to choose from; null (and nothing
     * granted) when the loot holds no cards, so the usual loot screen shows it.
     */
    public static Array<Reward> choose(Array<Reward> loot) {
        AdventurePlayer player = Current.player();
        CardScores scores = CardScores.get();
        boolean anyCard = false;
        for (Reward r : new Array.ArrayIterator<>(loot)) {
            anyCard |= r.getType() == Reward.Type.Card && r.getCard() != null;
        }
        if (!anyCard) {
            return null;
        }
        List<PaperCard> cards = new ArrayList<>();
        for (Reward r : new Array.ArrayIterator<>(loot)) {
            if (r.getType() == Reward.Type.Card && r.getCard() != null) {
                if (!r.getCard().getRules().getType().isBasicLand()) {
                    cards.add(r.getCard());
                }
            } else {
                player.addReward(r);
            }
        }
        Array<Reward> choices = new Array<>();
        if (scores == null) {
            for (int i = 0; i < Math.min(3, cards.size()); i++) {
                choices.add(new Reward(cards.get(i)));
            }
            return choices;
        }
        cards.sort(Comparator.comparingInt((PaperCard c) -> -scores.score(c.getName())));
        LinkedHashSet<String> names = new LinkedHashSet<>();
        for (PaperCard c : cards) {
            if (names.size() < 2) {
                names.add(c.getName());
            }
        }
        // The region's card: in the player's colours, good but not a bomb (score 45-80, no
        // planeswalkers), and only sometimes rare. The first version took the pool's best third,
        // which in Magic 2010 meant an off-colour mythic planeswalker after every win (playtest).
        Map<String, Integer> pool = scores.pool(regionPool());
        Merchant.DeckProfile deck = Merchant.DeckProfile.of(player, scores);
        Random random = new Random();
        List<String> fits = new ArrayList<>();
        for (Map.Entry<String, Integer> e : pool.entrySet()) {
            CardScores.Card c = scores.card(e.getKey());
            if (c == null || e.getValue() < 45 || e.getValue() > 80 || "Planeswalker".equals(c.type())
                    || !deck.inColours(c.colors()) || names.contains(e.getKey())) {
                continue;
            }
            PaperCard pc = StaticData.instance().getCommonCards().getCard(e.getKey());
            boolean rare = pc != null && pc.getRarity() != null
                    && (pc.getRarity().ordinal() >= forge.card.CardRarity.Rare.ordinal()
                        && pc.getRarity() != forge.card.CardRarity.Special);
            if (!rare || random.nextInt(100) < 15) {
                fits.add(e.getKey());
            }
        }
        if (names.size() < 3 && !fits.isEmpty()) {
            names.add(fits.get(random.nextInt(fits.size())));
        }
        for (PaperCard c : cards) { // a small pool or an unlucky draw: fill from the loot
            if (names.size() < 3) {
                names.add(c.getName());
            }
        }
        for (String name : names) {
            PaperCard card = StaticData.instance().getCommonCards().getCard(name);
            if (card != null) {
                choices.add(new Reward(card));
            }
        }
        return choices;
    }

    /** The card pool of the region at the player's position (the hub's if none). */
    private static String regionPool() {
        RegionLayout layout = RegionLayout.get();
        if (layout == null || WorldSave.getCurrentSave() == null) {
            return "hub";
        }
        World world = WorldSave.getCurrentSave().getWorld();
        AdventurePlayer player = Current.player();
        int x = (int) (player.getWorldPosX() / world.getTileSize());
        int mapY = world.getHeightInTiles() - 1 - (int) (player.getWorldPosY() / world.getTileSize());
        int region = world.campaignRegionAt(x, mapY);
        if (region < 0) {
            return "hub";
        }
        String pool = layout.regions.get(region).pool();
        return pool == null ? "hub" : pool;
    }
}
