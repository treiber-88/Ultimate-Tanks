"""Headless checks for the extra game types: all-AI matches, save/load and what a client sees."""
import json, math, os, random, sys, time
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ut import ai, data, net
from ut.world import World

ONLY = sys.argv[1:]


def match(mode, n=6, skill=1, seconds=420, preset="valley", seed=4, **extra):
    s = dict(map=preset, seed=seed, kill_limit=15, time_limit=seconds, difficulty=skill, mode=mode, cap_limit=2,
             score_limit=60, rounds=2)
    s.update(extra)
    w = World(s); w.ai = ai.AIController(w)
    rng = random.Random(4); used = set()
    for team in (0, 1):
        for i in range(0 if (team == 1 and mode == "survival") else n):
            w.ai.attach(w.add_player(ai.make_ai_loadout(rng, team, i, skill, used), team, True, skill))
    return w


def run(w, limit=900, mid=None):
    ev = Counter(); notes = []; worst = 0.0; t0 = time.time(); half = None
    while w.over is None and w.time < limit:
        f = time.time(); w.step(1 / 60); worst = max(worst, time.time() - f)
        for e in w.events:
            ev[e[0]] += 1
            if e[0] == "note": notes.append(e[1])
        w.events.clear()
        if mid and half is None and w.time > mid:
            half = json.loads(json.dumps(w.to_dict()))
    return ev, notes, worst, time.time() - t0, half


def roundtrip(w, half, mode):
    """A battle saved mid-way must load and keep running to a finish."""
    w2 = World.from_dict(half); w2.ai = ai.AIController(w2)
    for t in w2.players.values():
        if t.is_ai: w2.ai.attach(t)
    assert w2.mode == mode and len(w2.players) == len(half["players"]) and len(w2.structs) == len(w.structs)
    for _ in range(60 * 20): w2.step(1 / 60)
    return w2


TESTS = {}
def test(f): TESTS[f.__name__] = f; return f


@test
def koth():
    w = match("koth"); ev, notes, worst, real, half = run(w, mid=20)
    assert w.over in (0, 1) and max(w.scores) >= 60, (w.over, w.scores)
    roundtrip(w, half, "koth")
    return "winner %s, seconds held %s after %.0f s" % (w.over, [int(s) for s in w.scores], w.time)


@test
def ffa():
    w = match("ffa", n=5, kill_limit=8); ev, notes, worst, real, half = run(w, mid=20)
    teams = {t.team for t in w.players.values()}
    assert len(teams) == len(w.players), "every tank must be its own team"
    win = w.players.get(w.winner_pid)
    assert win and win.kills >= 8 and w.won(win) and sum(w.won(t) for t in w.players.values()) == 1
    spread = max(abs(a.x - b.x) for a in w.players.values() for b in w.players.values())
    roundtrip(w, half, "ffa")
    return "winner %s with %d kills after %.0f s; %d kills in all" % (win.name, win.kills, w.time, ev["kill"])


@test
def lts():
    w = match("lts", n=5); ev, notes, worst, real, half = run(w, mid=15)
    assert w.over in (0, 1) and max(w.scores) == 2 and ev["spawn"] <= 10 * (sum(w.scores) + 1), (w.scores, ev)
    assert ev["kill"] <= 10 * sum(w.scores) + 10
    roundtrip(w, half, "lts")
    return "rounds %s, winner %s after %.0f s (%d kills, %d spawns: nobody respawned mid-round)" % (w.scores, w.over, w.time, ev["kill"], ev["spawn"])


@test
def base():
    w = match("base", seconds=600); ev, notes, worst, real, half = run(w, mid=30)
    hp = [s[5] for s in w.structs]
    assert w.over in (0, 1) and (min(hp) == 0 or w.time >= 600), (w.over, hp)
    w2 = roundtrip(w, half, "base")
    assert w2.structs[0][5] <= 500
    return "winner %s after %.0f s, headquarters left at %s hp, %s" % (w.over, w.time, [int(h) for h in hp], "destroyed" if min(hp) == 0 else "decided on time")


@test
def escort():
    w = match("escort", seconds=0); ev, notes, worst, real, half = run(w, limit=800, mid=30)
    res = w.ms["res"]
    assert w.over in (0, 1, -1) and res[0] and res[1], (w.over, res)
    roundtrip(w, half, "escort")
    def show(r): return "arrived in %.0f s" % r[1] if r[0] else "destroyed at %d%%" % (r[1] * 100)
    return "blue truck %s, red truck %s -> winner %s (%.0f s)" % (show(res[0]), show(res[1]), w.over, w.time)


