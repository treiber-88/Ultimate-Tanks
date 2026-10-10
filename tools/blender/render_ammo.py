"""Render ammunition: in-flight top-down sprites (pointing +X) and 3/4 shop icons for all ten weapons."""
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

OUT = os.path.join(L.ASSETS, "ammo")
SPRITE_PPM = 40.0     # flight sprites are rendered at 2x and scaled by the game
ONLY = globals().get("ONLY")


def mats():
    M = {}
    M["brass"] = L.mat_surface("UT_A_Brass", [(0.3, (0.60, 0.42, 0.13)), (0.7, (0.85, 0.65, 0.25))], noise_scale=9.0,
                               rough=0.25, metallic=1.0, bump=0.02)
    M["copper"] = L.mat_surface("UT_A_Copper", [(0.3, (0.55, 0.22, 0.10)), (0.7, (0.80, 0.38, 0.20))], rough=0.3,
                                metallic=1.0, bump=0.02)
    M["olive"] = L.mat_surface("UT_A_Olive", [(0.3, (0.13, 0.17, 0.06)), (0.7, (0.22, 0.27, 0.10))], rough=0.5,
                               bump=0.05)
    M["steel"] = L.mat_surface("UT_A_Steel", [(0.3, (0.25, 0.26, 0.28)), (0.7, (0.45, 0.46, 0.5))], rough=0.3,
                               metallic=1.0, bump=0.03)
    M["dark"] = L.mat_surface("UT_A_Dark", [(0.3, (0.03, 0.03, 0.035)), (0.7, (0.08, 0.08, 0.09))], rough=0.35,
                              metallic=0.9, bump=0.03)
    M["red"] = L.mat_surface("UT_A_Red", [(0.3, (0.45, 0.04, 0.02)), (0.7, (0.7, 0.09, 0.04))], rough=0.4, bump=0.03)
    M["white"] = L.mat_surface("UT_A_White", [(0.3, (0.62, 0.62, 0.6)), (0.7, (0.82, 0.82, 0.8))], rough=0.35,
                               bump=0.02)
    M["yellow"] = L.mat_surface("UT_A_Yellow", [(0.3, (0.75, 0.55, 0.02)), (0.7, (0.9, 0.7, 0.05))], rough=0.4,
                                bump=0.0)
    M["black"] = L.mat_surface("UT_A_Black", [(0.3, 0.01), (0.7, 0.03)], rough=0.5, bump=0.0)
    M["blue"] = L.mat_surface("UT_A_Blue", [(0.3, (0.03, 0.12, 0.5)), (0.7, (0.06, 0.2, 0.7))], rough=0.4, bump=0.0)
    M["g_yellow"] = L.mat_glow("UT_A_GY", (1.0, 0.85, 0.25), 2.9)
    M["g_orange"] = L.mat_glow("UT_A_GO", (1.0, 0.35, 0.05), 2.9)
    M["g_red"] = L.mat_glow("UT_A_GR", (1.0, 0.1, 0.05), 3.2)
    M["g_violet"] = L.mat_glow("UT_A_GV", (0.65, 0.15, 1.0), 2.9)
    M["g_green"] = L.mat_glow("UT_A_GG", (0.4, 1.0, 0.15), 2.6)
    return M


