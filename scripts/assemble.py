"""Assemble the build tree: Forge and Neo Forge at the pinned commits, with our module inside.

What it does, in order:
  1. Fetches Card-Forge/forge at FORGE_REF and AdrianLopez98/NeoForge at NEO_REF (upstream.lock).
  2. Checks that every file we shadow still matches its upstream original (check_shadows.py).
  3. Copies Neo Forge's forge-gui-neo and our forge-gui-campaign into the Forge checkout.
  4. Adds both modules to Forge's parent pom: the only change made to any upstream file.

Then build with Maven from _build/forge (see the workflow, or README "Building").

Usage: python scripts/assemble.py
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import check_shadows
from common import FORGE, NEO, ROOT, WORK, read_lock, run, step

MODULES = ("forge-gui-neo", "forge-gui-campaign")


def fetch(repo: str, ref: str, dest: Path) -> None:
    """A shallow checkout of exactly one commit, reusing the folder if it exists."""
    if not (dest / ".git").is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        run(["git", "init", "-q", dest])
        run(["git", "-C", dest, "remote", "add", "upstream", repo])
    # Forge has paths longer than Windows' 260-character limit.
    run(["git", "-C", dest, "config", "core.longpaths", "true"])
    run(["git", "-C", dest, "fetch", "-q", "--depth", "1", "upstream", ref])
    run(["git", "-C", dest, "checkout", "-q", "--force", "FETCH_HEAD"])


def copy_module(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("target"))


def add_modules_to_pom(pom: Path) -> None:
    text = pom.read_text(encoding="utf-8")
    anchor = "<module>forge-gui-desktop</module>"
    if anchor not in text:
        sys.exit(f"{pom}: cannot find {anchor} to add our modules after it")
    for module in reversed(MODULES):
        line = f"<module>{module}</module>"
        if line in text:
            continue
        text = re.sub(r"(\s*)" + re.escape(anchor), lambda m: m.group(0) + m.group(1) + line, text, count=1)
    pom.write_text(text, encoding="utf-8")
    for module in MODULES:
        count = text.count(f"<module>{module}</module>")
        if count != 1:
            sys.exit(f"{pom}: expected <module>{module}</module> once, found {count}")


def main() -> int:
    lock = read_lock()
    WORK.mkdir(parents=True, exist_ok=True)

    step(f"1. Forge at {lock['FORGE_REF'][:12]}")
    fetch(lock["FORGE_REPO"], lock["FORGE_REF"], FORGE)
    step(f"   Neo Forge at {lock['NEO_REF'][:12]}")
    fetch(lock["NEO_REPO"], lock["NEO_REF"], NEO)

    step("2. Shadowed files still match upstream")
    if check_shadows.main() != 0:
        return 1

    step("3. Our module and Neo Forge's, inside the Forge reactor")
    copy_module(NEO / "forge-gui-neo", FORGE / "forge-gui-neo")
    copy_module(ROOT / "forge-gui-campaign", FORGE / "forge-gui-campaign")

    step("4. The one line each in Forge's parent pom")
    add_modules_to_pom(FORGE / "pom.xml")
    print(f"Assembled in {FORGE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
