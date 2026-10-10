"""Render UI art: title logo, menu backdrop, metal panel/button skins, credit coin."""
import importlib
import math
import os
import random
import sys

# tools/blrun.py passes UT_HERE; when run as a file (blender -b --python ...) __file__ is used instead
HERE = globals().get("UT_HERE") or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import utlib as L
import tanks as T
import render_scenery as S
import render_terrain as RT
for _m in (L, T, S, RT):
    importlib.reload(_m)
import bmesh
import bpy

OUT = os.path.join(L.ASSETS, "ui")
ONLY = globals().get("ONLY") or ["logo", "panel", "coin", "hero"]


def lights(sc, **kw):
    L.setup_world(sc)
    L.add_sun(sc, **kw)
    fill = L.add_sun(sc, elevation=35, azimuth=-40, energy=0.8, angle=30, color=(0.75, 0.85, 1.0), name="Fill")
    fill.data.use_shadow = False


def logo(sc):
    font = None
    for f in ("impact.ttf", "bahnschrift.ttf", "arialbd.ttf"):
        p = os.path.join(r"C:\Windows\Fonts", f)
        if os.path.exists(p):
            font = bpy.data.fonts.load(p, check_existing=True)
            break
    steel = L.mat_surface("UT_UI_Steel", [(0.3, (0.42, 0.44, 0.47)), (0.7, (0.75, 0.77, 0.8))], noise_scale=3.0,
                          rough=0.28, metallic=1.0, bump=0.08, bump_scale=60.0)
    orange = L.mat_surface("UT_UI_Orange", [(0.3, (0.75, 0.2, 0.02)), (0.7, (1.0, 0.42, 0.04))], noise_scale=2.0,
                           rough=0.3, metallic=0.6, bump=0.1, bump_scale=30.0)
    dark = L.mat_surface("UT_UI_Dark", [(0.3, 0.02), (0.7, 0.05)], rough=0.4, metallic=0.9, bump=0.0)

    def text(body, size, y, mat, spacing=1.0):
        cu = bpy.data.curves.new("UT_Text", "FONT")
        cu.body = body
        cu.align_x = "CENTER"
        cu.size = size
        cu.extrude = 0.16
        cu.bevel_depth = 0.035
        cu.bevel_resolution = 3
        cu.space_character = spacing
        if font:
            cu.font = font
        ob = bpy.data.objects.new("UT_Text", cu)
        ob.data.materials.append(mat)
        ob.location = (0, y, 0)
        sc.collection.objects.link(ob)
        return ob

    text("ULTIMATE", 1.25, 0.72, steel, 1.12)
    text("TANKS", 2.3, -1.22, orange, 1.08)
    col = L.new_collection("logo")
    sc.collection.children.link(col)
    L.box(col, "bar", (7.6, 0.1, 0.12), (0, 0.46, 0.05), dark, bevel=0.02)
    L.setup_world(sc, strength=0.9)
    L.add_sun(sc, elevation=50, azimuth=120, energy=3.0)
    f = L.add_sun(sc, elevation=25, azimuth=-60, energy=1.5, name="Fill", color=(1.0, 0.8, 0.6))
    f.data.use_shadow = False
    L.add_topdown_camera(sc, 8.4, 3.9, 1400, 650, center=(0, -0.12))
    L.setup_render(sc, samples=64)
    L.render(sc, os.path.join(OUT, "logo.png"))


