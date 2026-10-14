package forge.campaign;

import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.graphics.Pixmap;
import com.badlogic.gdx.graphics.PixmapIO;
import com.badlogic.gdx.utils.Array;
import forge.StaticData;
import forge.adventure.player.AdventurePlayer;
import forge.adventure.util.Current;
import forge.adventure.util.Reward;
import forge.adventure.world.World;
import forge.adventure.world.WorldSave;
import forge.campaign.shop.DuelRewards;
import forge.campaign.shop.Merchant;
import forge.campaign.world.Fog;
import forge.campaign.world.RegionLayout;

import java.io.File;
import java.util.Random;

/**
 * An in-game check of the region slice, for scripts/test_package.py: with
 * -Dcampaign.selfcheck=<folder>, the first enemy created (Neo Forge's anteduel self-test makes a
 * new world and starts a duel) runs these checks once and logs "[campaign] selfcheck PASS|FAIL".
 * It writes the fogged map before and after the White watchtower to the folder.
 */
public final class SelfCheck {
    private static boolean done;
    private static int failures;

    private SelfCheck() {
    }

    public static synchronized void maybeRun() {
        String folder = System.getProperty("campaign.selfcheck");
        if (done || folder == null || folder.isEmpty() || WorldSave.getCurrentSave() == null) {
            return;
        }
        done = true;
        try {
            run(new File(folder));
        } catch (Throwable t) {
            check("selfcheck ran without an error", false, t.toString());
            t.printStackTrace();
        }
        System.out.println("[campaign] selfcheck " + (failures == 0 ? "PASS" : "FAIL (" + failures + ")"));
    }

    private static void check(String what, boolean ok, String detail) {
        if (!ok) {
            failures++;
        }
        System.out.println("[campaign] selfcheck " + (ok ? "ok   " : "FAIL ") + what + (detail == null ? "" : ": " + detail));
    }

    private static void run(File folder) {
        folder.mkdirs();
        RegionLayout layout = RegionLayout.get();
        check("the plane has a region layout", layout != null, null);
        if (layout == null) {
            return;
        }
        World world = WorldSave.getCurrentSave().getWorld();
        AdventurePlayer player = Current.player();

        // Gates: the hub-to-White pass is shut until its quest flag is set.
        RegionLayout.Pass pass = layout.passes.stream().filter(p -> p.gateFlag() != null).findFirst().orElse(null);
        check("a gated pass exists", pass != null, null);
        if (pass != null) {
            int worldY = world.getHeightInTiles() - pass.y() - 1;
            check("the gate blocks before it is opened", world.isColliding(pass.x(), worldY), null);
            player.setQuestFlag(pass.gateFlag(), 1);
            check("the gate lets you through once opened", !world.isColliding(pass.x(), worldY), null);
            player.setQuestFlag(pass.gateFlag(), 0);
        }

        // Fog: the hub shows from the start, White only after its watchtower.
        int hub = indexOf(layout, "hub");
        int white = indexOf(layout, "white");
        boolean[] before = Fog.revealed(layout);
        check("the hub is revealed at the start", hub >= 0 && before[hub], null);
        check("White is dark at the start", white >= 0 && !before[white], null);
        write(world.getBiomeImage(), new File(folder, "fog_start.png"));
        RegionLayout.Region w = layout.regions.get(white);
        player.setQuestFlag(w.towerFlag(), 1);
        check("White is revealed after its watchtower", Fog.revealed(layout)[white], null);
        write(world.getBiomeImage(), new File(folder, "fog_after_tower.png"));
        player.setQuestFlag(w.towerFlag(), 0);

        // Merchant: offers for the starter deck from White's pool, with their previews.
        Array<Reward> offers = Merchant.offers("white", 6, new Random(42), false);
        StringBuilder list = new StringBuilder();
        for (Reward r : new Array.ArrayIterator<>(offers)) {
            String name = r.getCard().getName();
            list.append("\n      ").append(name).append("  [").append(Merchant.preview(name)).append("]");
        }
        check("the White merchant makes 6 offers", offers.size == 6, offers.size + " offers:" + list);
        Array<Reward> again = Merchant.offers("white", 6, new Random(42), false);
        boolean same = again.size == offers.size;
        for (int i = 0; same && i < offers.size; i++) {
            same = offers.get(i).getCard().getName().equals(again.get(i).getCard().getName());
        }
        check("the same stock gives the same offers", same, null);

        // Pick 1 of 3: loot of five cards and gold becomes three choices, the gold is paid at once.
        Array<Reward> loot = new Array<>();
        for (String name : new String[] {"Grizzly Bears", "Lightning Bolt", "Serra Angel", "Shock", "Divination"}) {
            loot.add(new Reward(StaticData.instance().getCommonCards().getCard(name)));
        }
        loot.add(new Reward(Reward.Type.Gold, 25));
        int gold = player.getGold();
        Array<Reward> choices = DuelRewards.choose(loot);
        check("won-duel loot becomes three choices", choices != null && choices.size == 3,
                choices == null ? "none" : choices.size + ": " + names(choices));
        check("the loot's gold is paid at once", player.getGold() == gold + 25, (player.getGold() - gold) + " gold paid");

        // Deck size: +2 life per full 10 cards over the minimum, capped at +4.
        check("a 40-card deck gets no bonus life", DeckSize.lifeBonus(deckOf(40)) == 0, null);
        check("a 50-card deck gets +2 life", DeckSize.lifeBonus(deckOf(50)) == 2, null);
        check("a 75-card deck gets +4 life (the cap)", DeckSize.lifeBonus(deckOf(75)) == 4, null);
    }

    private static forge.deck.Deck deckOf(int cards) {
        forge.deck.Deck deck = new forge.deck.Deck("check");
        deck.getMain().add(StaticData.instance().getCommonCards().getCard("Plains"), cards);
        return deck;
    }

    private static String names(Array<Reward> rewards) {
        StringBuilder sb = new StringBuilder();
        for (Reward r : new Array.ArrayIterator<>(rewards)) {
            sb.append(sb.length() == 0 ? "" : ", ").append(r.getCard() == null ? r.getType() : r.getCard().getName());
        }
        return sb.toString();
    }

    private static int indexOf(RegionLayout layout, String id) {
        for (int i = 0; i < layout.regions.size(); i++) {
            if (layout.regions.get(i).id().equals(id)) {
                return i;
            }
        }
        return -1;
    }

    private static void write(Pixmap image, File file) {
        if (image != null) {
            PixmapIO.writePNG(new FileHandle(file), image);
        }
    }
}
