# -*- coding: utf-8 -*-
import calendar
import holidays
import copy
import json
import os
import re
from src.lifebench.utils.utils_io import *
from datetime import datetime, timedelta
from src.lifebench.utils.llm_call import *
from src.lifebench.utils.maptool import *
from src.lifebench.event.templates.templates import *
from src.lifebench.event.templates.template_simulation import *
from src.lifebench.event.simulation.memory.store import MemoryStore
from src.lifebench.event.simulation.memory.consolidation import FuzzyMemoryBuilder
from src.lifebench.event.simulation.memory.retrieval import build_short_memory
from src.lifebench.event.simulation.state import CognitiveState
from typing import List, Dict, Optional
from src.lifebench.utils.json_utils import remove_json_wrapper
from src.lifebench.utils.date_utils import (
    extract_start_date,
    extract_start_date_or_default,
    iterate_dates,
)
from src.lifebench.event.simulation.generators import (
    generate_subjective_thought,
    generate_objective_events,
    generate_poi_route,
    adjust_event_trajectory,
    generate_reflection,
)
from src.lifebench.event.simulation.engine import DailySimulationEngine
from src.lifebench.event.simulation.memory.consolidation import update_long_term_memory
from src.lifebench.event.simulation.telemetry import MemoryTraceRecorder


def convert_chinese_to_pinyin(chinese_str: str) -> str:
    """将中文转换为拼音，去除空格和特殊字符"""
    try:
        from pypinyin import lazy_pinyin
        # 获取拼音列表并连接
        pinyin_list = lazy_pinyin(chinese_str)
        pinyin = ''.join(pinyin_list)
        # 去除空格和特殊字符，只保留字母和数字
        pinyin = re.sub(r'[^a-zA-Z0-9]', '', pinyin)
        return pinyin if pinyin else chinese_str
    except ImportError:
        # 如果没有安装 pypinyin，返回原始字符串
        return chinese_str


