"""Tune bosses' life (and starting hand) to a target win rate, headlessly (wraps region_bench.py).

Each boss of TARGETS fights the reference decks with its map's effects, as region_bench.py does.
Its life is searched between a floor and its current life (bisection on the measured enemy win
rate); when even the floor wins too often, its starting hand shrinks by one card (twice at most).
Each step edits the packaged app's world/enemies.json and world/enemy_effects.json directly, so no
repackaging is needed between steps; the results are written to plane/world/boss_tuning.json,
which scripts/make_relics.py merges into enemies.patch.json and enemy_effects.json.

Targets are enemy wins per single game against the reference decks (castles and most bosses play
best of three, which widens the gap: 50% a game is 50% a match, 70% a game is 78%).

Usage: python scripts/boss_tune.py [--games 8] [--steps 4] [--only "A;B"]
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys

from common import OUT, ROOT
from region_bench import slug

APP_WORLD = ROOT / "_build" / "dist" / "ForgeCampaign" / "res" / "adventure" / "Campaign" / "world"
TUNING = ROOT / "plane" / "world" / "boss_tuning.json"

# boss -> target enemy win rate per game. Castles are the gym leaders on the main path; side bosses
# guard the Power 9; champions are optional; the Oracle and Emrakul are the legends.
TARGETS = {
    "Akroma": 0.50, "Lorthos": 0.55, "Ghalta": 0.55, "Lathliss": 0.62, "Griselbrand": 0.62,
    "Nahiri": 0.65, "Jace": 0.68, "Garruk": 0.68, "Tibalt": 0.70, "Grolnok": 0.70,
    "Scarecrow Captain": 0.55, "Teferi": 0.60, "Kiora": 0.62, "Slimefoot": 0.65, "Slobad": 0.65,
    "Xira": 0.68, "Zedruu": 0.70, "Liliana": 0.72,
    "The Hydra of Shandalaar": 0.78, "Sorin": 0.78, "Sliver Queen": 0.80,
    "Oracle of the Alpha": 0.80,
}
TOLERANCE = 0.10
FLOOR = 10
MAX_HAND_CUT = 2
BASE_HAND: dict[str, int] = {}  # each boss's own hand change before tuning


def measure(boss: str, games: int) -> float:
    cmd = [sys.executable, "-u", str(ROOT / "scripts" / "region_bench.py"), "--only", boss, "--games", str(games)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    folder = sorted((OUT / "bench").glob(f"*-{slug(boss)}"))[-1]
    with open(folder / "results.csv", encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["winner"] in ("enemy", "player")]
    return sum(r["winner"] == "enemy" for r in rows) / max(1, len(rows))


def set_boss(boss: str, life: int, hand: int) -> None:
    enemies_file = APP_WORLD / "enemies.json"
    enemies = json.loads(enemies_file.read_text(encoding="utf-8"))
    for e in enemies:
        if e.get("name") == boss:
            e["life"] = life
    enemies_file.write_text(json.dumps(enemies, indent=1, ensure_ascii=False), encoding="utf-8")
    fx_file = APP_WORLD / "enemy_effects.json"
    fx = json.loads(fx_file.read_text(encoding="utf-8"))
    entry = fx.setdefault(boss, {"effect": {}})
    base = BASE_HAND.setdefault(boss, entry["effect"].get("changeStartCards", 0))
    entry["effect"]["changeStartCards"] = base + hand
    fx_file.write_text(json.dumps(fx, indent=1, ensure_ascii=False), encoding="utf-8")


def life_of(boss: str) -> int:
    for e in json.loads((APP_WORLD / "enemies.json").read_text(encoding="utf-8")):
        if e.get("name") == boss:
            return int(e["life"])
    sys.exit(f"no enemy {boss!r} in the packaged app")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=8, help="games per reference deck per step")
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    only = {n for n in args.only.split(";") if n}
    tuning = json.loads(TUNING.read_text(encoding="utf-8")) if TUNING.is_file() else {}
    for boss, target in TARGETS.items():
        if only and boss not in only:
            continue
        start = life_of(boss)
        lo, hi, hand = FLOOR, start, 0
        life, rate = start, measure(boss, args.games)
        log = [(life, hand, rate)]
        print(f"{boss}: target {target:.0%}, life {life} -> {rate:.0%}", flush=True)
        for _ in range(args.steps):
            if abs(rate - target) <= TOLERANCE:
                break
            if rate > target:
                if life <= lo:
                    if hand <= -MAX_HAND_CUT:
                        break
                    hand -= 1  # the floor is not enough: one card fewer in the opening hand
                else:
                    hi = life
                    life = max(lo, (lo + life) // 2)
            else:
                if life >= hi and hand == 0:
                    break  # weaker than the target even at its own life: leave it
                lo = life
                life = (life + hi + 1) // 2
            set_boss(boss, life, hand)
            rate = measure(boss, args.games)
            log.append((life, hand, rate))
            print(f"  life {life}, hand {hand:+d} -> {rate:.0%}", flush=True)
        best = min(log, key=lambda x: abs(x[2] - target))
        set_boss(boss, best[0], best[1])
        tuning[boss] = {"life": best[0], "hand": best[1], "measured": round(best[2], 2), "target": target,
                        "games": 2 * args.games}
        TUNING.write_text(json.dumps(tuning, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"  => {boss}: life {best[0]}, hand {best[1]:+d}, {best[2]:.0%}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
