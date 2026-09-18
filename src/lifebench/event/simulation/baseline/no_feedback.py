# -*- coding: utf-8 -*-
"""no-mobility（无移动反馈）基线：切断「地理移动 → 客观/主观思考」的全部移动考量。

与 simple 地理基线叠加：simple 的地理分配（LLM + 地理工具）本身不读写
behavior_history / trajectory_location_history，也不消费 day_variation_context /
mobility_day_profile，但 daily_event_gen1 每天仍会写入 behavior_history，次日
build_subjective_context 把它读回，将移动统计与今日移动软画像注入主观/客观上下文。

本模块不改动任何源码：用「临时置空结构化反馈载体 + 无移动版提示词」包装主观与
客观生成器，使 thinking 只由 persona / plan / memory / state / environment 驱动，
完全不再考虑移动轨迹；反思/记忆叙事通道（通道 2）与地理分配/回填不受影响。
"""
import json

from src.lifebench.event.simulation.activity_contract import (
    extract_named_json,
    validate_optional_activity_contract,
)
from src.lifebench.event.simulation.context import build_subjective_context
from src.lifebench.event.simulation.state import LongTermMemory
from src.lifebench.event.simulation.baseline.templates_no_mobility import (
    template_daily_event_subjective_plan_no_mobility,
    template_daily_event_objective_optimize_no_mobility,
)


def generate_subjective_thought_no_feedback(mind, plan, date):
    """无移动模式下生成主观思考：置空反馈载体 + 无移动版主观模板。"""
    saved_behavior_history = getattr(mind, "behavior_history", None)
    saved_trajectory_location_history = getattr(mind, "trajectory_location_history", None)
    mind.behavior_history = []
    mind.trajectory_location_history = []
    try:
        context = build_subjective_context(mind, plan, date)
        mind.last_subjective_context = context
        dump = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        prompt = template_daily_event_subjective_plan_no_mobility.format(
            date=date,
            persona=dump(context["persona"]),
            plan=dump(context["plan"]),
            long_memory=dump(context["long_memory"]),
            short_memory_context=dump(context["short_memory_context"]),
            previous_thought=dump(context["previous_thought"]),
            state_and_needs=dump(context["state_and_needs"]),
            environment=dump(context["environment"]),
        )
        thought = mind.llm_call_s(prompt, 0)
        mind.last_optional_activity_plan = extract_named_json(
            thought, "OPTIONAL_ACTIVITY_PLAN"
        )
        mind._log_event("主观思考（计划如何执行、想安排什么活动）-----------------------------------------------------------------------")
        mind._log_event(thought)
        mind._save_log(date, "t1", thought)
        return thought
    finally:
        mind.behavior_history = saved_behavior_history
        mind.trajectory_location_history = saved_trajectory_location_history


def generate_objective_events_no_feedback(mind, plan, date, event):
    """无移动模式下生成客观事件：只读非移动字段 + 无移动版客观模板。"""
    context = getattr(mind, "last_subjective_context", None) or {}
    memory_context = {
        "long_memory": context.get("long_memory") or LongTermMemory.from_string(
            str(getattr(mind, "long_memory", "") or "")
        ).to_dict(),
        "short_memory_context": context.get("short_memory_context") or getattr(
            mind, "short_memory_context", {}
        ),
    }
    dump = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    prompt = template_daily_event_objective_optimize_no_mobility.format(
        event=event,
        plan=plan,
        memory=dump(memory_context),
        date=mind.get_date_string(date),
        persona=dump(
            context.get("persona") or getattr(mind, "persona", {}),
        ),
        state_and_needs=dump(context.get("state_and_needs", "")),
        environment=dump(context.get("environment", {})),
    )
    events = mind.llm_call_s(prompt, 0)
    mind.last_optional_activity_result = extract_named_json(
        events, "OPTIONAL_ACTIVITY_RESULT"
    )
    mind.last_optional_activity_diagnostics = validate_optional_activity_contract(
        getattr(mind, "last_optional_activity_plan", {}),
        mind.last_optional_activity_result,
        0,
    )
    mind._log_event("客观生成-----------------------------------------------------------------------")
    mind._log_event(events)
    mind._save_log("", "t2", events)
    return events
