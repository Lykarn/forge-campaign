"""Re-apply the FORGE-CAMPAIGN changes to a fresh copy of Forge's World.java (for rebases).

Copy the upstream original over forge-gui-campaign/src/main/java/forge/adventure/world/World.java,
run this, then update its hash in shadows.tsv. Each replacement asserts its anchor still exists.
"""
from pathlib import Path

p = Path(__file__).resolve().parents[2] / "forge-gui-campaign/src/main/java/forge/adventure/world/World.java"
t = p.read_text(encoding="utf-8").replace("\r\n", "\n")

HEADER = """// SHADOW COPY of forge-gui-mobile/src/forge/adventure/world/World.java (Card-Forge/forge).
// It sits ahead of Forge's original on the classpath; the original is never edited.
// Changes are marked FORGE-CAMPAIGN. If upstream changes the original, scripts/check_shadows.py
// fails: re-copy the new original and re-apply the marked blocks.
"""

def rep(old, new):
    global t
    assert t.count(old) == 1, old[:80]
    t = t.replace(old, new)

# 1. Fixed seed from the layout.
rep("""            if (seed == 0) {
                seed = random.nextLong();
            }
            this.seed = seed;""",
"""            // FORGE-CAMPAIGN: an authored layout fixes the seed, so the terrain is the same in every
            // game and the layout's positions stay valid (forge.campaign.world.RegionLayout).
            forge.campaign.world.RegionLayout layout = forge.campaign.world.RegionLayout.get();
            if (layout != null && layout.seed != 0) {
                seed = layout.seed;
            }
            // FORGE-CAMPAIGN end
            if (seed == 0) {
                seed = random.nextLong();
            }
            this.seed = seed;""")

# 1b. Region and wall masks right after the biomes, so random placement can avoid future walls.
rep("""            currentTime[0] = measureGenerationTime("biomes in total", currentTime[0]);
""",
"""            currentTime[0] = measureGenerationTime("biomes in total", currentTime[0]);
            // FORGE-CAMPAIGN: where the region walls will go, before any point of interest is placed.
            campaignWall = null;
            if (layout != null) {
                computeRegionMasks(layout);
            }
            // FORGE-CAMPAIGN end
""")
rep("""                                if ((int) x < 0 || (int) y <= 0 || (int) y >= height || (int) x >= width || biomeIndex2 != highestBiome(getBiome((int) x, (int) y))) {
                                    continue;
                                }""",
"""                                if ((int) x < 0 || (int) y <= 0 || (int) y >= height || (int) x >= width || biomeIndex2 != highestBiome(getBiome((int) x, (int) y))) {
                                    continue;
                                }
                                // FORGE-CAMPAIGN: not on or next to a future region wall.
                                if (nearCampaignWall((int) x, height - 1 - (int) y, 4)) {
                                    continue;
                                }""")

# 2. No random points of interest in authored regions.
rep("""                    biomeIndex2++;
                    for (PointOfInterestData poi : biome.getPointsOfInterest()) {""",
"""                    biomeIndex2++;
                    // FORGE-CAMPAIGN: authored regions get their points of interest from the layout.
                    if (layout != null && layout.isAuthored(biome.name)) {
                        continue;
                    }
                    // FORGE-CAMPAIGN end
                    for (PointOfInterestData poi : biome.getPointsOfInterest()) {""")

