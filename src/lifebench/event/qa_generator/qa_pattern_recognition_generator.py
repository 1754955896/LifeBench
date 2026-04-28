import json
import os
import random
import time
from typing import List, Dict, Any, Tuple
import threading
import concurrent.futures

from src.lifebench.utils.llm_call import llm_call, llm_call_j,llm_call_reason_j
from src.lifebench.event.templates.template_qa import (
    PATTERN_RECOGNITION_TEMPLATE,
    EVENT_TRACING_ENHANCED_TEMPLATE
)
from src.lifebench.event.templates.template_nd import (
    get_preference_template,
    get_interest_template,
    get_emotional_template,
    get_health_template,
    get_filter_template,
    get_yearly_preference_template,
    get_yearly_interest_template,
    get_yearly_emotional_template,
    get_yearly_health_template,
    get_yearly_filter_template
)
from .base_generator import BaseQAGenerator
from .phone_operation_generator import PhoneOperationGenerator


class QAPatternRecognitionGenerator(BaseQAGenerator):
    def __init__(self, persona_data: Dict[str, Any] = None, event_tree: Dict[str, Any] = None, 
                 daily_event: Dict[str, Any] = None, draft_event: Dict[str, Any] = None, 
                 special_event: Dict[str, Any] = None, phone_data_dir: str = None, 
                 is_print: bool = True):
        """
        初始化模式识别 QA 生成器
        
        Args:
            persona_data: 用户画像数据
            event_tree: 事件树数据
            daily_event: 每日事件数据
            draft_event: 草稿事件数据
            special_event: 特殊事件数据
            phone_data_dir: 手机数据目录路径
            is_print: 是否打印调试信息
        """
        super().__init__(persona_data=persona_data, event_tree=event_tree, 
                        daily_event=daily_event, draft_event=draft_event, 
                        special_event=special_event, phone_data_dir=phone_data_dir)
        self.is_print = is_print
        
        # 线程锁
        self.phonedata_lock = threading.Lock()
        self.phone_id_counters = {}
        
        # 手机操作生成器
        self.phone_op_generator = PhoneOperationGenerator()
    
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
                    op['phone_id'] = str(self.phone_id_counters[op_type])
                
                self.phone_id_counters[op_type] += 1
                
                self.phonedata[op_type].append(op)
        
        print(f"[Evidence Refine] 已将 {len(operations)} 条操作数据添加到 phonedata")
    
    def _generate_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        """
        基于 draft_event 生成单个月份的总结（并行调用 5 个 LLM prompt）
        
        Args:
            year: 年份
            month: 月份
            
        Returns:
            月份总结数据
        """
        month_key = f"{year}-{month:02d}"
        print(f"\n[Monthly Summary] 生成 {month_key} 的月份总结...")
        
        # 获取该月份的 draft_event 数据
        month_events = self.draft_event.get(month_key, [])
        
        if not month_events or not isinstance(month_events, list):
            print(f"[Monthly Summary] {month_key} 没有事件数据")
            return None
        
        # 定义 5 个独立的 prompt
        prompts = {
            'major_events': f"""
            作为生活分析专家，请分析以下 {month_key} 的生活记录数据，总结主要事件。
            
            【月份数据】
            {json.dumps(month_events, ensure_ascii=False, indent=2)}
            
            **任务要求**
            - 本月发生了哪些重要事件？
            - 这些事件对生活有什么影响？
            - 哪些事件具有里程碑意义？
            
            请以 JSON 格式返回：
            {{
                "major_events": "主要事件总结（详细描述）",
                "key_milestones": ["里程碑事件列表"]
            }}
            """,
            
            'preference_changes': f"""
            作为生活分析专家，请分析以下 {month_key} 的生活记录数据，识别偏好和习惯的变化。
            
            【月份数据】
            {json.dumps(month_events, ensure_ascii=False, indent=2)}
            
            **任务要求**
            - 本月出现了哪些新的兴趣爱好或习惯？
            - 原有的习惯有哪些改变？
            - 生活方式有什么调整？
            - 消费偏好或休闲方式的变化？
            
            请以 JSON 格式返回：
            {{
                "preference_changes": "偏好和习惯变化（详细描述）",
                "new_habits": ["新养成的习惯"],
                "changed_habits": ["发生改变的习惯"]
            }}
            """,
            
            'interest_changes': f"""
            作为生活分析专家，请分析以下 {month_key} 的生活记录数据，分析感兴趣内容的变化。
            
            【月份数据】
            {json.dumps(month_events, ensure_ascii=False, indent=2)}
            
            **任务要求**
            - 本月关注的领域或话题有什么变化？
            - 学习重点或阅读方向的转变？
            - 对哪些新知识或技能表现出兴趣？
            
            请以 JSON 格式返回：
            {{
                "interest_changes": "感兴趣内容变化（详细描述）",
                "focus_areas": ["关注的领域/话题"],
                "learning_focus": "学习重点"
            }}
            """,
            
            'health_fitness': f"""
            作为健康分析师，请分析以下 {month_key} 的生活记录数据，总结健康和运动变化。
            
            【月份数据】
            {json.dumps(month_events, ensure_ascii=False, indent=2)}
            
            **任务要求**
            - 运动频率和类型的变化？
            - 健康状况、饮食习惯的调整？
            - 作息规律的改变？
            - 是否有健康问题或突破？
            
            请以 JSON 格式返回：
            {{
                "health_fitness_changes": "健康和运动变化（详细描述）",
                "exercise_changes": "运动变化",
                "health_status": "健康状况",
                "lifestyle_adjustments": "生活方式调整"
            }}
            """,
            
            'emotional_events': f"""
            作为情感分析师，请分析以下 {month_key} 的生活记录数据，找出给人带来深刻心理冲击或情绪集中的前三个重要事件。
            
            【月份数据】
            {json.dumps(month_events, ensure_ascii=False, indent=2)}
            
            **任务要求**
            请识别并分析本月最具影响力的前三个事件，这些事件应该满足以下标准之一：
            - 引发强烈情绪波动（兴奋、焦虑、感动、愤怒、惊讶等）
            - 带来新奇或惊讶的体验，超出日常经验范围
            - 造成深刻的心理冲击，对内心产生重大影响
            - 情绪高度集中，成为当月的情感焦点
            
            对于每个事件，请详细分析：
            1. 事件本身及其引发的核心情绪
            2. 前因：导致该事件发生的背景和原因是什么？
            3. 后果：该事件对当事人产生了什么影响和改变？
            
            请以 JSON 格式返回：
            {{
                "emotional_events": [
                    {{
                        "event": "事件描述",
                        "emotion": "核心情感类型（兴奋/焦虑/感动/愤怒/惊讶等）",
                        "intensity": "强度（1-10）",
                        "impact_level": "影响程度（深刻/中等/轻微）",
                        "cause": "前因分析（导致事件发生的背景和原因）",
                        "effect": "后果分析（事件带来的影响和改变）",
                        "why_significant": "为何该事件具有深刻影响或心理冲击"
                    }},
                    {{
                        "event": "第二个事件描述",
                        "emotion": "核心情感类型",
                        "intensity": "强度（1-10）",
                        "impact_level": "影响程度",
                        "cause": "前因分析",
                        "effect": "后果分析",
                        "why_significant": "为何该事件具有深刻影响或心理冲击"
                    }},
                    {{
                        "event": "第三个事件描述",
                        "emotion": "核心情感类型",
                        "intensity": "强度（1-10）",
                        "impact_level": "影响程度",
                        "cause": "前因分析",
                        "effect": "后果分析",
                        "why_significant": "为何该事件具有深刻影响或心理冲击"
                    }}
                ],
                "emotional_summary": "本月整体情感状态总结（重点描述这三个事件如何塑造了当月的情感基调）"
            }}
            """
        }
        
        # 使用 ThreadPoolExecutor 并行调用 5 个 LLM
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # 提交所有任务
            future_to_key = {
                executor.submit(llm_call_j, prompt): key
                for key, prompt in prompts.items()
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    llm_result = future.result()
                    
                    if self.is_print:
                        print(f"\n[Monthly Summary - {month_key}] {key} LLM 输出:")
                        print(llm_result[:300] + "..." if len(llm_result) > 300 else llm_result)
                    
                    # 如果返回的是字符串，需要提取 JSON 并解析
                    if isinstance(llm_result, str):
                        # 尝试提取 JSON 对象（处理可能的多余文本）
                        start_idx = llm_result.find('{')
                        end_idx = llm_result.rfind('}') + 1
                        if start_idx != -1 and end_idx != -1:
                            json_str = llm_result[start_idx:end_idx]
                            try:
                                results[key] = json.loads(json_str)
                            except json.JSONDecodeError as e:
                                print(f"[Monthly Summary - {month_key}] {key} JSON 解析失败：{e}")
                                results[key] = {}
                        else:
                            print(f"[Monthly Summary - {month_key}] {key} 未找到有效的 JSON 对象")
                            results[key] = {}
                    elif isinstance(llm_result, dict):
                        # 已经是字典，直接使用
                        results[key] = llm_result
                    else:
                        print(f"[Monthly Summary - {month_key}] {key} 返回了未知类型：{type(llm_result)}")
                        results[key] = {}
                except Exception as e:
                    print(f"[Monthly Summary - {month_key}] {key} 解析失败：{e}")
                    results[key] = {}
        
        # 整合所有结果
        summary = {
            'month': month_key,
            'major_events': results.get('major_events', {}).get('major_events', ''),
            'key_milestones': results.get('major_events', {}).get('key_milestones', []),
            'preference_changes': results.get('preference_changes', {}).get('preference_changes', ''),
            'new_habits': results.get('preference_changes', {}).get('new_habits', []),
            'changed_habits': results.get('preference_changes', {}).get('changed_habits', []),
            'interest_changes': results.get('interest_changes', {}).get('interest_changes', ''),
            'focus_areas': results.get('interest_changes', {}).get('focus_areas', []),
            'learning_focus': results.get('interest_changes', {}).get('learning_focus', ''),
            'health_fitness_changes': results.get('health_fitness', {}).get('health_fitness_changes', ''),
            'exercise_changes': results.get('health_fitness', {}).get('exercise_changes', ''),
            'health_status': results.get('health_fitness', {}).get('health_status', ''),
            'lifestyle_adjustments': results.get('health_fitness', {}).get('lifestyle_adjustments', ''),
            'emotional_events': results.get('emotional_events', {}).get('emotional_events', []),
            'emotional_summary': results.get('emotional_events', {}).get('emotional_summary', '')
        }
        
        print(f"[Monthly Summary] {month_key} 总结生成完成")
        return summary
    
    
    def _generate_yearly_summaries(self, year: int) -> List[Dict[str, Any]]:
        """
        并行生成全年各月份的总结
        
        Args:
            year: 年份
            
        Returns:
            月份总结列表
        """
        print(f"\n========== 开始生成 {year} 年各月总结 ==========")
        
        monthly_summaries = []
        
        # 使用 ThreadPoolExecutor 并行处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # 提交所有月份的任务
            future_to_month = {
                executor.submit(self._generate_monthly_summary, year, month): month
                for month in range(1, 13)
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_month):
                month = future_to_month[future]
                try:
                    result = future.result()
                    if result is not None:
                        monthly_summaries.append(result)
                        print(f"[Yearly Summaries] 完成 {year}-{month:02d}")
                    else:
                        print(f"[Yearly Summaries] {year}-{month:02d} 返回 None")
                except Exception as e:
                    print(f"[Yearly Summaries] {year}-{month:02d} 生成失败：{e}")
        
        # 按月份排序
        monthly_summaries.sort(key=lambda x: x.get('month', ''))
        
        print(f"\n========== 完成 {len(monthly_summaries)}/12 个月的总结 ==========")
        return monthly_summaries
    
    def QAGen(self, year: str = "2025", num_questions_per_month: int = 5) -> List[Dict[str, Any]]:
        """
        生成模式识别与习惯分析 QA 对的主入口函数
        
        Args:
            year: 年份，格式为"YYYY"，默认为"2025"
            num_questions_per_month: 每月生成的问题数量
        
        Returns:
            生成的 QA 对列表
        """
        print(f"\n开始生成 {year} 年的模式识别与习惯分析问答对...")
        
        # Step 1: 生成全年各月总结
        yearly_summaries = self._generate_yearly_summaries(int(year))
        
        if not yearly_summaries:
            print("[Error] 未能生成任何月份总结")
            return []
        
        # Step 2: 基于月份总结并行生成各月的问题
        all_questions = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_month = {
                executor.submit(self._generate_monthly_questions, summary): summary.get('month', 'unknown')
                for summary in yearly_summaries
            }
            
            for future in concurrent.futures.as_completed(future_to_month):
                month_key = future_to_month[future]
                try:
                    month_questions = future.result()
                    if month_questions:
                        all_questions.extend(month_questions)
                        print(f"[QAGen] 完成 {month_key} 的问题生成，共{len(month_questions)}个问题")
                except Exception as e:
                    print(f"[QAGen] {month_key} 问题生成失败：{e}")
        
        # # Step 3: 生成年度问题（基于全年 12 个月的数据）
        # yearly_questions = self._generate_yearly_questions(yearly_summaries, int(year))
        # if yearly_questions:
        #     all_questions.extend(yearly_questions)
        
        print(f"\n========== 问题生成完成，共{len(all_questions)}个问题 ==========")
        
        # Step 4: 设置所有问题的 question_type 为"ND"
        print("\n[QAGen] 设置所有问题的 question_type 为'ND'...")
        for question in all_questions:
            question['question_type'] = 'Non-declarative'
        
        # Step 5: 并行过滤和优化问题
        print("\n[QAGen] 开始并行过滤和优化问题...")
        filtered_questions = self._parallel_filter_and_refine(all_questions)
        
        # Step 6: 保存结果
        if filtered_questions:
            self._save_questions(filtered_questions, year)
        
        return filtered_questions
    
    def _generate_monthly_questions(self, monthly_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        基于月份总结生成该月的所有问题
        
        Args:
            monthly_summary: 月份总结数据
            
        Returns:
            该月生成的所有问题列表
        """
        month_key = monthly_summary.get('month', '')
        print(f"\n[Monthly Questions] 开始为 {month_key} 生成问题...")
        
        all_questions = []
        
        # 准备各类问题的输入数据
        major_events_summary = monthly_summary.get('major_events', '') or ''
        
        # 1. 习惯与偏好问题（2-3 个）
        preference_input = {
            'preference_changes': monthly_summary.get('preference_changes', '') or '',
            'new_habits': monthly_summary.get('new_habits', []) or [],
            'changed_habits': monthly_summary.get('changed_habits', []) or [],
            'major_events': major_events_summary
        }
        preference_questions = self._generate_preference_questions(preference_input, month_key)
        all_questions.extend(preference_questions)
        
        # 2. 兴趣问题（2-3 个）
        interest_input = {
            'interest_changes': monthly_summary.get('interest_changes', '') or '',
            'focus_areas': monthly_summary.get('focus_areas', []) or [],
            'learning_focus': monthly_summary.get('learning_focus', '') or '',
            'major_events': major_events_summary
        }
        interest_questions = self._generate_interest_questions(interest_input, month_key)
        all_questions.extend(interest_questions)
        
        # 3. 主要情感事件问题（2-3 个）
        emotional_input = {
            'emotional_events': monthly_summary.get('emotional_events', []) or [],
            'emotional_summary': monthly_summary.get('emotional_summary', '') or '',
            'major_events': major_events_summary
        }
        emotional_questions = self._generate_emotional_questions(emotional_input, month_key)
        all_questions.extend(emotional_questions)
        
        # 4. 运动健康问题（2-3 个）
        health_input = {
            'health_fitness_changes': monthly_summary.get('health_fitness_changes', '') or '',
            'exercise_changes': monthly_summary.get('exercise_changes', '') or '',
            'health_status': monthly_summary.get('health_status', '') or '',
            'lifestyle_adjustments': monthly_summary.get('lifestyle_adjustments', '') or '',
            'major_events': major_events_summary
        }
        health_questions = self._generate_health_questions(health_input, month_key)
        all_questions.extend(health_questions)
        print(f"[Monthly Questions] {month_key} 问题生成完成，共{len(all_questions)}个问题", all_questions)
        # Step 5: LLM 过滤
        filtered_questions = self._filter_questions_by_llm(all_questions, month_key)
        
        print(f"[Monthly Questions] {month_key} 最终保留{len(filtered_questions)}个问题")
        
        # Step 6: 并行调用 check_agent 对所有问题进行完善（最多 20 线程）
        if filtered_questions:
            print(f"\n[Monthly Questions] 开始并行调用 Check Agent 优化问题...")
            refined_questions = self._parallel_check_agent(filtered_questions, month_key)
            print(f"[Monthly Questions] Check Agent 优化完成，共{len(refined_questions)}个问题")
            return refined_questions
        
        return filtered_questions
    
    def _parallel_check_agent(self, questions: List[Dict[str, Any]], month_key: str) -> List[Dict[str, Any]]:
        """
        并行调用 check_agent 对所有问题进行优化（最多 20 线程）
            
        Args:
            questions: 问题列表
            month_key: 月份标识，格式为 "YYYY-MM"
                
        Returns:
            优化后的问题列表
        """
        import concurrent.futures
        
        # 使用临时列表存储结果，保持顺序
        results_dict = {}
        
        def process_question(idx, question):
            """处理单个问题"""
            print(f"\n[Check Agent] 开始处理第 {idx + 1}/{len(questions)} 个问题...")
            try:
                refined = self.check_agent(question, month_key)
                print(f"[Check Agent] 完成第 {idx + 1} 个问题的优化")
                return idx, refined
            except Exception as e:
                print(f"[Check Agent] 第 {idx + 1} 个问题处理失败：{e}")
                return idx, question
        
        # 使用 ThreadPoolExecutor 并行处理，最多 20 个线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(process_question, idx, question)
                for idx, question in enumerate(questions)
            ]
            
            # 收集结果
            for future in concurrent.futures.as_completed(futures):
                idx, refined_question = future.result()
                results_dict[idx] = refined_question
        
        # 按索引顺序构建结果列表
        refined_questions = [results_dict[i] for i in range(len(questions))]
        
        return refined_questions
    
    def _generate_yearly_questions(self, yearly_summaries: List[Dict[str, Any]], year: int) -> List[Dict[str, Any]]:
        """
        基于全年 12 个月的总结数据，从全年视角生成年度问题
        
        Args:
            yearly_summaries: 全年各月总结列表
            year: 年份
            
        Returns:
            生成的年度问题列表
        """
        print(f"\n{'='*80}")
        print(f"[Yearly Questions] 开始为 {year} 年生成年度问题...")
        print(f"{'='*80}")
        
        # 整合全年数据
        yearly_data = self._aggregate_yearly_data(yearly_summaries)
        
        all_yearly_questions = []
        
        # 1. 年度习惯与偏好变化问题（3-5 个）
        preference_yearly = self._generate_yearly_preference_questions(yearly_data, year)
        all_yearly_questions.extend(preference_yearly)
        
        # 2. 年度兴趣发展问题（3-5 个）
        interest_yearly = self._generate_yearly_interest_questions(yearly_data, year)
        all_yearly_questions.extend(interest_yearly)
        
        # 3. 年度情感成长问题（3-5 个）
        emotional_yearly = self._generate_yearly_emotional_questions(yearly_data, year)
        all_yearly_questions.extend(emotional_yearly)
        
        # 4. 年度健康生活问题（3-5 个）
        health_yearly = self._generate_yearly_health_questions(yearly_data, year)
        all_yearly_questions.extend(health_yearly)
        
        # LLM 过滤
        filtered_yearly_questions = self._filter_yearly_questions_by_llm(all_yearly_questions, year)
        
        print(f"[Yearly Questions] {year} 年最终保留{len(filtered_yearly_questions)}个年度问题")
        return filtered_yearly_questions
    
    def _aggregate_yearly_data(self, yearly_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        整合全年 12 个月的总结数据
        
        Args:
            yearly_summaries: 全年各月总结列表
            
        Returns:
            整合后的全年数据
        """
        aggregated = {
            'monthly_summaries': yearly_summaries,
            'all_major_events': [],
            'all_new_habits': [],
            'all_changed_habits': [],
            'all_focus_areas': [],
            'all_emotional_events': [],
            'exercise_changes_timeline': [],
            'health_status_timeline': []
        }
        
        for summary in yearly_summaries:
            month = summary.get('month', '')
            
            # 收集主要事件
            major_event = summary.get('major_events', '')
            if major_event:
                aggregated['all_major_events'].append({'month': month, 'events': major_event})
            
            # 收集新习惯
            new_habits = summary.get('new_habits', [])
            if new_habits:
                for habit in new_habits:
                    aggregated['all_new_habits'].append({'month': month, 'habit': habit})
            
            # 收集改变的习惯
            changed_habits = summary.get('changed_habits', [])
            if changed_habits:
                for habit in changed_habits:
                    aggregated['all_changed_habits'].append({'month': month, 'habit': habit})
            
            # 收集关注领域
            focus_areas = summary.get('focus_areas', [])
            if focus_areas:
                for area in focus_areas:
                    aggregated['all_focus_areas'].append({'month': month, 'area': area})
            
            # 收集情感事件
            emotional_events = summary.get('emotional_events', [])
            if emotional_events:
                for event in emotional_events:
                    aggregated['all_emotional_events'].append({'month': month, 'event': event})
            
            # 运动变化时间线
            exercise_change = summary.get('exercise_changes', '')
            if exercise_change:
                aggregated['exercise_changes_timeline'].append({'month': month, 'change': exercise_change})
            
            # 健康状况时间线
            health_status = summary.get('health_status', '')
            if health_status:
                aggregated['health_status_timeline'].append({'month': month, 'status': health_status})
        
        return aggregated
    
    def _generate_yearly_preference_questions(self, yearly_data: Dict[str, Any], year: int) -> List[Dict[str, Any]]:
        """
        生成年度习惯与偏好变化问题
        
        Args:
            yearly_data: 整合后的全年数据
            year: 年份
            
        Returns:
            生成的年度问题列表
        """
        import json
        prompt = get_yearly_preference_template(
            year=year,
            all_major_events=yearly_data['all_major_events'],
            all_new_habits=yearly_data['all_new_habits'],
            all_changed_habits=yearly_data['all_changed_habits']
        )
        
        return self._call_llm_for_yearly_questions(prompt, year, 'yearly_preference_habit')
    
    def _generate_yearly_interest_questions(self, yearly_data: Dict[str, Any], year: int) -> List[Dict[str, Any]]:
        """
        生成年度兴趣发展问题
        
        Args:
            yearly_data: 整合后的全年数据
            year: 年份
            
        Returns:
            生成的年度问题列表
        """
        import json
        prompt = get_yearly_interest_template(
            year=year,
            all_major_events=yearly_data['all_major_events'],
            all_focus_areas=yearly_data['all_focus_areas']
        )
        
        return self._call_llm_for_yearly_questions(prompt, year, 'yearly_interest_learning')
    
    def _generate_yearly_emotional_questions(self, yearly_data: Dict[str, Any], year: int) -> List[Dict[str, Any]]:
        """
        生成年度情感成长问题
        
        Args:
            yearly_data: 整合后的全年数据
            year: 年份
            
        Returns:
            生成的年度问题列表
        """
        import json
        prompt = get_yearly_emotional_template(
            year=year,
            all_major_events=yearly_data['all_major_events'],
            all_emotional_events=yearly_data['all_emotional_events']
        )
        
        return self._call_llm_for_yearly_questions(prompt, year, 'yearly_emotional_reflection')
    
    def _generate_yearly_health_questions(self, yearly_data: Dict[str, Any], year: int) -> List[Dict[str, Any]]:
        """
        生成年度健康生活问题
        
        Args:
            yearly_data: 整合后的全年数据
            year: 年份
            
        Returns:
            生成的年度问题列表
        """
        import json
        prompt = get_yearly_health_template(
            year=year,
            all_major_events=yearly_data['all_major_events'],
            exercise_changes_timeline=yearly_data['exercise_changes_timeline'],
            health_status_timeline=yearly_data['health_status_timeline']
        )
        
        return self._call_llm_for_yearly_questions(prompt, year, 'yearly_health_fitness')
    
    def _call_llm_for_yearly_questions(self, prompt: str, year: int, question_type: str) -> List[Dict[str, Any]]:
        """
        调用 LLM 生成年度问题
        
        Args:
            prompt: 提示词
            year: 年份
            question_type: 问题类型
            
        Returns:
            生成的问题列表
        """
        try:
            llm_result = llm_call_j(prompt)
            
            if self.is_print:
                print(f"\n[Yearly LLM Call - {year} - {question_type}] LLM 输出:")
                print(str(llm_result)[:300] + "..." if len(str(llm_result)) > 300 else str(llm_result))
            
            # llm_call_json 已经返回解析后的 JSON
            if isinstance(llm_result, list):
                # 添加年度标识
                for q in llm_result:
                    q['ask_time'] = f"{year}-12-31"  # 年度问题标记为 12 月
                    q['is_yearly'] = True
                return llm_result
            
            print(f"[Yearly LLM Call] {year} - {question_type} 返回格式错误")
            return []
        except Exception as e:
            print(f"[Yearly LLM Call] {year} - {question_type} 调用失败：{e}")
            return []
    
    def _filter_yearly_questions_by_llm(self, questions: List[Dict[str, Any]], year: int) -> List[Dict[str, Any]]:
        """
        使用 LLM 过滤年度问题，保留高质量问题
        
        Args:
            questions: 待过滤的问题列表
            year: 年份
            
        Returns:
            过滤后的问题列表
        """
        if not questions:
            return []
        
        prompt = get_yearly_filter_template(questions, year)
        
        try:
            llm_result = llm_call_j(prompt)
            
            if self.is_print:
                print(f"\n[Yearly Filter - {year}] LLM 过滤输出:")
                print(str(llm_result)[:300] + "..." if len(str(llm_result)) > 300 else str(llm_result))
            
            # llm_call_json 已经返回解析后的 JSON
            selected_indices = llm_result.get('selected_indices', [])
            
            filtered_questions = [questions[i] for i in selected_indices if i < len(questions)]
            print(f"[Yearly Filter - {year}] 从{len(questions)}个年度问题中筛选出{len(filtered_questions)}个")
            return filtered_questions
        except Exception as e:
            print(f"[Yearly Filter] {year} 过滤失败：{e}，保留所有{len(questions)}个年度问题")
            return questions
        
        all_questions = []
        
        # 准备各类问题的输入数据
        major_events_summary = monthly_summary.get('major_events', '')
        
        # 1. 习惯与偏好问题（2-3 个）
        preference_input = {
            'preference_changes': monthly_summary.get('preference_changes', ''),
            'new_habits': monthly_summary.get('new_habits', []),
            'changed_habits': monthly_summary.get('changed_habits', []),
            'major_events': major_events_summary
        }
        preference_questions = self._generate_preference_questions(preference_input, month_key)
        all_questions.extend(preference_questions)
        
        # 2. 兴趣问题（2-3 个）
        interest_input = {
            'interest_changes': monthly_summary.get('interest_changes', ''),
            'focus_areas': monthly_summary.get('focus_areas', []),
            'learning_focus': monthly_summary.get('learning_focus', ''),
            'major_events': major_events_summary
        }
        interest_questions = self._generate_interest_questions(interest_input, month_key)
        all_questions.extend(interest_questions)
        
        # 3. 主要情感事件问题（2-3 个）
        emotional_input = {
            'emotional_events': monthly_summary.get('emotional_events', []),
            'emotional_summary': monthly_summary.get('emotional_summary', ''),
            'major_events': major_events_summary
        }
        emotional_questions = self._generate_emotional_questions(emotional_input, month_key)
        all_questions.extend(emotional_questions)
        
        # 4. 运动健康问题（2-3 个）
        health_input = {
            'health_fitness_changes': monthly_summary.get('health_fitness_changes', ''),
            'exercise_changes': monthly_summary.get('exercise_changes', ''),
            'health_status': monthly_summary.get('health_status', ''),
            'lifestyle_adjustments': monthly_summary.get('lifestyle_adjustments', ''),
            'major_events': major_events_summary
        }
        health_questions = self._generate_health_questions(health_input, month_key)
        all_questions.extend(health_questions)
        
        # Step 5: LLM 过滤
        filtered_questions = self._filter_questions_by_llm(all_questions, month_key)
        
        print(f"[Monthly Questions] {month_key} 最终保留{len(filtered_questions)}个问题")
        return filtered_questions
    
    def _generate_preference_questions(self, input_data: Dict[str, Any], month_key: str) -> List[Dict[str, Any]]:
        """
        生成习惯与偏好类问题
        
        Args:
            input_data: 包含偏好变化、新习惯、改变的习惯和主要事件的输入数据
            month_key: 月份标识
            
        Returns:
            生成的问题列表
        """
        import json
        prompt = get_preference_template(
            month_key=month_key,
            major_events=input_data['major_events'],
            preference_changes=input_data['preference_changes'],
            new_habits=json.dumps(input_data['new_habits'], ensure_ascii=False, indent=2),
            changed_habits=json.dumps(input_data['changed_habits'], ensure_ascii=False, indent=2)
        )
        
        return self._call_llm_for_questions(prompt, month_key, 'preference_habit')
    
    def _generate_interest_questions(self, input_data: Dict[str, Any], month_key: str) -> List[Dict[str, Any]]:
        """
        生成兴趣类问题
        
        Args:
            input_data: 包含兴趣变化、关注领域、学习重点和主要事件的输入数据
            month_key: 月份标识
            
        Returns:
            生成的问题列表
        """
        import json
        prompt = get_interest_template(
            month_key=month_key,
            major_events=input_data['major_events'],
            interest_changes=input_data['interest_changes'],
            focus_areas=json.dumps(input_data['focus_areas'], ensure_ascii=False, indent=2),
            learning_focus=input_data['learning_focus']
        )
        
        return self._call_llm_for_questions(prompt, month_key, 'interest_learning')
    
    def _generate_emotional_questions(self, input_data: Dict[str, Any], month_key: str) -> List[Dict[str, Any]]:
        """
        生成情感事件类问题
        
        Args:
            input_data: 包含情感事件、情感总结和主要事件的输入数据
            month_key: 月份标识
            
        Returns:
            生成的问题列表
        """
        import json
        prompt = get_emotional_template(
            month_key=month_key,
            major_events=input_data['major_events'],
            emotional_events=json.dumps(input_data['emotional_events'], ensure_ascii=False, indent=2),
            emotional_summary=input_data['emotional_summary']
        )
        
        return self._call_llm_for_questions(prompt, month_key, 'emotional_reflection')
    
    def _generate_health_questions(self, input_data: Dict[str, Any], month_key: str) -> List[Dict[str, Any]]:
        """
        生成运动健康类问题
        
        Args:
            input_data: 包含健康变化、运动变化、健康状况、生活调整和主要事件的输入数据
            month_key: 月份标识
            
        Returns:
            生成的问题列表
        """
        prompt = get_health_template(
            month_key=month_key,
            major_events=input_data['major_events'],
            health_fitness_changes=input_data['health_fitness_changes'],
            exercise_changes=input_data['exercise_changes'],
            health_status=input_data['health_status'],
            lifestyle_adjustments=input_data['lifestyle_adjustments']
        )
        
        return self._call_llm_for_questions(prompt, month_key, 'health_fitness')
    
    def _call_llm_for_questions(self, prompt: str, month_key: str, question_type: str) -> List[Dict[str, Any]]:
        """
        调用 LLM 生成问题
        
        Args:
            prompt: 提示词
            month_key: 月份标识
            question_type: 问题类型
            
        Returns:
            生成的问题列表
        """
        try:
            llm_result = llm_call_j(prompt)
            
            if self.is_print:
                print(f"\n[LLM Call - {month_key} - {question_type}] LLM 输出:")
                print(str(llm_result)[:300] + "..." if len(str(llm_result)) > 300 else str(llm_result))
            
            # 处理可能的字符串返回
            if isinstance(llm_result, str):
                # 尝试提取 JSON 数组或对象
                start_idx = llm_result.find('[')
                end_idx = llm_result.rfind(']') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = llm_result[start_idx:end_idx]
                    try:
                        llm_result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"[LLM Call] {month_key} - {question_type} JSON 解析失败：{e}")
                        return []
                else:
                    # 尝试查找对象
                    start_idx = llm_result.find('{')
                    end_idx = llm_result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        json_str = llm_result[start_idx:end_idx]
                        try:
                            parsed = json.loads(json_str)
                            # 如果是包含 questions 字段的对象
                            if isinstance(parsed, dict) and 'questions' in parsed:
                                llm_result = parsed['questions']
                            else:
                                llm_result = parsed
                        except json.JSONDecodeError as e:
                            print(f"[LLM Call] {month_key} - {question_type} JSON 解析失败：{e}")
                            return []
                    else:
                        print(f"[LLM Call] {month_key} - {question_type} 未找到有效的 JSON")
                        return []
            
            # 现在处理解析后的结果
            if isinstance(llm_result, list):
                # 添加月份信息
                for q in llm_result:
                    q['ask_time'] = '2025-12-31'
                return llm_result
            elif isinstance(llm_result, dict) and 'questions' in llm_result:
                # 如果返回的是包含 questions 字段的字典
                questions = llm_result['questions']
                if isinstance(questions, list):
                    for q in questions:
                        q['ask_time'] = '2025-12-31'
                    return questions
            
            print(f"[LLM Call] {month_key} - {question_type} 返回格式错误：{type(llm_result)}")
            return []
        except Exception as e:
            print(f"[LLM Call] {month_key} - {question_type} 调用失败：{e}")
            return []
    
    def _filter_questions_by_llm(self, questions: List[Dict[str, Any]], month_key: str) -> List[Dict[str, Any]]:
        """
        使用 LLM 过滤问题，保留高质量问题
        
        Args:
            questions: 待过滤的问题列表
            month_key: 月份标识
            
        Returns:
            过滤后的问题列表
        """
        if not questions:
            return []
        
        prompt = get_filter_template(questions, month_key)
        
        try:
            llm_result = llm_call_j(prompt)
            
            if self.is_print:
                print(f"\n[Filter - {month_key}] LLM 过滤输出:")
                print(str(llm_result)[:300] + "..." if len(str(llm_result)) > 300 else str(llm_result))
            
            # 处理可能的字符串返回
            if isinstance(llm_result, str):
                # 尝试提取 JSON 对象
                start_idx = llm_result.find('{')
                end_idx = llm_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = llm_result[start_idx:end_idx]
                    try:
                        llm_result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"[Filter] {month_key} JSON 解析失败：{e}")
                        return questions
                else:
                    print(f"[Filter] {month_key} 未找到有效的 JSON 对象")
                    return questions
            
            # 现在 llm_result 应该是字典
            if not isinstance(llm_result, dict):
                print(f"[Filter] {month_key} 返回了非字典类型：{type(llm_result)}")
                return questions
            
            selected_indices = llm_result.get('selected_indices', [])
            
            filtered_questions = [questions[i] for i in selected_indices if i < len(questions)]
            print(f"[Filter - {month_key}] 从{len(questions)}个问题中筛选出{len(filtered_questions)}个")
            return filtered_questions
        except Exception as e:
            print(f"[Filter] {month_key} 过滤失败：{e}，保留所有{len(questions)}个问题")
            return questions
    
    def _save_questions(self, questions: List[Dict[str, Any]], year: str):
        """
        保存问题到文件
        
        Args:
            questions: 问题列表
            year: 年份
        """
        if not self.phone_data_dir:
            print("[Save] phone_data_dir 未设置，跳过保存")
            return
        
        try:
            parent_dir = os.path.dirname(self.phone_data_dir)
            file_path = os.path.join(parent_dir, f"pattern_recognition_qa_{year}.json")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(questions, f, ensure_ascii=False, indent=2)
            
            print(f"\n[Save] 问题已保存到：{file_path}")
            print(f"[Save] 共保存{len(questions)}个问题")
        except Exception as e:
            print(f"[Save] 保存失败：{e}")
    
    def _parallel_filter_and_refine(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        使用 20 线程并行过滤和优化问题
        
        工作流程：
        1. 调用 LLM 分析问题和答案的合理性
        2. 检查答案是否能根据 evidence 字段推理出来，是否存在幻觉
        3. 如果题目可回答但答案不合理，只修改答案
        4. 否则根据 evidence 重新设计题目和答案
        5. 遇到难以修改成合理的问题，直接抛弃
        
        Args:
            questions: 待过滤的问题列表
            
        Returns:
            过滤和优化后的问题列表
        """
        import concurrent.futures
        
        print(f"\n{'='*80}")
        print(f"[Parallel Filter & Refine] 开始并行过滤和优化 {len(questions)} 个问题...")
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
                eval_prompt = f"""
                作为 QA 质量评估专家，请仔细分析以下问答对的质量。
                
                【问题】
                {question.get('question', '')}
                
                【答案】
                {question.get('answer', '')}
                
                【证据数据】
                {json.dumps(question.get('evidence', []), ensure_ascii=False, indent=2)}
                
                **评估任务**
                
                1. **题面合理性检查**
                   - 问题表述是否逻辑清晰、无矛盾？
                   - 问题是否可以已经evidence回答
                   - 问题是否过于简单，不需要整合多个evidence推理分析
                
                2. **答案合理性检查**
                   - 答案是否完整回答了问题？
                   - 答案内部逻辑是否自洽？
                   - 答案中的事实是否与 evidence 中的数据匹配？
                
                3. **可回答性检查（核心）**
                   - 基于现有 evidence，能否准确回答问题？
                   - 关键信息（时间、地点、人物、事件）是否齐全？
                   - 是否存在多个可能的答案？是否有歧义？
                   - 是否需要多步推理？推理过程是否合理？
                
                4. **幻觉检测（核心）**
                   - 答案中是否有 evidence 中没有的信息？
                   - 答案是否在编造不存在的事实？
                   - 答案是否过度推断或臆测？
                
                **决策规则**
                
                情况 A：题目本身不可回答（evidence 不足或无关）
                - 判断标准：evidence 与问题完全不相关，或关键信息严重缺失
                - 处理方式：**尝试根据 evidence 重新设计一个可回答的新问题和新答案**
                - 要求：新问题必须能从所有 evidence 综合分析提取特征才能回答
                - 如果无法设计出合理问题：**直接抛弃该问题**
                
                情况 B：题目可回答，但答案不合理或有幻觉，或可以优化
                - 判断标准：evidence 充足，但答案不准确、不完整或包含幻觉
                - 处理方式：**主要修改答案**，使其与 evidence 一致
                - 可合理修改问题或重新设计问题，增加难度和合理性（如换一种提问方式，换一种提问点，使其更适配已有证据和修改后的答案，且更合理），但必须保留对月份信息的展现
                
                情况 C：题目和答案都合理
                - 判断标准：题面清晰、答案准确、evidence 充足
                - 处理方式：**保持不变**
                
                请以 JSON 格式返回评估结果：
                {{
                    "decision": "keep/modify_answer/redesign/discard",  // 决策类型
                    "analysis": "详细分析（包括题面、答案、可回答性、幻觉检测）",
                    "modified_question": null,  // 在 redesign 或 modify_answer时填写新问题
                    "modified_answer": null,  // 在 modify_answer 或 redesign 时填写新答案
                    "reason": "决策理由"
                }}
                """
                
                # 调用 LLM 进行评估
                llm_result = llm_call_j(eval_prompt)
                #print(f"[Filter Thread {idx + 1}] LLM 评估结果: {llm_result}")
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
                
                decision = llm_result.get('decision', 'keep')
                analysis = llm_result.get('analysis', '')
                reason = llm_result.get('reason', '')
                
                print(f"[Filter Thread {idx + 1}] 决策：{decision}")
                print(f"  理由：{reason[:100]}..." if len(reason) > 100 else f"  理由：{reason}")
                
                # 根据决策执行相应操作
                if decision == 'keep':
                    # 情况 C：保持不变
                    print(f"[Filter Thread {idx + 1}] ✓ 问题质量良好，保留")
                    return idx, question, True
                
                elif decision == 'modify_answer':
                    # 情况 B：只修改答案
                    modified_answer = llm_result.get('modified_answer', '')
                    if modified_answer:
                        question['answer'] = modified_answer
                        print(f"[Filter Thread {idx + 1}] ✓ 答案已修正")
                        return idx, question, True
                    else:
                        print(f"[Filter Thread {idx + 1}] ⚠ 需要修改答案但未提供新答案，保留原问题")
                        return idx, question, True
                
                elif decision == 'redesign':
                    # 情况 A：重新设计问题和答案
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
                        {json.dumps(question.get('evidence', []), ensure_ascii=False, indent=2)[:2000]}{'...' if len(json.dumps(question.get('evidence', []), ensure_ascii=False, indent=2)) > 2000 else ''}
                        
                        **验证要求**
                        1. 新问题是否需要从所有 evidence 综合分析提取特征才能回答？
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
                    # 情况 A：直接抛弃
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
                        print(f"\n[Parallel Filter & Refine] 已完成 {completed}/{len(futures)} 个问题")
                except Exception as e:
                    print(f"[Parallel Filter & Refine] 结果收集异常：{e}")
        
        # 按索引顺序构建结果列表
        filtered_questions = [results_dict[i] for i in range(len(questions)) if i in results_dict]
        
        print(f"\n{'='*80}")
        print(f"[Parallel Filter & Refine] 过滤完成")
        print(f"  - 原始问题数：{len(questions)}")
        print(f"  - 保留问题数：{len(filtered_questions)}")
        print(f"  - 抛弃问题数：{len(questions) - len(filtered_questions)}")
        print(f"{'='*80}")
        
        return filtered_questions
    
    def check_agent(self, question: Dict[str, Any], month_key: str) -> Dict[str, Any]:
        """
        系统性检查对应月的 daily_event 来优化单个问题
            
        Args:
            question: 待检查的单个问题
            month_key: 月份标识，格式为 "YYYY-MM"
                
        Returns:
            优化后的单个问题
        """
        print(f"\n[Check Agent] 开始检查 {month_key} 的问题...")
            
        # 获取该月份的事件数据
        month_events = []
        if isinstance(self.daily_event, list):
            for event in self.daily_event:
                if isinstance(event, dict) and 'date' in event:
                    event_dates = event.get('date', [])
                    if isinstance(event_dates, list):
                        for time_range in event_dates:
                            if '至' in time_range:
                                start_time_str = time_range.split('至')[0].strip()
                                event_date = start_time_str[:10]
                            else:
                                event_date = time_range[:10]
                                
                            # 检查是否在指定月份
                            if event_date.startswith(month_key):
                                month_events.append(event)
                                break
        
        if not month_events:
            print(f"[Check Agent] {month_key} 没有事件数据")
            return question
            
        # 按 7 天为一个窗口分割事件
        windows = self._split_events_into_windows(month_events)
        print(f"[Check Agent] 将 {month_key} 分割为 {len(windows)} 个 7 天窗口")
            
        # 并行分析每个窗口
        window_analyses = self._parallel_analyze_windows(windows, question, month_key)
            
        # 整合分析结果并优化问题
        optimized_question = self._optimize_question(question, window_analyses, month_key)
            
        print(f"[Check Agent] 完成 {month_key} 的问题优化")
        
        # 调用 evidence_refine 生成证据
        print(f"\n[Check Agent] 开始为优化后的问题生成证据...")
        refined_question = self.evidence_refine(optimized_question, month_key)
        print(f"[Check Agent] 完成证据生成")
            
        return refined_question
    
    def _split_events_into_windows(self, events: List[Dict]) -> List[Dict]:
        """
        将事件按 5 天为一个窗口分割
            
        Args:
            events: 事件列表
                
        Returns:
            窗口列表，每个窗口包含事件和日期范围：{"events": [...], "date_range": "2025-10-01 至 2025-10-05"}
        """
        # 按日期排序事件
        def get_event_date(event):
            if isinstance(event, dict) and 'date' in event:
                event_dates = event.get('date', [])
                if isinstance(event_dates, list) and event_dates:
                    time_range = event_dates[0]
                    if '至' in time_range:
                        start_time_str = time_range.split('至')[0].strip()
                        return start_time_str[:10]
                    else:
                        return time_range[:10]
            return '9999-99-99'
            
        sorted_events = sorted(events, key=get_event_date)
            
        windows = []
        current_window = []
        current_window_start_date = None
        current_window_end_date = None
            
        for event in sorted_events:
            event_date = get_event_date(event)
                
            if not current_window:
                current_window = [event]
                current_window_start_date = event_date
                current_window_end_date = event_date
            else:
                # 计算日期差
                import datetime
                try:
                    start_date = datetime.datetime.strptime(current_window_start_date, '%Y-%m-%d')
                    current_date = datetime.datetime.strptime(event_date, '%Y-%m-%d')
                    days_diff = (current_date - start_date).days
                        
                    if days_diff < 5:  # 修改为 5 天窗口
                        current_window.append(event)
                        # 更新窗口结束日期
                        current_window_end_date = event_date
                    else:
                        # 保存当前窗口（带日期范围）
                        windows.append({
                            "events": current_window,
                            "date_range": f"{current_window_start_date}至{current_window_end_date}"
                        })
                        current_window = [event]
                        current_window_start_date = event_date
                        current_window_end_date = event_date
                except ValueError:
                    # 日期格式错误，按事件数量分割
                    if len(current_window) < 5:  # 修改为 5 个事件
                        current_window.append(event)
                    else:
                        windows.append({
                            "events": current_window,
                            "date_range": f"{current_window_start_date}至{current_window_end_date}"
                        })
                        current_window = [event]
                        current_window_start_date = event_date
                        current_window_end_date = event_date
            
        if current_window:
            windows.append({
                "events": current_window,
                "date_range": f"{current_window_start_date}至{current_window_end_date}"
            })
            
        return windows
    
    def _parallel_analyze_windows(self, windows: List[Dict], question: Dict, month_key: str) -> List[Dict]:
        """
        并行分析每个窗口
            
        Args:
            windows: 窗口列表，每个窗口包含 {"events": [...], "date_range": "..."}
            question: 单个问题
            month_key: 月份标识
                
        Returns:
            分析结果列表
        """
        import concurrent.futures
          
            
        analyses = []
            
        def analyze_window(window_data, window_idx):
            """分析单个窗口"""
            import json
            window_events = window_data.get("events", [])
            window_date_range = window_data.get("date_range", "")
            
            prompt = f"""
            作为事件分析专家，请分析以下窗口的事件数据，并与给定的问题进行匹配。
                
            【窗口时间范围】
            {window_date_range}
                
            【窗口事件数据】
            {json.dumps(window_events, ensure_ascii=False, indent=2)}
                
            【问题】
            {json.dumps(question, ensure_ascii=False, indent=2)}
                
            **分析要求**
            1. 分析窗口中的事件，提取与问题相关的事件。注意，只提取与问题有明确关系的事件。当有关系的事件过多时，仅提取最相关的前10个事件。
            2. 指出哪些事件与该问题相关
            3. 评估问题与实际事件的匹配程度
            4. 提供反馈和建议（请结合时间范围 {window_date_range} 内的具体事件）
                
            **输出格式**
            请以 JSON 格式返回分析结果：
            {{
                "window_idx": {window_idx},
                "window_date_range": "{window_date_range}",
                "relevant_events": [
                    {{
                        "event_id": "事件 ID",
                        "event_description": "事件描述",
                        "event_date": "事件日期",
                        "relevance_score": 0.9  // 相关度评分（0-1）
                    }}
                ],
                "feedback": "对问题的反馈和建议（结合时间范围）",
                "matching_score": 0.8  // 匹配度评分（0-1）
            }}
            """
            
            try:
                #print(prompt)
                response = llm_call_j(prompt)
                print(response)
                # 匹配第一个和最后一个 {} 并 load
                if isinstance(response, str):
                    import re
                    match = re.search(r'\{[\s\S]*\}', response)
                    if match:
                        json_str = match.group(0)
                        import json
                        try:
                            result = json.loads(json_str)
                        except json.JSONDecodeError as e:
                            # 第一次解析失败，调用 llm_call_reason_j 重试
                            print(f"[Check Agent] 窗口 {window_idx} JSON 解析失败：{e}，尝试重新调用 LLM...")
                            retry_prompt = prompt
                            response = llm_call_reason_j(retry_prompt)
                            print(f"[Check Agent] 窗口 {window_idx} 重试响应：{response}")
                            
                            # 再次尝试解析
                            if isinstance(response, str):
                                match_retry = re.search(r'\{[\s\S]*\}', response)
                                if match_retry:
                                    json_str_retry = match_retry.group(0)
                                    result = json.loads(json_str_retry)
                                else:
                                    result = {
                                        "window_idx": window_idx,
                                        "relevant_events": [],
                                        "feedback": "重试后仍无法解析",
                                        "matching_score": 0.0
                                    }
                            else:
                                result = response
                    else:
                        result = response
                else:
                    result = response
                
                return result
            except Exception as e:
                print(f"[Check Agent] 窗口 {window_idx} 分析失败：{e}")
                return {
                    "window_idx": window_idx,
                    "relevant_events": [],
                    "feedback": "分析失败",
                    "matching_score": 0.0
                }
        
        # 并行处理窗口
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_window = {
                executor.submit(analyze_window, window, idx): idx
                for idx, window in enumerate(windows)
            }
            
            for future in concurrent.futures.as_completed(future_to_window):
                window_idx = future_to_window[future]
                try:
                    analysis = future.result()
                    analyses.append(analysis)
                    print(f"[Check Agent] 完成窗口 {window_idx} 的分析")
                except Exception as e:
                    print(f"[Check Agent] 窗口 {window_idx} 处理失败：{e}")
        
        return analyses
    
    def _optimize_question(self, question: Dict, window_analyses: List[Dict], month_key: str) -> Dict[str, Any]:
        """
        整合分析结果并优化单个问题
            
        Args:
            question: 原始问题
            window_analyses: 窗口分析结果
            month_key: 月份标识
                
        Returns:
            优化后的单个问题
        """
        # 整合所有分析结果
        all_relevant_events = []
        feedback_with_dates = []
            
        for analysis in window_analyses:
            all_relevant_events.extend(analysis.get('relevant_events', []))
            # 提取日期范围和反馈
            date_range = analysis.get('window_date_range', '')
            feedback = analysis.get('feedback', '')
            if date_range and feedback:
                feedback_with_dates.append(f"{date_range}：{feedback}")
        import json
                
        # 构建带时间标注的分析结果字典
        analysis_result = {
            "relevant_events_with_time": [
                {
                    "event_id": event.get("event_id", ""),
                    "event_description": event.get("event_description", ""),
                    "event_date": event.get("event_date", ""),
                }
                for event in all_relevant_events
            ],
            "feedback_summary": feedback_with_dates  # 带日期范围的反馈列表
        }
                
        # 生成优化提示
        prompt = f"""
        作为问题优化专家，请基于以下分析结果，对单个问题进行深度优化和重新设计。
                                        
        【原始问题】
        {json.dumps(question, ensure_ascii=False, indent=2)}
                                        
        【分析结果】
        {json.dumps(analysis_result, ensure_ascii=False, indent=2)}
                                        
        **重要说明**
        分析结果中 `relevant_events_with_time` 字段提取的事件**并不一定都是与问题直接相关的重要事件**。这些事件只是从窗口分析中初步收集到的候选事件，其中可能包含：
        - 与问题关联度不高或完全无关的事件
        - 信息重复或冗余的事件
        - 不适合用于设计高质量问题的事件
                        
        因此，你需要**自行判断和筛选**，从分析结果中找出真正与问题相关、有价值的关键事件，并基于这些事件重新设计问题。
                                        
        **首要任务：评估并调整问题**
        在开始优化之前，请先评估提供的事件数据是否足以回答该问题：
        1. **检查关键信息**：分析原始问题和答案需要哪些关键信息
        2. **验证事件覆盖**：检查提供的事件是否包含这些关键信息
        3. **判断充分性**：
           - **如果事件数据充足**：继续优化原始问题
           - **如果事件数据不足**：**改写问题以匹配现有事件数据**
                
        **情况一：事件数据不足时，主动改写问题**
        - 分析现有事件数据主要反映了什么内容（例如：跑步频率、训练时长、运动类型等）
        - 将原始问题改写为一个可以用现有事件数据回答的问题
        - 保持问题的自然性和真实性，使用第一人称
        - 示例：
          - 原始问题："我这个月的体重变化如何？"
          - 现有事件：只有跑步训练记录，没有体重数据
          - 改写后："我这个月的跑步频率有什么变化？"
                  
        **情况二：事件数据充足时，正常优化，不需大幅度调整问题**
        - 继续进行问题优化，确保以下几点：
        1. **筛选关键事件**：从【分析结果】的 `relevant_events_with_time` 中，仔细判断并筛选出真正与问题相关的重点事件，不要盲目使用所有列出的事件
        2. **整合时间信息**：继续筛选出的关键事件的信息进行整合，分析问题和答案是否需要修正优化，使 QA 建立在真实数据基础上
        3. **优化问题表述**：修正问题表述，使其更自然、更符合用户真实提问方式，以最小信息量表述问题，题面不要出现冗余信息
        4. **校正答案内容**：确保答案准确反映用户的实际生活数据和对应的时间段
        5. **标注事件依据**：将筛选出的关键事件的 id 增加到 required_events_id，明确标注问题所需的事件依据
        6. **提供评分要点**：提供清晰的评分要点，说明回答该问题需要覆盖的关键信息
        7. **规范输出格式**：规范化问题格式，确保符合输出要求
                                        
        **输出格式**
        请以 JSON 格式返回优化后的问题（必须包含以下字段）：
        {{
            "question": "优化后的问题（使用第一人称'我'，表述自然真实）。如果原始问题无法用现有事件数据回答，则改写为一个可以用现有事件回答的问题",
            "answer": "准确的答案（基于筛选出的关键事件和时间段）",
            "score_points": [
                {{
                    "description": "评分要点描述（回答该问题需要覆盖的关键信息点）",
                    "score": 10
                }}
            ],
            "required_events_id": ["事件 ID1", "事件 ID2"],  // 必须是经过你判断筛选后认为真正相关的关键事件 ID
            "question_type": "ND",
            "evidence": []
        }}
                
        **改写问题的原则**
        - 只在实际数据无法支撑原始问题时才改写
        - 改写后的问题应该：
          1. 与现有事件数据高度相关
          2. 保持自然真实的提问方式
          3. 能够考察用户的习惯、偏好、兴趣、情感或健康变化
          4. 具有一定难度，不是简单的信息查询
        - 示例：
          ✅ 原始："我这个月减了多少斤？" → 改写："我这个月的运动频率有什么变化？"
          ✅ 原始："我吃了什么药？" → 改写："我这个月去医院复查的情况如何？"
          ❌ 不要改成："我今天做了什么？"（太简单）
        """
            
        try:
            response = llm_call_j(prompt)
            print(response)
            # 匹配第一个和最后一个 {} 并 load
            if isinstance(response, str):
                import re
                match = re.search(r'\{[\s\S]*\}', response)
                if match:
                    json_str = match.group(0)
                    import json
                    result = json.loads(json_str)
                else:
                    result = response
            else:
                result = response
                        
            # 检查 LLM 是否认为事件数据不足
            if isinstance(result, dict):
                if result.get('skip') == True:
                    reason = result.get('reason', '事件数据不足以回答该问题')
                    print(f"[Check Agent] 事件数据不足，放弃生成问题：{reason}")
                    return None  # 返回 None 表示应该跳过该问题
                elif 'question' in result:
                    print(f"[Check Agent] 成功优化问题")
                    return result
                else:
                    print("[Check Agent] 优化结果格式错误")
                    return question
            else:
                print("[Check Agent] 优化结果不是字典格式")
                return question
        except Exception as e:
            print(f"[Check Agent] 优化问题失败：{e}")
            return question

    def evidence_refine(self, question: Dict[str, Any], month_key: str) -> Dict[str, Any]:
        """
        Evidence Refine: 分析并优化问题的证据数据，确保手机数据能够充足反映事件并提供足够回答问题的数据

        Args:
            question: 优化后的问题
            month_key: 月份标识

        Returns:
            优化证据后的问题
        """
        print(f"\n[Evidence Refine] 开始优化 {month_key} 的证据数据...")

        # 获取 required_events_id 列表
        required_events_ids = question.get('required_events_id', [])
        if not required_events_ids:
            print("[Evidence Refine] 无需补充证据数据")
            return question

        # 初始化操作列表
        to_generate = []
        to_delete = []
        
        # 定义允许的操作类型
        ALLOWED_OP_TYPES = {'sms', 'phonecall', 'photo', 'push', 'note', 'calendar'}
        
        # 准备所有需要分析的事件任务
        analysis_tasks = []
        for event_id in required_events_ids:
            analysis_tasks.append({
                'event_id': event_id,
                'question': question
            })
        
        print(f"[Evidence Refine] 使用 20 线程并行分析 {len(analysis_tasks)} 个事件...")
        
        # 并行分析函数
        def analyze_single_event(task_data):
            """分析单个事件的证据数据"""
            event_id = task_data['event_id']
            question = task_data['question']
            
            # 在 daily_event 中查找对应事件
            target_event = None
            if isinstance(self.daily_event, list):
                for event in self.daily_event:
                    event_id_in_event = event.get('event_id', '')
                    if str(event_id_in_event) == str(event_id):
                        target_event = event
                        break
                    # 也检查一下整数类型
                    try:
                        if int(event_id_in_event) == int(event_id):
                            target_event = event
                            break
                    except (ValueError, TypeError):
                        pass
            
            if not target_event:
                print(f"[Evidence Refine - {event_id}] 未找到事件，跳过")
                return [], []
                    
            # 获取事件信息
            event_date = target_event.get('date', [])
            event_description = target_event.get('description', '')
                        
            # 从手机数据中查找与该事件对应的数据（基于 event_id 匹配）
            existing_evidence = []
            if self.phonedata:
                with self.phonedata_lock:  # 加锁保护共享数据
                    for data_type, data_list in self.phonedata.items():
                        if isinstance(data_list, list):
                            for item in data_list:
                                if isinstance(item, dict):
                                    # 检查 daily_event_id 或 related_event 字段
                                    item_event_id = str(item.get('daily_event_id', ''))
                                    related_event = str(item.get('related_event', ''))
                                                
                                    # 如果匹配，添加完整的操作数据
                                    if item_event_id == str(event_id) or related_event == str(event_id):
                                        existing_evidence.append({
                                            'type': data_type,
                                            'data': item,
                                            'phone_id': item.get('phone_id', '')
                                        })

            print(f"[Evidence Refine - {event_id}] 找到 {len(existing_evidence)} 条现有相关数据")
                        
            # 使用 LLM 分析现有数据是否充足，以及需要增删哪些数据
            analysis_prompt = f"""
            作为数据分析师，请分析以下事件、问题和现有证据。
                        
            【任务背景】
            您正在为问题的回答设计证据。这些证据是手机操作数据（包括短信、通话、照片、推送通知、笔记、日历等），手机智能助手会基于这些手机操作推理并回答问题。
                        
            现在正在分析回答该问题的一个子事件。**请注意**：
            - 我们提供的手机数据只是与该事件有关的数据
            - 这个事件只是用来回答问题的众多事件中的其中一个
            - **不需要检查手机数据能否回答整个问题**
            - **只需要分析这个事件的重要信息是否都手机数据被表现并反映出来**
                        
            【问题与答案】
            - 问题：{question.get('question', '')}
            - 答案：{question.get('answer', '')[:500]}{'...' if len(question.get('answer', '')) > 500 else ''}
                        
            【事件信息】
            - 事件 ID: {event_id}
            - 事件描述：{event_description}
            - 事件日期：{json.dumps(event_date, ensure_ascii=False)}
                        
            【现有手机数据证据】（共{len(existing_evidence)}条）
            {json.dumps([{'type': ev['type'], 'phone_id': ev['phone_id'], 'data_summary': str(ev['data'])[:200]} for ev in existing_evidence], ensure_ascii=False, indent=2)}
                        
            【可生成的数据类型】
            sms, phonecall, photo, push, note, calendar
                        
            **重要原则**
            1. **非必要不生成**：只有当十分确定缺乏关键信息，或缺乏足以支持回答的信息时，才考虑新增。若已有数据能大致反映事件则不用新增。**能不生成就不生成**。
            2. **重点优先**：不需要全面反映出事件的所有细节，只关注与问题相关的重点内容。
               - 例如：问题可能只问跑步频率，那只要手机数据能反映出用户跑步了就行，至于距离、时间可以不关心
               - 例如：如果问题问了跑量，则需要反映公里数
            3. **互补性原则**：如果要生成新数据，必须与已有数据形成互补关系，不要和已有数据反映同样的信息。
               - **检查已有数据**：先看看已经有了什么信息
               - **补充缺失信息**：只生成能提供新信息的数据
               - **避免重复**：**严禁**生成与已有数据内容重复或高度相似的数据
               - **示例**：
                 - ✅ 已有一条短信提到"今天跑了 5 公里"，但缺少具体时间 → 生成推送"您于 07:30 完成晨跑 5 公里"
                 - ❌ 已有短信"今天跑了 5 公里"，又生成笔记"今天早上我跑了 5 公里"（信息重复）
            4. **最小信息量**：当要新增手机数据时：
               - 先分析缺少的具体信息是什么
               - 只生成包含缺少信息的数据，不要在数据中反映所有信息
               - **禁止**生成一个包含了事件所有信息或可以直接反映答案的充足数据（如一个反映了所有信息的笔记/信息）
               - **示例**：
                 - ✅ 缺少跑步公里数：生成短信"今天跑了 5 公里"或推送"你今日已运动 5 公里，十分健康"
                 - ❌ 不要生成：详细的跑步笔记，包含时间、路线、配速、心率等完整信息
            5. **谨慎删除**：**除非数据明显不合理，否则不要删除手机数据**。仅在数据存在明显错误或矛盾情况下考虑删除，有些数据是合理的噪声：
                
            
            **分析任务**
            1. 现有手机数据是否充分反映了该事件的关键信息？
            2. 该事件的重要信息是否都在手机数据中有所体现？
            3. 如果不足，最需要补充哪些关键数据来完整展现该事件？（尽可能少地增加）
            4. 如果有与该事件不相关或冗余的数据，应该删除哪些？
                        
            **输出格式**
            请以 JSON 格式返回：
            {{
                "sufficiency_analysis": "对现有数据是否充分反映该事件的分析",
                "to_generate": [
                    {{
                        "type": "sms/phonecall/photo/push/note/calendar",
                        "content_summary": "数据内容描述（用于生成具体数据，只包含缺少的关键信息，保持最小信息量）",
                        "reason": "为什么需要这个数据来反映该事件的哪个重要信息，以及为何现有数据不足"
                    }}
                ],
                "to_delete": [
                    {{
                        "type": "数据类型",
                        "phone_id": "数据 ID",
                        "reason": "为什么要删除（与该事件不相关/冗余/错误等）"
                    }}
                ],
                "rationale": "数据分析理由"
            }}
            """
                    
            try:
                llm_result = llm_call_j(analysis_prompt)
                        
                # 解析 LLM 结果
                if isinstance(llm_result, str):
                    start_idx = llm_result.find('{')
                    end_idx = llm_result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        llm_result = json.loads(llm_result[start_idx:end_idx])
                        
                if isinstance(llm_result, dict):
                    # 收集需要生成的数据
                    event_to_generate = []
                    for gen_item in llm_result.get('to_generate', []):
                        gen_item['target_event_id'] = event_id
                        event_to_generate.append(gen_item)
                            
                    # 收集需要删除的数据
                    event_to_delete = llm_result.get('to_delete', [])
                            
                    print(f"[Evidence Refine - {event_id}] 分析完成")
                    print(f"  - 现有数据：{len(existing_evidence)} 条")
                    print(f"  - 需要生成：{len(event_to_generate)} 条数据")
                    print(f"  - 需要删除：{len(event_to_delete)} 条数据")
                    
                    return event_to_generate, event_to_delete
                else:
                    return [], []
                            
            except Exception as e:
                print(f"[Evidence Refine - {event_id}] 分析失败：{e}")
                return [], []
        
        # 使用 ThreadPoolExecutor 并行处理，最多 20 个线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # 提交所有任务
            futures = [executor.submit(analyze_single_event, task) for task in analysis_tasks]
            
            # 收集结果
            for future in concurrent.futures.as_completed(futures):
                try:
                    event_to_generate, event_to_delete = future.result()
                    to_generate.extend(event_to_generate)
                    to_delete.extend(event_to_delete)
                except Exception as e:
                    print(f"[Evidence Refine] 分析任务异常：{e}")
        
        print(f"\n[Evidence Refine] 所有事件分析完成")
        print(f"  - 共待生成：{len(to_generate)} 条")
        print(f"  - 共待删除：{len(to_delete)} 条")

        # 执行数据操作
        print(f"\n[Evidence Refine] 开始执行数据操作...")
        print(f"  - 待生成：{len(to_generate)} 条")
        print(f"  - 待删除：{len(to_delete)} 条")

        # 1. 执行删除操作
        if to_delete:
            print(f"\n[Evidence Refine] === 开始执行删除操作 ===")
            with self.phonedata_lock:
                for del_item in to_delete:
                    op_type = del_item.get('type', 'unknown')
                    phone_id = del_item.get('phone_id', '')
                    reason = del_item.get('reason', '')
                    
                    print(f"\n准备删除：{op_type}:{phone_id}")
                    print(f"  原因：{reason}")

                    if op_type in self.phonedata:
                        original_len = len(self.phonedata[op_type])
                        
                        # 找到要删除的数据并打印详情
                        for op in self.phonedata[op_type]:
                            if str(op.get('phone_id', '')) == str(phone_id):
                                print(f"  删除数据详情:")
                                print(f"    {json.dumps(op, ensure_ascii=False, indent=2)}")
                                break
                        
                        # 执行删除
                        self.phonedata[op_type] = [
                            op for op in self.phonedata[op_type]
                            if str(op.get('phone_id', '')) != str(phone_id)
                        ]

                        if len(self.phonedata[op_type]) < original_len:
                            print(f"  ✓ 已成功删除 {op_type}:{phone_id}\n")

        # 2. 执行生成操作（仅生成必需的数据）
        generated_operations = []
        if to_generate:
            print(f"\n[Evidence Refine] === 开始执行生成操作 ===")
            print(f"[Evidence Refine] 使用 20 线程并行处理 {len(to_generate)} 个生成任务...")

            # 定义允许的 operative types
            ALLOWED_OP_TYPES = {'sms', 'phonecall', 'photo', 'push', 'note', 'calendar'}
            
            # 准备所有需要生成的任务
            generation_tasks = []
            for gen_item in to_generate:
                op_type = gen_item.get('type', 'sms')
                
                # 验证类型是否在允许列表中
                if op_type not in ALLOWED_OP_TYPES:
                    print(f"[Evidence Refine] 警告：'{op_type}' 不是允许的操作类型，跳过")
                    continue
                
                content_summary = gen_item.get('content_summary', '')
                target_event_id = gen_item.get('target_event_id', '')
                reason = gen_item.get('reason', '')
                
                # 在 phonedata 中查找目标事件的上下文
                target_event = None
                if isinstance(self.daily_event, list):
                    for event in self.daily_event:
                        if event.get('event_id') == target_event_id:
                            target_event = event
                            break
                
                # 创建临时事件用于生成
                temp_event = {
                    'question': question.get('question', ''),
                    'target_event': target_event or {}
                }
                
                # 使用 content_summary 作为 generation_hint
                generation_hint = f"""
                请生成{op_type}类型的数据，要求：{content_summary}

                注意：这是为了支持事件 {target_event_id} 的证据数据，请确保数据准确反映该事件。
                可生成的数据类型仅限于：sms, phonecall, photo, push, note, calendar
                """
                
                generation_tasks.append({
                    'gen_item': gen_item,
                    'op_type': op_type,
                    'temp_event': temp_event,
                    'generation_hint': generation_hint,
                    'target_event_id': target_event_id,
                    'reason': reason,
                    'content_summary': content_summary
                })
            
            # 并行生成函数
            def generate_single_task(task_data):
                """生成单个任务的手机操作数据"""
                op_type = task_data['op_type']
                temp_event = task_data['temp_event']
                generation_hint = task_data['generation_hint']
                target_event_id = task_data['target_event_id']
                reason = task_data['reason']
                content_summary = task_data['content_summary']
                
                try:
                    print(f"\n准备生成：{op_type}")
                    print(f"  目标事件 ID: {target_event_id}")
                    print(f"  生成原因：{reason}")
                    print(f"  内容要求：{content_summary[:100]}...")
                    
                    # 使用 PhoneOperationGenerator 生成
                    operations = self.phone_op_generator.generate(
                        operation_type=op_type,
                        original_event=temp_event,
                        question=question.get('question', ''),
                        generation_hint=generation_hint
                    )
                    
                    if operations:
                        print(f"  ✓ 已生成 {len(operations)} 条 {op_type} 数据")
                        return operations
                    else:
                        print(f"  ⚠ 未生成任何 {op_type} 数据")
                        return []
                except Exception as e:
                    print(f"  ✗ 生成失败：{e}")
                    return []
            
            # 使用 ThreadPoolExecutor 并行处理，最多 20 个线程
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                # 提交所有任务
                futures = [executor.submit(generate_single_task, task) for task in generation_tasks]
                
                # 收集结果
                for future in concurrent.futures.as_completed(futures):
                    try:
                        operations = future.result()
                        generated_operations.extend(operations)
                    except Exception as e:
                        print(f"[Evidence Refine] 生成任务异常：{e}")
            
            # 打印生成的每条数据详情
            if generated_operations:
                print(f"\n[Evidence Refine] 生成完成，共 {len(generated_operations)} 条数据")
                for i, op in enumerate(generated_operations[:5], 1):  # 只显示前 5 条
                    op_type = op.get('type', '')
                    print(f"\n  生成的第 {i} 条数据 ({op_type}):")
                    print(f"    type: {op.get('type', '')}")
                    print(f"    daily_event_id: {op.get('daily_event_id', '')}")
                    print(f"    datetime: {op.get('datetime', '')}")
                    # 根据类型打印特定字段
                    if op_type == 'sms':
                        print(f"    contactName: {op.get('contactName', '')}")
                        print(f"    phoneNumber: {op.get('phoneNumber', '')}")
                        print(f"    message_content: {op.get('message_content', '')[:100]}...")
                    elif op_type == 'phonecall':
                        print(f"    contactName: {op.get('contactName', '')}")
                        print(f"    phoneNumber: {op.get('phoneNumber', '')}")
                        print(f"    call_result: {op.get('call_result', '')}")
                    elif op_type == 'photo':
                        print(f"    title: {op.get('title', '')}")
                        print(f"    caption: {op.get('caption', '')[:100]}...")
                        loc = op.get('location', {})
                        if isinstance(loc, dict):
                            print(f"    location: {loc.get('poi', '')} - {loc.get('city', '')}")
                    elif op_type == 'push':
                        print(f"    title: {op.get('title', '')}")
                        print(f"    content: {op.get('content', '')[:100]}...")
                        print(f"    source: {op.get('source', '')}")
                    elif op_type == 'note':
                        print(f"    title: {op.get('title', '')}")
                        print(f"    content: {op.get('content', '')[:100]}...")
                    elif op_type == 'calendar':
                        print(f"    title: {op.get('title', '')}")
                        print(f"    description: {op.get('description', '')[:100]}...")
                        print(f"    start_time: {op.get('start_time', '')}")
                        print(f"    end_time: {op.get('end_time', '')}")
                
                if len(generated_operations) > 5:
                    print(f"\n  ... 还有 {len(generated_operations) - 5} 条数据未显示")

            # 添加到 phonedata
            if generated_operations:
                print(f"\n[Evidence Refine] 将生成的 {len(generated_operations)} 条数据添加到 phonedata")
                self._add_operations_to_phonedata(generated_operations)

        # 更新问题的 evidence 字段
        # 重新收集所有事件的最新证据（因为 phonedata 已经被更新）
        updated_evidence = []
                
        print(f"\n[Evidence Refine] 重新收集所有事件的证据...")
                
        # 遍历所有必需的事件 ID，收集最新的证据
        for event_id in required_events_ids:
            # 在 daily_event 中查找对应事件
            target_event = None
            if isinstance(self.daily_event, list):
                for event in self.daily_event:
                    if str(event.get('event_id', '')) == str(event_id):
                        target_event = event
                        break
                    
            if not target_event:
                continue
                    
            # 从手机数据中查找与该事件对应的数据（基于 event_id 匹配）
            if self.phonedata:
                for data_type, data_list in self.phonedata.items():
                    if isinstance(data_list, list):
                        for item in data_list:
                            if isinstance(item, dict):
                                # 检查 daily_event_id 或 related_event 字段
                                item_event_id = str(item.get('daily_event_id', ''))
                                related_event = str(item.get('related_event', ''))
                                        
                                # 如果匹配，添加到 updated_evidence
                                if item_event_id == str(event_id) or related_event == str(event_id):
                                    updated_evidence.append(item)
                
        # 更新问题的 evidence 字段
        question['evidence'] = updated_evidence
        
        print(f"\n[Evidence Refine] 证据优化完成")
        print(f"  - 最终证据：{len(updated_evidence)} 条")

        return question
