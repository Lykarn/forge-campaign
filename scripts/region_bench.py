"""The difficulty curve of the campaign, region by region, headlessly (wraps scripts/bench.py).

For each region of plane/world/region_layout.json: a sample of the enemies that roam it (its
biomes' enemy lists, bosses left out), played with the region's enemyLifeBonus and enemyMinTier
against the reference decks at the deck size a player has there (40 in the hub and the first
region, 50 after the first castle, 60 after the third). Then each colour castle's boss, and the
finale, at the deck size the player would have when reaching it. One summary for all of it:
_build/out/bench/<time>-region-curve.md.

The reference decks are piloted by Forge's Default AI (see bench.py): read the numbers as "how
this region does against stock Forge AI with a good deck"; a human does better.

Usage: python scripts/region_bench.py [--sample 12] [--games 2] [--workers 5]
       python scripts/region_bench.py --castles-only | --bosses | --only "Emrakul;Akroma"

Bosses fight with their map's effects (a castle's Presence, Emrakul's Awakening...), as in the game.
"""
from __future__ import annotations

import argparse
import html
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

from common import FORGE, OUT, ROOT

BIOMES = FORGE / "forge-gui" / "res" / "adventure" / "common" / "world" / "biomes"
ENEMIES = FORGE / "forge-gui" / "res" / "adventure" / "common" / "world" / "enemies.json"
# Deck size by region: the minimum is 40, 50 after the first castle, 60 after the third.
DECK_SIZE = {"hub": 40, "white": 40, "blue": 50, "green": 50, "red": 60, "black": 60}
# Castle bosses (their castle's upper floor) and the deck size a player has when reaching them.
CASTLES = [("white", "Akroma", 40), ("blue", "Lorthos", 50), ("green", "Ghalta", 50),
           ("red", "Lathliss", 60), ("black", "Griselbrand", 60), ("hub", "Emrakul", 60)]
# Side bosses (a Power 9 each), champions (a relic each) and the Oracle of the Alpha: region, and
# the deck size a player is likely to have there.
BOSSES = [("white", "Nahiri", 40), ("blue", "Jace", 50), ("green", "Garruk", 50), ("red", "Tibalt", 60),
          ("black", "Grolnok", 60), ("hub", "Scarecrow Captain", 40), ("white", "Teferi", 40), ("blue", "Kiora", 50),
          ("green", "Slimefoot", 50), ("green", "The Hydra of Shandalaar", 50), ("red", "Slobad", 60),
          ("red", "Zedruu", 60), ("red", "Sliver Queen", 60), ("black", "Xira", 60), ("black", "Sorin", 60),
          ("black", "Liliana", 60), ("hub", "Oracle of the Alpha", 60)]
MAPS = [FORGE / "forge-gui" / "res" / "adventure" / "common" / "maps", ROOT / "plane" / "maps"]
# Bosses that also appear on other maps (a town, an entrance): where they are fought.
MAP_OF = {"Emrakul": "map/emrakul/emrakul.tmx"}


def lenient_json(text: str):
    return json.loads(re.sub(r",\s*([\]}])", r"\1", html.unescape(text)))


def map_effect(boss: str) -> dict:
    """The effects a boss fights with on its map: the map's dungeonEffect and its own "effect"
    (on maps with a variant per difficulty, the Normal one). Its enemy_effects.json effect is
    added by TierBench itself."""
    merged: dict = {}

    def add(effect: dict) -> None:
        for key, value in effect.items():
            if isinstance(value, list):
                merged.setdefault(key, []).extend(value)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                merged[key] = merged.get(key, 0) + value

    marker = f'name="enemy" value="{html.escape(boss, quote=True)}"'
    # A boss's own map first (one listed in MAP_OF), then the first map that has it; never Forge's debug map.
    candidates = [MAPS[0] / MAP_OF[boss]] if boss in MAP_OF else []
    candidates += [tmx for root in MAPS for tmx in sorted(root.rglob("*.tmx")) if "debug" not in tmx.name]
    for tmx in candidates:
        text = tmx.read_text(encoding="utf-8", errors="replace")
        if marker not in text:
            continue
        objects = [o for o in re.findall(r"<object [^>]*>.*?</object>", text, re.S) if marker in o]
        normal = [o for o in objects if 'name="spawn.Normal" type="bool" value="false"' not in o]
        obj = (normal or objects)[0]
        fx = re.search(r'<property name="effect"(?: value="([^"]*)"\s*/>|>(.*?)</property>)', obj, re.S)
        if fx:
            add(lenient_json(fx.group(1) or fx.group(2)))
        head = text[:text.find("<objectgroup")] if "<objectgroup" in text else text
        dfx = re.search(r'<property name="dungeonEffect"(?: value="([^"]*)"\s*/>|>(.*?)</property>)', head, re.S)
        if dfx:
            add(lenient_json(dfx.group(1) or dfx.group(2)))
        return merged
    return merged


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def biome_enemies() -> dict[str, list[str]]:
    out = {}
    for f in BIOMES.glob("*.json"):
        try:
            data = json.loads(re.sub(r",\s*([\]}])", r"\1", f.read_text(encoding="utf-8")))
        except ValueError:
            continue
        out[data.get("name")] = data.get("enemies", [])
    return out


