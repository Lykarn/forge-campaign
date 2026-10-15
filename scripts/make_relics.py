"""Relics and legendary rewards: one source for each relic's card, item and catalogue entry.

A relic is an Adventure item that puts one of our custom cards in the command zone at the start of
every duel (Adventure's own mechanism: Death Ring, Chandra's Tome...). Two equipment slots, added
by plane/ui/inventory*.json:
  Relic    castle relics: a pick of three after each colour castle (marker "Choice: Castle Relic")
  Trinket  champion relics: a pick of three after a champion (marker "Choice: Relic")
Relics are never sold; forge.campaign.relics.LegendaryChoice draws the picks from the relics the
player does not own yet, one of the three in the colours of the player's deck.

Also here: the custom cards of our enemies (boss phases, champions' presences), and the marker
items. Writes, all committed:
  res/adventure/common/custom_cards/campaign_*.txt   the cards (res/ only adds files to Forge's)
  plane/world/relics.json                            the catalogue LegendaryChoice reads
  plane/world/items.patch.json                       the items (its other entries are kept)
  plane/world/enemy_effects.json, enemies.patch.json enemy effects, boss rewards and tuned life
                                                     (plane/world/boss_tuning.json, by scripts/boss_tune.py)

Every card says AI:RemoveDeck:All, and Adventure's reward pools skip custom cards, so none of them
can turn up in a shop, a random deck or loot. A name that is already a Magic card is an error.

Usage: python scripts/make_relics.py   (after scripts/assemble.py: it checks names against Forge)
"""
from __future__ import annotations

import json
import re
import sys

from common import FORGE, ROOT

CARDS_OUT = ROOT / "res" / "adventure" / "common" / "custom_cards"
CATALOGUE = ROOT / "plane" / "world" / "relics.json"
ITEMS_PATCH = ROOT / "plane" / "world" / "items.patch.json"
EFFECTS_FILE = ROOT / "plane" / "world" / "enemy_effects.json"
TUNING = ROOT / "plane" / "world" / "boss_tuning.json"
ENEMIES_PATCH = ROOT / "plane" / "world" / "enemies.patch.json"
UPSTREAM_ENEMIES = FORGE / "forge-gui" / "res" / "adventure" / "common" / "world" / "enemies.json"
CARDSFOLDER = FORGE / "forge-gui" / "res" / "cardsfolder"
UPSTREAM_CUSTOM = FORGE / "forge-gui" / "res" / "adventure" / "common" / "custom_cards"

FIRST_UPKEEP = "Mode$ Phase | Phase$ Upkeep | ValidPlayer$ You | TriggerZones$ Command | CheckSVar$ Count$YourTurns | SVarCompare$ EQ1"
EACH_UPKEEP = "Mode$ Phase | Phase$ Upkeep | ValidPlayer$ You | TriggerZones$ Command"
SECOND_SPELL = "Mode$ SpellCast | ValidCard$ Card.YouCtrl | ValidActivatingPlayer$ You | TriggerZones$ Command | ActivatorThisTurnCast$ EQ2"
PLANESWALKERS = ("Ajani Goldmane,Jace Beleren,Liliana Vess,Chandra Nalaar,Garruk Wildspeaker,Nissa Revane,"
                 "Elspeth; Knight-Errant,Tezzeret the Seeker,Sorin Markov,Gideon Jura")


def wish(cost: str) -> list[str]:
    return [f"A:AB$ ChangeZone | Cost$ {cost} | ActivationZone$ Command | SorcerySpeed$ True | Origin$ Sideboard | "
            "Destination$ Hand | ChangeType$ Card.YouOwn | ChangeTypeDesc$ card you own | ChangeNum$ 1 | Hidden$ True | "
            "Reveal$ True | SubAbility$ DBExileSelf | SpellDescription$ Put a card you own from your sideboard into your "
            "hand, then exile CARDNAME. Activate only as a sorcery.",
            "SVar:DBExileSelf:DB$ ChangeZone | Origin$ Command | Destination$ Exile | Defined$ Self"]


