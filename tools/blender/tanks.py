"""Tank models for Ultimate Tanks. build_tank(key, M) -> (hull_col, turret_col, meta)."""
import math

SPECS = {
    "basic": dict(
        L=5.2, hull_w=1.9, H=1.05, track_w=0.52, track_h=0.78, pods="single",
        turret=dict(x=0.15, style="round", rx=0.98, ry=0.9, h=0.62),
        barrels=[dict(y=0.0, reach=2.7, r=0.095, brake=False)],
        extras=("boxes",),
    ),
    "medium": dict(
        L=6.2, hull_w=2.2, H=1.15, track_w=0.6, track_h=0.86, pods="single",
        turret=dict(x=0.1, style="angular", rx=1.35, ry=1.02, h=0.7),
        barrels=[dict(y=0.0, reach=3.9, r=0.115, brake=True)],
        extras=("boxes", "skirts", "bustle", "mg"),
    ),
    "heavy": dict(
        L=6.9, hull_w=2.6, H=1.25, track_w=0.7, track_h=0.95, pods="single",
        turret=dict(x=-0.1, style="boxy", rx=1.55, ry=1.25, h=0.78),
        barrels=[dict(y=0.42, reach=4.0, r=0.125, brake=True), dict(y=-0.42, reach=4.0, r=0.125, brake=True)],
        extras=("boxes", "drums", "bustle", "mg", "skirts"),
    ),
    "mammoth": dict(
        L=8.0, hull_w=2.9, H=1.4, track_w=0.95, track_h=1.1, pods="quad",
        turret=dict(x=-0.2, style="boxy", rx=1.85, ry=1.5, h=0.9),
        barrels=[dict(y=0.55, reach=4.7, r=0.155, brake=True), dict(y=-0.55, reach=4.7, r=0.155, brake=True)],
        extras=("drums", "bustle", "mg", "pods", "armor"),
    ),
    "goliath": dict(
        L=9.2, hull_w=3.5, H=1.5, track_w=1.1, track_h=1.2, pods="quad",
        turret=dict(x=-0.3, style="fortress", rx=2.2, ry=1.8, h=1.0),
        barrels=[dict(y=0.0, reach=5.6, r=0.18, brake=True), dict(y=0.85, reach=4.9, r=0.145, brake=True),
                 dict(y=-0.85, reach=4.9, r=0.145, brake=True)],
        extras=("drums", "bustle", "mg", "armor", "pods", "tower"),
    ),
    "speed": dict(
        L=5.6, hull_w=1.7, H=0.85, track_w=0.48, track_h=0.7, pods="single", wedge=True,
        turret=dict(x=-0.55, style="wedge", rx=1.0, ry=0.72, h=0.45),
        barrels=[dict(y=0.0, reach=3.0, r=0.07, brake=False, rotary=True)],
        extras=("spoiler", "intakes"),
    ),
}

ORDER = ["basic", "medium", "heavy", "mammoth", "goliath", "speed"]


def _track_pod(L, col, M, name, x, y, length, width, height, cleat=0.2):
    L.profile_xz(col, name, L.stadium_xz(length, height), width, (x, y, 0.0), M["track"], bevel=0.015)
    # cleats along the top run
    n = int((length - height) / cleat)
    x0 = x - (n - 1) * cleat / 2
    for i in range(n):
        L.box(col, f"{name}_c{i}", (cleat * 0.5, width + 0.05, 0.05), (x0 + i * cleat, y, height + 0.005),
              M["metal"], bevel=0.008, segments=1)
    # guide ridge down the middle of the track
    L.box(col, name + "_ridge", (length - height * 1.1, width * 0.16, 0.03), (x, y, height + 0.035), M["track"],
          bevel=0.005, segments=1)
    # wheels (only visible in the 3/4 preview renders)
    wr = height * 0.36
    nw = max(3, int((length - height) / (wr * 2.15)))
    for i in range(nw):
        wx = x - (nw - 1) * wr * 1.08 + i * wr * 2.16
        side = 1 if y > 0 else -1
        L.cyl(col, f"{name}_w{i}", wr, 0.12, (wx, y + side * (width / 2 + 0.02), wr + 0.04), M["metal"], axis="Y",
              verts=20, bevel=0.01)
        L.cyl(col, f"{name}_h{i}", wr * 0.35, 0.16, (wx, y + side * (width / 2 + 0.03), wr + 0.04), M["paint2"],
              axis="Y", verts=12, bevel=0.005)


