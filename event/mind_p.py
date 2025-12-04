import json
import re
import copy
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Set, Callable
from openai import OpenAI
import holidays  # 需提前安装：pip install holidays


# ------------------------------ 全局配置常量 ------------------------------
class Config:
    """全局配置常量"""
    # LLM配置
    OPENAI_API_KEY = "sk-e90f17355573420597c914ef38a58239"
    OPENAI_BASE_URL = "https://api.deepseek.com"

    # 地图工具配置
    MAP_API_KEY = "e8f87eef67cfe6f83e68e7a65b9b848b"

    # 文件路径配置
    DEFAULT_DATA_PATH = "./data/"
    DEFAULT_LOG_PATH = "./data/log.txt"
    DEFAULT_RECORD_PATH = "record.json"
    DEFAULT_EVENT_PATH = "./data/event_update.json"

    # 线程配置
    THREAD_TIMEOUT = 600  # 10分钟
    LOCK_TIMEOUT = 10  # 锁超时时间（秒）


# ------------------------------ 基础工具类（无状态） ------------------------------
class BasicToolkit:
    """基础通用工具（纯静态方法，无状态）"""

    @staticmethod
    def is_date_match(target_date_str: str, event_date_str: str) -> bool:
        """判断事件日期是否包含目标日期（支持单个日期/日期范围）"""
        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"目标日期格式错误：{target_date_str}，需符合YYYY-MM-DD")

        if "至" in event_date_str:
            try:
                start_str, end_str = event_date_str.split("至")
                start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d").date()
                end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(f"事件日期格式错误：{event_date_str}，范围需符合YYYY-MM-DD至YYYY-MM-DD")
            return start_date <= target_date <= end_date
        else:
            try:
                event_date = datetime.strptime(event_date_str.strip(), "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(f"事件日期格式错误：{event_date_str}，单个日期需符合YYYY-MM-DD")
            return event_date == target_date

    @staticmethod
    def extract_start_date(date_str: str) -> str:
        """从时间字符串中提取起始日期（兼容区间/单个时间）"""
        if "至" in date_str:
            start_time_part = date_str.split("至")[0].strip()
        else:
            start_time_part = date_str.strip()

        supported_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H"
        ]

        for fmt in supported_formats:
            try:
                start_datetime = datetime.strptime(start_time_part, fmt)
                return start_datetime.strftime("%Y-%m-%d")
            except ValueError:
                continue

        raise ValueError(
            f"时间格式不支持！请输入以下格式之一：\n"
            f"1. 时间区间（如'2025-01-01 07:30:00至2025-01-01 08:45:00'）\n"
            f"2. 单个时间（如'2025-01-01 07:30:00'或'2025-01-01'）\n"
            f"当前输入：{date_str}"
        )

    @staticmethod
    def parse_date(date_str: str) -> Tuple[datetime, datetime]:
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

    @staticmethod
    def get_date_string(date_str: str, country: str = "CN") -> str:
        """生成包含日期、周几和节日的格式化字符串"""
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            weekday_map = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            weekday = weekday_map[date_obj.weekday()]

            country_holidays = holidays.CountryHoliday(country)
            holidays_list = []
            if date_obj in country_holidays:
                raw_holidays = country_holidays.get(date_obj)
                holidays_list = raw_holidays if isinstance(raw_holidays, list) else [raw_holidays]
            festival_str = "，".join(holidays_list) if holidays_list else ""

            parts = [date_str, weekday]
            if festival_str:
                parts.append(festival_str)
            return "，".join(parts)

        except ValueError:
            return "日期格式错误，请使用'YYYY-MM-DD'格式"

    @staticmethod
    def get_next_n_day(date_str: str, n: int) -> str:
        """获取字符串日期的n天后/前日期"""
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            next_day_obj = date_obj + timedelta(days=n)
            return next_day_obj.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(f"日期格式错误：{date_str}，请使用YYYY-MM-DD格式")

    @staticmethod
    def remove_json_wrapper(s: str) -> str:
        """去除JSON包装符并清理非法字符"""
        # 去除```json标记
        pattern = r'^\s*```json\s*\n?|\s*```\s*$'
        result = re.sub(pattern, '', s, flags=re.MULTILINE)

        # 清理非法控制字符
        valid_pattern = r'[^\x20-\x7E\n\r\t\b\f\u4E00-\u9FFF\u3000-\u303F\uFF00-\uFFEF\u2000-\u206F\u2E80-\u2EFF]'
        result = re.sub(valid_pattern, '', result)

        # 规范化格式
        result = result.strip()
        result = result.replace('\u3000', ' ')
        result = re.sub(r'\r\n?', '\n', result)
        result = re.sub(r'\n+', '\n', result)

        return result


