// SHADOW COPY of forge-gui-mobile/src/forge/adventure/world/World.java (Card-Forge/forge).
// It sits ahead of Forge's original on the classpath; the original is never edited.
// Changes are marked FORGE-CAMPAIGN. If upstream changes the original, scripts/check_shadows.py
// fails: re-copy the new original and re-apply the marked blocks.
package forge.adventure.world;

import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.Pixmap;
import com.badlogic.gdx.graphics.Texture;
import com.badlogic.gdx.graphics.TextureData;
import com.badlogic.gdx.graphics.g2d.TextureAtlas;
import com.badlogic.gdx.math.Rectangle;
import com.badlogic.gdx.math.Vector2;
import com.badlogic.gdx.scenes.scene2d.Actor;
import com.badlogic.gdx.utils.Array;
import com.badlogic.gdx.utils.Disposable;
import com.badlogic.gdx.utils.Json;
import forge.Forge;
import forge.adventure.data.*;
import forge.adventure.pointofintrest.PointOfInterest;
import forge.adventure.pointofintrest.PointOfInterestMap;
import forge.adventure.scene.Scene;
import forge.adventure.stage.WorldStage;
import forge.adventure.util.Config;
import forge.adventure.util.Paths;
import forge.adventure.util.SaveFileContent;
import forge.adventure.util.SaveFileData;
import forge.gui.GuiBase;
import org.apache.commons.lang3.tuple.Pair;

import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Class that will create the world from the configuration
 */
public class World implements Disposable, SaveFileContent {
    private WorldData data;
    private Pixmap biomeImage;
    private long[][] biomeMap;
    public int[][] terrainMap;
    private static final int collisionBit = 0b10000000000000000000000000000000;
    private static final int isStructureBit = 0b01000000000000000000000000000000;
    private static final int terrainMask = collisionBit | isStructureBit;
    private int width;
    private int height;
    private SpritesDataMap mapObjectIds;
    private PointOfInterestMap mapPoiIds;
    private BiomeTexture[] biomeTexture;
    private long seed;
    private final Random random = new Random();
    private boolean worldDataLoaded = false;
    private Texture globalTexture = null;
    private final ArrayList<DrawingInformation> drawingInfoCache = new ArrayList<>(32);
    private Pixmap globalTileDrawing = null;
    private Pixmap emptyTile = null;

    public Random getRandom() {
        return random;
    }

    static public int highestBiome(long biome) {
        return (int) (Math.log(Long.highestOneBit(biome)) / Math.log(2));
    }

    public boolean collidingTile(Rectangle boundingRect) {

        int xLeft = (int) boundingRect.getX() / getTileSize();
        int yTop = (int) boundingRect.getY() / getTileSize();
        int xRight = (int) ((boundingRect.getX() + boundingRect.getWidth()) / getTileSize());
        int yBottom = (int) ((boundingRect.getY() + boundingRect.getHeight()) / getTileSize());

        if (isColliding(xLeft, yTop))
            return true;
        if (isColliding(xLeft, yBottom))
            return true;
        if (isColliding(xRight, yBottom))
            return true;
        if (isColliding(xRight, yTop))
            return true;

        return false;
    }

    public void loadWorldData() {
        if (worldDataLoaded)
            return;

        FileHandle handle = Config.instance().getFile(Paths.WORLD);
        String rawJson = handle.readString();
        this.data = (new Json()).fromJson(WorldData.class, rawJson);
        biomeTexture = new BiomeTexture[data.GetBiomes().size() + 1];

        int biomeIndex = 0;
        for (BiomeData biome : data.GetBiomes()) {

            biomeTexture[biomeIndex] = new BiomeTexture(biome, data.tileSize);
            biomeIndex++;
        }
        biomeTexture[biomeIndex] = new BiomeTexture(data.roadTileset, data.tileSize);
        worldDataLoaded = true;
    }

    @Override
    public void load(SaveFileData saveFileData) {

        if (biomeImage != null) {
            biomeImage.dispose();
            biomeImage = null;
        }

        loadWorldData();

        biomeImage = saveFileData.readPixmap("biomeImage");
        biomeMap = (long[][]) saveFileData.readObject("biomeMap");
        terrainMap = (int[][]) saveFileData.readObject("terrainMap");


        width = saveFileData.readInt("width");
        height = saveFileData.readInt("height");
        mapObjectIds = new SpritesDataMap(getChunkSize(), this.data.tileSize, this.data.width / getChunkSize());
        mapObjectIds.load(saveFileData.readSubData("mapObjectIds"));
        mapPoiIds = new PointOfInterestMap(getChunkSize(), this.data.tileSize, this.data.width / getChunkSize(), this.data.height / getChunkSize());
        mapPoiIds.load(saveFileData.readSubData("mapPoiIds"));
        seed = saveFileData.readLong("seed");
        forge.campaign.shop.MerchantLedger.restore(saveFileData.readObject("campaignMerchants")); // FORGE-CAMPAIGN
        forge.campaign.rift.RiftRun.restore(saveFileData.containsKey("campaignRift") ? saveFileData.readObject("campaignRift") : null); // FORGE-CAMPAIGN
    }

