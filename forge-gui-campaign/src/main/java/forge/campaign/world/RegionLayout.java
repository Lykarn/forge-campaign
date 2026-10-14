package forge.campaign.world;

import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.utils.JsonReader;
import com.badlogic.gdx.utils.JsonValue;
import forge.adventure.util.Config;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The authored world: world/region_layout.json in the plane, read by our shadowed World.
 *
 * Adventure normally scatters points of interest at random over a noise map that differs every
 * game. With a layout, the world uses a fixed seed (so the terrain is the same in every game and
 * authored positions stay valid), points of interest in authored regions sit at fixed tiles, and
 * water walls separate regions except at passes. A pass can be a gate: blocked until a quest flag
 * is set (the gate's own map sets it when the player brings the key), or closed for good.
 *
 * Coordinates are map tiles counted from the top-left, the same as the minimap image divided by
 * its tile size (4 px), so positions can be read straight off a picture of the map.
 */
public final class RegionLayout {
    public static final String FILE = "world/region_layout.json";

    /** authored: its points of interest come from this file, not Adventure's random placement.
     *  pool: the card pool (plane/card_scores.json) its merchants and rewards draw from.
     *  requiresFlag: a quest flag that must be set before quests may send the player here (its gate). */
    public record Region(String id, String name, List<String> biomes, String towerFlag, boolean revealedAtStart,
                         boolean authored, String pool, String requiresFlag) {
    }

    public record Poi(String name, int x, int y, String displayName) {
    }

    /** A gap in the walls. gateFlag null = always open; closed = never opens. */
    public record Pass(String id, int x, int y, int radius, String gateFlag, boolean closed) {
    }

    private static RegionLayout instance;
    private static boolean loaded;

    public final long seed;
    public final int wallWidth;
    public final List<Region> regions = new ArrayList<>();
    public final List<Poi> pois = new ArrayList<>();
    public final List<Pass> passes = new ArrayList<>();
    private final Map<String, Region> regionOfBiome = new HashMap<>();

    /** The plane's layout, or null when the plane has none (then the world is Adventure's own). */
    public static synchronized RegionLayout get() {
        if (!loaded) {
            loaded = true;
            FileHandle file = Config.instance().getFile(FILE);
            if (file != null && file.exists()) {
                instance = new RegionLayout(new JsonReader().parse(file));
                System.out.println("[campaign] region layout: " + instance.regions.size() + " regions, "
                        + instance.pois.size() + " points of interest, " + instance.passes.size() + " passes");
            }
        }
        return instance;
    }

    public RegionLayout(JsonValue root) {
        seed = root.getLong("seed", 0);
        wallWidth = root.getInt("wallWidth", 3);
        for (JsonValue r = child(root, "regions"); r != null; r = r.next) {
            List<String> biomes = new ArrayList<>();
            for (JsonValue b = child(r, "biomes"); b != null; b = b.next) {
                biomes.add(b.asString());
            }
            Region region = new Region(r.getString("id"), r.getString("name", r.getString("id")), biomes,
                    r.getString("towerFlag", null), r.getBoolean("revealedAtStart", false),
                    r.getBoolean("authored", false), r.getString("pool", null), r.getString("requiresFlag", null));
            regions.add(region);
            for (String b : biomes) {
                regionOfBiome.put(b, region);
            }
        }
        for (JsonValue p = child(root, "pois"); p != null; p = p.next) {
            pois.add(new Poi(p.getString("name"), p.getInt("x"), p.getInt("y"), p.getString("displayName", null)));
        }
        for (JsonValue p = child(root, "passes"); p != null; p = p.next) {
            passes.add(new Pass(p.getString("id"), p.getInt("x"), p.getInt("y"), p.getInt("radius", 3),
                    p.getString("gateFlag", null), p.getBoolean("closed", false)));
        }
    }

    private static JsonValue child(JsonValue v, String name) {
        JsonValue list = v.get(name);
        return list == null ? null : list.child;
    }

    /** The region a biome belongs to, or null. */
    public Region regionOf(String biomeName) {
        return regionOfBiome.get(biomeName);
    }

    /** True when the region holding this biome has authored points of interest (no random ones). */
    public boolean isAuthored(String biomeName) {
        Region r = regionOfBiome.get(biomeName);
        return r != null && r.authored();
    }
}
