"""Game data: weapons, tanks, colours and tuning constants. Edit numbers here to rebalance the game."""

PPM = 20                    # pixels per metre (matches the Blender renders)
MAP_W, MAP_H = 8000, 6000   # world size in pixels (400 m x 300 m)
CELL = 20                   # collision grid cell size in pixels
NAV = 80                    # AI navigation cell size in pixels

HP_PER_STRENGTH = 4.0       # a tank's hit points = strength * this
SPEED_PX = 14.0             # top speed in px/s = speed stat * this
AUTO_DPS = 0.4              # automatic weapons deal (damage stat * this) per second of sustained hits
RESPAWN_TIME = 4.0
TREE_CRUSH_STRENGTH = 12    # tanks this strong (Heavy and up) knock trees down; any tank flattens bushes
FIRE_ARC = 0.1              # a player's gun only fires once the turret is within this many radians of the cursor
SPAWN_SHIELD = 2.5
WIN_BONUS, LOSS_BONUS = 30, 10
DEFAULT_PORT = 27877
MODES = [("tdm", "Team Deathmatch"), ("ctf", "Capture the Flag")]
FLAG_RETURN_TIME = 30.0     # a dropped flag goes home by itself after this many seconds
FLAG_CARRIER_SPEED = 1.0    # speed multiplier while carrying a flag (1.0 = no penalty)
FLAG_CARRIER_ARMOR = 0.65   # a flag carrier takes this fraction of normal damage
CTF_RESPAWN_TIME = 9.0      # longer than deathmatch, so a successful attack has time to get away
CTF_RESPAWNS = 2            # in Capture the Flag a tank comes back this many times, then it is out
CAPTURE_REWARD = 40         # credits for bringing the enemy flag home
RETURN_REWARD = 10          # credits for touching your own dropped flag to send it home
DISCOVERY_PORT = 27878       # UDP: how the Join screen finds games on the local network

SHELL, AUTO = 0, 1          # weapon slots: left mouse fires the cannon, right mouse the machine gun


def _w(key, name, damage, reload, cost, slot, speed, rng, **kw):
    d = dict(key=key, name=name, damage=damage, reload=reload, cost=cost, slot=slot, speed=speed, range=rng,
             rate=0.0, spread=0.0, pellets=1, hit=float(damage), splash=0, splash_frac=0.0, zone=None,
             hurts_all=False, glow=None, size=1.0, shake=0.0, desc="")
    d.update(kw)
    if slot == AUTO:
        d["hit"] = damage * AUTO_DPS / d["rate"]
    return d


