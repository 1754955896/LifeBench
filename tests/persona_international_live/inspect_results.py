"""Build a readable report from saved real-generation artifacts (no API calls)."""
import json
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def report():
    lines = ['# 国内与海外画像真实生成结果', '',
             '两份输入均为虚构数据。生产 CLI 运行，seed=42，基准日期 2025-12-31。',
             '结构检查通过不等于生活内容真实，下面同时保留叙述以便人工审阅。',
             '这两个在线样本不构成新旧代码行为完全等价的证明。', '',
             '人工审阅与问题定位见 [REVIEW.md](REVIEW.md)；重新生成后需重新审阅。', '']
    for case, title in (('cn', '国内：北京'), ('gb', '海外：伦敦')):
        folder = HERE / case
        lines += [f'## {title}', '']
        if (folder / 'run_summary.json').exists():
            summary = load(folder / 'run_summary.json')
            lines += [f"- 退出码：{summary['exit_code']}；耗时：{summary['elapsed_seconds']} 秒；完整输出：{summary['success']}"]
        tokens = [load(p) for p in (folder / 'token_usage').glob('token_*.json')] if (folder / 'token_usage').exists() else []
        lines += [f"- 累计 API 响应次数：{sum(t.get('call_count', 0) for t in tokens)}；"
                  f"累计 token：{sum(t.get('total_tokens', 0) for t in tokens)}（含本目录重跑）", '']
        final = folder / 'persona_list.json'
        basic = folder / 'persona_list_basic_temp.json'
        if final.exists() or basic.exists():
            person = load(final if final.exists() else basic)[0]
            lines += [f"当前可审阅产物：{'完整画像' if final.exists() else '基础画像，尚非最终成功结果'}。", '']
            for field in ('name', 'age', 'nationality', 'home_address', 'workplace', 'salary', 'hobbies', 'favorite_foods'):
                lines += [f'- {field}：{json.dumps(person.get(field), ensure_ascii=False)}']
            contacts = [c for group in person.get('relation', []) for c in group]
            lines += [f'- 联系人数：{len(contacts)}', '']
            for field in ('lifestyle_desc', 'economic_desc', 'work_desc'):
                lines += [f'### {field}', '', str(person.get(field) or ''), '']
            if contacts:
                lines += ['### 联系人摘要', '', '| 姓名 | 关系 | 圈子 | 组织 | 居住地 |', '| --- | --- | --- | --- | --- |']
                for contact in contacts:
                    values = [contact.get(k, '') for k in ('name', 'relation', 'social circle', 'organization', 'home_address')]
                    lines += ['| ' + ' | '.join(str(v).replace('|', '/') for v in values) + ' |']
                lines += ['']
            context = person.get('_quality_context') or {}
            if context:
                lines += ['### 地址与通勤证据', '', '```json', json.dumps(context, ensure_ascii=False, indent=2), '```', '']
        else:
            lines += ['尚无可审阅画像输出。', '']
        failures = list(folder.glob('*.failures.jsonl'))
        for path in failures:
            lines += [f'历史失败日志：`{path.name}`（可能包含之前网络受限的尝试）。', '',
                      '```json', path.read_text(encoding='utf-8').strip(), '```', '']
        log_path = folder / 'generation.log'
        if log_path.exists():
            lines += ['### 本次执行日志末尾', '', '```text',
                      '\n'.join(log_path.read_text(encoding='utf-8').splitlines()[-15:]), '```', '']
    (HERE / 'RESULTS.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', type=Path, default=HERE)
    args = parser.parse_args()
    HERE = args.output_root.resolve()
    report()
