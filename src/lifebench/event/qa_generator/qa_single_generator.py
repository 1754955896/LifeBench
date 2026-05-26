"""
QA Single Generator Class
基于标准化 Agentic 流程的单跳问答生成器
"""

import json
import os
import random
import threading
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta
import calendar
from src.lifebench.event.templates.template_qa import (
    EVENT_QUESTION_TEMPLATE,
    QUESTION_SCREENING_OPTIMIZATION_TEMPLATE,
    PHONE_OPERATIONS_REGENERATION_TEMPLATE1
)
from src.lifebench.utils.llm_call import llm_call, llm_call_reason, llm_call_j
from .phone_operation_generator import PhoneOperationGenerator
from .base_generator import BaseQAGenerator


class QASingleGenerator(BaseQAGenerator):
    """
    单跳 QA 生成器 - 基于 Agentic 协作流程
    
    流程：
    1. Select Agent: 确定提问月份，随机采样连续 3 天，决定基于什么生成问题
    2. Search Agent: 搜索 draft_event 中相关的事件数据
    3. Evaluation Agent: 优化问题质量
    4. Design Agent: 重新设计问题及对应的手机数据
    5. Output: 输出最终问题
    """
    
    def __init__(self, daily_event: List[Dict], event_tree: List[Dict],
                 draft_event: Dict[str, List], phonedata: Dict[str, List],
                 phone_data_dir: str = None, is_print: bool = True,
                 persona_data: Dict = None):
        """
        初始化单跳 QA 生成器

        Args:
            phone_data_dir: 手机数据文件夹路径
            is_print: 是否打印 Agent 的 LLM 输出，默认 True
        """
        # 调用父类的 __init__
        #print(phone_data_dir)
        super().__init__(phone_data_dir=phone_data_dir)
        self.daily_event = daily_event
        self.event_tree = event_tree
        self.draft_event = draft_event
        self.persona_data = persona_data or {}
        # 如果传入了 phone_data_dir，则使用父类加载的数据（不要覆盖）
        # 如果没有传入 phone_data_dir，才使用传入的 phonedata
        if not phone_data_dir:
            self.phonedata = phonedata
        # 初始化 QASingleGenerator 特有的属性
        self.phonedata_lock = threading.Lock()
        self.phone_id_lock = threading.Lock()
        self.is_print = is_print  # 打印控制标志

        # 初始化手机操作生成器
        self.phone_op_generator = PhoneOperationGenerator(persona_data=self.persona_data)
    
    def load_data_from_path(self, data_path: str):
        """从指定路径加载用户数据"""
        persona_path = os.path.join(data_path, "persona.json")
        if os.path.exists(persona_path):
            with open(persona_path, 'r', encoding='utf-8') as f:
                self.persona_data = json.load(f)
        
        event_tree_path = os.path.join(data_path, "event_tree.json")
        if os.path.exists(event_tree_path):
            with open(event_tree_path, 'r', encoding='utf-8') as f:
                self.event_tree = json.load(f)
        
        daily_event_path = os.path.join(data_path, "daily_event.json")
        if os.path.exists(daily_event_path):
            with open(daily_event_path, 'r', encoding='utf-8') as f:
                self.daily_event = json.load(f)
        
        draft_event_path = os.path.join(data_path, "daily_draft.json")
        if os.path.exists(draft_event_path):
            with open(draft_event_path, 'r', encoding='utf-8') as f:
                self.draft_event = json.load(f)
        
        special_event_path = os.path.join(data_path, "special_event.json")
        if os.path.exists(special_event_path):
            with open(special_event_path, 'r', encoding='utf-8') as f:
                self.special_event = json.load(f)
                self.unique_events = self.special_event.get('unique_events', [])
        
        phone_data_path = os.path.join(data_path, "phone_data")
        if os.path.exists(phone_data_path):
            self.load_phone_data_from_dir(phone_data_path)
            self.phone_data_dir = phone_data_path
    
    def load_phone_data_from_dir(self, phone_data_dir: str):
        """从目录加载手机数据"""
        if not os.path.exists(phone_data_dir):
            print(f"手机数据目录不存在：{phone_data_dir}")
            return
        
        self.phone_data_dir = phone_data_dir
        
        for filename in os.listdir(phone_data_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(phone_data_dir, filename)
                data_type = filename[:-5]
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data_list = json.load(f)
                    
                    if isinstance(data_list, list):
                        max_id = 0
                        for i, item in enumerate(data_list):
                            if isinstance(item, dict):
                                if 'phone_id' in item:
                                    try:
                                        current_id = int(item['phone_id'])
                                        if current_id > max_id:
                                            max_id = current_id
                                    except ValueError:
                                        item['phone_id'] = i + 1  # 使用 int 格式
                                        max_id = i + 1
                                else:
                                    item['phone_id'] = i + 1  # 使用 int 格式
                                    max_id = i + 1
                        
                        self.phone_id_counters[data_type] = max_id + 1
                    
                    self.phonedata[data_type] = data_list
                    print(f"成功加载手机数据：{filename}")
                except Exception as e:
                    print(f"加载手机数据文件失败 {filename}: {e}")
    
    # ========== Agentic 流程核心方法 ==========
    
    def select_agent(self, year: int, target_month: int) -> List[Dict[str, Any]]:
        """
        Select Agent: 从本月和之前月份随机抽样一天，往后扩展两天，基于事件设计问题

        Args:
            year: 年份
            target_month: 目标月份（问题提问的月份）

        Returns:
            包含采样日期和问题设计信息的列表
        """
        print(f"\n[Select Agent] 处理月份：{year}-{target_month:02d}")

        # Step 1: 获取 3 天的 daily event 数据
        date_strs = self._get_consecutive_dates(year, target_month)
        daily_events_in_range = self._filter_events_by_dates(date_strs)

        print(f"[Select Agent] 获取 {date_strs[0]} 到 {date_strs[-1]} 的 daily event 数据：")
        print(daily_events_in_range)

        # Step 2: 调用 LLM 选择目标事件并分析
        design_json = self._call_llm_for_target_event(daily_events_in_range, date_strs)

        # Step 3: 根据 LLM 返回查找或随机选择事件
        target_event_full, daily_events_on_target_date = self._find_or_sample_target_event(
            design_json, daily_events_in_range
        )

        # Step 4: 构造结果并返回
        sampling_results = [{
            'dates': date_strs,
            'target_event': target_event_full,
            'structure_analysis': design_json.get('structure_analysis', {}) if design_json else {},
            'daily_events_in_range': daily_events_on_target_date or daily_events_in_range
        }]

        # Step 5: 查找与目标事件极度相似的事件（可能引起混淆的事件）
        if target_event_full:
            print(f"\n[Select Agent] Step 5: 查找与目标事件极度相似的历史事件...")
            similar_confusing_events = self._find_similar_confusing_events(
                target_event_full, year, target_month
            )
            sampling_results[0]['similar_confusing_events'] = similar_confusing_events
            if similar_confusing_events:
                print(f"[Select Agent] 找到 {len(similar_confusing_events)} 个可能引起混淆的相似事件")
                # 注意：similar_confusing_events 仅用于内部逻辑，不输出到最终QA

        print(f"[Select Agent] 完成，选择了 {len(sampling_results)} 个时间段")
        return sampling_results

    def _get_consecutive_dates(self, year: int, target_month: int) -> List[str]:
        """收集从 1 月到目标月份的所有可用日期，随机选择连续 3 天"""
        all_available_dates = []
        for month in range(1, target_month + 1):
            if month == 12:
                last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = datetime(year, month + 1, 1) - timedelta(days=1)

            first_day = datetime(year, month, 1)
            month_dates = [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]
            all_available_dates.extend(month_dates)

        selected_start = random.choice(all_available_dates)
        consecutive_dates = [selected_start + timedelta(days=i) for i in range(3)]
        return [d.strftime("%Y-%m-%d") for d in consecutive_dates]

    def _filter_events_by_dates(self, date_strs: List[str]) -> List[Dict[str, Any]]:
        """根据日期范围筛选 daily_event 数据"""
        filtered_events = []
        for event in self.daily_event:
            if not isinstance(event, dict) or 'date' not in event:
                continue

            event_dates = event.get('date', [])
            if not isinstance(event_dates, list):
                continue

            for time_range in event_dates:
                event_date = self._extract_date_from_time_range(time_range)
                if event_date and event_date in date_strs:
                    filtered_events.append(event)
                    break

        return filtered_events

    def _extract_date_from_time_range(self, time_range: str) -> str:
        """从时间范围字符串中提取日期"""
        if '至' in time_range:
            return time_range.split('至')[0].strip()[:10]
        return time_range[:10]

    def _call_llm_for_target_event(self, daily_events_in_range: List[Dict], date_strs: List[str]) -> Dict:
        """调用 LLM 选择目标事件并分析"""
        prompt = self._build_selection_prompt(daily_events_in_range, date_strs)
        result = llm_call_j(prompt)

        if self.is_print:
            print("\n[Select Agent] LLM 输出:")
            print(result)

        try:
            start_idx = result.find('{')
            end_idx = result.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                return json.loads(result[start_idx:end_idx])
        except Exception as e:
            print(f"[Select Agent] LLM 返回解析失败：{e}")

        return None

    def _find_similar_confusing_events(self, target_event: Dict, year: int, target_month: int) -> List[Dict]:
        """
        查找与目标事件极度相似的事件（可能引起混淆的事件）
        使用两月窗口并行分析，避免上下文过长

        Args:
            target_event: 目标事件
            year: 年份
            target_month: 目标月份

        Returns:
            相似事件列表，每个包含 date 和 description
        """
        import concurrent.futures

        target_event_id = target_event.get('event_id', '')
        target_desc = target_event.get('description', '')
        target_name = target_event.get('name', target_event.get('event_name', ''))

        # 按两月窗口收集候选事件
        window_data = []
        for month in range(1, target_month + 1, 2):
            window_months = [month, month + 1] if month + 1 <= target_month else [month]
            window_events = []

            for m in window_months:
                month_key = f"{year}-{m:02d}"
                if month_key not in self.draft_event:
                    continue

                month_data = self.draft_event[month_key]
                if not isinstance(month_data, list):
                    continue

                for day_data in month_data:
                    date_str = day_data.get('date', '')
                    events_list = day_data.get('events', [])
                    if not isinstance(events_list, list):
                        continue

                    for evt in events_list:
                        evt_id = evt.get('event_id', [])
                        if isinstance(evt_id, list) and evt_id:
                            evt_id_str = evt_id[0]
                        else:
                            evt_id_str = str(evt_id) if evt_id else ''

                        # 排除目标事件本身
                        if evt_id_str == target_event_id:
                            continue

                        window_events.append({
                            'date': date_str,
                            'name': evt.get('name', ''),
                            'description': evt.get('description', '')
                        })

            if window_events:
                window_data.append({
                    'months': f"{window_months[0]}-{window_months[-1]}" if len(window_months) > 1 else str(window_months[0]),
                    'events': window_events
                })

        if not window_data:
            return []

        print(f"[_find_similar_confusing_events] 将按 {len(window_data)} 个两月窗口并行分析")

        # 并行分析每个窗口
        def analyze_window(window: Dict) -> List[Dict]:
            """分析单个窗口的相似事件"""
            window_months = window['months']
            window_events = window['events']

            if not window_events:
                return []

            prompt = f"""
作为相似度分析专家，请从以下候选事件中找出与目标事件极度相似的历史事件。只分析目标事件发生之前的日期的数据。

**极度相似的定义**：主要内容相似，但发生时间和一些细节不一样。
如果直接提问"今年XXX"，可能导致指代不明确、混淆。

【目标事件】
事件名称：{target_name}
事件描述：{target_desc}

【候选事件列表】（{window_months}月，共 {len(window_events)} 个）
{json.dumps(window_events, ensure_ascii=False, indent=2)}

**输出要求**
请以 JSON 格式返回极度相似的事件列表：
{{
    "similar_events": [
        {{
            "date": "YYYY-MM-DD",
            "description": "事件描述（全量内容）",
            "similarity_reason": "相似原因说明"
        }}
    ]
}}

注意：
1. 只返回与目标事件极度相似的历史事件
2. 如果没有找到相似事件，返回空的 similar_events 数组
3. 最多返回 3 个最相似的事件
4. 重点关注事件类型、人物关系、活动内容相似的条目
5. 输出时 description 字段请使用完整描述，不要截断
"""
            try:
                result = llm_call_j(prompt)
                if isinstance(result, str):
                    start_idx = result.find('{')
                    end_idx = result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        result = json.loads(result[start_idx:end_idx])

                if isinstance(result, dict):
                    return result.get('similar_events', [])
            except Exception as e:
                print(f"[_find_similar_confusing_events] 窗口 {window_months} 分析失败: {e}")

            return []

        # 使用线程池并行处理
        all_similar_events = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(analyze_window, w): w for w in window_data}
            for future in concurrent.futures.as_completed(futures):
                try:
                    window_result = future.result()
                    all_similar_events.extend(window_result)
                except Exception as e:
                    print(f"[_find_similar_confusing_events] 窗口处理异常: {e}")

        # 去重并按日期排序
        seen = set()
        unique_events = []
        for evt in all_similar_events:
            key = evt.get('date', '')
            if key not in seen:
                seen.add(key)
                unique_events.append(evt)

        unique_events.sort(key=lambda x: x.get('date', ''))
        print(f"[_find_similar_confusing_events] 共找到 {len(unique_events)} 个相似事件")

        return unique_events[:5]

    def _build_selection_prompt(self, daily_events: List[Dict], date_strs: List[str]) -> str:
        """构建选择目标事件的 prompt"""
        return f"""
作为 Select Agent，请仔细分析以下 daily event 数据，选择值得提问的目标事件并进行结构化分析。

日期范围：{date_strs[0]} 到 {date_strs[-1]}

该时间段内的 daily event 数据：
{json.dumps(daily_events, ensure_ascii=False, indent=2)}

请完成以下任务：

**1. 选择目标事件**
   - 选择具有重要价值或值得回忆的事件（如重要会议、特殊活动、关键决策等）
   - 优先选择包含复杂时间、地点、人物关系的事件
   - 优先选择涉及多个相关方或跨多个时间段的事件

**2. 结构化分析**（重点）
   对选定的目标事件进行详细分析：

   a) **主要人物**：
      - 事件中涉及哪些关键人物？
      - 他们的角色和关系是什么？

   b) **地点信息**：
      - 事件发生在哪里？
      - 是否有多个相关地点？

   c) **过程描述**：
      - 事件的完整过程是怎样的？
      - 有哪些关键节点或转折点？

   d) **相关操作**：
      - 可能产生哪些手机操作数据？（短信、通话、照片、日历、笔记、推送等）
      - 这些操作数据的特点是什么？

   e) **可提问点**：
      - 从时间角度可以问什么？（何时发生、持续时间、时间顺序等）
      - 从地点角度可以问什么？（发生地点、多个地点的顺序等）
      - 从人物角度可以问什么？（参与者、人物关系、互动对象等）
      - 从事件角度可以问什么？（事件内容、主题、结果、影响等）
      - 从原因角度可以问什么？（动机、目的、触发因素等）
      - 从方式角度可以问什么？（如何实现的、使用的方法等）

请以 JSON 格式返回：
{{
    "target_event": {{  // 选定的目标事件（必须从上述数据中选取，不要编造）
        "event_id": "事件 ID（必须使用上面数据中的 event_id 字段值，直接复制，不要修改或重新生成）",
        "event_name": "事件名称",
        "event_type": "事件类型",
        "date": "事件日期（从上面数据中复制）"
    }},
    "analysis_text": "对该事件的详细分析文本，包括主要人物、地点、过程、相关操作和可提问点等的连贯叙述"
}}

【重要提醒】
- event_id 必须从上面的 daily event 数据中直接提取
- 不要自行生成、修改或编造 event_id
- 如果数据中没有合适的 event_id，请从数据中选择最匹配的事件并使用其原始 event_id
"""

    def _find_or_sample_target_event(self, design_json: Dict, daily_events_in_range: List[Dict]) -> Tuple[Dict, List[Dict]]:
        """
        根据 LLM 返回查找目标事件，如果找不到则随机选择一个

        Returns:
            (target_event_full, daily_events_on_target_date)
        """
        # 如果 LLM 返回无效，随机选择
        if not design_json:
            return self._sample_random_event(daily_events_in_range, "LLM 返回为空")

        # 直接获取 event_id，不获取整个 target_event
        target_event = design_json.get('target_event')
        if target_event is None:
            target_event = {}
        event_id = design_json.get('event_id') or target_event.get('event_id', '')

        # 根据 event_id 查找完整事件
        target_event_full = self._find_event_by_id(event_id, daily_events_in_range)

        # 找不到则随机选择
        if not target_event_full:
            return self._sample_random_event(daily_events_in_range, f"未找到 event_id={event_id}")

        # 提取目标日期的事件列表
        daily_events_on_target_date = self._get_events_on_date(target_event_full, daily_events_in_range)

        return target_event_full, daily_events_on_target_date

    def _find_event_by_id(self, event_id: str, events: List[Dict]) -> Optional[Dict]:
        """根据 event_id 在事件列表中查找匹配的事件"""
        if not event_id:
            return None

        for event in events:
            if isinstance(event, dict) and str(event.get('event_id', '')) == str(event_id):
                return event

        return None

    def _sample_random_event(self, events: List[Dict], reason: str) -> Tuple[Dict, List[Dict]]:
        """随机选择一个事件"""
        if not events:
            print(f"[Select Agent] {reason}，但事件列表为空")
            return {}, []

        sampled = random.choice(events)
        print(f"[Select Agent] {reason}，随机选择：event_id={sampled.get('event_id')}")
        return sampled, events

    def _get_events_on_date(self, target_event: Dict, all_events: List[Dict]) -> List[Dict]:
        """获取与目标事件同一天的所有事件"""
        event_date = target_event.get('date', [])
        target_date_str = self._extract_target_date_str(event_date)

        if not target_date_str:
            return all_events

        print(f"[Select Agent] 获取 {target_date_str} 的 daily event 数据：")

        events_on_date = []
        for event in all_events:
            if not isinstance(event, dict) or 'date' not in event:
                continue

            event_dates = event.get('date', [])
            event_date_str_list = self._normalize_date_field(event_dates)

            for time_range in event_date_str_list:
                event_date_str = self._extract_date_from_time_range(time_range)
                if event_date_str == target_date_str:
                    events_on_date.append(event)
                    break

        print(f"[Select Agent] 目标事件日期：{target_date_str}")
        print(f"[Select Agent] 该日期的 daily_event 数量：{len(events_on_date)}")
        return events_on_date

    def _extract_target_date_str(self, event_date) -> str:
        """从目标事件的 date 字段提取日期字符串"""
        if isinstance(event_date, str):
            return self._extract_date_from_time_range(event_date)
        elif isinstance(event_date, list) and len(event_date) > 0:
            first_time_range = event_date[0]
            if isinstance(first_time_range, str):
                return self._extract_date_from_time_range(first_time_range)
        return ''

    def _normalize_date_field(self, date_field) -> List[str]:
        """规范化 date 字段为字符串列表"""
        if isinstance(date_field, str):
            return [date_field]
        elif isinstance(date_field, list):
            return date_field
        return []

    def evaluation_agent(self, question: Dict[str, Any], search_result: Dict[str, Any], daily_events_on_target_date: List[Dict[str, Any]] = None, current_month: str = None) -> Dict[str, Any]:
        """
        Evaluation Agent: 评估问题质量
        
        Args:
            question: 当前问题
            search_result: Search Agent 的搜索结果（不直接使用）
            daily_events_on_target_date: 目标事件三天的 daily_event 数据（来自 select_agent）
            current_month: 当前月份（格式：YYYY-MM），用于计算用户提问时间
            
        Returns:
            评估结果（包含是否合格和改进建议）
        """
        print("[Evaluation Agent] 评估问题质量")
        
        # 计算用户发起问题的时间（当前月份后一月的 1 号）
        ask_time_description = ''
        if current_month:
            try:
                month = int(current_month.split('-')[1])
                next_month = month + 1
                if next_month > 12:
                    next_month = 1
                ask_time_description = f"\n【用户提问时间】{next_month:02d}月 1 日（用户正在回顾过去的生活记录）"
            except:
                ask_time_description = ''
        
        # 调用 LLM 评估问题质量
        persona_name = self.persona_data.get('name', '于晓雯') if self.persona_data else '于晓雯'
        eval_prompt = f"""
        作为 Evaluation Agent，请全面评估以下问题QA的质量。下面的问题QA基于的场景是手机用户在提问一个记录了他一年手机数据的手机智能助手，回忆自己的生活。

        【背景信息】
        - 当前年份：2025年
        - 用户名字：{persona_name}
        - 问题中的"我"均指代{persona_name}

        {ask_time_description}

        【当前问题】
        {question.get('question', '')}
        
        【预期答案】
        {question.get('answer', '暂无答案')}
        
        【问题策略】
        {question.get('strategy_narrative', '')}
        
        【提问时间】
        {question.get('ask_time', '')}
        
        【已有证据（evidence）—— 回答问题的唯一依据】
        {json.dumps(question.get('evidence', []), ensure_ascii=False, indent=2)}
        注意：evidence 是手机数据（短信、通话、笔记、日历等），是回答问题的**唯一**依据。

        请从以下维度进行深入评估：

        ## 1. 题面合理性检查
        - **场景真实性**：问题描述的场景是否符合真实生活？
        - **逻辑连贯性**：问题表述是否逻辑清晰、无矛盾？
        - **信息合理性**：题目的信息是否足够定位回答问题，手机数据是否能推理出问题的答案？是否需要补充信息/去除冗余信息？题面的提供的信息符合一般人提问时会提供的信息吗（时间or地点or人物or描述）？
        - **信息适度性**：提供的信息量是否合理？是否充足，过多或过少，是否有冗余信息？
        - **检索困难性**：题面和证据之间的相似性是否过高，导致检索证据回答问题很容易。在保证问题可从 evidence 中回答的前提下，检减少题面和证据的相似度。（可以减少一些题面描述的细节信息内容，只保留可回答的最小信息即可。）
        - **信息精简**：对于题面中可以删除的不影响回答问题的细节信息，可以减少并优化题面。
        - **答案泄露检查**：题面是否包含了过多答案内容？如果题面中已经描述了答案的核心信息，用户无需检索 evidence 就能回答，则说明题面设计有问题，需要精简题面中与答案重复的描述。
   
        ## 2. 答案合理性正确性检查
        - **答案完整性**：答案是否完整回答了问题？
        - **答案正确性**：答案与 evidence 中的数据是否一致？是否存在矛盾？
        - **逻辑自洽**：答案内部逻辑是否自洽？有无自相矛盾之处？
        - **事实准确性**：答案中的事实（时间、地点、人物、事件）是否与 evidence 手机数据匹配？

        ## 3. 手机数据合理性检查（基于 evidence）
        - **数据充分性**：现有 evidence 手机数据是否足以支持问题和答案？
        - **数据一致性**：各条 evidence 手机数据之间是否一致？有无相互矛盾的地方？
        - **数据真实性**：手机数据是否符合真实使用场景？是否过于人工痕迹明显？
        - **证据链完整性**：关键证据是否齐全？是否需要补充其他类型的手机数据？

        ## 4. 问题可回答性检查（仅基于 evidence 手机数据）
        - **证据充分性**：基于现有 evidence 手机数据，能否准确回答问题？
        - **信息完整性**：evidence 中关键信息（时间、地点、人物、事件）是否齐全？
        - **答案唯一性**：是否存在多个可能的答案？是否有歧义？
        - **检索可行性**：能否通过 evidence 手机数据有效检索并推理出答案？
        - **推理链条**：是否需要多步推理？推理过程是否合理？
        - **ask_time**：用户提问时间是否合理？是否在所有引用事件的最晚日期之后？
        
        请以 JSON 格式返回评估结果：
        {{
            "is_qualified": true/false,  // 是否质量合格
            "analysis": "综合分析文本（包括题面、答案、手机数据、可回答性的详细分析）",
            "suggestions": "改进建议（如有问题，给出具体的修改方案；）"
        }}
        """
        
        eval_result = llm_call(eval_prompt)
        
        # 打印 Evaluation Agent 的输出
        if self.is_print:
            print("\n[Evaluation Agent] LLM 输出:")
            print(eval_result)
        
        try:
            start_idx = eval_result.find('{')
            end_idx = eval_result.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                eval_json = json.loads(eval_result[start_idx:end_idx])
                
                is_qualified = eval_json.get('is_qualified', False)
                analysis = eval_json.get('analysis', '')
                suggestions = eval_json.get('suggestions', '')
                
                print(f"[Evaluation Agent] 评估完成，合格：{is_qualified}")
                
                return {
                    'is_qualified': is_qualified,
                    'analysis': analysis,
                    'suggestions': suggestions
                }
        except Exception as e:
            print(f"[Evaluation Agent] 评估失败：{e}")
        
        # 默认不合格，需要改进
        return {
            'is_qualified': False,
            'analysis': '评估失败',
            'suggestions': '重新设计问题'
        }
    
    def _build_generate_prompt(self, question: Dict[str, Any], feedback: str) -> str:
        """
        构建生成模式的 prompt

        Args:
            question: 当前问题
            feedback: 检索总结

        Returns:
            生成模式的 prompt
        """
        # ask_time 要求：事件发生后两个月到当年12-31之间随机选取
        ask_time_description = '\n\n【用户提问时间】LLM 需根据 required_events_id 中所有事件的发生日期，选取最晚事件发生后两个月到 2025-12-31 之间的任意一天作为 ask_time（YYYY-MM-DD 格式）。例如若最晚事件在 3月15日，则 ask_time 可选 5月16日到 12月31日之间的任意一天。'

        return f"""
        你是 Design Agent（生成模式），需要模拟真实用户向手机智能体提问的场景。

        想象一下：用户正在回忆自己生活中的事件，于是向记录了自己生活数据的手机智能体提问。或是某事件的内容被用户遗忘，用户现在想回忆起来。或是有重要的细节用户需要回忆。{ask_time_description}
            
        【目标事件】
        {json.dumps(question.get('target_event', {}), ensure_ascii=False, indent=2)}
            
        【事件分析】
        {question.get('analysis_text', '')}
            
        【检索到的相关信息】
        {feedback}
            
        【已有的手机数据】
        {json.dumps(question.get('evidence', []), ensure_ascii=False, indent=2) if question.get('evidence') else '暂无'}

         **重要约束（可回答性）**
        - 设计的问题必须能从【已有的手机数据】中推断出答案
        - 如果【已有的手机数据】不足以回答问题，你需要在 phone_data_plan 中规划生成新的手机数据
        - 生成的手机数据必须包含能够回答问题的关键信息
        - 生成的证据数据将用于验证问题的可回答性
        - 请你合理设计问题和证据，使得问题具有一定的难度，题面不是完全和证据一样的描述，减少问题和证据的表面相似度，但又能通过合理推理从证据中得出答案
            
            
        **任务要求**

        0. **问题设计**
          - 注意，问题只得针对目标事件设计，答案的信息应在目标事件里，不要涉及对其他事件的提问。
          - **重要约束（ask_time 时间一致性）**：所有引用的必需事件（required_events_id）其发生日期必须在提问时间（ask_time）之前。如果设计的问题中引用的最晚事件发生在 ask_time 之后，LLM 应主动将 ask_time 调整到该事件所在月份之后（YYYY-MM 格式，最晚为 2025-12），以确保时间逻辑一致。
        
        1. **模拟真实用户的提问口吻**
           - 像普通人在日常生活中询问自己的手机助手
           - 使用第一人称“我”，语气自然、口语化。注意一般情况下用户和手机助手的对话不会很生动，也不会叙述过多冗余细节。
           - 问题要有一定的价值或意义
           - 思考假设用户可能遗忘了哪些事情或事件的哪些细节或者可能该事件本身完全不记得，那么用户应该怎么描述这个事件？
           - 符合回忆、反思、好奇等真实情感
            
        2. **表述技巧**
           - **时间模糊化策略**（重要）
             * **一般原则**：除非是明显一年/一生不会发生多次的事件（如生日、晋升、毕业、认识新朋友等），否则最好在叙述时有模糊的时间信息
             * **可以使用事件锚点代替时间的情况**：
               - ✅ 生日类：“我爸过生日那天”、“我生日那周”
               - ✅ 晋升类：“我晋升主管两天后”、“升职后的庆祝”
               - ✅ 毕业类：“毕业典礼那天”、“毕业旅行时”
               - ✅ 人生节点：“婚礼前一天”、“孩子出生那周”、“搬家前一周”
               - ✅ 特殊相识：“第一次见面的时候”、“认识新朋友的那天”
             * **需要模糊时间信息的情况**（适用于日常事件、重复性事件）
               - 相对时间：“3 周前”、“两周前”、“前几天”、“上周”
               - 月份描述：“2 月份”、“年初”、“那个月”、“这个月初”
               - 季节时段：“那年冬天”、“春天”、“夏天结束的时候”
               - 工作阶段：“刚换工作后”、“连续加班的那周”、“项目结束后”
               - 节日节气：“春节那会儿”、“国庆假期”、“情人节前后”
             * **尽量避免使用精确日期，除非事件难以通过其他信息表述**：
               - ❌ “2025-01-03 上午 9 点”
               - ✅ “年初有次很重要的会议”
               - ✅ “2 月份的一个周末”
           
           - 人物关系化：用关系角色替代具体姓名
             * 关系称谓：“那位前辈”、“新来的同事”、“经常一起吃饭的朋友”、“我导师”
             * 特征描述：“考过 CFA 的朋友”、“在上海读书的同学”、“比我早入职两年的同事”
             * 模糊指代：“一个关系还不错的同事”、“某个朋友”、“家里人”
           
           - 地点隐喻化：用特征或感受替代准确地名
             * 习惯场所：“老地方”、“公司楼下那家咖啡店”、“常去的健身房”
             * 特征描述：“可以看见江景的餐厅”、“地铁直达的商场”、“有个大落地窗的会议室”
             * 情感关联：“我们第一次见面的地方”、“经常聚餐的小馆子”
           
           - 事件特征化：用影响或感受替代事件名称
             * 重要性：“那场重要的考试”、“改变我职业轨迹的决定”、“让我很纠结的选择”
             * 情感印记：“特别紧张的一次面试”、“很开心的一次聚会”、“压力很大的项目”
             * 结果导向：“那次升职后的庆祝”、“搬家前的最后一次聚餐”
           
           - **实体替换策略**（关键）
             * 选择易遗忘的细节：用户可能记不清具体店名、人名、日期，但记得大致特征
             * 选择性模糊：不要把所有信息都模糊处理，这同样不真实。
             * 重要事件锚定：用用户记忆深刻的事件作为时间参考点，无需额外描述（如“婚礼前一天”、“孩子出生那周”）
             * 减少信息量：只保留核心识别信息，省略次要细节，模拟真实用户的简洁提问
             * 降低相似度：确保问题与手机数据有区别，可合理通过实体替换和增加手机数据没有的冗余描述来降低问题和手机数据的相似度。
            
        3. **避免机械式直白式问法**
           - ❌ “2025-01-03 上午 9 点我在哪里？”
           - ✅ “记得年初有次很重要的会议，我准备了好久，是在什么地方开的来着？”
               
           - ❌ “我和冯浩然讨论了 CFA 考试”
           - ✅ “之前跟一个考过 CFA 的朋友请教备考经验，我们聊了什么来着？”
            
        4. **同步规划手机数据**
           - 分析问题需要哪些手机数据来支持回答
           - 考虑问题怎么设计需要根据手机数据推理，且具有一定的难度。
           
        **手机数据规划原则**
           - **避免冗余**：如果现有手机数据已经足以回答问题，不要新增多余的数据。让主要信息反映在尽可能少的数据条目中。
           - **干扰数据例外**：只有为了增加检索难度的干扰/迷惑性数据才值得新增（这种数据不包含能回答问题的信息）
           - **删除不合理数据**：当发现手机数据与问题不匹配、相互矛盾或明显冗余时，应该删除
           - **精简优先**：保持手机数据的精简性和合理性，宁缺毋滥
           - **类别多样性**：优先考虑增加不同类型的手机数据（如短信、通话、照片、日历等），而不是在同一类型中增加大量数据
        **好的问题示例**
            
        ✅ "我晋升主管后第一次带团队去聚餐，当时选的地方是哪里？我记得有个同事还迟到了"
        （用职业重要事件作为锚点，只忘记地点细节）
            
        ✅ "我爸过生日我请假回去陪他，那两天我都安排了些什么活动来着？"
        （用家人生日作为时间锚点，不需要具体月份等信息（减少不必要信息），询问安排细节）
            
        ✅ "我和张浩然讨论 CFA 备考经验那次，他给我推荐了什么资料？就在我们常去的那家咖啡店聊的"
        （人物 + 事件明确，但需要检索具体对话内容）
            
        ✅ "我发烧去医院看急诊那天，医生开的什么药？记得花了不少钱"
        （用生病这种印象深刻的事件，询问具体医疗记录和费用）
            
        ✅ "换房前我去中介公司登记，那天留的联系人电话是多少来着？"
        （用人生重大事件作为参考点，询问具体数据细节）
            
        ✅ "国庆去苏州玩，回来高铁上收到一条工作短信，说的什么事？"
        （节日 + 旅行场景明确，但需要检索特定情境下的具体信息）
            
        请以 JSON 格式返回：
        {{
            "designed_question": {{
                "question": "生成的问题（真实用户的口吻，第一人称）",
                "answer": "预期答案",
                "score_points": [
                    {{
                        "description": "得分点描述",
                        "score": 分数
                    }}
                ],
                "required_events_id": ["相关事件 ID 列表"],
                "ask_time": "YYYY-MM-DD 格式的用户提问时间（必须在所有引用事件的最晚日期之后）"
            }},
            "phone_data_plan": {{
                "to_delete": [],  // 生成模式通常不需要删除
                "to_generate": [
                    {{
                        "type": "数据类型 (必须是 sms/phonecall/photo/push/note/calendar 之一)",
                        "content_summary": "数据内容概要（包含关键信息、时间、参与者等）",
                        "purpose": "生成此数据的目的（干扰/关键证据/辅助信息）"
                    }}
                ]
            }},
            "design_rationale": "整体设计理由"
        }}
        """
    
    def _build_revise_prompt(self, question: Dict[str, Any], feedback: str) -> str:
        """
        构建修改模式的 prompt
        
        Args:
            question: 当前问题
            feedback: 评估反馈
            
        Returns:
            修改模式的 prompt
        """
        return f"""
        作为 Design Agent（修改模式），请根据评估反馈对现有问题进行针对性润色和优化。
        
        **问题场景描述**
        想象一下：用户正在回忆自己生活中的事件，于是向记录了自己生活数据的手机智能体提问。或是某事件的内容被用户遗忘，用户现在想回忆起来。或是有重要的细节用户需要回忆
        【当前问题】
        {question.get('question', '')}
        
        【当前答案】
        {question.get('answer', '暂无答案')}
        
        【评估反馈】
        {feedback}
        
        【已有手机数据】
        {json.dumps(question.get('evidence', []), ensure_ascii=False, indent=2) if question.get('evidence') else '暂无'}
        
         **重要约束（可回答性）**
        - 设计的问题必须能从【已有的手机数据】中推断出答案
        - 如果【已有的手机数据】不足以回答问题，你需要在 phone_data_plan 中规划生成新的手机数据
        - 生成的手机数据必须包含能够回答问题的关键信息
        - 生成的证据数据将用于验证问题的可回答性
        - 请你合理设计问题和证据，使得问题具有一定的难度，题面不是完全和证据一样的描述，减少问题和证据的表面相似度，但又能通过合理推理从证据中得出答案
            
        
        **任务要求**
        1. **评估优先**：如果评估认为题面和答案已经合理，可以不做修改，只关注手机数据的优化
        2. **针对性润色题面**：根据反馈中提到的不足，优化问题表述，使其更自然、更符合真实用户的提问方式
        3. **优化答案**：如果答案不合理、不完整或与问题不匹配，可以重新组织答案表述
        4. **调整手机数据**：基于反馈和润色后的问题，全面评估手机数据的合理性，必要时进行增删改
        5. **注意：如果你觉得质量已经很好，或评估反馈认为问题质量合理，那么可以不做修改。**

        
        **优化方向**
        - 如果“难度偏低” → 增加模糊表述、间接描述、或生成干扰迷惑噪声的手机操作（要求明显不符合题目，不会影响答案）
        - 如果“过于生硬” → 增加生活化语气、口语化表达
        - 如果“证据不足” → 补充关键手机数据来支持答案
        - 如果“答案不合理” → 重新组织答案，使其更清晰、完整、符合逻辑
        - 如果“手机数据不合理” → 删除无关数据、修改不准确的数据、补充缺失的数据
        
        **手机数据调整策略**
        - 优先保留已有的关键证据数据，如果手机数据已经足以回答问题，则不要新增手机数据，避免冗余。
        - 如果润色后的问题需要新的证据支持，可以补充生成
        - 如果某些手机数据与润色后的问题不匹配，可以删除或修改
        - 确保手机数据与问题和答案保持一致性和逻辑连贯性
        - **类别多样性**：优先考虑增加不同类型的手机数据（如短信、通话、照片、日历等），而不是在同一类型中增加大量数据
        
        请以 JSON 格式返回：
        {{
            "designed_question": {{
                "question": "润色后的问题（第一人称视角，自然口语化）",
                "answer": "优化后的预期答案",
                "score_points": [
                    {{
                        "description": "得分点描述",
                        "score": 分数
                    }}
                ],
                "required_events_id": ["相关事件 ID 列表"]
            }},
            "phone_data_plan": {{
                "to_delete": [
                    {{
                        "type": "数据类型",
                        "phone_id": "要删除的数据 ID",
                        "reason": "删除原因（如：与润色后的问题不匹配/冗余/不准确）"
                    }}
                ],
                "to_generate": [
                    {{
                        "type": "数据类型 (必须是 sms/phonecall/photo/push/note/calendar 之一)",
                        "content_summary": "数据内容概要",
                        "purpose": "生成此数据的目的（干扰/关键证据/辅助信息）",
                        "reason": "为什么需要生成此数据（如：补充关键证据/支持新的答案表述）"
                    }}
                ]
            }},
            "revision_notes": "具体的修改说明，包括改了哪里、为什么这样改、手机数据如何调整的"
        }}
        """

    def _adjust_ask_time_if_needed(self, required_events_id: List[str], ask_time: str) -> str:
        """
        根据 required_events_id 对应的最晚事件日期，随机选取其之后某天作为提问时间，
        返回 YYYY-MM-DD 格式。

        流程：
        1. 找到 required_events_id 对应事件的最晚日期
        2. 从该最晚日期的下一天开始，随机选一个月
        3. 在该月内随机选一天
        4. 上限为 2025-12-31

        Args:
            required_events_id: 问题引用的必需事件 ID 列表
            ask_time: 当前提问时间（仅作保底，格式 YYYY-MM 或 YYYY-MM-DD）

        Returns:
            提问时间（格式 YYYY-MM-DD）
        """
        # 构建 event_id -> date 的映射
        event_id_to_date = {}
        for event in self.daily_event:
            if isinstance(event, dict):
                eid = str(event.get('event_id', ''))
                event_id_to_date[eid] = event.get('date', [])

        # 找到所有引用的最晚事件日期
        latest_dt = None
        for eid in required_events_id:
            dates = event_id_to_date.get(str(eid), [])
            for date_range in dates:
                if isinstance(date_range, str) and '至' in date_range:
                    start_part = date_range.split('至')[0].strip()
                    try:
                        dt = datetime.strptime(start_part, "%Y-%m-%d %H:%M:%S")
                        if latest_dt is None or dt > latest_dt:
                            latest_dt = dt
                    except ValueError:
                        pass

        # 从最晚日期的下一天开始
        if latest_dt is None:
            # 保底：使用 ask_time 解析为下一个月
            try:
                if ask_time.count('-') == 2:
                    base_dt = datetime.strptime(ask_time, "%Y-%m-%d")
                else:
                    base_dt = datetime.strptime(ask_time, "%Y-%m")
            except ValueError:
                base_dt = datetime(2025, 12, 1)
        else:
            base_dt = latest_dt + timedelta(days=1)

        max_dt = datetime(2025, 12, 31)
        if base_dt > max_dt:
            return "2025-12-31"

        # 计算可选月份范围（从 base_dt 月到 2025-12）
        months_range = (max_dt.year - base_dt.year) * 12 + (max_dt.month - base_dt.month)
        if months_range <= 0:
            return max_dt.strftime("%Y-%m-%d")

        # 随机选一个偏移月
        random_offset = random.randint(0, months_range)
        target_month_num = base_dt.month + random_offset
        target_year = base_dt.year + (target_month_num - 1) // 12
        target_month = (target_month_num - 1) % 12 + 1

        # 在该月内随机选一天
        _, last_day = calendar.monthrange(target_year, target_month)
        random_day = random.randint(1, last_day)

        return f"{target_year}-{target_month:02d}-{random_day:02d}"

    def design_agent(self, question: Dict[str, Any], feedback: str, mode: str = 'generate', current_month: str = None) -> Tuple[Dict[str, Any], bool]:
        """
        Design Agent: 基于反馈信息重新设计问题（包含规划和执行两个阶段）
            
        Args:
            question: 当前问题
            feedback: 综合反馈信息（包括检索总结和评估意见）
            mode: 模式类型，'generate'（生成模式）或'revise'（修改模式）
            current_month: 当前月份（格式：YYYY-MM），用于计算用户提问时间
                
        Returns:
            (新问题，是否需要继续迭代)
        """
        print(f"[Design Agent] 开始 {mode} 模式...")
            
        # ========== Stage 1: Plan Prompt ==========
        if mode == 'generate':
            plan_prompt = self._build_generate_prompt(question, feedback)
        else:  # mode == 'revise'
            plan_prompt = self._build_revise_prompt(question, feedback)
        if self.is_print:
            # print("[Design Agent] 规划提示：", plan_prompt)
            pass
        plan_result = llm_call(plan_prompt)
        
        # 打印 Design Agent Plan 阶段的输出
        if self.is_print:
            print("\n[Design Agent - Plan] LLM 输出:")
            print(plan_result)
        
        try:
            start_idx = plan_result.find('{')
            end_idx = plan_result.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                plan_json = json.loads(plan_result[start_idx:end_idx])
                
                print("[Design Agent] 规划完成，开始执行...")
                
                # ========== Stage 2: 解析并执行计划 ==========
                
                # 1. 解析问题部分
                designed_question = plan_json.get('designed_question', {})

                # 验证 required_events_id 是否与 target_event.event_id 一致
                target_event_id = str(question.get('target_event', {}).get('event_id', ''))
                validated_required_ids = []
                if target_event_id:
                    required_ids = designed_question.get('required_events_id', [])
                    for rid in required_ids:
                        if str(rid) == target_event_id:
                            validated_required_ids.append(rid)
                        else:
                            print(f"[Design Agent] 警告：required_events_id={rid} 与 target_event.event_id={target_event_id} 不一致，已替换")
                            validated_required_ids.append(target_event_id)
                else:
                    validated_required_ids = designed_question.get('required_events_id', [])

                new_question_obj = {
                    'question': designed_question.get('question', ''),
                    'answer': designed_question.get('answer', ''),
                    'score_points': designed_question.get('score_points', []),
                    'required_events_id': validated_required_ids,  # 使用验证后的 ID
                    'question_type': 'Single_hop',
                    'evidence': [],  # 将在生成数据后填充
                    'design_rationale': plan_json.get('design_rationale', ''),
                    'strategy_narrative': question.get('strategy_narrative', ''),
                    'target_event': question.get('target_event', {}),
                    'similar_confusing_events': question.get('similar_confusing_events', []),  # 携带相似事件信息
                    'ask_time': designed_question.get('ask_time', '')  # LLM 设计的提问时间
                }

                # Step 5: 如果是 generate 模式且有相似事件，检查并重写问题描述以避免混淆
                if mode == 'generate' and question.get('similar_confusing_events'):
                    print("\n[Design Agent - Step 5] 检查问题描述是否可能导致与相似事件混淆...")
                    new_question_obj = self._check_and_rewrite_question_for_similarity(
                        new_question_obj, question.get('similar_confusing_events', [])
                    )

                # 2. 解析手机数据规划
                phone_data_plan = plan_json.get('phone_data_plan', {})
                to_generate = phone_data_plan.get('to_generate', [])
                to_delete = phone_data_plan.get('to_delete', [])
                
                # 3. 执行删除操作
                if to_delete:
                    print(f"[Design Agent] 执行删除操作：{len(to_delete)} 条数据")
                    with self.phonedata_lock:
                        for item in to_delete:
                            op_type = item.get('type', 'unknown')
                            phone_id = item.get('phone_id', '')
                            
                            if op_type in self.phonedata:
                                original_len = len(self.phonedata[op_type])
                                self.phonedata[op_type] = [
                                    op for op in self.phonedata[op_type] 
                                    if str(op.get('phone_id', '')) != str(phone_id)
                                ]
                                
                                if len(self.phonedata[op_type]) < original_len:
                                    print(f"[Design Agent] 已删除 {op_type}:{phone_id}")
                
                # 4. 执行生成操作
                generated_operations = []
                if to_generate:
                    print(f"[Design Agent] 执行生成操作：{len(to_generate)} 条数据")
                    
                    # 定义允许的 operative types
                    ALLOWED_OP_TYPES = {'sms', 'phonecall', 'photo', 'push', 'note', 'calendar'}
                    
                    for item in to_generate:
                        op_type = item.get('type', 'sms')
                        
                        # 验证类型是否在允许列表中
                        if op_type not in ALLOWED_OP_TYPES:
                            print(f"[Design Agent] 警告：'{op_type}' 不是允许的操作类型，跳过。允许的类型：{ALLOWED_OP_TYPES}")
                            continue
                        
                        content_summary = item.get('content_summary', '')
                        
                        # 使用 content_summary 作为 generation_hint，并告知允许的类型
                        generation_hint = f"""
                        请生成{op_type}类型的数据，要求：{content_summary}
                        
                        注意：可生成的数据类型仅限于以下 6 种：sms, phonecall, photo, push, note, calendar
                        当前请求的类型 '{op_type}' 已经在允许列表中。
                        """
                        
                        # 创建临时事件用于生成
                        temp_event = {
                            'question': new_question_obj.get('question', ''),
                            'target_event': new_question_obj.get('target_event', {})
                        }
                        
                        # 使用 PhoneOperationGenerator 生成
                        operations = self.phone_op_generator.generate(
                            operation_type=op_type,
                            original_event=temp_event.get('target_event', {}),
                            question=new_question_obj.get('question', ''),
                            generation_hint=generation_hint
                        )
                        
                        if operations:
                            generated_operations.extend(operations)
                    
                    # 添加到 phonedata
                    if generated_operations:
                        self._add_operations_to_phonedata(generated_operations)
                
                # 5. 构建 updated_evidence（基于 new_question_obj 的 evidence，删除旧的，添加新的）
                # 注意：直接使用 target_event.event_id 来收集证据，避免 required_events_id 被伪造的问题
                updated_evidence = []
                target_event = new_question_obj.get('target_event', {})
                target_event_id = str(target_event.get('event_id', ''))

                # 直接使用 target_event_id 收集证据
                if target_event_id and self.phonedata:
                    for _, data_list in self.phonedata.items():
                        if isinstance(data_list, list):
                            for item in data_list:
                                if isinstance(item, dict):
                                    # 检查 daily_event_id 或 related_event 字段
                                    item_event_id = str(item.get('daily_event_id', ''))
                                    related_event = str(item.get('related_event', ''))

                                    # 如果匹配，添加到 updated_evidence
                                    if item_event_id == target_event_id or related_event == target_event_id:
                                        updated_evidence.append(item)

                new_question_obj['evidence'] = updated_evidence
                
                print("[Design Agent] 问题重新设计完成，已生成/删除手机操作数据")
                
                # 判断是否需要继续迭代
                should_continue = '需要改进' in feedback or '不足' in feedback
                return new_question_obj, should_continue
                
        except Exception as e:
            print(f"[Design Agent] 设计失败：{e}")
        
        # 失败情况下返回原问题，不继续迭代
        return question, False

    def _check_and_rewrite_question_for_similarity(self, question_obj: Dict, similar_events: List[Dict]) -> Dict:
        """
        检查问题描述是否可能导致与相似事件混淆，如果是则重写

        Args:
            question_obj: 问题对象
            similar_events: 相似事件列表

        Returns:
            可能有重写后的问题对象
        """
        if not similar_events:
            return question_obj

        target_event = question_obj.get('target_event', {})
        target_desc = target_event.get('description', '')[:200]

        prompt = f"""
作为问题质量审核专家，请先分析以下问题描述和相似事件，再决定是否需要重写。

【目标事件】
事件名称：{target_event.get('name', '')}
事件日期：{target_event.get('date', '')}
事件描述：{target_desc}

【生成的问题】
问题：{question_obj.get('question', '')}
答案：{question_obj.get('answer', '')}
用户提问时间（ask_time）：{question_obj.get('ask_time', '')}

【相似历史事件】（可能导致混淆）
{json.dumps(similar_events, ensure_ascii=False, indent=2)}

**分析步骤**

**第一步：验证相似事件是否真的相似**
- 逐个分析每个"相似事件"，判断它与目标事件是否真的内容相似
- 如果两个事件只是时间接近但内容截然不同，它们其实不相似，不需要通过时间约束区分
- 例如："3月5日跑步"和"3月6日购物"时间接近但内容不同，不混淆

**第二步：检验题面是否会同时回答多个事件**
- 用当前问题去问"相似事件"的内容，看答案是否也对
- 如果对目标事件的回答同时也适用于相似事件，说明题面设计有问题，需要重写
- 如果回答只针对目标事件而不能回答相似事件，说明题面设计合理

**判断标准**
- 如果相似事件内容不同、或题面能明确区分目标事件 → 不需要重写
- 如果相似事件内容高度重叠、且题面会让用户混淆 → 需要重写（加强时间约束）

**重写原则**
- 如果可能混淆：加强时间约束到更小范围（"春夏之际" → "具体月份"，或"今年" → "具体月份"）
- 如果不会混淆：可以选择性放宽时间约束（"具体月份" → "春夏之际"、"X月后"）
- 重写时保持问题的自然口语化，不改变核心问题意图

**重要约束：ask_time 一致性**
- ask_time 是用户提问时间（{question_obj.get('ask_time', '')}），必须在所有引用事件的最晚日期之后
- 问题中的相对时间描述应该与 ask_time 保持逻辑一致

**时间约束宽松度优先级（从宽到严）**
当题面不会与相似事件发生混淆冲突时，优先选择最宽松的约束：
1. "今年"、"今年上半年"
2. "春季"、"年初"、"新年伊始"
3. "1月之后"、"春季前后"
4. "3月份"、"第二季度"
5. "3月上旬"、"3月第2周"、"月中左右"
6. "3月4号"、"3月5日"等精确日期

**输出格式**
请以 JSON 格式返回：
{{
    "similarity_analysis": "分析每个相似事件是否真的与目标事件内容相似",
    "question_confusion_check": "检验题面是否会让用户同时回答了相似事件",
    "needs_rewrite": true/false,
    "rewritten_question": "重写后的问题（如果需要）",
    "rewritten_answer": "重写后的答案（如果需要）",
    "rewrite_reason": "重写原因说明"
}}
"""
        try:
            print("\n[Step 5] 检查问题描述与相似事件的区分度...",prompt)
            result = llm_call(prompt)
            if isinstance(result, str):
                start_idx = result.find('{')
                end_idx = result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    result = json.loads(result[start_idx:end_idx])

            if isinstance(result, dict) and result.get('needs_rewrite', False):
                new_q = result.get('rewritten_question', '')
                new_a = result.get('rewritten_answer', '')
                if new_q:
                    print(f"\n[Step 5] 问题描述已重写:")
                    print(f"  原问题: {question_obj.get('question', '')[:80]}...")
                    print(f"  新问题: {new_q[:80]}...")
                    question_obj['question'] = new_q
                    question_obj['answer'] = new_a
                    question_obj['rewritten_for_similarity'] = True

        except Exception as e:
            print(f"[_check_and_rewrite_question_for_similarity] 分析失败: {e}")

        return question_obj

    def _delete_phone_operations(self, to_delete: List[Dict[str, Any]]) -> bool:
        """
        删除指定的手机操作数据
        
        Args:
            to_delete: 需要删除的数据列表
            
        Returns:
            是否成功删除
        """
        success_count = 0
        
        with self.phonedata_lock:
            for item in to_delete:
                op_type = item.get('type', 'unknown')
                phone_id = item.get('phone_id', '')
                reason = item.get('reason', '未指定原因')
                
                if op_type in self.phonedata:
                    # 查找并删除
                    original_len = len(self.phonedata[op_type])
                    self.phonedata[op_type] = [
                        op for op in self.phonedata[op_type] 
                        if str(op.get('phone_id', '')) != str(phone_id)
                    ]
                    
                    if len(self.phonedata[op_type]) < original_len:
                        print(f"[Design Agent] 已删除 {op_type} 类型的数据，phone_id={phone_id}, 原因：{reason}")
                        success_count += 1
                    else:
                        print(f"[Design Agent] 未找到要删除的数据：{op_type}:{phone_id}")
        
        print(f"[Design Agent] 删除操作完成，成功删除 {success_count}/{len(to_delete)} 条数据")
        return success_count > 0
    
    def _add_operations_to_phonedata(self, operations: List[Dict[str, Any]]):
        """
        将手机操作数据添加到 phonedata
        
        Args:
            operations: 手机操作数据列表
        """
        with self.phonedata_lock:
            for op in operations:
                op_type = op.get('type', 'unknown')
                
                if op_type not in self.phonedata:
                    self.phonedata[op_type] = []
                
                # 分配 phone_id
                if op_type not in self.phone_id_counters:
                    self.phone_id_counters[op_type] = 1
                
                if 'phone_id' not in op:
                    op['phone_id'] = self.phone_id_counters[op_type]  # 使用 int 格式
                
                self.phone_id_counters[op_type] += 1
                
                self.phonedata[op_type].append(op)
        
        print(f"[Design Agent] 已将 {len(operations)} 条操作数据添加到 phonedata")
    
    def _get_related_phone_data(self, target_event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        获取与目标事件相关的所有手机数据
        
        Args:
            target_event: 目标事件信息
            
        Returns:
            相关的手机数据列表
        """
        related_phone_data = []
        event_id = target_event.get('event_id', '')
        
        if self.phonedata:
            for _, data_list in self.phonedata.items():
                if isinstance(data_list, list):
                    for item in data_list:
                        if isinstance(item, dict):
                            # 检查 daily_event_id 或 related_event 字段
                            item_event_id = str(item.get('daily_event_id', ''))
                            related_event = str(item.get('related_event', ''))
                            
                            # 如果匹配，添加完整的操作数据
                            if event_id and (item_event_id == str(event_id) or related_event == str(event_id)):
                                related_phone_data.append(item)
        
        return related_phone_data
    
    def generate_monthly_qa(self, year: int, month: int) -> List[Dict[str, Any]]:
        """
        生成单个月份的问答对（Agentic 流程）
        
        Args:
            year: 年份
            month: 月份
            
        Returns:
            问答列表
        """
        print(f"\n========== 生成 {year}-{month:02d} 的问答 ==========")
        
        # Step 1: Select Agent
        select_results = self.select_agent(year, month)
        
        monthly_qa = []
        
        for select_result in select_results:
            target_event = select_result.get('target_event', {})
            question_draft = select_result.get('question_draft', '')
            daily_events_on_target_date = select_result.get('daily_events_in_range', [])  # 直接使用 select_agent 返回的数据
            similar_confusing_events = select_result.get('similar_confusing_events', [])  # 提取相似事件

            # Step 2: Search Agent (已禁用，始终返回空字典)
            search_result = {}

            # 生成初始问题（只生成一个）
            initial_question = {
                'question': question_draft,  # 使用 Select Agent 生成的问题草稿
                'answer': '',
                'score_points': [],
                'target_event': target_event,
                'strategy_narrative': select_result.get('strategy_narrative', ''),
                'similar_confusing_events': similar_confusing_events  # 携带相似事件信息
            }
            
            # ========== 在 Step 3 之前，先格式化问题为标准结构 ==========
            event_id = target_event.get('event_id', '')
            
            # 获取与 event_id 相关的 phone_data 作为 evidence
            related_phone_data = []
            if event_id and self.phonedata:
                # 遍历所有类型的 phone_data
                for _, data_list in self.phonedata.items():
                    if isinstance(data_list, list):
                        for item in data_list:
                            if isinstance(item, dict):
                                # 检查 event_id 或 related_event 字段
                                item_event_id = str(item.get('daily_event_id', ''))
                                related_event = str(item.get('related_event', ''))
                                
                                # 如果匹配，添加完整的操作数据到 evidence
                                if item_event_id == str(event_id) or related_event == str(event_id):
                                    related_phone_data.append(item)
            
            # 构建标准格式的问题对象
            formatted_question = {
                'question': initial_question.get('question', ''),
                'answer': initial_question.get('answer', ''),
                'score_points': initial_question.get('score_points', []),
                'required_events_id': [event_id] if event_id else [],
                'evidence': related_phone_data,
                'strategy_narrative': initial_question.get('strategy_narrative', ''),
                'target_event': target_event,
                'similar_confusing_events': initial_question.get('similar_confusing_events', [])
            }
            
            # Step 3: Design Agent 生成初始问题（使用生成模式）
            print("\n[Initial Design] 基于搜索结果生成初始问题...")
            
            initial_feedback = f"""
            【检索总结】
            {json.dumps(search_result, ensure_ascii=False, indent=2)}
            
            【目标事件当日的 daily_event】
            {json.dumps(daily_events_on_target_date, ensure_ascii=False, indent=2) if daily_events_on_target_date else '暂无'}
            
            请基于以上检索到的信息和当日事件数据，设计一个高质量的单跳检索问题。
            """
            
            # 计算当前月份（用于用户提问时间）
            current_month_str = f"{year}-{month:02d}"
            current_question, _ = self.design_agent(formatted_question, initial_feedback, mode='generate', current_month=current_month_str)
            
            # 如果设计失败，使用格式化后的问题
            if not current_question:
                print("[Initial Design] 设计失败，使用格式化后的问题")
                current_question = formatted_question
            
            # Step 4: Evaluation & Design 循环迭代优化
            max_iterations = 3  # 最大迭代次数
            iteration_count = 0
            
            while iteration_count < max_iterations:
                print(f"\n[Iteration {iteration_count + 1}/{max_iterations}]")

                # 保留上一次生成的 ask_time
                ask_time = current_question.get('ask_time')

                # Evaluation Agent（传入最新的 current_question）
                eval_result = self.evaluation_agent(current_question, search_result, daily_events_on_target_date, current_month=current_month_str)
                
                # 构建反馈信息
                feedback = f"""
                【评估结果】
                - 质量合格：{eval_result.get('is_qualified', False)}
                - 分析：{eval_result.get('analysis', '')}
                - 建议：{eval_result.get('suggestions', '')}
                
                【目标事件当日的 daily_event】
                {json.dumps(daily_events_on_target_date, ensure_ascii=False, indent=2) if daily_events_on_target_date else '暂无'}
            
                """
                
                # Design Agent（使用修改模式）
                designed_question, should_continue = self.design_agent(current_question, feedback, mode='revise')
                
                # 如果设计失败，使用当前问题
                if not designed_question:
                    print("[Design Agent] 设计失败，使用当前问题")
                    break
                
                # 更新当前问题
                current_question = designed_question
                if not current_question.get('ask_time') and ask_time:
                    current_question['ask_time'] = ask_time
                
                # 如果不需要继续迭代或已合格，退出循环
                if not should_continue or eval_result.get('is_qualified', False):
                    print(f"[Iteration] 迭代完成，最终评分：{eval_result.get('score', 0)}/10")
                    break
                
                iteration_count += 1
            
            final_question = current_question

            # 添加 ask_time（如果 LLM 没有设计，则使用 _adjust_ask_time_if_needed 生成）
            if not final_question.get('ask_time'):
                final_question['ask_time'] = self._adjust_ask_time_if_needed(
                    final_question.get('required_events_id', []),
                    f"{year}-{month:02d}"
                )
            final_question['question_type'] = 'Single_hop'
            
            # 删除内部使用字段
            final_question.pop('design_rationale', None)
            final_question.pop('strategy_narrative', None)
            final_question.pop('target_event', None)
            
            monthly_qa.append(final_question)
        
        print(f"========== {year}-{month:02d} 完成，生成 {len(monthly_qa)} 个问题 ==========")
        return monthly_qa
    
    def QAGen(self, year: int = 2025, output_path: str = None) -> List[Dict[str, Any]]:
        """
        生成单跳 QA 对的主入口函数
        
        Args:
            year: 年份，默认 2025
            output_path: 输出文件路径
            
        Returns:
            生成的 QA 对列表
        """
        print(f"\n开始生成 {year} 年的单跳问答对...")
        
        # 确保 year 是整数类型
        year = int(year)
        
        all_qa = []
        
        # 使用 ThreadPoolExecutor 并行 20 线程生成
        import concurrent.futures
        
        def generate_single_question(month: int):
            """为指定月份生成单个问题"""
            try:
                monthly_qa = self.generate_monthly_qa(year, month)
                return monthly_qa
            except Exception as e:
                print(f"[QAGen] {month}月生成问题失败：{e}")
                return []
        
        # 准备所有任务：1 月到 12 月，问题数从 2 到 24
        tasks = []
        for month in range(1, 13):
            num_questions_for_month = 7  # 1 月=2 个，2 月=4 个，...，12 月=24 个
            for _ in range(num_questions_for_month):
                tasks.append(month)
        
        print(f"\n[QAGen] 准备生成 {len(tasks)} 个问题（1 月 2 个，2 月 4 个，...，12 月 24 个）")
        print(f"[QAGen] 使用 20 线程并行生成...")
        
        # 使用 ThreadPoolExecutor 并行处理，最多 20 个线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(generate_single_question, month) for month in tasks]
            
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    monthly_qa = future.result()
                    if monthly_qa:
                        all_qa.extend(monthly_qa)
                    completed += 1
                    if completed % 10 == 0 or completed == len(futures):
                        print(f"[QAGen] 已完成 {completed}/{len(futures)} 个问题")
                except Exception as e:
                    print(f"[QAGen] 问题生成异常：{e}")
        
        # 去除 similar_confusing_events 字段（在过滤和优化之前）
        for qa in all_qa:
            qa.pop('similar_confusing_events', None)

        # 过滤和优化生成的问题
        print("\n[QAGen] 开始过滤和优化生成的问题...")
        filtered_qa = self._filter_and_refine_questions(all_qa)

        # 保存到文件 - 已移除，统一由调用方处理
        # if output_path is None:
        #     parent_dir = os.path.dirname(self.phone_data_dir)
        #     output_path = os.path.join(parent_dir, "single_hop_qa.json")
        #
        # with open(output_path, "w", encoding="utf-8") as f:
        #     json.dump(filtered_qa, f, ensure_ascii=False, indent=2)
        #
        # print(f"\n问答对已成功写入文件：{output_path}")
        print(f"\n共生成 {len(filtered_qa)} 个问答对（过滤前：{len(all_qa)}）\n")

        return filtered_qa
    
    def _filter_and_refine_questions(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        使用 20 线程并行过滤和优化问题
        
        工作流程：
        1. 检查问题和答案是否可以根据 evidence 推断回答
        2. 如果可以，则通过
        3. 否则重新设计问题和答案
        4. 若难以设计则抛弃
        
        Args:
            questions: 待过滤的问题列表
            
        Returns:
            过滤和优化后的问题列表
        """
        import concurrent.futures
        
        print(f"\n{'='*80}")
        print(f"[Filter & Refine] 开始并行过滤和优化 {len(questions)} 个问题...")
        print(f"{'='*80}")
        
        # 用于存储结果的字典（保持顺序）
        results_dict = {}
        
        def process_single_question(idx: int, question: Dict[str, Any]) -> Tuple[int, Dict[str, Any], bool]:
            """
            处理单个问题的过滤和优化
            
            Args:
                idx: 问题索引
                question: 问题对象
                
            Returns:
                (索引, 优化后的问题或 None, 是否保留)
            """
            try:
                print(f"\n[Filter Thread {idx + 1}/{len(questions)}] 开始处理问题...")
                
                # 构建评估 prompt
                persona_name = self.persona_data.get('name', '于晓雯') if self.persona_data else '于晓雯'
                eval_prompt = f"""
                作为 QA 质量评估专家，请仔细分析以下问答对的质量。

                【背景信息】
                - 当前年份：2025年
                - 用户名字：{persona_name}
                - 问题中的"我"均指代{persona_name}

                【问题】
                {question.get('question', '')}

                【答案】
                {question.get('answer', '')}
                
                【证据数据】
                {json.dumps(question.get('evidence', []), ensure_ascii=False, indent=2)}
                
                **评估任务**
                
                1. **可回答性检查（核心）**
                   - 基于现有 evidence，能否准确回答问题？
                   - 关键信息（时间、地点、人物、事件）是否齐全？
                   - 答案是否能完全从 evidence 中推理出来？
                   - 是否存在幻觉或编造的信息？
                
                2. **题面合理性检查**
                   - 问题表述是否逻辑清晰、无矛盾？
                   - 问题是否可以已经 evidence 回答？
                
                3. **答案合理性检查**
                   - 答案是否完整回答了问题？
                   - 答案内部逻辑是否自洽？
                   - 答案中的事实是否与 evidence 中的数据严格匹配？
                
                **决策规则**
                
                ### 情况 A：问题和答案可以根据 evidence 推断回答
                - **判断标准**：
                  * evidence 充足，能支撑答案
                  * 答案准确、无幻觉
                  * 问题表述合理
                - **处理方式**：**通过**
                
                ### 情况 B：无法根据 evidence 推断回答，但可以重新设计
                - **判断标准**：
                  * evidence 与问题不匹配，或答案有幻觉
                  * 但 evidence 中有足够的信息可以设计一个合理的新问题
                - **处理方式**：**重新设计问题和答案**
                - **设计要求**：
                  * 新问题必须能从 evidence 中推理出来
                  * 新答案必须严格基于 evidence
                  * 增加难度：需要综合分析多个证据点
                
                ### 情况 C：难以设计出合理问题
                - **判断标准**：
                  * evidence 不足或与问题完全不相关
                  * 无法从 evidence 中设计出有意义的问答对
                - **处理方式**：**抛弃该问题**
                
                **输出格式**
                请以 JSON 格式返回评估结果：
                {{
                    "decision": "pass/redesign/discard",
                    "analysis": "详细分析（包括可回答性、题面合理性、答案合理性）",
                    "modified_question": null,
                    "modified_answer": null,
                    "reason": "决策理由"
                }}
                
                **字段说明**：
                - `decision`: 决策类型
                  * `pass`: 问题和答案合理，可以通过
                  * `redesign`: 需要重新设计问题和答案
                  * `discard`: 难以设计，直接抛弃
                - `modified_question`: 在 `redesign` 时必须填写新问题
                - `modified_answer`: 在 `redesign` 时必须填写新答案
                """
                
                # 调用 LLM 进行评估
                llm_result = llm_call_j(eval_prompt)
                print(f"[Filter Thread {idx + 1}] LLM 评估结果: {llm_result}")
                if self.is_print:
                    print(f"[Filter Thread {idx + 1}] LLM 评估输出:")
                    print(str(llm_result)[:300] + "..." if len(str(llm_result)) > 300 else str(llm_result))
                
                # 解析 LLM 结果
                if isinstance(llm_result, str):
                    start_idx = llm_result.find('{')
                    end_idx = llm_result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        llm_result = json.loads(llm_result[start_idx:end_idx])
                
                if not isinstance(llm_result, dict):
                    print(f"[Filter Thread {idx + 1}] LLM 返回格式错误，保留原问题")
                    return idx, question, True
                
                decision = llm_result.get('decision', 'pass')
                analysis = llm_result.get('analysis', '')
                reason = llm_result.get('reason', '')
                
                print(f"[Filter Thread {idx + 1}] 决策：{decision}")
                print(f"  理由：{reason[:100]}..." if len(reason) > 100 else f"  理由：{reason}")
                
                # 根据决策执行相应操作
                if decision == 'pass':
                    # 情况 A：通过
                    print(f"[Filter Thread {idx + 1}] ✓ 问题质量良好，通过")
                    return idx, question, True
                
                elif decision == 'redesign':
                    # 情况 B：重新设计
                    modified_question = llm_result.get('modified_question', '')
                    modified_answer = llm_result.get('modified_answer', '')
                    
                    if modified_question and modified_answer:
                        # 验证新问题是否真的可以从 evidence 中推理出来
                        verification_prompt = f"""
                        请验证以下新问题是否可以从提供的 evidence 中推理出来。
                        
                        【新问题】
                        {modified_question}
                        
                        【新答案】
                        {modified_answer}
                        
                        【证据数据】
                        {json.dumps(question.get('evidence', []), ensure_ascii=False, indent=2)}
                        
                        **验证要求**
                        1. 新问题是否能从 evidence 中推理出来？
                        2. 新答案是否能完全从 evidence 中推理出来？
                        3. 是否存在幻觉或编造的信息？
                        
                        请以 JSON 格式返回：
                        {{
                            "is_valid": true/false,
                            "reason": "验证理由"
                        }}
                        """
                        
                        verify_result = llm_call_j(verification_prompt)
                        
                        if isinstance(verify_result, str):
                            start_idx = verify_result.find('{')
                            end_idx = verify_result.rfind('}') + 1
                            if start_idx != -1 and end_idx != -1:
                                verify_result = json.loads(verify_result[start_idx:end_idx])
                        
                        if isinstance(verify_result, dict) and verify_result.get('is_valid', False):
                            question['question'] = modified_question
                            question['answer'] = modified_answer
                            print(f"[Filter Thread {idx + 1}] ✓ 问题已重新设计并通过验证")
                            return idx, question, True
                        else:
                            print(f"[Filter Thread {idx + 1}] ✗ 重新设计的问题未通过验证，抛弃")
                            return idx, None, False
                    else:
                        print(f"[Filter Thread {idx + 1}] ✗ 需要重新设计但未提供新问题或答案，抛弃")
                        return idx, None, False
                
                elif decision == 'discard':
                    # 情况 C：直接抛弃
                    print(f"[Filter Thread {idx + 1}] ✗ 问题无法修复，抛弃")
                    return idx, None, False
                
                else:
                    print(f"[Filter Thread {idx + 1}] ⚠ 未知决策类型：{decision}，保留原问题")
                    return idx, question, True
            
            except Exception as e:
                print(f"[Filter Thread {idx + 1}] 处理异常：{e}，保留原问题")
                return idx, question, True
        
        # 使用 ThreadPoolExecutor 并行处理，最多 20 个线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(process_single_question, idx, question)
                for idx, question in enumerate(questions)
            ]
            
            # 收集结果
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, result, should_keep = future.result()
                    if should_keep and result is not None:
                        results_dict[idx] = result
                    completed += 1
                    if completed % 10 == 0 or completed == len(futures):
                        print(f"\n[Filter & Refine] 已完成 {completed}/{len(futures)} 个问题")
                except Exception as e:
                    print(f"[Filter & Refine] 结果收集异常：{e}")
        
        # 按索引顺序构建结果列表
        filtered_questions = [results_dict[i] for i in range(len(questions)) if i in results_dict]
        
        print(f"\n{'='*80}")
        print(f"[Filter & Refine] 过滤完成")
        print(f"  - 原始问题数：{len(questions)}")
        print(f"  - 保留问题数：{len(filtered_questions)}")
        print(f"  - 抛弃问题数：{len(questions) - len(filtered_questions)}")
        print(f"{'='*80}")
        
        return filtered_questions
