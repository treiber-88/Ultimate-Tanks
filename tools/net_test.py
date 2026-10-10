"""Headless multiplayer test: a host and a client in one process over localhost."""
import math, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ut import net, ai, data
from ut.world import World

PORT = 27991
server = net.Server(PORT)
settings = dict(map="farmland", seed=11, kill_limit=0, time_limit=0, difficulty=2)
w = World(settings); w.ai = ai.AIController(w)
host = w.add_player(dict(name="Host", color=[1, 2, 3]), 0)
rng = random.Random(1); used = set()
for team in (0, 1):
    for i in range(6):
        w.ai.attach(w.add_player(ai.make_ai_loadout(rng, team, i, 2, used), team, True, 2))
hs = net.LocalSession(w, host.pid, server, {})

conn, inbox = net.connect("127.0.0.1", PORT)
conn.send({"t": "join", "lo": dict(name="Guest<script>", color=[9, 9, 9], credits=500, tanks=["basic", "bogus"], weapons=["nuke_shell"], tank="basic")})
start = None
t0 = time.time()
while start is None and time.time() - t0 < 5:
    hs.update(1 / 60)
    while not inbox.empty():
        _c, msg = inbox.get()
        if msg["t"] == "start": start = msg
    time.sleep(0.005)
assert start, "no start message"
cs = net.RemoteSession(conn, inbox, start)
print("client joined as pid", cs.pid, "roster size", len(cs.world.players), "map objects equal:", len(cs.world.map.objects) == len(w.map.objects),
      "solid grids equal:", bool((cs.world.map.solid == w.map.solid).all()))
guest = w.players[cs.pid]
print("guest loadout after cleaning:", guest.name, guest.tanks, guest.weapons, guest.credits, "team", guest.team)

cs.buy("tank", "goliath"); cs.buy("weapon", "combust_shell")
ev_host = ev_client = 0; err = []
for f in range(60 * 12):
    cs.set_input(1.0, 0.3, 1.0, f > 200, True)
    ev_host += len(hs.update(1 / 60))
    ev_client += len(cs.update(1 / 60))
    if f == 120: cs.select_tank("goliath")
    if f % 60 == 59:
        g2 = cs.world.players[cs.pid]
        err.append(math.hypot(g2.x - guest.x, g2.y - guest.y))
    time.sleep(1 / 240)
g2 = cs.world.players[cs.pid]
print("events host %d client %d" % (ev_host, ev_client))
print("guest on host: tank %s credits %d alive %s pos (%.0f, %.0f)" % (guest.tank_key, guest.credits, guest.alive, guest.x, guest.y))
print("guest on client: tank %s credits %d weapons %s" % (g2.tank_key, g2.credits, g2.weapons))
print("position error client vs host (px) each second:", [round(e) for e in err])
print("client projectiles alive %d, host %d; scores host %s client %s" % (len(cs.world.projectiles), len(w.projectiles), w.scores, cs.world.scores))
conn.close(); t1 = time.time()
while cs.pid in w.players and time.time() - t1 < 3:
    hs.update(1 / 60); time.sleep(0.01)
print("host removed guest after disconnect:", cs.pid not in w.players)
hs.close()
