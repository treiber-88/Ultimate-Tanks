"""Headless Capture-the-Flag checks: the rules, an all-AI match, save/load and what a client sees."""
import json, math, os, random, sys, time
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ut import ai, data, net
from ut.world import World

S = dict(map="valley", seed=6, kill_limit=5, time_limit=0, mode="ctf", cap_limit=2)


def place(w, t, x, y):
    t.x, t.y, t.speed, t.throttle = x, y, 0.0, 0.0
    w.step(1 / 60)


# 1. the rules, by hand
w = World(S)
a = w.add_player(dict(name="Blue", color=[1, 1, 1]), 0)
b = w.add_player(dict(name="Red", color=[2, 2, 2]), 1)
w.step(0.0)
h0, h1 = w.map.flag_homes
ev = lambda: [e[1:] for e in w.events if e[0] == "flag"]


def destroy(victim, by):
    victim.shield = 0.0                            # spawn protection would otherwise absorb the hit
    w._damage(victim, 999, by.pid if by else -1, by.team if by else 1 - victim.team, 0)
    assert not victim.alive


place(w, a, *h1)
assert a.flag == 1 and w.flags[1][0] == 1, "blue did not pick up the red flag"
base_speed = data.tank_speed(a.spec)
a.throttle = 1.0
for _ in range(120): w.step(1 / 60)
hp = a.hp; a.shield = 0.0; w._damage(a, 10, b.pid, b.team, 0)
print("1. pick up ok; carrier speed %.0f (normal %.0f); a 10-damage hit costs the carrier %.1f" % (abs(a.speed), base_speed, hp - a.hp))
a.hp = a.max_hp
place(w, b, *h0)                                   # red steals blue's flag
place(w, a, *h0)                                   # blue arrives home, but its own flag is gone
assert w.scores == [0, 0] and a.flag == 1, "scored while own flag was away"
destroy(b, a)                                      # blue destroys the red carrier
assert w.flags[0][0] == 2 and b.flag == -1, "flag was not dropped"
assert w.scores == [0, 0], "a kill must not score in CTF"
place(w, a, 3000, 3000)
place(w, a, w.flags[0][1], w.flags[0][2])          # blue touches its own dropped flag
assert w.flags[0][0] == 0, "flag did not return"
place(w, a, *h0)
assert w.scores == [1, 0] and a.flag == -1 and w.flags[1][0] == 0, (w.scores, a.flag, w.flags)
want = b.spec["reward"] + data.RETURN_REWARD + data.CAPTURE_REWARD
assert a.credits == want, (a.credits, want)
print("   blocked while own flag away, drop on death, return by touch, capture: ok (kill %d + return %d + capture %d credits)"
      % (b.spec["reward"], data.RETURN_REWARD, data.CAPTURE_REWARD))
destroy(a, b)
for _ in range(60 * 11): w.step(1 / 60)     # wait out the respawn
place(w, a, *h1); destroy(a, None)                 # dies carrying: dropped flag times out by itself
t0 = w.time
while w.flags[1][0] == 2: w.step(1 / 60)
print("   dropped flag returned by itself after %.0f s" % (w.time - t0))
for _ in range(60 * 11): w.step(1 / 60)     # wait out the respawn
place(w, a, *h1); place(w, a, *h0)
assert w.over == 0 and w.scores == [2, 0], (w.over, w.scores)
print("   second capture ends the match: winner team %s, events seen: %s" % (w.over, dict(Counter(e[0] for e in ev()))))

# 2. an all-AI match plays itself to a finish
for preset, n in (("valley", 6), ("highlands", 8), ("farmland", 5)):
    w = World(dict(S, map=preset, seed=9, cap_limit=3, time_limit=900)); w.ai = ai.AIController(w)
    rng = random.Random(4); used = set()
    for team in (0, 1):
        for i in range(n): w.ai.attach(w.add_player(ai.make_ai_loadout(rng, team, i, 1, used), team, True, 1))
    c = Counter(); t0 = time.time(); worst = 0
    while w.over is None:
        f = time.time(); w.step(1 / 60); worst = max(worst, time.time() - f)
        for e in w.events:
            if e[0] == "flag": c[e[1]] += 1
            if e[0] == "kill": c["kill"] += 1
        w.events.clear()
    print("2. %-9s %dv%d: finished %s in %3.0f game-seconds (%.0fs real, worst step %.0f ms)  %s  defenders %d"
          % (preset, n, n, w.scores, w.time, time.time() - t0, worst * 1000, dict(c), sum(t.brain.defender for t in w.players.values())))
    assert c["captured"] >= 1, "the AI never captured a flag"

