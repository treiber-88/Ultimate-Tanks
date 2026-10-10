"""Ultimate Tanks - run this file to play:  python main.py"""
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

from ut import profile as profiles
from ut.assets import Assets
from ut.screens import Menu, ProfileSelect
from ut.sound import Sound
from ut.ui import UI

WINDOW = (1600, 900)


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Ultimate Tanks")
        self.screen = pygame.display.set_mode(WINDOW, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self._splash()
        self.sound = Sound()
        self.assets = Assets()
        self.ui = UI(self)
        self.profile = None
        self.running = True
        self.current = None
        self.show_fps = False
        last = profiles.last_profile_name()
        found = [p for p in profiles.list_profiles() if p.name == last]
        if found:
            self.set_profile(found[0])
            self.current = Menu(self)
        else:
            self.current = ProfileSelect(self)

    def _splash(self):
        self.screen.fill((10, 12, 16))
        f = pygame.font.Font(None, 48)
        t = f.render("Loading Ultimate Tanks...", True, (220, 220, 220))
        self.screen.blit(t, t.get_rect(center=self.screen.get_rect().center))
        pygame.display.flip()

    def set_profile(self, p):
        self.profile = p
        profiles.set_last_profile(p.name)
        self.sound.volume = p.settings["sound"]
        if p.settings["fullscreen"] != bool(self.screen.get_flags() & pygame.FULLSCREEN):
            self.apply_display()

    def apply_display(self):
        if self.profile and self.profile.settings["fullscreen"]:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(WINDOW, pygame.RESIZABLE)

    def switch(self, screen):
        if self.current is not None:
            self.current.close()
        self.ui.focus = None
        self.current = screen

    def run(self):
        while self.running:
            dt = min(0.05, self.clock.tick(60) / 1000.0)
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.VIDEORESIZE and not (self.screen.get_flags() & pygame.FULLSCREEN):
                    self.screen = pygame.display.set_mode((max(1024, e.w), max(600, e.h)), pygame.RESIZABLE)
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11 and self.profile:
                    self.profile.settings["fullscreen"] = not self.profile.settings["fullscreen"]
                    self.profile.save()
                    self.apply_display()
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F3:
                    self.show_fps = not self.show_fps
            self.ui.begin(self.screen, events)
            self.current.frame(dt)
            if self.show_fps:
                self.ui.text("%d fps" % self.clock.get_fps(), self.ui.vw - 20, 1050, 20, (255, 255, 0), "r")
            pygame.display.flip()
        if self.current is not None:
            self.current.close()
        pygame.quit()


if __name__ == "__main__":
    try:
        App().run()
    except Exception:
        # leave a record so a crash can be diagnosed afterwards
        import time
        import traceback
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log"), "a", encoding="utf-8") as f:
            f.write("\n=== %s ===\n%s" % (time.strftime("%Y-%m-%d %H:%M:%S"), traceback.format_exc()))
        raise
    sys.exit(0)
