"""Player profiles (career saves) and saved single-player battles, stored as JSON in the saves/ folder."""
import json
import os
import re
import time

from . import data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVES = os.path.join(ROOT, "saves")


def _slug(name):
    return re.sub(r"[^a-z0-9_-]+", "_", name.lower()).strip("_") or "player"


class Profile:
    def __init__(self, name="Player"):
        self.name = name
        self.color = list(data.COLORS[3][1])
        self.credits = 0
        self.tanks = ["basic"]
        self.weapons = ["basic_shell", "tracer"]
        self.tank = "basic"
        self.upgrades = {}           # tank key -> [engine, armour, loader] levels
        self.kills = 0
        self.deaths = 0
        self.battles = 0
        self.wins = 0
        self.created = time.time()
        self.settings = dict(sound=0.7, fullscreen=False)
        self.last_setup = {}
        self.last_host = "127.0.0.1"

    # -- persistence -------------------------------------------------------
    @property
    def path(self):
        return os.path.join(SAVES, "profile_%s.json" % _slug(self.name))

    @property
    def battle_path(self):
        return os.path.join(SAVES, "battle_%s.json" % _slug(self.name))

    def to_dict(self):
        return dict(self.__dict__)

    def save(self):
        """Write the profile. Never raises: a save that fails (file briefly locked by a virus scanner or a
        sync client) is retried, and at worst skipped until the next save."""
        text = json.dumps(self.to_dict(), indent=1)
        tmp = self.path + ".tmp"
        try:
            os.makedirs(SAVES, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError:
            return False
        for attempt in range(6):
            try:
                os.replace(tmp, self.path)
                return True
            except OSError:
                time.sleep(0.02 * (attempt + 1))
        try:                                    # last resort: overwrite in place
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(text)
            os.remove(tmp)
            return True
        except OSError:
            return False

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        p = cls(d.get("name", "Player"))
        for k, v in d.items():
            if k == "settings":
                p.settings.update(v)
            elif hasattr(p, k):
                setattr(p, k, v)
        p.validate()
        return p

    def validate(self):
        self.upgrades = data.clean_upgrades(self.upgrades)
        self.tanks = [t for t in self.tanks if t in data.TANK_INDEX] or ["basic"]
        self.weapons = [w for w in self.weapons if w in data.WEAPON_INDEX]
        for w in ("basic_shell", "tracer"):
            if w not in self.weapons:
                self.weapons.append(w)
        if "basic" not in self.tanks:
            self.tanks.insert(0, "basic")
        if self.tank not in self.tanks or not data.usable(self.tank, self.weapons):
            self.tank = "basic"

    def delete(self):
        for p in (self.path, self.battle_path):
            if os.path.exists(p):
                os.remove(p)

    # -- shop ----------------------------------------------------------------
    def buy_tank(self, key):
        t = data.TANKS[data.TANK_INDEX[key]]
        if key in self.tanks or self.credits < t["cost"]:
            return False
        self.credits -= t["cost"]
        self.tanks.append(key)
        return True

    def buy_weapon(self, key):
        w = data.WEAPONS[data.WEAPON_INDEX[key]]
        if key in self.weapons or self.credits < w["cost"]:
            return False
        self.credits -= w["cost"]
        self.weapons.append(key)
        return True

    def buy_upgrade(self, tank_key, kind):
        if tank_key not in self.tanks:
            return False
        lv = self.upgrades.get(tank_key, [0] * len(data.UPGRADES))
        if lv[kind] >= data.UPGRADE_MAX:
            return False
        cost = data.upgrade_cost(tank_key, lv[kind] + 1)
        if self.credits < cost:
            return False
        self.credits -= cost
        lv = list(lv)
        lv[kind] += 1
        self.upgrades[tank_key] = lv
        return True

    def loadout(self):
        """What a battle needs to know about this player."""
        return dict(name=self.name, color=list(self.color), credits=self.credits, tanks=list(self.tanks),
                    weapons=list(self.weapons), tank=self.tank,
                    upgrades={k: list(v) for k, v in self.upgrades.items()})

    def absorb(self, state):
        """Copy battle results (credits, purchases) back into the profile."""
        self.credits = int(state["credits"])
        self.tanks = list(state["tanks"])
        self.weapons = list(state["weapons"])
        self.tank = state["tank"]
        if "upgrades" in state:
            self.upgrades = {k: list(v) for k, v in state["upgrades"].items()}
        self.validate()

    # -- saved battle ----------------------------------------------------------
    def has_battle(self):
        return os.path.exists(self.battle_path)

    def save_battle(self, d):
        try:
            os.makedirs(SAVES, exist_ok=True)
            with open(self.battle_path, "w", encoding="utf-8") as f:
                json.dump(d, f)
            return True
        except OSError:
            return False

    def load_battle(self):
        with open(self.battle_path, encoding="utf-8") as f:
            return json.load(f)

    def clear_battle(self):
        try:
            if os.path.exists(self.battle_path):
                os.remove(self.battle_path)
        except OSError:
            pass


def list_profiles():
    out = []
    if os.path.isdir(SAVES):
        for f in sorted(os.listdir(SAVES)):
            if f.startswith("profile_") and f.endswith(".json"):
                try:
                    out.append(Profile.load(os.path.join(SAVES, f)))
                except (OSError, ValueError):
                    pass
    return out


def last_profile_name():
    p = os.path.join(SAVES, "last.txt")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    return None


def set_last_profile(name):
    os.makedirs(SAVES, exist_ok=True)
    try:
        with open(os.path.join(SAVES, "last.txt"), "w", encoding="utf-8") as f:
            f.write(name)
    except OSError:
        pass
