"""Rules for the game types that need more than the core simulation provides.

Team Deathmatch, Capture the Flag and Zone Defense live in world.py; everything here plugs into the World
through a small set of hooks. Each rule set keeps its state in `world.ms` (plain JSON data), which is sent to
multiplayer clients and written into saved battles, so the same object can drive the HUD on a client's mirror.

World "structures" (headquarters, the convoy truck) are lists: [kind, team, x, y, radius, hp, max hp, angle].
"""
import math

from . import data

GOLD, GOOD, BAD, PLAIN = "gold", "good", "bad", "plain"


class Rules:
    individual = False      # scored per player rather than per team
    own_clock = False       # True if the rule set ignores the battle's time limit
    out_text = "No respawns left."

    def __init__(self, world):
        self.w = world
        self.setup()

    # -- hooks, all optional -------------------------------------------------------
    def setup(self):
        """Create zones / structures. Runs on the host and on client mirrors, so it must be deterministic."""

    def after_load(self):
        """Rebuild anything not stored in world.ms after a saved battle is loaded."""

    def restrict(self):
        """Apply any limits on what players may drive and fire (Tank.allow). Also run on client mirrors."""

    def assign_team(self, team, pid, is_ai):
        return team

    def step(self, dt):
        pass

    def on_kill(self, victim, killer):
        pass

    def on_struct_destroyed(self, s, attacker_pid):
        pass

    def damage_scale(self, t):
        return 1.0

    def spawn_point(self, t):
        return None

    def respawn_time(self, t):
        return data.RESPAWN_TIME

    def can_swap(self, t):
        return True

    def time_up(self):
        """Return True if the rule set decided the winner itself."""
        return False

    def hud(self, me):
        w = self.w
        return str(w.scores[0]), str(w.scores[1]), ""

    def hints(self, me):
        return []

    def title(self, me):
        return None

    def marks(self):
        """pid -> label for tanks that should be highlighted."""
        return {}

    # -- AI ------------------------------------------------------------------------------
    def ai_goal(self, ai, t, alive, target):
        return None

    def ai_struct(self, t):
        return -1

    def ai_priority(self, t, e):
        return False

    # -- helpers -----------------------------------------------------------------------------
    def limit(self, key, default):
        return self.w.settings.get(key, default) or 0

    def top_player(self, key):
        """(best, runner-up is tied) by a per-player score function."""
        ps = sorted(self.w.players.values(), key=key, reverse=True)
        if not ps:
            return None, False
        return ps[0], len(ps) > 1 and key(ps[1]) == key(ps[0])


# ---------------------------------------------------------------------------------------------
class KingOfTheHill(Rules):
    """One zone in the middle. A team scores one point per second while it is the only team inside."""

    def setup(self):
        x, y = self.w.map.zone_points[2]
        self.w.cps = [[x, y, -1, -1, 0.0]]
        self.w.scores = [0.0, 0.0]

    def _inside(self, t):
        c = self.w.cps[0]
        return t.alive and (t.x - c[0]) ** 2 + (t.y - c[1]) ** 2 < data.ZONE_RADIUS ** 2

    def step(self, dt):
        w = self.w
        teams = {t.team for t in w.players.values() if self._inside(t)}
        c = w.cps[0]
        if len(teams) == 1:
            team = teams.pop()
            if c[2] != team:
                c[2] = team
                w.note("%s holds the hill" % data.TEAM_NAMES[team], team)
            w.scores[team] += dt
            goal = self.limit("score_limit", 100)
            if goal and w.scores[team] >= goal:
                w.finish(team)
        else:
            c[2] = -1

    def hud(self, me):
        w = self.w
        return "%d" % w.scores[0], "%d" % w.scores[1], "seconds on the hill - first to %d" % self.limit("score_limit", 100)

    def hints(self, me):
        w = self.w
        if not me.alive:
            return []
        c = w.cps[0]
        if self._inside(me):
            foes = any(self._inside(t) and t.team != me.team for t in w.players.values())
            return [("Contested - drive them off the hill!", BAD)] if foes else [("Your team holds the hill", GOOD)]
        return [("Enemy holds the hill - take it back!", BAD)] if c[2] not in (-1, me.team) else []

    def ai_goal(self, ai, t, alive, target):
        c = self.w.cps[0]
        return "cp0", (c[0], c[1]), False