def round_(col, M, length, r, body, case=None, case_frac=0.0, bands=(), tip=None, nose=0.42, fins=None,
           tracer=None, spikes=False):
    """A projectile along +X centred on the origin. bands: [(pos 0..1 along the body, width, material)]."""
    x0 = -length / 2
    case_len = length * case_frac
    body_len = length - case_len
    nose_len = body_len * nose
    cyl_len = body_len - nose_len
    if case:
        L.cyl(col, "case", r * 1.04, case_len, (x0 + case_len / 2, 0, 0), M[case], axis="X", bevel=0.004)
        L.cyl(col, "rim", r * 1.15, r * 0.25, (x0 + r * 0.12, 0, 0), M[case], axis="X", bevel=0.004)
    bx = x0 + case_len
    L.cyl(col, "body", r, cyl_len, (bx + cyl_len / 2, 0, 0), M[body], axis="X", bevel=0.0)
    # ogive nose: one lathed surface, the last third optionally in the tip material
    import bmesh
    bm = bmesh.new()
    steps, segs = 14, 28
    rings = []
    for i in range(steps + 1):
        f = i / steps
        rr = max(r * math.cos(f * math.pi / 2) ** 0.75, 0.0005)
        x = bx + cyl_len + f * nose_len
        rings.append([bm.verts.new((x, rr * math.cos(2 * math.pi * k / segs), rr * math.sin(2 * math.pi * k / segs)))
                      for k in range(segs)])
    for i in range(steps):
        for k in range(segs):
            fc = bm.faces.new((rings[i][k], rings[i][(k + 1) % segs], rings[i + 1][(k + 1) % segs], rings[i + 1][k]))
            fc.material_index = 1 if (tip and i >= steps * 0.62) else 0
    bm.faces.new(rings[-1])
    nose_ob = L._obj("nose", bm)
    nose_ob.data.materials.append(M[body])
    nose_ob.data.materials.append(M[tip] if tip else M[body])
    L._finish(nose_ob, col, None, 0.0)
    for i, (pos, w, mat) in enumerate(bands):
        L.cyl(col, f"band{i}", r * 1.035, w, (bx + cyl_len * pos, 0, 0), M[mat], axis="X", bevel=0.002)
    if tracer:
        L.cyl(col, "tracer", r * 0.8, r * 0.5, (x0 - r * 0.2, 0, 0), M[tracer], axis="X", bevel=0.0)
    if fins:
        for k in range(4):
            a = k * math.pi / 2 + math.pi / 4
            L.box(col, f"fin{k}", (length * 0.24, 0.012, r * 1.5), (x0 + length * 0.12, math.cos(a) * r * 1.2,
                                                                     math.sin(a) * r * 1.2), M[fins], bevel=0.003,
                  rot=(a - math.pi / 2, 0, 0))
    if spikes:
        for k in range(6):
            a = k * math.pi / 3
            L.cyl(col, f"spike{k}", r * 0.16, r * 0.8, (bx + cyl_len * 0.55, math.cos(a) * r * 1.2,
                                                        math.sin(a) * r * 1.2), M["dark"], axis="Y", bevel=0.0,
                  radius2=0.0, rot=(a - math.pi / 2, 0, 0), verts=8)


def canister_can(col, M):
    L.cyl(col, "can", 0.2, 0.62, (0, 0, 0), M["olive"], axis="X", bevel=0.01)
    L.cyl(col, "case", 0.21, 0.3, (-0.42, 0, 0), M["brass"], axis="X", bevel=0.006)
    L.cyl(col, "lid", 0.205, 0.03, (0.31, 0, 0), M["steel"], axis="X", bevel=0.004)
    L.cyl(col, "band", 0.207, 0.06, (0.05, 0, 0), M["yellow"], axis="X", bevel=0.002)
    for i, (x, y, z) in enumerate(((0.5, 0.05, 0.02), (0.62, -0.12, -0.05), (0.7, 0.14, 0.08), (0.84, -0.02, 0.12),
                                   (0.95, 0.1, -0.1))):
        L.sphere(col, f"ball{i}", 0.075, (x, y, z), M["steel"], segs=16)


