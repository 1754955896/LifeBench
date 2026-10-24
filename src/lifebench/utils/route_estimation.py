"""Explicit surface travel estimates for synthetic overseas life records.

These values are not routing API results and do not imply a particular service,
road, public transport connection, or timetable.
"""
import math


def estimate_surface_route(origin, destination, mode):
    speeds = {'walking': 4.8, 'bicycling': 14.0, 'driving': 35.0, 'transit': 45.0}
    if mode not in speeds:
        return None
    if origin.get('country_code') != destination.get('country_code'):
        return None  # Cross-border feasibility needs separate evidence.
    try:
        lon1, lat1 = map(float, origin['location'].split(','))
        lon2, lat2 = map(float, destination['location'].split(','))
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    if not all(math.isfinite(v) for v in (lon1, lat1, lon2, lat2)):
        return None
    if not all(-180 <= v <= 180 for v in (lon1, lon2)) or not all(-90 <= v <= 90 for v in (lat1, lat2)):
        return None
    lat_delta, lon_delta = math.radians(lat2-lat1), math.radians(lon2-lon1)
    hav = math.sin(lat_delta/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(lon_delta/2)**2
    straight_km = 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, hav))))
    distance = max(0.001, straight_km * 1.3)
    duration = max(1, math.ceil(distance/speeds[mode]*60 + (8 if mode=='transit' else 0)))
    return {'mode': mode, 'distance_km': round(distance, 3), 'duration_minutes': duration,
            'source': 'synthetic_route_estimate', 'map_verified': False,
            'estimate_method': 'straight_line_detour_speed', 'confidence': 0.4}
