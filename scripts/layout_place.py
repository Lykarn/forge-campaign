"""Place points of interest and passes of plane/world/region_layout.json automatically.

Reads the region map from scripts/dump_world.py (_build/out/world_regions.png) and fills in:
  - points of interest marked "auto": true (and their x/y): spread over their region's land,
    at least --margin tiles from its edge and as far as possible from every other point of
    interest; one marked "far": true (a castle) goes to the region's tile farthest from the hub.
  - passes marked "auto": true with "between": [a, b]: the shortest crossing of the wall between
    regions a and b, at the point nearest the middle of the two regions' authored points.
  - a point of interest with "atPass": "<pass id>" and "side": "<region>": just inside that
    region, in front of the pass (a gate or a sign).
Fixed coordinates are never moved. Placement is deterministic, so re-running gives the same
layout. Re-run scripts/dump_world.py then scripts/layout_check.py to see the result.

Usage: python scripts/layout_place.py [--margin 7] [--spacing 22]
"""
from __future__ import annotations

import argparse
import json
import math
import sys

from common import OUT, ROOT
from layout_check import COLOURS, WALL, PASS, read_png

LAYOUT = ROOT / "plane" / "world" / "region_layout.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--margin", type=int, default=7)
    parser.add_argument("--spacing", type=int, default=22, help="minimum tiles between points of interest")
    args = parser.parse_args()
    png = OUT / "world_regions.png"
    if not png.is_file():
        sys.exit(f"{png} not found: run scripts/dump_world.py first")
    width, height, grid = read_png(png)
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    ids = [r["id"] for r in layout["regions"]]
    colour = {rid: COLOURS[i % len(COLOURS)] for i, rid in enumerate(ids)}
    red = 0xff0000

    def region_at(x, y):
        c = grid[y][x]
        for rid, col in colour.items():
            if c == col:
                return rid
        return None

    # Distance (in tiles) from each land tile to the nearest tile that is not that region, by BFS.
    from collections import deque
    edge = [[0] * width for _ in range(height)]
    queue = deque()
    for y in range(height):
        for x in range(width):
            here = region_at(x, y) if grid[y][x] != red else "?"
            if here is None:
                edge[y][x] = 0
                queue.append((x, y))
            else:
                edge[y][x] = -1
    while queue:
        x, y = queue.popleft()
        # 8 neighbours: the distance is then a clear square around the tile, as layout_check wants.
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1),
                       (x + 1, y + 1), (x - 1, y - 1), (x + 1, y - 1), (x - 1, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and edge[ny][nx] < 0:
                edge[ny][nx] = edge[y][x] + 1
                queue.append((nx, ny))

    # Each region's main landmass: walls can cut scraps off a region, and a point of interest on a
    # scrap could never be reached. The main piece is the one holding the region's fixed points
    # of interest (Spawn, for the hub), else its largest.
    component = [[-1] * width for _ in range(height)]
    sizes = []
    for y in range(height):
        for x in range(width):
            if component[y][x] >= 0 or region_at(x, y) is None and grid[y][x] != red:
                continue
            rid = region_at(x, y)
            if rid is None:
                continue
            cid = len(sizes)
            sizes.append(0)
            stack = [(x, y)]
            component[y][x] = cid
            while stack:
                cx, cy = stack.pop()
                sizes[cid] += 1
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < width and 0 <= ny < height and component[ny][nx] < 0 \
                            and (region_at(nx, ny) == rid or grid[ny][nx] == red):
                        component[ny][nx] = cid
                        stack.append((nx, ny))
    main_piece = {}
    for rid in ids:
        fixed = [component[p["y"]][p["x"]] for p in layout["pois"]
                 if p.get("region") == rid and "x" in p and not p.get("auto") and not p.get("atPass")
                 and component[p["y"]][p["x"]] >= 0]
        if fixed:
            main_piece[rid] = max(set(fixed), key=fixed.count)
        else:
            pieces = {component[y][x] for y in range(0, height, 3) for x in range(0, width, 3)
                      if region_at(x, y) == rid and component[y][x] >= 0}
            main_piece[rid] = max(pieces, key=lambda c: sizes[c]) if pieces else -1

    def tiles_of(rid):
        col = colour[rid]
        return [(x, y) for y in range(0, height, 2) for x in range(0, width, 2)
                if grid[y][x] == col and edge[y][x] >= args.margin and component[y][x] == main_piece[rid]]

    placed = [(p["x"], p["y"]) for p in layout["pois"] if "x" in p and not p.get("auto")]
    hub = next((p for p in layout["pois"] if p["name"] == "Spawn"), {"x": width // 2, "y": height // 2})

    def centre(rid):
        pts = [(p["x"], p["y"]) for p in layout["pois"] if p.get("region") == rid and "x" in p and not p.get("auto")]
        if not pts:
            ts = tiles_of(rid)
            pts = ts or [(width // 2, height // 2)]
        return (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))

    # Passes first: gates and signs are placed in front of them.
    for pas in layout["passes"]:
        if not pas.get("auto"):
            continue
        a, b = pas["between"]
        ca, cb = centre(a), centre(b)
        mid = ((ca[0] + cb[0]) / 2, (ca[1] + cb[1]) / 2)
        best = None
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                if grid[y][x] not in (WALL, PASS):
                    continue
                # A crossing: region a and region b both within reach across this wall tile.
                ra = rb = None
                for d in range(1, 9):
                    for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d)):
                        xx, yy = x + dx, y + dy
                        if 0 <= xx < width and 0 <= yy < height:
                            r = region_at(xx, yy)
                            main = component[yy][xx]
                            if r == a and main == main_piece[a] and ra is None:
                                ra = d
                            if r == b and main == main_piece[b] and rb is None:
                                rb = d
                    if ra and rb:
                        break
                if not (ra and rb):
                    continue
                score = (ra + rb) * 10 + math.dist((x, y), mid)
                if best is None or score < best[0]:
                    best = (score, x, y, ra + rb)
        if best is None:
            sys.exit(f"pass {pas['id']}: no crossing between {a} and {b}")
        pas["x"], pas["y"] = best[1], best[2]
        pas["radius"] = max(4, best[3] // 2 + 2)
        print(f"  pass {pas['id']}: ({pas['x']}, {pas['y']}) radius {pas['radius']}")

    passes = {p["id"]: p for p in layout["passes"]}
    for poi in layout["pois"]:
        if not poi.get("atPass"):
            continue
        pas = passes[poi["atPass"]]
        side = poi.get("side", poi.get("region"))
        best = None
        for (x, y) in tiles_of(side) + [(x, y) for y in range(max(0, pas["y"] - 20), min(height, pas["y"] + 20))
                                         for x in range(max(0, pas["x"] - 20), min(width, pas["x"] + 20))
                                         if region_at(x, y) == side and edge[y][x] >= 3]:
            d = math.dist((x, y), (pas["x"], pas["y"]))
            if d < pas["radius"] + 3:
                continue
            if best is None or d < best[0]:
                best = (d, x, y)
        poi["x"], poi["y"] = best[1], best[2]
        poi.pop("auto", None)
        placed.append((poi["x"], poi["y"]))
        print(f"  {poi['name']:28} ({poi['x']}, {poi['y']})  in front of {pas['id']}")

    for poi in sorted(layout["pois"], key=lambda p: not p.get("far")):
        if not poi.get("auto"):
            continue
        tiles = tiles_of(poi["region"])
        if not tiles:
            sys.exit(f"{poi['name']}: no room in region {poi['region']}")
        if poi.get("far"):
            pick = max(tiles, key=lambda t: math.dist(t, (hub["x"], hub["y"])))
        else:
            ok = [t for t in tiles if all(math.dist(t, p) >= args.spacing for p in placed)] or tiles
            pick = max(ok, key=lambda t: (min((math.dist(t, p) for p in placed), default=1e9), -t[0], -t[1]))
        poi["x"], poi["y"] = pick
        placed.append(pick)
        print(f"  {poi['name']:28} ({poi['x']}, {poi['y']})  {poi['region']}")
    # Keep the auto marks: re-running after a map change re-places them; fixed points stay.
    LAYOUT.write_text(json.dumps(layout, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{LAYOUT.relative_to(ROOT)} updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
