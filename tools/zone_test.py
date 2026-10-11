"""Headless Zone Defense checks: the rules, all-AI matches, save/load and what a client sees."""
import json
import math
import os
import random
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ut import ai, data, mapgen, net
from ut.world import World

S = dict(map="valley", seed=6, kill_limit=5, time_limit=600, mode="zones")
T = data.ZONE_CAPTURE_TIME


def run(w, seconds):
    for _ in range(int(seconds * 60)):
        w.step(1 / 60)


def put(t, c, dx=0.0):
    t.x, t.y, t.speed, t.throttle = c[0] + dx, c[1], 0.0, 0.0


# 0. zone placement on every map
for preset in ("valley", "highlands", "farmland"):
    for seed in (1, 2, 3):
        m = mapgen.GameMap(preset, seed)
        pts = m.zone_points
        assert len(pts) == 5
        for x, y in pts:
            assert not m.blocked_circle(x, y, 80), (preset, seed, x, y)
        gaps = [math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]) for i in range(5) for j in range(i)]
        assert min(gaps) > 700, (preset, seed, min(gaps))
print("0. five zones on open ground on all maps; e.g. valley seed 1:", [(int(x), int(y)) for x, y in mapgen.GameMap("valley", 1).zone_points])

# 1. the rules, by hand
w = World(S)
a = w.add_player(dict(name="Blue", color=[1, 1, 1]), 0)
b = w.add_player(dict(name="Red", color=[2, 2, 2]), 1)
w.step(0.0)
assert [c[2] for c in w.cps] == [0, -1, -1, -1, 1] and w.scores == [1, 1]
C = w.cps[2]
put(a, C); a.hold = False
run(w, 6)
assert C[2] == -1, "captured without holding Z"
a.hold = True
run(w, T - 0.5)
assert C[2] == -1 and C[3] == a.pid and C[4] > T - 1, "should be nearly captured"
a.hold = False; run(w, 0.2); a.hold = True
assert C[4] < 0.5, "letting go of Z must start the count over"
run(w, T - 1)
put(a, C, data.ZONE_RADIUS + 60); run(w, 0.2); put(a, C)
run(w, 1.0)
assert C[2] == -1 and C[4] < 1.5, "leaving the ring must start the count over"
put(b, C, 80); b.hold = False
before = C[4]
run(w, 3)
assert abs(C[4] - before) < 0.05 and C[2] == -1, "count must pause while an enemy is inside"
put(b, w.cps[4])
credits = a.credits
run(w, T + 0.5)
assert C[2] == 0 and w.scores == [2, 1] and a.credits == credits + data.ZONE_REWARD, (C, w.scores)
print("1. needs Z held for %.0f s; resets on release and on leaving; pauses while contested; pays %d credits: ok"
      % (T, data.ZONE_REWARD))
a.shield = 0; run(w, 0.1)
put(a, w.cps[1]); run(w, T - 1); a.shield = 0
w._damage(a, 999, b.pid, 1, 0)
assert w.cps[1][2] == -1 and w.scores == [2, 1]
run(w, 6)
assert w.cps[1][4] == 0.0 and w.over is None, "dying must start the count over; kills must not end the match"
print("   dying resets the count, a kill scores nothing and does not end the match: ok")

# time runs out: most zones wins
w2 = World(dict(S, time_limit=60)); x = w2.add_player(dict(name="X", color=[1, 1, 1]), 0); y = w2.add_player(dict(name="Y", color=[1, 1, 1]), 1)
w2.step(0.0); put(y, w2.cps[3]); y.hold = True
run(w2, 61)
assert w2.over == 1 and w2.scores == [1, 2], (w2.over, w2.scores)
w3 = World(dict(S, time_limit=30)); w3.add_player(dict(name="X", color=[1, 1, 1]), 0); w3.add_player(dict(name="Y", color=[1, 1, 1]), 1)
run(w3, 31)
assert w3.over == -1, "equal zones at the end should be a draw"
print("   timer: red led 2-1 at the end -> red wins; 1-1 -> draw: ok")

