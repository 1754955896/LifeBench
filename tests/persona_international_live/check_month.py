"""Check actual one-month pipeline artifacts; never treats exit zero alone as success."""
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.lifebench.utils.locale_context import configure_settings, persona_scope
from src.lifebench.event.simulation.geolocation.validator import validate_location_records

FOLDER=Path(__file__).resolve().parent/'monthly_2026_01'
EXPECTED={f'2026-01-{day:02d}' for day in range(1,32)}


def dates(value):
    found=set()
    if isinstance(value,dict):
        for key,child in value.items():
            if key=='date':
                for item in child if isinstance(child,list) else [child]:
                    if isinstance(item,str) and re.match(r'^\d{4}-\d{2}-\d{2}',item):
                        found.add(item[:10])
            if isinstance(child,(dict,list)):
                found.update(dates(child))
    elif isinstance(value,list):
        for child in value:
            found.update(dates(child))
    return found


def inspect_phone(folder):
    files={};days=set()
    for path in folder.glob('*.json'):
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        files[path.name]={'records':len(data),'bytes':path.stat().st_size}
        if path.name=='contact.json' or not isinstance(data,list): continue
        for record in data:
            if not isinstance(record,dict): continue
            for field in ('date','datetime','日期'):
                value=record.get(field)
                if isinstance(value,str) and re.match(r'^\d{4}-\d{2}-\d{2}',value): days.add(value[:10])
    return files,days


