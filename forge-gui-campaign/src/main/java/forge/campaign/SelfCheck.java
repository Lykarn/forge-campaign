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
            boolean whileOpen = hasPoi(world, "Serra's Rest");
            player.setQuestFlag(pass.gateFlag(), 0);
            check("quests can target the Plains once the gate is open", whileOpen, null);
            check("quests cannot target the Plains while the gate is shut", !hasPoi(world, "Serra's Rest"), null);
            check("quests cannot target closed regions", world.getAllPointOfInterest().size() < 40,
                    world.getAllPointOfInterest().size() + " targetable points of interest");
        }

        // Every gated road: shut until its flag is set, open after (castle flags for the later regions).
        for (RegionLayout.Pass p : layout.passes) {
            if (p.gateFlag() == null) {
                continue;
            }
            int y = world.getHeightInTiles() - p.y() - 1;
            boolean shut = world.isColliding(p.x(), y);
            player.setQuestFlag(p.gateFlag(), 1);
            boolean open = !world.isColliding(p.x(), y);
            player.setQuestFlag(p.gateFlag(), 0);
            check("road " + p.id() + " opens with " + p.gateFlag(), shut && open, null);
        }
        // The finale appears only once all five colour castles have fallen.
        forge.adventure.pointofintrest.PointOfInterest finale = null;
        for (forge.adventure.pointofintrest.PointOfInterest poi : world.getAllPointOfInterest()) {
            if ("Emrakul".equals(poi.getData().name)) {
                finale = poi;
            }
        }
        check("the finale is placed in the hub", finale != null, null);
        if (finale != null) {
            boolean hidden = !finale.getActive();
            player.setQuestFlag(DeckSize.CASTLES_FLAG, 5);
            boolean shown = finale.getActive();
            player.setQuestFlag(DeckSize.CASTLES_FLAG, 0);
            check("the finale appears after five castles", hidden && shown, null);
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

        // A town: load the Crossroads map as entering it does, and find its merchant.
        forge.adventure.pointofintrest.PointOfInterest town = null;
        for (forge.adventure.pointofintrest.PointOfInterest poi : world.getAllPointOfInterest()) {
            if ("Crossroads".equals(poi.getData().name)) {
                town = poi;
            }
        }
        check("the Crossroads town exists", town != null, null);
        if (town != null) {
            forge.adventure.scene.TileMapScene.instance().load(town);
            java.util.List<forge.adventure.character.ShopActor> shops = new java.util.ArrayList<>();
            findShops(forge.adventure.stage.MapStage.getInstance().getRoot(), shops);
            StringBuilder found = new StringBuilder();
            for (forge.adventure.character.ShopActor s : shops) {
                found.append(found.length() == 0 ? "" : "; ").append(s.getDescription()).append(" (")
                        .append(s.getRewardData().size).append(" offers)");
            }
            check("the Crossroads has exactly one merchant with offers",
                    shops.size() == 1 && shops.get(0).getRewardData().size >= 6, shops.size() + " shops: " + found);
        }

        // Deck size: +2 life per full 10 cards over the minimum, capped at +4.
        check("a 40-card deck gets no bonus life", DeckSize.lifeBonus(deckOf(40)) == 0, null);
        check("a 50-card deck gets +2 life", DeckSize.lifeBonus(deckOf(50)) == 2, null);
        check("a 75-card deck gets +4 life (the cap)", DeckSize.lifeBonus(deckOf(75)) == 4, null);
        int start = DeckSize.minimum();
        player.setQuestFlag(DeckSize.CASTLES_FLAG, 1);
        int afterOne = DeckSize.minimum();
        player.setQuestFlag(DeckSize.CASTLES_FLAG, 3);
        int afterThree = DeckSize.minimum();
        player.setQuestFlag(DeckSize.CASTLES_FLAG, 0);
        DeckSize.minimum();
        check("the minimum deck grows 40, 50, 60 with castles", start == 40 && afterOne == 50 && afterThree == 60,
                start + ", " + afterOne + ", " + afterThree);
    }

    private static boolean hasPoi(World world, String name) {
        for (forge.adventure.pointofintrest.PointOfInterest poi : world.getAllPointOfInterest()) {
            if (name.equals(poi.getData().name)) {
                return true;
            }
        }
        return false;
    }

    private static void findShops(com.badlogic.gdx.scenes.scene2d.Actor actor,
                                  java.util.List<forge.adventure.character.ShopActor> out) {
        if (actor instanceof forge.adventure.character.ShopActor shop) {
            out.add(shop);
        }
        if (actor instanceof com.badlogic.gdx.scenes.scene2d.Group group) {
            for (com.badlogic.gdx.scenes.scene2d.Actor child : group.getChildren()) {
                findShops(child, out);
            }
        }
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
