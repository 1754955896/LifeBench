# -*- coding: utf-8 -*-
"""认知状态数据结构。

- LongTermMemory：状态型长记忆（覆盖式维护的「用户状态 + 常用信息」）。
- CognitiveState：Mind 的完整认知状态（长期记忆 + 短期记忆 + 想法/认知/上下文/环境），
  用于 checkpoint 持久化与后续遥测。
"""
from dataclasses import dataclass, fields, asdict


@dataclass
class LongTermMemory:
    state: str = ""          # 当前状态：位置/职业/关系/健康/经济/心理（慢变化）
    facts: str = ""          # 客观事实/常用信息
    preferences: str = ""    # 固定偏好
    routines: str = ""       # 重复/习惯性行为
    key_events: str = ""     # 有界关键事件（带遗忘）
    plans: str = ""          # 未来规划（含日期）
    summary: str = ""        # 滚动总结

    _LABELS = [
        ("当前状态", "state"),
        ("客观事实", "facts"),
        ("固定偏好", "preferences"),
        ("习惯行为", "routines"),
        ("关键事件", "key_events"),
        ("未来规划", "plans"),
        ("近期总结", "summary"),
    ]

    # 稳定字段：新值漏填时继承旧值（key_events/plans 保持 LLM 权威，有界、带遗忘）
    _STABLE_FIELDS = ("state", "facts", "preferences", "routines")

    @classmethod
    def from_dict(cls, d) -> "LongTermMemory":
        """从 LLM 输出的 JSON 字典构造（缺字段/非字典时安全降级为空字段）。"""
        if not isinstance(d, dict):
            return cls()
        result = {}
        for f in fields(cls):
            v = d.get(f.name, "")
            if v is None:
                v = ""
            elif not isinstance(v, str):
                v = str(v)
            result[f.name] = v
        return cls(**result)

    def to_string(self) -> str:
        """序列化为可读的带标签文本，注入下游 prompt。"""
        parts = []
        for label, name in self._LABELS:
            value = getattr(self, name)
            if value:
                parts.append(f"【{label}】{value}")
        return "\n".join(parts)

    @classmethod
    def from_string(cls, s: str) -> "LongTermMemory":
        """从 to_string() 的【标签】文本反解析回结构化字段。"""
        result = cls()
        if not isinstance(s, str) or not s:
            return result
        for label, name in cls._LABELS:
            marker = f"【{label}】"
            if marker in s:
                start = s.index(marker) + len(marker)
                rest = s[start:]
                next_idx = rest.find("【")
                value = rest if next_idx == -1 else rest[:next_idx]
                setattr(result, name, value.strip())
        return result

    @classmethod
    def merge(cls, old: "LongTermMemory", new: "LongTermMemory") -> "LongTermMemory":
        """稳定字段（state/facts/preferences/routines）新值漏填时继承旧值。"""
        merged = cls()
        for f in fields(cls):
            new_val = getattr(new, f.name)
            old_val = getattr(old, f.name)
            if f.name in cls._STABLE_FIELDS:
                setattr(merged, f.name, new_val if new_val else old_val)
            else:
                setattr(merged, f.name, new_val)
        return merged


@dataclass
class CognitiveState:
    long_memory: str = ""    # 状态型长记忆（LongTermMemory.to_string() 序列化结果）
    short_memory: str = ""   # 短期记忆（近期详细事件 + 检索事件）
    thought: str = ""        # 当前想法/感受
    cognition: str = ""      # 自我认知
    context: str = ""        # 角色扮演 context
    env: str = ""            # 环境信息

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d) -> "CognitiveState":
        if not isinstance(d, dict):
            return cls()
        result = {}
        for f in fields(cls):
            v = d.get(f.name, "")
            if v is None:
                v = ""
            elif not isinstance(v, str):
                v = str(v)
            result[f.name] = v
        return cls(**result)