# ---------------------------------------------------------------------------------------------
class FreeForAll(Rules):
    """No teams. Every player is a team of one; first to the kill target wins."""
    individual = True

    def setup(self):
        self.w.ffa = True

    def assign_team(self, team, pid, is_ai):
        return pid

    def spawn_point(self, t):
        w = self.w
        others = [e for e in w.players.values() if e.alive and e is not t]
        best, score = None, -1.0
        for _ in range(18):
            x, y = w.rng.choice(w.map.ffa_spawns)
            near = min([math.hypot(e.x - x, e.y - y) for e in others] or [9e9])
            if near > score:
                best, score = (x, y), near
        return best

    def on_kill(self, victim, killer):
        if killer:
            killer.points = killer.kills
            goal = self.limit("kill_limit", 20)
            if goal and killer.kills >= goal:
                self.w.finish(killer.team, killer.pid)

    def time_up(self):
        best, tied = self.top_player(lambda t: t.kills)
        self.w.finish(-1 if (tied or best is None) else best.team, None if (tied or best is None) else best.pid)
        return True

    def hud(self, me):
        rival = max([t.kills for t in self.w.players.values() if t is not me] or [0])
        return str(me.kills if me else 0), str(rival), "you / best rival - first to %d kills" % self.limit("kill_limit", 20)

    def ai_goal(self, ai, t, alive, target):
        if target is None:
            return None
        return "ffa%d" % target.pid, (target.x, target.y), False


# ---------------------------------------------------------------------------------------------
class LastTeamStanding(Rules):
    """No respawns. Wipe out the other side to win the round; first to the round target wins the battle."""
    out_text = "You are out until the next round."
    ROUND_CAP = 180.0

    def setup(self):
        self.w.ms.update(round=1, phase="play", t=0.0, brk=0.0)

    def step(self, dt):
        w, ms = self.w, self.w.ms
        if ms["phase"] == "break":
            ms["brk"] -= dt
            if ms["brk"] <= 0:
                ms.update(round=ms["round"] + 1, phase="play", t=0.0)
                w.reset_round()
            return
        ms["t"] += dt
        if ms["t"] >= self.ROUND_CAP:               # stalemate: whoever has more tanks left takes the round
            left = [sum(1 for p in w.players.values() if p.team == team and not p.out) for team in (0, 1)]
            self._round_over(0 if left[0] > left[1] else 1 if left[1] > left[0] else -1)

    def on_kill(self, victim, killer):
        w = self.w
        victim.out = True
        if w.ms["phase"] != "play":
            return
        left = [sum(1 for p in w.players.values() if p.team == team and not p.out) for team in (0, 1)]
        if left[0] == 0 or left[1] == 0:
            self._round_over(-1 if left[0] == left[1] else (0 if left[0] else 1))

    def _round_over(self, team):
        w = self.w
        if team >= 0:
            w.scores[team] += 1
            w.note("%s wins round %d" % (data.TEAM_NAMES[team], w.ms["round"]), team)
            if w.scores[team] >= self.limit("rounds", 3):
                w.finish(team)
                return
        else:
            w.note("Round %d is a draw" % w.ms["round"])
        w.ms.update(phase="break", brk=4.0)

    def hud(self, me):
        w = self.w
        return str(w.scores[0]), str(w.scores[1]), "round %d - first to %d rounds" % (w.ms["round"], self.limit("rounds", 3))

    def hints(self, me):
        w = self.w
        if w.ms["phase"] == "break":
            return [("Next round in %d" % math.ceil(max(0.0, w.ms["brk"])), PLAIN)]
        left = [sum(1 for p in w.players.values() if p.team == team and not p.out) for team in (0, 1)]
        return [("%d left on your side   -   %d enemies left" % (left[me.team % 2], left[1 - me.team % 2]), PLAIN)]


