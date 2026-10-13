"""Procedural battlefields. A map is fully determined by (preset, seed), so multiplayer clients rebuild it locally.

No pygame in here: the dedicated simulation (and tests) can build maps headless.
"""
import json
import math
import os
import random
from collections import deque

import numpy as np
from PIL import Image

from . import data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENERY_DIR = os.path.join(ROOT, "assets", "scenery")
CELL, NAV = data.CELL, data.NAV
GW, GH = data.MAP_W // CELL, data.MAP_H // CELL
NW, NH = data.MAP_W // NAV, data.MAP_H // NAV
LAYER_GROUND, LAYER_LOW, LAYER_SOLID, LAYER_CANOPY = 0, 1, 2, 3
CRUSH_CELL = 160

PRESETS = {
    "valley": dict(river=dict(amp=520, hw=115, bridges=3, fords=2), mountains=5, villages=3, forest=0.50,
                   pine=0.25, boulders=70, lone_trees=0.035, dry=0.45),
    "highlands": dict(river=None, mountains=11, villages=1, forest=0.46, pine=0.8, boulders=150, lone_trees=0.03,
                      dry=0.6),
    "farmland": dict(river=dict(amp=700, hw=70, bridges=2, fords=5), mountains=2, villages=6, forest=0.62,
                     pine=0.1, boulders=35, lone_trees=0.05, dry=0.3),
}

_meta = None
_masks = {}


def scenery_meta():
    global _meta
    if _meta is None:
        with open(os.path.join(SCENERY_DIR, "scenery.json"), encoding="utf-8") as f:
            _meta = json.load(f)
    return _meta


