# -*- coding: utf-8 -*-
"""simulation 基线包：在不动源码反馈逻辑的前提下，用只读开关包装新的消融过程。"""
from src.lifebench.event.simulation.baseline.no_feedback import (
    generate_subjective_thought_no_feedback,
    generate_objective_events_no_feedback,
)

__all__ = [
    "generate_subjective_thought_no_feedback",
    "generate_objective_events_no_feedback",
]
