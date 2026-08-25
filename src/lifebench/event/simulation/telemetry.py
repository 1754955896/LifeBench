# -*- coding: utf-8 -*-
"""遥测：manifest（可复现元数据）+ memory_trace（检索/写入命中 ID）。

- build_manifest / save_manifest：记录模型/温度/seed/模板哈希/config/依赖版本，
  支撑「数据集可复现」（见问题 #5）。
- MemoryTraceRecorder：按天累积检索命中与写入的记忆 ID，序列化为
  ``{ day: { retrieved_memory_ids, written_memory_ids } }``（§3.3），供 QA 评估检索质量。

边界：遥测只负责「记录」与「落盘」，不反向依赖 store/retrieval；
trace 的采集点位于 retrieval.py / consolidation.py（见计划 §5.1 注释）。
"""
import json
import os
import hashlib
import threading
import copy
from typing import List, Dict, Optional, Any


def _project_root() -> str:
    # src/lifebench/event/simulation/telemetry.py → 项目根目录
    # (simulation → event → lifebench → src → 项目根，共 5 层)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))))


def _load_config() -> Dict[str, Any]:
    config_path = os.path.join(_project_root(), "config", "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _redact(obj: Any) -> Any:
    """递归脱敏：去掉 api_key / base_url 等敏感字段，避免 manifest 泄漏密钥。"""
    if isinstance(obj, dict):
        return {
            k: _redact(v)
            for k, v in obj.items()
            if k not in {"api_key", "base_url", "password", "token"}
        }
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


def collect_dependency_versions() -> Dict[str, str]:
    """采集关键依赖版本（缺失时报「未安装」而非抛错）。"""
    from importlib.metadata import version, PackageNotFoundError
    packages = [
        "openai", "numpy", "sentence-transformers", "holidays", "pypinyin",
        "torch", "transformers",
    ]
    versions = {}
    for pkg in packages:
        try:
            versions[pkg] = version(pkg)
        except PackageNotFoundError:
            versions[pkg] = "未安装"
    return versions


def compute_template_hash() -> str:
    """计算模拟专用模板文件的 SHA-256 摘要（模板变更 → 摘要变化，保证可复现）。"""
    hasher = hashlib.sha256()
    templates_dir = os.path.join(_project_root(), "src", "lifebench", "event", "templates")
    for name in ("template_simulation.py", "templates.py"):
        path = os.path.join(templates_dir, name)
        if os.path.exists(path):
            with open(path, "rb") as f:
                hasher.update(name.encode("utf-8"))
                hasher.update(b"\x00")
                hasher.update(f.read())
                hasher.update(b"\x00")
    return hasher.hexdigest()


def build_manifest(config: Optional[Dict[str, Any]] = None,
                   seed: Any = None,
                   temperature: Any = None,
                   template_hash: Optional[str] = None) -> Dict[str, Any]:
    """构造 manifest（模型/温度/seed/模板哈希/config/依赖版本）。"""
    if config is None:
        config = _load_config()

    llm_config = config.get("llm", {}) if isinstance(config, dict) else {}

    if template_hash is None:
        template_hash = compute_template_hash()

    return {
        "model": {
            "default_model": llm_config.get("default_model"),
            "reason_model": llm_config.get("reason_model"),
        },
        "temperature": temperature if temperature is not None else llm_config.get("temperature"),
        "seed": seed if seed is not None else config.get("seed"),
        "template_hash": template_hash,
        "config": _redact(config),
        "dependencies": collect_dependency_versions(),
    }


def save_manifest(path: str, manifest: Optional[Dict[str, Any]] = None) -> str:
    """落盘 manifest.json（事务化：写临时文件后原子替换）。"""
    if manifest is None:
        manifest = build_manifest()
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


class MemoryTraceRecorder:
    """按天累积检索命中（retrieved）与写入（written）的记忆 ID。

    线程安全：分片内逐日串行，但保留锁以防将来并行巩固。
    """

    def __init__(self):
        self._trace: Dict[str, Dict[str, List[str]]] = {}
        self._lock = threading.RLock()

    def record(self, date: str,
               retrieved: Optional[List[str]] = None,
               written: Optional[List[str]] = None) -> None:
        """记录某日的命中/写入 ID（可重入：多次调用按日期合并去重）。"""
        if not retrieved and not written:
            return
        with self._lock:
            entry = self._trace.setdefault(date, {
                "retrieved_memory_ids": [],
                "written_memory_ids": [],
            })
            for rid in (retrieved or []):
                if rid and rid not in entry["retrieved_memory_ids"]:
                    entry["retrieved_memory_ids"].append(rid)
            for wid in (written or []):
                if wid and wid not in entry["written_memory_ids"]:
                    entry["written_memory_ids"].append(wid)

    def record_retrieved(self, date: str, ids: List[str]) -> None:
        self.record(date, retrieved=ids)

    def record_written(self, date: str, ids: List[str]) -> None:
        self.record(date, written=ids)

    def to_dict(self) -> Dict[str, Dict[str, List[str]]]:
        with self._lock:
            return copy.deepcopy(self._trace)

    def clear(self) -> None:
        with self._lock:
            self._trace = {}

    def save(self, path: str) -> str:
        """落盘 memory_trace.json（事务化）。"""
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return path

    @staticmethod
    def merge(traces: List[Dict[str, Dict[str, List[str]]]]) -> Dict[str, Dict[str, List[str]]]:
        """合并多个分片 trace（日期不重叠，按日期取并集）。"""
        merged: Dict[str, Dict[str, List[str]]] = {}
        for trace in traces:
            for day, entry in (trace or {}).items():
                slot = merged.setdefault(day, {
                    "retrieved_memory_ids": [],
                    "written_memory_ids": [],
                })
                for field in ("retrieved_memory_ids", "written_memory_ids"):
                    for x in entry.get(field, []):
                        if x not in slot[field]:
                            slot[field].append(x)
        return merged