# ------------------------------ 资源模块（有状态，可全局复用） ------------------------------
class MapModule:
    """地图模块（全局单例，统一管理地图工具）"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, api_key: str = Config.MAP_API_KEY):
        """单例模式创建"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.api_key = api_key
                cls._instance._init_tools()
            return cls._instance

    def _init_tools(self):
        """初始化地图工具（实际实现需替换）"""
        self.map_tool = MapMaintenanceTool(self.api_key)

    def get_poi_route(self, persona: str, data: str) -> str:
        """统一POI和路线获取接口"""
        from llm_utils import llm_call_skip  # 实际项目中需确保导入

        # 第一轮POI分析
        prompt = template_get_poi3.format(persona=persona, data=data)
        res = llm_call_skip(prompt, "")  # context后续从共享数据获取
        print("poi分析-----------------------------------------------------------------------")
        print(res)

        # 调用地图工具
        data_json = json.loads(res)
        result, error_summary = self.map_tool.process_instruction_route(data_json)
        instr = self.map_tool.extract_route_summary(result)
        print(instr)

        # 第二轮POI优化
        prompt = template_get_poi2.format(
            persona=persona,
            data=data,
            first_round_instruction=res,
            api_feedback=instr
        )
        res = llm_call_skip(prompt, "")
        print("poi分析2-----------------------------------------------------------------------")
        print(res)

        # 再次调用地图工具
        data_json = json.loads(res)
        resultx, error_summary = self.map_tool.process_instruction_route(data_json)
        instr = self.map_tool.extract_poi_route_simplified(resultx)
        print(instr)

        return instr

    def reset(self):
        """重置地图工具实例"""
        with self._lock:
            self._init_tools()


class MemoryModule:
    """记忆模块（全局单例/多例可选，统一管理记忆操作）"""
    _instances: Dict[str, "MemoryModule"] = {}
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, instance_id: str = "default") -> "MemoryModule":
        """获取实例（支持多实例，默认单例）"""
        with cls._lock:
            if instance_id not in cls._instances:
                cls._instances[instance_id] = cls()
                cls._instances[instance_id]._init_memory_manager()
            return cls._instances[instance_id]

    def _init_memory_manager(self):
        """初始化记忆管理器（实际实现需替换）"""
        from memory_manager import PersonalMemoryManager  # 实际项目中需确保导入
        self.mem_mgr = PersonalMemoryManager()

    def add_memory(self, data: Any):
        """添加记忆"""
        self.mem_mgr.add_memory(data)

    def search_by_date(self, start_time: str) -> List[Dict]:
        """按日期检索记忆"""
        return self.mem_mgr.search_by_date(start_time)

    def search_by_topic_embedding(self, topic: str, top_k: int) -> List[Dict]:
        """按主题向量检索记忆"""
        return self.mem_mgr.search_by_topic_embedding(topic, top_k)

    def update_short_memory(self, dailyevent: Any, date: str) -> str:
        """统一更新短期记忆（封装原有逻辑）"""

        # 生成目标日期集合
        def get_target_dates(date_str: str) -> List[str]:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
            dates = [target_date - timedelta(days=i) for i in range(0, 4)]
            return [d.strftime("%Y-%m-%d") for d in dates]

        def get_next_day(date_str: str) -> str:
            current_date = datetime.strptime(date_str, "%Y-%m-%d")
            next_day = current_date + timedelta(days=1)
            return next_day.strftime("%Y-%m-%d")

        def get_cycle_dates_array(date_str: str) -> List[str]:
            current_date = datetime.strptime(date_str, "%Y-%m-%d")
            # 上个月同日
            try:
                last_month_day = current_date.replace(month=current_date.month - 1)
            except ValueError:
                last_month_day = current_date.replace(day=1) - timedelta(days=1)
            # 上周同星期
            last_week_weekday = current_date - timedelta(days=7)
            return [
                last_month_day.strftime("%Y-%m-%d"),
                last_week_weekday.strftime("%Y-%m-%d")
            ]

        # 收集记忆数据
        date_set: Set[str] = set()
        mem = ""

        # 前4天事件
        for i in get_target_dates(date):
            res = self.search_by_date(start_time=i)
            for j in res:
                mem += j['events']
                date_set.add(j['date'])

        # 周期事件（上月同日、上周同星期）
        for i in get_cycle_dates_array(get_next_day(date)):
            res = self.search_by_date(start_time=i)
            for j in res:
                mem += j['events']
                date_set.add(j['date'])

        # 相似事件
        next_day = get_next_day(date)
        from global_tool_center import GlobalToolCenter  # 循环导入需注意
        events = GlobalToolCenter.get_instance().basic_toolkit.filter_by_date(next_day)
        res_topic = ""
        for item in events:
            res_topic += item['name']
        res = self.search_by_topic_embedding(res_topic, 2)
        for i in res:
            if i['date'] not in date_set:
                mem += i['events']

        return mem

    @classmethod
    def destroy_instance(cls, instance_id: str = "default"):
        """销毁指定实例"""
        with cls._lock:
            if instance_id in cls._instances:
                del cls._instances[instance_id]


