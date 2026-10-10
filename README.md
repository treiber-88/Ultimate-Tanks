# Ultimate Tanks

A top-down tank battle game: team deathmatch against AI or friends, an in-game economy, six tanks and ten kinds
of ammunition. Every piece of art was modelled and rendered in Blender.

## Playing

Double-click `run.bat`, or from a terminal:

```
pip install -r requirements.txt
python main.py
```

Needs 64-bit Python 3.10–3.13 with `pygame-ce` (or classic `pygame` 2.5+), `numpy` and `pillow`.
`run.bat` installs them the first time. If you see *failed to build pygame*, the Python on that
computer has no prebuilt pygame: install 64-bit Python 3.12 and run `run.bat` again.

### Controls

| Action | Key |
| --- | --- |
| Drive / steer | `W` `S` / `A` `D` (or arrow keys) |
| Aim turret | Mouse |
| Fire cannon (shells) | Left mouse button |
| Fire machine gun (automatic weapons) | Right mouse button or `Space` |
| Next shell type / next automatic weapon | `Q` or mouse wheel / `E` |
| Pick a weapon directly | `1`–`9`, `0` (in the order of the ammunition list) |
| Shop and tank swap, mid-battle | `B` |
| Scoreboard | hold `Tab` |
| Pause / menu | `Esc` |
| Fullscreen | `F11` |
| FPS counter | `F3` |

### How a battle works

- Two teams. First team to the kill target wins, or whoever leads when the clock runs out.
- Destroying an enemy tank pays credits (15 for a Basic Tank up to 65 for a Goliath). Everyone also gets a small
  bonus when the battle ends. AI tanks earn and spend money by the same rules.
- Spend credits in the Garage between battles, or press `B` during one. Purchases take effect immediately.
  Switching tank mid-battle keeps your damage percentage and takes a moment to deploy.
- Any tank can carry any weapon you own.
- A cannon shot fires one shell from every barrel: two from the Heavy and Mammoth, three from the Goliath.
- Shots go where the cursor was when you fired. A shell bursts on that exact spot (or on anything it hits
  on the way); if the spot is out of range the crosshair turns red and the shell bursts at maximum range.
  Bullets pass through the spot and carry on. The gun holds fire until the turret has swung onto the cursor.
- Any tank flattens bushes by driving over them. Heavy, Mammoth and Goliath tanks also knock down trees,
  opening new paths; lighter tanks have to go around.
- Destroyed tanks respawn after four seconds with a short spawn shield.
- Fire from the Combust Shell and fallout from the Nuke Shell hurt *everyone* in the area, including you.
- Trees hide whatever is under them. Rivers can only be crossed at bridges and fords (fords slow you down).

### Saving

- A **commander** is a save slot: name, paint colour, credits, tanks, weapons and career stats. Create as many as
  you like from *Commander* in the main menu. Progress is saved automatically.
- In single player, *Esc → Save & quit* stores the whole battle; *Continue Saved Battle* resumes it.
- Saves are plain JSON files in `saves/`.

### Multiplayer

One player chooses *Host Multiplayer*, sets up the battle and opens the lobby. The lobby shows the address and
port to give to friends, who choose *Join Multiplayer* and type it in. Players can also join a battle already in
progress.

- Same Wi-Fi or LAN: the host's game appears in the *Join Multiplayer* list by itself; press Join. If it does
  not appear, type the address shown in the host's lobby. The host must allow Python through Windows
  Firewall on private networks (Windows asks the first time a lobby is opened - choose Allow).
- "Actively refused" means nothing was listening at that address: the host had not opened the lobby,
  or the address was wrong (`127.0.0.1` always means *your own* PC). No answer at all usually means
  the host's firewall is blocking the game.
- Security suites with their own firewall (Norton, McAfee, Bitdefender...) block incoming connections to
  Python even when Windows Firewall allows them, and typically show up as "actively refused". On the
  host's PC, allow `python.exe` in the suite's firewall/program rules (TCP 27877 for the game, UDP 27878
  for the game list) - or simply host from the PC that does not have the suite; joining is not affected.
- Over the internet: the host must forward TCP port 27877 on their router.
- Up to 16 humans; AI tanks fill each team as configured by the host (0–20 per side).
- Each player brings their own commander. Credits earned and things bought during the battle are saved back to it.

