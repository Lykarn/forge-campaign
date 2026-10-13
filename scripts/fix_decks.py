"""Write AI-playable copies of enemy decks into plane/decks/ (overrides of Forge's common/decks/).

Every card marked AI:RemoveDeck:All (the AI cannot use it; see lint_decks.py) is taken out and
its slots go to more copies of the deck's own AI-playable spells, so the deck keeps its theme and
curve: same card type first (a creature for a creature), the deck's most-played cards first,
at most 4 copies, or a 5th of its main card of that type when all are at 4. Only a dead land
becomes a basic land of the deck's colours.

Why an override and not an edit: Adventure looks up an enemy's deck path in the plane folder
before common/, so plane/decks/<same path> replaces the deck for our plane only.

Only fixed .dck decks are touched; generated .json decks draw cards at random. Decks listed in
plane/decks/HAND_EDITED.txt are never overwritten. Re-run after a Forge rebase.

Usage: python scripts/fix_decks.py [--tiers Boss,Elite,Grunt]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

from common import ROOT
from lint_decks import ADVENTURE, card_flags, tiers

BASICS = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
PLANE_DECKS = ROOT / "plane" / "decks"


def card_types(names: set[str]) -> dict[str, tuple[str, str]]:
    """Card name -> (main type, colour letters) from the card scripts, for the names asked."""
    from lint_decks import RES
    found = {}
    for path in (RES / "cardsfolder").rglob("*.txt"):
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^Name:(.+)$", text, re.M)
        if not m or m.group(1).strip() not in names:
            continue
        types = re.search(r"^Types:(.+)$", text, re.M)
        cost = re.search(r"^ManaCost:(.+)$", text, re.M)
        t = types.group(1) if types else ""
        main = "Land" if "Land" in t else "Creature" if "Creature" in t else "Spell"
        colours = "".join(c for c in "WUBRG" if cost and c in cost.group(1))
        found[m.group(1).strip()] = (main, colours)
    return found


def parse(path):
    """The deck as lines, plus main-deck counts and where each card's line is."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    main, where, section = Counter(), {}, None
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("["):
            section = s.lower()
            continue
        m = re.match(r"(\d+)\s+([^|]+)(\|.*)?$", s)
        if m and section == "[main]":
            name = m.group(2).strip()
            main[name] += int(m.group(1))
            where.setdefault(name, i)
    return lines, main, where


def fix(path, flags, types) -> tuple[list[str], list[str]] | None:
    lines, main, where = parse(path)
    dead = {c: n for c, n in main.items() if flags.get(c) == "All"}
    if not dead:
        return None
    new = Counter({c: n for c, n in main.items() if c not in dead})
    colours = "".join(sorted({col for c in new for col in types.get(c, ("", ""))[1]}, key="WUBRG".index)) or "W"
    changes = []
    for card, count in sorted(dead.items()):
        kind = types.get(card, ("Spell", ""))[0]
        for _ in range(count):
            playable = [c for c in new if types.get(c, ("", ""))[0] not in ("Land", "") and flags.get(c) is None]
            under4 = [c for c in playable if new[c] < 4]
            same = [c for c in under4 if types[c][0] == kind]
            # A spell never becomes a land (that floods the deck): when every playable card is at 4,
            # the deck's main card of the same type gets a 5th copy. Enemy decks are not
            # format-checked, and a 5th good card beats a dead one.
            fifth = [c for c in playable if types[c][0] == kind and new[c] < 5]
            pool = same or under4 or fifth
            if kind == "Land" or not pool:
                pick = BASICS[colours[len(changes) % len(colours)]]
            else:
                pick = max(pool, key=lambda c: (new[c], c))
            new[pick] += 1
            changes.append(f"{card} -> {pick}")
    # Rewrite the [Main] section, keeping everything else (metadata, sideboard) as it was.
    out, section, written = [], None, False
    for line in lines:
        s = line.strip()
        if s.startswith("["):
            if section == "[main]" and not written:
                out += [f"{n} {c}" for c, n in sorted(new.items())]
                written = True
            section = s.lower()
            out.append(line)
            continue
        if section == "[main]" and re.match(r"\d+\s+", s):
            continue
        out.append(line)
    if section == "[main]" and not written:
        out += [f"{n} {c}" for c, n in sorted(new.items())]
    return out, changes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tiers", default="Boss,Elite,Grunt")
    args = parser.parse_args()
    wanted = {t.strip().capitalize() for t in args.tiers.split(",")}
    flags = card_flags()
    tier_of, enemies = tiers()
    keep = set()
    if (PLANE_DECKS / "HAND_EDITED.txt").is_file():
        keep = {l.strip() for l in (PLANE_DECKS / "HAND_EDITED.txt").read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")}
    decks = {}
    for e in enemies:
        if tier_of[e["name"]] in wanted:
            for d in e.get("deck", []):
                if d.endswith(".dck"):
                    decks.setdefault(d, tier_of[e["name"]])
    names = set()
    for d in decks:
        if (ADVENTURE / "common" / d).is_file():
            names |= set(parse(ADVENTURE / "common" / d)[1])
    types = card_types(names)
    report = ["# Enemy decks rewritten by scripts/fix_decks.py: AI-unusable cards swapped for playable ones.",
              "# Deck paths in this file are relative to plane/. Do not edit by hand: edit the deck and add it",
              "# to HAND_EDITED.txt instead.", ""]
    written = 0
    for deck, tier in sorted(decks.items()):
        if deck in keep or not (ADVENTURE / "common" / deck).is_file():
            continue
        result = fix(ADVENTURE / "common" / deck, flags, types)
        target = ROOT / "plane" / deck
        if result is None:
            if target.is_file() and deck not in keep:
                target.unlink()  # upstream fixed it: our override is no longer needed
            continue
        lines, changes = result
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        report.append(f"{deck} ({tier}): " + "; ".join(changes))
        written += 1
    PLANE_DECKS.mkdir(parents=True, exist_ok=True)
    (PLANE_DECKS / "FIXED_DECKS.txt").write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
    print(f"{written} decks rewritten into plane/decks/ (see plane/decks/FIXED_DECKS.txt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
