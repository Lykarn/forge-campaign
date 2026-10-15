# Forge Campaign: context for Claude

A free, non-commercial hobby project by Rory: a reworked Magic: The Gathering Adventure campaign on Forge's rules engine (Card-Forge/forge) with duels on Neo Forge's JavaFX table (AdrianLopez98/NeoForge). Separate from Rory's job. Mostly for personal use; may be shared free with the Forge community later. GPL-3.0.

The full research and design plan is a Claude doc Rory owns: https://claude.ai/code/artifact/273d784a-cda6-4a27-92cf-ee3ab790a138

## Working agreement

- Rory is hands-off. Claude designs and builds everything in the plan and makes the calls inside it.
- Ask Rory only about: scope changes, sharing or licensing, and problems only visible on his Windows machine.
- Work happens on `claude/...` branches, one branch per gate, each with a test script in `docs/gates/` that also summarises what changed. Rory tests, then merges the branch into `main` himself with GitHub Desktop: the merge is his sign-off. Hand him the branch name (and the merge order if branches are stacked); no pull-request pages or pasted descriptions, and he reports in chat. There is no `gh` CLI on his machine.
- Rory prefers to understand the reasoning behind technical steps, so explain why, briefly.

## Hard rules

- Never edit upstream files. The only upstream change is the two `<module>` lines `scripts/assemble.py` adds to Forge's parent pom.
- Change upstream behaviour only through shadowed classes in `forge-gui-campaign/`: a full copy of the original with changes marked `FORGE-CAMPAIGN`, listed in `shadows.tsv` with the sha256 of the original. Keep the shadow set small.
- Neo Forge already shadows `forge/adventure/scene/DuelScene.java` and `DeckEditScene.java`. To change either, start from Neo Forge's copy, not Forge's, and record the Neo file in `shadows.tsv` with upstream `neo`.
- Plane data changes go in `plane/`, which is laid over a copy of Shandalar to make `res/adventure/Campaign`. Files there override `common/` too (Adventure looks in the plane first), which is how `plane/decks/` replaces enemy decks.
- New resources outside the plane (e.g. an AI profile) go in `res/` (none at the moment), add-only: `package.py` refuses to replace a Forge file.
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

