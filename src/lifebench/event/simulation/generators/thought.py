# -*- coding: utf-8 -*-
"""主观思考生成器：生成拟人化的当日主观安排（计划如何执行、想安排什么活动）。

从 Mind._generate_subjective_thought 迁出。
"""
from src.lifebench.event.templates.template_simulation import template_daily_event_subjective_plan


def generate_subjective_thought(mind, plan, date):
    """
    生成主观思考。

    参数:
        mind: Mind 实例（读取 cognition/long_memory/short_memory/thought/persona 及日志/LLM 工具）
        plan: 今日规划
        date: 目标日期

    返回:
        str: 主观思考内容
    """
    prompt = template_daily_event_subjective_plan.format(
        cognition=mind.cognition,
        memory='这是长期记忆:' + mind.long_memory + '这是短期记忆:' + mind.short_memory,
        thought=mind.thought,
        plan=plan,
        date=mind.get_date_string(date),
        persona=mind.persona
    )
    thought = mind.llm_call_s(prompt, 0)
    mind._log_event("主观思考（计划如何执行、想安排什么活动）-----------------------------------------------------------------------")
    mind._log_event(thought)
    mind._save_log(date, "t1", thought)
    return thought
