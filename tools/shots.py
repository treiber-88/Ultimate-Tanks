"""Headless smoke test: drives the real game screens off-screen and saves screenshots for review.

Usage: python tools/shots.py OUT_DIR [width height]
"""
import os
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pygame

import main
from ut import net, profile as profiles, screens

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
if len(sys.argv) > 3:
    main.WINDOW = (int(sys.argv[2]), int(sys.argv[3]))
profiles.SAVES = os.path.join(out, "saves")          # never touch real save files

app = main.App()
p = profiles.Profile("Tester")
p.credits = 135
p.tanks += ["medium"]
p.weapons += ["gatling", "heavy_shell"]
p.tank = "medium"
p.color = [176, 46, 42]
p.save()
app.set_profile(p)


def frames(n, dt=1 / 60, events=()):
    for i in range(n):
        app.ui.begin(app.screen, list(events) if i == 0 else [])
        app.current.frame(dt)


def shot(name):
    pygame.image.save(app.screen, os.path.join(out, name + ".png"))
    print("saved", name)


app.switch(screens.Menu(app))
frames(2)
shot("01_menu")
app.switch(screens.Garage(app))
frames(2)
shot("02_garage")
app.switch(screens.Setup(app, host=False))
frames(2)
shot("03_setup")

settings = dict(map="valley", seed=7, kill_limit=40, time_limit=600, difficulty=1)
w, pids = screens.build_world(app, settings, 8, 9)
battle = screens.Battle(app, net.LocalSession(w, pids[0]))
app.switch(battle)
pygame.mouse.get_pos = lambda: (app.screen.get_width() // 2 + 260, app.screen.get_height() // 2 - 40)
t0 = time.time()
frames(120)
shot("04_battle_start")
# drive toward the fight for a while with the AI at the wheel of our tank
me = w.players[pids[0]]
me.is_ai = True
w.ai.attach(me)
real_set = battle.session.set_input
battle.session.set_input = lambda *a: None
n = 0
worst = 0.0
for chunk in range(40):
    for _ in range(60):
        f0 = time.time()
        frames(1)
        worst = max(worst, time.time() - f0)
        n += 1
    if me.alive and any(e.alive and e.team != me.team and abs(e.x - me.x) < 700 and abs(e.y - me.y) < 420
                        for e in w.players.values()):
        frames(25)
        break
el = time.time() - t0
print("battle frames %d, avg %.1f ms, worst %.0f ms" % (n + 120, el / (n + 120) * 1000, worst * 1000))
shot("05_battle_fight")
frames(90)
shot("06_battle_fight2")
battle.shop_open = True
frames(2)
shot("07_battle_shop")
battle.shop_open = False
# a nuke for the camera
from ut.data import WEAPON_INDEX
w.spawn_projectile(me.pid, me.team, WEAPON_INDEX["nuke_shell"], me.x + 60, me.y, 0.3)
w.spawn_projectile(me.pid, me.team, WEAPON_INDEX["combust_shell"], me.x - 60, me.y, 2.6)
for k, v in w.projectiles.items():
    v[8] = 420
frames(48)
shot("08_nuke")
frames(70)
shot("09_aftermath")
battle.paused = True
frames(2)
shot("09b_pause")
battle.paused = False
pygame.key.get_pressed = lambda _o=pygame.key.get_pressed: type("K", (), {"__getitem__": lambda self, k: k == pygame.K_TAB})()
frames(2)
shot("09c_scores")
pygame.key.get_pressed = lambda: type("K", (), {"__getitem__": lambda self, k: False})()
# save, reload and compare
d = dict(world=w.to_dict(), pid=me.pid)
import json
from ut.world import World
w2 = World.from_dict(json.loads(json.dumps(d["world"])))
print("save/load: players %d -> %d, scores %s -> %s, time %.1f -> %.1f" % (len(w.players), len(w2.players), w.scores, w2.scores, w.time, w2.time))
w._finish(0)
frames(100)
shot("10_results")
srv = net.Server(27992)
app.switch(screens.Lobby(app, srv, settings, 4, 5))
c, inbox = net.connect("127.0.0.1", 27992)
c.send({"t": "join", "lo": dict(name="Friend", color=[42, 146, 140])})
time.sleep(0.3)
frames(3)
shot("12_lobby")
c.close()
app.switch(screens.Join(app))
frames(2)
shot("13_join")
app.switch(screens.ProfileSelect(app))
frames(2)
shot("11_profiles")
pygame.quit()
