"""Draws the battlefield: blended ground, scenery, tanks, projectiles, particles and decals."""
import math
import random
from collections import OrderedDict, deque

import numpy as np
import pygame

from . import data
from .data import WEAPONS, SHELL, AUTO, PPM
from .mapgen import CELL, GW, GH, LAYER_GROUND, LAYER_LOW, LAYER_SOLID, LAYER_CANOPY

TAU = math.pi * 2
CH = 256                       # ground chunk size in pixels
FRAME_STEP = TAU / 32
ADD = pygame.BLEND_RGB_ADD


def sample(field, px0, py0, n=CH):
    """Bilinear lookup of a cell-grid field for an n x n pixel block whose top-left is (px0, py0)."""
    xs = (px0 + np.arange(n, dtype=np.float32) + 0.5) / CELL - 0.5
    ys = (py0 + np.arange(n, dtype=np.float32) + 0.5) / CELL - 0.5
    x0 = np.clip(np.floor(xs).astype(np.int32), 0, GW - 2)
    y0 = np.clip(np.floor(ys).astype(np.int32), 0, GH - 2)
    fx = np.clip(xs - x0, 0, 1)[None, :]
    fy = np.clip(ys - y0, 0, 1)[:, None]
    top = field[y0][:, x0] * (1 - fx) + field[y0][:, x0 + 1] * fx
    bot = field[y0 + 1][:, x0] * (1 - fx) + field[y0 + 1][:, x0 + 1] * fx
    return top * (1 - fy) + bot * fy


