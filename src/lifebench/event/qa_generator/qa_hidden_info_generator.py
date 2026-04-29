# -*- coding: utf-8 -*-
"""
隐藏信息问题生成器：基于用户行为挖掘隐藏需求
工作流程：
1. 并行对每个月生成问题
2. 分析每月 daily_draft 数据，识别某日可能的隐藏需求
3. 调用 LLM 基于该日期及前后3天的 daily_event，润色需求并找到体现需求的事件
4. 设计隐藏信息问题（发掘用户未被明确提及但可推理出的需求）
"""
import os
import json
import random
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from .base_generator import BaseQAGenerator
from src.lifebench.utils.llm_call import llm_call_j


class QAHiddenInfoGenerator(BaseQAGenerator):
    def __init__(self, daily_event: List[Dict], event_tree: List[Dict],
                 draft_event: Dict[str, List], phonedata: Dict[str, List],
                 phone_data_dir: str = None, is_print: bool = True,
                 persona: Dict = None, year: int = 2025):
        """
        初始化隐藏信息 QA 生成器

        Args:
            daily_event: daily_event 数据列表
            event_tree: event_tree 数据列表
            draft_event: draft_event 数据字典（按月份组织）
            phonedata: 手机操作数据字典
            phone_data_dir: 手机数据目录路径
            is_print: 是否打印调试信息
            persona: 用户画像数据
            year: 年份，默认 2025
        """
        super().__init__()
        self.daily_event = daily_event
        self.event_tree = event_tree
        self.draft_event = draft_event
        self.phonedata = phonedata
        self.phone_data_dir = phone_data_dir
        self.is_print = is_print
        self.year = year
        self.persona = persona
    
    def QAGen(self, **kwargs) -> List[Dict]:
        """
        实现基类抽象方法，作为外部调用的统一入口
        """
        return self.generate_questions()
    
    def generate_questions(self) -> List[Dict]:
        """
        生成隐藏信息问题，并行处理每个月
        
        Returns:
            生成的 QA 列表
        """
        if self.is_print:
            print("\n[HiddenInfoGen] 开始生成隐藏信息问题...")
        
        all_questions = []
        months = list(self.draft_event.keys())
        
        if self.is_print:
            print(f"  - 共 {len(months)} 个月份需要处理")
        
        # 并行处理每个月
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_month = {}
            for month in months:
                future = executor.submit(
                    self._generate_questions_for_month,
                    month
                )
                future_to_month[future] = month
            
            # 收集结果
            for future in as_completed(future_to_month):
                month = future_to_month[future]
                try:
                    questions = future.result()
                    if questions:
                        all_questions.extend(questions)
                        if self.is_print:
                            print(f"  ✓ {month}: 生成 {len(questions)} 个问题")
                except Exception as e:
                    if self.is_print:
                        print(f"  ✗ {month}: 处理失败 - {e}")
        
        if self.is_print:
            print(f"[HiddenInfoGen] ✓ 完成，共生成 {len(all_questions)} 个隐藏信息问题")

        # 过滤不可回答的问题（20线程并行）
        if self.is_print:
            print("\n[HiddenInfoGen] 开始过滤不可回答的问题...")

        from src.lifebench.utils.llm_call import llm_call_j

        def validate_single_qa(idx: int, qa: Dict) -> tuple:
            """验证单个 QA 对"""
            try:
                filter_prompt = f"""
作为问答质量审核员，请验证以下问题是否可以通过现有证据回答。

【问题】
{qa.get('question', '')}

【答案】
{qa.get('correct_answer', '')}（选择题答案）

【选项】
{json.dumps(qa.get('options', []), ensure_ascii=False, indent=2)}

【证据列表】（共 {len(qa.get('evidence', []))} 条）
{json.dumps([{'type': e.get('type', 'unknown'), 'summary': str(e)[:300]} for e in qa.get('evidence', [])], ensure_ascii=False, indent=2)}

**任务要求**
1. 分析问题、答案和证据之间的关系
2. 判断证据是否足以支撑选出正确的选项
3. 如果证据不足以回答问题，返回 pass=False，并说明原因
4. 如果证据可以回答问题，返回 pass=True

**重要约束**
- 问题必须是具体、可回答的
- 选项必须与问题匹配
- 证据必须能支撑答案的推理过程

**输出要求**
请以 JSON 格式返回：
{{
    "pass": true/false,
    "reason": "验证通过/不通过的原因"
}}
"""
                llm_result = llm_call_j(filter_prompt)

                if isinstance(llm_result, str):
                    start_idx = llm_result.find('{')
                    end_idx = llm_result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        llm_result = json.loads(llm_result[start_idx:end_idx])

                if isinstance(llm_result, dict):
                    is_pass = llm_result.get('pass', True)
                    reason = llm_result.get('reason', '')
                    print(f"[HiddenInfoGen] 第 {idx + 1} 个问题: {'✓ 通过' if is_pass else '✗ 未通过'} - {reason}")
                    return idx, qa, is_pass
                else:
                    return idx, qa, True

            except Exception as e:
                print(f"[HiddenInfoGen] 第 {idx + 1} 个问题验证失败：{e}")
                return idx, qa, True

        # 20线程并行验证
        filtered_results = [None] * len(all_questions)
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(validate_single_qa, idx, qa)
                for idx, qa in enumerate(all_questions)
            ]

            for future in as_completed(futures):
                try:
                    idx, qa, is_pass = future.result()
                    if is_pass:
                        filtered_results[idx] = qa
                except Exception as e:
                    print(f"[HiddenInfoGen] 结果收集失败：{e}")

        # 过滤掉 None 值
        all_questions = [r for r in filtered_results if r is not None]

        if self.is_print:
            print(f"[HiddenInfoGen] ✓ 过滤完成，通过验证的问题数量：{len(all_questions)}")

        # 转换选择题格式为问答题格式
        all_questions = self._convert_to_qa_format(all_questions)

        return all_questions

    def _convert_to_qa_format(self, questions: List[Dict]) -> List[Dict]:
        """
        将选择题格式转换为问答题格式

        将 options 和 correct_answer 转换为：
        - question: 原题 + 选项列表
        - answer: correct_answer（字母如 "C"）
        - score_points: 评分点
        """
        converted_count = 0
        new_questions = []

        # 调试：检查有多少问题包含 options 和 correct_answer
        debug_count = sum(1 for qa in questions if 'options' in qa and 'correct_answer' in qa)
        print(f"[HiddenInfoGen] 调试: 共 {len(questions)} 个问题，其中 {debug_count} 个包含 options 和 correct_answer")

        for qa in questions:
            if 'options' in qa and 'correct_answer' in qa:
                options = qa.get('options', [])
                correct_answer = qa.get('correct_answer', '')
                #print(options)
                
                # 将选项转字符串拼接
                options_text = str(options)
                #print(options_text)
                # 构建新的问题字典，只保留需要的字段
                new_qa = {
                    'question': qa.get('question', '') + options_text,
                    'answer': correct_answer,
                    'score_points': [{"description": "准确回答出答案", "score": 10}]
                }
                #print(new_qa)
                
                # 复制其他字段
                for key in qa:
                    if key not in ['options', 'correct_answer']:
                        new_qa[key] = qa[key]

                new_questions.append(new_qa)
                converted_count += 1
            else:
                new_questions.append(qa)

        if converted_count > 0:
            print(f"[HiddenInfoGen] ✓ 格式转换完成: {converted_count} 个问题已转换为问答题格式")

        return new_questions
    
    def _generate_questions_for_month(self, month: str) -> List[Dict]:
        """
        为单月生成隐藏信息问题
        
        Args:
            month: 月份字符串，格式 YYYY-MM
        
        Returns:
            该月生成的 QA 列表
        """
        print(f"[HiddenInfoGen] 开始处理月份 {month}")
        month_data = self.draft_event.get(month, [])
        print(f"  - 月份 {month}: 共 {len(month_data)} 条数据")
        if not month_data or not isinstance(month_data, list):
            return []
        
        # Step 1: 分析整月的隐藏需求
        print(f"  - 开始分析隐藏需求...")
        hidden_needs = self._analyze_hidden_needs_for_month(month, month_data)
        
        if not hidden_needs:
            print(f"  ⚠️ 未发现隐藏需求，返回空列表")
            return []
        
        # Step 2: 为每个需求收集证据
        for need in hidden_needs:
            self._collect_evidence_for_need(need, month_data)

        print(f"  - 共 {len(hidden_needs)} 个隐藏需求")
        print(hidden_needs)

        # Step 2.5: 生成当月主要事件和主题总结
        month_summary = self._generate_month_summary(month, month_data)
        print(f"  - 月度总结: {month_summary}")

        # Step 3: 对所有隐藏需求一次性生成问题
        questions = self._design_questions_for_all_needs(hidden_needs, month, month_summary)
        
        # Step 4: 为每个问题补充 evidence 字段（手机数据）
        for qa in questions:
            required_events_id = qa.get("required_events_id", [])
            if required_events_id:
                # 从 phonedata 中查找对应的手机数据
                evidence_data = self._get_phone_evidence_by_event_ids(required_events_id)
                qa["evidence"] = evidence_data
            else:
                qa["evidence"] = []
            qa['ask_time'] = f'{self.year}-12-31'
        return questions
    
    def _analyze_hidden_needs_for_month(self, month: str, month_data: List[Dict]) -> List[Dict]:
        """
        分析整月的隐藏需求
        
        Args:
            month: 月份字符串
            month_data: 该月的所有数据
        
        Returns:
            隐藏需求列表
        """
        prompt = f"""
        你是一位用户行为分析师和心理学家。请分析以下用户在 {month} 的整体活动数据，挖掘用户可能存在的**隐藏需求**。
        
        【重要概念】
        隐藏需求是指：
        - 用户没有明确表达，但可以通过行为模式推理出的需求
        - 不是表面的活动，而是活动背后的动机或潜在需求
        - 例如：频繁搜索健身信息 → 可能有减肥或塑形的需求（但未明确说）
        - 例如：多次查看机票 → 可能有旅行计划（但未预订或告诉他人）
        
        【月度活动数据】
        {json.dumps(month_data, ensure_ascii=False, indent=2)}
        
        【任务要求】
        请分析用户的行为模式，找出 3-5 个可能的隐藏需求。
        
        **分析维度**：
        1. **行为模式**：用户的哪些行为暗示了某种需求？
        2. **潜在动机**：这些行为背后可能的动机是什么？
        3. **未满足的需求**：用户可能需要什么但没有明确表达？
        
        **筛选标准**：
        - 需求必须是隐藏的，不能是用户明确表达的
        - 必须有行为证据支持，不能凭空猜测
        - 需求应该是具体的、可验证的
        - 优先选择贯穿整个月或多个日期的需求
        
        **输出格式**：
        请以 JSON 数组格式返回：
        [
            {{
                "need_description": "隐藏需求的描述（具体、清晰）",
                "confidence": "置信度（high/medium/low）",
                "evidence_summary": "支持该需求的行为证据摘要",
                "related_dates": ["2025-01-05", "2025-01-12"]  // 相关日期列表，按最能体现该需求的程度排序（最相关的排在前面）
            }}
        ]
        
        **示例**：
        [
            {{
                "need_description": "用户可能有学习新技能的需求，特别是编程或数据分析",
                "confidence": "medium",
                "evidence_summary": "多次浏览在线课程网站，搜索Python教程，收藏技术博客",
                "related_dates": ["2025-01-05", "2025-01-12", "2025-01-20"]
            }},
            {{
                "need_description": "用户可能有改善睡眠质量的需求",
                "confidence": "high",
                "evidence_summary": "深夜频繁查看手机，搜索助眠方法，购买眼罩和耳塞",
                "related_dates": ["2025-01-08", "2025-01-15", "2025-01-22"]
            }}
        ]
        
        如果没有发现明显的隐藏需求，返回空数组 []。
        """
        
        try:
            res = llm_call_j(prompt)
            print(f"  - LLM 分析整月隐藏需求: {res}")
            if isinstance(res, str):
                res = json.loads(res)
            
            # 兼容不同的返回格式
            if isinstance(res, list):
                return res
            elif isinstance(res, dict):
                # 尝试从常见字段名中提取列表
                hidden_needs = res.get("hidden_needs") or res.get("needs") or res.get("data") or []
                if isinstance(hidden_needs, list):
                    return hidden_needs
            
            return []
        
        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ 分析整月隐藏需求失败 ({month}): {e}")
            return []
    
    def _generate_month_summary(self, month: str, month_data: List[Dict]) -> Dict:
        """
        生成当月主要事件和主题的总结
        
        Args:
            month: 月份字符串
            month_data: 该月的所有数据
        
        Returns:
            包含主要事件和主题的总结字典
        """
        prompt = f"""
        你是一位用户行为分析师。请分析用户在 {month} 的主要活动和涉及的主题。
        
        【月度活动数据】
        {json.dumps(month_data[:10], ensure_ascii=False, indent=2)}  # 只取前10条作为样本
        
        【任务要求】
        请总结该月的主要事件类型和涉及的主题领域。
        
        **输出格式**：
        请以 JSON 格式返回：
        {{
            "main_events": ["主要事件类型1", "主要事件类型2", ...],
            "topics": ["主题领域1", "主题领域2", ...],
            "summary": "一句话总结该月的核心活动特征"
        }}
        
        **示例**：
        {{
            "main_events": ["职业发展与学习", "健康管理", "社交活动", "投资理财"],
            "topics": ["CFA备考", "健身运动", "摄影爱好", "客户咨询", "家庭聚会", "邮票收藏"],
            "summary": "该月用户主要围绕职业发展（CFA备考、客户工作）、健康管理（运动、体检）和社交活动（朋友聚会、家庭联系）展开"
        }}
        """
        
        try:
            res = llm_call_j(prompt)
            if isinstance(res, str):
                res = json.loads(res)
            
            if isinstance(res, dict):
                return res
            else:
                return {
                    "main_events": [],
                    "topics": [],
                    "summary": ""
                }
        
        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ 生成月度总结失败: {e}")
            return {
                "main_events": [],
                "topics": [],
                "summary": ""
            }
    
    def _collect_evidence_for_need(self, need: Dict, month_data: List[Dict]):
        """
        基于需求的相关日期，遍历每个日期，获取该日期的所有daily_event，
        使用LLM分析并提取能体现需求的事件，直到收集到超过3个证据
        
        Args:
            need: 隐藏需求信息（包含 related_dates）
            month_data: 该月的所有数据（未使用，保留参数兼容性）
        """
        related_dates = need.get("related_dates", [])
        if not related_dates:
            need["evidence"] = []
            return
        
        # 按日期排序
        sorted_dates = sorted(related_dates)
        
        # 收集证据
        evidence_events = []
        
        for date in sorted_dates:
            if len(evidence_events) > 3:
                break
            
            # 获取该日期的所有事件
            daily_events = self._get_events_for_single_date(date)
            print(f"  - 日期 {date}: 共 {len(daily_events)} 个事件")
            if not daily_events:
                continue
            
            # 使用LLM分析该日期的事件中哪些能体现需求
            relevant_events = self._check_daily_events_relevance(daily_events, need, date)
            
            # 添加到证据列表
            evidence_events.extend(relevant_events)
        
        need["evidence"] = evidence_events
    
    def _get_events_for_single_date(self, date: str) -> List[Dict]:
        """
        获取指定日期的所有事件
        
        Args:
            date: 日期字符串，格式 YYYY-MM-DD
        
        Returns:
            该日期的事件列表
        """
        events = []
        for event in self.daily_event:
            event_dates = event.get("date", [])
            if not event_dates:
                continue
            
            # 检查事件是否在该日期
            for date_range in event_dates:
                if isinstance(date_range, str):
                    # 处理日期范围或单个日期
                    if "至" in date_range:
                        # 日期范围：检查目标日期是否在范围内
                        start_end = date_range.split("至")
                        start_date = start_end[0].strip().split(" ")[0]
                        end_date = start_end[1].strip().split(" ")[0]
                        if start_date <= date <= end_date:
                            events.append(event)
                            break
                    else:
                        # 单个日期
                        event_date = date_range.split(" ")[0]
                        if event_date == date:
                            events.append(event)
                            break
        
        return events
    
    def _check_daily_events_relevance(self, daily_events: List[Dict], need: Dict, date: str) -> List[Dict]:
        """
        使用LLM分析某日的所有事件中，哪些能体现隐藏需求
        
        Args:
            daily_events: 某日的所有事件列表
            need: 隐藏需求信息
            date: 日期字符串
        
        Returns:
            能体现需求的事件列表（带日期信息）
        """
        if not daily_events:
            return []
        
        need_description = need.get("need_description", "")
        
        # 直接使用完整的事件数据
        events_desc = json.dumps(daily_events, ensure_ascii=False, indent=2)
        
        prompt = f"""
        你是一位用户行为分析师。请分析以下用户在 {date} 的所有事件，找出能体现用户隐藏需求的事件。
        
        【隐藏需求】
        {need_description}
        
        【{date} 的所有事件】
        {events_desc}
        
        【任务要求】
        请分析这些事件中，哪些事件能作为支持该隐藏需求的证据。
        
        **判断标准**：
        - 事件应该直接或间接反映了用户的需求或动机
        - 事件可能是需求的表现、原因或结果
        - 只选择与需求有明显关联的事件
        
        **输出格式**：
        请以 JSON 数组格式返回相关事件的ID列表：
        ["event_id_1", "event_id_2", ...]
        
        如果没有相关事件，返回空数组 []。
        """
        
        try:
            res = llm_call_j(prompt)
            print(f"  - LLM 分析日期 {date} 的事件相关性: {res}")
            if isinstance(res, str):
                res = json.loads(res)
            
            if not isinstance(res, list):
                # 兼容不同的返回格式
                if isinstance(res, dict):
                    # 尝试多种可能的字段名
                    relevant_event_ids = res.get("relevant_event_ids") or res.get("relevant_events") or res.get("event_ids") or []
                    if isinstance(relevant_event_ids, list):
                        res = relevant_event_ids
                    else:
                        return []
                else:
                    return []
            
            # 根据返回的ID列表提取对应事件
            relevant_event_ids = set(res)
            relevant_events = []
            
            for event in daily_events:
                event_id = event.get("id") or event.get("event_id")
                if event_id in relevant_event_ids:
                    relevant_events.append({
                        "date": date,
                        "event": event
                    })
            
            print(f"    - 找到 {len(relevant_events)} 个相关事件")
            return relevant_events
        
        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ LLM 分析日期 {date} 的事件相关性失败: {e}")
            return []
    
    def _design_questions_for_all_needs(self, hidden_needs: List[Dict], month: str, month_summary: Dict = None) -> List[Dict]:
        """
        基于该月的所有隐藏需求，一次性生成一组推荐类选择题
        
        Args:
            hidden_needs: 该月的所有隐藏需求列表
            month: 月份字符串
            month_summary: 月度主要事件和主题总结
        
        Returns:
            生成的 QA 列表
        """
        if not hidden_needs:
            return []
        
        print(f"\n  - 开始为 {len(hidden_needs)} 个隐藏需求生成推荐问题...")
        
        # 构建所有需求的摘要
        needs_summary = []
        for idx, need in enumerate(hidden_needs, 1):
            needs_summary.append({
                "need_id": idx,
                "need_description": need.get("need_description", ""),
                "evidence_summary": need.get("evidence_summary", ""),
                "evidence_count": len(need.get("evidence", []))
            })
        
        # 准备 persona 数据
        persona_info = json.dumps(self.persona, ensure_ascii=False, indent=2) if self.persona else "无用户画像数据"
        
        # 准备月度总结数据
        month_summary_info = json.dumps(month_summary, ensure_ascii=False, indent=2) if month_summary else "无月度总结"
        
        prompt = f"""
        你是一位精通用户心理的内容推荐专家。基于对用户行为的深度分析，我们发现用户在 {month} 可能存在多个隐藏需求。
        
        【{month} 的主要事件和主题】
        {month_summary_info}
        
        【{month} 的所有隐藏需求】（**重点**）
        {json.dumps(needs_summary, ensure_ascii=False, indent=2)}
        
        【任务要求】
        请基于这些隐藏需求和用户画像，为**最多前5个最明显的隐藏需求**设计**推荐类选择题**。
        
        **筛选原则**：
        - 优先选择置信度高（high）、证据充分的需求
        - 如果需求超过5个，只选择前5个最明显、最有把握的需求
        - 每个选中的需求对应一个问题
        
        **问题设计要求**：
        1. **题面自然多样化且包含月份，体现推荐性质**：
           - **必须在题面中明确提及月份**（如"在2025-01"、"这个月"、"1月期间"等）
           - **题面要体现推荐性质**，让用户感觉是在做内容/活动推荐选择
           - 不要机械地使用固定格式，要让问题读起来自然流畅
           - 可以根据需求特点调整问法，例如：
             * "在2025-01，我最近似乎对哪类内容更感兴趣？"
             * "以下哪个话题最符合我在1月的关注点？"
             * "如果要选择一个方向深入学习，我在2025-01更可能选哪个？"
             * "哪项活动最能反映我在1月期间的潜在兴趣？"
           - 保持第一人称视角，像用户在自我反思
           - 问题要间接探索隐藏需求，不要直接暴露
        
        2. **选项设计**（针对每个需求）：
           - 提供 4 个选项（A/B/C/D）
           - 其中 1 个是正确答案（与该隐藏需求高度相关）
           - 其他 3 个是错误选项（干扰项）
           
        3. **正确答案分布要求**：
           - **正确答案的位置要多样分布**，不能所有问题的正确答案都是 A
           - 应该在 A/B/C/D 之间随机分布，保持平衡
           - 避免让答题者发现规律
        
        4. **错误选项的关键要求**：
           - **不得包含本月的任何隐藏需求**：错误选项不能反映用户在本月的任何隐藏需求
           - **与本月主要主题尽量无关**：错误选项应该避开【{month} 的主要事件和主题】中提到的主题领域，选择与该月核心活动不相关的内容
           - **必须与问题主题相关**：错误选项必须与问题的主题领域相关，不能出现完全无关的内容
             * 例如：如果问题是关于"个人社交"的，错误选项应该是其他社交/人际关系相关的内容，不能是"野外求生"这种完全不相关的主题
             * 错误选项应该在同一个大主题下，但指向不同的子方向或需求
             * 要让答题者需要在相似主题中进行判断，而不是通过主题差异直接排除
           - **包含一定量与人物关联不大的数据**：不要所有错误选项都基于用户的个人特征或历史行为设计，应该包含一些通用的、与人物关联度较低的内容选项
           - **错误选项的合理性控制**：
             * 错误选项要有一定的吸引力，不能非常不合理
             * 但从深层逻辑来看，除正确答案外的其他选项不应该真正合理
             * 不能让答题者从题面轻易分辨出哪个是正确答案
             * 错误选项应该是"看似合理但实际不符合用户当前隐藏需求"的内容
           - **不可直接判断**：不能让答题者根据选项内容就能直接推断出正确答案
           - **多样化来源**：错误选项可以来自：
             * 用户过去的兴趣爱好（但本月未体现）
             * 与用户职业/生活相关但不涉及本月主题的内容
             * 通用的热门话题/内容（与本月活动无关，与人物关联不大，但与问题主题相关）
             * 与其他月份的需求相关的内容
             * 中性、普适性的内容选项（但与问题主题相关）
           - **避免明显错误**：错误选项不应该是明显不合理或与用户完全无关的内容
        
        5. **答案解释和推理过程不需要输出**：只需要返回问题和选项
        
        **重要提示**：
        - 每个需求对应一个问题
        - 不同问题的选项应该有所区别，避免重复
        - 错误选项要精心设计，让题目有挑战性但不是陷阱题
        - 结合用户画像信息，使选项更符合用户的背景和兴趣
        
        **输出格式**：
        请以 JSON 数组格式返回，每个元素对应一个隐藏需求的问题：
        [
            {{
                "need_id": 1,
                "question": "自然流畅的问题表述（第一人称，多样化表达，**必须包含月份信息**）",
                "options": [
                    "A. [选项A内容]",
                    "B. [选项B内容]",
                    "C. [选项C内容]",
                    "D. [选项D内容]"
                ],
                "correct_answer": "A"
            }},
            ...
        ]
        
        **示例**：
        [
            {{
                "need_id": 1,
                "question": "在2025-01，我最近似乎在寻找一种方式来平衡工作和生活的压力，以下哪个内容最符合我的需求？",
                "options": [
                    "A. 《CFA二级备考策略与时间管理技巧》",
                    "B. 《周末城市徒步摄影指南》",
                    "C. 《职场压力管理与工作生活平衡实践》",
                    "D. 《家庭理财规划与税务优化方案》"
                ],
                "correct_answer": "C"
            }},
            {{
                "need_id": 2,
                "question": "在2025-01，如果要选择一个方向来拓展我的人际关系，我更可能倾向于哪个？",
                "options": [
                    "A. 《高效沟通技巧：如何在职场建立影响力》",
                    "B. 《亲密关系心理学：建立深层连接的艺术》",
                    "C. 《Python数据分析实战：从入门到精通》",
                    "D. 《马拉松训练计划：从零到全马》"
                ],
                "correct_answer": "B"
            }}
        ]
        
        【用户画像】
        {persona_info}
        
        【重要约束】
        - **只返回 JSON 数组**，不要有任何其他文字、解释或标记
        - **不要使用 Markdown 代码块**（如 ```json ... ```）
        - **不要添加任何前缀或后缀**
        - **确保 JSON 格式完全正确**，可以被 json.loads() 直接解析
        - **每个需求必须对应一个问题**，不得遗漏
        - **选项必须是字符串数组**，格式为 ["A. xxx", "B. xxx", "C. xxx", "D. xxx"]
        - **correct_answer 必须是单个字母**："A"、"B"、"C" 或 "D"
        """
        
        try:
            res = llm_call_j(prompt)
            print(f"  - LLM 返回结果数量: {len(res) if isinstance(res, list) else '非列表'}")
            if isinstance(res, str):
                res = json.loads(res)
            
            if not isinstance(res, list):
                print(f"  ⚠️ LLM 返回格式错误，期望列表")
                return []
            
            # 构建 QA 列表
            questions = []
            for qa_data in res:
                need_id = qa_data.get("need_id", 0)
                if need_id < 1 or need_id > len(hidden_needs):
                    print(f"  ⚠️ 无效的 need_id: {need_id}")
                    continue
                
                need = hidden_needs[need_id - 1]
                
                # 提取证据中的事件ID
                evidence = need.get("evidence", [])
                required_events_id = [evt.get("event", {}).get("id") or evt.get("event", {}).get("event_id") 
                                     for evt in evidence 
                                     if evt.get("event")]
                # 过滤掉 None 值
                required_events_id = [eid for eid in required_events_id if eid]
                
                qa = {
                    "question": qa_data.get("question", ""),
                    "options": qa_data.get("options", []),
                    "correct_answer": qa_data.get("correct_answer", ""),
                    "required_events_id": required_events_id,
                    "question_type": "Hidden_info"
                }
                
                # 验证必要字段
                if not qa["question"] or not qa["options"] or not qa["correct_answer"]:
                    print(f"  ⚠️ 需求 {need_id}: 问题、选项或正确答案为空，跳过")
                    continue
                
                questions.append(qa)
                print(f"  ✓ 需求 {need_id}: 成功生成推荐问题 (证据事件数: {len(required_events_id)})")
            
            print(f"  - 共生成 {len(questions)} 个问题")
            return questions
        
        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ 批量设计问题失败: {e}")
                import traceback
                traceback.print_exc()
            return []

    
    def _get_events_for_dates(self, dates: List[str]) -> List[Dict]:
        """
        获取指定日期列表的相关事件
        
        Args:
            dates: 日期字符串列表
        
        Returns:
            相关事件列表
        """
        if not dates:
            return []
        
        # 收集这些日期的所有事件
        related_events = []
        for event in self.daily_event:
            event_dates = event.get("date", [])
            if not event_dates:
                continue
            
            # 提取事件的日期部分
            for date_range in event_dates:
                if isinstance(date_range, str):
                    start_date = date_range.split("至")[0].split(" ")[0] if "至" in date_range else date_range.split(" ")[0]
                    
                    if start_date in dates:
                        evt_with_date = event.copy()
                        evt_with_date["event_date"] = start_date
                        related_events.append(evt_with_date)
                        break
        
        return related_events
    
    def _get_phone_evidence_by_event_ids(self, event_ids: List[str]) -> List[Dict]:
        """
        根据事件ID列表，从手机数据中提取对应的证据
        
        Args:
            event_ids: 事件ID列表
        
        Returns:
            对应的手机数据证据列表
        """
        if not event_ids or not self.phonedata:
            return []
        
        evidence_list = []
        event_id_set = set(str(eid) for eid in event_ids)
        
        # 遍历所有类型的手机数据
        for data_type, data_items in self.phonedata.items():
            if not isinstance(data_items, list):
                continue
            
            for item in data_items:
                if not isinstance(item, dict):
                    continue
                
                # 检查 daily_event_id 或 related_event 字段
                item_event_id = str(item.get('daily_event_id', ''))
                related_event = str(item.get('related_event', ''))
                
                # 如果匹配，添加完整的操作数据
                if item_event_id in event_id_set or related_event in event_id_set:
                    evidence_list.append({
                        'type': data_type,
                        'data': item,
                        'phone_id': item.get('phone_id', '')
                    })
        
        return evidence_list
