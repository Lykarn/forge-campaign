# Gate C test: one full region

**What this gate proves:** the three fixes work together in one region you can play from start to finish. The world has a shape, the merchants sell cards worth buying, and you want the next region.

This is a playtest, not a checklist: play it as a player would and tell me what you think.

## What changed

| Part | What you will see |
| --- | --- |
| A fixed, authored world | The same map in every new game. You start in **The Crossroads** (the grey centre). Water separates the regions; roads cross it only at passes |
| A gate | The road north to the **Plains of Serra** is barred. The writ that opens it is in the **Old Watch Fort**, in the Crossroads |
| Closed roads | Signs at the roads to the other colours: those lands open in a later update |
| Fog of war | On the minimap and the map screen, only the Crossroads shows at first. The **Serra Watchtower** reveals the Plains |
| Fewer, named towns | Three towns in the Crossroads, four in the Plains (one is the capital, **Serra's Rest**). Each has one merchant; the other shop buildings are scenery |
| Curated merchants | 6 offers (8 in the capital): 3 for your deck, 2 region specials, 1 off-colour wildcard. Under each price, a line says what it does for your deck: "Swap: X" (it beats X, your weakest card in that role), "Adds card draw", "Off-colour" or "Region pick". The Crossroads sells Magic 2010; the Plains sell Dominaria |
| Pick 1 of 3 | After a won duel on the map, gold and shards are paid as usual, and you choose one of three cards: the two best from the enemy's loot and one from the region. Chests are unchanged |
| Bigger decks pay | Each full 10 cards above 40 gives +2 starting life in duels (at most +4) |
| The finale | **White Castle**, at the north of the Plains, is open from the start of the slice |

Plus the Phase 1 enemy tiers (Grunts, Elites, Bosses). A Boss may think for a few seconds per turn.

## Get the build

Unzip `_build\out\ForgeCampaign-windows-x64.zip` somewhere outside Program Files. **Start a new game**: saves from before this build keep their old random world.

## Test (as long as you like; the whole slice is roughly 1-3 hours)

1. New game, Normal difficulty, any starter deck.
2. Explore the Crossroads, visit its towns and merchants, find the Old Watch Fort and take the writ to the north gate.
3. In the Plains, find the watchtower, visit the towns, and beat White Castle if you can.

## Report

Tell me in chat:

- **Did you finish the region?** If not, where did you stop and why?
- **Do you want the next region?** (This is the gate: "testers finish the region and want more".)
- **Merchants:** were the offers worth buying? Were the "Swap: ..." lines right?
- **Pick 1 of 3:** better or worse than the old card piles?
- **The world:** was it clear where to go? Did the gate, the closed roads and the fog make sense?
- Anything broken, slow or confusing. If something failed: `ForgeCampaign\data\neo\adventure.log`.

When you are happy, merge `claude/phase-2-region-slice` into `main` in GitHub Desktop: that is your sign-off.