# name, slot (Relic = castle tier, Trinket = champion tier), colours ("" = any deck), icon, card type,
# script lines (Oracle text is taken from their descriptions), extra item effect fields.
RELICS = [
    # ---- Castle relics (Relic slot) ----
    ("Oathstone of the Walkers", "Relic", "", "Star", "Artifact", [
        f"T:{FIRST_UPKEEP} | Execute$ TrigConjure | TriggerDescription$ At the beginning of your first upkeep, conjure a random planeswalker card from the Oathstone's spellbook onto the battlefield.",
        f"SVar:TrigConjure:DB$ MakeCard | Conjure$ True | Zone$ Battlefield | AtRandom$ True | Spellbook$ {PLANESWALKERS}",
    ], {}),
    ("Crown of the Five Castles", "Relic", "", "MulticolorRune", "Artifact", [
        "A:AB$ Mana | Cost$ 0 | Produced$ Any | ActivationZone$ Command | ActivationLimit$ 1 | SpellDescription$ Add one mana of any color. Activate only once each turn.",
    ], {}),
    ("Bell of Wishes", "Relic", "", "RingofThreeWishes", "Artifact", wish("3"), {}),
    ("Whetstone of Ages", "Relic", "", "SteelSword", "Artifact", [
        "T:Mode$ DamageDone | ValidSource$ Creature.YouCtrl | ValidTarget$ Opponent | CombatDamage$ True | TriggerZones$ Command | Execute$ TrigPump | TriggerDescription$ Whenever a creature you control deals combat damage to an opponent, it perpetually gets +1/+0.",
        "SVar:TrigPump:DB$ Pump | Defined$ TriggeredSource | NumAtt$ +1 | Duration$ Perpetual",
    ], {}),
    ("Standard of the Vanguard", "Relic", "W", "CartoucheOfSolidarity", "Artifact", [
        "T:Mode$ SpellCast | ValidCard$ Creature | ValidActivatingPlayer$ You | TriggerZones$ Command | Execute$ TrigPump | TriggerDescription$ Whenever you cast a creature spell, that spell perpetually gets +1/+0 and gains vigilance.",
        "SVar:TrigPump:DB$ Pump | PumpZone$ Stack | Defined$ TriggeredCard | NumAtt$ +1 | KW$ Vigilance | Duration$ Perpetual",
    ], {}),
    ("Chalice of Dawn", "Relic", "W", "SunMagusStaff", "Artifact", [
        f"T:{EACH_UPKEEP} | Execute$ TrigGain | TriggerDescription$ At the beginning of your upkeep, you gain 1 life.",
        "SVar:TrigGain:DB$ GainLife | Defined$ You | LifeAmount$ 1",
        "T:Mode$ LifeGained | ValidPlayer$ You | TriggerZones$ Command | FirstTime$ True | Execute$ TrigCounter | TriggerDescription$ Whenever you gain life for the first time each turn, put a +1/+1 counter on target creature you control.",
        "SVar:TrigCounter:DB$ PutCounter | ValidTgts$ Creature.YouCtrl | TgtPrompt$ Select target creature you control | CounterType$ P1P1 | CounterNum$ 1",
    ], {}),
    ("Tidecaller's Codex", "Relic", "U", "CartoucheOfKnowledge", "Artifact", [
        f"T:{SECOND_SPELL} | Execute$ TrigDraw | TriggerDescription$ Whenever you cast your second spell each turn, draw a card.",
        "SVar:TrigDraw:DB$ Draw | Defined$ You | NumCards$ 1",
        "S:Mode$ Continuous | EffectZone$ Command | Affected$ You | SetMaxHandSize$ Unlimited | Description$ You have no maximum hand size.",
    ], {}),
    ("Astrolabe of First Light", "Relic", "U", "MindMagusStaff", "Artifact", [
        f"T:{FIRST_UPKEEP} | Execute$ TrigDraw | TriggerDescription$ At the beginning of your first upkeep, draw two cards.",
        "SVar:TrigDraw:DB$ Draw | Defined$ You | NumCards$ 2",
        f"T:{EACH_UPKEEP} | Execute$ TrigScry | TriggerDescription$ At the beginning of your upkeep, scry 1.",
        "SVar:TrigScry:DB$ Scry | ScryNum$ 1",
    ], {}),
    ("Phylactery of the Undying", "Relic", "B", "EvilAnkh", "Artifact", [
        "R:Event$ GameLoss | ActiveZones$ Command | ValidPlayer$ You | ReplaceWith$ ExileSetLife | Description$ If you would lose the game, instead exile CARDNAME and your life total becomes 7.",
        "SVar:ExileSetLife:DB$ ChangeZone | Origin$ Command | Destination$ Exile | Defined$ Self | SubAbility$ DBSetLife",
        "SVar:DBSetLife:DB$ SetLife | Defined$ You | LifeAmount$ 7",
    ], {}),
    ("Grimoire of the First Tutor", "Relic", "B", "BurningBook", "Artifact", [
        f"T:{FIRST_UPKEEP} | Execute$ TrigTutor | TriggerDescription$ At the beginning of your first upkeep, search your library for a card, put it into your hand, then shuffle. You lose 2 life.",
        "SVar:TrigTutor:DB$ ChangeZone | Origin$ Library | Destination$ Hand | ChangeType$ Card | ChangeNum$ 1 | Mandatory$ True | SubAbility$ DBLoseLife",
        "SVar:DBLoseLife:DB$ LoseLife | Defined$ You | LifeAmount$ 2",
    ], {}),
    ("Lantern of the Lich-Lord", "Relic", "B", "DeathMagusStaff", "Artifact", [
        "T:Mode$ ChangesZone | Origin$ Battlefield | Destination$ Graveyard | ValidCard$ Creature.YouCtrl | TriggerZones$ Command | Execute$ TrigDrain | TriggerDescription$ Whenever a creature you control dies, each opponent loses 1 life and you gain 1 life.",
        "SVar:TrigDrain:DB$ LoseLife | Defined$ Player.Opponent | LifeAmount$ 1 | SubAbility$ DBGain",
        "SVar:DBGain:DB$ GainLife | Defined$ You | LifeAmount$ 1",
    ], {}),
    ("Emberheart Brand", "Relic", "R", "FireMagusStaff", "Artifact", [
        "R:Event$ DamageDone | ActiveZones$ Command | ValidSource$ Card.YouCtrl,Emblem.YouCtrl | ValidTarget$ Permanent.OppCtrl,Opponent | IsCombat$ False | ReplaceWith$ DmgPlus | Description$ If a source you control would deal noncombat damage to an opponent or a permanent an opponent controls, it deals that much damage plus 1 instead.",
        "SVar:DmgPlus:DB$ ReplaceEffect | VarName$ DamageAmount | VarValue$ X",
        "SVar:X:ReplaceCount$DamageAmount/Plus.1",
    ], {}),
    ("Sigil of the Storm", "Relic", "R", "CartoucheOfZeal", "Artifact", [
        f"T:{SECOND_SPELL} | Execute$ TrigDmg | TriggerDescription$ Whenever you cast your second spell each turn, CARDNAME deals 2 damage to each opponent.",
        "SVar:TrigDmg:DB$ DealDamage | Defined$ Player.Opponent | NumDmg$ 2",
    ], {}),
    ("Heart of the Wildwood", "Relic", "G", "WildMagusStaff", "Artifact", [
        "K:ETBReplacement:Other:AddExtraCounter:Mandatory:Command:Creature.YouCtrl",
        "SVar:AddExtraCounter:DB$ PutCounter | ETB$ True | Defined$ ReplacedCard | CounterType$ P1P1 | CounterNum$ 1 | SpellDescription$ Creatures you control enter with an additional +1/+1 counter on them.",
    ], {}),
    ("Gaea's Hearthstone", "Relic", "G", "GreenLeaf", "Artifact", [
        "S:Mode$ Continuous | EffectZone$ Command | Affected$ You | AdjustLandPlays$ 1 | Description$ You may play an additional land on each of your turns.",
        "T:Mode$ ChangesZone | Destination$ Battlefield | ValidCard$ Land.YouCtrl | TriggerZones$ Command | Execute$ TrigGain | TriggerDescription$ Whenever a land you control enters, you gain 1 life.",
        "SVar:TrigGain:DB$ GainLife | Defined$ You | LifeAmount$ 1",
    ], {}),
    # ---- Champion relics (Trinket slot) ----
    ("Explorer's Charm", "Trinket", "", "TravelersAmulet", "Artifact", [
        "S:Mode$ Continuous | EffectZone$ Command | Affected$ You | AdjustLandPlays$ 1 | Description$ You may play an additional land on each of your turns.",
    ], {}),
    ("Scrying Lens", "Trinket", "", "Magnifier", "Artifact", [
        f"T:{EACH_UPKEEP} | Execute$ TrigScry | TriggerDescription$ At the beginning of your upkeep, scry 1.",
        "SVar:TrigScry:DB$ Scry | ScryNum$ 1",
    ], {}),
    ("Seeker's Map", "Trinket", "", "DungeonMap", "Artifact", [
        f"T:{FIRST_UPKEEP} | Execute$ TrigSeek | TriggerDescription$ At the beginning of your first upkeep, put a random land card from your library into your hand.",
        "SVar:TrigSeek:DB$ ChangeZone | Origin$ Library | Destination$ Hand | ChangeType$ Land.YouOwn | ChangeNum$ 1 | Hidden$ True | AtRandom$ True",
    ], {}),
    ("Tutor's Satchel", "Trinket", "", "ToolBox", "Artifact", [
        f"T:{FIRST_UPKEEP} | Execute$ TrigDig | TriggerDescription$ At the beginning of your first upkeep, look at the top four cards of your library. Put one of them into your hand and the rest on the bottom of your library in a random order.",
        "SVar:TrigDig:DB$ Dig | DigNum$ 4 | ChangeNum$ 1 | DestinationZone$ Hand | RestRandomOrder$ True",
    ], {}),
    ("Wishing Coin", "Trinket", "", "FortuneCoin", "Artifact", wish("5"), {}),
    ("Charm of the Gatewatch", "Trinket", "", "SpiritGuard", "Artifact", [
        f"T:{FIRST_UPKEEP} | Execute$ TrigConjure | TriggerDescription$ At the beginning of your first upkeep, conjure a random planeswalker card from the Oathstone's spellbook into your hand.",
        f"SVar:TrigConjure:DB$ MakeCard | Conjure$ True | Zone$ Hand | AtRandom$ True | Spellbook$ {PLANESWALKERS}",
    ], {}),
    ("Pilgrim's Flask", "Trinket", "W", "LifeAmulet", "Artifact", [
        f"T:{EACH_UPKEEP} | CheckSVar$ YourLife | SVarCompare$ LE10 | Execute$ TrigGain | TriggerDescription$ At the beginning of your upkeep, if you have 10 or less life, you gain 2 life.",
        "SVar:TrigGain:DB$ GainLife | Defined$ You | LifeAmount$ 2",
        "SVar:YourLife:Count$YourLifeTotal",
    ], {"lifeModifier": 2}),
    ("Militia Horn", "Trinket", "W", "BattleStandard", "Artifact", [
        "T:Mode$ Phase | Phase$ BeginCombat | ValidPlayer$ You | TriggerZones$ Command | IsPresent$ Creature.YouCtrl | PresentCompare$ EQ0 | Execute$ TrigToken | TriggerDescription$ At the beginning of combat on your turn, if you control no creatures, create a 1/1 white Soldier creature token.",
        "SVar:TrigToken:DB$ Token | TokenScript$ w_1_1_soldier | TokenOwner$ You",
    ], {}),
    ("Quill of Insight", "Trinket", "U", "Bookmark", "Artifact", [
        "T:Mode$ SpellCast | ValidCard$ Instant,Sorcery | ValidActivatingPlayer$ You | TriggerZones$ Command | Execute$ TrigScry | TriggerDescription$ Whenever you cast an instant or sorcery spell, scry 1.",
        "SVar:TrigScry:DB$ Scry | ScryNum$ 1",
    ], {}),
    ("Pearl of the Deep", "Trinket", "U", "BlueRune", "Artifact", [
        "T:Mode$ Phase | Phase$ End of Turn | ValidPlayer$ You | TriggerZones$ Command | CheckSVar$ X | SVarCompare$ EQ0 | Execute$ TrigDraw | TriggerDescription$ At the beginning of your end step, if you have no cards in hand, draw a card.",
        "SVar:TrigDraw:DB$ Draw | Defined$ You | NumCards$ 1",
        "SVar:X:Count$InYourHand",
    ], {}),
    ("Gravecaller's Coin", "Trinket", "B", "BlackRune", "Artifact", [
        "T:Mode$ ChangesZone | Origin$ Battlefield | Destination$ Graveyard | ValidCard$ Creature.nonToken+YouCtrl | TriggerZones$ Command | Execute$ TrigDrain | TriggerDescription$ Whenever a nontoken creature you control dies, each opponent loses 1 life.",
        "SVar:TrigDrain:DB$ LoseLife | Defined$ Player.Opponent | LifeAmount$ 1",
    ], {}),
    ("Vial of Ichor", "Trinket", "B", "Blood", "Artifact", [
        "T:Mode$ ChangesZone | Origin$ Battlefield | Destination$ Graveyard | ValidCard$ Creature.OppCtrl | TriggerZones$ Command | Execute$ TrigGain | TriggerDescription$ Whenever a creature an opponent controls dies, you gain 1 life.",
        "SVar:TrigGain:DB$ GainLife | Defined$ You | LifeAmount$ 1",
    ], {}),
    ("Kindling Charm", "Trinket", "R", "RedRune", "Artifact", [
        "T:Mode$ SpellCast | ValidCard$ Instant,Sorcery | ValidActivatingPlayer$ You | TriggerZones$ Command | ActivationLimit$ 1 | Execute$ TrigDmg | TriggerDescription$ Whenever you cast an instant or sorcery spell, CARDNAME deals 1 damage to each opponent. This ability triggers only once each turn.",
        "SVar:TrigDmg:DB$ DealDamage | Defined$ Player.Opponent | NumDmg$ 1",
    ], {}),
    ("Spark of the Forge", "Trinket", "R", "RedStaff", "Artifact", [
        "T:Mode$ Phase | Phase$ BeginCombat | ValidPlayer$ You | TriggerZones$ Command | IsPresent$ Creature.YouCtrl | Execute$ TrigPump | TriggerDescription$ At the beginning of combat on your turn, target creature you control gets +1/+0 until end of turn.",
        "SVar:TrigPump:DB$ Pump | ValidTgts$ Creature.YouCtrl | TgtPrompt$ Select target creature you control | NumAtt$ +1",
    ], {}),
    ("Hunter's Fang", "Trinket", "G", "Dagger", "Artifact", [
        "S:Mode$ Continuous | EffectZone$ Command | Affected$ Creature.YouCtrl+powerGE4 | AddKeyword$ Trample | Description$ Creatures you control with power 4 or greater have trample.",
    ], {}),
    ("Whistle of the Pack", "Trinket", "G", "GreenRune", "Artifact", [
        f"T:{FIRST_UPKEEP} | Execute$ TrigToken | TriggerDescription$ At the beginning of your first upkeep, create a 2/2 green Wolf creature token.",
        "SVar:TrigToken:DB$ Token | TokenScript$ g_2_2_wolf | TokenOwner$ You",
    ], {}),
]

