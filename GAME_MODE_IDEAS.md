# Game mode ideas

Game types that could be added to Ultimate Tanks. None of these exist yet. The game currently has Team
Deathmatch, Capture the Flag and Zone Defense; `CLAUDE.md` lists what a new game type has to touch.

Effort is a rough guess relative to the Zone Defense addition:

- **Small**: a rule change on top of an existing mode, with no new art.
- **Medium**: new state, AI behaviour and HUD, and perhaps a little art.
- **Large**: a new mechanic the game does not have yet.

## Common modes

| Mode | How it plays | Builds on | Effort |
|---|---|---|---|
| King of the Hill | One zone in the middle of the map. A team scores for every second it holds the zone alone. | Zone Defense capture logic, with one zone and a running score | Small |
| Free-for-All | No teams. Every tank for itself; first to the kill target wins. | Deathmatch; needs spread-out spawns and a per-player scoreboard | Small |
| Last Team Standing | No respawns. A round ends when one side is wiped out; best of several rounds. | The respawn limit from Capture the Flag | Small |
| VIP (Assassination) | Each team has one marked tank. Destroying the enemy VIP scores, or ends the round. | Deathmatch scoring | Small |
| Juggernaut (Boss) | One player gets a Goliath with extra armour and everyone else hunts it. Whoever lands the kill becomes the next juggernaut. Works with odd player counts. | Deathmatch, with uneven teams | Medium |
| Survival (Waves) | All human players on one team against waves of AI tanks that grow bigger and tougher, with shopping between waves. The only co-op mode on this list. | The AI line-ups and the mid-battle shop | Medium |
| Base Assault | Each team has a headquarters building with a large health pool. Destroy the enemy's to win. Gives heavy shells and the nuke a clear purpose. | Flag home positions; needs a destructible building | Medium |
| Escort (Convoy) | One team protects a slow AI truck driving a route across the map; the other tries to destroy it. Then the sides swap. | AI path following; needs a scripted vehicle and its art | Large |

**Suggested first picks:** King of the Hill, because it is nearly free given Zone Defense, and Survival, because
it adds co-op play.

## Unusual modes

### Ball and object modes

| Mode | How it plays | Effort |
|---|---|---|
| Tank Soccer | A giant ball and two goals; shells and ramming knock the ball around. | Large (ball physics) |
| Bomb Run | One neutral bomb spawns mid-map. Carry it into the enemy base to score. The carrier cannot shoot. | Medium (reuses flag carrying) |
| Oddball | Hold a single object for as long as possible; your team's clock runs while you carry it. | Medium (reuses flag carrying) |

### Infection and role-swap modes

| Mode | How it plays | Effort |
|---|---|---|
| Infection | One tank starts infected. Anyone it destroys respawns on its team. The last clean tank wins. | Small |
| Tag (Hot Potato) | One tank carries a ticking bomb and passes it by ramming. Whoever holds it at zero explodes. | Medium |
| Prop Hunt | One team disguises itself as trees, boulders and hay bales; the other hunts them. | Large (disguises) |

### Rule-twist modes

| Mode | How it plays | Effort |
|---|---|---|
| Gun Game | Everyone starts with the Tracer. Each kill moves you to the next weapon; first to score with the last one wins. | Small |
| One in the Chamber | One shell, and one hit destroys. You only get another shell by scoring a kill. | Small |
| Instagib | Every hit destroys, with fast respawns. Short, chaotic rounds. | Small |
| Random Loadout | Every respawn gives a random tank and weapon, ignoring what you own. | Small |
| Ricochet | Shells bounce off walls a few times, so indirect shots become the whole game. | Medium (projectile bouncing) |

### Map-pressure modes

| Mode | How it plays | Effort |
|---|---|---|
| Battle Royale | No respawns, weapons scattered as pickups, and a shrinking safe area that pushes everyone together. The nuke's fallout area is already the right mechanic for the closing ring. | Large (pickups, ring) |
| Rising Flood | The river widens over time until only high ground and bridges remain. | Large (changing terrain) |
| Fog of War | You only see what is near you or a teammate; the rest of the minimap goes dark. Trees already hide tanks, so this extends that. | Medium |

### Economy and objective oddities

| Mode | How it plays | Effort |
|---|---|---|
| Bounty | Each kill raises the price on your own head. The richest tank at the end wins. | Small |
| Heist | A vault of credits sits mid-map. Grab bags and drive them home while everyone shoots at you. | Medium (reuses flag carrying) |
| Race | Checkpoints around the map with weapons live. Gives the Speed Tank a mode of its own. | Medium |
| Demolition Derby | No guns. Damage comes only from ramming, and heavier tanks hit harder. | Medium (ram damage) |

**Suggested first picks:** Gun Game and Infection, because both are rule changes on top of deathmatch with no
new art. Tank Soccer and Prop Hunt are likely the most fun, but each needs a new mechanic.
