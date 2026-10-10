# Engine migration plan

Ultimate Tanks is moving from Python/pygame to a game engine in three stages, as a learning exercise:

1. **Godot with GDScript**: rebuild the game in real 3D.
2. **Godot with C#**: convert the scripts, and pull the game rules into engine-independent C#.
3. **Unity**: rebuild the engine-facing half around that same C# code.

Each stage ends with a complete, playable game on Windows and macOS. The Python version stays in the repo
untouched as the reference for how everything should behave.

## Summary

| Stage | Sessions | Calendar time |
|---|---|---|
| 1. Godot (GDScript) | 28–42 | 6–9 weeks |
| 2. Godot (C#) | 11–15 | 2–3 weeks |
| 3. Unity | 20–28 | 4–6 weeks |
| **Total** | **59–85** | **12–17 weeks** |

A *session* is one weekday of 2–4 hours with a person at the keyboard working with Claude. Five sessions make
a week; there is no weekend work. The total is about 180–250 hours.

These numbers are judgement, not measurement. They include time to learn each editor. The low end assumes
sessions closer to four hours and few surprises; the high end assumes shorter sessions and the usual ones.

## Ground rules

These hold for all three stages. The first two are what keep the estimates this low.

- **The battle stays on a flat plane.** Tanks, shells and collisions keep working exactly as they do now, in two
  dimensions. 3D is what you see, not what the rules run on. Driving over real hills with engine physics would
  add weeks and change aiming and multiplayer.
- **Multiplayer is ported, not replaced.** The existing host-and-snapshot protocol moves across as it is. Neither
  engine's built-in networking is used.
- **Rules and presentation live in separate folders.** `core/` holds weapons, tanks, battle rules, AI, map
  generation and the network protocol. `game/` holds everything that touches the engine. The Python code is
  already split this way (`ut/world.py` has no graphics or networking in it).
- **The Python game is the answer key.** Its test scripts (`tools/aim_test.py`, `net_test.py`, `flow_test.py`)
  print numbers that each new version should reproduce.
- **Camera: tilted top-down.** Same controls and aiming as now, with the depth visible. Other camera styles are
  a later experiment.

### Who does what

| Claude | Person at the keyboard |
|---|---|
| Translates code between languages | Installs tools and runs the editors |
| Writes tests and runs them headless | Judges how it looks, sounds and feels |
| Writes Blender export scripts | Tunes particles, lighting and layout in the editor |
| Writes Godot scenes directly (they are text files) | Play-tests, especially multiplayer on two machines |

In Unity more of the work shifts to the right-hand column, because scenes and prefabs are built in the editor.

## Stage 1: Godot with GDScript (28–42 sessions)

| # | Step | Sessions | Done when |
|---|---|---|---|
| 1.0 | Set-up: install Godot, create the project and folder layout, confirm the camera | 1–2 | An empty project runs on the Mac and the PC |
| 1.1 | Art export: extend the Blender scripts to export tanks, scenery and ammunition as glTF models with baked textures and a team-colour mask; save the synthesised sounds as audio files | 4–6 | All six tanks and the scenery show correctly in Godot's viewer, in any team colour |
| 1.2 | Core logic: translate data, battle rules, AI and map generation to GDScript; port the tests | 4–6 | A headless battle runs and the test numbers match Python |
| 1.3 | First playable: 3D ground and river from the generated map, placed scenery, a tank that drives and shoots, AI opponents, camera | 4–6 | You can play a single-player battle start to finish, with no menus |
| 1.4 | Effects and sound: muzzle flash, explosions, fire, smoke, fallout, craters, track marks | 3–4 | Every weapon looks and sounds distinct |
| 1.5 | Menus and HUD: commanders, main menu, garage and shop, battle set-up, HUD, minimap, scoreboard, pause, results, saving | 5–7 | The full single-player loop works, including save and continue |
| 1.6 | Multiplayer: connection, snapshots, prediction and smoothing, lobby, finding games on the local network | 4–6 | A Mac and a PC play a battle together on the home network |
| 1.7 | Polish and builds: balance check against the Python game, bug fixing, Windows and macOS builds | 3–5 | A double-clickable build on both platforms |

**Most likely to overrun:** 1.1 (the Blender materials are procedural, and baking them to textures is fiddly),
1.5 (there are about ten screens) and 1.6 (two-machine testing is slow).

## Stage 2: Godot with C# (11–15 sessions)

GDScript and C# can live in the same Godot project, so this is done one script at a time with the game playable
throughout.

| # | Step | Sessions | Done when |
|---|---|---|---|
| 2.0 | Set-up: the .NET edition of Godot, the .NET SDK, a C# code editor | 1 | A C# "hello" script runs in the project |
| 2.1 | Core logic to plain C#: a separate library with no Godot types in it, written to the older C# level that Unity accepts, with unit tests that run without any engine | 4–6 | `dotnet test` passes and the game plays on the C# core |
| 2.2 | Engine-facing scripts to C#: tank and scenery views, effects, menus, HUD, input, network glue | 4–6 | No GDScript is left |
| 2.3 | Regression play-test and builds | 2 | Builds on both platforms behave like the stage 1 game |

**The rule that matters:** nothing in `core/` may mention Godot. That is the only reason any code survives
into stage 3. Networking in `core/` should use the standard .NET sockets, not Godot's.

## Stage 3: Unity (20–28 sessions)

The C# core, the models, the textures and the sounds carry over. Scenes, materials, effects and menus are rebuilt.

| # | Step | Sessions | Done when |
|---|---|---|---|
| 3.0 | Set-up: Unity Hub, a Unity 6 editor, a new project, the core library dropped in with its tests | 1–2 | The core tests pass inside Unity |
| 3.1 | Art import: models, textures, a team-colour material | 2–3 | Tanks and scenery look right in any colour |
| 3.2 | World: ground and river, scenery, tank views, camera, input | 4–5 | A single-player battle is playable with no menus |
| 3.3 | Effects and sound | 3–4 | Parity with the Godot version |
| 3.4 | Menus and HUD | 5–7 | The full single-player loop works |
| 3.5 | Multiplayer glue: lobby and join screens on top of the unchanged protocol | 2–3 | Mac and PC play together |
| 3.6 | Polish and builds | 3–4 | A double-clickable build on both platforms |

A bonus check at the end: because stages 2 and 3 share the protocol code, a Godot player and a Unity player
should be able to join the same battle.

## Decisions to make before starting

- **Disk space.** Godot needs under 1 GB. Unity needs 10–15 GB by stage 3.
- **Which computer is the main one.** The plan assumes one Mac and one Windows PC are both available for testing.
- **Unity's editor connection for Claude.** Unity's official one is in beta and reportedly needs a paid Unity AI
  plan. Without it, stage 3 still works but leans more on hands-on editor work. This can wait until stage 3.
- **Where the projects live.** Suggested: `godot/` and `unity/` folders in this repo, beside the Python game.

## What is not in the plan

- New features, tanks, weapons or maps. Each stage aims to match the Python game, not extend it.
- Carrying save files or multiplayer compatibility over from the Python version.
- Signing the macOS build with an Apple Developer account. Unsigned builds run after a right-click → Open.
- Phones, consoles or the web.
