"""Only new current-player badges generate celebrations."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Scripts'))
from achievement_toast import UnlockTracker,toast_pose
from achievements import award


class UnlockNotifications(unittest.TestCase):
    def setUp(self):
        self.data={'devs':[{'name':'A','achievements':{'first':'old'}},{'name':'B','achievements':{}}]}
        self.tracker=UnlockTracker(self.data)

    def test_existing_badges_stay_quiet(self):
        self.assertEqual(self.tracker.update(self.data,'A'),[])

    def test_current_player_only_and_once(self):
        self.data['devs'][0]['achievements']['five']='now'
        self.data['devs'][1]['achievements']['first']='now'
        self.assertEqual(self.tracker.update(self.data,'A'),['five'])
        self.assertEqual(self.tracker.update(self.data,'A'),[])
        self.assertEqual(self.tracker.update(self.data,'B'),[])

    def test_sync_history_and_undo_do_not_replay(self):
        badges=self.data['devs'][0]['achievements'];badges['ten']='synced'
        self.assertEqual(self.tracker.update(self.data,'A',quiet=True),[])
        del badges['ten'];self.tracker.update(self.data,'A')
        badges['ten']='restored'
        self.assertEqual(self.tracker.update(self.data,'A'),[])

    def test_toast_enters_holds_and_fades_at_ten_seconds(self):
        self.assertEqual(toast_pose(0)[1],0)
        self.assertEqual(toast_pose(.5),(0,1))
        self.assertEqual(toast_pose(9),(0,1))
        self.assertTrue(0<toast_pose(9.8)[1]<1)
        self.assertEqual(toast_pose(10)[1],0)
        self.assertEqual(toast_pose(2,.25)[1],0)

    def test_secrets_games_and_other_master_work_share_the_notification_path(self):
        self.data['devs'][0]['secrets']=['egg_arctic','halloween_ghost']
        self.data['rr_game_scores']=[dict(dev='A',game='flags',score=5,answered=5,completed=True,duration=20)]
        self.data['master_activity']=[dict(id=master,who='A',master=master,action='saved',files=[])
            for master in ('Music Master','Culture Master','Country Master')]
        award(self.data)
        new=set(self.tracker.update(self.data,'A'))
        self.assertTrue({'egg_arctic','spooked','game_speed','music_master','culture_master','country_master'}<=new)
        self.assertEqual(self.tracker.update(self.data,'A'),[])


if __name__=='__main__':unittest.main()
