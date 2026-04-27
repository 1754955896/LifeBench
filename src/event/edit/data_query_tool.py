# -*- coding: utf-8 -*-
"""
数据查询工具类
为 PlanningAgent 提供按 ID、日期、条件查询数据的能力
"""

import json
import os
import re
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta


class DataQueryTool:
    """
    数据查询工具
    支持按多种维度查询数据，为 PlanningAgent 提供决策依据
    """
    
    def __init__(self, base_dir: str):
        """
        初始化查询工具
        
        Args:
            base_dir: 基础数据目录路径
        """
        self.base_dir = base_dir
        self._cache: Dict[str, Any] = {}
    
    # ========== 按 ID 查询 ==========
    
    def query_by_id(self, data_type: str, record_id: str) -> Optional[Dict]:
        """
        按 ID 查询单条数据
        
        Args:
            data_type: 数据类型（daily_event/daily_draft/phone_data/xxx）
            record_id: 记录 ID（如 event_id、draf_id 等）
            
        Returns:
            查询到的数据，未找到返回 None
        """
        if data_type == "daily_event":
            return self._query_event_by_id(record_id)
        elif data_type == "daily_draft":
            return self._query_draft_by_id(record_id)
        elif data_type.startswith("phone_data/"):
            subtype = data_type.replace("phone_data/", "")
            return self._query_phone_data_by_id(subtype, record_id)
        else:
            # 尝试通用查询
            return self._query_generic_by_id(data_type, record_id)
    
    def _query_event_by_id(self, event_id: str) -> Optional[Dict]:
        """按 event_id 查询日常事件"""
        events = self._load_daily_events()
        for event in events:
            if event.get("event_id") == event_id:
                return event
        return None
    
    def _query_draft_by_id(self, draft_id: str) -> Optional[Dict]:
        """按 draft_id 查询草稿"""
        drafts = self._load_daily_drafts()
        return drafts.get(draft_id)
    
    def _query_phone_data_by_id(self, subtype: str, record_id) -> Optional[Dict]:
        """按 ID 查询手机数据"""
        phone_data = self._load_phone_data(subtype)
        data_list = phone_data.get(subtype, [])
        
        # 尝试将 record_id 转为 int，兼容 phone_id 等整数字段
        try:
            record_id_int = int(record_id)
        except (TypeError, ValueError):
            record_id_int = None
        
        for record in data_list:
            # 手机数据可能有不同的 ID 字段，含整数类型的 phone_id
            id_fields = ["phone_id", "event_id", "id", "record_id", "call_id", "sms_id"]
            for id_field in id_fields:
                val = record.get(id_field)
                if val is None:
                    continue
                if val == record_id:
                    return record
                if record_id_int is not None and val == record_id_int:
                    return record
        return None
    
    def _query_generic_by_id(self, data_type: str, record_id: str) -> Optional[Dict]:
        """通用 ID 查询"""
        # 尝试从缓存查找
        if data_type in self._cache:
            data = self._cache[data_type]
            if isinstance(data, list):
                for item in data:
                    if item.get("id") == record_id or item.get("event_id") == record_id:
                        return item
            elif isinstance(data, dict):
                return data.get(record_id)
        return None
    
    # ========== 按日期查询 ==========
    
    def query_by_date(
        self,
        data_type: str,
        date: str,
        date_field: str = "date"
    ) -> List[Dict]:
        """
        按日期查询数据
        
        Args:
            data_type: 数据类型
            date: 日期字符串（YYYY-MM-DD 格式）
            date_field: 日期字段名
            
        Returns:
            该日期下的所有数据
        """
        if data_type == "daily_event":
            return self._query_events_by_date(date, date_field)
        elif data_type.startswith("phone_data/"):
            subtype = data_type.replace("phone_data/", "")
            return self._query_phone_data_by_date(subtype, date, date_field)
        else:
            return self._query_generic_by_date(data_type, date, date_field)
    
    def query_by_date_range(
        self,
        data_type: str,
        start_date: str,
        end_date: str,
        date_field: str = "date"
    ) -> List[Dict]:
        """
        按日期范围查询数据
        
        Args:
            data_type: 数据类型
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            date_field: 日期字段名
            
        Returns:
            日期范围内的所有数据
        """
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        # daily_event 的 date 字段是列表格式，必须用 _extract_dates_from_event 解析
        if data_type == "daily_event":
            all_data = self._load_daily_events()
            results = []
            for item in all_data:
                item_dates = self._extract_dates_from_event(item)
                for d_str in item_dates:
                    try:
                        d = datetime.strptime(d_str, "%Y-%m-%d")
                        if start <= d <= end:
                            results.append(item)
                            break  # 一个事件只加一次
                    except ValueError:
                        continue
            return results
        
        all_data = self._load_all_by_type(data_type)
        results = []
        
        for item in all_data:
            item_date_str = self._extract_date_from_item(item, date_field)
            if item_date_str:
                try:
                    item_date = datetime.strptime(item_date_str, "%Y-%m-%d")
                    if start <= item_date <= end:
                        results.append(item)
                except ValueError:
                    continue
        
        return results
    
    def _query_events_by_date(self, date: str, date_field: str = "date") -> List[Dict]:
        """查询某日的所有日常事件"""
        events = self._load_daily_events()
        results = []
        
        for event in events:
            # 检查多种可能的日期字段
            event_dates = self._extract_dates_from_event(event)
            if date in event_dates:
                results.append(event)
        
        return results
    
    def _query_phone_data_by_date(
        self,
        subtype: str,
        date: str,
        date_field: str = "timestamp"
    ) -> List[Dict]:
        """查询某日的手机数据"""
        phone_data = self._load_phone_data(subtype)
        data_list = phone_data.get(subtype, [])
        results = []
        
        for record in data_list:
            # 从 timestamp 或 datetime 字段提取日期
            ts = record.get(date_field, record.get("datetime", record.get("date", "")))
            if ts and date in ts:  # 简单字符串匹配
                results.append(record)
        
        return results
    
    def _query_generic_by_date(
        self,
        data_type: str,
        date: str,
        date_field: str = "date"
    ) -> List[Dict]:
        """通用日期查询"""
        all_data = self._load_all_by_type(data_type)
        results = []
        
        for item in all_data:
            item_date = self._extract_date_from_item(item, date_field)
            if item_date == date:
                results.append(item)
        
        return results
    
    # ========== Draft 日期范围查询（粗略数据）==========
    
    def _query_drafts_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """查询日期范围内的草稿数据"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        drafts = self._load_daily_drafts()
        results = []
        
        for draft_id, draft_content in drafts.items():
            # draft_id 格式通常为 "2025-03-10" 或包含日期
            draft_date = None
            
            # 尝试从 draft_id 提取日期
            if isinstance(draft_id, str):
                match = re.search(r'(\d{4}-\d{2}-\d{2})', draft_id)
                if match:
                    draft_date = match.group(1)
            
            # 如果 draft_id 中没有日期，尝试从 content 中提取
            if not draft_date and isinstance(draft_content, dict):
                draft_date = draft_content.get("date")
            
            if draft_date:
                try:
                    d = datetime.strptime(draft_date, "%Y-%m-%d")
                    if start <= d <= end:
                        results.append({
                            "draft_id": draft_id,
                            **(draft_content if isinstance(draft_content, dict) else {"content": draft_content})
                        })
                except ValueError:
                    continue
        
        return results
    
    def _query_events_by_date_range_simple(self, start_date: str, end_date: str) -> List[Dict]:
        """查询日期范围内的事件（简化版，只返回基本信息以减少数据量）"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        all_data = self._load_daily_events()
        results = []
        
        for item in all_data:
            item_dates = self._extract_dates_from_event(item)
            for d_str in item_dates:
                try:
                    d = datetime.strptime(d_str, "%Y-%m-%d")
                    if start <= d <= end:
                        # 简化版：只返回基本字段，减少数据量
                        results.append({
                            "event_id": item.get("event_id"),
                            "name": item.get("name"),
                            "type": item.get("type"),
                            "date": d_str,
                            "start_time": item.get("start_time"),
                            "end_time": item.get("end_time")
                        })
                        break  # 一个事件只加一次
                except ValueError:
                    continue
        
        return results
    
    def _query_phone_data_by_date_range(
        self,
        subtype: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """查询日期范围内的手机数据"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        phone_data = self._load_phone_data(subtype)
        data_list = phone_data.get(subtype, [])
        results = []
        
        for record in data_list:
            # 从 timestamp 或 datetime 字段提取日期
            ts = record.get("timestamp", record.get("datetime", record.get("date", "")))
            if ts:
                match = re.search(r'(\d{4}-\d{2}-\d{2})', ts)
                if match:
                    record_date = match.group(1)
                    try:
                        d = datetime.strptime(record_date, "%Y-%m-%d")
                        if start <= d <= end:
                            results.append(record)
                    except ValueError:
                        continue
        
        return results
    
    def _query_generic_by_date_range(
        self,
        data_type: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """通用日期范围查询"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        all_data = self._load_all_by_type(data_type)
        results = []
        
        for item in all_data:
            item_date = self._extract_date_from_item(item, "date")
            if item_date:
                try:
                    d = datetime.strptime(item_date, "%Y-%m-%d")
                    if start <= d <= end:
                        results.append(item)
                except ValueError:
                    continue
        
        return results
    
    def query_by_date_range_draft(
        self,
        start_date: str,
        end_date: str,
        data_type: str = "daily_event"
    ) -> List[Dict]:
        """
        按日期范围查询数据（粗略数据，简化返回内容以减少数据量）
        
        Args:
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            data_type: 数据类型（daily_event/daily_draft/phone_data/xxx）
            
        Returns:
            日期范围内的数据列表（简化版）
        """
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        # 根据数据类型选择不同的加载方式
        if data_type == "daily_draft":
            return self._query_drafts_by_date_range(start_date, end_date)
        elif data_type == "daily_event":
            return self._query_events_by_date_range_simple(start_date, end_date)
        elif data_type.startswith("phone_data/"):
            subtype = data_type.replace("phone_data/", "")
            return self._query_phone_data_by_date_range(subtype, start_date, end_date)
        else:
            # 通用查询
            return self._query_generic_by_date_range(data_type, start_date, end_date)
    
    # ========== 复合查询 ==========
    
    def query_by_date_range_and_condition(
        self,
        data_type: str,
        start_date: str,
        end_date: str,
        condition: Dict[str, Any],
        date_field: str = "date"
    ) -> List[Dict]:
        """
        按日期范围和条件复合查询数据
        
        Args:
            data_type: 数据类型
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            condition: 查询条件字典 {字段名: 值}
            date_field: 日期字段名
            
        Returns:
            同时满足日期范围和条件的所有数据
        """
        # 先按日期范围查询
        date_range_results = self.query_by_date_range(
            data_type, start_date, end_date, date_field
        )
        
        # 再按条件过滤
        results = []
        for item in date_range_results:
            if self._match_condition(item, condition):
                results.append(item)
        
        return results
    
    # ========== 按条件查询 ==========
    
    def query_by_condition(
        self,
        data_type: str,
        condition: Dict[str, Any]
    ) -> List[Dict]:
        """
        按条件查询数据
        
        Args:
            data_type: 数据类型
            condition: 查询条件字典 {字段名: 值}
            
        Returns:
            匹配条件的所有数据
        """
        all_data = self._load_all_by_type(data_type)
        results = []
        
        for item in all_data:
            if self._match_condition(item, condition):
                results.append(item)
        
        return results
    
    def query_related_events(
        self,
        event_id: str,
        relation_type: str = "same_date"
    ) -> List[Dict]:
        """
        查询相关事件
        
        Args:
            event_id: 参考事件 ID
            relation_type: 关联类型（same_date/same_participant/same_location）
            
        Returns:
            相关事件列表
        """
        source_event = self._query_event_by_id(event_id)
        if not source_event:
            return []
        
        events = self._load_daily_events()
        results = []
        
        if relation_type == "same_date":
            # 查找同一天的其他事件
            source_dates = self._extract_dates_from_event(source_event)
            for event in events:
                if event.get("event_id") == event_id:
                    continue
                event_dates = self._extract_dates_from_event(event)
                if set(source_dates) & set(event_dates):  # 有日期交集
                    results.append(event)
        
        elif relation_type == "same_participant":
            # 查找相同参与者的其他事件
            source_participants = set(
                p.get("name") for p in source_event.get("participant", [])
            )
            for event in events:
                if event.get("event_id") == event_id:
                    continue
                event_participants = set(
                    p.get("name") for p in event.get("participant", [])
                )
                if source_participants & event_participants:
                    results.append(event)
        
        return results
    
    # ========== 数据加载方法 ==========
    
    def _load_daily_events(self) -> List[Dict]:
        """加载日常事件数据"""
        if "daily_event" not in self._cache:
            file_path = os.path.join(self.base_dir, "daily_event.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    self._cache["daily_event"] = json.load(f)
            else:
                self._cache["daily_event"] = []
        return self._cache["daily_event"]
    
    def _load_daily_drafts(self) -> Dict:
        """加载草稿数据"""
        if "daily_draft" not in self._cache:
            file_path = os.path.join(self.base_dir, "daily_draft.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    self._cache["daily_draft"] = json.load(f)
            else:
                self._cache["daily_draft"] = {}
        return self._cache["daily_draft"]
    
    def _load_phone_data(self, subtype: str = None) -> Dict[str, List[Dict]]:
        """加载手机数据"""
        cache_key = f"phone_data_{subtype}" if subtype else "phone_data"
        
        if cache_key not in self._cache:
            data_dir = os.path.join(self.base_dir, "phone_data")
            result = {}
            
            if os.path.exists(data_dir):
                if subtype:
                    # 加载指定类型
                    file_path = os.path.join(data_dir, f"{subtype}.json")
                    if os.path.exists(file_path):
                        with open(file_path, "r", encoding="utf-8") as f:
                            result[subtype] = json.load(f)
                else:
                    # 加载所有类型
                    for filename in os.listdir(data_dir):
                        if filename.endswith(".json"):
                            file_path = os.path.join(data_dir, filename)
                            dtype = filename.replace(".json", "")
                            with open(file_path, "r", encoding="utf-8") as f:
                                result[dtype] = json.load(f)
            
            self._cache[cache_key] = result
        
        return self._cache[cache_key]
    
    def _load_all_by_type(self, data_type: str) -> List[Dict]:
        """加载指定类型的所有数据"""
        if data_type == "daily_event":
            return self._load_daily_events()
        elif data_type == "daily_draft":
            return list(self._load_daily_drafts().values())
        elif data_type.startswith("phone_data/"):
            subtype = data_type.replace("phone_data/", "")
            phone_data = self._load_phone_data(subtype)
            return phone_data.get(subtype, [])
        return []
    
    # ========== 工具方法 ==========
    
    def _extract_dates_from_event(self, event: Dict) -> List[str]:
        """从事件中提取所有日期（含 datetime 格式和带时间的范围）"""
        dates = []
        
        # 检查 date 字段（可能是字符串或列表）
        date_field = event.get("date", [])
        if isinstance(date_field, str):
            date_field = [date_field]
        
        if isinstance(date_field, list):
            for d in date_field:
                if not isinstance(d, str):
                    continue
                if "至" in d:
                    # 带时间的范围："2025-01-02 06:30:00至2025-01-02 09:00:00"
                    # 先提取两端的日期部分再展开
                    parts = d.split("至")
                    clean = [re.search(r'(\d{4}-\d{2}-\d{2})', p) for p in parts]
                    clean_dates = [m.group(1) for m in clean if m]
                    if len(clean_dates) == 2:
                        dates.extend(self._expand_date_range(
                            f"{clean_dates[0]}至{clean_dates[1]}"
                        ))
                    else:
                        dates.extend(clean_dates)
                else:
                    # 可能是 "2025-01-02" 或 "2025-01-02 08:00:00"
                    m = re.search(r'(\d{4}-\d{2}-\d{2})', d)
                    if m:
                        dates.append(m.group(1))
        
        return dates
    
    def _extract_date_from_item(self, item: Dict, date_field: str) -> Optional[str]:
        """从数据项中提取日期"""
        value = item.get(date_field, "")
        if isinstance(value, str):
            # 尝试提取 YYYY-MM-DD 格式
            match = re.search(r'(\d{4}-\d{2}-\d{2})', value)
            if match:
                return match.group(1)
        return value if isinstance(value, str) else None
    
    def _expand_date_range(self, date_range: str) -> List[str]:
        """展开日期范围"""
        if "至" not in date_range:
            return [date_range]
        
        try:
            start_str, end_str = date_range.split("至")
            start = datetime.strptime(start_str.strip(), "%Y-%m-%d")
            end = datetime.strptime(end_str.strip(), "%Y-%m-%d")
            
            dates = []
            current = start
            while current <= end:
                dates.append(current.strftime("%Y-%m-%d"))
                current += timedelta(days=1)
            return dates
        except ValueError:
            return [date_range]
    
    def _match_condition(self, item: Dict, condition: Dict) -> bool:
        """检查数据项是否匹配条件"""
        for key, value in condition.items():
            if key not in item or item[key] != value:
                return False
        return True
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
    
    def get_summary(self, data_type: str) -> Dict[str, Any]:
        """获取数据摘要"""
        if data_type == "daily_event":
            events = self._load_daily_events()
            return {
                "total_count": len(events),
                "date_range": self._get_date_range(events),
                "type_distribution": self._get_type_distribution(events)
            }
        elif data_type == "daily_draft":
            drafts = self._load_daily_drafts()
            return {
                "total_count": len(drafts)
            }
        elif data_type.startswith("phone_data/"):
            subtype = data_type.replace("phone_data/", "")
            phone_data = self._load_phone_data(subtype)
            data_list = phone_data.get(subtype, [])
            return {
                "total_count": len(data_list),
                "subtype": subtype
            }
        return {}
    
    def _get_date_range(self, events: List[Dict]) -> Dict[str, str]:
        """获取事件的日期范围"""
        all_dates = []
        for event in events:
            all_dates.extend(self._extract_dates_from_event(event))
        
        if not all_dates:
            return {"start": None, "end": None}
        
        sorted_dates = sorted(set(all_dates))
        return {"start": sorted_dates[0], "end": sorted_dates[-1]}
    
    def _get_type_distribution(self, events: List[Dict]) -> Dict[str, int]:
        """获取事件类型分布"""
        type_count = {}
        for event in events:
            event_type = event.get("type", "unknown")
            type_count[event_type] = type_count.get(event_type, 0) + 1
        return type_count