- **Phase 0 (Foundation): Gate A passed**, merged to `main` (PR #1, 2026-10-14).
- **Phase 1 (AI tiers): merged to `main`** (PR #2, 2026-10-14) before Rory ran the Gate B playtest (`docs/gates/gate-b.md`, helper `docs/gates/gate-b-fight.cmd`); his findings (Boss strength, turn time) land as tuning on later branches.
  - Tiers from `plane/world/enemy_tiers.json`: overrides, else boss flag, else life >= 25 = Elite (366 Grunt / 58 Elite / 40 Boss). All tiers use the Default profile; Grunt = no simulation, Elite = hybrid (safety check, ~1 veto/game), Boss = full simulation with 1.5 s per decision and 10 s per turn.
  - Benchmark (enemy win % vs Forge Default AI with `bench/decks`, midrange / aggro): Grunt 27/33, Elite 35/56 (stock 37/57), Boss 66/74 (stock 41/80). Boss slowest turn: 12 s in 9 of 10 games, worst 45 s.
  - Findings: Experimental-based Elite.ai and Boss.ai profiles made both tiers weaker (dropped). The budget can only cut between whole candidate plays (cutting inside SpellAbilityChoicesIterator breaks the search stack), hence the per-turn cap. Forge's GameCopier still throws "Couldn't map <card>" (The Monarch, some creatures) on ~0.5% of Boss decisions: caught, worth an upstream report. Bosses vs aggro are carried by 30-40 starting life: tune in Phase 2 against real player progression.
- **Phase 2 (region slice), branch `claude/phase-2-region-slice`**: built; `test_package.py` passes, including `forge.campaign.SelfCheck` (in-game checks of gates, fog, merchant, pick 1 of 3, deck size, run during the Boss self-test duel). Waiting on Rory's Gate C playtest (`docs/gates/gate-c.md`).
  - World: `plane/world/region_layout.json` (fixed seed 20261014; regions = biome groups; authored regions hub + white place POIs at fixed tiles; water walls between regions; passes, gated by quest flag). Entries with `build` become generated maps via `scripts/make_maps.py` (towns with one merchant, watchtower, gate, closed-road signs, key fort) plus `points_of_interest.patch.json`. Author with `scripts/dump_world.py` (map + region PNG) and `scripts/layout_check.py`.
  - Fog: `World.getBiomeImage()` returns `forge.campaign.world.Fog`'s darkened copy; regions reveal via `revealedAtStart` or tower quest flag.
  - Shops: `scripts/card_scores.py` (MTGJSON edhrecRank + Forge editions/scripts, hand tiers in `plane/world/card_tiers.json`) -> `plane/card_scores.json`; pools in `plane/world/card_pools.json` (hub M10, white DOM). `RewardData` type `campaignMerchant` -> `forge.campaign.shop.Merchant` (3 deck-fit / 2 specials / 1 wildcard, offers snapshotted per stock in `MerchantLedger`, saved in the world save); swap preview on the buy button (`RewardScene`).
  - Rewards: won map duels -> pick 1 of 3 (`DuelRewards`, `RewardScene`). Deck size: +2 life per 10 cards over 40, max +4 (`DeckSize`, `DuelScene`).
  - Not done yet: rumours, authored quest threads, hand-made town maps (towns reuse upstream maps), dungeons as Ascent-style climbs, wishlist.
- **Phase 3 (all regions), branch `claude/phase-3-regions`** (stacked on Phase 2): five authored regions (pools M10, DOM, KLD, XLN, DTK, ISD), roads gated on castle flags (`Ch1<Colour>CastleComplete`: White opens blue+green, Green opens red, Blue opens black), finale Emrakul at `Ch1CastlesComplete` >= 5, Shandalar story locations placed for our order, deck minimum 40/50/60 by castles, region `enemyLifeBonus` (+2 blue/green, +4 red/black) and `enemyMinTier` (Elite in red/black). `test_package.py` passes. Waiting on Rory's Gate D (`docs/gates/gate-d.md`). Points of interest are auto-placed by `scripts/layout_place.py` (marks `auto`/`far`/`atPass`).
  - `SelfCheck` also enters all 79 POIs of the layout (closed regions opened for the check): each map loads, each town/capital has one merchant with 6 (8) offers.
  - Difficulty curve: `scripts/region_bench.py` benchmarks each region's roaming enemies (with its life bonus / min tier, at the player's deck size there; 50/60-card reference decks in `bench/decks`), then castle bosses and the finale. `scripts/enemy_curve.py` turns a full enemy-strength run (`bench.py --grunts -1 --elites -1 --bosses 0`) into per-region enemy lists by strength band (`plane/world/biomes/*.patch.json`; `package.py` patches single-object files with `{"set": ...}`). Measured roaming enemy wins: hub ~15% rising to ~31% in Duskmire (was flat 20-35%). Castle boss life in `plane/world/enemies.patch.json` (target ~40% enemy wins at the first castle rising to ~65% at the finale); 16-game samples swing ±12%, so tune on 32+. Final (32 games each, life): Akroma 47% (16), Lorthos 38% (40, untouched), Ghalta 41% (22), Lathliss 53% (30), Griselbrand 44% (31), Emrakul 69% (30). Further tuning waits on Rory's Gate D playtest.
- **Relics and special enemies, branch `claude/relics-and-bosses`** (stacked on Phase 3; Rory asked for them before his next test, 2026-10-15; test doc `docs/gates/gate-d-relics.md`):
  - Relics: Adventure items whose effect puts one of our custom cards in the command zone. Two new slots (`plane/ui/inventory*.json`: `Relic` = castle tier, `Trinket` = champion tier). `scripts/make_relics.py` is the single source: writes `res/adventure/common/custom_cards/campaign_*.txt` (Adventure only loads custom cards from common/; our `res/` adds files there), `plane/world/relics.json`, the items in `items.patch.json`, `enemy_effects.json` and the reward markers in `enemies.patch.json`. Card names are checked against Forge's. Every card has `AI:RemoveDeck:All`; Adventure's reward pools skip custom cards.
  - Legendary choices (`forge.campaign.relics.LegendaryChoice`): marker items in loot ("Choice: Relic", "Choice: Castle Relic", "Choice: Power 9"); `RewardScene` queues them and shows a pick of one after the loot, drawn from what the player does not own. Castles → castle relic, champions → relic, side bosses (Nahiri, Jace, Garruk, Tibalt, Grolnok) → Power 9.
  - Power 9: `config.json` `restrictedCards` only filters random loot and boosters (not decks), so given rewards are fully playable and stay out of shops.
  - Enemy effects (`plane/world/enemy_effects.json`, `forge.campaign.enemies.EnemyEffects`): applied in every map duel by our `DuelScene`, and by `TierBench`. Upstream applies an enemy's `equipment` only in events, and its map effects (`effect`, `dungeonEffect` in the .tmx) only on that map; `region_bench.py` reads those from the maps so bosses are benchmarked as fought.
  - Oracle of the Alpha: new boss (`plane/decks/boss/oracle_of_the_alpha.dck`), lair "Alpha Sanctum" (`make_maps.py` kind `lair`: an upstream boss map with the boss swapped), shown at `Ch1CastlesComplete` >= 3; `takesPower9` moves the player's Power 9 into his deck for the duel (`PowerNine`; Wastes replace them).
  - Champions: 11 upstream boss dungeons added to the layout (Scarecrow Farm, Teferi Hideout, Kiora Island, Slimefoots Lair, Grove7, Slobads Factory, Zedruu City, Skep, Xiras Hive, VampireCastle3, Temple of Liliana).
  - Tools: `relic_bench.py` (each relic on the reference decks vs a fixed enemy sample), `region_bench.py --bosses | --only "A;B"`.
- Shadows (`shadows.tsv`; `scripts/shadow_patches/*.py` re-apply each on a rebase): `Config` (plane; thread-safe path lookups), `DuelScene` (Neo's copy; tiers, deck-size life, duel-win mark), `SimulationController` (budget), `SpellAbilityPicker` (budgets, fallback), `OnePlaySafetyChecker` (fail open, veto count), `World` (layout, walls, gates, fog, merchant save, quest-target filter), `PointOfInterest` (flag gating), `RewardData` (merchant), `RewardScene` (pick 1 of 3, swap preview). `test_package.py` checks each packaged shadow is ours.
- Tools: `scripts/bench.py` (headless tier benchmark, `--stock` baseline, resumable workers), `lint_decks.py`, `fix_decks.py` (writes `plane/decks/`, keep list `plane/decks/HAND_EDITED.txt`).

## Roadmap and key decisions

Phases, each ending at a gate: 0 Foundation (Gate A) → 1 AI tiers (Gate B) → 2 one full region slice (Gate C) → 3 all regions, questline, castles (Gate D) → 4 free release.

- **AI tiers (Grunt, Elite, Boss):** a `tier` on enemies picks the AI profile (new `Elite.ai`, `Boss.ai` from Default/Experimental), simulation (`AIOption.USE_HYBRID_SIMULATION` for Elite, `USE_FULL_SIMULATION` for Boss, under a time budget), and deck rules (no `AI:RemoveDeck` cards, focused aggro/midrange). Set in the shadowed `DuelScene`, where `GamePlayerUtil.createAiPlayer(name, selectAI(currentEnemy.ai))` creates enemies today with no simulation. Measure with Forge's headless `sim` mode: win rate and seconds per turn by tier.
- **World:** replace the 700×700 noise world with an authored region graph (hub + five colour regions + late regions), gates via items or quest flags, fog of war, rumours, about 30 distinct towns. A region layout file drives a shadowed world generator; towns and dungeons stay Tiled `.tmx`.
- **Shops:** one merchant per town, 6–8 offers: 3 for your deck, 2 region specials, 1 wildcard, with a swap preview. Pick 1 of 3 after wins. Region card pools. Scores from a build-time pipeline (Scryfall bulk or MTGJSON, cached ≥24h) into `card_scores.json` in the plane.
- **Deck size:** minimum 40 in the first regions, 50 after the first castle, 60 late; enemies follow the same curve. +2 starting life per full 10 cards above the minimum, up to two breakpoints, tuned by benchmark. Some encounters set their own rules (60+, singleton, commons). Town drafts stay 40-card.
- **Setting:** Shandalar assets. **Platform:** Windows first.
- **Relics and legendary rewards (Rory, 2026-10-15)**: built on `claude/relics-and-bosses` (see Status). Rory wants the finale extremely hard ("requiring a very strong deck"). The original plan:
  - **Power 9:** one pick per colour region from a secret chest or boss (pick 1 of the 9), so up to 5 by the finale. Fully playable once earned; scarcity is the limit. Lift Adventure's `restrictedCards` ban for them in our plane, but keep them out of shops and random loot.
  - **Oracle of the Alpha** (boss): starts with the Power 9 (Moxen and Lotus on the battlefield via `startBattleWithCard`); takes the player's Power 9 into his deck **for that match only** (our `DuelScene`).
  - **Planeswalker bosses**: start with a planeswalker in play (`startBattleWithCard`), for strong tuned decks.
  - **Relics** (Adventure items whose `EffectData` puts our custom cards in the command zone or battlefield): start with a planeswalker; an extra land per turn; +1 non-combat damage; a named card fetched at the first upkeep; "companion" access to a card for {3} once per game; keywords added with Forge's perpetual effects.

## Useful upstream facts

- Adventure code: `forge-gui-mobile/src/forge/adventure` (libGDX). Data: `forge-gui/res/adventure/<Plane>` and `common/`.
- Plane choice: `Config` reads `settings.json` in `USER_ADVENTURE_DIR`; our shadow forces `Campaign` (override `-Dcampaign.plane=`).
- Adventure difficulty only scales enemy life (`enemyLifeFactor`); 462 of 464 enemies use the global AI profile.
- Neo Forge runs Adventure in a second process (`AdventureLauncher` → `AdventureNeoMain`); its self-test flags (`-Dneo.adventure.autoLaunch=true -Dneo.adventure.selftest=duel -Dneo.adventure.auto=true`) play a duel automatically and log `PARTIDA TERMINADA`.
- The packaged main jar holds our classes, then Neo Forge's; the launcher loads the main jar first, which is what makes shadowing work.
- World generation is one method, `World.generateNew`; POI placement, roads and the minimap image are its middle sections. Biomes are noise blobs; the highest biome index wins a cell. POI `map` paths resolve against `common/` (ours: `../Campaign/maps/...`).
- Upstream bugs we work around: `Config` path lookups were not thread-safe (world gen could hang forever on a garbled structure path); `PointOfInterest.load` dropped `questFlagsToActivate`; `GameCopier` throws "Couldn't map <card>" on ~0.5% of simulated decisions.
- Quest stages pick target POIs from `World.getAllPointOfInterest()` by tag and distance; ours returns only POIs in authored regions.
- Neo Forge's `selftest=duel` skips `DuelScene`; `selftest=anteduel` (new world + duel against `-Dneo.adventure.enemy`) goes through it.

## Windows gotchas found in the first local build

- Forge's `.gitattributes` (`* text=auto`) checks files out as CRLF on Windows; `check_shadows.py` hashes with LF so hashes match on every OS.
- jpackage strips `java.exe` from the runtime by default; then Neo Forge opens the Adventure by relaunching our own exe, which Surfshark quarantines (`Drop.Win64.UserProfileSelfRun`). `package.py` keeps `java.exe`/`javaw.exe` so the Adventure starts with `javaw.exe` instead.
- On a fresh `data/` Neo Forge shows its tutorial instead of the menu, which blocks the Adventure auto-launch; `test_package.py` seeds `tutorialSeen=true`.
- jpackage's exe launchers are read-only; delete build folders with `common.rmtree`.