class LLMModule:
    """LLM模块（全局单例，统一管理LLM调用）"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.client = OpenAI(
                    api_key=Config.OPENAI_API_KEY,
                    base_url=Config.OPENAI_BASE_URL
                )
            return cls._instance

    def call_reason(self, prompt: str, context: str, record: int = 0) -> str:
        """调用reasoner模型（统一接口）"""
        from llm_utils import llm_call_reason  # 实际实现需替换
        return llm_call_reason(prompt, context, record=record)

    def call_chat(self, prompt: str, context: str, record: int = 0) -> str:
        """调用chat模型（统一接口）"""
        from llm_utils import llm_call  # 实际实现需替换
        return llm_call(prompt, context, record=record)

    def call_skip(self, prompt: str, context: str) -> str:
        """调用skip模型（统一接口）"""
        from llm_utils import llm_call_skip  # 实际实现需替换
        return llm_call_skip(prompt, context)


class FileModule:
    """文件模块（全局单例，统一管理文件读写）"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def write_to_txt(self, content: str, date: str, section: str, file_path: str = Config.DEFAULT_LOG_PATH) -> None:
        """统一文本写入"""
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                header = f"date:{date}\n-----------------------{section}\n" if section == "t1" else f"-----------------------{section}\n"
                f.write(header + content + "\n")
        except Exception as e:
            raise RuntimeError(f"【{date}】写入文本文件失败: {str(e)}")

    def safe_json_dump(self, data: Any, file_path: str) -> None:
        """安全JSON写入"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise RuntimeError(f"写入JSON文件失败({file_path}): {str(e)}")

    def json_load(self, file_path: str) -> Dict:
        """安全JSON读取"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception as e:
            raise RuntimeError(f"读取JSON文件失败({file_path}): {str(e)}")