# ---------------------------------------------------------------------------------------------
class BaseAssault(Rules):
    """Each team has a headquarters. Destroy the enemy's to win."""
    HP = 500.0

    def setup(self):
        w = self.w
        w.structs = [["hq", team, x, y, 72, self.HP, self.HP, 0.0] for team, (x, y) in enumerate(w.map.flag_homes)]
        w.scores = [int(self.HP), int(self.HP)]

    def step(self, dt):
        self.w.scores = [int(math.ceil(s[5])) for s in self.w.structs]

    def on_struct_destroyed(self, s, attacker_pid):
        w = self.w
        w.scores = [int(math.ceil(x[5])) for x in w.structs]
        w.note("The %s headquarters is destroyed!" % data.TEAM_NAMES[s[1]].split()[0], 1 - s[1])
        w.finish(1 - s[1])

    def time_up(self):
        a, b = self.w.structs[0][5], self.w.structs[1][5]
        self.w.finish(0 if a > b else 1 if b > a else -1)
        return True

    def hud(self, me):
        s = self.w.structs
        return "%d%%" % math.ceil(100 * s[0][5] / s[0][6]), "%d%%" % math.ceil(100 * s[1][5] / s[1][6]), "headquarters"

    def hints(self, me):
        own = self.w.structs[me.team % 2]
        return [("Your headquarters is under attack!", BAD)] if own[5] < own[6] and self.w.time - own_hit(self.w, me.team) < 3 else []

    def ai_goal(self, ai, t, alive, target):
        s = self.w.structs
        if t.brain.defender:
            return "home%d" % t.team, (s[t.team][2], s[t.team][3]), False
        foe = s[1 - t.team]
        return "hq%d" % (1 - t.team), (foe[2], foe[3]), True

    def ai_struct(self, t):
        return 1 - t.team


def own_hit(world, team):
    return world.ms.get("hit%d" % (team % 2), -99.0)


