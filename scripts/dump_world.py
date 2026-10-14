"""Generate the Campaign world in the packaged app and save its map as a PNG, to author the layout.

Starts the app with Neo Forge's Adventure self-test (selftest=anteduel makes a new world) and our
World's dump hook (-Dcampaign.dumpWorld), waits for the image, then closes the app. A window opens
for about a minute. Map tiles = image pixels / 4, counted from the top-left: the coordinates
plane/world/region_layout.json uses. With --grid, a copy with a 25-tile grid is also written.

Usage: python scripts/dump_world.py [--out _build/out/world.png] [--grid]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from common import OUT, WORK

APP = WORK / "dist" / "ForgeCampaign"


def kill_app() -> None:
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '"
                    + str(APP) + "*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   capture_output=True)


def add_grid(src: Path, dest: Path, tile_px: int = 4, every: int = 25) -> None:
    """A grid every 25 tiles, labelled in tiles, without image libraries: via PowerShell's System.Drawing."""
    script = f"""
Add-Type -AssemblyName System.Drawing
$img = [System.Drawing.Image]::FromFile('{src}')
$bmp = New-Object System.Drawing.Bitmap $img
$img.Dispose()
$g = [System.Drawing.Graphics]::FromImage($bmp)
$pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(110, 0, 0, 0)), 2
$font = New-Object System.Drawing.Font 'Arial', 26
$brush = [System.Drawing.Brushes]::Black
$step = {tile_px * every}
for ($p = 0; $p -lt $bmp.Width; $p += $step) {{ $g.DrawLine($pen, $p, 0, $p, $bmp.Height); $g.DrawString(($p / {tile_px}).ToString(), $font, $brush, $p + 3, 3) }}
for ($p = 0; $p -lt $bmp.Height; $p += $step) {{ $g.DrawLine($pen, 0, $p, $bmp.Width, $p); $g.DrawString(($p / {tile_px}).ToString(), $font, $brush, 3, $p + 3) }}
$small = New-Object System.Drawing.Bitmap $bmp, ([int]($bmp.Width / 2)), ([int]($bmp.Height / 2))
$small.Save('{dest}', [System.Drawing.Imaging.ImageFormat]::Png)
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT / "world.png"))
    parser.add_argument("--grid", action="store_true")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    # The build's own data/ folder (a test copy, never a player's): the launcher's -Dneo.dataDir
    # wins over JAVA_TOOL_OPTIONS. Skip Neo Forge's first-run tutorial, as test_package.py does.
    prefs = APP / "data" / "preferences" / "neo.properties"
    if not prefs.is_file():
        prefs.parent.mkdir(parents=True, exist_ok=True)
        prefs.write_text("tutorialSeen=true\n", encoding="utf-8")
    env = dict(os.environ)
    env["JAVA_TOOL_OPTIONS"] = (f"-Dneo.adventure.autoLaunch=true -Dneo.adventure.selftest=anteduel "
                                f"-Dneo.adventure.ante=false \"-Dcampaign.dumpWorld={out}\"")
    exe = APP / "ForgeCampaign-console.exe"
    log = open(OUT / "dump_world.log", "w", encoding="utf-8", errors="replace")
    subprocess.Popen([str(exe), "ui"], cwd=APP, env=env, stdout=log, stderr=subprocess.STDOUT)
    start = time.time()
    while not out.exists() and time.time() - start < 300:
        time.sleep(2)
    time.sleep(3)
    kill_app()
    log.close()
    if not out.exists():
        print(f"no map written after 5 minutes: see {OUT / 'dump_world.log'}")
        return 1
    print(f"map: {out}")
    if args.grid:
        grid = out.with_name(out.stem + "_grid.png")
        add_grid(out, grid)
        print(f"map with grid (half size): {grid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
