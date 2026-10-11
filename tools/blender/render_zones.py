"""Render Zone Defense art: the ground marking of a control zone in neutral, blue and red.

Runs through tools/blrun.py or headless:  blender -b --factory-startup --python tools/blender/render_zones.py
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

OUT = os.path.join(L.ASSETS, "zones")
RADIUS = 8.5                 # metres; the game uses the same number (170 px)
COLORS = (("n", (0.55, 0.55, 0.52)), ("0", (0.05, 0.22, 0.85)), ("1", (0.85, 0.06, 0.04)))


def ring(col, name, r_out, r_in, z, mat, segs=96, a0=0.0, a1=math.tau):
    """Flat annulus (or an arc of one)."""
    bm = bmesh.new()
    n = max(2, int(segs * (a1 - a0) / math.tau))
    outer, inner = [], []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        outer.append(bm.verts.new((math.cos(a) * r_out, math.sin(a) * r_out, z)))
        inner.append(bm.verts.new((math.cos(a) * r_in, math.sin(a) * r_in, z)))
    for i in range(n):
        bm.faces.new((outer[i], outer[i + 1], inner[i + 1], inner[i]))
    ob = L._obj(name, bm)
    L._finish(ob, col, mat, 0.0)
    sol = ob.modifiers.new("Solid", "SOLIDIFY")
    sol.thickness = 0.06
    return ob


def marker(col, paint, stone):
    ring(col, "outer", RADIUS, RADIUS - 0.42, 0.06, paint)
    ring(col, "kerb", RADIUS - 0.42, RADIUS - 0.62, 0.05, stone)
    for k in range(16):                                   # dashed inner ring
        a = k * math.tau / 16
        ring(col, f"dash{k}", RADIUS - 1.3, RADIUS - 1.6, 0.05, paint, a0=a, a1=a + math.tau / 32)
    for k in range(4):                                    # corner brackets pointing inward
        a = k * math.pi / 2 + math.pi / 4
        for sgn in (-1, 1):
            L.box(col, f"arm{k}{sgn}", (1.5, 0.3, 0.08), (math.cos(a) * 4.2 + math.cos(a + sgn * 1.2) * 0.6,
                                                          math.sin(a) * 4.2 + math.sin(a + sgn * 1.2) * 0.6, 0.05),
                  paint, bevel=0.02, rot=(0, 0, a + sgn * 0.75))
    L.cyl(col, "hub", 1.15, 0.1, (0, 0, 0.05), stone, bevel=0.03, verts=48)
    L.cyl(col, "hub_c", 0.8, 0.1, (0, 0, 0.09), paint, bevel=0.02, verts=48)


def main():
    sc = L.reset_scene()
    L.setup_world(sc)
    L.add_sun(sc)
    stone = L.mat_surface("UT_Z_Stone", [(0.3, (0.14, 0.14, 0.13)), (0.7, (0.27, 0.27, 0.25))], noise_scale=2.0,
                          rough=0.85, bump=0.6)
    size = RADIUS * 2 + 0.6
    px = int(size * L.PPM / 2) * 2
    meta = {}
    for tag, c in COLORS:
        paint = L.mat_surface("UT_Z_" + tag, [(0.3, tuple(v * 0.7 for v in c)), (0.7, c)], noise_scale=2.5, rough=0.6,
                              bump=0.3, bump_scale=20.0)
        col = L.new_collection("zone_" + tag)
        marker(col, paint, stone)
        sc.collection.children.link(col)
        cam = L.add_topdown_camera(sc, px / L.PPM, px / L.PPM, px, px)
        L.setup_render(sc, samples=64)
        L.render(sc, os.path.join(OUT, "zone_%s.png" % tag))
        meta["zone_" + tag] = dict(w=px, h=px, ax=px / 2, ay=px / 2)
        bpy.data.objects.remove(cam, do_unlink=True)
        for ob in list(col.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.collections.remove(col)
    meta["radius_px"] = RADIUS * L.PPM
    with open(os.path.join(OUT, "zones.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta


result = {"sprites": main()}