# 3. The layout's points of interest at fixed tiles.
rep("""            currentTime[0] = measureGenerationTime("poi placement", currentTime[0]);""",
"""            // FORGE-CAMPAIGN: points of interest at fixed tiles from the layout (map tiles from the top).
            if (layout != null) {
                for (forge.campaign.world.RegionLayout.Poi p : layout.pois) {
                    PointOfInterestData poi = PointOfInterestData.getPointOfInterest(p.name());
                    if (poi == null) {
                        System.err.println("[campaign] layout: no point of interest named " + p.name());
                        continue;
                    }
                    int tileY = height - p.y();
                    float x = p.x() * (float) data.tileSize;
                    float y = tileY * (float) data.tileSize;
                    PointOfInterest newPoint = new PointOfInterest(poi, new Vector2(x, y), random);
                    clearTerrain(p.x(), tileY, 3);
                    mapPoiIds.add(newPoint);
                    TextureAtlas.AtlasRegion marker = mapMarker.findRegion(poi.type);
                    if (marker != null) {
                        int xInPixels = p.x() * data.miniMapTileSize - marker.getRegionWidth() / 2;
                        int yInPixels = p.y() * data.miniMapTileSize - marker.getRegionHeight() / 2;
                        drawPixmapLater(mapMarkerPixmap, marker.getRegionX(), marker.getRegionY(),
                                marker.getRegionWidth(), marker.getRegionHeight(), xInPixels, yInPixels,
                                marker.getRegionWidth(), marker.getRegionHeight());
                    }
                    if (p.displayName() != null) {
                        newPoint.setDisplayName(p.displayName());
                    } else if (poi.displayName != null && !poi.displayName.isEmpty()) {
                        newPoint.setDisplayName(poi.getDisplayName());
                    }
                    if (poi.type != null && (poi.type.equals("town") || poi.type.equals("capital"))) {
                        towns.add(newPoint);
                    } else {
                        notTowns.add(newPoint);
                    }
                }
            }
            // FORGE-CAMPAIGN end
            currentTime[0] = measureGenerationTime("poi placement", currentTime[0]);""")

# 4. Walls between regions, after roads (so no road cuts through) and before the minimap.
rep("""            currentTime[0] = measureGenerationTime("roads", currentTime[0]);
""",
"""            currentTime[0] = measureGenerationTime("roads", currentTime[0]);
            // FORGE-CAMPAIGN: water walls between regions, opened at passes.
            if (layout != null) {
                applyRegionWalls(layout);
                currentTime[0] = measureGenerationTime("region walls", currentTime[0]);
            }
            // FORGE-CAMPAIGN end
""")

# 5. Debug dump of the generated map.
rep("""            System.out.println("Generating world took :\\t\\t" + ((System.currentTimeMillis() - startTime) / 1000f) + " s");""",
"""            System.out.println("Generating world took :\\t\\t" + ((System.currentTimeMillis() - startTime) / 1000f) + " s");
            // FORGE-CAMPAIGN: -Dcampaign.dumpWorld=<file.png> saves the minimap, to author the layout.
            String dump = System.getProperty("campaign.dumpWorld");
            if (dump != null && !dump.isEmpty()) {
                com.badlogic.gdx.graphics.PixmapIO.writePNG(new FileHandle(dump), biomeImage);
                System.out.println("[campaign] world map written to " + dump + " (seed " + this.seed + ")");
            }
            // FORGE-CAMPAIGN end""")

# 6. Gates: pass tiles that block until their quest flag is set.
rep("""    public boolean isColliding(int x, int y) {
        try {
            return (terrainMap[x][height - y - 1] & collisionBit) != 0;""",
"""    public boolean isColliding(int x, int y) {
        try {
            // FORGE-CAMPAIGN: a gated pass blocks until its quest flag is set.
            return (terrainMap[x][height - y - 1] & collisionBit) != 0 || gateBlocks(x, height - y - 1);""")

