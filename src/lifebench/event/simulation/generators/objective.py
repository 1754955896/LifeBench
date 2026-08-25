# -*- coding: utf-8 -*-
"""客观事件生成器：结合日程与合理性，对全天事件进行调整、补充与优化。

从 Mind._generate_objective_events 迁出。
"""
from src.lifebench.event.templates.template_simulation import template_daily_event_objective_optimize


def generate_objective_events(mind, plan, date, event):
    """
    生成客观事件。

    参数:
        mind: Mind 实例（读取 long_memory/short_memory/cognition 及日志/LLM 工具）
        plan: 未来规划
        date: 目标日期
        event: 主观思考内容

    返回:
        str: 客观事件内容
    """
    prompt = template_daily_event_objective_optimize.format(
        event=event,
        plan=plan,
        memory=mind.long_memory + mind.short_memory,
        date=mind.get_date_string(date),
        persona=mind.cognition
    )
    events = mind.llm_call_s(prompt, 0)
    mind._log_event("客观生成-----------------------------------------------------------------------")
    mind._log_event(events)
    mind._save_log("", "t2", events)
    return events
