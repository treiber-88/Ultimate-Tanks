"""Render scenery sprites (trees, bushes, boulders, houses, mountains, bridge) top-down with baked shadows."""
import importlib
import json
import math
import os
import random
import sys

HERE = r"C:\Users\mk-ki\Desktop\Ultimate Tanks\tools\blender"
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import utlib as L
importlib.reload(L)
import bpy
from mathutils import Vector, noise

ONLY = globals().get("ONLY")
OUT = os.path.join(L.ASSETS, "scenery")
META = {}


def roof_mat(name, c1, c2):
    """Roof tiles: rows of tiles from wave textures, colour variation from noise."""
    m, nt = L._mat(name)
    vec = L._coords(nt)
    n1 = L._noise(nt, vec, 9.0, 6.0)
    ramp = L._ramp(nt, n1.outputs["Fac"], [(0.3, c1), (0.7, c2)])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 1.15
    wave.inputs["Distortion"].default_value = 0.6
    wave.inputs["Detail Scale"].default_value = 6.0
    nt.links.new(vec, wave.inputs["Vector"])
    wave2 = nt.nodes.new("ShaderNodeTexWave")
    wave2.wave_type = "BANDS"
    wave2.bands_direction = "X"
    wave2.inputs["Scale"].default_value = 1.9
    wave2.inputs["Distortion"].default_value = 1.5
    nt.links.new(vec, wave2.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(wave.outputs["Fac"], add.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 0.4
    nt.links.new(wave2.outputs["Fac"], mul.inputs[0])
    nt.links.new(mul.outputs[0], add.inputs[1])
    bump = L._bump(nt, add.outputs[0], 1.0, 0.12)
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(ramp.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.75
    nt.links.new(bump.outputs["Normal"], bs.inputs["Normal"])
    L._out(nt, bs.outputs["BSDF"])
    return m


def materials():
    M = {}
    leaf = dict(noise_scale=3.5, rough=0.75, bump=0.9, bump_scale=16.0, spec=0.25)
    M["leaf1"] = L.mat_surface("UT_Leaf1", [(0.25, (0.035, 0.11, 0.02)), (0.5, (0.07, 0.21, 0.035)),
                                            (0.8, (0.16, 0.33, 0.05))], **leaf)
    M["leaf2"] = L.mat_surface("UT_Leaf2", [(0.25, (0.05, 0.13, 0.02)), (0.5, (0.12, 0.25, 0.03)),
                                            (0.8, (0.26, 0.36, 0.05))], **leaf)
    M["leaf3"] = L.mat_surface("UT_Leaf3", [(0.25, (0.02, 0.085, 0.03)), (0.5, (0.035, 0.15, 0.05)),
                                            (0.8, (0.08, 0.24, 0.08))], noise_scale=5.0, rough=0.8, bump=0.9,
                               bump_scale=22.0, spec=0.2)
    M["autumn"] = L.mat_surface("UT_Autumn", [(0.25, (0.25, 0.07, 0.01)), (0.5, (0.45, 0.17, 0.02)),
                                              (0.8, (0.62, 0.36, 0.04))], **leaf)
    M["bark"] = L.mat_surface("UT_Bark", [(0.3, (0.06, 0.04, 0.025)), (0.7, (0.14, 0.09, 0.05))], noise_scale=12.0,
                              rough=0.9, bump=0.6)
    M["rock"] = L.mat_surface("UT_Rock", [(0.2, (0.13, 0.12, 0.11)), (0.5, (0.27, 0.26, 0.24)),
                                          (0.8, (0.42, 0.41, 0.38))], noise_scale=1.6, rough=0.85, bump=1.0,
                              bump_scale=7.0, detail=10.0, spec=0.3)
    M["moss"] = L.mat_surface("UT_Moss", [(0.3, (0.07, 0.12, 0.03)), (0.7, (0.14, 0.2, 0.05))], noise_scale=5.0,
                              rough=0.95, bump=0.6)
    M["roof_red"] = roof_mat("UT_RoofRed", (0.36, 0.09, 0.045), (0.55, 0.17, 0.08))
    M["roof_slate"] = roof_mat("UT_RoofSlate", (0.10, 0.12, 0.15), (0.20, 0.23, 0.27))
    M["roof_brown"] = roof_mat("UT_RoofBrown", (0.20, 0.12, 0.06), (0.36, 0.23, 0.12))
    M["thatch"] = L.mat_surface("UT_Thatch", [(0.3, (0.33, 0.25, 0.10)), (0.7, (0.58, 0.47, 0.22))], noise_scale=24.0,
                                rough=0.95, bump=0.8, bump_scale=70.0)
    M["wall"] = L.mat_surface("UT_Wall", [(0.3, (0.55, 0.50, 0.40)), (0.7, (0.75, 0.70, 0.58))], noise_scale=6.0,
                              rough=0.9, bump=0.3)
    M["brick"] = L.mat_surface("UT_Brick", [(0.3, (0.25, 0.10, 0.07)), (0.7, (0.40, 0.18, 0.12))], noise_scale=18.0,
                               rough=0.9, bump=0.5)
    M["wood"] = L.mat_surface("UT_SWood", [(0.3, (0.17, 0.10, 0.05)), (0.7, (0.34, 0.22, 0.11))], noise_scale=9.0,
                              rough=0.85, bump=0.5, bump_scale=40.0)
    M["wood_dark"] = L.mat_surface("UT_SWoodD", [(0.3, (0.07, 0.045, 0.025)), (0.7, (0.15, 0.10, 0.055))],
                                   noise_scale=9.0, rough=0.85, bump=0.5, bump_scale=40.0)
    M["metal"] = L.mat_surface("UT_SMetal", [(0.3, (0.12, 0.12, 0.13)), (0.7, (0.25, 0.25, 0.27))], rough=0.5,
                               metallic=0.8, bump=0.1)
    M["glass"] = L.mat_surface("UT_SGlass", [(0.3, (0.05, 0.12, 0.17)), (0.7, (0.10, 0.22, 0.3))], rough=0.08,
                               metallic=0.5, bump=0.0)
    M["soot"] = L.mat_surface("UT_Soot", [(0.3, 0.005), (0.7, 0.01)], rough=0.95, bump=0.0)
    M["hay"] = L.mat_surface("UT_Hay", [(0.3, (0.45, 0.33, 0.08)), (0.7, (0.72, 0.58, 0.2))], noise_scale=30.0,
                             rough=0.95, bump=0.9, bump_scale=80.0)
    M["flower_r"] = L.mat_surface("UT_FlowerR", [(0.3, (0.7, 0.05, 0.05)), (0.7, (0.9, 0.2, 0.1))], rough=0.6, bump=0)
    M["flower_y"] = L.mat_surface("UT_FlowerY", [(0.3, (0.85, 0.6, 0.05)), (0.7, (0.95, 0.85, 0.2))], rough=0.6,
                                  bump=0)
    M["flower_w"] = L.mat_surface("UT_FlowerW", [(0.3, (0.8, 0.8, 0.85)), (0.7, (0.95, 0.95, 0.95))], rough=0.6,
                                  bump=0)
    return M


# ---------------------------------------------------------------------------

def blob(col, name, r, loc, mat, squash=0.8, disp=0.5, scale=0.9):
    ob = L.ico(col, name, r, loc, mat, subdiv=4, scale=(1, 1, squash))
    L.displace(ob, disp * r, scale * r)
    L.displace(ob, 0.34, 0.22)
    return ob


def leafy_tree(col, M, rng, radius, mat, height=5.0):
    L.cyl(col, "trunk", radius * 0.09, height, (0, 0, height / 2), M["bark"], verts=10, bevel=0, radius2=radius * 0.05)
    blob(col, "c0", radius * 0.62, (0, 0, height), mat)
    for i in range(rng.randint(7, 10)):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0.35, 0.62) * radius
        r = rng.uniform(0.32, 0.5) * radius
        blob(col, f"c{i+1}", r, (math.cos(a) * d, math.sin(a) * d, height - rng.uniform(0.2, 1.2)), mat)
    return dict(solid_r=0.7, canopy=True)


def pine_tree(col, M, rng, radius, height=8.0):
    L.cyl(col, "trunk", radius * 0.1, height * 0.5, (0, 0, height * 0.25), M["bark"], verts=10, bevel=0)
    layers = 6
    for i in range(layers):
        f = i / (layers - 1)
        r = radius * (1.0 - 0.78 * f)
        z = height * (0.28 + 0.62 * f)
        nb = 9 if i < 3 else 7
        pts = []
        for k in range(nb * 2):
            a = math.pi * k / nb
            rr = r * (1.0 if k % 2 == 0 else 0.52) * rng.uniform(0.9, 1.08)
            pts.append((math.cos(a) * rr, math.sin(a) * rr))
        ob = L.prism_xy(col, f"p{i}", pts, z - height * 0.1, z + height * 0.16, (0, 0, 0), M["leaf3"],
                        top_scale=0.1, bevel=0.0)
        ob.rotation_euler = (rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), rng.uniform(0, 1))
        for p in ob.data.polygons:
            p.use_smooth = False
        L.displace(ob, 0.18, 0.3)
    return dict(solid_r=0.6, canopy=True)


def bush(col, M, rng, radius, mat, flowers=None):
    for i in range(rng.randint(3, 5)):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0.0, 0.5) * radius
        r = rng.uniform(0.4, 0.62) * radius
        blob(col, f"b{i}", r, (math.cos(a) * d, math.sin(a) * d, r * 0.45), mat, squash=0.7, disp=0.45, scale=0.6)
    if flowers:
        for i in range(26):
            a = rng.uniform(0, 2 * math.pi)
            d = rng.uniform(0, 0.85) * radius
            L.ico(col, f"f{i}", 0.07, (math.cos(a) * d, math.sin(a) * d, radius * 0.72), M[flowers], subdiv=1)
    return dict(solid_r=0.0)


