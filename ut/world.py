"""The battle simulation: tanks, weapons, damage, money, respawns. No rendering and no networking in here.

The host (or single-player game) runs it authoritatively; multiplayer clients run a mirror that only moves
projectiles for display and takes everything else from the host's snapshots.
"""
import json
import math
import os
import random

from . import data
from .data import WEAPONS, TANKS, TANK_INDEX, WEAPON_INDEX, SHELL, AUTO, PPM
from . import modes
from .mapgen import GameMap, CRUSH_CELL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "assets", "tanks", "tanks.json"), encoding="utf-8") as _f:
    TANK_ART = json.load(_f)

TAU = math.pi * 2
FLAG_HOME, FLAG_CARRIED, FLAG_DROPPED = 0, 1, 2


def angle_diff(a, b):
    """Shortest signed turn from b to a."""
    return (a - b + math.pi) % TAU - math.pi


def turn_toward(cur, target, max_step):
    d = angle_diff(target, cur)
    if abs(d) <= max_step:
        return target
    return cur + (max_step if d > 0 else -max_step)


class Tank:
    """A player (human or AI) and the tank they are currently driving."""

    def __init__(self, pid, loadout, team, is_ai=False, skill=1):
        self.pid = pid
        self.name = loadout["name"]
        self.color = tuple(loadout["color"])
        self.team = team
        self.is_ai = is_ai
        self.skill = skill
        self.credits = int(loadout.get("credits", 0))
        self.tanks = list(loadout.get("tanks", ["basic"]))
        self.weapons = list(loadout.get("weapons", ["basic_shell", "tracer"]))
        self.kills = 0
        self.deaths = 0
        self.earned = 0
        self.alive = False
        self.respawn = 0.0
        self.x = self.y = 0.0
        self.angle = self.turret = 0.0
        self.speed = 0.0
        self.hp = 0.0
        self.shield = 0.0
        self.lockout = 0.0
        self.barrel = 0
        self.cool = {}
        self.sel = [-1, -1]
        self.last_hit_by = -1
        self.recoil = 0.0
        self.flag = -1             # Capture the Flag: which team's flag this tank is carrying, or -1
        self.respawns = data.CTF_RESPAWNS      # Capture the Flag: how many more times this tank may come back
        self.points = 0            # personal score in the individually scored game types
        self.temp = []             # [kind, key] items lent by the game type (the Juggernaut's Goliath): never saved
        self.own_tank = loadout.get("tank", "basic")
        self.allow = None          # (tank keys, weapon keys) the game type limits this tank to, or None
        self.upgrades = data.clean_upgrades(loadout.get("upgrades"))
        self.out = False           # Capture the Flag: destroyed with no respawns left
        # inputs
        self.throttle = 0.0
        self.turn = 0.0
        self.aim = 0.0
        self.aim_dist = None       # how far away the player's cursor is; None = just shoot along the barrel
        self.hold = False          # Zone Defense: the capture key is being held
        self.fire = [False, False]
        self.brain = None
        self.set_tank(loadout.get("tank", "basic"))

    # -- loadout ---------------------------------------------------------------
    def up(self, kind):
        """Upgrade level of the tank being driven (0 when the game type assigns tanks)."""
        if self.allow:
            return 0
        lv = self.upgrades.get(self.tank_key)
        return lv[kind] if lv else 0

    def usable(self, slot=None, key=None):
        """Weapons this player can fire right now: owned, and permitted by the game type."""
        opts = data.usable(key or self.tank_key, self.weapons, slot)
        if self.allow:
            opts = [i for i in opts if WEAPONS[i]["key"] in self.allow[1]]
        return opts

    def set_tank(self, key):
        if self.allow and key not in self.allow[0]:
            key = self.allow[0][0]
        if key not in self.tanks or not data.usable(key, self.weapons):
            key = "basic"
        self.tank_key = key
        self.spec = TANKS[TANK_INDEX[key]]
        self.art = TANK_ART[key]
        self.max_hp = data.tank_hp(self.spec) * (1 + data.UPGRADES[1][2] * self.up(1))
        self.radius = self.spec["radius"]
        for slot in (SHELL, AUTO):
            opts = self.usable(slot, key)
            if self.sel[slot] not in opts:
                self.sel[slot] = max(opts, key=lambda i: WEAPONS[i]["damage"]) if opts else -1

    def state(self):
        """The part of a player that persists after the battle."""
        lent_t = [k for kind, k in self.temp if kind == "tank"]
        lent_w = [k for kind, k in self.temp if kind == "weapon"]
        tanks = [k for k in self.tanks if k not in lent_t]
        # while the game type dictates the tank, remember the one the player had chosen for themselves
        tank = self.tank_key if (self.tank_key in tanks and not self.allow) else             (self.own_tank if self.own_tank in tanks else "basic")
        return dict(name=self.name, color=list(self.color), credits=self.credits, tanks=tanks,
                    weapons=[k for k in self.weapons if k not in lent_w], tank=tank,
                    upgrades={k: list(v) for k, v in self.upgrades.items()})

    def pivot(self):
        tx = self.art["turret_x"] * PPM
        return self.x + math.cos(self.angle) * tx, self.y + math.sin(self.angle) * tx

    def muzzle(self, barrel):
        mx, my = self.art["muzzles"][barrel % len(self.art["muzzles"])]
        px, py = self.pivot()
        c, s = math.cos(self.turret), math.sin(self.turret)
        lx, ly = mx * PPM, -my * PPM
        return px + lx * c - ly * s, py + lx * s + ly * c