    @Override
    public SaveFileData save() {

        SaveFileData data = new SaveFileData();

        data.store("biomeImage", biomeImage);
        data.storeObject("biomeMap", biomeMap);
        data.storeObject("terrainMap", terrainMap);
        data.store("width", width);
        data.store("height", height);
        data.store("mapObjectIds", mapObjectIds.save());
        data.store("mapPoiIds", mapPoiIds.save());
        data.store("seed", seed);
        data.storeObject("campaignMerchants", forge.campaign.shop.MerchantLedger.snapshot()); // FORGE-CAMPAIGN
        data.storeObject("campaignRift", forge.campaign.rift.RiftRun.snapshot()); // FORGE-CAMPAIGN
        return data;
    }


    public BiomeSpriteData getObject(int id) {
        return mapObjectIds.get(id);
    }

    private static class DrawingInformation {

        private int neighbors;
        private final BiomeTexture regions;
        private final int terrain;

        public DrawingInformation(int neighbors, BiomeTexture regions, int terrain) {

            this.neighbors = neighbors;
            this.regions = regions;
            this.terrain = terrain;
        }

        public void draw(Pixmap drawingPixmap) {
            regions.drawPixmapOn(terrain, neighbors, drawingPixmap);
        }
    }

    public Pixmap getBiomeSprite(int x, int y) {
        if (x < 0 || y <= 0 || x >= width || y > height) {
            if (emptyTile == null) {
                emptyTile = new Pixmap(data.tileSize, data.tileSize, Pixmap.Format.RGBA8888);
                emptyTile.setColor(0, 0, 0, 0);
                emptyTile.fill();
            }
            return emptyTile;
        }

        // init exactly once on demand
        if (globalTileDrawing == null) {
            globalTileDrawing = new Pixmap(data.tileSize, data.tileSize, Pixmap.Format.RGBA8888);
        } else {
            // Clean the existing alpha pixels instead of instantiating a new object
            globalTileDrawing.setColor(0, 0, 0, 0);
            globalTileDrawing.fill();
        }

        long biomeIndex = getBiome(x, y);
        int biomeTerrain = getTerrainIndex(x, y);

        drawingInfoCache.clear();

        for (int i = 0; i < biomeTexture.length; i++) {
            if ((biomeIndex & 1L << i) == 0) continue;
            BiomeTexture regions = biomeTexture[i];
            if (x <= 0 || y <= 1 || x >= width - 1 || y >= height) {
                return regions.getPixmap(biomeTerrain);
            }

            int neighbors = 0b000_000_000;
            int bitIndex = 8;
            for (int ny = 1; ny > -2; ny--) {
                for (int nx = -1; nx < 2; nx++) {
                    if ((getBiome(x + nx, y + ny) & 1L << i) != 0 && (biomeTerrain == getTerrainIndex(x + nx, y + ny) || biomeTerrain == 0))
                        neighbors |= (1 << bitIndex);
                    bitIndex--;
                }
            }
            if (biomeTerrain != 0 && neighbors != 0b111_111_111) {
                bitIndex = 8;
                int baseNeighbors = 0;
                for (int ny = 1; ny > -2; ny--) {
                    for (int nx = -1; nx < 2; nx++) {
                        if ((getBiome(x + nx, y + ny) & (1L << i)) != 0)
                            baseNeighbors |= (1 << bitIndex);
                        bitIndex--;
                    }
                }
                drawingInfoCache.add(new DrawingInformation(baseNeighbors, regions, 0));
            }
            drawingInfoCache.add(new DrawingInformation(neighbors, regions, biomeTerrain));
        }

        int lastFullNeighbour = -1;
        int counter = 0;
        for (DrawingInformation info : drawingInfoCache) {
            if (info.neighbors == 0b111_111_111) lastFullNeighbour = counter;
            counter++;
        }
        counter = 0;
        if (lastFullNeighbour < 0 && !drawingInfoCache.isEmpty()) {
            drawingInfoCache.get(0).neighbors = 0b111_111_111;
        }
        for (DrawingInformation info : drawingInfoCache) {
            if (counter < lastFullNeighbour) {
                counter++;
                continue;
            }
            info.draw(globalTileDrawing);
        }

        return globalTileDrawing;
    }


    public int getTerrainIndex(int x, int y) {
        try {
            return terrainMap[x][height - y - 1] & ~terrainMask;
        } catch (ArrayIndexOutOfBoundsException e) {
            return 0;
        }
    }

    public long getBiomeMapXY(int x, int y) {
        try {
            return biomeMap[x][height - y - 1] & (~(0b1 << data.GetBiomes().size()));
        } catch (ArrayIndexOutOfBoundsException e) {
            return biomeMap[biomeMap.length - 1][biomeMap[biomeMap.length - 1].length - 1];
        }
    }

    public boolean isStructure(int x, int y) {
        try {
            return (terrainMap[x][height - y - 1] & ~isStructureBit) != 0;
        } catch (ArrayIndexOutOfBoundsException e) {
            return false;
        }
    }

    public long getBiome(int x, int y) {
        try {
            return biomeMap[x][height - y - 1];
        } catch (ArrayIndexOutOfBoundsException e) {
            return biomeMap[biomeMap.length - 1][biomeMap[biomeMap.length - 1].length - 1];
        }
    }

