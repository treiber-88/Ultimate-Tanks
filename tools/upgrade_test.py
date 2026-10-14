"""Headless checks for tank upgrades: effects, purchase rules, saving, multiplayer and the Juggernaut lock."""
import json, math, os, random, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ut import ai, data, net, profile as profiles
from ut.world import World

S = dict(map="farmland", seed=2, kill_limit=0, time_limit=0)
FULL = {"basic": [5, 5, 5]}


def tank(up, mode="tdm"):
    w = World(dict(S, mode=mode))
    t = w.add_player(dict(name="T", color=[1, 1, 1], upgrades=up), 0)
    w.step(0.0)
    return w, t


# 1. effects
w0, plain = tank({})
w1, maxed = tank(FULL)
for w, t in ((w0, plain), (w1, maxed)):
    t.throttle = 1.0
    for _ in range(180): w.step(1 / 60)
rl0, rl1 = w0.reload_time(plain, data.WEAPONS[0]), w1.reload_time(maxed, data.WEAPONS[0])
mg0, mg1 = w0.reload_time(plain, data.WEAPONS[1]), w1.reload_time(maxed, data.WEAPONS[1])
print("1. level 5 everything vs none: speed %.0f vs %.0f px/s (+%.0f%%), strength %.0f vs %.0f (+%.0f%%), shell reload %.2f vs %.2f s, mg interval %.3f vs %.3f s"
      % (abs(maxed.speed), abs(plain.speed), 100 * (abs(maxed.speed) / abs(plain.speed) - 1), maxed.max_hp, plain.max_hp,
         100 * (maxed.max_hp / plain.max_hp - 1), rl1, rl0, mg1, mg0))
assert abs(abs(maxed.speed) / abs(plain.speed) - 1.30) < 0.02 and abs(maxed.max_hp / plain.max_hp - 1.5) < 1e-6
assert abs(rl1 / rl0 - 0.6) < 1e-6 and abs(mg1 / mg0 - 0.6) < 1e-6
w, t = tank({"medium": [5, 5, 5]})
assert t.max_hp == data.tank_hp(t.spec), "upgrades belong to one tank only"

# 2. buying in battle
w, t = tank({})
t.credits = 10000; t.tanks.append("goliath")
assert not w.buy(t.pid, "upgrade", "heavy:0"), "cannot upgrade a tank you do not own"
assert not w.buy(t.pid, "upgrade", "basic:7") and not w.buy(t.pid, "upgrade", "nonsense")
t.hp = t.max_hp / 2
spent = []
for lvl in range(1, 7):
    before = t.credits
    ok = w.buy(t.pid, "upgrade", "basic:1")
    spent.append(before - t.credits if ok else "refused")
print("2. armour levels bought in battle cost %s; strength now %.0f with the damage kept at %.0f%%" % (spent, t.max_hp, 100 * t.hp / t.max_hp))
assert spent == [40, 80, 120, 160, 200, "refused"] and abs(t.hp / t.max_hp - 0.5) < 1e-6
t.credits = 50
assert not w.buy(t.pid, "upgrade", "goliath:0"), "160 credits needed"

# 3. profile: buying, absorbing battle results, saving
profiles.SAVES = tempfile.mkdtemp()
p = profiles.Profile("Up"); p.credits = 1000; p.tanks.append("heavy")
assert p.buy_upgrade("heavy", 0) and p.buy_upgrade("heavy", 0) and not p.buy_upgrade("mammoth", 2)
w, t = World(dict(S)), None
t = w.add_player(p.loadout(), 0); t.credits += 500
w.buy(t.pid, "upgrade", "heavy:2"); w.buy(t.pid, "upgrade", "basic:0")
p.absorb(t.state()); p.save()
q = profiles.Profile.load(p.path)
print("3. profile after garage + battle purchases, saved and reloaded:", q.upgrades, "credits", q.credits)
assert q.upgrades == {"heavy": [2, 0, 1], "basic": [1, 0, 0]}
w2 = World.from_dict(json.loads(json.dumps(w.to_dict())))
assert w2.players[t.pid].upgrades == t.upgrades

# 4. a client's forged upgrades are cleaned; a client sees real strengths
lo = net.clean_loadout(dict(name="Cheat", upgrades={"basic": [99, -4, "x"], "goliath": [9, 9, 9], "bogus": [1, 1, 1]}))
print("4. forged upgrades from a client become:", lo["upgrades"])
assert lo["upgrades"] == {"goliath": [5, 5, 5]}
srv = net.Server(27951)
w = World(dict(S)); h = w.add_player(dict(name="Host", color=[1, 1, 1], upgrades=FULL), 0)
hs = net.LocalSession(w, h.pid, srv, {})
conn, inbox = net.connect("127.0.0.1", 27951); conn.send({"t": "join", "lo": dict(name="Guest", credits=500, upgrades={"basic": [1, 2, 3]})})
start = None
while start is None:
    hs.update(1 / 60)
    while not inbox.empty():
        m = inbox.get()[1]
        if m["t"] == "start": start = m
    time.sleep(0.004)
cs = net.RemoteSession(conn, inbox, start)
cs.buy("upgrade", "basic:0")
for _ in range(120): hs.update(1 / 60); cs.update(1 / 60); time.sleep(1 / 300)
host_seen = cs.world.players[h.pid]; me = cs.me()
print("   client sees the host's strength as %.0f (real %.0f); its own upgrades %s, own strength %.0f"
      % (host_seen.max_hp, h.max_hp, me.upgrades, me.max_hp))
assert abs(host_seen.max_hp - h.max_hp) < 0.2 and me.upgrades == {"basic": [2, 2, 3]} and abs(me.max_hp - 20 * 1.2) < 0.2
conn.close(); hs.close()

# 5. Juggernaut ignores upgrades
w = World(dict(S, mode="jugg"))
ts = [w.add_player(dict(name="T%d" % i, color=[1, 1, 1], upgrades={"basic": [5, 5, 5], "goliath": [5, 5, 5]}), 0) for i in range(3)]
for _ in range(5): w.step(1 / 60)
for t in ts:
    role = "Juggernaut" if t.pid == w.ms["jugg"] else "hunter"
    print("5. Juggernaut mode, fully upgraded %-10s: %s strength %.0f (base %.0f), shell reload %.1f s"
          % (role, t.tank_key, t.max_hp, data.tank_hp(t.spec), w.reload_time(t, data.WEAPONS[t.sel[0]])))
    assert t.max_hp == data.tank_hp(t.spec) and w.reload_time(t, data.WEAPONS[t.sel[0]]) == data.WEAPONS[t.sel[0]]["reload"]

# 6. the AI spends money on upgrades too
w = World(dict(S, time_limit=300)); w.ai = ai.AIController(w)
rng = random.Random(3); used = set()
for team in (0, 1):
    for i in range(6): w.ai.attach(w.add_player(ai.make_ai_loadout(rng, team, i, 2, used), team, True, 2))
while w.over is None: w.step(1 / 60); w.events.clear()
levels = sum(sum(v) for t in w.players.values() for v in t.upgrades.values())
print("6. 12 AI tanks bought %d upgrade levels in a 5-minute battle; tanks now %s" % (levels, sorted(t.tank_key for t in w.players.values())))
print("ALL OK")
