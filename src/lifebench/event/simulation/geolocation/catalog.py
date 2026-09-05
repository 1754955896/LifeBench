# -*- coding: utf-8 -*-
"""将画像地址归一化为可复用地点目录。"""
import hashlib
from typing import Any, Dict, Iterable, List, Optional

from .models import LocationCandidate


CATEGORY_TERMS = {
    "meal": ("餐厅", "饭店", "食堂", "咖啡", "茶餐厅", "小吃", "火锅", "麻辣烫", "麻辣香锅"),
    "fitness": ("健身", "体育馆", "游泳馆", "球馆"),
    "shopping": ("商场", "超市", "便利店", "市场", "购物"),
    "medical": ("医院", "诊所", "药店", "门诊"),
    "leisure": ("公园", "影院", "剧院", "博物馆", "景区", "娱乐"),
    "education": ("学校", "大学", "学院", "幼儿园"),
    "work": ("工作地", "公司", "办公室", "写字楼", "单位", "产业园", "园区", "工厂", "制造", "物流"),
    "home": ("家", "住址", "住所", "居住", "住宅", "宿舍"),
}


def infer_category(text: Any, fallback: str = "other") -> str:
    value = str(text or "").lower()
    for category, terms in CATEGORY_TERMS.items():
        if any(term in value for term in terms):
            return category
    return fallback or "other"


def infer_role(name: str, description: str) -> str:
    normalized_name = str(name or "").strip().lower()
    value = str(description or "").lower()
    if normalized_name in {"家", "住址", "住所", "住宅", "宿舍", "home"} or any(
        term in value for term in ("常住地址", "居住地址", "家庭住址", "日常居住", "长期居住")
    ):
        return "home"
    if normalized_name in {"工作地", "公司", "单位", "办公室", "work"} or any(
        term in value for term in ("固定工作地", "工作地址", "办公地址", "工作的办公楼", "日常工作地点")
    ):
        return "work"
    if normalized_name in {"学校", "大学", "学院", "school"}:
        return "education"
    return ""


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(item) for item in value if item)
    if isinstance(value, dict):
        return "".join(str(item) for item in value.values() if item)
    return str(value or "")


def _stable_id(name: str, coordinates: str) -> str:
    digest = hashlib.sha1((name + "|" + coordinates).encode("utf-8")).hexdigest()[:12]
    return "catalog_" + digest


class LocationCatalog:
    def __init__(self, addresses: Optional[Iterable[Dict[str, Any]]]):
        self.items = []  # type: List[LocationCandidate]
        flattened = []  # type: List[Dict[str, Any]]

        def collect(value: Any) -> None:
            if isinstance(value, dict):
                flattened.append(value)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    collect(child)

        collect(addresses or [])
        for index, item in enumerate(flattened):
            if not isinstance(item, dict):
                continue
            name = _text(item.get("name") or item.get("poi") or "地点%d" % (index + 1))
            coordinates = _text(item.get("location"))
            if len(coordinates.split(",")) != 2:
                continue
            description = _text(item.get("description"))
            role = infer_role(name, description)
            declared_category = _text(item.get("category"))
            category = declared_category if declared_category in CATEGORY_TERMS or declared_category == "other" else infer_category(name + _text(item.get("type")))
            if category == "other":
                category = infer_category(description)
            category = role or category
            address = _text(item.get("formatted_address") or item.get("structured_address") or item.get("address"))
            city = _text(item.get("city"))
            candidate = LocationCandidate(
                location_id=_text(item.get("location_id") or item.get("id")) or _stable_id(name, coordinates),
                name=name,
                address=address,
                coordinates=coordinates,
                province=_text(item.get("province")),
                city=city,
                district=_text(item.get("district")),
                adcode=_text(item.get("adcode")),
                category=category,
                role=role,
                source=_text(item.get("source")) or "persona_catalog",
                map_rank=index,
                raw=dict(item),
                confidence=float(item.get("confidence", 1.0) or 1.0),
                map_verified=bool(item.get("map_verified", True)),
            )
            self.items.append(candidate)

    def exact(self, name: str = "", coordinates: str = "",
              city: str = "") -> Optional[LocationCandidate]:
        for item in self.items:
            if coordinates and item.coordinates == coordinates:
                return item
            if (
                name
                and city_matches(city, item.city)
                and (item.name == name or name in item.name or item.name in name)
            ):
                return item
        return None

    def by_location_id(self, location_id: str) -> Optional[LocationCandidate]:
        """按注册表稳定 ID 精确解析；不做模糊匹配。"""
        wanted = str(location_id or "").strip()
        if not wanted:
            return None
        return next((item for item in self.items if item.location_id == wanted), None)

    def anchor(self, role: str, city: str = "") -> Optional[LocationCandidate]:
        return next((
            item for item in self.items
            if item.role == role and city_matches(city, item.city)
        ), None)

    def by_category(self, category: str, city: str = "") -> List[LocationCandidate]:
        return [item for item in self.items if item.category == category and city_matches(city, item.city)]


def normalize_city(city: str) -> str:
    value = str(city or "").strip().lower()
    for suffix in ("特别行政区", "自治州", "地区", "市"):
        if value.endswith(suffix):
            value = value[:-len(suffix)]
    return value


def city_matches(expected: str, actual: str) -> bool:
    return not expected or not actual or normalize_city(expected) == normalize_city(actual)
