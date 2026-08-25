# -*- coding: utf-8 -*-
"""逐日校验：schema 与不变量校验。

对内部/外部产物做结构与不变量校验，返回问题列表（空列表表示通过）。
调用方可用 ``assert_valid`` 将问题列表转为异常，或自行收集报告。

校验对象：
- daily_event（最终稳定输出，§3.1 schema）
- memory_store（结构化记忆 + 索引，§3.3）
- memory_trace（检索/写入命中 ID，§3.3）
- manifest（可复现元数据，§3.3）

设计约定：校验函数不抛异常，只返回 ``List[str]`` 问题描述；
``assert_valid`` 负责在存在问题时抛出 ``ValueError``。
"""
import re
from typing import List, Dict, Any

# 模板约定的事件类型枚举（见 §3.1）
EVENT_TYPES = {
    "Career",
    "Education",
    "Relationships",
    "Family&Living Situation",
    "Personal Life",
    "Finance",
    "Health",
    "Unexpected Events",
    "Other",
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def assert_valid(issues: List[str], label: str) -> None:
    """若存在校验问题，抛 ValueError（用于「坏数据不报错」的整改，见问题 #3）。"""
    if issues:
        raise ValueError(f"{label} 校验失败（{len(issues)} 项）：\n- " + "\n- ".join(issues))


# ----------------------------------------------------------------------
# daily_event（最终输出）
# ----------------------------------------------------------------------
def validate_daily_event(event: Any) -> List[str]:
    """校验单条 daily_event（§3.1 schema）。返回问题列表。"""
    issues: List[str] = []
    if not isinstance(event, dict):
        return ["事件不是 dict"]

    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id.strip():
        issues.append(f"event_id 缺失或为空：{event_id!r}")

    name = event.get("name")
    if not isinstance(name, str) or not name.strip():
        issues.append("name 缺失或为空")

    date = event.get("date")
    if not isinstance(date, list) or len(date) == 0:
        issues.append("date 必须是含至少一个字符串的非空数组")
    else:
        for d in date:
            if not isinstance(d, str) or not d.strip():
                issues.append(f"date 数组含非法元素：{d!r}")

    event_type = event.get("type")
    if event_type not in EVENT_TYPES:
        issues.append(f"type 非法（不在枚举内）：{event_type!r}")

    if not isinstance(event.get("description"), str):
        issues.append("description 缺失或非字符串")

    participant = event.get("participant")
    if not isinstance(participant, list):
        issues.append("participant 必须是数组")
    else:
        for p in participant:
            if not isinstance(p, dict) or "name" not in p:
                issues.append(f"participant 元素缺少 name：{p!r}")

    if not isinstance(event.get("location"), str):
        issues.append("location 缺失或非字符串")

    atomic_id = event.get("atomic_id")
    if not isinstance(atomic_id, list):
        issues.append("atomic_id 必须是数组")

    return issues


def validate_daily_events(events: Any) -> List[str]:
    """校验 daily_event 数组：逐条 schema + event_id 全局唯一不变量。"""
    issues: List[str] = []
    if not isinstance(events, list):
        return ["daily_event 顶层必须是数组"]

    seen_ids: Dict[str, int] = {}
    for i, event in enumerate(events):
        issues.extend(f"[{i}] {msg}" for msg in validate_daily_event(event))
        eid = event.get("event_id") if isinstance(event, dict) else None
        if isinstance(eid, str) and eid in seen_ids:
            issues.append(f"event_id 重复：{eid!r}（第 {seen_ids[eid]} 与第 {i} 条）")
        elif isinstance(eid, str):
            seen_ids[eid] = i

    return issues


# ----------------------------------------------------------------------
# memory_store（结构化记忆 + 索引）
# ----------------------------------------------------------------------
def validate_memory_store(data: Any) -> List[str]:
    """校验 memory_store.json：schema + event_id_map 与 memories/embeddings 的一致性不变量。"""
    issues: List[str] = []
    if not isinstance(data, dict):
        return ["memory_store 不是 dict"]

    memories = data.get("memories", {})
    embeddings = data.get("embeddings", {})
    event_id_map = data.get("event_id_map", {})
    event_id_counter = data.get("event_id_counter", 0)

    if not isinstance(memories, dict):
        issues.append("memories 必须是 dict（YYYY-MM-DD → 记忆数组）")
        return issues

    if not isinstance(event_id_map, dict):
        issues.append("event_id_map 必须是 dict（event_id → [date, idx]）")

    # 记忆对象字段
    for date_str, mem_list in memories.items():
        if not _DATE_RE.match(date_str):
            issues.append(f"memories 键非法日期：{date_str!r}")
        if not isinstance(mem_list, list):
            issues.append(f"memories[{date_str!r}] 不是数组")
            continue
        for j, mem in enumerate(mem_list):
            if not isinstance(mem, dict):
                issues.append(f"memories[{date_str}][{j}] 不是 dict")
                continue
            for field in ("date", "topic", "events", "thought"):
                if not isinstance(mem.get(field), str) or not mem[field].strip():
                    issues.append(f"memories[{date_str}][{j}] 缺少字段 {field}")
            if "event_id" not in mem:
                issues.append(f"memories[{date_str}][{j}] 缺少 event_id（记忆未自标识）")

    # event_id_map 一致性：每个 eid 必须指向存在的 (date, idx) 且记忆的 event_id 匹配
    for eid, loc in event_id_map.items():
        if not (isinstance(loc, list) and len(loc) == 2):
            issues.append(f"event_id_map[{eid!r}] 定位必须是 [date, idx]")
            continue
        date_str, idx = loc
        mem_list = memories.get(date_str)
        if mem_list is None or not isinstance(idx, int) or not (0 <= idx < len(mem_list)):
            issues.append(f"event_id_map[{eid!r}] 指向不存在的记忆 ({date_str}, {idx})")
            continue
        if mem_list[idx].get("event_id") != eid:
            issues.append(f"event_id_map[{eid!r}] 与 memories[{date_str}][{idx}].event_id 不一致")

    # embeddings 键应与 event_id_map 键一致（或为其子集）
    emb_keys = set(embeddings) if isinstance(embeddings, dict) else set()
    map_keys = set(event_id_map)
    if emb_keys - map_keys:
        issues.append(f"embeddings 存在 event_id_map 中不存在的键：{sorted(emb_keys - map_keys)}")

    if not isinstance(event_id_counter, int) or event_id_counter < len(map_keys):
        issues.append(f"event_id_counter({event_id_counter}) 小于已分配 event_id 数量({len(map_keys)})")

    return issues


# ----------------------------------------------------------------------
# memory_trace（检索/写入命中 ID）
# ----------------------------------------------------------------------
def validate_memory_trace(data: Any) -> List[str]:
    """校验 memory_trace.json：{ day: { retrieved_memory_ids, written_memory_ids } }。"""
    issues: List[str] = []
    if not isinstance(data, dict):
        return ["memory_trace 不是 dict"]

    for day, entry in data.items():
        if not _DATE_RE.match(day):
            issues.append(f"memory_trace 键非法日期：{day!r}")
        if not isinstance(entry, dict):
            issues.append(f"memory_trace[{day!r}] 不是 dict")
            continue
        for field in ("retrieved_memory_ids", "written_memory_ids"):
            ids = entry.get(field, [])
            if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
                issues.append(f"memory_trace[{day}].{field} 必须是字符串数组")

    return issues


# ----------------------------------------------------------------------
# manifest（可复现元数据）
# ----------------------------------------------------------------------
def validate_manifest(data: Any) -> List[str]:
    """校验 manifest.json 的必要字段存在性与类型。"""
    issues: List[str] = []
    if not isinstance(data, dict):
        return ["manifest 不是 dict"]

    for field in ("model", "temperature", "seed", "template_hash", "config", "dependencies"):
        if field not in data:
            issues.append(f"manifest 缺少字段：{field}")

    if "template_hash" in data and not isinstance(data["template_hash"], str):
        issues.append("manifest.template_hash 必须是字符串")
    if "dependencies" in data and not isinstance(data["dependencies"], dict):
        issues.append("manifest.dependencies 必须是 dict")

    return issues
