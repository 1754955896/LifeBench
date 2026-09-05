# -*- coding: utf-8 -*-
"""每日模拟各阶段生成器（惰性导出，避免阶段间导入耦合）。

将 Mind 中的 4 个生成方法迁出为独立模块，Mind 保留薄委托方法。
各函数第一个参数 mind 为 Mind 实例（Duck-typed）；后续步骤会替换为
结构化的 CognitiveState / ContextProvider，当前保持零行为差异迁出。
"""
from importlib import import_module

__all__ = [
    "generate_subjective_thought",
    "generate_objective_events",
    "generate_poi_route",
    "adjust_event_trajectory",
    "generate_reflection",
]


_EXPORTS = {
    "generate_subjective_thought": ("thought", "generate_subjective_thought"),
    "generate_objective_events": ("objective", "generate_objective_events"),
    "generate_poi_route": ("trajectory", "generate_poi_route"),
    "adjust_event_trajectory": ("trajectory", "adjust_event_trajectory"),
    "generate_reflection": ("reflection", "generate_reflection"),
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute = _EXPORTS[name]
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value
