# Working on this project

## Ask which one, when a name has more than one thing behind it

Several names in this game belong to more than one thing: the same character or object appears
in a different act, in Sanctuary, or as part of a different system. If a request names one of
these and does not say which, **ask before changing anything**. Changing the wrong one breaks a
working part of the game for the sake of a different part.

Known ones, and where each lives:

| name | the one | the other |
| --- | --- | --- |
| Tyrael | Act 4 (Pandemonium Fortress) and Act 5 (Harrogath), his own quest lines | Sanctuary's Tyrael, the healer, `game/world.py HEALERS` |
| Tree of Inifuss | Act 1's quest object, `game/act1.py QUEST_OBJECTS` / `game/quests.py` | Sanctuary's bounty board, `game/act6.py TREE_OID` |
| Izual | Act 4's quest, killed in the Plains of Despair | Sanctuary's Izual, a vendor |
| Hadriel (malachai) | the act 5 NPC | Sanctuary's gambler |
| Arreat Summit | Act 5's real summit, where the Ancients are fought | Sanctuary, the Act 6 town, `assets/maps/sanctuary.json` |
| the red portals | the waypoint portal, the bounty portals, and the four pedestals | all three are in Sanctuary and all three are different code |
| Essences | the three account currencies, `game/essences.py` | D2's own Pandemonium essences, which share their art |
| the rift | Act 1's old rift entrance | the Infernal Rift behind Sanctuary's second pedestal |

The same goes for anything else that turns out to have a twin: ask rather than guess.

## The rest of the standing rules

- Windows 7, Python 3.8, pygame 2.6.1, GOG D2 1.14d. Verify every change with
  `/tmp/v38/bin/python -m compileall -q game render d2 main.py` - no 3.9+ syntax.
- No Blizzard files are ever committed. Art, sound, text and tables are read at runtime from the
  player's own MPQs. Hand-made maps in `assets/maps/*.json` are fine: they hold tile indices and
  preset references, not art.
- Push after each feature.
- TEST ONLY options stay until asked for otherwise.
- Write-ups are plain and factual: ordinary language, no flavour text.
