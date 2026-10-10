"""Computer-controlled tanks.

Navigation uses one flow field per team (distance to the nearest enemy over the nav grid), refreshed a couple of
times a second, so forty tanks cost about the same as one. Each tank then adds its own target choice, aiming
error, stand-off range and shopping habits.
"""
import math
import random

from . import data
from .data import WEAPONS, TANKS, TANK_INDEX, WEAPON_INDEX, SHELL, AUTO, NAV
from .mapgen import NW, NH
from .world import angle_diff

NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
# aim error (radians), reaction delay (s), think interval (s)
SKILL = ((0.16, 0.9, 0.34), (0.075, 0.45, 0.24), (0.028, 0.15, 0.16))


class Brain:
    def __init__(self, rng):
        self.next_think = rng.uniform(0, 0.3)
        self.target = -1
        self.heading = None
        self.throttle = 0.0
        self.aim_err = 0.0
        self.err_time = 0.0
        self.seen_for = 0.0
        self.los = False
        self.dist = 1e9
        self.orbit = rng.choice((-1, 1))
        self.range_bias = rng.uniform(0.75, 1.15)
        self.stuck = 0.0
        self.escape = 0.0
        self.escape_turn = 1.0
        self.last = (0.0, 0.0)
        self.scout = rng.random() < 0.18          # this driver likes the Speed Tank
        self.defender = rng.random() < 0.25       # Capture the Flag: stays home to guard the flag
        self.greed = rng.uniform(0.0, 1.0)        # saves up for big purchases instead of buying early