    public boolean isColliding(int x, int y) {
        try {
            // FORGE-CAMPAIGN: a gated pass blocks until its quest flag is set.
            return (terrainMap[x][height - y - 1] & collisionBit) != 0 || gateBlocks(x, height - y - 1);
        } catch (ArrayIndexOutOfBoundsException e) {
            return true;
        }
    }

    public WorldData getData() {
        return data;
    }

    private void clearTerrain(int x, int y, int size) {

        for (int xclear = -size; xclear < size; xclear++)
            for (int yclear = -size; yclear < size; yclear++) {
                try {
                    terrainMap[x + xclear][height - 1 - (y + yclear)] = 0;
                } catch (ArrayIndexOutOfBoundsException ignored) {}
            }
    }

    private long measureGenerationTime(String msg, long lastTime) {
        long currentTime = System.currentTimeMillis();
        System.out.println(msg + " :\t\t" + ((currentTime - lastTime) / 1000f) + " s");
        return currentTime;
    }

    // FORGE-CAMPAIGN: helpers for the authored layout (forge.campaign.world.RegionLayout).
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

    public boolean generateNew(long seed) {
        try {
            if (GuiBase.isMobile())
                GuiBase.getInterface().preventSystemSleep(true);
            final long[] currentTime = {System.currentTimeMillis()};
            long startTime = System.currentTimeMillis();

            loadWorldData();
            forge.campaign.shop.MerchantLedger.restore(null); // FORGE-CAMPAIGN: a new world, no stocks yet
            forge.campaign.rift.RiftRun.restore(null); // FORGE-CAMPAIGN: and no rift run
//////////////////
///////// initialize
//////////////////

            // FORGE-CAMPAIGN: an authored layout fixes the seed, so the terrain is the same in every
            // game and the layout's positions stay valid (forge.campaign.world.RegionLayout).
            forge.campaign.world.RegionLayout layout = forge.campaign.world.RegionLayout.get();
            if (layout != null && layout.seed != 0) {
                seed = layout.seed;
            }
            // FORGE-CAMPAIGN end
            if (seed == 0) {
                seed = random.nextLong();
            }
            this.seed = seed;
            random.setSeed(seed);
            OpenSimplexNoise noise = new OpenSimplexNoise(seed);

            float noiseZoom = data.noiseZoomBiome;
            width = data.width;
            height = data.height;
            //save at all data
            biomeMap = new long[width][height];
            terrainMap = new int[width][height];

            for (int x = 0; x < width; x++) {
                for (int y = 0; y < height; y++) {
                    biomeMap[x][y] = 0;
                    terrainMap[x][y] = 0;
                }
            }

            final int[] biomeIndex = {-1};
            currentTime[0] = measureGenerationTime("loading data", currentTime[0]);
            Map<BiomeStructureData, BiomeStructure> structureDataMap = new ConcurrentHashMap<>();

//////////////////
///////// calculation structure position with wavefunctioncollapse
//////////////////
            List<CompletableFuture<Long>> futures = new ArrayList<>();
            for (BiomeData biome : data.GetBiomes()) {
                if (biome.structures != null) {
                    int biomeWidth = (int) Math.round(biome.width * (double) width);
                    int biomeHeight = (int) Math.round(biome.height * (double) height);
                    for (BiomeStructureData data : biome.structures) {
                        long localSeed = seed;
                        futures.add(CompletableFuture.supplyAsync(()-> {
                            long threadStartTime = System.currentTimeMillis();
                            BiomeStructure structure = new BiomeStructure(data, localSeed, biomeWidth, biomeHeight);
                            structure.initialize();
                            structureDataMap.put(data, structure);
                            return measureGenerationTime("wavefunctioncollapse " + data.sourcePath, threadStartTime);
                        }).exceptionally(ex -> {
                            ex.printStackTrace();
                            return 0L;
                        }));
                    }
                }
            }
            CompletableFuture<?>[] futuresArray = futures.toArray(new CompletableFuture<?>[0]);
            CompletableFuture.allOf(futuresArray).join();
            futures.clear();

//////////////////
///////// calculation each biome position based on noise and radius
//////////////////
            for (BiomeData biome : data.GetBiomes()) {

                biomeIndex[0]++;
                int biomeXStart = (int) Math.round(biome.startPointX * (double) width);
                int biomeYStart = (int) Math.round(biome.startPointY * (double) height);
                int biomeWidth = (int) Math.round(biome.width * (double) width);
                int biomeHeight = (int) Math.round(biome.height * (double) height);

                int beginX = Math.max(biomeXStart - biomeWidth / 2, 0);
                int beginY = Math.max(biomeYStart - biomeHeight / 2, 0);
                int endX = Math.min(biomeXStart + biomeWidth / 2, width);
                int endY = Math.min(biomeYStart + biomeHeight / 2, height);
                if (biome.width == 1.0 && biome.height == 1.0) {
                    beginX = 0;
                    beginY = 0;
                    endX = width;
                    endY = height;
                }
                for (int x = beginX; x < endX; x++) {
                    for (int y = beginY; y < endY; y++) {
                        //value 0-1 based on noise
                        float noiseValue = ((float) noise.eval(x / (float) width * noiseZoom, y / (float) height * noiseZoom) + 1) / 2f;
                        noiseValue *= biome.noiseWeight;
                        //value 0-1 based on dist to origin
                        float distanceValue = ((float) Math.sqrt((x - biomeXStart) * (x - biomeXStart) + (y - biomeYStart) * (y - biomeYStart))) / (Math.max(biomeWidth, biomeHeight) / 2f);
                        distanceValue *= biome.distWeight;
                        if (noiseValue + distanceValue < 1.0 || biome.invertHeight && (1 - noiseValue) + distanceValue < 1.0) {
                            Color color = biome.GetColor();
                            float[] hsv = new float[3];
                            color.toHsv(hsv);
                            int count = (int) ((noiseValue - 0.5) * 10 / 4);
                            //hsv[2]+=(count*0.2);
                            biomeMap[x][y] |= (1L << biomeIndex[0]);
                            int terrainCounter = 1;
                            terrainMap[x][y] = 0;
                            if (biome.terrain != null) {
                                for (BiomeTerrainData terrain : biome.terrain) {
                                    float terrainNoise = ((float) noise.eval(x / (float) width * (noiseZoom * terrain.resolution), y / (float) height * (noiseZoom * terrain.resolution)) + 1) / 2;
                                    if (terrainNoise >= terrain.min && terrainNoise <= terrain.max) {
                                        terrainMap[x][y] = terrainCounter;
                                        //pix.fillRectangle(x*data.miniMapTileSize, y*data.miniMapTileSize,data.miniMapTileSize,data.miniMapTileSize);
                                    }
                                    terrainCounter++;
                                }
                            }
                            if (biome.collision)
                                terrainMap[x][y] |= collisionBit;
                            if (biome.structures != null) {
                                for (BiomeStructureData data : biome.structures) {
                                    while (!structureDataMap.containsKey(data)) {
                                        try {
                                            Thread.sleep(10);
                                        } catch (InterruptedException e) {
                                            throw new RuntimeException(e);
                                        }
                                    }

                                    BiomeStructure structure = structureDataMap.get(data);
                                    int structureXStart = x - (biomeXStart - biomeWidth / 2) - (int) ((data.x * biomeWidth) - (data.width * biomeWidth / 2));
                                    int structureYStart = y - (biomeYStart - biomeHeight / 2) - (int) ((data.y * biomeHeight) - (data.height * biomeHeight / 2));

                                    int structureIndex = structure.objectID(structureXStart, structureYStart);
                                    if (structureIndex >= 0) {

                                        terrainMap[x][y] = terrainCounter + structureIndex;
                                        if (structure.collision(structureXStart, structureYStart))
                                            terrainMap[x][y] |= collisionBit;
                                        terrainMap[x][y] |= isStructureBit;

                                    }

                                    terrainCounter += structure.structureObjectCount();
                                }
                            }
                        }

                    }
                }
            }
            currentTime[0] = measureGenerationTime("biomes in total", currentTime[0]);
            // FORGE-CAMPAIGN: where the region walls will go, before any point of interest is placed.
            campaignWall = null;
            if (layout != null) {
                computeRegionMasks(layout);
            }
            // FORGE-CAMPAIGN end

//////////////////
///////// set poi placement
//////////////////
            List<PointOfInterest> towns = new ArrayList<>();
            List<PointOfInterest> notTowns = new ArrayList<>();
            List<Rectangle> otherPoints = new ArrayList<>();

            TextureAtlas mapMarker = Config.instance().getAtlas(Paths.MAP_MARKER);
            TextureData texture = mapMarker.getTextures().first().getTextureData();
            if (!texture.isPrepared())
                texture.prepare();
            Pixmap mapMarkerPixmap = texture.consumePixmap();
            clearTerrain((int) (data.width * data.playerStartPosX), (int) (data.height * data.playerStartPosY), 10);
            //otherPoints.add(new Rectangle(((float) data.width * data.playerStartPosX * (float) data.tileSize) - data.tileSize * 3, ((float) data.height * data.playerStartPosY * data.tileSize) - data.tileSize * 3, data.tileSize * 6, data.tileSize * 6));
            boolean running = true;
            here:
            while (running) {
                mapPoiIds = new PointOfInterestMap(getChunkSize(), data.tileSize, data.width / getChunkSize(), data.height / getChunkSize());
                int biomeIndex2 = -1;
                running = false;
                for (BiomeData biome : data.GetBiomes()) {
                    biomeIndex2++;
                    // FORGE-CAMPAIGN: authored regions get their points of interest from the layout.
                    if (layout != null && layout.isAuthored(biome.name)) {
                        continue;
                    }
                    // FORGE-CAMPAIGN end
                    for (PointOfInterestData poi : biome.getPointsOfInterest()) {
                        for (int i = 0; i < poi.count; i++) {
                            for (int counter = 0; counter < 500; counter++)//tries 500 times to find a free point
                            {
                                float radius = (float) Math.sqrt(((random.nextDouble()) / 2 * poi.radiusFactor));
                                float theta = (float) (random.nextDouble() * 2 * Math.PI);
                                float x = (float) (radius * Math.cos(theta));
                                x *= (biome.width * width / 2);
                                x += (biome.startPointX * width);
                                float y = (float) (radius * Math.sin(theta));
                                y *= (biome.height * height / 2);
                                y += (height - (biome.startPointY * height));

                                y += (poi.offsetY * (biome.height * height));
                                x += (poi.offsetX * (biome.width * width));

                                if ((int) x < 0 || (int) y <= 0 || (int) y >= height || (int) x >= width || biomeIndex2 != highestBiome(getBiome((int) x, (int) y))) {
                                    continue;
                                }
                                // FORGE-CAMPAIGN: not on or next to a future region wall.
                                if (nearCampaignWall((int) x, height - 1 - (int) y, 4)) {
                                    continue;
                                }

                                x *= data.tileSize;
                                y *= data.tileSize;

                                boolean breakNextLoop = false;
                                for (Rectangle rect : otherPoints) {
                                    if (rect.contains(x, y)) {
                                        breakNextLoop = true;
                                        break;
                                    }
                                }
                                if (breakNextLoop) {
                                    boolean foundSolution = false;
                                    boolean noSolution = false;
                                    breakNextLoop = false;
                                    for (int xi = -1; xi < 2 && !foundSolution; xi++) {
                                        for (int yi = -1; yi < 2 && !foundSolution; yi++) {
                                            for (Rectangle rect : otherPoints) {
                                                if (rect.contains(x + xi * data.tileSize, y + yi * data.tileSize)) {
                                                    noSolution = true;
                                                    break;
                                                }
                                            }
                                            if (!noSolution) {
                                                foundSolution = true;
                                                x = x + xi * data.tileSize;
                                                y = y + yi * data.tileSize;


                                            }
                                        }
                                    }
                                    if (!foundSolution) {
                                        if (counter == 499) {
                                            System.err.print("Can not place POI " + poi.name + "...Rerunning..\n");
                                            running = true;
                                            towns.clear();
                                            notTowns.clear();
                                            otherPoints.clear();
                                            clearTerrain((int) (data.width * data.playerStartPosX), (int) (data.height * data.playerStartPosY), 10);
                                            storedInfo.clear();
                                            continue here;
                                        }
                                        continue;
                                    }
                                }
                                otherPoints.add(new Rectangle(x - data.tileSize * 4, y - data.tileSize * 4, data.tileSize * 8, data.tileSize * 8));
                                PointOfInterest newPoint = new PointOfInterest(poi, new Vector2(x, y), random);
                                clearTerrain((int) (x / data.tileSize), (int) (y / data.tileSize), 3);
                                mapPoiIds.add(newPoint);

                                TextureAtlas.AtlasRegion marker = mapMarker.findRegion(poi.type);

                                if (marker != null) {
                                    int xInPixels = (int) ((x / data.tileSize) * data.miniMapTileSize);
                                    int yInPixels = (int) ((height - (y / data.tileSize)) * data.miniMapTileSize);
                                    xInPixels -= (marker.getRegionWidth() / 2);
                                    yInPixels -= (marker.getRegionHeight() / 2);
                                    drawPixmapLater(mapMarkerPixmap, marker.getRegionX(), marker.getRegionY(),
                                            marker.getRegionWidth(), marker.getRegionHeight(), xInPixels, yInPixels, marker.getRegionWidth(), marker.getRegionHeight());
                                }


                                if (poi.type != null && (poi.type.equals("town") || poi.type.equals("capital"))) {
                                    if (!newPoint.hasDisplayName()) {
                                        if (poi.displayName == null || poi.displayName.isEmpty()) {
                                            newPoint.setDisplayName(biome.getNewTownName());
                                        } else {
                                            newPoint.setDisplayName(poi.getDisplayName());
                                        }
                                    }
                                    towns.add(newPoint);
                                } else {
                                    notTowns.add(newPoint);
                                }
                                break;
                            }
                        }
                    }
                }
            }
            // FORGE-CAMPAIGN: points of interest at fixed tiles from the layout (map tiles from the top).
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
            currentTime[0] = measureGenerationTime("poi placement", currentTime[0]);

//////////////////
///////// sort towns and build roads in between
//////////////////
            List<Pair<PointOfInterest, PointOfInterest>> allSortedTowns = new ArrayList<>();

            HashSet<Long> usedEdges = new HashSet<>();//edge is first 32 bits id of first id and last 32 bits id of second
            for (int i = 0; i < towns.size() - 1; i++) {

                PointOfInterest current = towns.get(i);
                int smallestIndex = -1;
                int secondSmallestIndex = -1;
                float smallestDistance = Float.MAX_VALUE;
                for (int j = 0; j < towns.size(); j++) {

                    if (i == j || usedEdges.contains((long) i | ((long) j << 32)))
                        continue;
                    float dist = current.getPosition().dst(towns.get(j).getPosition());
                    if (dist > data.maxRoadDistance)
                        continue;
                    if (dist < smallestDistance) {
                        smallestDistance = dist;
                        secondSmallestIndex = smallestIndex;
                        smallestIndex = j;

                    }
                }
                if (smallestIndex < 0)
                    continue;
                usedEdges.add((long) i | ((long) smallestIndex << 32));
                usedEdges.add((long) i << 32 | ((long) smallestIndex));
                allSortedTowns.add(Pair.of(current, towns.get(smallestIndex)));

                if (secondSmallestIndex < 0)
                    continue;
                usedEdges.add((long) i | ((long) secondSmallestIndex << 32));
                usedEdges.add((long) i << 32 | ((long) secondSmallestIndex));
                //allSortedTowns.add(Pair.of(current, towns.get(secondSmallestIndex)));
            }
            List<Pair<PointOfInterest, PointOfInterest>> allPOIPathsToNextTown = new ArrayList<>();
            for (int i = 0; i < notTowns.size() - 1; i++) {

                PointOfInterest poi = notTowns.get(i);
                int smallestIndex = -1;
                float smallestDistance = Float.MAX_VALUE;
                for (int j = 0; j < towns.size(); j++) {

                    float dist = poi.getPosition().dst(towns.get(j).getPosition());
                    if (dist < smallestDistance) {
                        smallestDistance = dist;
                        smallestIndex = j;

                    }
                }
                if (smallestIndex < 0)
                    continue;
                allPOIPathsToNextTown.add(Pair.of(poi, towns.get(smallestIndex)));
            }
            biomeIndex[0]++;

            //reset terrain path to the next town
            for (Pair<PointOfInterest, PointOfInterest> poiToTown : allPOIPathsToNextTown) {
                futures.add(CompletableFuture.supplyAsync(()-> {
                    int startX = (int) poiToTown.getKey().getTilePosition(data.tileSize).x;
                    int startY = (int) poiToTown.getKey().getTilePosition(data.tileSize).y;
                    int x1 = (int) poiToTown.getValue().getTilePosition(data.tileSize).x;
                    int y1 = (int) poiToTown.getValue().getTilePosition(data.tileSize).y;
                    int dx = Math.abs(x1 - startX);
                    int dy = Math.abs(y1 - startY);
                    int sx = startX < x1 ? 1 : -1;
                    int sy = startY < y1 ? 1 : -1;
                    int err = dx - dy;
                    int e2;
                    for (int i = 0; i < 1000; i++) {
                        if (startX < 0 || startY <= 0 || startX >= width || startY > height) continue;
                        if ((terrainMap[startX][height - startY] & collisionBit) != 0)//clear terrain if it has collision
                            terrainMap[startX][height - startY] = 0;

                        if (startX == x1 && startY == y1)
                            break;
                        e2 = 2 * err;
                        if (e2 > -dy) {
                            err = err - dy;
                            startX = startX + sx;
                        } else if (e2 < dx) {
                            err = err + dx;
                            startY = startY + sy;
                        }
                    }
                    return 0L;
                }).exceptionally(ex -> {
                    ex.printStackTrace();
                    return 0L;
                }));
            }
            futuresArray = futures.toArray(new CompletableFuture<?>[0]);
            CompletableFuture.allOf(futuresArray).join();
            futures.clear();
            for (Pair<PointOfInterest, PointOfInterest> townPair : allSortedTowns) {
                futures.add(CompletableFuture.supplyAsync(()-> {
                    int startX = (int) townPair.getKey().getTilePosition(data.tileSize).x;
                    int startY = (int) townPair.getKey().getTilePosition(data.tileSize).y;
                    int x1 = (int) townPair.getValue().getTilePosition(data.tileSize).x;
                    int y1 = (int) townPair.getValue().getTilePosition(data.tileSize).y;
                    for (int x = startX - 1; x < startX + 2; x++) {
                        for (int y = startY - 1; y < startY + 2; y++) {
                            if (x < 0 || y < 0 || x >= width || y >= height) continue;
                            biomeMap[x][height - y - 1] |= (1L << biomeIndex[0]);
                            terrainMap[x][height - y - 1] = 0;
                        }
                    }
                    int dx = Math.abs(x1 - startX);
                    int dy = Math.abs(y1 - startY);
                    int sx = startX < x1 ? 1 : -1;
                    int sy = startY < y1 ? 1 : -1;
                    int err = dx - dy;
                    int e2;
                    for (int i = 0; i < 1000; i++) {
                        if (startX < 0 || startY <= 0 || startX >= width || startY > height) continue;
                        biomeMap[startX][height - startY] |= (1L << biomeIndex[0]);
                        terrainMap[startX][height - startY] = 0;

                        if (startX == x1 && startY == y1)
                            break;
                        e2 = 2 * err;
                        if (e2 > -dy) {
                            err = err - dy;
                            startX = startX + sx;
                        } else if (e2 < dx) {
                            err = err + dx;
                            startY = startY + sy;
                        }
                    }
                    return 0L;
                }).exceptionally(ex -> {
                    ex.printStackTrace();
                    return 0L;
                }));
            }
            futuresArray = futures.toArray(new CompletableFuture<?>[0]);
            CompletableFuture.allOf(futuresArray).join();
            futures.clear();
            currentTime[0] = measureGenerationTime("roads", currentTime[0]);
            // FORGE-CAMPAIGN: water walls between regions, opened at passes.
            if (layout != null) {
                applyRegionWalls(layout);
                currentTime[0] = measureGenerationTime("region walls", currentTime[0]);
            }
            // FORGE-CAMPAIGN end

//////////////////
///////// draw mini map
//////////////////

            Pixmap pix = new Pixmap(width * data.miniMapTileSize, height * data.miniMapTileSize, Pixmap.Format.RGBA8888);
            pix.setColor(1, 0, 0, 1);
            pix.fill();
            for (int x = 0; x < width; x++) {
                for (int y = 0; y < height; y++) {
                    if (highestBiome(biomeMap[x][y]) >= data.GetBiomes().size()) {
                        Pixmap smallPixmap = createSmallPixmap(data.roadTileset.tilesetAtlas, data.roadTileset.tilesetName, 0);
                        pix.drawPixmap(smallPixmap, x * data.miniMapTileSize, y * data.miniMapTileSize);
                    } else {

                        BiomeData biome = data.GetBiomes().get(highestBiome(biomeMap[x][y]));
                        int terrainIndex = terrainMap[x][y] & ~terrainMask;
                        if (terrainIndex > biome.terrain.length) {
                            Pixmap smallPixmap = createSmallPixmap(biome.tilesetAtlas, biome.tilesetName, 0);
                            pix.drawPixmap(smallPixmap, x * data.miniMapTileSize, y * data.miniMapTileSize);

                            terrainIndex -= biome.terrain.length;
                            terrainIndex--;
                            for (BiomeStructureData structData : biome.structures) {
                                if (terrainIndex >= structData.mappingInfo.length) {
                                    terrainIndex -= structData.mappingInfo.length;
                                    continue;
                                }
                                smallPixmap = createSmallPixmap(structData.structureAtlasPath, structData.mappingInfo[terrainIndex].name, 0);
                                pix.drawPixmap(smallPixmap, x * data.miniMapTileSize, y * data.miniMapTileSize);
                                break;
                            }
                        } else {
                            Pixmap smallPixmap = createSmallPixmap(biome.tilesetAtlas, biome.tilesetName, terrainIndex);
                            pix.drawPixmap(smallPixmap, x * data.miniMapTileSize, y * data.miniMapTileSize);
                        }

                    }

                }

            }
            for (Map.Entry<String, Pair<Pixmap, HashMap<String, Pixmap>>> entry : pixmapHash.entrySet()) {
                try {
                    entry.getValue().getLeft().dispose();
                } catch (Exception e) {
                    //e.printStackTrace();
                }
                for (Map.Entry<String, Pixmap> pairEntry : entry.getValue().getRight().entrySet()) {
                    try {
                        pairEntry.getValue().dispose();
                    } catch (Exception e) {
                        //e.printStackTrace();
                    }
                }
            }
            pixmapHash.clear();
            try {
                drawPixmapNow(pix);
            } catch (Exception e) {
                //e.printStackTrace();
            }
            currentTime[0] = measureGenerationTime("mini map", currentTime[0]);


//////////////////
///////// distribute small rocks and trees across the map
//////////////////
            mapObjectIds = new SpritesDataMap(getChunkSize(), data.tileSize, data.width / getChunkSize());
            for (int x = 0; x < width; x++) {
                for (int y = 0; y < height; y++) {
                    int invertedHeight = height - y - 1;
                    int currentBiome = highestBiome(biomeMap[x][invertedHeight]);
                    if (currentBiome >= data.GetBiomes().size())
                        continue;//roads
                    if (isStructure(x, y))
                        continue;
                    BiomeData biome = data.GetBiomes().get(currentBiome);
                    for (String name : biome.spriteNames) {
                        BiomeSpriteData sprite = data.GetBiomeSprites().getSpriteData(name);
                        double spriteNoise = (noise.eval(x / (double) width * noiseZoom * sprite.resolution, y / (double) invertedHeight * noiseZoom * sprite.resolution) + 1) / 2;
                        if (spriteNoise >= sprite.startArea && spriteNoise <= sprite.endArea) {
                            if (random.nextFloat() <= sprite.density) {
                                String spriteKey = sprite.key();
                                int key;
                                if (!mapObjectIds.containsKey(spriteKey)) {

                                    key = mapObjectIds.put(sprite.key(), sprite, data.GetBiomeSprites());
                                } else {
                                    key = mapObjectIds.intKey(spriteKey);
                                }
                                mapObjectIds.putPosition(key, new Vector2((((float) x) + .25f + random.nextFloat() / 2) * data.tileSize, (((float) y + .25f) - random.nextFloat() / 2) * data.tileSize));
                                break;//only on sprite per point
                            }
                        }
                    }
                }
            }
            mapMarkerPixmap.dispose();
            biomeImage = pix;
            measureGenerationTime("sprites", currentTime[0]);
            System.out.println("Generating world took :\t\t" + ((System.currentTimeMillis() - startTime) / 1000f) + " s");
            // FORGE-CAMPAIGN: -Dcampaign.dumpWorld=<file.png> saves the minimap, to author the layout.
            String dump = System.getProperty("campaign.dumpWorld");
            if (dump != null && !dump.isEmpty()) {
                com.badlogic.gdx.graphics.PixmapIO.writePNG(new FileHandle(dump), biomeImage);
                System.out.println("[campaign] world map written to " + dump + " (seed " + this.seed + ")");
            }
            // FORGE-CAMPAIGN end
            WorldStage.getInstance().clearCache();

            if (GuiBase.isMobile())
                GuiBase.getInterface().preventSystemSleep(false);
        } catch (Exception e) {
            e.printStackTrace();
            return false;
        }
        return true;
    }