# 7. The helpers, before generateNew.
rep("""    public boolean generateNew(long seed) {""",
"""    // FORGE-CAMPAIGN: helpers for the authored layout (forge.campaign.world.RegionLayout).
    /** True if map tile (x, y from the top) lies in a pass whose gate is shut. */
    private boolean gateBlocks(int x, int mapY) {
        forge.campaign.world.RegionLayout layout = forge.campaign.world.RegionLayout.get();
        if (layout == null) {
            return false;
        }
        for (forge.campaign.world.RegionLayout.Pass pass : layout.passes) {
            if (pass.gateFlag() == null && !pass.closed()) {
                continue;
            }
            int dx = x - pass.x();
            int dy = mapY - pass.y();
            if (dx * dx + dy * dy > pass.radius() * pass.radius()) {
                continue;
            }
            if (pass.closed()) {
                return true;
            }
            forge.adventure.player.AdventurePlayer player = forge.adventure.util.Current.player();
            return player == null || player.getQuestFlag(pass.gateFlag()) < 1;
        }
        return false;
    }

    /**
     * Water walls along every border between two regions of the layout, wallWidth tiles each
     * side, except inside a pass, which becomes road. Cells outside any region (the ocean) are
     * left alone, so the coast stays as it is.
     */
    private void applyRegionWalls(forge.campaign.world.RegionLayout layout) {
        List<BiomeData> biomes = data.GetBiomes();
        long roadBit = 1L << biomes.size();
        int ocean = 0;
        for (int i = 0; i < biomes.size(); i++) {
            if (biomes.get(i).collision && biomes.get(i).invertHeight) {
                ocean = i;
                break;
            }
        }
        List<forge.campaign.world.RegionLayout.Region> regions = layout.regions;
        if (campaignWall == null) {
            computeRegionMasks(layout);
        }
        int[][] region = campaignRegion;
        boolean[][] wall = campaignWall;
        for (int x = 0; x < width; x++) {
            for (int y = 0; y < height; y++) {
                if (wall[x][y] && !inPass(layout, x, y)) {
                    biomeMap[x][y] = 1L << ocean;
                    terrainMap[x][y] = collisionBit;
                }
            }
        }
        finishRegionWalls(layout, region, wall, ocean, roadBit, regions);
    }

    /** The region of every tile and where the walls will go, from the biomes alone. */
    private int[][] campaignRegion;
    private boolean[][] campaignWall;

    /**
     * Computed right after the biomes, before any point of interest is placed: Adventure's random
     * placement then avoids the future walls (a town placed first and walled over later sat in
     * the water: playtest), and the walls themselves are drawn after the roads, from these masks.
     */
    private void computeRegionMasks(forge.campaign.world.RegionLayout layout) {
        List<BiomeData> biomes = data.GetBiomes();
        long roadBit = 1L << biomes.size();
        List<forge.campaign.world.RegionLayout.Region> regions = layout.regions;
        int[][] region = new int[width][height];
        for (int x = 0; x < width; x++) {
            for (int y = 0; y < height; y++) {
                long bits = biomeMap[x][y] & ~roadBit;
                region[x][y] = -1;
                if (bits == 0) {
                    continue;
                }
                forge.campaign.world.RegionLayout.Region r = layout.regionOf(biomes.get(highestBiome(bits)).name);
                region[x][y] = r == null ? -1 : regions.indexOf(r);
            }
        }
        int w = layout.wallWidth;
        boolean[][] wall = new boolean[width][height];
        for (int x = 0; x < width - 1; x++) {
            for (int y = 0; y < height - 1; y++) {
                int r = region[x][y];
                if (r < 0) {
                    continue;
                }
                int right = region[x + 1][y];
                int down = region[x][y + 1];
                if ((right >= 0 && right != r) || (down >= 0 && down != r)) {
                    for (int wx = Math.max(0, x - w); wx <= Math.min(width - 1, x + w); wx++) {
                        for (int wy = Math.max(0, y - w); wy <= Math.min(height - 1, y + w); wy++) {
                            wall[wx][wy] = true;
                        }
                    }
                }
            }
        }
        campaignRegion = region;
        campaignWall = wall;
    }

    /** True if a wall (outside a pass) lies within r tiles of map tile (x, y from the top). */
    private boolean nearCampaignWall(int x, int mapY, int r) {
        forge.campaign.world.RegionLayout layout = forge.campaign.world.RegionLayout.get();
        if (campaignWall == null || layout == null) {
            return false;
        }
        for (int wx = Math.max(0, x - r); wx <= Math.min(width - 1, x + r); wx++) {
            for (int wy = Math.max(0, mapY - r); wy <= Math.min(height - 1, mapY + r); wy++) {
                if (campaignWall[wx][wy] && !inPass(layout, wx, wy)) {
                    return true;
                }
            }
        }
        return false;
    }

    private void finishRegionWalls(forge.campaign.world.RegionLayout layout, int[][] region, boolean[][] wall,
                                        int ocean, long roadBit, List<forge.campaign.world.RegionLayout.Region> regions) {
        dumpRegions(layout, region, wall);
        // Where each authored point of interest landed: a typo'd tile shows up here, not in play.
        for (forge.campaign.world.RegionLayout.Poi p : layout.pois) {
            if (p.x() < 0 || p.y() < 0 || p.x() >= width || p.y() >= height) {
                System.err.println("[campaign] layout: " + p.name() + " is off the map");
                continue;
            }
            int r = region[p.x()][p.y()];
            String where = wall[p.x()][p.y()] && !inPass(layout, p.x(), p.y()) ? "IN A WALL"
                    : r < 0 ? "IN THE OCEAN" : regions.get(r).id();
            System.out.println("[campaign] layout: " + p.name() + " at (" + p.x() + ", " + p.y() + "): " + where);
        }
        for (forge.campaign.world.RegionLayout.Pass pass : layout.passes) {
            int r = pass.radius();
            for (int x = Math.max(0, pass.x() - r); x <= Math.min(width - 1, pass.x() + r); x++) {
                for (int y = Math.max(0, pass.y() - r); y <= Math.min(height - 1, pass.y() + r); y++) {
                    if (inPass(layout, x, y) && biomeMap[x][y] != 0) {
                        biomeMap[x][y] = (biomeMap[x][y] & ~(1L << ocean)) | roadBit;
                        terrainMap[x][y] = 0;
                    }
                }
            }
        }
    }

    /** With -Dcampaign.dumpWorld, also a flat map: regions, walls, passes, authored points of interest. */
    private void dumpRegions(forge.campaign.world.RegionLayout layout, int[][] region, boolean[][] wall) {
        String dump = System.getProperty("campaign.dumpWorld");
        if (dump == null || dump.isEmpty()) {
            return;
        }
        int[] colours = {0xb0b0b0ff, 0xf0e6b0ff, 0x80c8f0ff, 0x505050ff, 0xe07050ff, 0x70c050ff, 0xc090e0ff, 0x90e0c0ff};
        Pixmap map = new Pixmap(width, height, Pixmap.Format.RGBA8888);
        for (int x = 0; x < width; x++) {
            for (int y = 0; y < height; y++) {
                int c = region[x][y] < 0 ? 0x2060a0ff : colours[region[x][y] % colours.length];
                if (wall[x][y]) {
                    c = inPass(layout, x, y) ? 0xffe000ff : 0x103060ff;
                }
                map.drawPixel(x, y, c);
            }
        }
        for (forge.campaign.world.RegionLayout.Poi p : layout.pois) {
            map.setColor(1, 0, 0, 1);
            map.fillCircle(p.x(), p.y(), 3);
        }
        String file = dump.replace(".png", "_regions.png");
        com.badlogic.gdx.graphics.PixmapIO.writePNG(new FileHandle(file), map);
        map.dispose();
    }

    private static boolean inPass(forge.campaign.world.RegionLayout layout, int x, int mapY) {
        for (forge.campaign.world.RegionLayout.Pass pass : layout.passes) {
            int dx = x - pass.x();
            int dy = mapY - pass.y();
            if (dx * dx + dy * dy <= pass.radius() * pass.radius()) {
                return true;
            }
        }
        return false;
    }
    // FORGE-CAMPAIGN end

    public boolean generateNew(long seed) {""")

