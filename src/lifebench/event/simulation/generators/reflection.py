# -*- coding: utf-8 -*-
"""反思生成器：生成记忆摘要、活动统计与下一日上下文。

从 Mind._generate_reflection 迁出。
"""
import json

from src.lifebench.event.templates.template_simulation import template_daily_reflection
from src.lifebench.event.simulation.state import LongTermMemory
from src.lifebench.utils.llm_call import llm_call_j
from src.lifebench.utils.json_utils import remove_json_wrapper


def generate_reflection(mind, events, plan, date):
    """
    生成反思。

    参数:
        mind: Mind 实例（读取分离后的主观上下文及日志/LLM 工具）
        events: 事件内容
        plan: 今日规划
        date: 目标日期

    返回:
        dict: 规范化反思数据；JSON 解析失败时返回可写入记忆的降级结果
    """
    context = getattr(mind, "last_subjective_context", None) or {}
    dumps = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    prompt = template_daily_reflection.format(
        persona=dumps(context.get("persona", getattr(mind, "persona", {}))),
        long_memory=dumps(context.get("long_memory", {})),
        short_memory_context=dumps(context.get("short_memory_context", {})),
        previous_thought=dumps(context.get("previous_thought", {})),
        state_and_needs=dumps(context.get("state_and_needs", "")),
        open_loops=dumps(context.get("open_loops", [])),
        environment=dumps(context.get("environment", {})),
        content=events,
        plan=dumps(plan),
        date=mind.get_date_string(date)
    )
    reflection = llm_call_j(prompt)
    mind._log_event("反思（真实情绪，自我洞察，事件记忆，总结反思，未来期望）-----------------------------------------------------------------------")

    cleaned_reflection = remove_json_wrapper(reflection)
    mind._log_event(cleaned_reflection)
    mind._save_log("", "t4", cleaned_reflection)
    try:
        parsed = json.loads(cleaned_reflection)
    except (json.JSONDecodeError, TypeError):
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    # 反思基础字段必须稳定存在；扩展字段失败不应中断整日模拟。
    event_text = str(events or "").strip()
    raw_metrics = parsed.get("activity_metrics", {})
    raw_metrics = raw_metrics if isinstance(raw_metrics, dict) else {}
    metrics = {}
    for key in ("exercise_minutes", "work_minutes", "overtime_minutes", "social_minutes"):
        try:
            metrics[key] = max(0, min(1440, int(raw_metrics.get(key, 0) or 0)))
        except (TypeError, ValueError):
            metrics[key] = 0
    raw_next = parsed.get("next_day_context", {})
    raw_next = raw_next if isinstance(raw_next, dict) else {}
    open_loops = raw_next.get("open_loops", [])
    state_and_needs = str(raw_next.get("state_and_needs") or "")
    if not state_and_needs:
        state_and_needs = "；".join(
            value for value in (
                str(raw_next.get("state") or "").strip(),
                str(raw_next.get("needs") or "").strip(),
            ) if value
        )
    previous_long_memory = LongTermMemory.from_string(
        str(getattr(mind, "long_memory", "") or "")
    )
    raw_long_memory = parsed.get("long_memory")
    required_memory_fields = {
        "profile_changes", "persistent_patterns", "key_memories", "period_summary",
    }
    valid_long_memory = (
        isinstance(raw_long_memory, dict)
        and required_memory_fields.issubset(raw_long_memory)
        and isinstance(raw_long_memory.get("profile_changes"), str)
        and isinstance(raw_long_memory.get("persistent_patterns"), list)
        and isinstance(raw_long_memory.get("key_memories"), list)
        and isinstance(raw_long_memory.get("period_summary"), str)
    )
    if valid_long_memory:
        next_long_memory = LongTermMemory.from_dict(raw_long_memory)
    else:
        # LLM/JSON 失败时保留完整旧快照，不让一次失败清空长期记忆。
        next_long_memory = previous_long_memory
    result = {
        "date": str(parsed.get("date") or date),
        "topic": str(parsed.get("topic") or "日常活动"),
        "events": str(parsed.get("events") or event_text or f"{date}无可用事件摘要"),
        "thought": str(parsed.get("thought") or "当日反思生成失败，暂不形成新的主观判断。"),
        "activity_metrics": metrics,
        "next_day_context": {
            "state_and_needs": state_and_needs,
            "open_loops": open_loops if isinstance(open_loops, list) else [],
        },
        "long_memory": next_long_memory.to_dict(),
    }
    return result
