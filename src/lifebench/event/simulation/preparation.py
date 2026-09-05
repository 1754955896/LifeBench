# -*- coding: utf-8 -*-
"""Single-process preparation of immutable assets used by all date shards."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Optional

from src.lifebench.event.tools.location_opportunity_builder import (
    LocationOpportunityBuilder, location_asset_is_current,
    normalize_location_document,
)
from src.lifebench.utils.maptool import MapMaintenanceTool


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _atomic_json(path: str, value: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


class SimulationAssetPreparer:
    """Prepare fuzzy memory and persona location assets before any worker starts."""

    def __init__(
        self, *, data_dir: str, persona: Any, events: Any, location_data: Any,
        location_path: str, config: Any, simulation_start: str,
    ) -> None:
        self.data_dir = data_dir
        self.persona = persona
        self.events = events
        self.location_data = location_data
        self.location_path = location_path
        self.config = _dict(config)
        self.simulation_start = simulation_start
        self.sim_dir = os.path.join(data_dir, "sim")

    def prepare(self) -> Dict[str, Any]:
        settings = _dict(self.config.get("simulation_asset_preparation"))
        if settings.get("enabled", True) is False:
            return {
                "location_data": normalize_location_document(self.location_data, self.persona),
                "asset_snapshot": {"enabled": False},
            }
        os.makedirs(self.sim_dir, exist_ok=True)
        if settings.get("ensure_fuzzy_memory", True):
            self._ensure_fuzzy_memory()
        location_data, location_status = self._ensure_locations(settings)
        anchors = location_data.get("anchors", [])
        if settings.get("strict_anchor_validation", True) and not anchors:
            raise RuntimeError("人物地点资产缺少可用核心锚点，停止创建日期分片")
        snapshot = {
            "schema_version": "simulation_asset_snapshot_v1",
            "simulation_start": self.simulation_start,
            "persona_hash": _hash(self.persona),
            "events_hash": _hash(self.events),
            "location_asset_hash": _hash(location_data),
            "location_status": location_status,
            "frozen": bool(settings.get("freeze_for_run", True)),
        }
        _atomic_json(os.path.join(self.sim_dir, "asset_snapshot.json"), snapshot)
        return {"location_data": location_data, "asset_snapshot": snapshot}

    def _ensure_fuzzy_memory(self) -> None:
        # Lazy import keeps location-only preparation usable without loading the
        # optional sentence-transformer memory stack.
        from src.lifebench.event.simulation.memory.consolidation import FuzzyMemoryBuilder
        builder = FuzzyMemoryBuilder.get_instance(self.events, self.persona, self.sim_dir)
        monthly = os.path.join(self.sim_dir, "monthly_summaries.json")
        cumulative = os.path.join(self.sim_dir, "cumulative_summaries.json")
        if os.path.exists(monthly) and os.path.exists(cumulative):
            builder.load_summaries()
            return
        try:
            year = int(str(self.simulation_start)[:4])
        except (TypeError, ValueError):
            raise ValueError("simulation_start 必须是 YYYY-MM-DD")
        print("模拟预处理：生成 %s 年模糊记忆资产" % year)
        builder.build_all_summaries(year)

    def _ensure_locations(self, settings: Dict[str, Any]):
        trajectory = _dict(self.config.get("trajectory_assignment"))
        pool = _dict(trajectory.get("location_opportunity_pool"))
        normalized = normalize_location_document(self.location_data, self.persona)
        enrich = (
            settings.get("ensure_location_opportunity_pool", True) is not False
            and pool.get("enabled", True) is not False
        )
        refresh = bool(pool.get("refresh", False))
        if enrich and not refresh and location_asset_is_current(normalized, self.persona):
            return normalized, "cache_hit"
        if not enrich:
            if self.location_path:
                _atomic_json(self.location_path, normalized)
            return normalized, "normalized_without_enrichment"

        map_api_key = str(_dict(self.config.get("map_tool")).get("api_key") or "")
        llm_api_key = str(_dict(self.config.get("llm")).get("api_key") or "")
        if not map_api_key or not llm_api_key:
            if self.location_path:
                _atomic_json(self.location_path, normalized)
            return normalized, "normalized_missing_external_configuration"

        from src.lifebench.utils.llm_call import llm_call_j
        builder = LocationOpportunityBuilder(
            maptool=MapMaintenanceTool(map_api_key, persona_address_data=normalized),
            llm_callable=lambda prompt: llm_call_j(prompt),
            target_count=int(pool.get("preseed_target_count", 60) or 60),
            per_query_limit=int(pool.get("per_query_limit", 6) or 6),
        )
        try:
            document, manifest = builder.build(
                self.persona, normalized, self.simulation_start,
            )
        except Exception as error:
            if not settings.get("allow_partial_optional_pois", True):
                raise
            document = normalized
            manifest = {"partial_failures": ["builder_exception:%s" % type(error).__name__]}
        if self.location_path:
            _atomic_json(self.location_path, document)
            _atomic_json(
                os.path.join(os.path.dirname(os.path.abspath(self.location_path)), "location_opportunity_manifest.json"),
                manifest,
            )
        return document, "generated" if document.get("city_reference_pois") else "generated_without_optional_pois"
