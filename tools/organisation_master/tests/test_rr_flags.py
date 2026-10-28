"""Medium flags must filter using the path that difficulty actually displays."""
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Scripts'))
from rr_games_data import QuestionFactory,read_image


class FlagQuestions(unittest.TestCase):
    def setUp(self):
        self.countries={
            'MAP':dict(name='Startup country',flag='startup',base_flag='base',on_map=True),
            'OFF':dict(name='Off-map country',flag='off-ideology',base_flag='off-base',on_map=False),
            'BAD':dict(name='Off-map without base',flag='only-ideology',base_flag=None,on_map=False),
            'FALL':dict(name='On-map fallback',flag=None,base_flag='fallback-base',on_map=True),
        }
        self.data=SimpleNamespace(countries=self.countries,flag_labels={k:v['name'] for k,v in self.countries.items()},
            fingerprint=lambda path:path,flags=[],availability=lambda:{'flags':4})

    def test_medium_excludes_missing_base_and_keeps_startup_cosmetics(self):
        loaded=[]
        def image(path):
            self.assertIsNotNone(path);loaded.append(path)
            return Image.new('RGBA',(8,5),'red')
        factory=QuestionFactory(self.data,random.Random(12))
        with patch('rr_games_data.read_image',side_effect=image):
            for _ in range(100):
                q=factory.make_flags('medium')
                self.assertNotIn('BAD',q.labels)
                self.assertEqual(set(q.labels),{'MAP','OFF','FALL'})
                self.assertEqual(sum(q.accepts(key) for key,_ in q.options),1)
        self.assertEqual(set(loaded),{'startup','off-base','fallback-base'})

    def test_missing_image_is_unavailable_instead_of_crashing_pillow(self):
        self.assertIsNone(read_image(None))
        self.assertIsNone(read_image(''))


if __name__=='__main__':unittest.main()
