"""Shared helpers for the build scripts. Standard library only, so the scripts run on any
machine with Python 3.9+ (GitHub's Windows runners included)."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("CAMPAIGN_WORK", ROOT / "_build"))
FORGE = WORK / "forge"
NEO = WORK / "neo"
OUT = WORK / "out"

IS_WINDOWS = sys.platform.startswith("win")


def read_lock() -> dict[str, str]:
    """upstream.lock as a dict: FORGE_REPO, FORGE_REF, NEO_REPO, NEO_REF."""
    values: dict[str, str] = {}
    for line in (ROOT / "upstream.lock").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    for key in ("FORGE_REPO", "FORGE_REF", "NEO_REPO", "NEO_REF"):
        if not values.get(key):
            sys.exit(f"upstream.lock is missing {key}")
    return values


def run(cmd: list[str], cwd: Path | None = None, **kwargs) -> subprocess.CompletedProcess:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], cwd=cwd, check=True, **kwargs)


def rmtree(path: Path) -> None:
    """shutil.rmtree that also removes read-only files (jpackage makes its .exe launchers
    read-only, and Windows refuses to delete those)."""
    def clear_and_retry(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)
    shutil.rmtree(path, onerror=clear_and_retry)


def step(title: str) -> None:
    print(f"\n== {title}", flush=True)