# 9. Merchant offers are remembered per stock and saved with the world (forge.campaign.shop.MerchantLedger).
rep("""        data.store("seed", seed);
        return data;""",
"""        data.store("seed", seed);
        data.storeObject("campaignMerchants", forge.campaign.shop.MerchantLedger.snapshot()); // FORGE-CAMPAIGN
        return data;""")
rep("""        seed = saveFileData.readLong("seed");
    }""",
"""        seed = saveFileData.readLong("seed");
        forge.campaign.shop.MerchantLedger.restore(saveFileData.readObject("campaignMerchants")); // FORGE-CAMPAIGN
    }""")
rep("""            loadWorldData();
//////////////////
///////// initialize""",
"""            loadWorldData();
            forge.campaign.shop.MerchantLedger.restore(null); // FORGE-CAMPAIGN: a new world, no stocks yet
//////////////////
///////// initialize""")

# 10. Quests (and anything else that asks) only see points of interest in authored regions
# whose gate (requiresFlag) is open: the others sit behind closed roads or a shut gate.
rep("""    public List<PointOfInterest> getAllPointOfInterest(){
        return mapPoiIds.getAllPointOfInterest();
    }""",
"""    public List<PointOfInterest> getAllPointOfInterest(){
        // FORGE-CAMPAIGN: only points of interest in the layout's authored regions.
        List<PointOfInterest> all = mapPoiIds.getAllPointOfInterest();
        forge.campaign.world.RegionLayout layout = forge.campaign.world.RegionLayout.get();
        if (layout == null) {
            return all;
        }
        List<PointOfInterest> open = new ArrayList<>();
        for (PointOfInterest poi : all) {
            int x = (int) (poi.getPosition().x / data.tileSize);
            int mapY = height - 1 - (int) (poi.getPosition().y / data.tileSize);
            int r = campaignRegionAt(x, mapY);
            forge.campaign.world.RegionLayout.Region region = r >= 0 ? layout.regions.get(r) : null;
            // A gated region counts once its gate is open, so early quests stay in reach.
            if (region != null && region.authored() && (region.requiresFlag() == null
                    || (forge.adventure.util.Current.player() != null
                        && forge.adventure.util.Current.player().getQuestFlag(region.requiresFlag()) >= 1))) {
                open.add(poi);
            }
        }
        return open;
        // FORGE-CAMPAIGN end
    }""")

