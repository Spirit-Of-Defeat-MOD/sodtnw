"""Startup country presentation and permitted Hard name variants."""
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Scripts'))
from rr_games_data import GameData,QuestionFactory,normalise


class StartupNames(unittest.TestCase):
    def bank(self):
        politics=[SimpleNamespace(key='ruling_party',value='communism')]
        country=SimpleNamespace(states={1},get=lambda key:politics if key=='set_politics' else None)
        source=SimpleNamespace(countries={'SOV':country},mains=['communism'],all_mains=['communism'],
            flag_stems=['SOV'],flag_map={'sov.tga':'base-flag'},label=lambda *args:'',
            name=Mock(side_effect=lambda tag,ideology=None,raw=False:'USSR' if ideology=='communism' and not raw else 'Eurasia'),
            flag_path=Mock(return_value='startup-flag'))
        bank=GameData.__new__(GameData);bank.country_data=source
        bank.countries={};bank.flags=[];bank.border_profiles={}
        bank._countries();bank._country_names()
        return bank,source

    def test_startup_ideology_name_and_flag_are_requested_together(self):
        bank,source=self.bank()
        self.assertEqual(bank.countries['SOV']['name'],'USSR')
        self.assertEqual(bank.countries['SOV']['flag'],'startup-flag')
        source.flag_path.assert_called_once_with('SOV',ideology='communism')
        self.assertIn(unittest.mock.call('SOV',ideology='communism'),source.name.call_args_list)

    def test_non_hard_always_uses_startup_name(self):
        bank,_=self.bank();factory=QuestionFactory(bank,random.Random(7))
        for level in ('easy','medium'):
            self.assertEqual(factory.country_labels(level)['SOV'],'USSR')

    def test_hard_can_alternate_base_and_startup_names(self):
        bank,_=self.bank();factory=QuestionFactory(bank,random.Random(7))
        self.assertEqual({factory.country_labels('hard')['SOV'] for _ in range(40)},{'USSR','Eurasia'})

    def test_both_names_and_real_tag_are_valid_typed_answers(self):
        bank,_=self.bank();aliases,ambiguous=bank.typed_country_aliases({'SOV'})
        self.assertTrue({normalise(n) for n in ('SOV','USSR','Eurasia')}<=aliases)
        self.assertFalse(ambiguous)


if __name__=='__main__':unittest.main()
