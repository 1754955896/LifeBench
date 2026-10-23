"""Offline regressions for country rules and default Amap compatibility."""
from copy import deepcopy
from datetime import date
import importlib
import inspect
import json
from pathlib import Path
import random
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.lifebench.utils.locale_context import configure_settings, persona_scope
from src.lifebench.persona import prompts, grounding
from src.lifebench.persona.address_generation import PersonaAddressService
from src.lifebench.persona.region_normalization import normalize_address, same_region
from src.lifebench.persona.international_policy import validate_commute

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from run_generation import fixture
GB = fixture('gb')
CN = fixture('cn')


def baseline(filename):
    source = subprocess.run(['git', 'show', '7f25d62:src/lifebench/persona/' + filename + '.py'],
                            cwd=ROOT, check=True, capture_output=True, encoding='utf-8').stdout
    module = types.ModuleType('src.lifebench.persona._baseline_' + filename)
    module.__package__ = 'src.lifebench.persona'
    exec(compile(source, '<baseline-' + filename + '>', 'exec'), module.__dict__)
    return module


class OptimizationChecks(unittest.TestCase):
    def setUp(self):
        configure_settings('overseas', {'valhalla_url': 'https://example.org'})
        self.scope = persona_scope(GB)
        self.scope.__enter__()

    def tearDown(self):
        self.scope.__exit__(None, None, None)
        configure_settings()

    def test_country_templates_are_selected(self):
        prompt = prompts.build_base_profile_prompt(GB, {}, '2025-12-31')
        self.assertIn('[PERSONA_INTERNATIONAL_STAGE:base_profile]', prompt)
        self.assertIn('gb-persona-v1', prompt)
        self.assertIn('routing_modes', prompt)

    def test_all_default_prompts_identical(self):
        configure_settings()
        values = dict(source=CN, seed_person=CN, profile=CN, structured_profile=CN, references={}, as_of_date='2025-12-31',
            expected_keys=list(CN), slots=[], relation_groups=[], dimensions=['习惯'], core_addresses=[],
            locked_facts={}, soft_clues={}, source_description='', diversity='low', variant_index=0,
            variant_seed=42, previous_blueprints=[], enriched={}, data={}, violations=[], allowed_paths=[])
        for name in prompts.__all__:
            if not name.startswith('build_'):
                continue
            builder = getattr(prompts, name)
            kwargs = {key: values[key] for key, parameter in inspect.signature(builder).parameters.items()
                      if key in values and parameter.kind != inspect.Parameter.VAR_KEYWORD}
            with self.subTest(builder=name):
                self.assertEqual(builder(**kwargs), builder.__wrapped__(**kwargs))

    def test_hybrid_keeps_explicit_transit(self):
        profile = deepcopy(GB)
        profile['work_desc'] = '每周三天去办公室，另外两天远程办公'
        source = deepcopy(GB)
        source['lifestyle_desc'] = '地铁通勤，不自驾'
        mobility = grounding.extract_mobility_profile(profile, source_profile=source)
        self.assertEqual(mobility['work_arrangement'], 'hybrid')
        self.assertEqual(mobility['primary_transport'], 'transit')
        self.assertEqual(PersonaAddressService._commute_preferences(profile, mobility)[0], 'transit')

    def test_model_transit_can_adapt_without_rewriting_user(self):
        profile = dict(GB, lifestyle_desc='地铁通勤')
        result = grounding.extract_mobility_profile(profile, source_profile=GB)
        self.assertFalse(result['explicit'])
        self.assertEqual(result['primary_transport'], 'walking')
        result = grounding.extract_mobility_profile(profile, source_profile=profile)
        self.assertTrue(result['explicit'])
        self.assertEqual(result['primary_transport'], 'transit')

    def test_borough_and_neighbourhood_are_distinct(self):
        raw = {'country_code': 'GB', 'province': 'England', 'city': 'London Borough of Camden', 'district': 'Hampstead'}
        normalized = normalize_address(raw)
        self.assertEqual(normalized['district'], 'Camden')
        self.assertEqual(normalized['neighbourhood'], 'Hampstead')
        self.assertEqual(normalized['city'], 'London')
        self.assertEqual(normalized['raw_provider_address']['city'], raw['city'])
        self.assertTrue(same_region(GB['home_address'], normalized))
        self.assertFalse(same_region(GB['home_address'], dict(raw, city='London Borough of Islington')))
        self.assertFalse(same_region(GB['home_address'], dict(raw, country_code='FR')))

    def test_neighbourhood_validation_uses_normalized_region(self):
        circle = {'circle_type': 'neighborhood', 'shared_facts': {'_structured_plan': True, 'neighborhood_region': 'Camden'}}
        address = {'country_code': 'GB', 'province': 'England', 'city': 'London Borough of Camden', 'district': 'Hampstead'}
        self.assertEqual(grounding.circle_contact_errors([{'home_address': address}], circle, GB), [])
        address['city'] = 'London Borough of Islington'
        self.assertEqual(grounding.circle_contact_errors([{'home_address': address}], circle, GB), [])
        address['country_code']='FR'
        self.assertTrue(grounding.circle_contact_errors([{'home_address': address}], circle, GB))

    def test_employer_is_local_and_deterministic(self):
        anchor = grounding.build_employer_anchor(GB, 42)
        self.assertNotIn('有限公司', anchor['name'])
        self.assertTrue(anchor['name'].endswith('Ltd'))
        self.assertFalse(anchor['relationship_verified'])
        self.assertEqual(anchor, grounding.build_employer_anchor(GB, 42))

    def test_unverified_transit_estimate_is_not_mislabeled_as_map(self):
        fake = types.SimpleNamespace(get_duration_between_pois=lambda *a, **k: self.fail('unsupported transit must not call a walking route'))
        service = PersonaAddressService(map_tool=fake)
        home = {'name': 'home', 'location': '-0.1,51.5'}
        work = {'name': 'office', 'location': '-0.12,51.51'}
        service._select_core_pair(GB, [home], [work], random.Random(42), {'primary_transport': 'transit', 'explicit': True})
        self.assertGreater(service.last_assignment_metrics['commute_minutes'],0)
        self.assertEqual(service.last_assignment_metrics['duration_source'],'estimate')
        self.assertFalse(service.last_assignment_metrics['route_verified'])
        self.assertEqual(service.last_assignment_metrics['commute_transport'], 'transit')

    def test_mode_keyword_absence_is_a_review_note(self):
        context={'commute':{'commute_transport':'walking','status':'verified','route_api_used':True}}
        self.assertEqual(grounding.narrative_grounding_errors({'lifestyle_desc':'Il se rend au bureau à pied.'},context),[])
        self.assertEqual(context['review_notes'][0]['code'],'NARRATIVE_MODE_UNCONFIRMED')

    def test_unavailable_route_is_not_estimated(self):
        configure_settings('overseas',{'valhalla_url':'https://example.org'},{'allow_fictional_details':False})
        service = PersonaAddressService(map_tool=types.SimpleNamespace(get_duration_between_pois=lambda *a, **k: None))
        home, work = {'name': 'h', 'location': '-0.1,51.5'}, {'name': 'w', 'location': '-0.12,51.51'}
        service._select_core_pair(GB, [home], [work], random.Random(1), {'primary_transport': 'walking'})
        self.assertIsNone(service.last_assignment_metrics['commute_minutes'])

    def test_bad_commute_fails_before_contacts(self):
        context = {'commute': {'commute_transport': 'walking', 'commute_minutes': 78.4, 'route_api_used': True},
                   'mobility_profile': {'primary_transport': 'transit', 'explicit': True}}
        self.assertTrue(validate_commute(context))
        with self.assertRaises(ValueError):
            grounding.enrich_grounding_context([], context['commute'], {}, context['mobility_profile'])

    def test_no_unverified_leasing_narrative(self):
        context = {'employer_anchor': {'relationship_verified': False}}
        self.assertTrue(grounding.narrative_grounding_errors({'work_desc': '租用楼层办公'}, context))

    def test_synthetic_leasing_and_schools_are_allowed(self):
        context = {'employer_anchor': grounding.build_employer_anchor(GB,42)}
        self.assertEqual(grounding.narrative_grounding_errors({'work_desc':'租用楼层办公'},context), [])
        service=PersonaAddressService(map_tool=types.SimpleNamespace())
        anchors=[dict(circle_id='school1',circle_type='school',shared_facts={'institution_name':'Alderwick College'})]
        grounded,pois=service.ground_circle_anchors(anchors,GB,[])
        self.assertEqual(grounded[0]['shared_facts']['institution_name'],'Alderwick College')
        self.assertEqual(grounded[0]['shared_facts']['institution_source'],'synthetic')
        self.assertFalse(grounded[0]['shared_facts']['institution_verified'])
        self.assertEqual(pois,[])

    def test_synthetic_birth_place_does_not_require_map_lookup(self):
        service=PersonaAddressService(map_tool=types.SimpleNamespace(amap_geocode=lambda *a,**k:self.fail('birth place does not need live proof')))
        result=service._ground_birth_place({'country_code':'GB','province':'Scotland','city':'Glasgow','district':'Glasgow City'})
        self.assertEqual(result['verification'],'synthetic')
        self.assertEqual(result['city'],'Glasgow')

    def test_synthetic_contact_audit_does_not_require_fake_coordinates(self):
        person={'relation':[[{'name':'Alex','relation':'朋友','social circle':'朋友'}]]}
        audit=dict(contact_name='Alex',home_address='Glasgow',home_location='',home_source='synthetic',
                   birth_place_verified=False,birth_place_source='synthetic')
        self.assertEqual(grounding.semantic_quality_errors(person,None,{'contact_address_audit':[audit]}),[])

    def test_recorded_response_cache_revalidates_before_reuse(self):
        import tempfile
        from src.lifebench.utils.structured_llm import StructuredLLMCaller
        sys.path.insert(0,str(HERE))
        from trace_generation import install
        original=StructuredLLMCaller.call_json_object
        calls=[]
        def call(prompt):
            calls.append(prompt)
            return json.dumps({'value':len(calls)})
        try:
            with tempfile.TemporaryDirectory(prefix='cache-',dir=HERE) as folder:
                self.assertEqual(Path(folder).resolve().parent,HERE.resolve())
                caller=StructuredLLMCaller(object_call=call,reason_object_call=call,max_retries=0)
                install(folder)
                caller.call_json_object('same input')
                StructuredLLMCaller.call_json_object=original
                install(folder,replay_successes=True)
                reused=caller.call_json_object('same input')
                self.assertEqual(len(calls),1)
                self.assertEqual(reused.data,{'value':1})
                fresh=caller.call_json_object('same input',validator=lambda data:[] if data['value']==2 else ['stale value'])
                self.assertEqual(len(calls),2)
                self.assertEqual(fresh.data,{'value':2})
        finally:
            StructuredLLMCaller.call_json_object=original

    def test_shared_school_does_not_require_literal_name_in_each_description(self):
        circle={'circle_type':'school','shared_facts':{'institution_name':'University of Manchester'}}
        contacts=[{'relation_description':'本科室友，毕业后每月交流近况。'}]
        self.assertEqual(grounding.circle_contact_errors(contacts,circle,GB),[])
        configure_settings()
        self.assertTrue(grounding.circle_contact_errors(contacts,circle,CN))

    def test_missing_administrative_data_is_not_a_conflict(self):
        from src.lifebench.persona.region_normalization import region_relationship
        self.assertEqual(region_relationship(GB['home_address'],{'country_code':'GB','city':'London'}),'unknown')

    def test_declared_region_keeps_consistent_synthetic_metadata(self):
        profile=deepcopy(GB)
        poi={'geocode':{'country_code':'GB','province':'England','city':'Westminster','district':'Mayfair','street':'Newman Street'}}
        PersonaAddressService._synchronize_address(profile,'home_address',poi,{'city':'London','district':'Camden'})
        self.assertEqual(profile['home_address']['district'],'Camden')
        self.assertEqual(profile['home_address']['administrative_area'],'Camden')
        self.assertEqual(profile['home_address']['administrative_area_source'],'synthetic')
        self.assertEqual(poi['geocode']['administrative_area'],'Camden')
        self.assertEqual(profile['home_address']['raw_provider_address']['district'],'Mayfair')

    def test_fully_remote_does_not_become_hybrid_from_weekly_meetings(self):
        from src.lifebench.persona.international_policy import work_arrangement
        profile=dict(GB, work_desc='完全远程，每周进行线上例会')
        self.assertEqual(work_arrangement(profile),'remote')

    def test_synthesis_policy_changes_resume_fingerprint(self):
        from src.lifebench.utils.locale_context import context_fingerprint
        first=context_fingerprint(GB)
        configure_settings('overseas', {'valhalla_url':'https://example.org'}, {'allow_fictional_details':False})
        self.assertNotEqual(first,context_fingerprint(GB))

    def test_default_rules_match_committed_snapshot(self):
        configure_settings()
        old = baseline('grounding')
        for source in (CN, dict(CN, lifestyle_desc='地铁通勤'), dict(CN, work_desc='每周远程办公')):
            self.assertEqual(grounding.extract_mobility_profile(source), old.extract_mobility_profile(source))
            self.assertEqual(grounding.build_employer_anchor(source, 42), old.build_employer_anchor(source, 42))
        old_address = baseline('address_generation')
        self.assertEqual(PersonaAddressService._commute_preferences(dict(CN, work_desc='每周远程办公'), {'primary_transport': 'transit'}),
                         old_address.PersonaAddressService._commute_preferences(dict(CN, work_desc='每周远程办公'), {'primary_transport': 'transit'}))

    def test_default_basic_stage_trace_and_output_match_snapshot(self):
        configure_settings()
        current = importlib.import_module('src.lifebench.persona.persona_gen')
        old = baseline('persona_gen')
        from src.lifebench.persona.stages import GenerationContext
        def execute(module):
            trace = []
            owner = module.PersonaGenerator.__new__(module.PersonaGenerator)
            owner.seed, owner.as_of_date = 42, date(2025, 12, 31)
            owner._context = lambda *a: GenerationContext(as_of_date=owner.as_of_date, caller=None, references={})
            def stage(label):
                def run(person, context):
                    trace.append((label, deepcopy(person)))
                    if label == 'narrative':
                        return {key: '固定描述' for key in prompts.NARRATIVE_FIELDS}, 'hash'
                    return deepcopy(person), 'hash'
                return run
            def ground(person, locked, **kwargs):
                trace.append(('map', deepcopy(person), deepcopy(locked), kwargs))
                return deepcopy(person), []
            owner.address_service = types.SimpleNamespace(ground_core_addresses=ground, last_assignment_metrics={})
            with patch.object(module, 'generate_base_profile', stage('base')), \
                 patch.object(module, 'generate_profile_enrich', stage('enrich')), \
                 patch.object(module, 'generate_narratives', stage('narrative')):
                result = owner._generate_basic_one(deepcopy(CN), 0)
            return trace, result
        self.assertEqual(execute(current), execute(old))

    def test_default_relation_stage_trace_and_output_match_snapshot(self):
        configure_settings()
        current = importlib.import_module('src.lifebench.persona.persona_gen')
        old = baseline('persona_gen')
        from src.lifebench.persona.stages import GenerationContext
        from src.lifebench.persona.internal_models import RelationSlot
        from src.lifebench.persona.normalization import normalize_contact_items
        groups=[]
        for gi in range(4):
            group=[]
            for ci in range(4):
                group.append(dict(name='Friend %d-%d'%(gi,ci),relation='朋友',**{'social circle':'Reading group %d'%gi},
                    gender='男',age=30,birth_date='1995-05-10',home_address=deepcopy(CN['home_address']),
                    birth_place=deepcopy(CN['birth_place']),personality='INTJ',economic_level='稳定',
                    occupation='软件工程师',organization='Cedar Services',nickname='Friend',relation_description='读书小组朋友'))
            groups.append(group)
        saved=deepcopy(CN)
        saved['_index']=0
        saved['_core_locations']=[dict(name='测试住宅',location='116.30,39.98',address_type='居住地'),
                                   dict(name='测试办公楼',location='116.31,39.98',address_type='工作地')]
        saved['_quality_context']=grounding.enrich_grounding_context(saved['_core_locations'],{},grounding.build_employer_anchor(CN,42),grounding.extract_mobility_profile(CN))
        locations=[dict(name='居住地·测试住宅',location='116.30,39.98'),dict(name='工作地·测试办公楼',location='116.31,39.98')]
        def execute(module):
            trace = []
            owner = module.PersonaGenerator.__new__(module.PersonaGenerator)
            owner.seed, owner.as_of_date = 42, date(2025, 12, 31)
            owner._context = lambda *a: GenerationContext(as_of_date=owner.as_of_date, caller=None, references={})
            def slots(internal, context):
                trace.append(('slots', deepcopy(internal.data)))
                result, anchors = [], []
                for gi, group in enumerate(groups):
                    circle = 'group%d' % gi
                    anchors.append(dict(circle_id=circle,circle_type='other',shared_facts={}))
                    for ci, contact in enumerate(group):
                        result.append(RelationSlot(slot_id='%s:%d'%(circle,ci), name_hint=contact['name'],
                            relation=contact['relation'],social_circle=contact['social circle'],circle_id=circle,circle_type='other'))
                context.circle_anchors = anchors
                return result, 'hash'
            def circles(anchors,*a,**k):
                trace.append(('circle_map',deepcopy(anchors)))
                return deepcopy(anchors), []
            def enrich(profile,context):
                trace.append(('enrich',deepcopy(profile)))
                return {}, 'hash'
            def contacts(internal,slots,context,gi):
                trace.append(('contacts',gi,deepcopy(slots)))
                return normalize_contact_items(deepcopy(groups[gi]),'contacts:%d'%gi), 'hash'
            def contact_map(profile,contacts,*a,**k):
                trace.append(('contact_map',[c.name for c in contacts]))
                return []
            def consistency(internal,context):
                trace.append(('consistency',len(internal.relation_groups)))
            def surroundings(*a,**k):
                trace.append(('surroundings',))
                return deepcopy(locations)
            owner.address_service = types.SimpleNamespace(ground_circle_anchors=circles,
                ground_contact_addresses=contact_map,generate_surrounding_locations=surroundings,
                consistency_errors=lambda *a:[])
            with patch.object(module,'generate_relation_slots',slots), patch.object(module,'generate_enrich',enrich), \
                 patch.object(module,'generate_contact_group',contacts), patch.object(module,'generate_persona_consistency',consistency):
                result=owner._generate_relations_for_basic(deepcopy(saved))
            return trace,result
        self.assertEqual(execute(current),execute(old))


if __name__ == '__main__':
    unittest.main(verbosity=2)
