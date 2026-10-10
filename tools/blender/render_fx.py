"""Render effect sprites: smoke and fire puffs, glows, shockwave, muzzle flash, sparks, scorch/crater decals, debris."""
import importlib
import math
import os
import sys

HERE = r"C:\Users\mk-ki\Desktop\Ultimate Tanks\tools\blender"
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import utlib as L
importlib.reload(L)
import bmesh
import bpy

OUT = os.path.join(L.ASSETS, "fx")
ONLY = globals().get("ONLY")


class G:
    """Tiny node-graph builder for 'shader plane' sprites. The plane spans -1..1 in object space."""

    def __init__(self, name):
        self.m, self.nt = L._mat(name)
        tc = self.nt.nodes.new("ShaderNodeTexCoord")
        self.obj = tc.outputs["Object"]

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.nt.nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                self.nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    def mapped(self, scale=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0)):
        mp = self.nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = scale
        mp.inputs["Location"].default_value = loc
        mp.inputs["Rotation"].default_value = rot
        self.nt.links.new(self.obj, mp.inputs["Vector"])
        return mp.outputs["Vector"]

    def radius(self, vec=None):
        n = self.nt.nodes.new("ShaderNodeVectorMath")
        n.operation = "LENGTH"
        self.nt.links.new(vec or self.obj, n.inputs[0])
        return n.outputs["Value"]

    def noise(self, scale, seed=0.0, detail=5.0, rough=0.6, distortion=0.0, vec=None):
        v = vec or self.mapped(loc=(seed * 7.13, seed * 3.71, seed * 1.37))
        return L._noise(self.nt, v, scale, detail, rough, distortion).outputs["Fac"]

    def ramp(self, fac, stops):
        return L._ramp(self.nt, fac, stops)

    def smooth(self, x, lo, hi):
        """smoothstep via a colour ramp with ease interpolation"""
        r = L._ramp(self.nt, x, [(lo, 0.0), (hi, 1.0)])
        r.color_ramp.interpolation = "EASE"
        return r.outputs["Color"]

    def finish(self, color, alpha, strength=1.0):
        em = self.nt.nodes.new("ShaderNodeEmission")
        if isinstance(color, tuple):
            em.inputs["Color"].default_value = (*color, 1.0)
        else:
            self.nt.links.new(color, em.inputs["Color"])
        em.inputs["Strength"].default_value = strength
        tr = self.nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = self.nt.nodes.new("ShaderNodeMixShader")
        self.nt.links.new(alpha, mix.inputs[0])
        self.nt.links.new(tr.outputs[0], mix.inputs[1])
        self.nt.links.new(em.outputs[0], mix.inputs[2])
        L._out(self.nt, mix.outputs[0])
        try:
            self.m.surface_render_method = "BLENDED"
        except Exception:
            self.m.blend_method = "BLEND"
        return self.m


def falloff(g, power=1.0, vec=None):
    r = g.radius(vec)
    f = g.math("SUBTRACT", 1.0, r, clamp=True)
    return g.math("POWER", f, power) if power != 1.0 else f


def glow(name, power=2.4):
    g = G(name)
    return g.finish((1, 1, 1), falloff(g, power))


def smoke(name, seed):
    g = G(name)
    f = falloff(g, 0.9)
    n = g.noise(2.2, seed, 6.0, 0.62, 0.6)
    d = g.math("MULTIPLY", f, g.math("MULTIPLY_ADD", n, 1.7, 0.1))
    alpha = g.smooth(d, 0.22, 0.62)
    shade = g.noise(3.0, seed + 11.0, 5.0, 0.6)
    col = g.ramp(shade, [(0.25, 0.42), (0.75, 1.0)]).outputs["Color"]
    return g.finish(col, alpha)


def fire(name, seed):
    g = G(name)
    f = falloff(g, 0.8)
    n = g.noise(2.6, seed, 6.0, 0.65, 1.0)
    d = g.math("MULTIPLY", f, g.math("MULTIPLY_ADD", n, 1.9, 0.05))
    alpha = g.smooth(d, 0.2, 0.5)
    col = g.ramp(d, [(0.22, (0.35, 0.02, 0.0)), (0.42, (1.0, 0.16, 0.0)), (0.62, (1.0, 0.55, 0.05)),
                     (0.85, (1.0, 0.95, 0.6))]).outputs["Color"]
    return g.finish(col, alpha, 1.25)


