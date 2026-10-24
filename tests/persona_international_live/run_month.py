"""Real one-month end-to-end run using the already authorized synthetic GB persona."""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime
import time
import argparse

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
FOLDER=HERE/'monthly_2026_01'

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--resume-format',action='store_true',help='Reuse completed simulation and run the native formatter before resuming the parent pipeline')
    parser.add_argument('--resume-qa',action='store_true',help='Reuse completed phone records and resume the QA stage')
    args=parser.parse_args()
    FOLDER.mkdir(exist_ok=True)
    source=HERE/'optimized/gb'
    if not (FOLDER/'persona.json').exists():
        person=json.loads((source/'persona_list.json').read_text(encoding='utf-8'))[0]
        locations=json.loads((source/'persona_list_locations.json').read_text(encoding='utf-8'))[0]
        (FOLDER/'persona.json').write_text(json.dumps(person,ensure_ascii=False,indent=2),encoding='utf-8')
        (FOLDER/'location.json').write_text(json.dumps(locations,ensure_ascii=False,indent=2),encoding='utf-8')
    command=[sys.executable,'-u',str(ROOT/'scripts/run.py'),'--base-path',str(FOLDER),
        '--year','2026','--months','1','--max-workers','3',
        '--map-tool','overseas','--map-config',str(ROOT/'config/overseas_map.demo.json')]
    if args.resume_qa:
        command.extend(['--generate-phone-data','0'])
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1',
             LIFEBENCH_TOKEN_DIR=str(FOLDER/'token_usage'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    started=datetime.now().isoformat(timespec='seconds')
    start=time.monotonic()
    print('Starting full pipeline: GB, 2026-01-01 through 2026-01-31',flush=True)
    with (FOLDER/'pipeline.log').open('a',encoding='utf-8') as log:
        if args.resume_format:
            format_command=[sys.executable,'-u',str(ROOT/'scripts/run/simulator.py'),
                '--file-path',str(FOLDER),'--start-date','2026-01-01','--end-date','2026-01-31',
                '--generate-data','0','--map-tool','overseas','--map-config',str(ROOT/'config/overseas_map.demo.json')]
            result=subprocess.run(format_command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:
                raise SystemExit(result.returncode)
        result=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    summary=dict(started=started,elapsed_seconds=round(time.monotonic()-start,1),exit_code=result.returncode,
        year=2026,months=1,map_policy='overseas',stages=['draft','simulation','matching','monthly_report','phone','QA'],
        commit=subprocess.check_output(['git','rev-parse','--short','HEAD'],cwd=ROOT,text=True).strip(),
        resumed_format=args.resume_format,resumed_qa=args.resume_qa)
    (FOLDER/'run_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)
    raise SystemExit(result.returncode)
