"""Alert animation phases, theme changes and popup lifecycle must remain bounded."""
import sys
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import tkinter as tk
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"Scripts"))
import ui
from error_alert_style import nuke_scene,AlertHeader
from error_alert_scenes import SCENES,DRAWERS,ASSETS,scene_sheet,sprite_frame
from error_alerts import AlertWindow
from soviet_alert_wireframe import cloud_profile


class ErrorAlertStyle(unittest.TestCase):
    def test_terminal_cloud_is_a_bounded_flat_outline(self):
        small=cloud_profile(0);full=cloud_profile(1)
        self.assertEqual(full[0],full[-1])
        self.assertLess(max(x for x,y in small)-min(x for x,y in small),max(x for x,y in full)-min(x for x,y in full))
        for x,y in full:
            self.assertTrue(270<=x<=510)
            self.assertTrue(25<=y<=150)

    def test_nuke_has_one_bounded_fall_impact_and_cloud(self):
        for elapsed,phase in ((0,"fall"),(1.49,"fall"),(1.5,"blast"),(2.04,"blast"),(2.05,"cloud"),(4.99,"cloud"),(5,"settled"),(100,"settled")):
            got,progress=nuke_scene(elapsed)
            self.assertEqual(got,phase)
            self.assertGreaterEqual(progress,0)
            self.assertLessEqual(progress,1)

    def test_all_selected_themes_have_their_own_renderer(self):
        self.assertEqual(len(SCENES),13)
        self.assertEqual(set(SCENES),set(DRAWERS))
        self.assertEqual(len(set(DRAWERS.values())),13)

    def test_all_selected_sprites_are_packaged_with_transparent_backgrounds(self):
        self.assertEqual(set(ASSETS),set(SCENES))
        for theme,key in ASSETS.items():
            image=scene_sheet(key)
            self.assertIsNotNone(image,theme)
            columns=2 if key=="pipe" else 4
            self.assertEqual(image.size,(columns*256,512),theme)
            alpha=image.getchannel("A")
            self.assertGreater(alpha.histogram()[0],image.width*image.height*.15,theme)
            for point in ((0,0),(image.width-1,0),(0,image.height-1),(image.width-1,image.height-1)):
                self.assertLessEqual(alpha.getpixel(point),2,theme)
            for frame in range(columns*2):
                x=frame%columns*256;y=frame//columns*256
                self.assertIsNotNone(alpha.crop((x,y,x+256,y+256)).getbbox(),(theme,frame))

    def test_sprite_timing_is_bounded_and_settles(self):
        for key in ASSETS.values():
            count=4 if key=="pipe" else 8
            frames=[sprite_frame(key,t/20) for t in range(121)]
            self.assertGreater(len(set(frames)),1,key)
            self.assertTrue(all(0<=frame<count for frame in frames),key)
            self.assertEqual(sprite_frame(key,5),sprite_frame(key,100),key)

    def test_header_stops_animation_when_theme_changes_and_on_destroy(self):
        root=tk.Tk();ui.init(root);ui.load_themes(str(Path(__file__).resolve().parents[1]/"themes"))
        try:
            ui.apply_theme(root,"Soviet Terminal")
            audio=Mock()
            header=AlertHeader(root,audio);header.pack();root.update()
            audio.play.assert_called_once_with("Soviet Terminal")
            header.retheme()
            audio.play.assert_called_once()
            self.assertIsNotNone(header.job)
            for theme in ui.theme_names():
                ui.apply_theme(root,theme);root.update()
                for elapsed in (0,1.5,2.1,5.5):header.draw(elapsed)
                self.assertIsNotNone(header.job)
                if header.job:header.after_cancel(header.job);header.job=None
                with patch("error_alert_style.time.monotonic",return_value=header.started+5.1):header.tick()
                self.assertIsNone(header.job)
            hook=header.retheme;header.destroy();root.update()
            audio.stop.assert_called_once()
            self.assertNotIn(hook,ui.THEME_HOOKS)
        finally:root.destroy()

    def test_answer_keeps_existing_behavior_and_cleans_hooks(self):
        root=tk.Tk();ui.init(root)
        todo=SimpleNamespace(data={},me=SimpleNamespace(get=lambda:"Test dev"),save=Mock())
        app=SimpleNamespace(root=root,todo_page=lambda:todo,feedback=Mock())
        event=dict(by="Sender",to="Test dev",title="Example",key="sample",when="2026-10-25T12:00:00")
        done=Mock()
        try:
            with patch("error_alerts.flash"):
                window=AlertWindow(app,event,done);root.update()
                hook=window.retheme;header_hook=window.header.retheme
                todo.save.assert_not_called()
                window.answer("taking","on it");root.update()
                self.assertEqual(todo.data["error_claims"]["sample"]["who"],"Test dev")
                self.assertEqual(event["state"],"taking")
                done.assert_called_once_with(event)
                self.assertNotIn(hook,ui.THEME_HOOKS)
                self.assertNotIn(header_hook,ui.THEME_HOOKS)
        finally:root.destroy()
