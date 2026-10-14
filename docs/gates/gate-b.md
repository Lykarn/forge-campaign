# Gate B test: AI tiers

**What this gate proves:** enemies play at their tier (Grunt, Elite, Boss), Bosses think harder without keeping you waiting, and nothing crashes.

The benchmark has already measured win rates and speed (below). This test covers what only playing shows: whether Bosses feel smarter, and whether their thinking time is acceptable.

## What changed

| Tier | Who | How it plays |
| --- | --- | --- |
| Grunt | Most enemies (366 of 464) | Forge's normal AI, as before |
| Elite | Enemies with 25+ life (58) | Forge's normal AI plus a safety check: each play is simulated once and dropped if it backfires (about 1 play per game) |
| Boss | Enemies marked as bosses (40) | Looks ahead before each play, up to 1.5 s per decision and 10 s per turn |

Enemy decks also lost the cards Forge's AI cannot use (152 decks, including 37 of the 40 Boss decks), swapped for more copies of the deck's own playable cards.

## What the benchmark measured

Headless games of enemies against two tuned 40-card decks played by Forge's standard AI (the full 512-game run, plus 232 Elite and 160 Boss games on the final settings). Enemy win rate:

| Tier | vs Green-White Midrange | vs Red Aggro | Slowest turn (9 in 10 games / worst) |
| --- | ---: | ---: | ---: |
| Grunt | 27% | 33% | 0.3 s / 10 s |
| Elite | 35% | 56% | 1 s / 26 s |
| Boss | 66% | 74% | 12 s / 45 s |

- Before Phase 1, Bosses with the same decks won 40-41% against midrange: the look-ahead adds about 25 points. Elites win as often as before (37% / 57%); the safety check stops bad plays rather than winning more games against an AI opponent.
- Targets: Grunts lose most games (met). Bosses "win close to half": above it here (66%), but the reference deck is played by Forge's AI, and you play better than it, so against you they should land nearer half. Your test below decides whether they are too strong; a smaller time budget softens them. Against aggro their 30-40 starting life does much of the work; that gets tuned in Phase 2 against real player progression.
- Two tuned AI profiles (Elite.ai, Boss.ai, from Forge's Experimental) were tried and dropped: both made their tier weaker.

## Get the build

Unzip `_build\out\ForgeCampaign-windows-x64.zip` twice, into two folders outside Program Files:

- **Play copy**: for normal Adventure play. Your Gate A copy is fine to replace.
- **Fight copy**: for the Boss test below. It makes a throwaway Adventure world, so never use your real saves here.

## Test (about 20 minutes)

1. **Normal play (play copy).** Start or continue an Adventure, fight 2-3 ordinary enemies. They should play as before; big enemies (25+ life) should make fewer obviously bad plays.
2. **A Boss (fight copy).** Copy `docs\gates\gate-b-fight.cmd` into the fight copy, next to `ForgeCampaign.exe`, and double-click it. Type `Jace` and press Enter. The Adventure opens straight into a duel with Jace. You play with a weak starter deck at starting life, so you will likely lose: what matters is how Jace plays and how long his turns take.
3. Repeat step 2 with `Sliver Queen` if you have time.

## Report

Reply on the pull request with:

- **Pass or fail**: no crashes, and Boss turns were not annoyingly slow (most under 10 seconds; an occasional long one can happen).
- Did the Boss feel smarter than a normal enemy? (Any example of a clever or a dumb play helps.)
- If something failed: attach `ForgeCampaign\data\neo\adventure.log` from that copy.

Merging the pull request is your sign-off that Gate B passed.
