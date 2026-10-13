"""Render art for the extra game modes: team headquarters (intact + destroyed) and the convoy truck.

Runs through tools/blrun.py or headless:  blender -b --factory-startup --python tools/blender/render_modes.py
"""
import importlib
import json
import math
import os
import sys

# tools/blrun.py passes UT_HERE; when run as a file (blender -b --python ...) __file__ is used instead
HERE = globals().get("UT_HERE") or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import utlib as L
importlib.reload(L)
import bpy
from mathutils import Vector

OUT = os.path.join(L.ASSETS, "modes")
TEAMS = (("0", (0.05, 0.22, 0.85)), ("1", (0.85, 0.06, 0.04)))
FRAMES, COLS = 32, 8
META = {}


def octagon(r, skew=0.0):
    return [(math.cos(a) * r, math.sin(a) * r) for a in [math.pi / 8 + skew + k * math.pi / 4 for k in range(8)]]


def headquarters(col, M, paint, concrete, dead=False):
    """A squat octagonal command bunker with corner emplacements, radar and a painted roof."""
    h = 1.6 if dead else 3.2
    L.prism_xy(col, "skirt", octagon(4.3), 0.0, 0.7, (0, 0, 0), concrete, top_scale=0.93, bevel=0.06)
    L.prism_xy(col, "walls", octagon(3.7), 0.6, h, (0, 0, 0), concrete, top_scale=0.84, bevel=0.08)
    if dead:
        for i, (x, y, s, rz) in enumerate(((1.2, 0.8, 1.6, 0.4), (-1.5, 0.3, 1.9, 1.3), (0.2, -1.6, 1.4, 2.2),
                                           (-0.6, 1.9, 1.2, 0.9), (2.6, -1.8, 1.1, 2.9), (-2.9, -2.2, 1.3, 0.2),
                                           (3.4, 2.1, 0.9, 1.7), (-3.3, 2.6, 1.0, 2.5))):
            L.box(col, f"slab{i}", (s, s * 0.7, 0.35), (x, y, h * (0.9 if i < 4 else 0.25)), concrete, bevel=0.05,
                  rot=(0.25 * math.sin(i * 2.1), 0.3 * math.cos(i * 1.7), rz))
        L.cyl(col, "crater", 1.5, 0.3, (0.2, -0.1, h - 0.05), M["black"], bevel=0.05, verts=20)
        return
    L.prism_xy(col, "roof", octagon(2.9), h - 0.05, h + 0.3, (0, 0, 0), paint, top_scale=0.9, bevel=0.05)
    L.cyl(col, "hatch", 0.75, 0.2, (0, 0, h + 0.36), M["metal"], bevel=0.04, verts=32)
    L.cyl(col, "hatch_lid", 0.55, 0.1, (0, 0, h + 0.48), concrete, bevel=0.03, verts=32)
    for k in range(4):                                   # a white cross so it reads as a command post
        a = k * math.pi / 2
        L.box(col, f"cross{k}", (1.25, 0.42, 0.06), (math.cos(a) * 1.55, math.sin(a) * 1.55, h + 0.31), M["stripe"],
              bevel=0.01, rot=(0, 0, a))
    for k in range(4):                                   # corner emplacements
        a = k * math.pi / 2 + math.pi / 4
        x, y = math.cos(a) * 3.55, math.sin(a) * 3.55
        L.cyl(col, f"tower{k}", 0.85, 1.9, (x, y, 0.95), concrete, bevel=0.06, verts=20)
        L.cyl(col, f"cap{k}", 0.7, 0.16, (x, y, 1.96), paint, bevel=0.03, verts=20)
        L.cyl(col, f"gun{k}", 0.09, 1.1, (x + math.cos(a) * 0.7, y + math.sin(a) * 0.7, 2.12), M["steel"], bevel=0.0,
              verts=10, rot=(0, math.radians(90), a))
    # radar dish and mast
    L.cyl(col, "mast", 0.07, 2.4, (1.7, -1.5, h + 1.4), M["metal"], bevel=0.0, verts=8)
    L.cyl(col, "dish", 0.75, 0.12, (-1.6, 1.5, h + 0.75), M["steel"], bevel=0.03, verts=28, radius2=0.25,
          rot=(math.radians(35), math.radians(25), 0))
    L.cyl(col, "dish_post", 0.09, 0.5, (-1.6, 1.5, h + 0.45), M["metal"], bevel=0.0, verts=8)
    for k in range(8):                                   # entrance blast walls / sandbag arcs
        a = k * math.pi / 4
        L.box(col, f"bag{k}", (1.5, 0.55, 0.5), (math.cos(a) * 4.75, math.sin(a) * 4.75, 0.25), M["canvas"],
              bevel=0.12, rot=(0, 0, a + math.pi / 2), segments=3)


