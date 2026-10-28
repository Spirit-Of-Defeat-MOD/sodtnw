"""Milestone broadcasts must outlive stale snapshots and deliver once per developer."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"Scripts"))
from milestone_celebration import EVENTS, SEEN, publish, merge_records, restore_status, unseen, animation_for, mechanics_frame, technology_frame, mechanics_sound_step, technology_sound_step
from todo_sync import merge_data


class MilestoneDelivery(unittest.TestCase):
    def setUp(self):
        self.data = {"milestones": [{"name": "Culture Map Completion"}], "tasks": [{"ref": "RR-0001", "status": "To do"}]}

    def test_completion_is_explicit_idempotent_and_preserves_tasks(self):
        tasks=copy.deepcopy(self.data["tasks"])
        event=publish(self.data,"Culture Map Completion","Mike",["Nilo","George","Nilo"])
        self.assertEqual(event["thanks"],["Nilo","George"])
        self.assertEqual(event["animation"],"culture_duck")
        self.assertIsNone(publish(self.data,"Culture Map Completion","Globus",[]))
        self.assertEqual(self.data["tasks"],tasks)
        self.assertEqual(len(self.data[EVENTS]),1)

    def test_offline_delivery_and_independent_receipts(self):
        event=publish(self.data,"Culture Map Completion","Mike",[])
        self.assertEqual(unseen(self.data,"Nilo"),[event])
        self.data[SEEN]={"Nilo":{event["id"]:"2026-10-25T12:00:00+00:00"}}
        self.assertEqual(unseen(self.data,"Nilo"),[])
        self.assertEqual(unseen(self.data,"George"),[event])
        self.assertEqual(unseen(self.data,"George",[event["id"]]),[])

    def test_stale_client_cannot_erase_event_or_receipts(self):
        event=publish(self.data,"Culture Map Completion","Mike",[])
        self.data[SEEN]={"Nilo":{event["id"]:"2026-10-25T12:00:00+00:00"}}
        stale={"milestones":[{"name":"Culture Map Completion"}],"tasks":copy.deepcopy(self.data["tasks"])}
        merged,_=merge_data(copy.deepcopy(self.data),copy.deepcopy(stale),copy.deepcopy(stale))
        self.assertIn(event["id"],merged[EVENTS])
        self.assertEqual(unseen(merged,"Nilo"),[])
        self.assertTrue(merged["milestones"][0]["completed_event"])

    def test_simultaneous_thanks_and_seen_receipts_are_unioned(self):
        a=copy.deepcopy(self.data);b=copy.deepcopy(self.data)
        event=publish(a,"Culture Map Completion","Mike",["Nilo"])
        publish(b,"Culture Map Completion","Globus",["George"])
        a[SEEN]={"Nilo":{event["id"]:"one"}};b[SEEN]={"Mike":{event["id"]:"two"}}
        result=merge_records(a,b)
        self.assertEqual(set(result[EVENTS][event["id"]]["thanks"]),{"Nilo","George"})
        self.assertEqual(set(result[SEEN]),{"Nilo","Mike"})
        self.assertEqual(len(result[EVENTS]),1)

    def test_renaming_completed_milestone_keeps_snapshot_and_status(self):
        event=publish(self.data,"Culture Map Completion","Mike",[])
        milestone=self.data["milestones"][0];milestone["name"]="Culture map done"
        restore_status(self.data)
        self.assertEqual(milestone["completed_event"],event["id"])
        self.assertEqual(self.data[EVENTS][event["id"]]["name"],"Culture Map Completion")


class MechanicsCelebration(unittest.TestCase):
    def test_names_and_manual_style_selection(self):
        self.assertEqual(animation_for("Mechanics Completion"),"mechanics_duck")
        self.assertEqual(animation_for("Stage 2 — Mechanical systems"),"mechanics_duck")
        self.assertEqual(animation_for("Culture Map Completion"),"culture_duck")
        self.assertEqual(animation_for("Stage 2"),"celebration")
        data={"milestones":[{"name":"Stage 2"}]}
        self.assertEqual(publish(data,"Stage 2","Mike",[],animation="mechanics_duck")["animation"],"mechanics_duck")

    def test_effort_finishes_then_wipes_without_restarting(self):
        tightening=[mechanics_frame(i/10) for i in range(60)]
        self.assertEqual(tightening,sorted(tightening))
        self.assertEqual(set(tightening),set(range(8)))
        self.assertEqual(mechanics_frame(6),8)
        self.assertEqual(mechanics_frame(8),9)
        self.assertEqual(mechanics_frame(9.5),10)
        self.assertEqual(mechanics_frame(10.5),11)
        self.assertEqual(mechanics_frame(11.5),10)
        for second in (12,18,20,25,31.9):self.assertEqual(mechanics_frame(second),11)
        self.assertTrue(all(mechanics_frame(i/10)>=8 for i in range(60,320)))

    def test_struggle_cues_end_when_the_bolt_is_seated(self):
        self.assertEqual(mechanics_sound_step(.9),-1)
        self.assertEqual({mechanics_sound_step(i/10) for i in range(10,60)},{0,1,2,3})
        for second in (6,8,12,31.9):self.assertEqual(mechanics_sound_step(second),-1)


class TechnologyCelebration(unittest.TestCase):
    def test_technology_names_and_explicit_style(self):
        self.assertEqual(animation_for("Technology Completion"),"technology_duck")
        self.assertEqual(animation_for("Tech milestone"),"technology_duck")
        self.assertEqual(animation_for("Mechanics"),"mechanics_duck")
        data={"milestones":[{"name":"Stage 3"}]}
        self.assertEqual(publish(data,"Stage 3","Mike",[],animation="technology_duck")["animation"],"technology_duck")

    def test_gag_runs_once_and_soot_blink_keeps_animating(self):
        for time,frame in ((0,0),(2,1),(4,2),(5.7,3),(6,4)):
            self.assertEqual(technology_frame(time),frame)
        for cycle in range(9):
            start=5.82+cycle*2.7
            for offset,frame in ((.5,4),(2.15,5),(2.25,6),(2.37,7),(2.5,4)):
                self.assertEqual(technology_frame(start+offset),frame)
        self.assertTrue(all(technology_frame(t/10)>=4 for t in range(59,320)))


class TechnologySoundTiming(unittest.TestCase):
    def test_sound_beats_advance_once_and_stay_at_the_last_afterward(self):
        self.assertEqual(technology_sound_step(1.5),-1)
        for elapsed,step in ((1.7,0),(3.3,1),(4.6,2),(5.7,3),(5.9,4),(20,4),(31.9,4)):
            self.assertEqual(technology_sound_step(elapsed),step)
