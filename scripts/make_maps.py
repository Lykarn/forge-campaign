"""Build the authored points of interest of plane/world/region_layout.json: maps and data.

Each layout entry with a "build" block becomes a point of interest of its own, with a map
generated from one of Forge's (paths rewritten to point back at common/):
  town        a copy of an upstream town with ONE merchant (the region's curated merchant shop)
  watchtower  a small map whose dialog sets the region's tower flag (lifts its fog of war)
  gate        a small map whose dialog opens the pass (sets its quest flag) if you hold the key
  closed      a small map with a sign: the road opens in a later update
  keyfort     a copy of an upstream dungeon whose treasure chest holds the gate's key
and plane/world/points_of_interest.patch.json lists them (package.py merges it into Adventure's
list). Entries without "build" use Adventure's points of interest as they are.

Reads the assembled Forge tree, so run after scripts/assemble.py; re-run after editing the
layout. Outputs are committed: plane/maps/map/campaign/*.tmx and the patch file.

Usage: python scripts/make_maps.py
"""
from __future__ import annotations

import html
import json
import re
import sys

from common import FORGE, ROOT

COMMON = FORGE / "forge-gui" / "res" / "adventure" / "common"
LAYOUT = ROOT / "plane" / "world" / "region_layout.json"
OUT_MAPS = ROOT / "plane" / "maps" / "map" / "campaign"
POI_PATCH = ROOT / "plane" / "world" / "points_of_interest.patch.json"
# Map paths in points_of_interest.json are relative to common/, so ours go up to the plane.
MAP_PREFIX = "../Campaign/maps/map/campaign/"
SMALL_MAP = COMMON / "maps" / "map" / "demontower" / "portal_2.tmx"  # 30x30, an entry and a dialog


def rewrite_paths(tmx: str) -> str:
    """Relative tileset and template paths of a map from common/maps/map/<dir>/ now point back there."""
    return re.sub(r'(source|template)="\.\./\.\./', r'\1="../../../../common/maps/', tmx)


def dialog_property(dialog: list) -> str:
    return '<property name="dialog">' + html.escape(json.dumps(dialog, indent=1), quote=True) + "</property>"


def small_map(dialog: list) -> str:
    """The 30x30 map with its exit, and a hidden dialog trigger one tile in front of the arrival point."""
    tmx = rewrite_paths(SMALL_MAP.read_text(encoding="utf-8"))
    objects = re.search(r'(<objectgroup id="4" name="Objects">)(.*?)(</objectgroup>)', tmx, re.S)
    entry = re.search(r'<object id="38" template="([^"]+)" x="([\d.]+)" y="([\d.]+)">.*?</object>', objects.group(2), re.S)
    ex, ey = float(entry.group(2)), float(entry.group(3))
    new_objects = (
        f'\n  {entry.group(0)}\n'
        f'  <object id="90" template="../../../../common/maps/obj/dialog.tx" type="dialog" x="{ex - 8}" '
        f'y="{ey - 40}" width="32" height="24">\n   <properties>\n    {dialog_property(dialog)}\n'
        f'   </properties>\n  </object>\n ')
    return tmx[:objects.start(2)] + new_objects + tmx[objects.end(2):]


def town_map(source_map: str, merchant: str) -> str:
    """An upstream town with every shop removed but the first, which sells from our merchant."""
    tmx = rewrite_paths((COMMON / source_map.replace("../common/", "")).read_text(encoding="utf-8"))
    shops = list(re.finditer(r'<object id="\d+" template="[^"]*(?:shop|RotatingShop)\.tx"[^>]*?(?:/>|>.*?</object>)', tmx, re.S))
    if not shops:
        sys.exit(f"{source_map}: no shop objects")
    keep = shops[0]
    head = re.match(r'(<object id="\d+" template=")[^"]*("[^>]*?)(/?>)', keep.group(0))
    attrs = re.sub(r'\s*type="[^"]*"', "", head.group(2).rstrip("/"))
    lists = "".join(f'\n    <property name="{k}" value="{merchant}"/>'
                    for k in ("commonShopList", "uncommonShopList", "rareShopList", "mythicShopList"))
    merchant_obj = (f'{head.group(1)}../../../../common/maps/obj/shop.tx{attrs}>\n   <properties>{lists}\n'
                    f'   </properties>\n  </object>')
    out, last = [], 0
    for m in shops:
        out.append(tmx[last:m.start()])
        if m is keep:
            out.append(merchant_obj)
        last = m.end()
    out.append(tmx[last:])
    return "".join(out)


