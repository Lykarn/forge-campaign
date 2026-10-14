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
"""
from __future__ import annotations

import argparse
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


def biome_enemies() -> dict[str, list[str]]:
    out = {}
    for f in BIOMES.glob("*.json"):
        try:
            data = json.loads(re.sub(r",\s*([\]}])", r"\1", f.read_text(encoding="utf-8")))
        except ValueError:
            continue
        out[data.get("name")] = data.get("enemies", [])
    return out


def run(label: str, enemies: list[str], deck_size: int, life: int, tier: str, args) -> Path:
    cmd = [sys.executable, "-u", str(ROOT / "scripts" / "bench.py"), "--enemies", ";".join(enemies),
           "--deck-size", str(deck_size), "--life-bonus", str(life), "--games", str(args.games),
           "--workers", str(args.workers), "--label", label]
    if tier:
        cmd += ["--min-tier", tier]
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
    args = parser.parse_args()
    layout = json.loads((ROOT / "plane" / "world" / "region_layout.json").read_text(encoding="utf-8"))
    enemies = {e["name"]: e for e in json.loads(ENEMIES.read_text(encoding="utf-8"))}
    lists = biome_enemies()
    rng = random.Random(args.seed)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    sections = []
    regions = {r["id"]: r for r in layout["regions"]}
    if not args.castles_only:
        for r in layout["regions"]:
            pool = sorted({n for b in r["biomes"] for n in lists.get(b, []) if n in enemies and not enemies[n].get("boss")})
            sample = sorted(rng.sample(pool, min(args.sample, len(pool))))
            folder = run(f"region-{r['id']}", sample, DECK_SIZE.get(r["id"], 40), r.get("enemyLifeBonus", 0),
                         r.get("enemyMinTier", ""), args)
            sections.append((f"{r['name']} (roaming enemies)", folder))
    for rid, boss, size in CASTLES:
        r = regions[rid]
        folder = run(f"castle-{boss.lower()}", [boss], size, r.get("enemyLifeBonus", 0), "", args)
        sections.append((f"{boss}, {'finale' if rid == 'hub' else r['name'] + ' castle'}", folder))
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