def boulder(col, M, rng, radius, moss=False):
    ob = L.ico(col, "rock", radius, (0, 0, radius * 0.35), M["rock"], subdiv=3, smooth=False,
               scale=(rng.uniform(0.85, 1.2), rng.uniform(0.75, 1.0), rng.uniform(0.55, 0.75)))
    ob.rotation_euler = (0, 0, rng.uniform(0, 6.28))
    L.displace(ob, radius * 0.75, radius * 1.1, kind="VORONOI")
    L.displace(ob, radius * 0.25, radius * 0.35)
    for i in range(rng.randint(1, 3)):
        a = rng.uniform(0, 6.28)
        r2 = radius * rng.uniform(0.25, 0.42)
        o2 = L.ico(col, f"rock{i}", r2, (math.cos(a) * radius * 0.95, math.sin(a) * radius * 0.9, r2 * 0.3), M["rock"],
                   subdiv=2, scale=(1, 0.85, 0.65), smooth=False)
        L.displace(o2, r2 * 0.6, r2 * 1.0, kind="VORONOI")
    if moss:
        o3 = L.ico(col, "moss", radius * 0.55, (-radius * 0.15, radius * 0.1, radius * 0.5), M["moss"], subdiv=3,
                   scale=(1.1, 0.9, 0.5))
        L.displace(o3, radius * 0.3, radius * 0.5)
    return dict(solid_r=round(radius * 0.9, 2))


