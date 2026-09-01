# -*- coding: utf-8 -*-
"""
数据翻译脚本：将中文 life_bench 数据原封不动翻译为英文版本。

本脚本完全自包含，除 pip 包 `openai` 外不依赖项目其它内容（不 import src/、不读取
config/ 目录）。LLM 配置在文件开头直接实现，仅依赖环境变量与文件内默认值。

设计要点：
1. 键名（key）使用下方 KEY_TRANSLATIONS 固定映射确定性翻译，不调用 LLM，
   保证同一键名在所有文件里翻译一致。遇到未收录的中文键名会告警并保留原文。
2. 只有「包含中文的字符串值」才调用 LLM 翻译；不含中文的值（日期、时间、
   数字、电话、邮箱、URL、ID 等）原样保留，不消耗 token。
3. 跳过 `lifebench_multi_source_format_*.json`（合并冗余文件，无需翻译）。
4. 支持 `--input` 参数选择要翻译的文件夹，输出到对应的 `data_en` 文件夹。
5. 跨文件去重 + 磁盘缓存，相同字符串只翻译一次；断点续跑。
6. 多线程并发调用 LLM 翻译，加速大批量数据。

用法示例（默认输入为脚本同级的 data 文件夹，可在任意目录运行）：
    python life_bench_data/version2/translate.py
    python life_bench_data/version2/translate.py --input data/fenghaoran
    python life_bench_data/version2/translate.py --input data --output data_en
    python life_bench_data/version2/translate.py --dry-run   # 仅统计，不调用 LLM
"""

import os
import re
import json
import argparse
import fnmatch
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI

