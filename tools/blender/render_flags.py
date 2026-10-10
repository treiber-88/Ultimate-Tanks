"""Render Capture-the-Flag art: a flag and a base pad for each team, top-down with baked shadows.

Runs through tools/blrun.py or headless:  blender -b --factory-startup --python tools/blender/render_flags.py
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
import bmesh
import bpy
from mathutils import Vector

OUT = os.path.join(L.ASSETS, "ctf")
TEAMS = (("blue", (0.05, 0.22, 0.85)), ("red", (0.85, 0.06, 0.04)))
META = {}


def cloth(col, name, mat, width, height, origin, lean):
    """A rippling banner. It leans back so its face is visible from straight above."""
    bm = bmesh.new()
    nx, ny = 26, 12
    rows = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            u, v = i / nx, j / ny
            wave = math.sin(u * 9.0 + v * 2.0) * 0.16 * u + math.sin(u * 4.0 - v * 3.0) * 0.08 * u
            # u runs away from the pole (+X); v runs down the hoist, laid back along -Y by `lean`
            x = u * width
            y = -v * height * math.sin(lean) + wave * 0.6
            z = -v * height * math.cos(lean) + wave
            row.append(bm.verts.new((x, y, z)))
        rows.append(row)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    ob = L._obj(name, bm)
    ob.location = origin
    L._finish(ob, col, mat, 0.0)
    sol = ob.modifiers.new("Solid", "SOLIDIFY")
    sol.thickness = 0.03
    return ob


def flag(col, M, paint, dark):
    L.cyl(col, "foot", 0.42, 0.16, (0, 0, 0.08), M["metal"], bevel=0.03, verts=24)
    L.cyl(col, "foot2", 0.24, 0.3, (0, 0, 0.2), M["metal"], bevel=0.03, verts=20)
    # the pole leans toward the top of the picture so the banner reads clearly from above
    tilt = math.radians(32)
    length = 5.2
    top = Vector((0, math.sin(tilt) * length, math.cos(tilt) * length))
    L.cyl(col, "pole", 0.055, length, tuple(top / 2), M["steel"], bevel=0.0, verts=12, rot=(-tilt, 0, 0))
    L.sphere(col, "finial", 0.14, tuple(top), M["brass"], segs=16)
    cloth(col, "cloth", paint, 3.3, 2.0, tuple(top * 0.97 + Vector((0.05, 0, 0))), math.radians(62))
    # a darker band along the fly and a white disc make it read as a flag rather than a coloured sheet
    stripe = cloth(col, "stripe", dark, 3.32, 0.42, tuple(top * 0.97 + Vector((0.05, -0.62, -0.31))), math.radians(62))
    stripe.location.z += 0.02


def base_pad(col, M, paint, dark):
    stone = L.mat_surface("UT_CTF_Stone", [(0.3, (0.16, 0.16, 0.15)), (0.7, (0.30, 0.30, 0.28))], noise_scale=3.0,
                          rough=0.85, bump=0.6)
    L.cyl(col, "pad", 2.6, 0.12, (0, 0, 0.06), stone, bevel=0.04, verts=64)
    L.cyl(col, "ring", 2.35, 0.05, (0, 0, 0.13), paint, bevel=0.01, verts=64)
    L.cyl(col, "inner", 2.0, 0.05, (0, 0, 0.14), stone, bevel=0.01, verts=64)
    L.cyl(col, "centre", 0.95, 0.05, (0, 0, 0.16), dark, bevel=0.01, verts=48)
    for k in range(8):                        # chevrons pointing at the centre
        a = k * math.pi / 4
        L.box(col, f"mark{k}", (0.7, 0.2, 0.04), (math.cos(a) * 1.5, math.sin(a) * 1.5, 0.165), paint, bevel=0.01,
              rot=(0, 0, a))


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


def shoot(sc, name, col, catcher, shadow=True):
    sc.collection.children.link(col)
    lo, hi = bounds(sc, col)
    pad = 0.3
    sh = (hi.z * 0.8 + 0.3) if shadow else 0.0
    x0, x1 = lo.x - pad, hi.x + pad + sh
    y0, y1 = lo.y - pad - sh, hi.y + pad
    px_w = int(math.ceil((x1 - x0) * L.PPM / 2) * 2)
    px_h = int(math.ceil((y1 - y0) * L.PPM / 2) * 2)
    w_m, h_m = px_w / L.PPM, px_h / L.PPM
    cx, cy = x0 + w_m / 2, y1 - h_m / 2
    cam = L.add_topdown_camera(sc, w_m, h_m, px_w, px_h, center=(cx, cy), z=80)
    plane = L.add_catcher(sc, max(w_m, h_m) * 3, catcher, center=(cx, cy))
    L.setup_render(sc, samples=64)
    L.render(sc, os.path.join(OUT, name + ".png"))
    META[name] = dict(w=px_w, h=px_h, ax=round(-x0 * L.PPM, 1), ay=round(y1 * L.PPM, 1))
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.objects.remove(plane, do_unlink=True)
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
    catcher = L.mat_shadow_catcher()
    L.calibrate_catcher(sc, catcher, os.path.join(OUT, "_probe.png"))
    for i, (name, c) in enumerate(TEAMS):
        paint = L.mat_surface(f"UT_CTF_{name}", [(0.3, tuple(v * 0.75 for v in c)), (0.7, c)], noise_scale=3.0,
                              rough=0.6, bump=0.25, bump_scale=30.0)
        dark = L.mat_surface(f"UT_CTF_{name}_d", [(0.3, (0.75, 0.75, 0.72)), (0.7, (0.95, 0.95, 0.92))],
                             noise_scale=3.0, rough=0.6, bump=0.2, bump_scale=30.0)
        col = L.new_collection(f"flag_{i}")
        flag(col, M, paint, dark)
        shoot(sc, f"flag_{i}", col, catcher)
        col = L.new_collection(f"base_{i}")
        base_pad(col, M, paint, dark)
        shoot(sc, f"base_{i}", col, catcher, shadow=False)
    with open(os.path.join(OUT, "ctf.json"), "w") as f:
        json.dump(META, f, indent=1)
    try:
        os.remove(os.path.join(OUT, "_probe.png"))
    except OSError:
        pass
    return META


result = {"sprites": main()}