# Planar relics: one per Planar Rift, the reward for beating its boss (forge.campaign.rift.RiftRun).
# Relic slot, tier "planar": never offered by a choice.
PLANAR_RELICS = [
    ("Heart of the Shards", "Relic", "", "MulticolorRune", "Artifact", [
        "S:Mode$ ReduceCost | ValidCard$ Card.MultiColor | EffectZone$ Command | Type$ Spell | Activator$ You | Amount$ 1 | Description$ Multicolored spells you cast cost {1} less.",
        "T:Mode$ SpellCast | ValidCard$ Card.MultiColor | ValidActivatingPlayer$ You | TriggerZones$ Command | Execute$ TrigScry | TriggerDescription$ Whenever you cast a multicolored spell, scry 1.",
        "SVar:TrigScry:DB$ Scry | ScryNum$ 1",
    ], {}),
    ("Lantern of the Kami", "Relic", "", "ZedruuLantern", "Artifact", [
        "S:Mode$ ReduceCost | ValidCard$ Card.Legendary | EffectZone$ Command | Type$ Spell | Activator$ You | Amount$ 1 | Description$ Legendary spells you cast cost {1} less.",
        f"T:{SECOND_SPELL} | Execute$ TrigToken | TriggerDescription$ Whenever you cast your second spell each turn, create a 1/1 colorless Spirit creature token.",
        "SVar:TrigToken:DB$ Token | TokenScript$ c_1_1_spirit | TokenOwner$ You",
    ], {}),
    ("Ichor of the Mother", "Relic", "", "Blood", "Artifact", [
        "S:Mode$ Continuous | EffectZone$ Command | Affected$ Creature.YouCtrl | AddKeyword$ Toxic:1 | Description$ Creatures you control have toxic 1.",
        "T:Mode$ Phase | Phase$ End of Turn | ValidPlayer$ You | TriggerZones$ Command | Execute$ TrigProliferate | TriggerDescription$ At the beginning of your end step, proliferate.",
        "SVar:TrigProliferate:DB$ Proliferate",
    ], {}),
]

