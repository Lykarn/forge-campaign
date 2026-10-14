"""Package the built tree as a portable folder with its own Java, then zip it.

Run after Maven has built forge-gui-campaign inside _build/forge. Must run on the target OS:
jpackage only builds launchers for the machine it runs on (CI uses a Windows runner).

Layout of the result (ForgeCampaign/):
  ForgeCampaign.exe          the game (no console window)
  ForgeCampaign-console.exe  the same with a console, for headless checks (Windows only)
  app/, runtime/             jars and a bundled Java 17
  res/                       Forge's resources, plus our plane in res/adventure/Campaign
  data/                      created on first launch: saves, decks, settings (portable)

Usage: python scripts/package.py
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

from common import FORGE, IS_WINDOWS, NEO, OUT, ROOT, WORK, read_lock, rmtree, run, step

APP_NAME = "ForgeCampaign"
PLANE_NAME = "Campaign"
BASE_PLANE = "Shandalar"

# --add-opens the engine and the Adventure need (the union of Neo Forge's package list and
# the list its AdventureLauncher passes to a plain java child process).
ADD_OPENS = [
    "java.base/java.util", "java.base/java.lang", "java.base/java.lang.reflect",
    "java.base/java.text", "java.base/java.util.concurrent", "java.base/java.math",
    "java.base/java.net", "java.base/java.nio", "java.base/sun.nio.ch",
    "java.base/jdk.internal.misc",
    "java.desktop/java.beans", "java.desktop/javax.swing.border", "java.desktop/javax.swing.event",
    "java.desktop/sun.swing", "java.desktop/java.awt.image", "java.desktop/java.awt.color",
    "java.desktop/sun.awt.image", "java.desktop/javax.swing", "java.desktop/java.awt",
    "java.desktop/java.awt.font",
]
JAVA_OPTIONS = [
    "-Dfile.encoding=UTF-8",
    "-XX:MaxRAMPercentage=50",
    "-Dio.netty.tryReflectionSetAccessible=true",
    # $ROOTDIR is replaced by the launcher with the ForgeCampaign/ folder. The trailing slash
    # matters: Forge builds paths as ASSETS_DIR + "res".
    "-Dforge.assetsDir=$ROOTDIR/",
    "-Dneo.dataDir=$ROOTDIR/data",
] + [f"--add-opens={m}=ALL-UNNAMED" for m in ADD_OPENS]


def campaign_version() -> str:
    pom = (ROOT / "forge-gui-campaign" / "pom.xml").read_text(encoding="utf-8")
    match = re.search(r"<campaign.version>(.+?)</campaign.version>", pom)
    if not match:
        sys.exit("forge-gui-campaign/pom.xml has no <campaign.version>")
    return match.group(1)


def one(paths: list[Path], what: str) -> Path:
    if len(paths) != 1:
        sys.exit(f"expected exactly one {what}, found {len(paths)}: {paths}")
    return paths[0]


def merge_jars(ours: Path, neo: Path, dest: Path) -> int:
    """One main jar: our classes first, then Neo Forge's.

    The launcher puts the main jar first on the classpath, so every class in it shadows the
    same class in Forge's jars. Neo Forge relies on that for its own shadow of DuelScene, so its
    classes must live in the main jar too; ours go on top and win over both.
    """
    seen: set[str] = set()
    shadowed = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
        for jar in (ours, neo):
            with zipfile.ZipFile(jar) as src:
                for info in src.infolist():
                    name = info.filename
                    if re.match(r"META-INF/.*\.(SF|RSA|DSA|EC)$", name):
                        continue
                    if name in seen:
                        if not name.endswith("/") and jar == neo:
                            shadowed += 1
                        continue
                    seen.add(name)
                    out.writestr(info, src.read(name))
    return shadowed


def zip_cardsfolder(cardsfolder: Path) -> int:
    """All card scripts in one cardsfolder.zip, as every Forge download ships them.

    The engine reads the zip on its own and loads faster from it. The loose .txt files must go:
    with both present, the engine loads every card twice.
    """
    scripts = sorted((p for p in cardsfolder.rglob("*.txt")), key=lambda p: p.as_posix())
    with zipfile.ZipFile(cardsfolder / "cardsfolder.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for path in scripts:
            zf.write(path, path.relative_to(cardsfolder).as_posix())
    for path in scripts:
        path.unlink()
    for folder in sorted((p for p in cardsfolder.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
        if not any(folder.iterdir()):
            folder.rmdir()
    return len(scripts)


def write_source_notice(app: Path, lock: dict[str, str]) -> None:
    ours = os.environ.get("GITHUB_SHA", "local build")
    (app / "SOURCE.txt").write_text(
        "Forge Campaign is free software under the GNU GPL v3 (see LICENSE-GPL3.txt).\n"
        "This build was made from these exact sources:\n\n"
        f"  Forge Campaign  https://github.com/Lykarn/forge-campaign  {ours}\n"
        f"  Forge           {lock['FORGE_REPO']}  {lock['FORGE_REF']}\n"
        f"  Neo Forge       {lock['NEO_REPO']}  {lock['NEO_REF']}\n",
        encoding="utf-8",
    )


def zip_folder(folder: Path, dest: Path) -> None:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(folder.rglob("*")):
            arc = (Path(folder.name) / path.relative_to(folder)).as_posix()
            if path.is_dir():
                continue
            zf.write(path, arc)


def main() -> int:
    lock = read_lock()
    version = campaign_version()
    target = FORGE / "forge-gui-campaign" / "target"
    lib = target / "lib"
    stage = WORK / "stage"
    dist = WORK / "dist"
    OUT.mkdir(parents=True, exist_ok=True)

    step("1. Jars: one main jar (ours over Neo Forge's), the rest as they are")
    if stage.exists():
        rmtree(stage)
    stage.mkdir(parents=True)
    neo_jar = one(sorted(lib.glob("forge-gui-neo-*.jar")), "forge-gui-neo jar in target/lib")
    our_jar = one([p for p in target.glob("forge-gui-campaign-*.jar")
                   if not p.name.endswith(("-sources.jar", "-javadoc.jar"))], "forge-gui-campaign jar")
    for jar in lib.glob("*.jar"):
        if jar != neo_jar:
            shutil.copy2(jar, stage / jar.name)
    shadowed = merge_jars(our_jar, neo_jar, stage / "campaign.jar")
    print(f"  campaign.jar: merged; {shadowed} duplicate entries kept from ours")
    platform_fx = "win" if IS_WINDOWS else "linux"
    if not any(re.match(rf"javafx-graphics-.*-{platform_fx}", p.name) for p in stage.iterdir()):
        sys.exit(f"JavaFX native libraries for {platform_fx} are missing from the jars")

    step("2. The app folder with its own Java (jpackage)")
    if dist.exists():
        rmtree(dist)
    jpackage = shutil.which("jpackage")
    if not jpackage and os.environ.get("JAVA_HOME"):
        jpackage = str(Path(os.environ["JAVA_HOME"]) / "bin" / ("jpackage.exe" if IS_WINDOWS else "jpackage"))
    if not jpackage or not Path(jpackage).exists():
        sys.exit("jpackage not found: use a JDK 17 (not a JRE) and put it on PATH or JAVA_HOME")
    cmd = [jpackage, "--type", "app-image", "--name", APP_NAME, "--app-version", version,
           "--vendor", "Forge Campaign (fan project)",
           "--input", stage, "--main-jar", "campaign.jar", "--main-class", "forge.neo.NeoMain",
           "--arguments", "ui", "--dest", dist,
           # Keep java.exe/javaw.exe in the runtime (jpackage strips them by default). Without
           # them Neo Forge opens the Adventure by relaunching ForgeCampaign.exe itself, and
           # antivirus heuristics (Surfshark: Drop.Win64.UserProfileSelfRun) quarantine an
           # unsigned exe that runs itself from the user profile. With them it starts javaw.exe.
           "--jlink-options", "--strip-debug --no-man-pages --no-header-files"]
    for option in JAVA_OPTIONS:
        cmd += ["--java-options", option]
    if IS_WINDOWS:
        console = WORK / "console-launcher.properties"
        console.write_text("win-console=true\n", encoding="utf-8")
        cmd += ["--add-launcher", f"{APP_NAME}-console={console}"]
    run(cmd)
    app = dist / APP_NAME
    if not app.is_dir():
        sys.exit(f"jpackage did not create {app}")
    for cfg in app.rglob("*.cfg"):
        print(f"  {cfg.relative_to(app)}:")
        print("    " + cfg.read_text(encoding="utf-8", errors="replace").replace("\n", "\n    "))

    step("3. Forge's resources, our added resources, and our plane")
    res = app / "res"
    shutil.copytree(FORGE / "forge-gui" / "res", res)
    # res/ in this repo (when present) only ADDS files, such as a new AI profile; never replace
    # one of Forge's, which would be an upstream edit by another name.
    added = 0
    for src in (ROOT / "res").rglob("*") if (ROOT / "res").is_dir() else []:
        if src.is_file():
            dest = res / src.relative_to(ROOT / "res")
            if dest.exists():
                sys.exit(f"res/{dest.relative_to(res).as_posix()} already exists in Forge: res/ may only add files")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            added += 1
    print(f"  res/: Forge's, plus {added} files of ours")
    plane = res / "adventure" / PLANE_NAME
    shutil.copytree(res / "adventure" / BASE_PLANE, plane)
    overlay = ROOT / "plane"
    files = 0
    for src in overlay.rglob("*"):
        if src.is_file():
            dest = plane / src.relative_to(overlay)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            files += 1
    print(f"  res/adventure/{PLANE_NAME}: a copy of {BASE_PLANE} with {files} overlay files")
    print(f"  cardsfolder.zip: {zip_cardsfolder(res / 'cardsfolder')} scripts")

    step("4. Licence, notices and source pointers")
    shutil.copy2(ROOT / "LICENSE", app / "LICENSE-GPL3.txt")
    shutil.copy2(ROOT / "NOTICE.md", app / "NOTICE.txt")
    shutil.copy2(ROOT / "docs" / "PLAYING.md", app / "README.txt")
    if (NEO / "AVISOS.txt").is_file():
        shutil.copy2(NEO / "AVISOS.txt", app / "NEOFORGE-AVISOS.txt")
    write_source_notice(app, lock)

    step("5. The zip (before any test writes into data/)")
    if (app / "data").exists():
        sys.exit("the package already has a data/ folder: it is not clean")
    arch = "x64"
    zip_path = OUT / f"{APP_NAME}-{'windows' if IS_WINDOWS else 'linux'}-{arch}.zip"
    if zip_path.exists():
        zip_path.unlink()
    zip_folder(app, zip_path)
    print(f"  {zip_path.name}: {zip_path.stat().st_size / 1e6:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