# ------------------------------ 全局工具中心（统一入口） ------------------------------
class GlobalToolCenter:
    """全局工具中心（所有工具的统一调用入口）"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                # 初始化所有工具模块
                cls._instance.basic_toolkit = BasicToolkit()
                cls._instance.map_module = MapModule()
                cls._instance.memory_module = MemoryModule.get_instance()
                cls._instance.llm_module = LLMModule()
                cls._instance.file_module = FileModule()
            return cls._instance

    @classmethod
    def get_instance(cls) -> "GlobalToolCenter":
        """获取全局工具中心实例"""
        return cls()

    # ------------------------------ 快捷调用方法 ------------------------------
    def get_poi_route(self, persona: str, data: str) -> str:
        """快捷调用地图模块获取POI路线"""
        return self.map_module.get_poi_route(persona, data)

    def update_short_memory(self, dailyevent: Any, date: str, mem_instance_id: str = "default") -> str:
        """快捷调用记忆模块更新短期记忆"""
        return MemoryModule.get_instance(mem_instance_id).update_short_memory(dailyevent, date)

    def llm_call(self, prompt: str, context: str, model_type: str = "chat", record: int = 0) -> str:
        """统一LLM调用入口"""
        if model_type == "reason":
            return self.llm_module.call_reason(prompt, context, record)
        elif model_type == "chat":
            return self.llm_module.call_chat(prompt, context, record)
        elif model_type == "skip":
            return self.llm_module.call_skip(prompt, context)
        else:
            raise ValueError(f"不支持的模型类型：{model_type}")

    def save_record(self, data: Dict, file_path: str = Config.DEFAULT_RECORD_PATH):
        """统一保存记录"""
        self.file_module.safe_json_dump(data, file_path)

    def load_record(self, file_path: str = Config.DEFAULT_RECORD_PATH) -> Dict:
        """统一加载记录"""
        return self.file_module.json_load(file_path)


# ------------------------------ 共享数据中心 ------------------------------
class SharedMindData:
    """全局共享数据中心（线程安全）"""
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._data = {
                    "persona": "",
                    "persona_withoutrl": {},
                    "context": "",
                    "cognition": "",
                    "env": ""
                }
            return cls._instance

    # 线程安全的读写方法
    def get(self, key: str) -> Any:
        with self._lock:
            return copy.deepcopy(self._data.get(key))

    def set(self, key: str, value: Any):
        with self._lock:
            self._data[key] = value

    def batch_set(self, data: Dict):
        with self._lock:
            self._data.update(data)

    def reset(self):
        """重置共享数据"""
        with self._lock:
            self._data = {
                "persona": "",
                "persona_withoutrl": {},
                "context": "",
                "cognition": "",
                "env": ""
            }


# ------------------------------ 业务实例（仅保留业务逻辑） ------------------------------
class MindInstance:
    """业务实例（仅包含核心业务逻辑，工具调用依赖全局工具中心）"""

    def __init__(self, file_path: str = Config.DEFAULT_DATA_PATH, mem_instance_id: str = "default"):
        # 全局工具中心
        self.tool_center = GlobalToolCenter.get_instance()
        # 共享数据
        self.shared_data = SharedMindData()
        # 私有数据
        self.calendar: Dict[str, List[str]] = {}
        self.events: List[Dict] = []
        self.long_memory: str = ""
        self.short_memory: str = ""
        self.reflection: str = ""
        self.thought: str = ""
        self.bottom_events: Optional[List[Dict]] = None
        # 配置
        self.file_path = file_path
        self.txt_file_path = Config.DEFAULT_LOG_PATH
        self.mem_instance_id = mem_instance_id
        # 线程锁
        self._lock = threading.Lock()

    # ------------------------------ 核心业务方法 ------------------------------
    def load_from_json(self, event: List[Dict], persona: Dict[str, Any], record: int = 1) -> bool:
        """加载初始数据"""
        with self._lock:
            # 设置私有事件数据
            self.events = copy.deepcopy(event)
            self.long_memory = ""
            self.short_memory = ""

            # 加载共享数据
            self.shared_data.set("persona", copy.deepcopy(persona))
            if record == 1:
                d = self.tool_center.load_record()
                self.shared_data.batch_set({
                    "cognition": d.get("cognition", ""),
                    "context": d.get("context", ""),
                    "env": d.get("env", "")
                })
                self.long_memory = d.get("long_memory", "")
                self.short_memory = d.get("short_memory", "")
                self.thought = d.get("thought", "")
            else:
                self._init_cognition_and_context()

            # 处理persona_withoutrl
            persona_withoutrl = copy.deepcopy(persona)
            persona_withoutrl.pop("relation", None)
            self.shared_data.set("persona_withoutrl", persona_withoutrl)

            # 初始化底层事件缓存
            self._get_bottom_level_events()
            return False

    def _init_cognition_and_context(self):
        """初始化认知和上下文"""
        persona = self.shared_data.get("persona")

        # 生成cognition
        prompt_cog = '''
        请你基于下面的个人画像，以第一人称视角描述你对自己的自我认知，包括1）个人基本信息。2）工作的主要特征、内容、方式、习惯、主要人物。3）家庭的主要特征、内容、方式、习惯、主要人物。4）其他生活的主要特征、内容、方式、习惯、主要人物。5）平常工作日的常见安排，目前的主要每天安排。
        个人画像：{persona}
        '''.format(persona=persona)
        cog_res = self.tool_center.llm_call(prompt_cog, "", model_type="chat")
        self.shared_data.set("cognition", cog_res)
        print(f"初始化认知：{cog_res}")

        # 生成context
        prompt_ctx = '''
        请你基于下面的个人画像，设计一句让大模型扮演该角色的context，以”你是一位“开头。不超过50个字，只保留重要信息。
        个人画像：{persona}
        '''.format(persona=persona)
        ctx_res = self.tool_center.llm_call(prompt_ctx, "", model_type="chat")
        self.shared_data.set("context", ctx_res)
        print(f"初始化上下文：{ctx_res}")

    def _get_bottom_level_events(self) -> List[Dict]:
        """递归提取最底层事件"""
        if self.bottom_events is not None:
            print("已计算过，直接返回缓存")
            return self.bottom_events

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

    def update_bottom_level_events(self) -> List[Dict]:
        """重新提取底层事件"""

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

    def filter_by_date(self, target_date: str) -> List[Dict]:
        """筛选指定日期的最底层事件"""
        bottom_events = self._get_bottom_level_events()
        matched = []
        for event in bottom_events:
            date_values = event.get("date", [])
            if not isinstance(date_values, list):
                date_values = [date_values]

            for date_str in date_values:
                date_str = self.tool_center.basic_toolkit.extract_start_date(date_str)
                if self.tool_center.basic_toolkit.is_date_match(target_date, date_str):
                    matched.append(event)
                    break
        return matched

    def filter_events_by_start_range(self, events_data: List[Dict], start_range_str: str, end_range_str: str) -> List[
        Dict]:
        """筛选指定时间范围的顶层事件"""
        try:
            start_range = datetime.strptime(start_range_str, "%Y-%m-%d")
            end_range = datetime.strptime(end_range_str, "%Y-%m-%d")
        except ValueError:
            raise ValueError("日期格式错误，请使用'YYYY-MM-DD'格式")

        if start_range > end_range:
            raise ValueError("开始时间不能晚于结束时间")

        matched_events = []
        for event in events_data:
            event_dates = event.get("date", [])
            for date_str in event_dates:
                date_str = self.tool_center.basic_toolkit.extract_start_date(date_str)
                event_start, _ = self.tool_center.basic_toolkit.parse_date(date_str)
                if start_range <= event_start <= end_range:
                    matched_events.append(event)
                    break
        return matched_events

    def get_event_by_id(self, target_event_id: str) -> List[Dict]:
        """递归查找匹配ID的事件"""
        matched_events = []

        def recursive_search(events: List[Dict]):
            for event in events:
                if event.get("event_id") == target_event_id:
                    matched_events.append(event)
                subevents = event.get("subevent", [])
                if subevents:
                    recursive_search(subevents)

        recursive_search(self.events)
        return matched_events

    def get_plan(self, date: str) -> Dict[str, Any]:
        """获取今日+未来一周计划（顶层事件）"""
        res = {"今日事件": "", "未来一周背景": ""}
        id_set: Set[str] = set()

        def getdata(date_str: str) -> Dict[str, List[Dict]]:
            data1 = {"事件序列": [], "事件背景": []}
            arr = self.filter_by_date(date_str)
            arr1 = []
            for item in arr:
                event_id = item['event_id']
                if event_id in id_set:
                    continue
                id_set.add(event_id)
                parts = event_id.split('-', 1)[0]
                e = self.get_event_by_id(parts)
                arr1.append(e)
            data1["事件序列"] = arr
            data1["事件背景"] = arr1
            return data1

        res["今日事件"] = getdata(date)
        next_7_day = self.tool_center.basic_toolkit.get_next_n_day(date, 7)
        r = []
        for event in self.filter_events_by_start_range(self.events, date, next_7_day):
            event_copy = copy.deepcopy(event)
            r.append(event_copy)

        for i in r:
            i['subevent'] = []
        res["未来一周背景"] = r
        return res

    def get_plan2(self, date: str) -> Dict[str, Any]:
        """获取今日+未来一周计划（底层事件）"""
        res = {"今日事件": "", "未来一周背景": "", "前一天事件": ""}
        id_set: Set[str] = set()

        def getdata(date_str: str) -> Dict[str, List[Dict]]:
            data1 = {"事件序列": [], "事件背景": []}
            arr = self.filter_by_date(date_str)
            arr1 = []
            for item in arr:
                event_id = item['event_id']
                if event_id in id_set:
                    continue
                id_set.add(event_id)
                parts = event_id.rsplit('-', 1)[0]
                e = self.get_event_by_id(parts)
                arr1.append(e)
            data1["事件序列"] = arr
            data1["事件背景"] = arr1
            return data1

        res["今日事件"] = getdata(date)
        r = {}
        for d in self._iterate_dates(date, self.tool_center.basic_toolkit.get_next_n_day(date, 5)):
            e = self.filter_by_date(d)
            r[d] = e
        res["未来一周背景"] = r
        prev_day = self.tool_center.basic_toolkit.get_next_n_day(date, -1)
        res["前一天事件"] = {prev_day: self.filter_by_date(prev_day)}
        return res

    def _iterate_dates(self, start_date: str, end_date: str) -> List[str]:
        """生成日期区间内的所有日期"""
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current = self.tool_center.basic_toolkit.get_next_n_day(current, 1)
        return dates

    # ------------------------------ 事件管理 ------------------------------
    def delete_top_event(self, events: List[Dict], target_id: str) -> List[Dict]:
        """删除顶层事件"""
        return [event for event in events if event.get("event_id") != target_id]

    def add_top_event(self, events: List[Dict], new_event: Dict[str, Any]) -> List[Dict]:
        """添加顶层事件"""
        event_to_add = new_event.copy()
        event_to_add['event_id'] = "0"

        if event_to_add.get("event_id") in ("0", 0):
            existing_ids = []
            for event in events:
                try:
                    existing_ids.append(int(event.get("event_id", "")))
                except (ValueError, TypeError):
                    pass
            new_id = max(existing_ids) + 1 if existing_ids else 1
            event_to_add["event_id"] = str(new_id)

        if "subevent" not in event_to_add:
            event_to_add["subevent"] = []

        return events + [event_to_add]

    def event_schedule(self, operations: List[Dict[str, Any]], date: str) -> None:
        """更新事件调度"""

        def modify_event_data(original_data: List[Dict], ops: List[Dict]) -> List[Dict]:
            modified_data = json.loads(json.dumps(original_data))
            for op in ops:
                op_type = op["type"]
                event_info = op["event"]
                target_event_id = event_info["event_id"]

                if op_type == "delete":
                    def delete_target_event(event_list: List[Dict], target_id: str) -> bool:
                        deleted = False
                        for i in range(len(event_list)):
                            current_event = event_list[i]
                            if current_event["event_id"] == target_id:
                                del event_list[i]
                                deleted = True
                                break
                            if current_event.get("subevent"):
                                deleted = delete_target_event(current_event["subevent"], target_id)
                                if deleted:
                                    break
                        return deleted

                    for top_event in modified_data:
                        if delete_target_event([top_event], target_event_id):
                            break

                elif op_type == "update":
                    def update_subevent(event_list: List[Dict], target_id: str, new_event: Dict) -> bool:
                        updated = False
                        for i in range(len(event_list)):
                            current_event = event_list[i]
                            if current_event["event_id"] == target_id:
                                event_list[i] = new_event
                                updated = True
                                break
                            if current_event.get("subevent"):
                                updated = update_subevent(current_event["subevent"], target_id, new_event)
                                if updated:
                                    break
                        return updated

                    for top_event in modified_data:
                        if update_subevent([top_event], target_event_id, event_info):
                            break

            return modified_data

        with self._lock:
            for op in operations:
                self.events = modify_event_data(self.events, operations)
            self.update_bottom_level_events()
        print("[【【【【【【【【【【【【【【【【【【更新事件】】】】】】】】】】】】】】】】】】】]")

    def event_add(self, data: List[Dict[str, Any]]) -> None:
        """添加顶层事件"""
        with self._lock:
            for event in data:
                self.events = self.add_top_event(self.events, event)
            self.update_bottom_level_events()

    # ------------------------------ 每日事件生成 ------------------------------
    def event_refine(self, date: str) -> bool:
        """优化事件调度"""
        plan = self.get_plan2(date)
        prompt = template_plan_4.format(
            plan0=plan['今日事件']["事件序列"],
            plan1=plan['今日事件'],
            plan2=plan['未来一周背景'],
            plan3=plan['前一天事件'],
            date=self.tool_center.basic_toolkit.get_date_string(date)
        )
        res = self.tool_center.llm_call(prompt, self.shared_data.get("context"), model_type="chat", record=0)
        print("思考-----------------------------------------------------------------------")
        print(res)

        data = json.loads(res)
        data = data['event_update']

        def update_subevent(event_list: List[Dict], target_id: str, new_event: str):
            updated = False
            for i in range(len(event_list)):
                current_event = event_list[i]
                if current_event["event_id"] == target_id:
                    for j in range(len(event_list[i]['date'])):
                        if self.tool_center.basic_toolkit.is_date_match(event_list[i]['date'][j], date):
                            event_list[i]['date'][j] = new_event
                    updated = True
                    break
                if current_event.get("subevent"):
                    updated = update_subevent(current_event["subevent"], target_id, new_event)
                    if updated:
                        break
            return updated

        with self._lock:
            for i in data:
                update_subevent(self.events, i['event_id'], i['new_date'])
                self.update_bottom_level_events()
        return True

    def daily_event_gen(self, date: str, next_day_thread_start_event: threading.Event) -> bool:
        """每日事件生成主流程"""
        with self._lock:
            # 1. 主观思考
            plan = self.get_plan(date)
            prompt = template_plan_21.format(
                cognition=self.shared_data.get("cognition"),
                memory=self.long_memory + self.short_memory,
                thought=self.thought,
                plan=plan['今日事件'],
                date=self.tool_center.basic_toolkit.get_date_string(date),
                persona=self.shared_data.get("persona")
            )
            res = self.tool_center.llm_call(prompt, self.shared_data.get("context"), model_type="chat", record=1)
            print("主观思考-----------------------------------------------------------------------")
            print(res)
            self.tool_center.file_module.write_to_txt(res, date, "t1", self.txt_file_path)

            # 2. 客观生成（触发下一线程）
            plan2 = self.get_plan2(date)
            prompt = template_plan_11.format(plan=plan2)
            res1 = self.tool_center.llm_call(prompt, self.shared_data.get("context"), model_type="chat", record=1)
            print("客观生成-----------------------------------------------------------------------")
            print(res1)
            self.tool_center.file_module.write_to_txt(res1, date, "t2", self.txt_file_path)

            # 触发下一日线程
            next_day_thread_start_event.set()
            print(f"🔔【{date}】客观生成完成，已触发下一日线程")

            # 3. 轨迹调整（POI）
            poidata = self.tool_center.get_poi_route(self.shared_data.get("persona"), res1)
            prompt = template_plan_5.format(poi=poidata)
            res1 = self.tool_center.llm_call(prompt, self.shared_data.get("context"), model_type="chat", record=0)
            print("轨迹调整-----------------------------------------------------------------------")
            print(res1)
            self.tool_center.file_module.write_to_txt(res1, date, "t3", self.txt_file_path)

            # 4. 细节丰富
            prompt = template_plan_31.format(
                memory=self.short_memory,
                life=res1,
                cognition=self.shared_data.get("cognition"),
                poi=poidata
            )
            res2 = self.tool_center.llm_call(prompt, self.shared_data.get("context"), model_type="chat", record=0)
            print("丰富细节-----------------------------------------------------------------------")
            print(res2)
            self.tool_center.file_module.write_to_txt(res2, date, "t4", self.txt_file_path)

            # 5. 事件提取 & 更新
            prompt = template_get_event_31.format(
                content=res2,
                poi=poidata + "家庭住址：上海市浦东新区张杨路123号，工作地点：上海市浦东新区世纪大道88号",
                date=self.tool_center.basic_toolkit.get_date_string(date)
            )
            res = self.tool_center.llm_call(prompt, self.shared_data.get("context"), model_type="chat", record=0)
            print("提取事件-----------------------------------------------------------------------")
            record = res
            res = self.tool_center.basic_toolkit.remove_json_wrapper(res)
            print(res)
            event_data = json.loads(res)
            self.event_add(event_data)

            # 6. 反思 & 想法更新
            prompt = template_reflection.format(
                cognition=self.shared_data.get("cognition"),
                memory=self.long_memory + self.short_memory,
                content=res2,
                plan=plan,
                date=self.tool_center.basic_toolkit.get_date_string(date)
            )
            res = self.tool_center.llm_call(prompt, self.shared_data.get("context"), model_type="chat", record=0)
            print("反思-----------------------------------------------------------------------")
            res = self.tool_center.basic_toolkit.remove_json_wrapper(res)
            print(res)
            reflection_data = json.loads(res)
            self.thought = reflection_data["thought"]

            # 7. 长期记忆更新
            m = reflection_data
            mm = [m]
            mem_module = MemoryModule.get_instance(self.mem_instance_id)
            for i in range(1, 3):
                mm += mem_module.search_by_date(self.tool_center.basic_toolkit.get_next_n_day(date, -i))

            prompt = template_update_cog.format(
                cognition=self.shared_data.get("cognition"),
                memory=self.long_memory,
                plan=plan,
                history=mm,
                now=record,
                thought=self.thought,
                date=self.tool_center.basic_toolkit.get_date_string(date)
            )
            res = self.tool_center.llm_call(prompt, self.shared_data.get("context"), model_type="chat")
            res = self.tool_center.basic_toolkit.remove_json_wrapper(res)
            print("更新长期记忆-----------------------------------------------------------------------")
            print(res)
            mem_data = json.loads(res)
            self.long_memory = mem_data['long_term_memory']
            self.tool_center.file_module.write_to_txt(res, date, "t2", self.txt_file_path)

            # 8. 短期记忆更新 & 持久化
            self.short_memory = self.tool_center.update_short_memory(m, date, self.mem_instance_id)
            self.save_to_json()
            self.tool_center.file_module.safe_json_dump(
                self.events,
                self.file_path + "event_update.json"
            )

            print(f"✅【{date}】事件生成完成")
            return True

    def save_to_json(self) -> None:
        """保存当前实例状态"""
        with self._lock:
            data = {
                "persona": self.shared_data.get("persona"),
                "context": self.shared_data.get("context"),
                "cognition": self.shared_data.get("cognition"),
                "long_memory": self.long_memory,
                "short_memory": self.short_memory,
                "reflection": self.reflection,
                "thought": self.thought,
                "env": self.shared_data.get("env")
            }
            self.tool_center.save_record(data)


# ------------------------------ 控制器 & 占位类 ------------------------------
class MindController:
    """多线程控制器"""

    def __init__(self, file_path: str = Config.DEFAULT_DATA_PATH):
        self.file_path = file_path
        self.shared_data = SharedMindData()

    def create_mind_instance(self, mem_instance_id: str = "default") -> MindInstance:
        """创建业务实例"""
        return MindInstance(self.file_path, mem_instance_id)

    def run_daily_event_with_threading(
            self,
            start_date: str,
            end_date: str,
            initial_events: List[Dict],
            initial_persona: Dict[str, Any]
    ) -> None:
        """多线程执行"""
        # 初始化共享数据
        self.shared_data.set("persona", copy.deepcopy(initial_persona))

        # 生成日期列表
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current = GlobalToolCenter.get_instance().basic_toolkit.get_next_n_day(current, 1)

        if not dates:
            print("⚠️ 无需要处理的日期")
            return

        # 线程控制
        threads = []
        prev_event = threading.Event()
        prev_event.set()

        for idx, date in enumerate(dates):
            prev_event.wait()
            print(f"\n📅 开始处理日期：{date}")

            current_event = threading.Event()
            mind_instance = self.create_mind_instance(f"mem-{date}")  # 每个日期独立记忆实例
            mind_instance.load_from_json(initial_events, initial_persona, record=1)

            # 线程执行函数
            def thread_func(date_str: str, trigger_next_event: threading.Event, instance: MindInstance):
                try:
                    instance.event_refine(date_str)
                    instance.daily_event_gen(date_str, trigger_next_event)
                except Exception as e:
                    print(f"\n❌【{date_str}】线程执行失败: {str(e)}")
                    trigger_next_event.set()

            # 启动线程
            thread = threading.Thread(
                target=thread_func,
                args=(date, current_event, mind_instance),
                name=f"MindThread-{date}",
                daemon=True
            )
            threads.append(thread)
            thread.start()

            prev_event = current_event

        # 等待所有线程完成
        for thread in threads:
            thread.join(timeout=Config.THREAD_TIMEOUT)
            if thread.is_alive():
                print(f"⚠️ 【{thread.name}】线程执行超时，强制终止")

        print("\n🎉 所有日期事件生成完成")


# 占位类（实际项目中替换为真实实现）
class MapMaintenanceTool:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def process_instruction_route(self, data: Dict) -> Tuple[Any, str]:
        return {}, ""

    def extract_route_summary(self, result: Any) -> str:
        return "示例路线摘要"

    def extract_poi_route_simplified(self, result: Any) -> str:
        return "示例简化POI路线"


# 模板常量（实际项目中替换）
template_plan_21 = ""
template_plan_11 = ""
template_plan_5 = ""
template_plan_4 = ""
template_plan_31 = ""
template_get_poi2 = ""
template_get_poi3 = ""
template_get_event_31 = ""
template_reflection = ""
template_update_cog = ""


# ------------------------------ 使用示例 ------------------------------
if __name__ == "__main__":
    # 1. 初始化控制器
    controller = MindController()

    # 2. 初始数据
    initial_events = [
        {"event_id": "1", "name": "上班", "date": ["2025-01-01"], "subevent": []}
    ]
    initial_persona = {
        "name": "张三", "age": 30, "job": "程序员", "relation": {"家人": ["李四"]}
    }

    # 3. 执行多线程生成
    controller.run_daily_event_with_threading(
        start_date="2025-01-01",
        end_date="2025-01-03",
        initial_events=initial_events,
        initial_persona=initial_persona
    )