# Our enemies' custom cards: (name, card type, script lines). Given to enemies by
# plane/world/enemy_effects.json.
ENEMY_CARDS = [
    ("Emrakul's Ascension", "Artifact", [
        "R:Event$ GameLoss | ActiveZones$ Command | ValidPlayer$ You | ReplaceWith$ Ascend | Description$ If Emrakul would lose the game, instead exile CARDNAME and her life total becomes 8.",
        "SVar:Ascend:DB$ ChangeZone | Origin$ Command | Destination$ Exile | Defined$ Self | SubAbility$ DBSetLife",
        "SVar:DBSetLife:DB$ SetLife | Defined$ You | LifeAmount$ 8",
        "S:Mode$ Continuous | EffectZone$ Command | Affected$ Eldrazi.YouCtrl | AddKeyword$ Annihilator:1 | Description$ Eldrazi you control have annihilator 1.",
    ]),
    ("The Alpha's Hoard", "Artifact", [
        f"T:{EACH_UPKEEP} | Execute$ TrigScry | TriggerDescription$ At the beginning of your upkeep, scry 1.",
        "SVar:TrigScry:DB$ Scry | ScryNum$ 1",
    ]),
]

MOXEN = ["Mox Pearl", "Mox Sapphire", "Mox Jet", "Mox Ruby", "Mox Emerald"]

