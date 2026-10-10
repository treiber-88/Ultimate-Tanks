"""Multiplayer plumbing and the two kinds of battle session.

The host simulates everything and streams snapshots (20 per second) plus events over TCP; clients send their
controls and draw an interpolated mirror of the host's world. Messages are newline-delimited JSON.
"""
import json
import math
import queue
import socket
import threading
import time

from . import data
from .data import TANKS, TANK_INDEX, WEAPON_INDEX
from .world import World, angle_diff

SNAP_RATE = 20.0
DISCOVER, FOUND = b"UTANKS?", b"UTANKS!"
INPUT_RATE = 30.0
MAX_HUMANS = 16


class Conn:
    """One TCP connection with a reader thread. Incoming messages land in `inbox`."""

    def __init__(self, sock, inbox, cid):
        self.sock = sock
        self.cid = cid
        self.inbox = inbox
        self.alive = True
        self.lock = threading.Lock()
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(None)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buf = b""
        try:
            while self.alive:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > 4_000_000:
                    break
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if isinstance(msg, dict):
                        self.inbox.put((self.cid, msg))
        except OSError:
            pass
        self.alive = False
        self.inbox.put((self.cid, {"t": "_drop"}))

    def send(self, msg):
        if not self.alive:
            return
        raw = (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            with self.lock:
                self.sock.sendall(raw)
        except OSError:
            self.alive = False

    def close(self):
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


class Server:
    def __init__(self, port):
        self.inbox = queue.Queue()
        self.conns = {}
        self._next = 1
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", port))
        self.sock.listen(8)
        self.port = port
        self.open = True
        self.info = dict(name="?", map="", players=1)       # shown to people browsing for games
        threading.Thread(target=self._accept, daemon=True).start()
        self.udp = None
        try:
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp.bind(("", data.DISCOVERY_PORT))
            threading.Thread(target=self._answer, daemon=True).start()
        except OSError:
            self.udp = None                                  # discovery is a convenience; hosting still works

    def _answer(self):
        """Reply to "who is hosting?" broadcasts from Join screens on the local network."""
        while self.open:
            try:
                msg, addr = self.udp.recvfrom(256)
            except OSError:
                break
            if msg.startswith(DISCOVER):
                reply = dict(self.info, port=self.port)
                try:
                    self.udp.sendto(FOUND + json.dumps(reply, separators=(",", ":")).encode("utf-8"), addr)
                except OSError:
                    pass

    def _accept(self):
        while self.open:
            try:
                s, _addr = self.sock.accept()
            except OSError:
                break
            cid = self._next
            self._next += 1
            self.conns[cid] = Conn(s, self.inbox, cid)

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                return out

    def send(self, cid, msg):
        c = self.conns.get(cid)
        if c:
            c.send(msg)

    def drop(self, cid):
        c = self.conns.pop(cid, None)
        if c:
            c.close()

    def close(self):
        self.open = False
        for s in (self.sock, self.udp):
            try:
                if s:
                    s.close()
            except OSError:
                pass
        for c in list(self.conns.values()):
            c.close()
        self.conns.clear()


class Finder:
    """Looks for games on the local network: broadcasts a question, hosts answer. Used by the Join screen."""

    def __init__(self):
        self.games = {}          # (ip, port) -> (info, last heard)
        self.last = 0.0
        self.sock = None
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.sock.bind(("", 0))
            self.sock.setblocking(False)
        except OSError:
            self.sock = None

    def poll(self):
        """Call every frame. Returns [(ip, port, info)] for games heard from in the last few seconds."""
        now = time.time()
        if self.sock:
            if now - self.last > 1.0:
                self.last = now
                targets = {"255.255.255.255", "127.0.0.1"}
                for ip in local_addresses():                 # also each adapter's own subnet broadcast
                    targets.add(ip.rsplit(".", 1)[0] + ".255")
                for t in targets:
                    try:
                        self.sock.sendto(DISCOVER, (t, data.DISCOVERY_PORT))
                    except OSError:
                        pass
            while True:
                try:
                    msg, addr = self.sock.recvfrom(1024)
                except OSError:
                    break
                if msg.startswith(FOUND):
                    try:
                        info = json.loads(msg[len(FOUND):].decode("utf-8"))
                        port = int(info["port"])
                    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                        continue
                    self.games[(addr[0], port)] = (info, now)
        self.games = {k: v for k, v in self.games.items() if now - v[1] < 3.5}
        own = set(local_addresses())
        out = {}
        for (ip, port), (info, _t) in self.games.items():
            # a host on this same PC answers on several addresses: show it once
            key = ("local", port) if (ip in own or ip.startswith("127.")) else (ip, port)
            if key not in out or ip.startswith("127."):
                out[key] = (ip, port, info)
        return sorted(out.values())

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None


def explain(ex, host, port):
    """Turn a socket error into something a player can act on."""
    text = str(ex).lower()
    where = "%s port %s" % (host, port)
    if isinstance(ex, ConnectionRefusedError) or "refused" in text:
        if host.startswith("127.") or host == "localhost":
            return ("Nothing is hosting on this computer. 127.0.0.1 means 'this PC' - to join a friend, "
                    "use the address shown in their lobby.")
        return ("%s refused the connection. Either the host has not clicked 'Open lobby' yet, or security "
                "software on the host's PC (Norton, McAfee, ...) is blocking Python - allow it there, or let the "
                "other PC host instead." % where)
    if isinstance(ex, socket.timeout) or "timed out" in text:
        return ("No answer from %s. The host's firewall or security software is probably blocking the game "
                "(allow Python there), or you are on different networks and the host has not forwarded the port."
                % where)
    if isinstance(ex, socket.gaierror):
        return "'%s' is not a valid address. It should look like 192.168.1.23." % host
    if "unreachable" in text:
        return "Cannot reach %s. Are both computers on the same network?" % where
    return "Could not connect to %s: %s" % (where, ex)


def connect(host, port, timeout=5.0):
    """Returns (conn, inbox). Raises OSError if the host cannot be reached."""
    s = socket.create_connection((host, port), timeout=timeout)
    inbox = queue.Queue()
    return Conn(s, inbox, 0), inbox


def local_addresses():
    out = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in out and not ip.startswith("127."):
                out.append(ip)
    except OSError:
        pass
    try:                                    # the address used to reach the internet / LAN gateway
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        if ip not in out and not ip.startswith("127."):
            out.insert(0, ip)
    except OSError:
        pass
    return out or ["127.0.0.1"]


def clean_loadout(lo):
    """Never trust what a client sends: keep only well-formed, known values."""
    if not isinstance(lo, dict):
        lo = {}
    name = str(lo.get("name", "Player"))[:16].strip() or "Player"
    color = lo.get("color", [200, 200, 200])
    if not (isinstance(color, list) and len(color) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in color)):
        color = [200, 200, 200]
    tanks = [k for k in lo.get("tanks", []) if k in TANK_INDEX] if isinstance(lo.get("tanks"), list) else []
    weapons = [k for k in lo.get("weapons", []) if k in WEAPON_INDEX] if isinstance(lo.get("weapons"), list) else []
    if "basic" not in tanks:
        tanks.insert(0, "basic")
    for k in ("basic_shell", "tracer"):
        if k not in weapons:
            weapons.append(k)
    try:
        credits = max(0, min(100000, int(lo.get("credits", 0))))
    except (TypeError, ValueError):
        credits = 0
    tank = lo.get("tank", "basic")
    return dict(name=name, color=color, credits=credits, tanks=tanks, weapons=weapons,
                tank=tank if tank in tanks else "basic")


