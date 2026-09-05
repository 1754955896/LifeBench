# -*- coding: utf-8 -*-
"""认知状态数据结构。

- LongTermMemory：由每日 reflection 覆盖式维护的四字段长期记忆。
- CognitiveState：Mind 的完整认知状态（长期记忆 + 短期记忆 + 想法/认知/上下文/环境），
  用于 checkpoint 持久化与后续遥测。
"""
import json
from dataclasses import dataclass, field, fields, asdict
from typing import List, Dict


@dataclass
class LongTermMemory:
    profile_changes: str = ""                 # 相对基础画像发生的长期变化
    persistent_patterns: List[str] = field(default_factory=list)  # 反复验证的偏好/习惯/关系模式
    key_memories: List[Dict[str, str]] = field(default_factory=list)  # 有界关键经历
    period_summary: str = ""                  # 当前生活阶段的滚动概括

    @classmethod
    def from_dict(cls, d) -> "LongTermMemory":
        """读取并约束四字段结构。"""
        if not isinstance(d, dict):
            return cls()
        patterns = d.get("persistent_patterns", [])
        memories = d.get("key_memories", [])
        patterns = patterns if isinstance(patterns, list) else []
        memories = memories if isinstance(memories, list) else []
        normalized_memories = []
        for item in memories[:20]:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()
            if content:
                normalized_memories.append({
                    "date": str(item.get("date") or ""),
                    "content": content,
                    "impact": str(item.get("impact") or ""),
                })
        return cls(
            profile_changes=str(d.get("profile_changes") or ""),
            persistent_patterns=[str(item).strip() for item in patterns[:20] if str(item).strip()],
            key_memories=normalized_memories,
            period_summary=str(d.get("period_summary") or ""),
        )

    def to_string(self) -> str:
        """序列化为统一 JSON，便于下一轮直接作为结构化输入。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_string(cls, s: str) -> "LongTermMemory":
        """读取新结构 JSON；其他格式视为空记忆。"""
        if not isinstance(s, str) or not s:
            return cls()
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return cls.from_dict(parsed)
        except (TypeError, ValueError):
            return cls()
        return cls()


@dataclass
class CognitiveState:
    long_memory: str = ""    # 状态型长记忆（LongTermMemory.to_string() 序列化结果）
    thought: str = ""        # 当前想法/感受
    cognition: str = ""      # 自我认知
    context: str = ""        # 角色扮演 context
    env: str = ""            # 环境信息
    short_memory_context: dict = field(default_factory=dict)  # 保留日期和检索来源的短记忆
    next_day_context: dict = field(default_factory=dict)  # reflection 生成的综合状态需求与未完事项
    trajectory_location_history: list = field(default_factory=list)  # 跨日稳定地点注册表
    behavior_history: list = field(default_factory=list)  # 最近30天结构化活动与移动摘要

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d) -> "CognitiveState":
        if not isinstance(d, dict):
            return cls()
        result = {}
        for f in fields(cls):
            dict_field = f.name in {"short_memory_context", "next_day_context"}
            list_field = f.name in {"trajectory_location_history", "behavior_history"}
            v = d.get(f.name, [] if list_field else ({} if dict_field else ""))
            if list_field:
                result[f.name] = v if isinstance(v, list) else []
                continue
            if dict_field:
                result[f.name] = v if isinstance(v, dict) else {}
                continue
            if v is None:
                v = ""
            elif not isinstance(v, str):
                v = str(v)
            result[f.name] = v
        return cls(**result)
