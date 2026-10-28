"""Result reactions use earned scores, not the leaderboard or a partial accuracy."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Scripts'))
from rr_games_style import result_band,result_motion


class ResultReactions(unittest.TestCase):
    def test_quiz_and_endless_flag_thresholds(self):
        for score,expected in ((0,'bad'),(1,'bad'),(3,'bad'),(4,'ok'),(6,'ok'),(7,'good'),(9,'good'),(10,'perfect'),(20,'perfect')):
            for game in ('holy','flags'):
                self.assertEqual(result_band(game,score),expected)

    def test_pinpoint_uses_points_out_of_ten_thousand(self):
        for score,expected in ((0,'bad'),(3999,'bad'),(4000,'ok'),(6999,'ok'),(7000,'good'),(9999,'good'),(10000,'perfect')):
            self.assertEqual(result_band('pinpoint',score),expected)

    def test_daily_has_only_solved_and_unsolved(self):
        for points in (0,1,4,7,10):
            self.assertEqual(result_band('rrdle',points,solved=True),'solved')
            self.assertEqual(result_band('rrdle',points,solved=False),'unsolved')

    def test_all_reactions_settle_and_paused_never_moves(self):
        for band in ('perfect','good','ok','bad','solved','unsolved'):
            self.assertNotEqual(result_motion(band,.4),(0.,0.,0.))
            self.assertEqual(result_motion(band,3),(0.,0.,0.))
            self.assertEqual(result_motion(band,10),(0.,0.,0.))
            for t in (.1,.4,.8,1.5,2.5):
                dx,dy,angle=result_motion(band,t)
                self.assertLessEqual(abs(dx),5)
                self.assertLessEqual(abs(dy),11)
                self.assertLessEqual(abs(angle),7)
        self.assertEqual(result_motion('paused',.4),(0.,0.,0.))


if __name__=='__main__':unittest.main()
