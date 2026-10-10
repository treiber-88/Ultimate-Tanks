"""Sound effects, synthesised at start-up so the game ships without audio files."""
import numpy as np
import pygame

RATE = 22050


def _env(n, attack, decay):
    t = np.arange(n) / RATE
    return np.minimum(t / max(attack, 1e-4), 1.0) * np.exp(-t / decay)


def _lowpass(x, k):
    c = np.cumsum(np.insert(x, 0, 0.0))
    y = np.copy(x)
    y[k - 1:] = (c[k:] - c[:-k]) / k
    return y


def _noise(rs, dur, k, decay, attack=0.002):
    n = int(RATE * dur)
    return _lowpass(rs.uniform(-1, 1, n), k) * _env(n, attack, decay)


def _tone(dur, f0, f1, decay):
    n = int(RATE * dur)
    f = np.linspace(f0, f1, n)
    return np.sin(2 * np.pi * np.cumsum(f) / RATE) * _env(n, 0.002, decay)


def _make(sig, gain=1.0):
    sig = sig / (np.abs(sig).max() + 1e-9) * gain
    pcm = (np.clip(sig, -1, 1) * 32000).astype(np.int16)
    return pygame.mixer.Sound(buffer=np.ascontiguousarray(np.column_stack([pcm, pcm])).tobytes())


class Sound:
    def __init__(self, volume=0.7):
        self.ok = False
        self.volume = volume
        self.s = {}
        self._last = {}
        try:
            pygame.mixer.init(RATE, -16, 2, 512)
            pygame.mixer.set_num_channels(24)
            rs = np.random.RandomState(7)
            self.s["cannon"] = _make(_noise(rs, 0.55, 14, 0.11) + 0.9 * _tone(0.55, 110, 38, 0.14))
            self.s["heavy"] = _make(_noise(rs, 0.8, 22, 0.17) + 1.1 * _tone(0.8, 85, 28, 0.22))
            self.s["mg"] = _make(_noise(rs, 0.09, 4, 0.02) + 0.4 * _tone(0.09, 320, 140, 0.02), 0.55)
            self.s["mg2"] = _make(_noise(rs, 0.11, 6, 0.028) + 0.5 * _tone(0.11, 230, 100, 0.03), 0.65)
            self.s["hit"] = _make(_noise(rs, 0.12, 3, 0.025) + 0.6 * _tone(0.12, 900, 380, 0.03), 0.5)
            self.s["boom"] = _make(_noise(rs, 1.1, 30, 0.26) + 0.8 * _tone(1.1, 70, 24, 0.3))
            self.s["bigboom"] = _make(_noise(rs, 2.6, 60, 0.7) + 1.0 * _tone(2.6, 48, 16, 0.8))
            self.s["fire"] = _make(_noise(rs, 0.7, 10, 0.3, 0.1), 0.5)
            self.s["click"] = _make(_tone(0.05, 700, 500, 0.015), 0.4)
            self.s["buy"] = _make(_tone(0.12, 660, 660, 0.05) + np.pad(_tone(0.1, 990, 990, 0.05), (441, 0))[:2646],
                                  0.5)
            self.s["deny"] = _make(_tone(0.14, 160, 120, 0.06), 0.5)
            self.ok = True
        except (pygame.error, ValueError, NotImplementedError):
            self.ok = False

    def play(self, name, vol=1.0, min_gap=0.0):
        if not self.ok or self.volume <= 0:
            return
        now = pygame.time.get_ticks() / 1000.0
        if min_gap and now - self._last.get(name, -9) < min_gap:
            return
        self._last[name] = now
        v = max(0.0, min(1.0, vol * self.volume))
        if v > 0.02:
            ch = self.s[name].play()
            if ch:
                ch.set_volume(v)

    def play_at(self, name, x, y, listener, vol=1.0, min_gap=0.0, reach=1900.0):
        d = ((x - listener[0]) ** 2 + (y - listener[1]) ** 2) ** 0.5
        if d < reach:
            self.play(name, vol * (1.0 - d / reach) ** 1.5, min_gap)
