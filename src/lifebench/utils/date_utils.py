# -*- coding: utf-8 -*-
"""统一日期工具。

从 daily_simulator.py 抽出的唯一来源，消除多份语义不一致的重复实现。
后续步骤会继续把 get_next_n_day / parse_date / is_date_match / get_date_string 等迁入。
"""
import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

DEFAULT_FALLBACK_DATE = "2026-01-01"

DEFAULT_YEAR = 2025
DEFAULT_MONTHS = 12

_SUPPORTED_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",  # 带秒级时间的格式（如"2025-01-01 07:30:00"）
    "%Y-%m-%d",           # 纯日期格式（如"2025-01-01"）
    "%Y-%m-%d %H:%M",     # 带分钟级时间的格式（如"2025-01-01 07:30"）
    "%Y-%m-%d %H",        # 带小时级时间的格式（如"2025-01-01 07"）
]


@dataclass(frozen=True)
class TimeSpec:
    """生成数据的时间范围规格：目标年份 + 模拟该年前 months 个月。

    贯穿 draft 生成全链路，替换各处硬编码的 2025 与 range(1, 13)。

    用法：
        spec = TimeSpec(year=2027, months=3)
        spec.month_keys   -> ["2027-01", "2027-02", "2027-03"]
        spec.start_date   -> "2027-01-01"
        spec.end_date     -> "2027-03-31"
    """
    year: int = DEFAULT_YEAR
    months: int = DEFAULT_MONTHS

    def __post_init__(self):
        if not isinstance(self.year, int) or not (1900 <= self.year <= 2999):
            raise ValueError(f"year 需为 1900..2999 的整数，收到 {self.year!r}")
        if not isinstance(self.months, int) or not (1 <= self.months <= 12):
            raise ValueError(f"months 需为 1..12 的整数，收到 {self.months!r}")

    @property
    def month_nums(self) -> List[int]:
        """[1, 2, ..., months]"""
        return list(range(1, self.months + 1))

    @property
    def month_keys(self) -> List[str]:
        """["2025-01", "2025-02", ...]，长度为 months"""
        return [self.month_key(m) for m in self.month_nums]

    @property
    def start_date(self) -> str:
        """第一个月的第一天，"YYYY-01-01" """
        return f"{self.year}-01-01"

    @property
    def end_date(self) -> str:
        """最后一个模拟月的最后一天（自动处理闰年与月长）"""
        return self.month_end_date(self.months)

    @property
    def total_days(self) -> int:
        """模拟范围内的总天数"""
        return sum(self.days_in_month(m) for m in self.month_nums)

    def month_key(self, month: int) -> str:
        """月份数字 -> "YYYY-MM"，替换所有 f"2025-{m:02d}" 字面量"""
        return f"{self.year}-{month:02d}"

    def days_in_month(self, month: int) -> int:
        return calendar.monthrange(self.year, month)[1]

    def month_start_date(self, month: int) -> str:
        return f"{self.year}-{month:02d}-01"

    def month_end_date(self, month: int) -> str:
        return f"{self.year}-{month:02d}-{self.days_in_month(month):02d}"

    def is_last_month(self, month: int) -> bool:
        """是否为本次模拟的最后一个月（注意与 month == 12 的"是否为自然年末"区分）"""
        return month == self.months

    def contains_month(self, month_key: str) -> bool:
        """"YYYY-MM" 是否落在模拟范围内"""
        return month_key in set(self.month_keys)

    def contains_date(self, date_str: str) -> bool:
        """"YYYY-MM-DD" 是否落在模拟范围内"""
        return self.start_date <= date_str[:10] <= self.end_date

    def describe(self) -> str:
        """人类可读描述，可注入 prompt"""
        return (f"{self.year}年1月至{self.months}月"
                f"（{self.start_date} 至 {self.end_date}，共 {self.total_days} 天）")

    @classmethod
    def from_args(cls, args, default_year: int = DEFAULT_YEAR,
                  default_months: int = DEFAULT_MONTHS) -> "TimeSpec":
        """从 argparse 命名空间构造（缺失字段回落默认值）"""
        return cls(
            year=getattr(args, "year", None) or default_year,
            months=getattr(args, "months", None) or default_months,
        )