# What each special enemy brings to every duel (plane/world/enemy_effects.json, read by
# forge.campaign.enemies.EnemyEffects): planeswalker bosses start with their planeswalker in play.
ENEMY_EFFECTS = {
    "Nahiri": {"effect": {"startBattleWithCard": ["Nahiri, the Harbinger"]}},
    "Jace": {"effect": {"startBattleWithCard": ["Jace Beleren"]}},
    "Garruk": {"effect": {"startBattleWithCard": ["Garruk Wildspeaker"]}},
    "Tibalt": {"effect": {"startBattleWithCard": ["Tibalt, the Fiend-Blooded"]}},
    "Teferi": {"effect": {"startBattleWithCard": ["Teferi, Temporal Archmage"]}},
    "Kiora": {"effect": {"startBattleWithCard": ["Kiora, the Crashing Wave"]}},
    "Sorin": {"effect": {"startBattleWithCard": ["Sorin, Vengeful Bloodlord"]}},
    "Liliana": {"effect": {"startBattleWithCard": ["Liliana of the Veil"]}},
    "Emrakul": {"effect": {"startBattleWithCardInCommandZone": ["Emrakul's Ascension"]}},
    "Oracle of the Alpha": {"effect": {"startBattleWithCard": MOXEN,
                                       "startBattleWithCardInCommandZone": ["The Alpha's Hoard"]},
                            "takesPower9": True},
}

