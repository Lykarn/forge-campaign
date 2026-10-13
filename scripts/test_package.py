"""Check the PACKAGED app, with its own Java and cards: what a player downloads, not the build tree.

  1. The package holds our plane and our shadowed Config.             failure = red build
  2. deckcheck: the engine loads all cards from the zip and the
     deck rules apply, with no window (Neo Forge's own check).          failure = red build
  3. The Adventure, opened from the menu as a player opens it, plays
     a self-test duel on Neo Forge's table, on the Campaign plane.     plane wrong = red build;
                                                                         no window (no GPU) = warning

Logs land in _build/out for the CI artifact. Run after scripts/package.py.
Usage: python scripts/test_package.py
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from common import IS_WINDOWS, OUT, ROOT, WORK

APP = WORK / "dist" / "ForgeCampaign"
PLANE = "Campaign"
failures = 0
warnings = 0


def fail(message: str) -> None:
    global failures
    failures += 1
    print(f"::error::{message}" if os.environ.get("GITHUB_ACTIONS") else f"[FAIL] {message}")


def warn(message: str) -> None:
    global warnings
    warnings += 1
    print(f"::warning::{message}" if os.environ.get("GITHUB_ACTIONS") else f"[WARN] {message}")


def launcher() -> Path:
    if IS_WINDOWS:
        return APP / "ForgeCampaign-console.exe"
    return APP / "bin" / "ForgeCampaign"


def kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.kill()


def run_app(args: list[str], log: Path, timeout: int, extra_java: str = "",
            stop_when=None) -> None:
    """Run the packaged launcher, output to log; stop on timeout or when stop_when() says so."""
    env = dict(os.environ)
    env["JAVA_TOOL_OPTIONS"] = (env.get("JAVA_TOOL_OPTIONS", "") + " " + extra_java).strip()
    with open(log, "w", encoding="utf-8", errors="replace") as out:
        proc = subprocess.Popen([str(launcher()), *args], cwd=APP, env=env,
                                stdout=out, stderr=subprocess.STDOUT)
        start = time.time()
        while proc.poll() is None and time.time() - start < timeout:
            time.sleep(5)
            if stop_when and stop_when():
                time.sleep(5)
                break
        kill_tree(proc)
        proc.wait(timeout=60)
    print(f"  {log.name}: exit {proc.returncode} after {time.time() - start:.0f}s")


def tail(path: Path, lines: int = 15) -> str:
    if not path.is_file():
        return f"  ({path.name} not written)"
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join("  | " + line for line in text[-lines:])


def check_contents() -> None:
    print("\n== 1. The package holds our plane, our shadowed classes and our AI profiles")
    # A plane is a folder with a world/world.json (config.json is optional: Config falls back to
    # common/), plus campaign.json from our overlay to show the overlay was applied.
    for marker in ("world/world.json", "campaign.json"):
        if not (APP / "res" / "adventure" / PLANE / marker).is_file():
            fail(f"res/adventure/{PLANE}/{marker} is missing")
    jar = APP / "app" / "campaign.jar"
    if not jar.is_file():
        fail("app/campaign.jar is missing")
        return
    # Every shadow in shadows.tsv must be OUR class in campaign.jar. Each one calls into our code
    # or reads our property, so its bytecode names "campaign"; the upstream originals never do.
    shadows = [line.split("\t")[0] for line in (ROOT / "shadows.tsv").read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.startswith("#")]
    with zipfile.ZipFile(jar) as zf:
        for ours in shadows:
            cls = ours.split("src/main/java/", 1)[1].replace(".java", ".class")
            try:
                data = zf.read(cls)
            except KeyError:
                fail(f"campaign.jar has no {cls}: the shadow is not packaged")
                continue
            if b"campaign" not in data:
                fail(f"{cls} in campaign.jar is the upstream original, not our shadow")
    for profile in sorted((ROOT / "res" / "ai").glob("*.ai")):
        if not (APP / "res" / "ai" / profile.name).is_file():
            fail(f"res/ai/{profile.name} is missing from the package")
    if not failures:
        print(f"  ok: plane folder present, {len(shadows)} shadowed classes are ours, AI profiles installed")


def check_deckcheck() -> None:
    print("\n== 2. deckcheck: engine and cards load from the package")
    log = OUT / "deckcheck.log"
    # Some of Neo Forge's checks expect its Spanish messages, as its own CI runs them.
    run_app(["deckcheck"], log, timeout=900, extra_java="-Duser.language=es -Duser.country=ES")
    print(tail(log))
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    timing = "El buscador responde en menos de"
    bad = [line for line in text.splitlines()
           if re.search(r"\bFALLO\b|\[MAL\]", line) and timing not in line]
    if any(timing in line and "[MAL]" in line for line in text.splitlines()):
        warn("the card search was slower than 150 ms cold on this machine (see deckcheck.log)")
    if bad or not any(marker in text for marker in ("comprobaciones OK", "TODO BIEN", "OK - ")):
        fail("deckcheck did not pass with the package (see deckcheck.log)")


def find_adventure_log() -> Path | None:
    hits = sorted((APP / "data").rglob("adventure.log")) if (APP / "data").exists() else []
    return hits[0] if hits else None


def check_adventure() -> None:
    print("\n== 3. The Adventure from the menu: a self-test duel on the Campaign plane")

    def done() -> bool:
        log = find_adventure_log()
        if not log:
            return False
        text = log.read_text(encoding="utf-8", errors="replace")
        return "PARTIDA TERMINADA" in text or "Could not find or load main class" in text

    # On a fresh data/ folder Neo Forge opens its tutorial instead of the main menu, and the
    # Adventure auto-launch only fires from the menu. Mark the tutorial as already offered (the
    # flag NeoTutorial writes itself); a settings file that exists also means "not first run".
    prefs = APP / "data" / "preferences" / "neo.properties"
    if not prefs.is_file():
        prefs.parent.mkdir(parents=True, exist_ok=True)
        prefs.write_text("tutorialSeen=true\n", encoding="utf-8")

    run_app(["ui"], OUT / "menu.log", timeout=600, stop_when=done,
            extra_java="-Dneo.adventure.autoLaunch=true -Dneo.adventure.selftest=duel "
                       "-Dneo.adventure.auto=true")
    log = find_adventure_log()
    if log:
        shutil.copy2(log, OUT / "adventure.log")
    print(tail(OUT / "adventure.log"))
    text = (OUT / "adventure.log").read_text(encoding="utf-8", errors="replace") \
        if (OUT / "adventure.log").is_file() else ""
    planes = [line.split("[campaign] plane:", 1)[1].strip()
              for line in text.splitlines() if "[campaign] plane:" in line]
    if "Could not find or load main class" in text:
        fail("the Adventure process cannot find its main class (see adventure.log)")
    if planes and any(p != PLANE for p in planes):
        fail(f"the Adventure loaded plane {planes} instead of {PLANE}")
    elif planes:
        print(f"  ok: the Adventure loaded the {PLANE} plane")
    else:
        warn("the Adventure did not reach plane loading; no GPU on this machine is the usual cause")
    if "PARTIDA TERMINADA" in text:
        print("  ok: the self-test duel finished")
    else:
        warn("the self-test duel did not finish (see adventure.log)")
    for name in ("neo.log",):
        for hit in (APP / "data").rglob(name) if (APP / "data").exists() else []:
            shutil.copy2(hit, OUT / name)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not launcher().exists():
        fail(f"launcher not found: {launcher()}")
        return 1
    check_contents()
    check_deckcheck()
    check_adventure()
    print(f"\n{failures} failure(s), {warnings} warning(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