def flame(name, seed):
    """Tear-drop flame licking toward +Y, for ground fires."""
    g = G(name)
    v = g.mapped(scale=(1.9, 1.05, 1.0), loc=(0, 0.12, 0))
    f = falloff(g, 0.8, v)
    n = g.noise(2.4, seed, 5.0, 0.6, 1.4)
    sep = g.nt.nodes.new("ShaderNodeSeparateXYZ")
    g.nt.links.new(g.obj, sep.inputs[0])
    taper = g.math("MULTIPLY_ADD", sep.outputs["Y"], -0.35, 0.75, clamp=True)
    d = g.math("MULTIPLY", g.math("MULTIPLY", f, taper), g.math("MULTIPLY_ADD", n, 2.2, 0.1))
    alpha = g.smooth(d, 0.16, 0.42)
    col = g.ramp(d, [(0.16, (0.5, 0.03, 0.0)), (0.34, (1.0, 0.22, 0.0)), (0.52, (1.0, 0.6, 0.05)),
                     (0.75, (1.0, 0.95, 0.55))]).outputs["Color"]
    return g.finish(col, alpha, 1.25)


def ring(name):
    g = G(name)
    r = g.radius()
    band = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", g.math("ABSOLUTE", g.math("SUBTRACT", r, 0.8)), 7.0),
                  clamp=True)
    n = g.noise(5.0, 3.0, 4.0, 0.6)
    a = g.math("MULTIPLY", g.math("POWER", band, 1.6), g.math("MULTIPLY_ADD", n, 0.8, 0.5), clamp=True)
    return g.finish((1, 1, 1), a)


def muzzle(name, seed):
    """Flash pointing along +X from the left edge of the sprite."""
    g = G(name)
    v = g.mapped(scale=(0.62, 2.3, 1.0), loc=(0.42, 0, 0))
    f = falloff(g, 0.75, v)
    n = g.noise(3.2, seed, 4.0, 0.6, 1.5)
    d = g.math("MULTIPLY", f, g.math("MULTIPLY_ADD", n, 1.6, 0.35))
    # side jets from the muzzle brake
    v2 = g.mapped(scale=(3.0, 1.0, 1.0), loc=(1.6, 0, 0))
    f2 = g.math("MULTIPLY", falloff(g, 1.2, v2), 0.75)
    d = g.math("MAXIMUM", d, f2)
    alpha = g.smooth(d, 0.14, 0.45)
    col = g.ramp(d, [(0.15, (1.0, 0.25, 0.0)), (0.4, (1.0, 0.65, 0.1)), (0.7, (1.0, 0.97, 0.75))]).outputs["Color"]
    return g.finish(col, alpha, 1.3)


def spark(name):
    g = G(name)
    v = g.mapped(scale=(1.0, 9.0, 1.0))
    return g.finish((1.0, 0.85, 0.5), falloff(g, 1.6, v), 1.4)


def scorch(name, seed):
    g = G(name)
    f = falloff(g, 0.7)
    n = g.noise(2.0, seed, 7.0, 0.7, 0.8)
    d = g.math("MULTIPLY", f, g.math("MULTIPLY_ADD", n, 1.8, 0.1))
    alpha = g.math("MULTIPLY", g.smooth(d, 0.1, 0.7), 0.85)
    col = g.ramp(n, [(0.3, (0.012, 0.01, 0.008)), (0.7, (0.05, 0.04, 0.03))]).outputs["Color"]
    return g.finish(col, alpha)


def crater(name, seed):
    g = G(name)
    r = g.radius()
    n = g.noise(3.0, seed, 7.0, 0.7, 0.5)
    rr = g.math("ADD", r, g.math("MULTIPLY_ADD", n, 0.3, -0.15))
    alpha = g.math("MULTIPLY", g.smooth(g.math("SUBTRACT", 1.0, rr), 0.08, 0.3), 0.95)
    col = g.ramp(rr, [(0.0, (0.03, 0.022, 0.015)), (0.42, (0.07, 0.05, 0.03)), (0.56, (0.22, 0.16, 0.09)),
                      (0.68, (0.12, 0.085, 0.05)), (0.9, (0.07, 0.055, 0.035))]).outputs["Color"]
    grain = g.ramp(g.noise(14.0, seed + 5), [(0.3, 0.6), (0.7, 1.25)]).outputs["Color"]
    mix = g.nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    g.nt.links.new(col, mix.inputs[6])
    g.nt.links.new(grain, mix.inputs[7])
    return g.finish(mix.outputs[2], alpha)


