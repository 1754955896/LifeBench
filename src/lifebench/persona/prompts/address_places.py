"""Prompt for planning frequently visited places around grounded core addresses."""

import json
from typing import Any, Dict, List

PROMPT_VERSION = "persona-address-places-v3"


def build_address_places_prompt(profile: Dict[str, Any], core_addresses: List[Dict[str, Any]]) -> str:
    compact_core = [
        {
            "address_type": item.get("address_type"),
            "name": item.get("name"),
            "formatted_address": item.get("formatted_address") or item.get("structured_address"),
            "city": item.get("city") or (item.get("geocode") or {}).get("city"),
        }
        for item in core_addresses
    ]
    return f"""
根据人物画像和已经冻结的真实核心地址，规划 6～12 个现实中可能经常前往的周边场所类型和城市级公共地标。

输出格式：
{{"items":[{{
  "base_address_type":"居住地或工作地",
  "scope":"around 或 city",
  "keyword":"公园、超市、咖啡馆等通用场所类型",
  "poi_type":"可选的 POI 类型",
  "frequency":"daily、weekly 或 monthly",
  "description":"该人物前往此处的具体用途"
}}]}}

要求：
- base_address_type 必须来自给定核心地址，不能创造新的核心地址。
- scope=around 时必须填写 base_address_type；scope=city 时 base_address_type 填“城市”，用于全城搜索真实公共地标。
- keyword 只能是通用场所类型，不能虚构或指定品牌、门店名称。
- frequency 表示现实访问频率：daily 为几乎每天/每周多次，weekly 为每周，monthly 为每月偶尔。
- 至少包含一个 daily 和一个 weekly 场所；monthly 只用于医院、远郊休闲、大型商场等低频目的地。
- 必须覆盖以下生活刚需，不能只生成兴趣、休闲类场所：
  - 居住地周边至少一个「超市/便利店/菜市场/药店」类采购场所，frequency 为 daily 或 weekly。
  - 居住地周边至少一个「餐馆/餐厅/快餐/面馆/小吃」类餐饮场所，frequency 为 daily 或 weekly。
  - 工作地周边至少一个「餐馆/快餐/便利店/咖啡」类即时场所，frequency 为 daily。
- 至少规划一个 scope=city 的城市级地点，结合人物兴趣从博物馆、城市公园、图书馆、体育中心、历史地标等公共场所中选择通用类型。
- 健身、球类、跑步、游泳、阅读、兴趣班等高频兴趣地点必须以居住地为 base_address_type；工作地周边只规划工作日餐饮、咖啡、便利店等即时需求。城市级低频地标除外。
- 根据职业、健康、爱好和生活方式选择，避免所有画像都生成同一组场所。
- 不生成家和工作地本身，不输出 Markdown 或额外字段。

核心地址：
{json.dumps(compact_core, ensure_ascii=False, indent=2)}

人物画像：
{json.dumps(profile, ensure_ascii=False, indent=2)}
""".strip()