# Legendary choices added to bosses' loot (LegendaryChoice markers).
CASTLE, RELIC, POWER = "Choice: Castle Relic", "Choice: Relic", "Choice: Power 9"
REWARD_MARKERS = {
    # colour castles: a castle relic each
    "Akroma": [CASTLE], "Lorthos": [CASTLE], "Ghalta": [CASTLE], "Lathliss": [CASTLE], "Griselbrand": [CASTLE],
    # each colour region's side boss: one of the Power 9
    "Nahiri": [POWER], "Jace": [POWER], "Garruk": [POWER], "Tibalt": [POWER], "Grolnok": [POWER],
    # champions (upstream boss dungeons our layout now places): a relic; the hard ones a castle relic
    "Teferi": [RELIC], "Kiora": [RELIC], "Slimefoot": [RELIC], "Slobad": [RELIC], "Zedruu": [RELIC],
    "Xira": [RELIC], "Liliana": [RELIC], "Scarecrow Captain": [RELIC],
    "The Hydra of Shandalaar": [CASTLE], "Sorin": [CASTLE], "Sliver Queen": [CASTLE],
    "Oracle of the Alpha": [POWER, POWER, CASTLE],
    "Emrakul": [POWER],
}

RIFT_BOSSES = [
    ("Hegemon of Esper", "sprites/enemy/humanoid/human/artificer/esper_artificer.atlas", "decks/standard/esper_artificer.dck", "WUB", "Heart of the Shards"),
    ("The Myojin of Night", "sprites/enemy/celestial/seraphim.atlas", "decks/standard/seraphim.dck", "WB", "Lantern of the Kami"),
    ("Grand Cenobite", "sprites/enemy/aberration/phyrexian/copperhostbrutalizer.atlas", "decks/miniboss/copperhostbrutalizer.dck", "BG", "Ichor of the Mother"),
]

