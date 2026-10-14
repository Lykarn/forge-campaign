"""Build plane/card_scores.json: the cards each region sells, with roles and a score.

Merchants and the reward picker read the result at runtime (Phase 2: curated shops). Inputs:
  plane/world/card_pools.json   pools: which sets (and rarities) each region draws from
  plane/world/card_tiers.json   optional hand-set tiers that override the computed score
  Forge's res/editions/*.txt    set membership and rarity (from the assembled Forge tree)
  Forge's res/cardsfolder       card scripts: types, cost, P/T, keywords, ability types -> roles
  MTGJSON AtomicCards           edhrecRank, a weak popularity prior (cached 24 h in _build/cache)

Why MTGJSON and not Scryfall: Scryfall's terms bar using its data to make new games; MTGJSON's
data is free to use. Card images still come from Scryfall at runtime, as Forge does.

Score (0-100, within each pool):
  creatures      50% stats for the cost (power counts most, evasion, per mana), 35% popularity, 15% rarity
  other spells   50% role value (removal > draw/tokens > counter/ramp > tricks), 35%, 15%
  a hand tier in card_tiers.json (S/A/B/C/D) replaces the computed score.

Usage: python scripts/card_scores.py      (after scripts/assemble.py)
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

from common import FORGE, ROOT, WORK

RES = FORGE / "forge-gui" / "res"
CACHE = WORK / "cache"
MTGJSON_URL = "https://mtgjson.com/api/v5/AtomicCards.json.gz"
POOLS = ROOT / "plane" / "world" / "card_pools.json"
TIERS = ROOT / "plane" / "world" / "card_tiers.json"
OUT = ROOT / "plane" / "card_scores.json"

TIER_SCORES = {"S": 95, "A": 85, "B": 70, "C": 50, "D": 30}
RARITY = {"C": 0.0, "U": 0.33, "R": 0.66, "M": 1.0, "S": 0.66, "L": 0.0}
ROLE_VALUE = {"removal": 1.0, "sweeper": 0.9, "draw": 0.6, "token": 0.6, "counter": 0.5,
              "ramp": 0.5, "discard": 0.45, "lifegain": 0.25, "trick": 0.35, "burn": 0.5}
EVASION = ("Flying", "Menace", "Trample", "Shadow", "Fear", "Intimidate", "Horsemanship", "Skulk")


def mtgjson() -> dict[str, dict]:
    """AtomicCards by name, downloaded at most once a day (MTGJSON asks for caching too)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "AtomicCards.json.gz"
    if not path.is_file() or time.time() - path.stat().st_mtime > 24 * 3600:
        print(f"  downloading {MTGJSON_URL}")
        req = urllib.request.Request(MTGJSON_URL, headers={"User-Agent": "ForgeCampaign/0.1 (free fan project)"})
        with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
            f.write(r.read())
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)["data"]


def editions() -> dict[str, list[tuple[str, str]]]:
    """Set code -> [(card name, rarity letter)] from Forge's edition files."""
    sets = {}
    for path in (RES / "editions").glob("*.txt"):
        text = path.read_text(encoding="utf-8", errors="replace")
        code = re.search(r"^Code=(.+)$", text, re.M)
        if not code:
            continue
        cards, section = [], None
        for line in text.splitlines():
            if line.startswith("["):
                section = line.strip().lower()
                continue
            m = re.match(r"\S+\s+([CURMSL])\s+([^@]+?)\s*(@.*)?$", line.strip())
            if m and section == "[cards]":
                cards.append((m.group(2), m.group(1)))
        sets[code.group(1).strip()] = cards
    return sets


def scripts() -> dict[str, str]:
    """Card name -> its Forge script (first face for double-faced cards)."""
    out = {}
    for path in (RES / "cardsfolder").rglob("*.txt"):
        text = path.read_text(encoding="utf-8", errors="replace")
        name = re.search(r"^Name:(.+)$", text, re.M)
        if name:
            out.setdefault(name.group(1).strip(), text)
    return out


def roles(text: str) -> list[str]:
    """What a card does, from the ability types and keywords in its script."""
    found = set()
    apis = re.findall(r"(?:SP|AB|DB)\$\s*(\w+)([^\n]*)", text)
    for api, rest in apis:
        targets_creature = re.search(r"ValidTgts\$\s*(Any|Creature|Permanent)", rest) is not None
        if api in ("Destroy", "Sacrifice") and ("ValidTgts" in rest or "Opponent" in rest):
            found.add("removal")
        elif api in ("DestroyAll", "DamageAll"):
            found.add("sweeper")
        elif api == "DealDamage":
            found.add("removal" if targets_creature else "burn")
            if re.search(r"ValidTgts\$\s*(Any|Player)", rest):
                found.add("burn")
        elif api == "ChangeZone":
            if re.search(r"Origin\$\s*Library", rest) and "Land" in rest and "Battlefield" in rest:
                found.add("ramp")
            elif re.search(r"Destination\$\s*(Exile|Hand|Library)", rest) and targets_creature:
                found.add("removal")
        elif api in ("Draw", "Dig"):
            found.add("draw")
        elif api == "Counter":
            found.add("counter")
        elif api == "Token":
            found.add("token")
        elif api == "Mana" and not re.search(r"^Types:.*\bLand\b", text, re.M):
            found.add("ramp")
        elif api == "Discard" and re.search(r"Opponent|ValidTgts\$\s*(Player|Opponent)", rest):
            found.add("discard")
        elif api == "GainLife":
            found.add("lifegain")
        elif api == "Fight":
            found.add("removal")
        elif api == "Pump":
            if re.search(r"NumDef\$\s*-", rest):
                found.add("removal")
            elif targets_creature:
                found.add("trick")
    if re.search(r"AILogic:Curse|AttachAILogic:Curse", text) and "Enchant" in text:
        found.add("removal")
    if is_creature(text):
        power, toughness = pt(text)
        evasive = any(re.search(rf"^K:{k}\b", text, re.M) for k in EVASION)
        if evasive:
            found.add("evasion")
        if power >= 3 or (power >= 2 and evasive):
            found.add("threat")
    return sorted(found)