    HashMap<String, Pair<Pixmap, HashMap<String, Pixmap>>> pixmapHash = new HashMap<>();

    private Pixmap createSmallPixmap(String tilesetName, String key, int i) {

        if (i > 2) i = 2;
        String tileSetNameWithIndex;
        if (i == 0)
            tileSetNameWithIndex = (key);
        else
            tileSetNameWithIndex = (key + "_" + i);
        if (!pixmapHash.containsKey(tilesetName)) {
            TextureAtlas.AtlasRegion region;
            TextureAtlas atlas = Config.instance().getAtlas(tilesetName);
            region = atlas.findRegion(tileSetNameWithIndex);
            TextureData data = region.getTexture().getTextureData();
            if (!data.isPrepared()) {
                data.prepare();
            }
            pixmapHash.put(tilesetName, Pair.of(data.consumePixmap(), new HashMap<>()));
        }
        Pair<Pixmap, HashMap<String, Pixmap>> pair = pixmapHash.get(tilesetName);
        if (!pair.getRight().containsKey(tileSetNameWithIndex)) {
            TextureAtlas atlas = Config.instance().getAtlas(tilesetName);
            TextureAtlas.AtlasRegion region = atlas.findRegion(tileSetNameWithIndex);
            int tileSize = data.tileSize;
            Pixmap smallPixmap = new Pixmap(data.miniMapTileSize, data.miniMapTileSize, Pixmap.Format.RGBA8888);
            smallPixmap.setColor(0, 0, 0, 0);
            smallPixmap.fill();
            smallPixmap.drawPixmap(pair.getLeft(), 0, 0, region.getRegionX(), region.getRegionY(), data.miniMapTileSize, data.miniMapTileSize);
            pair.getRight().put(tileSetNameWithIndex, smallPixmap);
        }
        return pair.getRight().get(tileSetNameWithIndex);

    }

