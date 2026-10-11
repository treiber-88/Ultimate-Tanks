"""Menus, the garage/shop, lobby and the battle screen."""
import math
import random
import time

import pygame

from . import data, net, profile as profiles
from .ai import AIController, make_ai_loadout
from .data import WEAPONS, TANKS, TANK_INDEX, WEAPON_INDEX, SHELL, AUTO, PPM
from .render import BattleView
from .ui import WHITE, DIM, GOLD, GREEN, RED, ORANGE
from .world import World

DIGITS = "0123456789"


def draw_backdrop(app, dark=120):
    scr = app.screen
    w, h = scr.get_size()
    bg = app.assets.ui["menu_bg"]
    sc = max(w / bg.get_width(), h / bg.get_height())
    s = app.assets.scaled(bg, bg.get_width() * sc + 1, bg.get_height() * sc + 1, "menu_bg")
    scr.blit(s, ((w - s.get_width()) // 2, (h - s.get_height()) // 2))
    if dark:
        app.ui.fill(0, 0, app.ui.vw + 2, 1082, (6, 8, 12), dark)


def credits_label(ui, x, y, amount, size=34, align="l"):
    """Coin icon + amount. x is the left edge (or right edge for align='r')."""
    txt = str(int(amount))
    w = ui.render(txt, size, GOLD).get_width() / ui.s
    if align == "r":
        x -= w + size * 1.25
    ui.image(ui.a.ui["coin"], x, y, size * 1.1, size * 1.1, "coin")
    ui.text(txt, x + size * 1.25, y - size * 0.05, size, GOLD)
    return w + size * 1.25


class Screen:
    def __init__(self, app):
        self.app = app
        self.ui = app.ui

    def frame(self, dt):
        pass

    def close(self):
        pass


class Loading(Screen):
    """Shows a message for one frame, then runs a slow job (map generation) and switches to its result."""

    def __init__(self, app, message, job):
        super().__init__(app)
        self.message = message
        self.job = job
        self.drawn = 0

    def frame(self, dt):
        draw_backdrop(self.app, 170)
        ui = self.ui
        ui.text(self.message, ui.vw / 2, 500, 54, WHITE, "c")
        self.drawn += 1
        if self.drawn == 3:
            try:
                self.app.switch(self.job())
            except (OSError, ValueError) as ex:
                self.app.switch(Menu(self.app, "Could not start: %s" % ex))


# ---------------------------------------------------------------------------
# profiles

class ProfileSelect(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.name = ""
        self.confirm = None

    def frame(self, dt):
        app, ui = self.app, self.ui
        draw_backdrop(app, 150)
        ps = profiles.list_profiles()
        x = ui.vw / 2 - 480
        ui.panel(x, 110, 960, 860)
        ui.text("CHOOSE YOUR COMMANDER", ui.vw / 2, 140, 46, WHITE, "c")
        y = 230
        for p in ps[:7]:
            if ui.button("", x + 50, y, 700, 70, active=(app.profile and app.profile.name == p.name)):
                app.set_profile(p)
                app.switch(Menu(app))
                return
            ui.fill(x + 66, y + 14, 42, 42, tuple(p.color))
            ui.text(p.name, x + 126, y + 14, 32)
            credits_label(ui, x + 730, y + 16, p.credits, 30, "r")
            ui.text("%d tanks  %d wins" % (len(p.tanks), p.wins), x + 430, y + 20, 24, DIM, bold=False)
            label = "Sure?" if self.confirm == p.name else "Delete"
            if ui.button(label, x + 770, y, 140, 70, size=24, color=RED):
                if self.confirm == p.name:
                    p.delete()
                    if app.profile and app.profile.name == p.name:
                        app.profile = None
                    self.confirm = None
                else:
                    self.confirm = p.name
            y += 82
        if not ps:
            ui.text("No saved commanders yet. Create one below.", ui.vw / 2, 300, 28, DIM, "c", bold=False)
        ui.text("New commander", x + 50, 836, 26, DIM)
        self.name = ui.text_input("pname", x + 50, 876, 560, 64, self.name, 16)
        taken = any(p.name.lower() == self.name.strip().lower() for p in ps)
        ok = len(self.name.strip()) >= 1 and not taken and len(ps) < 7
        if ui.button("Create", x + 630, 876, 280, 64, ok) or (ok and ui.focus == "pname" and ui.key(pygame.K_RETURN)):
            p = profiles.Profile(self.name.strip())
            p.save()
            app.set_profile(p)
            app.switch(Garage(app, first=True))
            return
        if ui.focus is None and not self.name and not ps:
            ui.focus = "pname"
        if app.profile and ui.key(pygame.K_ESCAPE):
            app.switch(Menu(app))


# ---------------------------------------------------------------------------
# main menu

class Menu(Screen):
    def __init__(self, app, message=None):
        super().__init__(app)
        self.message = message

    def frame(self, dt):
        app, ui = self.app, self.ui
        p = app.profile
        draw_backdrop(app, 40)
        ui.fill(0, 0, 640, 1082, (6, 8, 12), 175)
        logo = app.assets.ui["logo"]
        ui.image(logo, 70, 26, 500, 500 * logo.get_height() / logo.get_width(), "logo")
        y = 290
        items = [("Single Player", "sp")]
        if p.has_battle():
            items.append(("Continue Saved Battle", "continue"))
        items += [("Host Multiplayer", "host"), ("Join Multiplayer", "join"), ("Garage & Shop", "garage"),
                  ("Commander: %s" % p.name, "profile"),
                  ("Fullscreen: %s" % ("On" if p.settings["fullscreen"] else "Off"), "fs"),
                  ("Sound: %d%%" % round(p.settings["sound"] * 100), "snd"), ("Quit", "quit")]
        for label, key in items:
            if ui.button(label, 100, y, 440, 62, size=28):
                self.choose(key)
                return
            y += 72
        # commander card
        ui.panel(ui.vw - 560, 40, 520, 250, 235)
        ui.fill(ui.vw - 530, 70, 56, 56, tuple(p.color))
        ui.text(p.name, ui.vw - 458, 70, 40)
        credits_label(ui, ui.vw - 530, 150, p.credits, 38)
        ui.text("Battles %d   Wins %d" % (p.battles, p.wins), ui.vw - 530, 206, 24, DIM, bold=False)
        ui.text("Kills %d   Losses %d" % (p.kills, p.deaths), ui.vw - 530, 238, 24, DIM, bold=False)
        ui.image(app.assets.preview(p.tank, p.color, 256), ui.vw - 250, 60, 210, 210, ("pv", p.tank, tuple(p.color)))
        if self.message:
            ui.panel(ui.vw / 2 - 420, 930, 1000, 90, 235)
            ui.text(self.message, ui.vw / 2 + 80, 958, 28, ORANGE, "c")
        ui.text("WASD drive   Mouse aim   LMB cannon   RMB machine gun   Q/E change ammo   B shop",
                ui.vw - 40, 1034, 22, DIM, "r", bold=False)

    def choose(self, key):
        app, p = self.app, self.app.profile
        if key == "sp":
            app.switch(Setup(app, host=False))
        elif key == "continue":
            def job():
                d = p.load_battle()
                w = World.from_dict(d["world"])
                w.ai = AIController(w)
                me = w.players.get(d["pid"])
                if me:                      # the profile is the truth for money and purchases
                    me.credits, me.tanks, me.weapons = p.credits, list(p.tanks), list(p.weapons)
                    me.set_tank(me.tank_key)
                for t in w.players.values():
                    if t.is_ai:
                        w.ai.attach(t)
                return Battle(app, net.LocalSession(w, d["pid"]))
            app.switch(Loading(app, "Returning to the battlefield...", job))
        elif key == "host":
            app.switch(Setup(app, host=True))
        elif key == "join":
            app.switch(Join(app))
        elif key == "garage":
            app.switch(Garage(app))
        elif key == "profile":
            app.switch(ProfileSelect(app))
        elif key == "fs":
            p.settings["fullscreen"] = not p.settings["fullscreen"]
            p.save()
            app.apply_display()
        elif key == "snd":
            p.settings["sound"] = round((p.settings["sound"] + 0.1) % 1.1, 1)
            app.sound.volume = p.settings["sound"]
            p.save()
            app.sound.play("cannon")
        elif key == "quit":
            app.running = False


# ---------------------------------------------------------------------------
# garage / shop (also used as the in-battle shop)

class ShopView:
    """Draws the tank + weapon shop. Works on any object that has credits / tanks / weapons / current tank."""

    def __init__(self, app):
        self.app = app
        self.view = None
        self.note = None

    def draw(self, x, y, credits, tanks, weapons, current, color, buy, use):
        """buy(kind, key) and use(tank_key) are callbacks. Returns nothing; all state lives with the caller."""
        app, ui = self.app, self.app.ui
        if self.view not in TANK_INDEX:
            self.view = current
        W, H = 1780, 860
        ui.panel(x, y, W, H, 248)
        ui.text("GARAGE", x + 40, y + 26, 40)
        credits_label(ui, x + W - 40, y + 28, credits, 38, "r")

        # --- tank list -------------------------------------------------------
        ty = y + 96
        for t in TANKS:
            k = t["key"]
            owned = k in tanks
            if ui.button("", x + 30, ty, 400, 118, active=(self.view == k)):
                self.view = k
            ui.image(app.assets.preview(k, color, 128), x + 38, ty + 4, 110, 110, ("pv128", k, tuple(color)))
            ui.text(t["name"], x + 158, ty + 16, 28)
            if k == current:
                ui.text("IN USE", x + 158, ty + 60, 24, GREEN)
            elif owned:
                ui.text("Owned", x + 158, ty + 60, 24, DIM)
            else:
                ui.image(app.assets.ui["coin"], x + 158, ty + 58, 30, 30, "coin")
                ui.text(str(t["cost"]), x + 194, ty + 56, 28, GOLD if credits >= t["cost"] else RED)
            ty += 124

        # --- selected tank ---------------------------------------------------------
        t = TANKS[TANK_INDEX[self.view]]
        k = t["key"]
        owned = k in tanks
        cx = x + 460
        ui.image(app.assets.preview(k, color, 512), cx + 60, y + 60, 440, 440, ("pv512", k, tuple(color)))
        ui.text(t["name"].upper(), cx + 280, y + 500, 44, WHITE, "c")
        ui.wrap(t["desc"], cx + 20, y + 562, 540, 24)
        barrels = len(app.assets.tank_meta[k]["muzzles"])
        sy = y + 634
        for label, val, col in (("Speed", t["speed"], (110, 190, 255)), ("Strength", t["strength"], (255, 150, 60))):
            ui.text(label, cx + 20, sy, 24, DIM)
            ui.bar(cx + 150, sy + 4, 330, 24, val / 20.0, col)
            ui.text(str(val), cx + 500, sy, 24)
            sy += 38
        ui.text("Barrels", cx + 20, sy, 24, DIM)
        ui.text(str(barrels), cx + 150, sy, 24)
        allowed = t["weapons"]
        can_arm = bool(data.usable(k, weapons))
        by = y + H - 100
        if not owned:
            if ui.button("Buy for %d" % t["cost"], cx + 60, by, 440, 70, credits >= t["cost"], color=GOLD):
                if buy("tank", k):
                    app.sound.play("buy")
                    self.note = None
                else:
                    app.sound.play("deny")
        elif k == current:
            ui.button("In use", cx + 60, by, 440, 70, False)
        elif not can_arm:
            ui.button("Needs a weapon it can fire", cx + 60, by, 440, 70, False, size=26)
        elif ui.button("Use this tank", cx + 60, by, 440, 70, color=GREEN):
            use(k)
        if owned and not can_arm:
            ui.text("Buy one of the highlighted weapons to drive it.", cx + 280, by - 40, 22, ORANGE, "c", bold=False)

        # --- weapons ------------------------------------------------------------------
        wx = x + 1060
        ui.text("AMMUNITION", wx, y + 34, 28, DIM)
        wy = y + 84
        for i, w in enumerate(WEAPONS):
            ok = i in allowed
            have = w["key"] in weapons
            ui.slot(wx, wy, 690, 72, "hot" if ok else "off")
            ui.image(app.assets.icons[w["key"]], wx + 6, wy + 2, 68, 68, ("icon", w["key"]))
            ui.text(w["name"], wx + 84, wy + 6, 26, WHITE if ok else DIM)
            rl = "auto-fire" if w["slot"] == AUTO else "reload %gs" % w["reload"]
            extra = "  x5" if w["pellets"] > 1 else ""
            ui.text("DMG %d%s   %s   %s" % (w["damage"], extra, rl, "RMB" if w["slot"] == AUTO else "LMB"),
                    wx + 84, wy + 40, 20, DIM, bold=False)
            if have:
                ui.text("Owned", wx + 676, wy + 22, 24, GREEN if ok else DIM, "r")
            else:
                if ui.button(str(w["cost"]), wx + 540, wy + 8, 140, 56, credits >= w["cost"], size=26, color=GOLD):
                    if buy("weapon", w["key"]):
                        app.sound.play("buy")
                    else:
                        app.sound.play("deny")
            wy += 76
        # description of whichever weapon row is under the mouse
        hover = int((ui.mouse[1] / ui.s - (y + 84)) // 76)
        if 0 <= hover < len(WEAPONS) and ui.hot(wx, y + 84, 690, 760):
            ui.text(WEAPONS[hover]["desc"], cx + 280, y + H - 26, 20, DIM, "c", bold=False)


class Garage(Screen):
    def __init__(self, app, first=False):
        super().__init__(app)
        self.shop = ShopView(app)
        self.first = first

    def frame(self, dt):
        app, ui, p = self.app, self.ui, self.app.profile
        draw_backdrop(app, 160)
        x = ui.vw / 2 - 890

        def use(k):
            p.tank = k
            p.validate()
            p.save()

        def buy(kind, key):
            ok = p.buy_tank(key) if kind == "tank" else p.buy_weapon(key)
            if ok:
                p.save()
            return ok

        self.shop.draw(x, 30, p.credits, p.tanks, p.weapons, p.tank, p.color, buy, use)
        # paint shop
        ui.panel(x, 900, 1780, 150, 248)
        ui.text("PAINT", x + 40, 950, 30, DIM)
        cx = x + 180
        for name, col in data.COLORS:
            sel = tuple(p.color) == col
            if ui.button("", cx, 932, 82, 82, active=sel):
                p.color = list(col)
                p.save()
            ui.fill(cx + 14, 946, 54, 54, col)
            cx += 90
        if ui.button("Done" if not self.first else "To battle!", x + 1500, 938, 240, 72, color=GREEN) or \
                ui.key(pygame.K_ESCAPE):
            app.switch(Menu(app))


# ---------------------------------------------------------------------------
# battle setup, hosting and joining

def build_world(app, settings, allies, enemies, humans=()):
    """Create the authoritative world. humans: [(loadout, team)] for remote players. Returns (world, pids)."""
    w = World(settings)
    w.ai = AIController(w)
    me = w.add_player(app.profile.loadout(), 0)
    pids = [me.pid]
    for lo, team in humans:
        pids.append(w.add_player(lo, team).pid)
    rng = random.Random(settings["seed"] * 101 + 3)
    used = {t.name for t in w.players.values()}
    skill = settings["difficulty"]
    # the AI's tanks keep pace with the best garage among the human players
    tier = max([data.player_tier(app.profile.tanks)] + [data.player_tier(lo.get("tanks", ())) for lo, _ in humans])
    for team, count in ((0, allies), (1, enemies)):
        lineup = data.ai_lineup(tier, count)
        rng.shuffle(lineup)
        for i in range(count):
            t = w.add_player(make_ai_loadout(rng, team, i, skill, used, lineup[i]), team, True, skill)
            w.ai.attach(t)
    return w, pids


class Setup(Screen):
    def __init__(self, app, host):
        super().__init__(app)
        self.host = host
        d = dict(map=0, allies=4, enemies=5, difficulty=1, kills=30, minutes=10, port=str(data.DEFAULT_PORT),
                 mode=0, caps=3)
        d.update(app.profile.last_setup or {})
        self.d = d
        self.seed = random.randrange(1, 99999)
        self.error = None

    def frame(self, dt):
        app, ui, d = self.app, self.ui, self.d
        draw_backdrop(app, 150)
        x = ui.vw / 2 - 520
        ui.panel(x, 90, 1040, 900)
        ui.text("HOST A BATTLE" if self.host else "SINGLE PLAYER BATTLE", ui.vw / 2, 122, 46, WHITE, "c")
        y, w, row = 196, 940, 68
        d["mode"] = ui.choice("Game type", x + 50, y, w, [m[1] for m in data.MODES], d["mode"] % len(data.MODES))
        mode = data.MODES[d["mode"]][0]
        ctf = mode == "ctf"
        if mode == "zones" and d["minutes"] == 0:
            d["minutes"] = 10                     # this game type is decided by the clock
        y += row
        d["map"] = ui.choice("Battlefield", x + 50, y, w, [m["name"] for m in data.MAPS], d["map"])
        ui.text("Steal the enemy flag and bring it to your own. Your flag must be at home to score." if ctf
                else "Hold Z for 5 seconds inside a zone to capture it. Most zones when time runs out wins."
                if mode == "zones" else data.MAPS[d["map"]]["desc"], x + 50, y + 58, 22, DIM, bold=False)
        y += row + 30
        self.seed = ui.stepper("Terrain seed", x + 50, y, w, self.seed, 1, 99999)
        y += row
        d["allies"] = ui.stepper("AI tanks on your team", x + 50, y, w, d["allies"], 0, 20)
        y += row
        d["enemies"] = ui.stepper("AI tanks on the enemy team", x + 50, y, w, d["enemies"], 0 if self.host else 1, 20)
        y += row
        d["difficulty"] = ui.choice("AI difficulty", x + 50, y, w, data.DIFFICULTIES, d["difficulty"])
        y += row
        if ctf:
            d["caps"] = ui.stepper("Captures to win", x + 50, y, w, d["caps"], 1, 10)
        elif mode == "zones":
            ui.text("To win", x + 50, y + 12, 26, DIM)
            ui.text("hold all 5 zones, or the most at the end", x + 50 + w, y + 14, 24, WHITE, "r")
        else:
            d["kills"] = ui.stepper("Kills to win", x + 50, y, w, d["kills"], 5, 150, 5)
        y += row
        d["minutes"] = ui.stepper("Time limit", x + 50, y, w, d["minutes"], 1 if mode == "zones" else 0, 60, 1,
                                  lambda v: "none" if v == 0 else "%d min" % v)
        y += row
        if self.host:
            ui.text("Port", x + 50, y + 12, 26, DIM)
            d["port"] = ui.text_input("port", x + 50 + w - 300, y, 300, 54, d["port"], 5, DIGITS)
        # what the AI will bring, given the best tank in your garage
        lineup = data.ai_lineup(data.player_tier(app.profile.tanks), d["enemies"])
        if lineup:
            names = {t["key"]: t["name"].replace(" Tank", "") for t in TANKS}
            parts = ["%d %s" % (lineup.count(k), names[k]) for k in dict.fromkeys(lineup)]
            ui.text("Enemy AI tanks (they keep pace with your garage):  " + ",  ".join(parts), ui.vw / 2, 832, 20,
                    DIM, "c", bold=False)
        if self.error:
            ui.text(self.error, ui.vw / 2, 858, 22, RED, "c")
        if ui.button("Back", x + 50, 890, 300, 70) or ui.key(pygame.K_ESCAPE):
            app.switch(Menu(app))
            return
        if ui.button("Open lobby" if self.host else "Start battle", x + 690, 890, 300, 70, color=GREEN):
            app.profile.last_setup = dict(d)
            app.profile.save()
            settings = dict(map=data.MAPS[d["map"]]["key"], seed=self.seed, kill_limit=d["kills"],
                            time_limit=d["minutes"] * 60, difficulty=d["difficulty"],
                            mode=data.MODES[d["mode"]][0], cap_limit=d["caps"])
            if self.host:
                try:
                    port = int(d["port"] or data.DEFAULT_PORT)
                    server = net.Server(port)
                except (OSError, ValueError, OverflowError) as ex:
                    self.error = "Cannot open port %s: %s" % (d["port"], ex)
                    return
                app.switch(Lobby(app, server, settings, d["allies"], d["enemies"]))
            else:
                app.profile.clear_battle()

                def job():
                    w, pids = build_world(app, settings, d["allies"], d["enemies"])
                    return Battle(app, net.LocalSession(w, pids[0]))
                app.switch(Loading(app, "Generating battlefield...", job))


class Lobby(Screen):
    """Host side: wait for players, then start."""

    def __init__(self, app, server, settings, allies, enemies):
        super().__init__(app)
        self.server = server
        self.settings = settings
        self.allies, self.enemies = allies, enemies
        self.joined = {}                 # cid -> [loadout, team]
        self.ips = net.local_addresses()
        maps = {m["key"]: m["name"] for m in data.MAPS}
        self.mode_name = dict(data.MODES).get(settings.get("mode", "tdm"), "")
        server.info.update(name=app.profile.name, players=1,
                           map="%s - %s" % (self.mode_name, maps.get(settings["map"], "")))
        self.started = False

    def frame(self, dt):
        app, ui = self.app, self.ui
        for cid, msg in self.server.poll():
            kind = msg.get("t")
            if kind == "join":
                if len(self.joined) + 1 >= net.MAX_HUMANS:
                    self.server.send(cid, {"t": "error", "msg": "The game is full."})
                    continue
                t0 = 1 + sum(1 for v in self.joined.values() if v[1] == 0)
                t1 = sum(1 for v in self.joined.values() if v[1] == 1)
                self.joined[cid] = [net.clean_loadout(msg.get("lo")), 0 if t0 <= t1 else 1]
            elif kind == "team" and cid in self.joined:
                self.joined[cid][1] = 1 if msg.get("team") else 0
            elif kind == "_drop":
                self.joined.pop(cid, None)
                self.server.drop(cid)
            self._send_lobby()
            self.server.info["players"] = 1 + len(self.joined)
        draw_backdrop(app, 150)
        x = ui.vw / 2 - 560
        ui.panel(x, 90, 1120, 900)
        ui.text("LOBBY  -  " + self.mode_name.upper(), ui.vw / 2, 122, 46, WHITE, "c")
        ui.text("Friends on your network will see this game in 'Join Multiplayer'.", ui.vw / 2, 178, 24, WHITE,
                "c", bold=False)
        ui.text("Or they can type:  %s   port %d" % ("  or  ".join(self.ips[:3]), self.server.port), ui.vw / 2,
                210, 26, GOLD, "c")
        ui.text("If nobody can join, this PC's firewall or security suite (Norton, McAfee...) is blocking Python: "
                "allow it, or let the other PC host.", ui.vw / 2, 248, 20, DIM, "c", bold=False)
        for team in (0, 1):
            tx = x + 60 + team * 520
            ui.text(data.TEAM_NAMES[team], tx, 290, 32, data.TEAM_UI[team])
            y = 340
            rows = [(app.profile.name + "  (host)", app.profile.color, None)] if team == 0 else []
            rows += [(v[0]["name"], v[0]["color"], cid) for cid, v in self.joined.items() if v[1] == team]
            for name, col, cid in rows:
                ui.slot(tx, y, 480, 56)
                ui.fill(tx + 12, y + 12, 32, 32, tuple(col))
                ui.text(name, tx + 58, y + 10, 26)
                if cid is not None and ui.button("Swap", tx + 380, y + 4, 92, 48, size=20):
                    self.joined[cid][1] = 1 - team
                    self._send_lobby()
                y += 62
            n_ai = self.allies if team == 0 else self.enemies
            ui.text("+ %d AI tank%s" % (n_ai, "" if n_ai == 1 else "s"), tx, y + 8, 24, DIM, bold=False)
        if ui.button("Cancel", x + 60, 890, 300, 70) or ui.key(pygame.K_ESCAPE):
            self.server.close()
            app.switch(Menu(app))
            return
        if ui.button("Start battle", x + 760, 890, 300, 70, color=GREEN):
            self.started = True
            order = list(self.joined.items())

            def job():
                w, pids = build_world(app, self.settings, self.allies, self.enemies, [(v[0], v[1]) for _, v in order])
                remote = {}
                for (cid, _v), pid in zip(order, pids[1:]):
                    remote[cid] = pid
                    self.server.send(cid, {"t": "start", "settings": w.settings, "roster": w.roster(), "pid": pid})
                return Battle(app, net.LocalSession(w, pids[0], self.server, remote))
            app.switch(Loading(app, "Generating battlefield...", job))

    def _send_lobby(self):
        rows = [[self.app.profile.name, 0]] + [[v[0]["name"], v[1]] for v in self.joined.values()]
        for cid in self.joined:
            self.server.send(cid, {"t": "lobby", "players": rows, "ai": [self.allies, self.enemies]})

    def close(self):
        if not self.started:
            self.server.close()


class Join(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.host = app.profile.last_host if app.profile.last_host != "127.0.0.1" else ""
        self.port = str(data.DEFAULT_PORT)
        self.conn = None
        self.inbox = None
        self.status = None
        self.lobby = None
        self.handed_over = False
        self.finder = net.Finder()

    def connect(self, host, port):
        app = self.app
        try:
            port = int(port or data.DEFAULT_PORT)
            self.conn, self.inbox = net.connect(host, port)
            self.conn.send({"t": "join", "lo": app.profile.loadout()})
            app.profile.last_host = host
            app.profile.save()
            self.status = None
        except (OSError, ValueError, OverflowError) as ex:
            self.conn = None
            self.status = net.explain(ex, host, port)

    def frame(self, dt):
        app, ui = self.app, self.ui
        draw_backdrop(app, 150)
        x = ui.vw / 2 - 520
        ui.panel(x, 110, 1040, 860)
        ui.text("JOIN A BATTLE", ui.vw / 2, 140, 46, WHITE, "c")
        if self.conn is None:
            games = self.finder.poll()
            ui.text("Games on your network", x + 60, 226, 26, DIM)
            y = 270
            for ip, port, info in games[:4]:
                ui.slot(x + 60, y, 920, 70)
                ui.text(str(info.get("name", "?"))[:16] + "'s game", x + 84, y + 8, 28)
                n = info.get("players", 1)
                ui.text("%s    %s player%s    %s" % (info.get("map", ""), n, "" if n == 1 else "s", ip), x + 84,
                        y + 42, 20, DIM, bold=False)
                if ui.button("Join", x + 790, y + 7, 180, 56, color=GREEN):
                    self.connect(ip, port)
                    return
                y += 78
            if not games:
                dots = "." * (1 + int(pygame.time.get_ticks() / 500) % 3)
                ui.text("Searching" + dots, x + 84, 284, 26, WHITE, bold=False)
                ui.text("The host must be on their lobby screen, on the same Wi-Fi or LAN as you.", x + 84, 322, 22,
                        DIM, bold=False)
                ui.text("Nothing showing? Security software on the host's PC may be blocking it - try hosting from",
                        x + 84, 354, 22, DIM, bold=False)
                ui.text("this PC instead, or type the address below.", x + 84, 382, 22, DIM, bold=False)
            ui.text("Or type the host's address (shown in their lobby)", x + 60, 606, 26, DIM)
            self.host = ui.text_input("host", x + 60, 646, 560, 64, self.host, 40)
            self.port = ui.text_input("jport", x + 640, 646, 160, 64, self.port, 5, DIGITS)
            typed = self.host.strip()
            if ui.button("Connect", x + 820, 646, 160, 64, bool(typed), color=GREEN) or \
                    (typed and ui.focus in ("host", "jport") and ui.key(pygame.K_RETURN)):
                self.connect(typed, self.port)
                if self.conn:
                    return
            if self.status:
                ui.wrap(self.status, x + 60, 730, 920, 24, ORANGE)
        else:
            while not self.inbox.empty():
                _cid, msg = self.inbox.get()
                kind = msg.get("t")
                if kind == "lobby":
                    self.lobby = msg
                elif kind == "start":
                    conn, inbox = self.conn, self.inbox
                    self.handed_over = True
                    app.switch(Loading(app, "Generating battlefield...",
                                       lambda: Battle(app, net.RemoteSession(conn, inbox, msg))))
                    return
                elif kind in ("_drop", "error"):
                    self.status = msg.get("msg", "The host closed the game.")
                    self.conn.close()
                    self.conn = None
                    return
            ui.text("Connected. Waiting for the host to start...", ui.vw / 2, 260, 30, GREEN, "c")
            if self.lobby:
                y = 330
                for name, team in self.lobby["players"][:12]:
                    ui.text(name, ui.vw / 2 - 20, y, 28, WHITE, "r")
                    ui.text(data.TEAM_NAMES[team], ui.vw / 2 + 20, y, 28, data.TEAM_UI[team])
                    y += 40
        if ui.button("Back", x + 60, 870, 300, 70) or ui.key(pygame.K_ESCAPE):
            app.switch(Menu(app))

    def close(self):
        self.finder.close()
        if self.conn and not self.handed_over:
            self.conn.close()


# ---------------------------------------------------------------------------
# the battle

class Battle(Screen):
    def __init__(self, app, session):
        super().__init__(app)
        self.session = session
        self.world = session.world
        if not self.world.mirror and self.world.time == 0.0:
            self.world.step(0.0)             # place every tank now, so the battle opens with you on the field
            self.world.events = [e for e in self.world.events if e[0] != "spawn"]
        self.view = BattleView(app, self.world, session.pid)
        self.shop = ShopView(app)
        self.shop_open = False
        self.paused = False
        self.minimap = self.view.ground.minimap(400, 300)
        self.save_t = 0.0
        self.finished = False
        self.cam = (0, 0)
        self.over_t = 0.0
        self.watch = 0              # which teammate we are spectating once eliminated
        pygame.mouse.set_visible(False)
        me = session.me()
        if me:                               # start the camera on our side of the map
            z = self.world.map.zones[me.team]
            self.view.focus = (me.x, me.y) if me.alive else ((z[0] + z[2]) / 2, (z[1] + z[3]) / 2)
            sw, sh = app.screen.get_size()
            self.view.cam = [self.view.focus[0] - sw / 2, self.view.focus[1] - sh / 2]

    # -- helpers -------------------------------------------------------------------
    def cycle(self, slot, step=1):
        me = self.session.me()
        if not me:
            return
        opts = data.usable(me.tank_key, me.weapons, slot)
        if len(opts) > 1:
            i = opts.index(me.sel[slot]) if me.sel[slot] in opts else 0
            self.session.select_weapon(slot, opts[(i + step) % len(opts)])
            if not self.session.is_host and not self.session.can_pause:
                me.sel[slot] = opts[(i + step) % len(opts)]
            self.app.sound.play("click")

    def bank(self, final=False):
        """Copy what we earned and bought into the profile (so nothing is lost if the game closes)."""
        me, p = self.session.me(), self.app.profile
        first_final = final and not self.finished
        if final:
            self.finished = True
        if me:
            p.absorb(me.state())
            if first_final:
                p.battles += 1
                p.kills += me.kills
                p.deaths += me.deaths
                if self.world.over == me.team:
                    p.wins += 1
            p.save()

    def leave(self, message=None):
        self.bank()
        self.app.switch(Menu(self.app, message))

    def close(self):
        pygame.mouse.set_visible(True)
        self.session.close()

    # -- frame ---------------------------------------------------------------------------
    def frame(self, dt):
        app, ui, s = self.app, self.ui, self.session
        w = self.world
        me = s.me()
        scr = app.screen
        sw, sh = scr.get_size()
        over = w.over is not None
        modal = self.shop_open or self.paused or over or bool(s.lost)

        # --- keys ----------------------------------------------------------------
        for k in ui.keys:
            if k == pygame.K_ESCAPE:
                if self.shop_open:
                    self.shop_open = False
                elif not over:
                    self.paused = not self.paused
            elif k == pygame.K_b and not over and not self.paused:
                self.shop_open = not self.shop_open
                self.shop.view = me.tank_key if me else None
            elif not modal:
                if k == pygame.K_q:
                    self.cycle(SHELL)
                elif k == pygame.K_e:
                    self.cycle(AUTO)
                elif pygame.K_0 <= k <= pygame.K_9 and me:
                    i = (k - pygame.K_1) % 10
                    if i in data.usable(me.tank_key, me.weapons):
                        s.select_weapon(WEAPONS[i]["slot"], i)
                        me.sel[WEAPONS[i]["slot"]] = i
        if ui.wheel and not modal:
            self.cycle(SHELL, -1 if ui.wheel > 0 else 1)

        # --- controls -> session ------------------------------------------------------
        keys = pygame.key.get_pressed()
        mb = pygame.mouse.get_pressed()
        mx, my = ui.mouse
        thr = turn = 0.0
        f0 = f1 = False
        aim = me.aim if me else 0.0
        aim_dist = 0.0
        if me and not modal:
            thr = (1.0 if keys[pygame.K_w] or keys[pygame.K_UP] else 0.0) - \
                  (1.0 if keys[pygame.K_s] or keys[pygame.K_DOWN] else 0.0)
            turn = (1.0 if keys[pygame.K_d] or keys[pygame.K_RIGHT] else 0.0) - \
                   (1.0 if keys[pygame.K_a] or keys[pygame.K_LEFT] else 0.0)
            if thr < 0:
                turn = -turn                      # steer like a car when reversing
            px, py = me.pivot()
            aim = math.atan2(my + self.cam[1] - py, mx + self.cam[0] - px) % (math.pi * 2)
            aim_dist = math.hypot(mx + self.cam[0] - px, my + self.cam[1] - py)
            f0, f1 = mb[0], mb[2] or keys[pygame.K_SPACE]
        self.aim_dist = aim_dist
        s.set_input(thr, turn, aim, f0, f1, aim_dist, bool(me) and not modal and keys[pygame.K_z])

        # --- eliminated: ride along with a teammate (click to switch) -----------------------
        if me and me.out and not over:
            mates = [t for t in w.players.values() if t.team == me.team and t.alive]
            if ui.clicked and not modal:
                self.watch += 1
            self.view.follow = mates[self.watch % len(mates)].pid if mates else None
        else:
            self.view.follow = None

        # --- simulate + draw the world ---------------------------------------------------
        sim_dt = 0.0 if (self.paused and s.can_pause) else dt
        events = s.update(sim_dt) if sim_dt or not s.can_pause else []
        self.view.handle(events)
        self.view.update(sim_dt, (sw, sh), (mx, my) if not modal else (sw / 2, sh / 2))
        self.cam = self.view.draw(scr)
        if not (over and self.over_t > 1.2):
            self.draw_tags(me)
            self.draw_hud(me)

        self.save_t += dt
        if self.save_t > 8.0:
            self.save_t = 0.0
            self.bank()

        # --- overlays ------------------------------------------------------------------------
        if s.lost:
            if not self.finished:
                self.finished = True
                self.bank()
            ui.fill(0, 0, ui.vw + 2, 1082, (0, 0, 0), 150)
            ui.panel(ui.vw / 2 - 400, 400, 800, 260)
            ui.text(s.lost, ui.vw / 2, 440, 32, ORANGE, "c")
            ui.text("Your credits and purchases were saved.", ui.vw / 2, 492, 24, DIM, "c", bold=False)
            pygame.mouse.set_visible(True)
            if ui.button("Main menu", ui.vw / 2 - 150, 560, 300, 70):
                self.leave()
            return
        if over:
            self.over_t += dt
            if not self.finished:               # once, not every frame
                self.bank(final=True)
                if s.can_pause:
                    app.profile.clear_battle()
            if self.over_t > 1.2:
                pygame.mouse.set_visible(True)
                self.draw_results(me)
            return
        if keys[pygame.K_TAB] and not modal:
            self.draw_scores(ui.vw / 2 - 620, 150)
        if self.shop_open and me:
            pygame.mouse.set_visible(True)
            ui.fill(0, 0, ui.vw + 2, 1082, (0, 0, 0), 110)
            self.shop.draw(ui.vw / 2 - 890, 30, me.credits, me.tanks, me.weapons, me.tank_key, me.color, s.buy,
                           s.select_tank)
            ui.text("The battle is still running!  B or Esc to close" if not s.can_pause else "B or Esc to close",
                    ui.vw / 2, 898, 26, ORANGE if not s.can_pause else DIM, "c")
        elif self.paused:
            pygame.mouse.set_visible(True)
            ui.fill(0, 0, ui.vw + 2, 1082, (0, 0, 0), 130)
            x = ui.vw / 2 - 260
            ui.panel(x, 300, 520, 470)
            ui.text("PAUSED" if s.can_pause else "MENU", ui.vw / 2, 330, 44, WHITE, "c")
            if ui.button("Resume", x + 50, 420, 420, 66):
                self.paused = False
            if s.can_pause:
                if ui.button("Save & quit", x + 50, 500, 420, 66):
                    self.bank()
                    ok = app.profile.save_battle(dict(world=w.to_dict(), pid=s.pid))
                    self.leave("Battle saved. Pick 'Continue Saved Battle' to return." if ok
                               else "Could not write the save file - the battle was not saved.")
                    return
            if ui.button("Abandon battle" if s.can_pause else "Leave battle", x + 50, 580 if s.can_pause else 500,
                         420, 66, color=RED):
                if s.can_pause:
                    app.profile.clear_battle()
                self.leave()
                return
        else:
            pygame.mouse.set_visible(False)
            self.draw_crosshair(me)

    # -- world-space labels -----------------------------------------------------------------
    def draw_tags(self, me):
        scr, ui = self.app.screen, self.ui
        sw, sh = scr.get_size()
        cx, cy = self.cam
        my_team = me.team if me else 0
        for t in self.world.players.values():
            if not t.alive or t is me:
                continue
            x, y = t.x - cx, t.y - cy
            if not (-80 < x < sw + 80 and -80 < y < sh + 80):
                continue
            friend = t.team == my_team
            col = (110, 210, 120) if friend else (255, 96, 80)
            bw = int(64 * ui.s)
            by = int(y - t.radius - 26 * ui.s)
            pygame.draw.rect(scr, (10, 12, 14), (x - bw // 2 - 1, by - 1, bw + 2, int(7 * ui.s) + 2))
            pygame.draw.rect(scr, col, (x - bw // 2, by, int(bw * max(0.0, t.hp / t.max_hp)), int(7 * ui.s)))
            name = ui.render(t.name, 18, col if not t.is_ai else tuple(int(c * 0.82) for c in col))
            scr.blit(name, (x - name.get_width() // 2, by - name.get_height() - 1))

    def draw_crosshair(self, me):
        scr = self.app.screen
        mx, my = self.ui.mouse
        s = self.ui.s
        col = (255, 255, 255)
        if me and me.alive and me.sel[SHELL] >= 0:
            # red when the cursor is beyond the shell's range: it will burst short of this spot
            reach = max(m[0] for m in me.art["muzzles"]) * PPM
            if getattr(self, "aim_dist", 0.0) - reach > WEAPONS[me.sel[SHELL]]["range"]:
                col = (255, 90, 70)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(scr, (0, 0, 0), (mx + dx * 7 * s, my + dy * 7 * s), (mx + dx * 19 * s, my + dy * 19 * s),
                             max(3, int(4 * s)))
            pygame.draw.line(scr, col, (mx + dx * 8 * s, my + dy * 8 * s), (mx + dx * 18 * s, my + dy * 18 * s),
                             max(1, int(2 * s)))
        if me and me.alive and me.sel[SHELL] >= 0:
            wp = WEAPONS[me.sel[SHELL]]
            total = self.world.reload_time(me, wp)
            left = max(0.0, me.cool.get(me.sel[SHELL], 0.0))
            if left > 0 and total > 0:
                r = int(26 * s)
                pygame.draw.arc(scr, (255, 170, 60), (mx - r, my - r, r * 2, r * 2), math.pi / 2,
                                math.pi / 2 + math.pi * 2 * (1 - left / total), max(2, int(3 * s)))

    # -- HUD ---------------------------------------------------------------------------------------
    def draw_hud(self, me):
        app, ui, w = self.app, self.ui, self.world
        vw = ui.vw
        # score strip
        ui.panel(vw / 2 - 300, 10, 600, 86, 225)
        ui.text(str(w.scores[0]), vw / 2 - 150, 22, 50, data.TEAM_UI[0], "c")
        ui.text(str(w.scores[1]), vw / 2 + 150, 22, 50, data.TEAM_UI[1], "c")
        limit = w.settings["time_limit"]
        tsec = max(0, limit - w.time) if limit else w.time
        ui.text("%d:%02d" % (tsec // 60, tsec % 60), vw / 2, 22, 34, WHITE, "c")
        if w.cps:
            ui.text("zones held", vw / 2, 60, 20, DIM, "c", bold=False)
            self.draw_zones(me)
        elif w.flags:
            n = w.settings["cap_limit"]
            ui.text("first to %d capture%s" % (n, "" if n == 1 else "s"), vw / 2, 60, 20, DIM, "c", bold=False)
            self.draw_flags(me)
        elif w.settings["kill_limit"]:
            ui.text("first to %d" % w.settings["kill_limit"], vw / 2, 60, 20, DIM, "c", bold=False)
        if not me:
            return
        # credits
        ui.panel(20, 10, 250, 70, 225)
        credits_label(ui, 44, 26, me.credits, 34)
        ui.text("B  shop    Tab  scores    Esc  menu", 24, 88, 20, DIM, bold=False)

        # tank + health
        ui.panel(20, 950, 470, 116, 225)
        ui.text(me.spec["name"], 44, 966, 28)
        frac = me.hp / me.max_hp if me.alive else 0.0
        col = (110, 210, 120) if frac > 0.5 else (240, 190, 70) if frac > 0.25 else (255, 96, 80)
        ui.bar(44, 1010, 420, 34, frac, col)
        ui.text("%d / %d" % (math.ceil(max(0.0, me.hp)), me.max_hp), 254, 1012, 24, WHITE, "c")
        if w.flags:
            ui.text("OUT" if me.out else "Respawns left: %d" % me.respawns, 464, 970, 22,
                    RED if (me.out or me.respawns == 0) else DIM, "r")

        # weapon slots
        x = vw / 2 - 330
        for slot, hint, key in ((SHELL, "LMB", "Q"), (AUTO, "RMB", "E")):
            ui.panel(x, 950, 320, 116, 225)
            wi = me.sel[slot]
            if wi < 0:
                ui.text("no cannon ammo" if slot == SHELL else "no machine gun", x + 160, 992, 22, DIM, "c", bold=False)
            else:
                wp = WEAPONS[wi]
                ui.image(app.assets.icons[wp["key"]], x + 12, 962, 92, 92, ("icon", wp["key"]))
                ui.text(wp["name"], x + 110, 966, 24)
                total = w.reload_time(me, wp)
                left = max(0.0, me.cool.get(wi, 0.0))
                ready = 1.0 - min(1.0, left / total) if total > 0.2 else 1.0
                ui.bar(x + 110, 1004, 192, 16, ready, (120, 220, 110) if ready >= 1 else (255, 170, 60))
                n = len(data.usable(me.tank_key, me.weapons, slot))
                ui.text("%s%s" % (hint, "    %s: next (%d)" % (key, n) if n > 1 else ""), x + 110, 1028, 20, DIM,
                        bold=False)
            x += 340

        # minimap
        mw, mh = 340, 255
        mx0, my0 = vw - mw - 24, 1080 - mh - 24
        ui.panel(mx0 - 10, my0 - 10, mw + 20, mh + 20, 235)
        ui.image(self.minimap, mx0, my0, mw, mh, "minimap%d" % id(self.minimap))
        sx, sy = mw / w.map.w, mh / w.map.h
        for z in w.zones:
            col = (255, 120, 30) if z[1] == "fire" else (120, 255, 60)
            r = max(3, z[4] * sx)
            ui.fill(mx0 + z[2] * sx - r, my0 + z[3] * sy - r, r * 2, r * 2, col, 110)
        for i, c in enumerate(w.cps):                       # zones: a lettered square in the owner's colour
            col = (200, 200, 196) if c[2] < 0 else data.TEAM_UI[c[2]]
            px, py = mx0 + c[0] * sx, my0 + c[1] * sy
            ui.fill(px - 9, py - 9, 18, 18, (255, 255, 255) if c[3] >= 0 and int(self.view.time * 4) % 2 else (0, 0, 0))
            ui.fill(px - 7, py - 7, 14, 14, col)
            ui.text(data.ZONE_NAMES[i], px, py - 9, 13, (0, 0, 0), "c", shadow=False)
        for team, f in enumerate(w.flags):                  # bases (hollow) and flags (solid, white rim)
            hx, hy = w.map.flag_homes[team]
            pygame.draw.rect(app.screen, data.TEAM_UI[team], ui.r(mx0 + hx * sx - 7, my0 + hy * sy - 7, 14, 14), 2)
            ui.fill(mx0 + f[1] * sx - 6, my0 + f[2] * sy - 6, 12, 12, (255, 255, 255))
            ui.fill(mx0 + f[1] * sx - 4, my0 + f[2] * sy - 4, 8, 8, data.TEAM_UI[team])
        for t in w.players.values():
            if t.alive and t is not me:
                ui.fill(mx0 + t.x * sx - 3, my0 + t.y * sy - 3, 6, 6, data.TEAM_UI[t.team])
        if me.alive:
            ui.fill(mx0 + me.x * sx - 5, my0 + me.y * sy - 5, 10, 10, (0, 0, 0))
            ui.fill(mx0 + me.x * sx - 3.5, my0 + me.y * sy - 3.5, 7, 7, (255, 255, 255))
        vr = ui.r(mx0 + self.cam[0] * sx, my0 + self.cam[1] * sy, app.screen.get_width() * sx,
                  app.screen.get_height() * sy)
        pygame.draw.rect(app.screen, (255, 255, 255), vr, 1)

        # kill feed
        y = 20
        for when, killer, kteam, victim, vteam, wi in list(self.view.feed):
            if self.view.time - when > 7:
                continue
            x = vw - 30
            x -= ui.text(victim, x, y, 22, data.TEAM_UI[vteam], "r")
            if wi is not None:
                x -= ui.text("  %s  " % WEAPONS[wi]["name"], x, y + 2, 18, DIM, "r", bold=False)
            if killer:
                ui.text(killer, x, y, 22, data.TEAM_UI[kteam], "r")
            y += 30
        if self.view.banner and self.view.time - self.view.banner[0] < 2.6:
            ui.text(self.view.banner[1], vw / 2, 150, 36, self.view.banner[2], "c")
        if me.out and self.world.over is None:
            ui.text("ELIMINATED", vw / 2, 150, 60, RED, "c")
            seen = w.players.get(self.view.follow) if self.view.follow is not None else None
            ui.text("No respawns left.  %s" % ("Watching %s - click to switch" % seen.name if seen
                                             else "Waiting for your team..."), vw / 2, 224, 28, WHITE, "c")
        elif not me.alive and self.world.over is None and me.deaths == 0:
            ui.text("Deploying...", vw / 2, 440, 40, WHITE, "c")      # not yet placed on the map
        elif not me.alive and self.world.over is None:
            ui.text("DESTROYED", vw / 2, 400, 72, RED, "c")
            ui.text("Back in the fight in %.1f   -   press B to shop or change tank" % max(0.0, me.respawn), vw / 2,
                    490, 30, WHITE, "c")
            if w.flags:
                ui.text("This is your last tank!" if me.respawns == 0 else
                        "%d respawn%s left after this one" % (me.respawns, "" if me.respawns == 1 else "s"),
                        vw / 2, 536, 26, ORANGE if me.respawns == 0 else DIM, "c")
        elif me.shield > 0:
            ui.text("Spawn shield", vw / 2, 880, 24, (130, 190, 255), "c")
        if me.alive and me.lockout > 0:
            ui.text("Deploying new tank...", vw / 2, 846, 26, GOLD, "c")

    def draw_zones(self, me):
        """Zone Defense: the five zones under the score, and the capture prompt when standing in one."""
        ui, w = self.ui, self.world
        vw = ui.vw
        n = len(w.cps)
        x0 = vw / 2 - (n * 64 - 12) / 2
        here = None
        for i, c in enumerate(w.cps):
            x = x0 + i * 64
            col = (150, 152, 150) if c[2] < 0 else data.TEAM_UI[c[2]]
            busy = c[3] >= 0
            ui.fill(x - 3, 101, 58, 46, (255, 255, 255) if busy and int(self.view.time * 4) % 2 else (10, 12, 14))
            ui.fill(x, 104, 52, 40, col)
            ui.text(data.ZONE_NAMES[i], x + 26, 106, 30, (12, 14, 16), "c", shadow=False)
            if busy:
                who = w.players.get(c[3])
                ui.bar(x, 148, 52, 8, c[4] / data.ZONE_CAPTURE_TIME, data.TEAM_UI[who.team] if who else WHITE)
            if me and me.alive and (me.x - c[0]) ** 2 + (me.y - c[1]) ** 2 < data.ZONE_RADIUS ** 2:
                here = (i, c)
        if not here:
            return
        i, c = here
        name = data.ZONE_NAMES[i]
        foes = any(t.alive and t.team != me.team and (t.x - c[0]) ** 2 + (t.y - c[1]) ** 2 < data.ZONE_RADIUS ** 2
                   for t in w.players.values())
        if c[2] == me.team:
            mate = w.players.get(c[3])
            if mate and mate.team != me.team:
                ui.text("%s is capturing zone %s - drive them out!" % (mate.name, name), vw / 2, 236, 28, RED, "c")
            else:
                ui.text("Zone %s is yours" % name, vw / 2, 236, 24, DIM, "c")
        elif c[3] == me.pid:
            ui.text("Capturing zone %s..." % name if not foes else "Zone %s contested - clear the enemy out!" % name,
                    vw / 2, 236, 28, GOLD if not foes else ORANGE, "c")
            ui.bar(vw / 2 - 200, 276, 400, 22, c[4] / data.ZONE_CAPTURE_TIME, GOLD)
        elif c[3] >= 0 and w.players.get(c[3]) and w.players[c[3]].team == me.team:
            ui.text("%s is capturing zone %s - cover them" % (w.players[c[3]].name, name), vw / 2, 236, 24, DIM, "c")
        else:
            ui.text("Hold Z to capture zone %s" % name, vw / 2, 236, 30, GOLD, "c")

    def draw_flags(self, me):
        """Capture the Flag: status of both flags under the score, and pointers to off-screen objectives."""
        app, ui, w = self.app, self.ui, self.world
        vw = ui.vw
        scr = app.screen
        sw, sh = scr.get_size()
        for team, f in enumerate(w.flags):
            if f[0] == 0:
                text, col = "at base", DIM
            elif f[0] == 1:
                c = w.players.get(f[3])
                text, col = "TAKEN by %s" % (c.name if c else "?"), ORANGE
            else:
                text, col = "dropped - returns in %d" % max(0, math.ceil(f[4])), GOLD
            x = vw / 2 - 310 if team == 0 else vw / 2 + 310
            icon = app.assets.ctf["flag_%d" % team]
            ui.image(icon, x - (56 if team == 0 else 0), 100, 56, 56 * icon.get_height() / icon.get_width(),
                     "flagicon%d" % team)
            ui.text(text, x - 66 if team == 0 else x + 66, 108, 22, col, "r" if team == 0 else "l")
        if not me:
            return
        # what should I be doing right now?
        if me.flag >= 0:
            own = w.flags[me.team]
            hint = "You have the flag - take it to your base!" if own[0] == 0 else \
                "You have the flag, but yours is missing - get it back to score!"
            ui.text(hint, vw / 2, 236, 28, GOLD, "c")
        # arrows at the screen edge toward anything important that is out of view
        targets = []
        theirs, mine = w.flags[1 - me.team], w.flags[me.team]
        if me.flag >= 0:
            targets.append((w.map.flag_homes[me.team], "base_%d" % me.team, "base"))
        else:
            targets.append(((theirs[1], theirs[2]), "flag_%d" % (1 - me.team), "enemy flag"))
        if mine[0] != 0:
            targets.append(((mine[1], mine[2]), "flag_%d" % me.team, "your flag"))
        cx, cy = self.cam
        for (wx, wy), art, label in targets:
            px, py = wx - cx, wy - cy
            if 60 < px < sw - 60 and 150 < py < sh - 150:
                continue
            ex = max(70, min(sw - 70, px))
            ey = max(170 * ui.s, min(sh - 170 * ui.s, py))
            icon = app.assets.scaled(app.assets.ctf[art], 54 * ui.s, 54 * ui.s * 0.94, ("edge", art))
            scr.blit(icon, (ex - icon.get_width() // 2, ey - icon.get_height() // 2))
            dist = math.hypot(wx - me.x, wy - me.y) / PPM
            lab = ui.render("%s  %d m" % (label, dist), 18, WHITE)
            scr.blit(lab, (max(4, min(sw - lab.get_width() - 4, ex - lab.get_width() // 2)),
                           ey + icon.get_height() // 2))

    def draw_scores(self, x, y):
        ui, w = self.ui, self.world
        ui.panel(x, y, 1240, 700, 245)
        for team in (0, 1):
            tx = x + 40 + team * 600
            ui.text("%s   %d" % (data.TEAM_NAMES[team], w.scores[team]), tx, y + 30, 34, data.TEAM_UI[team])
            ui.text("K", tx + 420, y + 84, 22, DIM, "c")
            ui.text("D", tx + 490, y + 84, 22, DIM, "c")
            ry = y + 116
            rows = sorted((t for t in w.players.values() if t.team == team), key=lambda t: (-t.kills, t.deaths))
            for t in rows[:21]:
                mine = t.pid == self.session.pid
                if mine:
                    ui.fill(tx - 8, ry - 2, 560, 26, (255, 255, 255), 40)
                ui.fill(tx, ry + 3, 16, 16, t.color)
                ui.text(t.name + ("" if t.is_ai else "  *"), tx + 26, ry - 2, 20,
                        (110, 114, 120) if t.out else (WHITE if not t.is_ai else DIM), bold=not t.is_ai)
                if w.flags:
                    ui.text("OUT" if t.out else "+%d" % t.respawns, tx + 550, ry - 2, 18,
                            RED if t.out else DIM, "r", bold=False)
                ui.text(TANKS[TANK_INDEX[t.tank_key]]["name"].replace(" Tank", ""), tx + 250, ry - 2, 18, DIM,
                        bold=False)
                ui.text(str(t.kills), tx + 420, ry - 2, 20, WHITE, "c")
                ui.text(str(t.deaths), tx + 490, ry - 2, 20, DIM, "c")
                ry += 27

    def draw_results(self, me):
        app, ui, w = self.app, self.ui, self.world
        ui.fill(0, 0, ui.vw + 2, 1082, (0, 0, 0), 140)
        won = me is not None and w.over == me.team
        title = "DRAW" if w.over == -1 else ("VICTORY" if won else "DEFEAT")
        ui.text(title, ui.vw / 2, 30, 84, GOLD if won else (WHITE if w.over == -1 else RED), "c")
        self.draw_scores(ui.vw / 2 - 620, 150)
        if me:
            ui.text("You earned", ui.vw / 2 - 60, 872, 30, WHITE, "r")
            credits_label(ui, ui.vw / 2 - 40, 870, me.earned, 34)
            ui.text("%d kills" % me.kills, ui.vw / 2 + 170, 872, 30, DIM)
        if ui.button("Continue", ui.vw / 2 - 170, 940, 340, 76, color=GREEN) or ui.key(pygame.K_RETURN):
            self.leave()