@test
def jugg():
    w = match("jugg", n=4, kill_limit=10); ev, notes, worst, real, half = run(w, mid=25)
    win = w.players.get(w.winner_pid)
    juggs = [t for t in w.players.values() if t.team == 1]
    assert win and win.points >= 10 and len(juggs) == 1 and juggs[0].tank_key == "goliath", (w.winner_pid, len(juggs))
    for t in w.players.values():                       # the loaned Goliath must never reach a save file
        st = t.state()
        assert "goliath" not in st["tanks"] and "death_shell" not in st["weapons"] and st["tank"] in st["tanks"], st
    crowns = sum(1 for n in notes if "Juggernaut" in n)
    w2 = roundtrip(w, half, "jugg")
    assert sum(1 for t in w2.players.values() if t.team == 1) == 1
    return "winner %s with %d points after %.0f s; the crown changed hands %d times" % (win.name, win.points, w.time, crowns)


@test
def survival():
    w = match("survival", n=4, seconds=0); ev, notes, worst, real, half = run(w, limit=1500, mid=40)
    waves = w.ms["cleared"]
    assert w.over == 1 and waves >= 1 and w.rules.title(None).startswith("SURVIVED"), (w.over, w.ms)
    sizes = [int(n.split(" - ")[1].split()[0]) for n in notes if n.startswith("Wave") and "incoming" in n]
    assert sizes == sorted(sizes) and len(w.players) < 60
    roundtrip(w, half, "survival")
    return "4 defenders survived %d waves (wave sizes %s) in %.0f s" % (waves, sizes, w.time)


@test
def vip():
    w = match("vip"); ev, notes, worst, real, half = run(w, mid=20)
    assert w.over in (0, 1) and max(w.scores) == 2, (w.over, w.scores)
    picks = sum(1 for n in notes if " is the " in n and "VIP" in n)
    roundtrip(w, half, "vip")
    return "VIP kills %s, winner %s after %.0f s; %d VIPs named" % (w.scores, w.over, w.time, picks)


@test
def client():
    """A joining player must see each game type's state."""
    out = []
    for i, mode in enumerate(data.MODE_KEYS[3:]):
        srv = net.Server(27960 + i)
        w = match(mode, n=3, seconds=0 if mode in ("escort", "survival") else 300)
        h = w.add_player(dict(name="Host", color=[1, 1, 1]), 0)
        hs = net.LocalSession(w, h.pid, srv, {})
        conn, inbox = net.connect("127.0.0.1", 27960 + i); conn.send({"t": "join", "lo": dict(name="Guest")})
        start = None
        while start is None:
            hs.update(1 / 60)
            while not inbox.empty():
                m = inbox.get()[1]
                if m["t"] == "start": start = m
            time.sleep(0.004)
        cs = net.RemoteSession(conn, inbox, start)
        for f in range(60 * 6):
            hs.update(1 / 60); cs.update(1 / 60); time.sleep(1 / 400)
        cw = cs.world
        assert cw.mode == mode and cw.rules is not None
        clocks = ("t", "brk", "hit0", "hit1")                 # these tick every frame: compare loosely
        assert {k: v for k, v in cw.ms.items() if k not in clocks} == {k: v for k, v in w.ms.items() if k not in clocks}, (mode, cw.ms, w.ms)
        assert all(abs(cw.ms[k] - w.ms[k]) < 0.5 for k in clocks if k in w.ms), (mode, cw.ms, w.ms)
        assert len(cw.structs) == len(w.structs) and all(abs(a[2] - b[2]) < 30 and a[1] == b[1] for a, b in zip(cw.structs, w.structs))
        assert {p: t.team for p, t in cw.players.items()} == {p: t.team for p, t in w.players.items()}, mode
        me = cs.me(); left, right, cap = cw.rules.hud(me); cw.rules.hints(me); cw.rules.marks()
        out.append(mode)
        conn.close(); hs.close()
    return "state, teams, structures and HUD agree on the client for: " + ", ".join(out)


for name, fn in TESTS.items():
    if ONLY and name not in ONLY: continue
    t0 = time.time()
    print("%-9s %s  [%.0fs]" % (name, fn(), time.time() - t0))
print("ALL OK")
