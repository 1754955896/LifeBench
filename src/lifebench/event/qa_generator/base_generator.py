# -*- coding: utf-8 -*-
"""
QA 生成器基类
提供通用的数据加载、手机操作处理等功能
所有具体的 QA 生成器都继承自此类
"""

import json
import os
import random
import copy
import threading
from typing import List, Dict, Any, Tuple
from abc import ABC, abstractmethod


class BaseQAGenerator(ABC):
    """QA 生成器抽象基类"""
    
    def __init__(self, persona_data: Dict[str, Any] = None, event_tree: Dict[str, Any] = None, 
                 daily_event: Dict[str, Any] = None, draft_event: Dict[str, Any] = None, 
                 special_event: Dict[str, Any] = None, phone_data_dir: str = None):
        """
        初始化基础 QA 生成器
        
        Args:
            persona_data: 用户画像数据
            event_tree: 事件树数据
            daily_event: 每日事件数据
            draft_event: 草稿事件数据
            special_event: 特殊事件数据
            phone_data_dir: 手机数据目录路径
        """
        self.persona_data = persona_data or {}
        self.event_tree = event_tree or {}
        self.daily_event = daily_event or {}
        self.draft_event = draft_event or {}
        self.special_event = special_event or {}
        self.phone_data_dir = phone_data_dir
        self.phonedata = {}
        self.phone_id_counters = {}
        
        # 添加线程锁以保护共享状态的修改
        self.phonedata_lock = threading.Lock()
        self.phone_id_lock = threading.Lock()
        
        # 从 special_event 中提取 unique_events
        self.unique_events = self.special_event.get('unique_events', []) if self.special_event else []
        
        # 数据更新标记，用于同步不同生成器之间的数据
        self._data_updated = False
        
        # 如果提供了 phone_data_dir，则加载手机数据
        if phone_data_dir:
            self.load_phone_data_from_dir(phone_data_dir)
    
    @abstractmethod
    def QAGen(self, **kwargs) -> List[Dict[str, Any]]:
        """
        生成 QA 对的抽象方法
        所有子类必须实现此方法
        
        Returns:
            生成的 QA 对列表
        """
        pass
    
    def load_data_from_path(self, data_path: str):
        """
        从指定路径加载用户数据
        
        Args:
            data_path: 数据文件路径
        """
        # 加载用户画像
        persona_path = os.path.join(data_path, "persona.json")
        if os.path.exists(persona_path):
            with open(persona_path, 'r', encoding='utf-8') as f:
                self.persona_data = json.load(f)
        
        # 加载事件树数据
        event_tree_path = os.path.join(data_path, "event_tree.json")
        if os.path.exists(event_tree_path):
            with open(event_tree_path, 'r', encoding='utf-8') as f:
                self.event_tree = json.load(f)
        
        # 加载每日事件数据
        daily_event_path = os.path.join(data_path, "daily_event.json")
        if os.path.exists(daily_event_path):
            with open(daily_event_path, 'r', encoding='utf-8') as f:
                self.daily_event = json.load(f)
        
        # 加载草稿事件数据
        draft_event_path = os.path.join(data_path, "daily_draft.json")
        if os.path.exists(draft_event_path):
            with open(draft_event_path, 'r', encoding='utf-8') as f:
                self.draft_event = json.load(f)
        
        # 加载特殊事件数据
        special_event_path = os.path.join(data_path, "special_event.json")
        if os.path.exists(special_event_path):
            with open(special_event_path, 'r', encoding='utf-8') as f:
                self.special_event = json.load(f)
                self.unique_events = self.special_event.get('unique_events', [])
        
        # 加载手机数据
        phone_data_path = os.path.join(data_path, "phone_data")
        if os.path.exists(phone_data_path):
            self.load_phone_data_from_dir(phone_data_path)
            self.phone_data_dir = phone_data_path
    
    def load_phone_data_from_dir(self, phone_data_dir: str):
        """从目录加载手机数据"""
        if not os.path.exists(phone_data_dir):
            print(f"手机数据目录不存在：{phone_data_dir}")
            return
        
        self.phone_data_dir = phone_data_dir
        
        for filename in os.listdir(phone_data_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(phone_data_dir, filename)
                data_type = filename[:-5]
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data_list = json.load(f)
                    
                    if isinstance(data_list, list):
                        max_id = 0
                        for i, item in enumerate(data_list):
                            if isinstance(item, dict):
                                if 'phone_id' in item:
                                    try:
                                        current_id = int(item['phone_id'])
                                        if current_id > max_id:
                                            max_id = current_id
                                    except ValueError:
                                        item['phone_id'] = i + 1  # 使用 int 格式
                                        max_id = i + 1
                                else:
                                    item['phone_id'] = i + 1  # 使用 int 格式
                                    max_id = i + 1
                        
                        self.phone_id_counters[data_type] = max_id + 1
                    
                    self.phonedata[data_type] = data_list
                    print(f"成功加载手机数据：{filename}")
                except Exception as e:
                    print(f"加载手机数据文件失败 {filename}: {e}")
    
    def save_phone_data_to_dir(self, phone_data_dir: str):
        """保存手机数据到目录"""
        if not os.path.exists(phone_data_dir):
            os.makedirs(phone_data_dir)
        
        for data_type, data_list in self.phonedata.items():
            file_path = os.path.join(phone_data_dir, f"{data_type}.json")
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data_list, f, ensure_ascii=False, indent=2)
                print(f"成功保存手机数据：{data_type}")
            except Exception as e:
                print(f"保存手机数据文件失败 {data_type}: {e}")
    
    def get_draft_event_by_month(self, month: str) -> List[Dict[str, Any]]:
        """获取指定月份的 draft event 数据"""
        if not month or not isinstance(month, str) or len(month) != 7 or month[4] != '-':
            print(f"月份格式错误：{month}，应为 YYYY-MM 格式")
            return []
        
        if not self.draft_event or not isinstance(self.draft_event, dict):
            print("draft_event 数据不存在或格式错误")
            return []
        
        if month in self.draft_event:
            month_data = self.draft_event[month]
            if isinstance(month_data, list):
                filtered_month_data = []
                for day_data in month_data:
                    filtered_day_data = {k: v for k, v in day_data.items() if k != 'state'}
                    filtered_month_data.append(filtered_day_data)
                print(f"找到{month}月份的 draft event 数据，共{len(filtered_month_data)}条")
                return filtered_month_data
            else:
                print(f"{month}对应的数据不是列表格式")
                return []
        
        print(f"没有找到{month}月份的 draft event 数据")
        available_months = [key for key in self.draft_event.keys() 
                          if isinstance(key, str) and len(key) == 7 and key[4] == '-']
        if available_months:
            print(f"可用的月份有：{', '.join(available_months)}")
        
        return []
    
    def _get_daily_event_data(self, count: int = 10, continuous: bool = False) -> List[Dict[str, Any]]:
        """通用每日事件数据获取函数"""
        events = self.daily_event if isinstance(self.daily_event, list) else []
        
        if not events:
            return []
        
        if continuous and len(events) > count:
            max_start_index = len(events) - count
            start_index = random.randint(0, max_start_index)
            return events[start_index:start_index + count]
        else:
            return random.sample(events, min(count, len(events)))
    
    def _get_event_tree_data(self, count: int = 10) -> List[Dict[str, Any]]:
        """通用事件树数据获取函数"""
        if isinstance(self.event_tree, list) and len(self.event_tree) > 0:
            return random.sample(self.event_tree, min(count, len(self.event_tree)))
        return self.event_tree if isinstance(self.event_tree, list) else []
    
    def _get_persona_data(self) -> Dict[str, Any]:
        """通用人画像数据获取函数"""
        return self.persona_data
    
    def get_phone_operations_by_event_id(self, event_id: str) -> List[Dict[str, Any]]:
        """根据事件 ID 获取相关手机操作"""
        phone_operations = []

        if not self.phonedata:
            print("手机数据未加载")
            return phone_operations

        for data_type, data_list in self.phonedata.items():
            if isinstance(data_list, list):
                for item in data_list:
                    if isinstance(item, dict):
                        # 优先匹配 daily_event_id（重命名前的 event_id）
                        if "daily_event_id" in item and item["daily_event_id"] == event_id:
                            phone_operations.append(item)
                        elif "related_event" in item and item["related_event"] == event_id:
                            phone_operations.append(item)

        return phone_operations
    
    def sync_data_from(self, other_generator: 'BaseQAGenerator'):
        """
        从另一个生成器同步数据

        Args:
            other_generator: 数据来源的生成器实例
        """
        with self.phonedata_lock:
            self.phonedata = copy.deepcopy(other_generator.phonedata)
        with self.phone_id_lock:
            self.phone_id_counters = copy.deepcopy(other_generator.phone_id_counters)
        self.persona_data = copy.deepcopy(other_generator.persona_data)
        self.event_tree = copy.deepcopy(other_generator.event_tree)
        self.daily_event = copy.deepcopy(other_generator.daily_event)
        self.draft_event = copy.deepcopy(other_generator.draft_event)
        self.special_event = copy.deepcopy(other_generator.special_event)
    
    def clear_phonedata(self):
        """清空手机数据"""
        with self.phonedata_lock:
            self.phonedata.clear()
        with self.phone_id_lock:
            self.phone_id_counters.clear()