# ---------------------------------------------------------------------------------------------
class Escort(Rules):
    """One side escorts a slow supply truck across the map while the other tries to destroy it; then they
    swap. The side whose truck got further (or arrived faster) wins."""
    own_clock = True
    SPEED = 42.0
    HP = 300.0
    PHASE_CAP = 300.0

    def setup(self):
        self.w.ms.update(phase=0, t=0.0, brk=0.0, res=[None, None])
        self._begin(0)

    def after_load(self):
        self._route(self.w.structs[0][1])

    def _route(self, team):
        m = self.w.map
        self.dest = m.flag_homes[1 - team]
        self.field = m.flow_field([(int(self.dest[0]) // data.NAV, int(self.dest[1]) // data.NAV)])
        sx, sy = m.flag_homes[team]
        self.total = max(1.0, self.field[int(sy) // data.NAV][int(sx) // data.NAV])

    def _begin(self, team):
        w = self.w
        self._route(team)
        sx, sy = w.map.flag_homes[team]
        w.structs = [["truck", team, sx, sy, 46, self.HP, self.HP, 0.0 if team == 0 else math.pi]]

    def progress(self):
        s = self.w.structs[0]
        d = self.field[int(s[3]) // data.NAV][int(s[2]) // data.NAV]
        return max(0.0, min(1.0, 1.0 - d / self.total)) if d < 1e8 else 0.0

    def step(self, dt):
        w, ms = self.w, self.w.ms
        if ms["brk"] > 0:
            ms["brk"] -= dt
            if ms["brk"] <= 0:
                if ms["phase"] == 0:
                    ms.update(phase=1, t=0.0)
                    self._begin(1)
                    w.reset_round()
                    w.note("Sides swap: %s now escorts the convoy" % data.TEAM_NAMES[1])
                else:
                    self._decide()
            return
        s = w.structs[0]
        ms["t"] += dt
        cap = min(self.PHASE_CAP, (w.settings["time_limit"] or 2 * self.PHASE_CAP) / 2.0)
        # drive: follow the flow field downhill toward the destination
        cx, cy = int(s[2]) // data.NAV, int(s[3]) // data.NAV
        best, bx, by = self.field[cy][cx], cx, cy
        nav = w.map.nav_list
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < len(nav[0]) and 0 <= ny < len(nav) and not (dx and dy and (nav[cy][nx] or nav[ny][cx])):
                d = self.field[ny][nx] + (0.4 if dx and dy else 0.0)
                if d < best:
                    best, bx, by = d, nx, ny
        tx, ty = (self.dest if (bx, by) == (cx, cy) else (bx * data.NAV + data.NAV / 2, by * data.NAV + data.NAV / 2))
        want = math.atan2(ty - s[3], tx - s[2])
        diff = (want - s[7] + math.pi) % (2 * math.pi) - math.pi
        s[7] += max(-1.2 * dt, min(1.2 * dt, diff))
        v = self.SPEED * (1.0 if abs(diff) < 0.6 else 0.25) * dt
        s[2] += math.cos(s[7]) * v
        s[3] += math.sin(s[7]) * v
        w.scores[s[1]] = int(100 * self.progress())
        if math.hypot(self.dest[0] - s[2], self.dest[1] - s[3]) < 130:
            w.scores[s[1]] = 100
            self._end_phase([1, round(ms["t"], 1)], "The convoy got through!", s[1])
        elif ms["t"] >= cap:
            self._end_phase([0, round(self.progress(), 3)], "Out of time - the convoy stopped", 1 - s[1])

    def on_struct_destroyed(self, s, attacker_pid):
        self._end_phase([0, round(self.progress(), 3)], "The convoy truck is destroyed!", 1 - s[1])

    def _end_phase(self, res, text, good_team):
        w, ms = self.w, self.w.ms
        if ms["brk"] > 0:
            return
        ms["res"][ms["phase"]] = res
        w.note(text, good_team)
        ms["brk"] = 5.0

    def _decide(self):
        a, b = self.w.ms["res"]
        if a[0] != b[0]:
            win = 0 if a[0] else 1
        elif a[0]:
            win = 0 if a[1] < b[1] else 1 if b[1] < a[1] else -1       # both arrived: the faster run wins
        else:
            win = 0 if a[1] > b[1] else 1 if b[1] > a[1] else -1       # neither arrived: the longer run wins
        self.w.finish(win)

    def hud(self, me):
        w = self.w
        esc = w.structs[0][1]
        return "%d%%" % w.scores[0], "%d%%" % w.scores[1], "convoy distance - %s escorting" % data.TEAM_NAMES[esc].split()[0]

    def hints(self, me):
        w, ms = self.w, self.w.ms
        if ms["brk"] > 0:
            return [("Next phase in %d" % math.ceil(ms["brk"]), PLAIN)]
        s = w.structs[0]
        if me.team == s[1]:
            return [("Protect the convoy!   Truck health %d%%" % math.ceil(100 * s[5] / s[6]), GOOD)]
        return [("Destroy the convoy truck!   Truck health %d%%" % math.ceil(100 * s[5] / s[6]), GOLD)]

    def ai_goal(self, ai, t, alive, target):
        s = self.w.structs[0]
        return "truck", (s[2], s[3]), t.team != s[1]

    def ai_struct(self, t):
        return 0 if t.team != self.w.structs[0][1] else -1


# ---------------------------------------------------------------------------------------------
class Juggernaut(Rules):
    """One tank is the Juggernaut: an armoured Goliath hunted by everyone else. Whoever destroys it
    becomes the next one, and every new Juggernaut starts a new round: the field is cleared, the Juggernaut
    starts at the east end of the map and the hunters at the west end.
    Points: 1 per kill as the Juggernaut, 3 for bringing it down."""
    individual = True
    ARMOR = 0.4
    KIT = ("death_shell", "heavy_gatling")
    # Whatever anyone owns, hunters get exactly this, so the hunt is even; the Juggernaut gets the Goliath kit.
    HUNTER = (("basic",), ("basic_shell", "tracer"))
    BOSS = (("goliath",), ("death_shell", "heavy_gatling"))

    def restrict(self):
        j = self.w.ms["jugg"]
        for t in self.w.players.values():
            want = self.BOSS if t.pid == j else self.HUNTER
            if t.allow is not want:
                t.allow = want
                # always re-fit: this also strips upgrade bonuses (strength) from a tank already in use
                frac = t.hp / t.max_hp if t.max_hp else 1.0
                t.set_tank(t.tank_key if t.tank_key in want[0] else want[0][0])
                if t.alive:
                    t.hp = t.max_hp * frac

    def setup(self):
        self.w.ms.update(jugg=-1, round=0, fresh=False)

    def assign_team(self, team, pid, is_ai):
        return 0

    def marks(self):
        return {self.w.ms["jugg"]: "JUGGERNAUT"}

    def step(self, dt):
        w = self.w
        if w.ms["jugg"] not in w.players and w.players:
            alive = [t for t in w.players.values() if t.alive] or list(w.players.values())
            self._crown(w.rng.choice(alive))
        self.restrict()
        if w.ms["fresh"]:
            # new Juggernaut, new round. (Done here rather than inside the kill, which happens while
            # projectiles are still being processed.) Teams decide the spawn ends: hunters (team 0) start in
            # the west spawn area, the Juggernaut (team 1) in the east one, the full width of the map apart.
            w.ms["fresh"] = False
            w.reset_round()

    def _crown(self, t):
        w = self.w
        old = w.players.get(w.ms["jugg"])
        if old is not None and old is not t:
            self._uncrown(old)
        w.ms["jugg"] = t.pid
        t.team = 1
        t.temp = []
        if "goliath" not in t.tanks:
            t.tanks.append("goliath")
            t.temp.append(["tank", "goliath"])
        for k in self.KIT:
            if k not in t.weapons:
                t.weapons.append(k)
                t.temp.append(["weapon", k])
        t.allow = self.BOSS
        t.set_tank("goliath")
        w.ms["round"] += 1
        w.ms["fresh"] = True
        w.note("Round %d: %s is the Juggernaut!" % (w.ms["round"], t.name), -1, t.pid)

    def _uncrown(self, t):
        t.team = 0
        for kind, key in t.temp:
            lst = t.tanks if kind == "tank" else t.weapons
            if key in lst:
                lst.remove(key)
        t.temp = []
        t.allow = self.HUNTER
        t.set_tank("basic")

    def damage_scale(self, t):
        return self.ARMOR if t.pid == self.w.ms["jugg"] else 1.0

    def can_swap(self, t):
        return False                    # tanks are assigned in this game type

    def on_kill(self, victim, killer):
        w = self.w
        if victim.pid == w.ms["jugg"]:
            if killer and killer is not victim:
                killer.points += 3
                nxt = killer
            else:
                others = [t for t in w.players.values() if t is not victim]
                alive = [t for t in others if t.alive]
                nxt = w.rng.choice(alive or others) if others else victim
            if nxt is not victim:
                self._crown(nxt)
        elif killer and killer.pid == w.ms["jugg"]:
            killer.points += 1
        goal = self.limit("kill_limit", 20)
        best, _tied = self.top_player(lambda t: t.points)
        if goal and best and best.points >= goal:
            w.finish(best.team, best.pid)

    def time_up(self):
        best, tied = self.top_player(lambda t: t.points)
        self.w.finish(-1 if (tied or best is None) else best.team, None if (tied or best is None) else best.pid)
        return True

    def hud(self, me):
        w = self.w
        j = w.players.get(w.ms["jugg"])
        rival = max([t.points for t in w.players.values() if t is not me] or [0])
        return (str(me.points if me else 0), str(rival),
                "round %d - you / best rival - first to %d points" % (w.ms["round"], self.limit("kill_limit", 20)))

    def hints(self, me):
        w = self.w
        j = w.players.get(w.ms["jugg"])
        if j is me:
            return [("You are the Juggernaut - destroy them all!", GOLD)]
        return [("Hunt the Juggernaut: %s" % j.name, PLAIN)] if j else []

    def ai_goal(self, ai, t, alive, target):
        return None


# ---------------------------------------------------------------------------------------------
class Survival(Rules):
    """Everyone on one team against waves of AI tanks that keep getting bigger and tougher.
    Destroyed defenders return when the wave is cleared; the battle ends when all are down at once."""
    own_clock = True
    out_text = "You return when this wave is cleared."

    def setup(self):
        self.w.ms.update(wave=0, phase="break", t=6.0, cleared=0)
        self.w.scores = [0, 0]

    def assign_team(self, team, pid, is_ai):
        return team if (is_ai and team == 1) else 0

    def step(self, dt):
        w, ms = self.w, self.w.ms
        mine = [p for p in w.players.values() if p.team == 0]
        if ms["phase"] == "break":
            ms["t"] -= dt
            if ms["t"] <= 0:
                self._start_wave(mine)
            return
        left = sum(1 for p in w.players.values() if p.team == 1 and not p.out)
        w.scores = [ms["wave"], left]
        if mine and all(p.out for p in mine):
            w.note("Overrun on wave %d" % ms["wave"])
            w.finish(1)
        elif left == 0:
            ms["cleared"] = ms["wave"]
            pay = 10 + 5 * ms["wave"]
            for p in mine:
                p.credits += pay
                p.earned += pay
                if p.out:
                    p.out = False
                    p.respawn = 0.5
            w.note("Wave %d cleared!  +%d credits - shop now (B)" % (ms["wave"], pay), 0)
            ms.update(phase="break", t=12.0)

    def _start_wave(self, mine):
        from .ai import make_ai_loadout          # (ai imports world, world imports this module)
        w, ms = self.w, self.w.ms
        ms.update(wave=ms["wave"] + 1, phase="fight")
        n = ms["wave"]
        for p in [p for p in w.players.values() if p.team == 1]:
            w.remove_player(p.pid)
        count = min(30, max(1, round(len(mine) * 0.6)) + n - 1)     # 1 defender: 1, 2, 3...   4: 2, 3, 4...
        tier = min(len(data.AI_MIX) - 1, (n - 1) // 3)
        skill = min(2, max(0, w.settings["difficulty"] - 1) + (n - 1) // 4)
        lineup = data.ai_lineup(tier, count)
        used = {p.name for p in w.players.values()}
        for i, tank in enumerate(lineup):
            t = w.add_player(make_ai_loadout(w.rng, 1, i, skill, used, tank), 1, True, skill)
            if w.ai:
                w.ai.attach(t)
        for p in mine:
            if p.out:
                p.out = False
                p.respawn = 0.0
        w.scores = [n, count]
        w.note("Wave %d - %d enemy tanks incoming!" % (n, count))

    def on_kill(self, victim, killer):
        victim.out = True

    def hud(self, me):
        ms = self.w.ms
        if ms["phase"] == "break":
            return str(ms["wave"] + 1), "%d" % math.ceil(max(0.0, ms["t"])), "next wave / seconds until it arrives"
        return str(ms["wave"]), str(self.w.scores[1]), "wave / enemies left"

    def hints(self, me):
        if self.w.ms["phase"] == "break":
            return [("Wave %d incoming - press B to shop" % (self.w.ms["wave"] + 1), GOLD)]
        return []

    def title(self, me):
        n = self.w.ms["cleared"]
        return "SURVIVED %d WAVE%s" % (n, "" if n == 1 else "S")


# ---------------------------------------------------------------------------------------------
class Vip(Rules):
    """Each team has one marked tank. Destroying the enemy VIP scores a point; a new VIP is then chosen."""
    BONUS = 25

    def setup(self):
        self.w.ms.update(vip=[-1, -1])

    def marks(self):
        return {pid: "VIP" for pid in self.w.ms["vip"] if pid >= 0}

    def _pick(self, team, avoid=-1):
        w = self.w
        team_ps = [p for p in w.players.values() if p.team == team]
        pool = [p for p in team_ps if p.pid != avoid] or team_ps
        if not pool:
            w.ms["vip"][team] = -1
            return
        t = w.rng.choice(pool)
        w.ms["vip"][team] = t.pid
        w.note("%s is the %s VIP" % (t.name, data.TEAM_NAMES[team].split()[0]), -1, t.pid)

    def step(self, dt):
        w = self.w
        for team in (0, 1):
            v = w.players.get(w.ms["vip"][team])
            if v is None or v.team != team:
                self._pick(team)

    def on_kill(self, victim, killer):
        w = self.w
        team = victim.team
        if team in (0, 1) and victim.pid == w.ms["vip"][team]:
            if killer and killer.team != team:
                w.scores[killer.team] += 1
                killer.credits += self.BONUS
                killer.earned += self.BONUS
                w.note("%s destroyed the %s VIP!" % (killer.name, data.TEAM_NAMES[team].split()[0]), killer.team)
                if w.scores[killer.team] >= self.limit("cap_limit", 3):
                    w.finish(killer.team)
                    return
            self._pick(team, victim.pid)

    def hud(self, me):
        w = self.w
        return str(w.scores[0]), str(w.scores[1]), "VIP kills - first to %d" % self.limit("cap_limit", 3)

    def hints(self, me):
        w = self.w
        if me.team not in (0, 1):
            return []
        if w.ms["vip"][me.team] == me.pid:
            return [("You are the VIP - stay alive!", GOLD)]
        foe = w.players.get(w.ms["vip"][1 - me.team])
        mate = w.players.get(w.ms["vip"][me.team])
        out = []
        if foe:
            out.append(("Enemy VIP: %s" % foe.name, PLAIN))
        if mate:
            out.append(("Protect %s" % mate.name, PLAIN))
        return out

    def ai_priority(self, t, e):
        return e.team in (0, 1) and e.pid == self.w.ms["vip"][e.team]

    def ai_goal(self, ai, t, alive, target):
        v = self.w.players.get(self.w.ms["vip"][t.team]) if t.team in (0, 1) else None
        if t.brain.defender and v is not None and v is not t and v.alive:
            return "vip%d" % t.team, (v.x, v.y), False
        return None


RULES = dict(koth=KingOfTheHill, ffa=FreeForAll, lts=LastTeamStanding, base=BaseAssault, escort=Escort,
             jugg=Juggernaut, survival=Survival, vip=Vip)


def make(world):
    cls = RULES.get(world.mode)
    return cls(world) if cls else None
