"""Shared Blender helpers for the Ultimate Tanks art pipeline.

Everything lives in a dedicated scene called "UT"; the user's own scene is never touched.
World axes: +X is "forward" for tanks and projectiles, +Z is up. Sprites are rendered
straight down with +X pointing to the right of the image.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

SCENE = "UT"
PPM = 20.0  # pixels per metre in the game
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")


# ---------------------------------------------------------------------------
# scene management

def get_scene():
    sc = bpy.data.scenes.get(SCENE)
    if sc is None:
        sc = bpy.data.scenes.new(SCENE)
    return sc


def reset_scene():
    """Remove every object in the UT scene and orphaned UT datablocks."""
    sc = get_scene()
    for ob in list(sc.collection.all_objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for col in list(bpy.data.collections):
        if col.name.startswith("UT_"):
            for ob in list(col.objects):
                bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.collections.remove(col)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    for blocks in (bpy.data.cameras, bpy.data.lights, bpy.data.curves):
        for b in list(blocks):
            if b.users == 0 and b.name.startswith("UT_"):
                blocks.remove(b)
    return sc


def new_collection(name, link=False):
    col = bpy.data.collections.new("UT_" + name)
    if link:
        get_scene().collection.children.link(col)
    return col


def setup_render(sc, samples=32, transparent=True, view="Standard", look="None"):
    r = sc.render
    r.engine = "BLENDER_EEVEE"
    r.film_transparent = transparent
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    r.image_settings.color_depth = "8"
    r.image_settings.compression = 60
    r.resolution_percentage = 100
    r.filter_size = 1.2
    ee = sc.eevee
    ee.taa_render_samples = samples
    ee.use_shadows = True
    ee.use_raytracing = True
    ee.ray_tracing_method = "SCREEN"
    ee.use_fast_gi = True
    ee.fast_gi_method = "GLOBAL_ILLUMINATION"
    ee.fast_gi_distance = 2.5
    ee.shadow_ray_count = 3
    ee.shadow_step_count = 8
    sc.view_settings.view_transform = view
    try:
        sc.view_settings.look = look
    except TypeError:
        pass
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.display_settings.display_device = "sRGB"


def setup_world(sc, color=(0.62, 0.70, 0.82), strength=0.55):
    w = bpy.data.worlds.get("UT_World") or bpy.data.worlds.new("UT_World")
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (*color, 1.0)
    bg.inputs[1].default_value = strength
    sc.world = w
    return w


def add_sun(sc, elevation=52.0, azimuth=135.0, energy=3.3, angle=6.0, color=(1.0, 0.96, 0.9), name="Sun"):
    """azimuth: direction the light comes FROM, degrees CCW from +X. 135 = upper-left of a top-down image."""
    light = bpy.data.lights.new("UT_" + name, "SUN")
    light.energy = energy
    light.angle = math.radians(angle)
    light.color = color
    if hasattr(light, 'shadow_maximum_resolution'):
        light.shadow_maximum_resolution = 0.0002
    ob = bpy.data.objects.new("UT_" + name, light)
    sc.collection.objects.link(ob)
    el, az = math.radians(elevation), math.radians(azimuth)
    src = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
    ob.rotation_euler = (-src).to_track_quat("-Z", "Y").to_euler()
    return ob


def add_topdown_camera(sc, width_m, height_m, px_w, px_h, center=(0.0, 0.0), z=60.0):
    cam = bpy.data.cameras.new("UT_Cam")
    cam.type = "ORTHO"
    cam.ortho_scale = max(width_m, height_m)
    cam.clip_start = 0.1
    cam.clip_end = 200.0
    ob = bpy.data.objects.new("UT_Cam", cam)
    sc.collection.objects.link(ob)
    ob.location = (center[0], center[1], z)
    ob.rotation_euler = (0.0, 0.0, 0.0)
    sc.camera = ob
    sc.render.resolution_x = int(px_w)
    sc.render.resolution_y = int(px_h)
    return ob


def add_persp_camera(sc, location, target, lens=50.0, px=(512, 512)):
    cam = bpy.data.cameras.new("UT_Cam")
    cam.lens = lens
    cam.clip_start = 0.1
    cam.clip_end = 500.0
    ob = bpy.data.objects.new("UT_Cam", cam)
    sc.collection.objects.link(ob)
    ob.location = location
    d = Vector(target) - Vector(location)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = ob
    sc.render.resolution_x, sc.render.resolution_y = px
    return ob


def render(sc, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    return path


# ---------------------------------------------------------------------------
# materials

def _mat(name):
    m = bpy.data.materials.get(name)
    if m is not None:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return m, nt


def _out(nt, shader_socket):
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(shader_socket, out.inputs["Surface"])
    return out


def _coords(nt, scale=(1, 1, 1), kind="Object"):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    nt.links.new(tc.outputs[kind], mp.inputs["Vector"])
    return mp.outputs["Vector"]


def _noise(nt, vec, scale, detail=6.0, rough=0.55, distortion=0.0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    n.inputs["Distortion"].default_value = distortion
    if vec is not None:
        nt.links.new(vec, n.inputs["Vector"])
    return n


def _ramp(nt, fac, stops):
    """stops: [(pos, (r,g,b)|grey), ...]"""
    r = nt.nodes.new("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for el, (pos, col) in zip(els, stops):
        el.position = pos
        if isinstance(col, (int, float)):
            col = (col, col, col)
        el.color = (*col[:3], col[3] if len(col) > 3 else 1.0)
    nt.links.new(fac, r.inputs["Fac"])
    return r


def _bump(nt, height, strength=0.2, distance=0.02):
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    nt.links.new(height, b.inputs["Height"])
    return b


def mat_surface(name, stops, noise_scale=4.0, rough=0.5, metallic=0.0, bump=0.15, bump_scale=None,
                rough_var=0.12, detail=7.0, spec=0.5, coat=0.0):
    """Generic procedural PBR surface: colour driven by a noise -> colour ramp."""
    m, nt = _mat(name)
    vec = _coords(nt)
    n1 = _noise(nt, vec, noise_scale, detail)
    ramp = _ramp(nt, n1.outputs["Fac"], stops)
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(ramp.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Metallic"].default_value = metallic
    rr = _ramp(nt, n1.outputs["Fac"], [(0.3, max(0.0, rough - rough_var)), (0.7, min(1.0, rough + rough_var))])
    nt.links.new(rr.outputs["Color"], bs.inputs["Roughness"])
    if "Specular IOR Level" in bs.inputs:
        bs.inputs["Specular IOR Level"].default_value = spec
    if coat and "Coat Weight" in bs.inputs:
        bs.inputs["Coat Weight"].default_value = coat
    if bump:
        n2 = _noise(nt, vec, bump_scale or noise_scale * 6.0, 4.0)
        b = _bump(nt, n2.outputs["Fac"], bump)
        nt.links.new(b.outputs["Normal"], bs.inputs["Normal"])
    _out(nt, bs.outputs["BSDF"])
    return m


def mat_emit(name, color, strength=1.0):
    m, nt = _mat(name)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color[:3], 1.0)
    e.inputs["Strength"].default_value = strength
    _out(nt, e.outputs["Emission"])
    return m


def mat_glow(name, color, strength=3.0, base=(0.05, 0.05, 0.05)):
    m, nt = _mat(name)
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Base Color"].default_value = (*base, 1.0)
    bs.inputs["Emission Color"].default_value = (*color[:3], 1.0)
    bs.inputs["Emission Strength"].default_value = strength
    bs.inputs["Roughness"].default_value = 0.3
    _out(nt, bs.outputs["BSDF"])
    return m


def tank_materials():
    """Returns the dict of materials used by tanks. 'paint*' materials are the team-colour areas."""
    M = {}
    # Paint is rendered near-white so the game can multiply the player's colour into it.
    M["paint"] = mat_surface("UT_Paint", [(0.22, 0.44), (0.48, 0.65), (0.8, 0.76)], noise_scale=1.7,
                             rough=0.42, bump=0.06, bump_scale=38.0, coat=0.15)
    M["paint2"] = mat_surface("UT_PaintDark", [(0.25, 0.30), (0.55, 0.38), (0.8, 0.43)], noise_scale=2.6,
                              rough=0.48, bump=0.06, bump_scale=38.0)
    M["metal"] = mat_surface("UT_Metal", [(0.3, (0.10, 0.105, 0.115)), (0.7, (0.20, 0.21, 0.23))], noise_scale=5.0,
                             rough=0.42, metallic=0.85, bump=0.1)
    M["steel"] = mat_surface("UT_Steel", [(0.3, (0.16, 0.17, 0.19)), (0.7, (0.30, 0.31, 0.34))], noise_scale=7.0,
                             rough=0.3, metallic=1.0, bump=0.05)
    M["track"] = mat_surface("UT_Track", [(0.3, (0.045, 0.043, 0.04)), (0.6, (0.10, 0.09, 0.08)),
                                          (0.85, (0.17, 0.14, 0.11))], noise_scale=9.0, rough=0.7,
                             metallic=0.5, bump=0.3)
    M["rubber"] = mat_surface("UT_Rubber", [(0.3, 0.02), (0.7, 0.05)], rough=0.85, bump=0.1)
    M["black"] = mat_surface("UT_Black", [(0.3, 0.006), (0.7, 0.02)], rough=0.9, bump=0.0)
    M["stripe"] = mat_surface("UT_Stripe", [(0.3, (0.80, 0.80, 0.78)), (0.7, (0.95, 0.95, 0.93))], noise_scale=9.0,
                              rough=0.5, bump=0.0)
    M["canvas"] = mat_surface("UT_Canvas", [(0.3, (0.16, 0.14, 0.09)), (0.7, (0.27, 0.24, 0.15))], noise_scale=14.0,
                              rough=0.95, bump=0.5, bump_scale=60.0)
    M["wood"] = mat_surface("UT_Wood", [(0.3, (0.16, 0.09, 0.04)), (0.7, (0.30, 0.18, 0.09))], noise_scale=12.0,
                            rough=0.8, bump=0.3)
    M["lamp"] = mat_glow("UT_Lamp", (1.0, 0.86, 0.55), 2.5, base=(0.5, 0.45, 0.3))
    M["glass"] = mat_surface("UT_Glass", [(0.3, (0.02, 0.05, 0.07)), (0.7, (0.04, 0.10, 0.14))], rough=0.08,
                             metallic=0.6, bump=0.0)
    M["red"] = mat_surface("UT_Red", [(0.3, (0.45, 0.03, 0.02)), (0.7, (0.62, 0.06, 0.04))], rough=0.4, bump=0.0)
    M["brass"] = mat_surface("UT_Brass", [(0.3, (0.55, 0.38, 0.12)), (0.7, (0.80, 0.60, 0.22))], noise_scale=9.0,
                             rough=0.28, metallic=1.0, bump=0.03)
    return M


# ---------------------------------------------------------------------------
# mesh helpers

def _finish(ob, col, mat, bevel=0.0, segments=2, smooth=True):
    if mat is not None:
        ob.data.materials.append(mat)
    if smooth:
        for p in ob.data.polygons:
            p.use_smooth = True
    if bevel > 0:
        b = ob.modifiers.new("Bevel", "BEVEL")
        b.width = bevel
        b.segments = segments
        b.limit_method = "ANGLE"
        b.angle_limit = math.radians(40)
        b.harden_normals = False
    if smooth:
        w = ob.modifiers.new("WN", "WEIGHTED_NORMAL")
        w.keep_sharp = True
        w.weight = 50
    col.objects.link(ob)
    return ob


def _obj(name, bm):
    me = bpy.data.meshes.new("UT_" + name)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    return bpy.data.objects.new("UT_" + name, me)


def box(col, name, size, loc, mat, bevel=0.02, rot=(0, 0, 0), segments=2):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts[:])
    ob = _obj(name, bm)
    ob.location = loc
    ob.rotation_euler = rot
    return _finish(ob, col, mat, bevel, segments)


def cyl(col, name, radius, depth, loc, mat, axis="Z", verts=32, bevel=0.01, radius2=None, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts, radius1=radius,
                          radius2=radius if radius2 is None else radius2, depth=depth)
    ob = _obj(name, bm)
    ob.location = loc
    if rot is not None:
        ob.rotation_euler = rot
    elif axis == "X":
        ob.rotation_euler = (0, math.radians(90), 0)
    elif axis == "Y":
        ob.rotation_euler = (math.radians(-90), 0, 0)
    return _finish(ob, col, mat, bevel)


def sphere(col, name, radius, loc, mat, scale=(1, 1, 1), segs=32):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2, radius=radius)
    ob = _obj(name, bm)
    ob.location = loc
    ob.scale = scale
    return _finish(ob, col, mat, 0.0)


def ico(col, name, radius, loc, mat, subdiv=3, scale=(1, 1, 1), smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    ob = _obj(name, bm)
    ob.location = loc
    ob.scale = scale
    return _finish(ob, col, mat, 0.0, smooth=smooth)


def profile_xz(col, name, pts, width, loc, mat, bevel=0.03):
    """Extrude a side profile [(x,z),...] across Y (centred)."""
    bm = bmesh.new()
    a = [bm.verts.new((x, -width / 2, z)) for x, z in pts]
    b = [bm.verts.new((x, width / 2, z)) for x, z in pts]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], b[i], b[j], a[j]))
    ob = _obj(name, bm)
    ob.location = loc
    return _finish(ob, col, mat, bevel)


def prism_xy(col, name, pts, z0, z1, loc, mat, top_scale=1.0, top_shift=(0.0, 0.0), bevel=0.04, segments=2):
    """Extrude a top-view outline [(x,y),...] from z0 to z1 with a tapered top."""
    bm = bmesh.new()
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    ts = top_scale if isinstance(top_scale, (tuple, list)) else (top_scale, top_scale)
    a = [bm.verts.new((x, y, z0)) for x, y in pts]
    b = [bm.verts.new((cx + (x - cx) * ts[0] + top_shift[0], cy + (y - cy) * ts[1] + top_shift[1], z1))
         for x, y in pts]
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    ob = _obj(name, bm)
    ob.location = loc
    return _finish(ob, col, mat, bevel, segments)


def superellipse(rx, ry, n=2.6, count=40, cx=0.0, cy=0.0):
    pts = []
    for i in range(count):
        t = 2 * math.pi * i / count
        c, s = math.cos(t), math.sin(t)
        pts.append((cx + rx * math.copysign(abs(c) ** (2 / n), c), cy + ry * math.copysign(abs(s) ** (2 / n), s)))
    return pts


def stadium_xz(length, height, steps=8):
    """Side profile of a track loop: flat top/bottom, round ends."""
    r = height / 2
    half = length / 2 - r
    pts = []
    for i in range(steps + 1):
        t = -math.pi / 2 + math.pi * i / steps
        pts.append((half + r * math.cos(t), r + r * math.sin(t)))
    for i in range(steps + 1):
        t = math.pi / 2 + math.pi * i / steps
        pts.append((-half + r * math.cos(t), r + r * math.sin(t)))
    return pts


def instance(sc, col, loc=(0, 0, 0), rot_z=0.0, name="inst"):
    e = bpy.data.objects.new("UT_" + name, None)
    e.instance_type = "COLLECTION"
    e.instance_collection = col
    e.location = loc
    e.rotation_euler = (0, 0, rot_z)
    sc.collection.objects.link(e)
    return e


def exclude(sc, col, hide=True):
    """Hide a source collection from the render while keeping it instanceable."""
    def walk(lc):
        if lc.collection == col:
            return lc
        for c in lc.children:
            r = walk(c)
            if r:
                return r
        return None
    for vl in sc.view_layers:
        if vl.layer_collection is None:
            continue
        lc = walk(vl.layer_collection)
        if lc:
            lc.exclude = hide


# ---------------------------------------------------------------------------
# colour-mask rendering

class MaskMaterials:
    """Temporarily swaps materials so team-colour areas render white and everything else black."""

    def __init__(self, cols, paint_names=("UT_Paint", "UT_PaintDark")):
        self.cols = cols
        self.paint = set(paint_names)
        self.saved = []

    def __enter__(self):
        white = mat_emit("UT_MaskWhite", (1, 1, 1))
        black = mat_emit("UT_MaskBlack", (0, 0, 0))
        for col in self.cols:
            for ob in col.all_objects:
                if ob.type != "MESH":
                    continue
                for i, slot in enumerate(ob.material_slots):
                    self.saved.append((ob, i, slot.material))
                    slot.material = white if (slot.material and slot.material.name in self.paint) else black
        return self

    def __exit__(self, *a):
        for ob, i, m in self.saved:
            ob.material_slots[i].material = m


# ---------------------------------------------------------------------------
# shadow catcher + scenery helpers

def mat_shadow_catcher(strength=0.62):
    """Ground material that is invisible where lit and dark-translucent where shadowed (EEVEE only)."""
    m, nt = _mat("UT_ShadowCatcher")
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    d.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    nt.links.new(d.outputs["BSDF"], s2r.inputs["Shader"])
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(s2r.outputs["Color"], bw.inputs["Color"])
    div = nt.nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.name = "UT_SC_Div"
    div.inputs[1].default_value = 3.0
    nt.links.new(bw.outputs["Val"], div.inputs[0])
    ramp = _ramp(nt, div.outputs[0], [(0.22, 1.0), (0.93, 0.0)])
    ramp.name = "UT_SC_Ramp"
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = strength
    nt.links.new(ramp.outputs["Color"], mul.inputs[0])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.0, 0.004, 0.012, 1)
    em.inputs["Strength"].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(mul.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    _out(nt, mix.outputs[0])
    try:
        m.surface_render_method = "BLENDED"
    except Exception:
        m.blend_method = "BLEND"
    return m


def calibrate_catcher(sc, mat, probe_path):
    """Find the catcher's fully-lit brightness so that lit ground renders fully transparent."""
    div = mat.node_tree.nodes["UT_SC_Div"]
    plane = add_catcher(sc, 4.0, mat)
    cam = add_topdown_camera(sc, 2.0, 2.0, 16, 16)
    setup_render(sc, samples=8)
    lo, hi = 0.3, 12.0
    for _ in range(9):
        mid = (lo + hi) / 2
        div.inputs[1].default_value = mid
        render(sc, probe_path)
        img = bpy.data.images.load(probe_path, check_existing=False)
        a = max(img.pixels[3::4])
        bpy.data.images.remove(img)
        if a > 0.004:
            hi = mid      # still shadowed-looking: divisor too large
        else:
            lo = mid
    div.inputs[1].default_value = lo * 0.97
    bpy.data.objects.remove(plane, do_unlink=True)
    bpy.data.objects.remove(cam, do_unlink=True)
    return lo


