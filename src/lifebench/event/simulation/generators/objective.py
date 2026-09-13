# -*- coding: utf-8 -*-
"""客观事件生成器：结合日程与合理性，对全天事件进行调整、补充与优化。

从 Mind._generate_objective_events 迁出。
"""
import json

from src.lifebench.event.templates.template_simulation import template_daily_event_objective_optimize
from src.lifebench.event.simulation.context import lean_mobility_day_profile
from src.lifebench.event.simulation.state import LongTermMemory
from src.lifebench.event.simulation.activity_contract import (
    extract_named_json, validate_optional_activity_contract,
)


def generate_objective_events(mind, plan, date, event):
    """
    生成客观事件。

    参数:
        mind: Mind 实例（读取结构化画像、记忆、状态、环境及日志/LLM工具）
        plan: 未来规划
        date: 目标日期
        event: 主观思考内容

    返回:
        str: 客观事件内容
    """
    context = getattr(mind, "last_subjective_context", None) or {}
    memory_context = {
        "long_memory": context.get("long_memory") or LongTermMemory.from_string(
            str(getattr(mind, "long_memory", "") or "")
        ).to_dict(),
        "short_memory_context": context.get("short_memory_context") or getattr(
            mind, "short_memory_context", {}
        ),
    }
    prompt = template_daily_event_objective_optimize.format(
        event=event,
        plan=plan,
        memory=json.dumps(memory_context, ensure_ascii=False, separators=(",", ":")),
        date=mind.get_date_string(date),
        persona=json.dumps(
            context.get("persona") or getattr(mind, "persona", {}),
            ensure_ascii=False, separators=(",", ":"),
        ),
        state_and_needs=json.dumps(
            context.get("state_and_needs", ""),
            ensure_ascii=False, separators=(",", ":"),
        ),
        environment=json.dumps(
            context.get("environment", {}),
            ensure_ascii=False, separators=(",", ":"),
        ),
        recent_behavior_summary=json.dumps(
            context.get("recent_behavior_summary", {}),
            ensure_ascii=False, separators=(",", ":"),
        ),
        day_variation_context=json.dumps(
            context.get("day_variation_context", {}),
            ensure_ascii=False, separators=(",", ":"),
        ),
        mobility_day_profile=json.dumps(
            lean_mobility_day_profile(context.get("mobility_day_profile", {})),
            ensure_ascii=False, separators=(",", ":"),
        ),
        location_inspiration_context=json.dumps(
            context.get("location_inspiration_context", {}),
            ensure_ascii=False, separators=(",", ":"),
        ),
    )
    events = mind.llm_call_s(prompt, 0)
    mind.last_optional_activity_result = extract_named_json(
        events, "OPTIONAL_ACTIVITY_RESULT"
    )
    variation = context.get("day_variation_context", {}) or {}
    mind.last_optional_activity_diagnostics = validate_optional_activity_contract(
        getattr(mind, "last_optional_activity_plan", {}),
        mind.last_optional_activity_result,
        int(variation.get("preferred_extra_activity_count", 0) or 0),
    )
    mind._log_event("客观生成-----------------------------------------------------------------------")
    mind._log_event(events)
    mind._save_log("", "t2", events)
    return events
