# -*- coding: utf-8 -*-
"""
不可回答问题生成器
生成基于事件但未在事件中描述的、可能真实存在的事件或细节的问题
答案为"无法回答"
"""

import calendar

import json
import os
import random
import threading
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.lifebench.event.templates.template_qa import UNANSWERABLE_QUESTION_TEMPLATE
from src.lifebench.utils.llm_call import llm_call
from .base_generator import BaseQAGenerator



class QAUnanswerableGenerator(BaseQAGenerator):
    """
    不可回答问题生成器
    
    功能流程：
    1. 对于每个月的数据，随机抽取一天的事件
    2. 生成一个这天事件中没有描述的，但可能真实存在的事件或细节的问题
    3. 答案为"无法回答"
    4. 并行对12个月生成，每个月生成5个问题
    """

    def __init__(self, daily_event: List[Dict], event_tree: List[Dict],
                 draft_event: Dict[str, List], phonedata: Dict[str, List],
                 phone_data_dir: str = None, is_print: bool = True,
                 persona_data: Dict = None):
        """
        初始化不可回答问题 QA 生成器

        Args:
            daily_event: daily_event 数据列表
            event_tree: event_tree 数据列表
            draft_event: draft_event 数据字典（按月份组织）
            phonedata: 手机操作数据字典
            phone_data_dir: 手机数据目录路径
            is_print: 是否打印调试信息
            persona_data: 用户画像数据
        """
        # 调用父类的 __init__
        super().__init__()
        self.daily_event = daily_event
        self.event_tree = event_tree
        self.draft_event = draft_event
        self.phonedata = phonedata
        self.phone_data_dir = phone_data_dir
        self.is_print = is_print
        self.persona_data = persona_data or {}

        # 初始化线程锁
        self.phonedata_lock = threading.Lock()
        self.phone_id_lock = threading.Lock()

        # 初始化手机操作生成器

    def _extract_date_from_event(self, event: Dict[str, Any]) -> str:
        """
        从事件中提取日期字符串
        
        Args:
            event: 事件字典
            
        Returns:
            日期字符串 (YYYY-MM-DD)，如果提取失败返回空字符串
        """
        event_dates = event.get('date', [])
        
        # 处理 date 字段：可能是字符串或数组
        if isinstance(event_dates, str):
            time_range = event_dates
        elif isinstance(event_dates, list) and len(event_dates) > 0:
            time_range = event_dates[0]
        else:
            return ''
        
        # 提取日期部分
        if isinstance(time_range, str):
            if '至' in time_range:
                return time_range.split('至')[0].strip()[:10]
            else:
                return time_range[:10]
        
        return ''
    
    def _get_events_by_date(self, target_date: str) -> List[Dict[str, Any]]:
        """
        从 daily_event 中获取指定日期的所有事件
        
        Args:
            target_date: 目标日期 (YYYY-MM-DD)
            
        Returns:
            该日期的事件列表
        """
        events_on_date = []
        
        # daily_event 是列表格式
        if not isinstance(self.daily_event, list):
            return events_on_date
        
        for event in self.daily_event:
            if not isinstance(event, dict):
                continue
            
            event_date = self._extract_date_from_event(event)
            if event_date == target_date:
                events_on_date.append(event)
        
        return events_on_date
    
    def _generate_unanswerable_for_month(self, year: int, month: int, num_questions: int = 5) -> List[Dict[str, Any]]:
        """
        为指定月份生成不可回答问题
        
        Args:
            year: 年份
            month: 月份 (1-12)
            num_questions: 生成的问题数量，默认 5
            
        Returns:
            生成的问题列表
        """
        month_key = f"{year}-{month:02d}"
        print(f"\n[不可回答问题生成] 开始处理月份：{month_key}")
        
        # 1. 检查 daily_event 数据
        if not isinstance(self.daily_event, list) or not self.daily_event:
            print(f"[不可回答问题生成] 警告：daily_event 没有数据，跳过")
            return []
        
        # 2. 收集该月份所有可用的日期（从 daily_event）
        all_dates_in_month = set()
        for event in self.daily_event:
            if isinstance(event, dict):
                event_date = self._extract_date_from_event(event)
                if event_date and event_date.startswith(month_key):
                    all_dates_in_month.add(event_date)
        
        if not all_dates_in_month:
            print(f"[不可回答问题生成] 警告：{month_key} 没有有效日期，跳过")
            return []
        
        all_dates_list = list(all_dates_in_month)
        print(f"[不可回答问题生成] {month_key} 共有 {len(all_dates_list)} 个可用日期")
        
        # 3. 随机采样 num_questions 次日期，每次生成一个问题
        all_questions = []
        for i in range(num_questions):
            # 随机选择一个日期
            selected_date = random.choice(all_dates_list)
            print(f"[不可回答问题生成] 第 {i+1}/{num_questions} 个问题 - 随机选择日期：{selected_date}")
            
            # 获取该日期的所有事件
            events_on_selected_date = self._get_events_by_date(selected_date)
            
            if not events_on_selected_date:
                print(f"[不可回答问题生成] 警告：{selected_date} 没有事件数据，跳过本次生成")
                continue
            
            print(f"[不可回答问题生成] {selected_date} 共有 {len(events_on_selected_date)} 个事件")
            
            # 准备用户画像信息
            persona_info = json.dumps(self.persona_data, ensure_ascii=False, indent=2)
            
            # 准备事件数据（只包含选定日期的事件）
            draft_event_info = json.dumps(events_on_selected_date, ensure_ascii=False, indent=2)
            
            # 使用模板生成问题（每次只生成1个问题）
            prompt = UNANSWERABLE_QUESTION_TEMPLATE.format(
                num_questions=1,
                persona_info=persona_info,
                draft_event_info=draft_event_info
            )
            
            # 调用 LLM 生成问题
            try:
                result = llm_call(prompt)
                
                if self.is_print:
                    print(f"\n[不可回答问题生成] {month_key} 第 {i+1} 个问题 LLM 输出:")
                    print(result)
                
                # 解析 JSON 结果
                start_idx = result.find('{')
                end_idx = result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    result_json = json.loads(result[start_idx:end_idx])
                    questions = result_json.get('questions', [])
                    
                    if questions:
                        question = questions[0]  # 只取第一个问题

                        # 确保问题有必要的字段
                        if 'question_type' not in question:
                            question['question_type'] = 'Unanswerable'
                        if 'answer' not in question:
                            question['answer'] = '无法回答'
                        if 'score_points' not in question:
                            question['score_points'] = [{
                                "description": "准确回答出答案",
                                "score": 10
                            }]
                        # 直接设置 required_events_id，不使用 required_events
                        question['required_events_id'] = []

                        if 'ask_time' not in question:
                            # 随机分配 ask_time，在选定日期之后
                            question['ask_time'] = self._generate_ask_time(selected_date, year, month)

                        all_questions.append(question)
                        print(f"[不可回答问题生成] ✓ 成功生成第 {i+1} 个问题")
                    else:
                        print(f"[不可回答问题生成] ✗ 第 {i+1} 个问题解析为空")
                else:
                    print(f"[不可回答问题生成] ✗ 第 {i+1} 个问题 JSON 解析失败")
                    
            except Exception as e:
                print(f"[不可回答问题生成] ✗ 第 {i+1} 个问题生成失败：{e}")
        
        print(f"[不可回答问题生成] {month_key} 共成功生成 {len(all_questions)}/{num_questions} 个问题")
        return all_questions
    
    def _generate_ask_time(self, event_date: str, year: int, month: int) -> str:
        """
        生成问题的提问时间（具体到日期）

        Args:
            event_date: 事件日期 (YYYY-MM-DD)
            year: 年份
            month: 月份

        Returns:
            提问时间 (YYYY-MM-DD)
        """
        # 解析事件日期
        event_dt = datetime.strptime(event_date, "%Y-%m-%d")

        # 提问时间应该在事件日期之后，最大为 2025-12-31
        max_date = datetime(2025, 12, 31)

        # 从事件日期的下一个月开始
        if event_dt.month == 12:
            next_month_dt = datetime(event_dt.year + 1, 1, 1)
        else:
            next_month_dt = datetime(event_dt.year, event_dt.month + 1, 1)

        # 如果下一个月超过 2025-12，则使用 2025-12-31
        if next_month_dt > max_date:
            return "2025-12-31"

        # 计算可选的月份范围（从 next_month 到 2025-12）
        months_diff = (max_date.year - next_month_dt.year) * 12 + (max_date.month - next_month_dt.month)

        # 随机选择一个偏移月（0 到 months_diff）
        random_offset = random.randint(0, months_diff)

        # 计算目标年月
        target_month_num = next_month_dt.month + random_offset
        target_year = next_month_dt.year + (target_month_num - 1) // 12
        target_month = (target_month_num - 1) % 12 + 1

        # 在该月内随机选择一天（1 到该月最大天数）
        _, last_day = calendar.monthrange(target_year, target_month)
        random_day = random.randint(1, last_day)

        return f"{target_year}-{target_month:02d}-{random_day:02d}"
    
    def QAGen(self, year: int = 2025, num_questions_per_month: int = 5) -> List[Dict[str, Any]]:
        """
        生成不可回答问题
        
        Args:
            year: 年份，默认 2025
            num_questions_per_month: 每个月生成的问题数量，默认 5
            
        Returns:
            生成的所有问题列表
        """
        print(f"\n{'='*60}")
        print(f"开始生成 {year} 年的不可回答问题")
        print(f"每个月生成 {num_questions_per_month} 个问题")
        print(f"{'='*60}\n")
        
        all_questions = []
        
        # 并行处理 12 个月
        with ThreadPoolExecutor(max_workers=12) as executor:
            # 提交所有月份的任务
            future_to_month = {}
            for month in range(1, 13):
                future = executor.submit(self._generate_unanswerable_for_month, year, month)
                future_to_month[future] = month
            
            # 收集结果
            for future in as_completed(future_to_month):
                month = future_to_month[future]
                try:
                    questions = future.result()
                    if questions:
                        all_questions.extend(questions)
                        print(f"[完成] {year}-{month:02d}: 生成 {len(questions)} 个问题")
                    else:
                        print(f"[完成] {year}-{month:02d}: 未生成问题")
                except Exception as e:
                    print(f"[错误] {year}-{month:02d} 处理失败：{e}")
        
        print(f"\n{'='*60}")
        print(f"总共生成 {len(all_questions)} 个不可回答问题")
        print(f"{'='*60}\n")
        
        return all_questions
    
    def save_questions(self, questions: List[Dict[str, Any]], output_path: str):
        """
        保存生成的问题到文件
        
        Args:
            questions: 问题列表
            output_path: 输出文件路径
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(questions, f, ensure_ascii=False, indent=2)
            print(f"成功保存 {len(questions)} 个问题到：{output_path}")
        except Exception as e:
            print(f"保存问题失败：{e}")