class Mind:
    def __init__(self,file_path, instance_id=0, persona=None, event=None, daily_state=None, persona_address_data=None, daily_draft=None):
        self.events = event if event is not None else []
        self.persona = persona if persona is not None else ""
        self.persona_withoutrl = ""
        # 记忆存储延迟到 initialize 创建：每个分片持有独立 MemoryStore，消除并行写竞争
        self.mem_module = None
        self.context = ""
        self.cognition = ""  # 主要存储对自我的认知，包括画像信息
        self.long_memory = ""  # 主要存储近期事件感知、印象深刻的关键事件、长期主要事件感知、近期想法及推理思考（动机）
        self.short_memory = ""  # 主要存储近期所有详细事件和相关检索事件
        self.thought = ""  # 记录个人的感受、想法，包括情绪、想法、需求及思考过程中的打算
        self.bottom_events : Optional[List[Dict]] = None
        # 读取配置文件，使用项目根目录下的 config.json
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
        config_path = os.path.join(project_root, 'config', 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        # 保存配置，供遥测（manifest）读取模型/温度等元数据
        self.config = config
        # 本分片逐日检索/写入命中记录器（telemetry → memory_trace.json）
        self.memory_trace = MemoryTraceRecorder()
        # 获取地图工具配置
        map_config = config.get('map_tool', {})
        map_api_key = map_config.get('api_key', '')
        self.maptools = MapMaintenanceTool(map_api_key, persona_address_data=persona_address_data)
        self.env = ""
        self.file_path = file_path
        self.instance_id = instance_id
        # 分片起始日（initialize 时由引擎传入），用于统一命名 sim/ 下产物
        self.interval_start = None
        # 统一输出根目录：所有运行态产物都写到 {file_path}/sim/ 下
        self.sim_dir = os.path.join(file_path, "sim")
        # 存储每日处理的中间输出，用于后续统一提取事件
        self.daily_intermediate_outputs = {}
        # Fuzzy memory builder reference
        self.fuzzy_memory_builder = None
        # 新增daily_state属性
        self.daily_state = daily_state if daily_state is not None else []
        # 新增daily_draft属性
        self.daily_draft = daily_draft if daily_draft is not None else []
        self.persona_address_data = persona_address_data if persona_address_data is not None else []
        
    def save_to_json(self):
        data = {}
        data["persona"] =  self.persona
        data["context"] = self.context
        data["cognition"] = self.cognition
        data["long_memory"] = self.long_memory
        data["short_memory"] = self.short_memory
        data["thought"] = self.thought
        data['env'] = self.env
        
        # 按分片（instance_id + 分片起始日）命名，替代线程ID，保证可复现
        shard_key = getattr(self, "interval_start", None) or "unknown"
        if not os.path.exists(self.sim_dir):
            os.makedirs(self.sim_dir)

        filename = f"state_{self.instance_id}_{shard_key}.json"
        file_path = os.path.join(self.sim_dir, filename)

        # 保存到同一个文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n=== 数据已保存到 {file_path} ===")

    def to_cognitive_state(self) -> CognitiveState:
        """导出结构化认知状态（用于 checkpoint 持久化）。"""
        return CognitiveState(
            long_memory=self.long_memory,
            short_memory=self.short_memory,
            thought=self.thought,
            cognition=self.cognition,
            context=self.context,
            env=self.env,
        )

    def restore_cognitive_state(self, state: CognitiveState) -> None:
        """从结构化认知状态恢复字段。"""
        self.long_memory = state.long_memory
        self.short_memory = state.short_memory
        self.thought = state.thought
        self.cognition = state.cognition
        self.context = state.context
        self.env = state.env

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

        # 步骤2：筛选匹配日期的事件
        matched = []
        for event in bottom_events:
            # 统一处理date为数组或单个字符串的情况，转为可迭代对象
            date_values = event.get("date", [])
            if not isinstance(date_values, list):
                date_values = [date_values]  # 若为单个字符串，转为单元素列表

            for date_str in date_values:
                date_str = extract_start_date_or_default(date_str)
                if self.is_date_match(target_date, date_str):
                    matched.append(event)
                    break # 避免同一事件因多个日期重复加入

        return matched
    def initialize(self, event, persona, date, daily_state=None, daily_draft=None):
        """
        初始化Mind对象

        参数:
            event: 事件数据
            persona: 人物画像数据
            date: 模拟开始日期，格式为"YYYY-MM-DD"
            daily_state: 每日状态数据，格式与test_daily_state.json相同
            daily_draft: 每日草稿数据
        """
        print("[DEBUG] date=" + str(date))
        print("[DEBUG] event type=" + str(type(event)))
        print("[DEBUG] persona type=" + str(type(persona)))
        if isinstance(persona, dict):
            print("[DEBUG] persona keys=" + str(list(persona.keys())))
        print("[DEBUG] daily_draft type=" + str(type(daily_draft)))

        self.persona = copy.deepcopy(persona)
        self.events = event
        self.current_date = date
        # 记录分片起始日，供 sim/ 下产物统一命名
        self.interval_start = date
        # 确保统一输出目录存在（模糊记忆等产物依赖 sim/ 已建）
        os.makedirs(self.sim_dir, exist_ok=True)
        # 初始化daily_state
        self.daily_state = daily_state if daily_state is not None else []
        if daily_state is None:
            print("未提供daily_state，将使用默认值。")
        # 初始化daily_draft
        self.daily_draft = daily_draft if daily_draft is not None else []
        if daily_draft is None:
            print("未提供daily_draft，将使用默认值。")
        # 初始化FuzzyMemoryBuilder（输出到 sim/ 下）
        self.fuzzy_memory_builder = FuzzyMemoryBuilder.get_instance(event, persona, self.sim_dir)

        # 检查fuzzymemory文件是否存在，如果不存在则生成
        year = int(date[:4])
        monthly_file = os.path.join(self.sim_dir, "monthly_summaries.json")
        cumulative_file = os.path.join(self.sim_dir, "cumulative_summaries.json")

        if not (os.path.exists(monthly_file) and os.path.exists(cumulative_file)):
            print("未找到fuzzymemory文件，开始生成" + str(year) + "年的月度总结和累积总结...")
            self.fuzzy_memory_builder.build_all_summaries(year)
            print("fuzzymemory生成完成！")
        else:
            print("fuzzymemory文件已存在，直接加载...")
            self.fuzzy_memory_builder.load_summaries()

        self.update_bottom_level_events()

        # 创建独立记忆存储：按分片（date 为分片起始日）命名，去单例、去并行写竞争
        persona_name = ""
        if isinstance(persona, dict) and "name" in persona:
            persona_name = convert_chinese_to_pinyin(persona["name"])
        memory_file_name = f"personal_memories_{self.instance_id}_{persona_name}_{date}.json"
        memory_file_path = os.path.join(self.sim_dir, "memory_file", memory_file_name)
        self.mem_module = MemoryStore(memory_file=memory_file_path)

        # 初始化长期记忆和短期记忆
        self.long_memory = self.get_fuzzy_long_memory(date)
        self.update_short_memory("",self.get_next_n_day(date,-1))

        # 生成cognition和context
        t1 = '''
        请你基于下面的个人画像和详细地址信息，以第一人称视角描述你对自己的自我认知，包括1）个人基本信息。2）工作的主要特征、内容、方式、习惯、主要人物。3）家庭的主要特征、内容、方式、习惯、主要人物。4）其他生活的主要特征、内容、方式、习惯、主要人物。5）平常工作日的常见安排，目前的主要每天安排。描述要全面覆盖个人信息，地址相关数据请优先参考详细地址信息而非画像信息。

        个人画像：{persona}
        详细地址信息：{persona_address_data}
        '''

        t2 = '''
        请你基于下面的个人画像，设计一句让大模型扮演该角色的context，以"你是一位"开头。不超过50个字，只保留重要信息。
        个人画像：{persona}
        '''

        print("[DEBUG initialize] self.persona type=" + str(type(self.persona)))
        print("[DEBUG initialize] self.persona_address_data type=" + str(type(self.persona_address_data)))
        prompt = t1.format(persona=self.persona, persona_address_data=self.persona_address_data)
        res = self.llm_call_s(prompt)
        self.cognition = res

        prompt = t2.format(persona=self.persona)
        res = self.llm_call_s(prompt)
        self.context = res

        # 结构化长记忆种子：把叙述式模糊记忆整理为 7 字段（P1 改进）
        self.seed_long_term_memory()

        self.persona_withoutrl = persona.copy()
        if "relation" in self.persona_withoutrl:
            del self.persona_withoutrl["relation"]

    def seed_long_term_memory(self):
        """将叙述式模糊记忆冷启动种子转换为 7 字段结构化长记忆。

        冷启动的 get_fuzzy_long_memory 返回叙述式总结，直接作为 long_memory 会导致
        update_long_term_memory 只填充 key_events/summary 而 state/facts/preferences/
        routines 全空。这里用一次 LLM 调用把画像 + 自我认知 + 模糊记忆整理为
        7 字段 JSON，作为结构化的长记忆种子。
        """
        from src.lifebench.event.simulation.state import LongTermMemory
        from src.lifebench.utils.llm_call import llm_call_j
        from src.lifebench.utils.json_utils import remove_json_wrapper

        prompt = '''
请你基于以下信息，为角色初始化一份「状态型长期记忆」，严格输出七字段 JSON。
各字段含义：
- state（当前状态）：位置、职业、关系、健康、经济、心理等慢变化状态。
- facts（客观事实/常用信息）：固定场所、常用服务、重要时间点等客观信息，标注日期。
- preferences（固定偏好）：长期稳定的偏好（饮食、消费、运动、娱乐）。
- routines（重复/习惯性行为）：重复多次进行的行为总结。
- key_events（关键事件）：高价值、印象深刻的关键节点，需明确日期。
- plans（未来规划）：明确的未来规划，需含具体日期；无则留空。
- summary（滚动总结）：对过去一段生活的滚动概括。

要求：
1. 尽量从画像与自我认知中提取 state/facts/preferences/routines，不得随意留空（确实无相关信息才写空字符串）。
2. 仅输出 JSON 对象，无任何额外文本或代码块标记。

个人画像：{persona}
自我认知：{cognition}
模糊记忆（草稿派生总结）：{fuzzy}

输出格式：
{{"state":"...","facts":"...","preferences":"...","routines":"...","key_events":"...","plans":"...","summary":"..."}}
'''
        try:
            res = llm_call_j(prompt.format(
                persona=json.dumps(self.persona, ensure_ascii=False, indent=2),
                cognition=self.cognition,
                fuzzy=self.long_memory,
            ))
            cleaned = remove_json_wrapper(res)
            data = json.loads(cleaned)
            ltm = LongTermMemory.from_dict(data)
            seeded = ltm.to_string()
            if seeded.strip():
                self.long_memory = seeded
        except Exception as e:
            print(f"[seed_long_term_memory] 结构化种子生成失败，保留叙述式长记忆：{str(e)}")

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
        res = llm_call(prompt,self.context)
        return res

    def llm_call_j(self, prompt, record=0):
        """
        调用大模型进行JSON格式返回
        
        参数:
            prompt: 提示词
            record: 是否记录调用（默认0：不记录）
        
        返回:
            dict: 大模型返回的JSON解析结果
        """
        res = llm_call_j(prompt,self.context)
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
            #print("下一天日期：", next_day_obj)
            return next_day_obj.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(f"日期格式错误：{date_str}，请使用YYYY-MM-DD格式（例如'2025-01-01'）")

    def get_plan4(self,date,i=0):

        import json
        from datetime import datetime, timedelta
        #print('here')
        # 计算目标日期
        base_date = datetime.strptime(date, "%Y-%m-%d")
        target_date = base_date + timedelta(days=i)
        target_date_str = target_date.strftime("%Y-%m-%d")

        # 直接从self.daily_draft获取数据
        try:
            data = self.daily_draft
            print("[DEBUG get_plan4] self.daily_draft type=" + str(type(data)) + ", date=" + str(date) + ", i=" + str(i))
            # 从目标日期中提取年月，例如 "2025-01-05" -> "2025-01"
            year_month = "-".join(target_date_str.split("-")[:2])

            # 检查年月数据是否存在
            if year_month not in data:
                print("警告: 年月 " + year_month + " 的数据在文件中不存在")
                return {}

            # 在对应的月份数据中查找指定日期
            month_data = data[year_month]

            for day_data in month_data:
                # print(day_data)
                if day_data.get("date") == target_date_str:
                        return day_data

                # 如果指定日期不存在，返回空字典
            print("警告: 日期 " + target_date_str + " 的数据在文件中不存在")
            return {}
        except json.JSONDecodeError:
            print("错误: daily_draft 不是有效的JSON格式")
            return {}
        except Exception as e:
            print("读取daily_draft时发生错误: " + str(e))
            import traceback
            traceback.print_exc()
            return {}

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

    def event_add(self,data):
        """
            新增上层事件，并更新底层事件

        """
        for i in data:
            self.events = self.add_top_event(self.events,i)
        self.update_bottom_level_events()
        return
    def update_short_memory(self, dailyevent, date):
        """更新短期记忆（委托给 retrieval 模块）。"""
        build_short_memory(self, dailyevent, date)

    def get_fuzzy_short_memory(self,date):
        date_events = self.get_plan4(date)
        if not date_events:
            return ""
        #print('here')
        #print(date_events)
        res = "我在"+date+"做了下面这些事："
        for item in date_events['events']:
            #print(item)
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
            
            # 如果是当月一号，直接返回累积记忆
            if day == 1:
                if self.fuzzy_memory_builder is None:
                    # 如果没有初始化FuzzyMemoryBuilder，尝试创建一个
                    self.fuzzy_memory_builder = FuzzyMemoryBuilder.get_instance(self.events, self.persona, self.sim_dir)
                
                # 加载已保存的总结（如果有）
                self.fuzzy_memory_builder.load_summaries()
                
                # 获取累积记忆
                cumulative_memory = self.fuzzy_memory_builder.get_memory_up_to_month(date)
                
                return cumulative_memory
            
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
        """获取真实poi数据和通行信息（委托给轨迹生成器）。"""
        return generate_poi_route(self, pt)

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
            plan = self.get_plan4(date)
            print("[DEBUG daily_event_gen1] plan type=" + str(type(plan)) + ", keys=" + str(list(plan.keys()) if isinstance(plan, dict) else "N/A"))
            if isinstance(plan, dict) and "events" in plan:
                print("[DEBUG daily_event_gen1] plan events count=" + str(len(plan.get("events", []))))
            subjective_thought = self._generate_subjective_thought(plan, date)

            # 2. 生成客观事件
            objective_events = self._generate_objective_events(plan, date, subjective_thought)
            # 3. 获取POI数据并调整轨迹
            poi_data = self.map(objective_events)
            # 从plan2中获取当日事件参考数据
            adjusted_events = self._adjust_event_trajectory(poi_data, objective_events, plan,
                                                            self.get_plan4(date,-1))

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
                "objective_events": objective_events,
                "poi_data": poi_data,
                "adjusted_events": adjusted_events,
                "reflection": reflection
            }

            # 8. 保存当前状态
            self.save_to_json()
            self.save_intermediate_outputs()
            # self._save_events_to_file()

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
        # 按分片（instance_id + 分片起始日）命名，替代线程ID，保证可复现
        shard_key = getattr(self, "interval_start", None) or "unknown"
        intermediate_folder = os.path.join(self.sim_dir, "intermediate")
        if not os.path.exists(intermediate_folder):
            os.makedirs(intermediate_folder)

        filename = f"intermediate_outputs_{self.instance_id}_{shard_key}.json"
        file_path = os.path.join(intermediate_folder, filename)

        # 保存到同一个文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.daily_intermediate_outputs, f, ensure_ascii=False, indent=2)
        print(f"\n=== 中间输出已保存到 {file_path} ===")
        return filename
    
    def _log_event(self, message):
        """
        记录事件日志到控制台
        
        参数:
            message: 要记录的消息
        """
        #print(message)
    
    def _save_log(self, date, log_type, content):
        """
        保存日志内容到文件
        
        参数:
            date: 日期字符串
            log_type: 日志类型
            content: 日志内容
        """
        # 创建 sim/logs 目录
        log_folder = os.path.join(self.sim_dir, 'logs')
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
        """生成主观思考（委托给 thought 生成器）。"""
        return generate_subjective_thought(self, plan, date)
    
    def _generate_objective_events(self, plan,date,event):
        """生成客观事件（委托给 objective 生成器）。"""
        return generate_objective_events(self, plan, date, event)
    
    def _adjust_event_trajectory(self, poi_data, event, daily_event_reference="",history=""):
        """调整事件轨迹（委托给 trajectory 生成器）。"""
        return adjust_event_trajectory(self, poi_data, event, daily_event_reference, history)
    
    def _generate_reflection(self, events, plan, date):
        """生成反思（委托给 reflection 生成器）。"""
        return generate_reflection(self, events, plan, date)
    
    def _update_long_term_memory(self, plan, reflection, date):
        """更新长期记忆（委托给 consolidation 模块，状态型长记忆）。"""
        update_long_term_memory(self, plan, reflection, date)