NEW_ENEMIES = [{
    "name": "Oracle of the Alpha",
    "sprite": "sprites/enemy/humanoid/human/wizard/archmage.atlas",
    "deck": ["decks/boss/oracle_of_the_alpha.dck"],
    "ai": "", "boss": True, "flying": False, "speed": 1, "scale": 1.5, "life": 14,
    "rewards": [{"type": "gold", "probability": 1, "count": 3000, "addMaxCount": 1000},
                {"type": "shards", "probability": 1, "count": 30, "addMaxCount": 20}],
    "colors": "UR", "questTags": ["Boss", "Wizard", "Humanoid", "IdentityBlue", "IdentityRed"],
    "gamesPerMatch": 3,
    "bossIntro": "Before your kind had names, I held the first power. Show me yours, and it is mine.",
    "bossInsult": "The Alpha remembers what you have forgotten.",
}]

for _name, _sprite, _deck, _colours, _relic in RIFT_BOSSES:
    # Their decks are dealt by the rift (sealed, more packs); the deck here is only a fallback.
    NEW_ENEMIES.append({
        "name": _name, "sprite": _sprite, "deck": [_deck], "ai": "", "boss": False, "flying": False,
        "speed": 1, "scale": 1.5, "life": 25,
        "rewards": [{"type": "item", "probability": 1, "count": 1, "itemNames": [_relic]},
                    {"type": "gold", "probability": 1, "count": 1500, "addMaxCount": 500}],
        "colors": _colours, "questTags": ["Rift", "Boss"],
    })
    ENEMY_EFFECTS[_name] = {"effect": {"changeStartCards": 1}}

MARKERS = [
    {"name": "Choice: Relic", "iconName": "TreasureChest",
     "description": "Choose one of three relics for your Trinket slot."},
    {"name": "Choice: Castle Relic", "iconName": "Star",
     "description": "Choose one of three castle relics for your Relic slot."},
    {"name": "Choice: Power 9", "iconName": "BlackLotus",
     "description": "Choose one of the Power 9 you do not own yet."},
]


def marker_reward(marker: str) -> dict:
    return {"type": "item", "probability": 1, "count": 1, "itemNames": [marker]}


def is_marker(reward: dict) -> bool:
    return any(n.startswith("Choice: ") for n in reward.get("itemNames", []) + [reward.get("itemName") or ""])


def slug(name: str) -> str:
    return "campaign_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def oracle(lines: list[str]) -> str:
    texts = []
    for line in lines:
        m = re.search(r"(?:TriggerDescription|SpellDescription|Description)\$ (.*?)(?: \| |$)", line)
        # Abilities carry their own text; an SVar only when it is an ETB replacement's (K:ETBReplacement).
        if m and (not line.startswith("SVar:") or "ETB$ True" in line):
            texts.append(m.group(1))
    return "\\n".join(texts)


def card_text(name: str, ctype: str, lines: list[str], colours: str = "") -> str:
    out = [f"Name:{name}", "ManaCost:no cost"]
    names = {"W": "white", "U": "blue", "B": "black", "R": "red", "G": "green"}
    if len(colours) == 1:
        out.append(f"Colors:{names[colours]}")
    out += [f"Types:{ctype}"] + lines + ["AI:RemoveDeck:All", f"Oracle:{oracle(lines)}"]
    return "\n".join(out) + "\n"


def forge_names() -> set[str]:
    names = set()
    for f in CARDSFOLDER.rglob("*.txt"):
        with f.open(encoding="utf-8", errors="replace") as fh:
            first = fh.readline()
        if first.startswith("Name:"):
            names.add(first[5:].strip())
    for f in UPSTREAM_CUSTOM.glob("*.txt"):
        names.add(f.read_text(encoding="utf-8").splitlines()[0][5:].strip())
    return names