def run(label: str, enemies: list[str], deck_size: int, life: int, tier: str, args, effect: dict | None = None) -> Path:
    cmd = [sys.executable, "-u", str(ROOT / "scripts" / "bench.py"), "--enemies", ";".join(enemies),
           "--deck-size", str(deck_size), "--life-bonus", str(life), "--games", str(args.games),
           "--workers", str(args.workers), "--label", label]
    if tier:
        cmd += ["--min-tier", tier]
    if args.gamelog:
        cmd += ["--gamelog"]
    if effect:
        fx = OUT / "bench" / f"effects-{label}.json"
        fx.parent.mkdir(parents=True, exist_ok=True)
        fx.write_text(json.dumps({"enemy": effect}), encoding="utf-8")
        cmd += ["--effects", str(fx)]
        print(f"   map effect: {effect}", flush=True)
    print(f"\n== {label}: {len(enemies)} enemies, {deck_size}-card decks, +{life} life, floor {tier or '-'}", flush=True)
    subprocess.run(cmd, check=True)
    return sorted((OUT / "bench").glob(f"*-{label}"))[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=12, help="roaming enemies per region")
    parser.add_argument("--games", type=int, default=2, help="games per enemy per reference deck")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--castles-only", action="store_true")
    parser.add_argument("--bosses", action="store_true", help="side bosses, champions and the Oracle instead")
    parser.add_argument("--only", default="", help="just these bosses, separated by ;")
    parser.add_argument("--gamelog", action="store_true", help="save each game's log (bench.py --gamelog)")
    args = parser.parse_args()
    layout = json.loads((ROOT / "plane" / "world" / "region_layout.json").read_text(encoding="utf-8"))
    enemies = {e["name"]: e for e in json.loads(ENEMIES.read_text(encoding="utf-8"))}
    lists = biome_enemies()
    rng = random.Random(args.seed)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    sections = []
    regions = {r["id"]: r for r in layout["regions"]}
    only = {n for n in args.only.split(";") if n}
    if not args.castles_only and not args.bosses and not only:
        for r in layout["regions"]:
            pool = sorted({n for b in r["biomes"] for n in lists.get(b, []) if n in enemies and not enemies[n].get("boss")})
            sample = sorted(rng.sample(pool, min(args.sample, len(pool))))
            folder = run(f"region-{r['id']}", sample, DECK_SIZE.get(r["id"], 40), r.get("enemyLifeBonus", 0),
                         r.get("enemyMinTier", ""), args)
            sections.append((f"{r['name']} (roaming enemies)", folder))
    for rid, boss, size in [] if args.bosses else CASTLES:
        if only and boss not in only:
            continue
        r = regions[rid]
        folder = run(f"castle-{slug(boss)}", [boss], size, r.get("enemyLifeBonus", 0), "", args, map_effect(boss))
        sections.append((f"{boss}, {'finale' if rid == 'hub' else r['name'] + ' castle'}", folder))
    for rid, boss, size in BOSSES if (args.bosses or only) else []:
        if only and boss not in only:
            continue
        r = regions[rid]
        folder = run(f"boss-{slug(boss)}", [boss], size, r.get("enemyLifeBonus", 0), "", args, map_effect(boss))
        sections.append((f"{boss}, {r['name']}", folder))
    report = [f"# Campaign difficulty curve {stamp}", "",
              "Enemy win rate against the reference decks (Forge's Default AI piloting), at the deck size a player has "
              "there. Targets: roaming enemies lose most games; castle bosses win about half.", ""]
    for title, folder in sections:
        summary = (folder / "summary.md").read_text(encoding="utf-8")
        table = "\n".join(l for l in summary.splitlines() if l.startswith("|"))
        report += [f"## {title}", "", table, ""]
    out = OUT / "bench" / f"{stamp}-region-curve.md"
    out.write_text("\n".join(report), encoding="utf-8")
    print(f"\n{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
