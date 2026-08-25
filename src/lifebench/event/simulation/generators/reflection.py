# -*- coding: utf-8 -*-
"""反思生成器：真实情绪、自我洞察、事件记忆、总结反思、未来期望。

从 Mind._generate_reflection 迁出。
"""
import json

from src.lifebench.event.templates.template_simulation import template_daily_reflection
from src.lifebench.utils.llm_call import llm_call_j
from src.lifebench.utils.json_utils import remove_json_wrapper


def generate_reflection(mind, events, plan, date):
    """
    生成反思。

    参数:
        mind: Mind 实例（读取 cognition/long_memory/short_memory 及日志/LLM 工具）
        events: 事件内容
        plan: 今日规划
        date: 目标日期

    返回:
        dict: 反思数据；JSON 解析失败时返回 {"thought": ""}
    """
    prompt = template_daily_reflection.format(
        cognition=mind.cognition,
        memory=mind.long_memory + mind.short_memory,
        content=events,
        plan=plan,
        date=mind.get_date_string(date)
    )
    reflection = llm_call_j(prompt)
    mind._log_event("反思（真实情绪，自我洞察，事件记忆，总结反思，未来期望）-----------------------------------------------------------------------")

    cleaned_reflection = remove_json_wrapper(reflection)
    mind._log_event(cleaned_reflection)
    mind._save_log("", "t4", cleaned_reflection)
    try:
        return json.loads(cleaned_reflection)
    except json.JSONDecodeError:
        # JSON 加载失败，返回空的 thought 字典
        return {"thought": ""}
