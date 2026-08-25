# -*- coding: utf-8 -*-
"""统一日期工具。

从 daily_simulator.py 抽出的唯一来源，消除多份语义不一致的重复实现。
后续步骤会继续把 get_next_n_day / parse_date / is_date_match / get_date_string 等迁入。
"""
import re
from datetime import datetime, timedelta
from typing import List

DEFAULT_FALLBACK_DATE = "2026-01-01"

_SUPPORTED_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",  # 带秒级时间的格式（如"2025-01-01 07:30:00"）
    "%Y-%m-%d",           # 纯日期格式（如"2025-01-01"）
    "%Y-%m-%d %H:%M",     # 带分钟级时间的格式（如"2025-01-01 07:30"）
    "%Y-%m-%d %H",        # 带小时级时间的格式（如"2025-01-01 07"）
]


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
