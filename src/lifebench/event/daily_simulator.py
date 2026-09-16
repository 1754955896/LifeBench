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
from src.lifebench.event.simulation.state import CognitiveState, LongTermMemory
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
from src.lifebench.event.simulation.preparation import SimulationAssetPreparer
from src.lifebench.event.simulation.telemetry import MemoryTraceRecorder
from src.lifebench.event.simulation.geolocation import build_location_records
from src.lifebench.event.simulation.geolocation.baseline import simple_allocate_trajectory
from src.lifebench.event.simulation.geolocation.catalog import flatten_location_data
from src.lifebench.event.simulation.context import (
    append_daily_behavior_record,
    build_daily_behavior_record,
)


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
        self.thought = ""  # 记录个人的感受、想法，包括情绪、想法、需求及思考过程中的打算
        self.short_memory_context = {}  # 带日期和检索来源的短记忆结构
        self.next_day_context = {}  # reflection 生成的下一日状态、需求和未完成事项
        self.last_subjective_context = None
        self.last_trajectory_intent_diagnostics = None
        self.last_optional_activity_plan = {}
        self.last_optional_activity_result = {}
        self.last_optional_activity_diagnostics = {}
        # In-run stage cache: a downstream failure can retry from that stage
        # without paying again for already completed subjective/objective calls.
        self._daily_stage_cache = {}
        self.trajectory_location_history = []  # 最终采用地点的跨日稳定注册表
        self.behavior_history = []  # 最近30天结构化活动与移动摘要
        # 人物级只读地点资产；保留 v2 分层结构供每日地点灵感抽样。
        self.persona_location_data = copy.deepcopy(persona_address_data or [])
        self.assets_prepared = False
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
        # 是否开启真实地理匹配；关闭时跳过真实地理搜索，直接由 LLM 在 adjust 阶段统一分配地点
        self.enable_real_geo = True
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
        # 与地图工具共享归一化后的扁平地址目录，兼容历史 location.json 多层数组格式。
        self.persona_address_data = list(self.maptools.persona_address_data)
        # cognition 只应看到人物已知、稳定的地点。城市机会池是每日抽样用的
        # “可能选项”，若整池注入自我认知，LLM 会把未访问 POI 误写成熟悉地点。
        self.persona_core_address_data = [
            row for row in flatten_location_data(persona_address_data or [])
            if str(row.get("location_role") or "") not in {
                "city_reference", "social_location",
            }
        ]
        
    def save_to_json(self):
        data = {}
        data["persona"] =  self.persona
        data["context"] = self.context
        data["cognition"] = self.cognition
        data["long_memory"] = self.long_memory
        data["thought"] = self.thought
        data['env'] = self.env
        data["short_memory_context"] = self.short_memory_context
        data["next_day_context"] = self.next_day_context
        data["trajectory_location_history"] = self.trajectory_location_history
        data["behavior_history"] = self.behavior_history
        
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
            thought=self.thought,
            cognition=self.cognition,
            context=self.context,
            env=self.env,
            short_memory_context=self.short_memory_context,
            next_day_context=self.next_day_context,
            trajectory_location_history=self.trajectory_location_history,
            behavior_history=self.behavior_history,
        )

    def restore_cognitive_state(self, state: CognitiveState) -> None:
        """从结构化认知状态恢复字段。"""
        self.long_memory = state.long_memory
        self.thought = state.thought
        self.cognition = state.cognition
        self.context = state.context
        self.env = state.env
        self.short_memory_context = state.short_memory_context
        self.next_day_context = state.next_day_context
        self.trajectory_location_history = state.trajectory_location_history
        self.behavior_history = state.behavior_history

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
            if self.assets_prepared:
                raise RuntimeError("预处理已完成但模糊记忆资产缺失，禁止在日期分片中重新生成")
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
        prompt = t1.format(
            persona=self.persona,
            persona_address_data=self.persona_core_address_data,
        )
        res = self.llm_call_s(prompt)
        self.cognition = res

        prompt = t2.format(persona=self.persona)
        res = self.llm_call_s(prompt)
        self.context = res

        # 将模糊记忆整理为新的四字段长期记忆冷启动快照。
        self.seed_long_term_memory()

        self.persona_withoutrl = persona.copy()
        if "relation" in self.persona_withoutrl:
            del self.persona_withoutrl["relation"]

    def seed_long_term_memory(self):
        """把画像之外的模糊历史整理为四字段长期记忆。"""
        from src.lifebench.utils.llm_call import llm_call_j
        from src.lifebench.utils.json_utils import remove_json_wrapper

        prompt = '''
请基于以下信息初始化一份有界长期记忆，严格输出四字段 JSON。
各字段含义：
- profile_changes：相对基础画像已经发生的长期变化，没有则为空字符串。
- persistent_patterns：历史反复验证的稳定偏好、习惯和关系模式，字符串数组，最多20条。
- key_memories：重要且会持续影响后续行为的经历，最多20条；每项包含date、content、impact。
- period_summary：当前生活阶段的简洁概括。

要求：
1. 人物基础画像只是判断基线，不要把画像原文重复写入 profile_changes。
2. profile_changes 只记录已经发生且会持续影响后续生活的重大画像变化，如居住、职业、长期健康、家庭结构、明确关系、持续职责或经济状态变化。普通心情、疲劳、临时压力、一次互动或一次尝试不得写入。
3. persistent_patterns 只记录模糊历史中明确表达形成的长期习惯/偏好，或至少3个不同日期反复出现的稳定行为。单次尝试、偶尔行为和同一天重复提及不得写入。
4. 不保存即时状态、临时需求、未来计划或地点地址；证据不足时保持为空，不得从基础画像推测变化。
5. 仅输出 JSON 对象，无任何额外文本或代码块标记。

个人画像：{persona}
自我认知：{cognition}
模糊记忆（草稿派生总结）：{fuzzy}

输出格式：
{{"profile_changes":"...","persistent_patterns":["..."],"key_memories":[{{"date":"YYYY-MM-DD","content":"...","impact":"..."}}],"period_summary":"..."}}
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
            self.long_memory = LongTermMemory().to_string()
            print(f"[seed_long_term_memory] 结构化种子生成失败，使用空四字段长期记忆：{str(e)}")

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
        self.thought = d['thought']
        self.env = d['env']
        self.cognition = d['cognition']
        self.context = d['context']
        self.short_memory_context = d.get("short_memory_context", {})
        self.next_day_context = d.get("next_day_context", {})
        self.trajectory_location_history = d.get("trajectory_location_history", [])
        self.behavior_history = d.get("behavior_history", [])
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
            
            # 2. 只获取当月1日至目标日前一天的事件，禁止把目标日草稿提前当成记忆。
            start_of_month = datetime(year, month, 1).strftime("%Y-%m-%d")
            end_of_month = (target_date - timedelta(days=1)).strftime("%Y-%m-%d")
            
            # 提取当月到目标日期的事件
            events_this_month = []
            for d in range(1, day):
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
                你是一位记忆专家，请基于以下个人画像和{start_of_month}到{end_of_month}的事件，仅聚焦于以下信息进行总结：
                
                1. 截至目标日前一天，个人近期主要做了什么
                2. 最近一次已知的位置和持续状态信息
                3. 近期已发生事件可能延续到目标日的影响
                4. 目标日前最后可知的状态及其历史原因
                
                个人画像：{json.dumps(self.persona, ensure_ascii=False, indent=2)}
                
                {start_of_month}到{end_of_month}的事件：
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
                combined_memory = f"{cumulative_memory}\n\n{start_of_month}到{end_of_month}的重要事件：\n{monthly_summary}"
            else:
                combined_memory = cumulative_memory
            
            return combined_memory
            
        except Exception as e:
            print(f"获取模糊长期记忆时出错：{e}")
            # 出错时返回空记忆
            return ""

    def _is_simple_geo_mode(self):
        """朴素地理基线是否启用（allocation_mode == simple 且模块开启）。"""
        cfg = self.config.get("trajectory_assignment", {}) if isinstance(self.config, dict) else {}
        return bool(cfg.get("enabled", True)) and cfg.get("allocation_mode", "full") == "simple"

    def map(self, pt, plan=None):
        """获取真实poi数据和通行信息（委托给轨迹生成器）。"""
        if self._is_simple_geo_mode():
            # 朴素基线只替换“分配”这一步，产出与完整版相同的 TrajectoryAssignment
            # 与 poi 参考串；下游 adjust event → 回填 → 通行统计复用完整版。
            return simple_allocate_trajectory(self, pt, plan)
        return generate_poi_route(self, pt, plan)

    def daily_event_gen1(self, date):
        """
        生成单日事件的核心方法

        参数:
            date: 目标日期（格式：YYYY-MM-DD）

        返回:
            bool: 执行是否成功的标志
        """
        try:
            stage_cache = self._daily_stage_cache.setdefault(date, {})
            stage_cache_hits = []
            # 地理位置分配的随机种子、追踪记录和复现均以正在处理的日期为准。
            self.current_date = date
            self._log_event(f"\n=== 开始生成 {date} 的事件 ===")
            # 1. 生成主观思考
            plan = self.get_plan4(date)
            print("[DEBUG daily_event_gen1] plan type=" + str(type(plan)) + ", keys=" + str(list(plan.keys()) if isinstance(plan, dict) else "N/A"))
            if isinstance(plan, dict) and "events" in plan:
                print("[DEBUG daily_event_gen1] plan events count=" + str(len(plan.get("events", []))))
            if "subjective_thought" in stage_cache:
                subjective_thought = stage_cache["subjective_thought"]
                self.last_subjective_context = copy.deepcopy(
                    stage_cache.get("subjective_context") or {}
                )
                self.last_optional_activity_plan = copy.deepcopy(
                    stage_cache.get("optional_activity_plan") or {}
                )
                stage_cache_hits.append("subjective_thought")
            else:
                subjective_thought = self._generate_subjective_thought(plan, date)
                stage_cache["subjective_thought"] = subjective_thought
                stage_cache["subjective_context"] = copy.deepcopy(
                    self.last_subjective_context or {}
                )
                stage_cache["optional_activity_plan"] = copy.deepcopy(
                    self.last_optional_activity_plan
                )

            # 2. 生成客观事件
            if "objective_events" in stage_cache:
                objective_events = stage_cache["objective_events"]
                self.last_optional_activity_plan = copy.deepcopy(
                    stage_cache.get("optional_activity_plan") or {}
                )
                self.last_optional_activity_result = copy.deepcopy(
                    stage_cache.get("optional_activity_result") or {}
                )
                self.last_optional_activity_diagnostics = copy.deepcopy(
                    stage_cache.get("optional_activity_diagnostics") or {}
                )
                stage_cache_hits.append("objective_events")
            else:
                objective_events = self._generate_objective_events(
                    plan, date, subjective_thought
                )
                stage_cache["objective_events"] = objective_events
                stage_cache["optional_activity_plan"] = copy.deepcopy(
                    self.last_optional_activity_plan
                )
                stage_cache["optional_activity_result"] = copy.deepcopy(
                    self.last_optional_activity_result
                )
                stage_cache["optional_activity_diagnostics"] = copy.deepcopy(
                    self.last_optional_activity_diagnostics
                )
            # 3. 获取POI数据并调整轨迹
            if "poi_data" in stage_cache:
                poi_data = stage_cache["poi_data"]
                self.last_trajectory_assignment = stage_cache.get(
                    "trajectory_assignment"
                )
                self.last_activity_plan = copy.deepcopy(
                    stage_cache.get("activity_plan")
                )
                self.last_trajectory_intent_diagnostics = copy.deepcopy(
                    stage_cache.get("trajectory_intent_diagnostics")
                )
                stage_cache_hits.append("trajectory_assignment")
            else:
                if getattr(self, "enable_real_geo", True):
                    poi_data = self.map(objective_events, plan)
                else:
                    # 关闭真实地理匹配：跳过真实地理搜索，直接由 LLM 在 adjust 阶段统一分配地点
                    poi_data = ""
                    self.last_trajectory_assignment = None
                stage_cache["poi_data"] = poi_data
                stage_cache["trajectory_assignment"] = getattr(
                    self, "last_trajectory_assignment", None
                )
                stage_cache["activity_plan"] = copy.deepcopy(
                    getattr(self, "last_activity_plan", None)
                )
                stage_cache["trajectory_intent_diagnostics"] = copy.deepcopy(
                    getattr(self, "last_trajectory_intent_diagnostics", None)
                )
            # 从plan2中获取当日事件参考数据
            if "adjusted_events" in stage_cache:
                adjusted_events = stage_cache["adjusted_events"]
                self.final_location_records = copy.deepcopy(
                    stage_cache.get("final_location_records")
                )
                self.last_location_reconciliation = copy.deepcopy(
                    stage_cache.get("location_reconciliation")
                )
                stage_cache_hits.append("adjusted_events")
            else:
                # 简单模式与完整版共用同一条下游：adjust event → reconcile/回填 →
                # 通行统计；差异只在 map() 阶段的“分配”算法。
                adjusted_events = self._adjust_event_trajectory(
                    poi_data, objective_events, plan, self.get_plan4(date, -1)
                )
                stage_cache["adjusted_events"] = adjusted_events
                stage_cache["final_location_records"] = copy.deepcopy(
                    getattr(self, "final_location_records", None)
                )
                stage_cache["location_reconciliation"] = copy.deepcopy(
                    getattr(self, "last_location_reconciliation", None)
                )

            # 4. 生成反思和更新想法
            if "reflection" in stage_cache:
                reflection = copy.deepcopy(stage_cache["reflection"])
                stage_cache_hits.append("reflection")
            else:
                reflection = self._generate_reflection(adjusted_events, plan, date)
                stage_cache["reflection"] = copy.deepcopy(reflection)
            self.thought = reflection.get("thought") or self.thought
            self.next_day_context = copy.deepcopy(
                reflection.get("next_day_context", {})
            )

            # 5. reflection 已在同一次 LLM 调用中生成完整长期记忆快照。
            self.long_memory = LongTermMemory.from_dict(
                reflection.get("long_memory", {})
            ).to_string()

            # 6. 更新短期记忆并保存数据
            if not stage_cache.get("short_memory_updated"):
                self.update_short_memory(reflection, date)
                stage_cache["short_memory_updated"] = True

            # 7. 用最终结构化行程更新跨日行为摘要；只统计事实，不解析自然语言。
            assignment = getattr(self, "last_trajectory_assignment", None)
            assignment_data = assignment.to_dict() if assignment is not None else None
            location_records = getattr(self, "final_location_records", None)
            if location_records is None:
                location_records = build_location_records(assignment) if assignment is not None else None
            from src.lifebench.event.simulation.geolocation import (
                build_half_hour_trajectory, write_half_hour_trajectory,
            )
            trajectory_config = self.config.get("trajectory_assignment", {}) if isinstance(self.config, dict) else {}
            export_config = trajectory_config.get("half_hour_export", {}) if isinstance(trajectory_config, dict) else {}
            export_enabled = export_config.get("enabled", True) if isinstance(export_config, dict) else True
            half_hour_trajectory = build_half_hour_trajectory(
                location_records, date=date, instance_id=self.instance_id,
                slot_minutes=int(export_config.get("slot_minutes", 30) or 30),
            ) if export_enabled else None
            if half_hour_trajectory is not None:
                half_hour_path = os.path.join(
                    self.sim_dir, "half_hour",
                    "half_hour_%s_%s.jsonl" % (
                        self.instance_id, getattr(self, "interval_start", None) or "unknown",
                    ),
                )
                write_half_hour_trajectory(half_hour_path, half_hour_trajectory)
            subjective_context = getattr(self, "last_subjective_context", None) or {}
            behavior_record = build_daily_behavior_record(
                date=date,
                location_records=location_records,
                reflection=reflection,
                history=self.behavior_history,
                day_variation_context=subjective_context.get("day_variation_context", {}),
            )
            self.behavior_history = append_daily_behavior_record(
                self.behavior_history, behavior_record
            )

            # 8. 保存每日中间输出到实例变量
            self.daily_intermediate_outputs[date] = {
                "plan": plan,
                "subjective_thought": subjective_thought,
                "subjective_context": subjective_context,
                "recent_behavior_summary": copy.deepcopy(
                    subjective_context.get("recent_behavior_summary", {})
                ),
                "day_variation_context": copy.deepcopy(
                    subjective_context.get("day_variation_context", {})
                ),
                "mobility_day_budget": copy.deepcopy(
                    subjective_context.get("mobility_day_budget", {})
                ),
                "mobility_day_profile": copy.deepcopy(
                    subjective_context.get("mobility_day_profile", {})
                ),
                "location_inspiration_context": copy.deepcopy(
                    subjective_context.get("location_inspiration_context", {})
                ),
                "activity_recommendation": copy.deepcopy(
                    subjective_context.get("activity_recommendation", {})
                ),
                "stage_cache_hits": stage_cache_hits,
                "trajectory_intent_diagnostics": copy.deepcopy(
                    getattr(self, "last_trajectory_intent_diagnostics", None)
                ),
                "optional_activity_plan": copy.deepcopy(
                    getattr(self, "last_optional_activity_plan", {})
                ),
                "optional_activity_result": copy.deepcopy(
                    getattr(self, "last_optional_activity_result", {})
                ),
                "optional_activity_diagnostics": copy.deepcopy(
                    getattr(self, "last_optional_activity_diagnostics", {})
                ),
                "objective_events": objective_events,
                "activity_plan": getattr(self, "last_activity_plan", None),
                "poi_data": poi_data,
                "trajectory_assignment": assignment_data,
                "location_records": location_records,
                "final_event_segments": (
                    copy.deepcopy(location_records.get("event_segments", []))
                    if isinstance(location_records, dict) else []
                ),
                "half_hour_trajectory": half_hour_trajectory,
                "location_reconciliation": copy.deepcopy(
                    getattr(self, "last_location_reconciliation", None)
                ),
                "adjusted_events": adjusted_events,
                "reflection": reflection,
                "next_day_context": copy.deepcopy(self.next_day_context),
                "daily_behavior_record": behavior_record,
            }

            # 9. 保存当前状态
            self.save_to_json()
            self.save_intermediate_outputs()
            # self._save_events_to_file()

            self._log_event(f"\n=== {date} 的事件生成完成 ===")
            self._daily_stage_cache.pop(date, None)
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
    
class MindController:
    """
    Mind类的并行化控制器，用于管理多个Mind实例的并行执行
    """
        
    def __init__(self, event_file='event.json', persona_file='persona.json', data_dir='data/2025-12-07', daily_state_file='daily_state.json', instance_id=0, loc_data='location.json', enable_real_geo=True):
        """
        初始化MindController实例

        参数:
            event_file: 事件数据文件路径
            persona_file: 人物画像数据文件路径
            data_dir: 数据存储目录
            daily_state_file: 每日状态数据文件路径
            instance_id: 人物实例ID，用于确保每个人只有一个memory文件
            enable_real_geo: 是否开启真实地理匹配（True 开启；False 跳过真实地理搜索，由 LLM 统一分配）
        """
        self.data_dir = data_dir
        self.instance_id = instance_id
        self.enable_real_geo = enable_real_geo
        self.event_file = event_file
        self.persona_file = persona_file
        self.location_file = os.path.abspath(loc_data)
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
        # Shared assets must be produced once before ThreadPoolExecutor creates shards.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
        with open(os.path.join(project_root, 'config', 'config.json'), 'r', encoding='utf-8') as file:
            simulation_config = json.load(file)
        prepared = SimulationAssetPreparer(
            data_dir=self.data_dir,
            persona=self.persona,
            events=self.events,
            location_data=self.loc_data,
            location_path=self.location_file,
            config=simulation_config,
            simulation_start=start_date,
        ).prepare()
        self.loc_data = prepared["location_data"]
        asset_snapshot = prepared["asset_snapshot"]

        def mind_factory():
            # 使用人物的 instance_id 作为标识，确保每个人只有一个 memory 文件
            mind = Mind(
                file_path=self.data_dir,
                instance_id=self.instance_id,
                persona=self.persona,
                event=self.events,
                daily_state=None,
                persona_address_data=self.loc_data
            )
            mind.assets_prepared = True
            mind.asset_snapshot = copy.deepcopy(asset_snapshot)
            mind.enable_real_geo = self.enable_real_geo
            return mind

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