def panels(sc):
    plate = L.mat_surface("UT_UI_Plate", [(0.3, (0.012, 0.015, 0.02)), (0.7, (0.024, 0.029, 0.036))], noise_scale=0.9,
                          rough=0.62, metallic=0.25, bump=0.1, bump_scale=45.0)
    edge = L.mat_surface("UT_UI_Edge", [(0.3, (0.10, 0.11, 0.125)), (0.7, (0.18, 0.195, 0.215))], noise_scale=3.0,
                         rough=0.4, metallic=0.7, bump=0.05)
    btn = L.mat_surface("UT_UI_Btn", [(0.3, (0.035, 0.045, 0.06)), (0.7, (0.06, 0.075, 0.095))], noise_scale=0.9,
                        rough=0.55, metallic=0.3, bump=0.08, bump_scale=50.0)
    rivet = L.mat_surface("UT_UI_Rivet", [(0.3, (0.3, 0.3, 0.32)), (0.7, (0.5, 0.5, 0.53))], rough=0.3, metallic=1.0,
                          bump=0.0)

    def shoot(name, w, h, body, frame=0.12, rivets=True, px_per=64):
        col = L.new_collection(name)
        sc.collection.children.link(col)
        L.box(col, "frame", (w, h, 0.2), (0, 0, 0.1), edge, bevel=0.07, segments=3)
        L.box(col, "inner", (w - frame * 2, h - frame * 2, 0.2), (0, 0, 0.13), body, bevel=0.03)
        if rivets:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    L.ico(col, f"r{sx}{sy}", 0.045, (sx * (w / 2 - frame * 1.7), sy * (h / 2 - frame * 1.7), 0.235),
                          rivet, subdiv=2, scale=(1, 1, 0.5))
        cam = L.add_topdown_camera(sc, w, h, int(w * px_per), int(h * px_per))
        L.setup_render(sc, samples=48)
        L.render(sc, os.path.join(OUT, name + ".png"))
        bpy.data.objects.remove(cam, do_unlink=True)
        for ob in list(col.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.collections.remove(col)

    lights(sc, elevation=60, energy=2.6)
    shoot("panel", 4.0, 4.0, plate)
    shoot("button", 5.0, 1.0, btn, frame=0.07, rivets=False)
    shoot("slot", 2.0, 2.0, btn, frame=0.07, rivets=False)


def coin(sc):
    gold = L.mat_surface("UT_UI_Gold", [(0.3, (0.75, 0.5, 0.08)), (0.7, (1.0, 0.78, 0.25))], noise_scale=6.0,
                         rough=0.25, metallic=1.0, bump=0.05)
    col = L.new_collection("coin")
    sc.collection.children.link(col)
    L.cyl(col, "c", 0.9, 0.16, (0, 0, 0.08), gold, bevel=0.03, verts=48)
    L.cyl(col, "rim", 0.9, 0.06, (0, 0, 0.17), gold, bevel=0.02, verts=48)
    L.cyl(col, "in", 0.74, 0.07, (0, 0, 0.17), gold, bevel=0.02, verts=48)
    pts = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        r = 0.52 if k % 2 == 0 else 0.22
        pts.append((math.cos(a) * r, math.sin(a) * r))
    L.prism_xy(col, "star", pts, 0.2, 0.27, (0, 0, 0), gold, top_scale=0.8, bevel=0.01)
    lights(sc, elevation=55, energy=3.0)
    L.add_topdown_camera(sc, 2.0, 2.0, 96, 96)
    L.setup_render(sc, samples=64)
    L.render(sc, os.path.join(OUT, "coin.png"))


def hero(sc):
    """Menu backdrop: an armoured column on a meadow at golden hour."""
    rng = random.Random(11)
    base = L.tank_materials()
    grass = RT.TEXTURES["grass"]()
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=600)
    ground = L._obj("HeroGround", bm)
    ground.data.materials.append(grass)
    sc.collection.objects.link(ground)

    colors = {"goliath": (0.50, 0.06, 0.05), "mammoth": (0.11, 0.22, 0.42), "heavy": (0.20, 0.30, 0.10),
              "medium": (0.55, 0.42, 0.20), "basic": (0.36, 0.40, 0.44), "speed": (0.75, 0.33, 0.04)}
    places = {"goliath": (0, 0, 0.0), "mammoth": (-5, 9.5, 0.06), "heavy": (-3.5, -9.0, -0.08),
              "medium": (-13, 17.5, 0.1), "basic": (-11, -16.5, -0.05), "speed": (8.0, -8.0, -0.2)}
    for i, key in enumerate(T.ORDER):
        c = colors[key]
        M = dict(base)
        M["paint"] = L.mat_surface(f"UT_HeroPaint{i}", [(0.22, tuple(v * 0.55 for v in c)), (0.5, c),
                                                        (0.8, tuple(min(1, v * 1.25) for v in c))], noise_scale=1.7,
                                   rough=0.42, bump=0.06, bump_scale=38.0, coat=0.2)
        M["paint2"] = L.mat_surface(f"UT_HeroPaintD{i}", [(0.25, tuple(v * 0.3 for v in c)),
                                                          (0.7, tuple(v * 0.55 for v in c))], noise_scale=2.6,
                                    rough=0.5, bump=0.06, bump_scale=38.0)
        hull, tur, meta = T.build_tank(L, key, M)
        x, y, rot = places[key]
        L.instance(sc, hull, (x, y, 0), rot, "h" + key)
        tx = meta["turret_x"]
        L.instance(sc, tur, (x + math.cos(rot) * tx, y + math.sin(rot) * tx, 0), rot + rng.uniform(-0.3, 0.3),
                   "t" + key)

    SM = S.materials()
    n = 0

    def place(builder, x, y, scale=1.0, rot=0.0):
        nonlocal n
        n += 1
        col = L.new_collection(f"hero{n}")
        builder(col)
        e = L.instance(sc, col, (x, y, 0), rot, f"hs{n}")
        e.scale = (scale, scale, scale)

    # distant ridge line
    for i, (x, y, sz, h) in enumerate(((-150, 60, 110, 46), (-170, -40, 130, 60), (-140, -150, 100, 40),
                                       (-175, 160, 120, 52), (-120, 240, 90, 38), (-125, -250, 100, 44))):
        place(lambda c, a=(sz, h, i + 3): S.mountain(c, SM, *a), x, y)
    # tree lines and scattered trees
    for i in range(70):
        x = rng.uniform(-110, -28)
        y = rng.uniform(-140, 140)
        r2 = random.Random(i)
        if i % 3 == 0:
            place(lambda c, r2=r2: S.pine_tree(c, SM, r2, r2.uniform(2.0, 2.8), r2.uniform(7, 10)), x, y, 1.0,
                  rng.uniform(0, 6))
        else:
            mat = SM[r2.choice(["leaf1", "leaf2", "leaf2", "autumn"])]
            place(lambda c, r2=r2, mat=mat: S.leafy_tree(c, SM, r2, r2.uniform(2.4, 3.4), mat, r2.uniform(4.5, 6)),
                  x, y, 1.0, rng.uniform(0, 6))
    for i, (x, y) in enumerate(((12, 13), (-18, -27), (-24, 30), (-2, 22), (2, -22))):
        r2 = random.Random(100 + i)
        place(lambda c, r2=r2: S.boulder(c, SM, r2, r2.uniform(0.9, 2.0), i % 2 == 0), x, y)
    place(lambda c: S.house(c, SM, rng, 9, 6.5, "roof_red"), -34, 42, 1.0, 0.5)
    place(lambda c: S.house(c, SM, rng, 15, 9, "roof_brown", wall="wood_dark", wh=4.2, pitch=0.55, chimney=False),
          -48, -46, 1.0, -0.3)

    # golden-hour light
    w = L.setup_world(sc, color=(0.55, 0.62, 0.85), strength=0.7)
    nt = w.node_tree
    try:
        sky = nt.nodes.new("ShaderNodeTexSky")
        for attr, val in (("sun_elevation", math.radians(14)), ("sun_rotation", math.radians(200)),
                          ("sun_intensity", 0.0), ("sun_disc", False)):
            if hasattr(sky, attr):
                setattr(sky, attr, val)
        nt.links.new(sky.outputs[0], nt.nodes["Background"].inputs[0])
        nt.nodes["Background"].inputs[1].default_value = 0.3
    except Exception:
        pass
    L.add_sun(sc, elevation=15, azimuth=55, energy=6.5, angle=3.0, color=(1.0, 0.6, 0.3))
    f = L.add_sun(sc, elevation=40, azimuth=-110, energy=0.6, angle=40, color=(0.6, 0.72, 1.0), name="Fill")
    f.data.use_shadow = False
    cam = L.add_persp_camera(sc, (25, -3.0, 2.5), (-6, 1.0, 2.6), lens=32, px=(1920, 1080))
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = 25
    cam.data.dof.aperture_fstop = 5.6
    L.setup_render(sc, samples=96, transparent=False, view="AgX", look="AgX - Medium High Contrast")
    sc.eevee.fast_gi_distance = 6.0
    L.render(sc, os.path.join(OUT, "menu_bg.png"))


def main():
    done = []
    for what, fn in (("logo", logo), ("panel", panels), ("coin", coin), ("hero", hero)):
        if what in ONLY:
            sc = L.reset_scene()
            fn(sc)
            done.append(what)
    for t in list(bpy.data.objects):
        if t.name.startswith("UT_Text") and t.users == 0:
            bpy.data.objects.remove(t)
    return done


result = {"done": main()}
