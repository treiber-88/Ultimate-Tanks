"""Render ground textures (grass, dirt, sand, rock, water...) top-down. tools/make_tileable.py makes them seamless."""
import importlib
import os
import sys

HERE = r"C:\Users\mk-ki\Desktop\Ultimate Tanks\tools\blender"
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import utlib as L
importlib.reload(L)
import bmesh
import bpy

OUT = os.path.join(L.ASSETS, "terrain", "raw")
SIZE_PX = 1024
SIZE_M = SIZE_PX / L.PPM
ONLY = globals().get("ONLY")


def ground_mat(name, stops, scale=0.22, fine=(0.6, 1.25), fine_scale=9.0, bump=0.8, bump_scale=14.0, rough=0.9,
               spots=None, voronoi_bump=0.0, metallic=0.0, spec=0.3, distortion=0.4):
    """Large colour patches (noise->ramp) multiplied by fine grain, with a bumpy micro surface."""
    m, nt = L._mat(name)
    vec = L._coords(nt)
    big = L._noise(nt, vec, scale, 10.0, 0.6, distortion)
    ramp = L._ramp(nt, big.outputs["Fac"], stops)
    grain = L._noise(nt, vec, fine_scale, 6.0, 0.7)
    gr = L._ramp(nt, grain.outputs["Fac"], [(0.25, fine[0]), (0.75, fine[1])])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], mix.inputs[6])
    nt.links.new(gr.outputs["Color"], mix.inputs[7])
    color = mix.outputs[2]
    if spots:
        # scattered specks (pebbles, flowers, dry tufts)
        col, sc, thr = spots
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = sc
        nt.links.new(vec, vor.inputs["Vector"])
        sr = L._ramp(nt, vor.outputs["Distance"], [(thr * 0.6, 1.0), (thr, 0.0)])
        mix2 = nt.nodes.new("ShaderNodeMix")
        mix2.data_type = "RGBA"
        nt.links.new(sr.outputs["Color"], mix2.inputs[0])
        nt.links.new(color, mix2.inputs[6])
        mix2.inputs[7].default_value = (*col, 1.0)
        color = mix2.outputs[2]
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(color, bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = rough
    bs.inputs["Metallic"].default_value = metallic
    if "Specular IOR Level" in bs.inputs:
        bs.inputs["Specular IOR Level"].default_value = spec
    bn = L._noise(nt, vec, bump_scale, 5.0, 0.7)
    b = L._bump(nt, bn.outputs["Fac"], bump, 0.08)
    last = b
    if voronoi_bump:
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = 3.5
        nt.links.new(vec, vor.inputs["Vector"])
        b2 = L._bump(nt, vor.outputs["Distance"], voronoi_bump, 0.15)
        nt.links.new(b.outputs["Normal"], b2.inputs["Normal"])
        last = b2
    nt.links.new(last.outputs["Normal"], bs.inputs["Normal"])
    L._out(nt, bs.outputs["BSDF"])
    return m


def water_mat(name, deep, shallow):
    m, nt = L._mat(name)
    vec = L._coords(nt)
    big = L._noise(nt, vec, 0.25, 6.0, 0.55, 1.2)
    ramp = L._ramp(nt, big.outputs["Fac"], [(0.3, deep), (0.75, shallow)])
    # caustic-like light lines
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 0.9
    warp = L._noise(nt, vec, 0.7, 3.0, 0.5, 2.0)
    nt.links.new(warp.outputs["Color"], vor.inputs["Vector"])
    vor.inputs["Scale"].default_value = 7.0
    cr = L._ramp(nt, vor.outputs["Distance"], [(0.0, (0.10, 0.2, 0.22)), (0.07, (0.0, 0.0, 0.0))])
    add = nt.nodes.new("ShaderNodeMix")
    add.data_type = "RGBA"
    add.blend_type = "ADD"
    add.inputs[0].default_value = 0.55
    nt.links.new(ramp.outputs["Color"], add.inputs[6])
    nt.links.new(cr.outputs["Color"], add.inputs[7])
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(add.outputs[2], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.4
    wn = L._noise(nt, vec, 1.6, 4.0, 0.6, 1.5)
    b = L._bump(nt, wn.outputs["Fac"], 0.35, 0.2)
    nt.links.new(b.outputs["Normal"], bs.inputs["Normal"])
    L._out(nt, bs.outputs["BSDF"])
    return m


TEXTURES = {
    "grass": lambda: ground_mat("UT_T_Grass", [(0.2, (0.045, 0.115, 0.022)), (0.5, (0.075, 0.17, 0.032)),
                                               (0.8, (0.13, 0.235, 0.048))], fine=(0.35, 1.7), fine_scale=5.7,
                                bump=1.0, bump_scale=10.0, spots=((0.25, 0.3, 0.07), 2.36, 0.13)),
    "grass_dry": lambda: ground_mat("UT_T_GrassDry", [(0.2, (0.12, 0.15, 0.035)), (0.5, (0.19, 0.20, 0.05)),
                                                      (0.8, (0.30, 0.27, 0.08))], fine=(0.35, 1.7), fine_scale=5.7,
                                    bump=1.0, bump_scale=10.0),
    "forest": lambda: ground_mat("UT_T_Forest", [(0.2, (0.03, 0.06, 0.018)), (0.5, (0.055, 0.085, 0.025)),
                                                 (0.8, (0.10, 0.09, 0.04))], fine=(0.3, 1.7), fine_scale=4.3,
                                 bump=1.0, bump_scale=5.3, spots=((0.16, 0.10, 0.04), 1.64, 0.19)),
    "dirt": lambda: ground_mat("UT_T_Dirt", [(0.2, (0.10, 0.065, 0.035)), (0.5, (0.17, 0.115, 0.06)),
                                             (0.8, (0.25, 0.18, 0.10))], fine=(0.4, 1.6), fine_scale=3.0, bump=1.0,
                               bump_scale=2.9, spots=((0.32, 0.29, 0.25), 9.0, 0.09), voronoi_bump=0.3),
    "sand": lambda: ground_mat("UT_T_Sand", [(0.2, (0.42, 0.33, 0.18)), (0.5, (0.55, 0.45, 0.26)),
                                             (0.8, (0.66, 0.56, 0.35))], fine=(0.6, 1.35), fine_scale=7.4, bump=0.5,
                               bump_scale=0.9, spots=((0.3, 0.27, 0.22), 1.27, 0.10)),
    "rock": lambda: ground_mat("UT_T_Rock", [(0.2, (0.11, 0.105, 0.095)), (0.5, (0.20, 0.19, 0.175)),
                                             (0.8, (0.31, 0.30, 0.28))], fine=(0.35, 1.6), fine_scale=2.0, bump=1.0,
                               bump_scale=1.5, voronoi_bump=0.8),
    "water": lambda: water_mat("UT_T_Water", (0.006, 0.04, 0.085), (0.014, 0.085, 0.125)),
    "water_shallow": lambda: water_mat("UT_T_WaterS", (0.02, 0.10, 0.12), (0.05, 0.17, 0.165)),
}


def main():
    sc = L.reset_scene()
    L.setup_world(sc, strength=0.5)
    L.add_sun(sc, elevation=58, energy=2.3)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=SIZE_M / 2 + 1)
    ob = L._obj("Ground", bm)
    sc.collection.objects.link(ob)
    L.add_topdown_camera(sc, SIZE_M, SIZE_M, SIZE_PX, SIZE_PX)
    L.setup_render(sc, samples=32, transparent=False)
    done = []
    for name, fn in TEXTURES.items():
        if ONLY and name not in ONLY:
            continue
        ob.data.materials.clear()
        ob.data.materials.append(fn())
        L.render(sc, os.path.join(OUT, name + ".png"))
        done.append(name)
    return done


if __name__ != "render_terrain":
    result = {"done": main()}
