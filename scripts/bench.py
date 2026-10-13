"""Benchmark the enemy tiers headlessly with the PACKAGED app (what players run).

Plays Adventure enemies, with the AI their tier gives them, against reference player decks
piloted by Forge's stock Default AI (forge.campaign.bench.TierBench), in parallel worker
processes. Writes every game to results.csv and a summary by tier to summary.md, under
_build/out/bench/<time>/.

Why a fixed AI pilot and not a human: it is a repeatable yardstick. A tier's win rate reads as
"how this enemy does against stock Forge AI playing this deck", so changes to tiers, profiles or
decks show up as changes in the numbers.

Gate B targets (from the plan, tuned against the tuned reference decks):
  Grunts lose most games (enemy win rate under 40%); Bosses win close to half (40-60%);
  and turns stay inside the time budget (mean seconds per turn and the slowest turn).

Usage:
  python scripts/bench.py                 all Bosses and Elites, 30 Grunts, 2 games per deck
  python scripts/bench.py --quick         a smoke test: 2 enemies per tier, 1 game, 1 deck
  python scripts/bench.py --games 4 --grunts 60 --workers 6
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

from common import OUT, ROOT, WORK, step

APP = WORK / "dist" / "ForgeCampaign"
BENCH_DATA = WORK / "bench-data"
MAIN = "forge.campaign.bench.TierBench"
TUNED_DECKS = [ROOT / "bench" / "decks" / "ref_red_aggro.dck", ROOT / "bench" / "decks" / "ref_gw_midrange.dck"]
STARTER_DECKS = ["decks/starter/red_n.json", "decks/starter/green_n.json"]
TIERS = ("Grunt", "Elite", "Boss")


def java_command() -> list[str]:
    """The packaged runtime and jars, in the launcher's classpath order (campaign.jar first)."""
    import package  # scripts/package.py: the same Java options the launcher uses
    cfg = (APP / "app" / "ForgeCampaign.cfg").read_text(encoding="utf-8")
    jars = [str(APP / "app" / line.split("\\", 1)[1].strip())
            for line in cfg.splitlines() if line.startswith("app.classpath=")]
    java = APP / "runtime" / "bin" / ("java.exe" if os.name == "nt" else "java")
    options = [o for o in package.JAVA_OPTIONS if "$ROOTDIR" not in o and "MaxRAMPercentage" not in o]
    return [str(java), "-Xmx3g", *options, f"-Dforge.assetsDir={APP}{os.sep}",
            f"-Dneo.dataDir={BENCH_DATA}", "-cp", os.pathsep.join(jars), MAIN]


def list_enemies(cmd: list[str]) -> list[tuple[str, str, int]]:
    result = subprocess.run([*cmd, "--list"], cwd=APP, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=600)
    enemies = []
    for line in result.stdout.splitlines():
        if line.startswith("ENEMY\t"):
            _, name, tier, life, _decks = line.split("\t")
            enemies.append((name, tier, int(life)))
    if not enemies:
        sys.exit("TierBench --list printed no enemies:\n" + result.stdout[-3000:] + result.stderr[-3000:])
    return enemies


def pick(enemies, args) -> list[tuple[str, str]]:
    by_tier = defaultdict(list)
    for name, tier, _life in enemies:
        by_tier[tier].append(name)
    rng = random.Random(args.seed)
    chosen = []
    for tier in TIERS:
        names = sorted(by_tier[tier])
        limit = {"Grunt": args.grunts, "Elite": args.elites, "Boss": args.bosses}[tier]
        if args.quick:
            limit = 2
        if limit >= 0 and len(names) > limit:
            names = sorted(rng.sample(names, limit))
        chosen += [(n, tier) for n in names]
    return chosen