class World:
    def __init__(self, settings, mirror=False):
        self.settings = dict(map="valley", seed=1, kill_limit=30, time_limit=600, difficulty=1, mode="tdm",
                             cap_limit=3, score_limit=100, rounds=3)
        self.settings.update(settings)
        self.mode = self.settings["mode"] if self.settings["mode"] in data.MODE_KEYS else "tdm"
        self.map = GameMap(self.settings["map"], self.settings["seed"])
        self.mirror = mirror
        self.rng = random.Random(self.settings["seed"] * 31 + 7)
        self.players = {}
        self.projectiles = {}
        self.zones = []
        self.events = []
        self.time = 0.0
        self.scores = [0, 0]
        self.over = None           # None while playing, else winning team (or -1 for a draw)
        self.crushed = set()       # indices of map objects (bushes, trees) that tanks have flattened
        self._nav_time = 0.0
        self._next_pid = 1
        self._next_proj = 1
        self._next_zone = 1
        self.ai = None
        # Capture the Flag: one entry per team: [state, x, y, carrier pid, seconds until auto-return]
        self.flags = [[FLAG_HOME, x, y, -1, 0.0] for x, y in self.map.flag_homes] if self.mode == "ctf" else []
        # Zone Defense: one entry per zone: [x, y, owner team or -1, pid capturing or -1, seconds of progress]
        self.cps = []
        if self.mode == "zones":
            self.cps = [[x, y, -1, -1, 0.0] for x, y in self.map.zone_points]
            self.cps[0][2], self.cps[-1][2] = 0, 1        # each side starts holding the zone outside its base
            self._count_zones()
        # the other game types (see modes.py) plug in through `rules`
        self.ffa = False           # every player is their own team
        self.structs = []          # headquarters / convoy truck: [kind, team, x, y, radius, hp, max hp, angle]
        self.ms = {}               # the game type's own state; shared with clients and saved battles
        self.winner_pid = None     # set when a single player (not a team) wins
        self.rules = modes.make(self)

    # -- players -----------------------------------------------------------------
    def add_player(self, loadout, team, is_ai=False, skill=1, pid=None):
        if pid is None:
            pid = self._next_pid
        self._next_pid = max(self._next_pid, pid) + 1
        if self.rules:
            team = self.rules.assign_team(team, pid, is_ai)
        t = Tank(pid, loadout, team, is_ai, skill)
        self.players[pid] = t
        return t

    def remove_player(self, pid):
        t = self.players.pop(pid, None)
        if t and t.flag >= 0 and self.flags:
            self._drop_flag(t)

    def team_count(self, team):
        return sum(1 for t in self.players.values() if t.team == team)

    # -- shop ----------------------------------------------------------------------
    def buy(self, pid, kind, key):
        t = self.players.get(pid)
        if not t:
            return False
        if kind == "tank" and key in TANK_INDEX and key not in t.tanks:
            cost = TANKS[TANK_INDEX[key]]["cost"]
            if t.credits >= cost:
                t.credits -= cost
                t.tanks.append(key)
                return True
        if kind == "upgrade":
            tank_key, _, which = str(key).partition(":")
            if tank_key not in t.tanks or which not in ("0", "1", "2"):
                return False
            k = int(which)
            lv = list(t.upgrades.get(tank_key, [0] * len(data.UPGRADES)))
            if lv[k] >= data.UPGRADE_MAX:
                return False
            cost = data.upgrade_cost(tank_key, lv[k] + 1)
            if t.credits < cost:
                return False
            t.credits -= cost
            lv[k] += 1
            t.upgrades[tank_key] = lv
            if tank_key == t.tank_key:                 # takes effect at once on the tank in use
                frac = t.hp / t.max_hp if t.max_hp else 1.0
                t.max_hp = data.tank_hp(t.spec) * (1 + data.UPGRADES[1][2] * t.up(1))
                if t.alive:
                    t.hp = t.max_hp * frac
            return True
        if kind == "weapon" and key in WEAPON_INDEX and key not in t.weapons:
            cost = WEAPONS[WEAPON_INDEX[key]]["cost"]
            if t.credits >= cost:
                t.credits -= cost
                t.weapons.append(key)
                t.set_tank(t.tank_key)       # may unlock a better default weapon
                return True
        return False

    def select_tank(self, pid, key):
        """Switch to another owned tank. Mid-battle the new tank keeps the old one's damage percentage."""
        t = self.players.get(pid)
        if not t or key not in t.tanks or key == t.tank_key or not data.usable(key, t.weapons):
            return False
        if self.rules and not self.rules.can_swap(t):
            return False
        t.own_tank = key
        frac = t.hp / t.max_hp if t.alive else 1.0
        t.set_tank(key)
        if t.alive:
            t.hp = max(1.0, t.max_hp * frac)
            t.lockout = 1.5
            t.speed = 0.0
            self.events.append(("swap", pid, t.x, t.y))
            if self.map.blocked_circle(t.x, t.y, t.radius):     # a bigger tank may not fit where we stand
                self._nudge_free(t)
        return True

    def select_weapon(self, pid, slot, idx):
        t = self.players.get(pid)
        if t and idx in t.usable(slot):
            t.sel[slot] = idx
            return True
        return False

    def _nudge_free(self, t):
        for r in range(20, 400, 20):
            for i in range(12):
                a = i * math.pi / 6
                x, y = t.x + math.cos(a) * r, t.y + math.sin(a) * r
                if not self.map.blocked_circle(x, y, t.radius):
                    t.x, t.y = x, y
                    return

    # -- main step --------------------------------------------------------------------
    def step(self, dt):
        if self.over is not None:
            self._step_projectiles(dt)
            return
        self.time += dt
        if self.ai:
            self.ai.update(dt)
        tanks = list(self.players.values())
        for t in tanks:
            if t.alive:
                self._move(t, dt)
                self._shoot(t, dt)
            elif not t.out:
                t.respawn -= dt
                if t.respawn <= 0:
                    self._spawn(t)
        self._separate(tanks)
        self._step_projectiles(dt)
        self._step_zones(dt)
        if self.flags and self.over is None:
            self._step_flags(dt)
        if self.mode == "zones" and self.over is None:
            self._step_cps(dt)
        if self.rules and self.over is None:
            self.rules.step(dt)
        if self.map.nav_dirty and self.time - self._nav_time > 2.0:     # let the AI use freshly cleared ground
            self._nav_time = self.time
            self.map.rebuild_nav()
        limit = self.settings["time_limit"]
        if limit and self.time >= limit and self.over is None and not (self.rules and self.rules.own_clock):
            if not (self.rules and self.rules.time_up()):
                a, b = self.scores[0], self.scores[1]
                self._finish(0 if a > b else 1 if b > a else -1)

    def _spawn(self, t):
        pts = self.map.spawns[t.team % 2]
        enemies = [e for e in self.players.values() if e.alive and e.team != t.team]
        mates = [e for e in self.players.values() if e.alive and e is not t]
        best, best_score = (self.rules.spawn_point(t) if self.rules else None), -1e9
        for _ in range(14 if best is None else 0):
            x, y = self.rng.choice(pts)
            near_mate = min((math.hypot(e.x - x, e.y - y) for e in mates), default=1e4)
            if near_mate < 130:
                continue
            near_enemy = min((math.hypot(e.x - x, e.y - y) for e in enemies), default=1e4)
            score = min(near_enemy, 2500) + min(near_mate, 400) + self.rng.uniform(0, 300)
            if score > best_score:
                best, best_score = (x, y), score
        if best is None:
            t.respawn = 0.3
            return
        if t.is_ai and self.ai:
            self.ai.shop(t)
        t.x, t.y = best
        t.angle = t.turret = t.aim = 0.0 if t.team == 0 else math.pi
        if self.ffa:
            t.angle = t.turret = t.aim = math.atan2(self.map.h / 2 - best[1], self.map.w / 2 - best[0]) % TAU
        t.hp = t.max_hp
        t.alive = True
        t.speed = 0.0
        t.shield = data.SPAWN_SHIELD
        t.lockout = 0.0
        t.cool = {}
        t.last_hit_by = -1
        self.events.append(("spawn", t.pid, t.x, t.y))

    def _move(self, t, dt):
        spec = t.spec
        engine = 1 + data.UPGRADES[0][2] * t.up(0)
        vmax = data.tank_speed(spec) * engine
        if self.map.shallow_at(t.x, t.y):
            vmax *= 0.55
        if t.flag >= 0:
            vmax *= data.FLAG_CARRIER_SPEED
        thr = max(-1.0, min(1.0, t.throttle))
        target = thr * vmax * (1.0 if thr >= 0 else 0.6)
        rate = vmax * (3.5 if abs(target) < abs(t.speed) or target * t.speed < 0 else 1.8) * dt
        if t.speed < target:
            t.speed = min(target, t.speed + rate)
        else:
            t.speed = max(target, t.speed - rate)
        t.angle = (t.angle + max(-1.0, min(1.0, t.turn)) * math.radians(spec["turn"]) * engine * dt) % TAU
        t.turret = turn_toward(t.turret, t.aim, math.radians(spec["traverse"]) * dt) % TAU
        if t.speed:
            dx = math.cos(t.angle) * t.speed * dt
            dy = math.sin(t.angle) * t.speed * dt
            m = self.map
            r = t.radius
            self._crush(t, t.x + dx, t.y + dy)
            if not m.blocked_circle(t.x + dx, t.y + dy, r):
                t.x += dx
                t.y += dy
            elif not m.blocked_circle(t.x + dx, t.y, r):
                t.x += dx
                t.speed *= 0.9
            elif not m.blocked_circle(t.x, t.y + dy, r):
                t.y += dy
                t.speed *= 0.9
            else:
                t.speed = 0.0
        if t.shield > 0:
            t.shield -= dt
        if t.lockout > 0:
            t.lockout -= dt
        if t.recoil > 0:
            t.recoil = max(0.0, t.recoil - dt * 4)
        for k in t.cool:
            if t.cool[k] > 0:
                t.cool[k] -= dt

    def _crush(self, t, x, y):
        """Flatten bushes under the tank; Heavy tanks and bigger also knock down trees in their way."""
        cells = self.map.crushables
        if not cells:
            return
        r = t.radius
        trees = t.spec["crush_trees"]
        gx, gy = int(x) // CRUSH_CELL, int(y) // CRUSH_CELL
        for cy in (gy - 1, gy, gy + 1):
            for cx in (gx - 1, gx, gx + 1):
                for idx, ox, oy, is_tree in cells.get((cx, cy), ()):
                    if idx in self.crushed or (is_tree and not trees):
                        continue
                    reach = r + 16 if is_tree else r * 0.8
                    if (ox - x) ** 2 + (oy - y) ** 2 < reach * reach:
                        self.crush(idx, emit=not self.mirror)
                        if is_tree:
                            t.speed *= 0.6

    def crush(self, idx, emit=True):
        if idx in self.crushed or not (0 <= idx < len(self.map.objects)):
            return
        o = self.map.objects[idx]
        if o["kind"] not in ("bush", "tree"):
            return
        self.crushed.add(idx)
        if o["kind"] == "tree":
            self.map.remove_tree(idx)
        if emit:
            self.events.append(("crush", idx))

    def _separate(self, tanks):
        alive = [t for t in tanks if t.alive]
        m = self.map
        for i, a in enumerate(alive):
            for b in alive[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                rr = a.radius + b.radius - 6
                if abs(dx) < rr and abs(dy) < rr:
                    d = math.hypot(dx, dy)
                    if d < rr:
                        if d < 0.01:
                            dx, dy, d = 1.0, 0.0, 1.0
                        push = (rr - d) / 2
                        nx, ny = dx / d * push, dy / d * push
                        if not m.blocked_circle(a.x - nx, a.y - ny, a.radius):
                            a.x -= nx
                            a.y -= ny
                        if not m.blocked_circle(b.x + nx, b.y + ny, b.radius):
                            b.x += nx
                            b.y += ny
        for s in self.structs:                      # buildings and the truck do not give way
            if s[5] <= 0 and s[0] != "hq":
                continue
            for a in alive:
                dx, dy = a.x - s[2], a.y - s[3]
                rr = a.radius + s[4] - 4
                if abs(dx) < rr and abs(dy) < rr:
                    d = math.hypot(dx, dy) or 1.0
                    if d < rr:
                        nx, ny = dx / d * (rr - d), dy / d * (rr - d)
                        if not m.blocked_circle(a.x + nx, a.y + ny, a.radius):
                            a.x += nx
                            a.y += ny

    # -- weapons ------------------------------------------------------------------------
    def reload_time(self, t, w):
        loader = 1 - data.UPGRADES[2][2] * t.up(2)
        if w["slot"] == AUTO:
            return loader / (w["rate"] * (1 + 0.35 * (len(t.art["muzzles"]) - 1)))
        return w["reload"] * loader     # cannons fire every barrel at once instead of reloading faster

    def _shoot(self, t, dt):
        if t.lockout > 0:
            return
        aimed = t.aim_dist is not None
        if aimed and abs(angle_diff(t.aim, t.turret)) > data.FIRE_ARC:
            return                      # hold fire until the gun has swung onto the cursor
        for slot in (SHELL, AUTO):
            wi = t.sel[slot]
            if not t.fire[slot] or wi < 0 or t.cool.get(wi, 0) > 0:
                continue
            w = WEAPONS[wi]
            t.cool[wi] = self.reload_time(t, w)
            t.shield = 0.0
            if slot == SHELL:
                t.recoil = 1.0
                barrels = range(len(t.art["muzzles"]))      # a cannon shot is one shell from every barrel
            else:
                barrels = (t.barrel,)                       # machine guns alternate barrels
                t.barrel += 1
            for barrel in barrels:
                mx, my = t.muzzle(barrel)
                # A player's shot goes from the muzzle to the exact spot the cursor was on. Shells burst there
                # (or at maximum range, whichever comes first); bullets pass through it and keep going.
                base, reach = t.turret, w["range"]
                if aimed:
                    px, py = t.pivot()
                    tx, ty = px + math.cos(t.aim) * t.aim_dist, py + math.sin(t.aim) * t.aim_dist
                    d = math.hypot(tx - mx, ty - my)
                    if t.aim_dist > math.hypot(mx - px, my - py) + 20 and d > 20:
                        base = math.atan2(ty - my, tx - mx)
                        if slot == SHELL and w["pellets"] == 1:
                            reach = min(reach, d)
                n = w["pellets"]
                for k in range(n):
                    if n > 1:
                        ang = base + math.radians(w["spread"]) * ((k - (n - 1) / 2) / ((n - 1) / 2))
                        ang += self.rng.uniform(-0.03, 0.03)
                    else:
                        ang = base + math.radians(self.rng.uniform(-w["spread"], w["spread"]))
                    self.spawn_projectile(t.pid, t.team, wi, mx, my, ang, reach=reach)

    def spawn_projectile(self, pid, team, wi, x, y, ang, proj_id=None, reach=None):
        w = WEAPONS[wi]
        if proj_id is None:
            proj_id = self._next_proj
            self._next_proj += 1
            self.events.append(("shot", pid, wi, round(x, 1), round(y, 1), round(ang, 4), proj_id))
        # [id, owner, team, weapon, x, y, vx, vy, range left, angle]
        self.projectiles[proj_id] = [proj_id, pid, team, wi, x, y, math.cos(ang) * w["speed"],
                                     math.sin(ang) * w["speed"], w["range"] if reach is None else reach, ang]

    def _step_projectiles(self, dt):
        if not self.projectiles:
            return
        m = self.map
        targets = [t for t in self.players.values() if t.alive] if not self.mirror else []
        dead = []
        for p in self.projectiles.values():
            dist = WEAPONS[p[3]]["speed"] * dt
            steps = int(dist / 14.0) + 1
            sx, sy = p[6] * dt / steps, p[7] * dt / steps
            seg = dist / steps
            hit = None
            for _ in range(steps):
                p[4] += sx
                p[5] += sy
                p[8] -= seg
                x, y = p[4], p[5]
                if m.shot_blocked_at(x, y):
                    hit = ("wall", None)
                    break
                for t in targets:
                    if t.team != p[2]:
                        dx, dy = t.x - x, t.y - y
                        r = t.radius * 0.92
                        if -r < dx < r and -r < dy < r and dx * dx + dy * dy < r * r:
                            hit = ("tank", t)
                            break
                if not hit:
                    for s in self.structs:
                        if s[1] != p[2] and s[5] > 0:
                            dx, dy = s[2] - x, s[3] - y
                            if dx * dx + dy * dy < s[4] * s[4]:
                                hit = ("struct", s)
                                break
                if hit:
                    break
                if p[8] <= 0:
                    over = p[8] / (seg or 1.0)          # step back onto the exact end point
                    p[4] += sx * over
                    p[5] += sy * over
                    hit = ("ground", None) if WEAPONS[p[3]]["slot"] == SHELL else ("fade", None)
                    break
            if hit:
                dead.append(p[0])
                if not self.mirror:
                    self._impact(p, *hit)
        for i in dead:
            self.projectiles.pop(i, None)

    def _impact(self, p, kind, victim):
        wi = p[3]
        w = WEAPONS[wi]
        x, y = p[4], p[5]
        if kind == "fade":
            return
        self.events.append(("hit", p[0], round(x, 1), round(y, 1), wi, kind))
        owner = self.players.get(p[1])
        owner_team = p[2]
        if kind == "struct":
            self._damage_struct(victim, w["hit"], p[1])
        elif victim:
            self._damage(victim, w["hit"], p[1], owner_team, wi)
        if w["splash"]:
            sr = w["splash"]
            for s in self.structs:
                if s is victim or s[5] <= 0 or (s[1] == owner_team and not w["hurts_all"]):
                    continue
                d = math.hypot(s[2] - x, s[3] - y) - s[4]
                if d < sr:
                    self._damage_struct(s, w["hit"] * w["splash_frac"] * (0.2 + 0.8 * (1.0 - max(0.0, d) / sr)),
                                        p[1])
            for t in list(self.players.values()):
                if not t.alive or t is victim:
                    continue
                if t.team == owner_team and not w["hurts_all"]:
                    continue
                d = math.hypot(t.x - x, t.y - y) - t.radius * 0.5
                if d < sr:
                    frac = 1.0 - max(0.0, d) / sr
                    amount = w["hit"] * w["splash_frac"] * (0.2 + 0.8 * frac)
                    self._damage(t, amount, p[1], owner_team, wi)
        if w["zone"]:
            zk, zr, zt, zdps = w["zone"]
            self.zones.append([self._next_zone, zk, x, y, zr, zt, zdps, p[1], owner_team])
            self._next_zone += 1

    def _damage(self, t, amount, attacker_pid, attacker_team, wi):
        if not t.alive or t.shield > 0 or self.over is not None:
            return
        if t.flag >= 0:
            amount *= data.FLAG_CARRIER_ARMOR
        if self.rules:
            amount *= self.rules.damage_scale(t)
        t.hp -= amount
        if attacker_pid != t.pid:
            t.last_hit_by = attacker_pid
        if t.hp <= 0:
            self._kill(t, attacker_pid, attacker_team, wi)

    def _damage_struct(self, s, amount, attacker_pid):
        if self.over is not None or s[5] <= 0:
            return
        s[5] -= amount
        self.ms["hit%d" % (s[1] % 2)] = round(self.time, 1)
        if s[5] <= 0:
            s[5] = 0.0
            self.events.append(("sdead", self.structs.index(s), round(s[2]), round(s[3])))
            if self.rules:
                self.rules.on_struct_destroyed(s, attacker_pid)

    def _kill(self, t, attacker_pid, attacker_team, wi):
        t.alive = False
        t.hp = 0.0
        t.deaths += 1
        t.respawn = data.CTF_RESPAWN_TIME if self.flags else \
            (self.rules.respawn_time(t) if self.rules else data.RESPAWN_TIME)
        t.fire = [False, False]
        killer = self.players.get(attacker_pid)
        if attacker_pid == t.pid or attacker_team == t.team:
            # own goal (fire, fallout, nuke): credit the last enemy who hurt this tank, if any
            k2 = self.players.get(t.last_hit_by)
            killer = k2 if (k2 and k2.team != t.team) else None
        reward = 0
        if killer and killer.team != t.team:
            reward = t.spec["reward"]
            killer.kills += 1
            killer.credits += reward
            killer.earned += reward
            if self.mode == "tdm":
                self.scores[killer.team] += 1
        if t.flag >= 0:
            self._drop_flag(t)
        if self.flags:
            if t.respawns > 0:
                t.respawns -= 1
            else:
                t.out = True
        self.events.append(("kill", killer.pid if killer else -1, t.pid, wi, round(t.x, 1), round(t.y, 1),
                            round(t.angle, 3), t.tank_key, reward))
        if self.rules and self.over is None:
            self.rules.on_kill(t, killer)
        limit = self.settings["kill_limit"]
        if self.mode == "tdm" and limit and killer and self.scores[killer.team] >= limit:
            self._finish(killer.team)
        if t.out:
            self.events.append(("out", t.pid))
            if self.flags:
                self._check_eliminated()

    def _check_eliminated(self):
        """Capture the Flag: a team with nobody left to field loses on the spot."""
        gone = [all(p.out for p in self.players.values() if p.team == team) and self.team_count(team) > 0
                for team in (0, 1)]
        if gone[0] and gone[1]:
            self._finish(-1)
        elif gone[0]:
            self._finish(1)
        elif gone[1]:
            self._finish(0)

    # -- Zone Defense ----------------------------------------------------------------------
    def _count_zones(self):
        self.scores = [sum(1 for c in self.cps if c[2] == team) for team in (0, 1)]

    def _step_cps(self, dt):
        """A tank inside a zone it does not own captures it by holding the capture key for 5 seconds.
        Progress only advances while no enemy tank is inside; leaving, letting go or dying starts it over."""
        r2 = data.ZONE_RADIUS ** 2
        alive = [t for t in self.players.values() if t.alive]
        for i, c in enumerate(self.cps):
            inside = [t for t in alive if (t.x - c[0]) ** 2 + (t.y - c[1]) ** 2 < r2]
            cap = self.players.get(c[3])
            if cap is not None and not (cap in inside and cap.hold and cap.team != c[2]):
                cap = None
            if cap is None:
                c[3], c[4] = -1, 0.0
                for t in sorted(inside, key=lambda t: t.pid):
                    if t.hold and t.team != c[2]:
                        cap = t
                        c[3] = t.pid
                        break
                if cap is None:
                    continue
            if any(t.team != cap.team for t in inside):
                continue                                  # contested: the clock stops until they are driven out
            c[4] += dt
            if c[4] >= data.ZONE_CAPTURE_TIME:
                c[2], c[3], c[4] = cap.team, -1, 0.0
                cap.credits += data.ZONE_REWARD
                cap.earned += data.ZONE_REWARD
                self._count_zones()
                self.events.append(("zone", "captured", i, cap.pid))
                if self.scores[cap.team] == len(self.cps):
                    self._finish(cap.team)                # holding every zone wins on the spot
                    return

    # -- Capture the Flag ----------------------------------------------------------------
    def _drop_flag(self, t):
        f = self.flags[t.flag]
        f[0], f[1], f[2], f[3], f[4] = FLAG_DROPPED, t.x, t.y, -1, data.FLAG_RETURN_TIME
        self.events.append(("flag", "dropped", t.flag, t.pid))
        t.flag = -1

    def _send_home(self, team):
        f = self.flags[team]
        f[0], f[1], f[2] = FLAG_HOME, self.map.flag_homes[team][0], self.map.flag_homes[team][1]
        f[3], f[4] = -1, 0.0

    def _step_flags(self, dt):
        """Pick up, carry, capture, drop and return. A flag belongs to team `ft`; the other team steals it."""
        alive = [t for t in self.players.values() if t.alive]
        for ft, f in enumerate(self.flags):
            if f[0] == FLAG_CARRIED:
                c = self.players.get(f[3])
                if c is None or not c.alive or c.flag != ft:
                    f[0], f[3], f[4] = FLAG_DROPPED, -1, data.FLAG_RETURN_TIME
                    continue
                f[1], f[2] = c.x, c.y
                own = self.flags[c.team]
                hx, hy = self.map.flag_homes[c.team]
                reach = c.radius + 34
                if own[0] == FLAG_HOME and (c.x - hx) ** 2 + (c.y - hy) ** 2 < reach * reach:
                    c.flag = -1
                    self._send_home(ft)
                    self.scores[c.team] += 1
                    c.credits += data.CAPTURE_REWARD
                    c.earned += data.CAPTURE_REWARD
                    self.events.append(("flag", "captured", ft, c.pid))
                    limit = self.settings["cap_limit"]
                    if limit and self.scores[c.team] >= limit:
                        self._finish(c.team)
                        return
                continue
            if f[0] == FLAG_DROPPED:
                f[4] -= dt
                if f[4] <= 0:
                    self._send_home(ft)
                    self.events.append(("flag", "returned", ft, -1))
                    continue
            for t in alive:
                reach = t.radius + 34
                if (t.x - f[1]) ** 2 + (t.y - f[2]) ** 2 >= reach * reach:
                    continue
                if t.team != ft and t.flag < 0:
                    f[0], f[3] = FLAG_CARRIED, t.pid
                    t.flag = ft
                    self.events.append(("flag", "taken", ft, t.pid))
                    break
                if t.team == ft and f[0] == FLAG_DROPPED:
                    self._send_home(ft)
                    t.credits += data.RETURN_REWARD
                    t.earned += data.RETURN_REWARD
                    self.events.append(("flag", "returned", ft, t.pid))
                    break

    def _step_zones(self, dt):
        if not self.zones:
            return
        keep = []
        for z in self.zones:
            z[5] -= dt
            if z[5] <= 0:
                continue
            keep.append(z)
            _, kind, x, y, r, _, dps, owner, team = z
            for t in list(self.players.values()):
                if t.alive and math.hypot(t.x - x, t.y - y) < r + t.radius * 0.4:
                    self._damage(t, dps * dt, owner, team, WEAPON_INDEX["combust_shell" if kind == "fire"
                                                                        else "nuke_shell"])
            for s in self.structs:
                if s[5] > 0 and math.hypot(s[2] - x, s[3] - y) < r + s[4] * 0.5:
                    self._damage_struct(s, dps * dt, owner)
        self.zones = keep

    def won(self, t):
        """Did this player win? (Individually scored game types name one player, the others a team.)"""
        if self.over is None or t is None:
            return False
        return t.pid == self.winner_pid if self.winner_pid is not None else t.team == self.over

    def finish(self, winner, pid=None):
        self._finish(winner, pid)

    def note(self, text, team=-1, pid=-1):
        """A headline for everyone's screen. It is good news for `team` (or for player `pid`)."""
        self.events.append(("note", text, team, pid))

    def reset_round(self):
        """Clear the field and put every tank back at its base (round-based game types)."""
        self.projectiles.clear()
        self.zones = []
        for t in self.players.values():
            t.alive = False
            t.out = False
            t.respawn = 0.0
            t.fire = [False, False]
        self.events.append(("reset",))

    def _finish(self, winner, pid=None):
        if self.over is not None:
            return
        self.over = winner
        self.winner_pid = pid
        for t in self.players.values():
            bonus = data.WIN_BONUS if self.won(t) else data.LOSS_BONUS
            t.credits += bonus
            t.earned += bonus
            t.fire = [False, False]
            t.throttle = t.turn = 0.0
        self.events.append(("over", winner))

    # -- snapshots (network + interpolation) ----------------------------------------------
    def snapshot(self):
        tk = []
        for t in self.players.values():
            tk.append([t.pid, 1 if t.alive else 0, round(t.x, 1), round(t.y, 1), round(t.angle, 3),
                       round(t.turret, 3), round(t.hp, 1), TANK_INDEX[t.tank_key], 1 if t.shield > 0 else 0,
                       t.sel[0], t.sel[1], round(max(0.0, t.respawn), 1), t.kills, t.deaths,
                       round(t.speed, 0), -1 if t.out else t.respawns, t.points, round(t.max_hp, 1)])
        zn = [[z[0], z[1], round(z[2]), round(z[3]), z[4], round(z[5], 1)] for z in self.zones]
        fl = [[f[0], round(f[1]), round(f[2]), f[3], round(f[4], 1)] for f in self.flags]
        cp = [[c[2], c[3], round(c[4], 2)] for c in self.cps]
        st = [[s[1], round(s[2], 1), round(s[3], 1), round(s[5], 1), round(s[7], 3)] for s in self.structs]
        return dict(time=round(self.time, 3), sc=[round(v, 1) for v in self.scores], over=self.over, tk=tk, zn=zn,
                    fl=fl, cp=cp, st=st, ms=self.ms, wp=self.winner_pid)

    def apply_mode(self, msg):
        """Client side: structures, the game type's state and the individual winner from the host."""
        for s, (team, x, y, hp, ang) in zip(self.structs, msg.get("st", ())):
            s[1], s[2], s[3], s[5], s[7] = team, x, y, hp, ang
        if "ms" in msg:
            self.ms = msg["ms"]
        self.winner_pid = msg.get("wp")

    def apply_cps(self, cp):
        """Client side: take zone ownership and capture progress from the host."""
        for c, (owner, pid, progress) in zip(self.cps, cp):
            c[2], c[3], c[4] = owner, pid, progress

    def apply_flags(self, fl):
        """Client side: take the flag state from the host."""
        self.flags = [list(f) for f in fl]
        for t in self.players.values():
            t.flag = -1
        for team, f in enumerate(self.flags):
            c = self.players.get(f[3])
            if f[0] == FLAG_CARRIED and c:
                c.flag = team

    def roster(self):
        return [[t.pid, t.name, list(t.color), t.team, 1 if t.is_ai else 0] for t in self.players.values()]

    def apply_roster(self, roster):
        seen = set()
        for pid, name, color, team, is_ai in roster:
            seen.add(pid)
            t = self.players.get(pid)
            if t is None:
                t = self.add_player(dict(name=name, color=color), team, bool(is_ai), pid=pid)
            t.name, t.color, t.team, t.is_ai = name, tuple(color), team, bool(is_ai)
        for pid in list(self.players):
            if pid not in seen:
                del self.players[pid]

    # -- saving a single-player battle -------------------------------------------------------
    def to_dict(self):
        ps = []
        for t in self.players.values():
            ps.append(dict(pid=t.pid, loadout=t.state(), team=t.team, is_ai=t.is_ai, skill=t.skill, kills=t.kills,
                           deaths=t.deaths, earned=t.earned, alive=t.alive, respawn=t.respawn, x=t.x, y=t.y,
                           respawns=t.respawns, out=t.out, points=t.points, temp=t.temp, own_tank=t.own_tank,
                           full=[list(t.tanks), list(t.weapons), t.tank_key],
                           angle=t.angle, turret=t.turret, hp=t.hp, sel=t.sel))
        return dict(settings=self.settings, time=self.time, scores=self.scores, players=ps,
                    zones=self.zones, crushed=sorted(self.crushed), flags=self.flags,
                    cps=[c[2:] for c in self.cps], structs=self.structs, ms=self.ms)

    @classmethod
    def from_dict(cls, d):
        w = cls(d["settings"])
        w.time = d["time"]
        w.scores = list(d["scores"])
        w.zones = [list(z) for z in d.get("zones", [])]
        for idx in d.get("crushed", []):
            w.crush(int(idx), emit=False)
        if w.cps and d.get("cps"):
            w.apply_cps(d["cps"])
            w._count_zones()
        if w.flags and d.get("flags"):
            w.flags = [list(f) for f in d["flags"]]
        if w.map.nav_dirty:
            w.map.rebuild_nav()
        for p in d["players"]:
            t = w.add_player(p["loadout"], p["team"], p["is_ai"], p["skill"], pid=p["pid"])
            t.kills, t.deaths, t.earned = p["kills"], p["deaths"], p["earned"]
            t.alive, t.respawn = p["alive"], p["respawn"]
            t.respawns, t.out = p.get("respawns", data.CTF_RESPAWNS), p.get("out", False)
            t.team = p["team"]
            t.points, t.own_tank = p.get("points", 0), p.get("own_tank", t.tank_key)
            if p.get("temp"):                       # items on loan from the game type (the Juggernaut's Goliath)
                t.temp = [list(i) for i in p["temp"]]
                t.tanks, t.weapons = list(p["full"][0]), list(p["full"][1])
                t.set_tank(p["full"][2])
            t.x, t.y, t.angle, t.turret, t.hp = p["x"], p["y"], p["angle"], p["turret"], p["hp"]
            t.aim = t.turret
            for slot in (0, 1):
                if p["sel"][slot] in t.usable(slot):
                    t.sel[slot] = p["sel"][slot]
        if w.flags:
            w.apply_flags(w.flags)
        if d.get("structs") and len(d["structs"]) == len(w.structs):
            w.structs = [list(s) for s in d["structs"]]
        if d.get("ms"):
            w.ms = d["ms"]
        if w.rules:
            w.rules.after_load()
            w.rules.restrict()
        return w
