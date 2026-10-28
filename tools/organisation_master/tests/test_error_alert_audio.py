import sys,wave,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"Scripts"))
from error_alert_audio import AlertAudio,SOUNDS


class ErrorAlertAudioTests(unittest.TestCase):
    def test_all_themes_have_distinct_bounded_nonempty_recordings(self):
        self.assertEqual(len(SOUNDS),14)
        self.assertEqual(len(set(SOUNDS.values())),14)
        folder=Path(__file__).resolve().parents[1]/"sounds"/"error_alerts"
        for key in SOUNDS.values():
            with wave.open(str(folder/(key+".wav"))) as w:
                self.assertEqual(w.getnframes()/w.getframerate(),5)
                self.assertGreater(len(set(w.readframes(w.getnframes()))),100)

    def test_muting_prevents_mixer_use_and_playback(self):
        settings=Mock();settings.enabled.return_value=False
        audio=AlertAudio(settings)
        with patch.dict(sys.modules,{"pygame":Mock()}) as modules:
            audio.play("Soviet Terminal")
            modules["pygame"].mixer.Sound.assert_not_called()

    def test_own_channel_volume_stop_and_no_radio_interruption(self):
        settings=Mock();settings.enabled.return_value=True;settings.volume.return_value=.5
        pygame=Mock();channel=pygame.mixer.find_channel.return_value
        audio=AlertAudio(settings)
        with patch.dict(sys.modules,{"pygame":pygame}):
            audio.play("Soviet Terminal")
            pygame.mixer.find_channel.assert_called_once_with()
            channel.set_volume.assert_called_with(.225)
            channel.play.assert_called_once()
            pygame.mixer.music.stop.assert_not_called()
            channel.get_sound.return_value=audio.clip
            settings.enabled.return_value=False;audio.update()
            channel.stop.assert_called_once()
            self.assertIsNone(audio.channel)

    def test_completed_channel_reused_by_another_sound_is_left_alone(self):
        settings=Mock();audio=AlertAudio(settings)
        channel=audio.channel=Mock();audio.clip=object()
        channel.get_sound.return_value=object()
        audio.stop()
        channel.stop.assert_not_called()

    def test_audio_device_failure_is_nonfatal(self):
        settings=Mock();settings.enabled.return_value=True
        pygame=Mock();pygame.mixer.Sound.side_effect=RuntimeError("No device")
        with patch.dict(sys.modules,{"pygame":pygame}):
            audio=AlertAudio(settings);audio.play("Classic");audio.stop()
            self.assertIsNone(audio.channel)