def main() -> int:
    taken = forge_names()
    clash = [n for n, *_ in RELICS + PLANAR_RELICS + ENEMY_CARDS if n in taken]
    if clash:
        sys.exit(f"these names are already Magic or Adventure cards: {clash}")
    CARDS_OUT.mkdir(parents=True, exist_ok=True)
    for old in CARDS_OUT.glob("campaign_*.txt"):
        old.unlink()
    catalogue = {"_about": "Written by scripts/make_relics.py; read by forge.campaign.relics.Relics."}
    items = []
    for name, slot, colours, icon, ctype, lines, extra in RELICS + PLANAR_RELICS:
        (CARDS_OUT / f"{slug(name)}.txt").write_text(card_text(name, ctype, lines, colours), encoding="utf-8", newline="\n")
        tier = "planar" if (name, slot) in {(r[0], r[1]) for r in PLANAR_RELICS} else "castle" if slot == "Relic" else "champion"
        catalogue[name] = {"tier": tier, "colors": colours, "card": name}
        text = oracle(lines).replace("\\n", " ").replace("CARDNAME", name)
        effect = {"startBattleWithCardInCommandZone": [name]}
        effect.update(extra)
        items.append({"name": name, "equipmentSlot": slot, "iconName": icon,
                      "cost": 12000 if tier == "castle" else 6000,
                      "description": {"castle": "Castle relic. ", "planar": "Planar relic. "}.get(tier, "Relic. ") + text,
                      "effect": effect})
    for name, ctype, lines in ENEMY_CARDS:
        (CARDS_OUT / f"{slug(name)}.txt").write_text(card_text(name, ctype, lines), encoding="utf-8", newline="\n")
    CATALOGUE.write_text(json.dumps(catalogue, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    patch = json.loads(ITEMS_PATCH.read_text(encoding="utf-8"))
    ours = {i["name"] for i in items} | {m["name"] for m in MARKERS}
    patch["add"] = [e for e in patch.get("add", []) if e["name"] not in ours] + MARKERS + items
    ITEMS_PATCH.write_text(json.dumps(patch, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    # Boss tuning (scripts/boss_tune.py): life into the enemies patch, a smaller hand into the effects.
    tuning = {k: v for k, v in json.loads(TUNING.read_text(encoding="utf-8")).items() if not k.startswith("_")}         if TUNING.is_file() else {}
    effects = {"_about": "Written by scripts/make_relics.py; read by forge.campaign.enemies.EnemyEffects "
                         "(each enemy's effect in every map duel)."}
    effects.update(json.loads(json.dumps(ENEMY_EFFECTS)))
    for name, tune in tuning.items():
        if tune.get("hand"):
            fx = effects.setdefault(name, {"effect": {}})["effect"]
            fx["changeStartCards"] = fx.get("changeStartCards", 0) + tune["hand"]
    EFFECTS_FILE.write_text(json.dumps(effects, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    upstream = {e["name"]: e for e in json.loads(UPSTREAM_ENEMIES.read_text(encoding="utf-8"))}
    new = {e["name"]: e for e in NEW_ENEMIES}
    enemies = json.loads(ENEMIES_PATCH.read_text(encoding="utf-8"))
    enemies["add"] = [e for e in enemies.get("add", []) if e["name"] not in new]
    for name, enemy in new.items():
        enemy = dict(enemy, rewards=enemy["rewards"] + [marker_reward(m) for m in REWARD_MARKERS.get(name, [])])
        if name in tuning:
            enemy["life"] = tuning[name]["life"]
        enemies["add"].append(enemy)
    modify = enemies.setdefault("modify", {})
    for name, markers in REWARD_MARKERS.items():
        if name in new:
            continue
        if name not in upstream:
            sys.exit(f"REWARD_MARKERS: no enemy {name!r} in Adventure's enemies.json")
        base = [r for r in upstream[name].get("rewards", []) if not is_marker(r)]
        modify.setdefault(name, {})["rewards"] = base + [marker_reward(m) for m in markers]
    for name, tune in tuning.items():
        if name not in new:
            if name not in upstream:
                sys.exit(f"boss_tuning.json: no enemy {name!r}")
            modify.setdefault(name, {})["life"] = tune["life"]
    ENEMIES_PATCH.write_text(json.dumps(enemies, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    castle = sum(1 for r in RELICS if r[1] == "Relic")
    print(f"{len(RELICS)} relics ({castle} castle, {len(RELICS) - castle} champion), {len(ENEMY_CARDS)} enemy cards, "
          f"{len(MARKERS)} choice markers, {len(ENEMY_EFFECTS)} enemy effects, {len(REWARD_MARKERS)} bosses with choices")
    return 0


if __name__ == "__main__":
    sys.exit(main())
