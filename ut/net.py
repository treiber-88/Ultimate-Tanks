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

SNAP_RATE = 30.0
DISCOVER, FOUND = b"UTANKS?", b"UTANKS!"
INPUT_RATE = 60.0
MAX_HUMANS = 16


class Conn:
    """One TCP connection with a reader thread. Incoming messages land in `inbox`."""

    def __init__(self, sock, inbox, cid):
        self.sock = sock
        self.cid = cid
        self.inbox = inbox
        self.alive = True
        self.out = queue.Queue()
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(None)
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._write, daemon=True).start()

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
        """Queue a message. Never blocks: a writer thread does the actual sending."""
        if self.alive:
            self.out.put((json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8"))

    def backlog(self):
        """How many messages are still waiting to go out (large = this link cannot keep up)."""
        return self.out.qsize()

    def _write(self):
        try:
            while True:
                raw = self.out.get()
                if raw is None:
                    break
                self.sock.sendall(raw)
        except OSError:
            pass
        self.alive = False

    def close(self):
        self.alive = False
        self.out.put(None)
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
                tank=tank if tank in tanks else "basic", upgrades=data.clean_upgrades(lo.get("upgrades")))


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
        self._pending = {}          # connection id -> events not yet delivered to that client
        self._roster_sent = {}
        self._ack = {}              # connection id -> timestamp of the newest input we applied

    def me(self):
        return self.world.players.get(self.pid)

    def set_input(self, throttle, turn, aim, fire0, fire1, dist=None, hold=False):
        t = self.me()
        if t:
            t.throttle, t.turn, t.aim, t.aim_dist = throttle, turn, aim, dist
            t.hold = bool(hold) and t.alive
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
            if events:
                for cid in self.remote:
                    self._pending.setdefault(cid, []).extend(events)
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
                    for d in (self._pending, self._roster_sent, self._ack):
                        d.pop(cid, None)
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
                        self._ack[cid] = float(msg.get("ts", 0.0))
                        m = msg.get("m", [0, 0])
                        t.throttle = max(-1.0, min(1.0, float(m[0])))
                        t.turn = max(-1.0, min(1.0, float(m[1])))
                        t.aim = float(msg.get("a", 0.0)) % (math.pi * 2)
                        t.aim_dist = max(0.0, min(6000.0, float(msg.get("d", 0.0))))
                        f = int(msg.get("f", 0))
                        t.fire = [bool(f & 1), bool(f & 2)] if t.alive else [False, False]
                        t.hold = bool(f & 4) and t.alive
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
        base = w.snapshot()
        base["t"] = "snap"
        roster = w.roster()
        for cid, pid in list(self.remote.items()):
            conn = self.server.conns.get(cid)
            if conn is None or conn.backlog() > 2:
                if conn and len(self._pending.get(cid, ())) > 8000:
                    conn.close()            # hopelessly behind (frozen or gone): let it drop
                continue                    # that link is behind: skip a beat, its events wait in _pending
            snap = dict(base)
            snap["ev"] = self._pending.pop(cid, [])
            snap["ack"] = self._ack.get(cid, 0.0)
            if self._roster_sent.get(cid) != roster:
                self._roster_sent[cid] = roster
                snap["roster"] = roster
            t = w.players.get(pid)
            if t:
                snap["me"] = [t.credits, t.tanks, t.weapons, t.earned, t.temp, t.upgrades]
            conn.send(snap)

    def close(self):
        if self.server:
            self.server.close()
            self.server = None


class RemoteSession:
    """A client connected to somebody else's game.

    Two things keep it smooth on an imperfect connection:
    * other tanks are drawn slightly in the past, interpolated between buffered snapshots by the host's clock,
      so uneven packet arrival does not show;
    * the player's own tank is simulated locally the moment a key is pressed, then gently corrected toward
      what the host says actually happened.
    """

    is_host = False
    can_pause = False
    MIN_DELAY, MAX_DELAY = 0.07, 0.35

    def __init__(self, conn, inbox, start):
        self.conn = conn
        self.inbox = inbox
        self.world = World(start["settings"], mirror=True)
        self.world.apply_roster(start["roster"])
        for idx in start.get("crushed", ()):
            self.world.crush(int(idx), emit=False)
        self.pid = start["pid"]
        self.lost = None
        self._snaps = []            # buffered snapshots, oldest first
        self._offset = None         # host clock minus our clock
        self._late = 0.0            # how late packets have recently been arriving (jitter)
        self._delay = 0.1           # how far in the past we draw other tanks
        self._input = (0.0, 0.0, 0.0, 0, 0.0)
        self._input_t = 0.0
        self._clock = 0.0           # our own running time, stamped on inputs
        self._history = []          # (clock, x, y, angle) of our predicted tank, for reconciliation
        self._was_alive = False

    def me(self):
        return self.world.players.get(self.pid)

    def set_input(self, throttle, turn, aim, fire0, fire1, dist=None, hold=False):
        self._input = (throttle, turn, aim, (1 if fire0 else 0) | (2 if fire1 else 0) | (4 if hold else 0),
                       dist or 0.0)

    def buy(self, kind, key):
        self.conn.send({"t": "buy", "k": kind, "key": key})
        return True

    def select_tank(self, key):
        self.conn.send({"t": "tank", "key": key})
        return True

    def select_weapon(self, slot, idx):
        self.conn.send({"t": "wsel", "slot": slot, "i": idx})
        return True

    # -- per frame ---------------------------------------------------------------
    def update(self, dt):
        w = self.world
        events = []
        now = time.perf_counter()
        self._clock += dt
        while True:
            try:
                _cid, msg = self.inbox.get_nowait()
            except queue.Empty:
                break
            kind = msg.get("t")
            if kind == "snap":
                self._on_snapshot(msg, now, events)
            elif kind == "_drop":
                self.lost = "Lost connection to the host."
            elif kind == "error":
                self.lost = str(msg.get("msg", "Disconnected."))
        self._show_others(now)
        self._predict_me(dt)
        w._step_projectiles(dt)
        for t in w.players.values():
            if t.pid == self.pid and t.alive:
                continue                     # our own timers are advanced by the prediction step
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
                            "d": round(dist), "ts": round(self._clock, 3)})
        if not self.conn.alive and not self.lost:
            self.lost = "Lost connection to the host."
        return events

    def _on_snapshot(self, msg, now, events):
        w = self.world
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

        # clock sync: the least-delayed packets define the host clock; lateness beyond that is jitter
        sample = msg["time"] - now
        if self._offset is None or sample > self._offset:
            self._offset = sample
        else:
            self._late = max(self._late * 0.97, self._offset - sample)
            self._offset += (sample - self._offset) * 0.002
        want = min(self.MAX_DELAY, max(self.MIN_DELAY, 1.5 / SNAP_RATE + self._late * 1.3))
        self._delay += (want - self._delay) * 0.08
        self._snaps.append(msg)
        if len(self._snaps) > 40:
            del self._snaps[:-40]

        # things that are not interpolated are taken from the newest snapshot straight away
        w.time, w.scores, w.over = msg["time"], msg["sc"], msg["over"]
        w.zones = [z + [0, -1, -1] for z in msg["zn"]]
        if msg.get("cp"):
            w.apply_cps(msg["cp"])
        w.apply_mode(msg)
        if w.rules:
            w.rules.restrict()
        if msg.get("fl"):
            w.apply_flags(msg["fl"])
        me = w.players.get(self.pid)
        if me and "me" in msg:
            me.credits, me.tanks, me.weapons, me.earned = msg["me"][:4]
            me.temp = msg["me"][4] if len(msg["me"]) > 4 else []
            if len(msg["me"]) > 5:
                me.upgrades = msg["me"][5]
        for row in msg["tk"]:
            t = w.players.get(row[0])
            if t is None:
                continue
            key = TANKS[row[7]]["key"]
            if t.tank_key != key:
                if key not in t.tanks:
                    t.tanks.append(key)
                if t.pid != self.pid:
                    t.weapons = [w_["key"] for w_ in data.WEAPONS]     # mirrors do not track ownership
                t.set_tank(key)
            t.hp, t.shield, t.respawn = row[6], (1.0 if row[8] else 0.0), row[11]
            t.sel = [row[9], row[10]]
            t.kills, t.deaths = row[12], row[13]
            if len(row) > 15:
                t.out, t.respawns = row[15] < 0, max(0, row[15])
            if len(row) > 16:
                t.points = row[16]
            if len(row) > 17:
                t.max_hp = row[17]                    # includes any armour upgrade
            if t.pid == self.pid:
                self._reconcile(t, row, msg.get("ack", 0.0))

    def _show_others(self, now):
        """Place every other tank where it was `_delay` seconds ago, between two buffered snapshots."""
        if not self._snaps:
            return
        w = self.world
        rt = now + self._offset - self._delay
        snaps = self._snaps
        while len(snaps) > 2 and snaps[1]["time"] <= rt:
            snaps.pop(0)
        a = snaps[0]
        b = snaps[1] if len(snaps) > 1 else a
        span = b["time"] - a["time"]
        k = (rt - a["time"]) / span if span > 1e-6 else 1.0
        ahead = 0.0
        if k > 1.0:                          # nothing newer has arrived yet: coast briefly on last known speed
            ahead = min(rt - b["time"], 0.2)
            k = 1.0
        k = max(0.0, k)
        prev = {row[0]: row for row in a["tk"]}
        for row in b["tk"]:
            pid = row[0]
            t = w.players.get(pid)
            if t is None or pid == self.pid:
                continue
            _pid, alive, x, y, ang, tur = row[:6]
            p = prev.get(pid)
            if p and p[1] and alive and abs(p[2] - x) < 400 and abs(p[3] - y) < 400:
                t.x = p[2] + (x - p[2]) * k
                t.y = p[3] + (y - p[3]) * k
                t.angle = p[4] + angle_diff(ang, p[4]) * k
                t.turret = p[5] + angle_diff(tur, p[5]) * k
            else:
                t.x, t.y, t.angle, t.turret = x, y, ang, tur
            t.speed = row[14]
            if ahead and alive:
                t.x += math.cos(t.angle) * t.speed * ahead
                t.y += math.sin(t.angle) * t.speed * ahead
            t.alive = bool(alive)

    # -- our own tank ------------------------------------------------------------------
    def _predict_me(self, dt):
        me = self.me()
        if not me or not me.alive or self.world.over is not None:
            return
        me.throttle, me.turn, me.aim = self._input[0], self._input[1], self._input[2]
        self.world._move(me, dt)
        self._history.append((self._clock, me.x, me.y, me.angle))
        if len(self._history) > 180:
            del self._history[:-180]

    def _reconcile(self, me, row, ack):
        """The host says where we were when it applied input `ack`. Compare with where we thought we were
        at that moment and fold the difference into our present position, a little at a time."""
        _pid, alive, x, y, ang, tur = row[:6]
        if not alive:
            me.alive = False
            self._was_alive = False
            self._history.clear()
            return
        if not self._was_alive:              # just (re)spawned: take the host's word for everything
            me.alive = True
            me.x, me.y, me.angle, me.turret, me.speed = x, y, ang, tur, 0.0
            self._was_alive = True
            self._history.clear()
            return
        past = None
        for h in self._history:
            if h[0] <= ack:
                past = h
            else:
                break
        if past is None:
            past = (0.0, me.x, me.y, me.angle)
        ex, ey, ea = x - past[1], y - past[2], angle_diff(ang, past[3])
        if ex * ex + ey * ey > 260 * 260:    # badly out of step (teleport, tank swap): snap
            gx, gy, ga = ex, ey, ea
        else:
            gx, gy, ga = ex * 0.12, ey * 0.12, ea * 0.12
        if self.world.map.blocked_circle(me.x + gx, me.y + gy, me.radius):
            gx = gy = 0.0
        me.x += gx
        me.y += gy
        me.angle += ga
        self._history = [(c, hx + gx, hy + gy, ha + ga) for c, hx, hy, ha in self._history if c >= past[0]]

    def close(self):
        self.conn.close()
