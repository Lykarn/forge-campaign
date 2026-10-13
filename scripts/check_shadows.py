"""Fail if any upstream file we shadow has changed since we copied it.

A shadowed class is our full copy of an upstream class, placed ahead of the original on the
classpath. That only stays correct while the original is the one we copied. Each row of
shadows.tsv records the sha256 of the original; this script hashes the original in the
assembled upstream trees and stops the build on any mismatch.

Usage: python scripts/check_shadows.py   (after scripts/assemble.py has fetched upstream)
"""
from __future__ import annotations

import hashlib
import sys

from common import FORGE, NEO, ROOT


def main() -> int:
    trees = {"forge": FORGE, "neo": NEO}
    problems = 0
    rows = 0
    for raw in (ROOT / "shadows.tsv").read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        rows += 1
        ours, upstream, path, expected = raw.split("\t")
        if not (ROOT / ours).is_file():
            print(f"[FAIL] {ours}: listed in shadows.tsv but missing from this repo")
            problems += 1
            continue
        original = trees[upstream] / path
        if not original.is_file():
            print(f"[FAIL] {ours}: upstream original {upstream}:{path} no longer exists")
            problems += 1
            continue
        actual = hashlib.sha256(original.read_bytes()).hexdigest()
        if actual != expected:
            print(f"[FAIL] {ours}: upstream {upstream}:{path} changed "
                  f"(expected {expected[:12]}, found {actual[:12]}).\n"
                  f"       Re-copy the new original, re-apply the FORGE-CAMPAIGN blocks, "
                  f"and update its hash in shadows.tsv.")
            problems += 1
        else:
            print(f"[OK]   {ours}")
    if rows == 0:
        print("[FAIL] shadows.tsv lists no files")
        return 1
    print(f"{rows - problems}/{rows} shadowed files match their upstream originals")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
