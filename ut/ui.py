"""A small immediate-mode UI kit. Layouts are written for a 1080-pixel-tall virtual screen and scaled to fit."""
import pygame

WHITE = (236, 238, 240)
DIM = (150, 158, 166)
GOLD = (255, 206, 84)
GREEN = (120, 220, 110)
RED = (255, 104, 88)
ORANGE = (255, 150, 50)


class UI:
    def __init__(self, app):
        self.app = app
        self.a = app.assets
        self.screen = None
        self.s = 1.0
        self.vw = 1920.0
        self.mouse = (0, 0)
        self.clicked = False
        self.down = False
        self.wheel = 0
        self.keys = []
        self.text_events = []
        self.focus = None
        self._text = {}
        self._skin = {}
        self._size = None
        self.hot_any = False

    # -- frame setup ------------------------------------------------------------
    def begin(self, screen, events):
        self.screen = screen
        w, h = screen.get_size()
        if (w, h) != self._size:
            self._size = (w, h)
            self._skin.clear()
            self._text.clear()
        self.s = h / 1080.0
        self.vw = w / self.s
        self.mouse = pygame.mouse.get_pos()
        self.down = pygame.mouse.get_pressed()[0]
        self.clicked = False
        self.wheel = 0
        self.keys = []
        self.text_events = []
        self.hot_any = False
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.clicked = True
            elif e.type == pygame.MOUSEWHEEL:
                self.wheel += e.y
            elif e.type == pygame.KEYDOWN:
                self.keys.append(e.key)
                self.text_events.append(e)

    def r(self, x, y, w, h):
        s = self.s
        return pygame.Rect(int(x * s), int(y * s), int(w * s), int(h * s))

    def hot(self, x, y, w, h):
        return self.r(x, y, w, h).collidepoint(self.mouse)

    def key(self, k):
        return k in self.keys

    # -- text ----------------------------------------------------------------------
    def render(self, text, size, color=WHITE, bold=True):
        k = (text, int(size * self.s), color, bold)
        surf = self._text.get(k)
        if surf is None:
            if len(self._text) > 900:
                self._text.clear()
            surf = self.a.font(size * self.s, bold).render(text, True, color)
            self._text[k] = surf
        return surf

    def text(self, text, x, y, size=28, color=WHITE, align="l", bold=True, shadow=True):
        """Draw text with its top at y. align: l / c / r relative to x. Returns the width in virtual pixels."""
        surf = self.render(str(text), size, color, bold)
        px, py = int(x * self.s), int(y * self.s)
        if align == "c":
            px -= surf.get_width() // 2
        elif align == "r":
            px -= surf.get_width()
        if shadow:
            sh = self.render(str(text), size, (0, 0, 0), bold)
            o = max(1, int(2 * self.s))
            self.screen.blit(sh, (px + o, py + o))
        self.screen.blit(surf, (px, py))
        return surf.get_width() / self.s

    def wrap(self, text, x, y, width, size=24, color=DIM, line=1.25):
        font = self.a.font(size * self.s, False)
        words, cur, lines = text.split(), "", []
        for wd in words:
            test = (cur + " " + wd).strip()
            if font.size(test)[0] > width * self.s and cur:
                lines.append(cur)
                cur = wd
            else:
                cur = test
        if cur:
            lines.append(cur)
        for i, ln in enumerate(lines):
            self.text(ln, x, y + i * size * line, size, color, bold=False)
        return len(lines) * size * line

    # -- skinned boxes ---------------------------------------------------------------
    def _nine(self, name, w, h, border, variant=""):
        """Nine-slice a UI skin to (w, h) screen pixels."""
        k = (name, w, h, variant)
        surf = self._skin.get(k)
        if surf is None:
            if len(self._skin) > 400:
                self._skin.clear()
            src = self.a.ui[name]
            sw, sh = src.get_size()
            b = border
            d = max(2, min(int(border * self.s * 1.2), w // 2, h // 2))
            surf = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
            xs = ((0, b, 0, d), (b, sw - 2 * b, d, w - 2 * d), (sw - b, b, w - d, d))
            ys = ((0, b, 0, d), (b, sh - 2 * b, d, h - 2 * d), (sh - b, b, h - d, d))
            for sy, shh, dy, dh in ys:
                for sx, sww, dx, dw in xs:
                    if dw > 0 and dh > 0:
                        part = src.subsurface((sx, sy, sww, shh))
                        surf.blit(pygame.transform.smoothscale(part, (dw, dh)), (dx, dy))
            if variant == "hot":
                surf.fill((34, 34, 34, 0), special_flags=pygame.BLEND_RGB_ADD)
            elif variant == "on":
                surf.fill((80, 44, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
            elif variant == "off":
                surf.fill((120, 120, 120, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif variant.startswith("a"):
                surf.fill((255, 255, 255, int(variant[1:])), special_flags=pygame.BLEND_RGBA_MULT)
            self._skin[k] = surf
        return surf

    def panel(self, x, y, w, h, alpha=255):
        r = self.r(x, y, w, h)
        self.screen.blit(self._nine("panel", r.w, r.h, 30, "" if alpha >= 255 else "a%d" % alpha), r.topleft)
        return r

    def slot(self, x, y, w, h, variant=""):
        r = self.r(x, y, w, h)
        self.screen.blit(self._nine("slot", r.w, r.h, 16, variant), r.topleft)
        return r

    def button(self, label, x, y, w, h, enabled=True, active=False, size=30, color=WHITE):
        r = self.r(x, y, w, h)
        hot = enabled and r.collidepoint(self.mouse)
        variant = "off" if not enabled else ("on" if active else ("hot" if hot else ""))
        self.screen.blit(self._nine("button", r.w, r.h, 18, variant), r.topleft)
        if label:
            col = color if enabled else (110, 114, 120)
            self.text(label, x + w / 2, y + h / 2 - size * 0.62, size, col, "c")
        if hot:
            self.hot_any = True
            if self.clicked:
                self.app.sound.play("click")
                self.clicked = False
                return True
        return False

    def image(self, surf, x, y, w, h, key):
        r = self.r(x, y, w, h)
        self.screen.blit(self.a.scaled(surf, r.w, r.h, key), r.topleft)

    def fill(self, x, y, w, h, color, alpha=255):
        r = self.r(x, y, w, h)
        if alpha >= 255:
            self.screen.fill(color, r)
        else:
            s = pygame.Surface(r.size, pygame.SRCALPHA)
            s.fill((*color, alpha))
            self.screen.blit(s, r.topleft)

    def bar(self, x, y, w, h, frac, color, back=(18, 22, 26)):
        self.fill(x, y, w, h, back)
        if frac > 0:
            self.fill(x + 2, y + 2, max(0.0, (w - 4) * min(1.0, frac)), h - 4, color)

    # -- compound widgets -----------------------------------------------------------------
    def stepper(self, label, x, y, w, value, lo, hi, step=1, fmt=str):
        """[-] value [+] with a caption. Returns the new value."""
        self.text(label, x, y + 12, 26, DIM)
        bx = x + w - 300
        if self.button("-", bx, y, 60, 54, value > lo):
            value = max(lo, value - step)
        self.slot(bx + 66, y, 168, 54)
        self.text(fmt(value), bx + 150, y + 10, 28, WHITE, "c")
        if self.button("+", bx + 240, y, 60, 54, value < hi):
            value = min(hi, value + step)
        return value

    def choice(self, label, x, y, w, options, index):
        self.text(label, x, y + 12, 26, DIM)
        bx = x + w - 300
        if self.button("<", bx, y, 60, 54):
            index = (index - 1) % len(options)
        self.slot(bx + 66, y, 168, 54)
        label = str(options[index])
        self.text(label, bx + 150, y + (12 if len(label) <= 13 else 15), 24 if len(label) <= 13 else 19, WHITE, "c")
        if self.button(">", bx + 240, y, 60, 54):
            index = (index + 1) % len(options)
        return index

    def text_input(self, ident, x, y, w, h, value, maxlen=16, allowed=None):
        r = self.r(x, y, w, h)
        if self.clicked:
            if r.collidepoint(self.mouse):
                self.focus = ident
                self.clicked = False
            elif self.focus == ident:
                self.focus = None
        focused = self.focus == ident
        self.slot(x, y, w, h, "hot" if focused else "")
        if focused:
            for e in self.text_events:
                if e.key == pygame.K_BACKSPACE:
                    value = value[:-1]
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE, pygame.K_TAB):
                    pass
                elif e.unicode and e.unicode.isprintable() and len(value) < maxlen:
                    if allowed is None or e.unicode in allowed:
                        value += e.unicode
        caret = "|" if focused and (pygame.time.get_ticks() // 450) % 2 == 0 else ""
        self.text(value + caret, x + 16, y + h / 2 - 18, 28, WHITE)
        return value
