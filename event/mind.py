# -*- coding: utf-8 -*-
import ast
import json
import re
import holidays
import threading
import copy
import os
from pyarrow import string
from utils.IO import *
from datetime import datetime, timedelta
from utils.llm_call import *
from utils.maptool import *
from event.templates import *
from event.memory import *
from event.fuzzy_memory_builder import FuzzyMemoryBuilder
from typing import List, Dict, Optional
class Mind:
    def __init__(self,file_path, instance_id=0, persona=None, event=None, daily_state=None):
        self.calendar = {}  # 存储日程数据，格式如{"2025-01-01":["event1","event2"],...}
        self.events = event if event is not None else []
        self.persona = persona if persona is not None else ""
        self.persona_withoutrl = ""
        # 创建独立的记忆模块实例，使用基于人物标识的记忆文件
        # 使用instance_id作为人物唯一标识，确保每个人只有一个memory文件
        memory_file_name = f"personal_memories_{instance_id}.json"
        memory_file_path = os.path.join("memory_file", memory_file_name)
        self.mem_module = MemoryModule.get_instance(str(instance_id), memory_file=memory_file_path)
        self.context = ""
        self.cognition = ""  # 主要存储对自我的认知，包括画像信息
        self.long_memory = ""  # 主要存储近期事件感知、印象深刻的关键事件、长期主要事件感知、近期想法及推理思考（动机）
        self.short_memory = ""  # 主要存储近期所有详细事件和相关检索事件
        self.reflection = ""  # 主要存储对现在和未来的思考
        self.thought = ""  # 记录个人的感受、想法，包括情绪、想法、需求及思考过程中的打算
        self.bottom_events : Optional[List[Dict]] = None
        # 读取配置文件
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        # 获取地图工具配置
        map_config = config.get('map_tool', {})
        map_api_key = map_config.get('api_key', 'f6fa3480d4a0e08cd1243f311fa03582')
        self.maptools = MapMaintenanceTool(map_api_key)
        self.env = ""
        self.file_path = file_path
        self.instance_id = instance_id
        # 存储每日处理的中间输出，用于后续统一提取事件
        self.daily_intermediate_outputs = {}
        # Fuzzy memory builder reference
        self.fuzzy_memory_builder = None
        # 新增daily_state属性
        self.daily_state = daily_state if daily_state is not None else []

    def save_to_json(self):
        data = {}
        data["persona"] =  self.persona
        data["context"] = self.context
        data["cognition"] = self.cognition
        data["long_memory"] = self.long_memory
        data["short_memory"] = self.short_memory
        data["reflection"] = self.reflection
        data["thought"] = self.thought
        data['env'] = self.env
        
        # 获取当前日期和线程ID
        current_date = datetime.now().strftime("%Y-%m-%d")
        thread_id = threading.get_ident()
        
        # 创建日期文件夹和record子文件夹
        date_folder = os.path.join(self.file_path, current_date)
        record_folder = os.path.join(date_folder, "record")
        if not os.path.exists(record_folder):
            os.makedirs(record_folder)
        
        # 创建固定文件名，包含线程ID
        filename = f"record_thread_{thread_id}.json"
        file_path = os.path.join(record_folder, filename)
        
        # 保存到同一个文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n=== 数据已保存到 {file_path} ===")

    def _get_bottom_level_events(self) -> List[Dict]:
        """
        递归提取所有最底层事件（subevent为空），结果缓存到self.bottom_events
        
        返回:
            List[Dict]: 最底层事件列表
        """
        if self.bottom_events is not None:
            #print("已计算过，直接返回缓存")
            return self.bottom_events  # 已计算过，直接返回缓存

        def recursive_extract(events: List[Dict]) -> List[Dict]:
            result = []
            for event in events:
                subevents = event.get("subevent", [])
                if not subevents:
                    result.append(event)
                else:
                    result.extend(recursive_extract(subevents))
            return result

        self.bottom_events = recursive_extract(self.events)
        return self.bottom_events

    def update_bottom_level_events(self):
        """
        重新从事件中抽取底层事件（清空缓存并重新计算）
        
        返回:
            List[Dict]: 最底层事件列表
        """
        def recursive_extract(events: List[Dict]) -> List[Dict]:
            result = []
            for event in events:
                subevents = event.get("subevent", [])
                if not subevents:
                    result.append(event)
                else:
                    result.extend(recursive_extract(subevents))
            return result

        self.bottom_events = recursive_extract(self.events)
        return self.bottom_events
    @staticmethod
    def is_date_match(target_date_str: str, event_date_str: str) -> bool:
        """
        判断事件日期是否包含目标日期（支持单个日期/日期范围）
        
        参数:
            target_date_str: 目标日期（格式：YYYY-MM-DD）
            event_date_str: 事件日期（格式：YYYY-MM-DD 或 YYYY-MM-DD至YYYY-MM-DD）
        
        返回:
            bool: 匹配结果（True/False）
        """
        # 验证目标日期格式，如果包含"至"，则截取至之前的部分
        if "至" in target_date_str:
            target_date_str = target_date_str.split("至")[0].strip()
        
        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"目标日期格式错误：{target_date_str}，需符合YYYY-MM-DD")

        # 处理日期范围
        if "至" in event_date_str:
            try:
                start_str, end_str = event_date_str.split("至")
                start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d").date()
                end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(f"事件日期格式错误：{event_date_str}，范围需符合YYYY-MM-DD至YYYY-MM-DD")
            return start_date <= target_date <= end_date
        # 处理单个日期
        else:
            try:
                event_date = datetime.strptime(event_date_str.strip(), "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(f"事件日期格式错误：{event_date_str}，单个日期需符合YYYY-MM-DD")
            return event_date == target_date

    def filter_by_date(self, target_date: str) -> List[Dict]:

        """
        筛选指定日期的最底层事件
        
        参数:
            target_date: 目标日期（格式：YYYY-MM-DD）
        
        返回:
            List[Dict]: 匹配的事件列表
        """
        # 步骤1：获取所有底层事件（自动缓存）
        bottom_events = self._get_bottom_level_events()

        def extract_start_date(date_str: str) -> str:
            """
            从时间字符串中提取起始日期，兼容多种格式：
            1. 时间区间（如"2025-01-01 07:30:00至2025-01-01 08:45:00"）
            2. 单个时间（如"2025-01-01 07:30:00"或"2025-01-01"）
            3. 带中文时段的时间（如"2025-01-01 上午"或"2025-01-01 下午"）
            4. 短年份格式（如"5-03-23" → "2025-03-23"）

            参数:
                date_str: 输入的时间字符串（支持含"至"的区间和不含"至"的单个时间）

            返回:
                str: 提取的起始日期，格式固定为"YYYY-MM-DD"；提取失败时返回默认日期"2026-01-01"
            """
            import re
            #print("date_str:", date_str)
            # 步骤1：分割字符串，提取起始时间部分（含"至"则取左边，不含则取全部）
            if "至" in date_str:
                # 分割"至"，取左侧的起始时间（如"2025-01-01 07:30:00"）
                start_time_part = date_str.split("至")[0].strip()
            else:
                # 无"至"，整个字符串即为起始时间（如"2025-01-01 07:30:00"或"2025-01-01"）
                start_time_part = date_str.strip()

            # 增强鲁棒性：去除所有中文和无关字符
            # 只保留数字、字母、空格和日期分隔符（- : .）
            start_time_part = re.sub(r'[^0-9a-zA-Z\s\-:\.]', '', start_time_part)
            # 去除多余空格
            start_time_part = ' '.join(start_time_part.split())
            
            # 特殊处理：检查是否为短年份格式（如"5-03-23" → "2025-03-23"）
            date_part = start_time_part.split()[0] if ' ' in start_time_part else start_time_part
            if '-' in date_part:
                parts = date_part.split('-')
                if len(parts) == 3:
                    # 检查是否为短年份格式（如"5-03-23"）
                    if len(parts[0]) <= 2 and len(parts[1]) <= 2 and len(parts[2]) <= 2:
                        # 假设格式为 YYYY-MM-DD 但年份只有1-2位
                        # 补全年份为4位（20xx）
                        year = parts[0].zfill(2)
                        if len(year) == 2:
                            year = "20" + year
                        month = parts[1].zfill(2)
                        day = parts[2].zfill(2)
                        
                        # 重新组合日期部分
                        new_date_part = f"{year}-{month}-{day}"
                        
                        # 替换原始日期部分
                        if ' ' in start_time_part:
                            start_time_part = new_date_part + start_time_part[len(date_part):]
                        else:
                            start_time_part = new_date_part

            # 步骤2：解析起始时间部分，提取纯日期（支持多种子格式）
            supported_formats = [
                "%Y-%m-%d %H:%M:%S",  # 带秒级时间的格式（如"2025-01-01 07:30:00"）
                "%Y-%m-%d",  # 纯日期格式（如"2025-01-01"）
                "%Y-%m-%d %H:%M",     # 带分钟级时间的格式（如"2025-01-01 07:30"）
                "%Y-%m-%d %H"         # 带小时级时间的格式（如"2025-01-01 07"）
            ]

            for fmt in supported_formats:
                try:
                    # 解析时间后，按"YYYY-MM-DD"格式返回起始日期
                    start_datetime = datetime.strptime(start_time_part, fmt)
                    return start_datetime.strftime("%Y-%m-%d")
                except ValueError:
                    # 一种格式解析失败，尝试下一种
                    continue

            # 所有格式都解析失败时，返回默认日期"2026-01-01"
            return "2026-01-01"
        # 步骤2：筛选匹配日期的事件
        matched = []
        for event in bottom_events:
            # 统一处理date为数组或单个字符串的情况，转为可迭代对象
            date_values = event.get("date", [])
            if not isinstance(date_values, list):
                date_values = [date_values]  # 若为单个字符串，转为单元素列表

            for date_str in date_values:
                date_str = extract_start_date(date_str)
                if self.is_date_match(target_date, date_str):
                    matched.append(event)
                    break # 避免同一事件因多个日期重复加入

        return matched
    def initialize(self, event, persona, date, daily_state=None):
        """
        初始化Mind对象
        
        参数:
            event: 事件数据
            persona: 人物画像数据
            date: 模拟开始日期，格式为"YYYY-MM-DD"
            daily_state: 每日状态数据，格式与test_daily_state.json相同
        """
        self.persona = copy.deepcopy(persona)
        self.events = event
        self.current_date = date
        # 初始化daily_state
        self.daily_state = daily_state if daily_state is not None else []
        if daily_state is None:
            print("未提供daily_state，将使用默认值。")
        # 初始化FuzzyMemoryBuilder
        self.fuzzy_memory_builder = FuzzyMemoryBuilder.get_instance(event, persona, self.file_path)
        
        # 检查fuzzymemory文件是否存在，如果不存在则生成
        year = int(date[:4])
        monthly_file = os.path.join(self.file_path, "monthly_summaries.json")
        cumulative_file = os.path.join(self.file_path, "cumulative_summaries.json")
        
        if not (os.path.exists(monthly_file) and os.path.exists(cumulative_file)):
            print(f"未找到fuzzymemory文件，开始生成{year}年的月度总结和累积总结...")
            self.fuzzy_memory_builder.build_all_summaries(year)
            print("fuzzymemory生成完成！")
        else:
            print("fuzzymemory文件已存在，直接加载...")
            self.fuzzy_memory_builder.load_summaries()
        
        # 初始化长期记忆和短期记忆
        self.long_memory = self.get_fuzzy_long_memory(date)
        mem = ""
        self.update_short_memory("",self.get_next_n_day(date,-1))
        
        # 生成cognition和context
        t1 = '''
        请你基于下面的个人画像，以第一人称视角描述你对自己的自我认知，包括1）个人基本信息。2）工作的主要特征、内容、方式、习惯、主要人物。3）家庭的主要特征、内容、方式、习惯、主要人物。4）其他生活的主要特征、内容、方式、习惯、主要人物。5）平常工作日的常见安排，目前的主要每天安排。
        个人画像：{persona}
        '''

        t2 = '''
        请你基于下面的个人画像，设计一句让大模型扮演该角色的context，以”你是一位“开头。不超过50个字，只保留重要信息。
        个人画像：{persona}
        '''

        prompt = t1.format(persona=self.persona)
        res = self.llm_call_s(prompt)
        print(res)
        self.cognition = res
        
        prompt = t2.format(persona=self.persona)
        res = self.llm_call_s(prompt)
        print(res)
        self.context = res
        
        # 初始化persona_withoutrl
        self.persona_withoutrl = persona.copy()  # 创建副本以避免修改原始persona
        del self.persona_withoutrl["relation"]  # 在副本上删除relation键
        self.update_bottom_level_events()
    def load_from_json(self, event, persona):
        """
        从record.json加载记忆数据（仅当record=1时使用）
        
        参数:
            event: 事件数据
            persona: 人物画像数据
            record: 是否从record.json加载数据（1表示是，其他值表示否）
        
        返回:
            False: 保持原有返回值
        """
        self.persona = copy.deepcopy(persona)
        self.events = event

        d = read_json_file('record.json')
        self.long_memory = d['long_memory']
        self.short_memory = d['short_memory']
        self.thought = d['thought']
        self.env = d['env']
        self.cognition = d['cognition']
        self.context = d['context']
        # 创建副本以避免修改原始persona
        persona_copy = persona.copy()
        del persona_copy["relation"]
        self.persona_withoutrl = persona_copy
        
        return False

    def get_date_string(self,date_str, country="CN"):
        """
        生成包含日期、周几和节日（如有）的字符串
        :param date_str: 公历日期字符串，格式"YYYY-MM-DD"
        :param country: 国家/地区代码（默认中国"CN"）
        :return: 格式化字符串，例："2025-10-01，星期三，国庆节" 或 "2025-05-15，星期四"
        """
        try:
            # 解析日期
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")

            # 获取星期几
            weekday_map = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            weekday = weekday_map[date_obj.weekday()]

            # 获取节日（多个节日用顿号分隔）
            country_holidays = holidays.CountryHoliday(country)
            holidays_list = []
            if date_obj in country_holidays:
                raw_holidays = country_holidays.get(date_obj)
                holidays_list = raw_holidays if isinstance(raw_holidays, list) else [raw_holidays]
            festival_str = "，".join(holidays_list) if holidays_list else ""

            # 拼接结果（无节日则省略最后一个逗号）
            parts = [date_str, weekday]
            if festival_str:
                parts.append(festival_str)
            return "，".join(parts)

        except ValueError:
            return "日期格式错误，请使用'YYYY-MM-DD'格式"

    def parse_date(self,date_str):
        """解析日期字符串，返回(开始日期, 结束日期)的datetime元组"""
        date_format = "%Y-%m-%d"
        if "至" in date_str:
            start_str, end_str = date_str.split("至")
            start_date = datetime.strptime(start_str.strip(), date_format)
            end_date = datetime.strptime(end_str.strip(), date_format)
        else:
            single_date = datetime.strptime(date_str.strip(), date_format)
            start_date = single_date
            end_date = single_date
        return (start_date, end_date)

    def filter_events_by_start_range(self,events_data, start_range_str, end_range_str):
        """
        筛选事件开始时间在[start_range, end_range]范围内的最上层事件
        :param events_data: 最上层事件列表
        :param start_range_str: 筛选的开始时间（格式"YYYY-MM-DD"）
        :param end_range_str: 筛选的结束时间（格式"YYYY-MM-DD"）
        :return: 符合条件的事件列表
        """
        def extract_start_date(date_str: str) -> str:
            """
            从时间字符串中提取起始日期，兼容多种格式：
            1. 时间区间（如"2025-01-01 07:30:00至2025-01-01 08:45:00"）
            2. 单个时间（如"2025-01-01 07:30:00"或"2025-01-01"）
            3. 带中文时段的时间（如"2025-01-01 上午"或"2025-01-01 下午"）

            参数:
                date_str: 输入的时间字符串（支持含"至"的区间和不含"至"的单个时间）

            返回:
                str: 提取的起始日期，格式固定为"YYYY-MM-DD"

            异常:
                ValueError: 输入字符串不符合支持的时间格式时抛出
            """
            import re
            
            # 步骤1：分割字符串，提取起始时间部分（含"至"则取左边，不含则取全部）
            if "至" in date_str:
                # 分割"至"，取左侧的起始时间（如"2025-01-01 07:30:00"）
                start_time_part = date_str.split("至")[0].strip()
            else:
                # 无"至"，整个字符串即为起始时间（如"2025-01-01 07:30:00"或"2025-01-01"）
                start_time_part = date_str.strip()

            # 增强鲁棒性：去除所有中文和无关字符
            # 只保留数字、字母、空格和日期分隔符（- : .）
            start_time_part = re.sub(r'[^0-9a-zA-Z\s\-:\.]', '', start_time_part)
            # 去除多余空格
            start_time_part = ' '.join(start_time_part.split())
            
            # 步骤2：解析起始时间部分，提取纯日期（支持多种子格式）
            supported_formats = [
                "%Y-%m-%d %H:%M:%S",  # 带秒级时间的格式（如"2025-01-01 07:30:00"）
                "%Y-%m-%d",  # 纯日期格式（如"2025-01-01"）
                "%Y-%m-%d %H:%M",     # 带分钟级时间的格式（如"2025-01-01 07:30"）
                "%Y-%m-%d %H"         # 带小时级时间的格式（如"2025-01-01 07"）
            ]

            for fmt in supported_formats:
                try:
                    # 解析时间后，按"YYYY-MM-DD"格式返回起始日期
                    start_datetime = datetime.strptime(start_time_part, fmt)
                    return start_datetime.strftime("%Y-%m-%d")
                except ValueError:
                    # 一种格式解析失败，尝试下一种
                    continue

            # 所有格式都解析失败时，抛出明确错误
            raise ValueError(
                f"时间格式不支持！请输入以下格式之一：\n"
                f"1. 时间区间（如'2025-01-01 07:30:00至2025-01-01 08:45:00'）\n"
                f"2. 单个时间（如'2025-01-01 07:30:00'或'2025-01-01'）\n"
                f"当前输入：{date_str}"
            )
        date_format = "%Y-%m-%d"
        try:
            # 解析用户输入的时间范围
            start_range = datetime.strptime(start_range_str, date_format)
            end_range = datetime.strptime(end_range_str, date_format)
        except ValueError:
            raise ValueError("日期格式错误，请使用'YYYY-MM-DD'格式")

        if start_range > end_range:
            raise ValueError("开始时间不能晚于结束时间")

        matched_events = []
        for event in events_data:
            event_dates = event.get("date", [])
            for date_str in event_dates:
                date_str = extract_start_date(date_str)
                event_start, _ = self.parse_date(date_str)  # 只关注事件的开始时间
                # 检查事件开始时间是否在用户指定的范围内
                if start_range <= event_start <= end_range:
                    matched_events.append(event)
                    break  # 一个事件只要有一个日期项符合就保留
        return matched_events

    def get_event_by_id(self, target_event_id: str) -> List[Dict]:
        """
        递归遍历所有层级事件，提取匹配目标ID的事件
        
        参数:
            target_event_id: 目标事件ID（如"1-1"、"1-1-3"）
        
        返回:
            List[Dict]: 匹配ID的事件列表（理论上ID唯一时返回单个元素，兼容重复ID）
        """
        matched_events = []

        def recursive_search(events: List[Dict]):
            """内部递归函数：遍历事件及子事件，匹配ID"""
            for event in events:
                # 1. 检查当前事件的ID是否匹配
                current_event_id = event.get("event_id")
                if current_event_id == target_event_id or str(current_event_id) == target_event_id:
                    matched_events.append(event)
                # 2. 递归遍历当前事件的子事件（即使当前ID匹配，也继续找子事件中的潜在匹配）
                subevents = event.get("subevent", [])
                if subevents:
                    recursive_search(subevents)

        # 从原始数据的根节点开始递归搜索
        recursive_search(self.events)
        return matched_events
    def llm_call_sr(self, prompt, record=0):
        """
        调用大模型进行推理
        
        参数:
            prompt: 提示词
            record: 是否记录调用（默认0：不记录）
        
        返回:
            str: 大模型返回结果
        """
        res = llm_call_reason(prompt, self.context, record=record)
        return res

    def llm_call_s(self, prompt, record=0):
        """
        调用大模型
        
        参数:
            prompt: 提示词
            record: 是否记录调用（默认0：不记录）
        
        返回:
            str: 大模型返回结果
        """
        res = llm_call(prompt,self.context,record=record)
        return res

    def get_next_n_day(self,date_str: str,n) -> str:
        """
        获取字符串日期的一天后日期（格式保持一致：YYYY-MM-DD）
        :param date_str: 输入日期字符串（格式必须为YYYY-MM-DD）
        :return: 一天后日期的字符串（格式YYYY-MM-DD）
        """
        try:
            # 1. 将字符串转换为datetime日期对象
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            # 2. 加一天（timedelta(days=1)表示1天的时间间隔）
            next_day_obj = date_obj + timedelta(days=n)
            # 3. 将日期对象转回字符串（保持YYYY-MM-DD格式）
            return next_day_obj.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(f"日期格式错误：{date_str}，请使用YYYY-MM-DD格式（例如'2025-01-01'）")

    def get_plan(self,date):#今日行动的详细信息+未来行动的粗略信息
        res = {"今日事件":"","未来一周背景":""}
        id_set = set()

        def getdata(date):
            data1 = {"事件序列":[],"事件背景":[],"今日安排参考":""}
            arr = self.filter_by_date(date)
            arr1 = []
            for item in arr:
                id = item['event_id']
                if id in id_set:
                    continue
                else:
                    id_set.add(id)
                    parts = id.split('-', 1)[0]
                    e = self.get_event_by_id(parts)
                    arr1.append(e)
            data1["事件序列"] = arr
            data1["事件背景"] = arr1
            
            # 新增今日安排参考字段
            if self.daily_state:
                for daily_item in self.daily_state:
                    if daily_item.get("date") == date:
                        data1["今日安排参考"] = daily_item
                        break
            
            return data1
        res["今日事件"] = getdata(date)
        r = []
        for event in self.filter_events_by_start_range(self.events, date, self.get_next_n_day(date, 7)):
            # 深拷贝每个事件字典，创建独立副本
            event_copy = copy.deepcopy(event)
            r.append(event_copy)

        # 2. 此时修改 r 中的事件，不会影响原始 self.events
        for i in r:
            i['subevent'] = []

        # 3. 赋值给 res，完全不关联原始数据
        res["未来一周背景"] = r

        # 生成事件副本，避免修改原始数据
        #print(res)
        return res

    def get_plan2(self, date):  # 今日行动的详细信息+未来行动的粗略信息
            res = {"今日事件": "", "未来一周背景": ""}
            id_set = set()

            def getdata(date):
                data1 = {"事件序列": [], "事件背景": [], "今日安排参考": ""}
                arr = self.filter_by_date(date)
                arr1 = []
                for item in arr:
                    id = item['event_id']
                    if id in id_set:
                        continue
                    else:
                        id_set.add(id)
                        parts = id.rsplit('-', 1)[0]
                        e = self.get_event_by_id(parts)
                        arr1.append(e)
                data1["事件序列"] = arr
                data1["事件背景"] = arr1
                
                # 新增今日安排参考字段
                if self.daily_state:
                    for daily_item in self.daily_state:
                        if daily_item.get("date") == date:
                            data1["今日安排参考"] = daily_item
                            break
                
                return data1

            res["今日事件"] = getdata(date)
            r = {}
            for d in iterate_dates(date,self.get_next_n_day(date,5)):
                e = self.filter_by_date(d)
                r[d] = e
            # 3. 赋值给 res，完全不关联原始数据
            res["未来一周背景"] = r
            res["前一天事件"] = {self.get_next_n_day(date,-1):self.filter_by_date(self.get_next_n_day(date,-1))}
            # 生成事件副本，避免修改原始数据
            # print(res)
            return res

    def delete_top_event(self,events, target_id):
        """
        删除最上层事件（仅删除顶级事件，不处理子事件）

        :param events: 事件列表（顶层事件数组）
        :param target_id: 要删除的事件ID
        :return: 删除后的事件列表
        """
        return [event for event in events if event.get("event_id") != target_id]

    def add_top_event(self,events, new_event):
        """
        添加新的顶层事件，若event_id为0则自动分配不冲突的ID

        :param events: 原事件列表（顶层事件数组）
        :param new_event: 待添加的事件字典
        :return: 添加后的事件列表
        """
        # 复制新事件避免修改原对象
        new_event['event_id'] = "0"
        event_to_add = new_event.copy()

        # 处理ID为0的情况
        if event_to_add.get("event_id") in ("0", 0):
            # 提取现有顶层事件的ID并转换为整数
            existing_ids = []
            for event in events:
                try:
                    # 尝试将ID转换为整数（兼容数字型ID）
                    existing_ids.append(int(event.get("event_id", "")))
                except (ValueError, TypeError):
                    # 非数字ID不参与自动分配逻辑
                    pass

            # 计算新ID（最大ID+1，若没有则从1开始）
            new_id = max(existing_ids) + 1 if existing_ids else 1
            event_to_add["event_id"] = str(new_id)

        # 确保subevent字段存在（默认空列表）
        if "subevent" not in event_to_add:
            event_to_add["subevent"] = []

        # 添加到事件列表并返回
        return events + [event_to_add]

    def event_schedule(self,event,date):
        """
                    根据操作序列修改原始事件数据，删除操作仅删除目标ID事件本身，保留上层结构
                    :param original_data: 原始事件数据列表
                    :param operations: 操作序列列表
                    :return: 改动后的事件数据列表
        """
        def modify_event_data(original_data, operations):
            """
            根据操作序列修改原始事件数据，删除操作仅删除目标ID事件本身，保留上层结构
            :param original_data: 原始事件数据列表
            :param operations: 操作序列列表
            :return: 改动后的事件数据列表
            """
            # 深拷贝原始数据，避免修改原数据
            modified_data = json.loads(json.dumps(original_data))
            for op in operations:
                op_type = op["type"]
                event_info = op["event"]
                target_event_id = event_info["event_id"]

                # 1. 执行删除操作：仅删除目标ID事件本身，保留上层事件结构
                if op_type == "delete":
                    # 递归函数：查找并删除目标事件，保留上层结构
                    def delete_target_event(event_list, target_id):
                        deleted = False
                        for i in range(len(event_list)):
                            current_event = event_list[i]
                            # 匹配当前事件ID，直接删除该事件
                            if current_event["event_id"] == target_id:
                                del event_list[i]
                                deleted = True
                                break
                            # 递归检查子事件，删除子事件中的目标事件
                            if current_event.get("subevent") and len(current_event["subevent"]) > 0:
                                deleted = delete_target_event(current_event["subevent"], target_id)
                                if deleted:
                                    break
                        return deleted

                    # 遍历所有顶层事件，触发递归删除
                    for top_event in modified_data:
                        if delete_target_event([top_event], target_event_id):
                            break

                # 2. 执行更新操作：找到目标事件并更新（支持多层级）
                elif op_type == "update":
                    # 递归函数：查找并更新目标事件
                    def update_subevent(event_list, target_id, new_event):
                        updated = False
                        for i in range(len(event_list)):
                            current_event = event_list[i]
                            # 匹配当前事件ID
                            if current_event["event_id"] == target_id:
                                event_list[i] = new_event
                                updated = True
                                break
                            # 递归检查子事件
                            if current_event.get("subevent") and len(current_event["subevent"]) > 0:
                                updated = update_subevent(current_event["subevent"], target_id, new_event)
                                if updated:
                                    break
                        return updated

                    # 遍历最上层事件，触发递归更新
                    for top_event in modified_data:
                        if update_subevent([top_event], target_event_id, event_info):
                            break

            return modified_data

        for i in event:
            self.events = modify_event_data(self.events,event)

        self.update_bottom_level_events()
        print("[【【【【【【【【【【【【【【【【【【更新事件】】】】】】】】】】】】】】】】】】]")
        return

    def event_add(self,data):
        """
            新增上层事件，并更新底层事件

        """
        for i in data:
            self.events = self.add_top_event(self.events,i)
        self.update_bottom_level_events()
        return
    def update_short_memory(self, dailyevent, date):
        """
        更新短期记忆，插入今日事件并检索相关历史事件
        
        参数:
            dailyevent: 今日事件内容
            date: 当前日期字符串（格式：YYYY-MM-DD）
        
        返回:
            None: 直接更新实例的short_memory属性
        """
        # 记忆库插入今天事件
        if dailyevent!="":
            self.mem_module.add_memory(dailyevent)
        # 检索明天相关事件
        def get_target_dates(date_str: str, date_format: str = "%Y-%m-%d") -> List[str]:
            """
            根据输入的字符串日期，获取「前两天日期」和「本日日期」的字符串数组（按时间升序排列）

            参数:
                date_str: 输入的日期字符串，默认格式为"YYYY-MM-DD"（如"2025-01-01"）
                date_format: 日期字符串的格式，默认是"%Y-%m-%d"，可根据实际需求修改

            返回:
                List[str]: 按时间升序排列的日期数组，格式为[前两天日期, 本日日期]

            异常:
                ValueError: 若输入的日期字符串格式与指定格式不匹配，会抛出该异常
            """
            # 1. 将字符串日期转为datetime对象
            try:
                target_date = datetime.strptime(date_str, date_format)
            except ValueError as e:
                raise ValueError(f"日期格式错误！请确保输入符合'{date_format}'格式（如'2025-01-01'），错误信息：{str(e)}")

            # 2. 计算前四天的日期（本日日期 - 4天）
            two_days_ago = target_date - timedelta(days=2)
            one_days_ago = target_date - timedelta(days=1)
            three_days_ago = target_date - timedelta(days=3)
            f = target_date - timedelta(days=4)
            # 3. 将两个日期转回原格式的字符串
            two_days_ago_str = two_days_ago.strftime(date_format)
            target_date_str = target_date.strftime(date_format)
            one_days_ago_str = one_days_ago.strftime(date_format)
            three_days_ago_str = three_days_ago.strftime(date_format)
            f_str = f.strftime(date_format)
            # 4. 返回按时间升序排列的数组（前两天在前，本日在后）
            return [target_date_str,one_days_ago_str,two_days_ago_str,f_str]

        def get_next_day(date_str: str, date_format: str = "%Y-%m-%d") -> str:
            """
            输入字符串日期，返回其「后一天」的日期（同格式字符串）

            参数:
                date_str: 输入日期字符串，默认格式"YYYY-MM-DD"（如"2025-02-28"）
                date_format: 日期格式，默认"%Y-%m-%d"，可自定义（如"%Y/%m/%d"）

            返回:
                str: 后一天的日期字符串（与输入格式一致）

            异常:
                ValueError: 输入日期格式错误或日期无效（如"2025-02-30"）时抛出
            """
            # 1. 将字符串转为datetime对象（自动校验日期有效性）
            try:
                current_date = datetime.strptime(date_str, date_format)
            except ValueError as e:
                raise ValueError(f"日期错误！需符合'{date_format}'格式且为有效日期（如'2025-02-28'），错误：{str(e)}")

            # 2. 加1天（自动处理月份/年份交替，如2025-02-28→2025-03-01、2025-12-31→2026-01-01）
            next_day_date = current_date + timedelta(days=1)

            # 3. 转回原格式字符串并返回
            return next_day_date.strftime(date_format)

        def get_cycle_dates_array(date_str: str, date_format: str = "%Y-%m-%d") -> List[str]:
            """
            根据输入字符串日期，返回「上个月同日、上周同星期」的日期数组（按固定顺序排列）

            参数:
                date_str: 输入日期字符串，默认格式"YYYY-MM-DD"（如"2025-03-15"）
                date_format: 日期格式，默认"%Y-%m-%d"，可自定义（如"%Y/%m/%d"）

            返回:
                List[str]: 日期数组，顺序为 [上个月同日, 上周同星期]

            异常:
                ValueError: 输入日期格式不匹配时抛出
            """
            # 1. 解析输入日期
            try:
                current_date = datetime.strptime(date_str, date_format)
            except ValueError as e:
                raise ValueError(f"日期格式错误！需符合'{date_format}'（如'2025-03-15'），错误：{str(e)}")

            # 2. 计算上个月同日（处理当月无同日场景）
            def _get_last_month_same_day(date: datetime) -> datetime:
                try:
                    return date.replace(month=date.month - 1)
                except ValueError:
                    # 当月无该日期（如3月31日），返回上月最后一天
                    return date.replace(day=1) - timedelta(days=1)

            last_month_day = _get_last_month_same_day(current_date).strftime(date_format)

            # 3. 计算上周同星期（固定减7天）
            last_week_weekday = (current_date - timedelta(days=7)).strftime(date_format)

            # 4. 直接返回数组（顺序：上个月同日 → 上周同星期）
            return [last_month_day, last_week_weekday]

        #最终增加前五天事件、上周同日事件、上月同日事件、检索最相似2日事件
        date_set = set()
        mem = ""
        for i in get_target_dates(date):
            res = self.mem_module.search_by_date(start_time=i)
            for j in res:
                mem += j['events']
                date_set.add(j['date'])
            if res == []:
                mem += self.get_fuzzy_short_memory(i)

        for i in get_cycle_dates_array(get_next_day(date)):
            res = self.mem_module.search_by_date(start_time=i)
            for j in res:
                mem += j['events']
                date_set.add(j['date'])
        arr = self.filter_by_date(get_next_day(date))
        res = ""
        for item in arr:
            name = item['name']
            res += name
        res = self.mem_module.search_by_topic_embedding(res,2)
        for i in res:
            if i['date'] in date_set:
                continue
            mem += i['events']
        self.short_memory = mem
        return
    def get_fuzzy_short_memory(self,date):
        date_events = self.filter_by_date(date)
        res = "我在"+date+"做了下面这些事："
        for item in date_events:
            name = item['name']
            res += name
            res += "，"
        return res

    def get_fuzzy_long_memory(self, date):
        """
        获取到指定日期为止的模糊长期记忆
        
        参数:
            date: 目标日期，格式为"YYYY-MM-DD"
        
        返回:
            str: 合并后的长期记忆内容
        """
        try:
            # 解析日期
            target_date = datetime.strptime(date, "%Y-%m-%d")
            year = target_date.year
            month = target_date.month
            day = target_date.day
            
            # 1. 获取从1月到目标月份的累积记忆
            if self.fuzzy_memory_builder is None:
                # 如果没有初始化FuzzyMemoryBuilder，尝试创建一个
                self.fuzzy_memory_builder = FuzzyMemoryBuilder.get_instance(self.events, self.persona,self.file_path)
            
            # 加载已保存的总结（如果有）
            self.fuzzy_memory_builder.load_summaries()
            
            # 获取累积记忆
            cumulative_memory = self.fuzzy_memory_builder.get_memory_up_to_month(date)
            
            # 2. 获取当月从1日到目标日期的事件并生成总结
            start_of_month = datetime(year, month, 1).strftime("%Y-%m-%d")
            end_of_month = datetime(year, month, day).strftime("%Y-%m-%d")
            
            # 提取当月到目标日期的事件
            events_this_month = []
            for d in range(1, day + 1):
                current_date = datetime(year, month, d).strftime("%Y-%m-%d")
                events_this_month.extend(self.filter_by_date(current_date))
            
            # 如果有当月事件，生成总结
            monthly_summary = ""
            if events_this_month:
                # 构建事件描述字符串
                events_desc = "\n".join([
                    f"- {event.get('name', '未命名事件')}: {event.get('description', '无描述')} ({event.get('date', [''])[0]})"
                    for event in events_this_month
                ])
                
                # 使用LLM生成当月总结
                prompt = f"""
                你是一位记忆专家，请基于以下个人画像和{year}年{month}月1日到{day}日的事件，仅聚焦于以下信息进行总结：
                
                1. 个人近期（特别是前一日和当日）主要做了什么
                2. 个人当前所在的位置等状态信息（如是否在居住地,目前在关注什么,是否受什么影响）
                3. 近期事件对当日生活的影响
                4. 当下的状态及受之前哪些事件的影响
                
                个人画像：{json.dumps(self.persona, ensure_ascii=False, indent=2)}
                
                {year}年{month}月1日到{day}日的事件：
                {events_desc}
                
                输出要求：
                - 第一人称
                - 极度精简，仅保留核心信息
                - 忽略无关细节，只关注上述重点
                - 直接呈现关键内容，无冗余描述
                """
                
                monthly_summary = llm_call(prompt, self.context)
            
            # 3. 合并累积记忆和当月总结
            if monthly_summary:
                combined_memory = f"{cumulative_memory}\n\n{year}年{month}月1日到{day}日的重要事件：\n{monthly_summary}"
            else:
                combined_memory = cumulative_memory
            
            return combined_memory
            
        except Exception as e:
            print(f"获取模糊长期记忆时出错：{e}")
            # 出错时返回空记忆
            return ""

    def map(self,pt):
        #获取真实poi数据和通行信息
        prompt = template_poi_real_location_assign.format(persona = self.persona,data = pt)
        res = llm_call_skip(prompt,self.context)
        print("poi分析-----------------------------------------------------------------------")
        print(res)
        res = self.remove_json_wrapper(res)
        data = json.loads(res)
        result, error_summary = self.maptools.process_instruction_route(data)
        instr = ""
        instr += self.maptools.extract_route_summary(result)
        print(instr)
        prompt = template_poi_search_optimize.format(persona=self.persona_withoutrl, data=pt ,first_round_instruction=res,api_feedback=instr)
        res = llm_call_skip(prompt, self.context)
        print("poi分析2-----------------------------------------------------------------------")
        print(res)
        res = self.remove_json_wrapper(res)
        data = json.loads(res)
        resultx, error_summary = self.maptools.process_instruction_route(data)
        instr = self.maptools.extract_poi_route_simplified(resultx)
        print(instr)
        # with open(self.txt_file_path, "a", encoding="utf-8") as file:  # 记录，防止丢失
        #         file.write("-----------------------poi\n"+instr + "\n")  # 每个字符串后加换行符，实现分行存储
        return instr


    def remove_json_wrapper(self, input_str: str) -> str:
        """
        移除JSON字符串的前后包装（如```json ```标签、非法转义字符等）
        
        参数:
            input_str: 输入字符串
        
        返回:
            str: 清理后的字符串
        """
        # 步骤1：去除开头的```json（含空格/换行）和结尾的```（含空格）
        pattern = r'^\s*```json\s*\n?|\s*```\s*$'
        result = re.sub(pattern, '', input_str, flags=re.MULTILINE)

        # 步骤2：清理 JSON 非法控制字符（核心解决报错的步骤）
        # 保留：JSON 允许的控制字符（\n换行、\r回车、\t制表符、\b退格、\f换页）+ 可见ASCII字符（0x20-0x7E）+ 中文/全角字符（0x4E00-0x9FFF等）
        # 移除：零宽度空格、特殊控制符、不可见字符等
        # 正则说明：
        # [^\x20-\x7E]：排除可见ASCII字符
        # [^\n\r\t\b\f]：排除JSON允许的控制字符
        # [^\u4E00-\u9FFF\u3000-\u303F\uFF00-\uFFEF]：排除中文、全角符号（避免误删中文内容）
        valid_pattern = r'[^\x20-\x7E\n\r\t\b\f\u4E00-\u9FFF\u3000-\u303F\uFF00-\uFFEF\u2000-\u206F\u2E80-\u2EFF]'
        result = re.sub(valid_pattern, '', result)

        # 步骤3：规范空格和换行（进一步避免解析错误）
        result = result.strip()  # 去除首尾多余空格/换行
        result = result.replace('\u3000', ' ')  # 全角空格转半角空格（JSON不支持全角空格作为分隔符）
        result = re.sub(r'\r\n?', '\n', result)  # 统一换行符为 \n（兼容Windows/Mac格式）
        result = re.sub(r'\n+', '\n', result)  # 多个连续换行合并为一个（可选，优化可读性）

        return result

    def event_refine(self, date):
        """
        调整上层事件的兼容方法，调用独立的EventRefiner类
        
        参数:
            date: 目标日期（格式：YYYY-MM-DD）
        
        返回:
            bool: 执行是否成功
        """
        from event.event_refiner import EventRefiner
        refiner = EventRefiner(context=self.context)
        self.events = refiner.event_refine(self.events, date, self.context)
        self.update_bottom_level_events()
        return True



    def daily_event_gen1(self, date):
        """
        生成单日事件的核心方法
        
        参数:
            date: 目标日期（格式：YYYY-MM-DD）
        
        返回:
            bool: 执行是否成功的标志
        """
        try:
            self._log_event(f"\n=== 开始生成 {date} 的事件 ===")
            # 1. 生成主观思考
            plan = self.get_plan(date)
            subjective_thought = self._generate_subjective_thought(plan, date)
            
            # 2. 生成客观事件
            plan2 = self.get_plan2(date)
            objective_events = self._generate_objective_events(plan2,date,subjective_thought)
            # 3. 获取POI数据并调整轨迹
            poi_data = self.map(objective_events)
            # 从plan2中获取当日事件参考数据
            daily_event_reference = plan2["今日事件"] if plan2 and "今日事件" in plan2 else ""
            adjusted_events = self._adjust_event_trajectory(poi_data, objective_events, daily_event_reference,plan2['前一天事件'])
            
            # 4. 生成反思和更新想法
            reflection = self._generate_reflection(adjusted_events, plan, date)
            self.thought = reflection["thought"]
            
            # 5. 更新长期记忆
            self._update_long_term_memory(plan, reflection, date)
            
            # 6. 更新短期记忆并保存数据
            self.update_short_memory(reflection, date)
            
            # 7. 保存每日中间输出到实例变量
            self.daily_intermediate_outputs[date] = {
                "plan": plan,
                "subjective_thought": subjective_thought,
                "plan2": plan2,
                "objective_events": objective_events,
                "poi_data": poi_data,
                "adjusted_events": adjusted_events,
                "reflection": reflection
            }
            
            # 8. 保存当前状态
            self.save_to_json()
            self.save_intermediate_outputs()
            #self._save_events_to_file()
            
            self._log_event(f"\n=== {date} 的事件生成完成 ===")
            return True
        except Exception as e:
            self._log_event(f"\n=== {date} 的事件生成出现错误: {str(e)} ===")
            import traceback
            traceback.print_exc()
            return False
    
    def save_intermediate_outputs(self):
        """
        保存所有每日中间输出到JSON文件
        """
        # 获取当前日期和线程ID
        current_date = datetime.now().strftime("%Y-%m-%d")
        thread_id = threading.get_ident()
        
        # 创建日期文件夹和intermediate_output子文件夹
        date_folder = os.path.join(self.file_path, current_date)
        intermediate_folder = os.path.join(date_folder, "intermediate_output")
        if not os.path.exists(intermediate_folder):
            os.makedirs(intermediate_folder)
        
        # 创建固定文件名，包含线程ID
        filename = f"intermediate_outputs_thread_{thread_id}.json"
        file_path = os.path.join(intermediate_folder, filename)
        
        # 保存到同一个文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.daily_intermediate_outputs, f, ensure_ascii=False, indent=2)
        print(f"\n=== 中间输出已保存到 {file_path} ===")
        return filename
    
    def process_all_events_extraction(self):
        """
        处理所有保存的中间输出，提取事件
        """
        try:
            self._log_event(f"\n=== 开始批量提取事件 ===")
            all_extracted_events = []
            
            for date, outputs in self.daily_intermediate_outputs.items():
                self._log_event(f"  开始提取 {date} 的事件")
                adjusted_events = outputs["adjusted_events"]
                poi_data = outputs["poi_data"]
                
                # 提取事件
                extracted_events = self._extract_events(adjusted_events, poi_data, date)
                self.event_add(extracted_events)
                all_extracted_events.append(extracted_events)
                
            self._log_event(f"\n=== 批量提取事件完成，共提取 {len(all_extracted_events)} 天的事件 ===")
            return all_extracted_events
        except Exception as e:
            self._log_event(f"\n=== 批量提取事件出现错误: {str(e)} ===")
            import traceback
            traceback.print_exc()
            return []
    
    def _log_event(self, message):
        """
        记录事件日志到控制台
        
        参数:
            message: 要记录的消息
        """
        print(message)
    
    def _save_log(self, date, log_type, content):
        """
        保存日志内容到文件
        
        参数:
            date: 日期字符串
            log_type: 日志类型
            content: 日志内容
        """
        # 创建日期文件夹和log子文件夹
        date_folder = os.path.join(self.file_path, 'logs')
        log_folder = os.path.join(date_folder, "log")
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)
        
        # 创建日志文件路径
        log_file_path = os.path.join(log_folder, f'log_{self.instance_id}.txt')
        
        with open(log_file_path, "a", encoding="utf-8") as file:
            if log_type == "t1":
                file.write(f"date:{date}\n-----------------------{log_type}\n{content}\n")
            else:
                file.write(f"-----------------------{log_type}\n{content}\n")
    
    def _generate_subjective_thought(self, plan, date):
        """
        生成主观思考（计划如何执行、想安排什么活动）
        
        参数:
            plan: 今日规划
            date: 目标日期
        
        返回:
            str: 主观思考内容
        """
        prompt = template_daily_event_subjective_plan.format(
            cognition=self.cognition,
            memory='这是长期记忆:'+self.long_memory + '这是短期记忆:'+self.short_memory,
            thought=self.thought,
            plan=plan['今日事件'],
            date=self.get_date_string(date),
            persona=self.persona
        )
        thought = self.llm_call_s(prompt, 0)
        self._log_event("主观思考（计划如何执行、想安排什么活动）-----------------------------------------------------------------------")
        self._log_event(thought)
        self._save_log(date, "t1", thought)
        return thought
    
    def _generate_objective_events(self, plan,date,event):
        """
        生成客观事件
        
        参数:
            plan: 未来规划
        
        返回:
            str: 客观事件内容
        """
        prompt = template_daily_event_objective_optimize.format(
            event=event,
            plan=plan,
            memory=self.long_memory + self.short_memory,
            date=self.get_date_string(date),
            persona=self.cognition
        )
        events = self.llm_call_s(prompt, 0)
        self._log_event("客观生成-----------------------------------------------------------------------")
        self._log_event(events)
        self._save_log("", "t2", events)
        return events
    
    def _adjust_event_trajectory(self, poi_data, event, daily_event_reference="",history=""):
        """
        调整事件轨迹
        
        参数:
            poi_data: POI数据
            event: 事件数据
            daily_event_reference: 当日事件参考
        
        返回:
            str: 调整后的事件内容
        """
        #print(event)
        prompt = template_event_traffic_adjust.format(poi=poi_data, event=event, daily_event_reference=daily_event_reference,history=history,persona=self.cognition)
        #print(prompt)
        adjusted_events = self.llm_call_s(prompt, 0)
        self._log_event("轨迹调整-----------------------------------------------------------------------")
        self._log_event(adjusted_events)
        self._save_log("", "t3", adjusted_events)
        return adjusted_events
    
    def _extract_events(self, events, poi_data, date):
        """
        提取事件
        
        参数:
            events: 事件内容
            poi_data: POI数据
            date: 目标日期
        
        返回:
            dict: 提取的事件数据
        """
        prompt = template_event_format_sequence.format(
            content=events,
            poi=poi_data + "家庭住址：上海市浦东新区张杨路123号，工作地点：上海市浦东新区世纪大道88号",
            date=self.get_date_string(date)
        )
        extracted_events = self.llm_call_s(prompt, 0)
        self._log_event("提取-----------------------------------------------------------------------")
        self._log_event(extracted_events)
        
        cleaned_events = self.remove_json_wrapper(extracted_events)
        self._log_event(cleaned_events)
        
        return json.loads(cleaned_events)
    
    def _generate_reflection(self, events, plan, date):
        """
        生成反思（真实情绪，自我洞察，事件记忆，总结反思，未来期望）
        
        参数:
            events: 事件内容
            plan: 今日规划
            date: 目标日期
        
        返回:
            dict: 反思数据
        """
        prompt = template_daily_reflection.format(
            cognition=self.cognition,
            memory=self.long_memory + self.short_memory,
            content=events,
            plan=plan,
            date=self.get_date_string(date)
        )
        #print(prompt)
        reflection = self.llm_call_s(prompt, 0)
        self._log_event("反思（真实情绪，自我洞察，事件记忆，总结反思，未来期望）-----------------------------------------------------------------------")
        
        cleaned_reflection = self.remove_json_wrapper(reflection)
        self._log_event(cleaned_reflection)
        self._save_log("", "t4", cleaned_reflection)
        return json.loads(cleaned_reflection)
    
    def _update_long_term_memory(self, plan, reflection, date):
        """
        更新长期记忆
        
        参数:
            plan: 今日规划
            reflection: 反思数据
            date: 目标日期
        """
        # 获取历史数据
        history_data = [reflection]
        for i in range(1, 3):
            history_data += self.mem_module.search_by_date(self.get_next_n_day(date, -i))
        
        prompt = template_update_long_term_memory.format(
            cognition=self.cognition,
            memory=self.long_memory,
            plan=plan,
            history=history_data,
            now=json.dumps(reflection),
            thought=self.thought,
            date=self.get_date_string(date)
        )
        #print( prompt)
        updated_memory = self.llm_call_s(prompt)
        cleaned_memory = self.remove_json_wrapper(updated_memory)
        
        self._log_event("更新（客观事实与固定偏好，IMO记忆的关键事件，重复多次进行的事件，对过去总结）-----------------------------------------------------------------------")
        self._log_event(cleaned_memory)
        
        memory_data = json.loads(cleaned_memory)
        self.long_memory = memory_data['long_term_memory']
        self._save_log("", "t5", cleaned_memory)
    
    def _save_events_to_file(self):
        """
        保存事件到文件
        """
        with open(self.file_path+"event_update.json", "w", encoding="utf-8") as f:
            json.dump(self.events, f, ensure_ascii=False, indent=2)
            