def summarise(rows: list[dict]) -> str:
    groups = defaultdict(list)
    for r in rows:
        groups[(r["tier"], r["ref_deck"])].append(r)
    lines = ["| Tier | Reference deck | Games | Enemy wins | Draws | Errors | Mean s/turn | Slowest turn s |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for tier in TIERS:
        for (t, deck), rs in sorted(groups.items()):
            if t != tier:
                continue
            played = [r for r in rs if r["winner"] in ("enemy", "player", "draw")]
            wins = sum(r["winner"] == "enemy" for r in played)
            draws = sum(r["winner"] == "draw" for r in played)
            errors = len(rs) - len(played)
            decided = len(played)
            mean_turn = sum(float(r["mean_turn_s"]) for r in played) / decided if decided else 0
            slowest = max((float(r["max_turn_s"]) for r in played), default=0)
            rate = f"{100 * wins / decided:.0f}% ({wins})" if decided else "-"
            lines.append(f"| {tier} | {deck} | {decided} | {rate} | {draws} | {errors} | {mean_turn:.1f} | {slowest:.0f} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--games", type=int, default=2, help="games per enemy per reference deck")
    parser.add_argument("--grunts", type=int, default=30, help="Grunts to sample (-1 = all)")
    parser.add_argument("--elites", type=int, default=-1, help="Elites to sample (-1 = all)")
    parser.add_argument("--bosses", type=int, default=-1, help="Bosses to sample (-1 = all)")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--player-life", type=int, default=20)
    parser.add_argument("--starter", action="store_true", help="also play the Normal starter decks")
    parser.add_argument("--stock", action="store_true",
                        help="baseline: every enemy plays stock Default AI, no simulation (still grouped by tier)")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900, help="seconds before a game counts as a draw")
    args = parser.parse_args()
    if args.quick:
        args.games = 1

    if not (APP / "app" / "campaign.jar").is_file():
        sys.exit(f"no packaged app at {APP}: run scripts/package.py first")
    run_dir = OUT / "bench" / (time.strftime("%Y%m%d-%H%M%S") + ("-stock" if args.stock else ""))
    run_dir.mkdir(parents=True)
    BENCH_DATA.mkdir(parents=True, exist_ok=True)
    cmd = java_command()

    step("1. Enemies and their tiers")
    chosen = pick(list_enemies(cmd), args)
    counts = defaultdict(int)
    for _, tier in chosen:
        counts[tier] += 1
    print("  " + ", ".join(f"{counts[t]} {t}" for t in TIERS))

    decks = [str(d) for d in TUNED_DECKS[:1 if args.quick else None]]
    if args.starter:
        decks += STARTER_DECKS
    games = len(chosen) * len(decks) * args.games
    print(f"  {games} games: {args.games} per enemy against {len(decks)} reference deck(s), {args.workers} workers")

    step("2. Games")
    # Deal Bosses first and round-robin, so the slow simulated games spread over all workers.
    order = sorted(chosen, key=lambda c: TIERS.index(c[1]), reverse=True)
    shards = [order[i::args.workers] for i in range(args.workers)]
    procs = []
    for i, shard in enumerate(s for s in shards if s):
        names = run_dir / f"enemies-{i}.txt"
        names.write_text("\n".join(n for n, _ in shard) + "\n", encoding="utf-8")
        log = open(run_dir / f"worker-{i}.log", "w", encoding="utf-8", errors="replace")
        procs.append((subprocess.Popen(
            [*cmd, "--enemies", str(names), "--decks", ",".join(decks), "--games", str(args.games),
             "--player-life", str(args.player_life), "--timeout", str(args.timeout),
             "--out", str(run_dir / f"results-{i}.csv"), *(["--stock"] if args.stock else [])],
            cwd=APP, stdout=log, stderr=subprocess.STDOUT), log))
        time.sleep(2)  # let each worker write the shared portable profile before the next starts
    start = time.time()
    while any(p.poll() is None for p, _ in procs):
        time.sleep(15)
        done = sum(max(0, sum(1 for _ in open(f, encoding="utf-8")) - 1)
                   for f in run_dir.glob("results-*.csv"))
        print(f"  {done}/{games} games after {(time.time() - start) / 60:.0f} min", flush=True)
    for p, log in procs:
        log.close()
        if p.returncode != 0:
            print(f"  [WARN] a worker exited with {p.returncode}: see {run_dir}")

    step("3. Summary")
    rows = []
    for f in sorted(run_dir.glob("results-*.csv")):
        with open(f, encoding="utf-8", newline="") as fh:
            rows += list(csv.DictReader(fh))
    with open(run_dir / "results.csv", "w", encoding="utf-8", newline="") as fh:
        if rows:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    table = summarise(rows)
    # Decisions where full simulation threw and the Boss fell back to the heuristic AI.
    fallbacks = sum(f.read_text(encoding="utf-8", errors="replace").count("[campaign] simulation failed")
                    for f in run_dir.glob("worker-*.log"))
    (run_dir / "summary.md").write_text(
        f"# Tier benchmark {run_dir.name}\n\n{len(rows)} games, player life {args.player_life}, "
        f"{'STOCK AI baseline (no tiers), ' if args.stock else ''}"
        f"reference pilot: Forge Default AI. Enemy wins = the enemy beat the reference deck.\n\n{table}\n\n"
        f"Simulation fallbacks (a decision made by the heuristic AI after simulation failed): {fallbacks}\n",
        encoding="utf-8")
    print(table)
    print(f"\n  simulation fallbacks: {fallbacks}")
    print(f"\n  {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