def tracks(name):
    """A short stretch of twin tread marks running along X (tiled by the game)."""
    g = G(name)
    sep = g.nt.nodes.new("ShaderNodeSeparateXYZ")
    g.nt.links.new(g.obj, sep.inputs[0])
    y = g.math("ABSOLUTE", sep.outputs["Y"])
    band = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", g.math("ABSOLUTE", g.math("SUBTRACT", y, 0.62)), 4.2),
                  clamp=True)
    cleat = g.math("MULTIPLY_ADD", g.math("SINE", g.math("MULTIPLY", sep.outputs["X"], 25.13)), 0.3, 0.7)
    n = g.noise(6.0, 2.0)
    a = g.math("MULTIPLY", g.math("MULTIPLY", g.smooth(band, 0.1, 0.6), cleat), g.math("MULTIPLY_ADD", n, 0.6, 0.25),
               clamp=True)
    return g.finish((0.035, 0.026, 0.016), g.math("MULTIPLY", a, 0.8))


PLANES = {
    "glow": (lambda: glow("UT_FX_glow"), 128),
    "glow_soft": (lambda: glow("UT_FX_glow2", 1.3), 128),
    "ring": (lambda: ring("UT_FX_ring"), 256),
    "spark": (lambda: spark("UT_FX_spark"), 64),
    "tracks": (lambda: tracks("UT_FX_tracks"), 64),
}
for i in range(4):
    PLANES[f"smoke{i}"] = (lambda i=i: smoke(f"UT_FX_smoke{i}", i * 2.0 + 1), 128)
    PLANES[f"fire{i}"] = (lambda i=i: fire(f"UT_FX_fire{i}", i * 3.0 + 2), 128)
    PLANES[f"flame{i}"] = (lambda i=i: flame(f"UT_FX_flame{i}", i * 5.0 + 3), 96)
for i in range(2):
    PLANES[f"muzzle{i}"] = (lambda i=i: muzzle(f"UT_FX_muzzle{i}", i * 4.0 + 1), 128)
    PLANES[f"scorch{i}"] = (lambda i=i: scorch(f"UT_FX_scorch{i}", i * 6.0 + 4), 256)
    PLANES[f"crater{i}"] = (lambda i=i: crater(f"UT_FX_crater{i}", i * 8.0 + 5), 192)


def debris(sc):
    import random
    metal = L.mat_surface("UT_FX_Debris", [(0.3, (0.03, 0.03, 0.03)), (0.7, (0.12, 0.11, 0.1))], rough=0.5,
                          metallic=0.8, bump=0.4)
    col = L.new_collection("debris")
    sc.collection.children.link(col)
    rng = random.Random(5)
    for i in range(6):
        for ob in list(col.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        if i % 2 == 0:
            ob = L.ico(col, "d", 0.3, (0, 0, 0), metal, subdiv=1, smooth=False,
                       scale=(rng.uniform(0.6, 1.2), rng.uniform(0.3, 0.7), rng.uniform(0.2, 0.5)))
            L.displace(ob, 0.25, 0.3, kind="VORONOI")
        else:
            ob = L.box(col, "d", (rng.uniform(0.4, 0.8), rng.uniform(0.2, 0.45), 0.05), (0, 0, 0), metal, bevel=0.01,
                       rot=(rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(0, 3)))
        cam = L.add_topdown_camera(sc, 1.2, 1.2, 48, 48)
        L.setup_render(sc, samples=32)
        L.render(sc, os.path.join(OUT, f"debris{i}.png"))
        bpy.data.objects.remove(cam, do_unlink=True)
    for ob in list(col.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.collections.remove(col)


def main():
    sc = L.reset_scene()
    L.setup_world(sc, color=(0, 0, 0), strength=0.0)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
    plane = L._obj("FxPlane", bm)
    sc.collection.objects.link(plane)
    done = []
    for name, (fn, px) in PLANES.items():
        if ONLY and not any(name.startswith(o) for o in ONLY):
            continue
        plane.data.materials.clear()
        plane.data.materials.append(fn())
        cam = L.add_topdown_camera(sc, 2.0, 2.0, px, px)
        L.setup_render(sc, samples=16)
        L.render(sc, os.path.join(OUT, name + ".png"))
        bpy.data.objects.remove(cam, do_unlink=True)
        done.append(name)
    bpy.data.objects.remove(plane, do_unlink=True)
    if not ONLY or "debris" in ONLY:
        L.setup_world(sc)
        L.add_sun(sc)
        debris(sc)
    return done


result = {"done": main()}