def is_creature(text: str) -> bool:
    return re.search(r"^Types:.*\bCreature\b", text, re.M) is not None


def pt(text: str) -> tuple[int, int]:
    m = re.search(r"^PT:(\d+)/(\d+)", text, re.M)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def cmc(text: str) -> int:
    m = re.search(r"^ManaCost:(.+)$", text, re.M)
    if not m or m.group(1).strip() == "no cost":
        return 0
    total = 0
    for sym in m.group(1).split():
        total += int(sym) if sym.isdigit() else (0 if sym == "X" else 1)
    return total


def colours(text: str) -> str:
    m = re.search(r"^ManaCost:(.+)$", text, re.M)
    cost = m.group(1) if m else ""
    found = "".join(c for c in "WUBRG" if c in cost)
    ci = re.search(r"^Colors:(.+)$", text, re.M)
    if ci:
        found = "".join(c for c, word in zip("WUBRG", ("white", "blue", "black", "red", "green")) if word in ci.group(1))
    return found


def card_type(text: str) -> str:
    m = re.search(r"^Types:(.+)$", text, re.M)
    types = m.group(1) if m else ""
    for t in ("Creature", "Planeswalker", "Instant", "Sorcery", "Enchantment", "Artifact", "Land", "Battle"):
        if t in types.split():
            return t
    return "Other"


def percentile(values: dict[str, float], higher_is_better: bool = True) -> dict[str, float]:
    """Each value as a 0-1 rank within the group."""
    ordered = sorted(values, key=lambda k: values[k], reverse=not higher_is_better)
    n = max(1, len(ordered) - 1)
    return {k: i / n for i, k in enumerate(ordered)}


def main() -> int:
    if not RES.is_dir():
        sys.exit(f"{RES} not found: run scripts/assemble.py first")
    config = json.loads(POOLS.read_text(encoding="utf-8"))
    tiers = json.loads(TIERS.read_text(encoding="utf-8")).get("tiers", {}) if TIERS.is_file() else {}
    print("Reading Forge's editions and card scripts")
    sets, texts = editions(), scripts()
    print("Reading MTGJSON")
    atomic = mtgjson()

    out_pools, cards = {}, {}
    for pool_id, pool in config["pools"].items():
        allowed = set(pool.get("rarities", ["C", "U", "R", "M"]))
        members = {}
        for code in pool["sets"]:
            if code not in sets:
                sys.exit(f"card_pools.json: pool {pool_id}: unknown set code {code}")
            for name, rarity in sets[code]:
                if rarity in allowed and name in texts and card_type(texts[name]) != "Land":
                    members.setdefault(name, rarity)
        for name in pool.get("exclude", []):
            members.pop(name, None)

        rank = {n: float((atomic.get(n, [{}])[0] or {}).get("edhrecRank") or 10 ** 6) for n in members}
        popularity = percentile(rank, higher_is_better=False)
        creature_value = {}
        for n in members:
            t = texts[n]
            if is_creature(t):
                p, tg = pt(t)
                evasive = sum(1 for k in EVASION if re.search(rf"^K:{k}\b", t, re.M))
                # Power counts more than toughness, and evasion only matters with power: a 0/2 flier
                # for 0 is not a threat.
                creature_value[n] = (1.5 * p + tg + (1.5 * evasive if p > 0 else 0)
                                     + 0.5 * len(roles(t))) / (cmc(t) + 1.5)
        stats = percentile(creature_value)
        scored = {}
        for n, rarity in members.items():
            t = texts[n]
            r = roles(t)
            if n in stats:
                quality = stats[n]
            else:
                quality = max([ROLE_VALUE.get(x, 0.2) for x in r] or [0.2])
            score = 100 * (0.5 * quality + 0.35 * popularity[n] + 0.15 * RARITY.get(rarity, 0))
            if n in tiers:
                score = TIER_SCORES[tiers[n]]
            scored[n] = round(score)
            cards[n] = {"type": card_type(t), "cmc": cmc(t), "colors": colours(t), "roles": r}
        out_pools[pool_id] = {"name": pool.get("name", pool_id), "sets": pool["sets"],
                              "cards": dict(sorted(scored.items(), key=lambda kv: -kv[1]))}
        top = list(out_pools[pool_id]["cards"].items())[:8]
        print(f"  {pool_id}: {len(scored)} cards from {', '.join(pool['sets'])}; top: "
              + ", ".join(f"{n} {s}" for n, s in top))

    OUT.write_text(json.dumps({"about": "Generated by scripts/card_scores.py: do not edit; "
                                        "edit plane/world/card_pools.json or card_tiers.json and re-run.",
                               "pools": out_pools, "cards": dict(sorted(cards.items()))},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(cards)} cards in {len(out_pools)} pools")
    return 0


if __name__ == "__main__":
    sys.exit(main())