## Weapons and tanks

Damage is on a 1–20 scale and a tank's hit points are its strength × 4. A shell does its listed damage per hit.
Automatic weapons ("reload: none") spread their damage over a stream of bullets — roughly 40 % of the listed
number per second of sustained hits — so that the free Tracer does not outgun every cannon. Machine guns on
multi-barrel tanks alternate barrels and fire a little faster.

| Weapon | Damage | Reload | Cost | Notes |
| --- | --- | --- | --- | --- |
| Basic Shell | 5 | 4 s | free | |
| Tracer | 3 | none | free | accurate, long reach |
| Gatling | 6 | none | 20 | fast, loose, short range |
| Heavy Shell | 10 | 4 s | 40 | |
| Combust Shell | 11 | 3 s | 80 | leaves fire for 10 s |
| Heavy Tracer | 6 | none | 70 | |
| Heavy Gatling | 10 | none | 100 | |
| Canister | 10 | 4 s | 50 | 5 shells at once in a fan |
| Death Shell | 15 | 5 s | 130 | |
| Nuke Shell | 20 | 6 s | 200 | huge blast, leaves fallout |

| Tank | Cost | Speed | Strength | Shells per shot |
| --- | --- | --- | --- | --- |
| Basic | free | 12 | 5 | 1 |
| Medium | 60 | 10 | 8 | 1 |
| Heavy | 100 | 8 | 12 | 2 |
| Mammoth | 150 | 6 | 16 | 2 |
| Goliath | 200 | 6 | 20 | 3 |
| Speed | 60 | 20 | 4 | 1 |

All of these numbers, plus rewards, ranges and blast sizes, live in [ut/data.py](ut/data.py).

## Project layout

```
main.py            entry point and main loop
ut/data.py         weapons, tanks, colours, tuning constants
ut/world.py        the battle simulation (no graphics, no networking)
ut/ai.py           computer-controlled tanks
ut/mapgen.py       procedural battlefields (three presets, any seed)
ut/net.py          multiplayer host/client and the battle sessions
ut/render.py       ground, scenery, tanks, particles
ut/screens.py      menus, garage/shop, lobby, battle HUD
ut/ui.py           small immediate-mode UI kit
ut/assets.py       art loading, team-colour tinting, shadows
ut/sound.py        synthesised sound effects
ut/profile.py      commanders and saved battles
assets/            rendered art
tools/             art pipeline and test scripts
```

## Rebuilding the art

The art is generated by Python scripts that run inside Blender through the Blender MCP add-on (Blender 5.x,
add-on listening on its default port 9876). With Blender open:

```
python tools/blrun.py "" tools/blender/render_tanks.py      # tank sprite sheets, masks, shop previews
python tools/blrun.py "" tools/blender/render_scenery.py    # trees, houses, mountains, boulders, bridge
python tools/blrun.py "" tools/blender/render_terrain.py    # ground textures
python tools/make_tileable.py                               # ...made seamless
python tools/blrun.py "" tools/blender/render_ammo.py       # shells and bullets
python tools/blrun.py "" tools/blender/render_fx.py         # fire, smoke, flashes, craters, debris
python tools/blrun.py "" tools/blender/render_ui.py         # logo, menu backdrop, UI skins
```

The first argument is optional Python run before the script, e.g. `"ONLY=['goliath']"` to re-render one tank.
The scripts work in their own scene called `UT` and leave your other scenes alone. Tank shapes are defined in
[tools/blender/tanks.py](tools/blender/tanks.py).

Tanks are rendered in pale grey with a separate mask of the painted areas; the game multiplies each player's
colour into the mask, so any colour works without re-rendering.

## Tests

No window is opened by any of these.

```
python tools/shots.py out_dir 1920 1080   # drives every screen off-screen and saves screenshots
python tools/net_test.py                  # host + client over localhost
python tools/flow_test.py out_dir          # commander creation, shop, save/continue, client battle
python tools/aim_test.py                  # shots land on the cursor point; bush and tree crushing
python tools/lag_test.py 40 50            # multiplayer smoothness over a simulated bad connection
python tools/profile_battle.py 1920 1080  # frame-time profile of a 20 v 20 battle
```
