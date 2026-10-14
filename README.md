# Ultimate Tanks

A top-down tank battle game: team deathmatch against AI or friends, an in-game economy, six tanks and ten kinds
of ammunition. Every piece of art was modelled and rendered in Blender.

## Playing

On Windows double-click `run.bat`; on a Mac double-click `run.command`. On Linux, or from a terminal on
any platform:

```
pip install -r requirements.txt
python main.py
```

Needs 64-bit Python 3.10–3.13 with `pygame-ce` (or classic `pygame` 2.5+), `numpy` and `pillow`.
`run.bat` and `run.command` install them the first time. If you see *failed to build pygame*, the Python on
that computer has no prebuilt pygame: install 64-bit Python 3.12 and run the launcher again. On Linux this
also works with a virtual environment (`python -m venv .venv && .venv/bin/pip install -r requirements.txt
&& .venv/bin/python main.py`), and runs the same as on Windows and Mac - no platform-specific code is used.

On a Mac, `run.command` keeps the libraries in a `.venv` folder next to the game, so nothing else on the
computer is changed. If macOS refuses to open it the first time ("cannot be opened because it is from an
unidentified developer"), right-click it and choose *Open*.

### Controls

| Action | Key |
| --- | --- |
| Drive / steer | `W` `S` / `A` `D` (or arrow keys) |
| Aim turret | Mouse |
| Fire cannon (shells) | Left mouse button |
| Fire machine gun (automatic weapons) | Right mouse button (two-finger click on a trackpad) or `Space` |
| Next shell type / next automatic weapon | `Q` or mouse wheel / `E` |
| Pick a weapon directly | `1`–`9`, `0` (in the order of the ammunition list) |
| Shop and tank swap, mid-battle | `B` |
| Capture a zone (Zone Defense) | hold `Z` inside it |
| Scoreboard | hold `Tab` |
| Pause / menu | `Esc` |
| Fullscreen | `F11`, or `Cmd`+`F` on a Mac |
| FPS counter | `F3` |

### Game types

Pick the game type on the battle setup screen (single player or when hosting).

- **Team Deathmatch** - first team to the kill target wins.
- **Capture the Flag** - each team has a flag on a pad at the back of its spawn area. Drive over the enemy
  flag to pick it up and carry it to your own pad to score; first to the capture target wins.
  - You can only score while your own flag is at home.
  - A carrier takes only 65 % of normal damage, and drops the flag where it is destroyed.
  - Destroyed tanks take 9 seconds to return (4 in deathmatch), so a raid has time to get away.
  - Every tank can respawn only twice (three tanks in all). Destroyed a third time, it is out for the
    rest of the match and its driver watches a teammate (click to switch). A team with nobody left
    loses on the spot.
  - Touch your own dropped flag to send it home at once; otherwise it returns by itself after 30 seconds.
  - A capture pays 40 credits and a return 10. Kills still pay as usual but do not count toward the score.
  - The top of the screen shows where both flags are, the minimap marks flags and bases, and a pointer at
    the screen edge leads to the enemy flag (or to your base once you are carrying it).
  - AI tanks play it too: most go for the enemy flag, about a quarter stay to guard their own.
    With very large teams (15+ a side) the middle of the map becomes a wall of fire and captures get rare.

- **Zone Defense** - five zones (A to E) are strung across the map. Each side starts holding the one outside
  its base; the three in between start empty.
  - Drive into a zone you do not hold and **hold `Z` for 5 seconds** to capture it. You may move and shoot
    while you do, but leaving the ring, letting go of `Z` or being destroyed starts the count over.
  - The count pauses while any enemy tank is inside the zone, so defenders can stop a capture by getting in.
  - Hold all five zones at any moment and you win on the spot. Otherwise the team holding more zones when
    the timer runs out wins (set the timer on the setup screen, 1-60 minutes); equal zones is a draw.
  - A capture pays 15 credits. Kills pay as usual but do not count. Respawns are unlimited.
  - The zones show in their owner's colour on the ground, under the score and on the minimap.

- **King of the Hill** - one zone in the middle of the map. Your team scores a point for every second it
  is the only team with a tank inside; nobody scores while it is contested or empty. First to the target
  (30-300 seconds) wins, or whoever is ahead when the timer runs out.
- **Free-for-All** - no teams; everyone else is an enemy. Tanks appear all over the map rather than at two
  ends. First to the kill target wins. The scoreboard is one ranking, and your colour on the minimap is blue
  with everyone else red.
- **Last Team Standing** - no respawns. When one side is wiped out the other takes the round, and everyone
  returns for the next one; first to the round target (1-7) wins. A round that drags past three minutes goes
  to the side with more tanks left. Destroyed players watch a teammate until the round ends.
- **Base Assault** - each side has a headquarters with 500 health just in front of its spawn area. Destroy
  the enemy's to win; if the timer runs out, the healthier headquarters wins. Splash, fire and fallout all
  hurt it, so heavy shells and the nuke earn their keep.
- **Escort the Convoy** - Blue escorts a slow supply truck from its base to the enemy's while Red tries to
  destroy it; then the sides swap. A truck that arrives beats one that was destroyed; if both arrive the
  faster run wins, and if neither does the one that got further wins. The battle's time limit is not used.
- **Juggernaut** - one tank becomes the Juggernaut: a Goliath with Death Shells and a Heavy Gatling on loan
  that takes only 40 % damage, hunted by everyone else. Whoever destroys it becomes the next one. You score
  1 point per kill as the Juggernaut and 3 for bringing it down; first to the points target wins. The loaned
  tank and ammunition are never added to your garage.
- **Survival** - every human and allied AI tank on one side against waves of AI tanks. Each wave is one tank
  bigger than the last and the tanks get better every few waves. Destroyed defenders come back when the wave
  is cleared, and there are twelve seconds to shop (`B`) before the next one. Clearing a wave pays everyone
  10 credits plus 5 per wave number. It ends when all defenders are down at once; the result is how many
  waves you cleared. Good for playing together on one network.
- **VIP** - each team has one marked tank (gold ring, "VIP" over its name, gold on the minimap). Destroying
  the enemy VIP scores a point and pays 25 credits; a new VIP is then chosen. First to the target wins.

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

### The AI keeps pace with you

The tanks the AI brings to a battle depend on the best tank in your garage (in multiplayer, the best among
all the human players). Both teams' AI use the same mix, so your allies improve along with your enemies.

| Your best tank | AI tanks at the start of a battle |
| --- | --- |
| Basic | all Basic |
| Medium or Speed | 60 % Basic, 25 % Medium, 15 % Speed |
| Heavy | 35 % Basic, 25 % Medium, 20 % Speed, 20 % Heavy |
| Mammoth | 25 % Mammoth, 20 % Heavy, 20 % Speed, 15 % Medium, 20 % Basic |
| Goliath | 30 % Goliath, 20 % Mammoth, 20 % Speed, 10 % Medium, 10 % Heavy, 10 % Basic |

Each AI tank arrives with ammunition to match (a Goliath carries Death Shells and a Heavy Gatling, for
example). The setup screen shows the exact line-up before you start. During the battle the AI still earns
credits and upgrades as before, so the mix can creep upward in a long fight. The tables are `AI_MIX` and
`AI_KIT` in [ut/data.py](ut/data.py).

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
- Hosting on a Mac: if the macOS firewall is on, it asks *"Do you want the application Python to accept
  incoming network connections?"* the first time a lobby is opened - choose Allow. To change the answer
  later: System Settings → Network → Firewall → Options. Windows PCs and Macs can play together.
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
ut/modes.py        rules for the game types beyond deathmatch, flags and zones
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
python tools/blrun.py "" tools/blender/render_flags.py      # Capture the Flag flags and base pads
python tools/blrun.py "" tools/blender/render_zones.py      # Zone Defense ground markings
python tools/blrun.py "" tools/blender/render_modes.py      # headquarters and convoy truck
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
python tools/ctf_test.py                  # Capture the Flag rules, AI matches, save/load, client view
python tools/zone_test.py                 # Zone Defense rules, AI matches, save/load, client view
python tools/modes_test.py                # the eight other game types: AI matches, save/load, client view
python tools/profile_battle.py 1920 1080  # frame-time profile of a 20 v 20 battle
```