def _barrel(L, col, M, name, y, z, reach, r, brake, x0, rotary=False):
    length = reach - x0
    if rotary:
        # six-barrel rotary cannon inside a shroud
        L.cyl(col, name + "_shroud", r * 2.6, length * 0.45, (x0 + length * 0.225, y, z), M["metal"], axis="X",
              bevel=0.01)
        for i in range(6):
            a = i * math.pi / 3
            L.cyl(col, f"{name}_b{i}", r * 0.62, length, (x0 + length / 2, y + math.cos(a) * r * 1.5,
                                                           z + math.sin(a) * r * 1.5), M["steel"], axis="X",
                  verts=12, bevel=0.0)
        for f in (0.55, 0.78, 0.985):
            L.cyl(col, f"{name}_ring{f}", r * 2.45, 0.07, (x0 + length * f, y, z), M["metal"], axis="X", bevel=0.01)
        return
    L.cyl(col, name, r, length, (x0 + length / 2, y, z), M["steel"], axis="X", bevel=0.0)
    L.cyl(col, name + "_sleeve", r * 1.75, length * 0.26, (x0 + length * 0.13, y, z), M["paint2"], axis="X",
          bevel=0.02)
    L.cyl(col, name + "_evac", r * 1.5, length * 0.14, (x0 + length * 0.56, y, z), M["metal"], axis="X", bevel=0.02)
    if brake:
        L.box(col, name + "_brake", (r * 4.6, r * 3.9, r * 2.9), (reach - r * 2.3, y, z), M["metal"], bevel=0.03)
        for dx in (-r * 1.1, r * 1.1):
            L.box(col, f"{name}_slot{dx:.2f}", (r * 1.0, r * 4.2, r * 1.3), (reach - r * 2.3 + dx, y, z), M["black"],
                  bevel=0.0)
    else:
        L.cyl(col, name + "_muzzle", r * 1.45, r * 3.0, (reach - r * 1.5, y, z), M["metal"], axis="X", bevel=0.015)
    L.cyl(col, name + "_bore", r * 0.72, 0.02, (reach + 0.003, y, z), M["black"], axis="X", bevel=0.0)


def _hatch(L, col, M, name, x, y, z, r):
    L.cyl(col, name, r, 0.07, (x, y, z), M["paint2"], bevel=0.015)
    L.cyl(col, name + "_lid", r * 0.78, 0.05, (x, y, z + 0.05), M["paint"], bevel=0.012)
    L.box(col, name + "_hinge", (r * 0.35, r * 0.9, 0.05), (x - r * 0.85, y, z + 0.04), M["metal"], bevel=0.008)
    L.box(col, name + "_grip", (r * 0.12, r * 0.6, 0.04), (x + r * 0.3, y, z + 0.09), M["metal"], bevel=0.005)


def _rivets(L, col, M, name, pts, z, r=0.028):
    for i, (x, y) in enumerate(pts):
        L.ico(col, f"{name}{i}", r, (x, y, z), M["metal"], subdiv=1, scale=(1, 1, 0.6))


