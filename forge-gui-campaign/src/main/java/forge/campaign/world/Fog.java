package forge.campaign.world;

import com.badlogic.gdx.graphics.Pixmap;
import forge.adventure.player.AdventurePlayer;
import forge.adventure.util.Current;
import forge.adventure.world.World;

import java.util.Arrays;

/**
 * Fog of war on the overworld map (the HUD minimap and the full map screen).
 *
 * Both screens take the map image from World.getBiomeImage(), which our World shadow routes here.
 * A region is revealed if the layout says so from the start (the hub) or once its tower flag is
 * set (the watchtower's dialog sets it). Unrevealed regions are painted dark, which also hides
 * their point-of-interest markers; water stays visible only near revealed land, so the dark lands
 * do not give away their shape. The fogged image is cached until what is revealed changes: the
 * minimap texture cache keys on the image object, so returning the same object costs nothing.
 * The clear image is what gets saved (World.save reads its own field).
 */
public final class Fog {
    private static final int COAST = 6; // tiles of water shown around revealed land
    private static Pixmap fogged;
    private static Pixmap source;
    private static String signature;

    private Fog() {
    }

    public static synchronized Pixmap apply(World world, Pixmap clear) {
        RegionLayout layout = RegionLayout.get();
        if (layout == null || clear == null) {
            return clear;
        }
        boolean[] revealed = revealed(layout);
        boolean all = true;
        for (boolean r : revealed) {
            all &= r;
        }
        if (all) {
            return clear;
        }
        String sig = Arrays.toString(revealed);
        if (fogged != null && source == clear && sig.equals(signature)) {
            return fogged;
        }
        int width = world.getWidthInTiles();
        int height = world.getHeightInTiles();
        int tile = clear.getWidth() / width;
        boolean[][] visible = new boolean[width][height];
        boolean[][] land = new boolean[width][height];
        for (int x = 0; x < width; x++) {
            for (int y = 0; y < height; y++) {
                int r = world.campaignRegionAt(x, y);
                land[x][y] = r >= 0;
                visible[x][y] = r >= 0 && revealed[r];
            }
        }
        boolean[][] nearVisible = dilate(visible, width, height, COAST);
        Pixmap out = new Pixmap(clear.getWidth(), clear.getHeight(), clear.getFormat());
        out.setBlending(Pixmap.Blending.None);
        out.drawPixmap(clear, 0, 0);
        out.setBlending(Pixmap.Blending.SourceOver);
        out.setColor(0.04f, 0.04f, 0.07f, 0.93f);
        for (int x = 0; x < width; x++) {
            for (int y = 0; y < height; y++) {
                boolean dark = land[x][y] ? !visible[x][y] : !nearVisible[x][y];
                if (dark) {
                    out.fillRectangle(x * tile, y * tile, tile, tile);
                }
            }
        }
        if (fogged != null) {
            fogged.dispose();
        }
        fogged = out;
        source = clear;
        signature = sig;
        return out;
    }

    /** Which layout regions the player can see now. */
    public static boolean[] revealed(RegionLayout layout) {
        AdventurePlayer player = Current.player();
        boolean[] out = new boolean[layout.regions.size()];
        for (int i = 0; i < out.length; i++) {
            RegionLayout.Region r = layout.regions.get(i);
            out[i] = r.revealedAtStart()
                    || (r.towerFlag() != null && player != null && player.getQuestFlag(r.towerFlag()) >= 1);
        }
        return out;
    }

    /** Grows a mask by a square of radius r (two passes, so it stays cheap on a 700x700 map). */
    private static boolean[][] dilate(boolean[][] in, int width, int height, int r) {
        boolean[][] across = new boolean[width][height];
        for (int y = 0; y < height; y++) {
            int last = -1_000_000;
            for (int x = 0; x < width; x++) {
                if (in[x][y]) {
                    last = x;
                }
                across[x][y] = x - last <= r;
            }
            last = 1_000_000;
            for (int x = width - 1; x >= 0; x--) {
                if (in[x][y]) {
                    last = x;
                }
                across[x][y] |= last - x <= r;
            }
        }
        boolean[][] out = new boolean[width][height];
        for (int x = 0; x < width; x++) {
            int last = -1_000_000;
            for (int y = 0; y < height; y++) {
                if (across[x][y]) {
                    last = y;
                }
                out[x][y] = y - last <= r;
            }
            last = 1_000_000;
            for (int y = height - 1; y >= 0; y--) {
                if (across[x][y]) {
                    last = y;
                }
                out[x][y] |= last - y <= r;
            }
        }
        return out;
    }
}
