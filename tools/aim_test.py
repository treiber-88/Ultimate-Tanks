"""Headless checks: aimed fire lands on the cursor point; tanks flatten bushes; only heavy tanks fell trees."""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ut import data
from ut.world import World, angle_diff
from ut.data import WEAPON_INDEX as WI, SHELL, AUTO

ALL_T = [t["key"] for t in data.TANKS]; ALL_W = [w["key"] for w in data.WEAPONS]


def fresh(tank):
    w = World(dict(map="highlands", seed=4, kill_limit=0, time_limit=0))
    t = w.add_player(dict(name="P", color=[1, 1, 1], tanks=ALL_T, weapons=ALL_W, tank=tank), 0)
    for _ in range(60): w.step(1 / 60)
    assert t.alive
    return w, t


def open_spot(w, t, need=1500):
    """Find a place with a clear line in direction 0.6 rad."""
    for x, y in w.map.spawns[0]:
        if all(not w.map.shot_blocked_at(x + math.cos(0.6) * d, y + math.sin(0.6) * d) for d in range(0, need, 15)):
            t.x, t.y = x, y; return
    raise SystemExit("no open lane found")


# 1. aimed shells burst on the cursor point, for every barrel of every tank
print("1. aimed fire")
for tank, weapon in (("basic", "basic_shell"), ("heavy", "heavy_shell"), ("goliath", "death_shell"), ("medium", "combust_shell")):
    w, t = fresh(tank); open_spot(w, t)
    w.select_weapon(t.pid, SHELL, WI[weapon])
    worst = 0; shots = 0
    for dist, ang in ((300, 0.6), (700, 0.6), (1100, 0.62), (450, 0.58)) * 2:     # twice: every barrel fires
        t.angle = 0.2; t.aim = ang; t.aim_dist = dist
        px, py = t.pivot(); target = (px + math.cos(ang) * dist, py + math.sin(ang) * dist)
        fired = landed = False
        for _ in range(60 * 12):
            t.fire = [not fired, False]
            w.step(1 / 60)
            for e in w.events:
                if e[0] == "shot": fired = True
                if e[0] == "hit":
                    worst = max(worst, math.hypot(e[2] - target[0], e[3] - target[1])); shots += 1; landed = True
            w.events.clear()
            if landed and not w.projectiles: break       # wait for every barrel's shell
    print("   %-8s %-14s %d bursts, worst miss %.1f px" % (tank, weapon, shots, worst))
    assert shots >= 8 and worst < 16, (tank, worst)

# beyond range: bursts at max range, short of the cursor
w, t = fresh("basic"); open_spot(w, t, 1400)
t.aim = t.turret = 0.6; t.aim_dist = 3000; t.fire = [True, False]
hit = None
for _ in range(300):
    w.step(1 / 60)
    hit = next((e for e in w.events if e[0] == "hit"), hit); w.events.clear()
    t.fire = [False, False]
print("   out of range: burst %.0f px from the muzzle (range %d)" % (math.hypot(hit[2] - t.muzzle(0)[0], hit[3] - t.muzzle(0)[1]), data.WEAPONS[0]["range"]))

# turret not yet on the cursor: no shot until it swings round
w, t = fresh("mammoth"); open_spot(w, t)
t.turret = 0.6 + 2.0; t.aim = 0.6; t.aim_dist = 500; t.fire = [True, True]
first = None
for f in range(300):
    w.step(1 / 60)
    if first is None and any(e[0] == "shot" for e in w.events): first = (f, abs(angle_diff(t.aim, t.turret)))
    w.events.clear()
print("   swinging turret: first shot on frame %d with the gun %.3f rad off the cursor" % first)
assert first[0] > 30 and first[1] <= data.FIRE_ARC + 0.02

# tracer passes through the cursor point and carries on
w, t = fresh("speed"); open_spot(w, t)
t.aim = t.turret = 0.6; t.aim_dist = 400; t.fire = [False, True]
px, py = t.pivot(); target = (px + math.cos(0.6) * 400, py + math.sin(0.6) * 400)
w.select_weapon(t.pid, AUTO, WI["tracer"]); w.step(1 / 60); t.fire = [False, False]
p = next(iter(w.projectiles.values())); best = 1e9; far = 0
while w.projectiles:
    w.step(1 / 240); best = min(best, math.hypot(p[4] - target[0], p[5] - target[1])); far = max(far, math.hypot(p[4] - px, p[5] - py))
print("   tracer: passes %.1f px from the cursor point, flies on to %.0f px" % (best, far))
assert best < 8 and far > 800

# 2. crushing
print("2. crushing")
for tank in ("basic", "medium", "speed", "heavy", "mammoth", "goliath"):
    w, t = fresh(tank)
    m = w.map
    bush = next(i for i, o in enumerate(m.objects) if o["kind"] == "bush" and not m.blocked_circle(o["x"] - 150, o["y"], 70) and not m.blocked_circle(o["x"], o["y"], 70))
    tree = next(i for i, o in enumerate(m.objects) if o["kind"] == "tree" and all(not m.blocked_circle(o["x"] - d, o["y"], 66) for d in range(110, 260, 20)))
    res = []
    for idx in (bush, tree):
        o = m.objects[idx]
        t.x, t.y, t.angle, t.speed = o["x"] - 220, o["y"], 0.0, 0.0
        t.throttle = 1.0
        for _ in range(60 * 5): w.step(1 / 60)
        res.append((idx in w.crushed, round(t.x - o["x"])))
    solid_after = m.shot_blocked_at(m.objects[tree]["x"], m.objects[tree]["y"])
    print("   %-8s bush flattened: %-5s tree felled: %-5s (stopped %4d px %s the tree, trunk still solid: %s)"
          % (tank, res[0][0], res[1][0], abs(res[1][1]), "past" if res[1][1] > 0 else "before", solid_after))
    assert res[0][0], "bush survived"
    assert res[1][0] == (tank in ("heavy", "mammoth", "goliath")), tank
    assert solid_after != res[1][0]

# 3. saved battles remember what was flattened
w, t = fresh("goliath")
for i, o in enumerate(w.map.objects):
    if o["kind"] in ("tree", "bush") and i % 7 == 0: w.crush(i)
import json
w2 = World.from_dict(json.loads(json.dumps(w.to_dict())))
print("3. save/load keeps %d flattened objects: %s; solid grids match: %s" % (len(w.crushed), w2.crushed == w.crushed, bool((w2.map.solid == w.map.solid).all())))
assert w2.crushed == w.crushed and (w2.map.solid == w.map.solid).all()
print("ALL OK")
