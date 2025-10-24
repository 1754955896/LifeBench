# -*- coding: utf-8 -*-
import ast
import json
from utils.IO import *
from datetime import datetime, timedelta
from utils.llm_call import *
from event.templates import *
from event.memory import *

class Mind:
    def __init__(self):
        self.calendar = {}  # 存储日程数据，格式如{"2025-01-01":["event1","event2"],...}
        self.events = []
        self.persona = ""
        self.persona_withoutdesc = ""
        self.persona_withoutrl = ""
        self.calendar_atomic= {}
        self.daily_life = {}
        self.fix_concept = ""
        self.short_memory_reflection = ""
        self.mem_moudle = PersonalMemoryManager()
    def load_from_json(self, calendar,event,persona):
            self.persona = persona
            del persona["relation"]
            self.persona_withoutrl = persona
            keys_to_delete = [key for key in persona if 'desc' in key.lower()]
            for key in keys_to_delete:
                del persona[key]
            self.persona_withoutdesc = persona
            self.calendar = calendar
            self.events = event
            self.calendar_atomic = calendar
            return False
    def save_json(self):
        with open("../data_atomic/atomic_7_1.json", "w", encoding="utf-8") as json_f:
            json.dump(self.calendar_atomic, json_f, ensure_ascii=False, indent=4)
        with open("../data_atomic/life_7.json", "w", encoding="utf-8") as json_f:
            json.dump(self.daily_life, json_f, ensure_ascii=False, indent=4)

    def llm_call_sr(self,prompt,record=0):
        """调用大模型的函数"""
        res = llm_call_reason(prompt,context3,record=record)
        return res

    def llm_call_s(self,prompt,record=0):
        """调用大模型的函数"""
        res = llm_call(prompt,context3,record=record)
        return res

    def get_calendar_in_range(self, x, y):
        """
        获取日程数据中从x日到y日的所有数据

        参数:
            schedule_data: 包含日程数据的字典，键为日期字符串（格式"YYYY-MM-DD"）
            x: 起始日期字符串（格式"YYYY-MM-DD"）
            y: 结束日期字符串（格式"YYYY-MM-DD"）

        返回:
            包含指定日期范围内数据的字典，键为日期字符串，值为对应日程数据

        异常:
            ValueError: 当日期格式错误或y <= x时抛出
        """
        schedule_data = self.calendar
        # 定义日期格式
        date_format = "%Y-%m-%d"

        try:
            # 验证x和y的日期格式
            start_date = datetime.strptime(x, date_format)
            end_date = datetime.strptime(y, date_format)
        except ValueError:
            raise ValueError(f"日期格式错误，请使用'{date_format}'格式")

        # 检查y是否大于x
        if end_date < start_date:
            raise ValueError("结束日期必须晚于起始日期")

        # 筛选范围内的日期数据
        result = {}
        for date_str in schedule_data:
            try:
                current_date = datetime.strptime(date_str, date_format)
                # 检查当前日期是否在[x, y]范围内
                if start_date <= current_date <= end_date:
                    result[date_str] = schedule_data[date_str]
            except ValueError:
                # 忽略数据中格式错误的日期（如果有）
                continue

        return result

    def get_atomiccal_in_range(self,x,y):
        """
                获取日程数据中从x日到y日的所有数据

                参数:
                    schedule_data: 包含日程数据的字典，键为日期字符串（格式"YYYY-MM-DD"）
                    x: 起始日期字符串（格式"YYYY-MM-DD"）
                    y: 结束日期字符串（格式"YYYY-MM-DD"）

                返回:
                    包含指定日期范围内数据的字典，键为日期字符串，值为对应日程数据

                异常:
                    ValueError: 当日期格式错误或y <= x时抛出
                """
        schedule_data = self.calendar_atomic
        # 定义日期格式
        date_format = "%Y-%m-%d"

        try:
            # 验证x和y的日期格式
            start_date = datetime.strptime(x, date_format)
            end_date = datetime.strptime(y, date_format)
        except ValueError:
            raise ValueError(f"日期格式错误，请使用'{date_format}'格式")

        # 检查y是否大于x
        if end_date < start_date:
            raise ValueError("结束日期必须晚于起始日期")

        # 筛选范围内的日期数据
        result = {}
        for date_str in schedule_data:
            try:
                current_date = datetime.strptime(date_str, date_format)
                # 检查当前日期是否在[x, y]范围内
                if start_date <= current_date <= end_date:
                    result[date_str] = schedule_data[date_str]
            except ValueError:
                # 忽略数据中格式错误的日期（如果有）
                continue

        return result
    def get_events_in_range(self, x, y):
        """
        筛选数组中与[x, y]日期范围有重叠的事件

        参数:
            events: 事件数组，每个元素包含"事件"和"起止日期"字段
            x: 起始日期字符串（格式"YYYY-MM-DD"）
            y: 结束日期字符串（格式"YYYY-MM-DD"）

        返回:
            符合条件的事件列表

        异常:
            ValueError: 当日期格式错误或y <= x时抛出
        """
        events = self.events
        date_format = "%Y-%m-%d"

        # 验证输入日期格式和逻辑
        try:
            start_query = datetime.strptime(x, date_format)
            end_query = datetime.strptime(y, date_format)
        except ValueError:
            raise ValueError(f"日期格式错误，请使用'{date_format}'格式")

        if end_query < start_query:
            raise ValueError("结束日期必须晚于起始日期")

        result = []

        for event in events:
            original_time_ranges = event.get("起止日期", [])
            overlapping_ranges = []

            for time_str in original_time_ranges:
                # 拆分时间段（处理"YYYY-MM-DD至YYYY-MM-DD"格式）
                if "至" not in time_str:
                    # 处理单个日期（默认开始和结束为同一天）
                    start_event = datetime.strptime(time_str, date_format)
                    end_event = start_event
                else:
                    start_str, end_str = time_str.split("至")
                    try:
                        start_event = datetime.strptime(start_str.strip(), date_format)
                        end_event = datetime.strptime(end_str.strip(), date_format)
                    except ValueError:
                        # 跳过格式错误的时间段
                        continue

                # 判断时间段是否与查询范围重叠
                if start_event <= end_query and start_event >= start_query:
                    overlapping_range = f"{start_event}至{end_event}"

                    overlapping_ranges.append(overlapping_range)

            # 只保留有重叠时间段的事件
            if overlapping_ranges:
                # 创建新事件对象，仅包含重叠的时间段
                filtered_event = {
                    "事件": event["事件"],
                    "起止日期": overlapping_ranges
                }
                result.append(filtered_event)

        return result

    def get_dailylife_in_range(self,x,y):
        schedule_data = self.daily_life
        # 定义日期格式
        date_format = "%Y-%m-%d"

        try:
            # 验证x和y的日期格式
            start_date = datetime.strptime(x, date_format)
            end_date = datetime.strptime(y, date_format)
        except ValueError:
            raise ValueError(f"日期格式错误，请使用'{date_format}'格式")

        # 检查y是否大于x
        if end_date < start_date:
            raise ValueError("结束日期必须晚于起始日期")

        # 筛选范围内的日期数据
        result = {}
        for date_str in schedule_data:
            try:
                current_date = datetime.strptime(date_str, date_format)
                # 检查当前日期是否在[x, y]范围内
                if start_date <= current_date <= end_date:
                    result[date_str] = schedule_data[date_str]
            except ValueError:
                # 忽略数据中格式错误的日期（如果有）
                continue

        return result

    def EventDecomposer(self,data):
        #print("EventDecomposer")
        def merge_events(atomic_events):
            """
            将原子事件数据按日期合并到目标JSON中

            参数:
                atomic_events: 包含原子事件的列表
                target_json: 目标JSON数据

            返回:
                合并后的JSON数据
            """
            target_json = self.calendar_atomic
            # 复制目标JSON以避免修改原数据
            merged = target_json.copy()

            for event in atomic_events:
                # 提取日期部分（不包含时间）
                event_datetime = datetime.strptime(event["发生日期"], "%Y-%m-%d")
                event_date = event_datetime.strftime("%Y-%m-%d")

                # 检查日期是否存在于目标JSON中
                if event_date in merged:
                    # 准备要添加的详细事件
                    detailed_event = {
                        "原子事件": event["原子事件"],
                        "发生时间": event_datetime.strftime("%Y-%m-%d"),
                        "详细描述": event["详细描述"],
                        "原事件": event["原事件"]
                    }

                    # 如果"详细事件"字段不存在则创建
                    if "详细事件" not in merged[event_date]:
                        merged[event_date]["详细事件"] = []

                    # 添加详细事件到对应日期
                    merged[event_date]["详细事件"].append(detailed_event)

            return merged

        prompt = template_decomposer_1.format(content = data,persona = self.persona,memory=[])
        print(prompt)
        res = self.llm_call_s(prompt,1)
        print(res)
        prompt = template_decomposer_json
        res = self.llm_call_s(prompt)
        print(res)
        data = json.loads(res)
        self.calendar_atomic = merge_events(data)
        #print(self.calendar_atomic)
        return True

    def retrive_memory(self,date):
        def del_two_days(date_str):
            """
            计算指定日期-2天后的日期

            参数:
                date_str: 输入日期，格式为"YYYY-MM-DD"的字符串

            返回:
                加7天后的日期，格式为"YYYY-MM-DD"的字符串
            """
            # 将字符串转换为datetime对象
            if type(date_str) == str:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            else:
                date_obj = date_str
            # 加上7天
            new_date_obj = date_obj - timedelta(days=2)
            # 转换回字符串格式
            return new_date_obj.strftime("%Y-%m-%d")

        content1 = self.get_dailylife_in_range(del_two_days(date),date) #短期情景记忆
        content2 = self.short_memory_reflection #短期语义记忆
        q = "".join(self.calendar_atomic[date]["事件"])
        print(f'q:{q}')
        content3 = self.mem_moudle.search_by_similarity(q,top_n=10)

        mem = f'''
        近两天记忆：{content1},
        昨日总结：{content2}，
        长期相关记忆:{content3}
        '''

        return mem


    def update_memory(self,date):
        def del_two_days(date_str):
            """
            计算指定日期-2天后的日期

            参数:
                date_str: 输入日期，格式为"YYYY-MM-DD"的字符串

            返回:
                加7天后的日期，格式为"YYYY-MM-DD"的字符串
            """
            # 将字符串转换为datetime对象
            if type(date_str) == str:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            else:
                date_obj = date_str
            # 加上7天
            new_date_obj = date_obj - timedelta(days=2)
            # 转换回字符串格式
            return new_date_obj.strftime("%Y-%m-%d")
        date = del_two_days(date)
        if date in self.daily_life:
            data = self.daily_life[date]
            for item in data:
                self.mem_moudle.add_memory(del_two_days(date),item)
        return
    def relect_and_plan(self,date):
        def del_7_days(date_str):
            """
            计算指定日期-2天后的日期

            参数:
                date_str: 输入日期，格式为"YYYY-MM-DD"的字符串

            返回:
                加7天后的日期，格式为"YYYY-MM-DD"的字符串
            """
            # 将字符串转换为datetime对象
            if type(date_str) == str:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            else:
                date_obj = date_str
            # 加上7天
            new_date_obj = date_obj - timedelta(days=7)
            # 转换回字符串格式
            return new_date_obj.strftime("%Y-%m-%d")

        prompt = template_genatomic_reflect.format(content = self.get_dailylife_in_range(del_7_days(date),date),ref = self.short_memory_reflection)
        res = self.llm_call_s(prompt)
        print(res)
        self.short_memory_reflection = res
        self.update_memory(date)
        return

    def AtomicEventGen(self,data,date):
        def add_seven_days(date_str):
            """
            计算指定日期加7天后的日期

            参数:
                date_str: 输入日期，格式为"YYYY-MM-DD"的字符串

            返回:
                加7天后的日期，格式为"YYYY-MM-DD"的字符串
            """
            # 将字符串转换为datetime对象
            if type(date_str) == str:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            else:
                date_obj = date_str
            # 加上7天
            new_date_obj = date_obj + timedelta(days=7)
            # 转换回字符串格式
            return new_date_obj.strftime("%Y-%m-%d")

        for datex in data:
            if "描述" in data[datex]:
                description = data[datex]["描述"]
                # 找到第一个逗号的位置
                comma_index = description.find("，")
                if comma_index != -1:
                    # 只保留第一个逗号之前的内容
                    data[datex]["描述"] = description[:comma_index]
            if "详细事件" in data[datex]:
                devent = data[datex]["详细事件"]
                for item in devent:
                    del item["原事件"]
        def merge_events(atomic_events):
            """
            将原子事件数据按日期合并到目标JSON中

            参数:
                atomic_events: 包含原子事件的列表
                target_json: 目标JSON数据

            返回:
                合并后的JSON数据
            """
            target_json = self.calendar_atomic
            # 复制目标JSON以避免修改原数据
            merged = target_json.copy()

            for event in atomic_events:
                # 提取日期部分（不包含时间）
                event_datetime = datetime.strptime(event["延迟日期"], "%Y-%m-%d")
                event_date = event_datetime.strftime("%Y-%m-%d")

                # 检查日期是否存在于目标JSON中
                if event_date in merged:
                    # 准备要添加的详细事件
                    detailed_event = {
                        "原子事件": event["原子事件"],
                        "发生时间": event_datetime.strftime("%Y-%m-%d"),
                        "详细描述": event["详细描述"],
                        "原事件": event["原事件"]
                    }

                    # 如果"详细事件"字段不存在则创建
                    if "详细事件" not in merged[event_date]:
                        merged[event_date]["详细事件"] = []

                    # 添加详细事件到对应日期
                    merged[event_date]["详细事件"].append(detailed_event)

            return merged

        prompt = template_genatomic_1.format(content=data, persona=self.persona, memory=self.retrive_memory(date),plan=self.get_atomiccal_in_range(date,add_seven_days(date)))
        print(prompt)
        res = self.llm_call_sr(prompt,1)
        print(res)
        prompt = template_genatomic_json
        res = self.llm_call_s(prompt,1)
        print(res)
        data = json.loads(res)
        self.daily_life[date]=data
        prompt = template_genatomic_delay
        res = self.llm_call_s(prompt)
        print(res)
        if "[]" in res or "```" in res:
            self.relect_and_plan(date)
            return
        data = json.loads(res)
        merge_events(data)
        self.relect_and_plan(date)
        return

    def main(self,start_date_str,end_date_str):
        # 将字符串转换为datetime对象
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

        # 检查日期有效性
        if start_date > end_date:
            raise ValueError("开始日期不能晚于结束日期")

        def add_seven_days(date_str):
            """
            计算指定日期加7天后的日期

            参数:
                date_str: 输入日期，格式为"YYYY-MM-DD"的字符串

            返回:
                加7天后的日期，格式为"YYYY-MM-DD"的字符串
            """
            # 将字符串转换为datetime对象
            if type(date_str) == str:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            else:
                date_obj = date_str
            # 加上7天
            new_date_obj = date_obj + timedelta(days=7)
            # 转换回字符串格式
            return new_date_obj.strftime("%Y-%m-%d")

        dates = []
        current_date = start_date
        # 遍历日期范围
        while current_date < datetime.strptime(add_seven_days(start_date_str),"%Y-%m-%d"):
            self.EventDecomposer(self.get_events_in_range(current_date.strftime("%Y-%m-%d"), current_date.strftime("%Y-%m-%d")))
            current_date += timedelta(days=1)
            print(self.calendar_atomic)
        current_date = start_date
        with open("../data_atomic/atomic_7.json", "w", encoding="utf-8") as json_f:
            json.dump(self.calendar_atomic, json_f, ensure_ascii=False, indent=4)
        # 遍历日期范围
        while current_date <= end_date:
            self.EventDecomposer(self.get_events_in_range(add_seven_days(current_date),add_seven_days(current_date)))
            print(self.calendar_atomic)
            self.AtomicEventGen(self.get_atomiccal_in_range(current_date.strftime("%Y-%m-%d"),current_date.strftime("%Y-%m-%d")),current_date.strftime("%Y-%m-%d"))
            print(self.daily_life)
            self.save_json()
            # 日期加1天
            current_date += timedelta(days=1)