def keyfort_map(source_map: str, item: str) -> str:
    """An upstream dungeon whose first treasure chest also holds the key item."""
    tmx = rewrite_paths((COMMON / source_map.replace("../common/", "")).read_text(encoding="utf-8"))
    chest = re.search(r'<object id="(\d+)" template="([^"]*treasure\.tx)" x="([\d.]+)" y="([\d.]+)"\s*/>', tmx)
    if not chest:
        sys.exit(f"{source_map}: no plain treasure chest to put the key in")
    reward = [{"type": "item", "itemName": item}, {"type": "randomCard", "count": 3, "addMaxCount": 2}]
    new = (f'<object id="{chest.group(1)}" template="{chest.group(2)}" x="{chest.group(3)}" y="{chest.group(4)}">\n'
           f'   <properties>\n    <property name="reward">{html.escape(json.dumps(reward), quote=True)}</property>\n'
           f'   </properties>\n  </object>')
    return tmx[:chest.start()] + new + tmx[chest.end():]


def main() -> int:
    if not COMMON.is_dir():
        sys.exit(f"{COMMON} not found: run scripts/assemble.py first")
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    upstream = {p["name"]: p for p in json.loads((COMMON / "world" / "points_of_interest.json").read_text(encoding="utf-8"))}
    regions = {r["id"]: r for r in layout["regions"]}
    OUT_MAPS.mkdir(parents=True, exist_ok=True)
    for old in OUT_MAPS.glob("*.tmx"):
        old.unlink()
    added = []
    for poi in layout["pois"]:
        build = poi.get("build")
        if not build:
            if poi["name"] not in upstream:
                sys.exit(f"layout: {poi['name']!r} is neither an Adventure point of interest nor built here")
            continue
        kind = build["kind"]
        slug = re.sub(r"[^a-z0-9]+", "_", poi["name"].lower()).strip("_")
        entry = {"name": poi["name"], "displayName": poi.get("displayName", poi["name"]), "count": 0,
                 "map": MAP_PREFIX + slug + ".tmx", "questTags": ["Campaign"]}
        if kind == "town":
            src = upstream[build["from"]]
            region = regions[build["merchant"]]
            text = town_map(src["map"], f"Merchant of {region['name']}")
            entry.update({k: src[k] for k in ("type", "spriteAtlas", "sprite") if k in src})
            entry["questTags"] = list(src.get("questTags", [])) + ["Campaign"]
        elif kind == "watchtower":
            region = regions[build["region"]]
            text = small_map([{"text": f"From the top of the watchtower you can see all of {region['name']}: "
                                       f"its towns, roads and lairs are now on your map.",
                               "options": [{"name": "Climb down",
                                            "action": [{"setQuestFlag": {"key": region["towerFlag"], "val": 1}}]}]}])
            entry.update({"type": "landmark", "spriteAtlas": "../common/maps/tileset/buildings.atlas", "sprite": "MageTower"})
        elif kind == "gate":
            text = small_map([{"text": build["text"],
                               "options": [{"name": f"Show the {build['key']}", "condition": [{"item": build["key"]}],
                                            "text": build["opened"],
                                            "options": [{"name": "Go on",
                                                         "action": [{"setQuestFlag": {"key": build["flag"], "val": 1}}]}]},
                                           {"name": "Turn back"}]}])
            entry.update({"type": "landmark", "spriteAtlas": "../common/maps/tileset/buildings.atlas", "sprite": "Gate",
                          # Shown until the gate is open (negative val: our PointOfInterest shadow).
                          "questFlagsToActivate": [{"key": build["flag"], "val": -1}]})
        elif kind == "closed":
            text = small_map([{"text": build.get("text", "The road is closed. The lands beyond open in a later update "
                                                         "of Forge Campaign."),
                               "options": [{"name": "Turn back"}]}])
            entry.update({"type": "landmark", "spriteAtlas": "../common/maps/tileset/buildings.atlas", "sprite": "Gate"})
        elif kind == "keyfort":
            src = upstream[build["from"]]
            text = keyfort_map(src["map"], build["item"])
            entry.update({k: src[k] for k in ("type", "spriteAtlas", "sprite") if k in src})
        else:
            sys.exit(f"layout: {poi['name']}: unknown build kind {kind!r}")
        (OUT_MAPS / f"{slug}.tmx").write_text(text, encoding="utf-8", newline="\n")
        added.append(entry)
        print(f"  {kind:10} {poi['name']} -> maps/map/campaign/{slug}.tmx")
    patch_file = POI_PATCH
    patch = json.loads(patch_file.read_text(encoding="utf-8")) if patch_file.is_file() else {}
    patch["add"] = added
    patch_file.write_text(json.dumps(patch, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(added)} points of interest built; {patch_file.relative_to(ROOT)} updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
