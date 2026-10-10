"""Headless soak test: plays battles with random human input (driving, aiming, firing, shop, tank swaps)."""
import math, os, random, sys, time, traceback
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pygame, main
from ut import net, profile as profiles, screens, data

profiles.SAVES = os.path.join(os.environ.get("TEMP", "."), "ut_fuzz_saves")
main.WINDOW = (1600, 900)
app = main.App()
p = profiles.Profile("Fuzz"); p.credits = 5000; app.set_profile(p)
seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 240
rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
KEYS = [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_SPACE, pygame.K_TAB]
held = set(); buttons = [False, False, False]; mouse = [800, 450]
pygame.key.get_pressed = lambda: type("K", (), {"__getitem__": lambda self, k: k in held})()
pygame.mouse.get_pressed = lambda *a, **k: tuple(buttons)
pygame.mouse.get_pos = lambda: tuple(mouse)
PRESS = [pygame.K_q, pygame.K_e, pygame.K_b, pygame.K_ESCAPE] + list(range(pygame.K_0, pygame.K_9 + 1))
for mi, m in enumerate(data.MAPS):
    w, pids = screens.build_world(app, dict(map=m["key"], seed=rng.randrange(999), kill_limit=0, time_limit=0, difficulty=2), 8, 9)
    b = screens.Battle(app, net.LocalSession(w, pids[0])); app.switch(b)
    me = w.players[pids[0]]
    me.tanks = [t["key"] for t in data.TANKS]; me.weapons = [x["key"] for x in data.WEAPONS]
    t0 = time.time(); f = 0
    try:
        while w.time < seconds:
            f += 1
            ev = []
            if rng.random() < 0.05:
                k = rng.choice(KEYS); (held.discard if k in held else held.add)(k)
            if rng.random() < 0.6: held.add(pygame.K_w)
            if rng.random() < 0.04: buttons[0] = not buttons[0]
            if rng.random() < 0.04: buttons[2] = not buttons[2]
            if rng.random() < 0.1: mouse[:] = [rng.randrange(1600), rng.randrange(900)]
            if rng.random() < 0.01: ev.append(pygame.event.Event(pygame.KEYDOWN, key=rng.choice(PRESS), unicode="", mod=0))
            if rng.random() < 0.01: ev.append(pygame.event.Event(pygame.MOUSEWHEEL, y=rng.choice((-1, 1)), x=0))
            if rng.random() < 0.02: ev.append(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=tuple(mouse)))
            if rng.random() < 0.004: w.select_tank(me.pid, rng.choice(me.tanks))
            if b.paused and rng.random() < 0.2: b.paused = False
            if rng.random() < 0.002:                      # drop us somewhere new, often into trees
                o = rng.choice(w.map.objects); me.x, me.y = o["x"] + 90, o["y"]
            app.ui.begin(app.screen, ev)
            app.current.frame(1 / 60)
            if app.current is not b:
                print("  left battle screen at t=%.1f -> %s" % (w.time, type(app.current).__name__)); break
        print("%s ok: %.0fs game, %d frames, %.1f ms/frame, crushed %d, kills %s" % (m["key"], w.time, f, (time.time() - t0) / f * 1000, len(w.crushed), w.scores))
    except Exception:
        print("CRASH on %s at t=%.1f frame %d tank=%s sel=%s" % (m["key"], w.time, f, me.tank_key, me.sel))
        traceback.print_exc()
        break
pygame.quit()
