# Gate D test: the whole campaign

**What this gate proves:** the campaign can be played from the first step to the final boss: five regions opening one after another, the main story leading through them, and the finale.

## What changed (Phase 3)

| Part | What you will see |
| --- | --- |
| Five regions | The Crossroads (hub), the Plains of Serra (white), the Azure Reach (blue), the Wildwood (green), the Cinder Peaks (red) and Duskmire (black). Each has a capital, three towns, a watchtower, dungeons, caves, a side boss and its colour castle |
| Roads that open as you win | The Plains open with the writ (as before). Beating **White Castle** opens the roads to the Azure Reach (east) and the Wildwood (west). The **Green Castle** opens the Cinder Peaks (south); the **Blue Castle** opens Duskmire (south-east). Barred roads have a sign saying which castle opens them |
| The finale | **Emrakul** appears in the Crossroads once all five colour castles have fallen |
| The main story | Shandalar's story quests now lead through these regions (its locations are placed where the roads allow: the Shard Mines in the Plains, the Library in the Azure Reach...) |
| Each region's cards | Merchants and rewards: Crossroads Magic 2010, Plains Dominaria, Azure Reach Kaladesh, Wildwood Ixalan, Cinder Peaks Dragons of Tarkir, Duskmire Innistrad |
| Rising difficulty | Each region now roams enemies picked by measured strength (from a benchmark of all 424 enemies), so the Crossroads and the Plains are gentle and later regions are tougher; before, every region was about the same. Enemies in the Azure Reach and the Wildwood also start with +2 life; in the Cinder Peaks and Duskmire +4, and they play at least as Elites |
| Castle bosses | Their life is tuned so the castles rise in difficulty instead of starting with a wall: Akroma used to win every test game at 40 life and now has 16; Emrakul goes from 100 to 30 |
| Checked automatically | Every place in the campaign (79 of 79) loads in the game, and every town has its merchant |
| Rising deck size | Minimum 40 cards, 50 after your first castle, 60 after your third (a smaller deck is padded with blank cards in duels). Still +2 starting life per full 10 cards above the minimum, up to +4 |

## Get the build

Extract `_build\out\ForgeCampaign-windows-x64.zip` **over your existing folder** (keep your `data` folder) and **start a new game** in a new slot: the world layout changed.

## Test

This is a long one; it can be spread over several sessions.

1. Play from a new game: Crossroads, the writ, the Plains, White Castle.
2. Check that the east and west roads opened, and carry on: Azure Reach and Wildwood, their castles, then the Cinder Peaks and Duskmire.
3. After the fifth castle, find Emrakul in the Crossroads.

For spot checks without playing everything: **F9** opens Adventure's console; `teleport to poi Emberhold` (or any town or castle name) jumps there, gates or not.

## Report

Tell me in chat:

- **Did you reach and beat the finale?** If not, where did it stop: a road that did not open, a quest pointing somewhere odd, a fight that was a wall?
- Did the order of regions and the difficulty curve feel right?
- Merchants and rewards in the later regions: still worth it?
- Anything broken: `ForgeCampaign\data\neo\adventure.log`.

When you are happy, merge `claude/phase-2-region-slice` first (if not yet), then `claude/phase-3-regions`, into `main` in GitHub Desktop: that is your sign-off.
