# -*- coding: utf-8 -*-
"""
时序 QA 生成器
主要生成时序问题和涉及知识变动记忆更新的问题
包含三个Agent：
1. 时序问题生成 Agent (Temporal Sequence Agent)
2. 次数统计问题生成 Agent (Frequency Count Agent)
3. 知识更新问题生成 Agent (Knowledge Update Agent)
"""

import json
import os
import random
import time
from typing import List, Dict, Any, Tuple
import threading
import concurrent.futures

from src.lifebench.utils.llm_call import llm_call_j, llm_call_reason_j
from .base_generator import BaseQAGenerator
from .phone_operation_generator import PhoneOperationGenerator


class QATemporalGenerator(BaseQAGenerator):
    def __init__(self, persona_data: Dict[str, Any] = None, event_tree: Dict[str, Any] = None,
                 daily_event: Dict[str, Any] = None, draft_event: Dict[str, Any] = None,
                 special_event: Dict[str, Any] = None, phone_data_dir: str = None,
                 is_print: bool = True, year: int = 2025):
        """
        初始化时序 QA 生成器

        Args:
            persona_data: 用户画像数据
            event_tree: 事件树数据
            daily_event: 每日事件数据
            draft_event: 草稿事件数据
            special_event: 特殊事件数据
            phone_data_dir: 手机数据目录路径
            is_print: 是否打印调试信息
            year: 年份，默认 2025
        """
        super().__init__(persona_data=persona_data, event_tree=event_tree,
                        daily_event=daily_event, draft_event=draft_event,
                        special_event=special_event, phone_data_dir=phone_data_dir)
        self.is_print = is_print
        self.year = year
    
    def _generate_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        """
        基于 draft_event 提取月份的重要事件（带具体时间）
        
        Args:
            year: 年份
            month: 月份
            
        Returns:
            月份重要事件列表
        """
        month_key = f"{year}-{month:02d}"
        print(f"\n[Monthly Summary] 提取 {month_key} 的重要事件...")
        
        # 获取该月份的 draft_event 数据
        month_events = self.draft_event.get(month_key, [])
        
        if not month_events or not isinstance(month_events, list):
            print(f"[Monthly Summary] {month_key} 没有事件数据")
            return None
        
        prompt = f"""
        作为月度事件总结专家，请分析以下 {month_key} 的生活记录数据，输出用户本月主要做了什么。
        
        【月份数据】
        {json.dumps(month_events, ensure_ascii=False, indent=2)}
        
        **核心要求**
        - **叙述性总结**：以"用户这个月主要做了什么"的角度进行总结
        - **包含重要事件**：出行、娱乐、工作成就、等重要活动都要包含
        - **数量限制**：只输出 10 个最主要的事件
        - **独立性保证**：输出的事件之间不应存在可合并的步骤关系，请你分析已有事件的关联，可以把他们合并为一个连贯的事件输出。
        - 优先按独特性排序，这个月同类型事件只发生过一次的优先提取（如去云南旅行，去北京出差等），发生过多次的优先级较低（如跑步，工作）。
        
        **提取标准**
        1. **出行旅游事件**：短途旅行、长途旅游、出差等
        2. **娱乐休闲事件**：看电影、演唱会、聚会、运动比赛等
        3. **工作学习事件**：完成项目、考试、培训、技能提升等
        4. **健康医疗事件**：体检、治疗、健身突破等
        5. **社交人际事件**：重要聚会、拜访亲友、参加活动等
        6. **其他重要事件**：购物大件、搬家整理、特殊体验等
        
        **排除标准**
        ❌ 不要提取日常琐事（普通用餐、通勤、日常购物等）
        ❌ 不要提取规划性事件（计划但未执行的活动）
        ❌ 不要提取具有步骤关系的事件（如预约+执行应合并为一个）
        
        **事件独立性原则**
        ⚠️ **关键要求**：输出的 10 个事件必须是相互独立的，不存在可合并的步骤关系
        
        ✅ **正确示例**（独立事件）：
        - "云南五日游" （已合并机票、酒店、游览等步骤）
        - "参加半程马拉松比赛"
        - "完成Python入门课程学习"
        - "与朋友去KTV庆祝生日"
        
        ❌ **错误示例**（存在步骤关系，应合并）：
        - 事件1："预约了按摩" + 事件2："去按摩店按摩" → 应合并为"进行了按摩理疗"
        - 事件1："购买了去北京的机票" + 事件2："在北京游览故宫" → 应合并为"北京三日游"
        
        **输出要求**
        1. **数量限制**：严格输出 10 个事件（如果不足10个重要事件，可以少于10个）
        2. **事件描述**：简洁明了，突出主干内容，体现用户做了什么
        3. **时间段表示**：
           - 单日活动："YYYY-MM-DD"
           - 多日连贯活动："YYYY-MM-DD 至 YYYY-MM-DD"
        4. **优先级排序**：按重要性排序，最重要的事件排在前面
        
        请以 JSON 格式返回数组：
        [
            {{
                "date": "YYYY-MM-DD 或 YYYY-MM-DD 至 YYYY-MM-DD",
                "event_description": "事件描述（简洁突出用户做了什么）"
            }}
        ]
        
        **示例**
        [
            {{"date": "2025-03-10 至 2025-03-15", "event_description": "云南五日游，游览大理和丽江"}},
            {{"date": "2025-03-15", "event_description": "参加半程马拉松比赛，成绩2小时10分"}},
            {{"date": "2025-03-08", "event_description": "进行了全身按摩理疗，缓解肩颈疲劳"}},
            {{"date": "2025-03-20", "event_description": "完成了Python入门课程学习"}},
            {{"date": "2025-03-25", "event_description": "与朋友去KTV庆祝生日"}}
        ]
        """
        
        try:
            llm_result = llm_call_j(prompt)
            
            if self.is_print:
                print(f"\n[Monthly Summary - {month_key}] LLM 输出:")
                print(llm_result[:300] + "..." if len(llm_result) > 300 else llm_result)
            
            # 解析结果
            if isinstance(llm_result, str):
                start_idx = llm_result.find('[')
                end_idx = llm_result.rfind(']') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = llm_result[start_idx:end_idx]
                    try:
                        important_events = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"[Monthly Summary - {month_key}] JSON 解析失败：{e}")
                        return None
                else:
                    print(f"[Monthly Summary - {month_key}] 未找到有效的 JSON 数组")
                    return None
            elif isinstance(llm_result, list):
                important_events = llm_result
            elif isinstance(llm_result, dict):
                important_events = llm_result.get('important_events', [])
            else:
                print(f"[Monthly Summary - {month_key}] 返回格式错误：{type(llm_result)}")
                return None
            
            if not isinstance(important_events, list):
                print(f"[Monthly Summary - {month_key}] important_events 不是列表")
                return None
            
            summary = {
                'month': month_key,
                'important_events': important_events,
                'event_count': len(important_events)
            }
            
            print(f"[Monthly Summary] {month_key} 提取了 {len(important_events)} 个重要事件")
            return summary
                
        except Exception as e:
            print(f"[Monthly Summary - {month_key}] 提取失败：{e}")
            return None
    
    def _generate_yearly_summaries(self, year: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        并行生成全年各月份的总结并分析相似事件
        
        Args:
            year: 年份
            
        Returns:
            (月份总结列表, 事件分组结果)
        """
        print(f"\n========== 开始生成 {year} 年各月总结 ==========")
        
        monthly_summaries = []
        
        # 使用 ThreadPoolExecutor 并行处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
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

        # Step 2: 为每个事件添加相似事件分析
        print(f"\n========== 开始为每个事件分析相似事件 ==========")
        monthly_summaries = self._find_similar_events_for_all(monthly_summaries, year)
        print(f"========== 相似事件分析完成 ==========")

        return monthly_summaries, {}

    def _find_similar_events_for_all(self, monthly_summaries: List[Dict[str, Any]], year: int) -> List[Dict[str, Any]]:
        """
        并行为每个重要事件查找相似事件（可能混淆的事件）

        Args:
            monthly_summaries: 每月总结列表
            year: 年份

        Returns:
            添加了相似事件的每月总结列表
        """
        # 收集所有需要分析的事件及其上下文
        all_events_to_analyze = []
        for summary in monthly_summaries:
            month = summary.get('month', '')
            important_events = summary.get('important_events', [])
            for event in important_events:
                all_events_to_analyze.append({
                    'month': month,
                    'date': event.get('date', ''),
                    'event_description': event.get('event_description', ''),
                    'original_event': event
                })

        if not all_events_to_analyze:
            print("[Similar Events] 没有事件需要分析")
            return monthly_summaries

        print(f"[Similar Events] 共有 {len(all_events_to_analyze)} 个事件需要分析")

        # 并行处理所有事件
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_event = {
                executor.submit(self._find_similar_events_for_single_event, item, year): item
                for item in all_events_to_analyze
            }

            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_event):
                item = future_to_event[future]
                try:
                    similar_events = future.result()
                    # 将结果更新到原事件中
                    item['original_event']['similar_events'] = similar_events
                    completed_count += 1
                    if completed_count % 10 == 0 or completed_count == len(all_events_to_analyze):
                        print(f"[Similar Events] 已完成 {completed_count}/{len(all_events_to_analyze)} 个事件的相似分析")
                except Exception as e:
                    print(f"[Similar Events] 事件分析失败：{e}")
                    item['original_event']['similar_events'] = []

        return monthly_summaries

    def _find_similar_events_for_single_event(self, event_item: Dict[str, Any], year: int) -> List[Dict[str, Any]]:
        """
        为单个事件查找相似事件（可能与之混淆的事件）

        Args:
            event_item: 事件项，包含 month, date, event_description, original_event
            year: 年份

        Returns:
            相似事件列表
        """
        target_event = event_item.get('event_description', '')
        target_date = event_item.get('date', '')
        target_month = event_item.get('month', '')

        # 收集除当前月之外的所有月份的每日事件数据（原始 daily_draft 格式）
        other_months_daily_data = {}
        for month_key, month_data in self.draft_event.items():
            if not month_key.startswith(str(year)):
                continue
            if month_key == target_month:
                continue
            if not isinstance(month_data, list):
                continue

            # 只保留有事件的日期
            days_with_events = []
            for day_data in month_data:
                events = day_data.get('events', [])
                if events and len(events) > 0:
                    days_with_events.append(day_data)

            if days_with_events:
                other_months_daily_data[month_key] = days_with_events

        if not other_months_daily_data:
            return []

        # 构建 prompt，让 LLM 先聚合每月多日活动，再找相似事件
        prompt = f"""
        作为事件相似性分析专家，请完成以下任务：

        【目标事件】
        - 日期：{target_date}
        - 描述：{target_event}

        【其他月份每日事件数据】（原始格式，遍历每天的事件）
        {json.dumps(other_months_daily_data, ensure_ascii=False, indent=2)}

        **任务一：聚合每月多日活动**
        遍历每天的事件数据，根据目标事件的粒度决定是否需要聚合：
        - **如果目标事件是粒度较粗的跨多日事件**（如"云南五日游"、"参加马拉松比赛"）：
          必须将每月中相关联的多日活动聚合成摘要来匹配
          例如：杭州旅行每天活动 → "杭州三日游"
        - **如果目标事件是粒度较细的单日事件**（如"在某餐厅吃饭"、"看了某场电影"）：
          不强制聚合，可以直接用单日活动匹配
        - 时间表示：单日"YYYY-MM-DD"，多日"YYYY-MM-DD 至 YYYY-MM-DD"

        **任务二：找相似事件**
        从聚合后（或原始）的活动中找出与目标事件可能混淆的相似事件（最多5个）。

        **相似性标准**
        - 同类活动（多次旅行、多次聚会、多次比赛等）
        - 相关主题（多次医疗、多次学习等）
        - 相似场景（类似休闲活动、工作场景等）
        - 排除：仅日期不同的日常重复事件（如每天跑步）

        **输出格式**
        直接返回 JSON 数组，每个元素：
        {{
            "month": "月份",
            "date": "YYYY-MM-DD 或 YYYY-MM-DD 至 YYYY-MM-DD",
            "name": "活动名称",
            "description": "描述（不超过80字）",
            "similarity_reason": "相似原因"
        }}

        **输出示例**

        假设目标事件是"云南五日游"（粗粒度多日）：
        ```
        [
            {{
                "month": "2025-06",
                "date": "2025-06-10 至 2025-06-14",
                "name": "厦门鼓浪屿三日游",
                "description": "周末前往厦门游玩，游览鼓浪屿景区",
                "similarity_reason": "同属跨省市旅游活动，地点和性质相似，容易混淆具体时间和目的地"
            }},
            {{
                "month": "2025-10",
                "date": "2025-10-03 至 2025-10-05",
                "name": "参加云南全程马拉松比赛",
                "description": "前往云南参加全程马拉松比赛并游玩",
                "similarity_reason": "同属多日外出活动，且目的地都是云南，且有游玩成分，可能混淆"
            }}
        ]
        ```

        假设目标事件是"在图书馆借了5本书"（细粒度单日）：
        ```
        [
            {{
                "month": "2025-08",
                "date": "2025-08-20",
                "name": "图书馆归还图书",
                "description": "在图书馆归还之前借阅的书籍",
                "similarity_reason": "同属图书馆活动，可能混淆具体日期"
            }}
        ]
        ```

        无相似事件：
        ```
        []
        ```
        """

        try:
            llm_result = llm_call_j(prompt)

            # 解析结果
            if isinstance(llm_result, str):
                start_idx = llm_result.find('[')
                end_idx = llm_result.rfind(']') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = llm_result[start_idx:end_idx]
                    try:
                        similar_events = json.loads(json_str)
                    except json.JSONDecodeError:
                        return []
                else:
                    return []
            elif isinstance(llm_result, list):
                similar_events = llm_result
            else:
                return []

            if isinstance(similar_events, list):
                return similar_events
            return []

        except Exception as e:
            print(f"[Similar Events - Single] LLM 调用失败：{e}")
            return []

    def QAGen(self, year: str = "2025") -> List[Dict[str, Any]]:
        """
        生成时序相关 QA 对的主入口函数
        
        Args:
            year: 年份，格式为"YYYY"，默认为"2025"
        
        Returns:
            生成的 QA 对列表
        """
        print(f"\n开始生成 {year} 年的时序相关问答对...")
        
        # Step 1: 生成全年各月总结并分析相似事件
        yearly_summaries, event_groups = self._generate_yearly_summaries(int(year))
        
        if not yearly_summaries:
            print("[Error] 未能生成任何月份总结")
            return []
        
        # Step 2: 生成时序问题
        all_questions = self._generate_temporal_sequence_questions(yearly_summaries, int(year), event_groups)
        
        print(f"\n========== 问题生成完成，共{len(all_questions)}个问题 ==========")
        
        # Step 3: 设置所有问题的 question_type
        print("\n[QAGen] 设置所有问题的 question_type...")
        for question in all_questions:
            if 'question_type' not in question:
                question['question_type'] = 'Temporal'
        
        # Step 4: 保存结果
        if all_questions:
            self._save_questions(all_questions, year)
        
        return all_questions
    
    def _generate_temporal_sequence_questions(self, yearly_summaries: List[Dict[str, Any]], year: int, 
                                               event_groups: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        生成时序问题：从总结的事件中随机抽取事件，生成四类问题
        1. 排序问题
        2. 时间差计算问题
        3. 持续时长分析问题（针对持续时长大于1天的事件）
        4. 次数统计问题（基于相似事件分组）
        
        Args:
            yearly_summaries: 全年各月总结列表
            year: 年份
            event_groups: 相似事件分组结果
            
        Returns:
            生成的时序问题列表
        """
        print(f"\n{'='*80}")
        print(f"[Temporal Sequence Agent] 开始为 {year} 年生成时序问题...")
        print(f"{'='*80}")
        
        # 收集全年所有事件
        all_events = []
        for summary in yearly_summaries:
            month = summary.get('month', '')
            important_events = summary.get('important_events', [])
            for event in important_events:
                all_events.append({
                    'date': event.get('date', ''),
                    'description': event.get('event_description', ''),
                    'month': month,
                    'similar_events': event.get('similar_events', [])
                })
        
        if len(all_events) < 2:
            print("[Temporal Sequence Agent] 事件数量不足，无法生成时序问题")
            return []
        
        all_questions = []
        
        # 1. 并行20线程生成排序问题和时间差计算问题
        print(f"\n[Temporal Sequence Agent] 开始并行生成排序问题和时间差计算问题（20线程）...")
        
        import concurrent.futures
        
        def generate_sorting_task(task_id: int) -> List[Dict[str, Any]]:
            """生成排序问题的任务函数"""
            try:
                print(f"\n[Temporal Sequence Agent] 生成排序问题任务 {task_id + 1}/20...")
                questions = self._generate_sorting_questions(all_events, year)
                print(f"[Temporal Sequence Agent] 任务 {task_id + 1} 生成了 {len(questions)} 个排序问题")
                return questions
            except Exception as e:
                print(f"[Temporal Sequence Agent] 排序问题生成任务 {task_id + 1} 失败：{e}")
                return []
        
        def generate_time_diff_task(task_id: int) -> List[Dict[str, Any]]:
            """生成时间差计算问题的任务函数"""
            try:
                print(f"\n[Temporal Sequence Agent] 生成时间差问题任务 {task_id + 1}/20...")
                questions = self._generate_time_difference_questions(all_events, year)
                print(f"[Temporal Sequence Agent] 任务 {task_id + 1} 生成了 {len(questions)} 个时间差问题")
                return questions
            except Exception as e:
                print(f"[Temporal Sequence Agent] 时间差问题生成任务 {task_id + 1} 失败：{e}")
                return []
        
        # 使用 ThreadPoolExecutor 并行执行20次排序问题和20次时间差问题
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # 提交所有任务（20个排序 + 20个时间差 = 40个任务）
            futures = []
            for i in range(30):
                futures.append(executor.submit(generate_sorting_task, i))
                futures.append(executor.submit(generate_time_diff_task, i))
            
            # 收集结果
            completed_count = 0
            total_tasks = len(futures)
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        all_questions.extend(result)
                    completed_count += 1
                    if completed_count % 5 == 0 or completed_count == total_tasks:
                        print(f"\n[Temporal Sequence Agent] 已完成 {completed_count}/{total_tasks} 个生成任务，累计生成 {len(all_questions)} 个问题")
                except Exception as e:
                    print(f"[Temporal Sequence Agent] 任务结果收集失败：{e}")
        
        print(f"\n[Temporal Sequence Agent] 并行生成完成：共生成 {len(all_questions)} 个问题")
        
        # 3. 生成持续时长分析问题
        duration_questions = self._generate_duration_analysis_questions(all_events, year)
        all_questions.extend(duration_questions)
        print(f"[Temporal Sequence Agent] 生成了 {len(duration_questions)} 个持续时长分析问题")

        # # 4. 生成次数统计问题：基于相似事件分组
        # if event_groups and event_groups.get('event_groups'):
        #     frequency_questions = self._generate_frequency_count_questions(event_groups, year)
        #     all_questions.extend(frequency_questions)
        #     print(f"[Temporal Sequence Agent] 生成了 {len(frequency_questions)} 个次数统计问题")
        # else:
        #     print("[Temporal Sequence Agent] 没有相似事件分组数据，跳过次数统计问题生成")
        # 
        # print(f"[Temporal Sequence Agent] 总共生成 {len(all_questions)} 个时序问题")
        # 
        # 6. 为每个问题调用 evidence_refine 补充手机数据证据（20线程并行）
        print(f"\n[Temporal Sequence Agent] 开始为 {len(all_questions)} 个问题补充手机数据证据（20线程并行）...")

        import concurrent.futures
        refined_questions = [None] * len(all_questions)  # 预分配列表保持顺序

        def refine_single_question(idx: int, question: Dict[str, Any]) -> tuple:
            """处理单个问题的证据补充"""
            try:
                print(f"\n[Temporal Sequence Agent] 处理第 {idx + 1}/{len(all_questions)} 个问题...")
                refined_question = self.evidence_refine(question)
                return idx, refined_question
            except Exception as e:
                print(f"[Temporal Sequence Agent] 第 {idx + 1} 个问题证据补充失败：{e}")
                return idx, question

        # 使用 ThreadPoolExecutor 并行处理，最多20线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(refine_single_question, idx, question)
                for idx, question in enumerate(all_questions)
            ]

            # 收集结果
            completed_count = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, refined_question = future.result()
                    refined_questions[idx] = refined_question
                    completed_count += 1
                    if completed_count % 5 == 0 or completed_count == len(all_questions):
                        print(f"\n[Temporal Sequence Agent] 已完成 {completed_count}/{len(all_questions)} 个问题的证据补充")
                except Exception as e:
                    print(f"[Temporal Sequence Agent] 结果收集失败：{e}")

        # 过滤掉 None 值（如果有）
        refined_questions = [q for q in refined_questions if q is not None]

        # 为所有问题添加 ask_time 字段
        for question in refined_questions:
            question['ask_time'] = f'{self.year}-12-31'

        print(f"[Temporal Sequence Agent] 已为 {len(refined_questions)} 个问题添加 ask_time 字段")

        # 7. 并行20线程对已完成证据补充的问题进行过滤检查
        print(f"\n[Temporal Sequence Agent] 开始对 {len(refined_questions)} 个问题进行过滤检查（20线程并行）...")
        filtered_questions = self._filter_questions_parallel(refined_questions)

        print(f"\n[Temporal Sequence Agent] 总共生成 {len(filtered_questions)} 个时序问题（已完成过滤和证据补充）")
        return filtered_questions
    
    # ========== 公共辅助方法 ==========
    
    def _filter_questions_parallel(self, questions: List[Dict[str, Any]], max_workers: int = 20) -> List[Dict[str, Any]]:
        """
        并行过滤检查问题质量（20线程）
        
        Args:
            questions: 待检查的问题列表
            max_workers: 最大线程数，默认20
            
        Returns:
            过滤后的问题列表（保留通过检查或被重新生成的问题）
        """
        print(f"\n[_filter_questions_parallel] 开始对 {len(questions)} 个问题进行过滤检查（{max_workers}线程并行）...")
        
        import concurrent.futures
        filtered_results = [None] * len(questions)  # 预分配列表保持顺序
        
        def filter_single_question(idx: int, question: Dict[str, Any]) -> tuple:
            """处理单个问题的过滤检查"""
            try:
                print(f"\n[_filter_questions_parallel] 检查第 {idx + 1}/{len(questions)} 个问题...")
                
                # 调用 LLM 进行质量检查
                check_prompt = f"""
作为 QA Quality Checker，请检查以下时序推理问题的质量。

【问题】
{question.get('question', '')}

【答案】
{question.get('answer', '')}

【证据数据】
{json.dumps(question.get('evidence', []), ensure_ascii=False, indent=2) if question.get('evidence') else '无'}

**检查标准**

1. **问题和答案的合理性**
   - 问题是否清晰、无歧义？
   - 答案是否正确回答了问题？
   - 答案的内容是否合理、符合逻辑？

2. **可从 evidence 推理的可回答性**
   - 提供的 evidence 是否包含回答问题所需的足够信息？
   - 从 evidence 出发，是否能推导出答案？
   - 是否存在 evidence 不足导致无法回答的情况？
   - **对于持续时长分析问题（如"活动持续了多久"、"做了多长时间"等）：只要 evidence 中有表明事件/活动开始的标志和结束的标志即可，不需要期间该活动相关的数据**
     * 开始标志示例："开始跑步"、"进入健身房"、"打开应用"、"会议开始"
     * 结束标志示例："完成跑步"、"离开健身房"、"关闭应用"、"会议结束"
     * 只要有明确的开始和结束时间点，就能计算持续时间

3. **是否存在明显错误**
   - 问题或答案中是否有事实性错误？
   - 时间、地点、人物等信息是否一致？

**输出要求**

请以 JSON 格式返回检查结果：
{{
    "is_valid": true/false,
    "issues": ["问题列表，如果没有问题则为空数组"],
    "action": "keep/regenerate/discard",
    "reason": "做出该决定的原因",
    "suggested_question": "如果需要重新生成，建议的新问题（可选）",
    "suggested_answer": "如果需要重新生成，建议的新答案（可选）"
}}

**决策规则**：
- keep: 问题和答案都合理，且可以从 evidence 推理得出
- regenerate: 问题或答案有小问题，但可以通过修改改进
- discard: 问题严重不合理，或 evidence 完全不足以支持回答
"""
                
                check_result = llm_call_j(check_prompt)
                
                try:
                    start_idx = check_result.find('{')
                    end_idx = check_result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        check_json = json.loads(check_result[start_idx:end_idx])
                        is_valid = check_json.get('is_valid', True)
                        action = check_json.get('action', 'keep')
                        issues = check_json.get('issues', [])
                        reason = check_json.get('reason', '')
                        
                        if action == 'discard':
                            print(f"[_filter_questions_parallel] 第 {idx + 1} 个问题被抛弃：{reason}")
                            return idx, None
                        elif action == 'regenerate':
                            suggested_question = check_json.get('suggested_question', '')
                            suggested_answer = check_json.get('suggested_answer', '')
                            if suggested_question and suggested_answer:
                                print(f"[_filter_questions_parallel] 第 {idx + 1} 个问题需要重新生成：{reason}")
                                question['question'] = suggested_question
                                question['answer'] = suggested_answer
                                return idx, question
                            else:
                                print(f"[_filter_questions_parallel] 第 {idx + 1} 个问题需要重新生成但未提供建议，抛弃：{reason}")
                                return idx, None
                        else:  # keep
                            print(f"[_filter_questions_parallel] 第 {idx + 1} 个问题通过检查")
                            return idx, question
                    else:
                        print(f"[_filter_questions_parallel] 第 {idx + 1} 个问题检查结果解析失败，保留原问题")
                        return idx, question
                except Exception as e:
                    print(f"[_filter_questions_parallel] 第 {idx + 1} 个问题检查异常：{e}，保留原问题")
                    return idx, question
                    
            except Exception as e:
                print(f"[_filter_questions_parallel] 第 {idx + 1} 个问题检查失败：{e}")
                return idx, question
        
        # 使用 ThreadPoolExecutor 并行处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(filter_single_question, idx, question)
                for idx, question in enumerate(questions)
            ]
            
            # 收集结果
            completed_count = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, result = future.result()
                    filtered_results[idx] = result
                    completed_count += 1
                    if completed_count % 5 == 0 or completed_count == len(questions):
                        print(f"\n[_filter_questions_parallel] 已完成 {completed_count}/{len(questions)} 个问题的过滤检查")
                except Exception as e:
                    print(f"[_filter_questions_parallel] 结果收集失败：{e}")
        
        # 过滤掉 None 值（被抛弃的问题）
        filtered_questions = [q for q in filtered_results if q is not None]
        
        discarded_count = len(questions) - len(filtered_questions)
        print(f"\n[_filter_questions_parallel] 过滤完成：保留 {len(filtered_questions)} 个问题，抛弃 {discarded_count} 个问题")
        
        return filtered_questions
    
    def _get_month_key_from_event_id(self, event_id: str) -> str:
        """
        根据事件ID从 daily_event 中查找对应的月份
        
        Args:
            event_id: 事件ID
            
        Returns:
            月份键值（YYYY-MM格式），如果找不到则返回None
        """
        if isinstance(self.daily_event, list):
            for event in self.daily_event:
                if str(event.get('event_id', '')) == str(event_id):
                    # 从事件日期中提取月份
                    date_raw = event.get('date', '')
                    if isinstance(date_raw, list):
                        date_raw = date_raw[0] if date_raw else ''
                    
                    if date_raw:
                        # 提取日期部分
                        date_str = date_raw.split('至')[0].strip()[:10] if '至' in date_raw else date_raw.strip()[:10]
                        try:
                            # 解析日期并提取月份
                            from datetime import datetime
                            dt = datetime.strptime(date_str, '%Y-%m-%d')
                            return dt.strftime('%Y-%m')
                        except:
                            pass
        return None
    
    def _sample_events_by_month(self, events: List[Dict[str, Any]], sample_count: int = 8) -> List[Dict[str, Any]]:
        """
        从按月份分组的事件中随机采样指定数量的事件
        
        Args:
            events: 所有事件列表
            sample_count: 采样数量，默认8
            
        Returns:
            采样后的事件列表
        """
        # 按月份分组
        monthly_events = {}
        for event in events:
            month = event.get('month', '')
            if month not in monthly_events:
                monthly_events[month] = []
            monthly_events[month].append(event)
        
        print(f"[_sample_events_by_month] 共{len(monthly_events)}个月份有事件数据")
        
        # 合并所有事件
        all_events_flat = []
        for month, month_events in monthly_events.items():
            all_events_flat.extend(month_events)
        
        # 随机采样
        actual_count = min(sample_count, len(all_events_flat))
        if actual_count > 0:
            sampled = random.sample(all_events_flat, actual_count)
            print(f"[_sample_events_by_month] 从{len(all_events_flat)}个总事件中sample了{actual_count}个")
            return sampled
        else:
            print("[_sample_events_by_month] 没有可采样的事件")
            return []
    
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
        
        print(f"[Evidence Refine] 已将 {len(operations)} 条操作数据添加到 phonedata")
    
    def _locate_daily_events(self, summary_events: List[Dict[str, Any]], 
                             date_offset: int = 1) -> List[Dict[str, Any]]:
        """
        基于summary事件的日期，在目标日期及其前后offset天的范围内搜索daily_event（20线程并行）
        
        Args:
            summary_events: summary中的事件列表
            date_offset: 日期偏移量（前后各offset天），默认1
            
        Returns:
            找到的daily_event事件列表（已去重）
        """
        from datetime import datetime, timedelta
        import concurrent.futures
        
        print(f"[_locate_daily_events] 开始定位 {len(summary_events)} 个事件的daily_event（20线程并行）...")
        
        # 定义单个事件的搜索函数
        def search_single_event(idx, event):
            date_str = event.get('date', '')
            description = event.get('description', '') or event.get('event_description', '')

            print(f"  [_locate_daily_events] 输入[{idx}]: date={date_str[:10] if date_str else 'N/A'}, desc={description[:50]}...")

            if not date_str:
                return idx, description, []

            try:
                # 解析日期
                start_date_str = date_str.split('至')[0].strip()[:10]
                target_date = datetime.strptime(start_date_str, '%Y-%m-%d')

                # 计算日期范围
                prev_date = target_date - timedelta(days=date_offset)
                next_date = target_date + timedelta(days=date_offset)

                date_range = [
                    prev_date.strftime('%Y-%m-%d'),
                    target_date.strftime('%Y-%m-%d'),
                    next_date.strftime('%Y-%m-%d')
                ]

                # 调用LLM搜索
                found_events = self._search_daily_events_by_llm(
                    date_range=date_range,
                    event_description=description,
                    target_date=start_date_str
                )

                print(f"  [_locate_daily_events] 输出[{idx}]: 找到 {len(found_events)} 个事件")
                for evt in found_events[:3]:
                    print(f"    -> event_id={evt.get('event_id', '')}, desc={evt.get('description', '')[:40]}...")

                return idx, description, found_events

            except Exception as e:
                print(f"[_locate_daily_events] 处理事件失败：{e}")
                return idx, description, []

        # 使用 ThreadPoolExecutor 并行处理，最多20线程
        # 按 original_events 的索引顺序存储结果
        located_results = []  # [located_events_for_orig_0, located_events_for_orig_1, ...]
        for orig_event in summary_events:
            located_results.append([])  # 预分配，保持索引对应

        all_found_daily_events = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # 提交所有任务，使用 (idx, event) 便于记录位置
            future_to_idx = {
                executor.submit(search_single_event, idx, event): idx
                for idx, event in enumerate(summary_events)
            }

            # 收集结果
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_idx):
                try:
                    result_idx, result_desc, result_events = future.result()
                    if result_events:
                        located_results[result_idx] = result_events
                        all_found_daily_events.extend(result_events)
                    completed_count += 1
                    if completed_count % 5 == 0 or completed_count == len(summary_events):
                        print(f"[_locate_daily_events] 已完成 {completed_count}/{len(summary_events)} 个事件的搜索")
                except Exception as e:
                    print(f"[_locate_daily_events] 任务执行失败：{e}")

        if not all_found_daily_events:
            print("[_locate_daily_events] 未找到任何daily_event事件")
            return [], {}

        print(f"[_locate_daily_events] 总共找到{len(all_found_daily_events)}个daily_event事件")

        # 去重（基于event_id）
        unique_events = {}
        for event in all_found_daily_events:
            event_id = event.get('event_id', '') or event.get('atomic_id', '')
            if event_id and event_id not in unique_events:
                unique_events[event_id] = event

        deduped_events = list(unique_events.values())
        print(f"[_locate_daily_events] 去重后剩余{len(deduped_events)}个事件")

        # 构建映射：原事件索引 -> {original_event, located_events}
        event_mapping = {}
        for idx, orig_event in enumerate(summary_events):
            located = located_results[idx] if idx < len(located_results) else []
            if located:
                event_mapping[idx] = {
                    "original_event": orig_event,
                    "located_events": located
                }

        return deduped_events, event_mapping
    
    def _generate_sorting_questions(self, events: List[Dict[str, Any]], year: int) -> List[Dict[str, Any]]:
        """
        生成排序问题
        """
        from datetime import datetime, timedelta
        
        print(f"\n[Sorting Questions] 开始生成排序问题...")
        
        # Step 1: 筛选事件 - 从所有月份中随机sample 8个事件
        sampled_events = self._sample_events_by_month(events, sample_count=8)
        if not sampled_events:
            return []
        
        # Step 2: 定位到 daily_event
        daily_events, event_mapping = self._locate_daily_events(sampled_events, date_offset=1)
        if len(daily_events) < 3:
            print("[Sorting Questions] 事件数量不足3个，无法生成排序问题")
            return []

        # Step 3: 生成问题 - 随机sample 3-6个事件生成排序问题
        questions = []
        num_questions = 1

        for _ in range(num_questions):
            num_events = random.randint(4, min(6, len(daily_events)))
            selected_events = random.sample(daily_events, num_events)
            print(f"\n[Sorting Questions] 选取的 {num_events} 个事件:")
            for i, evt in enumerate(selected_events):
                print(f"  [{i+1}] event_id={evt.get('event_id', '')}, date={evt.get('date', '')}, desc={evt.get('description', '')[:50]}...")
            print(f"\n[Sorting Questions] event_mapping 内容:")
            print(f"  event_mapping 大小: {len(event_mapping)}")
            for idx, mapping in event_mapping.items():
                orig_desc = mapping['original_event'].get('description', '') or mapping['original_event'].get('event_description', '')
                print(f"  idx={idx}: {orig_desc[:40]}...")
                print(f"    -> original_event_id={mapping['original_event'].get('event_id', '')}")
                print(f"    -> similar_events count={len(mapping['original_event'].get('similar_events', []))}")
                print(f"    -> located_count={len(mapping['located_events'])}")

            # 构建用于 Step 4 的事件列表：需要包含 original_event 的 similar_events 和当日其他事件
            events_for_check = []
            for sel_evt in selected_events:
                sel_evt_id = sel_evt.get('event_id', '')
                # 从 event_mapping 中找到对应的 original_event（基于 event_id 匹配）
                matched_mapping = None
                matched_idx = None
                for idx, mapping in event_mapping.items():
                    # 检查 located_events 中是否有匹配的 event_id
                    for loc_evt in mapping['located_events']:
                        if str(loc_evt.get('event_id', '')) == str(sel_evt_id):
                            matched_mapping = mapping
                            matched_idx = idx
                            break
                    if matched_mapping:
                        break
                if matched_mapping:
                    events_for_check.append({
                        'event_id': sel_evt.get('event_id', ''),
                        'description': sel_evt.get('description', ''),
                        'date': sel_evt.get('date', ''),
                        'similar_events': matched_mapping['original_event'].get('similar_events', []),
                        'original_event': matched_mapping['original_event'],
                        'mapping_idx': matched_idx
                    })
                else:
                    events_for_check.append({
                        'event_id': sel_evt.get('event_id', ''),
                        'description': sel_evt.get('description', ''),
                        'date': sel_evt.get('date', ''),
                        'similar_events': [],
                        'original_event': sel_evt,
                        'mapping_idx': None
                    })

            question_data = self._generate_single_sorting_question_with_llm(selected_events, year)
            if question_data:
                # Step 4: 检查是否需要重写事件描述以避免混淆
                print(f"\n[Sorting Questions] 调用 _check_and_rewrite_event_descriptions...")
                question_data = self._check_and_rewrite_event_descriptions(
                    events_for_check, question_data, year, event_mapping
                )
                # Step 5: 如果重写发生了，需要将新增的锚点事件的 event_id 加入 required_events_id
                if question_data.get('needs_rewrite') and question_data.get('rewrite_details'):
                    original_ids = set(question_data.get('required_events_id', []))
                    for detail in question_data['rewrite_details']:
                        anchor_ids = detail.get('anchor_event_ids', [])
                        for anchor_id in anchor_ids:
                            if anchor_id:
                                original_ids.add(str(anchor_id))
                    question_data['required_events_id'] = list(original_ids)
                    print(f"[_check_and_rewrite] 重写后 required_events_id: {question_data['required_events_id']}")
                questions.append(question_data)
        
        #print(f"[Sorting Questions] 生成了 {len(questions)} 个排序问题")
        return questions
    
    def _generate_time_difference_questions(self, events: List[Dict[str, Any]], year: int) -> List[Dict[str, Any]]:
        """
        生成时间差计算问题
        """
        from datetime import datetime
        
        print(f"\n[Time Difference Questions] 开始生成时间差计算问题...")
        
        # Step 1: 筛选事件 - 随机抽取事件对
        num_questions = min(5, len(events) // 2)
        event_pairs = []
        for _ in range(num_questions):
            if len(events) >= 2:
                pair = random.sample(events, 2)
                event_pairs.append(pair)
        
        if not event_pairs:
            return []
        
        # Step 2: 定位到 daily_event
        all_daily_events = []
        for pair in event_pairs:
            for event in pair:
                all_daily_events.append(event)

        daily_events, event_mapping = self._locate_daily_events(all_daily_events, date_offset=0)
        if len(daily_events) < 2:
            print("[Time Difference Questions] 未找到足够的daily_event事件")
            return []
        
        # Step 3: 生成问题 - 计算时间差
        questions = []
        num_questions = 1
        
        for _ in range(num_questions):
            selected_events = random.sample(daily_events, 2)
            question_data = self._generate_time_diff_question_with_llm(selected_events, year)
            if question_data:
                questions.append(question_data)
        
        #print(f"[Time Difference Questions] 生成了 {len(questions)} 个时间差计算问题")
        return questions
    
    def _generate_duration_analysis_questions(self, events: List[Dict[str, Any]], year: int) -> List[Dict[str, Any]]:
        """
        生成持续时长分析问题
        
        流程：
        1. 筛选出多日事件（持续时长>1天）
        2. 调用LLM进一步筛选出重要的、值得回忆纪念的问题（不超过10个）
        3. 对每个事件设计问题
        4. 调用LLM从起始日期开始往后遍历daily_event，找到真正的开始和结束日期
        5. 若直到原定结束日期都没找到开始日期，则放弃该问题
        """
        from datetime import datetime, timedelta
        
        print(f"\n[Duration Analysis Questions] 开始生成持续时长分析问题...")
        
        # Step 1: 筛选事件 - 筛选持续时长>1天的事件
        multi_day_events = []
        for event in events:
            date_str = event.get('date', '')
            if '至' in date_str:
                try:
                    parts = date_str.split('至')
                    start_date = datetime.strptime(parts[0].strip()[:10], '%Y-%m-%d')
                    end_date = datetime.strptime(parts[1].strip()[:10], '%Y-%m-%d')
                    duration_days = (end_date - start_date).days + 1
                    if duration_days > 1:
                        multi_day_events.append({
                            **event,
                            'duration_days': duration_days,
                            'original_start_date': parts[0].strip()[:10],
                            'original_end_date': parts[1].strip()[:10]
                        })
                except:
                    continue
        
        if not multi_day_events:
            print("[Duration Analysis Questions] 没有多日事件")
            return []
        
        print(f"[Duration Analysis Questions] 初步筛选出 {len(multi_day_events)} 个多日事件")
        
        # Step 2: 调用LLM筛选出重要的、值得回忆纪念的事件（不超过10个）
        selected_events = self._filter_important_multi_day_events(multi_day_events)
        
        if not selected_events:
            print("[Duration Analysis Questions] LLM筛选后没有重要事件")
            return []
        
        print(f"[Duration Analysis Questions] LLM筛选出 {len(selected_events)} 个重要事件")
        
        # Step 3: 对每个事件设计问题并验证日期（12线程并行）
        print(f"\n[Duration Analysis Questions] 开始12线程并行验证和生成问题...")
        questions = []
        
        import concurrent.futures
        
        def process_single_event(event):
            """处理单个事件的验证和问题生成"""
            import traceback
            try:
                question_data = self._generate_and_verify_duration_question(event, year)
                return question_data
            except Exception as e:
                desc = event.get('name', '') or event.get('event_name', '') or event.get('description', '')
                print(f"[Duration Analysis Questions] 处理事件 '{desc}' 时出错: {e}")
                print(f"[Duration Analysis Questions] 异常详情: {traceback.format_exc()}")
                return None
        
        # 使用 ThreadPoolExecutor 并行处理，最多12线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            # 提交所有任务
            future_to_event = {
                executor.submit(process_single_event, event): event
                for event in selected_events
            }
            
            # 收集结果
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_event):
                try:
                    result = future.result()
                    if result:
                        questions.append(result)
                    completed_count += 1
                    if completed_count % 3 == 0 or completed_count == len(selected_events):
                        print(f"[Duration Analysis Questions] 已完成 {completed_count}/{len(selected_events)} 个事件的处理")
                except Exception as e:
                    print(f"[Duration Analysis Questions] 任务执行失败：{e}")
        
        print(f"[Duration Analysis Questions] 生成了 {len(questions)} 个持续时长分析问题")
        return questions
    
    def _filter_important_multi_day_events(self, multi_day_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        调用LLM筛选出重要的、值得回忆纪念的多日事件（不超过10个）
        
        Args:
            multi_day_events: 多日事件列表
            
        Returns:
            筛选后的重要事件列表
        """
        # 准备事件数据
        events_data = []
        for i, event in enumerate(multi_day_events):
            events_data.append({
                'index': i,
                'description': event.get('description', '') or event.get('event_description', ''),
                'name': event.get('name', '') or event.get('event_name', ''),
                'date': event.get('date', ''),
                'duration_days': event.get('duration_days', 0)
            })
        
        prompt = f"""
        作为事件重要性评估专家，请从以下多日事件中筛选出最重要的、值得回忆纪念的事件。
        
        【候选事件列表】（共{len(events_data)}个）
        {json.dumps(events_data, ensure_ascii=False, indent=2)}
        
        **筛选标准**（按优先级排序）
        1. **独特性与稀有性**（最高优先级）：
           - 一年只会发生一次或极少发生的事件（如生日、春节回家、婚礼、毕业典礼等）
           - 独特的旅行体验、特殊的成就或里程碑
           - 不寻常的、特别的体验
        
        2. **重要性**：
           - 重要会议、培训学习、特殊活动
           - 对用户有重大影响的事件
        
        3. **纪念价值**：
           - 对用户有深刻纪念意义的事件
           - 情感价值高的事件
        
        4. **排除日常**（最低优先级）：
           - 普通的出差、常规活动
           - 频繁发生的例行事务
        
        **特别注意 - 跨月连续事件识别**
        - 有些事件实际上是同一个连续事件，但因为跨月而被分成了多个记录
        - 例如：一个从6月28日持续到7月5日的旅行，可能被分成两个事件：
          * 索引X: 6月28日至6月30日，描述"云南旅游"
          * 索引Y: 7月1日至7月5日，描述"云南旅游"
        - **判断标准**：
          * 时间上连续：下一个事件的开始日期 = 当前事件结束日期 + 1天
          * 描述相似：名称或描述高度相似（包含相同关键词）
        - **处理策略**：如果发现这类跨月连续事件，应该将它们视为一个整体来评估重要性，并只选择其中一个索引（最早的）代表整个事件
        
        **输出要求**
        - 最多选择10个最重要的事件
        - 优先选择独特、稀有、一年不会发生多次的事件
        - 如果发现有跨月连续事件，只选择其中一个索引代表整个事件，避免重复
        - 返回选中事件的索引列表
        
        请以 JSON 格式返回：
        {{
            "selected_indices": [0, 2, 5, ...],
            "reason": "筛选原因说明，特别指出哪些是独特/稀有的事件，以及是否发现了跨月连续事件"
        }}
        """
        
        try:
            llm_result = llm_call_j(prompt)
            
            if self.is_print:
                print(f"\n[Filter Important Events] LLM 输出:")
                print(str(llm_result)[:300] + "..." if len(str(llm_result)) > 300 else str(llm_result))
            
            # 解析结果
            if isinstance(llm_result, str):
                start_idx = llm_result.find('{')
                end_idx = llm_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = llm_result[start_idx:end_idx]
                    try:
                        result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"[Filter Important Events] JSON 解析失败：{e}")
                        return multi_day_events[:10]  # 失败时返回前10个
                else:
                    return multi_day_events[:10]
            elif isinstance(llm_result, dict):
                result = llm_result
            else:
                return multi_day_events[:10]
            
            selected_indices = result.get('selected_indices', [])
            if not selected_indices or not isinstance(selected_indices, list):
                return multi_day_events[:10]
            
            # 根据索引获取选中的事件
            selected = []
            for idx in selected_indices:
                if isinstance(idx, int) and 0 <= idx < len(multi_day_events):
                    selected.append(multi_day_events[idx])
            
            # 最多返回10个
            return selected[:10]
            
        except Exception as e:
            print(f"[Filter Important Events] 筛选失败：{e}")
            return multi_day_events[:10]  # 失败时返回前10个

    def _generate_and_verify_duration_question(self, event: Dict[str, Any], 
                                                year: int) -> Dict[str, Any]:
        """
        为单个多日事件生成问题，并验证真正的开始和结束日期
        
        Args:
            event: 多日事件
            year: 年份
            
        Returns:
            生成的问题数据，如果验证失败则返回None
        """
        from datetime import datetime

        desc = event.get('name', '') or event.get('event_name', '') or event.get('description', '') or event.get('event_description', '')
        original_start = event.get('original_start_date', '')
        original_end = event.get('original_end_date', '')
        
        if not desc or not original_start or not original_end:
            return None

        print(f"[_generate_and_verify_duration_question] 输入事件: desc={desc}, original_start={original_start}, original_end={original_end}")

        # Step 1: 先验证真正的开始和结束日期
        print(f"[_generate_and_verify_duration_question] 调用 _verify_duration_dates，original_start={original_start}, original_end={original_end}")
        verified_dates = self._verify_duration_dates(event, original_start, original_end)
        print(f"[_generate_and_verify_duration_question] _verify_duration_dates 返回: {verified_dates}")

        if not verified_dates:
            print(f"[Verify Duration Dates] 无法验证事件 '{desc}' 的日期，放弃该问题")
            return None
        
        actual_start = verified_dates.get('actual_start_date', original_start)
        actual_end = verified_dates.get('actual_end_date', original_end)
        event_status_summary = verified_dates.get('event_status_summary', '')
        start_event_id = verified_dates.get('start_event_id')
        end_event_id = verified_dates.get('end_event_id')
        related_event_ids = verified_dates.get('related_event_ids', [])
        
        # 检查是否找到了开始和结束事件的ID，如果没有找到则放弃该问题
        if not start_event_id or not end_event_id:
            print(f"[Verify Duration Dates] 未找到开始或结束事件的ID，放弃该问题")
            return None
        
        # 获取开始事件和结束事件的详细信息
        start_event = self._get_event_by_id(start_event_id)
        end_event = self._get_event_by_id(end_event_id)
        
        # 计算实际持续天数
        try:
            start_dt = datetime.strptime(actual_start, '%Y-%m-%d')
            end_dt = datetime.strptime(actual_end, '%Y-%m-%d')
            actual_duration = (end_dt - start_dt).days + 1
        except:
            actual_duration = event.get('duration_days', 0)
        
        # Step 2: 使用验证后的日期和事件状态总结生成问题
        print(f"[Duration Question] 事件 '{desc}' 验证通过，开始生成问题...")

        # 获取相关事件的详细信息
        related_events_details = []
        for eid in related_event_ids:
            ev = self._get_event_by_id(eid)
            if ev:
                related_events_details.append(ev)

        question_draft = self._generate_duration_question_draft(
            desc, actual_start, actual_end, actual_duration, year,
            event_status_summary, start_event, end_event, related_events_details
        )
        if not question_draft:
            print(f"[Duration Question] 问题生成失败，返回 None")
            return None

        print(f"[Duration Question] 问题生成成功: {question_draft.get('question', '')[:50]}...")

        # 构建 required_events_id：包含开始事件、结束事件和相关节点事件的ID
        required_events_ids = []
        if start_event_id:
            required_events_ids.append(str(start_event_id))
        if end_event_id and end_event_id != start_event_id:
            required_events_ids.append(str(end_event_id))
        # 添加相关节点事件ID
        for eid in related_event_ids:
            if str(eid) not in required_events_ids:
                required_events_ids.append(str(eid))

        # 构建完整的问题数据
        question_data = {
            'question': question_draft.get('question', ''),
            'answer': question_draft.get('answer', ''),
            'score_points': [
                {
                    'description': f"准确回答出事件持续天数为{actual_duration}天",
                    'score': 10
                }
            ],
            'required_events_id': required_events_ids
        }

        return question_data
    
    def _get_event_by_id(self, event_id: str) -> Dict[str, Any]:
        """
        根据事件ID从 daily_event 中查找事件
        
        Args:
            event_id: 事件ID
            
        Returns:
            事件数据，如果找不到则返回空字典
        """
        if isinstance(self.daily_event, list):
            for event in self.daily_event:
                if str(event.get('event_id', '')) == str(event_id):
                    return event
        return {}
    
    def _generate_duration_question_draft(self, desc: str, start_date: str,
                                           end_date: str, duration_days: int, year: int,
                                           event_status_summary: str = '',
                                           start_event: Dict[str, Any] = None,
                                           end_event: Dict[str, Any] = None,
                                           related_events: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        生成持续时长问题的草稿

        Args:
            desc: 事件描述
            start_date: 开始日期
            end_date: 结束日期
            duration_days: 持续天数
            year: 年份
            event_status_summary: 事件状态总结，包含事件的详细过程记录
            start_event: 标志开始的事件数据
            end_event: 标志结束的事件数据
            related_events: 相关的事件列表（包含开始、结束及重要节点事件）

        Returns:
            问题草稿
        """
        # 准备开始和结束事件的信息
        start_event_info = ""
        if start_event:
            start_event_info = f"""
        【标志开始的事件】
        - 事件名称: {start_event.get('name', '') or start_event.get('event_name', '')}
        - 事件描述: {start_event.get('description', '')[:200]}
        - 事件类型: {start_event.get('type', '')}
        - 参与者: {start_event.get('participant', [])}
        - 地点: {start_event.get('location', '')}
        """

        end_event_info = ""
        if end_event:
            end_event_info = f"""
        【标志结束的事件】
        - 事件名称: {end_event.get('name', '') or end_event.get('event_name', '')}
        - 事件描述: {end_event.get('description', '')[:200]}
        - 事件类型: {end_event.get('type', '')}
        - 参与者: {end_event.get('participant', [])}
        - 地点: {end_event.get('location', '')}
        """

        # 准备相关事件的信息
        related_events_info = ""
        if related_events:
            related_events_list = []
            for ev in related_events:
                ev_name = ev.get('name', '') or ev.get('event_name', '') or ev.get('description', '')[:50]
                ev_date = ev.get('date', '')
                ev_desc = ev.get('description', '')[:100] if ev.get('description', '') else ''
                related_events_list.append(f"- [{ev_date}] {ev_name}: {ev_desc}")
            if related_events_list:
                related_events_info = "\n【相关事件列表】\n" + "\n".join(related_events_list)
        
        prompt = f"""
        作为持续时长分析问题设计专家,请模拟在**年末12月31日对今年进行年终回顾**的场景,基于以下多日事件,生成一个持续时长分析问题。

        【场景设定】
        现在是**12月31日**,我们在对**今年**发生的事件进行年终回顾。
        所有事件都发生在今年,问题中只提及月份或事件特征来定位,不需要也不应该提及具体日期。
        题面应该像是在年度总结时,自然地回忆:"我今年······?"

        【事件】
        {desc}
        时间:{start_date} 至 {end_date}
        持续天数:{duration_days}天

        【事件详细过程记录】
        {event_status_summary if event_status_summary else '无详细过程记录'}
        {start_event_info}
        {end_event_info}
        {related_events_info}

        **重要判断 - 结束事件的标志意义**
        ⚠️ 请分析【标志结束的事件】是否真正代表事情完全结束：
        - 请你先分析开始事件和结束事件是否有对应关系，是否代表详细过程记录的描述的整体事件的开始或结束。如果是，直接对这个整体事件提问持续时间即可，如果不是，我们需要针对性对开始事件和结束事件设计持续时长的提问（但题面不能直接说明这两个事件的时间，也不要包含过于详细的事件细节）
        - 如果结束事件确实标志事情完全结束（如：完成培训、结束旅行、完成搬家等），问题描述正常
        - **如果结束事件不能完全代表事情结束**（如：只是某个阶段结束、最后一次活动、某个标志事件但不一定是最终结束），则在题面设计中增加叙述"到X月（结束事件的描述）为止"，明确表示持续时间计算到该结束事件为止

        **重要 - 题面设计要求**
        ⚠️ **题面设计原则：简洁为主，避免堆砌细节**
        - 优先使用简单直接的问题，如"我4月的个人艺术展举办了多久？"
        - 只有当事件的结束时间存在歧义时（如：举办时间不确定是从会展结束算还是后续定金交付完成算），才在题面中增加对结束节点的最小化描述来消除歧义
        - 示例1（结束明确）："我4月的个人艺术展举办了多久？"→ 简洁明确
        示例2（结束模糊）："我4月的个人艺术展到会展结束持续了多久？"→ 引入结束节点描述消除歧义

        **问题类型选择**
        请根据事件特点，选择生成以下类型的问题：

        **持续时长问题**：
           - 优先简洁设计，题面尽量简单，包含较少的事件细节，只保留能定位回答出答案的信息量。
           - **当持续天数≥3天时**，应在问题中在询问持续时间之外，增加对过程中某个细节的询问，使问题更具挑战性
           - 如果结束时间存在歧义，在题面末尾增加对结束节点的最小化描述来消除歧义（但仍不直接说明具体日期）
           - 示例（持续天数≥3天，带细节询问）：
             - "我记得今年7月那次独立带组，到病例讨论获表扬，持续了多久？那段时间除了成功抢救了患有什么病的患者"
             - "我记得今年8月参加的那个摄影展，到闭幕式结束持续了多久？中间有哪些让我写在笔记的展出？"
           - 示例（持续天数<3天，简洁设计）：
             - "我记得今年5月参加主治医师资格考试，那次持续了多久？"

        **任务要求**
        1. **回忆口吻**：问题应该是在年末12月31日进行年终回顾时的口吻，像是在年终聚餐或年度总结时聊起往事
        2. **简洁设计**：优先使用最简洁的表述，不堆砌事件细节
        3. **持续天数≥3天时增加细节询问**：使问题更具挑战性，答案需要综合分析过程事件才能给出
        4. **结束节点处理**：如果结束时间明确，直接简洁提问；如果存在歧义，才增加对结束节点的描述
        5. **时间定位**：必须带有足够确定这段时间的事件的信息，让回答者能准确定位到是哪一次事件
           - **一年一次的事件**（如生日、节假日）：加入节假日/特殊日期信息
             * 示例："我今年春节回家..."、"我今年过生日那几天..."
           - **一年多次的事件**（如出差、旅游）：加入月份或时间段信息
             * 示例："我今年7月下旬那次出差..."、"我今年国庆节去的那次旅游..."
             * 示例："我今年上半年参加的那个培训..."
           - **独特性事件**：如果事件本身很独特，可以直接描述
             * 示例："我今年去云南那次旅游..."、"我今年参加马拉松那次..."
        6. 问题应该以第一人称口吻,语气自然流畅
        7. 提供准确的答案,答案中必须明确说明持续天数为{duration_days}天
        8. **参考【事件详细过程记录】**，了解事件的具体活动内容、地点、参与者等细节，使答案更加丰富和具体
        9. 合理设计题面，使答案符合开始日期和结束日期。题面具有一定难度。

        **重要约束 - answer 字段规范**
        ⚠️ **answer 字段只能包含最终答案内容,严禁包含任何思考过程、分析步骤或推理说明**

        ✅ **正确的 answer 示例**:
        - "你那次云南旅游一共去了5天,从3月10日到3月15日,主要游览了大理和丽江"
        - "这次培训持续了7天,从周一到周日,学习了Python基础和数据分析"

        ❌ **错误的 answer 示例**(包含思考过程):
        - "根据事件描述,这个活动从X日到Y日,所以持续了N天..."(不要解释计算过程)
        - "首先确定开始日期是...,然后结束日期是...,因此答案是..."(不要展示推理步骤)
        - "通过分析事件记录,我发现..."(不要说明分析方法)

        **题面 Bad Case 警示**
        ⚠️ 以下是**错误**的题面设计，请**避免**：

        ❌ **问题包含具体日期**（直接暴露答案，无需分析）：
        - "我从7月15日开始独立带组，到7月24日病例讨论获表扬，一共多少天？"
        - 正确做法：只给出月份提示，不在问题中写具体日期

        ❌ **堆砌过多开始/结束事件细节**（让回答者无需分析事件数据就能回答）：
        - "我从7月15日张磊主任宣布我正式接管16至19床医疗组成为责任主治医师那天开始，到7月24日在科室疑难病例讨论会上汇报多发性骨髓瘤合并肾衰竭病例并获得主任表扬，一共持续了多少天？"
        - 正确做法：简洁设计，问题应该要求回答者分析事件数据才能得出答案

        ❌ **题面过于冗长复杂**：
        - "我记得去年12月我在社区艺术空间举办的那个个人摄影展，从12月22日下午在社区艺术空间举办开幕式我拿着话筒致辞感谢到场的亲友，到12月30日上午在纺织工业遗址博物馆和林婉清一起举办闭幕式分享，整个展览从开幕式到闭幕式一共持续了多少天？"
        - 正确做法：简洁为主，如"我记得去年12月我办的那个摄影展，一共展出了多少天？"

        ❌ **过早/过多引入结束节点描述**（应优先简洁，只有必要时才增加）：
        - "我记得那次独立带组，到7月24日在科室汇报多发性骨髓瘤病例并获表扬，一共持续了多少天？"（结束时间存在歧义时才可以这样设计）
        - 但如果结束明确，不应该加那么多细节

        **输出要求**
        请以 JSON 格式返回:
        {{
            "question": "问题(回忆口吻,第一人称,简洁设计,只在必要时增加结束节点描述以消除歧义)",
            "answer": "直接给出答案,只包含事实性内容,不含任何思考过程,可引用事件过程中的关键信息"
        }}

        **示例**
        {{
            "question": "我记得今年5月参加的那个专业培训，一直到培训结束，一共持续了多少天？",
            "answer": "你今年5月参加的那个专业培训从5月10日到5月15日，一共持续了6天。"
        }},
        {{
            "question": "我记得今年8月安排的那次自驾游，从出发到返程，那次持续了多久？我们中间车辆抛锚是谁帮我们联系了拖车？",
            "answer": "你今年8月安排的那次自驾游持续了7天，从8月1日到8月7日，途经多个城市。是一位路过的交警帮你们联系了拖车。"
        }},
        {{
            "question": "我记得今年6月参与的那个项目，从开始到项目正式上线持续了多久？，除了日常开发，中间的测试是在几月几号进行的？",
            "answer": "从6月1日到6月20日一共20天，中间经历了需求评审、技术方案设计、两周冲刺开发、上线前测试等重要节点，最终在6月20日正式上线。测试是在6月18日进行的。"
        }}
        """
        
        try:
            print(f"[Duration Question Draft] 发送LLM请求...")
            llm_result = llm_call_j(prompt)
            print(f"[Duration Question Draft] LLM原始输出: {str(llm_result)[:200]}...")

            if isinstance(llm_result, str):
                start_idx = llm_result.find('{')
                end_idx = llm_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = llm_result[start_idx:end_idx]
                    result = json.loads(json_str)
                    print(f"[Duration Question Draft] 解析成功: question={result.get('question', '')[:50]}...")
                    return result
            elif isinstance(llm_result, dict):
                print(f"[Duration Question Draft] 解析成功(字典): question={llm_result.get('question', '')[:50]}...")
                return llm_result
        except Exception as e:
            print(f"[Duration Question Draft] 异常: {e}")

        return None
    
    def _verify_duration_dates(self, event: Dict[str, Any], original_start: str,
                                original_end: str) -> Dict[str, Any]:
        """
        调用LLM从起始日期的前一天开始往后遍历daily_event，逐日判断是否为开始/结束日期
        并提取标志开始和结束的事件及其event_id

        Args:
            event: 事件数据
            original_start: 原定开始日期
            original_end: 原定结束日期

        Returns:
            验证后的日期信息，包含开始和结束事件的event_id，如果找不到则返回None
        """
        from datetime import datetime, timedelta

        print(f"[_verify_duration_dates] 进入函数，输入: original_start={original_start}, original_end={original_end}")

        desc = event.get('description', '') or event.get('event_description', '')
        event_name = event.get('name', '') or event.get('event_name', '')
        
        # 从 original_start 的前一天开始往后遍历最多16天（原开始日期前一天 + 15天）
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(original_start, '%Y-%m-%d')
        search_start_dt = start_dt - timedelta(days=1)  # 从原开始日期的前一天开始
        search_start_str = search_start_dt.strftime('%Y-%m-%d')
        max_end_dt = start_dt + timedelta(days=30)  # 最多30天（包括起始日）
        max_end_str = max_end_dt.strftime('%Y-%m-%d')
        
        print(f"[Verify Duration Dates] 从 {search_start_str}（原开始日期前一天）开始往后遍历，最多到 {max_end_str}（共15天）")
        
        # 获取从 search_start_str 开始最多16天内的所有 daily_event，按日期分组
        daily_events_by_date = {}
        if isinstance(self.daily_event, list):
            for daily_event in self.daily_event:
                if isinstance(daily_event, dict) and 'date' in daily_event:
                    event_dates = daily_event.get('date', [])
                    if isinstance(event_dates, list):
                        for time_range in event_dates:
                            if '至' in time_range:
                                event_date = time_range.split('至')[0].strip()[:10]
                            else:
                                event_date = time_range[:10]
                            
                            # 检查是否在范围内（从原开始日期的前一天开始，最多16天）
                            if search_start_str <= event_date <= max_end_str:
                                if event_date not in daily_events_by_date:
                                    daily_events_by_date[event_date] = []
                                daily_events_by_date[event_date].append(daily_event)
                                break
        
        if not daily_events_by_date:
            print(f"[Verify Duration Dates] 在 {search_start_str} 至 {max_end_str} 范围内没有找到任何事件")
            return None
        
        # 按日期排序
        sorted_dates = sorted(daily_events_by_date.keys())
        
        print(f"[Verify Duration Dates] 共有 {len(sorted_dates)} 天有事件，开始逐日判断...")
        
        # 维护事件状态总结
        event_status_summary = ""
        actual_start_date = None
        actual_end_date = None
        start_event_id = None  # 标志开始日期的事件ID
        end_event_id = None    # 标志结束日期的事件ID
        related_event_ids = []  # 相关的重要节点事件ID列表
        
        # 逐日判断
        for i, current_date in enumerate(sorted_dates):
            day_events = daily_events_by_date[current_date]
            
            # 构建 prompt
            # 构建当天事件的简化版本
            day_events_summary = [
                {
                    'event_id': e.get('event_id', ''),
                    'name': e.get('name', '') or e.get('event_name', ''),
                    'description': e.get('description', '')[:300],
                    'type': e.get('type', ''),
                    'participant': e.get('participant', []),
                    'location': e.get('location', '')
                } for e in day_events
            ]
            
            prompt = f"""
            作为日期验证专家，请基于以下信息判断今天是否是该事件的开始或结束日期。
            
            【事件描述】
            事件名称：{event_name}
            事件详情：{desc}
            
            【当前判断的日期】
            {current_date}
            
            【当天的所有事件】（共{len(day_events)}个）
            {json.dumps(day_events_summary, ensure_ascii=False, indent=2)}
            
            【事件状态总结】（之前日期中与目标事件相关的累积信息，无字数限制，需详细记录每个日期的相关事件，具体到几月几日，只记录主要事件，忽略无关事件不重要的事件。合理进行总结压缩）
            {event_status_summary if event_status_summary else '这是第一天，还没有之前的状态信息'}
            
            **任务要求**
            1. 仔细分析当天的所有事件，判断是否有事件与目标事件描述匹配
            2. 如果有匹配的事件，判断今天是否是：
               - **开始日期**：如果是第一次出现与该事件相关的活动
               - **结束日期**：如果是最后一次出现与该事件相关的活动，且之后不再有相关活动
               - **中间日期**：如果事件仍在进行中
               - **无关日期**：如果当天没有与该事件相关的活动
            3. 参考【事件状态总结】，了解之前日期的情况，帮助判断今天是否是结束日期
            4. 识别并记录当天与目标事件相关的**重要节点事件**，如出发、回程、开始、结束、或任何重要的子事件开始/结束等

            **输出要求**
            请以 JSON 格式返回：
            {{
                "is_start_date": true/false,
                "is_end_date": true/false,
                "is_related": true/false,
                "start_event_id": "如果是开始日期，填写标志该事件开始的event_id；否则为空字符串",
                "end_event_id": "如果是结束日期，填写标志该事件结束的event_id；否则为空字符串",
                "related_event_ids": ["当天所有与目标事件相关的重要节点事件的event_id列表，包括开始、结束、出发、回程、或其他重要子事件等"],
                "status_update": "对今天与目标事件相关的所有事件的详细总结，包括具体活动内容、时间、地点等关键信息，无字数限制",
                "reason": "判断原因说明"
            }}
            
            **示例**
            {{
                "is_start_date": true,
                "is_end_date": false,
                "is_related": true,
                "start_event_id": "evt_12345",
                "end_event_id": "",
                "related_event_ids": ["evt_12345", "evt_12346"],
                "status_update": "今天开始了云南旅游，到达了大理，入住了酒店",
                "reason": "今天的第一个事件显示到达了大理并开始旅游，符合事件描述的开端"
            }}
            """
            
            try:
                llm_result = llm_call_j(prompt)
                
                # 解析结果
                result = None
                if isinstance(llm_result, str):
                    start_idx = llm_result.find('{')
                    end_idx = llm_result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        json_str = llm_result[start_idx:end_idx]
                        try:
                            result = json.loads(json_str)
                        except json.JSONDecodeError as e:
                            print(f"[Verify Duration Dates] {current_date} JSON解析失败: {e}")
                            print(f"  LLM原始输出: {llm_result[:200]}...")
                            print(f"[Verify Duration Dates] JSON解析失败，放弃该问题生成")
                            return None  # 直接返回None，放弃整个问题
                    else:
                        print(f"[Verify Duration Dates] {current_date} 未找到JSON格式")
                        print(f"  LLM原始输出: {llm_result[:200]}...")
                        print(f"[Verify Duration Dates] 未找到JSON格式，放弃该问题生成")
                        return None  # 直接返回None，放弃整个问题
                elif isinstance(llm_result, dict):
                    result = llm_result
                else:
                    print(f"[Verify Duration Dates] {current_date} LLM返回类型异常: {type(llm_result)}")
                    print(f"[Verify Duration Dates] LLM返回类型异常，放弃该问题生成")
                    return None  # 直接返回None，放弃整个问题
                
                # 检查result是否为None或非字典
                if result is None or not isinstance(result, dict):
                    print(f"[Verify Duration Dates] {current_date} result为None或非字典类型: {type(result)}")
                    print(f"[Verify Duration Dates] result类型异常，放弃该问题生成")
                    return None  # 直接返回None，放弃整个问题
                
                is_start = result.get('is_start_date', False)
                is_end = result.get('is_end_date', False)
                is_related = result.get('is_related', False)
                status_update = result.get('status_update', '')
                current_start_event_id = result.get('start_event_id', '')
                current_end_event_id = result.get('end_event_id', '')
                current_related_event_ids = result.get('related_event_ids', [])

                print(f"[Verify Duration Dates] {current_date}: is_start={is_start}, is_end={is_end}, is_related={is_related}")

                # 更新事件状态总结
                if is_related and status_update:
                    event_status_summary += f"\n[{current_date}] {status_update}"

                # 收集相关的重要节点事件ID
                if is_related and current_related_event_ids:
                    for eid in current_related_event_ids:
                        if eid and eid not in related_event_ids:
                            related_event_ids.append(eid)

                # 记录开始日期和对应的event_id
                if is_start and not actual_start_date:
                    actual_start_date = current_date
                    start_event_id = current_start_event_id if current_start_event_id else None
                    print(f"[Verify Duration Dates] ✓ 找到开始日期: {current_date}, event_id: {start_event_id}")
                
                # 记录结束日期和对应的event_id（只有在已经找到开始日期之后）
                if is_end and actual_start_date and not actual_end_date:
                    actual_end_date = current_date
                    end_event_id = current_end_event_id if current_end_event_id else None
                    print(f"[Verify Duration Dates] ✓ 找到结束日期: {current_date}, event_id: {end_event_id}")
                    break  # 找到结束日期后退出循环
                    
            except Exception as e:
                print(f"[Verify Duration Dates] 处理 {current_date} 时出错: {e}")
                continue
        
        # 检查结果
        if not actual_start_date:
            print(f"[Verify Duration Dates] 未找到开始日期")
            return None
        
        if not actual_end_date:
            print(f"[Verify Duration Dates] 未找到结束日期，放弃该问题")
            return None
        
        # Step 2: 调用LLM验证开始和结束事件的合理性
        print(f"[Verify Duration Dates] 找到开始日期: {actual_start_date}, 结束日期: {actual_end_date}")
        print(f"[Verify Duration Dates] 开始事件ID: {start_event_id}, 结束事件ID: {end_event_id}")
        
        # 获取开始和结束事件的详细信息
        start_event_detail = self._get_event_by_id(start_event_id) if start_event_id else {}
        end_event_detail = self._get_event_by_id(end_event_id) if end_event_id else {}
        
        validation_result = self._validate_start_end_events(
            event_name=event_name,
            event_desc=desc,
            start_event=start_event_detail,
            end_event=end_event_detail,
            event_status_summary=event_status_summary
        )
        
        if not validation_result or not validation_result.get('is_valid', False):
            reason = validation_result.get('reason', '未知原因') if validation_result else '验证失败'
            print(f"[Verify Duration Dates] 开始/结束事件验证不通过: {reason}，放弃该问题")
            return None
        
        print(f"[Verify Duration Dates] ✓ 开始/结束事件验证通过: {validation_result.get('reason', '')}")

        result_dict = {
            'actual_start_date': actual_start_date,
            'actual_end_date': actual_end_date,
            'start_event_id': start_event_id,
            'end_event_id': end_event_id,
            'related_event_ids': related_event_ids,
            'found': True,
            'verification_reason': f"从{actual_start_date}到{actual_end_date}，共{(datetime.strptime(actual_end_date, '%Y-%m-%d') - datetime.strptime(actual_start_date, '%Y-%m-%d')).days + 1}天",
            'event_status_summary': event_status_summary
        }
        print(f"[_verify_duration_dates] 返回结果: {result_dict}")
        return result_dict
    
    def _validate_start_end_events(self, event_name: str, event_desc: str,
                                    start_event: Dict[str, Any],
                                    end_event: Dict[str, Any],
                                    event_status_summary: str) -> Dict[str, Any]:
        """
        调用LLM验证开始和结束事件的合理性
        
        Args:
            event_name: 事件名称
            event_desc: 事件描述
            start_event: 标志开始的事件数据
            end_event: 标志结束的事件数据
            event_status_summary: 事件状态总结
            
        Returns:
            验证结果，包含 is_valid 和 reason 字段
        """
        prompt = f"""
        作为事件验证专家，请分析以下多日事件的开始和结束事件是否合理。
        
        【目标事件】
        事件名称：{event_name}
        事件描述：{event_desc}
        
        【标志开始的事件】
        {json.dumps(start_event, ensure_ascii=False, indent=2) if start_event else '无'}
        
        【标志结束的事件】
        {json.dumps(end_event, ensure_ascii=False, indent=2) if end_event else '无'}
        
        【事件过程总结】
        {event_status_summary if event_status_summary else '无'}
        
        **验证标准**
        1. **事件匹配度**：
           - 开始事件应该与目标事件描述高度相关，确实标志着事件的开始
           - 结束事件应该与目标事件描述高度相关，确实标志着事件的结束
           - 两个事件应该属于同一个连续的活动或体验
        
        2. **逻辑一致性**：
           - 事件状态总结中的内容应该与开始/结束事件一致
           - 整个过程应该是连贯的、合理的
           - 从开始到结束的演变过程应该自然流畅
        
        3. **排除错误情况**：
           - 开始事件和结束事件不相关（如一个是旅行开始，另一个是工作会议）
           - 事件描述完全不匹配
           - 事件状态总结显示中间过程与开始/结束事件矛盾
        
        **输出要求**
        请以 JSON 格式返回验证结果：
        {{
            "is_valid": true/false,
            "reason": "验证原因说明，如果无效请详细说明原因"
        }}
        
        **示例**
        {{
            "is_valid": true,
            "reason": "开始事件显示到达大理开始旅游，结束事件显示从丽江返回，事件状态总结显示中间游览了多个景点，整个过程连贯合理"
        }}
        
        {{
            "is_valid": false,
            "reason": "开始事件是'到达北京出差'，但结束事件是'参加朋友婚礼'，两者不相关，不属于同一个事件"
        }}
        """
        
        try:
            print(f"[Validate Start End Events] 开始验证...")
            llm_result = llm_call_j(prompt)
            print(f"[Validate Start End Events] LLM输出: {str(llm_result)[:200]}...")

            # 解析结果
            if isinstance(llm_result, str):
                start_idx = llm_result.find('{')
                end_idx = llm_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = llm_result[start_idx:end_idx]
                    try:
                        result = json.loads(json_str)
                        print(f"[Validate Start End Events] 验证结果: is_valid={result.get('is_valid')}, reason={result.get('reason', '')[:50]}...")
                        return result
                    except json.JSONDecodeError as e:
                        print(f"[Validate Start End Events] JSON解析失败: {e}")
                        return {'is_valid': False, 'reason': 'JSON解析失败'}
            elif isinstance(llm_result, dict):
                print(f"[Validate Start End Events] 验证结果: is_valid={llm_result.get('is_valid')}")
                return llm_result

            print(f"[Validate Start End Events] 返回格式异常")
            return {'is_valid': False, 'reason': 'LLM返回格式异常'}

        except Exception as e:
            print(f"[Validate Start End Events] 验证失败: {e}")
            return {'is_valid': False, 'reason': f'验证过程出错: {str(e)}'}
    
    def _search_daily_events_by_llm(self, date_range: List[str], event_description: str, 
                                     target_date: str) -> List[Dict[str, Any]]:
        """
        调用LLM在指定日期范围内查找与描述匹配的事件
        
        Args:
            date_range: 日期范围列表 [prev_date, target_date, next_date]
            event_description: 事件描述
            target_date: 目标日期
            
        Returns:
            匹配的daily_event事件列表
        """
        # 从 daily_event 中提取这三个日期的所有事件
        daily_events_in_range = []
        if isinstance(self.daily_event, list):
            for event in self.daily_event:
                if isinstance(event, dict) and 'date' in event:
                    event_dates = event.get('date', [])
                    if isinstance(event_dates, list):
                        for time_range in event_dates:
                            if '至' in time_range:
                                event_date = time_range.split('至')[0].strip()[:10]
                            else:
                                event_date = time_range[:10]
                            
                            if event_date in date_range:
                                daily_events_in_range.append(event)
                                break
        
        if not daily_events_in_range:
            return []
        
        # 构建 prompt 让 LLM 判断哪些事件与描述匹配
        prompt = f"""
        作为事件匹配专家，请分析以下事件描述和候选事件列表，找出与描述最匹配的事件。当事件描述涉及一段时间范围，本日候选事件列表只列出了其部分事件时，选取属于该事件的出发/开始节点的事件，或最关键事件。
        
        【目标事件描述】
        {event_description}
        
        【目标日期】
        {target_date}
        
        【候选事件列表】（日期范围：{date_range[0]} 至 {date_range[2]}）
        {json.dumps(daily_events_in_range, ensure_ascii=False, indent=2)}
        
        **任务要求**
        1. 仔细比对目标事件描述与每个候选事件的内容
        2. 找出语义上最匹配的 1-3 个事件（如果有的话）
        3. 考虑事件名称、类型、描述等字段的相似性
        4. 优先选择在目标日期或接近目标日期的事件
        
        **输出要求**
        请以 JSON 格式返回匹配的事件 ID 列表：
        {{
            "matched_event_ids": ["event_id_1", "event_id_2", ...],
            "reason": "匹配原因说明"
        }}
        
        如果没有匹配的事件，返回空列表：
        {{
            "matched_event_ids": [],
            "reason": "没有找到匹配的事件"
        }}
        """
        
        try:
            llm_result = llm_call_j(prompt)
            
            if self.is_print:
                print(f"\n[Search Daily Events] LLM 输出:")
                print(str(llm_result)[:300] + "..." if len(str(llm_result)) > 300 else str(llm_result))
            
            # 解析结果
            if isinstance(llm_result, str):
                start_idx = llm_result.find('{')
                end_idx = llm_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = llm_result[start_idx:end_idx]
                    try:
                        result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"[Search Daily Events] JSON 解析失败：{e}")
                        return []
                else:
                    return []
            elif isinstance(llm_result, dict):
                result = llm_result
            else:
                return []
            
            matched_ids = result.get('matched_event_ids', [])
            if not matched_ids or not isinstance(matched_ids, list):
                return []
            
            # 根据 ID 获取完整的事件数据
            matched_events = []
            for event in daily_events_in_range:
                event_id = event.get('event_id', '') or event.get('atomic_id', '')
                if event_id in matched_ids:
                    matched_events.append(event)
            
            return matched_events
            
        except Exception as e:
            print(f"[Search Daily Events] 搜索失败：{e}")
            return []
    
    def _generate_single_sorting_question_with_llm(self, events: List[Dict[str, Any]], 
                                                    year: int) -> Dict[str, Any]:
        """
        调用LLM为选定的事件生成排序问题
        
        Args:
            events: 选定的事件列表（3-6个）
            year: 年份
            
        Returns:
            生成的排序问题数据
        """
        if not events or len(events) < 3:
            return None
        
        prompt = f"""
        作为时序问题设计专家，请基于以下{len(events)}个事件，生成一个时间排序问题。
        
        【事件列表】（包含完整事件信息）
        {json.dumps(events, ensure_ascii=False, indent=2)}
        
        **任务要求**
        
        1. **事件筛选原则**：
           - 从给定事件中选取非日常的、有意义的事件（如旅行、重要会议、特殊活动、成就等）
           - 排除日常琐事（如普通用餐、通勤、日常购物等）
           - 选择用户可能会关心其发生顺序的事件
           - 确保选取的事件之间有明确的时间先后关系
           - 选取3-6个事件
           
        2. **问题设计规范**：
           - 题面必须包含对每个事件的简要叙述（时间、地点、活动内容等关键信息），使得回答者可以基于题目搜索对应事件，只提供足以找到事件的最小信息，不要提供时间信息。
           - 为每个事件分配一个序号（1、2、3...），但序号对应的顺序要打乱
           - **关键约束：题面中事件的序号顺序必须与真实时间顺序完全不同**
             * 严禁按时间先后顺序编号（如最早的事件不能是1号，最晚的不能是最后一个号）
             * 序号必须是随机打乱的，确保题面顺序与真实顺序没有任何规律性对应
             * 例如：如果真实顺序是 A→B→C→D，题面可以是 1.C, 2.A, 3.D, 4.B
           - 问题应该以第一人称口吻，像是用户在回忆和询问自己的生活经历
           - 问题要自然流畅，符合真实用户的询问方式
        
        3. **答案要求**：
           - 提供正确的时序答案，按实际发生顺序排列
           - 答案中应包含事件的关键细节，便于验证
           - 明确指出正确的事件顺序
        
        **输出格式**
        请以 JSON 格式返回：
        {{
            "question": "排序问题（包含打乱序号的事件叙述，第一人称）",
            "answer": "正确答案（按时间顺序列出事件及关键细节）",
            "correct_order": [事件ID列表，按时间顺序排列]
        }}
        
        **示例**
        {{
            "question": "我今年做了几件挺有意思的事，能帮我按时间顺序排一下吗？\n1. 去云南旅游，在大理和丽江玩了5天\n2. 参加市体育中心举办的马拉松比赛\n3. 和朋友在麦乐迪KTV庆祝生日\n4. 完成了Python入门课程的学习并拿到结业证书\n\n这几件事哪个先发生，哪个后发生？",
            "answer": "按时间顺序应该是：\n1. 参加马拉松比赛（3月15日，市体育中心）\n2. 去云南旅游（5月10-15日，游览大理和丽江）\n3. 完成Python课程学习（7月20日结业）\n4. 和朋友KTV庆生（9月8日，麦乐迪KTV）",
            "correct_order": ["event_id_2", "event_id_1", "event_id_4", "event_id_3"]
        }}
        
        **注意事项**
        - 事件叙述要简洁但有辨识度，包含时间、地点或活动内容等关键信息
        - 序号一定要打乱，不要按时间顺序编号
        - 问题表述要自然，像真实用户在询问
        - 如果某些事件太日常或缺乏特色，可以选择不纳入问题
        """
        
        try:
            llm_result = llm_call_j(prompt)
            
            if self.is_print:
                print(f"\n[Generate Sorting Question] LLM 输出:")
                print(str(llm_result)[:300] + "..." if len(str(llm_result)) > 300 else str(llm_result))
            
            # 解析结果
            if isinstance(llm_result, str):
                start_idx = llm_result.find('{')
                end_idx = llm_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = llm_result[start_idx:end_idx]
                    try:
                        result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"[Generate Sorting Question] JSON 解析失败：{e}")
                        return None
                else:
                    return None
            elif isinstance(llm_result, dict):
                result = llm_result
            else:
                return None
            
            question = result.get('question', '')
            answer = result.get('answer', '')
            correct_order = result.get('correct_order', [])
            
            if not question or not answer:
                return None
            
            # 构建完整的问题数据
            required_events_id = [str(event.get('event_id', '')) for event in events]
            question_data = {
                'question': question,
                'answer': answer,
                'score_points': [
                    {
                        'description': f"准确回答出{len(events)}个事件的时间顺序",
                        'score': 10
                    }
                ],
                'required_events_id': required_events_id
            }
            
            return question_data
            
        except Exception as e:
            print(f"[Generate Sorting Question] 生成失败：{e}")
            return None

    def _check_and_rewrite_event_descriptions(self, events: List[Dict[str, Any]],
                                               question_data: Dict[str, Any],
                                               year: int,
                                               event_mapping: Dict[int, Dict] = None) -> Dict[str, Any]:
        """
        Step 4: 分析并提取可能会干扰到题面的相似事件，决定是否需要重写题面中对事件的描述

        Args:
            events: 选定的事件列表
            question_data: 已生成的问题数据
            year: 年份
            event_mapping: 索引 -> {original_event, located_events} 映射

        Returns:
            更新后的问题数据（如果需要重写则包含重写后的描述）
        """
        try:
            # 提取问题中的事件描述
            question = question_data.get('question', '')
            if not question:
                return question_data

            print(f"\n[_check_and_rewrite] ========== Step 4 开始 ==========")
            print(f"[_check_and_rewrite] 原始问题:\n{question[:200]}...")

            # Step 4a: 检查事件是否有 similar_events 字段，构建事件列表
            events_with_similar = []
            for event in events:
                similar_events = event.get('similar_events', [])
                if similar_events and len(similar_events) > 0:
                    events_with_similar.append({
                        'event_id': event.get('event_id', ''),
                        'description': event.get('event_description', '') or event.get('description', ''),
                        'date': event.get('date', ''),
                        'similar_events': similar_events
                    })

            if not events_with_similar:
                print("[_check_and_rewrite] 没有相似事件，跳过重写")
                return question_data

            print(f"[_check_and_rewrite] 共 {len(events_with_similar)} 个事件有相似事件")

            # Step 4b: 输入题面和相似事件数组，让 LLM 判断哪些事件的描述需要重写
            print("[_check_and_rewrite] Step 4b: LLM 判断哪些事件需要重写...")
            decision_prompt = f"""
            作为时序问题质量审核专家，请分析以下排序问题中的事件描述是否可能导致答题时混淆。

            【原始问题】
            {question}

            【事件及其相似事件列表】
            {json.dumps(events_with_similar, ensure_ascii=False, indent=2)}

            **混淆判定标准**
            - 如果题面描述过于笼统（如"去云南旅行"），而存在多个相似事件（如"去云南丽江旅行"、"去云南昆明旅行"），会导致答题者无法确定具体是哪一个
            - 如果描述中包含的关键词（地点、人物、具体事项等）能在多个相似事件中找到，描述就不够清晰
            - 如果描述缺乏当日独特锚点（如当天其他事件），仅靠事件本身描述无法唯一确定是哪一天

            **决策规则**
            - 对于"需要重写"的事件：描述不足以区分目标事件和相似事件，需要加入当日其他事件作为锚点
            - 对于"不需要重写"的事件：描述已经足够清晰独特，或者没有相似事件

            **输出格式**
            请以 JSON 格式返回：
            {{
                "events_needing_rewrite": [
                    {{
                        "event_id": "事件ID",
                        "original_description": "原始描述",
                        "reason": "需要重写的原因（如：描述与相似事件过于相似、缺乏当日锚点等）"
                    }}
                ],
                "events_ok": [
                    {{
                        "event_id": "事件ID",
                        "description": "原始描述",
                        "reason": "为什么不需要重写（如：描述已包含独特细节、无相似事件等）"
                    }}
                ]
            }}
            """
            print(f"\n[_check_and_rewrite] Step 4b 决策 prompt:")
            print(f"  - 事件数量: {len(events_with_similar)}")
            for i, evt in enumerate(events_with_similar):
                print(f"  - 事件[{i+1}]: id={evt.get('event_id', '')}, similar_events数量={len(evt.get('similar_events', []))}")
            print(f"\n[_check_and_rewrite] ========== Step 4b LLM 输入 ==========")
            print(decision_prompt[:2000] + "..." if len(decision_prompt) > 2000 else decision_prompt)
            print(f"========== Step 4b LLM 输入结束 ==========")
            print(f"[_check_and_rewrite] Step 4b 决策 prompt 长度: {len(decision_prompt)}")

            decision_result = llm_call_j(decision_prompt)

            print(f"\n[_check_and_rewrite] ========== Step 4b LLM 输出 ==========")
            print(str(decision_result)[:2000] + "..." if len(str(decision_result)) > 2000 else str(decision_result))
            print(f"========== Step 4b LLM 输出结束 ==========")

            # 解析决策结果
            if isinstance(decision_result, str):
                start_idx = decision_result.find('{')
                end_idx = decision_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    decision_result = json.loads(decision_result[start_idx:end_idx])
            if not isinstance(decision_result, dict):
                print("[_check_and_rewrite] 决策结果解析失败，跳过")
                return question_data

            events_needing_rewrite = decision_result.get('events_needing_rewrite', [])
            events_ok = decision_result.get('events_ok', [])
            print(f"[_check_and_rewrite] 需要重写的事件: {len(events_needing_rewrite)}, 不需要重写的事件: {len(events_ok)}")

            if not events_needing_rewrite:
                print("[_check_and_rewrite] 没有事件需要重写")
                return question_data

            # Step 4c: 对于需要重写的事件，输入当日事件，让 LLM 加入独特内容来重写描述
            print(f"[_check_and_rewrite] Step 4c: 为 {len(events_needing_rewrite)} 个需要重写的事件获取当日事件...")

            # 构建 event_id 到 events_for_check 条目的映射
            events_check_map = {}
            for ec in events:
                eid = str(ec.get('event_id', ''))
                events_check_map[eid] = ec

            # 准备需要重写的事件及其当日事件
            rewrite_context = []
            for item in events_needing_rewrite:
                event_id = item.get('event_id', '')
                original_desc = item.get('original_description', '')

                # 从 events_for_check 中获取相似事件和当日事件信息
                ec_item = events_check_map.get(str(event_id), {})
                similar_events = ec_item.get('similar_events', [])
                daily_on_date = None

                # 获取目标日期
                target_date = None
                for evt in events:
                    if str(evt.get('event_id', '')) == str(event_id):
                        date_str = evt.get('date', '')
                        # 处理 date 可能是列表的情况
                        if isinstance(date_str, list):
                            date_str = date_str[0] if date_str else ''
                        if '至' in date_str:
                            target_date = date_str.split('至')[0].strip()[:10]
                        else:
                            target_date = date_str[:10] if date_str else None
                        break

                # 如果 events_for_check 中没有当日事件，尝试用 _get_daily_events_by_date 获取
                if not daily_on_date and target_date:
                    daily_on_date = self._get_daily_events_by_date(target_date)

                # 提取当日其他事件的 event_id（排除目标事件本身）
                anchor_event_ids = []
                anchor_event_descs = []
                for de in daily_on_date:
                    de_id = str(de.get('event_id', ''))
                    if de_id and de_id != str(event_id):
                        anchor_event_ids.append(de_id)
                        anchor_event_descs.append({
                            'event_id': de_id,
                            'description': de.get('description', '')[:100]
                        })

                rewrite_context.append({
                    'event_id': event_id,
                    'original_description': original_desc,
                    'reason': item.get('reason', ''),
                    'target_date': target_date,
                    'similar_events': similar_events,  # 相似事件列表，帮助 LLM 理解混淆点
                    'daily_events_on_date': anchor_event_descs,  # 当日其他事件（用于提取锚点）
                    'anchor_event_ids': anchor_event_ids
                })

            # 调用 LLM 重写描述
            rewrite_prompt = f"""
作为描述优化专家，请为以下需要重写的事件生成更具区分性的描述。

【事件列表】
{json.dumps(rewrite_context, ensure_ascii=False, indent=2)}

**重写要求**
1. **分析混淆原因**：对比 original_description 和 similar_events，找出导致混淆的关键点
2. **使用当日事件作为锚点**：从 daily_events_on_date 中选择最能区分的事件作为锚点
3. **重写格式**：将锚点信息自然融入描述，如"事件A（当天还发生了事件B）"
4. 不要减少任何原事件内容，只增加锚点信息
5. anchor_event_ids 必须填写实际使用了的当日事件的 event_id

**输出格式**
请以 JSON 格式返回：
{{
    "rewritten_descriptions": [
        {{
            "event_id": "事件ID",
            "original_description": "原始描述",
            "rewritten_description": "重写后的描述（增加当日其他事件作为锚点）",
            "anchor_added": "新增的当日其他事件锚点描述",
            "anchor_event_ids": ["使用的当日其他事件event_id列表"]
        }}
    ]
}}
"""
            print(f"\n[_check_and_rewrite] Step 4c 重写 prompt:")
            print(f"  - 需要重写的事件数量: {len(events_needing_rewrite)}")
            for i, evt in enumerate(events_needing_rewrite):
                print(f"  - 事件[{i+1}]: id={evt.get('event_id', '')}, reason={evt.get('reason', '')[:50]}...")
            print(f"\n========== Step 4c LLM 输入 ==========")
            print(rewrite_prompt[:3000] + "..." if len(rewrite_prompt) > 3000 else rewrite_prompt)
            print(f"========== Step 4c LLM 输入结束 ==========")

            rewrite_result = llm_call_j(rewrite_prompt)
            print(f"\n========== Step 4c LLM 输出 ==========")
            print(str(rewrite_result)[:2000] + "..." if len(str(rewrite_result)) > 2000 else str(rewrite_result))
            print(f"========== Step 4c LLM 输出结束 ==========")

            # 解析重写结果
            if isinstance(rewrite_result, str):
                start_idx = rewrite_result.find('{')
                end_idx = rewrite_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    rewrite_result = json.loads(rewrite_result[start_idx:end_idx])
            if not isinstance(rewrite_result, dict):
                print("[_check_and_rewrite] 重写结果解析失败，跳过")
                return question_data

            rewritten_descriptions = rewrite_result.get('rewritten_descriptions', [])
            print(f"[_check_and_rewrite] 共 {len(rewritten_descriptions)} 个事件被重写")

            if not rewritten_descriptions:
                print("[_check_and_rewrite] 没有事件被重写")
                return question_data

            # 打印重写后的描述
            print(f"\n[_check_and_rewrite] ========== 重写后的描述 ==========")
            for item in rewritten_descriptions:
                print(f"  事件ID: {item.get('event_id', '')}")
                print(f"  原始描述: {item.get('original_description', '')[:80]}...")
                print(f"  重写后: {item.get('rewritten_description', '')[:80]}...")
                print(f"  新增锚点: {item.get('anchor_added', '')}")
                print(f"  锚点event_ids: {item.get('anchor_event_ids', [])}")
                print(f"  ---")

            # 构建事件ID到新描述的映射
            desc_map = {}
            for item in rewritten_descriptions:
                event_id = item.get('event_id', '')
                rewritten = item.get('rewritten_description', '')
                if event_id and rewritten:
                    desc_map[event_id] = rewritten

            print(f"[_check_and_rewrite] 重写后的描述映射: {list(desc_map.keys())}")
            print(f"[_check_and_rewrite] ========== Step 4 结束 ==========")

            # 更新问题文本中的事件描述标记
            question_data['rewritten_descriptions'] = desc_map
            question_data['needs_rewrite'] = True
            question_data['rewrite_details'] = rewritten_descriptions

            # Step 5: 调用 LLM 将重写后的描述替换到问题文本中
            print(f"\n[_check_and_rewrite] Step 5: 调用 LLM 将重写后的描述替换到问题文本...")
            replace_prompt = f"""
作为文本替换专家，请根据【重写描述映射】将【原始问题】中的对应描述替换为【重写后的描述】。

【原始问题】
{question_data.get('question', '')}

【重写描述映射】
{json.dumps(desc_map, ensure_ascii=False, indent=2)}

**替换要求**
1. 找到【原始问题】中每个 event_id 对应的描述句
2. 将该描述句完整替换为【重写描述映射】中对应 event_id 的新描述
3. 保持问题中其他内容不变，包括编号格式
4. 如果某个 event_id 在原始问题中找不到对应描述，保持原样

**输出格式**
请以 JSON 格式返回：
{{
    "rewritten_question": "替换后的完整问题文本"
}}
"""
            print(f"\n========== Step 5 LLM 输入 ==========")
            print(replace_prompt[:2000] + "..." if len(replace_prompt) > 2000 else replace_prompt)
            print(f"========== Step 5 LLM 输入结束 ==========")

            replace_result = llm_call_j(replace_prompt)
            print(f"\n========== Step 5 LLM 输出 ==========")
            print(str(replace_result)[:2000] + "..." if len(str(replace_result)) > 2000 else str(replace_result))
            print(f"========== Step 5 LLM 输出结束 ==========")

            # 解析替换结果
            if isinstance(replace_result, str):
                start_idx = replace_result.find('{')
                end_idx = replace_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    replace_result = json.loads(replace_result[start_idx:end_idx])

            if isinstance(replace_result, dict):
                new_question = replace_result.get('rewritten_question', '')
                if new_question:
                    question_data['question'] = new_question
                    print(f"[_check_and_rewrite] Step 5: 问题文本已更新")

            return question_data

        except Exception as e:
            print(f"[_check_and_rewrite] 分析失败：{e}")
            import traceback
            traceback.print_exc()
            return question_data

    def _get_daily_events_by_date(self, date_str: str) -> List[Dict[str, Any]]:
        """
        根据日期获取该天的所有 daily_event 事件

        Args:
            date_str: 日期字符串，格式 YYYY-MM-DD

        Returns:
            该天的所有事件列表
        """
        target_date = date_str[:10] if len(date_str) > 10 else date_str
        matching_events = []

        if not isinstance(self.daily_event, list):
            return matching_events

        for event in self.daily_event:
            if not isinstance(event, dict):
                continue
            event_dates = event.get('date', [])
            if not isinstance(event_dates, list):
                continue
            for time_range in event_dates:
                if '至' in time_range:
                    start_part = time_range.split('至')[0].strip()[:10]
                    if start_part == target_date:
                        matching_events.append(event)
                        break
                else:
                    # 单个日期
                    event_date = time_range.strip()[:10]
                    if event_date == target_date:
                        matching_events.append(event)
                        break

        return matching_events

    def _save_questions(self, questions: List[Dict[str, Any]], year: str):
        """
        保存问题到文件（已移至 all_qa_generator 统一处理，注释掉）

        Args:
            questions: 问题列表
            year: 年份
        """
        # # 保存逻辑已移至 all_qa_generator 统一处理
        # if not self.phone_data_dir:
        #     print("[Save] phone_data_dir 未设置，跳过保存")
        #     return
        #
        # try:
        #     parent_dir = os.path.dirname(self.phone_data_dir)
        #     file_path = os.path.join(parent_dir, f"temporal_qa_{year}.json")
        #
        #     with open(file_path, 'w', encoding='utf-8') as f:
        #         json.dump(questions, f, ensure_ascii=False, indent=2)
        #
        #     print(f"\n[Save] 问题已保存到：{file_path}")
        #     print(f"[Save] 共保存{len(questions)}个问题")
        #
        #     # 统计各类问题数量
        #     type_counts = {}
        #     for q in questions:
        #         qtype = q.get('question_type', 'unknown')
        #         type_counts[qtype] = type_counts.get(qtype, 0) + 1
        #
        #     print(f"[Save] 问题类型分布：{type_counts}")
        # except Exception as e:
        #     print(f"[Save] 保存失败：{e}")
    
    def _generate_frequency_count_questions(self, event_groups: Dict[str, Any], year: int) -> List[Dict[str, Any]]:
        """
        生成次数统计问题：基于相似事件数组，遍历相似事件数组，调用llm选取同类事件，
        生成"我今年XXX了几次"，"我上一次XX是XX"这种类型的问题。
        考察模型对相似但不是同一个事件的定位识别和区分能力。
        
        Args:
            event_groups: 相似事件分组结果
            year: 年份
            
        Returns:
            次数统计问题列表
        """
        print(f"\n{'='*80}")
        print(f"[Frequency Count Agent] 开始为 {year} 年生成次数统计问题...")
        print(f"{'='*80}")
        
        questions = []
        groups = event_groups.get('event_groups', [])
        
        if not groups:
            print("[Frequency Count Agent] 没有事件分组数据")
            return questions
        
        print(f"[Frequency Count Agent] 共有 {len(groups)} 个事件组")
        
        # Step 1: 调用LLM筛选重要、独特的事件组
        print(f"\n[Frequency Count Agent] 开始筛选重要、独特的事件组...")
        filtered_groups = self._filter_important_event_groups(groups)
        filtered_groups = [filtered_groups[0]]
        if not filtered_groups:
            print("[Frequency Count Agent] 筛选后没有符合条件的事件组")
            return questions
        
        print(f"[Frequency Count Agent] 筛选后剩余 {len(filtered_groups)} 个事件组")
        
        # Step 2: 遍历筛选后的事件组，生成问题（20线程并行）
        print(f"\n[Frequency Count Agent] 开始20线程并行生成问题...")
        questions = []
        
        import concurrent.futures
        
        def process_single_group(group):
            """处理单个事件组的问题生成"""
            try:
                group_name = group.get('group_name', '')
                events = group.get('events', [])
                
                if not events or len(events) < 2:
                    return []
                
                group_questions = self._generate_questions_for_event_group(group_name, events, year)
                
                if group_questions:
                    print(f"[Frequency Count Agent] 事件组 '{group_name}' 生成了 {len(group_questions)} 个问题")
                
                return group_questions
            except Exception as e:
                group_name = group.get('group_name', '未知')
                print(f"[Frequency Count Agent] 处理事件组 '{group_name}' 时出错: {e}")
                return []
        
        # 使用 ThreadPoolExecutor 并行处理，最多20线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # 提交所有任务
            future_to_group = {
                executor.submit(process_single_group, group): group
                for group in filtered_groups
            }
            
            # 收集结果
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_group):
                try:
                    result = future.result()
                    if result:
                        questions.extend(result)
                    completed_count += 1
                    if completed_count % 5 == 0 or completed_count == len(filtered_groups):
                        print(f"[Frequency Count Agent] 已完成 {completed_count}/{len(filtered_groups)} 个事件组的处理")
                except Exception as e:
                    print(f"[Frequency Count Agent] 任务执行失败：{e}")
        print(f"\n[Frequency Count Agent] 总共生成 {len(questions)} 个次数统计问题")
        return questions
    
    def _filter_important_event_groups(self, groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        调用LLM筛选重要、独特的事件组，去除日常、多发的组别
        
        Args:
            groups: 事件组列表
            
        Returns:
            筛选后的重要事件组列表
        """
        # 准备事件组数据
        groups_data = []
        for i, group in enumerate(groups):
            group_name = group.get('group_name', '')
            events = group.get('events', [])
            groups_data.append({
                'index': i,
                'group_name': group_name,
                'event_count': len(events),
                'events': [
                    {
                        'description': e.get('description', '')[:100]  # 截断描述
                    } for e in events[:3]  # 只取前3个事件作为示例
                ]
            })
        
        prompt = f"""
        作为事件重要性评估专家，请从以下事件组中筛选出重要、独特、不平常的组别。
        
        【候选事件组列表】（共{len(groups_data)}个）
        {json.dumps(groups_data, ensure_ascii=False, indent=2)}
        
        **筛选标准**
        
        1. **排除习惯类和高频事件组**（最高优先级）：
           - **运动健身习惯**：如跑步、健身房锻炼、瑜伽、游泳等规律性运动
           - **日常饮食习惯**：如普通用餐、喝咖啡、喝茶等每天都会做的事
           - **学习工作习惯**：如日常阅读、写日记、常规工作会议等
           - **社交习惯**：如每周固定聚会、每月例行活动等
           - **其他高频习惯**：任何每个月都会做、经常发生的事件
           - 判断标准：如果这个事件组代表的是一个持续的习惯或例行公事，应该排除
        
        2. **排除日常、多发的组别**：
           - 正常情况下一个月会发生四次以上的事件组
           - 例如：日常通勤、常规购物、日常工作等
           - 例如：每周的例行活动、每天的固定习惯
        
        3. **排除过于细节的组别**：
           - 记录的内容过于琐碎、缺乏整体意义
           - 例如：每天喝水、每次开门、每顿饭的具体菜品等
        
        4. **保留重要、独特的组别**（优先选择）：
           - 不同平常、有特殊意义的事件组
           - 例如：旅行出游、重要会议、特殊聚会、学习培训等
           - 例如：健康医疗（非例行体检）、社交活动（非例行聚会）、成就里程碑等
           - 一年发生次数不多，但每次都有纪念价值
           - 突发的、计划外的重要事件
        
        5. **判断原则**：
           - **关键区分**：习惯类 vs 特殊事件
             * 习惯类：规律性、可预期、频率高（如每周跑步、每月聚餐）→ 排除
             * 特殊事件：偶发性、不可预期、频率低（如一次旅行、一次重要会议）→ 保留
           - 如果这个事件组代表的是用户的日常生活习惯，应该排除
           - 如果这个事件组代表的是用户的特殊经历或重要活动，应该保留
           - 考虑事件的稀有性、重要性、纪念价值
        
        **输出要求**
        - 返回选中事件组的索引列表
        - 最多选择10个最重要的事件组
        - **按独特性和非日常性排序**：
          * 最独特、最非日常的事件组排在前面
          * 排序优先级：独特体验/出行游玩 > 重要会议/特殊活动 > 一般社交/学习
          * 例如：旅行出游（最高）> 重要客户会议 > 朋友婚礼 > 培训课程 > 普通聚会（最低）
        
        请以 JSON 格式返回：
        {{
            "selected_indices": [0, 2, 5, ...],
            "reason": "筛选原因说明，特别指出排除了哪些习惯类/高频事件组，以及排序依据"
        }}
        
        **示例**
        {{
            "selected_indices": [1, 3, 7],
            "reason": "排除了'跑步健身'（每周3次的运动习惯）、'普通用餐'（每天多次的日常习惯）、'周未聚会'（每月例行的社交习惯）等习惯类和高频事件组；保留了'云南旅行'（一年1次，独特体验）、'重要客户会议'（季度性，工作成就）、'朋友婚礼'（偶发性，特殊社交活动）等重要、独特的组别"
        }}
        """
        
        try:
            llm_result = llm_call_j(prompt)
            
            if self.is_print:
                print(f"\n[Filter Important Event Groups] LLM 输出:")
                print(str(llm_result)[:300] + "..." if len(str(llm_result)) > 300 else str(llm_result))
            
            # 解析结果
            if isinstance(llm_result, str):
                start_idx = llm_result.find('{')
                end_idx = llm_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = llm_result[start_idx:end_idx]
                    try:
                        result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"[Filter Important Event Groups] JSON 解析失败：{e}")
                        return groups[:15]  # 失败时返回前15个
                else:
                    return groups[:15]
            elif isinstance(llm_result, dict):
                result = llm_result
            else:
                return groups[:15]
            
            selected_indices = result.get('selected_indices', [])
            if not selected_indices or not isinstance(selected_indices, list):
                return groups[:15]
            
            # 根据索引获取选中的事件组
            selected = []
            for idx in selected_indices:
                if isinstance(idx, int) and 0 <= idx < len(groups):
                    selected.append(groups[idx])
            
            # 最多返回15个
            return selected[:15]
            
        except Exception as e:
            print(f"[Filter Important Event Groups] 筛选失败：{e}")
            return groups[:15]  # 失败时返回前15个
    
    def _generate_questions_for_event_group(self, group_name: str, events: List[Dict[str, Any]], 
                                            year: int) -> List[Dict[str, Any]]:
        """
        为单个事件组生成次数统计问题（四种类型分别调用LLM）
            
        Args:
            group_name: 事件组名称
            events: 该组的事件列表
            year: 年份
                
        Returns:
            生成的问题列表
        """
        questions = []
            
        # 准备事件数据
        events_data = []
        for event in events:
            date_str = event.get('date', '')
            description = event.get('description', '')
            events_data.append({
                'date': date_str,
                'description': description
            })
            
        # 定义四种问题类型的prompt生成函数
        def get_frequency_prompt():
            return f"""
            作为次数统计问题设计专家，请分析以下事件组是否适合生成次数统计类问题。
            
            【事件组名称】
            {group_name}
            
            【事件列表】（共{len(events_data)}个事件）
            {json.dumps(events_data, ensure_ascii=False, indent=2)}
            
            **关键判断标准**
            
            1. **适合生成次数统计问题的情况**：
               - 事件之间是**重复关系**：多次发生的同类活动
               - 例如：多次去KTV、多次旅行、多次参加会议、多次聚餐等
               - 每次事件都是独立的、相似的活动
            
            2. **不适合生成次数统计问题的情况**（返回空数组）：
               - 事件之间是**顺序关系**：一个事件的多个阶段或步骤
                 * 例如："到达北京" → "游览故宫" → "离开北京"（这是同一次旅行的不同阶段）
               - 事件之间是**因果关系**：前一个事件导致后一个事件
                 * 例如："感冒发烧" → "去医院" → "买药"（这是因果链）
               - 事件之间是**组成关系**：一个大事件的组成部分
                 * 例如："准备材料" → "提交申请" → "等待审批"（这是同一个流程的步骤）
            
            **任务要求**
            1. 首先判断这些事件是否是重复关系
            2. 如果是重复关系，生成2-3个次数统计类问题
            3. 如果不是重复关系（是顺序/因果/组成关系），返回空数组 []
            
            **如果是重复关系，生成问题的要求**：
            - **关键策略 - 设计不同的ask_time**：
               - 为每个问题设定不同的提问时间（ask_time）
               - ask_time应该在事件发生期间的不同时间点
               - 例如：第一次事件后、中间某个时间点、年底等
            - **不同ask_time导致答案不同**：
               - ask_time较早的问题：只统计该时间点之前发生的事件
               - ask_time较晚的问题：统计更多或全部已发生的事件
            - 问题示例：
               - "到6月为止，我今年{group_name}了几次？"
               - "到9月为止，我{group_name}的经历有哪些？"
               - "今年我一共{group_name}了几次？"
            - 答案需要准确反映到该ask_time为止的事件情况
            
            **输出格式**
            请以 JSON 数组格式返回：
            
            如果是重复关系，返回问题数组：
            [
                {{
                    "question": "问题文本",
                    "answer": "答案文本（只包含该ask_time之前发生的事件）",
                    "ask_time": "提问时间（YYYY-MM格式）",
                    "events_referenced": [该ask_time之前发生的事件索引列表]
                }},
                ...
            ]
            
            如果不是重复关系（是顺序/因果/组成关系），返回空数组：
            []
            
            **示例1 - 重复关系（适合生成问题）**
            假设有3次KTV经历：3月、6月、9月
            [
                {{
                    "question": "到6月为止，我今年去KTV唱了几次歌？",
                    "answer": "到6月为止，你一共去了2次KTV：第一次是3月15日和朋友庆祝生日，第二次是6月20日公司团建。",
                    "ask_time": "2025-06",
                    "events_referenced": [0, 1]
                }},
                {{
                    "question": "到12月为止，我今年去KTV唱了几次歌？",
                    "answer": "到12月为止，你一共去了3次KTV：第一次是3月15日和朋友庆祝生日，第二次是6月20日公司团建，第三次是9月10日同学聚会。",
                    "ask_time": "2025-12",
                    "events_referenced": [0, 1, 2]
                }}
            ]
            
            **示例2 - 顺序关系（不适合生成问题）**
            假设是一次旅行的不同阶段："到达大理" → "游览洱海" → "离开大理"
            []
            
            **示例3 - 因果关系（不适合生成问题）**
            假设是因果链："感冒发烧" → "去医院就诊" → "购买药物"
            []
            """
            
        def get_detail_comparison_prompt():
            return f"""
            作为次数统计问题设计专家，请分析以下事件组是否适合生成细节分辨类问题。
            
            【事件组名称】
            {group_name}
            
            【事件列表】（共{len(events_data)}个事件）
            {json.dumps(events_data, ensure_ascii=False, indent=2)}
            
            **关键判断标准**
            
            1. **适合生成细节分辨类问题的情况**：
               - 事件之间是**重复关系**：多次发生的同类活动
               - 例如：多次去KTV、多次旅行、多次参加会议、多次聚餐等
               - 每次事件都是独立的、相似的活动
            
            2. **不适合生成细节分辨类问题的情况**（返回空数组）：
               - 事件之间是**顺序关系**：一个事件的多个阶段或步骤
               - 事件之间是**因果关系**：前一个事件导致后一个事件
               - 事件之间是**组成关系**：一个大事件的组成部分
            
            **任务要求**
            1. 首先判断这些事件是否是重复关系
            2. 如果是重复关系且事件数 >= 2，生成2-3个细节分辨类问题
            3. 如果不是重复关系或事件数 < 2，返回空数组 []
            
            **如果是重复关系，生成问题的要求**：
            - **问题类型多样化**：
              * **最近一次类**："我上一次{group_name}是什么时候？在哪里？和谁一起？"
              * **第n次类**："我第X次{group_name}是什么时候？有什么特别的？"（X可以是2、3等）
              * **细节对比类**："我第X次{group_name}和第Y次{group_name}有什么不同？"
              * **特别经历类**："我{group_name}的经历中，哪次最特别？为什么？"
            - **合理分配ask_time**：
              * 为每个问题设定不同的提问时间（ask_time）
              * ask_time应该在事件发生期间的不同时间点
              * 例如：在第二次事件后、中间某个事件后、年底等
            - **不同ask_time导致答案不同**：
              * ask_time较早：最后一次可能是较早的事件
              * ask_time较晚：最后一次可能是更晚的事件
            - 答案需要给出详细的事件信息，包括时间、地点、参与者、活动内容等
            
            **输出格式**
            请以 JSON 数组格式返回：
            
            如果是重复关系且事件数 >= 2，返回问题数组：
            [
                {{
                    "question": "问题文本",
                    "answer": "答案文本（包含详细的事件信息和细节）",
                    "ask_time": "提问时间（YYYY-MM格式）",
                    "events_referenced": [涉及的事件索引列表]
                }},
                ...
            ]
            
            如果不是重复关系或事件数 < 2，返回空数组：
            []
            
            **示例1 - 重复关系（适合生成问题）**
            假设有3次KTV经历：3月、6月、9月
            [
                {{
                    "question": "到6月为止，我上一次去KTV是什么时候？",
                    "answer": "到6月为止，你上一次去KTV是6月20日，和公司同事一起去参加团建活动，地点在市中心的麦乐迪KTV。",
                    "ask_time": "2025-06",
                    "events_referenced": [1]
                }},
                {{
                    "question": "我第二次去KTV是和谁一起去的？有什么特别的活动吗？",
                    "answer": "你第二次去KTV是6月20日，和公司同事一起去参加团建活动，地点在市中心的麦乐迪KTV。这次大家唱了很多经典老歌，还玩了骰子游戏，气氛非常热烈。",
                    "ask_time": "2025-12",
                    "events_referenced": [1]
                }},
                {{
                    "question": "我第三次去KTV和第一次有什么不同？",
                    "answer": "你第一次去KTV是3月15日，和朋友庆祝生日，在星光KTV；第三次是9月10日，和同学参加同学聚会，在万达广场的纯K KTV。第一次是为了庆祝生日，点了蛋糕；第三次是老同学重逢，聊了很多往事。",
                    "ask_time": "2025-12",
                    "events_referenced": [0, 2]
                }}
            ]
            
            **示例2 - 顺序关系（不适合生成问题）**
            假设是一次旅行的不同阶段："到达大理" → "游览洱海" → "离开大理"
            []
            
            **示例3 - 只有1个事件（不适合生成问题）**
            假设只有一次KTV经历
            []
            """
            
        def get_causal_sequence_prompt():
            return f"""
            作为时序推理问题设计专家，请分析以下事件组是否适合生成时间跨度类问题。
            
            【事件组名称】
            {group_name}
            
            【事件列表】（共{len(events_data)}个事件）
            {json.dumps(events_data, ensure_ascii=False, indent=2)}
            
            **关键判断标准**
            
            1. **适合生成时间跨度问题的情况**：
               - 事件之间是**顺序关系**：一个事件的多个阶段或步骤
                 * 例如："到达北京" → "游览故宫" → "离开北京"（同一次旅行的不同阶段）
               - 事件之间是**因果关系**：前一个事件导致后一个事件
                 * 例如："感冒发烧" → "去医院" → "买药"（因果链）
               - 事件之间是**组成关系**：一个大事件的组成部分
                 * 例如："准备材料" → "提交申请" → "等待审批"（同一个流程的步骤）
            
            2. **不适合生成时间跨度问题的情况**（返回空数组）：
               - 事件之间是**重复关系**：多次发生的同类活动
               - 例如：多次去KTV、多次旅行、多次参加会议等
            
            **任务要求**
            1. 首先判断这些事件是否是顺序/因果/组成关系
            2. 如果是且事件数 >= 2，生成1-2个时间跨度类问题
            3. 如果不是（是重复关系）或事件数 < 2，返回空数组 []
            
            **如果是顺序/因果/组成关系，生成问题的要求**：
            - **问题类型**：
              * **时间跨度类**："从XX到XX隔了多久？"、"XX之后多久发生了XX？"
              * **持续时间类**："整个XX过程持续了多长时间？"
            - **问题设计规范**：
              * 选择有因果关系或先后顺序的两个事件（起点和终点）
              * 题面提及起点事件，询问到终点事件的时间跨度
              * 回答者需要计算两个事件之间的天数或时间段
              * 答案需要明确说明时间跨度（多少天/星期/月）
            - **生成1-2个问题即可**，不需要太多
            
            **输出格式**
            请以 JSON 数组格式返回：
            
            如果是顺序/因果/组成关系且事件数 >= 2，返回问题数组：
            [
                {{
                    "question": "问题文本",
                    "answer": "答案文本（包含准确的时间跨度计算）",
                    "ask_time": "{year}-12",
                    "events_referenced": [涉及的两个事件的索引列表]
                }},
                ...
            ]
            
            如果不是（是重复关系）或事件数 < 2，返回空数组：
            []
            
            **示例1 - 顺序关系（适合生成问题）**
            假设是一次旅行的不同阶段："3月10日到达大理" → "3月11日游览洱海" → "3月15日离开大理"
            [
                {{
                    "question": "从我到达大理到离开大理，一共经历了多少天？",
                    "answer": "从你3月10日到达大理到3月15日离开大理，一共经历了6天（包括首尾两天）。这期间你在大理游览了洱海等景点。",
                    "ask_time": "2025-12",
                    "events_referenced": [0, 2]
                }},
                {{
                    "question": "我到达大理后多久开始游览洱海？",
                    "answer": "你3月10日到达大理，第二天（3月11日）就开始游览洱海，间隔了1天。",
                    "ask_time": "2025-12",
                    "events_referenced": [0, 1]
                }}
            ]
            
            **示例2 - 因果关系（适合生成问题）**
            假设是因果链："3月5日感冒发烧" → "3月6日去医院就诊" → "3月7日购买药物"
            [
                {{
                    "question": "我感冒发烧后多久去的医院？",
                    "answer": "你3月5日感冒发烧，第二天（3月6日）就去了医院就诊，间隔了1天。",
                    "ask_time": "2025-12",
                    "events_referenced": [0, 1]
                }},
                {{
                    "question": "从感冒发烧到购买药物，整个过程用了几天？",
                    "answer": "从你3月5日感冒发烧到3月7日购买药物，整个过程用了3天（包括首尾两天）。期间你在3月6日去了医院就诊。",
                    "ask_time": "2025-12",
                    "events_referenced": [0, 2]
                }}
            ]
            
            **示例3 - 重复关系（不适合生成问题）**
            假设有3次KTV经历：3月、6月、9月
            []
            
            **示例4 - 只有1个事件（不适合生成问题）**
            假设只有一次事件
            []
            """
                    
        # 轮流调用三种类型的prompt
        prompt_functions = [
            (get_frequency_prompt, "frequency"),
            (get_detail_comparison_prompt, "detail_comparison"),
            (get_causal_sequence_prompt, "causal_sequence")
        ]
                
        for prompt_func, question_type in prompt_functions:
            try:
                prompt = prompt_func()
                if not prompt:
                    continue
                        
                llm_result = llm_call_j(prompt)
                        
                if self.is_print:
                    print(f"\n[Generate {question_type} Question - {group_name}] LLM 输出:")
                    print(str(llm_result)[:300] + "..." if len(str(llm_result)) > 300 else str(llm_result))
                        
                # 解析结果
                result_items = []
                if isinstance(llm_result, str):
                    # 尝试解析为数组
                    start_idx = llm_result.find('[')
                    end_idx = llm_result.rfind(']') + 1
                    if start_idx != -1 and end_idx != -1:
                        json_str = llm_result[start_idx:end_idx]
                        try:
                            parsed = json.loads(json_str)
                            if isinstance(parsed, list):
                                result_items = parsed
                            elif isinstance(parsed, dict):
                                result_items = [parsed]
                        except json.JSONDecodeError as e:
                            print(f"[Generate {question_type} Question] JSON 解析失败：{e}")
                            continue
                    else:
                        # 尝试解析为单个对象
                        start_idx = llm_result.find('{')
                        end_idx = llm_result.rfind('}') + 1
                        if start_idx != -1 and end_idx != -1:
                            json_str = llm_result[start_idx:end_idx]
                            try:
                                result_item = json.loads(json_str)
                                if isinstance(result_item, dict):
                                    result_items = [result_item]
                            except json.JSONDecodeError as e:
                                print(f"[Generate {question_type} Question] JSON 解析失败：{e}")
                                continue
                elif isinstance(llm_result, list):
                    result_items = llm_result
                elif isinstance(llm_result, dict):
                    result_items = [llm_result]
                        
                if not result_items:
                    continue
                        
                # 处理每个结果项
                for result_item in result_items:
                    if not isinstance(result_item, dict):
                        continue
                            
                    question_text = result_item.get('question', '')
                    answer_text = result_item.get('answer', '')
                            
                    if not question_text or not answer_text:
                        continue
                    
                    # 获取引用的事件索引列表
                    events_referenced = result_item.get('events_referenced', [])
                    
                    # 为每个引用的事件查找对应的 daily_event_id
                    required_events_ids = []
                    if events_referenced and isinstance(events_referenced, list):
                        for idx in events_referenced:
                            if isinstance(idx, int) and 0 <= idx < len(events):
                                ref_event = events[idx]
                                # 调用 _locate_daily_events 查找对应的 daily_event
                                located_events = self._locate_daily_events([ref_event], date_offset=0)
                                if located_events:
                                    # 取第一个匹配的事件ID
                                    event_id = located_events[0].get('event_id', '') or located_events[0].get('atomic_id', '')
                                    if event_id:
                                        required_events_ids.append(str(event_id))
                            
                    # 构建完整的问题数据（标准格式）
                    question_data = {
                        'question': question_text,
                        'answer': answer_text,
                        'score_points': [
                            {
                                'description': f"准确回答问题",
                                'score': 10
                            }
                        ],
                        'required_events_id': required_events_ids
                    }
                            
                    questions.append(question_data)
                        
                print(f"[Generate {question_type} Question - {group_name}] ✓ 成功生成 {len(result_items)} 个问题")
                        
            except Exception as e:
                print(f"[Generate {question_type} Question - {group_name}] 生成失败：{e}")
                continue
            
        return questions
    
    def _generate_time_diff_question_with_llm(self, events: List[Dict[str, Any]], 
                                               year: int) -> Dict[str, Any]:
        """
        调用LLM生成时间差计算问题
        
        Args:
            events: 选定的2个事件
            year: 年份
            
        Returns:
            生成的时间差问题数据
        """
        from datetime import datetime
        
        if not events or len(events) < 2:
            print(f"[Generate Time Diff Question] 事件数量不足: {len(events) if events else 0}")
            return None
        
        event1, event2 = events[0], events[1]
        print(event1)

        print(event2)
        # 提取事件信息
        desc1 = event1.get('name', '') or event1.get('event_name', '') or event1.get('description', '')
        desc2 = event2.get('name', '') or event2.get('event_name', '') or event2.get('description', '')
        print(f"[Generate Time Diff Question] 事件1: {desc1}")
        print(f"[Generate Time Diff Question] 事件2: {desc2}")
        if not desc1 or not desc2:
            return None
        
        # 计算时间差
        date1_str = ''
        date2_str = ''
        diff_days = 0
        try:
            # date 字段可能是列表或字符串，需要先处理
            date1_raw = event1.get('date', '')
            date2_raw = event2.get('date', '')
            
            # 如果是列表，取第一个元素
            if isinstance(date1_raw, list):
                date1_raw = date1_raw[0] if date1_raw else ''
            if isinstance(date2_raw, list):
                date2_raw = date2_raw[0] if date2_raw else ''
            
            # 提取日期部分（去掉时间）
            date1_str = date1_raw.split('至')[0].strip()[:10] if '至' in date1_raw else date1_raw.strip()[:10]
            date2_str = date2_raw.split('至')[0].strip()[:10] if '至' in date2_raw else date2_raw.strip()[:10]
            
            date1 = datetime.strptime(date1_str, '%Y-%m-%d')
            date2 = datetime.strptime(date2_str, '%Y-%m-%d')
            diff_days = abs((date2 - date1).days)
        except Exception as e:
            print(f"[Generate Time Diff Question] 日期解析失败: {e}")
            date1_str = ''
            date2_str = ''
            diff_days = 0
        
        # 获取事件2对应日期的所有 daily_event，作为背景信息
        daily_events_on_date2 = []
        if date2_str and isinstance(self.daily_event, list):
            for event in self.daily_event:
                if isinstance(event, dict) and 'date' in event:
                    event_dates = event.get('date', [])
                    if isinstance(event_dates, list):
                        for time_range in event_dates:
                            if '至' in time_range:
                                event_date = time_range.split('至')[0].strip()[:10]
                            else:
                                event_date = time_range[:10]
                            
                            if event_date == date2_str:
                                daily_events_on_date2.append({
                                    'event_id': event.get('event_id', ''),
                                    'name': event.get('name', '') or event.get('event_name', ''),
                                    'description': event.get('description', '')[:200],  # 限制长度
                                    'type': event.get('type', ''),
                                    'participant': event.get('participant', []),
                                    'location': event.get('location', '')
                                })
                                break
        print(daily_events_on_date2)
        print(f"[Generate Time Diff Question] 事件2日期 {date2_str} 共有 {len(daily_events_on_date2)} 个事件")
        
        prompt = f"""
        作为时间推理问题设计专家，请基于以下两个事件，生成一个需要时间推理的问题。
                
        【事件1】
        {desc1}
        日期：{date1_str}
                
        【事件2（目标事件）】
        {desc2}
        日期：{date2_str}
        
        【事件2日期当天的其他事件】（共{len(daily_events_on_date2)}个）
        {json.dumps(daily_events_on_date2, ensure_ascii=False, indent=2) if daily_events_on_date2 else '无其他事件'}
                
        **任务要求**
                        
        1. **问题设计规范**：
           - 问题应该涉及时间推理,例如:"事件1的X天/星期后,我做了什么?"
           - **题面对事件1的描述必须带有月份信息**（如"5月我去云南旅游回来后"）
           - **如果事件1本身比较模糊或是可能经常发生的事件,必须带上事件1的具体日期**（如"5月10日我跑步回来后"）
             * 判断标准:事件名称过于通用(如"吃饭"、"开会"、"运动")、缺少独特特征、或可能在多日重复发生
             * 示例:"5月15日锻炼后"、"6月3日完成Python课程学习后"
           - 题面中只描述事件1的细节,不直接提及事件2
           - 回答者必须根据日期计算(事件1日期 + X天/星期),然后推理定位到事件2
           - **关键:题面必须包含能唯一定位事件2的最小信息**
             * **最小信息原则**：只给出能区别于当天其他事件的最少必要信息，不要添加冗余细节
             * 仔细查看【事件2日期当天的其他事件】列表，分析哪些特征能唯一区分事件2
             * 如果某个特征足以唯一定位，就不要添加额外信息
             
             **示例场景**：
             - ✅ 正确：如果当天只有和小明做的事 → "XX3天后我和小明谈了什么"
             - ❌ 错误：如果"和小明谈了什么"已足够 → 不要说"XX3天后在和平饭店和小明谈了什么"（地点是冗余的）
             - ✅ 正确：如果当天有多个和同事做的事，但只有和小明做的事 → "XX3天后我和小明谈了什么"
             - ✅ 正确：如果当天有多个地点的活动，但只有和平饭店有活动 → "XX3天后我在和平饭店做了什么"
             - ✅ 正确：如果和平饭店有多个活动，但只有就餐后和同事谈话 → "XX3天后我在和平饭店就餐后和同事谈了什么"（用"同事"指代小明，因为当天没有其他同事的事）
             - ❌ 错误：如果"在和平饭店就餐"已足够 → 不要说"在和平饭店就餐并点了招牌菜"（点菜是冗余的）
             
             **核心思想**：
             - 优先使用最独特的单一特征（独特人物、独特地点、独特活动等）
             - 如果单一特征不足以区分，才组合多个特征
             - 可以使用指代词（如"同事"、"朋友"）隐藏具体人名，前提是当天没有其他类似人物
             - 目标是让题面简洁但足够精确
           
           - 问题应该以第一人称口吻，自然流畅
                
        2. **时间表达多样化**：
           - 可以使用"X天后"、"X个星期后"、"X周后"等表达
           - 也可以使用"过了X天"、"相隔X天之后"等
           - 确保时间间隔与实际日期差匹配
                
        3. **答案要求**：
           - 明确指出通过时间推理定位到的事件
           - 提供事件2的关键细节（时间、地点、内容等）
           - 说明推理过程（事件1日期 + X天 = 事件2日期）
                
        **输出格式**
        请以 JSON 格式返回：
        {{
            "question": "时间推理问题（只描述事件1，通过时间推理定位事件2，题面使用最小信息唯一定位事件2）",
            "answer": "答案（包含推理过程和事件2的详细信息）",
            "reasoning_days": 实际相隔的天数,
            "reasoning_description": "推理说明，如'从{{date1_str}}往后推{{diff_days}}天是{{date2_str}}'"
        }}
                
        **示例**
        {{
            "question": "我去云南旅游回来后的第15天，我在市体育中心参加了什么比赛？成绩如何？",
            "answer": "你去云南旅游是5月10-15日，回来后的第15天是5月30日。那天你在市体育中心参加了马拉松比赛，全程42公里，成绩是3小时45分。\n\n推理过程：从5月15日（旅游结束）往后推15天是5月30日，这天你参加了马拉松比赛。",
            "reasoning_days": 15,
            "reasoning_description": "从2025-05-15往后推15天是2025-05-30"
        }},
        {{
            "question": "我参加完马拉松比赛的3个星期后，我和小李在KTV庆祝了什么？",
            "answer": "你参加马拉松比赛是3月15日，3个星期后（21天后）是4月5日。那天你和朋友小李在麦乐迪KTV庆祝生日，点了很多歌，还吃了蛋糕。\n\n推理过程：从3月15日往后推21天（3个星期）是4月5日，这天你在KTV庆生。",
            "reasoning_days": 21,
            "reasoning_description": "从2025-03-15往后推21天是2025-04-05"
        }},
        {{
            "question": "我完成Python课程学习后的第7天，我在和平饭店就餐后和同事谈了什么？",
            "answer": "你完成Python课程是6月10日，7天后是6月17日。那天你在和平饭店就餐后和同事小明讨论了项目合作方案，决定下周开始实施。\n\n推理过程：从6月10日往后推7天是6月17日，这天你在和平饭店与同事谈话。",
            "reasoning_days": 7,
            "reasoning_description": "从2025-06-10往后推7天是2025-06-17"
        }}
                
        **注意事项**
        - 题面不要直接提到事件2的名称或完整细节
        - **题面必须使用最小信息唯一定位事件2**（参考上述最小信息原则）
        - **一定要参考【事件2日期当天的其他事件】列表，分析哪些特征是必要的，哪些是冗余的**
        - 时间间隔要与实际日期差一致
        - 答案要包含完整的推理过程
        - 问题要像真实用户在回忆和询问
        """
        
        try:
            llm_result = llm_call_j(prompt)
            
            if self.is_print:
                print(f"\n[Generate Time Diff Question] LLM 输出:")
                print(str(llm_result)[:300] + "..." if len(str(llm_result)) > 300 else str(llm_result))
            
            # 解析结果
            if isinstance(llm_result, str):
                start_idx = llm_result.find('{')
                end_idx = llm_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = llm_result[start_idx:end_idx]
                    try:
                        result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"[Generate Time Diff Question] JSON 解析失败：{e}")
                        return None
                else:
                    return None
            elif isinstance(llm_result, dict):
                result = llm_result
            else:
                return None
            
            question = result.get('question', '')
            answer = result.get('answer', '')
            reasoning_days = result.get('reasoning_days', diff_days)
            reasoning_description = result.get('reasoning_description', '')
            
            if not question or not answer:
                return None
            
            question_data = {
                'question': question,
                'answer': answer,
                'score_points': [
                    {
                        'description': f"准确回答出时间推理结果，相隔{diff_days}天",
                        'score': 10
                    }
                ],
                'required_events_id': [str(event1.get('event_id', '')), str(event2.get('event_id', ''))]
            }
            
            return question_data
            
        except Exception as e:
            print(f"[Generate Time Diff Question] 生成失败：{e}")
            return None

    
    def evidence_refine(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evidence Refine: 分析并优化问题的证据数据，确保手机数据能够充足反映事件并提供足够回答问题的数据

        Args:
            question: 优化后的问题

        Returns:
            优化证据后的问题
        """
        print(f"\n[Evidence Refine] 开始优化问题的证据数据...")

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
            1. **非必要不生成**：只有当十分确定缺乏关键信息，或缺乏足以支持回答的信息时，才考虑新增。若已有数据能大致反映事件则不用新增。
            2. **重点优先**：不需要全面反映出事件的所有细节，只关注与问题相关的重点内容，题面中包含的信息必须要全面反映出来。
               - 例如：问题可能只问跑步频率，那只要手机数据能反映出用户跑步了就行，至于距离、时间可以不关心
               - 例如：如果问题问了跑量，则需要反映公里数
            3. **互补性原则**：如果要生成新数据，必须与已有数据形成互补关系，不要和已有数据反映同样的信息。
               - **检查已有数据**：先看看已经有了什么信息
               - **补充缺失信息**：只生成能提供新信息的数据
               - **避免重复**：**严禁**生成与已有数据内容重复或高度相似的数据
               - **示例**：
                 -  已有一条短信提到"今天跑了 5 公里"，但缺少具体时间  生成推送"您于 07:30 完成晨跑 5 公里"
                 -  已有短信"今天跑了 5 公里"，又生成笔记"今天早上我跑了 5 公里"（信息重复）
            4. **最小信息量**：当要新增手机数据时：
               - 先分析缺少的具体信息是什么
               - 只生成包含缺少信息的数据，不要在数据中反映所有信息
               - **禁止**生成一个包含了事件所有信息或可以直接反映答案的充足数据（如一个反映了所有信息的笔记/信息）
               - **示例**：
                 -  缺少跑步公里数：生成短信"今天跑了 5 公里"或推送"你今日已运动 5 公里，十分健康"
                 -  不要生成：详细的跑步笔记，包含时间、路线、配速、心率等完整信息
            5. **谨慎删除**：**除非数据明显不合理，否则不要删除手机数据**。仅在数据存在明显错误或矛盾情况下考虑删除，有些数据是合理的噪声。
            6. 当你决定要生成时，优先生成多个不同类型的手机操作，将信息分散在不同手机操作中，并降低手机操作里的文本描述和题面文本的相似性。来增加题目的挑战性和证据多样性。
                
            
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
                print(f"[Evidence Refine - {event_id}] LLM 分析结果：{llm_result}")
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
                            print(f"   已成功删除 {op_type}:{phone_id}\n")

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
                        if str(event.get('event_id', '')) == str(target_event_id):
                            target_event = event
                            break
                
                generation_tasks.append({
                    'op_type': op_type,
                    'content_summary': content_summary,
                    'target_event_id': target_event_id,
                    'target_event': target_event,
                    'reason': reason
                })
            
            # 并行生成函数
            def generate_single_operation(task):
                """生成单个手机操作数据"""
                op_type = task['op_type']
                content_summary = task['content_summary']
                target_event_id = task['target_event_id']
                target_event = task['target_event']
                reason = task['reason']
                
                try:
                    # 构建 generation_hint 字符串
                    generation_hint = f"需要生成{op_type}类型的数据，内容要求：{content_summary}。原因：{reason}"
                    
                    phone_op_generator = PhoneOperationGenerator()
                    # 使用 PhoneOperationGenerator 生成
                    operations = phone_op_generator.generate(
                        operation_type=op_type,
                        original_event=target_event,
                        question='',  # 时序问题中可能没有具体的 question
                        generation_hint=generation_hint
                    )
                    
                    if operations:
                        print(f"[Evidence Refine] 成功生成 {len(operations)} 条 {op_type} 数据")
                        return operations
                    else:
                        print(f"[Evidence Refine] 生成 {op_type} 数据失败")
                        return []
                        
                except Exception as e:
                    print(f"[Evidence Refine] 生成操作失败：{e}")
                    return []
            
            # 使用 ThreadPoolExecutor 并行生成
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(generate_single_operation, task) for task in generation_tasks]
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        if result:  # result 是一个列表
                            generated_operations.extend(result)
                    except Exception as e:
                        print(f"[Evidence Refine] 生成任务异常：{e}")
            
            # 将生成的操作添加到 phonedata
            if generated_operations:
                print(f"\n[Evidence Refine] 添加 {len(generated_operations)} 条新生成的数据到 phonedata...")
                self._add_operations_to_phonedata(generated_operations)

        # 3. 收集最终的证据数据
        print(f"\n[Evidence Refine] 收集最终证据数据...")
        updated_evidence = []
        
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
                with self.phonedata_lock:  # 加锁保护共享数据
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
        print(f"  - 删除了 {len(to_delete)} 条数据")
        print(f"  - 生成了 {len(generated_operations)} 条新数据")
        print(f"  - 最终证据：{len(updated_evidence)} 条")
        
        return question
