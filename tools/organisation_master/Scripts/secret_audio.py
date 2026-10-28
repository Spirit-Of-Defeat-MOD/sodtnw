"""Small mixer channels for the secret sounds; rapid drum hits can overlap."""
import os
import sys
import paths  # (Scripts/paths.py: where the tool's files are)


class SecretAudio:
    def __init__(self, app):
        self.app = app
        self.sounds = {}
        self.channels = []

    def load(self, name):
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        if name not in self.sounds:
            folder = os.path.join(paths.BUNDLE, 'sounds')
            path = next((os.path.join(folder, name+ext) for ext in ('.wav', '.ogg')
                         if os.path.isfile(os.path.join(folder, name+ext))), None)
            if path is None:
                raise FileNotFoundError(name)
            self.sounds[name] = pygame.mixer.Sound(path)
        return self.sounds[name]

    def play_sequence(self, names):
        """Queue two clips on their own channel; never take the Radio's music stream."""
        if not self.app.sound_settings.enabled():
            return None
        try:
            import pygame
            clips = [self.load(name) for name in names]
            if len(clips) != 2:
                raise ValueError('A sequence needs two clips')
            channel = pygame.mixer.find_channel()
            if channel is None:
                return None
            for clip in clips:
                clip.set_volume(.4 * self.app.sound_settings.volume())
            channel.play(clips[0])
            channel.queue(clips[1])
            self.channels = [c for c in self.channels if c.get_busy()]
            self.channels.append(channel)
            return channel
        except Exception:
            return None

    def play(self, name):
        if not self.app.sound_settings.enabled():
            return False
        try:
            self.load(name)
            # (their own level, times Settings > Sound volume)
            self.sounds[name].set_volume((.55 if name == 'field_drum' else .4) * self.app.sound_settings.volume())
            channel = self.sounds[name].play()
            self.channels = [c for c in self.channels if c.get_busy()]
            if channel:
                self.channels.append(channel)
            return channel is not None
        except Exception:
            return False  # Device unavailable: the visual still works.

    def stop(self, name=None):
        sounds=([self.sounds[name]] if name in self.sounds else []) if name is not None else self.sounds.values()
        for sound in sounds:sound.stop()
        self.channels=[channel for channel in self.channels if channel.get_busy()] if name else []
