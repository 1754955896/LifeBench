# -*- coding: utf-8 -*-
"""V1 事件模拟的约束式地理位置分配。"""

from .allocator import TrajectoryAllocator
from .epr import EPRProfile, build_personal_epr_profile
from .export import attach_event_geodata, build_location_records
from .reconciliation import reconcile_estimated_locations, reconcile_final_itinerary
from .injection import render_assignment_summary
from .intent_adapter import parse_stop_intents
from .models import PlausibleLocationSpec, TrajectoryAssignment
from .registry import find_registered_location, remember_location_records
from .timeslot import build_half_hour_trajectory, write_half_hour_trajectory
from .coordinates import attach_record_wgs84, gcj02_to_wgs84

__all__ = [
    "TrajectoryAllocator",
    "EPRProfile",
    "build_personal_epr_profile",
    "TrajectoryAssignment",
    "PlausibleLocationSpec",
    "attach_event_geodata",
    "build_location_records",
    "reconcile_estimated_locations",
    "reconcile_final_itinerary",
    "parse_stop_intents",
    "render_assignment_summary",
    "find_registered_location",
    "remember_location_records",
    "build_half_hour_trajectory",
    "write_half_hour_trajectory",
    "attach_record_wgs84",
    "gcj02_to_wgs84",
]