def truck(col, M, paint):
    """Six-wheel supply truck pointing +X: cab, bonnet and a canvas-covered load bed in the team colour."""
    L.box(col, "chassis", (6.4, 2.0, 0.35), (0, 0, 0.75), M["metal"], bevel=0.04)
    L.box(col, "bonnet", (1.3, 1.9, 0.8), (2.55, 0, 1.35), M["paint2"], bevel=0.12, segments=3)
    L.box(col, "grille", (0.08, 1.5, 0.55), (3.22, 0, 1.3), M["black"], bevel=0.0)
    L.box(col, "bumper", (0.25, 2.5, 0.3), (3.3, 0, 0.8), M["metal"], bevel=0.05)
    L.box(col, "cab", (1.5, 2.3, 1.5), (1.25, 0, 1.75), M["paint2"], bevel=0.1, segments=3)
    L.box(col, "cab_roof", (1.35, 2.1, 0.08), (1.22, 0, 2.52), M["paint"], bevel=0.03)
    L.box(col, "screen", (0.06, 1.9, 0.6), (2.02, 0, 2.0), M["glass"], bevel=0.0, rot=(0, math.radians(-14), 0))
    for sy in (1, -1):
        L.cyl(col, f"lamp{sy}", 0.14, 0.08, (3.24, sy * 0.72, 1.4), M["lamp"], axis="X", bevel=0.0, verts=14)
        L.box(col, f"mirror{sy}", (0.08, 0.3, 0.35), (1.9, sy * 1.35, 2.1), M["metal"], bevel=0.02)
        for i, wx in enumerate((2.45, -1.2, -2.5)):
            L.cyl(col, f"wheel{sy}{i}", 0.58, 0.5, (wx, sy * 1.1, 0.58), M["rubber"], axis="Y", bevel=0.08, verts=22)
            L.cyl(col, f"hubcap{sy}{i}", 0.22, 0.54, (wx, sy * 1.1, 0.58), M["metal"], axis="Y", bevel=0.02, verts=12)
        L.box(col, f"arch{sy}", (1.5, 0.62, 0.1), (2.45, sy * 1.1, 1.22), M["paint2"], bevel=0.04)
    # load bed with a ribbed canvas tilt
    L.box(col, "bed", (4.1, 2.5, 0.5), (-1.55, 0, 1.2), M["wood"], bevel=0.03)
    L.profile_xz(col, "tilt", [(-2.0, 0.0), (2.0, 0.0), (2.0, 1.05), (1.4, 1.45), (-1.4, 1.45), (-2.0, 1.05)], 2.4,
                 (-1.55, 0, 1.45), paint, bevel=0.1).rotation_euler = (0, 0, 0)
    for i in range(5):
        L.box(col, f"rib{i}", (0.09, 2.46, 1.5), (-3.35 + i * 0.9, 0, 2.2), M["canvas"], bevel=0.03)
    L.box(col, "stripe", (0.5, 2.42, 0.02), (-1.55, 0, 2.905), M["stripe"], bevel=0.0)
    L.cyl(col, "spare", 0.5, 0.3, (0.3, 0, 2.0), M["rubber"], axis="X", bevel=0.06, verts=20)


def bounds(sc, col):
    dg = sc.view_layers[0].depsgraph
    dg.update()
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for ob in col.all_objects:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        for v in me.vertices:
            p = ev.matrix_world @ v.co
            for k in range(3):
                lo[k] = min(lo[k], p[k])
                hi[k] = max(hi[k], p[k])
        ev.to_mesh_clear()
    return lo, hi