def house(col, M, rng, lx, ly, roof, wall="wall", wh=3.0, pitch=0.62, chimney=True, dormer=False, annex=None):
    """Gabled house, ridge along X."""
    L.box(col, "walls", (lx, ly, wh), (0, 0, wh / 2), M[wall], bevel=0.03)
    oh = 0.45
    run = ly / 2 + oh
    rise = run * pitch
    slope = math.hypot(run, rise)
    ang = math.atan2(rise, run)
    for sy in (1, -1):
        L.box(col, f"roof{sy}", (lx + oh * 2, slope, 0.18), (0, sy * run / 2, wh + rise / 2), M[roof], bevel=0.02,
              rot=(-sy * ang, 0, 0))
    L.box(col, "ridge", (lx + oh * 2 + 0.05, 0.36, 0.14), (0, 0, wh + rise + 0.05), M["metal"], bevel=0.04)
    for sx in (1, -1):
        g = L.profile_xz(col, f"gable{sx}", [(-ly / 2, 0), (ly / 2, 0), (0, rise - 0.1)], 0.2,
                         (sx * (lx / 2 - 0.1), 0, wh), M[wall], bevel=0.0)
        g.rotation_euler = (0, 0, math.radians(90))
    if chimney:
        cx, cy = lx * 0.25, -ly * 0.18
        L.box(col, "chim", (0.8, 0.8, rise + 1.1), (cx, cy, wh + (rise + 1.1) / 2), M["brick"], bevel=0.03)
        L.box(col, "chim_cap", (0.98, 0.98, 0.14), (cx, cy, wh + rise + 1.1), M["metal"], bevel=0.03)
        L.box(col, "chim_in", (0.5, 0.5, 0.05), (cx, cy, wh + rise + 1.16), M["soot"], bevel=0)
    if dormer:
        dx = -lx * 0.2
        L.box(col, "dormer", (1.5, 1.8, 1.1), (dx, ly * 0.28, wh + rise * 0.55), M[wall], bevel=0.03)
        L.box(col, "dormer_r", (1.8, 2.1, 0.14), (dx, ly * 0.3, wh + rise * 0.55 + 0.6), M[roof], bevel=0.03)
        L.box(col, "sky", (1.1, 0.9, 0.06), (lx * 0.22, ly * 0.2, wh + rise * 0.62 + 0.12), M["glass"], bevel=0.02,
              rot=(-ang, 0, 0))
    if annex:
        ax, ay = annex
        L.box(col, "annex", (ax, ay, wh * 0.8), (-lx / 2 + ax / 2, -ly / 2 - ay / 2 + 0.1, wh * 0.4), M[wall],
              bevel=0.03)
        L.box(col, "annex_roof", (ax + 0.5, ay + 0.5, 0.16), (-lx / 2 + ax / 2, -ly / 2 - ay / 2 - 0.05, wh * 0.86),
              M[roof], bevel=0.02, rot=(math.radians(14), 0, 0))
    return dict(solid="alpha")


