"""Headless test of flows the screenshot run does not cover: a client's battle screen, save/continue, the shop."""
import os, sys, time
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pygame, main
from ut import net, profile as profiles, screens, data

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
profiles.SAVES = os.path.join(out, "saves_flow")
for f in os.listdir(profiles.SAVES) if os.path.isdir(profiles.SAVES) else []:
    os.remove(os.path.join(profiles.SAVES, f))
main.WINDOW = (1600, 900)
app = main.App()
assert isinstance(app.current, screens.ProfileSelect), "fresh install should start on commander creation"


def frames(n, events=()):
    for i in range(n):
        app.ui.begin(app.screen, list(events) if i == 0 else [])
        app.current.frame(1 / 60)


def click(vx, vy):
    """Click at a virtual (1080-tall) coordinate."""
    s = app.ui.s
    pos = (int(vx * s), int(vy * s))
    pygame.mouse.get_pos = lambda: pos
    frames(1, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)])


def typed(text):
    for ch in text:
        frames(1, [pygame.event.Event(pygame.KEYDOWN, key=ord(ch), unicode=ch, mod=0)])


# 1. create a commander through the UI
frames(2)
x0 = app.ui.vw / 2 - 480
click(x0 + 100, 900); typed("Ace"); click(x0 + 700, 900)
assert app.profile and app.profile.name == "Ace", "commander not created"
assert isinstance(app.current, screens.Garage)
p = app.profile
print("1. commander created:", p.name, p.tanks, p.weapons, p.credits)

# 2. shop: cannot afford, then can
gx = app.ui.vw / 2 - 890
frames(2)
click(gx + 100, 30 + 96 + 124 + 40)                 # select Medium Tank in the list
click(gx + 460 + 200, 30 + 860 - 70)                # Buy
assert "medium" not in p.tanks, "bought a tank with no money"
p.credits = 800
click(gx + 460 + 200, 30 + 860 - 70)
assert "medium" in p.tanks and p.credits == 560, (p.tanks, p.credits)
click(gx + 460 + 200, 30 + 860 - 70)                # Use this tank
assert p.tank == "medium"
click(gx + 1060 + 600, 30 + 84 + 76 * 3 + 30)       # buy Heavy Shell (40)
assert "heavy_shell" in p.weapons and p.credits == 400, (p.weapons, p.credits)
click(gx + 100, 30 + 96 + 124 * 3 + 40)             # Mammoth: buy, but no usable ammo yet
click(gx + 460 + 200, 30 + 860 - 70)
assert "mammoth" not in p.tanks                      # 600 > 400
p.credits = 600
click(gx + 460 + 200, 30 + 860 - 70)
assert "mammoth" in p.tanks
click(gx + 460 + 200, 30 + 860 - 70)                # any tank can carry any weapon, so this just works
assert p.tank == "mammoth", p.tank
click(gx + 100, 30 + 96 + 124 + 40)                 # back to the Medium for the rest of the test
click(gx + 460 + 200, 30 + 860 - 70)
assert p.tank == "medium", p.tank
click(gx + 180 + 90 * 5 + 40, 970)                  # paint: Crimson
assert tuple(p.color) == data.COLORS[5][1], p.color
reloaded = profiles.Profile.load(p.path)
print("2. shop ok:", reloaded.tanks, reloaded.weapons, reloaded.credits, "tank", reloaded.tank, "colour", reloaded.color)

# 3. single-player battle -> save & quit -> continue
settings = dict(map="highlands", seed=4, kill_limit=10, time_limit=300, difficulty=1)
w, pids = screens.build_world(app, settings, 3, 4)
app.switch(screens.Battle(app, net.LocalSession(w, pids[0])))
frames(200)
me = w.players[pids[0]]
me.credits += 77                                    # pretend we earned something
pos = (round(me.x), round(me.y))
b = app.current
b.paused = True
frames(2)
x = app.ui.vw / 2 - 260
click(x + 200, 530)                                 # Save & quit
assert isinstance(app.current, screens.Menu) and p.has_battle(), "battle was not saved"
assert p.credits == 77, p.credits
p.credits -= 20                                     # spend in the garage while a battle is saved
p.save()
app.current.choose("continue")
frames(5)
assert isinstance(app.current, screens.Battle), type(app.current)
w2 = app.current.world
me2 = app.current.session.me()
print("3. save/continue ok: time %.1f -> %.1f, players %d, position %s -> %s, credits %d, tank %s"
      % (w.time, w2.time, len(w2.players), pos, (round(me2.x), round(me2.y)), me2.credits, me2.tank_key))
assert me2.credits == 57
frames(120)

# 4. a client's battle screen against a host in the same process
app.switch(screens.Menu(app))
server = net.Server(27993)
hw, hp = screens.build_world(app, dict(map="valley", seed=9, kill_limit=0, time_limit=0, difficulty=2), 5, 6)
host = net.LocalSession(hw, hp[0], server, {})
conn, inbox = net.connect("127.0.0.1", 27993)
p.credits = 200                                     # enough for a Gatling (80) at the new prices
conn.send({"t": "join", "lo": p.loadout()})
start = None
while start is None:
    host.update(1 / 60)
    while not inbox.empty():
        m = inbox.get()[1]
        if m["t"] == "start":
            start = m
    time.sleep(0.005)
client = net.RemoteSession(conn, inbox, start)
app.switch(screens.Battle(app, client))
mine = hw.players[client.pid]
for f in range(60 * 14):
    host.update(1 / 60)
    if f == 300:
        app.current.shop_open = True
    if f == 330:
        client.buy("weapon", "gatling")
        app.current.shop_open = False
    if f % 120 == 0:                                # keep our tank near a fight for the camera
        foe = min((t for t in hw.players.values() if t.alive and t.team != mine.team), key=lambda t: abs(t.x - 4000),
                  default=None)
        if foe and mine.alive:
            mine.x, mine.y = foe.x - 300, foe.y + 40
    frames(1)
    time.sleep(0.002)
cm = client.me()
print("4. client battle ok: %d players mirrored, client sees tank %s hp %.0f, weapons %s, zones %d, projectiles %d"
      % (len(client.world.players), cm.tank_key, cm.hp, cm.weapons, len(client.world.zones), len(client.world.projectiles)))
assert "gatling" in cm.weapons
pygame.image.save(app.screen, os.path.join(out, "client_view.png"))
server.close()
for _ in range(200):
    frames(1)
    time.sleep(0.005)
    if client.lost:
        break
print("5. host quit -> client told:", client.lost)
assert client.lost
frames(3)
pygame.quit()
print("ALL OK")
