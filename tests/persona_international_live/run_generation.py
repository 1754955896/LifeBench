"""Generate one CN and one GB persona through the production CLI (real API calls)."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def fixture(case):
        # Entirely fictional fixtures: no existing person's profile is reused.
        person = dict(name='陈明' if case == 'cn' else 'Oliver Bennett', birth='1994-10-29',
                      age=31, nationality='汉' if case == 'cn' else '英国',
                      home_address={}, birth_place={}, gender='男', education='大学本科',
                      job='软件工程师', occupation='软件开发企业', workplace={}, belief='不信仰宗教',
                      salary=300000 if case == 'cn' else 65000,
                      body={'height': 178, 'weight': 72, 'BMI': round(72 / 1.78 ** 2, 4)},
                      family='未婚', personality={'mbti': 'INTJ', 'traits': ['独立', '责任感']},
                      hobbies=['跑步', '阅读', '摄影'], favorite_foods=[], memory_date=[], aim=[],
                      healthy_desc='', lifestyle_desc='', economic_desc='', work_desc='',
                      experience_desc='', description='', relation=[])
        person['home_address'] = {'province': '北京市', 'city': '北京市', 'district': '海淀区'} if case == 'cn' else {
            'country_code': 'GB', 'country': 'United Kingdom', 'province': 'England',
            'city': 'London', 'district': 'Camden', 'timezone': 'Europe/London',
            'currency': 'GBP', 'salary_period': 'annual', 'output_language': 'zh-CN'}
        person['workplace'] = {'province': '北京市', 'city': '北京市', 'district': '海淀区'} if case == 'cn' else {
            'country_code': 'GB', 'country': 'United Kingdom', 'province': 'England',
            'city': 'London', 'district': 'Camden'}
        person['birth_place'] = {'province': '北京市', 'city': '北京市', 'district': '海淀区'} if case == 'cn' else {
            'country_code': 'GB', 'country': 'United Kingdom', 'province': 'England',
            'city': 'London', 'district': 'Camden'}
        # Leave narratives open so the production generator supplies the local details.
        for key in ('healthy_desc', 'lifestyle_desc', 'economic_desc', 'work_desc', 'experience_desc', 'description'):
            person[key] = ''
        person['memory_date'] = []
        person['aim'] = ['提升软件工程能力', '保持规律运动']
        person['favorite_foods'] = ['家常菜'] if case == 'cn' else ['英式早餐', '意大利面']
        return person


def prepare(cases=('cn', 'gb')):
    for case in cases:
        folder = HERE / case
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'input.json').write_text(json.dumps([fixture(case)], ensure_ascii=False, indent=2), encoding='utf-8')


def run(case, resume_relations=False):
    folder = HERE / case
    if (folder / 'persona_list.json').exists():
        raise RuntimeError(f'{case}: output already exists; preserve it or choose a new run directory')
    command = [sys.executable, '-u', str(ROOT / 'scripts/run/persona_gen.py'),
               '--file-path', str(folder), '--ref-file', str(ROOT / 'src/lifebench/persona/persona_file/refer.json'),
               '--input-file', 'input.json', '--output-file', 'persona_list.json',
               '--as-of-date', '2025-12-31', '--start', '0', '--end', '1',
               '--seed', '42', '--max-workers', '1', '--keep-checkpoints']
    if case == 'gb':
        command += ['--map-tool', 'overseas', '--map-config', str(ROOT / 'config/overseas_map.demo.json')]
    if resume_relations:
        if case != 'gb':
            raise ValueError('Relation resume is currently for the GB fixture only')
        command = [sys.executable, '-u', str(Path(__file__).with_name('resume_relations.py')), '--folder', str(folder)]
    start = time.monotonic()
    started = datetime.now().isoformat(timespec='seconds')
    print(f'{case}: starting real persona generation', flush=True)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1',
               LIFEBENCH_TOKEN_DIR=str(folder / 'token_usage'))
    with (folder / 'generation.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    summary = {'case': case, 'started': started, 'elapsed_seconds': round(time.monotonic() - start, 1),
               'exit_code': result.returncode, 'map_policy': 'amap' if case == 'cn' else 'overseas',
               'success': result.returncode == 0 and (folder / 'persona_list.json').exists()}
    if summary['success']:
        people = json.loads((folder / 'persona_list.json').read_text(encoding='utf-8'))
        person = people[0]
        summary.update(persona_count=len(people), name=person.get('name'),
                       top_level_keys=list(person), home_address=person.get('home_address'),
                       workplace=person.get('workplace'),
                       contact_count=sum(len(group) for group in person.get('relation', [])))
    (folder / 'run_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return summary['success']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('cn', 'gb', 'all'), default='all')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--output-root', type=Path, default=HERE, help='Separate directory for a new run; old results are preserved')
    parser.add_argument('--resume-relations', action='store_true', help='GB only: reuse saved successful base, migrate region metadata, trace real relation calls')
    args = parser.parse_args()
    HERE = args.output_root.resolve()
    cases = ('cn', 'gb') if args.case == 'all' else (args.case,)
    prepare(cases)
    if not args.prepare_only:
        results = [run(case, args.resume_relations) for case in cases]
        raise SystemExit(0 if all(results) else 1)