def iterate_dates(start_date: str, end_date: str) -> List[str]:
    """
    遍历从起始日期到结束日期（包含两端）的所有日期，返回日期字符串列表

    参数:
        start_date: 起始日期，格式为 'YYYY-MM-DD'（如 '2025-01-01'）
        end_date: 结束日期，格式为 'YYYY-MM-DD'（如 '2025-01-05'）

    返回:
        List[str]: 按时间顺序排列的日期列表，包含 start_date 和 end_date 之间的所有日期

    异常:
        ValueError: 日期格式错误或起始日期晚于结束日期时抛出
    """
    # 解析日期为datetime对象
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"日期格式错误，需为 'YYYY-MM-DD'，错误：{str(e)}")

    # 校验日期逻辑
    if start > end:
        raise ValueError(f"起始日期 {start_date} 不能晚于结束日期 {end_date}")

    # 遍历区间内所有日期
    current_date = start
    date_list = []
    while current_date <= end:
        # 转为 'YYYY-MM-DD' 格式字符串并添加到列表
        date_list.append(current_date.strftime("%Y-%m-%d"))
        # 移动到下一天
        current_date += timedelta(days=1)

    return date_list

class MindController:
    """
    Mind类的并行化控制器，用于管理多个Mind实例的并行执行
    """
        
    def __init__(self, event_file='event.json', persona_file='persona.json', data_dir='data/2025-12-07', daily_state_file='daily_state.json', instance_id=0):
        """
        初始化MindController实例
        
        参数:
            event_file: 事件数据文件路径
            persona_file: 人物画像数据文件路径
            data_dir: 数据存储目录
            daily_state_file: 每日状态数据文件路径
            instance_id: 人物实例ID，用于确保每个人只有一个memory文件
        """
        self.data_dir = data_dir
        self.instance_id = instance_id
        # 从文件加载初始数据
        from utils.IO import read_json_file
        try:
            # 加载事件数据
            self.events = read_json_file(event_file)
            # 加载人物画像数据
            self.persona = read_json_file(persona_file)
            
            # 加载每日状态数据
            self.daily_state = None
            try:
                self.daily_state = read_json_file(daily_state_file)
                print(f"成功加载每日状态数据: {daily_state_file}")
            except FileNotFoundError:
                print(f"未找到每日状态数据文件: {daily_state_file}")
            except Exception as e:
                print(f"加载每日状态数据失败: {str(e)}")
                self.daily_state = None
            
            print(f"成功加载初始事件和人物画像数据，数据存储目录: {data_dir}")
        except Exception as e:
            print(f"加载初始数据失败: {str(e)}")
            raise
    
    def create_mind_instance(self):
        """
        创建Mind实例
        
        返回:
            Mind: 创建的Mind实例
        """
        # 使用人物的instance_id作为标识，确保每个人只有一个memory文件
        # 不再使用thread_id，避免每个线程创建一个独立的memory文件
        return Mind(file_path=self.data_dir, instance_id=self.instance_id, persona=self.persona, event=self.events, daily_state=self.daily_state)
    
    def run_daily_event_with_threading(self, start_date, end_date, max_workers=5, interval_days=2):
        """
        使用分片并行模式生成指定日期范围内的事件
        
        参数:
            start_date: 起始日期，格式如 "2025-01-01"
            end_date: 结束日期，格式如 "2025-01-05"
            max_workers: 最大并行区间数（默认5）
            interval_days: 每个串行区间的天数（默认2）
        
        返回:
            List: 执行结果列表
        """
        print(f"=== 开始分片并行生成事件，日期范围：{start_date} 到 {end_date}，最大并行区间数：{max_workers}，区间大小：{interval_days}天 ===")
        
        # 生成日期列表
        date_list = iterate_dates(start_date, end_date)
        
        # 将日期列表划分为指定天数的区间
        intervals = []
        for i in range(0, len(date_list), interval_days):
            interval = date_list[i:i+interval_days]
            intervals.append(interval)
        
        # 结果列表
        results = []

        # 定义区间处理函数
        def process_interval(interval_dates):
            """处理单个日期区间，区间内串行执行"""
            # 为每个区间创建独立的Mind实例，避免共享状态
            mind_instance = self.create_mind_instance()
            # 正确初始化Mind实例，传入事件数据、人物画像和起始日期
            mind_instance.initialize(self.events, self.persona, interval_dates[0], self.daily_state)
            interval_results = []
            
            print(f"  开始处理区间：{interval_dates[0]} 到 {interval_dates[-1]}")
            
            # 区间内串行执行
            for date in interval_dates:
                try:
                    success = mind_instance.daily_event_gen1(date)
                    interval_results.append((date, True, None, None))
                except Exception as e:
                    error_type = type(e).__name__
                    error_msg = str(e)
                    print(f"    处理日期 {date} 时出错 ({error_type}): {error_msg}")
                    interval_results.append((date, False, error_type, error_msg))
            
            print(f"  区间处理完成：{interval_dates[0]} 到 {interval_dates[-1]}")
            return interval_results
        
        # 使用线程池并行处理区间
        from concurrent.futures import ThreadPoolExecutor
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有区间任务
            future_to_interval = {executor.submit(process_interval, interval): interval for interval in intervals}
            
            # 收集结果
            for future in future_to_interval:
                try:
                    interval_results = future.result()
                    results.extend(interval_results)
                except Exception as e:
                    print(f"  处理区间时出错: {str(e)}")
        
        print(f"\n=== 所有日期的事件生成完成，共生成 {len(results)} 天的事件 ===")
        return results