if __name__=='__main__':
    errors=[]
    report={'expected_days':31,'artifacts':{}}
    for name in ('daily_draft.json','daily_event.json','event_tree.json',
                 'summary/all_monthly_health_reports.json','phone_data/contact.json','QA_all/QA.json'):
        path=FOLDER/name
        if not path.exists():
            errors.append('Missing '+name)
            continue
        try:
            data=json.loads(path.read_text(encoding='utf-8-sig'))
            report['artifacts'][name]={'bytes':path.stat().st_size,'nonempty':bool(data),'records':len(data)}
            if not data: errors.append('Empty '+name)
            if name in ('daily_draft.json','daily_event.json'):
                seen=dates(data)
                report['artifacts'][name].update(days=len(seen),missing=sorted(EXPECTED-seen),outside=sorted(seen-EXPECTED))
                if seen!=EXPECTED: errors.append('Date coverage mismatch '+name)
            if name=='daily_event.json':
                mobility={'verified':0,'estimated':0,'narrative_unverified':0,'missing':0}
                for event in data:
                    if event.get('kind') not in ('travel','local_loop'): continue
                    route=event.get('mobility',{})
                    if route.get('map_verified'): mobility['verified']+=1
                    elif route.get('source')=='synthetic_route_estimate': mobility['estimated']+=1
                    elif route.get('source')=='narrative_unverified': mobility['narrative_unverified']+=1
                    else: mobility['missing']+=1
                report['mobility']=mobility
                if mobility['missing']: errors.append('Travel missing verification provenance')
            if name=='QA_all/QA.json':
                times=[row.get('ask_time') for row in data]
                outside=[value for value in times if isinstance(value,str) and not value.startswith('2026-')]
                report['qa']={'questions':len(data),'outside_ask_year':outside,
                              'undated_questions':sum(not value for value in times)}
                if outside: errors.append('QA ask times outside target year')
        except (OSError,ValueError) as error:
            errors.append(name+': '+type(error).__name__)
    for name in ('persona_context.json','stage_times.json'):
        if not (FOLDER/name).exists(): errors.append('Missing '+name)
    context_path=FOLDER/'persona_context.json'
    if context_path.exists():
        context=json.loads(context_path.read_text(encoding='utf-8'))
        report['locale']=context.get('locale',{})
        report['map_policy']=context.get('map_policy')
        if report['locale'].get('country_code')!='GB' or report['map_policy']!='overseas':
            errors.append('Wrong locale or map policy')
    completed=set()
    for path in (FOLDER/'sim').glob('checkpoint*.json'):
        completed.update(json.loads(path.read_text(encoding='utf-8')).get('completed_dates',[]))
    report['simulation']={'completed_days':len(completed),'missing':sorted(EXPECTED-completed),'outside':sorted(completed-EXPECTED)}
    if completed!=EXPECTED: errors.append('Simulation checkpoints do not cover the full month')
    geodata={'days':0,'issues':{},'verified_legs':0,'estimated_legs':0,'saved_diagnostic_issue_count':0}
    configure_settings('overseas')
    with persona_scope(json.loads((FOLDER/'persona.json').read_text(encoding='utf-8'))):
        for path in (FOLDER/'sim/intermediate').glob('*.json'):
            for day,data in json.loads(path.read_text(encoding='utf-8')).items():
                geodata['days']+=1
                records=data.get('location_records',{})
                issues=validate_location_records(records)
                geodata['saved_diagnostic_issue_count']+=len(data.get('location_reconciliation',{}).get('issues',[]))
                if records.get('coordinate_system')!='WGS-84': issues.append('Wrong coordinate system')
                for leg in records.get('legs',[]):
                    if leg.get('map_verified'):
                        geodata['verified_legs']+=1
                    elif leg.get('source')=='synthetic_route_estimate':
                        geodata['estimated_legs']+=1
                        if not leg.get('estimate_method') or leg.get('confidence',1)>0.65:
                            issues.append('Estimate missing method or low confidence')
                    else:
                        issues.append('Unresolved travel leg')
                if issues: geodata['issues'][day]=issues
    configure_settings()
    report['geodata']=geodata
    if geodata['days']!=31 or geodata['issues']: errors.append('Geodata validation failed')
    report['phone_files'],phone_days=inspect_phone(FOLDER/'phone_data')
    if not any(item['records'] for name,item in report['phone_files'].items() if name!='contact.json'):
        errors.append('No generated phone activities')
    report['phone_days']={'days':len(phone_days),'missing':sorted(EXPECTED-phone_days),'outside':sorted(phone_days-EXPECTED)}
    if EXPECTED-phone_days: errors.append('Phone data does not cover the full month')
    if phone_days-EXPECTED: errors.append('Phone record dates outside requested month')
    report['qa_phone_files'],qa_phone_days=inspect_phone(FOLDER/'phone_data/new')
    report['qa_phone_days']={'days':len(qa_phone_days),'missing':sorted(EXPECTED-qa_phone_days),'outside':sorted(qa_phone_days-EXPECTED)}
    if qa_phone_days!=EXPECTED: errors.append('Final QA phone evidence date coverage mismatch')
    report['qa_parts']={path.name:len(json.loads(path.read_text(encoding='utf-8'))) for path in (FOLDER/'QA_all').glob('qa_*_generator.json')}
    report['qa_checkpoint_files']=[path.name for path in (FOLDER/'process/qa_checkpoints').glob('*.json')]
    if len(report['qa_checkpoint_files'])!=9: errors.append('Not all nine QA generators completed a paired checkpoint')
    report['life_artifacts_success']=not errors
    # Embedded QA evidence must still exist in the final phone corpus. Later
    # generators can delete evidence that an earlier question already used.
    final_phone={}
    duplicates=[]
    for path in (FOLDER/'phone_data/new').glob('*.json'):
        if path.stem=='contact': continue
        for record in json.loads(path.read_text(encoding='utf-8')):
            key=(path.stem,str(record.get('phone_id')))
            if key in final_phone: duplicates.append(key)
            final_phone[key]=record
    questions=json.loads((FOLDER/'QA_all/QA.json').read_text(encoding='utf-8'))
    missing=[];changed=[];invalid_events=[];invalid_empty=[]
    event_ids={str(row['event_id']) for row in json.loads((FOLDER/'daily_event.json').read_text(encoding='utf-8'))}
    for index,question in enumerate(questions):
        types=question.get('question_type',[])
        if not question.get('evidence') and 'Unanswerable' not in types:
            invalid_empty.append(index)
        for event_id in question.get('required_events_id',[]):
            if str(event_id) not in event_ids: invalid_events.append([index,event_id])
        for evidence in question.get('evidence',[]):
            key=(evidence.get('type'),str(evidence.get('phone_id')))
            if key not in final_phone: missing.append([index,*key])
            elif evidence!=final_phone[key]: changed.append([index,*key])
    report['qa_evidence_integrity']={
        'missing_references':missing,'missing_reference_count':len(missing),
        'affected_questions':len({row[0] for row in missing}),
        'unique_missing_records':len({tuple(row[1:]) for row in missing}),
        'changed_references':changed,'duplicate_phone_ids':duplicates,
        'invalid_required_events':invalid_events,'invalid_empty_evidence':invalid_empty}
    if missing or changed or duplicates or invalid_events or invalid_empty:
        errors.append('QA evidence does not consistently match final phone corpus')
    report['errors']=errors
    report['success']=not errors
    (FOLDER/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(bool(errors))