    static class DrawInfo {
        Pixmap mapMarkerPixmap;
        int regionX;
        int regionY;
        int regionWidth;
        int regionHeight;
        int x;
        int y;
        int regionWidth1;
        int regionHeight1;
    }

    final Array<DrawInfo> storedInfo = new Array<>();

    private void drawPixmapLater(Pixmap mapMarkerPixmap, int regionX, int regionY, int regionWidth, int regionHeight, int x, int y, int regionWidth1, int regionHeight1) {
        DrawInfo info = new DrawInfo();
        info.mapMarkerPixmap = mapMarkerPixmap;
        info.regionX = regionX;
        info.regionY = regionY;
        info.regionWidth = regionWidth;
        info.regionHeight = regionHeight;
        info.x = x;
        info.y = y;
        info.regionWidth1 = regionWidth1;
        info.regionHeight1 = regionHeight1;
        storedInfo.add(info);
    }

    private void drawPixmapNow(Pixmap map) {
        for (DrawInfo info : storedInfo)
            map.drawPixmap(info.mapMarkerPixmap, info.regionX, info.regionY, info.regionWidth, info.regionHeight, info.x, info.y, info.regionWidth1, info.regionHeight1);
        storedInfo.clear();
    }

    public int getWidthInTiles() {
        return width;
    }

