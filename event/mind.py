# -*- coding: utf-8 -*-
import ast
import json
import re
import holidays
from pyarrow import string
from utils.IO import *
from datetime import datetime, timedelta
from utils.llm_call import *
from utils.maptool import *
from event.templates import *
from event.memory import *
from typing import List, Dict, Optional
class Mind:
    def __init__(self,file_path):
        self.calendar = {}  # 存储日程数据，格式如{"2025-01-01":["event1","event2"],...}
        self.events = []
        self.persona = ""
        self.persona_withoutrl = ""
        self.mem_moudle = PersonalMemoryManager()
        self.context = ""
        self.cognition = ""#主要存储对自我的认知，包括画像信息。
        self.long_memory = ""#主要存储对近期事件感知，印象深刻印象感知以及长期主要事件感知，近期想法，并推理思考（动机），当深化到一定程度可以加入自我感知。
        self.short_memory = ""#主要存储近期所有详细事件和相关检索事件。
        self.reflection = ""#主要存储对现在和未来的思考
        self.thought = ""#记录个人的感受，想法。包括情绪，想法，需求。以及思考过程中的打算。
        self.bottom_events : Optional[List[Dict]] = None
        self.maptools = MapMaintenanceTool("e8f87eef67cfe6f83e68e7a65b9b848b")
        self.env = ""
        self.file_path = file_path
        self.txt_file_path = file_path+'log.txt'

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
        with open("record.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_bottom_level_events(self) -> List[Dict]:
        """
        【内部辅助方法】递归提取所有最底层事件（subevent为空），结果缓存到self.bottom_events
        :return: 最底层事件列表
        """
        if self.bottom_events is not None:
            print("已计算过，直接返回缓存")
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
                重新从event抽取底层事件
                :return: 最底层事件列表
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
        【静态方法】判断事件日期是否包含目标日期（支持单个日期/日期范围）
        :param target_date_str: 目标日期（格式：YYYY-MM-DD）
        :param event_date_str: 事件日期（格式：YYYY-MM-DD 或 YYYY-MM-DD至YYYY-MM-DD）
        :return: 匹配结果（True/False）
        """
        # 验证目标日期格式
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
        【核心接口方法】筛选指定日期的最底层事件
        :param target_date: 目标日期（格式：YYYY-MM-DD）
        :return: 匹配的事件列表
        """
        # 步骤1：获取所有底层事件（自动缓存）
        bottom_events = self._get_bottom_level_events()

        def extract_start_date(date_str: str) -> str:
            """
            从时间字符串中提取起始日期，兼容两种格式：
            1. 时间区间（如"2025-01-01 07:30:00至2025-01-01 08:45:00"）
            2. 单个时间（如"2025-01-01 07:30:00"或"2025-01-01"）

            参数:
                date_str: 输入的时间字符串（支持含"至"的区间和不含"至"的单个时间）

            返回:
                str: 提取的起始日期，格式固定为"YYYY-MM-DD"

            异常:
                ValueError: 输入字符串不符合支持的时间格式时抛出
            """
            # 步骤1：分割字符串，提取起始时间部分（含"至"则取左边，不含则取全部）
            if "至" in date_str:
                # 分割"至"，取左侧的起始时间（如"2025-01-01 07:30:00"）
                start_time_part = date_str.split("至")[0].strip()
            else:
                # 无"至"，整个字符串即为起始时间（如"2025-01-01 07:30:00"或"2025-01-01"）
                start_time_part = date_str.strip()

            # 步骤2：解析起始时间部分，提取纯日期（支持两种子格式）
            supported_formats = [
                "%Y-%m-%d %H:%M:%S",  # 带秒级时间的格式（如"2025-01-01 07:30:00"）
                "%Y-%m-%d",  # 纯日期格式（如"2025-01-01"）
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H"
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
    def load_from_json(self,event,persona,record=1):
            self.persona = copy.deepcopy(persona)
            self.events = event
            #生成context和自我认知
            self.long_memory = ""
            self.short_memory = ""
            if record==1:
                d = read_json_file('record.json')
                self.long_memory = d['long_memory']
                self.short_memory = d['short_memory']
                self.thought = d['thought']
                self.env = d['env']
                self.cognition = d['cognition']
                self.context = d['context']
            else:
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
            del persona["relation"]
            self.persona_withoutrl = persona

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
            从时间字符串中提取起始日期，兼容两种格式：
            1. 时间区间（如"2025-01-01 07:30:00至2025-01-01 08:45:00"）
            2. 单个时间（如"2025-01-01 07:30:00"或"2025-01-01"）

            参数:
                date_str: 输入的时间字符串（支持含"至"的区间和不含"至"的单个时间）

            返回:
                str: 提取的起始日期，格式固定为"YYYY-MM-DD"

            异常:
                ValueError: 输入字符串不符合支持的时间格式时抛出
            """
            # 步骤1：分割字符串，提取起始时间部分（含"至"则取左边，不含则取全部）
            if "至" in date_str:
                # 分割"至"，取左侧的起始时间（如"2025-01-01 07:30:00"）
                start_time_part = date_str.split("至")[0].strip()
            else:
                # 无"至"，整个字符串即为起始时间（如"2025-01-01 07:30:00"或"2025-01-01"）
                start_time_part = date_str.strip()

            # 步骤2：解析起始时间部分，提取纯日期（支持两种子格式）
            supported_formats = [
                "%Y-%m-%d %H:%M:%S",  # 带秒级时间的格式（如"2025-01-01 07:30:00"）
                "%Y-%m-%d"  # 纯日期格式（如"2025-01-01"）
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
        【新增方法】递归遍历所有层级事件，提取匹配目标ID的事件
        :param target_event_id: 目标事件ID（如"1-1"、"1-1-3"）
        :return: 匹配ID的事件列表（理论上ID唯一时返回单个元素，兼容重复ID）
        """
        matched_events = []

        def recursive_search(events: List[Dict]):
            """内部递归函数：遍历事件及子事件，匹配ID"""
            for event in events:
                # 1. 检查当前事件的ID是否匹配
                current_event_id = event.get("event_id")
                if current_event_id == target_event_id:
                    matched_events.append(event)
                # 2. 递归遍历当前事件的子事件（即使当前ID匹配，也继续找子事件中的潜在匹配）
                subevents = event.get("subevent", [])
                if subevents:
                    recursive_search(subevents)

        # 从原始数据的根节点开始递归搜索
        recursive_search(self.events)
        return matched_events
    def llm_call_sr(self,prompt,record=0):
        """调用大模型的函数"""
        res = llm_call_reason(prompt,self.context,record=record)
        return res

    def llm_call_s(self,prompt,record=0):
        """调用大模型的函数"""
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
            data1 = {"事件序列":[],"事件背景":[]}
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
                data1 = {"事件序列": [], "事件背景": []}
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
        print("[【【【【【【【【【【【【【【【【【【更新事件】】】】】】】】】】】】】】】】】】】]")
        return

    def event_add(self,data):
        """
            新增上层事件，并更新底层事件

        """
        for i in data:
            self.events = self.add_top_event(self.events,i)
        self.update_bottom_level_events()
        return
    def update_short_memory(self,dailyevent,date):
        #记忆库插入今天事件
        self.mem_moudle.add_memory(dailyevent)
        #检索明天相关事件
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

        #最终增加前五天事件、上周同日事件、上月同日事件、检索最相似3日事件
        date_set = set()
        mem = ""
        for i in get_target_dates(date):
            res = self.mem_moudle.search_by_date(start_time=i)
            for j in res:
                mem += j['events']
                date_set.add(j['date'])
        for i in get_cycle_dates_array(get_next_day(date)):
            res = self.mem_moudle.search_by_date(start_time=i)
            for j in res:
                mem += j['events']
                date_set.add(j['date'])
        arr = self.filter_by_date(get_next_day(date))
        res = ""
        for item in arr:
            name = item['name']
            res += name
        res = self.mem_moudle.search_by_topic_embedding(res,2)
        for i in res:
            if i['date'] in date_set:
                continue
            mem += i['events']
        self.short_memory = mem
        return

    def map(self,pt):
        #获取真实poi数据和通行信息
        prompt = template_get_poi3.format(persona = self.persona,data = pt)
        res = llm_call_skip(prompt,self.context)
        print("poi分析-----------------------------------------------------------------------")
        print(res)
        data = json.loads(res)
        result, error_summary = self.maptools.process_instruction_route(data)
        instr = ""
        instr += self.maptools.extract_route_summary(result)
        print(instr)
        prompt = template_get_poi2.format(persona=self.persona_withoutrl, data=pt ,first_round_instruction=res,api_feedback=instr)
        res = llm_call_skip(prompt, self.context)
        print("poi分析2-----------------------------------------------------------------------")
        print(res)
        data = json.loads(res)
        resultx, error_summary = self.maptools.process_instruction_route(data)
        instr = self.maptools.extract_poi_route_simplified(resultx)
        print(instr)
        # with open(self.txt_file_path, "a", encoding="utf-8") as file:  # 记录，防止丢失
        #         file.write("-----------------------poi\n"+instr + "\n")  # 每个字符串后加换行符，实现分行存储
        return instr



        #
        # pois, durations = self.maptools.process_route(
        #     keywords=data['poi'],
        #     cities=data['city'],
        #     transports=data['transport']
        # )
        # cities = data['city']
        # transports = data['transport']
        # res = ""
        # res+="POI列表 检索方式1："
        # for i, (poi, city) in enumerate(zip(pois, cities)):
        #     res+=f"{i + 1}. {poi['name']}（{city}）- 类型：{poi['type']} - 详细地址：{poi['address']}"
        # res+="\n各POI间通行时长（分钟） 检索方式1："
        # for i, (dur, transport,poi) in enumerate(zip(durations, transports,pois)):
        #     res+=f"路段 {i + 1} {poi['pname']+poi['address']+poi['name']}至{pois[i+1]['pname']+pois[i+1]['address']+pois[i+1]['name']}（使用{transport}方式通行）：{dur // 60 if dur else '未知'}"
        # res += '\n---------------------------------------------------\n'
        # pois, durations = self.maptools.process_route_bycode(
        #     keywords=data['poi'],
        #     cities=data['city'],
        #     transports=data['transport']
        # )
        # print(pois)
        # print(durations)
        # res += "\nPOI列表 检索方式2："
        # for i, (poi, city) in enumerate(zip(pois, cities)):
        #
        #     res += f"{i + 1}. {poi['formatted_address']}（{city}）;"
        # res += "\n各POI间通行时长（分钟） 检索方式2："
        # for i, (dur, transport, poi) in enumerate(zip(durations, transports, pois)):
        #     res += f"路段 {i + 1} {poi['formatted_address']}至{pois[i + 1]['formatted_address']}（使用{transport}方式通行）：{dur // 60 if dur else '未知'}"
        # res += "\n以上是通过工具调用获得的与今日地点可能的相关真实地点，他们可能是同类型地点或者位置相近地点，由于搜索工具的问题，可能搜出来的不是同一个地点，但位置相近，请你参考他们替换目前事件中的地点使其真实并调整通行时间。"
        # print(res)
        # prompt = template_get_poi3.format(data = pt,poi = res)
        # res = llm_call_skip(prompt)
        # print("poi分析-----------------------------------------------------------------------")
        # print(res)
        # data = json.loads(res)
        # pois, durations = self.maptools.process_route_bycode(
        #     keywords=data['poi'],
        #     cities=data['city'],
        #     transports=data['transport']
        # )
        # print(pois)
        # print(durations)
        # res = ""
        # res += "\nPOI列表："
        # for i, (poi, city) in enumerate(zip(pois, cities)):
        #     res += f"{i + 1}. {poi['formatted_address']}（{city}）;"
        # res += "\n各POI间通行时长（分钟）："
        # for i, (dur, transport, poi) in enumerate(zip(durations, transports, pois)):
        #     res += f"路段 {i + 1} {poi['formatted_address']}至{pois[i + 1]['formatted_address']}（使用{transport}方式通行）：{dur // 60 if dur else '未知'}"
        # print(res)
        # return res
        # with open(self.txt_file_path, "a", encoding="utf-8") as file:  # 记录，防止丢失
        #         file.write("-----------------------poi\n"+res + "\n")  # 每个字符串后加换行符，实现分行存储



    def remove_json_wrapper(self, s: str) -> str:
        """
        去除字符串前后可能存在的```json  ```标记（包含可能的空格），并清理 JSON 非法字符
        解决 JSONDecodeError: Invalid control character 问题

        参数:
            s: 输入字符串

        返回:
            处理后的字符串（可直接用于 json.loads 解析），若不存在标记则返回清理后的原字符串
        """
        # 步骤1：去除开头的```json（含空格/换行）和结尾的```（含空格）
        pattern = r'^\s*```json\s*\n?|\s*```\s*$'
        result = re.sub(pattern, '', s, flags=re.MULTILINE)

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

    def daily_event_gen(self,date):
        #基于认知、检索更新后的短期记忆、长期记忆，昨日想法，推理规划反思+信息明确+需求情感推理
        plan = self.get_plan(date)
        prompt = template_plan_2.format(cognition=self.cognition, memory=self.long_memory + self.short_memory,thought=self.thought,plan = plan['今日事件'],date = self.get_date_string(date) ,persona=self.persona_withoutrl)
        res = self.llm_call_s(prompt,1)
        print("思考-----------------------------------------------------------------------")
        print(res)
        tt = res
        poidata = self.map(res)
        prompt = template_plan_1.format(plan=plan,poi=poidata)
        res1 = self.llm_call_s(prompt,1)
        print("生成-----------------------------------------------------------------------")
        print(res1)
        #随机细节事件引入+反应
        prompt = template_plan_3.format(memory = self.short_memory)
        res2 = self.llm_call_s(prompt,1)
        print("丰富-----------------------------------------------------------------------")
        print(res2)
        #事件生成
        print("test-----------------------------------------------------------------------")
        print(plan['今日事件']["事件序列"])
        prompt = template_get_event_1.format(content = res2 ,plan=plan['今日事件']["事件序列"],thought = tt)
        res = self.llm_call_s(prompt,0)
        print("提取1-----------------------------------------------------------------------")
        print(res)
        res = self.remove_json_wrapper(res)
        data = json.loads(res)
        self.event_schedule(data,date)
        prompt = template_get_event_3.format(content=res2, plan=plan['今日事件']["事件序列"],poi = poidata+"家庭住址：上海市浦东新区张杨路123号，工作地点：上海市浦东新区世纪大道88号",date = self.get_date_string(date))
        res = self.llm_call_s(prompt,1)
        print("提取2-----------------------------------------------------------------------")
        print(res)
        res = self.remove_json_wrapper(res)
        data = json.loads(res)
        # 事件更新
        self.event_add(data)
        prompt = template_get_event_2.format(date=self.get_date_string(date),plan=plan['今日事件'])
        res = mind.llm_call_s(prompt)
        print("提取3-----------------------------------------------------------------------")
        print(res)
        res = self.remove_json_wrapper(res)
        data = json.loads(res)
        # 事件更新
        self.event_add(data)
        #记忆更新(检索系统)+短期记忆更新+想法生成
        prompt = template_reflection.format(cognition=self.cognition, memory=self.long_memory + self.short_memory,content = res2,plan = plan,date = self.get_date_string(date) )
        res = self.llm_call_s(prompt,1)
        print("反思-----------------------------------------------------------------------")
        print(res)
        res = self.remove_json_wrapper(res)
        data=json.loads(res)
        self.thought = data["thought"]
        m = json.loads(res)
        mm = [m]
        for i in range(1,8):
            mm+=self.mem_moudle.search_by_date(self.get_next_n_day(date,-i))
        #总结：基于最新一天的记忆和思考想法，更新认知，长期记忆
        prompt = template_update_cog.format(cognition=self.cognition,memory=self.long_memory,plan=plan,history=mm)
        res = self.llm_call_s(prompt)
        res = self.remove_json_wrapper(res)
        data = json.loads(res)
        self.long_memory = data['long_term_memory']
        print("更新-----------------------------------------------------------------------")
        print(res)
        self.update_short_memory(m,date)
        self.save_to_json()
        with open("event_data/life_event/event_update.json", "w", encoding="utf-8") as f:
            json.dump(self.events, f, ensure_ascii=False, indent=2)
        return
    def event_refine(self,date):
        #调整上层事件
        plan = self.get_plan2(date)
        #思考推迟/提前什么事件
        prompt = template_plan_4.format(plan0 = plan['今日事件']["事件序列"],plan1=plan['今日事件'],plan2=plan['未来一周背景'],plan3 = plan['前一天事件'],date = self.get_date_string(date))
        res = self.llm_call_s(prompt, 0)
        print("思考-----------------------------------------------------------------------")
        print(res)
        data = json.loads(res)
        def update_subevent(event_list, target_id, new_event):
            updated = False
            for i in range(len(event_list)):
                current_event = event_list[i]
                # 匹配当前事件ID
                if current_event["event_id"] == target_id:
                    for j in range(len(event_list[i]['date'])):
                        if self.is_date_match(event_list[i]['date'][j],date):
                            event_list[i]['date'][j]=new_event
                    updated = True
                    break
                # 递归检查子事件
                if current_event.get("subevent") and len(current_event["subevent"]) > 0:
                    updated = update_subevent(current_event["subevent"], target_id, new_event)
                    if updated:
                        break
            return updated
        data = data['event_update']
        #更新
        for i in data:
            update_subevent(self.events,i['event_id'],i['new_date'])
            self.update_bottom_level_events()
        return True

    def daily_event_gen1(self,date):
        # 基于认知、检索更新后的短期记忆、长期记忆，昨日想法，推理规划反思+信息明确+需求情感推理
        #获取今日规划
        plan = self.get_plan(date)
        prompt = template_plan_21.format(cognition=self.cognition, memory=self.long_memory + self.short_memory,
                                        thought=self.thought, plan=plan['今日事件'], date=self.get_date_string(date),
                                        persona=self.persona)
        res = self.llm_call_s(prompt, 1)
        print("主观思考（计划如何执行、想安排什么活动）-----------------------------------------------------------------------")
        print(res)
        with open(self.txt_file_path, "a", encoding="utf-8") as file:  # 记录，防止丢失
                file.write("date:"+date+"\n-----------------------t1\n"+res + "\n")  # 每个字符串后加换行符，实现分行存储
        #获取未来规划
        plan = self.get_plan2(date)
        prompt = template_plan_11.format(plan=plan)
        res1 = self.llm_call_s(prompt, 1)
        print("客观生成-----------------------------------------------------------------------")
        print(res1)
        with open(self.txt_file_path, "a", encoding="utf-8") as file:  # 记录，防止丢失
                file.write("-----------------------t2\n"+res1 + "\n")  # 每个字符串后加换行符，实现分行存储
        tt = res1
        #获取poi数据
        poidata = self.map(tt)
        prompt = template_plan_5.format(poi=poidata)
        res1 = self.llm_call_s(prompt, 0)
        print("轨迹调整-----------------------------------------------------------------------")
        print(res1)
        with open(self.txt_file_path, "a", encoding="utf-8") as file:  # 记录，防止丢失
                file.write("-----------------------t3\n"+res1 + "\n")  # 每个字符串后加换行符，实现分行存储
        # 随机细节事件引入+反应
        prompt = template_plan_31.format(memory=self.short_memory,life=res1,cognition=self.cognition,poi=poidata)
        res2 = self.llm_call_s(prompt, 0)
        print("丰富（细节事件+多场景+描述润色）-----------------------------------------------------------------------")
        print(res2)
        with open(self.txt_file_path, "a", encoding="utf-8") as file:  # 记录，防止丢失
                file.write("-----------------------t4\n"+res1 + "\n")  # 每个字符串后加换行符，实现分行存储
        prompt = template_get_event_31.format(content=res2,
                                             poi=poidata + "家庭住址：上海市浦东新区张杨路123号，工作地点：上海市浦东新区世纪大道88号",
                                             date=self.get_date_string(date))
        res = self.llm_call_s(prompt, 0)
        print("提取-----------------------------------------------------------------------")
        record = res
        res = self.remove_json_wrapper(res)
        print(res)
        data = json.loads(res)
        # 事件更新
        self.event_add(data)
        # 记忆更新(检索系统)+想法生成
        prompt = template_reflection.format(cognition=self.cognition, memory=self.long_memory + self.short_memory,
                                            content=res2, plan=plan, date=self.get_date_string(date))
        res = self.llm_call_s(prompt, 0)
        print("反思（真实情绪，自我洞察，事件记忆，总结反思，未来期望）-----------------------------------------------------------------------")
        res = self.remove_json_wrapper(res)
        print(res)
        data = json.loads(res)
        #想法更新
        self.thought = data["thought"]
        m = json.loads(res)
        mm = [m]
        for i in range(1, 3):
            mm += self.mem_moudle.search_by_date(self.get_next_n_day(date, -i))
        # 总结：基于最新一天的记忆和思考想法，更新长期记忆
        prompt = template_update_cog.format(cognition=self.cognition, memory=self.long_memory, plan=plan, history=mm,now=record,thought = self.thought,date=self.get_date_string(date))
        res = self.llm_call_s(prompt)
        res = self.remove_json_wrapper(res)
        print("更新（客观事实与固定偏好，印象深刻的关键事件，重复多次进行的事件，对过去总结）-----------------------------------------------------------------------")
        print(res)
        data = json.loads(res)
        #长期记忆更新
        self.long_memory = data['long_term_memory']
        with open(self.txt_file_path, "a", encoding="utf-8") as file:  # 记录，防止丢失
                file.write("-----------------------t2\n"+res + "\n")  # 每个字符串后加换行符，实现分行存储
        #短期记忆更新
        self.update_short_memory(m, date)
        self.save_to_json()
        with open(self.file_path+"event_update.json", "w", encoding="utf-8") as f:
            json.dump(self.events, f, ensure_ascii=False, indent=2)

        return True


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

if __name__ == "__main__":
    mind = Mind(file_path='')
    persona = '''
     {
            "name": "徐静",
            "birth": "1993-07-10",
            "age": 28,
            "nationality": "汉",
            "home_address": {
                "province": "上海市",
                "city": "上海市",
                "district": "浦东新区",
                "street_name": "张杨路",
                "street_number": "123号"
            },
            "birth_place": {
                "province": "上海市",
                "city": "上海市",
                "district": "浦东新区"
            },
            "gender": "女",
            "education": "普通高中",
            "job": "服装店销售主管",
            "occupation": "时尚服饰零售企业",
            "workplace": {
                "province": "上海市",
                "city": "上海市",
                "district": "浦东新区",
                "street_name": "世纪大道",
                "street_number": "88号"
            },
            "belief": "不信仰宗教",
            "salary": 100000.0,
            "body": {
                "height": 158,
                "weight": 62.5,
                "BMI": 25.04
            },
            "family": "未婚",
            "personality": {
                "mbti": "ESFJ"
            },
            "hobbies": [
                "逛街购物",
                "听音乐",
                "羽毛球",
                "收藏纪念币"
            ],
            "favorite_foods": [
                "上海小笼包",
                "抹茶拿铁",
                "草莓蛋糕"
            ],
            "memory_date": [
                "2012-06-15：第一份工作入职纪念日",
                "2020-08-20：晋升销售主管日"
            ],
            "healthy_desc": "个人整体健康状况良好，无慢性病史，不定期进行健康体检，每年就医几次主要是常规检查。保持每周三次的体育锻炼习惯，注重个人护理和作息规律。",
            "lifestyle_desc": "日常生活高度依赖互联网，尤其喜欢使用社交媒体和购物APP获取信息。休闲活动包括每周两到三次逛街购物、在家听流行音乐、以及参加瑜伽锻炼。每月与朋友聚餐或看电影一次，每年会有一到两次短途旅行探亲或度假，生活风格偏向现代都市休闲型。",
            "economic_desc": "家庭年收入约10万元，拥有1处房产和家用汽车，目前没有股票、基金等投资活动，消费习惯偏谨慎，注重基本生活保障。",
            "work_desc": "在家族经营的服装零售企业工作，每周工作48小时，担任销售主管职务，负责店面管理和客户服务工作，工作稳定且与家庭生活紧密结合。",
            "experience_desc": "徐静自出生起便生活在上海浦东新区，2012年高中毕业后加入家族经营的服装零售企业，从基层销售员做起，通过努力逐步晋升为销售主管，负责店面运营和团队管理。她的工作经历稳定，与家庭事业深度绑定，积累了丰富的客户服务经验。",
            "description": "徐静是一位28岁的上海本地女性，高中毕业后在家族服装零售企业工作，现任销售主管。作为ESFJ人格类型，性格热情负责。日常生活中，她喜欢逛街购物、听音乐和体育锻炼，收藏纪念币是她的独特爱好。健康状况良好。经济状况稳定，拥有房产和汽车，消费观念务实。工作与家庭生活紧密结合，未来计划开设自己的服装店并保持家庭旅行传统。",
            "relation": [
                [
                    {
                        "name": "徐明",
                        "relation": "父亲",
                        "social circle": "家庭圈",
                        "gender": "男",
                        "age": 58,
                        "birth_date": "1965-03-12",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区",
                            "street_name": "张杨路",
                            "street_number": "123号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "黄浦区"
                        },
                        "personality": "ISTJ",
                        "economic_level": "中产",
                        "occupation": "服装零售企业主",
                        "organization": "明芳服饰有限公司",
                        "nickname": "老爸",
                        "relation_description": "徐静的父亲，与妻子共同经营家族服装企业。年轻时从裁缝学徒做起，1990年创办服装店并逐步发展成连锁企业。现在虽已半退休，仍会每周到店里巡视指导。与女儿关系亲密，每周至少三次家庭聚餐，经常一起讨论店铺经营。支持女儿开设分店的计划，时常传授商业经验。"
                    },
                    {
                        "name": "李芳",
                        "relation": "母亲",
                        "social circle": "家庭圈",
                        "gender": "女",
                        "age": 56,
                        "birth_date": "1967-08-25",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区",
                            "street_name": "张杨路",
                            "street_number": "123号"
                        },
                        "birth_place": {
                            "province": "江苏省",
                            "city": "苏州市",
                            "district": "姑苏区"
                        },
                        "personality": "ISFJ",
                        "economic_level": "中产",
                        "occupation": "服装企业财务主管",
                        "organization": "明芳服饰有限公司",
                        "nickname": "妈妈",
                        "relation_description": "徐静的母亲，负责家族企业的财务管理工作。原籍苏州，年轻时来上海打工认识徐明后结婚。性格温柔细心，不仅管理公司账务，还包办全家饮食起居。每天都会为女儿准备午餐便当，周末常一起逛街选购新款服装。母女关系融洽，经常交流生活琐事和情感问题。"
                    },
                    {
                        "name": "徐强",
                        "relation": "哥哥",
                        "social circle": "家庭圈",
                        "gender": "男",
                        "age": 32,
                        "birth_date": "1991-11-03",
                        "home_address": {
                            "province": "浙江省",
                            "city": "杭州市",
                            "district": "西湖区",
                            "street_name": "文三路",
                            "street_number": "456号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区"
                        },
                        "personality": "ENTJ",
                        "economic_level": "中产",
                        "occupation": "电商运营总监",
                        "organization": "杭州某电商平台",
                        "nickname": "强哥",
                        "relation_description": "徐静的哥哥，大学毕业后选择在杭州发展电商事业。虽然不在家族企业工作，但经常为妹妹提供线上销售建议。每月会回上海探望父母，与妹妹见面聚餐。兄妹关系良好，通过微信保持日常联系，主要讨论工作发展和家庭事务。徐静计划开设分店时也会征求哥哥的意见。"
                    }
                ],
                [
                    {
                        "name": "王丽",
                        "relation": "闺蜜",
                        "social circle": "高中同学圈",
                        "gender": "女",
                        "age": 28,
                        "birth_date": "1993-03-15",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "徐汇区",
                            "street_name": "淮海中路",
                            "street_number": "456号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "徐汇区"
                        },
                        "personality": "ENFP",
                        "economic_level": "中产",
                        "occupation": "市场专员",
                        "organization": "上海某广告公司",
                        "nickname": "丽丽",
                        "relation_description": "王丽是徐静高中时期的同桌，两人从学生时代就建立了深厚的友谊。现在同在上海工作，每周会约一次逛街或下午茶，经常分享工作和生活琐事。她们保持着密切的微信联系，节假日会一起聚餐或看电影，偶尔还会约上其他高中同学聚会。"
                    },
                    {
                        "name": "张婷",
                        "relation": "闺蜜",
                        "social circle": "高中同学圈",
                        "gender": "女",
                        "age": 29,
                        "birth_date": "1992-11-22",
                        "home_address": {
                            "province": "浙江省",
                            "city": "杭州市",
                            "district": "西湖区",
                            "street_name": "文三路",
                            "street_number": "789号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "静安区"
                        },
                        "personality": "ISFJ",
                        "economic_level": "中产",
                        "occupation": "小学教师",
                        "organization": "杭州市某实验小学",
                        "nickname": "婷婷",
                        "relation_description": "张婷是徐静高中时期的好友，大学毕业后选择到杭州发展。虽然分隔两地，但她们每月都会视频通话两到三次，分享各自的生活近况。每年春节张婷回上海探亲时，她们必定会见面聚餐，平时通过微信保持密切联系，互相支持对方的事业发展。"
                    },
                    {
                        "name": "赵小美",
                        "relation": "高中同学",
                        "social circle": "高中同学圈",
                        "gender": "女",
                        "age": 28,
                        "birth_date": "1993-09-08",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "闵行区",
                            "street_name": "虹梅路",
                            "street_number": "321号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "闵行区"
                        },
                        "personality": "ISTJ",
                        "economic_level": "小康",
                        "occupation": "会计",
                        "organization": "上海某会计师事务所",
                        "nickname": "小美",
                        "relation_description": "赵小美是徐静高中同学，现在同在上海工作。她们保持着每月一次的聚会频率，通常是在周末一起吃饭或逛街。作为高中同学圈的核心成员，赵小美经常组织同学聚会，与徐静及其他同学保持着稳定的联系，彼此在工作中也会互相提供建议和支持。"
                    },
                    {
                        "name": "钱多多",
                        "relation": "高中同学",
                        "social circle": "高中同学圈",
                        "gender": "女",
                        "age": 28,
                        "birth_date": "1993-12-03",
                        "home_address": {
                            "province": "广东省",
                            "city": "深圳市",
                            "district": "南山区",
                            "street_name": "科技园路",
                            "street_number": "654号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "黄浦区"
                        },
                        "personality": "ENTP",
                        "economic_level": "中产",
                        "occupation": "互联网产品经理",
                        "organization": "深圳某科技公司",
                        "nickname": "多多",
                        "relation_description": "钱多多是徐静的高中同学，大学毕业后选择到深圳发展。她们主要通过微信保持联系，每季度会视频通话一次。钱多多每年回上海探亲时会与徐静见面，平时在同学群里活跃互动。虽然距离较远，但她们仍保持着深厚的同学情谊，经常分享职场经验和生活趣事。"
                    }
                ],
                [
                    {
                        "name": "陈丽",
                        "relation": "同事",
                        "social circle": "工作圈",
                        "gender": "女",
                        "age": 26,
                        "birth_date": "1997-03-15",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区",
                            "street_name": "金桥路",
                            "street_number": "456号"
                        },
                        "birth_place": {
                            "province": "江苏省",
                            "city": "南京市"
                        },
                        "personality": "ENFP",
                        "economic_level": "中等",
                        "occupation": "服装销售员",
                        "organization": "时尚服饰零售企业",
                        "nickname": "丽丽",
                        "relation_description": "陈丽是徐静在服装店的同事，两人相识于2019年工作期间。作为销售团队的核心成员，她们每天共同处理店面事务，配合默契。工作之余会一起在商场餐厅吃午餐，周末偶尔相约逛街淘货。两人居住在同一城区，保持每周5天的工作接触和每月1-2次的私人聚会。"
                    },
                    {
                        "name": "刘伟",
                        "relation": "同事",
                        "social circle": "工作圈",
                        "gender": "男",
                        "age": 30,
                        "birth_date": "1993-11-22",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "闵行区",
                            "street_name": "虹梅路",
                            "street_number": "789号"
                        },
                        "birth_place": {
                            "province": "浙江省",
                            "city": "杭州市"
                        },
                        "personality": "ISTJ",
                        "economic_level": "中等",
                        "occupation": "仓储管理员",
                        "organization": "时尚服饰零售企业",
                        "nickname": "伟哥",
                        "relation_description": "刘伟负责店铺的仓储管理工作，与徐静在工作中密切配合已有3年。他做事严谨认真，经常协助徐静处理货品调配和库存盘点。两人主要在工作场合交流，偶尔参加公司组织的团建活动。虽然私下交往不多，但工作关系稳定可靠，保持每天工作时间的常规互动。"
                    },
                    {
                        "name": "赵敏",
                        "relation": "同事",
                        "social circle": "工作圈",
                        "gender": "女",
                        "age": 29,
                        "birth_date": "1994-05-08",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "徐汇区",
                            "street_name": "淮海中路",
                            "street_number": "321号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市"
                        },
                        "personality": "ESFP",
                        "economic_level": "中等",
                        "occupation": "销售助理",
                        "organization": "时尚服饰零售企业",
                        "nickname": "敏敏",
                        "relation_description": "赵敏是徐静最亲密的同事之一，两人既是工作搭档也是朋友。她们经常一起讨论销售策略，下班后偶尔相约喝咖啡聊天。赵敏性格活泼开朗，与徐静在工作上形成良好互补。两人保持每周工作日的密切合作，每月会有2-3次私人聚会，关系融洽而稳定。"
                    },
                    {
                        "name": "孙老板",
                        "relation": "供应商",
                        "social circle": "工作圈",
                        "gender": "男",
                        "age": 45,
                        "birth_date": "1978-09-12",
                        "home_address": {
                            "province": "广东省",
                            "city": "广州市",
                            "district": "天河区",
                            "street_name": "体育西路",
                            "street_number": "668号"
                        },
                        "birth_place": {
                            "province": "广东省",
                            "city": "潮州市"
                        },
                        "personality": "ENTJ",
                        "economic_level": "富裕",
                        "occupation": "服装厂老板",
                        "organization": "广州时尚制衣厂",
                        "nickname": "孙总",
                        "relation_description": "孙老板是服装店的主要供应商，与徐静保持业务往来已有5年。他每季度会来上海考察市场，徐静负责接待和洽谈订单。两人主要通过电话和微信沟通业务，见面频率较低但合作稳定。孙老板注重产品质量和商业信誉，与徐静建立了相互信任的工作关系。"
                    },
                    {
                        "name": "周经理",
                        "relation": "商场经理",
                        "social circle": "工作圈",
                        "gender": "男",
                        "age": 38,
                        "birth_date": "1985-12-03",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "静安区",
                            "street_name": "南京西路",
                            "street_number": "1000号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市"
                        },
                        "personality": "ESTJ",
                        "economic_level": "中高",
                        "occupation": "商场运营经理",
                        "organization": "世纪商场管理公司",
                        "nickname": "周经理",
                        "relation_description": "周经理是店铺所在商场的运营负责人，与徐静在工作上有频繁的业务往来。他负责商场的日常管理和商户协调，徐静经常需要与他沟通店铺运营事宜。两人每月会有1-2次正式会议，平时通过商场内部系统保持联系。周经理处事专业严谨，与徐静保持着良好的工作关系。"
                    }
                ],
                [
                    {
                        "name": "孙秀英",
                        "relation": "邻居",
                        "social circle": "社区圈",
                        "gender": "女",
                        "age": 65,
                        "birth_date": "1959-03-22",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区",
                            "street_name": "张杨路",
                            "street_number": "121号"
                        },
                        "birth_place": {
                            "province": "江苏省",
                            "city": "南通市"
                        },
                        "personality": "ISFJ",
                        "economic_level": "中等",
                        "occupation": "退休教师",
                        "organization": "浦东新区实验小学（已退休）",
                        "nickname": "孙阿姨",
                        "relation_description": "孙阿姨是徐静家对门的老邻居，退休前在附近小学任教。两人因社区活动相识，孙阿姨经常关心徐静的工作生活，会分享自己做的家常菜。现在主要通过微信保持联系，每周会碰面两三次，一起在小区散步或喝茶聊天。孙阿姨把徐静当作自家晚辈般照顾，逢年过节会互相赠送小礼物。"
                    }
                ],
                [
                    {
                        "name": "周晓雯",
                        "relation": "瑜伽教练",
                        "social circle": "瑜伽圈",
                        "gender": "女",
                        "age": 32,
                        "birth_date": "1991-03-15",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "徐汇区",
                            "street_name": "淮海中路",
                            "street_number": "356号"
                        },
                        "birth_place": {
                            "province": "浙江省",
                            "city": "杭州市"
                        },
                        "personality": "ENFJ",
                        "economic_level": "中产",
                        "occupation": "瑜伽馆",
                        "organization": "静心瑜伽工作室",
                        "nickname": "周老师",
                        "relation_description": "周晓雯是徐静在静心瑜伽工作室的专职教练，拥有8年瑜伽教学经验。两人通过2019年的团体课程相识，现在保持每周三次的私教课联系。上课时周教练会针对徐静的身体状况设计个性化训练方案，课后偶尔会交流健康饮食心得。虽然周教练住在徐汇区，但工作室距离徐静工作地点仅15分钟车程，教学关系稳定持续。"
                    },
                    {
                        "name": "李娜",
                        "relation": "瑜伽伙伴",
                        "social circle": "瑜伽圈",
                        "gender": "女",
                        "age": 29,
                        "birth_date": "1994-09-22",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区",
                            "street_name": "陆家嘴环路",
                            "street_number": "188号"
                        },
                        "birth_place": {
                            "province": "江苏省",
                            "city": "苏州市"
                        },
                        "personality": "ISFP",
                        "economic_level": "中产",
                        "occupation": "银行职员",
                        "organization": "浦东发展银行",
                        "nickname": "娜娜",
                        "relation_description": "李娜是徐静在瑜伽课上认识的固定练习伙伴，同在周教练的早课班练习两年。作为银行柜员，李娜下班后常与徐静结伴练习瑜伽，周末偶尔一起逛商场喝下午茶。两人住在同一行政区，每月会约两三次课后聚餐，交流工作和生活近况。李娜性格内向但体贴，经常与徐静分享护肤心得，是瑜伽圈里最亲近的练习搭档。"
                    },
                    {
                        "name": "王芳",
                        "relation": "瑜伽伙伴",
                        "social circle": "瑜伽圈",
                        "gender": "女",
                        "age": 31,
                        "birth_date": "1992-12-05",
                        "home_address": {
                            "province": "江苏省",
                            "city": "南京市",
                            "district": "鼓楼区",
                            "street_name": "北京西路",
                            "street_number": "72号"
                        },
                        "birth_place": {
                            "province": "安徽省",
                            "city": "合肥市"
                        },
                        "personality": "ENTP",
                        "economic_level": "小康",
                        "occupation": "自由职业者",
                        "organization": "自媒体工作室",
                        "nickname": "芳芳",
                        "relation_description": "王芳原是上海工作的瑜伽同伴，2021年移居南京发展自媒体事业，但仍通过线上群组与徐静保持联系。两人在2018年瑜伽进修班相识，曾经常结伴参加周末瑜伽工作坊。现在主要通过微信群分享瑜伽视频和健康资讯，每年王芳回沪探亲时会与徐静、李娜小聚。虽然异地发展，但三人仍维持着瑜伽圈的友谊，经常互相关注彼此的生活动态。"
                    }
                ],
                [
                    {
                        "name": "张秀英",
                        "relation": "姨妈",
                        "social circle": "亲戚圈",
                        "gender": "女",
                        "age": 58,
                        "birth_date": "1965-03-22",
                        "home_address": {
                            "province": "江苏省",
                            "city": "南京市",
                            "district": "鼓楼区",
                            "street_name": "中山北路",
                            "street_number": "256号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "黄浦区"
                        },
                        "personality": "ISFJ",
                        "economic_level": "小康",
                        "occupation": "退休教师",
                        "organization": "南京市鼓楼区实验小学",
                        "nickname": "张阿姨",
                        "relation_description": "张秀英是徐静母亲的姐姐，退休前在南京担任小学教师。两人虽然分居上海和南京，但每月会通过视频通话联系两到三次，主要聊家常和健康话题。每年春节和国庆节徐静会去南京探望，一起逛夫子庙、品尝南京小吃。张秀英经常关心徐静的婚姻和工作情况，是徐静重要的长辈倾诉对象。"
                    },
                    {
                        "name": "刘建国",
                        "relation": "舅舅",
                        "social circle": "亲戚圈",
                        "gender": "男",
                        "age": 55,
                        "birth_date": "1968-09-15",
                        "home_address": {
                            "province": "浙江省",
                            "city": "杭州市",
                            "district": "西湖区",
                            "street_name": "文三路",
                            "street_number": "189号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "静安区"
                        },
                        "personality": "ESTP",
                        "economic_level": "富裕",
                        "occupation": "餐饮企业主",
                        "organization": "杭帮菜餐饮连锁集团",
                        "nickname": "刘叔叔",
                        "relation_description": "刘建国是徐静的舅舅，在杭州经营连锁餐饮企业。他性格开朗，经常给徐静提供创业建议。两人每季度通一次电话，主要讨论商业经营和市场趋势。每年徐静会专程到杭州品尝舅舅的新菜品，同时考察当地服装市场。刘建国曾资助徐静参加商业管理培训，是她在事业上的重要支持者。"
                    },
                    {
                        "name": "陈明",
                        "relation": "表弟",
                        "social circle": "亲戚圈",
                        "gender": "男",
                        "age": 25,
                        "birth_date": "1998-12-03",
                        "home_address": {
                            "province": "广东省",
                            "city": "深圳市",
                            "district": "南山区",
                            "street_name": "科技园路",
                            "street_number": "66号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区"
                        },
                        "personality": "ENTJ",
                        "economic_level": "中产",
                        "occupation": "互联网产品经理",
                        "organization": "深圳某科技公司",
                        "nickname": "小明",
                        "relation_description": "陈明是徐静姑姑的儿子，目前在深圳从事互联网行业。两人从小一起在上海长大，现在主要通过微信保持联系，每周会分享生活趣事和工作心得。陈明经常给徐静推荐新的购物APP和时尚资讯，徐静则向他请教数字化营销知识。每年春节家庭聚会时见面，会一起逛商场、讨论最新的科技产品。"
                    }
                ],
                [
                    {
                        "name": "吴明远",
                        "relation": "家庭医生",
                        "social circle": "医疗圈",
                        "gender": "男",
                        "age": 45,
                        "birth_date": "1978-03-22",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "徐汇区",
                            "street_name": "淮海中路",
                            "street_number": "568号"
                        },
                        "birth_place": {
                            "province": "江苏省",
                            "city": "南京市",
                            "district": "鼓楼区"
                        },
                        "personality": "ISTJ",
                        "economic_level": "中产",
                        "occupation": "全科医生",
                        "organization": "浦东新区社区卫生服务中心",
                        "nickname": "吴医生",
                        "relation_description": "吴医生是徐静的家庭医生，五年前通过社区健康管理项目相识。他每月为徐静提供一次健康咨询，主要通过微信进行线上沟通，偶尔在社区卫生服务中心面诊。吴医生性格严谨负责，擅长慢性病管理和健康指导，与徐静保持着专业而友好的医患关系。"
                    }
                ],
                [
                    {
                        "name": "郑明辉",
                        "relation": "健身教练",
                        "social circle": "健身圈",
                        "gender": "男",
                        "age": 32,
                        "birth_date": "1992-03-15",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "徐汇区",
                            "street_name": "漕溪北路",
                            "street_number": "258号"
                        },
                        "birth_place": {
                            "province": "江苏省",
                            "city": "南京市",
                            "district": "鼓楼区"
                        },
                        "personality": "ESTP",
                        "economic_level": "中产",
                        "occupation": "健身教练",
                        "organization": "力健健身俱乐部",
                        "nickname": "郑教练",
                        "relation_description": "郑明辉是徐静在力健健身俱乐部的私人教练，两人通过健身课程相识已有两年。他擅长制定个性化训练计划，每周指导徐静进行三次力量训练和有氧运动。平时主要通过微信沟通训练安排和饮食建议，每月会组织会员户外拓展活动。郑教练性格开朗务实，注重训练效果的同时也会关心会员的生活状态。"
                    }
                ],
                [
                    {
                        "name": "王明远",
                        "relation": "纪念币藏友",
                        "social circle": "收藏圈",
                        "gender": "男",
                        "age": 45,
                        "birth_date": "1978-03-15",
                        "home_address": {
                            "province": "北京市",
                            "city": "北京市",
                            "district": "朝阳区",
                            "street_name": "建国门外大街",
                            "street_number": "88号"
                        },
                        "birth_place": {
                            "province": "北京市",
                            "city": "北京市"
                        },
                        "personality": "ISTJ",
                        "economic_level": "中产",
                        "occupation": "金融投资顾问",
                        "organization": "北京金融投资有限公司",
                        "nickname": "老王",
                        "relation_description": "王明远是徐静在纪念币收藏展会上认识的藏友，两人因共同爱好结缘。他目前在北京市从事金融投资工作，虽然分隔两地，但每月会通过线上交流收藏心得，偶尔会互相邮寄稀有纪念币。每年徐静去北京出差时会约见面，一起参观钱币博物馆或古玩市场。"
                    }
                ],
                [
                    {
                        "name": "李雪梅",
                        "relation": "同行朋友",
                        "social circle": "行业圈",
                        "gender": "女",
                        "age": 32,
                        "birth_date": "1991-03-15",
                        "home_address": {
                            "province": "浙江省",
                            "city": "杭州市",
                            "district": "西湖区",
                            "street_name": "文三路",
                            "street_number": "456号"
                        },
                        "birth_place": {
                            "province": "浙江省",
                            "city": "杭州市"
                        },
                        "personality": "ENTJ",
                        "economic_level": "中产",
                        "occupation": "区域运营经理",
                        "organization": "江南时尚集团",
                        "nickname": "雪梅姐",
                        "relation_description": "李雪梅是徐静在行业交流会上认识的同行朋友，两人因对服装零售业的共同兴趣而结缘。她们平时主要通过微信交流行业动态，每季度会在上海或杭州见面一次，通常选择在商圈咖啡馆讨论市场趋势和经营管理经验。虽然分处两地，但会互相推荐优质供应商和客户资源，去年还合作举办过跨区域促销活动。"
                    }
                ],
                [
                    {
                        "name": "张明远",
                        "relation": "熟客",
                        "social circle": "客户圈",
                        "gender": "男",
                        "age": 35,
                        "birth_date": "1988-03-15",
                        "home_address": {
                            "province": "浙江省",
                            "city": "杭州市",
                            "district": "西湖区",
                            "street_name": "文三路",
                            "street_number": "456号"
                        },
                        "birth_place": {
                            "province": "浙江省",
                            "city": "宁波市"
                        },
                        "personality": "ENTJ",
                        "economic_level": "中产",
                        "occupation": "互联网公司市场总监",
                        "organization": "杭州某科技股份有限公司",
                        "nickname": "张总",
                        "relation_description": "张明远是徐静服装店的长期客户，五年前因工作需要购买商务服装而结识。他每季度会从杭州来上海出差时到店选购，偏好简约商务风格。两人保持着专业的客户关系，主要通过微信沟通新款到货信息，平均每两月联系一次。见面时徐静会为他提供专业的穿搭建议，偶尔会聊及各自的工作近况。"
                    }
                ]
            ]
        }
    '''
    json_data_p = json.loads(persona)
    json_data_e = read_json_file("event_data/life_event/event_update2.json")
    mind.load_from_json(json_data_e,json_data_p,1)
    #
    # print('++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
    # for date in iterate_dates('2025-01-01','2025-03-30'):
    #     mind.daily_event_gen1(date)
    d = '''
    ### 2025年7月30日全天事件安排

**06:30-07:00、晨间健康监测与瑜伽练习、上海市浦东新区张杨路123号家中卧室、徐静**
完成晨间健康监测，体重连续146日稳定在60.5kg，使用新购买的深蓝色迪卡侬瑜伽垫完成25分钟流瑜伽练习，重点练习平衡体式和脊柱扭转。同时收听《零售心理学》音频课程复习客户投诉处理章节，记录2个实用沟通技巧。发现新瑜伽垫防滑效果明显优于旧款，决定将旧瑜伽垫清洗后作为备用。

**07:00-07:25、早餐准备与家庭交流、上海市浦东新区张杨路123号家中厨房、徐静、李芳、徐明**
协助母亲准备全麦三明治配豆浆早餐，讨论今日报告定稿事宜。母亲准备午餐便当（红烧鸡块配西兰花）时发现保鲜盒数量不足，临时调整菜品搭配。父亲提醒报告装订注意事项，确认下午需要使用的打印设备。

**07:25-08:00、通勤与晨会准备、上海市浦东新区世纪大道88号明芳服饰店面、徐静**
自驾前往店铺用时10分钟，途中整理晨会要点，确认今日重点工作顺序。收听交通广播了解实时路况，发现世纪大道部分路段施工，及时调整行车路线。到店后检查收银系统运行状态，准备晨会投影资料，确认七夕促销物料充足。

**08:00-08:30、每日晨会布置工作、上海市浦东新区世纪大道88号明芳服饰店面、徐静、陈丽、刘伟**
召开简短晨会强调七夕促销服务重点，分配陈丽负责VIP客户接待、刘伟负责库存调配。检查昨日销售数据发现情侣装销量增长明显，调整今日主推款式。演示新款到货的搭配技巧，强调服务细节要求，解答员工关于促销政策的疑问。

**08:30-09:30、报告最终定稿、上海市浦东新区世纪大道88号公司会议室、徐静、李芳**
与母亲共同完成分店开设可行性研究报告的最后修订，仔细核对市场数据、投资预算和风险评估部分。使用专业装订机将报告打印装订成册，检查页码顺序和印刷质量。讨论报告提交后的后续工作安排，确认需要补充的附件材料。

**09:30-10:00、通勤前往培训中心、上海市徐汇区客服培训中心、徐静**
自驾前往徐汇区客服培训中心用时25分钟，途中复习培训总结要点。等红灯时回复工作群消息，确认下午陈列调整时间。使用导航规划最优路线，避开早高峰拥堵路段。

**10:00-11:30、培训总结分享、上海市徐汇区客服培训中心、徐静、陈丽**
与陈丽轮流进行学习成果总结和经验分享，重点展示客户心理分析和投诉处理技巧的实际应用案例。获得培训师专业点评，记录改进建议。与其他学员交流实战经验，收集3个可借鉴的客户服务方法，完成培训反馈问卷。

**11:30-12:00、通勤返回店铺、上海市浦东新区世纪大道88号明芳服饰店面、徐静**
自驾返回店铺用时25分钟，途中整理培训收获，构思店铺服务改进方案。等红灯时确认下午工作安排，回复供应商关于面料样品的咨询。

**12:00-13:00、午餐与工作整理、上海市浦东新区世纪大道88号明芳服饰店面休息区、徐静**
在店铺休息区用餐，同时整理上午工作记录。分析培训中学到的客户服务技巧如何应用到实际工作中，更新员工服务手册。处理积压邮件，回复2个VIP客户的商品咨询。

**13:00-14:00、根据销售情况调整陈列、上海市浦东新区世纪大道88号明芳服饰店面展示区、徐静、赵敏**
与赵敏根据前几日销售数据分析热销款位置，将销量突出的情侣装调整至店铺入口显眼位置。重新布置七夕主题陈列区，补充心形装饰和灯光效果。测试新的陈列方案视觉效果，记录需要补充的展示物料。

**14:00-14:30、课程安排协调、上海市浦东新区世纪大道88号上海世纪商场办公室、徐静、陈丽**
与陈丽讨论服装搭配专业课程的上课时间安排，对比各自的工作日程，确定每周三晚上的上课时间最为合适。确认课程材料准备情况，讨论如何将学到的知识应用到店铺运营中。

**14:30-15:30、仓库突发事件处理、上海市浦东新区明芳服饰仓库、徐静、李芳**
到仓库例行检查时发现停电异常，恒温系统失效。立即与母亲共同检查真丝、羊绒制品受潮情况，初步统计受损商品数量。联系电力公司确认停电原因及恢复时间，得知因片区电网升级工程失误导致持续8小时停电。

**15:30-16:30、损失评估与应急处理、上海市浦东新区明芳服饰仓库、徐静、李芳、孙老板**
详细统计受损商品数量和价值，初步估算损失约15万元。联系供应商孙老板通报损失情况，商讨后续处理方案。同时向保险公司电话报案，获取理赔指引，记录需要准备的证明材料清单。

**16:30-17:00、通勤返回店铺、上海市浦东新区世纪大道88号明芳服饰店面、徐静**
自驾返回店铺用时18分钟，途中整理损失评估数据，构思应急预案。等红灯时回复工作群关于晚间营业的安排，调整员工排班。

**17:00-17:30、晚间工作安排、上海市浦东新区世纪大道88号明芳服饰店面、徐静**
检查店铺晚间营业准备情况，更新今日销售数据。指导员工处理突发客诉，演示学到的客户服务技巧。整理明日工作重点，确认需要跟进的订单状态。

**17:30-18:00、通勤回家、上海市浦东新区张杨路123号家中、徐静**
自驾回家用时12分钟，途中与母亲确认晚餐准备情况。等红灯时在线购买《星空之约》电影票，选择8月2日晚间合适场次，使用会员积分抵扣部分费用。

**18:00-19:00、晚餐与家庭交流、上海市浦东新区张杨路123号家中餐厅、徐静、李芳、徐明**
与父母共进晚餐（清蒸鲈鱼、蒜蓉西兰花、番茄蛋汤），详细汇报今日仓库损失情况及处理进展。讨论保险理赔后续工作，父亲提供风险管理建议，母亲关心工作压力，建议适当放松。

**19:00-20:00、个人学习与色彩练习、上海市浦东新区张杨路123号家中书房、徐静**
阅读《服装搭配艺术》教材色彩搭配章节，使用新购买的色卡进行实践练习。将今日培训所学客户服务知识与色彩心理学结合，设计3套适合不同客户类型的搭配方案，记录学习心得。

**20:00-20:30、线上事务处理、上海市浦东新区张杨路123号家中客厅、徐静**
在线查看保险理赔所需材料清单，开始整理购买凭证和库存记录。同时确认电影票购票成功，将电子票转发给闺蜜群。回复工作邮件，安排明日晨会内容。

**20:30-21:00、晚间放松与护理、上海市浦东新区张杨路123号家中卧室、徐静**
使用新瑜伽垫进行15分钟舒缓拉伸，重点放松肩颈部位。进行面部清洁和基础护肤，整理明日工作物品，记录感恩日记包括顺利完成报告定稿和培训总结。

**21:00-21:30、睡前准备、上海市浦东新区张杨路123号家中卧室、徐静**
整理今日工作笔记，确认明日重点工作清单。进行深呼吸放松练习，设定手机闹钟，检查门窗安全后准备休息。
    '''
    mind.map(d)



