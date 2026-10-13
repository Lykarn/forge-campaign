"""Lint enemy decks for cards Forge's AI cannot play well.

Forge marks cards in their own scripts:
  AI:RemoveDeck:All     the AI cannot use the card at all; a dead card in an AI deck
  AI:RemoveDeck:Random  the AI plays it badly; random AI decks leave it out
Enemy decks full of these play straight into the AI's weak spots (plan, Fix 1: "decks built for
the AI"). This lists, per enemy and tier, the fixed .dck decks that hold such cards. Generated
.json decks are skipped: their cards are drawn at random each game.

Reads the assembled Forge tree, so run after scripts/assemble.py. Writes
_build/out/deck_lint.csv (one row per card in a deck) and prints a summary by tier.

Usage: python scripts/lint_decks.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict

from common import FORGE, OUT, ROOT

RES = FORGE / "forge-gui" / "res"
ADVENTURE = RES / "adventure"


def card_flags() -> dict[str, str]:
    """Card name -> 'All' or 'Random' for every card marked AI:RemoveDeck."""
    flags = {}
    for path in (RES / "cardsfolder").rglob("*.txt"):
        text = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"AI:RemoveDeck:(All|Random)", text)
        if not match:
            continue
        for name in re.findall(r"^Name:(.+)$", text, re.M):
            flags[name.strip()] = match.group(1)
    return flags


def tiers() -> dict[str, str]:
    """Enemy name -> tier, by the same rules as forge.campaign.ai.EnemyTiers."""
    config = json.loads((ROOT / "plane" / "world" / "enemy_tiers.json").read_text(encoding="utf-8"))
    elite_min = config.get("rules", {}).get("eliteMinLife", 25)
    named = {k: v.capitalize() for k, v in config.get("enemies", {}).items()}
    enemies = json.loads((ADVENTURE / "common" / "world" / "enemies.json").read_text(encoding="utf-8"))
    out = {}
    for e in enemies:
        out[e["name"]] = named.get(e["name"]) or ("Boss" if e.get("boss") else
                                                  "Elite" if e.get("life", 0) >= elite_min else "Grunt")
    return out, enemies


def deck_cards(path) -> Counter:
    cards = Counter()
    section = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line.lower()
            continue
        match = re.match(r"(\d+)\s+([^|]+)", line)
        if match and section == "[main]":
            cards[match.group(2).strip()] += int(match.group(1))
    return cards


def main() -> int:
    if not RES.is_dir():
        sys.exit(f"{RES} not found: run scripts/assemble.py first")
    flags = card_flags()
    tier_of, enemies = tiers()
    rows = []
    per_tier = defaultdict(lambda: {"decks": 0, "flagged_decks": 0, "all": 0, "random": 0})
    for e in enemies:
        tier = tier_of[e["name"]]
        for deck in e.get("deck", []):
            if not deck.endswith(".dck"):
                continue
            path = ADVENTURE / "common" / deck
            if not path.is_file():
                continue
            stats = per_tier[tier]
            stats["decks"] += 1
            flagged = False
            for card, count in deck_cards(path).items():
                flag = flags.get(card)
                if flag:
                    flagged = True
                    stats[flag.lower()] += count
                    rows.append({"enemy": e["name"], "tier": tier, "deck": deck, "card": card,
                                 "count": count, "flag": flag})
            stats["flagged_decks"] += flagged
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "deck_lint.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["enemy", "tier", "deck", "card", "count", "flag"])
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["tier"], r["enemy"], r["deck"], r["card"])))
    print(f"{len(flags)} cards are marked AI:RemoveDeck in Forge")
    print("| Tier | Enemy decks (.dck) | Decks with marked cards | Copies: unusable (All) | Copies: played badly (Random) |")
    print("| --- | ---: | ---: | ---: | ---: |")
    for tier in ("Grunt", "Elite", "Boss"):
        s = per_tier[tier]
        print(f"| {tier} | {s['decks']} | {s['flagged_decks']} | {s['all']} | {s['random']} |")
    worst = Counter()
    for r in rows:
        if r["flag"] == "All":
            worst[r["card"]] += r["count"]
    print("\nMost common unusable cards in enemy decks: " +
          ", ".join(f"{c} ({n})" for c, n in worst.most_common(10)))
    print(f"\nDetails: {OUT / 'deck_lint.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