def add_catcher(sc, size, mat, z=0.0, center=(0.0, 0.0)):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
    ob = _obj("Catcher", bm)
    ob.location = (center[0], center[1], z)
    ob.data.materials.append(mat)
    sc.collection.objects.link(ob)
    ob.visible_shadow = False
    return ob


def displace(ob, strength, scale, kind="CLOUDS", depth=2, mid=0.5, seed=0):
    tex = bpy.data.textures.new("UT_Disp", kind)
    tex.noise_scale = scale
    if hasattr(tex, "noise_depth"):
        tex.noise_depth = depth
    mod = ob.modifiers.new("Disp", "DISPLACE")
    mod.texture = tex
    mod.strength = strength
    mod.mid_level = mid
    mod.texture_coords = "GLOBAL"
    # move the modifier before the weighted-normal one
    idx = list(ob.modifiers).index(mod)
    while idx > 0:
        ob.modifiers.move(idx, idx - 1)
        idx -= 1
    return mod


def subsurf(ob, levels=1):
    mod = ob.modifiers.new("Sub", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels
    idx = list(ob.modifiers).index(mod)
    while idx > 0:
        ob.modifiers.move(idx, idx - 1)
        idx -= 1
    return mod


def grid_mesh(col, name, nx, ny, size_x, size_y, height_fn, mat, cut_below=None, smooth=True):
    """Heightfield mesh; faces whose vertices are all below cut_below are removed."""
    bm = bmesh.new()
    verts = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            x = (i / nx - 0.5) * size_x
            y = (j / ny - 0.5) * size_y
            row.append(bm.verts.new((x, y, height_fn(x, y))))
        verts.append(row)
    for j in range(ny):
        for i in range(nx):
            q = (verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i])
            if cut_below is not None and all(v.co.z <= cut_below for v in q):
                continue
            bm.faces.new(q)
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    ob = _obj(name, bm)
    return _finish(ob, col, mat, 0.0, smooth=smooth)
