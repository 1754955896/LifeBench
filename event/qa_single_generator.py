"""
QA Single Generator Class
根据用户的事件数据和画像信息生成单跳问答对
单独实现，不继承自QAGenerator类
"""

import json
import os
import random
from typing import Dict, List, Any
from event.template3 import PERSONA_QUESTION_TEMPLATE, EVENT_QUESTION_TEMPLATE, PHONE_OPERATIONS_REGENERATION_TEMPLATE, EVENT_INFERENCE_JUDGMENT_TEMPLATE, QUESTION_SCREENING_OPTIMIZATION_TEMPLATE, USER_SUMMARY_TOPICS_TEMPLATE, PERSONA_BASED_SMS_QUESTION_TEMPLATE
from utils.llm_call import llm_call


class QASingleGenerator:
    """
    QA单跳生成器类，根据用户一年的事件数据和画像信息生成单跳询问问题
    单独实现，不继承自QAGenerator类，便于自由修改QA生成逻辑
    """
    
    def __init__(self, persona_data: Dict[str, Any] = None, event_tree: Dict[str, Any] = None, 
                 daily_event: Dict[str, Any] = None, draft_event: Dict[str, Any] = None, 
                 special_event: Dict[str, Any] = None, phone_data_dir: str = None):
        """
        初始化QA单跳生成器
        
        Args:
            persona_data: 用户画像数据（原始）
            event_tree: 事件树数据
            daily_event: 每日事件数据（原event_data）
            draft_event: 草稿事件数据
            special_event: 特殊事件数据（包含unique_events）
            phone_data_dir: 手机数据文件夹路径
        """
        self.persona_data = persona_data or {}  # persona原
        self.event_tree = event_tree or {}      # event_tree
        self.daily_event = daily_event or {}    # daily_event（原event_data）
        self.draft_event = draft_event or {}    # draft_event
        self.special_event = special_event or {} # special_event（包含unique_events）
        self.phone_data_dir = phone_data_dir    # 手机数据文件夹路径
        self.phonedata = {}                     # 手机数据存储
        self.phone_id_counters = {}             # 手机数据类型的id计数器，用于维护phone_id字段
        
        # 从special_event中提取unique_events
        self.unique_events = self.special_event.get('unique_events', []) if self.special_event else []
        
        # 如果提供了phone_data_dir，则加载手机数据
        if phone_data_dir:
            self.load_phone_data_from_dir(phone_data_dir)
    
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
        
        # 加载特殊事件数据（包含unique_events）
        special_event_path = os.path.join(data_path, "special_event.json")
        if os.path.exists(special_event_path):
            with open(special_event_path, 'r', encoding='utf-8') as f:
                self.special_event = json.load(f)
                # 从special_event中提取unique_events
                self.unique_events = self.special_event.get('unique_events', [])
        
        # 尝试加载手机数据（如果存在phone_data子目录）
        phone_data_path = os.path.join(data_path, "phone_data")
        if os.path.exists(phone_data_path):
            self.load_phone_data_from_dir(phone_data_path)
            self.phone_data_dir = phone_data_path
    
    def set_special_event_with_unique_events(self, special_event_data: Dict[str, Any]):
        """
        设置特殊事件数据并从中提取unique_events
        
        Args:
            special_event_data: 特殊事件数据，其中应包含unique_events字段
        """
        self.special_event = special_event_data
        self.unique_events = self.special_event.get('unique_events', []) if self.special_event else []
    
    def get_draft_event_by_month(self, month: str) -> List[Dict[str, Any]]:
        """
        获取指定月份的draft event数据（仅适配daily_draft.json格式）
        
        Args:
            month: 月份，格式为"YYYY-MM"
            
        Returns:
            指定月份的draft event数据列表
        """
        # 输入验证
        if not month or not isinstance(month, str) or len(month) != 7 or month[4] != '-':
            print(f"月份格式错误: {month}，应为YYYY-MM格式")
            return []
        
        if not self.draft_event or not isinstance(self.draft_event, dict):
            print("draft_event数据不存在或格式错误")
            return []
        
        # 仅处理daily_draft.json格式：直接以月份为键获取数据
        if month in self.draft_event:
            month_data = self.draft_event[month]
            if isinstance(month_data, list):
                print(f"找到{month}月份的draft event数据，共{len(month_data)}条")
                return month_data
            else:
                print(f"{month}对应的数据不是列表格式")
                return []
        
        # 如果没有找到数据，打印日志
        print(f"没有找到{month}月份的draft event数据")
        
        # 列出所有可用的月份，帮助调试
        available_months = [key for key in self.draft_event.keys() 
                          if isinstance(key, str) and len(key) == 7 and key[4] == '-']
        if available_months:
            print(f"可用的月份有: {', '.join(available_months)}")
        
        return []
    
    def generate_persona_based_sms_questions(self, month: str, num_questions: int = 4, existing_questions: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        基于画像生成问题和对应的短信对话数据
        
        Args:
            month: 要分析的月份，格式为"YYYY-MM"
            num_questions: 生成的问题数量（默认4个，两部分各2个）
            existing_questions: 已有的问题列表，用于避免生成相似主题的问题
            
        Returns:
            生成的问题列表，每个问题包含question、answer、score_points和evidence字段
        """
        import concurrent.futures
        
        # 1. 获取指定月份的draft event数据
        month_events = self.get_draft_event_by_month(month)
        for i in range(len(month_events)):
            del month_events[i]["state"]
        if not month_events:
            print(f"没有找到{month}月份的draft event数据")
            return []
        
        # 2. 分割数据为两部分：前15个事件和剩余事件
        events_part1 = month_events[:15]
        events_part2 = month_events[15:]
        
        # 定义并行处理的函数
        def process_events(events, part_name):
            print(f"开始处理{part_name}的数据...")
            
            # 分析数据，获取用户总结和感兴趣的话题
            event_data_str = json.dumps(events, ensure_ascii=False, indent=2)
            prompt = USER_SUMMARY_TOPICS_TEMPLATE.format(event_data=event_data_str)
            
            summary_result = llm_call(prompt)
            print(f"{part_name}用户总结和话题分析结果: {summary_result}")
            
            # 解析结果
            try:
                # 先匹配第一个和最后一个大括号，提取有效的JSON部分
                start_idx = summary_result.find('{')
                end_idx = summary_result.rfind('}')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_content = summary_result[start_idx:end_idx+1]
                    summary_data = json.loads(json_content)
                    user_summary = summary_data.get('user_summary', '')
                    interesting_topics = summary_data.get('interesting_topics', [])
                else:
                    print(f"{part_name}未找到有效的JSON格式数据")
                    return []
            except json.JSONDecodeError:
                print(f"解析{part_name}用户总结和话题失败")
                return []
            
            if not user_summary or not interesting_topics:
                print(f"{part_name}用户总结或话题为空")
                return []
            
            # 生成问题、答案、得分点和短信对话（每个部分生成2个问题）
            persona_info_str = json.dumps(self.persona_data, ensure_ascii=False, indent=2)
            topics_str = json.dumps(interesting_topics, ensure_ascii=False, indent=2)
            
            # 准备已有问题信息，用于避免生成相似主题
            existing_questions_info = ""
            if existing_questions and len(existing_questions) > 0:
                existing_question_texts = [q.get('question', '') for q in existing_questions if q.get('question')]
                existing_questions_info = "\n已有的问题列表（请避免生成相似主题的问题）：\n" + "\n".join(f"- {q}" for q in existing_question_texts[:10])  # 最多显示10个已有问题
            
            prompt = PERSONA_BASED_SMS_QUESTION_TEMPLATE.format(
                num_questions=2,  # 每个部分生成2个问题
                persona_info=persona_info_str,
                user_summary=user_summary,
                interesting_topics=topics_str,
                existing_questions_info=existing_questions_info
            )
            
            questions_result = llm_call(prompt)
            print(f"{part_name}问题生成结果: {questions_result}")
            
            # 解析结果
            try:
                # 先匹配第一个和最后一个大括号，提取有效的JSON部分
                start_idx = questions_result.find('{')
                end_idx = questions_result.rfind('}')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_content = questions_result[start_idx:end_idx+1]
                    questions_data = json.loads(json_content)
                    return questions_data.get('questions', [])
                else:
                    print(f"{part_name}未找到有效的JSON格式数据")
                    return []
            except json.JSONDecodeError:
                print(f"解析{part_name}问题生成结果失败")
                return []
        
        # 3. 并行处理两部分数据
        all_questions = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # 提交两个任务
            future_part1 = executor.submit(process_events, events_part1, "第一部分")
            future_part2 = executor.submit(process_events, events_part2, "第二部分")
            
            # 获取结果
            part1_questions = future_part1.result() or []
            part2_questions = future_part2.result() or []
            
            # 合并结果
            all_questions.extend(part1_questions)
            all_questions.extend(part2_questions)
        
        # 4. 处理所有问题，将'sms_conversations'改为'evidence'，并添加到手机数据中
        final_questions = []
        for question in all_questions:
            if 'sms_conversations' in question:
                sms_conversations = question.pop('sms_conversations')
                
                # 将短信对话数据添加到self.phonedata中的event_sms类型中
                sms_evidence = []
                for sms_op in sms_conversations:
                    # 确保event_id为0
                    sms_op['event_id'] = "0"
                    # 设置正确的数据类型
                    sms_op['type'] = "sms"
                    
                    # 如果event_sms类型不存在，则创建
                    if 'sms' not in self.phonedata:
                        self.phonedata['sms'] = []
                    
                    # 分配phone_id
                    if 'sms' not in self.phone_id_counters:
                        self.phone_id_counters['sms'] = 1
                    sms_op['phone_id'] = str(self.phone_id_counters['sms'])
                    sms_evidence.append({"type": "sms", "id": sms_op['phone_id']})
                    self.phone_id_counters['sms'] += 1
                    
                    # 将短信操作添加到手机数据中
                    self.phonedata['sms'].append(sms_op)
                
                # 设置evidence为包含类型和id的dict列表
                question['evidence'] = sms_evidence
                final_questions.append(question)
        
        # 确保只返回4个问题
        return final_questions[:4]
    
    def get_current_event_data(self, data_type: str = "daily_event"):
        """
        根据类型获取当前使用的事件数据
        
        Args:
            data_type: 数据类型 ("event_tree", "daily_event", "draft_event", "special_event")
            
        Returns:
            对应的事件数据
        """
        if data_type == "event_tree":
            return self.event_tree
        elif data_type == "daily_event":
            return self.daily_event
        elif data_type == "draft_event":
            return self.draft_event
        elif data_type == "special_event":
            return self.special_event
        else:
            # 默认返回daily_event（原event_data）
            return self.daily_event

    def _get_persona_data(self, count: int = 10) -> Dict[str, Any]:
        """
        通用画像数据获取函数
        
        Args:
            count: 数据数量限制
            
        Returns:
            画像数据字典
        """
        return self.persona_data

    def _get_event_tree_data(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        通用事件树数据获取函数
        
        Args:
            count: 数据数量限制
            
        Returns:
            事件树数据列表
        """
        import random
        if isinstance(self.event_tree, list) and len(self.event_tree) > 0:
            # 随机选择事件
            return random.sample(self.event_tree, min(count, len(self.event_tree)))
        return self.event_tree if isinstance(self.event_tree, list) else []

    def _get_daily_event_data(self, count: int = 10, continuous: bool = False) -> List[Dict[str, Any]]:
        """
        通用每日事件数据获取函数
        
        Args:
            count: 数据数量限制
            continuous: 是否连续选取数据
            
        Returns:
            每日事件数据列表
        """
        import random
        # 直接获取事件列表
        events = self.daily_event if isinstance(self.daily_event, list) else []
        
        if not events:
            return []
        
        if continuous and len(events) > count:
            # 连续选取数据
            max_start_index = len(events) - count
            start_index = random.randint(0, max_start_index)
            return events[start_index:start_index + count]
        else:
            # 随机选取数据
            return random.sample(events, min(count, len(events)))
    
    def _generate_questions_with_template(self, data: Any, template: str, num_questions: int = 5, bracket_type: str = '{', **kwargs) -> List[Dict[str, Any]]:
        """
        通用问题生成函数
        
        Args:
            data: 用于生成问题的数据
            template: 问题生成模板
            num_questions: 生成问题的数量
            bracket_type: 用于提取JSON内容的括号类型，可选值为'['或'{'，默认值为'{'
            **kwargs: 模板所需的其他参数
            
        Returns:
            生成的问题列表，每个问题包含question、answer、score_points和required_events字段
            选择题还会包含options字段和type字段
        """
        # 格式化模板
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            data_str = str(data)
        
        prompt = template.format(
            num_questions=num_questions,
            data_info=data_str,
            name=self.persona_data.get("basic_info", {}).get("name", "该用户"),
            **kwargs
        )
        
        # 调用LLM生成问题
        llm_result = llm_call(prompt)
        print(llm_result)
        
        # 提取JSON内容
        if bracket_type == '[':
            start_idx = llm_result.index('[')
            end_idx = llm_result.rindex(']') + 1
        elif bracket_type == '{':
            start_idx = llm_result.index('{')
            end_idx = llm_result.rindex('}') + 1
        else:
            # 如果括号类型不合法，使用原始结果
            start_idx = 0
            end_idx = len(llm_result)
        
        # 提取括号之间的内容
        json_content = llm_result[start_idx:end_idx]
        
        # 解析JSON
        json_result = json.loads(json_content)
        
        # 统一处理返回格式：如果是包含"questions"字段的对象，则返回questions数组
        if isinstance(json_result, dict) and "questions" in json_result:
            return json_result["questions"]
        return json_result
    

    def generate_single_hop_questions(self, num_questions: int = 5) -> List[Dict[str, Any]]:
        """
        生成单跳问题（基于单一事件或信息片段）
        拆分为画像问题生成与事件问题生成，按2:8比例分配
        
        Args:
            num_questions: 生成问题的总数
            
        Returns:
            单跳问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        
        # 按2:8比例分配问题数量
        persona_questions_count = int(num_questions * 0.2)  # 20% 来自画像
        event_questions_count = num_questions - persona_questions_count  # 80% 来自事件
        
        # 调用子函数生成画像问题
        if persona_questions_count > 0:
            persona_questions = self.generate_persona_questions(persona_questions_count)
            questions.extend(persona_questions)
        
        # 调用子函数生成事件问题
        if event_questions_count > 0:
            event_questions = self.generate_event_questions(event_questions_count, question_type="random")
            questions.extend(event_questions)
        
        # 如果生成的问题数量不足，补充基础问题
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")
        while len(questions) < num_questions:
            questions.append({
                "question": f"关于{name}的信息，你还想知道什么？",
                "answer": "",
                "score_points": [{"description": "问题回答正确性", "score": 10}],
                "required_events": [""]
            })
        
        return questions[:num_questions]
    
    def generate_persona_questions(self, count: int) -> List[Dict[str, Any]]:
        """
        生成基于用户画像的单跳问题
        
        Args:
            count: 需要生成的问题数量
            
        Returns:
            画像相关问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        persona_data = self._get_persona_data()
        return self._generate_questions_with_template(
            data=persona_data,
            template=PERSONA_QUESTION_TEMPLATE,
            num_questions=count,
            persona_info=json.dumps(persona_data, ensure_ascii=False, indent=2),
            question_type="画像信息"
        )
    
    def load_phone_data_from_dir(self, phone_data_dir: str):
        """
        从目录加载手机数据
        
        Args:
            phone_data_dir: 手机数据文件夹路径
        """
        if not os.path.exists(phone_data_dir):
            print(f"手机数据目录不存在: {phone_data_dir}")
            return
        
        self.phone_data_dir = phone_data_dir
        
        # 遍历目录中的所有JSON文件
        for filename in os.listdir(phone_data_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(phone_data_dir, filename)
                data_type = filename[:-5]  # 移除.json扩展名作为数据类型
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data_list = json.load(f)
                    
                    # 为每条记录添加phone_id字段，并维护计数器
                    if isinstance(data_list, list):
                        max_id = 0
                        for i, item in enumerate(data_list):
                            if isinstance(item, dict):
                                # 如果已有phone_id字段，使用它并更新计数器
                                if 'phone_id' in item:
                                    try:
                                        current_id = int(item['phone_id'])
                                        if current_id > max_id:
                                            max_id = current_id
                                    except ValueError:
                                        # 如果phone_id不是数字，重新分配
                                        item['phone_id'] = str(i + 1)
                                        max_id = i + 1
                                else:
                                    # 没有phone_id字段，分配新的id
                                    item['phone_id'] = str(i + 1)
                                    max_id = i + 1
                        
                        # 更新该类型的计数器
                        self.phone_id_counters[data_type] = max_id + 1
                    
                    # 保存更新后的数据
                    self.phonedata[data_type] = data_list
                    print(f"成功加载手机数据: {filename}")
                except Exception as e:
                    print(f"加载手机数据文件失败 {filename}: {e}")
                    
    def save_phone_data_to_dir(self, output_dir: str):
        """
        将手机数据保存到指定目录
        
        Args:
            output_dir: 输出目录路径
        """
        # 确保输出目录存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"创建手机数据输出目录: {output_dir}")
        
        # 遍历所有数据类型并保存为JSON文件
        for data_type, data_list in self.phonedata.items():
            filename = f"{data_type}.json"
            file_path = os.path.join(output_dir, filename)
            
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data_list, f, ensure_ascii=False, indent=2)
                print(f"成功保存手机数据: {filename}")
            except Exception as e:
                print(f"保存手机数据文件失败 {filename}: {e}")
    
    def find_phone_data_by_id(self, data_type: str, id_value: str) -> List[Dict[str, Any]]:
        """
        根据ID查找手机数据
        
        Args:
            data_type: 数据类型（如contact, event_call, event_calendar等）
            id_value: 要查找的ID值
            
        Returns:
            匹配的手机数据列表
        """
        result = []
        
        # 检查数据类型是否存在
        if data_type not in self.phonedata:
            print(f"数据类型不存在: {data_type}")
            return result
        
        # 获取数据
        data = self.phonedata[data_type]
        
        # 如果是列表，遍历查找
        if isinstance(data, list):
            for item in data:
                # 检查是否有ID字段
                if isinstance(item, dict):
                    if 'id' in item and item['id'] == id_value:
                        result.append(item)
                    # 也检查_id字段，因为有些数据可能使用这个命名
                    elif 'event_id' in item and item['event_id'] == id_value:
                        result.append(item)
        
        return result
    
    def find_phone_data_by_date(self, data_type: str, date_value: str) -> List[Dict[str, Any]]:
        """
        根据日期查找手机数据
        
        Args:
            data_type: 数据类型（如event_calendar, event_call, event_fitness_health等）
            date_value: 要查找的日期值（格式如YYYY-MM-DD或YYYY-MM-DD HH:MM:SS）
            
        Returns:
            匹配的手机数据列表
        """
        result = []
        
        # 检查数据类型是否存在
        if data_type not in self.phonedata:
            print(f"数据类型不存在: {data_type}")
            return result
        
        # 获取数据
        data = self.phonedata[data_type]
        
        # 如果是列表，遍历查找
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    # 检查常见的日期字段
                    date_matched = False
                    
                    # 检查各种可能的日期字段名
                    date_fields = ['date', 'start_date', 'end_date', 'datetime','日期']
                    
                    for field in date_fields:
                        if field in item:
                            item_date = str(item[field])
                            # 如果日期完全匹配或部分匹配（如只匹配年月日部分）
                            if item_date == date_value or item_date.startswith(date_value + ' '):
                                date_matched = True
                                break
                    
                    if date_matched:
                        result.append(item)
        
        return result
    
    def get_daily_events_by_date_range(self, start_date: str, days: int = 6) -> List[Dict[str, Any]]:
        """
        根据日期范围获取每日事件数据
        
        Args:
            start_date: 开始日期（格式：YYYY-MM-DD）
            days: 获取的天数，包括开始日期在内共days天
            
        Returns:
            指定日期范围内的每日事件列表
        """
        import datetime
        import json
        
        events = []
        daily_event = self.daily_event if isinstance(self.daily_event, list) else []
        
        try:
            # 转换为datetime对象
            start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            print(f"日期格式错误: {start_date}，应为YYYY-MM-DD")
            return events
        
        # 计算结束日期
        end_dt = start_dt + datetime.timedelta(days=days-1)
        
        for event in daily_event:
            if isinstance(event, dict) and "date" in event:
                event_date = event["date"]
                
                # 处理date字段可能为列表的情况
                if isinstance(event_date, list):
                    # 如果是列表，尝试获取第一个非空元素
                    event_date_str = str(event_date[0]) if event_date else ""
                else:
                    # 如果是字符串，直接使用
                    event_date_str = str(event_date)
                    
                try:
                    # 提取事件日期（忽略时间部分）
                    if " " in event_date_str:
                        event_date_str = event_date_str.split(" ")[0]
                    event_dt = datetime.datetime.strptime(event_date_str, "%Y-%m-%d")
                    
                    # 检查是否在指定范围内
                    if start_dt <= event_dt <= end_dt:
                        events.append(event)
                except (ValueError, IndexError):
                    # 跳过日期格式错误或列表为空的事件
                    continue
        
        return events
    
    def get_phone_operations_by_event_id(self, event_id: str) -> List[Dict[str, Any]]:
        """
        根据事件ID获取相关手机操作
        
        Args:
            event_id: 事件ID
            
        Returns:
            相关手机操作列表
        """
        phone_operations = []
        
        # 检查手机数据是否加载
        if not self.phonedata:
            print("手机数据未加载")
            return phone_operations
        
        # 遍历所有手机数据类型
        for data_type, data_list in self.phonedata.items():
            if isinstance(data_list, list):
                for item in data_list:
                    if isinstance(item, dict):
                        # 检查事件ID是否相关
                        if "event_id" in item and item["event_id"] == event_id:
                            phone_operations.append(item)
                        # 检查是否有其他与事件相关的字段
                        elif "related_event" in item and item["related_event"] == event_id:
                            phone_operations.append(item)
                        # 检查是否在事件时间范围内的操作
                        elif "event_time" in item and "event_date" in item:
                            # 这里可以根据需要添加时间范围匹配逻辑
                            pass
        
        return phone_operations
    
    def judge_event_from_phone_operations(self, event: Dict[str, Any], phone_operations: List[Dict[str, Any]], question: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用LLM判断手机操作数据所反映出的事件信息能否回答给定的问题
        
        Args:
            event: 事件数据
            phone_operations: 手机操作数据
            question: 需要回答的问题（包含完整问题信息的字典）
            
        Returns:
            包含判断结果的字典，格式如下：
            {
                "can_infer": bool,  # 是否能从手机操作中回答问题
                "missing_info": list,  # 缺少的信息列表
                "synthesis_background": str  # 新手机数据合成的背景指导
            }
        """
        import json
        
        # 第一步：问题筛选与优化
        
        # 使用问题筛选与优化模板构建提示
        screening_prompt = QUESTION_SCREENING_OPTIMIZATION_TEMPLATE.format(
            event_info=json.dumps(event, ensure_ascii=False, indent=2),
            question=question
        )
        print(f"问题筛选与优化提示: {screening_prompt}")
        # 调用LLM进行问题筛选与优化
        screening_result = llm_call(screening_prompt)
        print(f"问题筛选与优化结果: {screening_result}")
        
        # 解析问题筛选与优化结果
        try:
            if '{' in screening_result and '}' in screening_result:
                start_idx = screening_result.index('{')
                end_idx = screening_result.rindex('}') + 1
                json_content = screening_result[start_idx:end_idx]
                screening_result_json = json.loads(json_content)
                
                # 检查问题是否有效，处理0/1和"0"/"1"两种情况
                is_valid = screening_result_json.get("is_valid", False)
                # 转换为布尔值：0、"0"、False都视为无效
                if is_valid in [False, "0", 0]:
                    # 问题无效，返回无法回答的结果
                    return {
                        "is_valid": False,
                        "can_infer": False,
                        "missing_info": [],
                        "synthesis_background": "原始问题被筛选掉，因为它是无效的或太简单"
                    }
                
                # 获取优化后的完整问题格式
                optimized_question = screening_result_json.get("question", question)
                answer = screening_result_json.get("answer", "")
                score_points = screening_result_json.get("score_points", [])
                options = screening_result_json.get("options", [])
                required_events = screening_result_json.get("required_events", [])
                
                # 构建完整问题结构
                full_question = screening_result_json.copy()
            else:
                # 解析失败，使用原始问题
                optimized_question = question["question"]
                full_question = {
                    "question": question["question"]
                }
        except Exception as e:
            print(f"解析问题筛选与优化结果失败: {e}")
            # 解析失败，使用原始问题
            optimized_question = question["question"]
            full_question = {
                "question": question["question"]
            }
        
        # 第二步：使用优化后的问题进行手机操作数据判断
        
        # 使用模板构建判断提示
        prompt = EVENT_INFERENCE_JUDGMENT_TEMPLATE.format(
            event_info=json.dumps(event, ensure_ascii=False, indent=2),
            phone_operations=json.dumps(phone_operations, ensure_ascii=False, indent=2),
            question=full_question
        )
        print(f"判断提示: {prompt}")
        # 调用LLM
        llm_result = llm_call(prompt)
        print(f"LLM判断结果: {llm_result}")
        
        # 解析结果
        try:
            if '{' in llm_result and '}' in llm_result:
                start_idx = llm_result.index('{')
                end_idx = llm_result.rindex('}') + 1
                json_content = llm_result[start_idx:end_idx]
                result = json.loads(json_content)
                
                # 构建返回结果，包含完整的问题格式
                return_result = {
                    "is_valid": True,
                    "can_infer": result.get("can_infer", False),
                    "missing_info": result.get("missing_info", []),
                    "synthesis_background": result.get("synthesis_background", ""),
                    "optimized_question": optimized_question
                }
                
                # 将完整问题格式的字段合并到返回结果中
                return_result.update(full_question)
                
                return return_result
            else:
                # 默认返回False
                print("LLM返回结果格式不正确，默认返回False")
                return {
                    "is_valid": True,
                    "can_infer": False,
                    "missing_info": [],
                    "synthesis_background": "",
                    "optimized_question": optimized_question,
                    "answer": answer,
                    "score_points": score_points
                }
        except Exception as e:
            print(f"解析LLM判断结果失败: {e}")
            return {
                "is_valid": True,
                "can_infer": False,
                "missing_info": [],
                "synthesis_background": "",
                "optimized_question": optimized_question,
                "answer": answer,
                "score_points": score_points
            }
    
    def regenerate_phone_operations(self, event: Dict[str, Any], judge_result: Dict[str, Any], question: str) -> List[Dict[str, Any]]:
        """
        根据事件和判断结果重新生成手机操作数据
        
        Args:
            event: 事件数据
            judge_result: 判断结果，包含缺失信息和合成背景
            question: 需要回答的问题
            
        Returns:
            重新生成的手机操作数据列表
        """
        import json
        
        # 获取事件ID
        event_id = event.get("event_id")
        if not event_id:
            print("事件数据中没有event_id字段")
            return []
        from event.template3 import PHONE_OPERATIONS_REGENERATION_TEMPLATE1
        # 使用模板构建重新生成提示
        prompt = PHONE_OPERATIONS_REGENERATION_TEMPLATE1.format(
            event_info=json.dumps(event, ensure_ascii=False, indent=2),
            question=question,
            missing_info=json.dumps(judge_result.get("missing_info", []), ensure_ascii=False, indent=2),
            synthesis_background=judge_result.get("synthesis_background", "")
        )
        print(f"重新生成手机操作提示: {prompt}")
        # 调用LLM生成
        from utils.llm_call import llm_call_reason
        llm_result = llm_call_reason(prompt)
        print(f"LLM重新生成手机操作结果: {llm_result}")
        
        # 提取JSON内容
        try:
            if '[' in llm_result and ']' in llm_result:
                start_idx = llm_result.index('[')
                end_idx = llm_result.rindex(']') + 1
                json_content = llm_result[start_idx:end_idx]
                regenerated_operations = json.loads(json_content)
                
                # 1. 删除原有的与该事件相关的手机操作数据
                print(f"开始删除事件ID为{event_id}的原手机操作数据")
                deleted_count = 0
                
                for data_type, data_list in list(self.phonedata.items()):
                    if isinstance(data_list, list):
                        # 创建新的列表，不包含与该事件相关的操作数据
                        new_data_list = []
                        for item in data_list:
                            if isinstance(item, dict):
                                if ("event_id" in item and item["event_id"] == event_id) or \
                                   ("related_event" in item and item["related_event"] == event_id):
                                    deleted_count += 1
                                else:
                                    new_data_list.append(item)
                        # 更新数据列表
                        self.phonedata[data_type] = new_data_list
                
                print(f"成功删除{deleted_count}条与事件ID为{event_id}相关的手机操作数据")
                
                # 2. 将新生成的手机操作数据添加到self.phonedata中
                print(f"开始添加新生成的手机操作数据")
                added_count = 0
                
                for op in regenerated_operations:
                    if isinstance(op, dict):
                        # 设置事件ID
                        op["event_id"] = event_id
                        
                        # 获取操作类型
                        op_type = op.get("type")
                        if op_type:
                            # 如果操作类型对应的列表不存在，创建一个
                            if op_type not in self.phonedata:
                                self.phonedata[op_type] = []
                            
                            # 分配phone_id
                            if op_type not in self.phone_id_counters:
                                self.phone_id_counters[op_type] = 1
                            op['phone_id'] = str(self.phone_id_counters[op_type])
                            self.phone_id_counters[op_type] += 1
                            
                            # 将新操作添加到对应的数据类型列表中
                            self.phonedata[op_type].append(op)
                            added_count += 1
                
                print(f"成功添加{added_count}条新生成的手机操作数据")
                
                return regenerated_operations
            else:
                print("生成的手机操作格式不正确")
                return []
        except Exception as e:
            print(f"解析重新生成的手机操作失败: {e}")
            return []
    
    def generate_event_questions(self, count: int, start_date: str) -> List[Dict[str, Any]]:
        """
        生成基于事件数据的单跳问题
        
        Args:
            count: 需要生成的问题数量
            start_date: 开始日期（格式：YYYY-MM-DD），将获取该日期及之后5天的事件数据
            
        Returns:
            包含问题数组的字典，每个问题包含evidence字段，结构如下：
            {
                "questions": [
                    {
                        "question": "问题内容",
                        "answer": "问题答案",
                        "score_points": [得分点列表],
                        "required_events": [相关事件列表],
                        "evidence": [对应的手机操作事件列表]
                    },
                    ...
                ]
            }
        """
        # 获取指定日期范围的每日事件数据（包括开始日期在内共6天：开始日期 + 之后5天）
        event_data = self.get_daily_events_by_date_range(start_date, days=6)
        
        if not event_data:
            # 如果没有事件数据，打印错误并返回空数组
            print(f"错误：在{start_date}及之后5天内没有找到任何事件数据")
            return []
        
        # 生成单跳问题
        questions = self._generate_questions_with_template(
            data=event_data,
            template=EVENT_QUESTION_TEMPLATE,
            num_questions=count,
            event_info=json.dumps(event_data, ensure_ascii=False, indent=2),
            question_type="事件信息"
        )
        
        # 处理生成的问题，验证是否能从手机操作中推理出来
        valid_questions = []
        question_phone_operations = []
        
        for question in questions:
            # 获取问题相关的事件ID
            required_events = question.get("required_events", [])
            event_ids = []
            
            # 处理新格式：required_events是包含event_id和event_name的字典列表
            for event_item in required_events:
                if isinstance(event_item, dict) and "event_id" in event_item:
                    event_ids.append(event_item["event_id"])
                elif isinstance(event_item, str):
                    # 兼容旧格式：直接是事件ID字符串
                    event_ids.append(event_item)
            
            for event_id in event_ids:
                if event_id:
                    # 根据事件ID获取相关手机操作
                    phone_operations = self.get_phone_operations_by_event_id(event_id)
                    current_phone_operations = phone_operations
                    
                    # 查找对应的事件数据
                    corresponding_event = None
                    for event in event_data:
                        if event.get("id") == event_id or event.get("event_id") == event_id:
                            corresponding_event = event
                            break
                    
                    if corresponding_event:
                        # 判断事件是否能从手机操作中推理出来
                            judge_result = self.judge_event_from_phone_operations(corresponding_event, phone_operations, question)
                            
                            # 检查问题是否被筛选掉
                            if not judge_result.get("is_valid", True):
                                # 如果问题被筛选掉，跳过后续处理，不考虑该问题
                                print(f"问题 '{question['question']}' 被筛选掉，不进行后续处理")
                                break
                            
                            # 更新问题为优化后的完整版本
                            updated_question = question.copy()
                            
                            # 复制所有来自筛选优化的问题字段
                            if "question" in judge_result:
                                updated_question["question"] = judge_result["question"]
                            if "answer" in judge_result:
                                updated_question["answer"] = judge_result["answer"]
                            if "score_points" in judge_result:
                                updated_question["score_points"] = judge_result["score_points"]
                            if "options" in judge_result:
                                updated_question["options"] = judge_result["options"]
                            if "required_events" in judge_result:
                                updated_question["required_events"] = judge_result["required_events"]
                            
                            # 30%概率直接重新生成手机操作
                            if random.random() < 0:
                                # 确保judge_result包含问题和事件信息，要求完全重新生成手机操作
                                judge_result.update({
                                    "question": updated_question["question"],
                                    "event_info": corresponding_event,
                                    "regenerate_all": True,
                                    "missing_info": "所有信息都缺少，当前没有任何手机事件"  # 使用judge_event_from_phone_operations返回的缺失信息
                                })
                                # 直接重新生成手机操作数据，使用judge_event_from_phone_operations返回的missing_info
                                regenerated_operations = self.regenerate_phone_operations(corresponding_event, judge_result, updated_question["question"])
                                valid_questions.append(updated_question)
                                question_phone_operations.append(regenerated_operations)
                                break
                            elif judge_result["can_infer"]:
                                valid_questions.append(updated_question)
                                question_phone_operations.append(current_phone_operations)
                                break
                            else:
                                # 如果不能推理，重新生成手机操作数据
                                # 确保judge_result包含问题和事件信息，要求完全重新生成手机操作
                                judge_result.update({
                                    "question": updated_question["question"],
                                    "event_info": corresponding_event,
                                    "regenerate_all": True
                                })
                                # 使用judge_event_from_phone_operations返回的missing_info作为缺失信息输入重生成
                                regenerated_operations = self.regenerate_phone_operations(corresponding_event, judge_result, updated_question["question"])
                                # 去除再次判断的逻辑，直接添加到有效问题列表
                                valid_questions.append(updated_question)
                                question_phone_operations.append(regenerated_operations)
                                break
            
            # 如果没有找到对应的事件ID或所有事件都无法推理，也添加到有效问题列表中
            if updated_question not in valid_questions:
                valid_questions.append(updated_question)
                question_phone_operations.append([])
        
        # 确保问题和手机操作数量一致
        result_count = min(count, len(valid_questions), len(question_phone_operations))
        
        # 将手机操作数据的类型和ID整合到每个问题的evidence字段中
        for i in range(result_count):
            # 从手机操作中提取类型和ID
            operation_evidence = []
            for operation in question_phone_operations[i]:
                if isinstance(operation, dict) and 'phone_id' in operation:
                    operation_type = operation.get('type', 'unknown')
                    operation_evidence.append({"type": operation_type, "id": operation['phone_id']})
            valid_questions[i]["evidence"] = operation_evidence
        
        return valid_questions[:result_count]

    def generate_yearly_single_hop_qa(self, year: int, output_path: str = None) -> None:
        """
        生成一整年的单跳问答对，按月份并行生成
        
        Args:
            year: 年份（例如：2025）
            output_path: 输出文件路径（默认保存在self.phone_data_dir的上层目录）
        """
        import concurrent.futures
        from datetime import datetime, timedelta
        import json
        import random
        import os
        
        def generate_monthly_qa(month: int) -> List[Dict[str, Any]]:
            """
            生成单个月份的问答对
            
            Args:
                month: 月份（1-12）
                
            Returns:
                该月份生成的问答列表
            """
            print(f"开始生成{year}-{month:02d}的问答对...")
            
            # 确定月份的第一天和最后一天
            if month == 12:
                first_day = datetime(year, month, 1)
                last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                first_day = datetime(year, month, 1)
                last_day = datetime(year, month + 1, 1) - timedelta(days=1)
            
            # 生成月份内的所有日期
            all_dates = [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]
            
            # 在1号到3号之间随机选择一天作为第一个开始日期
            first_three_days = [d for d in all_dates if d.day <= 3]
            if not first_three_days:
                # 如果没有1-3号的日期（理论上不可能），则使用月份的第一天
                first_date = all_dates[0]
            else:
                first_date = random.choice(first_three_days)
            
            # 之后每过六天选择一个日期作为开始日期
            selected_dates = []
            current_date = first_date
            
            while current_date <= all_dates[-1]:  # 确保不超过月份的最后一天
                selected_dates.append(current_date)
                current_date += timedelta(days=6)
            
            # 确保每个月最多选择4个日期
            selected_dates = selected_dates[:4]
            print(f"{year}-{month:02d}共选择了{len(selected_dates)}个日期")
            
            # 对每个选择的日期生成3个问题
            monthly_qa = []
            for date in selected_dates:
                date_str = date.strftime("%Y-%m-%d")
                try:
                    questions = self.generate_event_questions(count=2, start_date=date_str)
                    monthly_qa.extend(questions)
                    print(f"  {date_str}成功生成{len(questions)}个问题")
                except Exception as e:
                    print(f"  {date_str}生成问题失败: {e}")
            
            # 生成该月份的基于画像的短信问题
            month_str = f"{year}-{month:02d}"
            try:
                # 传递已有问题，避免生成相似主题
                persona_questions = self.generate_persona_based_sms_questions(month_str, num_questions=2, existing_questions=monthly_qa)
                monthly_qa.extend(persona_questions)
                print(f"  基于画像的短信问题生成完成，新增{len(persona_questions)}个问题")
            except Exception as e:
                print(f"  基于画像的短信问题生成失败: {e}")
            
            print(f"{year}-{month:02d}完成，共生成{len(monthly_qa)}个问答对")
            return monthly_qa
        
        # 使用线程池并行生成每个月的问答
        all_qa = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            # 提交12个月份的任务
            future_to_month = {executor.submit(generate_monthly_qa, month): month for month in range(1, 13)}
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_month):
                month = future_to_month[future]
                try:
                    monthly_qa = future.result()
                    
                    # 为当前月的问答对添加ask_time字段
                    import random
                    for qa in monthly_qa:
                        # 生成随机月份，大于等于当前月份
                        random_month = random.randint(month, 12)
                        # 格式化为"2025-xx"形式
                        ask_time = f"2025-{str(random_month).zfill(2)}"
                        qa["ask_time"] = ask_time
                    
                    all_qa.extend(monthly_qa)
                except Exception as e:
                    print(f"{year}-{month:02d}生成失败: {e}")
        
        # 整合所有问答并写入文件
        print(f"所有月份生成完成，共生成{len(all_qa)}个问答对")
        
        # 为每个问答对添加question_type字段
        output_data = []
        for qa in all_qa:
            qa["question_type"] = "single_hop"
            output_data.append(qa)
        
        # 如果没有指定output_path，使用self.phone_data_dir的上层目录
        if output_path is None:
            # 获取self.phone_data_dir的上层目录
            parent_dir = os.path.dirname(self.phone_data_dir)
            output_path = os.path.join(parent_dir, "single_hop_qa.json")
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"问答对已成功写入文件: {output_path}")
        
        # # 保存修改后的手机数据
        # if hasattr(self, 'phone_data_dir') and self.phone_data_dir:
        #     # 创建新的输出目录，在原目录基础上添加_yearly_update后缀
        #     import os
        #     base_dir = os.path.dirname(self.phone_data_dir)
        #     phone_data_dir_name = os.path.basename(self.phone_data_dir)
        #     new_phone_data_dir = os.path.join(base_dir, f"{phone_data_dir_name}_yearly_update_{year}")
        #
        #     print(f"\n开始保存修改后的手机数据到: {new_phone_data_dir}")
        #     self.save_phone_data_to_dir(new_phone_data_dir)
        #     print(f"手机数据已成功保存到新目录: {new_phone_data_dir}")