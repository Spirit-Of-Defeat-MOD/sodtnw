"""Ghost animation bounds and feedback on successful present catches only."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Scripts'))
from halloween_ghost import flight_pose,pop_pose
from santa_game import PresentRun,SantaGame


class SeasonalFeedback(unittest.TestCase):
    def test_ghost_stays_in_window_and_reverses_direction(self):
        for width,height in ((800,600),(1920,1080),(60,60)):
            for t in (0,.3,4,8,12,15.9,16):
                right=flight_pose(t,1,width,height,88,.4)
                left=flight_pose(t,-1,width,height,88,.4)
                self.assertAlmostEqual(right[0]+left[0],max(0,width-88))
                self.assertGreaterEqual(right[1],0)
                self.assertLessEqual(right[1],max(0,height-88))
                self.assertTrue(0<=right[2]<=1)
                self.assertIn(right[3],range(4))
                self.assertIn(right[4],(-6,-3,0,3,6))

    def test_catch_plays_surprise_then_dissolves(self):
        self.assertEqual([pop_pose(t)[2] for t in (0,.2,.5,.9)],[4,5,6,7])
        self.assertEqual(pop_pose(1.1)[1],0)

    def test_present_jingle_only_on_new_successful_catch(self):
        run=PresentRun();run.gifts=[dict(id=1,x=100,y=100,kind=0)]
        audio=SimpleNamespace(play=Mock())
        game=SimpleNamespace(closed=False,run=run,owner=SimpleNamespace(audio=audio),dirty=False)
        event=SimpleNamespace(x=100,y=100)
        self.assertEqual(SantaGame.click(game,event),'break')
        self.assertEqual(run.score,1)
        audio.play.assert_called_once_with('santa_collect')
        SantaGame.click(game,event)
        audio.play.assert_called_once()
        game.closed=True
        SantaGame.click(game,event)
        audio.play.assert_called_once()


if __name__=='__main__':unittest.main()