if __name__ == "__main__":
    mind = Mind()
    json_data_p = read_json_file("../data_atomic/refer/persona_xujing.json")
    json_data_e = read_json_file("../data_atomic/refer/event_xujing.json")
    json_data_c = read_json_file("../data_atomic/refer/calendar_xujing.json")
    mind.load_from_json(json_data_c,json_data_e,json_data_p)
    #mind.calendar_atomic = read_json_file("../data_atomic/atomic_7.json")
    mind.main("2025-10-01","2025-10-31")

    # start_date = datetime.strptime("2025-01-01", "%Y-%m-%d")
    # end_date = datetime.strptime("2025-01-07", "%Y-%m-%d")
    # current_date = start_date
    # while current_date <= end_date:
    #     print(current_date)
    #     mind.AtomicEventGen(mind.get_atomiccal_in_range(current_date.strftime("%Y-%m-%d"),current_date.strftime("%Y-%m-%d")),current_date.strftime("%Y-%m-%d"))
    #     #mind.save_json()
    #     current_date += timedelta(days=1)
    #     break
    # print(mind.get_events_in_range("2025-01-13","2025-01-13"))
    # print(mind.EventDecomposer(mind.get_events_in_range("2025-01-13","2025-01-13")))
    #print(mind.AtomicEventGen(mind.get_calendar_in_range("2025-01-13", "2025-01-13")))