# all five: instant win
w4 = World(dict(S, time_limit=3600)); x = w4.add_player(dict(name="X", color=[1, 1, 1]), 0); w4.add_player(dict(name="Y", color=[1, 1, 1]), 1)
w4.step(0.0); x.hold = True
for i in (1, 2, 3, 4):
    assert w4.over is None
    put(x, w4.cps[i]); run(w4, T + 0.3)
assert w4.over == 0 and w4.scores == [5, 0], (w4.over, w4.scores)
print("   holding all five ends it at once (after %.0f s of a 60 min timer): ok" % w4.time)

# 2. all-AI matches
for preset, n, skill, minutes in (("valley", 5, 1, 6), ("highlands", 8, 2, 6), ("farmland", 12, 1, 6), ("valley", 3, 0, 6)):
    w = World(dict(S, map=preset, seed=9, time_limit=minutes * 60, difficulty=skill)); w.ai = ai.AIController(w)
    rng = random.Random(4); used = set()
    for team in (0, 1):
        for i in range(n):
            w.ai.attach(w.add_player(ai.make_ai_loadout(rng, team, i, skill, used), team, True, skill))
    caps = Counter(); t0 = time.time(); worst = 0; lead = []
    while w.over is None:
        f = time.time(); w.step(1 / 60); worst = max(worst, time.time() - f)
        for e in w.events:
            if e[0] == "zone":
                caps[data.ZONE_NAMES[e[2]]] += 1
        w.events.clear()
        if int(w.time * 60) % 1800 == 0:
            lead.append("%d-%d" % tuple(w.scores))
    print("2. %-9s %2dv%-2d: winner %2s, zones %s after %3.0f s (%2.0fs real, worst step %2.0f ms)  captures %d %s  score every 30 s: %s"
          % (preset, n, n, w.over, w.scores, w.time, time.time() - t0, worst * 1000, sum(caps.values()), dict(sorted(caps.items())), " ".join(lead)))
    assert sum(caps.values()) >= 3, "the AI barely captured anything"

# 3. save / load
w = World(S); a = w.add_player(dict(name="Blue", color=[1, 1, 1]), 0); w.add_player(dict(name="Red", color=[2, 2, 2]), 1)
w.step(0.0); a.hold = True; put(a, w.cps[2]); run(w, T + 0.2); put(a, w.cps[1]); run(w, 2)
w2 = World.from_dict(json.loads(json.dumps(w.to_dict())))
print("3. save/load: mode %s, owners %s -> %s, scores %s, progress on B %.1f s" % (w2.mode, [c[2] for c in w.cps], [c[2] for c in w2.cps], w2.scores, w2.cps[1][4]))
assert [c[2] for c in w2.cps] == [c[2] for c in w.cps] and w2.scores == w.scores == [2, 1] and w2.cps[1][4] > 1.5

# 4. a client holds Z over the network
srv = net.Server(27985)
w = World(S)
h = w.add_player(dict(name="Host", color=[1, 1, 1]), 0)
hs = net.LocalSession(w, h.pid, srv, {})
conn, inbox = net.connect("127.0.0.1", 27985); conn.send({"t": "join", "lo": dict(name="Guest")})
start = None
while start is None:
    hs.update(1 / 60)
    while not inbox.empty():
        m = inbox.get()[1]
        if m["t"] == "start":
            start = m
    time.sleep(0.005)
cs = net.RemoteSession(conn, inbox, start)
guest = w.players[cs.pid]
seen = []; mid = None
for f in range(int((T + 2) * 60)):
    if f == 20:
        put(guest, w.cps[2])
    cs.set_input(0, 0, 0, False, False, 300, f > 20)
    hs.update(1 / 60); seen += [e for e in cs.update(1 / 60) if e[0] == "zone"]
    if f == 200:
        mid = (cs.world.cps[2][3], cs.world.cps[2][4])
    time.sleep(1 / 240)
print("4. client: zone C mid-capture seen as (pid %s, %.1f s); afterwards owners %s, scores %s, events %s"
      % (mid[0], mid[1], [c[2] for c in cs.world.cps], cs.world.scores, [e[1] for e in seen]))
assert cs.world.cps[2][2] == guest.team and mid[0] == cs.pid and mid[1] > 1 and seen
conn.close(); hs.close()
print("ALL OK")
