# Forge Campaign: context for Claude

A free, non-commercial hobby project by Rory: a reworked Magic: The Gathering Adventure campaign on Forge's rules engine (Card-Forge/forge) with duels on Neo Forge's JavaFX table (AdrianLopez98/NeoForge). Separate from Rory's job. Mostly for personal use; may be shared free with the Forge community later. GPL-3.0.

The full research and design plan is a Claude doc Rory owns: https://claude.ai/code/artifact/273d784a-cda6-4a27-92cf-ee3ab790a138

## Working agreement

- Rory is hands-off. Claude designs and builds everything in the plan and makes the calls inside it.
- Ask Rory only about: scope changes, sharing or licensing, and problems only visible on his Windows machine.
- Work happens on `claude/...` branches, one pull request per gate. Each gate has a test script in `docs/gates/`. Rory tests, and merging the PR is his sign-off.
- Rory prefers to understand the reasoning behind technical steps, so explain why, briefly.

## Hard rules

- Never edit upstream files. The only upstream change is the two `<module>` lines `scripts/assemble.py` adds to Forge's parent pom.
- Change upstream behaviour only through shadowed classes in `forge-gui-campaign/`: a full copy of the original with changes marked `FORGE-CAMPAIGN`, listed in `shadows.tsv` with the sha256 of the original. Keep the shadow set small.
- Neo Forge already shadows `forge/adventure/scene/DuelScene.java` and `DeckEditScene.java`. To change either, start from Neo Forge's copy, not Forge's, and record the Neo file in `shadows.tsv` with upstream `neo`.
- Plane data changes go in `plane/`, which is laid over a copy of Shandalar to make `res/adventure/Campaign`. Files there override `common/` too (Adventure looks in the plane first), which is how `plane/decks/` replaces enemy decks.
- New resources outside the plane (AI profiles) go in `res/`, add-only: `package.py` refuses to replace a Forge file.
- Never ship card images (Forge downloads them from Scryfall at runtime). Never sell it. Keep `NOTICE.md` (Wizards Fan Content Policy wording).

## Build and test (Windows, PowerShell)

Needs JDK 17 (Temurin), Maven 3.9, Git, Python 3.9+.

```powershell
git config --global core.longpaths true
python scripts/assemble.py        # Forge + Neo Forge at upstream.lock commits, shadow check, add modules
cd _build/forge; mvn -B install -DskipTests -DskipLaunch4j=true -pl forge-gui-campaign -am; cd ../..
python scripts/package.py         # _build/dist/ForgeCampaign (jpackage app-image) and _build/out/*.zip
python scripts/test_package.py    # contents, Neo Forge deckcheck, Adventure self-test duel
```

`.github/workflows/windows.yml` does the same on GitHub Actions, but Rory's account has an Actions billing lock (Oct 2026), so build locally.

## Status

- **Phase 0 (Foundation), PR #1: Gate A passed** (Rory, 2026-10-13). Merging PR #1 is his sign-off.
- **Phase 1 (AI tiers), branch `claude/phase-1-ai-tiers`** (stacked on Phase 0). Built: tiers from `plane/world/enemy_tiers.json` (overrides, else boss flag, else life >= 25 = Elite; 366 Grunt / 58 Elite / 40 Boss), `CampaignAi` called from the shadowed `DuelScene`, `res/ai/Elite.ai` and `Boss.ai`, simulation budget (shadowed `SimulationController`), crash fallbacks for Forge's `GameCopier` "Couldn't map" bug (shadowed `SpellAbilityPicker`, `OnePlaySafetyChecker`), 152 AI-playable enemy decks (`scripts/fix_decks.py`), and `scripts/bench.py`. Next: benchmark A (today) vs B (tiers + fixed decks) vs C (fixed decks only), tune to Gate B targets, write `docs/gates/gate-b.md`.
- Shadows: `Config` (plane), `DuelScene` (Neo's copy; tiers), `SimulationController` (budget), `SpellAbilityPicker` and `OnePlaySafetyChecker` (fail safe). `test_package.py` checks each packaged shadow is ours.

## Roadmap and key decisions

Phases, each ending at a gate: 0 Foundation (Gate A) → 1 AI tiers (Gate B) → 2 one full region slice (Gate C) → 3 all regions, questline, castles (Gate D) → 4 free release.

- **AI tiers (Grunt, Elite, Boss):** a `tier` on enemies picks the AI profile (new `Elite.ai`, `Boss.ai` from Default/Experimental), simulation (`AIOption.USE_HYBRID_SIMULATION` for Elite, `USE_FULL_SIMULATION` for Boss, under a time budget), and deck rules (no `AI:RemoveDeck` cards, focused aggro/midrange). Set in the shadowed `DuelScene`, where `GamePlayerUtil.createAiPlayer(name, selectAI(currentEnemy.ai))` creates enemies today with no simulation. Measure with Forge's headless `sim` mode: win rate and seconds per turn by tier.
- **World:** replace the 700×700 noise world with an authored region graph (hub + five colour regions + late regions), gates via items or quest flags, fog of war, rumours, about 30 distinct towns. A region layout file drives a shadowed world generator; towns and dungeons stay Tiled `.tmx`.
- **Shops:** one merchant per town, 6–8 offers: 3 for your deck, 2 region specials, 1 wildcard, with a swap preview. Pick 1 of 3 after wins. Region card pools. Scores from a build-time pipeline (Scryfall bulk or MTGJSON, cached ≥24h) into `card_scores.json` in the plane.
- **Deck size:** minimum 40 in the first regions, 50 after the first castle, 60 late; enemies follow the same curve. +2 starting life per full 10 cards above the minimum, up to two breakpoints, tuned by benchmark. Some encounters set their own rules (60+, singleton, commons). Town drafts stay 40-card.
- **Setting:** Shandalar assets. **Platform:** Windows first.

## Useful upstream facts

- Adventure code: `forge-gui-mobile/src/forge/adventure` (libGDX). Data: `forge-gui/res/adventure/<Plane>` and `common/`.
- Plane choice: `Config` reads `settings.json` in `USER_ADVENTURE_DIR`; our shadow forces `Campaign` (override `-Dcampaign.plane=`).
- Adventure difficulty only scales enemy life (`enemyLifeFactor`); 462 of 464 enemies use the global AI profile.
- Neo Forge runs Adventure in a second process (`AdventureLauncher` → `AdventureNeoMain`); its self-test flags (`-Dneo.adventure.autoLaunch=true -Dneo.adventure.selftest=duel -Dneo.adventure.auto=true`) play a duel automatically and log `PARTIDA TERMINADA`.
- The packaged main jar holds our classes, then Neo Forge's; the launcher loads the main jar first, which is what makes shadowing work.

## Windows gotchas found in the first local build

- Forge's `.gitattributes` (`* text=auto`) checks files out as CRLF on Windows; `check_shadows.py` hashes with LF so hashes match on every OS.
- jpackage strips `java.exe` from the runtime by default; then Neo Forge opens the Adventure by relaunching our own exe, which Surfshark quarantines (`Drop.Win64.UserProfileSelfRun`). `package.py` keeps `java.exe`/`javaw.exe` so the Adventure starts with `javaw.exe` instead.
- On a fresh `data/` Neo Forge shows its tutorial instead of the menu, which blocks the Adventure auto-launch; `test_package.py` seeds `tutorialSeen=true`.
- jpackage's exe launchers are read-only; delete build folders with `common.rmtree`.