# key: (builder, flight-sprite builder or None -> same model)
DEFS = {
    "basic_shell": lambda c, M: round_(c, M, 1.0, 0.11, "olive", "brass", 0.42, [(0.25, 0.05, "yellow")]),
    "tracer": lambda c, M: round_(c, M, 0.62, 0.05, "copper", "brass", 0.5, tip="g_yellow", tracer="g_yellow"),
    "gatling": lambda c, M: round_(c, M, 0.55, 0.055, "copper", "brass", 0.55),
    "heavy_shell": lambda c, M: round_(c, M, 1.3, 0.15, "dark", "brass", 0.4, [(0.2, 0.06, "yellow"),
                                                                             (0.7, 0.04, "white")]),
    "combust_shell": lambda c, M: round_(c, M, 1.25, 0.145, "red", "brass", 0.38, [(0.3, 0.07, "g_orange"),
                                                                                  (0.72, 0.05, "g_orange")],
                                         tip="g_orange"),
    "heavy_tracer": lambda c, M: round_(c, M, 0.8, 0.07, "steel", "brass", 0.5, [(0.5, 0.03, "red")], tip="g_red",
                                        tracer="g_red"),
    "heavy_gatling": lambda c, M: round_(c, M, 0.75, 0.075, "steel", "brass", 0.55, [(0.4, 0.04, "blue")],
                                         tip="dark"),
    "canister": lambda c, M: canister_can(c, M),
    "death_shell": lambda c, M: round_(c, M, 1.4, 0.16, "black", "dark", 0.36, [(0.2, 0.06, "g_violet"),
                                                                              (0.5, 0.04, "g_violet"),
                                                                              (0.78, 0.04, "g_violet")],
                                       tip="g_violet", spikes=True),
    "nuke_shell": lambda c, M: round_(c, M, 1.7, 0.24, "white", None, 0.0, [(0.3, 0.1, "yellow"), (0.36, 0.03, "black"),
                                                                           (0.24, 0.03, "black"),
                                                                           (0.85, 0.06, "g_green")],
                                      tip="red", nose=0.34, fins="dark"),
}
# what actually flies (no cartridge case); canister flies as steel balls
FLIGHT = {
    "basic_shell": lambda c, M: round_(c, M, 0.62, 0.11, "olive", None, 0, [(0.3, 0.05, "yellow")], nose=0.55),
    "tracer": lambda c, M: round_(c, M, 0.36, 0.05, "copper", None, 0, tip="g_yellow", tracer="g_yellow", nose=0.6),
    "gatling": lambda c, M: round_(c, M, 0.3, 0.055, "copper", None, 0, nose=0.6),
    "heavy_shell": lambda c, M: round_(c, M, 0.82, 0.15, "dark", None, 0, [(0.25, 0.06, "yellow"),
                                                                          (0.75, 0.04, "white")], nose=0.52),
    "combust_shell": lambda c, M: round_(c, M, 0.8, 0.145, "red", None, 0, [(0.3, 0.07, "g_orange"),
                                                                           (0.75, 0.05, "g_orange")],
                                         tip="g_orange", nose=0.52),
    "heavy_tracer": lambda c, M: round_(c, M, 0.45, 0.07, "steel", None, 0, [(0.5, 0.03, "red")], tip="g_red",
                                        tracer="g_red", nose=0.6),
    "heavy_gatling": lambda c, M: round_(c, M, 0.4, 0.075, "steel", None, 0, [(0.4, 0.04, "blue")], tip="dark",
                                         nose=0.6),
    "canister": lambda c, M: L.sphere(c, "ball", 0.085, (0, 0, 0), M["steel"], segs=20),
    "death_shell": lambda c, M: round_(c, M, 0.95, 0.16, "black", None, 0, [(0.2, 0.06, "g_violet"),
                                                                           (0.5, 0.04, "g_violet"),
                                                                           (0.8, 0.04, "g_violet")], tip="g_violet",
                                       spikes=True, nose=0.5),
    "nuke_shell": DEFS["nuke_shell"],
}


def clear(col):
    for ob in list(col.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


def main():
    sc = L.reset_scene()
    L.setup_world(sc, strength=0.8)
    L.add_sun(sc, energy=3.0)
    fill = L.add_sun(sc, elevation=30, azimuth=-30, energy=1.2, angle=30, color=(0.8, 0.88, 1.0), name="Fill")
    fill.data.use_shadow = False
    M = mats()
    meta = {}
    col = L.new_collection("ammo")
    sc.collection.children.link(col)
    for key in DEFS:
        if ONLY and key not in ONLY:
            continue
        # flight sprite, top-down, pointing right
        clear(col)
        FLIGHT[key](col, M)
        grow = {"nuke_shell": 1.15, "canister": 1.6}.get(key, 1.7 if "shell" in key else 2.2)
        e = bpy.data.objects.new("UT_grow", None)
        col.objects.link(e)
        for ob in list(col.objects):
            if ob is not e:
                ob.parent = e
        e.scale = (grow, grow, grow)
        size_m = 2.4 if key == "nuke_shell" else 1.8
        px = int(size_m * SPRITE_PPM)
        cam = L.add_topdown_camera(sc, size_m, size_m / 2, px, px // 2)
        L.setup_render(sc, samples=64)
        L.render(sc, os.path.join(OUT, key + ".png"))
        bpy.data.objects.remove(cam, do_unlink=True)
        meta[key] = dict(w=px, h=px // 2, scale=L.PPM / SPRITE_PPM)
        # shop icon
        clear(col)
        DEFS[key](col, M)
        for ob in col.objects:
            pass
        ln = 1.9 if key == "nuke_shell" else (1.5 if key in ("death_shell", "heavy_shell", "combust_shell",
                                                           "canister") else (1.15 if key == "basic_shell" else 0.8))
        d = ln * 2.6
        cam = L.add_persp_camera(sc, (d * 0.55, -d * 0.62, d * 0.5), (0.02 * ln, 0, 0), lens=85, px=(256, 256))
        L.setup_render(sc, samples=64)
        L.render(sc, os.path.join(OUT, key + "_icon.png"))
        bpy.data.objects.remove(cam, do_unlink=True)
    clear(col)
    with open(os.path.join(OUT, "ammo.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return list(meta)


result = {"done": main()}
