# -*- coding: utf-8 -*-
"""每日模拟各阶段生成器。

将 Mind 中的 4 个生成方法迁出为独立模块，Mind 保留薄委托方法。
各函数第一个参数 mind 为 Mind 实例（Duck-typed）；后续步骤会替换为
结构化的 CognitiveState / ContextProvider，当前保持零行为差异迁出。
"""
from src.lifebench.event.simulation.generators.thought import generate_subjective_thought
from src.lifebench.event.simulation.generators.objective import generate_objective_events
from src.lifebench.event.simulation.generators.trajectory import generate_poi_route, adjust_event_trajectory
from src.lifebench.event.simulation.generators.reflection import generate_reflection

__all__ = [
    "generate_subjective_thought",
    "generate_objective_events",
    "generate_poi_route",
    "adjust_event_trajectory",
    "generate_reflection",
]
