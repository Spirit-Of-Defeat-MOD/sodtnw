"""Rule tests: run with python -m unittest discover -s tools/organisation_master/tests."""
import copy
import datetime as dt
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Scripts'))
from rr_geography import Geography,daily_answer,daily_board
from rr_games_data import distinct_country_names,GameData,normalise
from todo_sync import merge_data


class GeographyRules(unittest.TestCase):
    def setUp(self):
        self.geo=Geography.__new__(Geography)
        self.geo.width=100;self.geo.height=20;self.geo.km_per_pixel=400.75
        self.geo.raster=np.zeros((20,100),dtype=np.uint16);self.geo.raster[4:7,3:6]=1;self.geo.edges={};self.geo.positions={1:(4,5)}
        country=dict(states=[1,2],continent='Europe',ideology='democratic',ideology_name='Democratic',side=None,
            population=100,cultures={'test'},groups={'group'},position=(10,10))
        self.geo.countries={'A':copy.deepcopy(country),'B':copy.deepcopy(country)}

    def test_daily_is_order_independent_and_difficulty_seeded(self):
        pool=['C','A','B','D','E']
        self.assertEqual(daily_answer('2026-10-24','medium',pool),daily_answer('2026-10-24','medium',sorted(pool)))
        self.assertIn(daily_answer('2026-10-25','hard',pool),pool)
        with self.assertRaises(ValueError):daily_answer('2026-10-24','easy',[])

    def test_shared_country_names_have_stable_tag_qualifiers(self):
        names={'a':'France','a_variant':'France','b':'France','c':'Germany'}
        ids={'a':'FRA','a_variant':'FRA','b':'FRX','c':'GER'}
        labels=distinct_country_names(names,ids)
        self.assertEqual(labels,dict(a='France [FRA]',a_variant='France [FRA]',b='France [FRX]',c='Germany'))
        data=GameData.__new__(GameData)
        data.countries={tag:dict(name=name,aliases={normalise(tag),normalise(name)}) for tag,name in (('FRA','France'),('FRX','France'),('GER','Germany'))}
        data.border_profiles={};data.flag_labels={tag:c['name'] for tag,c in data.countries.items()}
        data._country_names();aliases,ambiguous=data.typed_country_aliases({'FRA'})
        self.assertNotIn('france',aliases);self.assertIn('france',ambiguous)
        self.assertIn(normalise('France [FRA]'),aliases);self.assertIn('fra',aliases)
        geo=Geography.__new__(Geography);geo.countries=data.countries;geo.lookup={}
        from collections import defaultdict
        geo.lookup=defaultdict(set)
        for tag,row in geo.countries.items():
            for alias in row['aliases']:geo.lookup[alias].add(tag)
        self.assertIsNone(geo.resolve('France',geo.countries))
        self.assertEqual(geo.resolve('France [FRX]',geo.countries),'FRX')

    def test_hints_thresholds_groups_and_direction(self):
        b=self.geo.countries['B'];b.update(population=110,states=[1],cultures={'other'})
        hints={title:(value,color) for title,value,color in self.geo.hints('B','A','medium')}
        self.assertEqual(hints['Population'][1],'green')
        self.assertIn('↑',hints['States'][0]);self.assertEqual(hints['Shared culture'][1],'yellow')
        b['population']=111
        self.assertEqual(dict((t,c) for t,_,c in self.geo.hints('B','A','easy'))['Population'],'black')
        hard=self.geo.hints('B','A','hard')
        self.assertNotIn('States',[t for t,_,_ in hard]);self.assertNotIn('Population',[t for t,_,_ in hard])
        self.assertFalse(any(arrow in value for _,value,_ in hard for arrow in '←→↑↓↗↘↙↖'))

    def test_missing_hints_are_omitted(self):
        self.geo.countries['A'].update(continent=None,ideology=None,population=None,cultures=set(),position=None)
        self.assertEqual([t for t,_,_ in self.geo.hints('B','A','hard')],[])

    def test_wrapped_distance_and_nearest_edge(self):
        km,arrow,_=self.geo.distance((99,5),(1,5))
        self.assertAlmostEqual(km,801.5);self.assertEqual(arrow,'→')
        self.assertEqual(self.geo.pinpoint_score(1,(4,5))['points'],1000)
        result=self.geo.pinpoint_score(1,(0,5))
        self.assertAlmostEqual(result['km'],1202.25);self.assertEqual(result['points'],399)
        self.assertEqual(self.geo.pinpoint_score(1,None)['points'],0)

    def test_daily_statistics_use_calendar_days_and_ignore_practice(self):
        rows=[];start=dt.date(2026,10,17)
        for n in range(7):rows.append(dict(game='rrdle',difficulty='hard',dev='Mike',day=str(start+dt.timedelta(days=n)),completed=True,finished=True,answered=3))
        board=daily_board(rows,'hard','2026-10-24')[0]
        self.assertEqual((board['current'],board['best'],board['win'],board['average']),(7,7,100,3))
        rows.append(dict(game='rrdle',difficulty='hard',dev='Mike',day='2026-10-24',completed=False,finished=True,answered=6))
        board=daily_board(rows,'hard','2026-10-24')[0]
        self.assertEqual((board['current'],board['best'],board['win']),(0,7,87.5))

    def test_sync_preserves_daily_authority_and_unfinished_guesses(self):
        empty={'tasks':[],'projects':[],'next_ref':1}
        base=dict(empty,rr_daily={'2026-10-24':{'easy':'ENG'}})
        mine=dict(empty,rr_daily={'2026-10-24':{'easy':'FRA','hard':'GER'}})
        remote=dict(empty,rr_daily={'2026-10-24':{'easy':'USA','medium':'MEX'}})
        out,_=merge_data(base,mine,remote)
        self.assertEqual(out['rr_daily']['2026-10-24'],dict(easy='ENG',medium='MEX',hard='GER'))
        out,_=merge_data(empty,mine,remote)
        self.assertEqual(out['rr_daily']['2026-10-24']['easy'],'USA')
        run=dict(id='daily',game='rrdle',score=0,guesses=['ENG'],updated='2026-10-24T10:00:00')
        a=dict(empty,rr_game_scores=[run]);b=dict(empty,rr_game_scores=[dict(run,guesses=['ENG','FRA'])])
        out,_=merge_data(empty,a,b)
        self.assertEqual(out['rr_game_scores'][0]['guesses'],['ENG','FRA'])
        out,_=merge_data(dict(empty,rr_game_scores=[run]),empty,empty)
        self.assertEqual(out['rr_game_scores'],[run])


if __name__=='__main__':unittest.main()
