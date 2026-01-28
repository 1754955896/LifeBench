import json
import os
import random
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

from event.mind import llm_call
from event.template3 import (
    PATTERN_RECOGNITION_TEMPLATE,
    CAUSAL_REASONING_TEMPLATE,
    UPDATING_REASONING_TEMPLATE
)

class QAReasoningGenerator:
    """
    推理问题生成器类，根据用户的事件数据和画像信息生成推理问题
    支持时序推理、模式识别与习惯分析、因果与隐藏推理等多种推理问题类型
    """
    
    def __init__(self, persona_data: Dict[str, Any] = None, event_tree: Dict[str, Any] = None, 
                 daily_event: Dict[str, Any] = None, draft_event: Dict[str, Any] = None, 
                 special_event: Dict[str, Any] = None, phone_data_dir: str = None):
        """
        初始化推理问题生成器
        
        Args:
            persona_data: 用户画像数据
            event_tree: 事件树数据
            daily_event: 每日事件数据
            draft_event: 草稿事件数据
            special_event: 特殊事件数据
            phone_data_dir: 手机数据目录路径
        """
        self.persona_data = persona_data or {}  # 用户画像数据
        self.event_tree = event_tree or {}      # 事件树数据
        self.daily_event = daily_event or {}    # 每日事件数据
        self.draft_event = draft_event or {}    # 草稿事件数据
        self.special_event = special_event or {} # 特殊事件数据
        self.phone_data_dir = phone_data_dir    # 手机数据文件夹路径
        self.phonedata = {}                     # 手机数据存储
        self.phone_id_counters = {}             # 手机数据类型的id计数器
        
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
        event_tree_path = os.path.join(data_path, "process/event_decompose_dfs.json")
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
                # 从special_event中提取unique_events
                self.unique_events = self.special_event.get('unique_events', [])
        
        # 加载手机操作数据
        phone_data_path = os.path.join(data_path, "phone_data")
        if os.path.exists(phone_data_path):
            self.load_phone_data_from_dir(phone_data_path)
    
    def generate_reasoning_questions_by_themes(self, themes: List[Dict[str, Any]], num_questions_per_theme: int = 2) -> List[Dict[str, Any]]:
        """
        根据输入的theme数组生成推理问题，输出只保留问题列表，不包含主题信息
        
        Args:
            themes: theme数组，每个theme包含theme_summary和event_ids字段
            num_questions_per_theme: 每个主题生成的问题数量
            
        Returns:
            List[Dict[str, Any]]: 包含所有生成的推理问题的列表，每个问题包含question、answer、score_points、required_events和question_type字段
        """
        import concurrent.futures
        import json
        import os
        
        # 创建一个辅助函数来生成单个主题的问题
        def generate_questions_for_theme(theme):
            theme_summary = theme["theme_summary"]
            event_ids = theme["event_ids"]
            
            try:
                questions = self.generate_reasoning_questions_from_event_tree_id(
                    event_ids=event_ids,
                    num_questions=num_questions_per_theme
                )
                
                if questions:
                    # 为每个问题添加question_type字段
                    for question in questions:
                        if not question.get("question_type"):
                            question["question_type"] = "reasoning"
                    return questions
                else:
                    return []
                    
            except Exception as e:
                print(f"为主题'{theme_summary}'生成问题时出错: {str(e)}")
                return []
        
        # 使用线程池并行处理所有主题
        all_questions = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=24) as executor:
            # 提交所有主题的处理任务
            future_to_theme = {executor.submit(generate_questions_for_theme, theme): theme for theme in themes}
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_theme):
                questions = future.result()
                all_questions.extend(questions)
        
        # 将结果保存到self.phone_data_dir的上一层目录的reasoning_qa.json文件
        if self.phone_data_dir:
            # 获取self.phone_data_dir的上一层目录
            parent_dir = os.path.dirname(self.phone_data_dir)
            output_path = os.path.join(parent_dir, "reasoning_qa.json")
            
            output_data = all_questions
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            print(f"推理问题已成功写入文件: {output_path}")
        else:
            print("self.phone_data_dir未设置，无法保存文件")
        
        return all_questions
        
    def generate_reasoning_questions_from_event_tree_id_groups(self, event_id_groups: List[List[int]], num_questions_per_group: int = 2) -> List[Dict[str, Any]]:
        """
        根据输入的事件ID组数组并行生成推理问题
        
        Args:
            event_id_groups: 事件ID组数组，每个组包含一个或多个事件ID
            num_questions_per_group: 每个事件ID组生成的问题数量
            
        Returns:
            List[Dict[str, Any]]: 包含所有生成的推理问题的列表
        """
        import concurrent.futures
        import json
        import os
        print("正在生成推理问题...", event_id_groups)
        # 创建一个辅助函数来处理单个事件ID组
        def generate_questions_for_group(event_ids):
            try:
                questions = self.generate_reasoning_questions_from_event_tree_id2(
                    event_ids=event_ids,
                    num_questions=num_questions_per_group
                )
                
                if questions:
                    # 为每个问题添加question_type字段
                    for question in questions:
                        question["question_type"] = "updating"
                    return questions
                else:
                    return []
                    
            except Exception as e:
                print(f"为事件ID组{event_ids}生成问题时出错: {str(e)}")
                return []
        
        # 使用线程池并行处理所有事件ID组
        all_questions = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=24) as executor:
            # 提交所有事件ID组的处理任务
            future_to_group = {executor.submit(generate_questions_for_group, event_ids): event_ids for event_ids in event_id_groups}
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_group):
                event_ids = future_to_group[future]
                try:
                    questions = future.result()
                    print(f"完成事件ID组{event_ids}的问题生成，共生成{len(questions)}个问题")
                    all_questions.extend(questions)
                except Exception as exc:
                    print(f"事件ID组{event_ids}的问题生成失败: {exc}")
        
        # 将结果保存到self.phone_data_dir的上一层目录的reasoning_qa.json文件
        if self.phone_data_dir:
            # 获取self.phone_data_dir的上一层目录
            parent_dir = os.path.dirname(self.phone_data_dir)
            output_path = os.path.join(parent_dir, "updating_qa.json")
            
            output_data = all_questions
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            print(f"推理问题已成功写入文件: {output_path}")
        else:
            print("self.phone_data_dir未设置，无法保存文件")
        
        return all_questions
    
    def _get_draft_event_data(self,month: str) -> List[Dict[str, Any]]:
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
                # 移除state字段（如果存在）
                filtered_month_data = []
                for day_data in month_data:
                    filtered_day_data = day_data
                    #filtered_day_data = {k: v for k, v in day_data.items() if k != 'state'}
                    filtered_month_data.append(filtered_day_data)
                print(f"找到{month}月份的draft event数据，共{len(filtered_month_data)}条")
                return filtered_month_data
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
            event_info=data_str,
            name=self.persona_data.get("basic_info", {}).get("name", "该用户"),
            **kwargs
        )
        print(prompt)
        from utils.llm_call import llm_call_reason
        # 调用LLM生成问题
        llm_result = llm_call_reason(prompt)
        print(llm_result)
        
        # 提取JSON内容
        try:
            if bracket_type == '[':
                start_idx = llm_result.index('[')
                end_idx = llm_result.rindex(']') + 1
            else:
                start_idx = llm_result.index('{')
                end_idx = llm_result.rindex('}') + 1
            
            json_str = llm_result[start_idx:end_idx]
            questions = json.loads(json_str)
            
            # 如果返回的是包含questions字段的字典，则提取questions字段
            if isinstance(questions, dict) and 'questions' in questions:
                questions = questions['questions']
            
            return questions
        except Exception as e:
            print(f"提取JSON内容失败: {e}")
            return []
    
    def generate_reasoning_questions(self, num_questions: int = 10) -> List[Dict[str, Any]]:
        """
        生成推理问题（需要推理能力才能回答的问题）
        拆分为更新推理问题、模式识别与习惯分析问题、因果推理问题，按3:3:4比例分配
        
        Args:
            num_questions: 生成问题的总数
            
        Returns:
            推理问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        
        # 按3:3:4的比例分配问题数量
        updating_questions_count = int(num_questions * 0.3)  # 更新推理问题
        pattern_questions_count = int(num_questions * 0.3)   # 模式识别与习惯分析问题
        causal_questions_count = num_questions - updating_questions_count - pattern_questions_count  # 因果与隐藏推理问题
        
        # 生成更新推理问题
        if updating_questions_count > 0:
            updating_questions = self._generate_updating_reasoning_questions(updating_questions_count)
            questions.extend(updating_questions)
        
        # 生成模式识别与习惯分析问题
        if pattern_questions_count > 0:
            pattern_questions = self._generate_pattern_recognition_and_habit_analysis_questions(pattern_questions_count)
            questions.extend(pattern_questions)
        
        # 生成因果与隐藏推理问题
        if causal_questions_count > 0:
            causal_questions = self._generate_causal_and_hidden_reasoning_questions(causal_questions_count)
            questions.extend(causal_questions)
        
        # 如果生成的问题数量不足，补充基础推理问题
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")
        while len(questions) < num_questions:
            questions.append({
                "question": f"{name}的行为背后可能有什么深层原因？",
                "answer": "",
                "score_points": [{"description": "问题回答正确性", "score": 10}],
                "required_events": [""]
            })
        
        return questions[:num_questions]
    
    def _generate_updating_reasoning_questions(self, num_questions: int) -> List[Dict[str, Any]]:
        """
        生成更新推理问题对（生成两个相关问题，分别代表不同时间询问后得到不同答案的问题）
        
        Args:
            num_questions: 生成问题对的数量
            
        Returns:
            更新推理问题列表，包含问题对中的两个问题
        """
        questions = []
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")
        
        # 获取draft事件数据
        draft_data = self._get_draft_event_data('2025-04')
        
        if draft_data:
            # 构建事件上下文
            event_context = {
                'name': name,
                'selected_events': draft_data
            }
            event_info_str = json.dumps(event_context, ensure_ascii=False, indent=2)
            
            # 格式化模板
            prompt = UPDATING_REASONING_TEMPLATE.format(
                num_questions=num_questions,
                event_info=event_info_str,
                name=name,
                question_prefix="更新推理",
                question_type="推理问题"
            )
            print(prompt)
            
            # 直接调用LLM
            from utils.llm_call import llm_call_reason
            llm_result = llm_call_reason(prompt)
            print(llm_result)
            
            # 解析JSON结果
            try:
                start_idx = llm_result.index('{')
                end_idx = llm_result.rindex('}') + 1
                json_str = llm_result[start_idx:end_idx]
                result = json.loads(json_str)
                
                # 处理返回的问题对格式
                if isinstance(result, dict):
                    if 'question_pairs' in result:
                        for pair in result['question_pairs']:
                            # 添加第一个问题
                            questions.append({
                                "question": pair.get("question1", ""),
                                "ask_time": pair.get("ask_time1", ""),
                                "answer": pair.get("answer1", ""),
                                "score_points": pair.get("score_points1", [{"description": "问题回答正确性", "score": 10}]),
                                "required_events": pair.get("required_events1", [""])
                            })
                            # 添加第二个问题
                            questions.append({
                                "question": pair.get("question2", ""),
                                "ask_time": pair.get("ask_time2", ""),
                                "answer": pair.get("answer2", ""),
                                "score_points": pair.get("score_points2", [{"description": "问题回答正确性", "score": 10}]),
                                "required_events": pair.get("required_events2", [""])
                            })
                    elif 'questions' in result:
                        # 兼容旧格式
                        questions = result['questions']
                elif isinstance(result, list):
                    # 兼容旧格式
                    questions = result
            except Exception as e:
                print(f"提取JSON内容失败: {e}")
        
        # 如果生成的问题不足，添加基础更新推理问题
        if not questions or len(questions) < num_questions * 2:
            fallback_question1 = {
                "question": f"2025年8月初，{name}有多少个未读消息？",
                "answer": "15个",
                "score_points": [{"description": "问题回答正确性", "score": 10}],
                "required_events": [""]
            }
            fallback_question2 = {
                "question": f"2025年8月底，{name}有多少个未读消息？",
                "answer": "8个",
                "score_points": [{"description": "问题回答正确性", "score": 10}],
                "required_events": [""]
            }
            
            while len(questions) < num_questions * 2:
                questions.append(fallback_question1)
                questions.append(fallback_question2)
        
        return questions[:num_questions * 2]
    
    def _generate_pattern_recognition_and_habit_analysis_questions(self, num_questions: int) -> List[Dict[str, Any]]:
        """
        生成模式识别与习惯分析问题（需要结合多个事件来识别行为模式、习惯、偏好或规律的问题）
        
        Args:
            num_questions: 生成问题的数量
            
        Returns:
            模式识别与习惯分析问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")
        
        # 获取draft事件数据
        draft_data = self._get_draft_event_data('2025-01')
        print(draft_data)
        if draft_data:
            # 构建事件上下文
            event_context = {
                'name': name,
                'selected_events': draft_data
            }
            event_info_str = json.dumps(event_context, ensure_ascii=False, indent=2)
            
            # 处理用户画像的relation字段，只保留"name"、"relation"、"birth_date"和"occupation"
            processed_persona_data = self.persona_data.copy()
            if "relation" in processed_persona_data:
                processed_relations = []
                for relation_group in processed_persona_data["relation"]:
                    processed_group = []
                    for relation in relation_group:
                        processed_relation = {
                            "name": relation.get("name", ""),
                            "relation": relation.get("relation", ""),
                            "birth_date": relation.get("birth_date", ""),
                            "occupation": relation.get("occupation", "")
                        }
                        processed_group.append(processed_relation)
                    processed_relations.append(processed_group)
                processed_persona_data["relation"] = processed_relations
            persona_info_str = json.dumps(processed_persona_data, ensure_ascii=False, indent=2)
            
            # 格式化模板
            prompt = PATTERN_RECOGNITION_TEMPLATE.format(
                num_questions=num_questions,
                event_info=event_info_str,
                persona_info=persona_info_str,
                name=name
            )
            
            # 调用LLM生成问题
            from event.mind import llm_call_reason
            llm_result = llm_call_reason(prompt)
            print(llm_result)
            
            # 提取JSON内容
            try:
                if '{' in llm_result and '}' in llm_result:
                    start_idx = llm_result.index('{')
                    end_idx = llm_result.rindex('}') + 1
                    json_content = llm_result[start_idx:end_idx]
                    json_result = json.loads(json_content)
                    
                    # 统一处理返回格式：如果是包含"questions"字段的对象，则返回questions数组
                    if isinstance(json_result, dict) and "questions" in json_result:
                        questions = json_result["questions"]
                    elif isinstance(json_result, list):
                        questions = json_result
            except Exception as e:
                print(f"解析LLM结果失败: {e}")
        print(questions)
        # 如果生成的问题不足，添加基础模式识别问题
        if not questions or len(questions) < num_questions:
            fallback_question = {
                "question": f"{name}有什么日常行为模式？",
                "answer": "",
                "score_points": [{"description": "问题回答正确性", "score": 10}],
                "required_events": [""]
            }
            
            while len(questions) < num_questions:
                questions.append(fallback_question)
        
        return questions[:num_questions]
    
    def _generate_causal_and_hidden_reasoning_questions(self, num_questions: int) -> List[Dict[str, Any]]:
        """
        生成因果与隐藏推理问题（需要分析事件之间的因果关系、隐藏动机或深层原因的问题）
        
        Args:
            num_questions: 生成问题的数量
            
        Returns:
            因果与隐藏推理问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")
        
        # 获取draft事件数据
        draft_data = self._get_draft_event_data(count=max(num_questions * 3, 20))
        
        if draft_data:
            # 构建事件上下文
            event_context = {
                'name': name,
                'selected_events': draft_data
            }
            event_info_str = json.dumps(event_context, ensure_ascii=False, indent=2)
            
            # 使用通用问题生成函数
            questions = self._generate_questions_with_template(
                data=draft_data,
                template=CAUSAL_REASONING_TEMPLATE,
                num_questions=num_questions,
                question_prefix="因果与隐藏推理",
                event_info=event_info_str,
                question_type="推理问题"
            )
        
        # 如果生成的问题不足，添加基础因果推理问题
        if not questions or len(questions) < num_questions:
            fallback_question = {
                "question": f"{name}做出重要决定的背后因素是什么？",
                "answer": "",
                "score_points": [{"description": "问题回答正确性", "score": 10}],
                "required_events": [""]
            }
            
            while len(questions) < num_questions:
                questions.append(fallback_question)
        
        return questions[:num_questions]
    
    def _get_event_tree_data(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        通用事件树数据获取函数：
        1. 先筛选跨度15天及以上的顶层事件
        2. 随机选取一个顶层事件
        3. 获取该顶层事件下的所有最底层事件
        4. 返回这些最底层事件的数组
        
        Args:
            count: 数据数量限制（此处未使用，返回所有符合条件的最底层事件）
            
        Returns:
            事件树中指定顶层事件下的所有最底层事件列表
        """
        if not isinstance(self.event_tree, list):
            return []
        
        # 筛选跨度15天及以上的顶层事件
        top_events_15d = []
        for event in self.event_tree:
            try:
                if 'date' in event and isinstance(event['date'], list) and event['date']:
                    # 获取第一个日期范围
                    date_range = event['date'][0]
                    
                    # 按"至"分割日期
                    if "至" in date_range:
                        start_date_str, end_date_str = date_range.split("至")
                    else:
                        # 没有"至"则代表为一天
                        start_date_str = date_range
                        end_date_str = date_range
                    
                    # 将字符串转换为日期对象
                    start_date = datetime.strptime(start_date_str.strip(), '%Y-%m-%d')
                    end_date = datetime.strptime(end_date_str.strip(), '%Y-%m-%d')
                    
                    # 计算时间差（天数）
                    days_diff = (end_date - start_date).days
                    
                    # 只保留跨度15天及以上的顶层事件
                    if days_diff >= 15:
                        top_events_15d.append(event)
            except ValueError:
                # 忽略时间格式错误的事件
                continue
        
        # 如果没有符合条件的顶层事件，返回空列表
        if not top_events_15d:
            return []
        
        # 随机选取一个顶层事件
        selected_top_event = random.choice(top_events_15d)
        
        # 递归函数：获取指定事件下的所有最底层事件
        def get_bottom_events(event):
            bottom_events = []
            # 检查是否为最底层事件
            if 'subevent' in event and isinstance(event['subevent'], list) and event['subevent']:
                # 不是最底层事件，递归获取子事件
                for subevent in event['subevent']:
                    bottom_events.extend(get_bottom_events(subevent))
            else:
                # 是最底层事件，添加到结果列表
                bottom_events.append(event)
            return bottom_events
        
        # 获取选中顶层事件下的所有最底层事件
        bottom_events = get_bottom_events(selected_top_event)
        
        return bottom_events
    
    def get_event_tree_data_by_id(self, event_ids: List[int]) -> List[Dict[str, Any]]:
        """
        根据event_id数组获取事件树数据（仅查找最上层事件）
        
        Args:
            event_ids: 要获取的事件ID数组（整数类型）
            
        Returns:
            匹配的最上层事件树数据列表
        """
        if not isinstance(self.event_tree, list) or not event_ids:
            return []
        
        # 只查找最上层事件，不递归查找子事件
        matched_events = []
        for event in self.event_tree:
            if 'event_id' in event:
                # 兼容event_id为整数或字符串的情况
                event_event_id = event['event_id']
                for target_id in event_ids:
                    # 比较时考虑两种类型的匹配
                    if event_event_id == target_id or str(event_event_id) == str(target_id):
                        matched_events.append(event)
                        break  # 避免重复匹配同一事件
        
        return matched_events

    
    def generate_reasoning_questions_from_event_tree(self, num_questions: int) -> List[Dict[str, Any]]:
        """
        基于事件树数据生成推理问题
        
        Args:
            num_questions: 生成问题的数量
            
        Returns:
            基于事件树数据的推理问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")
        
        # 获取事件树数据（将输入数据获取从draft改为事件树数据）
        event_tree_data = self._get_event_tree_data(count=1)
        print(event_tree_data)
        questions_opt = []
        if event_tree_data:
            # 构建事件上下文
            event_context = {
                'name': name,
                'selected_events': event_tree_data
            }
            
            # 使用通用问题生成函数
            questions = self._generate_questions_with_template(
                data=event_tree_data,
                template=CAUSAL_REASONING_TEMPLATE,  # 可以根据需要替换为其他推理模板
                num_questions=num_questions,
                event_info=json.dumps(event_context, ensure_ascii=False, indent=2),
                question_type="因果与隐藏推理"
            )
            
            print("开始溯源")
            
            # # 对生成的每个问题进行事件溯源
            # for question in questions:
            #     # 获取问题相关信息
            #     original_question = question.get("question", "")
            #     score_points = question.get("score_points", [])
            #     required_events = question.get("required_events", [])
            #     dates = question.get("required_event_dates", [])
            #
            #     # 添加一个空的event_tracing_result字段
            #     question['event_tracing_result'] = ""
            #     questions_opt.append(question)
        
        # 返回所有生成的问题
        return questions[:num_questions]
    
    def _event_tracing(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """
        事件溯源功能：基于问题对象，分析daily_event是否包含所需事件，
        判断是否需要修改问题，并根据信息完整性优化问题或重新设计问题。
        
        Args:
            question: 问题对象，包含question、score_points、required_events、required_event_dates等字段
        
        Returns:
            包含优化后问题、daily_event_id列表、新增事件等信息的字典，或包含questions数组的字典
        """
        # 从问题对象中提取所需信息
        dates = question.get("required_events_date", [])

        
        # 基于所有日期获取对应日期的daily_event，包括当天、前一天和后一天
        events_by_date = {}
        all_events = []
        event_id_map = {}
        added_event_ids = set()  # 用于跟踪已添加的事件ID，避免重复
        
        # 首先计算所有需要查询的目标日期（包括每个日期的前一天和后一天）
        all_target_dates = set()
        for date in dates:
            try:
                current_date = datetime.strptime(date, "%Y-%m-%d")
                prev_day = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
                next_day = (current_date + timedelta(days=1)).strftime("%Y-%m-%d")
                all_target_dates.update([prev_day, date, next_day])
            except ValueError:
                # 如果日期格式不正确，只使用原始日期
                all_target_dates.add(date)
        
        # 构建日期到事件的映射
        date_to_events = {}
        for event in self.daily_event:
            if "date" in event and event["date"]:
                # 从时间段字符串中提取日期部分
                time_range = event["date"][0] if isinstance(event["date"], list) else event["date"]
                date_part = time_range.split(" ")[0]
                
                if date_part in all_target_dates:
                    # 将事件添加到对应的日期分组
                    if date_part not in date_to_events:
                        date_to_events[date_part] = []
                    date_to_events[date_part].append(event)
        
        # 填充events_by_date字典，每个日期包含当天、前一天和后一天的事件
        for date in dates:
            events_on_date = []
            processed_event_ids = set()  # 用于跟踪当前日期组中已添加的事件ID
            
            try:
                current_date = datetime.strptime(date, "%Y-%m-%d")
                prev_day = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
                next_day = (current_date + timedelta(days=1)).strftime("%Y-%m-%d")
                target_dates_for_current = [prev_day, date, next_day]
            except ValueError:
                # 如果日期格式不正确，只使用原始日期
                target_dates_for_current = [date]
            
            # 收集当前日期组的所有事件
            for target_date in target_dates_for_current:
                if target_date in date_to_events:
                    for event in date_to_events[target_date]:
                        event_id = event.get("id")
                        # 确保事件ID存在且未在当前日期组中添加过
                        if event_id is not None and event_id not in processed_event_ids:
                            events_on_date.append(event)
                            processed_event_ids.add(event_id)
                            # 同时更新全局的事件ID映射和all_events列表
                            if event_id not in added_event_ids:
                                all_events.append(event)
                                added_event_ids.add(event_id)
                                event_id_map[event_id] = event
                        elif event_id is None:
                            # 对于没有ID的事件，直接添加（但可能会有重复）
                            events_on_date.append(event)
                            all_events.append(event)
            
            events_by_date[date] = events_on_date
        
        print(f"找到相关日期的daily event数据，共{len(all_events)}条")
        
        # 调用LLM分析事件和问题
        try:
            # 构建分析请求，使用template3.py中的新模板
            from .template3 import EVENT_TRACING_ENHANCED_NO_ADD_TEMPLATE
            
            # 处理persona数据，只保留relation中的name和relation信息
            processed_persona = self.persona_data.copy()
            if "relation" in processed_persona and isinstance(processed_persona["relation"], list):
                simplified_relations = []
                for relation in processed_persona["relation"]:
                    if isinstance(relation, list):
                        # 处理嵌套列表格式
                        group_relations = []
                        for item in relation:
                            if isinstance(item, dict):
                                simplified_item = {
                                    "name": item.get("name", ""),
                                    "relation": item.get("relation", "")
                                }
                                group_relations.append(simplified_item)
                        simplified_relations.append(group_relations)
                    elif isinstance(relation, dict):
                        # 处理字典格式
                        simplified_item = {
                            "name": relation.get("name", ""),
                            "relation": relation.get("relation", "")
                        }
                        simplified_relations.append(simplified_item)
                processed_persona["relation"] = simplified_relations
            
            prompt = EVENT_TRACING_ENHANCED_NO_ADD_TEMPLATE.format(
                question=json.dumps(question, ensure_ascii=False, indent=2),
                dates=', '.join(dates),
                events_by_date=json.dumps(events_by_date, ensure_ascii=False, indent=2),
                persona=json.dumps(processed_persona, ensure_ascii=False, indent=2)
            )
            from utils.llm_call import llm_call_reason
            # 直接调用LLM分析
            analysis_result = llm_call_reason(prompt, record=0)
            
            print("LLM分析结果：", analysis_result)
            
            # 尝试解析分析结果，直接提取JSON内容（因为模板不再输出<output>标签）
            try:
                # 直接提取JSON部分
                if "{" in analysis_result and "}" in analysis_result:
                    start_idx = analysis_result.index("{")
                    end_idx = analysis_result.rindex("}") + 1
                    json_result = json.loads(analysis_result[start_idx:end_idx])
                    return json_result
            except Exception as json_e:
                print(f"事件溯源增强版结果解析失败: {str(json_e)}")
                # 所有解析尝试失败，返回默认字典
                return {"instruction": 1}
        except Exception as e:
            print(f"事件溯源分析失败: {str(e)}")
            # 分析失败时，返回原问题和可用的事件ID
            available_event_ids = list(event_id_map.keys())
            return {
                "optimized_question": question,
                "daily_event_ids": available_event_ids,
                "new_events": [],
                "status": "error",
                "message": f"Analysis failed: {str(e)}"
            }

    def _event_tracing2(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """
        事件溯源功能：基于问题对象，分析daily_event是否包含所需事件，
        判断是否需要修改问题，并根据信息完整性优化问题或重新设计问题。

        Args:
            question: 问题对象，包含question、score_points、required_events、required_event_dates等字段

        Returns:
            包含优化后问题、daily_event_id列表、新增事件等信息的字典，或包含questions数组的字典
        """
        # 从问题对象中提取所需信息
        dates = question.get("required_events_date", [])

        # 基于所有日期获取对应日期的daily_event，包括当天、前一天和后一天
        events_by_date = {}
        all_events = []
        event_id_map = {}
        added_event_ids = set()  # 用于跟踪已添加的事件ID，避免重复

        # 首先计算所有需要查询的目标日期（包括每个日期的前一天和后一天）
        all_target_dates = set()
        for date in dates:
            try:
                current_date = datetime.strptime(date, "%Y-%m-%d")
                prev_day = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
                next_day = (current_date + timedelta(days=1)).strftime("%Y-%m-%d")
                all_target_dates.update([prev_day, date, next_day])
            except ValueError:
                # 如果日期格式不正确，只使用原始日期
                all_target_dates.add(date)

        # 构建日期到事件的映射
        date_to_events = {}
        for event in self.daily_event:
            if "date" in event and event["date"]:
                # 从时间段字符串中提取日期部分
                time_range = event["date"][0] if isinstance(event["date"], list) else event["date"]
                date_part = time_range.split(" ")[0]

                if date_part in all_target_dates:
                    # 将事件添加到对应的日期分组
                    if date_part not in date_to_events:
                        date_to_events[date_part] = []
                    date_to_events[date_part].append(event)

        # 填充events_by_date字典，每个日期包含当天、前一天和后一天的事件
        for date in dates:
            events_on_date = []
            processed_event_ids = set()  # 用于跟踪当前日期组中已添加的事件ID

            try:
                current_date = datetime.strptime(date, "%Y-%m-%d")
                prev_day = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
                next_day = (current_date + timedelta(days=1)).strftime("%Y-%m-%d")
                target_dates_for_current = [prev_day, date, next_day]
            except ValueError:
                # 如果日期格式不正确，只使用原始日期
                target_dates_for_current = [date]

            # 收集当前日期组的所有事件
            for target_date in target_dates_for_current:
                if target_date in date_to_events:
                    for event in date_to_events[target_date]:
                        event_id = event.get("id")
                        # 确保事件ID存在且未在当前日期组中添加过
                        if event_id is not None and event_id not in processed_event_ids:
                            events_on_date.append(event)
                            processed_event_ids.add(event_id)
                            # 同时更新全局的事件ID映射和all_events列表
                            if event_id not in added_event_ids:
                                all_events.append(event)
                                added_event_ids.add(event_id)
                                event_id_map[event_id] = event
                        elif event_id is None:
                            # 对于没有ID的事件，直接添加（但可能会有重复）
                            events_on_date.append(event)
                            all_events.append(event)

            events_by_date[date] = events_on_date

        print(f"找到相关日期的daily event数据，共{len(all_events)}条")

        # 调用LLM分析事件和问题
        try:
            # 构建分析请求，使用template3.py中的新模板
            from .template3 import EVENT_TRACING_ENHANCED_NO_ADD_TEMPLATE

            # 处理persona数据，只保留relation中的name和relation信息
            processed_persona = self.persona_data.copy()
            if "relation" in processed_persona and isinstance(processed_persona["relation"], list):
                simplified_relations = []
                for relation in processed_persona["relation"]:
                    if isinstance(relation, list):
                        # 处理嵌套列表格式
                        group_relations = []
                        for item in relation:
                            if isinstance(item, dict):
                                simplified_item = {
                                    "name": item.get("name", ""),
                                    "relation": item.get("relation", "")
                                }
                                group_relations.append(simplified_item)
                        simplified_relations.append(group_relations)
                    elif isinstance(relation, dict):
                        # 处理字典格式
                        simplified_item = {
                            "name": relation.get("name", ""),
                            "relation": relation.get("relation", "")
                        }
                        simplified_relations.append(simplified_item)
                processed_persona["relation"] = simplified_relations
            from event.template3 import EVENT_TRACING_ENHANCED_NO_ADD_TEMPLATE2
            prompt = EVENT_TRACING_ENHANCED_NO_ADD_TEMPLATE2.format(
                question=json.dumps(question, ensure_ascii=False, indent=2),
                dates=', '.join(dates),
                events_by_date=json.dumps(events_by_date, ensure_ascii=False, indent=2),
                persona=json.dumps(processed_persona, ensure_ascii=False, indent=2)
            )
            from utils.llm_call import llm_call_reason
            # 直接调用LLM分析
            analysis_result = llm_call_reason(prompt, record=0)

            print("LLM分析结果：", analysis_result)

            # 尝试解析分析结果，直接提取JSON内容（因为模板不再输出<output>标签）
            try:
                # 直接提取JSON部分
                if "{" in analysis_result and "}" in analysis_result:
                    start_idx = analysis_result.index("{")
                    end_idx = analysis_result.rindex("}") + 1
                    json_result = json.loads(analysis_result[start_idx:end_idx])
                    return json_result
            except Exception as json_e:
                print(f"事件溯源增强版结果解析失败: {str(json_e)}")
                # 所有解析尝试失败，返回默认字典
                return {"instruction": 1}
        except Exception as e:
            print(f"事件溯源分析失败: {str(e)}")
            # 分析失败时，返回原问题和可用的事件ID
            available_event_ids = list(event_id_map.keys())
            return {
                "optimized_question": question,
                "daily_event_ids": available_event_ids,
                "new_events": [],
                "status": "error",
                "message": f"Analysis failed: {str(e)}"
            }

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
                    
    def get_phone_operations_by_event_id(self, event_id: str) -> List[Dict[str, Any]]:
        """
        根据事件ID获取相关的手机操作数据
        
        Args:
            event_id: 事件ID
            
        Returns:
            与该事件相关的手机操作数据列表
        """
        phone_operations = []
        
        if not self.phonedata:
            return phone_operations
            
        for data_type, data_list in self.phonedata.items():
            if isinstance(data_list, list):
                for item in data_list:
                    if isinstance(item, dict):
                        # 检查事件ID是否匹配
                        if item.get("event_id") == event_id or \
                           item.get("id") == event_id or \
                           item.get("related_event") == event_id:
                            phone_operations.append(item)
        
        return phone_operations
    
    def get_phone_data_statistics(self, by_event_id: bool = False) -> Dict[str, Any]:
        """
        统计手机数据的数目
        
        Args:
            by_event_id: 是否按事件ID统计手机数据数目，默认False
            
        Returns:
            包含统计信息的字典，结构如下：
            {
                "total_count": int,  # 手机数据总数
                "by_data_type": Dict[str, int],  # 按数据类型统计的数目
                "by_event_id": Dict[str, int]  # 按事件ID统计的数目（仅当by_event_id=True时包含）
            }
        """
        stats = {
            "total_count": 0,
            "by_data_type": {}
        }
        
        if by_event_id:
            stats["by_event_id"] = {}
        
        if not self.phonedata:
            return stats
            
        for data_type, data_list in self.phonedata.items():
            if isinstance(data_list, list):
                # 按数据类型统计
                data_type_count = len(data_list)
                stats["by_data_type"][data_type] = data_type_count
                stats["total_count"] += data_type_count
                
                # 按事件ID统计
                if by_event_id:
                    for item in data_list:
                        if isinstance(item, dict):
                            event_id = item.get("event_id") or item.get("related_event")
                            if event_id:
                                if event_id not in stats["by_event_id"]:
                                    stats["by_event_id"][event_id] = 0
                                stats["by_event_id"][event_id] += 1
        
        return stats

    def judge_event_from_phone_operations(self, event_data_dict: Dict[str, Any], phone_operations_dict: Dict[str, Any], question: str) -> Dict[str, Any]:
        """
        根据事件数据和手机操作数据判断事件推理能力
        
        Args:
            event_data_dict: 事件数据字典 {event_id: event_data}
            phone_operations_dict: 手机操作数据字典 {event_id: phone_operations}
            question: 需要回答的问题
            
        Returns:
            包含事件判断结果的字典
        """
        try:
            from .template3 import EVENT_INFERENCE_JUDGMENT_TEMPLATE
            
            prompt = EVENT_INFERENCE_JUDGMENT_TEMPLATE.format(
                event_info=json.dumps(event_data_dict, ensure_ascii=False, indent=2),
                phone_operations=json.dumps(phone_operations_dict, ensure_ascii=False, indent=2),
                question=question
            )
            
            llm_result = llm_call(prompt)
            print(f"事件推理能力判断结果: {llm_result}")

            
            # 直接尝试解析JSON
            if "{" in llm_result and "}" in llm_result:
                start_idx = llm_result.index("{")
                end_idx = llm_result.rindex("}") + 1
                json_result = json.loads(llm_result[start_idx:end_idx])
                return json_result
            
            # 解析失败，返回默认结果
            print("无法解析LLM判断结果，返回默认值")
            default_result = {
                "event_judgments": []
            }
            
            for event_id in event_data_dict.keys():
                default_result["event_judgments"].append({
                    "event_id": event_id,
                    "related": False,
                    "can_infer": True
                })
            
            return default_result
        except Exception as e:
            print(f"事件推理能力判断失败: {str(e)}")
            # 返回默认结果
            default_result = {
                "event_judgments": []
            }
            
            for event_id in event_data_dict.keys():
                default_result["event_judgments"].append({
                    "event_id": event_id,
                    "related": False,
                    "can_infer": True
                })
            
            return default_result

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
        try:
            from .template3 import PHONE_OPERATIONS_REGENERATION_TEMPLATE
            
            # 获取事件ID
            event_id = event.get("event_id", event.get("id"))
            if not event_id:
                print("事件数据中没有event_id或id字段")
                return []
            from event.template3 import PHONE_OPERATIONS_REGENERATION_TEMPLATE1
            # 使用模板构建重新生成提示
            prompt = PHONE_OPERATIONS_REGENERATION_TEMPLATE1.format(
                event_info=json.dumps(event, ensure_ascii=False, indent=2),
                question=question,
                missing_info=json.dumps(judge_result.get("missing_info", []), ensure_ascii=False, indent=2),
                synthesis_background=judge_result.get("synthesis_background", "")
            )
            from utils.llm_call import llm_call_reason
            print(f"重新生成手机操作提示: {prompt}")
            llm_result = llm_call_reason(prompt)
            print(f"LLM重新生成手机操作结果: {llm_result}")
            
            # 提取JSON内容
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
                
                # 2. 为新生成的手机操作数据分配phone_id并添加到phonedata中
                added_count = 0
                
                for operation in regenerated_operations:
                    if isinstance(operation, dict):
                        # 确保operation有data_type字段
                        data_type = operation.get("type")
                        if not data_type:
                            print(f"手机操作数据缺少type字段: {operation}")
                            continue
                        
                        # 确保event_id与传入的事件ID一致
                        operation["event_id"] = event_id
                        
                        # 分配phone_id
                        if data_type not in self.phone_id_counters:
                            self.phone_id_counters[data_type] = 1
                        
                        phone_id = self.phone_id_counters[data_type]
                        operation["phone_id"] = str(phone_id)
                        self.phone_id_counters[data_type] += 1
                        
                        # 添加到相应的数据类型列表中
                        if data_type not in self.phonedata:
                            self.phonedata[data_type] = []
                        self.phonedata[data_type].append(operation)
                        added_count += 1
                
                print(f"成功添加{added_count}条新生成的手机操作数据")
                return regenerated_operations
            
            print("无法提取重新生成的手机操作数据")
            return []
        except Exception as e:
            print(f"重新生成手机操作数据失败: {str(e)}")
            return []

    def _validate_and_regenerate_phone_operations(self, question: Dict[str, Any], event_tree_data: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        验证并根据需要重生成手机操作数据
        
        Args:
            question: 问题字典，包含question、required_events等字段
            event_tree_data: 事件树数据列表
            
        Returns:
            Tuple[Dict[str, Any], List[Dict[str, Any]]]: 优化后的问题和对应的手机操作列表
        """
        updated_question = question['questions'].copy()
        all_phone_operations = []
        event_data_dict = {}
        phone_operations_dict = {}
        que =question['questions']
        # 获取问题相关的事件ID
        event_ids = que.get("required_events_id", [])
        print("event_ids:", event_ids)
        
        # 收集所有事件数据和对应的手机操作数据
        for event_id in event_ids:
            if event_id:
                # 查找对应的事件数据
                corresponding_event = None
                # 从self.daily_event中查找
                if self.daily_event and isinstance(self.daily_event, list):
                    for event in self.daily_event:
                        if event.get("id") == event_id or event.get("event_id") == event_id:
                            corresponding_event = event
                            break
                if not corresponding_event:
                    # 从传入的event_tree_data中查找
                    for event in event_tree_data:
                        if event.get("id") == event_id or event.get("event_id") == event_id:
                            corresponding_event = event
                            break
                
                if corresponding_event:
                    # 根据事件ID获取相关手机操作
                    phone_operations = self.get_phone_operations_by_event_id(event_id)
                    # 保存事件数据和手机操作数据
                    event_data_dict[event_id] = corresponding_event
                    phone_operations_dict[event_id] = phone_operations
                    # 收集所有手机操作
                    all_phone_operations.extend(phone_operations)

        # 如果有事件数据，统一调用LLM进行判断
        if event_data_dict:
            judge_result = self.judge_event_from_phone_operations(event_data_dict, phone_operations_dict, question["questions"])
            print('here--------')
            print(judge_result)
            event_judgment = judge_result
            can_infer = judge_result.get("can_infer", False)

            # # 根据判断结果处理每个事件
            # for event_judgment in judge_result.get("event_judgments", []):
            #     event_id = event_judgment.get("event_id")
            #     related = event_judgment.get("related", False)
            #     can_infer = event_judgment.get("can_infer", False)
            #     print('---------------')
            #     print(event_judgment)

            if not can_infer:
                    # 如果事件相关但手机操作数据无法推断出答案，重新生成手机操作数据
                    event_data = event_data_dict.get(event_id)
                    if event_data:
                        # 构建重生成所需的judge_result
                        regen_judge_result = {
                            "missing_info": event_judgment.get("missing_info", []),
                            "synthesis_background": event_judgment.get("synthesis_background", ""),
                            "regenerate_all": True
                        }
                        
                        regenerated_operations = self.regenerate_phone_operations(event_data, regen_judge_result, question["questions"])
                        # 更新手机操作数据 - 增加而不是替换
                        if event_id in phone_operations_dict:
                            phone_operations_dict[event_id].extend(regenerated_operations)
                        else:
                            phone_operations_dict[event_id] = regenerated_operations
                        # 更新所有手机操作列表 - 直接添加新生成的操作而不是重新构建
                        all_phone_operations.extend(regenerated_operations)
        
        return updated_question, all_phone_operations

    def generate_reasoning_questions_from_event_tree_id(self, event_ids: List[int], num_questions: int) -> List[Dict[str, Any]]:
        """
        基于指定event_id的事件树数据生成推理问题
        
        Args:
            event_ids: 要使用的事件ID数组（整数类型）
            num_questions: 生成问题的数量
            
        Returns:
            基于事件树数据的推理问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")
        
        # 获取事件树数据（通过event_id数组获取）
        event_tree_data = self.get_event_tree_data_by_id(event_ids)
        print(event_tree_data)
        questions_opt = []
        
        # 检查获取到的事件数目是否少于id数组的一半
        if not event_tree_data:
            return []
        
        # 计算获取到的事件数目和id数组长度
        found_events_count = len(event_tree_data)
        requested_events_count = len(event_ids)
        
        # 如果获取到的事件数目少于id数组的一半，放弃生成返回空数组
        if found_events_count < requested_events_count / 2:
            print(f"获取到的事件数目({found_events_count})少于请求的一半({requested_events_count/2})，放弃生成")
            return []
        
        # 重新计算num_questions：查找到的事件数/2下取整
        num_questions = min(requested_events_count // 2, 4)
        num_questions = max(2,num_questions)
        print(f"重新计算num_questions为：{num_questions}")
        
        # 如果num_questions为0，返回空数组
        if num_questions <= 0:
            return []
        else:
            # 构建事件上下文
            event_context = {
                'name': name,
                'selected_events': event_tree_data
            }
            
            # 直接使用llm_call生成问题
            prompt = CAUSAL_REASONING_TEMPLATE.format(
                num_questions=num_questions,
                event_info=json.dumps(event_context, ensure_ascii=False, indent=2)
            )

            from utils.llm_call import llm_call_reason
            # 调用LLM生成问题
            llm_result = llm_call_reason(prompt)
            print(llm_result)
            
            # 提取JSON内容
            try:
                if '{' in llm_result:
                    start_idx = llm_result.index('{')
                    end_idx = llm_result.rindex('}') + 1
                    json_content = llm_result[start_idx:end_idx]
                    json_result = json.loads(json_content)
                    
                    # 统一处理返回格式：如果是包含"questions"字段的对象，则返回questions数组
                    if isinstance(json_result, dict) and "questions" in json_result:
                        questions = json_result["questions"]
                    else:
                        questions = json_result
            except Exception as e:
                print(f"解析推理问题失败: {e}")
                questions = []
            
            print("开始溯源")
            
            # 对生成的每个问题进行事件溯源
            for question in questions:
                # 获取问题相关信息

                # 调用事件溯源功能
                tracing_result = self._event_tracing(question)
                question['event_tracing_result'] = tracing_result
                
                # 根据instruction字段判断是否需要处理问题
                instruction = tracing_result.get('instruction', 1)
                question['instruction'] = instruction

                # 添加到待处理问题列表
                questions_opt.append(tracing_result)
        
        # 处理生成的问题，验证是否能从手机操作中推理出来
        valid_questions = []
        question_phone_operations = []
        print("处理生成问题", len(questions_opt))
        
        for question in questions_opt:
            print(question)
            # 检查事件溯源结果的instruction字段
            instruction = question.get('instruction', 1)
            
            # 根据instruction判断是否处理该问题
            if instruction == 2:
                # instruction为2，跳过该问题
                print(f"问题 '{question.get('question', '')}' 的instruction为2，放弃处理")
                continue
            elif instruction in [1, 3, 4]:
                # instruction为1、3、4，进行验证和重生成
                updated_question, phone_ops = self._validate_and_regenerate_phone_operations(question, event_tree_data)
                valid_questions.append(updated_question)
                question_phone_operations.append(phone_ops)
            else:
                # 其他情况，默认处理
                updated_question, phone_ops = self._validate_and_regenerate_phone_operations(question, event_tree_data)
                valid_questions.append(updated_question)
                question_phone_operations.append(phone_ops)
        
        # 确保问题和手机操作数量一致
        result_count = min(len(valid_questions), len(question_phone_operations))
        
        # 将手机操作数据的类型和ID整合到每个问题的evidence字段中
        for i in range(result_count):
            # 从手机操作中提取类型和ID
            operation_evidence = []
            for operation in question_phone_operations[i]:
                if isinstance(operation, dict) and 'phone_id' in operation:
                    operation_type = operation.get('type', 'unknown')
                    operation_evidence.append({"type": operation_type, "id": operation['phone_id']})
            valid_questions[i]["evidence"] = operation_evidence
        
        return valid_questions[:num_questions]

    def generate_reasoning_questions_from_event_tree_id2(self, event_ids: List[int], num_questions: int) -> List[
        Dict[str, Any]]:
        """
        基于指定event_id的事件树数据生成推理问题

        Args:
            event_ids: 要使用的事件ID数组（整数类型）
            num_questions: 生成问题的数量

        Returns:
            基于事件树数据的推理问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")

        # 获取事件树数据（通过event_id数组获取）
        event_tree_data = self.get_event_tree_data_by_id(event_ids)
        print(event_tree_data)
        questions_opt = []

        # 检查获取到的事件数目是否少于id数组的一半
        if not event_tree_data:
            return []

        # 计算获取到的事件数目和id数组长度
        found_events_count = len(event_tree_data)
        requested_events_count = len(event_ids)

        # 如果获取到的事件数目少于id数组的一半，放弃生成返回空数组
        if found_events_count < requested_events_count / 2 :
            print(f"获取到的事件数目({found_events_count})少于请求的一半({requested_events_count / 2})，放弃生成")
            return []

        # 重新计算num_questions：查找到的事件数/2下取整
        num_questions = min(requested_events_count // 2, 3)
        num_questions = max(2,num_questions)
        print(f"重新计算num_questions为：{num_questions}")

        # 如果num_questions为0，返回空数组
        if num_questions <= 0:
            return []
        else:
            # 构建事件上下文
            event_context = {
                'name': name,
                'selected_events': event_tree_data
            }
            from event.template3 import COUNT_TEMPLATE
            # 直接使用llm_call生成问题
            prompt = COUNT_TEMPLATE.format(
                event_info=json.dumps(event_context, ensure_ascii=False, indent=2)
            )

            # 调用LLM生成问题
            llm_result = llm_call(prompt)
            print(llm_result)

            # 提取JSON内容
            try:
                if '[' in llm_result:
                    start_idx = llm_result.index('[')
                    end_idx = llm_result.rindex(']') + 1
                    json_content = llm_result[start_idx:end_idx]
                    json_result = json.loads(json_content)

                    # 统一处理返回格式：如果是包含"questions"字段的对象，则返回questions数组
                    if isinstance(json_result, dict) and "questions" in json_result:
                        questions = json_result["questions"]
                    else:
                        questions = json_result
            except Exception as e:
                print(f"解析推理问题失败: {e}")
                questions = []

            print("开始溯源")

            # 对生成的每个问题进行事件溯源
            for question in questions:
                # 获取问题相关信息

                # 调用事件溯源功能
                tracing_result = self._event_tracing2(question)
                question['event_tracing_result'] = tracing_result

                # 根据instruction字段判断是否需要处理问题
                instruction = tracing_result.get('instruction', 1)
                question['instruction'] = instruction

                # 添加到待处理问题列表
                questions_opt.append(tracing_result)

        # 处理生成的问题，验证是否能从手机操作中推理出来
        valid_questions = []
        question_phone_operations = []
        print("处理生成问题", len(questions_opt))
        print(
            questions_opt
        )
        print('-------------------------------')
        for question in questions_opt:
            print(question)
            # 检查事件溯源结果的instruction字段
            instruction = question.get('instruction', 1)

            # 根据instruction判断是否处理该问题
            if instruction == 2:
                # instruction为2，跳过该问题
                print(f"问题 '{question.get('question', '')}' 的instruction为2，放弃处理")
                continue
            elif instruction in [1, 3, 4]:
                # instruction为1、3、4，进行验证和重生成
                updated_question, phone_ops = self._validate_and_regenerate_phone_operations(question, event_tree_data)
                valid_questions.append(updated_question)
                question_phone_operations.append(phone_ops)
            else:
                # 其他情况，默认处理
                updated_question, phone_ops = self._validate_and_regenerate_phone_operations(question, event_tree_data)
                valid_questions.append(updated_question)
                question_phone_operations.append(phone_ops)

        # 确保问题和手机操作数量一致
        result_count = min(len(valid_questions), len(question_phone_operations))

        # 将手机操作数据的类型和ID整合到每个问题的evidence字段中
        for i in range(result_count):
            # 从手机操作中提取类型和ID
            operation_evidence = []
            for operation in question_phone_operations[i]:
                if isinstance(operation, dict) and 'phone_id' in operation:
                    operation_type = operation.get('type', 'unknown')
                    operation_evidence.append({"type": operation_type, "id": operation['phone_id']})
            valid_questions[i]["evidence"] = operation_evidence

        return valid_questions[:num_questions]