    public int getHeightInTiles() {
        return height;
    }

    public int getWidthInPixels() {
        return width * data.tileSize;
    }

    public int getHeightInPixels() {
        return height * data.tileSize;
    }

    public int getWidthInChunks() {
        return width / getChunkSize();
    }

    public int getHeightInChunks() {
        return height / getChunkSize();
    }

    public int getTileSize() {
        return data.tileSize;
    }

    public Pixmap getBiomeImage() {
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
    // FORGE-CAMPAIGN end

    public List<Pair<Vector2, Integer>> GetMapObjects(int chunkX, int chunkY) {
        return mapObjectIds.positions(chunkX, chunkY);
    }

    public List<PointOfInterest> getPointsOfInterest(Actor player) {
        return mapPoiIds.pointsOfInterest((int) player.getX() / data.tileSize / getChunkSize(), (int) player.getY() / data.tileSize / getChunkSize());
    }

    public List<PointOfInterest> getPointsOfInterest(int chunkX, int chunkY) {
        return mapPoiIds.pointsOfInterest(chunkX, chunkY);
    }

    public PointOfInterest findPointsOfInterest(String name) {
        return mapPoiIds.findPointsOfInterest(name);
    }

    public List<PointOfInterest> getAllPointOfInterest(){
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
    }

    public int getChunkSize() {
        return (Math.max(Scene.getIntendedWidth(), Scene.getIntendedHeight())) / data.tileSize;
    }

    public void dispose() {
        drawingInfoCache.clear();
        Forge.safeDispose(biomeImage, globalTileDrawing, globalTexture, emptyTile);
    }

    public void setSeed(long seedOffset) {
        random.setSeed(seedOffset + seed);
    }

    public Texture getGlobalTexture() {
        if (globalTexture == null) {
            globalTexture = Forge.getAssets().getTexture(Config.instance().getFile("ui/sprite_markers.png"), true, true);
            System.out.print("Loading auxiliary sprites.\n");
        }
        return globalTexture;
    }
}