# ---------------------------------------------------------------------------
# sessions: what the battle screen talks to

class LocalSession:
    """Single-player game, or the host side of a multiplayer game."""

    def __init__(self, world, pid, server=None, remote=None):
        self.world = world
        self.pid = pid
        self.server = server
        self.remote = dict(remote or {})        # connection id -> player id
        self.is_host = server is not None
        self.can_pause = server is None
        self.lost = None
        self._snap_t = 0.0
        self._outbox = []
        self._roster_sent = None

    def me(self):
        return self.world.players.get(self.pid)

    def set_input(self, throttle, turn, aim, fire0, fire1, dist=None):
        t = self.me()
        if t:
            t.throttle, t.turn, t.aim, t.aim_dist = throttle, turn, aim, dist
            t.fire = [bool(fire0), bool(fire1)] if t.alive else [False, False]

    def buy(self, kind, key):
        return self.world.buy(self.pid, kind, key)

    def select_tank(self, key):
        return self.world.select_tank(self.pid, key)

    def select_weapon(self, slot, idx):
        return self.world.select_weapon(self.pid, slot, idx)

    def update(self, dt):
        w = self.world
        if self.server:
            self._receive()
        w.step(dt)
        events = w.events
        w.events = []
        if self.server:
            self._outbox.extend(events)
            self._snap_t += dt
            if self._snap_t >= 1.0 / SNAP_RATE:
                self._snap_t = 0.0
                self._broadcast()
        return events

    def _receive(self):
        w = self.world
        for cid, msg in self.server.poll():
            kind = msg.get("t")
            pid = self.remote.get(cid)
            try:
                if kind == "_drop":
                    if pid is not None:
                        w.remove_player(pid)
                        del self.remote[cid]
                    self.server.drop(cid)
                elif kind == "join" and pid is None:
                    if len(self.remote) + 1 >= MAX_HUMANS:
                        self.server.send(cid, {"t": "error", "msg": "The game is full."})
                        continue
                    team = 0 if w.team_count(0) <= w.team_count(1) else 1
                    t = w.add_player(clean_loadout(msg.get("lo")), team)
                    self.remote[cid] = t.pid
                    self.server.send(cid, {"t": "start", "settings": w.settings, "roster": w.roster(),
                                           "pid": t.pid, "crushed": sorted(w.crushed)})
                elif pid is not None and pid in w.players:
                    t = w.players[pid]
                    if kind == "in":
                        m = msg.get("m", [0, 0])
                        t.throttle = max(-1.0, min(1.0, float(m[0])))
                        t.turn = max(-1.0, min(1.0, float(m[1])))
                        t.aim = float(msg.get("a", 0.0)) % (math.pi * 2)
                        t.aim_dist = max(0.0, min(6000.0, float(msg.get("d", 0.0))))
                        f = int(msg.get("f", 0))
                        t.fire = [bool(f & 1), bool(f & 2)] if t.alive else [False, False]
                    elif kind == "buy":
                        w.buy(pid, str(msg.get("k")), str(msg.get("key")))
                    elif kind == "tank":
                        w.select_tank(pid, str(msg.get("key")))
                    elif kind == "wsel":
                        w.select_weapon(pid, int(msg.get("slot", 0)), int(msg.get("i", -1)))
            except (TypeError, ValueError, IndexError, KeyError):
                continue

    def _broadcast(self):
        w = self.world
        self.server.info["players"] = sum(1 for t in w.players.values() if not t.is_ai)
        snap = w.snapshot()
        snap["t"] = "snap"
        snap["ev"] = self._outbox
        self._outbox = []
        roster = w.roster()
        if roster != self._roster_sent:
            self._roster_sent = roster
            snap["roster"] = roster
        for cid, pid in list(self.remote.items()):
            t = w.players.get(pid)
            if t:
                snap["me"] = [t.credits, t.tanks, t.weapons, t.earned]
            self.server.send(cid, snap)

    def close(self):
        if self.server:
            self.server.close()
            self.server = None


