"""What each relic is worth in a duel, headlessly (wraps scripts/bench.py).

Plays the reference decks with one relic equipped (its item effect: the card in the command zone,
plus any life) against a fixed sample of mid-campaign enemies, and the same games without a relic
as the baseline. A relic's worth is how far it lowers the enemy's win rate. It also proves each
relic's card works in a real duel: a game that errors, or a worker log that names one of our cards
as unknown, is reported.

The reference decks are piloted by Forge's Default AI, which uses a relic's triggered and static
effects fully but its activated ones (Bell of Wishes, Crown of the Five Castles) as well as it
can: read those relics' numbers as a floor.

Usage: python scripts/relic_bench.py [--games 2] [--sample 12] [--only "Name;Name"]
Writes _build/out/bench/<time>-relics.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import subprocess
import sys
import time

from common import OUT, ROOT
from region_bench import biome_enemies, ENEMIES

ITEMS_PATCH = ROOT / "plane" / "world" / "items.patch.json"
CATALOGUE = ROOT / "plane" / "world" / "relics.json"


def run(label: str, enemies: list[str], effect: dict | None, args) -> tuple[int, int, int, list[str]]:
    """(enemy wins, games, errors, problems) of one bench.py run."""
    cmd = [sys.executable, "-u", str(ROOT / "scripts" / "bench.py"), "--enemies", ";".join(enemies),
           "--deck-size", "50", "--games", str(args.games), "--workers", str(args.workers), "--label", label]
    if effect:
        fx = OUT / "bench" / f"effects-{label}.json"
        fx.parent.mkdir(parents=True, exist_ok=True)
        fx.write_text(json.dumps({"player": effect}), encoding="utf-8")
        cmd += ["--effects", str(fx)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    folder = sorted((OUT / "bench").glob(f"*-{label}"))[-1]
    with open(folder / "results.csv", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    wins = sum(r["winner"] == "enemy" for r in rows)
    errors = sum(r["winner"] == "error" for r in rows)
    problems = []
    for log in folder.glob("worker-*.log"):
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if "Can not find card" in line or "custom card" in line:
                problems.append(line.strip())
    return wins, len(rows), errors, sorted(set(problems))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=2, help="games per enemy per reference deck")
    parser.add_argument("--sample", type=int, default=12, help="enemies from the Azure Reach and the Wildwood")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--only", default="", help="just these relics, separated by ;")
    args = parser.parse_args()
    enemies = {e["name"]: e for e in json.loads(ENEMIES.read_text(encoding="utf-8"))}
    lists = biome_enemies()
    pool = sorted({n for b in ("blue", "green") for n in lists.get(b, []) if n in enemies and not enemies[n].get("boss")})
    sample = sorted(random.Random(7).sample(pool, min(args.sample, len(pool))))
    items = {i["name"]: i for i in json.loads(ITEMS_PATCH.read_text(encoding="utf-8"))["add"]}
    catalogue = {k: v for k, v in json.loads(CATALOGUE.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    only = {n for n in args.only.split(";") if n}
    stamp = time.strftime("%Y%m%d-%H%M%S")
    print(f"enemies: {', '.join(sample)}", flush=True)
    base_wins, base_games, base_err, _ = run("relic-baseline", sample, None, args)
    base = base_wins / max(1, base_games)
    print(f"baseline: enemy wins {base:.0%} of {base_games}", flush=True)
    lines = [f"# Relic benchmark {stamp}", "",
             f"Reference decks (50 cards, Forge's Default AI piloting) against {len(sample)} enemies of the Azure Reach "
             f"and the Wildwood, {args.games} game(s) each per deck. Baseline, no relic: the enemy wins "
             f"{base:.0%} of {base_games}. Lower is a stronger relic.", "",
             "| Relic | Tier | Enemy wins | Change | Games | Errors | Problems |", "|---|---|---|---|---|---|---|"]
    for name, info in catalogue.items():
        if only and name not in only:
            continue
        wins, games, errors, problems = run("relic-" + "".join(c for c in name.lower() if c.isalnum()),
                                            sample, items[name]["effect"], args)
        rate = wins / max(1, games)
        print(f"{name:28} {info['tier']:8} enemy wins {rate:.0%} ({rate - base:+.0%}) errors {errors} "
              f"{'; '.join(problems)[:200]}", flush=True)
        lines.append(f"| {name} | {info['tier']} | {rate:.0%} | {rate - base:+.0%} | {games} | {errors} | "
                     f"{'; '.join(problems)[:200]} |")
    out = OUT / "bench" / f"{stamp}-relics.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
