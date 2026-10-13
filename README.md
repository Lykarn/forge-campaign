# Forge Campaign

A reworked Adventure campaign for Magic: The Gathering, built on [Forge](https://github.com/Card-Forge/forge)'s rules engine with duels played on [Neo Forge](https://github.com/AdrianLopez98/NeoForge)'s table. It fixes three things about Forge's Adventure mode:

- **AI opponents** that play cards just because they can. Opponents get tiers: tuned AI profiles, simulation for elites and bosses, and decks built to the AI's strengths.
- **Exploration** across an open noise map of near-identical towns. The world becomes authored regions with gates, fog of war and towns worth remembering.
- **Shops** that bury upgrades in dozens of random cards. Each town gets one merchant with a short list scored against your deck.

Free, unofficial fan project; see [NOTICE.md](NOTICE.md). The full design is in the project plan doc.

## Status

**Phase 1, AI tiers.** Phase 0 (Gate A) passed: the build assembles Forge and Neo Forge at pinned commits, adds this module, and packages a Windows app whose Adventure runs on a `Campaign` plane. Phase 1 gives every enemy a tier. Grunts play Forge's normal AI. Elites get a tuned profile plus a simulated safety check on every play. Bosses get full look-ahead search under a time budget. Enemy decks are cleaned of cards the AI cannot use. A headless benchmark measures each tier's win rate and speed.

## How it is put together

This repo holds only our code and data. Upstream code is fetched at exact commits and never edited:

| Path | What it is |
| --- | --- |
| `upstream.lock` | The Forge and Neo Forge commits we build against. Bump both to rebase |
| `forge-gui-campaign/` | Our Maven module. It is built inside Forge's reactor, next to `forge-gui-neo` |
| `shadows.tsv` | Every upstream class we replace, with the hash of the original we copied |
| `plane/` | Files laid over a copy of Shandalar to make `res/adventure/Campaign`: enemy tiers (`world/enemy_tiers.json`) and AI-playable enemy decks (`decks/`) |
| `res/` | Files added to Forge's `res/` (the Elite and Boss AI profiles). Add-only: `package.py` refuses to replace a Forge file |
| `bench/` | Reference player decks for the tier benchmark |
| `scripts/` | Build: `assemble.py`, `package.py`, `test_package.py`, `check_shadows.py`. AI: `bench.py` (tier benchmark), `lint_decks.py`, `fix_decks.py` |
| `.github/workflows/windows.yml` | Builds, packages and tests on every push |

**Why shadowed classes.** To change Adventure behaviour without editing Forge, we put our own copy of a class ahead of Forge's on the classpath. The packaged app's main jar holds our classes, then Neo Forge's, and the launcher always loads the main jar first. Neo Forge uses the same trick for its duel screen. The risk is drift: if upstream changes a class we copied, our copy silently goes stale. `check_shadows.py` hashes each original at the pinned commit and fails the build if it moved.

**Why only Windows builds.** Neo Forge's Adventure bridge is Windows-only for now. CI uses a Windows runner because `jpackage` can only build launchers for the OS it runs on.

## Building

You normally don't need to: every push builds a Windows zip under **Actions > the run > Artifacts**. To build locally you need JDK 17, Maven 3.9, Git and Python 3.9+:

```powershell
git config --global core.longpaths true
python scripts/assemble.py                     # fetch upstream, check shadows, add our module
cd _build/forge
mvn -B install -DskipTests -DskipLaunch4j=true -pl forge-gui-campaign -am
cd ../..
python scripts/package.py                      # _build/out/ForgeCampaign-windows-x64.zip
python scripts/test_package.py                 # checks the packaged app
python scripts/bench.py                        # optional: enemy win rate and seconds per turn by tier
```

## Rebasing on newer upstream

1. Change `FORGE_REF` and `NEO_REF` in `upstream.lock` (take Neo Forge's `FORGE_REF` from its workflows, so the pair is one Neo Forge has tested).
2. Push. If `check_shadows.py` fails, re-copy each listed original, re-apply the blocks marked `FORGE-CAMPAIGN`, and update its hash in `shadows.tsv`.

## Licence

GNU GPL v3, the same as Forge and Neo Forge. See [LICENSE](LICENSE).
