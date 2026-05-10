import re
import random
from datetime import timedelta
from src.lifebench.utils.llm_call import *
from src.lifebench.event.memory_structure.memory import *
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
class Data_extract:
    def __init__(self):
        self.events = []
        self.persona = ""
        self.persona_withoutrl = ""
        self.context = "你是一位手机数据专家和深度用户"
        self.atomic_events : Optional[List[Dict]] = None
        self.daily_draft = {}

    def _get_bottom_level_events(self) -> List[Dict]:
        """
        【内部辅助方法】递归提取所有最底层事件（subevent为空），结果缓存到self.bottom_events
        :return: 最底层事件列表
        """
        if self.atomic_events is not None:
            return self.atomic_events  # 已计算过，直接返回缓存

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
        """更新底层事件缓存，委托给 _get_bottom_level_events"""
        self.atomic_events = None  # 重置缓存，触发重新计算
        self._get_bottom_level_events()
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
    def load_from_json(self,event,persona,daily_draft={}):

            self.persona = persona
            self.events = event
            # 创建副本以避免修改原始persona
            persona_copy = persona.copy()
            del persona_copy["relation"]
            self.persona_withoutrl = persona_copy
            self.daily_draft = daily_draft
            return False

    def getstatus(self,date):
        import json
        from datetime import datetime
        print('here')
        # 计算目标日期
        base_date = datetime.strptime(date, "%Y-%m-%d")
        target_date = base_date
        target_date_str = target_date.strftime("%Y-%m-%d")

        # 直接从self.daily_draft获取数据
        try:
            data = self.daily_draft
            # 从目标日期中提取年月，例如 "2025-01-05" -> "2025-01"
            year_month = "-".join(target_date_str.split("-")[:2])

            # 检查年月数据是否存在
            if year_month not in data:
                print(f"警告: 年月 {year_month} 的数据在文件中不存在")
                return {}

            # 在对应的月份数据中查找指定日期
            month_data = data[year_month]

            for day_data in month_data:
                # print(day_data)
                if day_data.get("date") == target_date_str:
                    return day_data

                # 如果指定日期不存在，返回空字典
            print(f"警告: 日期 {target_date_str} 的数据在文件中不存在")
            return {}
        except json.JSONDecodeError:
            print(f"错误: daily_draft 不是有效的JSON格式")
            return {}
        except Exception as e:
            print(f"读取daily_draft时发生错误: {str(e)}")
            return {}


def get_daily_events_with_subevent(events, target_date_str):
    """
    仅按日级别匹配，获取起始日期在目标日期且包含子事件（subevent非空）的事件

    参数:
    events (list): 原始事件列表，每个事件为字典格式
    target_date_str (str): 目标日期字符串，支持三种输入格式：
                          1. "%Y-%m-%d %H:%M:%S"（如"2025-03-04 14:00:00"）
                          2. "%Y-%m-%d %H:%M"（如"2025-03-04 14:00"）
                          3. "%Y-%m-%d"（如"2025-03-04"）
                          最终均按日级别（年月日）匹配

    返回:
    list: 符合条件的事件列表
    """
    # 存储符合条件的事件
    result_events = []

    # 步骤1：解析目标日期，提取年月日（统一转为日级别）
    # 定义支持的输入格式，确保能解析三种类型的目标时间
    supported_input_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d"
    ]
    target_date = None
    for fmt in supported_input_formats:
        try:
            # 解析目标时间
            parsed_datetime = datetime.strptime(target_date_str, fmt)
            # 提取日级别日期（转为"YYYY-MM-DD"字符串）
            target_date = parsed_datetime.strftime("%Y-%m-%d")
            break
        except ValueError:
            continue

    # 若目标日期解析失败，抛出异常
    if target_date is None:
        raise ValueError(
            f"目标日期格式错误！仅支持以下三种格式：\n1. %Y-%m-%d %H:%M:%S（如2025-03-04 14:00:00）\n2. %Y-%m-%d %H:%M（如2025-03-04 14:00）\n3. %Y-%m-%d（如2025-03-04）")

    # 步骤2：遍历事件，筛选符合条件的记录
    for event in events:
        # 条件1：事件必须包含子事件（subevent非空列表）
        if not event.get("subevent"):
            continue
        if event.get("subevent") == []:
            continue
        # 条件2：解析事件起始时间，判断是否与目标日期匹配（日级别）
        date_str_list = event.get("date", [])
        if not date_str_list:  # 无日期信息的事件跳过
            continue

        # 取第一个时间段作为事件主起始时间（默认date列表首个为核心时间）
        main_time_range = date_str_list[0]
        event_start_str = main_time_range.split("至")[0].strip()  # 分割"至"，取起始时间部分

        # 解析事件起始时间（支持三种格式）
        event_start_date = None
        for fmt in supported_input_formats:
            try:
                parsed_event_start = datetime.strptime(event_start_str, fmt)
                event_start_date = parsed_event_start.strftime("%Y-%m-%d")  # 转为日级别
                break
            except ValueError:
                continue

        # 若事件起始时间解析失败，打印警告并跳过
        if event_start_date is None:
            print(f"警告：事件{event.get('event_id')}的起始时间格式异常（{event_start_str}），跳过处理")
            continue

        # 日级别匹配：事件起始日期 == 目标日期
        if event_start_date == target_date:
            result_events.append(event)

    return result_events

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

def remove_json_wrapper(s: str, json_type: str = 'array') -> str:
        """
        处理字符串，移除JSON包装：
        1. 去除字符串前后可能存在的```json  ```标记（包含可能的空格）
        2. 根据json_type参数提取对应的JSON内容：
           - json_type='object'：提取第一个{到最后一个}之间的内容
           - json_type='array'：提取第一个[到最后一个]之间的内容

        参数:
            s: 输入字符串
            json_type: JSON类型，'object'对应{}，'array'对应[]，默认为'object'

        返回:
            处理后的字符串，若不存在有效JSON则返回原字符串
        """
        # 1. 先移除开头的```json和结尾的```标记
        pattern = r'^\s*```json\s*\n?|\s*```\s*$'
        result = re.sub(pattern, '', s, flags=re.MULTILINE)
        
        # 2. 根据json_type提取对应的括号内容
        if json_type == 'array':
            first_bracket = result.find('[')
            last_bracket = result.rfind(']')
            if first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
                result = result[first_bracket:last_bracket + 1]
        else:  # 默认处理JSON对象
            first_brace = result.find('{')
            last_brace = result.rfind('}')
            if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                result = result[first_brace:last_brace + 1]
            
        return result

def contact_gen(persona):
    temp = '''
    请根据以下 Persona 信息，参考给出的 Few-Shot 示例格式，生成对应的联系人列表。要求如下：
提取 Persona 中「relation」字段下所有关联人物，不遗漏任何一位，确保覆盖所有社交圈层；
联系人列表固定包含 8 个字段，字段顺序严格遵循示例：「name」「relation」「gender」「nickname」「phoneNumber」「personalEmail」「workEmail」「idNumber」；
各字段需与 Persona 中对应人物属性一致：phoneNumber 按人物所属省份合理虚构手机号段，personalEmail 结合姓名、所在城市拼音缩写 + 常见邮箱后缀（163.com/qq.com/126.com等），workEmail 结合姓名、所属组织拼音 / 英文缩写 + 常见后缀，idNumber 按人物 birth_date 和性别规则虚构（18 位，第 17 位男性为奇数、女性为偶数）；
最终输出标准 JSON 数组结构，无额外文字说明，格式整洁无冗余。
示例：
[{{"name": "徐明","relation": "父亲","gender": "男","nickname": "老爸","phoneNumber": "13917895623","personalEmail": "xuming_sh@163.com","workEmail": "xuming@mingfangfushi.com","idNumber": "310101196503124517"}},{{"name": "王丽","relation": "闺蜜","gender": "女","nickname": "丽丽","phoneNumber": "13681792345","personalEmail": "wangli_xh@163.com","workEmail": "wangli@shad.com","idNumber": "310104199303152826"}}]
参考persona:{persona}
    '''
    prompt = temp.format(persona=persona)
    res = llm_call(prompt)
    print(res)
    return res

extool = Data_extract()