class MindController:
    """
    Mind类的并行化控制器，用于管理多个Mind实例的并行执行
    """
        
    def __init__(self, event_file='event.json', persona_file='persona.json', data_dir='data/2025-12-07', daily_state_file='daily_state.json', instance_id=0, loc_data='location.json'):
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
        from src.lifebench.utils.utils_io import read_json_file
        try:
            # 加载事件数据
            self.events = read_json_file(event_file)
            # 加载人物画像数据
            self.persona = read_json_file(persona_file)
            # 加载位置数据
            self.loc_data = read_json_file(loc_data)
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

    def run_daily_event_with_threading(self, start_date, end_date, max_workers=5, interval_days=2):
        """
        使用分片并行模式生成指定日期范围内的事件（委托给 DailySimulationEngine）。

        参数:
            start_date: 起始日期，格式如 "2025-01-01"
            end_date: 结束日期，格式如 "2025-01-05"
            max_workers: 最大并行区间数（默认5）
            interval_days: 每个串行区间的天数（默认2）

        返回:
            List: 执行结果列表
        """
        def mind_factory():
            # 使用人物的 instance_id 作为标识，确保每个人只有一个 memory 文件
            return Mind(
                file_path=self.data_dir,
                instance_id=self.instance_id,
                persona=self.persona,
                event=self.events,
                daily_state=None,
                persona_address_data=self.loc_data
            )

        engine = DailySimulationEngine(
            mind_factory=mind_factory,
            events=self.events,
            persona=self.persona,
            daily_draft=self.daily_state,
            checkpoint_dir=os.path.join(self.data_dir, "sim"),
            instance_id=self.instance_id,
        )
        return engine.run(
            start_date=start_date,
            end_date=end_date,
            max_workers=max_workers,
            interval_days=interval_days,
        )
