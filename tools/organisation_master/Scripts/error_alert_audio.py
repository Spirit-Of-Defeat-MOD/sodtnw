"""Short scene soundtracks on a mixer channel separate from the Radio."""
from pathlib import Path
import paths
from error_alert_scenes import ASSETS

SOUNDS=dict(ASSETS, **{"Soviet Terminal":"terminal"})


class AlertAudio:
    def __init__(self, settings):
        self.settings=settings
        self.channel=None
        self.clip=None

    def play(self, theme):
        self.stop()
        if not self.settings.enabled() or theme not in SOUNDS:return
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050,size=-16,channels=2,buffer=512)
            self.clip=pygame.mixer.Sound(str(Path(paths.TOOL)/"sounds"/"error_alerts"/(SOUNDS[theme]+".wav")))
            self.channel=pygame.mixer.find_channel()
            if self.channel:
                self.channel.set_volume(.45*self.settings.volume())
                self.channel.play(self.clip)
        except Exception:
            self.channel=None;self.clip=None

    def update(self):
        if self.channel:
            if self.channel.get_sound()!=self.clip:
                self.channel=None;self.clip=None
                return
            if not self.settings.enabled():self.stop()
            else:self.channel.set_volume(.45*self.settings.volume())

    def stop(self):
        if self.channel and self.channel.get_sound()==self.clip:self.channel.stop()
        self.channel=None;self.clip=None
