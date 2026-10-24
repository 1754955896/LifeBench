"""Offline regressions for failures found by the real one-month pipeline run."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import runpy
import types
from datetime import datetime
from copy import deepcopy
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.lifebench.event.draft.event_tree import EventTree
from src.lifebench.event.draft.scheduler import Scheduler
from src.lifebench.utils.date_utils import TimeSpec
from src.lifebench.utils.route_estimation import estimate_surface_route
from src.lifebench.utils.locale_context import configure_settings, persona_scope
from src.lifebench.event.simulation.geolocation.baseline import simple_adjust_trajectory
from src.lifebench.event.simulation.geolocation.validator import validate_location_records
from src.lifebench.event.simulation.geolocation.export import attach_event_geodata
from src.lifebench.utils.json_utils import remove_json_wrapper
from src.lifebench.event.event_formatter import EventFormatter
from src.lifebench.event.tools.check_event_matching import is_date_in_range
from run_generation import fixture
from src.lifebench.event.qa_generator.base_generator import BaseQAGenerator
from src.lifebench.event.qa_generator.qa_single_generator import QASingleGenerator
from src.lifebench.event.qa_generator.qa_unanswerable_generator import QAUnanswerableGenerator
from src.lifebench.event.qa_generator.phone_operation_generator import PhoneOperationGenerator
from src.lifebench.event.all_qa_generator import QAGenerator
from src.lifebench.utils.locale_context import configure_generation_time_range, localize_prompt, LocaleThreadPoolExecutor
from src.lifebench.utils.locale_context import generation_date_allowed, qa_ask_date_allowed
from src.lifebench.event.phone_generator import CommunicationOperationGenerator, GalleryOperationGenerator, NoteCalendarOperationGenerator, PushOperationGenerator


class EventJSONChecks(unittest.TestCase):
    def parse(self, response, international=True):
        # Parsing itself needs neither a constructed event planner nor API calls.
        with patch('src.lifebench.event.draft.event_tree.international_run', return_value=international):
            with contextlib.redirect_stdout(io.StringIO()):
                return EventTree._extract_json_from_llm_output(None, response)

    def test_english_names_and_quotes_survive(self):
        events = [{'name': "Regent's Park", 'location': "St James's Square",
                   'description': 'Tom said "you alright?"', 'date': ['2026-01-28']}]
        self.assertEqual(self.parse(json.dumps(events)), events)

    def test_urls_unicode_and_whitespace_survive(self):
        events = [{'name': 'Caf\u00e9', 'url': 'https://example.org/book',
                   'description': "Oliver's  two spaces\nand Chlo\u00e9's notes"}]
        self.assertEqual(self.parse('```json\n' + json.dumps(events, ensure_ascii=False) + '\n```'), events)

    def test_legacy_repairs_remain_available(self):
        malformed = "[{'name': 'coffee', 'date': ['2026-01-01',],}]"
        expected = [{'name': 'coffee', 'date': ['2026-01-01']}]
        self.assertEqual(self.parse(malformed), expected)
        self.assertEqual(self.parse(malformed, international=False), expected)

    def test_invalid_json_still_fails(self):
        with self.assertRaises(ValueError):
            self.parse('[{"name": invalid}]')

    def test_international_common_parser_preserves_unicode(self):
        payload = {'name': 'Chlo\u00e9', 'place': 'Caf\u00e9', 'other': '\u0623\u062d\u0645\u062f'}
        raw = '```json\n' + json.dumps(payload, ensure_ascii=False) + '\n```'
        with patch('src.lifebench.utils.json_utils.international_run', return_value=True):
            self.assertEqual(json.loads(remove_json_wrapper(raw)), payload)

    def test_international_common_parser_removes_invalid_control_characters(self):
        with patch('src.lifebench.utils.json_utils.international_run', return_value=True):
            self.assertEqual(json.loads(remove_json_wrapper('{"name":"Chlo\u00e9\x00"}')), {'name': 'Chlo\u00e9'})


class RouteFallbackChecks(unittest.TestCase):
    origin = {'location': '-0.1300,51.5100', 'country_code': 'GB'}
    destination = {'location': '-0.1400,51.5200', 'country_code': 'GB'}

    def test_transit_estimate_keeps_mode_and_provenance(self):
        route = estimate_surface_route(self.origin, self.destination, 'transit')
        self.assertEqual(route['mode'], 'transit')
        self.assertFalse(route['map_verified'])
        self.assertGreater(route['distance_km'], 0)
        self.assertGreater(route['duration_minutes'], 0)

    def test_invalid_coordinates_are_rejected(self):
        for coordinates in ('nan,51.5', '500,51.5', 'bad', '0,100'):
            self.assertIsNone(estimate_surface_route(dict(self.origin, location=coordinates), self.destination, 'walking'))

    def test_unknown_modes_and_cross_country_are_rejected(self):
        self.assertIsNone(estimate_surface_route(self.origin, self.destination, 'flight'))
        self.assertIsNone(estimate_surface_route(self.origin, dict(self.destination, country_code='US'), 'walking'))

    def simulate_leg(self, route_result, policy='overseas'):
        configure_settings(policy)
        try:
            with persona_scope(fixture('gb')):
                points = [dict(self.origin, name='Home', address='Home', city='London'),
                          dict(self.destination, name='Office', address='Office', city='London')]
                payload = {'events': 'A synthetic day', 'locations': [
                    {'name': 'Home', 'city': 'London', 'start_time': '08:00', 'end_time': '08:30'},
                    {'name': 'Office', 'city': 'London', 'start_time': '09:00', 'end_time': '17:00', 'mode': 'transit'}]}
                mind = SimpleNamespace(_simple_geo_reference={'stops': points}, current_date='2026-01-01',
                                       persona={'name': 'Oliver'}, maptools=Mock(),
                                       llm_call_j=lambda *args: json.dumps(payload))
                mind.maptools.route_between_pois.return_value = route_result
                simple_adjust_trajectory(mind, '', 'Work day')
                return mind.final_location_records['legs'][0]
        finally:
            configure_settings()

    def test_live_path_accepts_tagged_estimate(self):
        leg = self.simulate_leg(None)
        self.assertEqual(leg['source'], 'synthetic_route_estimate')
        self.assertEqual(leg['mode'], 'transit')
        self.assertEqual(leg['estimate_method'], 'straight_line_detour_speed')
        self.assertFalse(leg['map_verified'])
        self.assertLessEqual(leg['confidence'], 0.5)

    def test_real_route_remains_verified(self):
        leg = self.simulate_leg({'duration_seconds': 1200, 'distance_meters': 4500})
        self.assertTrue(leg['map_verified'])
        self.assertEqual(leg['source'], 'map_route')
        self.assertEqual(leg['distance_km'], 4.5)

    def test_default_missing_route_behavior_is_preserved(self):
        leg = self.simulate_leg(None, policy='amap')
        self.assertEqual(leg['source'], 'unresolved')
        self.assertFalse(leg['map_verified'])
        self.assertEqual(leg['duration_minutes'], 0)

    def test_same_building_activity_needs_no_travel_leg(self):
        records = {'stops': [dict(stop_id=key, longitude=-0.13, latitude=51.51) for key in ('a','b')],
                   'legs': [], 'event_segments': [{'kind': 'activity', 'stop_id': key} for key in ('a','b')]}
        self.assertEqual(validate_location_records(records), [])

    def test_nearby_uk_administrative_names_are_not_cross_city_errors(self):
        configure_settings('overseas')
        try:
            with persona_scope(fixture('gb')):
                stops = [dict(stop_id='a', longitude=-0.13, latitude=51.51, city='London'),
                         dict(stop_id='b', longitude=-0.14, latitude=51.52, city='Westminster')]
                records = {'stops': stops, 'legs': [{'leg_id': 'x', 'origin_stop_id': 'a',
                           'destination_stop_id': 'b', 'mode': 'walking', 'duration_minutes': 30,
                           'distance_km': 1.8}], 'event_segments': [
                               {'kind': 'activity', 'stop_id': 'a'},
                               {'kind': 'travel', 'origin_stop_id': 'a', 'destination_stop_id': 'b'},
                               {'kind': 'activity', 'stop_id': 'b'}]}
                self.assertEqual(validate_location_records(records), [])
        finally:
            configure_settings()

    def test_unmatched_narrative_travel_is_explicitly_unverified(self):
        configure_settings('overseas')
        try:
            with persona_scope(fixture('gb')):
                row = attach_event_geodata([{'kind': 'travel', 'name': 'Unmatched transfer'}], {})[0]
                self.assertEqual(row['mobility']['source'], 'narrative_unverified')
                self.assertFalse(row['mobility']['map_verified'])
                self.assertNotIn('distance_km', row['mobility'])
                self.assertNotIn('geo', row)
        finally:
            configure_settings()


class DateRangeChecks(unittest.TestCase):
    def test_matching_uses_explicit_range_and_keeps_legacy_default(self):
        self.assertTrue(is_date_in_range('2026-01-31', datetime(2026,1,1), datetime(2026,1,31)))
        self.assertFalse(is_date_in_range('2026-02-01', datetime(2026,1,1), datetime(2026,1,31)))
        self.assertTrue(is_date_in_range('2025-01-01'))
        self.assertFalse(is_date_in_range('2026-01-01'))

    def test_simulator_cli_passes_dates_to_formatter(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            formatter = Mock()
            argv = ['simulator.py', '--file-path', folder, '--generate-data', '0',
                    '--start-date', '2026-01-01', '--end-date', '2026-01-31']
            dummy = types.ModuleType('src.lifebench.event.daily_simulator')
            with patch.dict(sys.modules, {'src.lifebench.event.daily_simulator': dummy}):
                with patch.object(sys, 'argv', argv), patch('src.lifebench.event.event_formatter.EventFormatter', return_value=formatter):
                    with patch('src.lifebench.utils.locale_context.bind_persona_file'), patch('src.lifebench.utils.utils_io.read_json_file', return_value={}):
                        with contextlib.redirect_stdout(io.StringIO()):
                            runpy.run_path(str(Path(__file__).resolve().parents[2]/'scripts/run/simulator.py'), run_name='__main__')
            formatter.run.assert_called_once_with(max_workers=30, start_date='2026-01-01', end_date='2026-01-31')

    def test_empty_formatter_result_cannot_be_reported_as_success(self):
        formatter = EventFormatter.__new__(EventFormatter)
        formatter.formatted_events = []
        with patch.object(formatter, 'process_all_files'), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                formatter.run(start_date='2026-01-01', end_date='2026-01-31')


class PartialYearChecks(unittest.TestCase):
    def probe(self, draft):
        probe = QASingleGenerator.__new__(QASingleGenerator)
        BaseQAGenerator.__init__(probe, draft_event=draft)
        return probe

    def test_partial_qa_months_and_end_date(self):
        probe = self.probe({'2026-01':[{'date':'2026-01-01'}]})
        self.assertEqual(probe.qa_month_numbers(2026), [1])
        self.assertEqual(probe.qa_period_end(), datetime(2026,12,31))

    def test_full_2025_qa_months_remain_unchanged(self):
        probe = self.probe({f'2025-{month:02d}':[{}] for month in range(1,13)})
        self.assertEqual(probe.qa_month_numbers(2025), list(range(1,13)))
        self.assertEqual(probe.qa_period_end(), datetime(2025,12,31))

    def test_single_qa_never_schedules_missing_months(self):
        probe = self.probe({'2026-01':[{}]})
        with patch.object(probe,'generate_monthly_qa',return_value=[]) as generate:
            with patch.object(probe,'_filter_and_refine_questions',return_value=[]), contextlib.redirect_stdout(io.StringIO()):
                probe.QAGen(year=2026)
        self.assertEqual(generate.call_count,7)
        self.assertTrue(all(call.args==(2026,1) for call in generate.call_args_list))

    def test_ask_time_uses_partial_year_deadline(self):
        probe = self.probe({'2026-01':[{}]})
        probe.daily_event=[{'event_id':'1','date':['2026-01-20 10:00:00至2026-01-20 11:00:00']}]
        with patch('src.lifebench.event.qa_generator.qa_single_generator.random.randint',side_effect=[0,1]):
            self.assertEqual(probe._adjust_ask_time_if_needed(['1'],'2026-01'), '2026-01-21')
        with patch('src.lifebench.event.qa_generator.qa_unanswerable_generator.random.randint',side_effect=[0,1]):
            self.assertEqual(QAUnanswerableGenerator._generate_ask_time(probe,'2026-01-20',2026,1),'2026-02-01')

    def test_retrospective_query_does_not_expand_phone_fact_scope(self):
        try:
            configure_generation_time_range('2026-01-01','2026-01-31')
            self.assertFalse(generation_date_allowed('2026-12-31'))
            self.assertTrue(qa_ask_date_allowed('2026-12-31'))
            self.assertFalse(qa_ask_date_allowed('2027-01-01'))
        finally:
            configure_generation_time_range()

    def test_time_scope_changes_constraints_without_rewriting_historical_input(self):
        raw='毕业年份为2025。Historical fact 2025-01-01. 年份必须为 2025。当前年份：2025年\n- datetime: 格式 YYYY-MM-DD，年份为 2025'
        configure_settings()
        try:
            configure_generation_time_range('2026-01-01','2026-01-31')
            with LocaleThreadPoolExecutor(max_workers=1) as executor:
                result=executor.submit(localize_prompt,raw).result()
            self.assertIn('Historical fact 2025-01-01',result)
            self.assertIn('毕业年份为2025',result)
            self.assertIn('- datetime: 格式 YYYY-MM-DD，年份为 2026',result)
            self.assertIn('年份必须为 2026',result)
            self.assertIn('2026-01-31',result)
        finally:
            configure_generation_time_range()
        self.assertEqual(localize_prompt(raw),raw)

    def phone_cases(self,year):
        date=f'{year}-01-01 10:00:00'
        return [
            (CommunicationOperationGenerator,dict(event_id='1',type='sms',message_content='Hello',contactName='Tom',phoneNumber='+447700900000',datetime=date,message_type='接收')),
            (GalleryOperationGenerator,dict(event_id='1',type='photo',caption='London',title=f'IMG_{year}0101_100000',datetime=date,location=dict(province='England',city='London',district='',streetName='',streetNumber='',poi='Park'),faceRecognition=[],imageTag=[],ocrText='',shoot_mode='正常拍照',image_size='4032×3024')),
            (PushOperationGenerator,dict(event_id='1',type='push',title='Notice',content='Hello',datetime=date,source='Bank',push_status='未读',jump_path='')),
            (NoteCalendarOperationGenerator,dict(event_id='1',type='note',title='Note',content='Hello',datetime=date)),
            (NoteCalendarOperationGenerator,dict(event_id='1',type='calendar',title='Meeting',description='Work',start_time=date,end_time=f'{year}-01-01 11:00:00',datetime=date))]

    def test_phone_validators_use_2026_generation_year(self):
        try:
            configure_generation_time_range('2026-01-01','2026-01-31')
            for cls,data in self.phone_cases(2026):
                generator=cls.__new__(cls)
                with self.subTest(cls=cls.__name__,type=data['type']):
                    self.assertTrue(generator._validate_format_only(deepcopy(data))[0])
                    invalid=deepcopy(data);invalid['datetime']='2025-01-01 10:00:00'
                    self.assertFalse(generator._validate_format_only(invalid)[0])
                    outside=deepcopy(data);outside['datetime']='2026-02-01 10:00:00'
                    self.assertFalse(generator._validate_format_only(outside)[0])
        finally:
            configure_generation_time_range()

    def test_phone_default_year_is_still_2025(self):
        configure_generation_time_range()
        for cls,data in self.phone_cases(2025):
            self.assertTrue(cls.__new__(cls)._validate_format_only(deepcopy(data))[0])

    def test_qa_phone_evidence_uses_current_year_and_month(self):
        generator=PhoneOperationGenerator.__new__(PhoneOperationGenerator)
        try:
            configure_generation_time_range('2026-01-01','2026-01-31')
            for cls,data in self.phone_cases(2026):
                valid,invalid,reasons=generator._validate_format([deepcopy(data)],data['type'])
                self.assertEqual(len(valid),1,reasons)
                outside=deepcopy(data);outside['datetime']='2026-03-01 10:00:00'
                self.assertEqual(len(generator._validate_format([outside],data['type'])[0]),0)
        finally:
            configure_generation_time_range()
        for cls,data in self.phone_cases(2025):
            self.assertEqual(len(generator._validate_format([deepcopy(data)],data['type'])[0]),1)

    def test_qa_agent_chat_accepts_iso_date_contract(self):
        generator=PhoneOperationGenerator.__new__(PhoneOperationGenerator)
        try:
            configure_generation_time_range('2026-01-01','2026-01-31')
            row={'type':'agent_chat','date':'2026-01-15','conversation':{}}
            self.assertEqual(len(generator._validate_format([row],'agent_chat')[0]),1)
        finally:
            configure_generation_time_range()


class QAResumeChecks(unittest.TestCase):
    def test_resume_restores_phone_evidence_before_reusing_questions(self):
        class Stub(BaseQAGenerator):
            def __init__(self, action):
                super().__init__()
                self.action=action
            def QAGen(self, **kwargs):
                return self.action(self)

        def question(text):
            return {'question':text,'answer':'A','score_points':[], 'question_type':['test'],
                    'required_events_id':[],'evidence':[{'type':'sms','phone_id':1}], 'ask_time':'2026-12-31'}
        def first(generator):
            generator.phonedata={'sms':[{'phone_id':1,'datetime':'2026-01-15 10:00:00','message_content':'Evidence'}]}
            generator.phone_id_counters={'sms':2}
            return [question('First')]
        def interrupt(generator):
            raise KeyboardInterrupt()
        def coordinator(folder, action1, action2):
            parent=QAGenerator(folder,auto_discover=False,year=2026)
            parent.generators={name:{'instance':Stub(action),'config':{'qagen_params':{}},'order':order}
                               for name,action,order in [('first',action1,1),('second',action2,2)]}
            return parent

        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            interrupted=coordinator(folder,first,interrupt)
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
                interrupted.generate_all_qa(2026)
            self.assertFalse((Path(folder)/'phone_data/new/sms.json').exists())

            should_not_run=Mock(side_effect=AssertionError('Completed QA must resume with its evidence'))
            def second(generator):
                self.assertEqual(generator.phonedata['sms'][0]['message_content'],'Evidence')
                self.assertEqual(generator.phone_id_counters['sms'],2)
                return [question('Second')]
            resumed=coordinator(folder,should_not_run,second)
            with patch.object(resumed,'_filter_unanswerable_qa_parallel',side_effect=lambda data,name:(data,{})):
                with patch.object(resumed,'_classify_qa_types_parallel',side_effect=lambda data:data):
                    with patch.object(resumed,'_regenerate_score_points_parallel',side_effect=lambda data,name:data):
                        with contextlib.redirect_stdout(io.StringIO()):
                            resumed.generate_all_qa(2026)
            should_not_run.assert_not_called()
            self.assertEqual(len(json.loads((Path(folder)/'QA_all/QA.json').read_text(encoding='utf-8'))),2)
            saved=json.loads((Path(folder)/'phone_data/new/sms.json').read_text(encoding='utf-8'))
            self.assertEqual(saved[0]['phone_id'],1)


class ResumeSummaryChecks(unittest.TestCase):
    def resume(self, checkpoint):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            base = Path(folder)
            process = base / 'process'
            process.mkdir()
            for name, value in {
                'optimized_timelines.json': {}, 'rich_timeline.json': {},
                'final_timeline.json': checkpoint, 'event_decompose_dfs.json': [],
            }.items():
                (process / name).write_text(json.dumps(value), encoding='utf-8')
            planner = Scheduler({'name': 'Oliver'}, str(base), spec=TimeSpec(2026, 1))
            with patch.object(planner, 'monthly_event_planning', side_effect=AssertionError('Checkpoint must be reused')):
                with patch.object(planner, 'parallel_daily_event_refine') as refine:
                    with contextlib.redirect_stdout(io.StringIO()):
                        planner.generate_yearly_timeline_draft(planner.persona, output_path=str(base))
                    refine.assert_called_once()
            return planner.yearly_summary

    def test_resume_restores_saved_summary(self):
        self.assertEqual(self.resume({'yearly_summary': 'January guidance', 'analysis_results': {}}),
                         'January guidance')

    def test_resume_accepts_older_checkpoint(self):
        self.assertEqual(self.resume({'comprehensive_summary': 'Older January summary', 'analysis_results': {}}),
                         'Older January summary')


if __name__ == '__main__':
    unittest.main()