def clean_json_string(json_str: str) -> str:
    """
    清理JSON字符串，使其能正常解析
    主要处理：
    1. 去除字符串值中的未转义换行符
    2. 处理值中的双引号（转义或去除，可选）
    3. 清理多余的空白字符
    4. 确保JSON格式合法
    """
    # 1. 先清理字符串两端的空白字符（包括换行、制表符等）
    cleaned = json_str.strip()

    # 2. 处理字符串值中的未转义换行符和双引号
    # 正则匹配JSON中的字符串值部分（"key": "value" 中的value）
    def replace_in_value(match: re.Match) -> str:
        # match.group(1) 是 key 部分，match.group(2) 是 value 部分
        key_part = match.group(1)
        value_part = match.group(2)

        # 处理value中的换行符：替换为空格或转义符（根据需求选择）
        # 方案1：替换为空格（推荐，可读性更好）
        value_part = value_part.replace('\n', ' ')
        # 方案2：转义为 \n（如果需要保留换行结构）
        # value_part = value_part.replace('\n', '\\n')

        # 处理value中的双引号：可以选择去除或转义
        # 方案1：去除双引号
        value_part = value_part.replace('"', '')
        # 方案2：转义双引号（如果需要保留双引号）
        # value_part = value_part.replace('"', '\\"')

        # 清理多余的空格（连续多个空格合并为一个）
        value_part = re.sub(r'\s+', ' ', value_part).strip()

        return f'"{key_part}": "{value_part}"'

    # 正则匹配所有 "key": "value" 格式的字符串
    # 匹配规则："任意key": "任意value"（value中可以包含除未转义双引号外的任意字符）
    cleaned = re.sub(
        r'"([^"]+)":\s*"([^"]*)"',
        replace_in_value,
        cleaned,
        flags=re.DOTALL  # 让.匹配换行符（虽然我们之后会处理换行）
    )

    # 3. 处理数组和对象末尾可能的逗号（防止多余逗号导致报错）
    cleaned = re.sub(r',\s*]', ']', cleaned)
    cleaned = re.sub(r',\s*}', '}', cleaned)

    return cleaned


# ============================================================================
# 并行处理相关函数 - 动态注册生成器
# ============================================================================

def get_registered_generators(file_path=None):
    """
    动态获取 phone_generator 包中注册的所有生成器
    
    参数：
        file_path: 文件保存路径，用于读取 persona.json 文件
    
    返回：字典 {文件名：(类名，方法名，初始数据)}
    """
    import json
    from src.lifebench.event.phone_generator import (
        PerceptionDataGenerator,
        CommunicationOperationGenerator,
        NoteCalendarOperationGenerator,
        GalleryOperationGenerator,
        FitnessHealthOperationGenerator,
        ChatOperationGenerator,
        PushOperationGenerator
    )
    
    # 读取用户画像数据
    profile = None
    if file_path:
        persona_file = f"{file_path}persona.json"
        try:
            with open(persona_file, 'r', encoding='utf-8') as f:
                profile = json.load(f)
            print(f"成功读取用户画像数据: {persona_file}")
        except Exception as e:
            print(f"读取用户画像数据失败: {str(e)}")
    
    # 注册所有生成器及其对应信息
    generators = {
        # 'perception': {
        #     'class': PerceptionDataGenerator,
        #     'method': 'generate_perception_data',
        #     'filename': 'event_perception.json',
        #     'init_args': {'profile': profile},
        #     'method_args': ['date', 'extool']
        # },
        'communication': {
            'class': CommunicationOperationGenerator,
            'method': 'phone_gen_callandmsm',
            'filename': 'event_call.json',
            'init_args': {},
            'method_args': ['date', 'contact', 'file_path']
        },
        'note_calendar': {
            'class': NoteCalendarOperationGenerator,
            'method': 'phone_gen_noteandcalendar',
            'filename': 'event_note.json',
            'init_args': {'random_seed': 42},
            'method_args': ['date', 'contact', 'file_path']
        },
        'gallery': {
            'class': GalleryOperationGenerator,
            'method': 'phone_gen_gallery',
            'filename': 'event_gallery.json',
            'init_args': {'random_seed': 42},
            'method_args': ['date', 'contact', 'file_path']
        },
        'fitness_health': {
            'class': FitnessHealthOperationGenerator,
            'method': 'phone_gen_fitness_health',
            'filename': 'event_fitness_health.json',
            'init_args': {'random_seed': 42},
            'method_args': ['date', 'contact', 'file_path']
        },
        'chat': {
            'class': ChatOperationGenerator,
            'method': 'phone_gen_agent_chat',
            'filename': 'event_chat.json',
            'init_args': {'random_seed': 42},
            'method_args': ['date', 'contact', 'file_path']
        },
        'push': {
            'class': PushOperationGenerator,
            'method': 'phone_gen_push',
            'filename': 'event_push.json',
            'init_args': {'random_seed': 42},
            'method_args': ['date', 'contact', 'file_path']
        }
    }
    
    return generators


def run_generator_task(generator_name, generator_info, date, contact, file_path, extool=None):
    """
    运行单个生成器任务

    参数:
        generator_name: 生成器名称
        generator_info: 生成器配置信息
        date: 日期
        contact: 联系人信息
        file_path: 文件路径
        extool: Data_extract 实例，用于提供事件数据

    返回:
        生成的数据列表
    """
    try:
        # 实例化生成器
        generator_class = generator_info['class']
        init_args = generator_info.get('init_args', {})

        if init_args:
            generator = generator_class(**init_args)
        else:
            generator = generator_class()

        # 获取方法名和参数
        method_name = generator_info['method']
        method = getattr(generator, method_name)

        # 根据方法签名调用
        method_args = generator_info.get('method_args', [])

        if 'extool' in method_args:
            # perception 生成器 - 传入 extool 实例
            result = method(date, extool)
        elif 'contact' in method_args:
            # 其他生成器 - 检查方法是否接受 extool 参数
            try:
                # 获取方法参数名
                import inspect
                sig = inspect.signature(method)
                param_names = list(sig.parameters.keys())
                if 'extool' in param_names:
                    result = method(date, contact, file_path, extool)
                else:
                    result = method(date, contact, file_path)
            except (ValueError, TypeError):
                # 如果无法获取签名，使用默认方式
                result = method(date, contact, file_path)
        else:
            result = method(date)

        print(f"✅ {generator_name} 生成器成功处理日期：{date}")
        return result

    except Exception as e:
        print(f"❌ {generator_name} 生成器处理日期 {date} 时出错：{str(e)}")
        import traceback
        traceback.print_exc()
        return []