class AIController:
    def __init__(self, world):
        self.world = world
        self.rng = random.Random(world.settings["seed"] * 13 + 5)
        self.fields = [None, None]
        self.field_time = [0.0, 0.3]
        self.goal_fields = {}           # Capture the Flag: name -> [nav cell, time computed, flow field]

    def attach(self, tank):
        tank.brain = Brain(self.rng)

    # -- per frame -------------------------------------------------------------
    def update(self, dt):
        w = self.world
        alive = [t for t in w.players.values() if t.alive]
        for team in (0, 1):
            self.field_time[team] -= dt
            if self.field_time[team] <= 0 or self.fields[team] is None:
                self.field_time[team] = 0.6
                src = [(int(e.x) // NAV, int(e.y) // NAV) for e in alive if e.team != team]
                self.fields[team] = w.map.flow_field(src) if src else None
        for t in w.players.values():
            if not t.is_ai:
                continue
            if t.brain is None:
                self.attach(t)
            if t.alive:
                self._drive(t, alive, dt)

    def _drive(self, t, alive, dt):
        b = t.brain
        w = self.world
        skill = SKILL[t.skill]
        b.next_think -= dt
        if b.next_think <= 0:
            b.next_think = skill[2] * self.rng.uniform(0.8, 1.25)
            self._think(t, alive)
        target = w.players.get(b.target)
        if target and not target.alive:
            target = None

        # --- stuck recovery -----------------------------------------------------
        if b.escape > 0:
            b.escape -= dt
            t.throttle = -0.8
            t.turn = b.escape_turn
        else:
            moved = math.hypot(t.x - b.last[0], t.y - b.last[1])
            if abs(b.throttle) > 0.3 and moved < 12 * dt:
                b.stuck += dt
                if b.stuck > 0.9:
                    b.stuck = 0.0
                    b.escape = self.rng.uniform(0.5, 1.0)
                    b.escape_turn = self.rng.choice((-1.0, 1.0))
            else:
                b.stuck = max(0.0, b.stuck - dt * 0.5)
            if b.heading is None:
                t.throttle, t.turn = 0.0, 0.0
            else:
                d = angle_diff(b.heading, t.angle)
                t.turn = max(-1.0, min(1.0, d * 3.0))
                t.throttle = b.throttle if abs(d) < 0.9 else b.throttle * 0.15
        b.last = (t.x, t.y)

        # --- gunnery ------------------------------------------------------------------
        t.fire[0] = t.fire[1] = False
        if not target:
            t.aim = t.angle
            b.seen_for = 0.0
            return
        b.err_time -= dt
        if b.err_time <= 0:
            b.err_time = self.rng.uniform(0.4, 0.9)
            b.aim_err = self.rng.gauss(0, skill[0])
        dx, dy = target.x - t.x, target.y - t.y
        dist = math.hypot(dx, dy)
        wi = t.sel[SHELL] if t.sel[SHELL] >= 0 else t.sel[AUTO]
        lead = dist / WEAPONS[wi]["speed"] if wi >= 0 else 0.0
        if t.skill == 0:
            lead *= 0.4
        px = target.x + math.cos(target.angle) * target.speed * lead
        py = target.y + math.sin(target.angle) * target.speed * lead
        t.aim = math.atan2(py - t.y, px - t.x) + b.aim_err
        if b.los:
            b.seen_for += dt
        else:
            b.seen_for = 0.0
            return
        if b.seen_for < skill[1]:
            return
        off = abs(angle_diff(t.aim, t.turret))
        s0, s1 = t.sel[SHELL], t.sel[AUTO]
        if s0 >= 0:
            w0 = WEAPONS[s0]
            danger = (w0["splash"] + 80) if (w0["hurts_all"] or w0["zone"]) else 0
            if dist < w0["range"] * 0.92 and dist > danger and off < 0.09:
                t.fire[0] = True
        if s1 >= 0:
            w1 = WEAPONS[s1]
            if dist < w1["range"] * 0.88 and off < 0.2:
                t.fire[1] = True

    # -- decisions a few times a second --------------------------------------------------
    def _think(self, t, alive):
        b = t.brain
        w = self.world
        m = w.map
        ctf = bool(w.flags)
        enemies = [e for e in alive if e.team != t.team]
        if not enemies and not ctf:
            b.target, b.heading, b.throttle = -1, None, 0.0
            return
        enemies.sort(key=lambda e: (e.x - t.x) ** 2 + (e.y - t.y) ** 2)
        if ctf:                                  # whoever has our flag is the priority target
            enemies.sort(key=lambda e: e.flag != t.team)
        target, los = (enemies[0], False) if enemies else (None, False)
        for e in enemies[:3]:
            if m.line_of_fire(t.x, t.y, e.x, e.y):
                target, los = e, True
                break
        b.target, b.los = (target.pid if target else -1), los
        if not los and t.credits >= 20 and self.rng.random() < 0.02:
            before = t.tank_key
            self.shop(t)                    # out of contact: a chance to spend winnings mid-life
            if t.tank_key != before:
                key = t.tank_key
                t.set_tank(before)
                w.select_tank(t.pid, key)
        dist = math.hypot(target.x - t.x, target.y - t.y) if target else 1e9
        b.dist = dist

        # preferred stand-off distance depends on what we are carrying
        s0, s1 = t.sel[SHELL], t.sel[AUTO]
        reach = min([WEAPONS[i]["range"] for i in (s0, s1) if i >= 0] or [600])
        want = min(reach * 0.62, 620) * b.range_bias
        if s0 >= 0 and WEAPONS[s0]["hurts_all"]:
            want = max(want, WEAPONS[s0]["splash"] + 220)
        to_target = math.atan2(target.y - t.y, target.x - t.x) if target else t.angle

        goal = self._ctf_goal(t) if ctf else None
        if goal:
            key, pos, rush = goal
            dgoal = math.hypot(pos[0] - t.x, pos[1] - t.y)
            # tanks on a mission keep driving and shoot on the move; only guards, escorts and hunters
            # stop to duel. (Stopping for every fight turns the match into a brawl nobody scores in.)
            may_fight = t.flag < 0 and not rush
        else:
            may_fight = True

        if may_fight and los and dist < want * 0.55:
            b.heading, b.throttle = to_target, -0.8               # too close: back away, still facing them
        elif may_fight and los and dist < want * 1.15:
            b.heading = to_target + b.orbit * 1.35                # circle to be a harder target
            b.throttle = 0.75
            if self.rng.random() < 0.04:
                b.orbit = -b.orbit
        elif goal:
            if not rush and key.startswith("home") and dgoal < 300:
                b.heading, b.throttle = (to_target if los else None), 0.0     # on guard at the base
            elif dgoal < 130:
                b.heading, b.throttle = math.atan2(pos[1] - t.y, pos[0] - t.x), 1.0
            else:
                b.heading = self._path_heading(t, math.atan2(pos[1] - t.y, pos[0] - t.x), self._field_to(key, pos))
                b.throttle = 1.0
        else:
            b.heading = self._path_heading(t, to_target)
            b.throttle = 1.0

    def _field_to(self, key, pos):
        """Flow field leading to a point (a flag or a base), recomputed when the point moves."""
        cell = (int(pos[0]) // NAV, int(pos[1]) // NAV)
        now = self.world.time
        g = self.goal_fields.get(key)
        if g is None or (g[0] != cell and now - g[1] > 0.4):
            g = [cell, now, self.world.map.flow_field([cell])]
            self.goal_fields[key] = g
        return g[2]

    def _ctf_goal(self, t):
        """Where this tank should be heading, and whether it should ignore fights on the way: (key, pos, rush)."""
        w = self.world
        mine, theirs = w.flags[t.team], w.flags[1 - t.team]
        home = w.map.flag_homes[t.team]
        if t.flag >= 0:
            return "home%d" % t.team, home, True                         # run it home
        if mine[0] == 1 and (t.brain.defender or math.hypot(mine[1] - t.x, mine[2] - t.y) < 900):
            return "flag%d" % t.team, (mine[1], mine[2]), False          # hunt the thief
        if t.brain.defender:
            if mine[0] == 2:
                return "flag%d" % t.team, (mine[1], mine[2]), True       # touch it to send it home
            return "home%d" % t.team, home, False                        # stand guard
        if theirs[0] == 1:
            return "flag%d" % (1 - t.team), (theirs[1], theirs[2]), False    # escort our carrier
        return "flag%d" % (1 - t.team), (theirs[1], theirs[2]), True     # go and get it

    def _path_heading(self, t, fallback, field=None):
        field = field or self.fields[t.team]
        if field is None:
            return fallback
        cx, cy = int(t.x) // NAV, int(t.y) // NAV
        if not (0 <= cx < NW and 0 <= cy < NH):
            return fallback
        nav = self.world.map.nav_list
        here = field[cy][cx]
        best, bx, by = here, None, None
        for dx, dy in NEIGHBOURS:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < NW and 0 <= ny < NH):
                continue
            if dx and dy and (nav[cy][nx] or nav[ny][cx]):       # no cutting corners
                continue
            d = field[ny][nx] + (0.4 if dx and dy else 0.0)
            if d < best:
                best, bx, by = d, nx, ny
        if bx is None:
            return fallback
        # look one cell further along the gradient for smoother driving
        best2, ex, ey = best, bx, by
        for dx, dy in NEIGHBOURS:
            nx, ny = bx + dx, by + dy
            if 0 <= nx < NW and 0 <= ny < NH and not (dx and dy and (nav[by][nx] or nav[ny][bx])):
                d = field[ny][nx]
                if d < best2:
                    best2, ex, ey = d, nx, ny
        tx = (bx + ex) / 2 * NAV + NAV / 2
        ty = (by + ey) / 2 * NAV + NAV / 2
        return math.atan2(ty - t.y, tx - t.x)

    # -- spending money -------------------------------------------------------------------
    def shop(self, t):
        """Called when an AI tank respawns: buy upgrades it can afford, then pick its best ride."""
        b = t.brain or Brain(self.rng)
        t.brain = b
        for _ in range(4):
            options = []
            for tank in TANKS:
                if tank["key"] in t.tanks or tank["cost"] > t.credits:
                    continue
                if tank["key"] == "speed" and not b.scout:
                    continue
                need = 0 if data.usable(tank["key"], t.weapons) else min(WEAPONS[i]["cost"] for i in tank["weapons"])
                if tank["cost"] + need <= t.credits:
                    options.append((tank["cost"] * 1.2, "tank", tank["key"]))
            owned_allowed = set()
            for k in t.tanks:
                owned_allowed.update(TANKS[TANK_INDEX[k]]["weapons"])
            for i in owned_allowed:
                wp = WEAPONS[i]
                if wp["key"] not in t.weapons and wp["cost"] <= t.credits:
                    options.append((wp["cost"], "weapon", wp["key"]))
            if not options:
                break
            options.sort(reverse=True)
            value, kind, key = options[0]
            # greedy drivers skip small purchases while a much bigger one is nearly in reach
            if b.greed > 0.6 and value < 60 and t.credits > 45 and len(options) == 1:
                break
            self.world.buy(t.pid, kind, key)
        # choose the tank: the most valuable one we can arm (scouts sometimes take the Speed Tank)
        best = max((k for k in t.tanks if data.usable(k, t.weapons)), key=lambda k: TANKS[TANK_INDEX[k]]["cost"])
        if b.scout and "speed" in t.tanks and self.rng.random() < 0.6:
            best = "speed"
        t.set_tank(best)


def make_ai_loadout(rng, team, index, skill, used_names, tank="basic"):
    names = [n for n in data.AI_NAMES if n not in used_names] or data.AI_NAMES
    name = rng.choice(names)
    used_names.add(name)
    colors = data.AI_COLORS[team]
    credits = (0, rng.choice((0, 0, 20, 40)), rng.choice((40, 60, 100, 140)))[skill]
    tanks = ["basic"] if tank == "basic" else ["basic", tank]
    return dict(name=name, color=list(colors[index % len(colors)]), credits=credits, tanks=tanks,
                weapons=["basic_shell", "tracer"] + data.AI_KIT.get(tank, []), tank=tank)