# "damage" and "reload" are the numbers shown to the player. Shells do `damage` per hit; automatic weapons
# (reload 0) spread their damage over a stream of bullets.
WEAPONS = [
    _w("basic_shell", "Basic Shell", 5, 4.0, 0, SHELL, 900, 1300, splash=45, splash_frac=0.4, shake=3,
       desc="Standard armour-piercing round."),
    _w("tracer", "Tracer", 3, 0.0, 0, AUTO, 1300, 1000, rate=6.0, spread=0.0, glow=(255, 220, 90),
       desc="Accurate automatic fire. Long reach."),
    _w("gatling", "Gatling", 6, 0.0, 20, AUTO, 1150, 760, rate=12.0, spread=2.0, glow=(255, 190, 110),
       desc="Rotary cannon. Fast, loose, short range."),
    _w("heavy_shell", "Heavy Shell", 10, 4.0, 40, SHELL, 950, 1400, splash=70, splash_frac=0.5, shake=5, size=1.15,
       desc="Big bore round with a wide blast."),
    _w("combust_shell", "Combust Shell", 11, 3.0, 80, SHELL, 900, 1300, splash=90, splash_frac=0.5, shake=5,
       zone=("fire", 115, 10.0, 1.6), glow=(255, 130, 40), size=1.15,
       desc="Spreads fire that burns everything nearby for 10 seconds."),
    _w("heavy_tracer", "Heavy Tracer", 6, 0.0, 70, AUTO, 1400, 1150, rate=6.0, spread=0.0, glow=(255, 80, 60),
       size=1.2, desc="Hard-hitting, precise automatic fire."),
    _w("heavy_gatling", "Heavy Gatling", 10, 0.0, 100, AUTO, 1200, 850, rate=12.0, spread=1.8, glow=(140, 190, 255),
       size=1.2, desc="A storm of heavy slugs."),
    _w("canister", "Canister", 10, 4.0, 50, SHELL, 1000, 650, pellets=5, spread=11.0, hit=2.6, shake=4,
       desc="Five shells at once in a spreading fan. Brutal up close."),
    _w("death_shell", "Death Shell", 15, 5.0, 130, SHELL, 1000, 1500, splash=120, splash_frac=0.6, shake=8,
       glow=(190, 90, 255), size=1.25, desc="Annihilates whatever it touches."),
    _w("nuke_shell", "Nuke Shell", 20, 6.0, 200, SHELL, 700, 1500, splash=300, splash_frac=1.0, hurts_all=True,
       shake=22, zone=("fallout", 300, 15.0, 1.2), glow=(170, 255, 90), size=1.0,
       desc="Levels the area and leaves radioactive fallout. Keep your distance."),
]
WEAPON_INDEX = {w["key"]: i for i, w in enumerate(WEAPONS)}


def _t(key, name, cost, speed, strength, weapons, radius, turn, traverse, reward, desc):
    # Every tank can carry every weapon. (The `weapons` argument is each tank's original restricted list,
    # kept here in case restrictions are ever wanted again: use `weapons=weapons` below.)
    return dict(key=key, name=name, cost=cost, speed=speed, strength=strength,
                weapons=list(range(len(WEAPONS))), radius=radius,
                turn=turn, traverse=traverse, reward=reward, desc=desc,
                crush_trees=strength >= TREE_CRUSH_STRENGTH)


def _span(a, b):
    return list(range(WEAPON_INDEX[a], WEAPON_INDEX[b] + 1))


TANKS = [
    _t("basic", "Basic Tank", 0, 12, 5, _span("basic_shell", "gatling"), 38, 130, 200, 15,
       "The tank everyone starts with. One barrel."),
    _t("medium", "Medium Tank", 60, 10, 8, _span("basic_shell", "combust_shell"), 44, 110, 170, 25,
       "A solid all-rounder with a long gun."),
    _t("heavy", "Heavy Tank", 100, 8, 12, _span("gatling", "canister"), 50, 90, 140, 35,
       "Two barrels, so every shot is two shells. Thick armour."),
    _t("mammoth", "Mammoth Tank", 150, 6, 16, _span("combust_shell", "death_shell"), 58, 70, 115, 50,
       "Twin heavy cannons on four track pods: two shells per shot."),
    _t("goliath", "Goliath Tank", 200, 6, 20, _span("combust_shell", "nuke_shell"), 64, 60, 100, 65,
       "Three barrels: every shot is three shells. The toughest tank there is."),
    _t("speed", "Speed Tank", 60, 20, 4, [WEAPON_INDEX[k] for k in ("tracer", "gatling", "heavy_tracer",
                                                                    "heavy_gatling")], 38, 190, 260, 25,
       "Blisteringly fast scout with a rotary cannon and paper-thin armour."),
]
TANK_INDEX = {t["key"]: i for i, t in enumerate(TANKS)}

