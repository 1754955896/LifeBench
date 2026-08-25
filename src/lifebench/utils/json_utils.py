# -*- coding: utf-8 -*-
"""JSON 工具：移除包装与安全解析。

统一 remove_json_wrapper / safe_json_loads，避免在多个文件中重复实现。
原实现分别存在于 daily_simulator.py 与 event_formatter.py，现收敛至此作为唯一来源。
"""
import re
import json
from typing import Any


def remove_json_wrapper(input_str: str, json_type: str = 'object') -> str:
    """
    移除JSON字符串的前后包装（如```json ```标签、非法转义字符等）
    并根据json_type参数提取对应的JSON内容：
    - json_type='object'：提取第一个{到最后一个}之间的内容
    - json_type='array'：提取第一个[到最后一个]之间的内容

    参数:
        input_str: 输入字符串
        json_type: JSON类型，'object'对应{}，'array'对应[]，默认为'object'

    返回:
        str: 清理后的字符串
    """
    # 步骤1：去除开头的```json（含空格/换行）和结尾的```（含空格）
    pattern = r'^\s*```json\s*\n?|\s*```\s*$'
    result = re.sub(pattern, '', input_str, flags=re.MULTILINE)

    # 步骤2：根据json_type提取对应的括号内容
    if json_type == 'array':
        first_bracket = result.find('[')
        last_bracket = result.rfind(']')
        if first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
            result = result[first_bracket:last_bracket + 1]
    else:  # 默认处理JSON对象
        first_brace = result.find('{')
        last_brace = result.rfind('}')
        if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
            result = result[first_brace:last_brace + 1]

    # 步骤3：清理 JSON 非法控制字符
    # 保留：JSON 允许的控制字符（\n换行、\r回车、\t制表符、\b退格、\f换页）+ 可见ASCII字符（0x20-0x7E）+ 中文/全角字符
    valid_pattern = r'[^\x20-\x7E\n\r\t\b\f一-鿿　-〿＀-￯ -⁯⺀-⻿]'
    result = re.sub(valid_pattern, '', result)

    # 步骤4：规范空格和换行
    result = result.strip()  # 去除首尾多余空格/换行
    result = result.replace('　', ' ')  # 全角空格转半角空格
    result = re.sub(r'\r\n?', '\n', result)  # 统一换行符为 \n
    return result


def safe_json_loads(input_str: str, json_type: str = 'object', default: Any = None) -> Any:
    """安全解析 JSON 字符串：先移除包装，再 json.loads，失败返回 default（默认 None）。"""
    try:
        return json.loads(remove_json_wrapper(input_str, json_type))
    except (json.JSONDecodeError, ValueError):
        return default
