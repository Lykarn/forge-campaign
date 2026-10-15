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

        checkLegendary();
        // Last: it leaves the player in the last place loaded (a Planar Rift), which other checks would see.
        checkEveryPlace(layout, world, player);
    }

    /**
     * Relics, special enemies and legendary choices: every relic item and every enemy effect
     * points at a card the game knows, the Power 9 and our custom cards stay out of random loot,
     * the choices offer what they should, and the Oracle's claim leaves the player's deck alone.
     */
    private static void checkLegendary() {
        java.util.List<String> problems = new java.util.ArrayList<>();
        int relics = 0;
        for (forge.campaign.relics.Relics.Relic r : forge.campaign.relics.Relics.get().all()) {
            forge.adventure.data.ItemData item = forge.adventure.data.ItemListData.getItem(r.item());
            forge.item.PaperCard card = StaticData.instance().getCommonCards().getCard(r.card());
            if (item == null) {
                problems.add(r.item() + ": no item");
            } else if (!"Relic".equals(item.equipmentSlot) && !"Trinket".equals(item.equipmentSlot)) {
                problems.add(r.item() + ": slot " + item.equipmentSlot);
            } else if (card == null || !card.getRules().isCustom()) {
                problems.add(r.item() + ": no custom card " + r.card());
            } else if (item.effect == null || item.effect.startBattleWithCardsInCommandZone().size != 1) {
                problems.add(r.item() + ": its effect does not start the card in the command zone");
            } else {
                relics++;
            }
        }
        check(relics + " relics, each an item with its card", problems.isEmpty() && relics >= 30,
                problems.isEmpty() ? null : String.join("; ", problems));

        problems.clear();
        int effects = 0;
        for (java.util.Map.Entry<String, forge.campaign.enemies.EnemyEffects.Entry> e
                : forge.campaign.enemies.EnemyEffects.all().entrySet()) {
            forge.adventure.data.EffectData fx = e.getValue().effect;
            int named = (fx.startBattleWithCard == null ? 0 : fx.startBattleWithCard.length)
                    + (fx.startBattleWithCardInCommandZone == null ? 0 : fx.startBattleWithCardInCommandZone.length);
            int found = fx.startBattleWithCards().size + fx.startBattleWithCardsInCommandZone().size;
            if (forge.adventure.data.WorldData.getEnemy(e.getKey()) == null) {
                problems.add(e.getKey() + ": no such enemy");
            } else if (found != named) {
                problems.add(e.getKey() + ": " + (named - found) + " unknown cards");
            } else {
                effects++;
            }
        }
        check(effects + " enemy effects, every card known", problems.isEmpty() && effects >= 10,
                problems.isEmpty() ? null : String.join("; ", problems));

        int leaks = 0;
        StringBuilder leaked = new StringBuilder();
        for (forge.item.PaperCard c : forge.adventure.data.RewardData.getAllCards()) {
            if (forge.campaign.enemies.PowerNine.isPower(c.getName()) || c.getRules().isCustom()) {
                leaks++;
                leaked.append(' ').append(c.getName());
            }
        }
        check("random loot never holds the Power 9 or a relic card", leaks == 0, leaks == 0 ? null : leaked.toString());

        Array<Reward> loot = new Array<>();
        loot.add(new Reward(Reward.Type.Gold, 10));
        loot.add(new Reward(forge.adventure.data.ItemListData.getItem(forge.campaign.relics.LegendaryChoice.CASTLE_RELIC)));
        loot.add(new Reward(forge.adventure.data.ItemListData.getItem(forge.campaign.relics.LegendaryChoice.POWER_9)));
        boolean queued = forge.campaign.relics.LegendaryChoice.queue(loot);
        Array<Reward> castle = forge.campaign.relics.LegendaryChoice.next();
        Array<Reward> power = forge.campaign.relics.LegendaryChoice.next();
        boolean drained = forge.campaign.relics.LegendaryChoice.next() == null;
        java.util.Set<String> castleNames = new java.util.HashSet<>();
        boolean allCastle = castle != null;
        for (Reward r : castle == null ? new Array<Reward>() : castle) {
            castleNames.add(r.getItem().name);
            allCastle &= "Relic".equals(r.getItem().equipmentSlot);
        }
        check("choice markers leave the loot and become choices", queued && loot.size == 1 && drained, loot.size + " left");
        check("a castle relic choice offers three different castle relics", allCastle && castleNames.size() == 3,
                String.valueOf(castleNames));
        check("a Power 9 choice offers the nine to a new player", power != null && power.size == 9,
                power == null ? "none" : names(power));

        forge.deck.Deck deck = deckOf(39);
        deck.getMain().add(StaticData.instance().getCommonCards().getCard("Black Lotus"), 1);
        forge.deck.Deck duelCopy = (forge.deck.Deck) deck.copyTo("PlayerDeckCopy");
        java.util.List<forge.item.PaperCard> taken = forge.campaign.enemies.PowerNine.takeFrom(duelCopy);
        forge.deck.Deck oracleDeck = new forge.deck.Deck("oracle");
        forge.campaign.enemies.PowerNine.giveTo(oracleDeck, taken);
        check("the Oracle takes Black Lotus for the duel and leaves Wastes",
                taken.size() == 1 && duelCopy.getMain().countAll() == 40
                        && duelCopy.getMain().count(StaticData.instance().getCommonCards().getCard("Wastes")) == 1
                        && oracleDeck.getMain().countAll() == 1, duelCopy.getMain().countAll() + " cards");
        check("the player's own deck keeps its Black Lotus",
                deck.getMain().count(StaticData.instance().getCommonCards().getCard("Black Lotus")) == 1, null);
        check("the Oracle of the Alpha claims the Power 9",
                forge.campaign.enemies.EnemyEffects.takesPower9(forge.adventure.data.WorldData.getEnemy("Oracle of the Alpha")), null);

        checkRelicSlots(Current.player());
        checkRifts();
    }

    /**
     * Each Planar Rift opens its packs and deals a playable sealed deck, its boss and planar relic
     * exist, and a run survives the world save.
     */
    private static void checkRifts() {
        java.util.List<String> problems = new java.util.ArrayList<>();
        int ok = 0;
        for (forge.campaign.rift.RiftRun.Rift rift : forge.campaign.rift.RiftRun.rifts().values()) {
            int pool = forge.campaign.rift.RiftRun.open(rift, rift.packs().size()).countAll();
            forge.deck.Deck deck = forge.campaign.rift.RiftRun.build(rift, rift.packs().size(), new Random(1));
            forge.adventure.data.EnemyData boss = forge.adventure.data.WorldData.getEnemy(rift.boss());
            String relic = boss == null || boss.rewards == null || boss.rewards.length == 0 || boss.rewards[0].itemNames == null
                    ? null : boss.rewards[0].itemNames[0];
            if (pool < 9 * rift.packs().size()) { // some older sets' Adventure boosters hold 10 cards
                problems.add(rift.name() + ": " + pool + " cards from " + rift.packs().size() + " packs");
            } else if (deck.getMain().countAll() < 40) {
                problems.add(rift.name() + ": a " + deck.getMain().countAll() + "-card deck");
            } else if (boss == null) {
                problems.add(rift.name() + ": no boss " + rift.boss());
            } else if (relic == null || forge.adventure.data.ItemListData.getItem(relic) == null) {
                problems.add(rift.name() + ": its boss drops no planar relic");
            } else {
                ok++;
            }
        }
        check(ok + " Planar Rifts deal sealed decks and have a boss with a planar relic",
                problems.isEmpty() && ok == 3, problems.isEmpty() ? null : String.join("; ", problems));

        forge.campaign.rift.RiftRun.Rift first = forge.campaign.rift.RiftRun.rifts().values().iterator().next();
        forge.campaign.rift.RiftRun.start(first, new Random(2));
        java.util.HashMap<String, java.util.ArrayList<String>> saved = forge.campaign.rift.RiftRun.snapshot();
        forge.campaign.rift.RiftRun.restore(null);
        boolean cleared = forge.campaign.rift.RiftRun.activeRift() == null;
        forge.campaign.rift.RiftRun.restore(saved);
        boolean back = first.name().equals(forge.campaign.rift.RiftRun.activeRift())
                && forge.campaign.rift.RiftRun.snapshot().values().iterator().next().size()
                == saved.values().iterator().next().size();
        forge.campaign.rift.RiftRun.restore(null);
        check("a rift run survives the world save", cleared && back, String.valueOf(saved.keySet()));
    }

    /** Relic slots open with castles, and two relics go to two slots once the second is open. */
    private static void checkRelicSlots(AdventurePlayer player) {
        int castles = player.getQuestFlag(DeckSize.CASTLES_FLAG);
        player.setQuestFlag(DeckSize.CASTLES_FLAG, 0);
        boolean closedAtStart = !forge.campaign.relics.RelicSlots.isOpen(player, "Relic2")
                && forge.campaign.relics.RelicSlots.isOpen(player, "Relic");
        player.setQuestFlag(DeckSize.CASTLES_FLAG, 2);
        boolean openAfterTwo = forge.campaign.relics.RelicSlots.isOpen(player, "Relic2")
                && forge.campaign.relics.RelicSlots.isOpen(player, "Trinket2")
                && !forge.campaign.relics.RelicSlots.isOpen(player, "Relic3");
        player.setQuestFlag(DeckSize.CASTLES_FLAG, 4);
        boolean openAfterFour = forge.campaign.relics.RelicSlots.isOpen(player, "Relic3");
        check("relic slots open with castles: 1 + 1 at the start, +2 after two, +1 after four",
                closedAtStart && openAfterTwo && openAfterFour, null);

        player.setQuestFlag(DeckSize.CASTLES_FLAG, 2);
        player.addItem("Crown of the Five Castles", false);
        player.addItem("Emberheart Brand", false);
        java.util.List<forge.adventure.data.ItemData> relics = new java.util.ArrayList<>();
        for (forge.adventure.data.ItemData item : player.getItems()) {
            if ("Crown of the Five Castles".equals(item.name) || "Emberheart Brand".equals(item.name)) {
                relics.add(item);
            }
        }
        for (forge.adventure.data.ItemData item : relics) { // as InventoryScene.equip does
            String family = item.equipmentSlot;
            item.equipmentSlot = forge.campaign.relics.RelicSlots.slotFor(player, item, null);
            player.equip(item);
            item.equipmentSlot = family;
        }
        boolean both = relics.size() == 2 && player.itemInSlot("Relic") != null && player.itemInSlot("Relic2") != null
                && !player.itemInSlot("Relic").equals(player.itemInSlot("Relic2"));
        for (forge.adventure.data.ItemData item : relics) { // and the same click takes each off again
            String family = item.equipmentSlot;
            item.equipmentSlot = forge.campaign.relics.RelicSlots.slotFor(player, item, null);
            player.equip(item);
            item.equipmentSlot = family;
        }
        boolean off = player.itemInSlot("Relic") == null && player.itemInSlot("Relic2") == null;
        for (forge.adventure.data.ItemData item : relics) {
            player.removeItem(item);
        }
        player.setQuestFlag(DeckSize.CASTLES_FLAG, castles);
        check("two relics equip into Relic and Relic2, and unequip again", both && off,
                relics.size() + " relics, " + player.itemInSlot("Relic") + " / " + player.itemInSlot("Relic2"));
    }

    /**
     * Every point of interest of the layout, entered as the player would (its map loaded through
     * TileMapScene): the map must load, and our towns must hold exactly one merchant with its
     * offers (6, or 8 in a capital). Closed regions are opened for the check and shut again.
     */
    private static void checkEveryPlace(RegionLayout layout, World world, AdventurePlayer player) {
        java.util.Map<String, Integer> saved = new java.util.HashMap<>();
        for (RegionLayout.Region r : layout.regions) {
            if (r.requiresFlag() != null) {
                saved.put(r.requiresFlag(), player.getQuestFlag(r.requiresFlag()));
                player.setQuestFlag(r.requiresFlag(), 1);
            }
        }
        java.util.Map<String, forge.adventure.pointofintrest.PointOfInterest> placed = new java.util.HashMap<>();
        for (forge.adventure.pointofintrest.PointOfInterest poi : world.getAllPointOfInterest()) {
            placed.put(poi.getData().name, poi);
        }
        for (java.util.Map.Entry<String, Integer> e : saved.entrySet()) {
            player.setQuestFlag(e.getKey(), e.getValue());
        }
        int loaded = 0;
        java.util.List<String> problems = new java.util.ArrayList<>();
        for (RegionLayout.Poi p : layout.pois) {
            forge.adventure.pointofintrest.PointOfInterest poi = placed.get(p.name());
            if (poi == null) {
                problems.add(p.name() + ": not placed");
                continue;
            }
            try {
                forge.adventure.scene.TileMapScene.instance().load(poi);
                loaded++;
                String map = poi.getData().map == null ? "" : poi.getData().map;
                String type = poi.getData().type == null ? "" : poi.getData().type;
                if (map.contains("/campaign/") && (type.equals("town") || type.equals("capital"))) {
                    java.util.List<forge.adventure.character.ShopActor> shops = new java.util.ArrayList<>();
                    findShops(forge.adventure.stage.MapStage.getInstance().getRoot(), shops);
                    int want = type.equals("capital") ? 8 : 6;
                    if (shops.size() != 1) {
                        problems.add(p.name() + ": " + shops.size() + " merchants");
                    } else if (shops.get(0).getRewardData().size < want) {
                        problems.add(p.name() + ": " + shops.get(0).getRewardData().size + " offers (want " + want + ")");
                    }
                }
            } catch (Throwable t) {
                problems.add(p.name() + ": " + t);
            }
        }
        check("every place loads, and every town has its merchant (" + loaded + " of " + layout.pois.size() + " entered)",
                problems.isEmpty(), problems.isEmpty() ? null : String.join("; ", problems));
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