COLORS = [
    ("Olive", (104, 122, 62)), ("Forest", (54, 118, 64)), ("Desert", (200, 168, 108)), ("Steel", (74, 116, 178)),
    ("Navy", (48, 68, 130)), ("Crimson", (176, 46, 42)), ("Orange", (218, 124, 38)), ("Gold", (216, 188, 50)),
    ("Violet", (128, 76, 166)), ("Teal", (42, 146, 140)), ("Arctic", (218, 220, 216)), ("Charcoal", (76, 78, 86)),
    ("Rose", (212, 104, 152)), ("Lime", (132, 196, 60)),
]
TEAM_NAMES = ("Blue Force", "Red Force")
TEAM_UI = ((90, 160, 255), (255, 96, 80))
AI_COLORS = (
    [(74, 116, 178), (48, 68, 130), (42, 146, 140), (86, 132, 150), (60, 96, 160)],
    [(176, 46, 42), (150, 60, 40), (190, 80, 50), (140, 40, 60), (200, 100, 60)],
)
AI_NAMES = ["Viper", "Brick", "Anvil", "Rhino", "Ghost", "Havoc", "Tusk", "Bolt", "Mako", "Grit", "Onyx", "Fang",
            "Sabre", "Diesel", "Crow", "Ridge", "Flint", "Bishop", "Talon", "Hammer", "Ox", "Jinx", "Cobra", "Zed",
            "Piston", "Wolf", "Mamba", "Torque", "Raptor", "Slab", "Ember", "Kodiak", "Lynx", "Gauge", "Pike",
            "Storm", "Badger", "Rivet", "Drake", "Maul", "Shrike", "Bison"]
DIFFICULTIES = ["Easy", "Normal", "Hard"]
MAPS = [
    dict(key="valley", name="River Valley", desc="A river splits the field. Fight for the bridges and fords."),
    dict(key="highlands", name="Highlands", desc="Mountain passes, boulders and pine forest. No river."),
    dict(key="farmland", name="Farmland", desc="Open fields, villages and a shallow stream."),
]


# --- AI opposition scales with the player's garage -------------------------------------------------
# A player's tier is the best tank they own. AI tanks (both teams) start the battle with this mix of tanks;
# percentages per tier, best tank first. The last row is the line-up a Goliath owner faces.
TANK_TIER = dict(basic=0, medium=1, speed=1, heavy=2, mammoth=3, goliath=4)
AI_MIX = [
    [("basic", 100)],
    [("medium", 25), ("speed", 15), ("basic", 60)],
    [("heavy", 20), ("speed", 20), ("medium", 25), ("basic", 35)],
    [("mammoth", 25), ("heavy", 20), ("speed", 20), ("medium", 15), ("basic", 20)],
    [("goliath", 30), ("mammoth", 20), ("speed", 20), ("medium", 10), ("heavy", 10), ("basic", 10)],
]
# what an AI driving each tank starts with, on top of the two free weapons
AI_KIT = dict(basic=[], medium=["gatling", "heavy_shell"], speed=["gatling", "heavy_tracer"],
              heavy=["heavy_shell", "heavy_gatling"], mammoth=["combust_shell", "heavy_gatling"],
              goliath=["death_shell", "heavy_gatling"])


def player_tier(tanks_owned):
    return max([TANK_TIER.get(k, 0) for k in tanks_owned] or [0])


def ai_lineup(tier, count):
    """Exactly `count` tank keys in the tier's proportions (largest-remainder rounding), best tanks first."""
    mix = AI_MIX[max(0, min(len(AI_MIX) - 1, tier))]
    exact = [(key, pct * count / 100.0) for key, pct in mix]
    out = {key: int(q) for key, q in exact}
    left = count - sum(out.values())
    for key, q in sorted(exact, key=lambda kq: -(kq[1] - int(kq[1])))[:left]:
        out[key] += 1
    return [key for key, _pct in mix for _ in range(out[key])]


def tank_hp(t):
    return t["strength"] * HP_PER_STRENGTH


def tank_speed(t):
    return t["speed"] * SPEED_PX


def usable(tank_key, weapons_owned, slot=None):
    """Weapon indices this tank can fire out of the ones the player owns."""
    allowed = TANKS[TANK_INDEX[tank_key]]["weapons"]
    return [i for i in allowed if WEAPONS[i]["key"] in weapons_owned and (slot is None or WEAPONS[i]["slot"] == slot)]