def process_single_date_dynamic(date, contact, file_path, matcher,
                               phone_count_control=None):
    """
    处理单个日期的所有数据生成（动态版本）

    参数:
        date: 要处理的日期
        contact: 联系人信息
        file_path: 文件保存路径
        matcher: PhoneEventMatcher 实例
        phone_count_control: 每日手机数据数目控制字典 {min: int, max: int}，默认 {5, 5}
            - min: 每天最少手机数据条数
            - max: 每天最多手机数据条数

    返回:
        (success, date, generated_data_dict)
    """
    try:
        # 获取所有注册的生成器
        registered_generators = get_registered_generators(file_path)

        # 内部并行执行所有生成器任务
        num_generators = len(registered_generators)
        with ThreadPoolExecutor(max_workers=num_generators) as inner_executor:
            # 提交所有生成器任务
            futures = {}
            for gen_name, gen_info in registered_generators.items():
                future = inner_executor.submit(
                    run_generator_task,
                    gen_name,
                    gen_info,
                    date,
                    contact,
                    file_path,
                    extool  # 传入 extool 实例以支持线程安全
                )
                futures[future] = gen_name

            # 收集结果
            generated_data = {}
            for future in as_completed(futures):
                gen_name = futures[future]
                gen_info = registered_generators[gen_name]
                filename = gen_info['filename']
                result = future.result()
                generated_data[filename] = result

        # 调用 PhoneEventMatcher 进行原子事件匹配分析
        try:
            # 汇总该日数据（除了 event_fitness_health.json）
            all_phone_operations = []
            for filename, data in generated_data.items():
                if filename != "event_fitness_health.json" and data:
                    all_phone_operations.extend(data)
            
            # 使用传入的 PhoneEventMatcher 实例
            match_result = matcher.match_phone_events_with_atomic_events(
                phone_operations=all_phone_operations,
                date=date,
                generate_unmatched=False
            )
            
            # 将匹配结果更新回 generated_data
            matched_phone_events = match_result["matched_phone_events"]
            
            # 按文件类型分配匹配后的手机事件
            phone_ops_by_type = {filename: [] for filename in generated_data.keys()}
            
            # 根据事件类型将匹配后的手机事件分配回相应的文件
            for op in matched_phone_events:
                if "type" in op:
                    event_type = op["type"]
                    # 根据 type 分配到对应的文件
                    if event_type in ["note", "calendar"]:
                        target_file = "event_note.json"
                        if target_file not in phone_ops_by_type:
                            phone_ops_by_type[target_file] = []
                        phone_ops_by_type[target_file].append(op)
                    elif event_type in ["call", "sms"]:
                        target_file = "event_call.json"
                        if target_file not in phone_ops_by_type:
                            phone_ops_by_type[target_file] = []
                        phone_ops_by_type[target_file].append(op)
                    elif event_type == "photo":
                        target_file = "event_gallery.json"
                        if target_file not in phone_ops_by_type:
                            phone_ops_by_type[target_file] = []
                        phone_ops_by_type[target_file].append(op)
                    elif event_type == "push":
                        target_file = "event_push.json"
                        if target_file not in phone_ops_by_type:
                            phone_ops_by_type[target_file] = []
                        phone_ops_by_type[target_file].append(op)
                    elif event_type == "chat" or "agent_chat" in op.get("type", ""):
                        target_file = "event_chat.json"
                        if target_file not in phone_ops_by_type:
                            phone_ops_by_type[target_file] = []
                        phone_ops_by_type[target_file].append(op)
                    elif event_type == "perception":
                        target_file = "event_perception.json"
                        if target_file not in phone_ops_by_type:
                            phone_ops_by_type[target_file] = []
                        phone_ops_by_type[target_file].append(op)
            
            # 更新 generated_data 中的手机事件数据
            for filename, ops in phone_ops_by_type.items():
                if ops:
                    generated_data[filename] = ops
            
            print(f"成功完成原子事件匹配，为手机数据添加 atomic_id 字段")
        except Exception as e:
            print(f"调用 PhoneEventMatcher 时出错：{str(e)}")
            import traceback
            traceback.print_exc()
        
        # 重命名字段：先将 event_id 更名为 daily_event_id，再将 atomic_id 更名为 event_id
        for filename, data_list in generated_data.items():
            if data_list:
                for item in data_list:
                    # 先重命名 event_id 为 daily_event_id
                    if 'event_id' in item and 'daily_event_id' not in item:
                        item['daily_event_id'] = item.pop('event_id')
                    # 如果没有 atomic_id，补充为空数组
                    if 'atomic_id' not in item:
                        item['atomic_id'] = []
                    # 再重命名 atomic_id 为 event_id
                    item['event_id'] = item.pop('atomic_id')

                # 重命名字段后：检查 daily_event_id 是否为有效数字/字符串数字，若无效则抛弃该数据
                valid_data = []
                for item in data_list:
                    deid = item.get('daily_event_id')
                    if isinstance(deid, int):
                        valid_data.append(item)
                    elif isinstance(deid, str) and deid.isdigit():
                        valid_data.append(item)
                    else:
                        print(f"  警告: {filename} 中一条数据因 daily_event_id='{deid}' 无效被抛弃")
                generated_data[filename] = valid_data
        
        # 手机数据采样阶段：控制每日数据条数
        if phone_count_control is None:
            phone_count_control = {"min": 5, "max": 5}

        min_count = phone_count_control.get("min", 5)
        max_count = phone_count_control.get("max", 5)
        # fitness_health 不参与采样但需保留，所以 min/max 减1
        min_count = max(1, min_count - 1)
        max_count = max(1, max_count - 1)
        target_count = random.randint(min_count, max_count)

        # 需要采样的文件类型（排除 event_fitness_health.json）
        sample_exclude = {"event_fitness_health.json"}
        # agent_chat 类型不参与采样但需保留
        preserved_items = []

        # 收集所有参与采样的手机数据项
        all_sampleable = []
        for filename, data_list in generated_data.items():
            if filename in sample_exclude or not data_list:
                continue
            for item in data_list:
                item_type = item.get("type", "")
                # agent_chat 类型不参与采样，但需保留
                if "agent_chat" in item_type:
                    preserved_items.append((filename, item))
                    continue
                all_sampleable.append((filename, item))

        total_count = len(all_sampleable)
        if total_count == 0:
            print(f"成功处理日期：{date}（无手机数据，跳过采样）")
            return (True, date, generated_data)

        # 采样
        if total_count <= target_count:
            sampled = all_sampleable
            print(f"[手机数据采样] 日期 {date}：原始 {total_count} 条 <= 目标 {target_count} 条，全部保留")
        else:
            # 第一优先：按覆盖 atomic_event 数量降序（event_id 字段）
            # 第二优先：按覆盖 daily_event_id 数量降序
            def sample_key(item):
                _, op = item
                # 第一优先：event_id 覆盖数量
                event_ids = op.get("event_id", [])
                event_coverage = len(event_ids) if isinstance(event_ids, list) else 0
                # 第二优先：daily_event_id 覆盖数量
                daily_event_ids = op.get("daily_event_id", [])
                daily_coverage = len(daily_event_ids) if isinstance(daily_event_ids, list) else 0
                return (-event_coverage, -daily_coverage)

            all_sampleable.sort(key=sample_key)

            # 第三优先：按类型均匀采样（优先选择不同类型的手机操作）
            # 先按类型分组
            type_groups = {}
            for fn, op in all_sampleable:
                op_type = op.get("type", "unknown")
                if op_type not in type_groups:
                    type_groups[op_type] = []
                type_groups[op_type].append((fn, op))

            # 计算每种类型需要选几个（均匀分配）
            num_types = len(type_groups)
            base_per_type = target_count // num_types
            remainder = target_count % num_types

            selected = []
            selected_set = set()
            type_counts = {t: 0 for t in type_groups}

            # 轮流从每种类型中选择，直到选够 target_count
            # 优先选择每种类型中 coverage 较高的
            for t in sorted(type_groups.keys()):
                type_groups[t].sort(key=sample_key)

            round = 0
            while len(selected) < target_count and round < 100:
                for t in sorted(type_groups.keys()):
                    if len(selected) >= target_count:
                        break
                    # 每轮从该类型中选一个
                    start_idx = type_counts[t]
                    if start_idx < len(type_groups[t]):
                        fn, op = type_groups[t][start_idx]
                        item_key = (fn, id(op))
                        if item_key not in selected_set:
                            selected.append((fn, op))
                            selected_set.add(item_key)
                            type_counts[t] += 1
                round += 1

            # 如果均匀采样没选够，从剩余的中按 coverage 补齐
            if len(selected) < target_count:
                for fn, op in all_sampleable:
                    if len(selected) >= target_count:
                        break
                    item_key = (fn, id(op))
                    if item_key not in selected_set:
                        selected.append((fn, op))
                        selected_set.add(item_key)

            sampled = selected
            print(f"[手机数据采样] 日期 {date}：原始 {total_count} 条，目标 {target_count} 条，已按优先级采样（含类型均匀采样）")

        # 用采样结果替换 generated_data
        sampled_set = set((fn, id(item)) for fn, item in sampled)
        sampled_set.update((fn, id(item)) for fn, item in preserved_items)
        for filename, data_list in generated_data.items():
            if filename in sample_exclude:
                continue
            generated_data[filename] = [
                item for item in data_list
                if (filename, id(item)) in sampled_set
            ]

        print(f"成功处理日期：{date}")
        return (True, date, generated_data)
    
    except Exception as e:
        print(f"处理日期 {date} 时出错：{str(e)}")
        import traceback
        traceback.print_exc()
        return (False, date, None)


