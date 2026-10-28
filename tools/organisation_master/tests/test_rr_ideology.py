"""Ideology quiz rules, without reading mod files or creating windows."""
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Scripts'))
from rr_games_data import QuestionFactory


class IdeologyQuiz(unittest.TestCase):
    def setUp(self):
        mains={main:[main+'_'+str(n) for n in range(4)] for main in ('democratic','communism','neutrality','fascism')}
        subs={sub:main for main,tokens in mains.items() for sub in tokens}
        self.source=SimpleNamespace(ideologies=mains,sub_ideology=subs,label=lambda key,default:key.replace('_',' ').title())
        self.leader=dict(id='known:person:AAA',name='Test Leader',path='portrait',ideologies=('democratic_0','communism_0'))
        self.data=SimpleNamespace(country_data=self.source,leaders=[self.leader],availability=lambda:{'ideology':1})
        self.factory=QuestionFactory(self.data,random.Random(5))
        self.image_patch=patch('rr_games_data.read_image',return_value=Image.new('RGBA',(80,100),'red'))
        self.image_patch.start();self.addCleanup(self.image_patch.stop)

    def test_easy_asks_for_main_ideology(self):
        q=self.factory.question('ideology','easy')
        self.assertEqual(q.answers,{'democratic','communism'})
        self.assertEqual(set(q.labels),set(self.source.ideologies))
        self.assertEqual(sum(q.accepts(key) for key,_ in q.options),1)

    def test_normal_draws_sub_ids_from_every_group(self):
        q=self.factory.question('ideology','medium')
        self.assertEqual(q.answers,{'democratic_0','communism_0'})
        self.assertEqual(set(q.labels),set(self.source.sub_ideology))
        self.assertEqual(len(q.options),4)

    def test_hard_keeps_all_sub_ids_in_the_stated_group(self):
        for _ in range(8):
            q=self.factory.make_ideology('hard')
            parents={self.source.sub_ideology[key] for key in q.labels}
            self.assertEqual(len(parents),1)
            self.assertEqual({self.source.sub_ideology[key] for key,_ in q.options},parents)
            self.assertEqual(len(q.answers),1)
            self.assertIn('Main ideology:',q.detail)

    def test_main_only_role_is_usable_only_on_easy(self):
        self.data.leaders=[dict(self.leader,ideologies=('neutrality',))]
        self.assertEqual(self.factory.make_ideology('easy').answers,{'neutrality'})
        with self.assertRaises(ValueError):self.factory.question('ideology','medium')

    def test_colons_in_character_id_do_not_combine_different_people(self):
        self.data.leaders.append(dict(self.leader,id='known:other:AAA',name='Other Person',path='other',ideologies=('fascism_0',)))
        q=self.factory.make_ideology('medium')
        self.assertIn(q.answers,({'democratic_0','communism_0'},{'fascism_0'}))


if __name__=='__main__':unittest.main()
