"""Resume the normal relation stage from a saved base, retaining diagnostics."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.lifebench.utils.overseas_runtime import configure_map_tool
from src.lifebench.utils.locale_context import persona_scope
from src.lifebench.persona.persona_gen import PersonaGenerator
from src.lifebench.persona.grounding import enrich_grounding_context
from src.lifebench.persona.address_generation import PersonaAddressService
from trace_generation import install


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=Path, required=True)
    args = parser.parse_args()
    folder = args.folder.resolve()
    configure_map_tool(argparse.Namespace(map_tool='overseas', map_config=str(ROOT/'config/overseas_map.demo.json')))
    install(folder, replay_successes=True)
    people = json.loads((folder/'persona_list_basic_temp.json').read_text(encoding='utf-8'))
    source = json.loads((folder/'input.json').read_text(encoding='utf-8'))[0]
    for person in people:
        with persona_scope(person):
            # Only migrate region/source metadata; retain the successful base and route evidence.
            core = person.get('_core_locations') or []
            for field, role in (('home_address','居住地'),('workplace','工作地')):
                point = next((p for p in core if p.get('address_type') == role), None)
                if point:
                    # Re-normalize original provider components, not the older locked region overlay.
                    raw = (point.get('geocode') or {}).get('raw_provider_address') or {}
                    for key in ('city','province','district'):
                        if raw.get(key): point['geocode'][key] = raw[key]
                    locks={key:value for key,value in (source.get(field) or {}).items() if key in ('country_code','country','province','city','district')}
                    PersonaAddressService._synchronize_address(person,field,point,locks)
            context = person.get('_quality_context') or {}
            person['_quality_context'] = enrich_grounding_context(core, context.get('commute'),context.get('employer_anchor'),context.get('mobility_profile'))
    checkpoint = folder/'basic_checkpoint_migrated.json'
    checkpoint.write_text(json.dumps(people,ensure_ascii=False,indent=2),encoding='utf-8')
    generator = PersonaGenerator(str(ROOT/'src/lifebench/persona/persona_file/refer.json'),
        as_of_date='2025-12-31', seed=42, keep_checkpoints=True, generate_locations=True)
    result = generator.generate_relation_and_complete(str(checkpoint),str(folder/'persona_list.json'),max_workers=1)
    raise SystemExit(0 if result is not None else 3)