def cell_mask(name):
    """Which collision cells a sprite's solid part covers, for a sprite whose top-left is aligned to the grid."""
    if name not in _masks:
        m = scenery_meta()[name]
        a = np.asarray(Image.open(os.path.join(SCENERY_DIR, name + ".png")).convert("RGBA"))[..., 3]
        solid = np.zeros(a.shape, bool)
        x0, y0, x1, y1 = m["foot"]
        solid[y0:y1, x0:x1] = a[y0:y1, x0:x1] > 215      # baked shadows are translucent, the object is opaque
        h = -(-a.shape[0] // CELL) * CELL
        w = -(-a.shape[1] // CELL) * CELL
        pad = np.zeros((h, w), np.float32)
        pad[:a.shape[0], :a.shape[1]] = solid
        _masks[name] = pad.reshape(h // CELL, CELL, w // CELL, CELL).mean(axis=(1, 3)) >= 0.45
    return _masks[name]


# ---------------------------------------------------------------------------
# small numeric helpers

def upsample(coarse, h, w):
    """Bilinear resize of a 2D array to (h, w)."""
    ch, cw = coarse.shape
    ys = np.linspace(0, ch - 1.001, h)
    xs = np.linspace(0, cw - 1.001, w)
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    a = coarse[y0][:, x0]
    b = coarse[y0][:, x0 + 1]
    c = coarse[y0 + 1][:, x0]
    d = coarse[y0 + 1][:, x0 + 1]
    return ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy).astype(np.float32)


def vnoise(rs, period, octaves=3):
    """Value noise over the cell grid, 0..1. `period` is the feature size in cells."""
    out = np.zeros((GH, GW), np.float32)
    amp, total = 1.0, 0.0
    for _ in range(octaves):
        p = max(2, int(period))
        out += amp * upsample(rs.rand(GH // p + 3, GW // p + 3).astype(np.float32), GH, GW)
        total += amp
        amp *= 0.5
        period /= 2
    return out / total


def blur(a, r):
    a = a.astype(np.float32)
    for axis in (0, 1):
        pad = [(r + 1, r) if ax == axis else (0, 0) for ax in (0, 1)]
        c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis)
        n = a.shape[axis]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
        lo = np.take(c, np.arange(0, n), axis=axis)
        a = (hi - lo) / (2 * r + 1)
    return a


def dilate(mask, r):
    out = mask.copy()
    for _ in range(r):
        m = out.copy()
        m[1:, :] |= out[:-1, :]
        m[:-1, :] |= out[1:, :]
        m[:, 1:] |= out[:, :-1]
        m[:, :-1] |= out[:, 1:]
        out = m
    return out


def dist_polyline(pts):
    """Distance in pixels from every cell centre to a polyline [(x, y), ...]."""
    ys, xs = np.mgrid[0:GH, 0:GW].astype(np.float32)
    px = xs * CELL + CELL / 2
    py = ys * CELL + CELL / 2
    best = np.full((GH, GW), 1e9, np.float32)
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        dx, dy = bx - ax, by - ay
        ln = dx * dx + dy * dy or 1.0
        t = np.clip(((px - ax) * dx + (py - ay) * dy) / ln, 0, 1)
        d = np.hypot(px - (ax + t * dx), py - (ay + t * dy))
        np.minimum(best, d, out=best)
    return best


# ---------------------------------------------------------------------------

class GameMap:
    def __init__(self, preset="valley", seed=1):
        self.preset = preset if preset in PRESETS else "valley"
        self.seed = int(seed)
        self.w, self.h = data.MAP_W, data.MAP_H
        for attempt in range(25):
            self._generate(self.seed * 7919 + attempt * 104729)
            if self._connected():
                break
        self._finish()

    # -- generation -------------------------------------------------------------
    def _generate(self, s):
        P = PRESETS[self.preset]
        rng = random.Random(s)
        rs = np.random.RandomState(s % (2 ** 31))
        W, H = self.w, self.h
        meta = scenery_meta()
        self.objects = []
        self.solid = np.zeros((GH, GW), bool)
        self.water = np.zeros((GH, GW), np.uint8)       # 0 land, 1 deep (impassable), 2 shallow (slow)
        occ = np.zeros((GH, GW), bool)                  # where nothing else may be placed
        occ[:3, :] = occ[-3:, :] = occ[:, :3] = occ[:, -3:] = True
        ys, xs = np.mgrid[0:GH, 0:GW]
        cy_px = ys * CELL + CELL / 2
        cx_px = xs * CELL + CELL / 2

        # spawn zones on the west and east edges
        self.zones = [(160, 600, 1000, H - 600), (W - 1000, 600, W - 160, H - 600)]
        for x0, y0, x1, y1 in self.zones:
            occ[(y0 - 100) // CELL:(y1 + 100) // CELL, (x0 - 100) // CELL:(x1 + 100) // CELL] = True

        # --- river ------------------------------------------------------------
        self.river = None
        self.rdist = np.full((GH, GW), 1e9, np.float32)
        self.ford = np.zeros((GH, GW), np.float32)
        self.crossings = []
        roads = []
        R = P["river"]
        if R:
            p1, p2 = rng.uniform(0, 6.28), rng.uniform(0, 6.28)
            f1, f2 = rng.uniform(1500, 2100), rng.uniform(600, 900)

            def rx(y):
                return W / 2 + R["amp"] * math.sin(y / f1 + p1) + R["amp"] * 0.3 * math.sin(y / f2 + p2)

            self.river = [(rx(y), y) for y in range(-300, H + 301, 120)]
            self.river_hw = hw = R["hw"]
            self.rdist = dist_polyline(self.river)
            self.water[self.rdist < hw - 20] = 1
            n = R["bridges"] + R["fords"]
            kinds = ["bridge"] * R["bridges"] + ["ford"] * R["fords"]
            # spread crossings top to bottom, alternating so bridges are not bunched together
            order = sorted(range(n), key=lambda i: (i * 2 + 1) % n if n % 2 else (i * 3 + 1) % n)
            for slot, i in enumerate(order):
                y = H * (slot + 0.5) / n + rng.uniform(-0.2, 0.2) * H / n
                y = int(y // NAV) * NAV + NAV // 2            # centred on an AI navigation cell
                x = rx(y)
                self.crossings.append((kinds[i], x, y))
            for kind, x, y in self.crossings:
                if kind == "bridge":
                    b = meta["bridge0"]
                    hl, hwid = b["length"] * data.PPM / 2 - 10, b["width"] * data.PPM / 2 - 10
                    tx = int(round((x - b["ax"]) / CELL)) * CELL
                    ty = int(round((y - b["ay"]) / CELL)) * CELL
                    bx, by = tx + b["ax"], ty + b["ay"]
                    self.objects.append(dict(name="bridge0", x=bx, y=by, layer=LAYER_GROUND, kind="bridge"))
                    deck = (np.abs(cx_px - bx) < hl) & (np.abs(cy_px - by) < hwid)
                    self.water[deck] = 0
                    # rails: water just outside the deck stays deep, so tanks cannot drive off the side
                else:
                    band = np.abs(cy_px - y) < 140
                    self.water[band & (self.water == 1)] = 2
                    self.ford = np.maximum(self.ford, np.clip(1.3 - np.abs(cy_px - y) / 150.0, 0, 1))
                occ |= (np.abs(cy_px - y) < 200) & (np.abs(cx_px - x) < 620)
                for z, side in ((self.zones[0], -1), (self.zones[1], 1)):
                    zx = z[2] if side < 0 else z[0]
                    zy = (z[1] + z[3]) / 2 + (y - H / 2) * 0.55
                    midx = (zx + x) / 2
                    roads.append([(zx, zy), (midx, (zy + y) / 2 + rng.uniform(-200, 200)), (x + side * 420, y),
                                  (x, y)])
            occ |= self.rdist < hw + 130
        else:
            for k in range(3):
                y = H * (0.2 + 0.3 * k)
                pts = [(self.zones[0][2], y)]
                for i in range(1, 6):
                    pts.append((W * i / 6, y + rng.uniform(-420, 420)))
                pts.append((self.zones[1][0], y))
                roads.append(pts)
        self.roads = roads
        rd = np.full((GH, GW), 1e9, np.float32)
        for r in roads:
            np.minimum(rd, dist_polyline(r), out=rd)
        self.road_dist = rd
        occ |= rd < 75

        def stamp(name, tx, ty, margin, layer, kind):
            """Place a sprite with its top-left at grid-aligned (tx, ty) if the footprint is free."""
            m = meta[name]
            mask = cell_mask(name)
            gx, gy = tx // CELL, ty // CELL
            mh, mw = mask.shape
            if gx < 2 or gy < 2 or gx + mw > GW - 2 or gy + mh > GH - 2:
                return False
            f = m["foot"]
            fx0, fy0 = gx + f[0] // CELL, gy + f[1] // CELL
            fx1, fy1 = gx + -(-f[2] // CELL), gy + -(-f[3] // CELL)
            if occ[max(0, fy0 - 1):fy1 + 1, max(0, fx0 - 1):fx1 + 1].any():
                return False
            self.solid[gy:gy + mh, gx:gx + mw] |= mask
            occ[max(0, fy0 - margin):fy1 + margin, max(0, fx0 - margin):fx1 + margin] = True
            self.objects.append(dict(name=name, x=tx + m["ax"], y=ty + m["ay"], layer=layer, kind=kind))
            return True

        def snap(v):
            return int(v // CELL) * CELL

        # --- mountains --------------------------------------------------------
        self.mountain_mask = np.zeros((GH, GW), bool)
        placed = 0
        for _ in range(P["mountains"] * 40):
            if placed >= P["mountains"]:
                break
            name = "mountain%d" % rng.choice([0, 0, 1, 1, 2, 2, 3])
            if stamp(name, snap(rng.uniform(900, W - 900 - meta[name]["w"])),
                     snap(rng.uniform(60, H - 60 - meta[name]["h"])), 7, LAYER_SOLID, "mountain"):
                placed += 1
        self.mountain_mask = self.solid.copy()

        # --- villages ----------------------------------------------------------
        house_names = ["house0", "house0_r", "house1", "house1_r", "house2", "house2_r", "house3", "house3_r",
                       "barn0", "barn0_r"]
        self.village_field = np.zeros((GH, GW), np.float32)
        made = 0
        for _ in range(P["villages"] * 30):
            if made >= P["villages"]:
                break
            vx, vy = rng.uniform(1300, W - 1300), rng.uniform(500, H - 500)
            if occ[int(vy) // CELL, int(vx) // CELL]:
                continue
            count = 0
            for _ in range(40):
                if count >= rng.randint(4, 7):
                    break
                name = rng.choice(house_names)
                a, d = rng.uniform(0, 6.28), rng.uniform(0, 520)
                if stamp(name, snap(vx + math.cos(a) * d - meta[name]["w"] / 2),
                         snap(vy + math.sin(a) * d * 0.8 - meta[name]["h"] / 2), 6, LAYER_SOLID, "house"):
                    count += 1
            if count >= 2:
                made += 1
                self.village_field = np.maximum(
                    self.village_field, np.clip(1.25 - np.hypot(cx_px - vx, (cy_px - vy) * 1.2) / 560.0, 0, 1))
                for _ in range(rng.randint(5, 9)):
                    name = rng.choice(["hay0", "hay0", "crates0"])
                    a, d = rng.uniform(0, 6.28), rng.uniform(80, 560)
                    self._prop(name, vx + math.cos(a) * d, vy + math.sin(a) * d, occ, meta)

        # --- forests ------------------------------------------------------------
        dens = vnoise(rs, 34, 3)
        pine_n = vnoise(rs, 50, 2)
        self.tree_field = np.zeros((GH, GW), np.float32)
        step = 175
        thr = P["forest"]
        for gy in range(int(H / step)):
            for gx in range(int(W / step)):
                x = (gx + 0.5) * step + rng.uniform(-55, 55)
                y = (gy + 0.5) * step + rng.uniform(-55, 55)
                cx, cy = int(x) // CELL, int(y) // CELL
                if not (3 <= cx < GW - 3 and 3 <= cy < GH - 3) or occ[cy, cx]:
                    continue
                d = dens[cy, cx]
                p = min(0.92, (d - thr) * 9.0) if d > thr else P["lone_trees"]
                if rng.random() >= p:
                    continue
                pine = pine_n[cy, cx] < P["pine"] * 0.62 + 0.19
                name = "pine%d" % rng.randrange(3) if pine else "tree%d" % rng.randrange(5)
                self.objects.append(dict(name=name, x=x, y=y, layer=LAYER_CANOPY, kind="tree"))
                self.solid[cy, cx] = True
                occ[cy - 1:cy + 2, cx - 1:cx + 2] = True
                self.tree_field[cy - 2:cy + 3, cx - 2:cx + 3] = 1.0

        # --- boulders, bushes ------------------------------------------------------
        left = P["boulders"]
        for _ in range(P["boulders"] * 8):
            if left <= 0:
                break
            name = "boulder%d" % rng.randrange(5)
            if self._prop(name, rng.uniform(200, W - 200), rng.uniform(200, H - 200), occ, meta):
                left -= 1
        for _ in range(520):
            x, y = rng.uniform(100, W - 100), rng.uniform(100, H - 100)
            cx, cy = int(x) // CELL, int(y) // CELL
            if self.solid[cy, cx] or self.water[cy, cx] or self.rdist[cy, cx] < 200 or rd[cy, cx] < 60:
                continue
            self.objects.append(dict(name="bush%d" % rng.randrange(5), x=x, y=y, layer=LAYER_LOW, kind="bush"))

        # --- ground blend fields -----------------------------------------------------
        self.fields = dict(
            shade=0.86 + 0.26 * vnoise(rs, 45, 3),
            dry=np.clip((vnoise(rs, 40, 3) - (1.0 - P["dry"]) + 0.12) * 5.0, 0, 1),
            forest=np.clip(blur(self.tree_field, 5) * 2.4, 0, 0.9),
            dirt=np.clip(np.maximum.reduce([
                np.clip(1.0 - rd / 46.0, 0, 1) * (0.55 + 0.6 * vnoise(rs, 6, 2)),
                self.village_field * (0.35 + 0.75 * vnoise(rs, 9, 2)),
                self._zone_field(cx_px, cy_px) * (0.25 + 0.8 * vnoise(rs, 8, 2)),
            ]), 0, 0.95),
            rock=np.clip(blur(dilate(self.mountain_mask, 3), 4) * 1.6, 0, 1),
            grain=vnoise(rs, 5, 2),
        )

    def _zone_field(self, cx_px, cy_px):
        f = np.zeros((GH, GW), np.float32)
        for x0, y0, x1, y1 in self.zones:
            dx = np.maximum(np.maximum(x0 - cx_px, cx_px - x1), 0)
            dy = np.maximum(np.maximum(y0 - cy_px, cy_px - y1), 0)
            f = np.maximum(f, np.clip(1.0 - np.hypot(dx, dy) / 160.0, 0, 1))
        return f

    def _prop(self, name, x, y, occ, meta):
        """Small round obstacle (boulder, hay bale, crates)."""
        m = meta[name]
        r = m["solid_r"] * data.PPM
        cx, cy = int(x) // CELL, int(y) // CELL
        k = int(r // CELL) + 2
        if not (k + 2 <= cx < GW - k - 2 and k + 2 <= cy < GH - k - 2) or occ[cy - k:cy + k + 1, cx - k:cx + k + 1].any():
            return False
        yy, xx = np.mgrid[cy - k:cy + k + 1, cx - k:cx + k + 1]
        inside = np.hypot(xx * CELL + CELL / 2 - x, yy * CELL + CELL / 2 - y) <= r
        inside[k, k] = True
        self.solid[cy - k:cy + k + 1, cx - k:cx + k + 1] |= inside
        occ[cy - k - 2:cy + k + 3, cx - k - 2:cx + k + 3] = True
        self.objects.append(dict(name=name, x=x, y=y, layer=LAYER_SOLID, kind=m["kind"]))
        return True

    # -- navigation ---------------------------------------------------------------
    def _build_nav(self):
        blocked = dilate(self.solid | (self.water == 1), 2)
        blocked[:2, :] = blocked[-2:, :] = blocked[:, :2] = blocked[:, -2:] = True
        k = NAV // CELL
        core = blocked.reshape(NH, k, NW, k)[:, 1:k - 1, :, 1:k - 1]
        self.nav = core.any(axis=(1, 3))

    def _connected(self):
        self._build_nav()
        z0, z1 = self.zones
        start = self._free_cell((z0[0] + z0[2]) // 2, (z0[1] + z0[3]) // 2)
        goal = self._free_cell((z1[0] + z1[2]) // 2, (z1[1] + z1[3]) // 2)
        if start is None or goal is None:
            return False
        dist = self.flow_field([start])
        return dist[goal[1]][goal[0]] < 1e8

    def _free_cell(self, x, y):
        cx, cy = int(x) // NAV, int(y) // NAV
        for r in range(0, 8):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < NW and 0 <= ny < NH and not self.nav[ny, nx]:
                        return nx, ny
        return None

    def flow_field(self, sources):
        """Breadth-first distance (in nav cells) from the nearest source cell; 1e9 where unreachable."""
        nav = self.nav_list
        dist = [[1e9] * NW for _ in range(NH)]
        q = deque()
        for sx, sy in sources:
            if 0 <= sx < NW and 0 <= sy < NH:
                dist[sy][sx] = 0
                q.append((sx, sy))
        while q:
            x, y = q.popleft()
            d = dist[y][x] + 1
            if x > 0 and not nav[y][x - 1] and dist[y][x - 1] > d:
                dist[y][x - 1] = d
                q.append((x - 1, y))
            if x < NW - 1 and not nav[y][x + 1] and dist[y][x + 1] > d:
                dist[y][x + 1] = d
                q.append((x + 1, y))
            if y > 0 and not nav[y - 1][x] and dist[y - 1][x] > d:
                dist[y - 1][x] = d
                q.append((x, y - 1))
            if y < NH - 1 and not nav[y + 1][x] and dist[y + 1][x] > d:
                dist[y + 1][x] = d
                q.append((x, y + 1))
        return dist

    @property
    def nav_list(self):
        if getattr(self, "_nav_list_src", None) is not self.nav:
            self._nav_list = self.nav.tolist()
            self._nav_list_src = self.nav
        return self._nav_list

    def _finish(self):
        self._build_nav()
        # flat byte strings give fast scalar lookups in the simulation's inner loops
        self.block = bytearray((self.solid | (self.water == 1)).astype(np.uint8).tobytes())   # stops tanks
        self.shot_block = bytearray(self.solid.astype(np.uint8).tobytes())                    # stops projectiles
        # things a tank can drive over and destroy, bucketed for fast lookup: (object index, x, y, is_tree)
        self.crushables = {}
        for i, o in enumerate(self.objects):
            if o["kind"] in ("bush", "tree"):
                self.crushables.setdefault((int(o["x"]) // CRUSH_CELL, int(o["y"]) // CRUSH_CELL), []).append(
                    (i, o["x"], o["y"], o["kind"] == "tree"))
        self.nav_dirty = False
        self.shallow = (self.water == 2).astype(np.uint8).tobytes()
        # Capture the Flag: each team's flag stands on open ground a little in front of its spawn zone -
        # close enough to defend, far enough that respawning tanks do not appear on top of it
        self.flag_homes = []
        trees = [(o["x"], o["y"]) for o in self.objects if o["kind"] == "tree"]
        for i, (x0, y0, x1, y1) in enumerate(self.zones):
            fy = (y0 + y1) / 2
            best = None
            for ahead in (520, 440, 600, 360, 680, 280):
                fx = x1 + ahead if i == 0 else x0 - ahead
                for dy in (0, -160, 160, -320, 320, -480, 480):
                    cx, cy = int(fx) // NAV, int(fy + dy) // NAV
                    px, py = cx * NAV + NAV / 2, cy * NAV + NAV / 2
                    if self.nav[cy, cx] or self.blocked_circle(px, py, 90) or self.shallow_at(px, py):
                        continue
                    if any(abs(tx - px) < 170 and abs(ty - py) < 170 for tx, ty in trees):
                        continue                   # keep it out from under tree canopies
                    best = (px, py)
                    break
                if best:
                    break
            if best is None:
                c = self._free_cell(x1 + 300 if i == 0 else x0 - 300, fy)
                best = (c[0] * NAV + NAV / 2, c[1] * NAV + NAV / 2) if c else ((x0 + x1) / 2, fy)
            self.flag_homes.append(best)
        # Zone Defense: five zones strung across the map - one in front of each base, three in between
        def open_spot(x, y):
            for r in range(0, 12):
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if max(abs(dx), abs(dy)) != r:
                            continue
                        cx, cy = int(x) // NAV + dx, int(y) // NAV + dy
                        if not (2 <= cx < NW - 2 and 2 <= cy < NH - 2) or self.nav[cy, cx]:
                            continue
                        px, py = cx * NAV + NAV / 2, cy * NAV + NAV / 2
                        if self.blocked_circle(px, py, 170) or self.blocked_circle(px, py, 90)                                 or self.shallow_at(px, py):
                            continue                # the whole ring should be clear of rock and buildings
                        if r < 6 and any(abs(tx - px) < 190 and abs(ty - py) < 190 for tx, ty in trees):
                            continue                # ...and of trees, unless there is no such spot nearby
                        if self.river is not None and self.rdist[int(py) // CELL, int(px) // CELL] < self.river_hw + 190:
                            continue                # keep the whole ring on dry land
                        return px, py
            return x, y
        W, H = self.w, self.h
        self.zone_points = [self.flag_homes[0], open_spot(W * 0.34, H * 0.2), open_spot(W * 0.5, H * 0.5),
                            open_spot(W * 0.66, H * 0.8), self.flag_homes[1]]
        # Free-for-All: places to appear all over the map, not just at the two team ends
        self.ffa_spawns = []
        for y in range(400, H - 300, 520):
            for x in range(400, W - 300, 520):
                if not self.nav[y // NAV, x // NAV] and not self.blocked_circle(x, y, 80) \
                        and not self.shallow_at(x, y):
                    self.ffa_spawns.append((x, y))
        self.spawns = []
        for x0, y0, x1, y1 in self.zones:
            pts = []
            for y in range(y0, y1, 170):
                for x in range(x0, x1, 170):
                    if not self.nav[y // NAV, x // NAV] and not self.blocked_circle(x, y, 70):
                        pts.append((x, y))
            self.spawns.append(pts or [((x0 + x1) // 2, (y0 + y1) // 2)])

    def remove_tree(self, index):
        """A felled tree no longer blocks tanks or shots."""
        o = self.objects[index]
        cx, cy = int(o["x"]) // CELL, int(o["y"]) // CELL
        self.solid[cy, cx] = False
        self.block[cy * GW + cx] = 1 if self.water[cy, cx] == 1 else 0
        self.shot_block[cy * GW + cx] = 0
        self.nav_dirty = True

    def rebuild_nav(self):
        self._build_nav()
        self.nav_dirty = False

    # -- queries used by the simulation ------------------------------------------------
    def blocked_at(self, x, y):
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return True
        return self.block[int(y) // CELL * GW + int(x) // CELL] != 0

    def shot_blocked_at(self, x, y):
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return True
        return self.shot_block[int(y) // CELL * GW + int(x) // CELL] != 0

    def shallow_at(self, x, y):
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return False
        return self.shallow[int(y) // CELL * GW + int(x) // CELL] != 0

    def blocked_circle(self, x, y, r, _dirs=tuple((math.cos(i * math.pi / 6), math.sin(i * math.pi / 6))
                                                   for i in range(12))):
        if x < r or y < r or x > self.w - r or y > self.h - r:
            return True
        block = self.block
        if block[int(y) // CELL * GW + int(x) // CELL]:
            return True
        r2 = r * 0.55
        for c, s in _dirs:
            if block[int(y + s * r) // CELL * GW + int(x + c * r) // CELL]:
                return True
            if block[int(y + s * r2) // CELL * GW + int(x + c * r2) // CELL]:
                return True
        return False

    def line_of_fire(self, x0, y0, x1, y1, step=18.0):
        """True if nothing solid lies between two points."""
        dx, dy = x1 - x0, y1 - y0
        d = math.hypot(dx, dy)
        n = int(d / step)
        if n <= 0:
            return True
        sx, sy = dx / n, dy / n
        blk = self.shot_block
        x, y = x0, y0
        for _ in range(n):
            x += sx
            y += sy
            if blk[int(y) // CELL * GW + int(x) // CELL]:
                return False
        return True