# 8. Fog of war: the map screens get a fogged image; saves keep the clear one.
rep("""    public Pixmap getBiomeImage() {
        return biomeImage;
    }""",
"""    public Pixmap getBiomeImage() {
        // FORGE-CAMPAIGN: fog of war on the minimap and the map screen (forge.campaign.world.Fog).
        // save() reads the field, so saves keep the clear image.
        return forge.campaign.world.Fog.apply(this, biomeImage);
        // FORGE-CAMPAIGN end
    }

    // FORGE-CAMPAIGN: for forge.campaign.world.Fog and DuelRewards.
    /** The layout region (its index) of map tile (x, y from the top), or -1 for none. */
    public int campaignRegionAt(int x, int mapY) {
        forge.campaign.world.RegionLayout layout = forge.campaign.world.RegionLayout.get();
        if (layout == null || x < 0 || mapY < 0 || x >= width || mapY >= height) {
            return -1;
        }
        List<BiomeData> biomes = data.GetBiomes();
        long bits = biomeMap[x][mapY] & ~(1L << biomes.size());
        if (bits == 0) {
            return -1;
        }
        int index = highestBiome(bits);
        if (index >= biomes.size()) {
            return -1;
        }
        forge.campaign.world.RegionLayout.Region r = layout.regionOf(biomes.get(index).name);
        return r == null ? -1 : layout.regions.indexOf(r);
    }
    // FORGE-CAMPAIGN end""")

p.write_text(HEADER + t, encoding="utf-8", newline="\n")
print("World.java patched")
