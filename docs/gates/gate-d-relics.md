# Gate D+ test: relics, legendary rewards and special enemies

**What this adds:** rewards worth hunting (relics, the Power 9) and enemies worth fearing (champions, planeswalker bosses, the Oracle of the Alpha, a much harder Emrakul). It sits on top of Gate D (branch `claude/phase-3-regions`), so test both together.

## What changed

| Part | What you will see |
| --- | --- |
| Relic slots that grow | In the inventory, a **Relic** slot (bottom left) and a **Trinket** slot (bottom right). After your second castle a second Relic and a second Trinket slot appear, and after your fourth a third Relic slot: up to five relics working together by the finale. Relics are never sold: you earn them |
| 15 castle relics (Relic slot) | After each colour castle, choose 1 of 3. Examples: *Oathstone of the Walkers* (start with a random planeswalker in play), *Crown of the Five Castles* (one free mana of any colour each turn), *Phylactery of the Undying* (the first time you would lose, you go to 7 life instead), *Emberheart Brand* (+1 to all your non-combat damage), *Bell of Wishes* (once per game, {3}: fetch any card from your sideboard), *Grimoire of the First Tutor*, *Heart of the Wildwood*, *Standard of the Vanguard* (your creature spells perpetually get +1/+0 and vigilance), *Whetstone of Ages* |
| 16 champion relics (Trinket slot) | After each champion, choose 1 of 3: smaller effects such as an extra land each turn, scry each upkeep, a free 2/2 Wolf, +1 damage on your first spell, a once-per-game wish for {5} |
| One of three is for your deck | Each relic choice offers at least one relic in your deck's colours when there is one |
| The Power 9 | Each region's side boss (Nahiri, Jace, Garruk, Tibalt, Grolnok) lets you choose 1 of the Power 9 you don't own yet: up to 5 by the finale. They are fully playable, and never appear in shops or random loot |
| Champions | 11 boss dungeons from Shandalar now stand in the regions: Scarecrow Farm (Crossroads), Teferi's Hideout (Plains), Kiora's Island (Azure Reach), Slimefoot's Lair and the Lake of the Hydra (Wildwood), Slobad's Factory, Zedruu City and the Skep (Cinder Peaks), Xira's Hive, Sorin's Keep and the Temple of Liliana (Duskmire). Each has its own boss effect; each pays a relic choice (the Hydra, Sorin and the Sliver Queen a castle relic) |
| Planeswalker bosses | Nahiri, Jace, Garruk, Tibalt, Teferi, Kiora, Sorin and Liliana start the duel with one of their planeswalkers already in play |
| The Oracle of the Alpha | A secret boss in the Crossroads (the **Alpha Sanctum**) that appears after your third castle. He starts with all five Moxen in play and plays Black Lotus, Ancestral Recall, Time Walk and Timetwister. **He takes your Power 9 for the match**: they play in his deck and yours gets Wastes instead (you keep them afterwards). He won 81% of test games. Beat him for two Power 9 choices and a castle relic |
| Emrakul, much harder | The finale now has a second phase: the first time Emrakul would lose, she comes back at 8 life. Until then her Eldrazi have an extra annihilator 1, and her map still ramps her a land every turn. In testing she won 88% of single games against my reference decks (a good midrange deck never beat her; an aggro deck won 1 in 4), and it is best of three: you will need a very strong deck, relics and Power 9. Beating her gives a Power 9 choice |

## Get the build

Extract `_build\out\ForgeCampaign-windows-x64.zip` over your existing folder (keep your `data` folder) and **start a new game**: the world gained new places.

## Test

Spot checks are fastest with the console: **F9**, then `teleport to poi <name>` (names: `Teferi Hideout`, `Kiora Island`, `Slimefoots Lair`, `Grove7`, `Slobads Factory`, `Zedruu City`, `Skep`, `Xiras Hive`, `VampireCastle3`, `Temple of Liliana`, `Scarecrow Farm`, `Alpha Sanctum`, `Nahiri Encampment`, `Jacehold`, `Garruk Forest`, `Tibalts Fortress`, `Grolnoks Bog`).

1. Beat a champion: after the loot, a "pick 1" screen offers three relics. Equip one in the Trinket slot and check it shows in your command zone in the next duel.
2. Beat a castle: the same with castle relics for the Relic slot.
3. Beat a side boss: the pick shows the Power 9 you don't own. Put one in your deck.
4. After three castles, find the Alpha Sanctum and duel the Oracle with a Power 9 card in your deck: it should be in his deck, not yours, and back in yours after.
5. Emrakul: does phase two happen, and does she feel like a final boss?

## Report

Tell me in chat:

- Which relics felt too strong, too weak, or did nothing?
- Were the champions and planeswalker bosses fair for their rewards?
- The Oracle and Emrakul: hard but beatable, or walls?
- Anything broken: `ForgeCampaign\data\neo\adventure.log`.

When you are happy: merge `claude/phase-2-region-slice`, then `claude/phase-3-regions`, then `claude/relics-and-bosses` into `main` in GitHub Desktop.
