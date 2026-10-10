"""Headless profile of a battle: prints the hottest functions. Usage: python tools/profile_battle.py [w h]"""
import cProfile, os, pstats, sys, time
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pygame, main
from ut import net, profile as profiles, screens
if len(sys.argv) > 2: main.WINDOW = (int(sys.argv[1]), int(sys.argv[2]))
profiles.SAVES = os.path.join(os.environ.get("TEMP", "."), "ut_profile_saves")
app = main.App(); p = profiles.Profile("Prof"); app.set_profile(p)
w, pids = screens.build_world(app, dict(map="valley", seed=7, kill_limit=0, time_limit=0, difficulty=1), 19, 20)
b = screens.Battle(app, net.LocalSession(w, pids[0])); app.switch(b)
me = w.players[pids[0]]; me.is_ai = True; w.ai.attach(me); b.session.set_input = lambda *a: None
def frames(n):
    for _ in range(n):
        app.ui.begin(app.screen, []); app.current.frame(1 / 60)
frames(60 * 25)           # let the armies meet
ts = []
pr = cProfile.Profile(); pr.enable()
for _ in range(600):
    t = time.perf_counter(); frames(1); ts.append(time.perf_counter() - t)
pr.disable()
ts.sort()
print("frame ms: median %.1f  p95 %.1f  max %.1f   particles %d  projectiles %d" % (ts[300] * 1000, ts[570] * 1000, ts[-1] * 1000, len(b.view.particles), len(w.projectiles)))
pstats.Stats(pr).sort_stats("tottime").print_stats(22)
