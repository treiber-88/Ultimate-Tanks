# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Ultimate Tanks is a top-down tank battle game in Python on pygame: two teams of human and AI tanks, an in-game
economy (credits for kills, a shop for tanks and weapons), LAN/internet multiplayer, and three game types
(Team Deathmatch, Capture the Flag, Zone Defense). It was built with Claude from the brief in
`Claude for Tanks.md`, and is played on both Windows and macOS. `README.md` is the player-facing manual and
holds the full rules, controls and balance tables; keep it in step when behaviour changes.

## Commands

There is no build step, linter or test framework. Tests are standalone scripts in `tools/`.

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # once (run.command / run.bat do this too)
.venv/bin/python main.py                                            # play
```

On Windows the interpreter is `.venv\Scripts\python` (or plain `python`, which is what `run.bat` uses).

Tests run headless (SDL dummy video and audio drivers) and print `ALL OK` or their measurements. Run one by
naming its script:

```
.venv/bin/python tools/aim_test.py                  # aiming, bush and tree crushing
.venv/bin/python tools/net_test.py                  # host + client over localhost
.venv/bin/python tools/flow_test.py OUT_DIR         # commander, shop, save/continue, client battle
.venv/bin/python tools/ctf_test.py                  # Capture the Flag rules, AI matches, save/load, client view
.venv/bin/python tools/zone_test.py                 # Zone Defense rules, AI matches, save/load, client view
.venv/bin/python tools/shots.py OUT_DIR 1920 1080   # drives every screen and saves screenshots to look at
.venv/bin/python tools/lag_test.py 40 50            # multiplayer smoothness on a simulated bad connection
.venv/bin/python tools/profile_battle.py 1920 1080  # frame-time profile of a 20 v 20 battle
```

Tests that write files redirect `profiles.SAVES` to their output folder, so they never touch real saves in
`saves/`. Do the same in any new script that creates a `Profile`.

## Architecture

The code is split so that the game rules never touch graphics or sockets:

- `ut/data.py` is every number: weapons, tanks, rewards, timings, ports, the `MODES` list. Rebalance here.
- `ut/world.py` is the battle simulation, stepped with `World.step(dt)`. No pygame, no networking.
  `ut/ai.py` drives AI tanks by setting the same inputs a player would.
- `ut/mapgen.py` builds a map from `(preset, seed)` alone. Multiplayer clients rebuild the map locally from
  those two values; map contents are never sent over the network.
- `ut/net.py` wraps a `World` in a session. `LocalSession` runs the authoritative world (single player, or the
  host). `RemoteSession` is a client: it holds a *mirror* world (`World(..., mirror=True)`) that only moves
  projectiles for display and takes everything else from host snapshots, with interpolation for other tanks and
  prediction plus reconciliation for the player's own tank. Screens talk to either session through the same
  methods, so battle code does not know which one it has.
- `ut/render.py` (`BattleView`) draws a world; `ut/screens.py` holds every menu and the battle HUD;
  `ut/ui.py` is an immediate-mode UI kit laid out on a virtual 1080-pixel-high screen and scaled to the window.

Consequences worth knowing before changing things:

- **New world state must travel three ways.** Anything added to `World` that players can see needs to be in
  `snapshot()` (and applied on the client in `RemoteSession`), and in `to_dict()` / `from_dict()` for saved
  battles. The mode tests check all three.
- **`world.zones` is not Zone Defense.** `zones` are the lingering fire and fallout areas left by weapons. The
  Zone Defense capture zones are `world.cps`, placed at `GameMap.zone_points`. CTF state is `world.flags`,
  placed at `GameMap.flag_homes`.
- **Simulation is 2D on a grid.** Positions are pixels at `PPM = 20` pixels per metre; collision uses
  `CELL`-sized cells and AI navigation uses coarser `NAV` cells with flow fields.

### Adding a game type

A game type is a key in `data.MODES` plus code in the places the Zone Defense commit (`6716c8e`) touched,
which is the best worked example: constants in `data.py`; placement in `mapgen.py`; state, per-step rules and
win condition in `world.py` (also the allow-list in `World.__init__`); goals in `ai.py`; snapshot fields in
`net.py`; ground markings and HUD in `render.py` and `screens.py`; set-up options in `screens.Setup`; a
`tools/<mode>_test.py`; and a README section. Ideas for further game types are in `GAME_MODE_IDEAS.md`.

## Rendering pitfalls

- **The window has an alpha channel on macOS and not on Windows.** `Surface.convert()` copies the window's
  format, so on macOS it yields a surface with alpha. Alpha-blitting into such a surface zeroes its alpha and
  later additive blits skip those pixels (dark boxes in explosions). Any opaque surface that gets drawn into
  must be created without alpha, as the ground chunks are in `Ground._build`.
- **Headless tests cannot see that class of bug.** The dummy video driver has no alpha channel, like Windows.
  Display-format problems only show in a real window, so check rendering changes in one on macOS.
- Effects use two sprite sets: `assets.fx` (normal alpha) and `assets.fx_add` (premultiplied, blitted with
  `BLEND_RGB_ADD`). Scaled, tinted and rotated variants are cached in `BattleView`; reuse those caches instead
  of transforming per frame.

## Art

All art is rendered from Blender by the scripts in `tools/blender/`, run through the Blender MCP add-on with
`tools/blrun.py` (commands are in the README). The PNGs in `assets/` are generated output: change the script
and re-render instead of editing an image. Tanks are rendered pale grey with a separate paint mask, and the
game multiplies each player's colour into the mask at load time.

## Other notes

- Player data lives in `saves/` (git-ignored) as plain JSON; uncaught errors append to `crash.log`.
- Multiplayer uses TCP 27877 for the game and UDP 27878 for finding games on the local network.
- `ENGINE_PLAN.md` on the `feature/engine` branch is a plan for moving the game to Godot and later Unity.
