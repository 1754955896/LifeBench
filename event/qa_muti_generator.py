import json
import os
import random
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import threading

from utils.llm_call import llm_call
from event.template3 import (
    MULTI_HOP_FROM_EVENT_TREE_TEMPLATE, 
    MULTI_HOP_QUESTION_TEMPLATE,
    EVENT_TRACING_TEMPLATE,
    EVENT_INFERENCE_JUDGMENT_TEMPLATE,
    MULTI_EVENT_INFERENCE_JUDGMENT_TEMPLATE,
    PHONE_OPERATIONS_REGENERATION_TEMPLATE,
    MULTI_DAY_CONVERSATION_QUESTION_TEMPLATE,
    PATTERN_RECOGNITION_TEMPLATE,
    UNANSWERABLE_QUESTION_TEMPLATE
)
class QAMutiGenerator:
    def __init__(self, persona_data: Dict[str, Any] = None, event_tree: Dict[str, Any] = None, 
                 daily_event: Dict[str, Any] = None, draft_event: Dict[str, Any] = None, 
                 special_event: Dict[str, Any] = None, phone_data_dir: str = None):
        """
        初始化多跳问题生成器
        
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
        
        # 添加线程锁以保护共享状态的修改
        self.phonedata_lock = threading.Lock()
        self.phone_id_lock = threading.Lock()
        
        # 从special_event中提取unique_events
        self.unique_events = self.special_event.get('unique_events', []) if self.special_event else []
        
        # 如果提供了phone_data_dir，则加载手机数据
        if phone_data_dir:
            self.load_phone_data_from_dir(phone_data_dir)
        

    

    
    def get_current_event_data(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        获取当前事件数据（默认从daily_event中随机获取）
        
        Args:
            count: 获取的数据数量
        
        Returns:
            事件数据列表
        """
        if not self.daily_event or not isinstance(self.daily_event, list):
            return []
        
        # 随机选择事件
        return random.sample(self.daily_event, min(count, len(self.daily_event)))
    
    def _get_event_tree_data(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        通用事件树数据获取函数
        
        Args:
            count: 数据数量限制
        
        Returns:
            事件树数据列表
        """
        if isinstance(self.event_tree, list) and len(self.event_tree) > 0:
            # 随机选择事件
            return random.sample(self.event_tree, min(count, len(self.event_tree)))
        return self.event_tree if isinstance(self.event_tree, list) else []
    
    def _get_persona_data(self, count: int = 10) -> Dict[str, Any]:
        """
        通用画像数据获取函数
        
        Args:
            count: 数据数量限制
        
        Returns:
            画像数据字典
        """
        return self.persona_data
    
    def _get_draft_event_data(self, count: int = 15) -> List[Dict[str, Any]]:
        """
        通用草稿事件数据获取函数
        
        Args:
            count: 数据数量限制（默认15天）
        
        Returns:
            草稿事件数据列表（按天组织，连续选择）
        """
        if not self.draft_event or not isinstance(self.draft_event, dict):
            return []
        
        # 收集所有天的数据
        all_days_data = []
        for month, month_data in self.draft_event.items():
            if isinstance(month_data, list):
                for day_data in month_data:
                    # 移除state字段（如果存在）
                    filtered_day_data = {k: v for k, v in day_data.items() if k != 'state'}
                    all_days_data.append(filtered_day_data)
        
        if not all_days_data:
            return []
        
        # 按日期排序
        all_days_data.sort(key=lambda x: x.get('date', ''))
        
        total_days = len(all_days_data)
        if total_days <= count:
            # 如果总天数不足或等于15天，则返回所有天的数据
            return all_days_data
        
        # 随机选择起始点，确保能连续选择15天
        max_start_index = total_days - count
        start_index = random.randint(0, max_start_index)
        
        # 返回连续的15天数据
        return all_days_data[start_index:start_index + count]
    
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
                # 移除state字段（如果存在）
                filtered_month_data = []
                for day_data in month_data:
                    filtered_day_data = {k: v for k, v in day_data.items() if k != 'state'}
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
    
    def _get_daily_event_data(self, count: int = 10, continuous: bool = False) -> List[Dict[str, Any]]:
        """
        通用每日事件数据获取函数
        
        Args:
            count: 数据数量限制
            continuous: 是否连续选取数据
        
        Returns:
            每日事件数据列表
        """
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
    
    def judge_event_from_phone_operations(self, event_data_dict: Dict[str, Dict[str, Any]], phone_operations_dict: Dict[str, List[Dict[str, Any]]], question: str) -> Dict[str, Any]:
        """
        调用LLM统一判断多个事件的手机操作数据能否回答给定的问题
        
        Args:
            event_data_dict: 事件数据字典，键为event_id，值为事件数据
            phone_operations_dict: 手机操作数据字典，键为event_id，值为手机操作数据列表
            question: 需要回答的问题
            
        Returns:
            包含各事件判断结果的字典，包括event_judgments（各事件的判断结果）、
            missing_info（缺失信息）、synthesis_background（合成背景）
        """
        import json
        
        # 构建事件和手机操作数据列表
        event_phone_data = []
        for event_id, event_data in event_data_dict.items():
            phone_operations = phone_operations_dict.get(event_id, [])
            event_phone_data.append({
                "event_id": event_id,
                "event_info": event_data,
                "phone_operations": phone_operations
            })
        
        # 使用多事件判断模板构建提示
        prompt = MULTI_EVENT_INFERENCE_JUDGMENT_TEMPLATE.format(
            event_phone_data=json.dumps(event_phone_data, ensure_ascii=False, indent=2),
            question=question
        )
        print(f"多事件判断提示: {prompt}")
        
        # 调用LLM
        llm_result = llm_call(prompt)
        print(f"LLM多事件判断结果: {llm_result}")
        
        # 解析结果
        try:
            if '{' in llm_result and '}' in llm_result:
                start_idx = llm_result.index('{')
                end_idx = llm_result.rindex('}') + 1
                json_content = llm_result[start_idx:end_idx]
                result = json.loads(json_content)
                return {
                    "event_judgments": result.get("event_judgments", [])
                }
            else:
                # 默认返回False
                print("LLM返回结果格式不正确，默认返回False")
                # 构建默认错误结果
            default_result = {
                "event_judgments": []
            }
            # 为每个事件添加默认判断
            for event_id in event_data_dict.keys():
                default_result["event_judgments"].append({
                    "event_id": event_id,
                    "related": False,
                    "can_infer": True,  # 不相关的事件不需要重新生成手机操作数据
                    "missing_info": ["无法解析判断结果"],
                    "synthesis_background": "无法进行判断"
                })
            return default_result
        except Exception as e:
            print(f"解析LLM判断结果失败: {e}")
            # 构建默认错误结果
            default_result = {
                "event_judgments": [],
                "missing_info": ["解析判断结果失败"],
                "synthesis_background": "无法进行判断"
            }
            # 为每个事件添加默认判断
            for event_id in event_data_dict.keys():
                default_result["event_judgments"].append({
                    "event_id": event_id,
                    "related": False,
                    "can_infer": True  # 不相关的事件不需要重新生成手机操作数据
                })
            return default_result
    
    def regenerate_phone_operations(self, event: Dict[str, Any], judge_result: Dict[str, Any], question: str, existing_phone_operations: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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
        
        # 使用模板构建重新生成提示
        prompt = PHONE_OPERATIONS_REGENERATION_TEMPLATE.format(
            existing_phone_operations=json.dumps(existing_phone_operations or [], ensure_ascii=False, indent=2),
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
                
                print(f"保留原有手机操作数据，仅添加新增的手机操作")
                
                # 2. 为新生成的手机操作数据分配phone_id并添加到phonedata中
                added_count = 0
                
                for operation in regenerated_operations:
                    if isinstance(operation, dict):
                        # 确保operation有data_type字段
                        data_type = operation.get("type")
                        if not data_type:
                            print(f"手机操作数据缺少ype字段: {operation}")
                            continue
                        
                        # 确保event_id与传入的事件ID一致
                        operation["event_id"] = event_id
                        
                        # 分配phone_id（线程安全）
                        with self.phone_id_lock:
                            if data_type not in self.phone_id_counters:
                                self.phone_id_counters[data_type] = 1
                            
                            phone_id = self.phone_id_counters[data_type]
                            operation["phone_id"] = str(phone_id)
                            self.phone_id_counters[data_type] += 1
                        
                        # 添加到相应的数据类型列表中（线程安全）
                        with self.phonedata_lock:
                            if data_type not in self.phonedata:
                                self.phonedata[data_type] = []
                            self.phonedata[data_type].append(operation)
                        added_count += 1
                
                print(f"成功添加{added_count}条新生成的手机操作数据")
                return regenerated_operations
            else:
                print("LLM返回结果不是有效的JSON数组")
                return []
        except Exception as e:
            print(f"解析或处理重新生成的手机操作数据失败: {e}")
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
        from utils.llm_call import llm_call_reason
        # 调用LLM生成问题
        llm_result = llm_call_reason(prompt)
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
    
    def generate_unanswerable_questions(self, num_questions: int = 5, month: str = None) -> List[Dict[str, Any]]:
        """
        生成不可回答的问题
        
        Args:
            num_questions: 生成问题的数量
            month: 指定月份，格式为YYYY-MM（此处不再使用，保留参数以保持接口兼容性）
            
        Returns:
            生成的不可回答问题列表
        """
        # 准备输入数据
        
        # 1. 处理用户画像数据（去掉relation字段）
        persona_data = self.persona_data.copy() if self.persona_data else {}
        if "relation" in persona_data:
            del persona_data["relation"]
        
        # 2. 获取连续5天的日常事件数据
        daily_event_data = self._get_daily_event_data(count=10, continuous=True)
        
        # 3. 构建提示模板
        prompt = UNANSWERABLE_QUESTION_TEMPLATE.format(
            num_questions=num_questions,
            persona_info=json.dumps(persona_data, ensure_ascii=False, indent=2),
            draft_event_info=json.dumps(daily_event_data, ensure_ascii=False, indent=2)
        )
        
        # 4. 调用LLM生成问题
        from utils.llm_call import llm_call_reason
        llm_result = llm_call_reason(prompt)
        print(f"LLM生成不可回答问题结果: {llm_result}")
        
        # 5. 解析结果
        try:
            if '{' in llm_result and '}' in llm_result:
                start_idx = llm_result.index('{')
                end_idx = llm_result.rindex('}') + 1
                json_content = llm_result[start_idx:end_idx]
                result = json.loads(json_content)
                
                # 返回生成的问题列表
                return result.get("questions", [])
            else:
                print("LLM返回结果格式不正确，无法解析")
                return []
        except Exception as e:
            print(f"解析不可回答问题生成结果失败: {e}")
            return []
    
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
        dates = question.get("required_event_dates", [])

        
        # 基于所有日期获取对应日期的daily_event
        events_by_date = {}
        all_events = []
        event_id_map = {}
        
        for date in dates:
            events_on_date = []
            for event in self.daily_event:
                if "date" in event and event["date"]:
                    # 从时间段字符串中提取日期部分
                    time_range = event["date"][0] if isinstance(event["date"], list) else event["date"]
                    date_part = time_range.split(" ")[0]
                    
                    if date_part == date:
                        events_on_date.append(event)
                        all_events.append(event)
                        # 记录事件ID映射
                        if "id" in event:
                            event_id_map[event["id"]] = event
            
            events_by_date[date] = events_on_date
        
        print(f"找到相关日期的daily event数据，共{len(all_events)}条")
        
        # 调用LLM分析事件和问题
        try:
            # 构建分析请求，使用template3.py中的新模板
            from .template3 import EVENT_TRACING_ENHANCED_TEMPLATE
            
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
            
            prompt = EVENT_TRACING_ENHANCED_TEMPLATE.format(
                question=json.dumps(question, ensure_ascii=False, indent=2),
                dates=', '.join(dates),
                events_by_date=json.dumps(events_by_date, ensure_ascii=False, indent=2),
                persona=json.dumps(processed_persona, ensure_ascii=False, indent=2)
            )
            
            # 直接调用LLM分析
            analysis_result = llm_call(prompt, record=0)
            
            print("LLM分析结果：", analysis_result)
            
            # 尝试解析分析结果，直接匹配第一个和最后一个{}并加载JSON
            try:
                if "{" in analysis_result and "}" in analysis_result:
                    start_idx = analysis_result.index("{")
                    end_idx = analysis_result.rindex("}") + 1
                    json_result = json.loads(analysis_result[start_idx:end_idx])
                    return json_result
            except Exception as json_e:
                print(f"事件溯源增强版结果解析失败: {str(json_e)}")
                
            # 所有解析尝试失败，返回原始分析结果
            return analysis_result
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
    
    def generate_multi_hop_questions(self, num_questions: int = 5) -> List[Dict[str, Any]]:
        """
        生成多跳问题（基于多个事件或信息片段的关联）
        支持四种生成方式：
        1. 基于事件树的生成（从事件树数据中随机抽取事件）
        2. 基于画像的生成（根据用户画像信息生成问题）
        3. 基于draft的生成（从draft数据中抽取一个月事件生成）
        4. 基于每日事件的生成（从每日事件数据中按日期获取事件生成）
        
        Args:
            num_questions: 生成问题的数量
        
        Returns:
            多跳问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")
        
        # 按2:2:3:3比例分配问题数量
        event_tree_questions_count = int(num_questions * 0.2)  # 20% 来自事件树
        persona_questions_count = int(num_questions * 0.2)      # 20% 来自画像
        draft_questions_count = int(num_questions * 0.3)        # 30% 来自草稿
        daily_questions_count = num_questions - event_tree_questions_count - persona_questions_count - draft_questions_count  # 30% 来自每日事件
        
        # 方法1：基于事件树的生成
        if event_tree_questions_count > 0:
            tree_questions = self._generate_multi_hop_questions_from_event_tree(event_tree_questions_count)
            questions.extend(tree_questions)
        
        # 方法2：基于画像的生成
        if persona_questions_count > 0:
            persona_questions = self._generate_multi_hop_questions_from_persona(persona_questions_count)
            questions.extend(persona_questions)
        
        # 方法3：基于draft的生成
        if draft_questions_count > 0:
            draft_questions = self._generate_multi_hop_questions_from_draft(draft_questions_count)
            questions.extend(draft_questions)
        
        # 方法4：基于每日事件的生成（按日期获取）
        if daily_questions_count > 0:
            daily_questions = self._generate_multi_hop_questions_from_daily_event(daily_questions_count)
            questions.extend(daily_questions)
        
        # 如果生成的问题数量不足，补充通用多跳问题
        while len(questions) < num_questions:
            questions.append({
                "question": f"{name}的哪些生活方面之间可能存在相互影响？",
                "answer": "",
                "score_points": [{"description": "问题回答正确性", "score": 10}],
                "required_events": [""]
            })
        
        return questions[:num_questions]
    
    def generate_yearly_pattern_recognition_questions(self, year: str, num_questions_per_month: int) -> List[Dict[str, Any]]:
        """
        并行生成一年12个月的模式识别与习惯分析问题，并为每个问题分配asktime字段
        
        Args:
            year: 年份，格式为"YYYY"
            num_questions_per_month: 每月生成的问题数量
        
        Returns:
            所有生成的问题列表
        """
        import concurrent.futures
        import time
        
        all_questions = []
        
        # 生成12个月的月份字符串列表，格式为"YYYY-MM"
        months = [f"{year}-{str(month).zfill(2)}" for month in range(1, 13)]
        
        print(f"开始并行生成{year}年12个月的模式识别与习惯分析问题，每月{num_questions_per_month}个问题")
        start_time = time.time()
        
        # 使用ThreadPoolExecutor并行生成每个月的问题
        with concurrent.futures.ThreadPoolExecutor(max_workers=24) as executor:
            # 提交所有月份的任务
            future_to_month = {
                executor.submit(self.generate_pattern_recognition_and_habit_analysis_questions, month, num_questions_per_month): month
                for month in months
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_month):
                month = future_to_month[future]
                try:
                    month_questions = future.result()
                    print(f"完成{month}月份的问题生成，共生成{len(month_questions)}个问题")
                    
                    # 为当前月的问题添加ask_time字段
                    import random
                    current_month = int(month.split('-')[1])  # 提取当前月份（如从"2023-01"提取01）
                    for question in month_questions:
                        # 生成随机月份，大于等于当前月份
                        random_month = random.randint(current_month, 12)
                        # 格式化为"2025-xx"形式
                        ask_time = f"2025-{str(random_month).zfill(2)}"
                        question["ask_time"] = ask_time
                    
                    all_questions.extend(month_questions)
                except Exception as exc:
                    print(f"{month}月份的问题生成失败: {exc}")
        
        total_time = time.time() - start_time
        print(f"所有问题生成完成，总耗时{total_time:.2f}秒，共生成{len(all_questions)}个问题")
        
        # 为所有问题添加question_type字段
        for question in all_questions:
            if "question_type" not in question:
                question["question_type"] = "user_modeling"
        
        # 保存所有问题到JSON文件
        import os
        
        try:
            if self.phone_data_dir and os.path.exists(self.phone_data_dir):
                # 获取phone_data_dir的上一级目录
                parent_dir = os.path.dirname(self.phone_data_dir)
                # 构造保存文件路径
                file_path = os.path.join(parent_dir, "user_modeling_qa.json")
                
                # 保存问题到文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(all_questions, f, ensure_ascii=False, indent=2)
                print(f"所有问题已保存到文件: {file_path}")
            else:
                print("phone_data_dir不存在，无法保存问题到指定路径")
        except Exception as e:
            print(f"保存问题失败: {e}")
        
        return all_questions
    
    def generate_yearly_multi_hop_questions(self, year: str, num_questions_per_month: int, num_persona_questions: int) -> List[Dict[str, Any]]:
        """
        并行生成一年12个月的多跳问题，并调用4次基于画像的问题生成
        
        Args:
            year: 年份，格式为"YYYY"
            num_questions_per_month: 每月生成的问题数量
            num_persona_questions: 每次基于画像生成的问题数量
        
        Returns:
            所有生成的问题列表
        """
        import concurrent.futures
        import time
        
        all_questions = []
        
        # 生成12个月的月份字符串列表，格式为"YYYY-MM"
        months = [f"{year}-{str(month).zfill(2)}" for month in range(1, 13)]
        
        print(f"开始并行生成{year}年12个月的问题，每月{num_questions_per_month}个问题")
        start_time = time.time()
        
        # 使用ThreadPoolExecutor并行生成每个月的问题
        with concurrent.futures.ThreadPoolExecutor(max_workers=24) as executor:
            # 提交所有月份的任务
            future_to_month = {
                executor.submit(self.generate_multi_hop_questions_from_draft, month, num_questions_per_month): month
                for month in months
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_month):
                month = future_to_month[future]
                try:
                    month_questions = future.result()
                    print(f"完成{month}月份的问题生成，共生成{len(month_questions)}个问题")
                    
                    all_questions.extend(month_questions)
                except Exception as exc:
                    print(f"{month}月份的问题生成失败: {exc}")
        
        draft_time = time.time() - start_time
        print(f"所有月份的问题生成完成，耗时{draft_time:.2f}秒，共生成{len(all_questions)}个问题")
        
        print(f"开始调用4次基于画像的问题生成，每次生成{num_persona_questions}个问题")
        start_time = time.time()
        
        # 调用4次基于画像的问题生成
        for i in range(4):
            try:
                persona_questions = self.generate_multi_hop_questions_from_persona(num_persona_questions)
                print(f"完成第{i+1}次基于画像的问题生成，共生成{len(persona_questions)}个问题")
                all_questions.extend(persona_questions)
            except Exception as exc:
                print(f"第{i+1}次基于画像的问题生成失败: {exc}")
        
        persona_time = time.time() - start_time
        print(f"所有基于画像的问题生成完成，耗时{persona_time:.2f}秒")
        
        # 生成不可回答问题
        print(f"开始生成不可回答问题，共调用6次，每次生成2个问题")
        start_time = time.time()
        
        unanswerable_questions = []
        for i in range(4):
            try:
                questions = self.generate_unanswerable_questions(num_questions=2)
                print(f"完成第{i+1}次不可回答问题生成，共生成{len(questions)}个问题")
                unanswerable_questions.extend(questions)
            except Exception as exc:
                print(f"第{i+1}次不可回答问题生成失败: {exc}")
        
        # 将不可回答问题添加到总列表中
        all_questions.extend(unanswerable_questions)
        
        unanswerable_time = time.time() - start_time
        print(f"所有不可回答问题生成完成，耗时{unanswerable_time:.2f}秒")
        
        total_time = draft_time + persona_time + unanswerable_time
        print(f"所有问题生成完成，总耗时{total_time:.2f}秒，共生成{len(all_questions)}个问题")
        
        # 为所有问题添加question_type字段
        for question in all_questions:
            if not question.get("question_type"):
                question["question_type"] = "mutihop"
        
        # 保存所有问题到JSON文件
        import os
        
        try:
            if self.phone_data_dir and os.path.exists(self.phone_data_dir):
                # 获取phone_data_dir的上一级目录
                parent_dir = os.path.dirname(self.phone_data_dir)
                # 构造保存文件路径
                file_path = os.path.join(parent_dir, "muti_hop_qa.json")
                
                # 保存问题到文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(all_questions, f, ensure_ascii=False, indent=2)
                print(f"所有问题已保存到文件: {file_path}")
            else:
                print("phone_data_dir不存在，无法保存问题到指定路径")
        except Exception as e:
            print(f"保存问题失败: {e}")
        
        return all_questions
    
    def _generate_multi_hop_questions_from_event_tree(self, num_questions: int) -> List[Dict[str, Any]]:
        """
        基于事件树的生成（从事件树数据中随机抽取事件，通过LLM生成多跳推理问题）
        
        Args:
            num_questions: 生成问题的数量
        
        Returns:
            基于事件树的多跳问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")
        
        # 获取事件树数据
        event_tree_data = self._get_event_tree_data()
        
        if event_tree_data:
            # 每次生成5个问题
            fixed_num_questions = 5
            llm_calls_needed = max(1, (num_questions + 4) // 5)
            
            for call_idx in range(llm_calls_needed):
                # 随机选择一个事件
                selected_event = random.choice(event_tree_data)
                
                # 递归查找所有最下层的子事件（叶子节点事件）
                def get_all_leaf_subevents(event):
                    leaf_events = []
                    if 'subevent' in event and event['subevent']:
                        for subevent in event['subevent']:
                            # 如果子事件还有子事件，递归处理
                            if 'subevent' in subevent and subevent['subevent']:
                                leaf_events.extend(get_all_leaf_subevents(subevent))
                            else:
                                # 如果没有子事件，这就是叶子节点事件
                                leaf_events.append(subevent)
                    return leaf_events
                
                # 获取所有叶子节点事件
                all_leaf_events = get_all_leaf_subevents(selected_event)
                
                # 构建简化版的事件上下文
                simplified_context = {
                    'main_event_name': selected_event.get('name', ''),
                    'leaf_subevents': all_leaf_events
                }
                
                # 使用通用问题生成函数
                generated_questions = self._generate_questions_with_template(
                    data=simplified_context,
                    template=MULTI_HOP_FROM_EVENT_TREE_TEMPLATE,
                    num_questions=fixed_num_questions,
                    event_info=json.dumps(simplified_context, ensure_ascii=False, indent=2),
                    question_type="事件树多跳问题"
                )
                
                # 添加生成的问题到结果列表
                for question in generated_questions:
                    if question and len(questions) < num_questions:
                        questions.append(question)
                        
                if len(questions) >= num_questions:
                    break
        else:
            # 如果event_tree为空或不是列表，使用基础问题
            for i in range(min(num_questions, 3)):
                questions.append({
                    "question": f"{name}的事件之间可能存在怎样的深层关联？",
                    "answer": "",
                    "score_points": [{"description": "问题回答正确性", "score": 10}],
                    "required_events": [""]
                })
        
        return questions[:num_questions]
    
    def generate_multi_hop_questions_from_persona(self, num_questions: int) -> List[Dict[str, Any]]:
        """
        基于画像的生成（根据用户画像信息生成需要整合不同天对话数据的问题）
        
        Args:
            num_questions: 生成问题的数量
        
        Returns:
            基于画像的多跳问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        name = self.persona_data.get("name", "该用户")
        
        # 获取画像数据
        persona_data = self._get_persona_data()
        
        # 使用新的多日对话问题模板直接生成问题（不调用_generate_questions_with_template）
        if isinstance(persona_data, (dict, list)):
            data_str = json.dumps(persona_data, ensure_ascii=False, indent=2)
        else:
            data_str = str(persona_data)
        
        # 获取联系人信息并过滤字段
        contact_data = self.phonedata.get('contact', [])
        # 只保留需要的字段：name、relation、phoneNumber
        filtered_contact_data = []
        for contact in contact_data:
            filtered_contact = {
                "name": contact.get("name", ""),
                "relation": contact.get("relation", ""),
                "phoneNumber": contact.get("phoneNumber", "")
            }
            filtered_contact_data.append(filtered_contact)
        
        # 构建多日对话问题的prompt
        multi_day_prompt = MULTI_DAY_CONVERSATION_QUESTION_TEMPLATE.format(
            num_questions=num_questions,
            data_info=data_str,
            name=name,
            persona_info=json.dumps(persona_data, ensure_ascii=False, indent=2),
            contact_info=json.dumps(filtered_contact_data, ensure_ascii=False, indent=2),
            question_type="多日对话整合推理"
        )
        
        # 调用LLM生成多日对话问题
        from utils.llm_call import llm_call_reason
        llm_result = llm_call_reason(multi_day_prompt)
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
            print(f"解析多日对话问题失败: {e}")
        
        # 处理生成的问题，将evidence中的手机数据提取并保存到phone_data
        final_questions = []
        for question in questions:
            if 'evidence' in question:
                evidence_data = question.pop('evidence')
                
                # 处理evidence中的手机数据
                processed_evidence = []
                for evidence_op in evidence_data:
                    # 确保event_id为0
                    evidence_op['event_id'] = "0"
                    
                    # 获取数据类型
                    data_type = evidence_op.get('type', 'unknown')
                    
                    # 如果该类型不存在于phonedata中，则创建
                    if data_type not in self.phonedata:
                        self.phonedata[data_type] = []
                    
                    # 分配phone_id
                    if data_type not in self.phone_id_counters:
                        self.phone_id_counters[data_type] = 1
                    evidence_op['phone_id'] = str(self.phone_id_counters[data_type])
                    processed_evidence.append({"type": data_type, "id": evidence_op['phone_id']})
                    self.phone_id_counters[data_type] += 1
                    
                    # 将操作数据添加到手机数据中
                    self.phonedata[data_type].append(evidence_op)
                
                # 设置evidence为包含类型和id的dict列表
                question['evidence'] = processed_evidence
                final_questions.append(question)
            else:
                # 如果没有evidence字段，直接添加到最终问题列表
                final_questions.append(question)
        
        # 为基于画像的问题添加ask_time字段，固定为"2025-12"
        for question in final_questions:
            question["ask_time"] = "2025-12"
        
        return final_questions[:num_questions]
    
    def get_phone_operations_by_event_id_muti(self, event_id: str) -> List[Dict[str, Any]]:
        """
        根据事件ID获取相关手机操作 (多跳问题生成器专用)
        
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

    def _validate_and_regenerate_phone_operations_muti(self, question: Dict[str, Any], draft_data: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        验证并根据需要重生成手机操作数据
        
        Args:
            question: 问题字典，包含question、required_events等字段
            draft_data: draft事件数据列表
        
        Returns:
            Tuple[Dict[str, Any], List[Dict[str, Any]]]: 优化后的问题和对应的手机操作列表
        """
        updated_question = question["questions"].copy()
        all_phone_operations = []
        event_data_dict = {}
        phone_operations_dict = {}

        # 获取问题相关的事件ID
        event_ids = question["questions"].get("required_events_id", [])
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
                    # 从传入的draft_data中查找
                    for event in draft_data:
                        if event.get("id") == event_id or event.get("event_id") == event_id:
                            corresponding_event = event
                            break
                
                if corresponding_event:
                    # 根据事件ID获取相关手机操作
                    phone_operations = self.get_phone_operations_by_event_id_muti(event_id)
                    # 保存事件数据和手机操作数据
                    event_data_dict[event_id] = corresponding_event
                    phone_operations_dict[event_id] = phone_operations
                    # 收集所有手机操作
                    all_phone_operations.extend(phone_operations)
        
        # 检查是否有新增事件（instruction=3的情况）
        instruction = question.get('instruction', 1)
        if instruction == 3:
            new_events = question.get('new_events', [])
            if new_events and isinstance(new_events, list):
                print(f"发现新增事件，共{len(new_events)}个")
                for event in new_events:
                    if isinstance(event, dict):
                        # 为新增事件生成手机操作数据
                        event_id = event.get("event_id", event.get("id"))
                        if not event_id:
                            # 如果事件没有ID，生成一个临时ID
                            import uuid
                            event_id = f"new_{uuid.uuid4().hex[:8]}"
                            event["event_id"] = event_id
                        
                        # 构建重生成所需的judge_result
                        regen_judge_result = {
                            "missing_info": ["新增事件，需要生成完整的一个短信手机操作数据，表达的信息参考info字段"],
                            "synthesis_background": "这是一个新增事件，需要生成相关的手机操作数据。",
                            "regenerate_all": True
                        }
                        
                        # 生成手机操作数据
                        print(f"为新增事件{event_id}生成手机操作数据")
                        regenerated_operations = self.regenerate_phone_operations(event, regen_judge_result, "无question，考虑反映事件信息即可", phone_operations_dict.get(event_id, []))
                        
                        # 保存新增事件的手机操作数据 - 增加而不是替换
                        if event_id in phone_operations_dict:
                            phone_operations_dict[event_id].extend(regenerated_operations)
                        else:
                            phone_operations_dict[event_id] = regenerated_operations
                        event_data_dict[event_id] = event
                        all_phone_operations.extend(regenerated_operations)
                        
                        # 确保新增的手机操作数据被添加到self.phonedata中
                        for operation in regenerated_operations:
                            if isinstance(operation, dict):
                                data_type = operation.get("type")
                                if data_type:
                                    # 为操作数据分配phone_id（如果没有的话，线程安全）
                                    if "phone_id" not in operation:
                                        with self.phone_id_lock:
                                            if data_type not in self.phone_id_counters:
                                                self.phone_id_counters[data_type] = 1
                                            operation["phone_id"] = str(self.phone_id_counters[data_type])
                                            self.phone_id_counters[data_type] += 1
                                    
                                    # 将操作数据添加到self.phonedata中（线程安全）
                                    with self.phonedata_lock:
                                        if data_type not in self.phonedata:
                                            self.phonedata[data_type] = []
                                        self.phonedata[data_type].append(operation)
        
        # 如果有事件数据，统一调用LLM进行判断
        if event_data_dict:
            judge_result = self.judge_event_from_phone_operations(event_data_dict, phone_operations_dict, question["questions"])
            # 根据判断结果处理每个事件
            for event_judgment in judge_result.get("event_judgments", []):
                event_id = event_judgment.get("event_id")
                related = event_judgment.get("related", False)
                can_infer = event_judgment.get("can_infer", False)
                
                if related and not can_infer:
                    # 如果事件相关但手机操作数据无法推断出答案，重新生成手机操作数据
                    event_data = event_data_dict.get(event_id)
                    if event_data:
                        # 构建重生成所需的judge_result，使用当前事件的missing_info和synthesis_background
                        regen_judge_result = {
                            "missing_info": event_judgment.get("missing_info", []),
                            "synthesis_background": event_judgment.get("synthesis_background", ""),
                            "regenerate_all": True
                        }
                        regenerated_operations = self.regenerate_phone_operations(event_data, regen_judge_result, question["questions"], phone_operations_dict.get(event_id, []))
                        # 更新手机操作数据 - 增加而不是替换
                        if event_id in phone_operations_dict:
                            phone_operations_dict[event_id].extend(regenerated_operations)
                        else:
                            phone_operations_dict[event_id] = regenerated_operations
                        # 更新所有手机操作列表 - 直接添加新生成的操作而不是重新构建
                        all_phone_operations.extend(regenerated_operations)
        
        return updated_question, all_phone_operations

    def generate_multi_hop_questions_from_draft(self, month: str, num_questions: int) -> List[Dict[str, Any]]:
        """
        基于draft的生成（从draft数据中抽取一个月事件生成）
        
        Args:
            month: 月份，格式为"YYYY-MM"
            num_questions: 生成问题的数量
        
        Returns:
            基于draft的多跳问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")
        
        # 获取draft事件数据
        draft_data = self.get_draft_event_by_month(month)
        print(draft_data)
        questions_opt = []
        if draft_data:
            # 构建事件上下文
            event_context = {
                'name': name,
                'selected_events': draft_data
            }
            
            # 使用通用问题生成函数
            questions = self._generate_questions_with_template(
                data=draft_data,
                template=MULTI_HOP_QUESTION_TEMPLATE,
                num_questions=num_questions,
                event_info=json.dumps(event_context, ensure_ascii=False, indent=2),
                question_type="多跳推理"
            )

            print("开始溯源")

            # 并行对生成的每个问题进行事件溯源
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def trace_event(question):
                """并行处理事件溯源的辅助函数"""
                original_question = question.get("question", "")
                dates = question.get("required_event_dates", [])
                
                if dates:
                    # 使用新的_event_tracing方法进行事件溯源，直接传递整个问题对象
                    tracing_result = self._event_tracing(question)
                    
                    print(f"\n问题 '{original_question}' 的事件溯源结果：")
                    print(tracing_result)
                    
                    # 将溯源结果添加到问题中
                    question['event_tracing_result'] = tracing_result
                    return tracing_result
                return None
            
            # 创建线程池，最大线程数设为CPU核心数
            with ThreadPoolExecutor(max_workers=None) as executor:
                # 提交所有任务
                future_to_question = {executor.submit(trace_event, question): question for question in questions}
                
                # 收集结果
                for future in as_completed(future_to_question):
                    result = future.result()
                    if result:
                        questions_opt.append(result)

        # 并行处理生成的问题，验证是否能从手机操作中推理出来
        valid_questions = []
        question_phone_operations = []
        print("处理生成问题", len(questions_opt))
        
        def process_question(question):
            """并行处理问题验证和重生成的辅助函数"""
            print(question)
            # 检查事件溯源结果的instruction字段
            instruction = question.get('instruction', 1)
            
            # 根据instruction判断是否处理该问题
            if instruction == 2:
                # instruction为2，跳过该问题
                print(f"问题 '{question.get('question', '')}' 的instruction为2，放弃处理")
                return None, None
            elif instruction in [1, 3, 4]:
                # instruction为1、3、4，进行验证和重生成
                updated_question, phone_ops = self._validate_and_regenerate_phone_operations_muti(question, draft_data)
                return updated_question, phone_ops
            else:
                # 其他情况，默认处理
                updated_question, phone_ops = self._validate_and_regenerate_phone_operations_muti(question, draft_data)
                return updated_question, phone_ops
        
        # 创建线程池，最大线程数设为CPU核心数
        with ThreadPoolExecutor(max_workers=None) as executor:
            # 提交所有任务
            future_to_question = {executor.submit(process_question, question): question for question in questions_opt}
            
            # 收集结果
            for future in as_completed(future_to_question):
                updated_question, phone_ops = future.result()
                if updated_question and phone_ops:
                    valid_questions.append(updated_question)
                    question_phone_operations.append(phone_ops)
        
        # 确保问题和手机操作数量一致
        result_count = min(num_questions, len(valid_questions), len(question_phone_operations))
        
        # 将手机操作数据的类型和ID整合到每个问题的evidence字段中
        for i in range(result_count):
            # 从手机操作中提取类型和ID
            operation_evidence = []
            for operation in question_phone_operations[i]:
                if isinstance(operation, dict) and 'phone_id' in operation:
                    operation_type = operation.get('type', 'unknown')
                    operation_evidence.append({"type": operation_type, "id": operation['phone_id']})
            valid_questions[i]["evidence"] = operation_evidence
        
        # 为当前月的问题添加ask_time字段
        import random
        current_month = int(month.split('-')[1])  # 提取当前月份（如从"2023-01"提取01）
        for question in valid_questions:
            # 生成随机月份，大于等于当前月份
            random_month = random.randint(current_month, 12)
            # 格式化为"2025-xx"形式
            ask_time = f"2025-{str(random_month).zfill(2)}"
            question["ask_time"] = ask_time
        
        return valid_questions
    
    def generate_pattern_recognition_and_habit_analysis_questions(self, month: str, num_questions: int) -> List[Dict[str, Any]]:
        """
        基于draft的模式识别与习惯分析问题生成（从draft数据中抽取一个月事件生成）
        
        Args:
            month: 月份，格式为"YYYY-MM"
            num_questions: 生成问题的数量
        
        Returns:
            基于draft的模式识别与习惯分析问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")
        
        # 获取draft事件数据
        draft_data = self.get_draft_event_by_month(month)
        print(draft_data)
        questions_opt = []
        if draft_data:
            # 构建事件上下文
            event_context = {
                'name': name,
                'selected_events': draft_data
            }
            
            # 直接调用LLM生成问题，不使用_generate_questions_with_template方法
            # 将data转换为JSON字符串
            if isinstance(draft_data, (dict, list)):
                data_str = json.dumps(draft_data, ensure_ascii=False, indent=2)
            else:
                data_str = str(draft_data)
            
            # 格式化模板
            # 处理用户画像数据，只保留relation字段中的指定字段，同时保持社交圈分组结构
            processed_persona = self.persona_data.copy()
            
            # 检查是否有relation字段
            if 'relation' in processed_persona:
                processed_social_circles = []
                # relation是二维数组，外层是社交圈分组，内层是同一社交圈的人员
                for social_circle in processed_persona['relation']:
                    processed_relations = []
                    for person in social_circle:
                        # 只保留指定的字段
                        processed_person = {
                            'name': person.get('name', ''),
                            'relation': person.get('relation', ''),
                            'occupation': person.get('occupation', ''),
                            'organization': person.get('organization', ''),
                            'gender': person.get('gender', '')
                        }
                        processed_relations.append(processed_person)
                    processed_social_circles.append(processed_relations)
                # 更新relation字段，保持社交圈分组结构
                processed_persona['relation'] = processed_social_circles
            
            # 将处理后的用户画像数据转换为JSON字符串
            persona_str = json.dumps(processed_persona, ensure_ascii=False, indent=2)
            
            prompt = PATTERN_RECOGNITION_TEMPLATE.format(
                num_questions=num_questions,
                event_info=json.dumps(event_context, ensure_ascii=False, indent=2),
                persona_info=persona_str
            )
            
            # 调用LLM生成问题
            from utils.llm_call import llm_call_reason
            llm_result = llm_call_reason(prompt)
            print(llm_result)
            
            # 提取JSON内容
            start_idx = llm_result.index('{')
            end_idx = llm_result.rindex('}') + 1
            json_content = llm_result[start_idx:end_idx]
            
            # 解析JSON
            json_result = json.loads(json_content)
            
            # 统一处理返回格式：如果是包含"questions"字段的对象，则返回questions数组
            if isinstance(json_result, dict) and "questions" in json_result:
                questions = json_result["questions"]
            else:
                questions = json_result

            print("开始溯源")

            # 并行对生成的每个问题进行事件溯源
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def trace_event(question):
                """并行处理事件溯源的辅助函数"""
                original_question = question.get("question", "")
                dates = question.get("required_event_dates", [])
                
                if dates:
                    # 使用新的_event_tracing方法进行事件溯源，直接传递整个问题对象
                    tracing_result = self._event_tracing(question)
                    
                    print(f"\n问题 '{original_question}' 的事件溯源结果：")
                    print(tracing_result)
                    
                    # 将溯源结果添加到问题中
                    question['event_tracing_result'] = tracing_result
                    return tracing_result
                return None
            
            # 创建线程池，最大线程数设为CPU核心数
            with ThreadPoolExecutor(max_workers=None) as executor:
                # 提交所有任务
                future_to_question = {executor.submit(trace_event, question): question for question in questions}
                
                # 收集结果
                for future in as_completed(future_to_question):
                    result = future.result()
                    if result:
                        questions_opt.append(result)

        # 并行处理生成的问题，验证是否能从手机操作中推理出来
        valid_questions = []
        question_phone_operations = []
        print("处理生成问题", len(questions_opt))
        
        def process_question(question):
            """并行处理问题验证和重生成的辅助函数"""
            print(question)
            # 检查事件溯源结果的instruction字段
            instruction = question.get('instruction', 1)
            
            # 根据instruction判断是否处理该问题
            if instruction == 2:
                # instruction为2，跳过该问题
                print(f"问题 '{question.get('question', '')}' 的instruction为2，放弃处理")
                return None, None
            elif instruction in [1, 3, 4]:
                # instruction为1、3、4，进行验证和重生成
                updated_question, phone_ops = self._validate_and_regenerate_phone_operations_muti(question, draft_data)
                return updated_question, phone_ops
            else:
                # 其他情况，默认处理
                updated_question, phone_ops = self._validate_and_regenerate_phone_operations_muti(question, draft_data)
                return updated_question, phone_ops
        
        # 创建线程池，最大线程数设为CPU核心数
        with ThreadPoolExecutor(max_workers=None) as executor:
            # 提交所有任务
            future_to_question = {executor.submit(process_question, question): question for question in questions_opt}
            
            # 收集结果
            for future in as_completed(future_to_question):
                updated_question, phone_ops = future.result()
                if updated_question and phone_ops:
                    valid_questions.append(updated_question)
                    question_phone_operations.append(phone_ops)
        
        # 确保问题和手机操作数量一致
        result_count = min(5, len(valid_questions), len(question_phone_operations))
        
        # 将手机操作数据的类型和ID整合到每个问题的evidence字段中
        for i in range(result_count):
            # 从手机操作中提取类型和ID
            operation_evidence = []
            for operation in question_phone_operations[i]:
                if isinstance(operation, dict) and 'phone_id' in operation:
                    operation_type = operation.get('type', 'unknown')
                    operation_evidence.append({"type": operation_type, "id": operation['phone_id']})
            valid_questions[i]["evidence"] = operation_evidence
        
        # 为当前月的问题添加ask_time字段
        import random
        current_month = int(month.split('-')[1])  # 提取当前月份（如从"2023-01"提取01）
        for question in valid_questions:
            # 生成随机月份，大于等于当前月份
            random_month = random.randint(current_month, 12)
            # 格式化为"2025-xx"形式
            ask_time = f"2025-{str(random_month).zfill(2)}"
            question["ask_time"] = ask_time
        
        return valid_questions
    
    def _generate_multi_hop_questions_from_daily_event(self, num_questions: int) -> List[Dict[str, Any]]:
        """
        基于每日事件的生成（从每日事件数据中按日期获取事件生成）
        
        Args:
            num_questions: 生成问题的数量
        
        Returns:
            基于每日事件的多跳问题列表，每个问题包含question、answer、score_points和required_events字段
        """
        questions = []
        name = self.persona_data.get("basic_info", {}).get("name", "该用户")
        
        # 基于日期获取每日事件数据，默认获取7天
        daily_data = self._get_daily_event_data(count=7)
        
        if daily_data:
            # 构建事件上下文
            event_context = {
                'name': name,
                'selected_events': daily_data
            }
            
            # 使用通用问题生成函数
            questions = self._generate_questions_with_template(
                data=daily_data,
                template=MULTI_HOP_QUESTION_TEMPLATE,
                num_questions=num_questions,
                event_info=json.dumps(event_context, ensure_ascii=False, indent=2),
                question_type="多跳推理"
            )
        
        # 如果生成的问题不足，添加基础问题
        while len(questions) < num_questions:
            questions.append({
                "question": f"{name}在最近一段时间内的活动模式有什么特点？",
                "answer": "",
                "score_points": [{"description": "问题回答正确性", "score": 10}],
                "required_events": [""]
            })
        
        return questions[:num_questions]
    
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