def shoot(sc, name, col, catcher):
    sc.collection.children.link(col)
    lo, hi = bounds(sc, col)
    pad, sh = 0.3, hi.z * 0.8 + 0.3
    x0, y1 = lo.x - pad, hi.y + pad
    px_w = int(math.ceil((hi.x + pad + sh - x0) * L.PPM / 2) * 2)
    px_h = int(math.ceil((y1 - (lo.y - pad - sh)) * L.PPM / 2) * 2)
    w_m, h_m = px_w / L.PPM, px_h / L.PPM
    cam = L.add_topdown_camera(sc, w_m, h_m, px_w, px_h, center=(x0 + w_m / 2, y1 - h_m / 2), z=80)
    plane = L.add_catcher(sc, max(w_m, h_m) * 3, catcher, center=(x0 + w_m / 2, y1 - h_m / 2))
    L.setup_render(sc, samples=64)
    L.render(sc, os.path.join(OUT, name + ".png"))
    META[name] = dict(w=px_w, h=px_h, ax=round(-x0 * L.PPM, 1), ay=round(y1 * L.PPM, 1))
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.objects.remove(plane, do_unlink=True)
    for ob in list(col.all_objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.collections.remove(col)


def sheet(sc, name, col, radius_m):
    """FRAMES headings in a grid; frame k faces game angle k*360/FRAMES (clockwise on screen)."""
    frame_px = int(math.ceil((radius_m * 2 + 0.5) * L.PPM / 2.0)) * 2
    cell = frame_px / L.PPM
    rows = FRAMES // COLS
    w_m, h_m = COLS * cell, rows * cell
    insts = []
    for k in range(FRAMES):
        x = (k % COLS + 0.5) * cell - w_m / 2
        y = h_m / 2 - (k // COLS + 0.5) * cell
        insts.append(L.instance(sc, col, (x, y, 0), -k * 2 * math.pi / FRAMES, f"i{k}"))
    cam = L.add_topdown_camera(sc, w_m, h_m, COLS * frame_px, rows * frame_px)
    L.setup_render(sc, samples=48)
    L.render(sc, os.path.join(OUT, name + ".png"))
    META[name] = dict(frame=frame_px, frames=FRAMES, cols=COLS)
    for o in insts + [cam]:
        bpy.data.objects.remove(o, do_unlink=True)
    for ob in list(col.all_objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.collections.remove(col)


def main():
    sc = L.reset_scene()
    L.setup_world(sc)
    L.add_sun(sc)
    fill = L.add_sun(sc, elevation=35, azimuth=-40, energy=0.6, angle=30, color=(0.75, 0.85, 1.0), name="Fill")
    fill.data.use_shadow = False
    M = L.tank_materials()
    concrete = L.mat_surface("UT_M_Concrete", [(0.25, (0.20, 0.20, 0.19)), (0.5, (0.33, 0.33, 0.31)),
                                               (0.8, (0.45, 0.45, 0.42))], noise_scale=1.4, rough=0.9, bump=0.7,
                             bump_scale=12.0, detail=9.0)
    burnt = L.mat_surface("UT_M_Burnt", [(0.25, (0.02, 0.018, 0.016)), (0.6, (0.07, 0.06, 0.05)),
                                         (0.85, (0.16, 0.13, 0.10))], noise_scale=2.0, rough=0.95, bump=1.0,
                          bump_scale=9.0)
    catcher = L.mat_shadow_catcher()
    L.calibrate_catcher(sc, catcher, os.path.join(OUT, "_probe.png"))
    for tag, c in TEAMS:
        paint = L.mat_surface("UT_M_Team" + tag, [(0.3, tuple(v * 0.7 for v in c)), (0.7, c)], noise_scale=2.5,
                              rough=0.55, bump=0.2, bump_scale=30.0)
        col = L.new_collection("hq_" + tag)
        headquarters(col, M, paint, concrete)
        shoot(sc, "hq_" + tag, col, catcher)
        T = dict(M)
        T["paint2"] = L.mat_surface("UT_M_Olive", [(0.3, (0.10, 0.13, 0.06)), (0.7, (0.19, 0.23, 0.11))],
                                    noise_scale=2.5, rough=0.6, bump=0.1, bump_scale=30.0)
        col = L.new_collection("truck_" + tag)
        truck(col, T, paint)
        sheet(sc, "truck_" + tag, col, 3.7)
    col = L.new_collection("hq_dead")
    headquarters(col, M, burnt, burnt, dead=True)
    shoot(sc, "hq_dead", col, catcher)
    with open(os.path.join(OUT, "modes.json"), "w") as f:
        json.dump(META, f, indent=1)
    try:
        os.remove(os.path.join(OUT, "_probe.png"))
    except OSError:
        pass
    return META


result = {"sprites": main()}