class RemoteSession:
    """A client connected to somebody else's game."""

    is_host = False
    can_pause = False

    def __init__(self, conn, inbox, start):
        self.conn = conn
        self.inbox = inbox
        self.world = World(start["settings"], mirror=True)
        self.world.apply_roster(start["roster"])
        for idx in start.get("crushed", ()):
            self.world.crush(int(idx), emit=False)
        self.pid = start["pid"]
        self.lost = None
        self._prev = None
        self._next = None
        self._next_at = 0.0
        self._interval = 1.0 / SNAP_RATE
        self._input = (0.0, 0.0, 0.0, 0, 0.0)
        self._input_t = 0.0

    def me(self):
        return self.world.players.get(self.pid)

    def set_input(self, throttle, turn, aim, fire0, fire1, dist=None):
        self._input = (throttle, turn, aim, (1 if fire0 else 0) | (2 if fire1 else 0), dist or 0.0)

    def buy(self, kind, key):
        self.conn.send({"t": "buy", "k": kind, "key": key})
        return True

    def select_tank(self, key):
        self.conn.send({"t": "tank", "key": key})
        return True

    def select_weapon(self, slot, idx):
        self.conn.send({"t": "wsel", "slot": slot, "i": idx})
        return True

    def update(self, dt):
        w = self.world
        events = []
        now = time.perf_counter()
        while True:
            try:
                _cid, msg = self.inbox.get_nowait()
            except queue.Empty:
                break
            kind = msg.get("t")
            if kind == "snap":
                if "roster" in msg:
                    w.apply_roster(msg["roster"])
                for e in msg.get("ev", ()):
                    e = tuple(e)
                    if e[0] == "shot":
                        owner = w.players.get(e[1])
                        w.spawn_projectile(e[1], owner.team if owner else 0, e[2], e[3], e[4], e[5], e[6])
                        if owner:
                            wp = data.WEAPONS[e[2]]
                            if wp["slot"] == data.SHELL:
                                owner.recoil = 1.0
                            owner.cool[e[2]] = w.reload_time(owner, wp)
                    elif e[0] == "hit":
                        w.projectiles.pop(e[1], None)
                    elif e[0] == "crush":
                        w.crush(int(e[1]), emit=False)
                    events.append(e)
                if self._next is not None:
                    self._interval = 0.8 * self._interval + 0.2 * max(0.02, min(0.25, now - self._next_at))
                self._prev, self._next, self._next_at = self._next, msg, now
                w.time, w.scores, w.over = msg["time"], msg["sc"], msg["over"]
                w.zones = [z + [0, -1, -1] for z in msg["zn"]]
                me = w.players.get(self.pid)
                if me and "me" in msg:
                    me.credits, me.tanks, me.weapons, me.earned = msg["me"]
            elif kind == "_drop":
                self.lost = "Lost connection to the host."
            elif kind == "error":
                self.lost = str(msg.get("msg", "Disconnected."))
        self._interpolate(now)
        w._step_projectiles(dt)
        for t in w.players.values():
            if t.recoil > 0:
                t.recoil = max(0.0, t.recoil - dt * 4)
            for k in t.cool:
                if t.cool[k] > 0:
                    t.cool[k] -= dt
        self._input_t += dt
        if self._input_t >= 1.0 / INPUT_RATE and self.conn.alive:
            self._input_t = 0.0
            thr, turn, aim, f, dist = self._input
            self.conn.send({"t": "in", "m": [round(thr, 2), round(turn, 2)], "a": round(aim, 3), "f": f,
                            "d": round(dist)})
        if not self.conn.alive and not self.lost:
            self.lost = "Lost connection to the host."
        return events

    def _interpolate(self, now):
        if self._next is None:
            return
        w = self.world
        k = min(1.0, (now - self._next_at) / self._interval) if self._prev else 1.0
        prev = {row[0]: row for row in self._prev["tk"]} if self._prev else {}
        for row in self._next["tk"]:
            t = w.players.get(row[0])
            if t is None:
                continue
            pid, alive, x, y, ang, tur, hp, ti, shield, s0, s1, resp, kills, deaths, speed = row
            key = TANKS[ti]["key"]
            if t.tank_key != key:
                if key not in t.tanks:
                    t.tanks.append(key)
                t.set_tank(key)
                if t.tank_key != key:           # mirror tanks do not track ownership: force it
                    t.tanks.append(key)
                    t.weapons = [w_["key"] for w_ in data.WEAPONS]
                    t.set_tank(key)
            p = prev.get(pid)
            if p and p[1] and alive and abs(p[2] - x) < 400 and abs(p[3] - y) < 400:
                t.x = p[2] + (x - p[2]) * k
                t.y = p[3] + (y - p[3]) * k
                t.angle = p[4] + angle_diff(ang, p[4]) * k
                t.turret = p[5] + angle_diff(tur, p[5]) * k
            else:
                t.x, t.y, t.angle, t.turret = x, y, ang, tur
            t.alive = bool(alive)
            t.hp, t.shield, t.respawn = hp, (1.0 if shield else 0.0), resp
            t.sel = [s0, s1]
            t.kills, t.deaths, t.speed = kills, deaths, speed

    def close(self):
        self.conn.close()