def extract_start_date(date_str: str, handle_short_year: bool = False) -> str:
    """
    从时间字符串中提取起始日期，兼容多种格式：
    1. 时间区间（如"2025-01-01 07:30:00至2025-01-01 08:45:00"）
    2. 单个时间（如"2025-01-01 07:30:00"或"2025-01-01"）
    3. 带中文时段的时间（如"2025-01-01 上午"或"2025-01-01 下午"）
    4. 短年份格式（仅当 handle_short_year=True，如"5-03-23" → "2025-03-23"）

    参数:
        date_str: 输入的时间字符串（支持含"至"的区间和不含"至"的单个时间）
        handle_short_year: 是否处理短年份格式

    返回:
        str: 提取的起始日期，格式固定为"YYYY-MM-DD"

    异常:
        ValueError: 输入字符串不符合支持的时间格式时抛出
    """
    # 步骤1：分割字符串，提取起始时间部分（含"至"则取左边，不含则取全部）
    if "至" in date_str:
        start_time_part = date_str.split("至")[0].strip()
    else:
        start_time_part = date_str.strip()

    # 增强鲁棒性：去除所有中文和无关字符，只保留数字、字母、空格和日期分隔符（- : .）
    start_time_part = re.sub(r'[^0-9a-zA-Z\s\-:\.]', '', start_time_part)
    # 去除多余空格
    start_time_part = ' '.join(start_time_part.split())

    if handle_short_year:
        # 特殊处理：检查是否为短年份格式（如"5-03-23" → "2025-03-23"）
        date_part = start_time_part.split()[0] if ' ' in start_time_part else start_time_part
        if '-' in date_part:
            parts = date_part.split('-')
            if len(parts) == 3:
                # 检查是否为短年份格式（如"5-03-23"）
                if len(parts[0]) <= 2 and len(parts[1]) <= 2 and len(parts[2]) <= 2:
                    # 假设格式为 YYYY-MM-DD 但年份只有1-2位，补全年份为4位（20xx）
                    year = parts[0].zfill(2)
                    if len(year) == 2:
                        year = "20" + year
                    month = parts[1].zfill(2)
                    day = parts[2].zfill(2)

                    new_date_part = f"{year}-{month}-{day}"
                    if ' ' in start_time_part:
                        start_time_part = new_date_part + start_time_part[len(date_part):]
                    else:
                        start_time_part = new_date_part

    # 步骤2：解析起始时间部分，提取纯日期（支持多种子格式）
    for fmt in _SUPPORTED_DATE_FORMATS:
        try:
            start_datetime = datetime.strptime(start_time_part, fmt)
            return start_datetime.strftime("%Y-%m-%d")
        except ValueError:
            continue

    raise ValueError(
        f"时间格式不支持！请输入以下格式之一：\n"
        f"1. 时间区间（如'2025-01-01 07:30:00至2025-01-01 08:45:00'）\n"
        f"2. 单个时间（如'2025-01-01 07:30:00'或'2025-01-01'）\n"
        f"当前输入：{date_str}"
    )


def extract_start_date_or_default(date_str: str, default: str = DEFAULT_FALLBACK_DATE) -> str:
    """同 extract_start_date，但解析失败时返回 default（原 filter_by_date 语义）。"""
    try:
        return extract_start_date(date_str, handle_short_year=True)
    except ValueError:
        return default


def iterate_dates(start_date: str, end_date: str) -> List[str]:
    """
    遍历从起始日期到结束日期（包含两端）的所有日期，返回日期字符串列表

    参数:
        start_date: 起始日期，格式为 'YYYY-MM-DD'（如 '2025-01-01'）
        end_date: 结束日期，格式为 'YYYY-MM-DD'（如 '2025-01-05'）

    返回:
        List[str]: 按时间顺序排列的日期列表，包含 start_date 和 end_date 之间的所有日期

    异常:
        ValueError: 日期格式错误或起始日期晚于结束日期时抛出
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"日期格式错误，需为 'YYYY-MM-DD'，错误：{str(e)}")

    if start > end:
        raise ValueError(f"起始日期 {start_date} 不能晚于结束日期 {end_date}")

    current_date = start
    date_list = []
    while current_date <= end:
        date_list.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)

    return date_list


def guard_time_spec_meta(meta_dir, spec, artifacts=None, write=True):
    """
    校验（并记录）某个输出目录的时间范围，防止跨 year/months 复用旧产物。

    整条流水线用"文件是否存在"跳过已完成的步骤，续跑很方便，但换了
    --year / --months 再跑同一目录时旧产物会被静默复用，产出年份自相矛盾的数据集。
    这里把时间范围落到 meta.json，不一致就报错中止。

    参数:
        meta_dir:  存放 meta.json 的目录（通常是 process/）
        spec:      本次运行的 TimeSpec
        artifacts: 需要提示的历史产物路径列表（缺 meta.json 时用于警告）
        write:     校验通过后是否写回 meta.json

    异常:
        RuntimeError: 已有 meta.json 的 year/months 与本次不一致
    """
    import json
    import os

    meta_path = os.path.join(meta_dir, 'meta.json')
    current = {'year': spec.year, 'months': spec.months}

    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                previous = json.load(f)
        except Exception as e:
            print(f"⚠️  meta.json 无法解析（{e}），按本次参数覆盖写入")
            previous = None

        if previous and (previous.get('year') != current['year']
                         or previous.get('months') != current['months']):
            raise RuntimeError(
                f"时间范围与已有产物不一致，已中止以免生成自相矛盾的数据。\n"
                f"  已有产物: year={previous.get('year')}, months={previous.get('months')}\n"
                f"  本次参数: year={current['year']}, months={current['months']}\n"
                f"请改用一致的参数，或换一个输出目录，或先删除 {meta_dir} "
                f"及同级 daily_draft.json / daily_event.json 后重跑。"
            )
    else:
        stale = [p for p in (artifacts or []) if os.path.exists(p)]
        if stale:
            print(f"⚠️  检测到无 meta.json 的历史产物，无法校验其时间范围，"
                  f"将按 {spec.describe()} 继续：{stale}")

    if write:
        os.makedirs(meta_dir, exist_ok=True)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
