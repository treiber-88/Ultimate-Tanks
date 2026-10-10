"""Loads the Blender-rendered art and prepares it for drawing (team tinting, shadows, additive variants)."""
import json
import os

import numpy as np
import pygame
from PIL import Image

from . import data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "assets")
TINT_GAIN = 1.14          # paint is rendered light grey; this brings tinted colours back up to full value


def _np(path, mode="RGBA"):
    return np.asarray(Image.open(path).convert(mode))


def to_surface(arr):
    """(h, w, 4) uint8 array -> per-pixel-alpha Surface."""
    h, w = arr.shape[:2]
    return pygame.image.frombuffer(np.ascontiguousarray(arr).tobytes(), (w, h), "RGBA").convert_alpha()


def tint(rgba, mask, color):
    """Multiply the player's colour into the painted areas (mask) of a grey render."""
    rgb = rgba[..., :3].astype(np.int32)
    col = np.array([int(c * TINT_GAIN) for c in color], np.int32)
    painted = np.minimum(rgb * col // 255, 255)
    m = mask.astype(np.int32)[..., None]
    out = rgba.copy()
    out[..., :3] = (rgb + (painted - rgb) * m // 255).astype(np.uint8)
    return out


def char(rgba):
    """Burnt-out version of a sprite for wrecks."""
    out = rgba.copy()
    g = rgba[..., :3].astype(np.float32).mean(axis=2, keepdims=True)
    out[..., :3] = np.clip(g * np.array([0.30, 0.26, 0.23], np.float32) + 6, 0, 255).astype(np.uint8)
    return out


def shadow_of(alpha, strength=0.5, soften=3):
    """Soft black silhouette from an alpha channel."""
    h, w = alpha.shape
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 3] = (alpha.astype(np.float32) * strength).astype(np.uint8)
    s = to_surface(arr)
    small = pygame.transform.smoothscale(s, (max(1, w // soften), max(1, h // soften)))
    return pygame.transform.smoothscale(small, (w, h))


def frames_of(sheet, frame, count, cols):
    return [sheet.subsurface(((i % cols) * frame, (i // cols) * frame, frame, frame)) for i in range(count)]


class TankSprites:
    __slots__ = ("hull", "turret", "hf", "tf")

    def __init__(self, hull, turret, hf, tf):
        self.hull, self.turret, self.hf, self.tf = hull, turret, hf, tf


class Assets:
    def __init__(self):
        with open(os.path.join(ART, "tanks", "tanks.json"), encoding="utf-8") as f:
            self.tank_meta = json.load(f)
        with open(os.path.join(ART, "scenery", "scenery.json"), encoding="utf-8") as f:
            self.scenery_meta = json.load(f)
        with open(os.path.join(ART, "ammo", "ammo.json"), encoding="utf-8") as f:
            self.ammo_meta = json.load(f)
        self._raw = {}
        self._tanks = {}
        self._shadows = {}
        self._previews = {}
        self._fonts = {}
        self._scaled = {}
        self.scenery = {}
        self.fx = {}
        self.fx_add = {}
        self.ammo = {}
        self.icons = {}
        self.terrain = {}
        self.ui = {}
        self._load_static()

    # -- static art -----------------------------------------------------------
    def _load_static(self):
        for name in self.scenery_meta:
            self.scenery[name] = pygame.image.load(os.path.join(ART, "scenery", name + ".png")).convert_alpha()
        for f in os.listdir(os.path.join(ART, "fx")):
            if f.endswith(".png"):
                arr = _np(os.path.join(ART, "fx", f))
                name = f[:-4]
                self.fx[name] = to_surface(arr)
                pre = arr.copy()            # premultiplied copy for additive blending
                pre[..., :3] = (arr[..., :3].astype(np.uint16) * arr[..., 3:4] // 255).astype(np.uint8)
                pre[..., 3] = 255
                self.fx_add[name] = to_surface(pre)
        for key, m in self.ammo_meta.items():
            s = pygame.image.load(os.path.join(ART, "ammo", key + ".png")).convert_alpha()
            w = data.WEAPONS[data.WEAPON_INDEX[key]]
            sc = m["scale"] * w["size"]
            self.ammo[key] = pygame.transform.smoothscale(s, (int(s.get_width() * sc), int(s.get_height() * sc)))
            self.icons[key] = pygame.image.load(os.path.join(ART, "ammo", key + "_icon.png")).convert_alpha()
        for f in os.listdir(os.path.join(ART, "terrain")):
            if f.endswith(".png"):
                self.terrain[f[:-4]] = _np(os.path.join(ART, "terrain", f), "RGB").astype(np.float32)
        for name in ("panel", "button", "slot", "coin", "logo"):
            self.ui[name] = pygame.image.load(os.path.join(ART, "ui", name + ".png")).convert_alpha()
        for name, shade in (("panel", (120, 124, 132)), ("button", (150, 156, 166)), ("slot", (126, 132, 142))):
            self.ui[name].fill(shade + (255,), special_flags=pygame.BLEND_RGBA_MULT)   # keep text readable
        self.ui["menu_bg"] = pygame.image.load(os.path.join(ART, "ui", "menu_bg.png")).convert()
        with open(os.path.join(ART, "ctf", "ctf.json"), encoding="utf-8") as f:
            self.ctf_meta = json.load(f)
        self.ctf = {n: pygame.image.load(os.path.join(ART, "ctf", n + ".png")).convert_alpha()
                    for n in self.ctf_meta}

    # -- tanks ---------------------------------------------------------------------
    def _tank_raw(self, key):
        if key not in self._raw:
            d = os.path.join(ART, "tanks")
            self._raw[key] = dict(
                hull=_np(os.path.join(d, key + "_hull.png")), hull_mask=_np(os.path.join(d, key + "_hull_mask.png"), "L"),
                turret=_np(os.path.join(d, key + "_turret.png")),
                turret_mask=_np(os.path.join(d, key + "_turret_mask.png"), "L"))
        return self._raw[key]

    def tank(self, key, color):
        """Sprite frames for a tank in a colour. color=None gives the burnt wreck."""
        ck = (key, tuple(color) if color else None)
        if ck not in self._tanks:
            raw, m = self._tank_raw(key), self.tank_meta[key]
            if color:
                hull = tint(raw["hull"], raw["hull_mask"], color)
                tur = tint(raw["turret"], raw["turret_mask"], color)
            else:
                hull, tur = char(raw["hull"]), char(raw["turret"])
            self._tanks[ck] = TankSprites(frames_of(to_surface(hull), m["hull_frame"], m["frames"], m["cols"]),
                                          frames_of(to_surface(tur), m["turret_frame"], m["frames"], m["cols"]),
                                          m["hull_frame"], m["turret_frame"])
        return self._tanks[ck]

    def tank_shadows(self, key):
        if key not in self._shadows:
            raw, m = self._tank_raw(key), self.tank_meta[key]
            self._shadows[key] = (
                frames_of(shadow_of(raw["hull"][..., 3], 0.5), m["hull_frame"], m["frames"], m["cols"]),
                frames_of(shadow_of(raw["turret"][..., 3], 0.38, 2), m["turret_frame"], m["frames"], m["cols"]))
        return self._shadows[key]

    def preview(self, key, color, size):
        ck = (key, tuple(color), size)
        if ck not in self._previews:
            d = os.path.join(ART, "tanks")
            if ("raw", key) not in self._previews:
                self._previews[("raw", key)] = (_np(os.path.join(d, key + "_preview.png")),
                                                _np(os.path.join(d, key + "_preview_mask.png"), "L"))
            rgba, mask = self._previews[("raw", key)]
            s = to_surface(tint(rgba, mask, color))
            self._previews[ck] = pygame.transform.smoothscale(s, (size, size))
            if len(self._previews) > 80:        # previews are re-tinted as the colour picker changes
                for k in [k for k in self._previews if k[0] != "raw" and k != ck][:30]:
                    del self._previews[k]
        return self._previews[ck]

    # -- misc ------------------------------------------------------------------------
    def font(self, px, bold=True):
        px = max(8, int(px))
        k = (px, bold)
        if k not in self._fonts:
            f = None
            for name in ("bahnschrift", "segoeui", "arial"):
                path = pygame.font.match_font(name, bold=bold)
                if path:
                    f = pygame.font.Font(path, px)
                    break
            self._fonts[k] = f or pygame.font.Font(None, px)
        return self._fonts[k]

    def scaled(self, surf, w, h, key):
        """Cached smooth-scaled copy of a surface."""
        k = (key, int(w), int(h))
        if k not in self._scaled:
            self._scaled[k] = pygame.transform.smoothscale(surf, (max(1, int(w)), max(1, int(h))))
        return self._scaled[k]