def parallel_process_dates_dynamic(start_time, end_time, contact, file_path, matcher,
                              daily_counts=None, max_workers=8):
    """
    多线程并行处理所有日期（动态版本）

    参数:
        start_time: 开始时间
        end_time: 结束时间
        contact: 联系人信息
        file_path: 文件保存路径
        matcher: PhoneEventMatcher 实例
        daily_counts: 每天计划生成的数据量字典 {date: count}，默认 None（随机 2-7）
        max_workers: 最大并行线程数

    返回:
        处理统计结果
    """
    # 收集所有处理结果
    success_dates = []
    failed_dates = []

    # 收集所有生成的数据
    registered_generators = get_registered_generators(file_path)
    data_collector = {gen_info['filename']: [] for gen_info in registered_generators.values()}

    # 创建线程池，并行处理所有日期
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有日期的处理任务
        futures = []
        for date in iterate_dates(start_time, end_time):
            # 获取该天的计划数据量，没有则随机生成
            if daily_counts and date in daily_counts:
                target_count = daily_counts[date]
            else:
                target_count = random.randint(2, 7)

            future = executor.submit(
                process_single_date_dynamic,
                date=date,
                contact=contact,
                file_path=file_path,
                matcher=matcher,
                phone_count_control={"min": target_count, "max": target_count}
            )
            futures.append(future)
        
        # 等待所有任务完成并收集结果
        for future in as_completed(futures):
            success, date, generated_data = future.result()
            if success:
                success_dates.append(date)
                # 合并生成的数据到收集器
                for filename, data in generated_data.items():
                    # 如果 data_collector 中不存在该键，先创建
                    if filename not in data_collector:
                        data_collector[filename] = []
                    if isinstance(data, list) and isinstance(data_collector[filename], list):
                        data_collector[filename].extend(data)
                    else:
                        data_collector[filename] = data
            else:
                failed_dates.append(date)
    
    # 创建 phone_data 文件夹（如果不存在）
    phone_data_dir = os.path.join(file_path, "phone_data")
    os.makedirs(phone_data_dir, exist_ok=True)
    
    # 将所有收集的数据写入文件（增量式，保留原有数据）
    for filename, data in data_collector.items():
        file_path_full = os.path.join(phone_data_dir, filename)
        try:
            # 读取原有数据
            existing_data = []
            if os.path.exists(file_path_full):
                with open(file_path_full, "r", encoding="utf-8") as f:
                    file_content = f.read().strip()
                    if file_content:
                        existing_data = json.loads(file_content)
                    else:
                        existing_data = []
            
            # 合并数据
            if isinstance(data, list) and isinstance(existing_data, list):
                merged_data = existing_data + data
            else:
                merged_data = data
            
            # 写入合并后的数据
            with open(file_path_full, "w", encoding="utf-8") as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 数据成功写入文件：{filename}")
            print(f"   共写入 {len(merged_data)} 条数据")
        except json.JSONDecodeError as e:
            print(f"❌ 文件 {filename} JSON 格式错误，将覆盖原有文件：{str(e)}")
            with open(file_path_full, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 写入文件 {filename} 时出错：{str(e)}")
    
    # 输出统计信息
    total_dates = len(success_dates) + len(failed_dates)
    print(f"\n处理完成统计：")
    print(f"总日期数：{total_dates}")
    print(f"成功处理：{len(success_dates)} 个")
    print(f"处理失败：{len(failed_dates)} 个")
    if failed_dates:
        print(f"失败日期：{failed_dates}")
    
    return {
        "total": total_dates,
        "success": len(success_dates),
        "failed": len(failed_dates),
        "failed_dates": failed_dates
    }


def process_phone_data(file_path):
    """
    处理手机数据的后处理操作：分类、排序、添加 phone_id
    :param file_path: 数据文件路径
    """
    # 数据后处理：分类、排序、添加 phone_id
    print(f"\n开始数据后处理...")

    # 1. 定义需要处理的文件（除了 contact.json）
    phone_data_dir = os.path.join(file_path, "phone_data")

    files_to_process = [f for f in os.listdir(phone_data_dir) if f.endswith('.json') and f.startswith('event_')]

    # 2. 创建 process 文件夹
    process_dir = os.path.join(file_path, "process")
    process_dir = os.path.join(process_dir, "phone_data")
    os.makedirs(process_dir, exist_ok=True)

    # 3. 处理每个文件
    for filename in files_to_process:
        file_path_old = os.path.join(phone_data_dir, filename)

        # 读取原始数据
        with open(file_path_old, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 特殊处理 event_perception.json 文件
        if filename == "event_perception.json":
            # 直接保留所有数据，不按 type 分类
            # 排序：先按 date 排序，再按 time 数组的第一个元素排序
            sorted_data = sorted(data, key=lambda x: (x.get('date', ''), x.get('time', [''])[0]))

            # 添加 phone_id
            for i, item in enumerate(sorted_data):
                item['phone_id'] = i

            # 保存为新文件 perception.json
            new_filename = "perception.json"
            new_file_path = os.path.join(phone_data_dir, new_filename)
            with open(new_file_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_data, f, ensure_ascii=False, indent=2)

            print(f"✅ 生成新文件：{new_filename}，共 {len(sorted_data)} 条记录")
        else:
            # 其他文件按 type 分类
            # 按 type 分类
            type_dict = {}
            for item in data:
                if 'type' in item:
                    data_type = item['type']
                    if data_type not in type_dict:
                        type_dict[data_type] = []
                    type_dict[data_type].append(item)
                else:
                    # 如果没有 type 字段，使用文件名作为类型
                    data_type = filename.replace('event_', '').replace('.json', '')
                    if data_type not in type_dict:
                        type_dict[data_type] = []
                    type_dict[data_type].append(item)

            # 生成新文件并排序
            for data_type, type_data in type_dict.items():
                # 排序
                if data_type in ['call', 'gallery', 'note', 'calendar', 'push', 'photo', 'sms']:
                    # 使用 datetime 字段排序
                    sorted_data = sorted(type_data, key=lambda x: x.get('datetime', ''))
                elif data_type == 'fitness_health':
                    # 按日期字段排序
                    sorted_data = sorted(type_data, key=lambda x: x.get('日期', ''))
                elif data_type == 'agent_chat':
                    # 按 date 字段排序
                    sorted_data = sorted(type_data, key=lambda x: x.get('date', ''))
                else:
                    # 默认按 datetime 排序
                    sorted_data = sorted(type_data, key=lambda x: x.get('datetime', ''))

                # 添加 phone_id
                for i, item in enumerate(sorted_data):
                    item['phone_id'] = i

                # 保存新文件
                new_filename = f"{data_type}.json"
                new_file_path = os.path.join(phone_data_dir, new_filename)
                with open(new_file_path, 'w', encoding='utf-8') as f:
                    json.dump(sorted_data, f, ensure_ascii=False, indent=2)

                print(f"✅ 生成新文件：{new_filename}，共 {len(sorted_data)} 条记录")

        # 将老文件移动到 process 文件夹
        new_file_path_old = os.path.join(process_dir, filename)
        os.replace(file_path_old, new_file_path_old)
        print(f"📁 已将原文件 {filename} 移动到 process 文件夹")

    print(f"\n数据后处理完成！")


class PhoneEventMatcher:
    """
    手机事件与原子事件匹配器
    功能：基于当日事件的atomic_id，为手机操作数据匹配对应的原子事件
    """

    def __init__(self, atomic_events_file: str):
        self.context = "你是一位事件匹配专家，擅长分析手机操作与原子事件之间的关联性"
        self.atomic_events_file = atomic_events_file
        # PhoneDataGenerator 在第一次使用时创建（确保 extool 已加载数据）
        self._phone_data_generator = None
    
    @property
    def phone_data_generator(self):
        """延迟初始化 PhoneDataGenerator，确保 extool 已加载数据"""
        if self._phone_data_generator is None:
            self._phone_data_generator = PhoneDataGenerator(extool)
        return self._phone_data_generator

    def match_phone_events_with_atomic_events(self, phone_operations: List[Dict], date: str, generate_unmatched: bool = False) -> Dict:
        """
        匹配手机操作数据与原子事件

        参数:
            phone_operations: 手机操作数据列表
            date: 要匹配的日期，格式为YYYY-MM-DD
            generate_unmatched: 是否为未匹配的原子事件生成手机操作数据，默认值为True

        返回:
            Dict: 包含两个字段：
                - matched_phone_events: 匹配后的手机操作数据，每个事件包含atomic_id字段
                - unmatched_atomic_events: 当日未被手机数据体现的原子事件
        """
        try:
            # 使用延迟初始化的 PhoneDataGenerator
            phone_data_generator = self.phone_data_generator
            
            # 步骤1：加载原子事件数据
            atomic_events_data = self._load_atomic_events(self.atomic_events_file)
            all_atomic_events = atomic_events_data.get("all_atomic_events", {})
            date_based_atomic_events = atomic_events_data.get("date_based_atomic_events", {})
            print(f"成功加载原子事件数据，共 {len(all_atomic_events)} 个原子事件")
            
            # 步骤2：获取当日的原子事件
            daily_atomic_events = date_based_atomic_events.get(date, [])
            print(f"当日（{date}）共有 {len(daily_atomic_events)} 个原子事件")
            
            # 步骤3：通过extool获取当日事件数据，并筛选出有atomic_id的事件
            daily_events = extool.filter_by_date(date)
            
            events_with_atomic_ids = []
            all_atomic_ids = set()
            
            for event in daily_events:
                atomic_ids = event.get("atomic_id", [])
                if atomic_ids:
                    events_with_atomic_ids.append(event)
                    all_atomic_ids.update(atomic_ids)
            
            print(f"当日事件中共有 {len(events_with_atomic_ids)} 个事件包含atomic_id，共 {len(all_atomic_ids)} 个原子事件")
            
            # 步骤4：合并当日原子事件和当日事件关联的原子事件
            # 从当日原子事件中提取原子事件ID
            daily_atomic_event_ids = {event.get("event_id", "") for event in daily_atomic_events}
            # 合并所有相关原子事件ID
            all_relevant_atomic_ids = all_atomic_ids.union(daily_atomic_event_ids)
            
            # 确保当日事件的所有atomic_id都能被包含在当日原子事件中
            # 检查当日事件的atomic_id是否在all_atomic_events中存在
            for atomic_id in all_atomic_ids:
                if atomic_id not in all_atomic_events:
                    print(f"警告：原子事件ID {atomic_id} 在all_atomic_events中不存在")
            
            # 确保所有相关原子事件ID都在all_atomic_events中存在
            all_relevant_atomic_ids = {atomic_id for atomic_id in all_relevant_atomic_ids if atomic_id in all_atomic_events}
            
            # 确保当日事件的所有atomic_id都被包含在当日原子事件中
            # 即使这些atomic_id不在date_based_atomic_events中
            for atomic_id in all_atomic_ids:
                if atomic_id in all_atomic_events and atomic_id not in daily_atomic_event_ids:
                    # 如果该atomic_id不在当日原子事件中，添加到当日原子事件列表
                    atomic_event_info = all_atomic_events.get(atomic_id, {})
                    daily_atomic_events.append({
                        "event_id": atomic_id,
                        "name": atomic_event_info.get("name", f"原子事件_{atomic_id}"),
                        "description": atomic_event_info.get("description", ""),
                        "date": [date]
                    })
                    print(f"添加原子事件ID {atomic_id} 到当日原子事件列表")
            
            print(f"当日所有相关原子事件ID：{len(all_relevant_atomic_ids)} 个")
            
            # 如果没有原子事件或手机操作，直接返回
            if not all_relevant_atomic_ids or not phone_operations:
                return {
                    "matched_phone_events": phone_operations,
                    "unmatched_atomic_events": list(all_relevant_atomic_ids)
                }
            
            # 步骤5：准备原子事件文本 - 从all_atomic_events中获取完整的原子事件信息
            atomic_events_text = "\n".join([
                f"原子事件ID {atomic_id}: {all_atomic_events.get(atomic_id, {}).get('name', '')} - {all_atomic_events.get(atomic_id, {}).get('description', '')}"
                for atomic_id in all_relevant_atomic_ids
                if atomic_id in all_atomic_events
            ])
            
            # 步骤6：准备当日事件背景信息（有atomic_id的事件）
            daily_events_background = "\n".join([
                f"当日事件ID {event.get('event_id', '')}: {event.get('name', '')} - {event.get('description', '')}\n  关联原子事件: {', '.join(event.get('atomic_id', []))}"
                for event in events_with_atomic_ids
            ])
            
            # 步骤7：为每个手机操作添加序号并准备文本
            # 先为每个手机操作添加序号字段
            phone_ops_with_index = []
            for i, op in enumerate(phone_operations):
                op_with_index = op.copy()
                op_with_index['index'] = i + 1  # 添加序号字段
                phone_ops_with_index.append(op_with_index)
            
            # 转换为JSON格式
            phone_operations_text = json.dumps(phone_ops_with_index, ensure_ascii=False, indent=2)
            
            # 步骤8：调用LLM进行匹配
            prompt = self._generate_match_prompt(atomic_events_text, phone_operations_text, daily_events_background)
            print("LLM调用参数：", prompt)
            match_result = llm_call_reason_j(prompt, self.context)
            print("LLM返回结果：", match_result)
            # 步骤9：解析匹配结果
            matched_indices = self._parse_match_result(match_result, len(phone_operations))
            
            # 步骤10：为手机操作添加atomic_id字段
            matched_phone_events = []
            matched_atomic_ids = set()
            
            for i, op in enumerate(phone_operations):
                if i in matched_indices:
                    op["atomic_id"] = matched_indices[i]
                    matched_atomic_ids.update(matched_indices[i])
                else:
                    op["atomic_id"] = []
                matched_phone_events.append(op)
            
            # 步骤11：找出未被匹配的原子事件
            unmatched_atomic_events = list(all_relevant_atomic_ids - matched_atomic_ids)
            
            print(f"匹配完成：{len(matched_atomic_ids)} 个原子事件被手机数据体现，{len(unmatched_atomic_events)} 个未被体现")
            
            # 步骤12：为未匹配的原子事件生成手机操作数据
            if generate_unmatched and unmatched_atomic_events:
                print(f"为 {len(unmatched_atomic_events)} 个未匹配的原子事件生成手机操作数据")
                for atomic_id in unmatched_atomic_events:
                    # 获取原子事件信息
                    atomic_event_info = all_atomic_events.get(atomic_id, {})
                    print(f"原子事件ID {atomic_id}：{atomic_event_info.get('name', '')} - {atomic_event_info.get('description', '')}")
                    if atomic_event_info:
                        # 查找包含该atomic_id的当日事件
                        event_id = None
                        for event in events_with_atomic_ids:
                            event_atomic_ids = event.get("atomic_id", [])
                            print(f"事件ID {event.get('event_id', '')}：{event.get('name', '')} - {event.get('description', '')}")
                            print(f"事件包含的 atomic_id：{event_atomic_ids}")
                            if atomic_id in event_atomic_ids:
                                event_id = event.get("event_id", '')
                                break
                        print(f"找到事件ID {event_id}，原子事件ID {atomic_id}")
                        # 如果没有匹配到对应的每日事件，则跳过这个原子事件的手机生成
                        if not event_id:
                            print(f"未找到包含原子事件ID {atomic_id} 的当日事件，跳过手机数据生成")
                            continue
                        
                        # 构造事件信息
                        event_info = {
                            "event_id": event_id,
                            "atomic_id": [atomic_id],
                            "name": atomic_event_info.get("name", f"原子事件_{atomic_id}"),
                            "description": atomic_event_info.get("description", "")
                        }
                        # 生成手机操作数据
                        generated_data = phone_data_generator.generate(date, event_info)
                        # 将生成的数据添加到matched_phone_events中
                        for data_type, data_list in generated_data.items():
                            for data in data_list:
                                data['atomic_id'] = [atomic_id]
                                matched_phone_events.append(data)
                # 清空未匹配原子事件列表，因为已经生成了对应的数据
                unmatched_atomic_events = []
            
            # 步骤13：photo 类数据增强 - 为没有 atomic_id 的 photo 数据匹配相关事件
            print("开始 photo 类数据增强...")
            photo_ops_without_atomic = [
                op for op in matched_phone_events 
                if op.get('type') == 'photo' and not op.get('atomic_id', [])
            ]
            
            if photo_ops_without_atomic:
                print(f"发现 {len(photo_ops_without_atomic)} 个没有 atomic_id 的 photo 数据")
                
                # 从完整事件树中查找所有起始时间包含 target_date 的事件
                def find_events_with_date(events, target_date):
                    """
                    遍历事件树，筛选出 date 在起止日期之内的事件
                    
                    参数:
                        events: 事件列表
                        target_date: 目标日期
                    
                    返回:
                        符合条件的事件列表
                    """
                    result = []
                    for event in events:
                        # 检查事件的日期是否包含 target_date
                        date_list = event.get("date", [])
                        if not isinstance(date_list, list):
                            date_list = [date_list]
                        
                        for date_str in date_list:
                            try:
                                # 处理日期范围
                                if "至" in date_str:
                                    # 有"至"分割，提取起始和结束日期
                                    parts = date_str.split("至")
                                    # 提取规范化的 YYYY-MM-DD 格式
                                    start_date_str = parts[0].strip()[:10]
                                    end_date_str = parts[1].strip()[:10]
                                    print(f"日期范围: {start_date_str} 至 {end_date_str}"f"处理日期范围：{date_str}")
                                    # 判断目标日期是否在起止日期之内（包含边界）
                                    if start_date_str <= target_date <= end_date_str:
                                        result.append(event)
                                        break
                                else:
                                    # 没有"至"，起止日期是同一天
                                    single_date = date_str.strip()[:10]
                                    if target_date == single_date:
                                        result.append(event)
                                        break
                            except:
                                continue
                    
                    return result
                
                # 从 atomic_events_file 加载完整事件树
                try:
                    with open(self.atomic_events_file, "r", encoding="utf-8") as f:
                        events_tree = json.load(f)
                    print(f"成功从 {self.atomic_events_file} 加载事件树")
                except Exception as e:
                    print(f"加载事件树失败：{str(e)}")
                    events_tree = []
                
                # 获取所有符合条件的事件
                top_level_parents = find_events_with_date(events_tree, date)
                print(f"找到 {len(top_level_parents)} 个起始时间包含 {date} 的最顶层父亲节点")
                
                if top_level_parents:
                    # 准备 LLM 分析所需的文本
                    parents_text = "\n".join([
                        f"事件ID: {p.get('event_id', '')}\n"
                        f"事件名称: {p.get('name', '')}\n"
                        f"事件描述: {p.get('description', '')}\n"
                        f"事件日期: {p.get('date', '')}\n"
                        for p in top_level_parents
                    ])
                    
                    photos_text = "\n".join([
                        f"Photo索引 {i}: "
                        f"caption={op.get('caption', '')}, "
                        f"title={op.get('title', '')}, "
                        f"datetime={op.get('datetime', '')}, "
                        f"location={json.dumps(op.get('location', {}), ensure_ascii=False)}, "
                        for i, op in enumerate(photo_ops_without_atomic)
                    ])
                    
                    # 调用 LLM 分析 photo 与事件的关联
                    analysis_prompt = f"""
请分析以下 photo 数据与当日相关事件的关联性，并为每个 photo 分配最相关的 event_id。

## 当日相关的最顶层父亲事件
{parents_text}

## 需要分析的 Photo 数据
{photos_text}

## 分析要求
1. 仔细阅读每个 photo 的 caption、location等信息
2. 分析 photo 内容与哪个事件最相关（基于地点、主题、时间等）
3. **如果 photo 与某个事件明显相关**，分配该事件的 event_id
4. **如果 photo 与任何事件都不相关或关联性很弱**，可以不分配 event_id（返回空字符串）
5. 一个 photo 最多只能关联一个 event_id
6. **不要强行匹配**：如果 photo 内容与所有事件都没有明显关联，保持为空即可

## 输出格式
仅输出 JSON 对象，格式如下：
{{
    "0": "event_id_1",  // Photo索引0关联的事件ID，如无关联则为空字符串
    "1": "",            // Photo索引1无关联，不分配
    "2": "event_id_2"
}}

注意：
- 键为 photo 在列表中的索引（从0开始）
- 值为 event_id 字符串，**无关联或不分配则为空字符串**
- **宁可少分配，不要错分配**：只有当 photo 与事件有明显关联时才分配
- 只输出 JSON，不要包含其他文本
                    """
                    
                    try:
                        print(prompt)
                        analysis_result = llm_call_reason_j(analysis_prompt, self.context)
                        print(f"LLM 分析结果：{analysis_result}")
                        
                        # 解析结果
                        cleaned_result = remove_json_wrapper(analysis_result, json_type='object')
                        mapping = json.loads(cleaned_result)
                        
                        # 为 photo 数据赋值 atomic_id（前缀加上 a_）
                        for idx_str, event_id in mapping.items():
                            idx = int(idx_str)
                            if 0 <= idx < len(photo_ops_without_atomic) and event_id:
                                # 在 event_id 前缀加上 a_
                                atomic_id_with_prefix = f"a_{event_id}"
                                photo_ops_without_atomic[idx]["atomic_id"] = [atomic_id_with_prefix]
                                print(f"Photo索引 {idx} 关联到事件 {atomic_id_with_prefix}")
                        
                        print("Photo 数据增强完成")
                    except Exception as e:
                        print(f"Photo 数据增强失败：{str(e)}")
                        import traceback
                        traceback.print_exc()
            else:
                print("没有需要增强的 photo 数据")
            
            return {
                "matched_phone_events": matched_phone_events,
                "unmatched_atomic_events": unmatched_atomic_events
            }
            
        except Exception as e:
            print(f"匹配手机事件与原子事件时出错：{str(e)}")
            import traceback
            traceback.print_exc()
            # 出错时，为所有手机事件添加空的atomic_id
            for op in phone_operations:
                op["atomic_id"] = []
            
            # 返回所有原子事件作为未匹配
            all_relevant_atomic_ids = set()
            # 重新获取当日原子事件
            try:
                atomic_events_data = self._load_atomic_events(self.atomic_events_file)
                date_based_atomic_events = atomic_events_data.get("date_based_atomic_events", {})
                daily_atomic_events = date_based_atomic_events.get(date, [])
                daily_atomic_event_ids = {event.get("event_id", "") for event in daily_atomic_events}
                
                # 重新获取当日事件的atomic_id
                daily_events = extool.filter_by_date(date)
                for event in daily_events:
                    all_relevant_atomic_ids.update(event.get("atomic_id", []))
                
                # 合并
                all_relevant_atomic_ids.update(daily_atomic_event_ids)
                
                # 确保当日事件的所有atomic_id都被包含在当日原子事件中
                # 即使这些atomic_id不在date_based_atomic_events中
                all_atomic_events = atomic_events_data.get("all_atomic_events", {})
                for atomic_id in all_relevant_atomic_ids:
                    if atomic_id in all_atomic_events and atomic_id not in daily_atomic_event_ids:
                        # 如果该atomic_id不在当日原子事件中，添加到当日原子事件列表
                        atomic_event_info = all_atomic_events.get(atomic_id, {})
                        daily_atomic_events.append({
                            "event_id": atomic_id,
                            "name": atomic_event_info.get("name", f"原子事件_{atomic_id}"),
                            "description": atomic_event_info.get("description", ""),
                            "date": [date]
                        })
                        print(f"添加原子事件ID {atomic_id} 到当日原子事件列表")
                
                # 尝试为未匹配的原子事件生成手机操作数据
                if generate_unmatched:
                    try:
                        phone_data_generator = self.phone_data_generator
                        for atomic_id in all_relevant_atomic_ids:
                            atomic_events_data = self._load_atomic_events(self.atomic_events_file)
                            all_atomic_events = atomic_events_data.get("all_atomic_events", {})
                            atomic_event_info = all_atomic_events.get(atomic_id, {})
                            if atomic_event_info:
                                # 查找包含该atomic_id的当日事件
                                event_id = None
                                try:
                                    daily_events = extool.filter_by_date(date)
                                    for event in daily_events:
                                        event_atomic_ids = event.get("atomic_id", [])
                                        if atomic_id in event_atomic_ids:
                                            event_id = event.get("event_id", atomic_id)
                                            break
                                except Exception as e4:
                                    print(f"查找包含atomic_id的事件时出错：{str(e4)}")
                                
                                # 如果没有匹配到对应的每日事件，则跳过这个原子事件的手机生成
                                if not event_id:
                                    print(f"未找到包含原子事件ID {atomic_id} 的当日事件，跳过手机数据生成")
                                    continue
                                
                                event_info = {
                                    "event_id": event_id,
                                    "atomic_id": [atomic_id],
                                    "name": atomic_event_info.get("name", f"原子事件_{atomic_id}"),
                                    "description": atomic_event_info.get("description", "")
                                }
                                generated_data = phone_data_generator.generate(date, event_info)
                                for data_type, data_list in generated_data.items():
                                    for data in data_list:
                                        phone_operations.append(data)
                        # 清空未匹配原子事件列表，因为已经生成了对应的数据
                        all_relevant_atomic_ids = set()
                    except Exception as e3:
                        print(f"为未匹配原子事件生成数据时出错：{str(e3)}")
            except Exception as e2:
                print(f"获取未匹配原子事件时出错：{str(e2)}")
            
            return {
                "matched_phone_events": phone_operations,
                "unmatched_atomic_events": list(all_relevant_atomic_ids)
            }
    
    def _load_atomic_events(self, atomic_events_file: str) -> Dict[str, Dict]:
        """
        加载原子事件数据
        
        参数:
            atomic_events_file: 原子事件数据文件路径
            
        返回:
            Dict: 包含两个键的字典：
                - "all_atomic_events": 所有原子事件字典，键为atomic_id，值为原子事件数据
                - "date_based_atomic_events": 按日期组织的原子事件，键为日期字符串，值为该日期的原子事件列表
        """
        try:
            if os.path.exists(atomic_events_file):
                with open(atomic_events_file, "r", encoding="utf-8") as f:
                    events_data = json.load(f)
                
                # 递归提取所有最底层事件（decompose=0）作为原子事件
                def extract_atomic_events(events):
                    atomic_events = []
                    for event in events:
                        # 如果是原子事件（decompose=0）
                        if event.get("decompose") == 0:
                            atomic_events.append(event)
                        # 如果有子事件，递归提取
                        elif "subevent" in event:
                            atomic_events.extend(extract_atomic_events(event["subevent"]))
                    return atomic_events
                
                # 提取所有原子事件
                atomic_events = extract_atomic_events(events_data)
                
                # 将原子事件转换为字典格式
                all_atomic_events = {}
                date_based_atomic_events = {}
                
                for atomic_event in atomic_events:
                    event_id = atomic_event.get("event_id")
                    if event_id:
                        all_atomic_events[event_id] = atomic_event
                        
                        # 按日期组织原子事件
                        date_list = atomic_event.get("date", [])
                        if not isinstance(date_list, list):
                            date_list = [date_list]
                        
                        for date_str in date_list:
                            # 处理日期范围（如"2025-01-19至2025-01-19"）
                            if "至" in date_str:
                                start_date, end_date = date_str.split("至")
                                start_date = start_date.strip()[:10]  # 确保格式为YYYY-MM-DD
                                end_date = end_date.strip()[:10]  # 确保格式为YYYY-MM-DD
                                # 这里简化处理，只取开始日期
                                date_key = start_date
                            else:
                                date_key = date_str.strip()[:10]  # 确保格式为YYYY-MM-DD
                            
                            if date_key not in date_based_atomic_events:
                                date_based_atomic_events[date_key] = []
                            
                            date_based_atomic_events[date_key].append(atomic_event)
                        
                print(f"成功从event_tree2.json提取 {len(all_atomic_events)} 个原子事件，分布在 {len(date_based_atomic_events)} 个日期")
                
                return {
                    "all_atomic_events": all_atomic_events,
                    "date_based_atomic_events": date_based_atomic_events
                }
            else:
                print(f"原子事件文件不存在：{atomic_events_file}")
                return {
                    "all_atomic_events": {},
                    "date_based_atomic_events": {}
                }
            
        except Exception as e:
            print(f"加载原子事件数据时出错：{str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "all_atomic_events": {},
                "date_based_atomic_events": {}
            }
    
    def _generate_match_prompt(self, atomic_events_text: str, phone_operations_text: str, daily_events_background: str = "") -> str:
        """
        生成匹配提示
        
        参数:
            atomic_events_text: 原子事件文本
            phone_operations_text: 手机操作JSON文本
            daily_events_background: 当日事件背景信息（有atomic_id的事件）
            
        返回:
            str: 匹配提示
        """
        return f"""
        请仔细分析以下JSON格式的手机操作数据、当日事件背景以及原子事件列表，找出每个手机操作与哪些原子事件相关：
        
        当日事件背景（这些事件包含atomic_id字段，代表与原子事件的对应关系）：
        {daily_events_background}
        
        原子事件列表：
        {atomic_events_text}
        
        手机操作数据（JSON格式）：
        {phone_operations_text}
        
        匹配要求：
        1. 分析每个手机操作的类型和内容，判断其与哪些原子事件相关
        2. 一个手机操作可能与多个原子事件相关，需列出所有相关的原子事件ID
        3. 如果某个手机操作与任何原子事件都不相关，请返回空列表
        
        返回格式：
        请返回JSON格式的字典，键为手机操作索引（数字，从1开始，表示手机操作列表中的第几个元素），值为相关的原子事件ID数组。
        例如：
        {{
            "1": ["159-1", "159-2"],
            "2": [],
            "3": ["159-3"]
        }}
        
        注意：
        - 只返回JSON数据，不要包含任何额外的解释或说明
        - 确保JSON格式正确，没有语法错误
        - 原子事件ID必须是字符串格式
        - 手机操作索引必须与输入的手机操作列表顺序一致
        """
    
    def _parse_match_result(self, match_result: str, phone_ops_count: int) -> Dict[int, List[str]]:
        """
        解析匹配结果
        
        参数:
            match_result: LLM返回的匹配结果
            phone_ops_count: 手机操作数量
            
        返回:
            Dict: 键为手机操作索引（从0开始），值为匹配的原子事件ID列表
        """
        matched_indices = {i: [] for i in range(phone_ops_count)}
        
        try:
            # 清理匹配结果
            cleaned_result = remove_json_wrapper(match_result, json_type='object')
            match_mappings = json.loads(cleaned_result)
            
            # 转换为0-based索引
            for phone_op_id_str, atomic_ids in match_mappings.items():
                phone_op_id = int(phone_op_id_str) - 1
                if 0 <= phone_op_id < phone_ops_count:
                    matched_indices[phone_op_id] = atomic_ids
            
        except Exception as e:
            print(f"解析匹配结果时出错：{str(e)}")
        
        return matched_indices

class PhoneDataGenerator:
    """
    手机操作数据生成器
    输入日期和目标事件信息，生成对应的手机操作数据
    支持：短信、通话、图片、推送、笔记、日历数据
    """
    def __init__(self, extool=None):
        """初始化手机数据生成器"""
        self.context = "你是一名手机数据生成专家，能够根据事件信息生成相应的手机操作数据"
    
    def get_daily_events(self, date: str, extool=None) -> List[Dict]:
        """
        通过extool获取当日事件作为背景信息
        
        参数:
            date: 日期
            extool: 提供事件上下文的工具
            
        返回:
            List[Dict]: 当日事件列表
        """
        if extool and hasattr(extool, 'get_daily_events'):
            return extool.get_daily_events(date)
        return []
    
    def determine_data_type(self, date: str, event_info: Dict, extool=None) -> List[Dict]:
        """
        调用LLM判断生成什么类别的手机操作数据
        
        参数:
            date: 日期，格式如"2025-01-01"
            event_info: 目标事件信息
            extool: 提供事件上下文的工具
            
        返回:
            List[Dict]: 要生成的数据类型和生成指导列表，如[
                {"type": "sms", "generate_text": "生成一条关于会议提醒的短信"},
                {"type": "calendar", "generate_text": "生成会议的日历记录"}
            ]
        """
        # 获取当日事件作为背景信息
        daily_events = self.get_daily_events(date, extool)
        daily_events_str = json.dumps(daily_events, ensure_ascii=False) if daily_events else "无"
        
        # 提取event_id和atomic_id
        event_id = event_info.get('event_id', '')
        atomic_id = event_info.get('atomic_id', [])
        
        prompt = f"""
        请作为手机数据生成专家，分析以下事件信息，并思考应该生成哪些类型的手机操作数据（1-3个）来共同反映该事件。
        
        ## 输入信息
        - 日期: {date}
        - 当日事件背景: {daily_events_str}
        - 目标事件信息: {json.dumps(event_info, ensure_ascii=False)}
        
        ## 可选数据类型
        1. 短信 (sms)
        2. 通话 (call)
        3. 图片 (photo)
        4. 推送 (notification)
        5. 笔记 (note)
        6. 日历 (calendar)
        
        ## 分析要求
        1. 任意选择最能共同反映该事件的数据类型，可以多类型，也可以都为同一类信息
        2. 解释为什么选择这些数据类型，它们如何共同反映事件
        3. 为每个数据类型提供具体的生成指导（生成文本）
        4. 生成的数据数目尽可能少，但要求能反映事件的全部信息，尽量多样化生成。数目不超过三个。
        ## 输出格式要求
        仅输出JSON数组，严格遵循以下格式，不添加任何额外文本：
        [
            {{"type": "<数据类型>", "generate_text": "<具体生成指导>"}},
            {{"type": "<数据类型>", "generate_text": "<具体生成指导>"}}
        ]
        
        示例：
        [
            {{"type": "calendar", "generate_text": "生成关于项目会议的日历记录，包含时间、地点、参会人员和会议主题"}},
            {{"type": "sms", "generate_text": "生成项目经理发送的会议提醒短信，包含会议时间和地点"}}
        ]
        """
        print(prompt)
        response = llm_call(prompt, self.context)
        response = self.remove_json_wrapper(response)
        print( response)
        try:
            data_types = json.loads(response)
            # 验证数据格式并添加event_id和atomic_id
            valid_types = []
            for item in data_types:
                if isinstance(item, dict) and "type" in item and "generate_text" in item:
                    item_type = item["type"]
                    if item_type in ["sms", "call", "photo", "notification", "note", "calendar"]:
                        # 直接添加event_id和atomic_id，不依赖LLM生成
                        item["event_id"] = event_id
                        item["atomic_id"] = atomic_id
                        valid_types.append(item)
            return valid_types[:3]  # 最多返回3个
        except json.JSONDecodeError:
            return []
    
    def generate_sms_data(self, date: str, event_info: Dict, generate_text: str = "", event_id: str = "", atomic_id: List = []) -> List[Dict]:
        """
        生成短信数据
        
        参数:
            date: 日期
            event_info: 事件信息
            generate_text: 生成指导文本
            event_id: 事件ID
            atomic_id: 原子事件ID列表
            
        返回:
            List[Dict]: 短信数据列表
        """
        # 获取生成指导
        generate_guide = generate_text if generate_text else "生成一条与事件相关的短信数据"
        
        prompt = f"""
        请根据以下事件信息和生成指导生成短信数据。
        
        ## 输入信息
        - 日期: {date}
        - 事件信息: {json.dumps(event_info, ensure_ascii=False)}
        - 生成指导: {generate_guide}
        - 事件ID: {event_id}
        - 原子事件ID: {json.dumps(atomic_id, ensure_ascii=False)}
        
        ## 输出格式要求
        仅输出JSON数组，严格遵循以下格式，不添加任何额外文本：
        [
            {{
                "type": "sms",
                "event_id": "{event_id}",
                "message_content": "<短信内容>",
                "contactName": "<联系人姓名>",
                "phoneNumber": "<电话号码>",
                "datetime": "<日期时间，格式为YYYY-MM-DD HH:MM:SS>",
                "message_type": "<接收/发送>",
                "atomic_id": {json.dumps(atomic_id, ensure_ascii=False)},
                "phone_id": 0
            }}
        ]
        
        请确保生成的数据与事件信息相关且合理。
        """
        
        response = llm_call(prompt, self.context)
        response = self.remove_json_wrapper(response)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return []
    
    def generate_call_data(self, date: str, event_info: Dict, generate_text: str = "", event_id: str = "", atomic_id: List = []) -> List[Dict]:
        """
        生成通话数据
        
        参数:
            date: 日期
            event_info: 事件信息
            generate_text: 生成指导文本
            event_id: 事件ID
            atomic_id: 原子事件ID列表
            
        返回:
            List[Dict]: 通话数据列表
        """
        # 获取生成指导
        generate_guide = generate_text if generate_text else "生成一条与事件相关的通话数据"
        
        prompt = f"""
        请根据以下事件信息和生成指导生成通话数据。
        
        ## 输入信息
        - 日期: {date}
        - 事件信息: {json.dumps(event_info, ensure_ascii=False)}
        - 生成指导: {generate_guide}
        - 事件ID: {event_id}
        - 原子事件ID: {json.dumps(atomic_id, ensure_ascii=False)}
        
        ## 输出格式要求
        仅输出JSON数组，严格遵循以下格式，不添加任何额外文本：
        [
            {{
                "type": "call",
                "event_id": "{event_id}",
                "phoneNumber": "<电话号码>",
                "contactName": "<联系人姓名>",
                "datetime": "<开始时间，格式为YYYY-MM-DD HH:MM:SS>",
                "datetime_end": "<结束时间，格式为YYYY-MM-DD HH:MM:SS>",
                "direction": <1表示接收，0表示发送>,
                "call_result": "<接通/未接通/拒接>",
                "atomic_id": {json.dumps(atomic_id, ensure_ascii=False)},
                "phone_id": 0
            }}
        ]
        
        请确保生成的数据与事件信息相关且合理。
        """
        
        response = llm_call(prompt, self.context)
        response = self.remove_json_wrapper(response)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return []
    
    def generate_photo_data(self, date: str, event_info: Dict, generate_text: str = "", event_id: str = "", atomic_id: List = []) -> List[Dict]:
        """
        生成图片数据
        
        参数:
            date: 日期
            event_info: 事件信息
            generate_text: 生成指导文本
            event_id: 事件ID
            atomic_id: 原子事件ID列表
            
        返回:
            List[Dict]: 图片数据列表
        """
        # 获取生成指导
        generate_guide = generate_text if generate_text else "生成一条与事件相关的图片数据"
        
        prompt = f"""
        请根据以下事件信息和生成指导生成图片数据。
        
        ## 输入信息
        - 日期: {date}
        - 事件信息: {json.dumps(event_info, ensure_ascii=False)}
        - 生成指导: {generate_guide}
        - 事件ID: {event_id}
        - 原子事件ID: {json.dumps(atomic_id, ensure_ascii=False)}
        
        ## 输出格式要求
        仅输出JSON数组，严格遵循以下格式，不添加任何额外文本：
        [
            {{
                "event_id": "{event_id}",
                "type": "photo",
                "caption": "<图片描述>",
                "title": "IMG_<年月日>_<时分秒>",
                "datetime": "<日期时间，格式为YYYY-MM-DD HH:MM:SS>",
                "location": {{
                    "province": "<省份>",
                    "city": "<城市>",
                    "district": "<区县>",
                    "streetName": "<街道>",
                    "streetNumber": "<门牌号>",
                    "poi": "<POI名称>"
                }},
                "faceRecognition": ["<识别到的人脸>", ...] or [],
                "imageTag": ["<标签1>", "<标签2>", ...],
                "ocrText": "<OCR识别文本>",
                "shoot_mode": "<拍摄模式>",
                "image_size": "<图片尺寸>",
                "summarized_info": "<图片操作总结>",
                "atomic_id": {json.dumps(atomic_id, ensure_ascii=False)},
                "phone_id": 0
            }}
        ]
        
        请确保生成的数据与事件信息相关且合理。
        """
        
        response = llm_call(prompt, self.context)
        response = self.remove_json_wrapper(response)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return []
    
    def generate_notification_data(self, date: str, event_info: Dict, generate_text: str = "", event_id: str = "", atomic_id: List = []) -> List[Dict]:
        """
        生成推送通知数据
        
        参数:
            date: 日期
            event_info: 事件信息
            generate_text: 生成指导文本
            event_id: 事件ID
            atomic_id: 原子事件ID列表
            
        返回:
            List[Dict]: 推送通知数据列表
        """
        # 获取生成指导
        generate_guide = generate_text if generate_text else "生成一条与事件相关的手机推送通知数据"
        
        prompt = f"""
        请根据以下事件信息和生成指导生成手机推送通知数据。
        
        ## 输入信息
        - 日期: {date}
        - 事件信息: {json.dumps(event_info, ensure_ascii=False)}
        - 生成指导: {generate_guide}
        - 事件ID: {event_id}
        - 原子事件ID: {json.dumps(atomic_id, ensure_ascii=False)}
        
        ## 输出格式要求
        仅输出JSON数组，严格遵循以下格式，不添加任何额外文本：
        [
            {{
                "type": "push",
                "event_id": "{event_id}",
                "title": "<通知标题>",
                "content": "<通知内容>",
                "datetime": "<日期时间，格式为YYYY-MM-DD HH:MM:SS>",
                "source": "<应用名称>",
                "push_status": "<未读/已读>",
                "jump_path": "<跳转路径>",
                "summarized_info": "<通知内容总结>",
                "atomic_id": {json.dumps(atomic_id, ensure_ascii=False)},
                "phone_id": <手机ID，整数>
            }}
        ]
        
        请确保生成的数据与事件信息相关且合理。
        """
        
        response = llm_call(prompt, self.context)
        response = self.remove_json_wrapper(response)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return []
    
    def generate_note_data(self, date: str, event_info: Dict, generate_text: str = "", event_id: str = "", atomic_id: List = []) -> List[Dict]:
        """
        生成笔记数据
        
        参数:
            date: 日期
            event_info: 事件信息
            generate_text: 生成指导文本
            event_id: 事件ID
            atomic_id: 原子事件ID列表
            
        返回:
            List[Dict]: 笔记数据列表
        """
        # 获取生成指导
        generate_guide = generate_text if generate_text else "生成一条与事件相关的笔记数据"
        
        prompt = f"""
        请根据以下事件信息和生成指导生成笔记数据。
        
        ## 输入信息
        - 日期: {date}
        - 事件信息: {json.dumps(event_info, ensure_ascii=False)}
        - 生成指导: {generate_guide}
        - 事件ID: {event_id}
        - 原子事件ID: {json.dumps(atomic_id, ensure_ascii=False)}
        
        ## 输出格式要求
        仅输出JSON数组，严格遵循以下格式，不添加任何额外文本：
        [
            {{
                "type": "note",
                "event_id": "{event_id}",
                "title": "<笔记标题>",
                "content": "<笔记内容>",
                "datetime": "<日期时间，格式为YYYY-MM-DD HH:MM:SS>",
                "summarized_info": "<笔记操作总结>",
                "atomic_id": {json.dumps(atomic_id, ensure_ascii=False)},
                "phone_id": 0
            }}
        ]
        
        请确保生成的数据与事件信息相关且合理。
        """
        
        response = llm_call(prompt, self.context)
        response = self.remove_json_wrapper(response)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return []
    
    def generate_calendar_data(self, date: str, event_info: Dict, generate_text: str = "", event_id: str = "", atomic_id: List = []) -> List[Dict]:
        """
        生成日历数据
        
        参数:
            date: 日期
            event_info: 事件信息
            generate_text: 生成指导文本
            event_id: 事件ID
            atomic_id: 原子事件ID列表
            
        返回:
            List[Dict]: 日历数据列表
        """
        # 获取生成指导
        generate_guide = generate_text if generate_text else "生成一条与事件相关的日历数据"
        
        prompt = f"""
        请根据以下事件信息和生成指导生成日历数据。
        
        ## 输入信息
        - 日期: {date}
        - 事件信息: {json.dumps(event_info, ensure_ascii=False)}
        - 生成指导: {generate_guide}
        - 事件ID: {event_id}
        - 原子事件ID: {json.dumps(atomic_id, ensure_ascii=False)}
        
        ## 输出格式要求
        仅输出JSON数组，严格遵循以下格式，不添加任何额外文本：
        [
            {{
                "type": "calendar",
                "event_id": "{event_id}",
                "title": "<日历标题>",
                "description": "<日历描述>",
                "start_time": "<开始时间，格式为YYYY-MM-DD HH:MM:SS>",
                "end_time": "<结束时间，格式为YYYY-MM-DD HH:MM:SS>",
                "datetime": "<创建时间，格式为YYYY-MM-DD HH:MM:SS>",
                "summarized_info": "<日历操作总结>",
                "atomic_id": {json.dumps(atomic_id, ensure_ascii=False)},
                "phone_id": 0
            }}
        ]
        
        请确保生成的数据与事件信息相关且合理。
        """
        
        response = llm_call(prompt, self.context)
        response = self.remove_json_wrapper(response)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return []
    
    def remove_json_wrapper(self, input_str: str) -> str:
        """
        移除JSON字符串的包装
        提取从第一个括号到最后一个匹配括号的内容
        """
        # 移除代码块包装
        if input_str.startswith('```json'):
            input_str = input_str[7:]
        if input_str.endswith('```'):
            input_str = input_str[:-3]
        
        # 去除首尾空格
        input_str = input_str.strip()
        
        # 判断是否以{或[开头
        if input_str.startswith('{'):
            # 找到对应的结束括号}
            bracket_count = 0
            end_idx = -1
            for i, char in enumerate(input_str):
                if char == '{':
                    bracket_count += 1
                elif char == '}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        end_idx = i
                        break
            if end_idx != -1:
                input_str = input_str[:end_idx+1]
        elif input_str.startswith('['):
            # 找到对应的结束括号]
            bracket_count = 0
            end_idx = -1
            for i, char in enumerate(input_str):
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        end_idx = i
                        break
            if end_idx != -1:
                input_str = input_str[:end_idx+1]
        
        return input_str
    
    def generate(self, date: str, event_info: Dict, extool=None) -> Dict[str, List[Dict]]:
        """
        生成手机操作数据的主方法
        
        参数:
            date: 日期
            event_info: 事件信息
            extool: 提供事件上下文的工具
            
        返回:
            Dict[str, List[Dict]]: 按数据类型分类的手机操作数据
        """
        # 确定要生成的数据类型和生成指导
        data_type_info = self.determine_data_type(date, event_info, extool)
        
        # 生成对应的数据
        result = {}
        for info in data_type_info:
            data_type = info["type"]
            generate_text = info["generate_text"]
            # 提取event_id和atomic_id
            event_id = info.get("event_id", event_info.get("event_id", ""))
            atomic_id = info.get("atomic_id", event_info.get("atomic_id", []))
            
            if data_type == "sms":
                result["sms"] = self.generate_sms_data(date, event_info, generate_text, event_id, atomic_id)
            elif data_type == "call":
                result["call"] = self.generate_call_data(date, event_info, generate_text, event_id, atomic_id)
            elif data_type == "photo":
                result["photo"] = self.generate_photo_data(date, event_info, generate_text, event_id, atomic_id)
            elif data_type == "notification":
                result["notification"] = self.generate_notification_data(date, event_info, generate_text, event_id, atomic_id)
            elif data_type == "note":
                result["note"] = self.generate_note_data(date, event_info, generate_text, event_id, atomic_id)
            elif data_type == "calendar":
                result["calendar"] = self.generate_calendar_data(date, event_info, generate_text, event_id, atomic_id)
        
        return result