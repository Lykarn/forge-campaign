"""Check (and suggest fixes for) the layout against the region map from scripts/dump_world.py.

Reads _build/out/world_regions.png (1 px per tile: one colour per region, walls dark, passes
yellow) and, for every point of interest in plane/world/region_layout.json, reports its region.
With "region" set on a layout entry, a point of interest outside that region, or closer than
--margin tiles to its edge, gets a suggested tile: the nearest one that fits.

Standard library only (a small PNG reader), like the other scripts.

Usage: python scripts/layout_check.py [--margin 5]
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from collections import deque

from common import OUT, ROOT

# Region colours as World.dumpRegions draws them, in layout order; then wall, pass, ocean.
COLOURS = [0xb0b0b0, 0xf0e6b0, 0x80c8f0, 0x505050, 0xe07050, 0x70c050, 0xc090e0, 0x90e0c0]
WALL, PASS, OCEAN = 0x103060, 0xffe000, 0x2060a0


def read_png(path) -> tuple[int, int, list[list[int]]]:
    """RGBA 8-bit PNG -> rows of 0xRRGGBB values."""
    data = path.read_bytes()
    pos, idat, width, height = 8, b"", 0, 0
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height = struct.unpack(">II", chunk[:8])
        elif kind == b"IDAT":
            idat += chunk
        pos += 12 + length
    raw = zlib.decompress(idat)
    bpp, stride = 4, width * 4
    rows, prev = [], bytearray(stride)
    for y in range(height):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append([(line[x * 4] << 16) | (line[x * 4 + 1] << 8) | line[x * 4 + 2] for x in range(width)])
        prev = line
    return width, height, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--margin", type=int, default=5)
    args = parser.parse_args()
    png = OUT / "world_regions.png"
    if not png.is_file():
        sys.exit(f"{png} not found: run scripts/dump_world.py first")
    width, height, grid = read_png(png)
    layout = json.loads((ROOT / "plane" / "world" / "region_layout.json").read_text(encoding="utf-8"))
    ids = [r["id"] for r in layout["regions"]]
    colour_of = {rid: COLOURS[i % len(COLOURS)] for i, rid in enumerate(ids)}
    name_of = {v: k for k, v in colour_of.items()} | {WALL: "WALL", PASS: "pass", OCEAN: "OCEAN"}

    # The dump draws each point of interest as a red dot: read those pixels as what lies under them.
    red = 0xff0000

    def fits(x, y, colour, margin):
        for dx in range(-margin, margin + 1):
            for dy in range(-margin, margin + 1):
                xx, yy = x + dx, y + dy
                if not (0 <= xx < width and 0 <= yy < height) or grid[yy][xx] not in (colour, red):
                    return False
        return True

    def under(x, y):
        for r in range(0, 6):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if 0 <= x + dx < width and 0 <= y + dy < height and grid[y + dy][x + dx] != red:
                        return grid[y + dy][x + dx]
        return red

    problems = 0
    for poi in layout["pois"]:
        x, y = poi["x"], poi["y"]
        c = under(x, y)
        here = name_of.get(c, f"#{c:06x}")
        want = poi.get("region")
        # Signs and gates stand next to their pass on purpose: a smaller margin for them.
        margin = 2 if poi.get("atPass") else args.margin
        ok = want is None or fits(x, y, colour_of[want], margin)
        line = f"  {poi['name']:24} ({x:3}, {y:3})  {here:6}"
        if not ok:
            problems += 1
            target = colour_of[want]
            seen, queue, found = {(x, y)}, deque([(x, y)]), None
            while queue:
                cx, cy = queue.popleft()
                if fits(cx, cy, target, margin):
                    found = (cx, cy)
                    break
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        queue.append((nx, ny))
            line += f"  -> should be {want}: try ({found[0]}, {found[1]})" if found else f"  -> no {want} tile fits"
        print(line)
    print(f"{problems} point(s) of interest to move" if problems else "all points of interest fit their regions")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