def build_tank(L, key, M):
    s = SPECS[key]
    hull = L.new_collection(key + "_hull")
    tur = L.new_collection(key + "_turret")
    Ln, hw, H, tw, th = s["L"], s["hull_w"], s["H"], s["track_w"], s["track_h"]
    ex = s["extras"]
    yt = hw / 2 + tw / 2 + 0.03          # track centre line
    total_w = hw + 2 * tw + 0.06

    # --- tracks ---------------------------------------------------------
    if s["pods"] == "quad":
        pl = Ln * 0.46
        for sx, nx in ((Ln / 2 - pl / 2, "f"), (-Ln / 2 + pl / 2, "r")):
            for sy, ny in ((yt, "l"), (-yt, "r")):
                _track_pod(L, hull, M, f"{key}_trk_{nx}{ny}", sx, sy, pl, tw, th, cleat=0.24)
                # armoured pod housing between the two runs
        for sy in (yt, -yt):
            L.box(hull, f"{key}_podlink{sy:.1f}", (Ln * 0.13, tw * 0.9, th * 0.75), (0, sy, th * 0.5), M["paint2"],
                  bevel=0.05)
    else:
        for sy, ny in ((yt, "l"), (-yt, "r")):
            _track_pod(L, hull, M, f"{key}_trk_{ny}", 0.0, sy, Ln, tw, th)

    # --- hull -----------------------------------------------------------
    zb = 0.32
    hl = Ln * 0.94
    if s.get("wedge"):
        prof = [(-hl / 2, zb), (hl / 2 - 0.2, zb), (hl / 2, zb + 0.14), (hl / 2 - 1.9, H * 0.86), (-hl / 2 + 1.2, H),
                (-hl / 2, H - 0.12)]
    else:
        prof = [(-hl / 2, zb), (hl / 2 - 0.45, zb), (hl / 2, zb + 0.32), (hl / 2 - 1.05, H), (-hl / 2 + 0.35, H),
                (-hl / 2, H - 0.3)]
    L.profile_xz(hull, key + "_hull", prof, hw, (0, 0, 0), M["paint"], bevel=0.05)

    # fenders: full-length inner shelf plus front and rear mudguards over the tracks
    fz = th + 0.08
    for sy in (1, -1):
        if s["pods"] == "quad":
            for sx in (1, -1):
                L.box(hull, f"{key}_fender{sy}{sx}", (Ln * 0.3, tw * 0.62, 0.06),
                      (sx * Ln * 0.27, sy * (hw / 2 + tw * 0.31), fz), M["paint"], bevel=0.02)
                L.box(hull, f"{key}_guard{sy}{sx}", (Ln * 0.12, tw + 0.1, 0.07),
                      (sx * (Ln / 2 - Ln * 0.055), sy * yt, fz), M["paint2"], bevel=0.025)
        else:
            L.box(hull, f"{key}_fender{sy}", (Ln * 0.74, tw * 0.5, 0.05), (-Ln * 0.02, sy * (hw / 2 + tw * 0.25), fz),
                  M["paint"], bevel=0.02)
            L.box(hull, f"{key}_guardf{sy}", (Ln * 0.11, tw + 0.08, 0.06), (Ln / 2 - Ln * 0.07, sy * yt, fz),
                  M["paint2"], bevel=0.025)
            L.box(hull, f"{key}_guardr{sy}", (Ln * 0.08, tw + 0.08, 0.06), (-Ln / 2 + Ln * 0.05, sy * yt, fz),
                  M["paint2"], bevel=0.025)

    # raised superstructure plate under the turret
    tx = s["turret"]["x"]
    L.box(hull, key + "_deck", (Ln * 0.42, hw * 0.94, 0.08), (tx, 0, H + 0.03), M["paint2"], bevel=0.03)
    ring_r = min(s["turret"]["ry"] * 0.86, hw * 0.46)
    L.cyl(hull, key + "_ring", ring_r, 0.1, (tx, 0, H + 0.1), M["metal"], bevel=0.015, verts=48)

    # engine deck: grille frame with louvres, exhausts
    gx = -hl / 2 + Ln * 0.15
    gw = hw * 0.7
    gl = Ln * 0.2
    L.box(hull, key + "_grille", (gl, gw, 0.07), (gx, 0, H + 0.02), M["metal"], bevel=0.015)
    L.box(hull, key + "_grille_in", (gl * 0.88, gw * 0.9, 0.06), (gx, 0, H + 0.035), M["black"], bevel=0.0)
    nl = 9
    for i in range(nl):
        L.box(hull, f"{key}_louvre{i}", (gl * 0.055, gw * 0.9, 0.05), (gx - gl * 0.4 + i * gl * 0.8 / (nl - 1), 0,
                                                                         H + 0.065), M["paint2"], bevel=0.008,
              rot=(0, math.radians(25), 0), segments=1)
    L.box(hull, key + "_grille_spine", (gl * 0.92, 0.07, 0.06), (gx, 0, H + 0.085), M["metal"], bevel=0.01)
    for sy in (1, -1):
        L.cyl(hull, f"{key}_exh{sy}", 0.09, 0.55, (-hl / 2 + 0.2, sy * hw * 0.3, H - 0.05), M["metal"], axis="X",
              bevel=0.01, verts=16)
        L.cyl(hull, f"{key}_exh_in{sy}", 0.06, 0.02, (-hl / 2 - 0.078, sy * hw * 0.3, H - 0.05), M["black"],
              axis="X", bevel=0.0, verts=16)

    # glacis: driver hatch, vision block, headlights, tow hooks, spare track links
    fx = hl / 2 - 1.05
    if not s.get("wedge"):
        _hatch(L, hull, M, key + "_drv", fx - 0.5, hw * 0.24, H + 0.03, min(0.3, hw * 0.13))
        L.box(hull, key + "_vis", (0.1, 0.34, 0.07), (fx - 0.12, hw * 0.24, H + 0.05), M["glass"], bevel=0.01)
        n_links = 4 if hw > 2.0 else 3
        for i in range(n_links):
            L.box(hull, f"{key}_link{i}", (0.3, 0.17, 0.06), (hl / 2 - 0.5, -hw * 0.1 - i * 0.19, zb + 0.56),
                  M["track"], bevel=0.012, rot=(0, math.radians(31), 0))
    for sy in (1, -1):
        L.cyl(hull, f"{key}_lamp_h{sy}", 0.1, 0.14, (hl / 2 - 0.62, sy * hw * 0.4, H - 0.12), M["metal"], axis="X",
              bevel=0.01, verts=16)
        L.cyl(hull, f"{key}_lamp{sy}", 0.08, 0.03, (hl / 2 - 0.545, sy * hw * 0.4, H - 0.12), M["lamp"], axis="X",
              bevel=0.0, verts=16)
        L.box(hull, f"{key}_hook{sy}", (0.16, 0.08, 0.12), (hl / 2 - 0.05, sy * hw * 0.28, zb + 0.22), M["metal"],
              bevel=0.02)
        L.cyl(hull, f"{key}_tail{sy}", 0.05, 0.03, (-hl / 2 - 0.01, sy * hw * 0.42, H - 0.22), M["red"], axis="X",
              bevel=0.0, verts=12)

    # deck rivet lines
    rp = []
    for i in range(int(hl * 0.6 / 0.32)):
        x = -hl * 0.3 + i * 0.32
        rp += [(x, hw / 2 - 0.07), (x, -hw / 2 + 0.07)]
    _rivets(L, hull, M, key + "_rv", rp, H + 0.005)

    if "boxes" in ex:
        L.box(hull, key + "_stow1", (0.9, tw * 0.42, 0.22), (-Ln * 0.16, hw / 2 + tw * 0.25, fz + 0.13), M["paint2"],
              bevel=0.025)
        L.box(hull, key + "_stow1lid", (0.84, tw * 0.36, 0.03), (-Ln * 0.16, hw / 2 + tw * 0.25, fz + 0.25),
              M["paint"], bevel=0.01)
        L.cyl(hull, key + "_roll", 0.11, 0.85, (Ln * 0.14, -(hw / 2 + tw * 0.25), fz + 0.13), M["canvas"], axis="X",
              bevel=0.03, verts=16)
        for dx in (-0.25, 0.25):
            L.box(hull, f"{key}_strap{dx}", (0.05, 0.25, 0.24), (Ln * 0.14 + dx, -(hw / 2 + tw * 0.25), fz + 0.13),
                  M["metal"], bevel=0.005)
        # shovel
        L.cyl(hull, key + "_shaft", 0.022, 0.8, (-Ln * 0.2, -(hw / 2 + tw * 0.2), fz + 0.06), M["wood"], axis="X",
              bevel=0.0, verts=8)
        L.box(hull, key + "_blade", (0.22, 0.16, 0.02), (-Ln * 0.2 + 0.48, -(hw / 2 + tw * 0.2), fz + 0.05),
              M["steel"], bevel=0.006)
    if "skirts" in ex:
        for sy in (1, -1):
            for i in range(4):
                L.box(hull, f"{key}_skirt{sy}{i}", (Ln * 0.17, 0.05, th * 0.55),
                      (-Ln * 0.28 + i * Ln * 0.185, sy * (total_w / 2 + 0.0), th * 0.72), M["paint"], bevel=0.012)
    if "drums" in ex:
        dr = 0.27 if hw < 3 else 0.32
        for sy in (1, -1):
            L.cyl(hull, f"{key}_drum{sy}", dr, hw * 0.4, (-hl / 2 - dr * 0.75, sy * hw * 0.24, H - dr * 0.4),
                  M["paint2"], axis="Y", bevel=0.02, verts=24)
            for dy in (-0.3, 0.3):
                L.cyl(hull, f"{key}_drumband{sy}{dy}", dr + 0.015, 0.05,
                      (-hl / 2 - dr * 0.75, sy * hw * 0.24 + dy * hw * 0.4, H - dr * 0.4), M["metal"], axis="Y",
                      bevel=0.005, verts=24)
    if "armor" in ex:
        # bolted appliqué plates on the glacis and hull sides
        for sy in (1, -1):
            L.box(hull, f"{key}_app{sy}", (Ln * 0.3, 0.09, H * 0.42), (Ln * 0.02, sy * (hw / 2 + 0.03), H * 0.72),
                  M["paint2"], bevel=0.02)
            L.box(hull, f"{key}_gl{sy}", (0.5, hw * 0.3, 0.07), (hl / 2 - 1.5, sy * hw * 0.26, H + 0.03), M["paint2"],
                  bevel=0.02)
            _rivets(L, hull, M, f"{key}_glrv{sy}", [(hl / 2 - 1.5 + a, sy * hw * 0.26 + b) for a in (-0.18, 0.18)
                                                    for b in (-hw * 0.11, hw * 0.11)], H + 0.07, r=0.035)
    if "spoiler" in ex:
        for sy in (1, -1):
            L.box(hull, f"{key}_fin{sy}", (0.55, 0.06, 0.34), (-hl / 2 + 0.3, sy * hw * 0.4, H + 0.17), M["paint2"],
                  bevel=0.015)
        L.box(hull, key + "_wing", (0.46, hw * 1.25, 0.05), (-hl / 2 + 0.22, 0, H + 0.36), M["paint"], bevel=0.02)
    if "intakes" in ex:
        for sy in (1, -1):
            L.box(hull, f"{key}_intake{sy}", (1.2, 0.26, 0.2), (0.25, sy * (hw / 2 - 0.16), H * 0.92), M["paint2"],
                  bevel=0.04, rot=(0, math.radians(-7), 0))
            L.box(hull, f"{key}_intake_in{sy}", (0.04, 0.2, 0.13), (0.85, sy * (hw / 2 - 0.16), H * 0.86), M["black"],
                  bevel=0.0)
        L.box(hull, key + "_stripe_h", (hl * 0.36, 0.2, 0.012), (hl / 2 - 1.9, 0, H * 0.62), M["stripe"],
              bevel=0.0, rot=(0, math.atan2(H * 0.86 - 0.46, hl - 3.1) * 0 + math.radians(18.5), 0))

    # --- turret (local origin = pivot) ------------------------------------
    t = s["turret"]
    rx, ry, h = t["rx"], t["ry"], t["h"]
    z0 = H + 0.15
    style = t["style"]
    if style == "round":
        L.prism_xy(tur, key + "_tur", L.superellipse(rx, ry, 2.3, 44, cx=-0.08), z0, z0 + h, (0, 0, 0), M["paint"],
                   top_scale=0.74, top_shift=(-0.08, 0), bevel=0.09, segments=3)
    elif style == "angular":
        pts = [(rx, ry * 0.42), (rx * 0.55, ry), (-rx * 0.75, ry), (-rx * 1.05, ry * 0.6), (-rx * 1.05, -ry * 0.6),
               (-rx * 0.75, -ry), (rx * 0.55, -ry), (rx, -ry * 0.42)]
        L.prism_xy(tur, key + "_tur", pts, z0, z0 + h, (0, 0, 0), M["paint"], top_scale=(0.8, 0.72), bevel=0.06)
    elif style == "boxy":
        pts = [(rx, ry * 0.62), (rx * 0.72, ry), (-rx * 0.9, ry), (-rx * 1.1, ry * 0.7), (-rx * 1.1, -ry * 0.7),
               (-rx * 0.9, -ry), (rx * 0.72, -ry), (rx, -ry * 0.62)]
        L.prism_xy(tur, key + "_tur", pts, z0, z0 + h, (0, 0, 0), M["paint"], top_scale=(0.86, 0.8), bevel=0.07)
        for sy in (1, -1):
            L.box(tur, f"{key}_cheek{sy}", (rx * 1.1, 0.1, h * 0.62), (-rx * 0.05, sy * (ry * 0.96), z0 + h * 0.42),
                  M["paint2"], bevel=0.02, rot=(sy * math.radians(-12), 0, 0))
    elif style == "fortress":
        pts = [(rx, ry * 0.7), (rx * 0.78, ry), (-rx * 0.85, ry), (-rx * 1.08, ry * 0.72), (-rx * 1.08, -ry * 0.72),
               (-rx * 0.85, -ry), (rx * 0.78, -ry), (rx, -ry * 0.7)]
        L.prism_xy(tur, key + "_tur", pts, z0, z0 + h * 0.7, (0, 0, 0), M["paint"], top_scale=(0.9, 0.86),
                   bevel=0.08)
        pts2 = [(rx * 0.62, ry * 0.42), (rx * 0.4, ry * 0.62), (-rx * 0.7, ry * 0.62), (-rx * 0.82, ry * 0.4),
                (-rx * 0.82, -ry * 0.4), (-rx * 0.7, -ry * 0.62), (rx * 0.4, -ry * 0.62), (rx * 0.62, -ry * 0.42)]
        L.prism_xy(tur, key + "_tur2", pts2, z0 + h * 0.66, z0 + h * 1.15, (0, 0, 0), M["paint2"],
                   top_scale=(0.86, 0.82), bevel=0.06)
        for sy in (1, -1):
            L.box(tur, f"{key}_cheek{sy}", (rx * 1.3, 0.12, h * 0.5), (-rx * 0.05, sy * (ry * 0.97), z0 + h * 0.34),
                  M["paint2"], bevel=0.02, rot=(sy * math.radians(-8), 0, 0))
            _rivets(L, tur, M, f"{key}_chrv{sy}", [(-rx * 0.55 + i * rx * 0.36, sy * ry * 0.9) for i in range(4)],
                    z0 + h * 0.66, r=0.04)
    elif style == "wedge":
        pts = [(rx * 1.15, ry * 0.25), (rx * 0.3, ry), (-rx * 0.9, ry * 0.85), (-rx, ry * 0.4), (-rx, -ry * 0.4),
               (-rx * 0.9, -ry * 0.85), (rx * 0.3, -ry), (rx * 1.15, -ry * 0.25)]
        L.prism_xy(tur, key + "_tur", pts, z0, z0 + h, (0, 0, 0), M["paint"], top_scale=(0.7, 0.62),
                   top_shift=(-0.14, 0), bevel=0.05)
        L.box(tur, key + "_canopy", (0.7, 0.5, 0.1), (-0.12, 0, z0 + h + 0.01), M["glass"], bevel=0.04)
        L.box(tur, key + "_feed", (0.6, 0.3, 0.26), (-rx * 0.55, -ry * 0.62, z0 + h * 0.55), M["metal"], bevel=0.03)
    top = z0 + h * (1.15 if style == "fortress" else 1.0)

    # mantlet + barrels
    bz = z0 + h * (0.42 if style != "fortress" else 0.36)
    span = max(abs(b["y"]) for b in s["barrels"]) * 2 + s["barrels"][0]["r"] * 7
    mant_x = rx * (0.92 if style != "wedge" else 1.0)
    L.box(tur, key + "_mantlet", (rx * 0.3, max(span, ry * 0.55), h * 0.62), (mant_x, 0, bz), M["paint2"],
          bevel=0.05)
    muzzles = []
    for i, b in enumerate(s["barrels"]):
        z = bz + (0.1 if (style == "fortress" and b["y"] == 0) else 0.0)
        _barrel(L, tur, M, f"{key}_bar{i}", b["y"], z, b["reach"], b["r"], b["brake"], mant_x,
                rotary=b.get("rotary", False))
        muzzles.append([b["reach"], b["y"]])

    # roof furniture
    if style != "wedge":
        cup_y = ry * 0.36
        cr = min(0.34, ry * 0.3)
        L.cyl(tur, key + "_cup", cr, 0.16, (-rx * 0.3, cup_y, top + 0.05), M["paint2"], bevel=0.02)
        for i in range(6):
            a = i * math.pi / 3 + 0.3
            L.box(tur, f"{key}_peri{i}", (0.1, 0.05, 0.05), (-rx * 0.3 + math.cos(a) * cr * 0.95,
                                                             cup_y + math.sin(a) * cr * 0.95, top + 0.12),
                  M["glass"], bevel=0.005, rot=(0, 0, a + math.pi / 2), segments=1)
        _hatch(L, tur, M, key + "_cuph", -rx * 0.3, cup_y, top + 0.14, cr * 0.8)
        _hatch(L, tur, M, key + "_ldr", -rx * 0.22, -ry * 0.36, top + 0.01, cr * 0.82)
        # gunner sight + ventilator
        L.box(tur, key + "_sight", (0.2, 0.16, 0.1), (rx * 0.38, ry * 0.34, top + 0.03), M["metal"], bevel=0.02)
        L.box(tur, key + "_sightg", (0.02, 0.11, 0.05), (rx * 0.38 + 0.1, ry * 0.34, top + 0.04), M["glass"],
              bevel=0.0)
        L.cyl(tur, key + "_vent", 0.12, 0.06, (rx * 0.12, -ry * 0.05, top + 0.01), M["metal"], bevel=0.02, verts=20)
        # ID stripe across the rear of the roof
        L.box(tur, key + "_stripe", (0.16, ry * 1.15, 0.012), (-rx * 0.66, 0, top + 0.004), M["stripe"], bevel=0.0)
        # antenna
        L.cyl(tur, key + "_ant_b", 0.045, 0.1, (-rx * 0.8, -ry * 0.5, top + 0.03), M["metal"], bevel=0.01, verts=12)
        L.cyl(tur, key + "_ant", 0.012, 1.3, (-rx * 0.8 - 0.2, -ry * 0.5 - 0.12, top + 0.65), M["metal"], bevel=0.0,
              verts=6, rot=(math.radians(10), math.radians(-18), 0))
        _rivets(L, tur, M, key + "_trv", [(rx * 0.6 * math.cos(a), ry * 0.6 * math.sin(a))
                                           for a in [i * math.pi / 7 for i in range(14)]][3:11], top + 0.002)
    if "bustle" in ex:
        L.box(tur, key + "_bustle", (rx * 0.42, ry * 1.5, h * 0.55), (-rx * 1.22, 0, z0 + h * 0.5), M["paint2"],
              bevel=0.04)
        for i in range(3):
            L.box(tur, f"{key}_bustle_r{i}", (rx * 0.44, 0.04, h * 0.58), (-rx * 1.22, (i - 1) * ry * 0.5,
                                                                            z0 + h * 0.5), M["metal"], bevel=0.008)
        L.box(tur, key + "_tarp", (rx * 0.32, ry * 1.2, 0.14), (-rx * 1.22, 0, z0 + h * 0.82), M["canvas"],
              bevel=0.06, segments=3)
    if "mg" in ex and style != "wedge":
        mx, my = -rx * 0.3 + 0.1, ry * 0.36
        L.box(tur, key + "_mg_body", (0.5, 0.09, 0.1), (mx + 0.2, my + 0.36, top + 0.3), M["metal"], bevel=0.015)
        L.cyl(tur, key + "_mg_bar", 0.022, 0.75, (mx + 0.8, my + 0.36, top + 0.31), M["steel"], axis="X", bevel=0.0,
              verts=8)
        L.box(tur, key + "_mg_ammo", (0.18, 0.14, 0.14), (mx + 0.15, my + 0.5, top + 0.26), M["canvas"], bevel=0.015)
        L.cyl(tur, key + "_mg_post", 0.03, 0.26, (mx + 0.15, my + 0.36, top + 0.16), M["metal"], bevel=0.0, verts=8)
    if "pods" in ex:
        for sy in (1, -1):
            px, py = -rx * 0.35, sy * (ry + 0.38)
            L.box(tur, f"{key}_pod{sy}", (1.5, 0.62, 0.5), (px, py, z0 + h * 0.62), M["paint2"], bevel=0.05)
            L.box(tur, f"{key}_podarm{sy}", (0.4, 0.3, 0.2), (px, sy * (ry + 0.03), z0 + h * 0.55), M["metal"],
                  bevel=0.03)
            for iy in (-1, 1):
                for iz in (-1, 1):
                    L.cyl(tur, f"{key}_tube{sy}{iy}{iz}", 0.1, 0.04, (px + 0.755, py + iy * 0.15,
                                                                      z0 + h * 0.62 + iz * 0.12), M["black"],
                          axis="X", bevel=0.0, verts=14)
                    L.cyl(tur, f"{key}_tip{sy}{iy}{iz}", 0.07, 0.1, (px + 0.76, py + iy * 0.15,
                                                                     z0 + h * 0.62 + iz * 0.12), M["red"],
                          axis="X", bevel=0.0, verts=14, radius2=0.02)
            L.box(tur, f"{key}_podstripe{sy}", (0.16, 0.63, 0.012), (px - 0.4, py, z0 + h * 0.62 + 0.252),
                  M["stripe"], bevel=0.0)
    if "tower" in ex:
        L.cyl(tur, key + "_radar_b", 0.2, 0.3, (-rx * 0.62, 0, top + 0.12), M["metal"], bevel=0.03, verts=20)
        L.box(tur, key + "_radar", (0.12, 1.1, 0.4), (-rx * 0.62, 0, top + 0.45), M["paint2"], bevel=0.03,
              rot=(0, math.radians(-12), math.radians(20)))
        L.box(tur, key + "_radar_f", (0.02, 1.0, 0.3), (-rx * 0.62 + 0.065, 0.02, top + 0.46), M["metal"],
              bevel=0.0, rot=(0, math.radians(-12), math.radians(20)))
    if style != "wedge":
        # smoke dischargers on the turret cheeks
        for sy in (1, -1):
            for i in range(3):
                L.cyl(tur, f"{key}_smk{sy}{i}", 0.05, 0.2, (rx * 0.42 + i * 0.03, sy * (ry * 0.78 + i * 0.1),
                                                            z0 + h * 0.86), M["metal"], bevel=0.008, verts=10,
                      rot=(sy * math.radians(-50), math.radians(60), 0))

    reach = max(b["reach"] for b in s["barrels"])
    side = ry + (1.1 if "pods" in ex else 0.3)
    back = rx * 1.5
    meta = dict(
        length=Ln, width=total_w, turret_x=tx, muzzles=muzzles,
        hull_radius=math.hypot(Ln / 2 + 0.75, total_w / 2 + 0.1),
        turret_radius=max(reach + 0.15, math.hypot(back, side)),
    )
    return hull, tur, meta
