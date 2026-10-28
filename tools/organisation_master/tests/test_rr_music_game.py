"""Music quiz rules using in-memory station fixtures, without playing audio."""
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

tools=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(tools/'organisation_master/Scripts'),str(tools/'culture_master'),str(tools/'country_master')]
from radio import Track
from rr_music_game import MusicQuestions


class MusicQuiz(unittest.TestCase):
    def setUp(self):
        self.stations={}
        for n in range(4):
            tracks=[Track('Song '+str(n),f'/music/song{n}.ogg')]
            if n<2:tracks.append(Track('Shared song','/music/shared.ogg'))
            tracks+=[Track('Advertisement','/music/ad.ogg'),Track('Jingle','/music/jingle.ogg')]
            self.stations[f'/mods/{n}|station{n}']=(f'Station {n}',tracks,0)
        for target,value in (('rr_music_game.Path.is_file',True),('music_master.ogg_info',(180.,{}))):
            p=patch(target,return_value=value);p.start();self.addCleanup(p.stop)
        self.bank=MusicQuestions('/mods',random.Random(4),stations=self.stations)

    def test_clips_and_choices_follow_difficulty(self):
        for level,seconds,count in (('easy',12,3),('medium',7,4),('hard',4,0)):
            q=self.bank.question(level)
            self.assertEqual(q.audio['seconds'],seconds)
            self.assertLessEqual(q.audio['start']+seconds,q.audio['duration'])
            self.assertEqual(len(q.options),count)
            self.assertEqual(q.typed,level=='hard')
            if count:self.assertEqual(sum(q.accepts(k) for k,_ in q.options),1)

    def test_ads_and_jingles_are_not_questions(self):
        self.assertEqual(len(self.bank.tracks),5)
        self.assertTrue(all(t['name'] not in ('Advertisement','Jingle') for t in self.bank.tracks.values()))

    def test_shared_file_accepts_both_stations(self):
        self.bank.tracks={p:t for p,t in self.bank.tracks.items() if t['name']=='Shared song'}
        q=self.bank.question('hard')
        self.assertEqual(len(q.answers),2)
        for key in q.answers:self.assertTrue(q.accepts(q.labels[key],True))

    def test_seen_clips_and_missing_music_fail_cleanly(self):
        self.bank.tracks={p:t for p,t in self.bank.tracks.items() if t['name']=='Shared song'}
        q=self.bank.question('easy')
        with self.assertRaises(ValueError):self.bank.question('easy',{q.key})
        with self.assertRaises(ValueError):MusicQuestions('/mods',stations={})

    def test_identically_named_stations_get_distinct_labels(self):
        stations={key:('Public Radio',tracks,missing) for key,(_,tracks,missing) in self.stations.items()}
        bank=MusicQuestions('/mods',stations=stations)
        self.assertEqual(len(set(bank.stations.values())),4)

    def test_song_copied_to_another_file_accepts_that_station_too(self):
        stations=dict(self.stations)
        stations['/mods/copy|copy']=('Copy Radio',[Track('Shared song','/music/shared-copy.ogg')],0)
        bank=MusicQuestions('/mods',stations=stations)
        bank.tracks={p:t for p,t in bank.tracks.items() if t['path']=='/music/shared.ogg'}
        q=bank.question('hard')
        self.assertEqual(len(q.answers),3)


if __name__=='__main__':unittest.main()