# ===========================================================================
# LLM 配置（脚本自包含）
#
# 优先读取环境变量，未设置时使用下方默认值。建议通过环境变量注入密钥，避免提交到仓库：
#   LIFEBENCH_LLM_API_KEY    API 密钥
#   LIFEBENCH_LLM_BASE_URL   API 服务地址
#   LIFEBENCH_LLM_MODEL      模型名称
# ===========================================================================
LLM_API_KEY = os.environ.get("LIFEBENCH_LLM_API_KEY", "sk-76bd3e29019f4a518a410abf5f915bd7")
LLM_BASE_URL = os.environ.get("LIFEBENCH_LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("LIFEBENCH_LLM_MODEL", "deepseek-v4-flash")

_client = None
_client_lock = threading.Lock()


def get_client():
    """返回线程安全的全局 OpenAI 客户端实例。"""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    return _client


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 脚本所在目录（life_bench_data/version2），默认输入/输出均基于此目录解析
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 需要跳过的文件（glob 通配，默认跳过冗余的 multi_source_format 合并文件）
DEFAULT_SKIP_PATTERN = "lifebench_multi_source_format_*.json"

# 中文键名 -> 英文键名的固定映射（确定性翻译，不经过 LLM）。
# 若日后数据新增中文键名，脚本运行时会告警，请把对应翻译补充到这里。
KEY_TRANSLATIONS = {
    # daily_draft 的 state 对象
    "今日运动": "daily_exercise",
    "体重": "weight",
    "起床时间": "wake_time",
    "起始状态": "start_state",
    "所处地点": "location",
    "所处点": "location",
    "心情": "mood",
    "睡觉时间": "sleep_time",
    "结束状态": "end_state",
    "身体状态": "body_state",

    # fitness_health 通用键
    "日期": "date",
    "城市": "city",
    "天气": "weather",
    "时间": "time",
    "描述": "description",

    # 日常活动
    "日常活动": "daily_activity",
    "步数": "steps",
    "距离": "distance",
    "热量": "calories",
    "锻炼时长": "workout_duration",
    "活动小时数": "activity_hours",

    # 跑步 / 骑行 / 步行
    "跑步": "running",
    "骑行": "cycling",
    "步行": "walking",
    "运动类型": "exercise_type",
    "运动时间": "exercise_time",
    "距离统计": "distance_stats",
    "平均心率": "avg_heart_rate",
    "平均步频": "avg_step_frequency",
    "平均配速": "avg_pace",
    "最佳配速": "best_pace",
    "总步数": "total_steps",
    "累计爬升": "total_ascent",
    "累计下降": "total_descent",
    "消耗热量": "calories_burned",
    "平均功率": "avg_power",
    "平均速度": "avg_speed",
    "最大踏频": "max_cadence",
    "平均踏频": "avg_cadence",
    "最佳速度": "best_speed",
    "步数统计": "steps_stats",

    # 睡眠
    "睡眠": "sleep",
    "入睡时间": "fall_asleep_time",
    "出睡时间": "wake_time",
    "睡眠得分": "sleep_score",
    "全部睡眠时长": "total_sleep_duration",
    "深睡时长": "deep_sleep_duration",
    "浅睡时长": "light_sleep_duration",
    "快速眼动时长": "rem_duration",
    "清醒时长": "awake_duration",
    "清醒次数": "awake_count",
    "零星小睡时长": "nap_duration",
    "深睡连续性得分": "deep_sleep_continuity_score",

    # 心率
    "心率统计": "heart_rate_stats",
    "平均静息心率": "avg_resting_heart_rate",
    "心率变异性": "heart_rate_variability",

    # 体温
    "体温统计": "body_temperature_stats",
    "平均体温": "avg_body_temperature",

    # 血糖
    "血糖统计": "blood_glucose_stats",
    "平均血糖水平": "avg_blood_glucose",

    # 压力
    "压力": "stress",
    "压力得分": "stress_score",

    # 饮食 / 用户交互
    "饮食记录": "diet_records",
    "摄入热量": "calorie_intake",
    "用户交互事件": "user_interaction_events",
}

TRANSLATE_SYSTEM = (
    "You are a professional translator producing a high-quality English localization "
    "of a Chinese life-logging benchmark dataset."
)

# 翻译规则（批量与逐条共用，保持一致）
TRANSLATE_RULES = """1. Translate ALL Chinese text into fluent, natural English — no Chinese characters may remain.
2. Transliterate Chinese person names into pinyin (e.g. 冯浩然 -> Feng Haoran), keeping surname first.
3. Translate place names into standard English (长沙 -> Changsha, 岳麓区 -> Yuelu District).
4. Translate company / app / brand names into their standard English names where one exists
   (华泰证券 -> Huatai Securities, 印象笔记 -> Evernote); otherwise use pinyin or a literal translation.
5. Translate Chinese units and dates into English: 元/块 -> yuan, 万 -> 10,000 (use digits),
   岁 -> years old, 2025年3月13日 -> March 13, 2025. Keep pure numbers, timestamps
   (2025-01-01 06:45:00), phone numbers, emails and IDs exactly unchanged. Render 至/到 inside
   time ranges as "to".
6. For URLs and app deep links (e.g. weixin://chat/家庭群, app://x?name=云南之旅): keep the
   scheme and structure, but translate any Chinese text inside the path or query.
7. Preserve newlines and punctuation structure. Do not add explanations, notes or quotation marks."""

# 批量翻译：要求返回编号 -> 译文的 JSON 对象
TRANSLATE_TEMPLATE = """Translate each numbered Chinese string into natural English.

Rules:
{rules}

Return ONLY a JSON object mapping each index number to its English translation,
using exactly the same index numbers. For example: {"0": "translation", "1": "translation"}.

Strings:
{body}"""

# 逐条翻译：直接给 content、直接返回译文，不做 JSON 解析（最鲁棒的兜底）
SINGLE_TEMPLATE = """Translate the following Chinese text into natural English.

Rules:
{rules}

Return ONLY the English translation, without any explanation or quotation marks.

Text:
{text}"""

# 严格重译：当结果仍残留中文时使用，强调不能留下任何中文
STRICT_SINGLE_TEMPLATE = """Your previous translation still contained Chinese characters.
Re-translate, converting EVERY Chinese character into English.

Rules:
{rules}

Return ONLY the English translation, with no Chinese characters remaining.

Text:
{text}"""


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def has_cjk(text):
    """判断字符串是否包含中日韩统一表意文字（用于识别需要翻译的中文内容）。"""
    return any('一' <= ch <= '鿿' for ch in text)


def safe_json_loads(text, json_type='object', default=None):
    """本地 JSON 解析：去除代码围栏/多余内容后尝试 json.loads，失败返回 default。"""
    if not isinstance(text, str):
        return default
    s = text.strip()
    if s.startswith('```'):
        s = re.sub(r'^```[a-zA-Z]*\s*', '', s)
        s = re.sub(r'\s*```$', '', s)
    if json_type == 'array':
        start, end = s.find('['), s.rfind(']')
    else:
        start, end = s.find('{'), s.rfind('}')
    if start != -1 and end != -1 and start < end:
        s = s[start:end + 1]
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return default


def collect(obj, strings, unknown_keys):
    """递归遍历 JSON：收集中文「字符串值」到 strings，记录未收录的中文键名到 unknown_keys。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and has_cjk(k) and k not in KEY_TRANSLATIONS:
                unknown_keys.add(k)
            collect(v, strings, unknown_keys)
    elif isinstance(obj, list):
        for v in obj:
            collect(v, strings, unknown_keys)
    elif isinstance(obj, str) and has_cjk(obj):
        strings.add(obj)


def substitute(obj, cache):
    """递归遍历 JSON：键名用固定映射翻译，中文值用翻译缓存替换，其余内容原样保留。"""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            new_key = KEY_TRANSLATIONS.get(k, k) if (isinstance(k, str) and has_cjk(k)) else k
            result[new_key] = substitute(v, cache)
        return result
    if isinstance(obj, list):
        return [substitute(v, cache) for v in obj]
    if isinstance(obj, str) and has_cjk(obj):
        return cache.get(obj, obj)
    return obj


def build_batches(strings, batch_size, max_chars):
    """将字符串列表切分为批量翻译任务（同时受数量与字符总量约束）。"""
    batches = []
    current = []
    current_chars = 0
    for s in strings:
        current.append(s)
        current_chars += len(s)
        if len(current) >= batch_size or current_chars >= max_chars:
            batches.append(current)
            current = []
            current_chars = 0
    if current:
        batches.append(current)
    return batches


# ---------------------------------------------------------------------------
# LLM 调用与翻译
# ---------------------------------------------------------------------------

def call_llm(messages, json_mode=False, retries=3):
    """调用 LLM（自包含客户端），带重试。"""
    kwargs = dict(model=LLM_MODEL, messages=messages, stream=False)
    if json_mode:
        kwargs['response_format'] = {'type': 'json_object'}

    for attempt in range(retries):
        try:
            response = get_client().chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return None


def _translate_batch_once(items):
    """单次批量翻译尝试，返回 {原文: 译文}（解析失败或缺失项不会出现在结果中）。"""
    body = "\n".join(f"{i}: {json.dumps(s, ensure_ascii=False)}" for i, s in enumerate(items))
    prompt = TRANSLATE_TEMPLATE.replace('{rules}', TRANSLATE_RULES).replace('{body}', body)
    messages = [
        {"role": "system", "content": TRANSLATE_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    raw = call_llm(messages, json_mode=True)
    data = safe_json_loads(raw, 'object') if raw else None

    result = {}
    if isinstance(data, dict):
        for i, s in enumerate(items):
            value = data.get(str(i))
            if not isinstance(value, str):
                value = data.get(i)
            if isinstance(value, str) and value.strip():
                result[s] = value
    elif isinstance(data, list):
        for i, s in enumerate(items):
            if i < len(data) and isinstance(data[i], str) and data[i].strip():
                result[s] = data[i]
    return result


def _single_translate(text, strict=False):
    """单条直翻的内部实现：直接给 content、直接返回译文，不做 JSON 解析。"""
    template = STRICT_SINGLE_TEMPLATE if strict else SINGLE_TEMPLATE
    prompt = template.replace('{rules}', TRANSLATE_RULES).replace('{text}', text)
    messages = [
        {"role": "system", "content": TRANSLATE_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = call_llm(messages, json_mode=False)
    except Exception:  # noqa: BLE001
        return None
    return raw.strip() if raw else None


def translate_one(text):
    """逐条翻译：直接返回译文；若结果仍残留中文，则用严格指令重试一次。"""
    result = _single_translate(text)
    if result and has_cjk(result):
        retry = _single_translate(text, strict=True)
        if retry and not has_cjk(retry):
            return retry
    return result


def translate_batch(items, max_rounds=3):
    """批量翻译：对缺失项重试若干轮，仍失败则逐条直接翻译兜底，保证不丢数据。"""
    pending = list(items)
    result = {}
    for _ in range(max_rounds):
        if not pending:
            break
        try:
            partial = _translate_batch_once(pending)
        except Exception:  # noqa: BLE001
            partial = {}
        result.update(partial)
        pending = [s for s in pending if s not in result]
    # 仍缺失的项：逐条直接翻译兜底
    for s in pending:
        translated = translate_one(s)
        if translated:
            result[s] = translated
    # 校验：结果仍残留中文的，用严格指令逐条重翻（translate_one 内部已含严格重试）
    for s in list(result):
        if has_cjk(result[s]):
            cleaned = translate_one(s)
            if cleaned and not has_cjk(cleaned):
                result[s] = cleaned
    return result


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------

class TranslationCache:
    """线程安全的翻译缓存（仅缓存字符串值），持久化到磁盘，支持断点续跑。"""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._data = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except Exception as exc:  # noqa: BLE001
                print(f"警告：缓存文件损坏，忽略：{exc}")

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def update(self, mapping):
        with self._lock:
            self._data.update(mapping)

    def save(self):
        with self._lock:
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False)
            os.replace(tmp, self.path)

    def __len__(self):
        with self._lock:
            return len(self._data)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def collect_files(input_dir, skip_pattern):
    """递归收集需要翻译的 JSON 文件（相对路径），并收集待翻译的中文值及未知键名。"""
    files = []
    strings = set()
    unknown_keys = set()
    for root, _dirs, names in os.walk(input_dir):
        for name in names:
            if not name.endswith('.json'):
                continue
            if fnmatch.fnmatch(name, skip_pattern):
                print(f"跳过：{name}")
                continue
            full = os.path.join(root, name)
            rel = os.path.relpath(full, input_dir)
            files.append(rel)
            try:
                with open(full, 'r', encoding='utf-8') as f:
                    collect(json.load(f), strings, unknown_keys)
            except Exception as exc:  # noqa: BLE001
                print(f"警告：无法解析 {full}，将原样复制：{exc}")
    return files, strings, unknown_keys


def main():
    parser = argparse.ArgumentParser(description='将中文 life_bench 数据翻译为英文版本')
    parser.add_argument('--input', type=str, default=os.path.join(SCRIPT_DIR, 'data'),
                        help='要翻译的源文件夹（默认为脚本同级的 data 文件夹）')
    parser.add_argument('--output', type=str, default=None,
                        help='输出文件夹（默认将 input 中的 data 段替换为 data_en）')
    parser.add_argument('--skip', type=str, default=DEFAULT_SKIP_PATTERN,
                        help='跳过的文件名 glob 通配（默认为 lifebench_multi_source_format_*.json）')
    parser.add_argument('--workers', type=int, default=8, help='并发线程数')
    parser.add_argument('--batch-size', type=int, default=40, help='单次 LLM 调用翻译的字符串数')
    parser.add_argument('--batch-max-chars', type=int, default=8000, help='单次 LLM 调用的最大字符量')
    parser.add_argument('--cache', type=str, default=None, help='翻译缓存文件路径')
    parser.add_argument('--dry-run', action='store_true', help='仅统计待翻译内容，不调用 LLM')
    args = parser.parse_args()

    # 解析输入路径（默认已是基于脚本目录的绝对路径；用户传入的相对路径基于当前工作目录）
    input_dir = args.input if os.path.isabs(args.input) else os.path.abspath(args.input)
    input_dir = os.path.normpath(input_dir)

    # 解析输出路径（默认把路径中的 data 段替换为 data_en）
    if args.output:
        output_dir = args.output if os.path.isabs(args.output) else os.path.abspath(args.output)
    else:
        parts = os.path.normpath(input_dir).split(os.sep)
        if 'data' in parts:
            parts[parts.index('data')] = 'data_en'
            output_dir = os.sep.join(parts)
        else:
            output_dir = input_dir + '_en'
    output_dir = os.path.normpath(output_dir)

    cache_path = args.cache
    if not cache_path:
        cache_path = os.path.join(os.path.dirname(output_dir), '.translate_cache.json')
    cache_path = os.path.normpath(cache_path)

    print(f"输入目录：{input_dir}")
    print(f"输出目录：{output_dir}")
    print(f"缓存文件：{cache_path}")

    # 1. 收集文件、待翻译中文值、未知中文键名
    print("正在收集文件与待翻译内容...")
    files, strings, unknown_keys = collect_files(input_dir, args.skip)
    print(f"共 {len(files)} 个 JSON 文件，{len(strings)} 个去重后的待翻译中文值")
    if unknown_keys:
        print("警告：发现未收录的中文键名（将保留原文），请补充到 KEY_TRANSLATIONS：")
        for k in sorted(unknown_keys):
            print(f"    {k}")

    # 2. 加载缓存，确定缺失项（缓存译文仍残留中文的也需重翻）
    cache = TranslationCache(cache_path)

    def _needs_translation(s):
        t = cache.get(s)
        return not t or has_cjk(t)

    missing = [s for s in strings if _needs_translation(s)]
    print(f"缓存中已有 {len(strings) - len(missing)} 条可用，待翻译 {len(missing)} 条")

    if args.dry_run:
        print("dry-run 模式，不调用 LLM。")
        return

    # 3. 并发批量翻译
    if missing:
        batches = build_batches(missing, args.batch_size, args.batch_max_chars)
        print(f"切分为 {len(batches)} 个批次，使用 {args.workers} 个线程翻译...")

        done = 0
        failed = 0
        save_lock = threading.Lock()

        def run_batch(batch):
            # translate_batch 内部已含重试 + 逐条兜底，这里再包一层异常保护
            try:
                return translate_batch(batch)
            except Exception:  # noqa: BLE001
                return {}

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(run_batch, b): b for b in batches}
            for future in as_completed(futures):
                batch = futures[future]
                try:
                    result = future.result()
                except Exception:  # noqa: BLE001
                    result = {}
                cache.update(result)
                failed += len(batch) - len(result)
                done += 1
                # 每 20 个批次持久化一次缓存
                with save_lock:
                    if done % 20 == 0:
                        cache.save()
                        print(f"进度：{done}/{len(batches)} 批次完成，缓存 {len(cache)} 条")
        cache.save()
        print(f"翻译完成：{len(batches)} 批次，失败 {failed} 条（失败项将保留原文）")

    # 4. 生成英文版文件
    print("正在生成英文版文件...")
    os.makedirs(output_dir, exist_ok=True)
    written = 0
    for rel in files:
        src = os.path.join(input_dir, rel)
        dst = os.path.join(output_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            with open(src, 'r', encoding='utf-8') as f:
                data = json.load(f)
            translated = substitute(data, cache._data)
            with open(dst, 'w', encoding='utf-8') as f:
                json.dump(translated, f, ensure_ascii=False, indent=2)
            written += 1
        except Exception as exc:  # noqa: BLE001
            # 解析失败或写入失败时原样复制，保证不丢失数据
            print(f"警告：{rel} 处理失败，原样复制：{exc}")
            with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                fdst.write(fsrc.read())
            written += 1

    cache.save()
    print(f"完成：{written}/{len(files)} 个文件已写入 {output_dir}")


if __name__ == '__main__':
    main()