def mountain(col, M, size, height, seed):
    """A massif of several sharp peaks joined by ridges, faceted like chiselled rock."""
    rng = random.Random(seed * 977)
    off = Vector((seed * 13.7, seed * 7.3, seed * 3.1))
    peaks = []
    for k in range(rng.randint(4, 6)):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0.0, 0.3) * size if k else 0.0
        peaks.append((math.cos(a) * d, math.sin(a) * d, rng.uniform(0.55, 1.0) if k else 1.0,
                      rng.uniform(0.24, 0.36) * size))

    def hf(x, y):
        p = Vector((x, y, 0)) * (3.0 / size) + off
        warp = noise.noise(p * 0.9) * size * 0.05
        best = 0.0
        for px, py, ph, pr in peaks:
            d = math.hypot(x - px + warp, y - py - warp) / pr
            if d < 1.0:
                best = max(best, ph * (1.0 - d) ** 0.8)
        if best <= 0.0:
            return -0.5
        ridge = noise.ridged_multi_fractal(p * 1.6, 1.0, 2.1, 5, 1.0, 2.0) / 2.6
        crag = noise.fractal(p * 6.0, 1.0, 2.0, 3)
        skirt = min(1.0, best * 7.0)
        return max(best * height * (0.5 + 0.9 * ridge) + skirt * crag * 0.9, 0.0)

    n = min(300, int(size * 6.0))
    return L.grid_mesh(col, "mtn", n, n, size, size, hf, mountain_mat(height), cut_below=0.02, smooth=False)


