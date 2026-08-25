# -*- coding: utf-8 -*-
"""轨迹生成器：真实 POI 定位与事件轨迹调整。

从 Mind.map 与 Mind._adjust_event_trajectory 迁出。
"""
import json

from src.lifebench.event.templates.template_simulation import (
    template_poi_real_location_assign,
    template_event_traffic_adjust,
)
from src.lifebench.utils.llm_call import llm_call_j


def generate_poi_route(mind, pt):
    """
    获取真实 POI 数据与通行信息。

    参数:
        mind: Mind 实例（读取 persona 与 maptools）
        pt: 事件数据

    返回:
        str: 精简后的 POI/路线指令；出错时返回空字符串
    """
    prompt = template_poi_real_location_assign.format(
        persona=mind.persona,
        data=pt,
        persona_address_data=mind.maptools.persona_address_data
    )
    res = llm_call_j(prompt)
    print("poi分析-----------------------------------------------------------------------")
    first_bracket = res.find('{')
    last_bracket = res.rfind('}')
    if first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
        res = res[first_bracket:last_bracket + 1]
    try:
        data = json.loads(res)
        result, error_summary = mind.maptools.process_instruction_route(data)
        instr = ""
        instr += mind.maptools.extract_poi_route_simplified(result)
        return instr
    except Exception as e:
        print(f"map函数出错: {str(e)}")
        return ""


def adjust_event_trajectory(mind, poi_data, event, daily_event_reference="", history=""):
    """
    调整事件轨迹。

    参数:
        mind: Mind 实例（读取 persona_address_data/cognition 及日志/LLM 工具）
        poi_data: POI 数据
        event: 事件数据
        daily_event_reference: 当日事件参考
        history: 历史

    返回:
        str: 调整后的事件内容
    """
    # 简化 persona_address_data，只保留 name、formatted_address 和 description 字段
    simplified_address_data = []
    if mind.persona_address_data and isinstance(mind.persona_address_data, list):
        for address in mind.persona_address_data:
            simplified_address = {
                "name": address.get("name", ""),
                "formatted_address": address.get("formatted_address", ""),
                "description": address.get("description", "")
            }
            simplified_address_data.append(simplified_address)

    print("[DEBUG _adjust_event_trajectory] daily_event_reference type=" + str(type(daily_event_reference)))
    print("[DEBUG _adjust_event_trajectory] daily_event_reference content=" + str(daily_event_reference))
    if isinstance(daily_event_reference, dict):
        print("[DEBUG _adjust_event_trajectory] daily_event_reference keys=" + str(list(daily_event_reference.keys())))

    prompt = template_event_traffic_adjust.format(
        poi=poi_data,
        event=event,
        daily_event_reference=daily_event_reference,
        history=history,
        persona=mind.cognition,
        persona_address_data=simplified_address_data
    )
    adjusted_events = mind.llm_call_s(prompt, 0)
    mind._log_event("轨迹调整-----------------------------------------------------------------------")
    mind._log_event(adjusted_events)
    mind._save_log("", "t3", adjusted_events)
    return adjusted_events
