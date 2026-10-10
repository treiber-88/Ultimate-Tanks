"""Render tank sprite sheets (hull + turret, colour + team mask) and shop previews.

Run through tools/bl.py. Set ONLY = [...] below to limit which tanks are rendered.
"""
import importlib
import json
import math
import os
import sys

HERE = r"C:\Users\mk-ki\Desktop\Ultimate Tanks\tools\blender"
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import utlib as L
import tanks as T
importlib.reload(L)
importlib.reload(T)

ONLY = globals().get("ONLY") or T.ORDER
PREVIEW_ONLY = globals().get("PREVIEW_ONLY", False)
FRAMES = 32
COLS = 8
OUT = os.path.join(L.ASSETS, "tanks")


def sheet(sc, col, radius_m, path_rgb, path_mask, others):
    """Render `col` at FRAMES headings into a grid. Frame k faces game angle k*360/FRAMES (clockwise on screen)."""
    frame_px = int(math.ceil((radius_m * 2 + 0.5) * L.PPM / 2.0)) * 2
    cell = frame_px / L.PPM
    rows = FRAMES // COLS
    w_m, h_m = COLS * cell, rows * cell
    insts = []
    for k in range(FRAMES):
        c, r = k % COLS, k // COLS
        x = (c + 0.5) * cell - w_m / 2
        y = h_m / 2 - (r + 0.5) * cell
        insts.append(L.instance(sc, col, (x, y, 0), -k * 2 * math.pi / FRAMES, f"i{k}"))
    cam = L.add_topdown_camera(sc, w_m, h_m, COLS * frame_px, rows * frame_px)
    L.setup_render(sc, samples=48)
    L.render(sc, path_rgb)
    with L.MaskMaterials([col]):
        sc.eevee.taa_render_samples = 16
        L.render(sc, path_mask)
    import bpy
    for o in insts + [cam]:
        bpy.data.objects.remove(o, do_unlink=True)
    return frame_px


def preview(sc, hull, tur, meta, path_rgb, path_mask, size=640):
    import bpy
    a = L.instance(sc, hull, (0, 0, 0), 0, "ph")
    b = L.instance(sc, tur, (meta["turret_x"], 0, 0), math.radians(-14), "pt")
    reach = max(m[0] for m in meta["muzzles"])
    span = max(meta["length"], reach + meta["length"] / 2)
    d = span * 2.25
    cx = (reach + meta["turret_x"] - meta["length"] / 2) / 2 * 0.55
    cam = L.add_persp_camera(sc, (cx + d * 0.62, -d * 0.6, d * 0.52), (cx, 0, 0.75), lens=70, px=(size, size))
    L.setup_render(sc, samples=64)
    L.render(sc, path_rgb)
    with L.MaskMaterials([hull, tur]):
        sc.eevee.taa_render_samples = 16
        L.render(sc, path_mask)
    for o in (a, b, cam):
        bpy.data.objects.remove(o, do_unlink=True)


def main():
    sc = L.reset_scene()
    L.setup_world(sc)
    L.add_sun(sc)
    L.add_sun(sc, elevation=35, azimuth=-40, energy=0.7, angle=30, color=(0.75, 0.85, 1.0), name="Fill")
    M = L.tank_materials()
    meta_path = os.path.join(OUT, "tanks.json")
    meta_all = {}
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta_all = json.load(f)
    for key in ONLY:
        hull, tur, meta = T.build_tank(L, key, M)
        L.exclude(sc, hull)
        L.exclude(sc, tur)
        if not PREVIEW_ONLY:
            meta["hull_frame"] = sheet(sc, hull, meta["hull_radius"], os.path.join(OUT, key + "_hull.png"),
                                       os.path.join(OUT, key + "_hull_mask.png"), tur)
            meta["turret_frame"] = sheet(sc, tur, meta["turret_radius"], os.path.join(OUT, key + "_turret.png"),
                                         os.path.join(OUT, key + "_turret_mask.png"), hull)
        elif key in meta_all:
            for fk in ("hull_frame", "turret_frame"):
                if fk in meta_all[key]:
                    meta[fk] = meta_all[key][fk]
        preview(sc, hull, tur, meta, os.path.join(OUT, key + "_preview.png"),
                os.path.join(OUT, key + "_preview_mask.png"))
        meta["frames"] = FRAMES
        meta["cols"] = COLS
        meta["ppm"] = L.PPM
        meta_all[key] = meta
    with open(meta_path, "w") as f:
        json.dump(meta_all, f, indent=1)
    return meta_all


result = {"tanks": main()}