def mountain_mat(height):
    """Rock coloured by altitude: scree at the base, bare rock, snow on the peaks."""
    m, nt = L._mat("UT_Mountain%d" % int(height * 10))
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    vec = L._coords(nt)
    n1 = L._noise(nt, vec, 0.35, 10.0, 0.65)
    sub = nt.nodes.new("ShaderNodeMath")
    sub.operation = "MULTIPLY_ADD"
    sub.inputs[1].default_value = 0.3
    sub.inputs[2].default_value = -0.15
    nt.links.new(n1.outputs["Fac"], sub.inputs[0])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.inputs[1].default_value = 1.0 / height
    nt.links.new(sep.outputs["Z"], add.inputs[0])
    nt.links.new(sub.outputs[0], add.inputs[2])
    ramp = L._ramp(nt, add.outputs[0], [(0.0, (0.16, 0.17, 0.10)), (0.10, (0.20, 0.18, 0.14)),
                                         (0.34, (0.25, 0.235, 0.22)), (0.62, (0.36, 0.35, 0.34)),
                                         (0.74, (0.62, 0.64, 0.68)), (0.86, (0.82, 0.84, 0.88))])
    n2 = L._noise(nt, vec, 1.6, 10.0, 0.7)
    bump = L._bump(nt, n2.outputs["Fac"], 1.0, 0.25)
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(ramp.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.85
    nt.links.new(bump.outputs["Normal"], bs.inputs["Normal"])
    L._out(nt, bs.outputs["BSDF"])
    return m


def bridge(col, M, length, width):
    L.box(col, "deck", (length, width, 0.3), (0, 0, 0.45), M["wood_dark"], bevel=0.02)
    n = int(length / 0.55)
    for i in range(n):
        x = -length / 2 + (i + 0.5) * length / n
        L.box(col, f"plank{i}", (length / n - 0.06, width - 0.5, 0.08), (x, 0, 0.64), M["wood"], bevel=0.015,
              rot=(0, 0, math.radians(((i * 37) % 5 - 2) * 0.4)))
    posts = int(length / 3)
    for sy in (1, -1):
        L.box(col, f"beam{sy}", (length, 0.3, 0.3), (0, sy * (width / 2 - 0.15), 0.78), M["wood_dark"], bevel=0.03)
        L.box(col, f"rail{sy}", (length, 0.14, 0.14), (0, sy * (width / 2 - 0.15), 1.75), M["wood"], bevel=0.02)
        for i in range(posts + 1):
            x = -length / 2 + 0.3 + i * (length - 0.6) / posts
            L.box(col, f"post{sy}{i}", (0.26, 0.26, 1.3), (x, sy * (width / 2 - 0.15), 1.25), M["wood_dark"],
                  bevel=0.03)
    return dict(solid_r=0.0, length=length, width=width)


def hay(col, M, rng):
    L.cyl(col, "bale", 0.85, 1.5, (0, 0, 0.85), M["hay"], axis="Y", verts=28, bevel=0.06)
    for dy in (-0.4, 0.4):
        L.cyl(col, f"twine{dy}", 0.87, 0.04, (0, dy, 0.85), M["wood_dark"], axis="Y", verts=28, bevel=0)
    return dict(solid_r=1.0)


def crates(col, M, rng):
    for i, (x, y, s, r) in enumerate(((0, 0, 1.3, 0.2), (1.25, 0.35, 1.0, -0.3), (0.3, -1.2, 0.9, 0.6))):
        L.box(col, f"crate{i}", (s, s, s), (x, y, s / 2), M["wood"], bevel=0.03, rot=(0, 0, r))
        L.box(col, f"lid{i}", (s * 1.03, s * 0.14, 0.05), (x, y, s + 0.01), M["wood_dark"], bevel=0.01, rot=(0, 0, r))
        L.box(col, f"lid2{i}", (s * 0.14, s * 1.03, 0.05), (x, y, s + 0.012), M["wood_dark"], bevel=0.01,
              rot=(0, 0, r))
    return dict(solid_r=1.3)


# ---------------------------------------------------------------------------

def bounds(sc, col):
    dg = sc.view_layers[0].depsgraph
    dg.update()
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in col.all_objects:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        for v in me.vertices:
            p = mw @ v.co
            for k in range(3):
                lo[k] = min(lo[k], p[k])
                hi[k] = max(hi[k], p[k])
        ev.to_mesh_clear()
    return lo, hi


def shoot(sc, name, col, info, catcher_mat, rot=0.0):
    sc.collection.children.link(col)
    if rot:
        e = bpy.data.objects.new("UT_rot", None)
        col.objects.link(e)
        for ob in list(col.objects):
            if ob is not e and ob.parent is None:
                ob.parent = e
        e.rotation_euler = (0, 0, rot)
    lo, hi = bounds(sc, col)
    h = hi.z
    pad = 0.3
    sh = h * 0.8 + 0.3            # the shadow falls toward +x, -y (sun from the upper-left)
    x0, x1 = lo.x - pad, hi.x + pad + sh
    y0, y1 = lo.y - pad - sh, hi.y + pad
    px_w = int(math.ceil((x1 - x0) * L.PPM / 2) * 2)
    px_h = int(math.ceil((y1 - y0) * L.PPM / 2) * 2)
    w_m, h_m = px_w / L.PPM, px_h / L.PPM
    x1, y0 = x0 + w_m, y1 - h_m
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cam = L.add_topdown_camera(sc, w_m, h_m, px_w, px_h, center=(cx, cy), z=80)
    plane = L.add_catcher(sc, max(w_m, h_m) * 3, catcher_mat, center=(cx, cy))
    L.setup_render(sc, samples=48)
    L.render(sc, os.path.join(OUT, name + ".png"))
    info = dict(info)
    # ax, ay: pixel position of the object's origin inside the sprite. foot: pixel box of the object itself.
    info.update(w=px_w, h=px_h, ax=round(-x0 * L.PPM, 1), ay=round(y1 * L.PPM, 1), height=round(h, 2),
                foot=[round((lo.x - x0) * L.PPM), round((y1 - hi.y) * L.PPM), round((hi.x - x0) * L.PPM),
                      round((y1 - lo.y) * L.PPM)])
    META[name] = info
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
    M = materials()
    catcher = L.mat_shadow_catcher()
    lit = L.calibrate_catcher(sc, catcher, os.path.join(OUT, "_probe.png"))
    meta_path = os.path.join(OUT, "scenery.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            META.update(json.load(f))

    jobs = []

    def job(name, kind, fn, rot=0.0):
        if ONLY is None or any(name.startswith(o) for o in ONLY):
            jobs.append((name, kind, fn, rot))

    for i, (r, mat, h) in enumerate(((2.6, "leaf1", 5.0), (3.3, "leaf2", 6.0), (2.2, "leaf2", 4.5), (3.0, "leaf1", 5.5),
                                     (2.7, "autumn", 5.0))):
        job(f"tree{i}", "tree", lambda c, rng, r=r, mat=mat, h=h: leafy_tree(c, M, rng, r, M[mat], h))
    for i, (r, h) in enumerate(((2.3, 8.0), (1.9, 7.0), (2.6, 9.5))):
        job(f"pine{i}", "tree", lambda c, rng, r=r, h=h: pine_tree(c, M, rng, r, h))
    for i, (r, mat, fl) in enumerate(((1.2, "leaf1", None), (1.5, "leaf2", "flower_r"), (1.0, "leaf3", None),
                                      (1.3, "leaf1", "flower_y"), (1.1, "leaf2", "flower_w"))):
        job(f"bush{i}", "bush", lambda c, rng, r=r, mat=mat, fl=fl: bush(c, M, rng, r, M[mat], fl))
    for i, (r, moss) in enumerate(((1.3, False), (1.9, True), (2.6, False), (1.6, False), (3.2, True))):
        job(f"boulder{i}", "boulder", lambda c, rng, r=r, moss=moss: boulder(c, M, rng, r, moss))
    houses = [
        ("house0", dict(lx=9, ly=6.5, roof="roof_red")),
        ("house1", dict(lx=12, ly=7.5, roof="roof_slate", dormer=True)),
        ("house2", dict(lx=10, ly=7, roof="roof_brown", annex=(4.5, 3.5))),
        ("house3", dict(lx=8, ly=6, roof="thatch", pitch=0.8)),
        ("barn0", dict(lx=15, ly=9, roof="roof_brown", wall="wood_dark", wh=4.2, pitch=0.55, chimney=False)),
    ]
    for name, kw in houses:
        for suffix, rot in (("", 0.0), ("_r", math.pi / 2)):
            job(name + suffix, "house", lambda c, rng, kw=kw: house(c, M, rng, **kw), rot)
    for i, (size, height) in enumerate(((30, 19), (40, 24), (24, 15), (50, 29))):
        job(f"mountain{i}", "mountain", lambda c, rng, a=(size, height, i + 1): (mountain(c, M, *a),
                                                                                  dict(solid="alpha"))[1])
    job("bridge0", "bridge", lambda c, rng: bridge(c, M, 22.0, 9.0))
    job("hay0", "prop", lambda c, rng: hay(c, M, rng))
    job("crates0", "prop", lambda c, rng: crates(c, M, rng))

    for name, kind, fn, rot in jobs:
        rng = random.Random(sum(map(ord, name)) * 7919)
        col = L.new_collection(name)
        info = fn(col, rng)
        info["kind"] = kind
        shoot(sc, name, col, info, catcher, rot=rot)

    with open(meta_path, "w") as f:
        json.dump(META, f, indent=1)
    try:
        os.remove(os.path.join(OUT, "_probe.png"))
    except OSError:
        pass
    return dict(lit=lit, names=list(META))


if __name__ != "render_scenery":
    result = main()