class Ground:
    """The terrain, composited on demand into cached chunks from the tileable Blender textures."""

    def __init__(self, assets, gmap, cache=420):
        self.t = assets.terrain
        self.map = gmap
        self.cache = OrderedDict()
        self.cap = cache

    def chunk(self, cx, cy):
        k = (cx, cy)
        s = self.cache.get(k)
        if s is None:
            s = self._build(cx, cy)
            self.cache[k] = s
            if len(self.cache) > self.cap:
                self.cache.popitem(last=False)
        else:
            self.cache.move_to_end(k)
        return s

    def has(self, cx, cy):
        return (cx, cy) in self.cache

    def stamp(self, surf, x, y):
        """Paint a decal (centred on world x, y) permanently into whichever cached chunks it touches."""
        w, h = surf.get_size()
        left, top = int(x - w / 2), int(y - h / 2)
        for cy in range(top // CH, (top + h) // CH + 1):
            for cx in range(left // CH, (left + w) // CH + 1):
                c = self.cache.get((cx, cy))
                if c is not None:
                    c.blit(surf, (left - cx * CH, top - cy * CH))

    def _build(self, cx, cy):
        m = self.map
        x0, y0 = cx * CH, cy * CH
        tx, ty = x0 % 1024, y0 % 1024
        T = self.t

        def tile(name):
            return T[name][ty:ty + CH, tx:tx + CH]

        out = tile("grass").copy()
        F = m.fields
        grain = sample(F["grain"], x0, y0) - 0.5

        def mix(name, mask):
            if mask.max() > 0.01:
                np.add(out, (tile(name) - out) * mask[..., None], out=out)

        mix("grass_dry", np.clip(sample(F["dry"], x0, y0) + grain * 0.8, 0, 1) * 0.9)
        mix("forest", np.clip(sample(F["forest"], x0, y0) * (1.0 + grain), 0, 0.92))
        mix("dirt", np.clip(sample(F["dirt"], x0, y0) * 1.5 + grain * 0.9 - 0.25, 0, 0.96))
        mix("rock", np.clip(sample(F["rock"], x0, y0) * 1.6 + grain * 0.8 - 0.2, 0, 0.97))
        if m.river is not None:
            d = sample(m.rdist, x0, y0)
            hw = m.river_hw
            if d.min() < hw + 140:
                wob = grain * 46.0
                mix("sand", np.clip((hw + 70 - d + wob) / 50.0, 0, 1))
                shallow = np.clip((hw + 2 - d + wob * 0.35) / 12.0, 0, 1)
                mix("water_shallow", shallow)
                ford = np.clip(sample(m.ford, x0, y0), 0, 1)
                mix("water", np.clip((hw - 24 - d) / 30.0, 0, 1) * (1.0 - ford * 0.9))
                foam = np.exp(-((hw + 1 - d + wob * 0.35) / 4.5) ** 2) * 46.0
                np.add(out, foam[..., None], out=out)
        out *= sample(F["shade"], x0, y0)[..., None]
        arr = np.clip(out, 0, 255).astype(np.uint8)
        # No alpha channel, whatever the window has: a plain convert() keeps one on macOS, and decals
        # stamped into such a chunk zero it, which leaves boxes that glows and flashes cannot light.
        return pygame.surfarray.make_surface(arr.swapaxes(0, 1)).convert((0xFF0000, 0xFF00, 0xFF, 0))

    def minimap(self, w, h):
        m = self.map
        F = m.fields
        img = np.empty((GH, GW, 3), np.float32)
        img[:] = (74, 112, 50)

        def mix(color, mask):
            img[:] = img + (np.array(color, np.float32) - img) * np.clip(mask, 0, 1)[..., None]

        mix((120, 124, 60), F["dry"] * 0.8)
        mix((44, 78, 36), F["forest"])
        mix((128, 98, 62), F["dirt"])
        if m.river is not None:
            mix((196, 172, 112), (m.river_hw + 60 - m.rdist) / 40.0)
            mix((70, 140, 150), (m.river_hw - m.rdist) / 10.0)
            mix((30, 76, 120), np.where(m.water == 1, 1.0, 0.0))
        mix((30, 62, 28), m.tree_field * 0.85)
        other = m.solid & ~m.mountain_mask & (m.tree_field < 0.5)
        mix((150, 96, 70), other.astype(np.float32))
        mix((150, 150, 152), m.mountain_mask.astype(np.float32))
        for o in m.objects:
            if o["kind"] == "bridge":
                x, y = int(o["x"]) // CELL, int(o["y"]) // CELL
                img[y - 3:y + 4, x - 10:x + 11] = (150, 110, 70)
        s = pygame.surfarray.make_surface(np.clip(img, 0, 255).astype(np.uint8).swapaxes(0, 1))
        return pygame.transform.smoothscale(s, (w, h)).convert()


class BattleView:
    BUCKET = 512

    def __init__(self, app, world, local_pid):
        self.app = app
        self.a = app.assets
        self.snd = app.sound
        self.world = world
        self.local = local_pid
        self.map = world.map
        self.ground = Ground(self.a, self.map)
        self.rng = random.Random(3)
        self.cam = [0.0, 0.0]
        self.focus = None
        self.follow = None          # pid to watch once our own tank is out of the match
        self.shake = 0.0
        self.flash = 0.0
        self.particles = []
        self.flashes = []
        self.wrecks = deque(maxlen=40)
        self.feed = deque(maxlen=6)
        self.banner = None
        self.track_pos = {}
        self.hp_seen = {}
        self.hit_flash = {}
        self.time = 0.0
        self._rot = {}
        self._fx = {}
        self._ammo_rot = {}
        self._emit = 0.0
        self.objs = [[], [], [], []]
        meta = self.a.scenery_meta
        for index, o in enumerate(self.map.objects):
            m = meta[o["name"]]
            s = self.a.scenery[o["name"]]
            left, top = int(o["x"] - m["ax"]), int(o["y"] - m["ay"])
            self.objs[o["layer"]].append((s, left, top, left + m["w"], top + m["h"], o["x"], o["y"],
                                          m.get("canopy", False), index))
        for layer in self.objs:
            layer.sort(key=lambda t: t[4])
        self.flat = [(li, o) for li, layer in enumerate(self.objs) for o in layer]
        self.buckets = {}
        B = self.BUCKET
        for i, (_li, o) in enumerate(self.flat):
            for by in range(o[2] // B, o[4] // B + 1):
                for bx in range(o[1] // B, o[3] // B + 1):
                    self.buckets.setdefault((bx, by), []).append(i)
        self._faded = {}

    # -- small caches -------------------------------------------------------------
    def fx_sprite(self, name, size, tint=None, add=False, level=255):
        """Scaled (and optionally tinted / dimmed) effect sprite."""
        size = max(6, int(size) // 6 * 6)
        level = level // 32 * 32 + 31 if add else 255
        k = (name, size, tint, add, level)
        s = self._fx.get(k)
        if s is None:
            base = (self.a.fx_add if add else self.a.fx)[name]
            s = pygame.transform.smoothscale(base, (size, size))
            if tint or level < 255:
                c = tint or (255, 255, 255)
                c = tuple(int(v * level / 255) for v in c)
                s.fill(c + (255,), special_flags=pygame.BLEND_RGBA_MULT if not add else pygame.BLEND_RGB_MULT)
            self._fx[k] = s
            if len(self._fx) > 2500:
                self._fx.clear()
        return s

    def rotated(self, surf, resid, key):
        """Frame rotated by a small residual angle (radians, clockwise on screen), cached in coarse buckets."""
        b = int(round(resid / 0.033))
        if b == 0:
            return surf
        k = (key, b)
        s = self._rot.get(k)
        if s is None:
            if len(self._rot) > 500:
                self._rot.clear()
            s = pygame.transform.rotozoom(surf, -math.degrees(b * 0.033), 1.0)
            self._rot[k] = s
        return s

    def ammo_sprite(self, key, ang):
        b = int(round(ang / TAU * 48)) % 48
        k = (key, b)
        s = self._ammo_rot.get(k)
        if s is None:
            s = pygame.transform.rotozoom(self.a.ammo[key], -b * 360.0 / 48, 1.0)
            self._ammo_rot[k] = s
        return s

    # -- particles ------------------------------------------------------------------------
    def puff(self, name, x, y, vx=0.0, vy=0.0, life=1.0, s0=30, s1=60, alpha=255, add=False, tint=None, drag=1.5,
             delay=0.0):
        if len(self.particles) < 1400:
            self.particles.append([name, x, y, vx, vy, -delay, life, s0, s1, alpha, add, tint, drag])

    def burst(self, name, x, y, n, speed, life, s0, s1, alpha=255, add=False, tint=None, spread=0.0, drag=2.0,
              delay=0.0):
        r = self.rng
        for _ in range(n):
            a = r.uniform(0, TAU)
            v = r.uniform(0.2, 1.0) * speed
            d = r.uniform(0, spread)
            self.puff(name % r.randrange(4) if "%d" in name else name, x + math.cos(a) * d, y + math.sin(a) * d,
                      math.cos(a) * v, math.sin(a) * v, life * r.uniform(0.7, 1.25), s0 * r.uniform(0.8, 1.2),
                      s1 * r.uniform(0.8, 1.2), alpha, add, tint, drag, delay * r.random())

    def explosion(self, x, y, size, scorch=True):
        """size ~1 for a shell, ~2.2 for a dying tank."""
        self.burst("fire%d", x, y, int(5 * size) + 3, 70 * size, 0.45, 26 * size, 62 * size, 255, True,
                   spread=10 * size)
        self.burst("smoke%d", x, y, int(4 * size) + 2, 45 * size, 1.5, 30 * size, 90 * size, 190, False,
                   (70, 66, 62), spread=12 * size, delay=0.15)
        self.puff("glow", x, y, 0, 0, 0.22, 150 * size, 260 * size, 255, True, (255, 210, 150))
        self.puff("ring", x, y, 0, 0, 0.3, 30 * size, 190 * size, 150, True)
        self.burst("spark", x, y, int(6 * size), 420, 0.35, 26, 8, 255, True, (255, 220, 150), drag=3.0)
        r = self.rng
        for _ in range(int(3 * size)):
            a = r.uniform(0, TAU)
            v = r.uniform(120, 380)
            self.puff("debris%d" % r.randrange(6), x, y, math.cos(a) * v, math.sin(a) * v, r.uniform(0.5, 1.0), 18,
                      14, 255, False, None, 2.2)
        if scorch:
            self.decal("scorch%d" % r.randrange(2), x, y, int(95 * size))

    def nuke(self, x, y):
        r = self.rng
        self.flash = 1.0
        self.puff("glow", x, y, 0, 0, 0.9, 900, 1500, 255, True, (255, 240, 200))
        self.puff("ring", x, y, 0, 0, 0.9, 80, 1500, 255, True)
        self.puff("ring", x, y, 0, 0, 1.4, 40, 900, 200, True, (255, 200, 140))
        for i in range(46):
            a = r.uniform(0, TAU)
            d = r.uniform(0, 250) * math.sqrt(r.random())
            self.puff("fire%d" % r.randrange(4), x + math.cos(a) * d, y + math.sin(a) * d, math.cos(a) * 60,
                      math.sin(a) * 60, r.uniform(0.7, 1.5), 90, 230, 255, True, None, 1.0, r.uniform(0, 0.35))
        for i in range(40):
            a = r.uniform(0, TAU)
            d = r.uniform(0, 280)
            self.puff("smoke%d" % r.randrange(4), x + math.cos(a) * d, y + math.sin(a) * d, math.cos(a) * 30,
                      math.sin(a) * 30, r.uniform(3.0, 6.0), 120, 330, 210, False, (64, 60, 56), 0.6,
                      r.uniform(0.2, 1.0))
        self.burst("spark", x, y, 40, 900, 0.7, 40, 10, 255, True, (255, 230, 170), drag=2.0)
        self.decal("scorch%d" % r.randrange(2), x, y, 760)
        self.decal("crater%d" % r.randrange(2), x, y, 420)

    # -- world events ----------------------------------------------------------------------
    def handle(self, events):
        w = self.world
        ear = self.listener()
        for e in events:
            kind = e[0]
            if kind == "shot":
                _, pid, wi, x, y, ang, _pid = e
                wp = WEAPONS[wi]
                c, s = math.cos(ang), math.sin(ang)
                if wp["slot"] == SHELL:
                    big = 1.0 + wp["damage"] / 14.0
                    self.flashes.append([x, y, ang, 0.0, 0.09, big])
                    self.puff("glow", x + c * 20, y + s * 20, 0, 0, 0.1, 120 * big, 170 * big, 230, True,
                              (255, 200, 130))
                    for i in range(3):
                        self.puff("smoke%d" % self.rng.randrange(4), x + c * 14, y + s * 14,
                                  c * 70 * (i + 1) + self.rng.uniform(-25, 25), s * 70 * (i + 1) +
                                  self.rng.uniform(-25, 25), 0.9, 18, 54, 150, False, (190, 186, 178), 2.5)
                    if wp["pellets"] == 1 or self.rng.random() < 0.3:
                        self.snd.play_at("heavy" if wp["damage"] >= 10 else "cannon", x, y, ear, 1.0, 0.04)
                    if pid == self.local:
                        self.shake = max(self.shake, wp["shake"] * 0.6)
                else:
                    self.flashes.append([x, y, ang, 0.0, 0.05, 0.42 * wp["size"]])
                    self.snd.play_at("mg2" if wp["size"] > 1 else "mg", x, y, ear, 0.8, 0.045)
            elif kind == "hit":
                _, _pid, x, y, wi, what = e
                wp = WEAPONS[wi]
                if wp["key"] == "nuke_shell":
                    self.nuke(x, y)
                    self.snd.play_at("bigboom", x, y, ear, 1.0, reach=6000)
                    self.add_shake(x, y, 26, 2600)
                elif wp["slot"] == SHELL and wp["pellets"] == 1:
                    size = 0.55 + wp["damage"] / 13.0
                    self.explosion(x, y, size)
                    if wp["key"] == "death_shell":
                        self.puff("glow", x, y, 0, 0, 0.5, 200, 420, 255, True, (190, 90, 255))
                        self.puff("ring", x, y, 0, 0, 0.5, 40, 420, 255, True, (200, 120, 255))
                    if wp["key"] == "combust_shell":
                        self.burst("flame%d", x, y, 14, 150, 0.9, 40, 80, 255, True, spread=30)
                    self.snd.play_at("boom", x, y, ear, 0.7 + size * 0.2, 0.03)
                    self.add_shake(x, y, wp["shake"], 700)
                else:
                    self.burst("spark", x, y, 3, 260, 0.22, 20, 6, 255, True, (255, 225, 160), drag=3.0)
                    self.puff("glow", x, y, 0, 0, 0.1, 36, 60, 200, True, wp["glow"] or (255, 210, 150))
                    if what != "tank":
                        self.puff("smoke%d" % self.rng.randrange(4), x, y, 0, 0, 0.5, 14, 34, 130, False,
                                  (150, 130, 100))
                    self.snd.play_at("hit", x, y, ear, 0.55 if what == "tank" else 0.3, 0.035)
            elif kind == "kill":
                _, killer, victim, wi, x, y, ang, tank_key, reward = e
                self.explosion(x, y, 2.3)
                self.burst("fire%d", x, y, 8, 30, 1.1, 50, 100, 255, True, spread=24, delay=0.3)
                self.wrecks.append([tank_key, x, y, ang, self.time])
                self.decal("crater%d" % self.rng.randrange(2), x, y, 150)
                self.snd.play_at("boom", x, y, ear, 1.0)
                self.add_shake(x, y, 9, 900)
                kt, vt = w.players.get(killer), w.players.get(victim)
                self.feed.append((self.time, kt.name if kt else None, self.side(kt) if kt else -1,
                                  vt.name if vt else "?", self.side(vt) if vt else 0, wi))
                if killer == self.local and reward:
                    self.banner = (self.time, "+%d credits   %s destroyed" % (reward, vt.name if vt else ""),
                                   (255, 214, 90))
                    self.snd.play("buy", 0.7)
                elif victim == self.local:
                    self.banner = (self.time, "Destroyed by %s" % (kt.name if kt else "the battlefield"),
                                   (255, 110, 90))
            elif kind == "spawn":
                _, pid, x, y = e
                self.puff("ring", x, y, 0, 0, 0.6, 40, 220, 200, True, (120, 190, 255))
                self.track_pos.pop(pid, None)
            elif kind == "note":
                _, text, team, pid = e
                me = w.players.get(self.local)
                if pid >= 0:
                    good = pid == self.local
                    col = (255, 214, 90) if good else (236, 238, 240)
                elif team >= 0 and me is not None:
                    good = me.team == team
                    col = (120, 220, 110) if good else (255, 110, 90)
                else:
                    good, col = True, (236, 238, 240)
                self.banner = (self.time, text, col)
                self.snd.play("buy" if good else "deny", 0.6)
            elif kind == "sdead":
                _, idx, x, y = e
                self.explosion(x, y, 3.6)
                self.burst("fire%d", x, y, 14, 60, 1.4, 70, 150, 255, True, spread=50, delay=0.5)
                self.burst("smoke%d", x, y, 12, 40, 4.0, 80, 220, 200, False, (50, 48, 46), spread=60, delay=0.8)
                self.decal("crater%d" % self.rng.randrange(2), x, y, 260)
                self.snd.play_at("bigboom", x, y, ear, 1.0, reach=5000)
                self.add_shake(x, y, 16, 1800)
            elif kind == "reset":
                self.wrecks.clear()
                self.track_pos.clear()
            elif kind == "zone":
                _, what, idx, pid = e
                me = w.players.get(self.local)
                who = w.players.get(pid)
                good = bool(me and who and me.team == who.team)
                self.banner = (self.time, "%s captured zone %s" % (who.name if who else "?", data.ZONE_NAMES[idx]),
                               (120, 220, 110) if good else (255, 110, 90))
                c = w.cps[idx]
                self.puff("ring", c[0], c[1], 0, 0, 0.7, 120, 560, 255, True,
                          data.TEAM_UI[who.team] if who else None)
                self.snd.play("buy" if good else "deny", 0.8)
            elif kind == "out":
                who = w.players.get(e[1])
                if who and e[1] != self.local:
                    self.feed.append((self.time, None, -1, who.name + " is out", who.team, None))
            elif kind == "flag":
                _, what, team, pid = e
                me = w.players.get(self.local)
                who = w.players.get(pid)
                name = who.name if who else ""
                ours = me is not None and me.team == team          # it is OUR flag this happened to
                flag = "your flag" if ours else "the enemy flag"
                if what == "taken":
                    text, good = "%s has taken %s!" % (name, flag), not ours
                elif what == "dropped":
                    text, good = "%s dropped %s" % (name, flag), ours
                elif what == "returned":
                    text, good = ("%s returned %s" % (name, flag)) if name else (flag.capitalize() + " returned"), ours
                else:
                    text, good = "%s captured %s!" % (name, flag), not ours
                    f = w.flags[team] if team < len(w.flags) else None
                    hx, hy = self.map.flag_homes[1 - team]
                    self.puff("ring", hx, hy, 0, 0, 0.8, 60, 520, 255, True, data.TEAM_UI[1 - team])
                self.banner = (self.time, text, (120, 220, 110) if good else (255, 110, 90))
                self.snd.play("buy" if good else "deny", 0.8)
            elif kind == "crush":
                o = self.map.objects[e[1]]
                self.snd.play_at("hit", o["x"], o["y"], ear, 0.5 if o["kind"] == "tree" else 0.2, 0.05, reach=900)
            elif kind == "swap":
                _, pid, x, y = e
                self.puff("ring", x, y, 0, 0, 0.5, 40, 200, 220, True, (255, 220, 120))
                self.burst("smoke%d", x, y, 6, 60, 0.8, 30, 70, 150, False, (200, 200, 200))

    def side(self, t):
        """0 / 1 colour index for a tank: its team, or us-versus-them when every tank is its own team."""
        if self.world.ffa:
            me = self.world.players.get(self.local)
            return 0 if (me is not None and t.team == me.team) else 1
        return t.team % 2

    def decal(self, name, x, y, size):
        """Scorch marks and craters are painted straight into the ground, so they cost nothing to keep."""
        self.ground.stamp(self.a.scaled(self.a.fx[name], size, size, name), x, y)

    def add_shake(self, x, y, amount, reach):
        lx, ly = self.listener()
        d = math.hypot(x - lx, y - ly)
        if d < reach:
            self.shake = max(self.shake, amount * (1 - d / reach))

    def listener(self):
        t = self.world.players.get(self.local)
        if t and (t.alive or self.focus is None):
            return (t.x, t.y)
        return self.focus or (self.map.w / 2, self.map.h / 2)

    # -- update ---------------------------------------------------------------------------------
    def update(self, dt, screen_size, mouse):
        self.time += dt
        sw, sh = screen_size
        t = self.world.players.get(self.local)
        watched = self.world.players.get(self.follow) if self.follow is not None else None
        if t and t.alive:
            self.focus = (t.x, t.y)
        elif watched and watched.alive:
            self.focus = (watched.x, watched.y)
        fx, fy = self.focus or (self.map.w / 2, self.map.h / 2)
        tx = fx - sw / 2 + (mouse[0] - sw / 2) * 0.28
        ty = fy - sh / 2 + (mouse[1] - sh / 2) * 0.28
        k = min(1.0, dt * 7.0)
        self.cam[0] += (tx - self.cam[0]) * k
        self.cam[1] += (ty - self.cam[1]) * k
        self.cam[0] = max(0.0, min(self.map.w - sw, self.cam[0]))
        self.cam[1] = max(0.0, min(self.map.h - sh, self.cam[1]))
        self.shake = max(0.0, self.shake - dt * 30.0)
        self.flash = max(0.0, self.flash - dt * 1.3)

        # particles
        keep = []
        for p in self.particles:
            p[5] += dt
            if p[5] < p[6]:
                if p[5] > 0:
                    f = max(0.0, 1.0 - p[12] * dt)
                    p[3] *= f
                    p[4] *= f
                    p[1] += p[3] * dt
                    p[2] += p[4] * dt
                keep.append(p)
        self.particles = keep
        for f in self.flashes:
            f[3] += dt
        self.flashes = [f for f in self.flashes if f[3] < f[4]]

        # tread marks, damage smoke, dust
        self._emit += dt
        emit = self._emit > 0.07
        if emit:
            self._emit = 0.0
        cx, cy = self.cam
        r = self.rng
        for tk in self.world.players.values():
            if not tk.alive:
                continue
            last = self.track_pos.get(tk.pid)
            if last is None or (tk.x - last[0]) ** 2 + (tk.y - last[1]) ** 2 > 30 * 30:
                if last is not None and (tk.x - last[0]) ** 2 + (tk.y - last[1]) ** 2 < 150 * 150 \
                        and self.ground.has(int(tk.x) // CH, int(tk.y) // CH):
                    self.ground.stamp(self._track_sprite(int(round(tk.angle / FRAME_STEP)) % 32,
                                                         int(tk.art["width"] * PPM)), tk.x, tk.y)
                self.track_pos[tk.pid] = (tk.x, tk.y)
            if not emit or not (cx - 100 < tk.x < cx + sw + 100 and cy - 100 < tk.y < cy + sh + 100):
                continue
            frac = tk.hp / tk.max_hp
            if frac < 0.5:
                self.puff("smoke%d" % r.randrange(4), tk.x + r.uniform(-10, 10), tk.y + r.uniform(-10, 10),
                          r.uniform(-12, 12), -r.uniform(10, 30), 1.2, 16, 52, 150 if frac < 0.25 else 90, False,
                          (48, 46, 44) if frac < 0.25 else (120, 118, 114), 0.6)
                if frac < 0.25 and r.random() < 0.6:
                    self.puff("flame%d" % r.randrange(4), tk.x + r.uniform(-12, 12), tk.y + r.uniform(-12, 12), 0,
                              -20, 0.4, 22, 38, 255, True)
            if abs(tk.speed) > 60 and r.random() < 0.5:
                bx = tk.x - math.cos(tk.angle) * tk.radius * (1 if tk.speed > 0 else -1)
                by = tk.y - math.sin(tk.angle) * tk.radius * (1 if tk.speed > 0 else -1)
                wet = self.map.shallow_at(tk.x, tk.y)
                self.puff("smoke%d" % r.randrange(4), bx + r.uniform(-14, 14), by + r.uniform(-14, 14), 0, 0, 0.8,
                          14, 46, 110 if wet else 70, False, (210, 230, 240) if wet else (150, 128, 96), 1.0)
        if emit:
            for z in self.world.zones:
                _id, kind, x, y, rad, left = z[:6]
                if not (cx - rad - 60 < x < cx + sw + rad + 60 and cy - rad - 60 < y < cy + sh + rad + 60):
                    continue
                fade = min(1.0, left / 1.5)
                if kind == "fire":
                    for _ in range(5):
                        a, d = r.uniform(0, TAU), rad * math.sqrt(r.random()) * 0.95
                        self.puff("flame%d" % r.randrange(4), x + math.cos(a) * d, y + math.sin(a) * d,
                                  r.uniform(-8, 8), -r.uniform(8, 30), r.uniform(0.35, 0.7), 34 * fade + 8,
                                  60 * fade + 10, 255, True)
                    a, d = r.uniform(0, TAU), rad * r.random()
                    self.puff("smoke%d" % r.randrange(4), x + math.cos(a) * d, y + math.sin(a) * d, r.uniform(-10, 10),
                              -r.uniform(20, 50), 1.6, 30, 100, int(120 * fade), False, (44, 42, 40), 0.3)
                    self.snd.play_at("fire", x, y, self.listener(), 0.35, 0.5, reach=900)
                else:
                    for _ in range(2):
                        a, d = r.uniform(0, TAU), rad * math.sqrt(r.random())
                        self.puff("smoke%d" % r.randrange(4), x + math.cos(a) * d, y + math.sin(a) * d,
                                  r.uniform(-14, 14), r.uniform(-14, 14), 2.4, 70, 150, int(70 * fade), False,
                                  (120, 210, 70), 0.3)
            for wk in self.wrecks:
                age = self.time - wk[4]
                if age < 9 and r.random() < 0.6 and cx - 80 < wk[1] < cx + sw + 80 and cy - 80 < wk[2] < cy + sh + 80:
                    self.puff("smoke%d" % r.randrange(4), wk[1] + r.uniform(-12, 12), wk[2] + r.uniform(-12, 12),
                              r.uniform(-10, 10), -r.uniform(15, 40), 1.8, 22, 80, int(150 * (1 - age / 9)), False,
                              (40, 38, 36), 0.3)
                    if age < 4:
                        self.puff("flame%d" % r.randrange(4), wk[1] + r.uniform(-16, 16), wk[2] + r.uniform(-16, 16),
                                  0, -18, 0.45, 26, 44, 255, True)

    # -- drawing -----------------------------------------------------------------------------------
    def draw(self, screen):
        sw, sh = screen.get_size()
        cx, cy = self.cam
        if self.shake > 0.3:
            cx += self.rng.uniform(-1, 1) * self.shake
            cy += self.rng.uniform(-1, 1) * self.shake
        cx, cy = int(cx), int(cy)
        a = self.a
        blit = screen.blit

        # ground
        gx0, gy0 = cx // CH, cy // CH
        gx1, gy1 = (cx + sw) // CH, (cy + sh) // CH
        for gy in range(gy0, gy1 + 1):
            for gx in range(gx0, gx1 + 1):
                blit(self.ground.chunk(gx, gy), (gx * CH - cx, gy * CH - cy))
        self._prewarm(gx0, gy0, gx1, gy1)

        seen = self._visible_objects(cx, cy, sw, sh)

        def visible(layer):
            return seen[layer]

        for o in visible(LAYER_GROUND):
            blit(o[0], (o[1] - cx, o[2] - cy))
        for i, c in enumerate(self.world.cps):       # Zone Defense: ground markings in the owner's colour
            zx, zy = c[0], c[1]
            if cx - 200 < zx < cx + sw + 200 and cy - 200 < zy < cy + sh + 200:
                art = a.zone_art["n" if c[2] < 0 else str(c[2])]
                blit(art, (zx - cx - art.get_width() // 2, zy - cy - art.get_height() // 2))
                if c[3] >= 0:                        # being captured: a ring sweeps round as the clock runs
                    who = self.world.players.get(c[3])
                    col = data.TEAM_UI[who.team] if who else (255, 255, 255)
                    r = data.ZONE_RADIUS + 14
                    frac = min(1.0, c[4] / data.ZONE_CAPTURE_TIME)
                    pygame.draw.arc(screen, col, (zx - cx - r, zy - cy - r, r * 2, r * 2), math.pi / 2 - TAU * frac,
                                    math.pi / 2, 7)
        flags = self.world.flags
        for team in range(len(flags)):               # Capture the Flag: the pads the flags stand on
            hx, hy = self.map.flag_homes[team]
            if cx - 80 < hx < cx + sw + 80 and cy - 80 < hy < cy + sh + 80:
                m = a.ctf_meta["base_%d" % team]
                blit(a.ctf["base_%d" % team], (hx - cx - m["ax"], hy - cy - m["ay"]))

        # wrecks (tread marks, scorches and craters are already painted into the ground)
        for key, x, y, ang, _t in self.wrecks:
            if cx - 150 < x < cx + sw + 150 and cy - 150 < y < cy + sh + 150:
                spr = a.tank(key, None)
                k = int(round(ang / FRAME_STEP)) % 32
                blit(spr.hull[k], (x - cx - spr.hf // 2, y - cy - spr.hf // 2))
                txo = a.tank_meta[key]["turret_x"] * PPM
                k2 = (k + 5) % 32
                blit(spr.turret[k2], (x + math.cos(ang) * txo - cx - spr.tf // 2 + 6,
                                      y + math.sin(ang) * txo - cy - spr.tf // 2 + 4))

        # lingering zones on the ground
        for z in self.world.zones:
            _id, kind, x, y, rad, left = z[:6]
            if cx - rad < x < cx + sw + rad and cy - rad < y < cy + sh + rad:
                lvl = int(110 * min(1.0, left / 2.0))
                col = (255, 120, 30) if kind == "fire" else (90, 255, 60)
                s = self.fx_sprite("glow_soft", rad * 2.6, col, True, lvl)
                blit(s, (x - cx - s.get_width() // 2, y - cy - s.get_height() // 2), special_flags=ADD)

        for o in visible(LAYER_LOW):
            blit(o[0], (o[1] - cx, o[2] - cy))

        # tanks
        tanks = [t for t in self.world.players.values()
                 if t.alive and cx - 220 < t.x < cx + sw + 220 and cy - 220 < t.y < cy + sh + 220]
        for s in self.world.structs:                 # the convoy truck drives among the tanks
            if s[0] == "truck" and s[5] > 0 and cx - 200 < s[2] < cx + sw + 200 and cy - 200 < s[3] < cy + sh + 200:
                k = int(round(s[7] / FRAME_STEP)) % 32
                sh_ = a.modes["truck_%d_shadow" % (s[1] % 2)][k]
                blit(sh_, (s[2] - cx - sh_.get_width() // 2 + 7, s[3] - cy - sh_.get_height() // 2 + 9))
                f = a.modes["truck_%d" % (s[1] % 2)][k]
                blit(f, (s[2] - cx - f.get_width() // 2, s[3] - cy - f.get_height() // 2))
        marks = self.world.rules.marks() if self.world.rules else {}
        for t in tanks:
            if t.pid in marks:                       # VIP / Juggernaut: a gold ring on the ground
                lvl = 150 + int(70 * math.sin(self.time * 5))
                g = self.fx_sprite("ring", t.radius * 4.2, (255, 200, 60), True, lvl)
                blit(g, (t.x - cx - g.get_width() // 2, t.y - cy - g.get_height() // 2), special_flags=ADD)
        for t in tanks:
            hs, _ts = a.tank_shadows(t.tank_key)
            k = int(round(t.angle / FRAME_STEP)) % 32
            f = hs[k]
            blit(f, (t.x - cx - f.get_width() // 2 + 7, t.y - cy - f.get_height() // 2 + 9))
        for t in tanks:
            self._draw_tank(screen, t, cx, cy)

        # projectiles
        for p in self.world.projectiles.values():
            x, y = p[4] - cx, p[5] - cy
            if -60 < x < sw + 60 and -60 < y < sh + 60:
                wp = WEAPONS[p[3]]
                if wp["glow"]:
                    if wp["slot"] == AUTO:
                        st = self._streak(wp, p[9])
                        blit(st, (x - math.cos(p[9]) * 26 - st.get_width() // 2,
                                  y - math.sin(p[9]) * 26 - st.get_height() // 2), special_flags=ADD)
                    else:
                        g = self.fx_sprite("glow", 66, wp["glow"], True)
                        blit(g, (x - 33, y - 33), special_flags=ADD)
                s = self.ammo_sprite(wp["key"], p[9])
                blit(s, (x - s.get_width() // 2, y - s.get_height() // 2))
        for fx_, fy_, ang, age, life, scale in self.flashes:
            s = self._muzzle(ang, scale)
            blit(s, (fx_ - cx + math.cos(ang) * 30 * scale - s.get_width() // 2,
                     fy_ - cy + math.sin(ang) * 30 * scale - s.get_height() // 2), special_flags=ADD)

        for team, f in enumerate(flags):             # flags stand above tanks, and ride on their carrier
            fx_, fy_ = f[1], f[2]
            if f[0] == 1:
                c = self.world.players.get(f[3])
                if c:
                    fx_, fy_ = c.x, c.y
            if cx - 200 < fx_ < cx + sw + 200 and cy - 200 < fy_ < cy + sh + 200:
                if f[0] == 2:                        # dropped: a pulsing ring so it is easy to spot
                    lvl = 120 + int(80 * math.sin(self.time * 6))
                    g = self.fx_sprite("ring", 150, data.TEAM_UI[team], True, lvl)
                    blit(g, (fx_ - cx - g.get_width() // 2, fy_ - cy - g.get_height() // 2), special_flags=ADD)
                m = a.ctf_meta["flag_%d" % team]
                blit(a.ctf["flag_%d" % team], (fx_ - cx - m["ax"], fy_ - cy - m["ay"]))

        # scenery above tanks
        for o in visible(LAYER_SOLID):
            blit(o[0], (o[1] - cx, o[2] - cy))
        for s in self.world.structs:                 # headquarters buildings
            if s[0] == "hq" and cx - 300 < s[2] < cx + sw + 300 and cy - 300 < s[3] < cy + sh + 300:
                name = "hq_%d" % (s[1] % 2) if s[5] > 0 else "hq_dead"
                m = a.modes_meta[name]
                blit(a.modes[name], (s[2] - cx - m["ax"], s[3] - cy - m["ay"]))
        me = self.world.players.get(self.local)
        for o in visible(LAYER_CANOPY):
            s = o[0]
            if me and me.alive and abs(me.x - o[5]) < 120 and abs(me.y - o[6]) < 120:
                s = self._fade(s)
            blit(s, (o[1] - cx, o[2] - cy))

        # particles
        for p in self.particles:
            age = p[5]
            if age <= 0:
                continue
            x, y = p[1] - cx, p[2] - cy
            if not (-160 < x < sw + 160 and -160 < y < sh + 160):
                continue
            f = age / p[6]
            size = p[7] + (p[8] - p[7]) * f
            if p[10]:
                lvl = int(p[9] * (1.0 - f) ** 1.3)
                if lvl < 24:
                    continue
                s = self.fx_sprite(p[0], size, p[11], True, lvl)
                blit(s, (x - s.get_width() // 2, y - s.get_height() // 2), special_flags=ADD)
            else:
                al = int(p[9] * (1.0 - f) * min(1.0, f * 8))
                if al < 8:
                    continue
                s = self.fx_sprite(p[0], size, p[11])
                s.set_alpha(al)
                blit(s, (x - s.get_width() // 2, y - s.get_height() // 2))

        if self.flash > 0.02:
            ov = pygame.Surface((sw, sh))
            v = int(255 * min(1.0, self.flash))
            ov.fill((v, v, int(v * 0.9)))
            blit(ov, (0, 0), special_flags=ADD)
        return cx, cy

    def _visible_objects(self, cx, cy, sw, sh):
        """Scenery on screen, per layer, in draw order. Uses a coarse grid so we never scan the whole map."""
        out = [[], [], [], []]
        found = set()
        gone = self.world.crushed            # flattened bushes and felled trees are simply no longer drawn
        B = self.BUCKET
        for by in range(cy // B, (cy + sh) // B + 1):
            for bx in range(cx // B, (cx + sw) // B + 1):
                for i in self.buckets.get((bx, by), ()):
                    if i not in found:
                        found.add(i)
        for i in sorted(found):
            layer, o = self.flat[i]
            if o[8] in gone:
                continue
            if o[3] > cx and o[1] < cx + sw and o[4] > cy and o[2] < cy + sh:
                out[layer].append(o)
        return out

    def _prewarm(self, gx0, gy0, gx1, gy1):
        """Build at most one off-screen neighbour chunk per frame so scrolling never stalls."""
        for gy in range(gy0 - 2, gy1 + 3):
            for gx in range(gx0 - 2, gx1 + 3):
                if gx >= 0 and gy >= 0 and gx * CH < self.map.w and gy * CH < self.map.h \
                        and not self.ground.has(gx, gy):
                    self.ground.chunk(gx, gy)
                    return

    def _fade(self, s):
        f = self._faded.get(id(s))
        if f is None:
            f = s.copy()
            f.fill((255, 255, 255, 105), special_flags=pygame.BLEND_RGBA_MULT)
            self._faded[id(s)] = f
        return f

    def _track_sprite(self, k, width):
        key = ("trk", k, width)
        s = self._ammo_rot.get(key)
        if s is None:
            base = pygame.transform.smoothscale(self.a.fx["tracks"], (34, max(8, width)))
            s = pygame.transform.rotozoom(base, -k * 360.0 / 32, 1.0)
            s.set_alpha(120)
            self._ammo_rot[key] = s
        return s

    def _streak(self, wp, ang):
        b = int(round(ang / TAU * 48)) % 48
        key = ("streak", wp["key"], b)
        s = self._ammo_rot.get(key)
        if s is None:
            base = pygame.transform.smoothscale(self.a.fx_add["spark"], (int(86 * wp["size"]), int(30 * wp["size"])))
            base.fill(wp["glow"] + (255,), special_flags=pygame.BLEND_RGB_MULT)
            s = pygame.transform.rotozoom(base, -b * 360.0 / 48, 1.0)
            self._ammo_rot[key] = s
        return s

    def _muzzle(self, ang, scale):
        b = int(round(ang / TAU * 32)) % 32
        sz = max(24, int(120 * scale) // 8 * 8)
        key = ("mz", b, sz, self.rng.randrange(2))
        s = self._ammo_rot.get(key)
        if s is None:
            base = pygame.transform.smoothscale(self.a.fx_add["muzzle%d" % key[3]], (sz, sz))
            s = pygame.transform.rotozoom(base, -b * 360.0 / 32, 1.0)
            self._ammo_rot[key] = s
        return s

    def _draw_tank(self, screen, t, cx, cy):
        a = self.a
        spr = a.tank(t.tank_key, t.color)
        x, y = t.x - cx, t.y - cy
        k = int(round(t.angle / FRAME_STEP))
        resid = t.angle - k * FRAME_STEP
        k %= 32
        hull = self.rotated(spr.hull[k], resid, (t.tank_key, t.color, 0, k))
        screen.blit(hull, (x - hull.get_width() // 2, y - hull.get_height() // 2))
        txo = t.art["turret_x"] * PPM
        rc = t.recoil * 5.0
        px = x + math.cos(t.angle) * txo - math.cos(t.turret) * rc
        py = y + math.sin(t.angle) * txo - math.sin(t.turret) * rc
        k2 = int(round(t.turret / FRAME_STEP))
        resid2 = t.turret - k2 * FRAME_STEP
        k2 %= 32
        _hs, ts = a.tank_shadows(t.tank_key)
        sh = ts[k2]
        screen.blit(sh, (px - sh.get_width() // 2 + 4, py - sh.get_height() // 2 + 5))
        tur = self.rotated(spr.turret[k2], resid2, (t.tank_key, t.color, 1, k2))
        screen.blit(tur, (px - tur.get_width() // 2, py - tur.get_height() // 2))
        if t.shield > 0:
            s = self.fx_sprite("ring", t.radius * 3.4, (110, 180, 255), True, 150)
            screen.blit(s, (x - s.get_width() // 2, y - s.get_height() // 2), special_flags=ADD)
        # white-hot flicker when the tank has just been hit
        last = self.hp_seen.get(t.pid, t.hp)
        if t.hp < last - 0.01:
            self.hit_flash[t.pid] = self.time
        self.hp_seen[t.pid] = t.hp
        if self.time - self.hit_flash.get(t.pid, -9) < 0.08:
            g = self.fx_sprite("glow", t.radius * 2.6, (255, 240, 220), True, 120)
            screen.blit(g, (x - g.get_width() // 2, y - g.get_height() // 2), special_flags=ADD)
