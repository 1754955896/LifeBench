# -*- coding: utf-8 -*-
"""主观思考生成器：生成拟人化的当日主观安排（计划如何执行、想安排什么活动）。

从 Mind._generate_subjective_thought 迁出。
"""
import json

from src.lifebench.event.templates.template_simulation import template_daily_event_subjective_plan
from src.lifebench.event.simulation.context import (
    build_subjective_context,
    lean_mobility_day_profile,
)


def generate_subjective_thought(mind, plan, date):
    """
    生成主观思考。

    参数:
        mind: Mind 实例（读取长期/短期记忆、上一日想法、状态、需求和环境）
        plan: 今日规划
        date: 目标日期

    返回:
        str: 主观思考内容
    """
    context = build_subjective_context(mind, plan, date)
    mind.last_subjective_context = context
    dump = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    prompt = template_daily_event_subjective_plan.format(
        date=date,
        persona=dump(context["persona"]),
        plan=dump(context["plan"]),
        long_memory=dump(context["long_memory"]),
        short_memory_context=dump(context["short_memory_context"]),
        previous_thought=dump(context["previous_thought"]),
        state_and_needs=dump(context["state_and_needs"]),
        environment=dump(context["environment"]),
        recent_behavior_summary=dump(context["recent_behavior_summary"]),
        day_variation_context=dump(context["day_variation_context"]),
        mobility_day_profile=dump(lean_mobility_day_profile(context["mobility_day_profile"])),
        location_inspiration_context=dump(context["location_inspiration_context"]),
        activity_recommendation=dump(context["activity_recommendation"]),
    )
    thought = mind.llm_call_s(prompt, 0)
    mind._log_event("主观思考（计划如何执行、想安排什么活动）-----------------------------------------------------------------------")
    mind._log_event(thought)
    mind._save_log(date, "t1", thought)
    return thought