# 使用示例
def test_event_count_by_date_range(start_date, end_date, persona_path, event_path):
    """
    统计指定日期范围内的事件数目，去除eventid不含-的事件
    
    参数:
        start_date: 起始日期，格式为"YYYY-MM-DD"
        end_date: 结束日期，格式为"YYYY-MM-DD"
        persona_path: persona数据文件路径
        event_path: event数据文件路径
    
    返回:
        int: 指定日期范围内的事件总数
    """
    import json
    from datetime import datetime, timedelta
    
    # 加载persona数据
    with open(persona_path, 'r', encoding='utf-8') as f:
        persona = json.load(f)
    
    # 加载event数据
    with open(event_path, 'r', encoding='utf-8') as f:
        event = json.load(f)
    
    # 初始化Mind实例
    mind = Mind("output", persona=persona, event=event)
    mind.events =  event
    mind.persona = persona
    mind.update_bottom_level_events()
    
    # 统计指定日期范围内的事件数目
    total_count = 0
    current_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    while current_date <= end_date_dt:
        date_str = current_date.strftime("%Y-%m-%d")
        # 调用filter_by_date方法获取当天的事件
        events_on_date = mind.filter_by_date(date_str)
        # 筛选出eventid包含-的事件
        filtered_events = [event for event in events_on_date if isinstance(event.get('event_id'), str) and '-' in event['event_id']]
        count_on_date = len(filtered_events)
        print(f"{date_str}: {count_on_date}个事件")
        total_count += count_on_date
        
        # 移动到下一天
        current_date += timedelta(days=1)
    
    print(f"\n{start_date}至{end_date}期间的事件总数: {total_count}个")
    return total_count

if __name__ == "__main__":
    # 测试统计指定日期范围内的事件数目
    print("测试统计指定日期范围内的事件数目")
    print("=" * 50)
    
    # 设置文件路径（根据用户要求：persona数据在output里，event数据在event_decompose_1）
    persona_path = "output/persona.json"
    event_path = "data_copy/data2/event_update.json"
    
    # 设置日期范围
    start_date = "2025-10-01"
    end_date = "2025-10-15"
    
    # 调用测试方法
    test_event_count_by_date_range(start_date, end_date, persona_path, event_path)