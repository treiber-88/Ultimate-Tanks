"""Multiplayer smoothness test over a simulated bad connection.

A host and a client run in this process, joined through a proxy that delays every packet (a base delay plus
random jitter, in both directions). Reports how smooth other tanks look on the client and how quickly the
client's own tank answers the controls.

Usage: python tools/lag_test.py [one-way delay ms] [jitter ms] [seconds]
"""
import math
import os
import random
import socket
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ut import ai, net
from ut.world import World

DELAY = float(sys.argv[1]) / 1000 if len(sys.argv) > 1 else 0.04
JITTER = float(sys.argv[2]) / 1000 if len(sys.argv) > 2 else 0.05
SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 14.0
HOST_PORT, PROXY_PORT = 27981, 27982


def pump(src, dst, rng):
    """Forward bytes with delay; order is preserved, as TCP would."""
    release = 0.0
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            due = max(release, time.perf_counter() + DELAY + rng.random() * JITTER)
            release = due
            wait = due - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            dst.sendall(data)
    except OSError:
        pass
    for s in (src, dst):
        try:
            s.close()
        except OSError:
            pass


def proxy():
    ls = socket.socket()
    ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ls.bind(("127.0.0.1", PROXY_PORT))
    ls.listen(1)

    def run():
        c, _ = ls.accept()
        h = socket.create_connection(("127.0.0.1", HOST_PORT))
        for s in (c, h):
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        threading.Thread(target=pump, args=(c, h, random.Random(1)), daemon=True).start()
        threading.Thread(target=pump, args=(h, c, random.Random(2)), daemon=True).start()
    threading.Thread(target=run, daemon=True).start()


server = net.Server(HOST_PORT)
w = World(dict(map="farmland", seed=11, kill_limit=0, time_limit=0, difficulty=1))
w.ai = ai.AIController(w)
host = w.add_player(dict(name="Host", color=[1, 2, 3]), 0)
rng = random.Random(1)
used = set()
for team in (0, 1):
    for i in range(8):
        w.ai.attach(w.add_player(ai.make_ai_loadout(rng, team, i, 1, used), team, True, 1))
hs = net.LocalSession(w, host.pid, server, {})
proxy()
conn, inbox = net.connect("127.0.0.1", PROXY_PORT)
conn.send({"t": "join", "lo": dict(name="Guest", color=[9, 9, 9])})
start = None
while start is None:
    hs.update(1 / 60)
    while not inbox.empty():
        m = inbox.get()[1]
        if m["t"] == "start":
            start = m
    time.sleep(1 / 60)
cs = net.RemoteSession(conn, inbox, start)
mine_host = w.players[cs.pid]

FPS = 60.0
frame = 0
steps = {}             # pid -> list of per-frame displayed movement (px) while that tank is driving
last = {}
own_err = []
react = None
go_at = 3.0            # the guest presses "forward" at this moment
t0 = time.perf_counter()
next_tick = t0
while True:
    now = time.perf_counter()
    t = now - t0
    if t > SECONDS:
        break
    driving = t >= go_at
    turn = 0.5 * math.sin(t * 1.3) if driving else 0.0
    cs.set_input(1.0 if driving else 0.0, turn, 0.0, False, False, 400.0)
    hs.update(1 / FPS)
    cs.update(1 / FPS)
    me = cs.world.players.get(cs.pid)
    if me and me.alive:
        if driving and react is None and "own0" in last and math.hypot(me.x - last["own0"][0], me.y - last["own0"][1]) > 3:
            react = t - go_at
        if not driving:
            last["own0"] = (me.x, me.y)
        if t > go_at + 2 and mine_host.alive:
            own_err.append(math.hypot(me.x - mine_host.x, me.y - mine_host.y))
    if t > 4.0:
        for pid, tk in cs.world.players.items():
            if pid == cs.pid or not tk.alive:
                last.pop(pid, None)
                continue
            src = w.players.get(pid)
            if pid in last and src and src.alive and abs(src.speed) > 100:
                steps.setdefault(pid, []).append(math.hypot(tk.x - last[pid][0], tk.y - last[pid][1]))
            last[pid] = (tk.x, tk.y)
    frame += 1
    next_tick += 1 / FPS
    pause = next_tick - time.perf_counter()
    if pause > 0:
        time.sleep(pause)

all_steps = [s for v in steps.values() if len(v) > 60 for s in v]
mean = statistics.mean(all_steps)
frozen = sum(1 for s in all_steps if s < mean * 0.15) / len(all_steps)
jumps = sum(1 for s in all_steps if s > mean * 2.0) / len(all_steps)
print("connection: %.0f ms each way + up to %.0f ms jitter   (%d frames, %d samples of other tanks)"
      % (DELAY * 1000, JITTER * 1000, frame, len(all_steps)))
print("other tanks on the client:  frozen frames %.1f%%   jump frames %.1f%%   unevenness %.2f  (0 = perfectly smooth)"
      % (frozen * 100, jumps * 100, statistics.pstdev(all_steps) / mean))
print("own tank:  starts moving %.0f ms after pressing forward   |   drift from the host's position: avg %.0f px, worst %.0f px"
      % ((react or 9.99) * 1000, statistics.mean(own_err), max(own_err)))
conn.close()
hs.close()