# 3. save / load mid-match
w = World(S); w.ai = ai.AIController(w)
a = w.add_player(dict(name="Blue", color=[1, 1, 1]), 0); b = w.add_player(dict(name="Red", color=[2, 2, 2]), 1)
w.step(0.0); place(w, a, *w.map.flag_homes[1]); place(w, a, 2000, 2500); w.scores = [1, 0]
w2 = World.from_dict(json.loads(json.dumps(w.to_dict())))
print("3. save/load: mode %s, scores %s, red flag state %s carried by pid %s, carrier.flag=%s"
      % (w2.mode, w2.scores, w2.flags[1][0], w2.flags[1][3], w2.players[a.pid].flag))
assert w2.flags[1][0] == 1 and w2.players[a.pid].flag == 1 and w2.mode == "ctf"

# 4. a client sees the same flags
srv = net.Server(27984)
w = World(S); w.ai = ai.AIController(w)
h = w.add_player(dict(name="Host", color=[1, 1, 1]), 0)
hs = net.LocalSession(w, h.pid, srv, {})
conn, inbox = net.connect("127.0.0.1", 27984); conn.send({"t": "join", "lo": dict(name="Guest")})
start = None
while start is None:
    hs.update(1 / 60)
    while not inbox.empty():
        m = inbox.get()[1]
        if m["t"] == "start": start = m
    time.sleep(0.005)
cs = net.RemoteSession(conn, inbox, start)
guest = w.players[cs.pid]
seen = []
for f in range(240):
    if f == 30: guest.x, guest.y = w.map.flag_homes[0]            # the guest (red) grabs the blue flag
    hs.update(1 / 60); seen += [e for e in cs.update(1 / 60) if e[0] == "flag"]; time.sleep(1 / 240)
print("4. client: mode %s, flags %s, own tank carrying %s, flag events received %s"
      % (cs.world.mode, [f[0] for f in cs.world.flags], cs.me().flag, [e[1] for e in seen]))
assert cs.world.flags[0][0] == 1 and cs.me().flag == 0 and seen
conn.close(); hs.close()

# 5. two respawns each, then out; a team with nobody left loses
w = World(dict(S, cap_limit=5))
a = w.add_player(dict(name="Blue1", color=[1, 1, 1]), 0); a2 = w.add_player(dict(name="Blue2", color=[1, 1, 1]), 0)
b = w.add_player(dict(name="Red", color=[2, 2, 2]), 1)
w.step(0.0)
log = []
for life in range(3):
    assert a.alive and not a.out
    destroy(a, b); log.append((a.respawns, a.out))
    for _ in range(60 * 11): w.step(1 / 60)
assert log == [(1, False), (0, False), (0, True)], log
assert not a.alive and a.out and w.over is None, "third death should put the tank out, with a teammate still in"
print("5. respawns left after each death: %s -> out; stays dead after 11 s: %s; match continues with a teammate left"
      % ([l[0] for l in log], not a.alive))
snap = w.snapshot(); row = next(r for r in snap["tk"] if r[0] == a.pid)
w3 = World.from_dict(json.loads(json.dumps(w.to_dict())))
assert row[15] == -1 and w3.players[a.pid].out and w3.players[a2.pid].respawns == 2
for life in range(3):
    destroy(a2, b)
    for _ in range(60 * 11): w.step(1 / 60)
assert w.over == 1, w.over
print("   whole blue team out -> red wins (over=%s); snapshot and save/load carry the state" % w.over)
wt = World(dict(S, mode="tdm")); x = wt.add_player(dict(name="X", color=[1, 1, 1]), 0); y = wt.add_player(dict(name="Y", color=[1, 1, 1]), 1)
wt.step(0.0); w = wt
for life in range(4):
    destroy(x, y)
    for _ in range(60 * 5): wt.step(1 / 60)
assert x.alive and not x.out
print("   deathmatch is unaffected: still respawning after 4 deaths")
print("ALL OK")
