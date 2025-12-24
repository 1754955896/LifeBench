# -*- coding: utf-8 -*-
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from utils.IO import read_json_file, write_json_file
from utils.llm_call import llm_call
from event.templates import *

class FuzzyMemoryBuilder:
    def __init__(self, event_data: List[Dict], persona: Dict, output_dir: str = "../data/"):
        self.event_data = event_data
        self.persona = persona
        self.output_dir = output_dir
        self.monthly_summaries: Dict[str, str] = {}  # 存储月度总结，格式：{"2025-01": "总结内容"}
        self.cumulative_summaries: Dict[str, str] = {}  # 存储累积总结，格式：{"2025-01-2025-02": "总结内容"}
        self.lock = threading.RLock()  # 读写锁，支持多线程读取
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 定义输出文件路径
        self.monthly_file = os.path.join(output_dir, "monthly_summaries.json")
        self.cumulative_file = os.path.join(output_dir, "cumulative_summaries.json")
    
    def _extract_events_by_month(self, year: int, month: int) -> List[Dict]:
        """
        提取指定年份和月份的所有事件
        
        参数:
            year: 年份
            month: 月份 (1-12)
        
        返回:
            List[Dict]: 该月份的事件列表
        """
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        matched_events = []
        
        # 递归提取所有底层事件
        def extract_bottom_events(events: List[Dict]) -> List[Dict]:
            result = []
            for event in events:
                subevents = event.get("subevent", [])
                if not subevents:
                    result.append(event)
                else:
                    result.extend(extract_bottom_events(subevents))
            return result
        
        bottom_events = extract_bottom_events(self.event_data)
        
        # 筛选日期在指定月份内的事件
        for event in bottom_events:
            date_values = event.get("date", [])
            if not isinstance(date_values, list):
                date_values = [date_values]
            
            for date_str in date_values:
                # 解析日期范围
                if "至" in date_str:
                    start_str, end_str = date_str.split("至")
                    try:
                        # 尝试不同的日期格式
                        for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                            try:
                                event_start = datetime.strptime(start_str.strip(), fmt)
                                event_end = datetime.strptime(end_str.strip(), fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            continue  # 所有格式都不匹配
                        
                        # 检查事件是否与目标月份有重叠
                        if not (event_end < start_date or event_start >= end_date):
                            matched_events.append(event)
                            break
                    except ValueError:
                        continue
                else:
                    try:
                        # 尝试不同的日期格式
                        for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                            try:
                                event_date = datetime.strptime(date_str.strip(), fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            continue  # 所有格式都不匹配
                        
                        if start_date <= event_date < end_date:
                            matched_events.append(event)
                            break
                    except ValueError:
                        continue
        
        return matched_events
    
    def _generate_monthly_summary(self, year: int, month: int) -> str:
        """
        生成指定月份的事件总结
        
        参数:
            year: 年份
            month: 月份 (1-12)
        
        返回:
            str: 月度总结内容
        """
        # 提取该月份的事件
        monthly_events = self._extract_events_by_month(year, month)
        
        if not monthly_events:
            return f"{year}年{month}月没有发生任何重要事件。"
        
        # 构建事件描述字符串
        events_desc = "\n".join([
            f"- {event.get('name', '未命名事件')}: {event.get('description', '无描述')} ({event.get('date', [''])[0]})"
            for event in monthly_events
        ])
        
        # 使用LLM生成月度总结
        prompt = f"""
        你是一位记忆专家，请基于以下个人画像和{year}年{month}月的事件，严格按以下标准筛选并总结重要事件：
        仅关注三类事件：
        1. 对个人有显著影响、可能改变未来行为的事件
        2. 导致个人画像需更新的变化性事件
        3. 对一段时期生活产生持续影响的事件
        
        个人画像：{json.dumps(self.persona, ensure_ascii=False, indent=2)}
        
        {year}年{month}月的事件：
        {events_desc}
        
        输出要求：
        - 第一人称
        - 事件+影响的简洁序列格式
        - 极度精简，仅保留核心信息
        - 无冗余描述，直接呈现重点
        """
        
        summary = llm_call(prompt, self.persona.get("context", ""))
        return summary
    
    def build_monthly_summaries(self, year: int = 2025, max_workers: int = 12):
        """
        并行生成12个月的事件总结
        
        参数:
            year: 年份
            max_workers: 并行工作线程数
        """
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交12个月的总结任务
            futures = {
                executor.submit(self._generate_monthly_summary, year, month): month
                for month in range(1, 13)
            }
            
            # 收集结果
            for future in futures:
                month = futures[future]
                try:
                    summary = future.result()
                    month_key = f"{year}-{month:02d}"
                    with self.lock:
                        self.monthly_summaries[month_key] = summary
                except Exception as e:
                    print(f"生成{year}年{month}月总结时出错：{e}")
        
        # 保存月度总结
        self._save_monthly_summaries()
    
    def build_cumulative_summaries(self, year: int = 2025):
        """
        基于月度总结生成累积总结（1月到2月，1月到3月，...，1月到11月）
        
        参数:
            year: 年份
        """
        # 确保月度总结已生成
        if not self.monthly_summaries:
            self.build_monthly_summaries(year)
        
        # 按月份排序月度总结
        sorted_months = sorted(self.monthly_summaries.keys())
        
        # 生成累积总结
        for i in range(2, len(sorted_months) + 1):
            # 获取从1月到当前月的所有月度总结
            months_range = sorted_months[:i]
            start_month = months_range[0]
            end_month = months_range[-1]
            
            # 构建累积总结的输入
            cumulative_input = "\n\n".join([
                f"{month}月总结：{self.monthly_summaries[month]}"
                for month in months_range
            ])
            
            # 使用LLM生成累积总结
            prompt = f"""
            你是一位记忆专家，请基于以下个人画像和从{start_month}到{end_month}的月度总结，严格执行以下要求：
            
            1. 从所有月度总结中筛选出**前10最重要的事件**
            2. 筛选标准：
               - 对个人有显著影响、可能改变未来行为的事件
               - 导致个人画像需更新的变化性事件
               - 对一段时期生活产生持续影响的事件
            
            个人画像：{json.dumps(self.persona, ensure_ascii=False, indent=2)}
            
            月度总结：
            {cumulative_input}
            
            输出要求：
            - 第一人称
            - 事件+影响的简洁序列格式
            - 极度精简，仅保留核心信息
            - 无冗余描述，直接呈现重点
            - 按事件重要性排序
            """
            
            summary = llm_call(prompt, self.persona.get("context", ""))
            
            # 保存累积总结
            with self.lock:
                self.cumulative_summaries[f"{start_month}-{end_month}"] = summary
        
        # 保存累积总结
        self._save_cumulative_summaries()
    
    def _save_monthly_summaries(self):
        """
        保存月度总结到文件
        """
        with open(self.monthly_file, "w", encoding="utf-8") as f:
            json.dump(self.monthly_summaries, f, ensure_ascii=False, indent=2)
        print(f"月度总结已保存到：{self.monthly_file}")
    
    def _save_cumulative_summaries(self):
        """
        保存累积总结到文件
        """
        with open(self.cumulative_file, "w", encoding="utf-8") as f:
            json.dump(self.cumulative_summaries, f, ensure_ascii=False, indent=2)
        print(f"累积总结已保存到：{self.cumulative_file}")
    
    def load_summaries(self):
        """
        从文件加载月度总结和累积总结
        """
        # 加载月度总结
        if os.path.exists(self.monthly_file):
            with open(self.monthly_file, "r", encoding="utf-8") as f:
                with self.lock:
                    self.monthly_summaries = json.load(f)
            print(f"已加载月度总结：{self.monthly_file}")
        
        # 加载累积总结
        if os.path.exists(self.cumulative_file):
            with open(self.cumulative_file, "r", encoding="utf-8") as f:
                with self.lock:
                    self.cumulative_summaries = json.load(f)
            print(f"已加载累积总结：{self.cumulative_file}")
    
    def save_summaries(self):
        """
        将月度总结和累积总结保存到文件
        """
        # 保存月度总结
        with self.lock:
            if write_json_file(self.monthly_file, self.monthly_summaries):
                print(f"月度总结已保存：{self.monthly_file}")
            else:
                print(f"保存月度总结失败：{self.monthly_file}")
        
        # 保存累积总结
        with self.lock:
            if write_json_file(self.cumulative_file, self.cumulative_summaries):
                print(f"累积总结已保存：{self.cumulative_file}")
            else:
                print(f"保存累积总结失败：{self.cumulative_file}")
    
    def get_memory_up_to_month(self, target_date: str) -> str:
        """
        获取从1月到指定月份的累积记忆
        
        参数:
            target_date: 目标日期，格式为"YYYY-MM-DD"
        
        返回:
            str: 累积记忆内容
        """
        try:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d")
            year = date_obj.year
            month = date_obj.month
        except ValueError:
            raise ValueError("日期格式错误，请使用YYYY-MM-DD格式")
        
        # 检查是否有直接匹配的累积总结
        start_key = f"{year}-01"
        end_key = f"{year}-{month:02d}"
        cumulative_key = f"{start_key}-{end_key}"
        
        with self.lock:
            # 如果有完整的累积总结，直接返回
            if cumulative_key in self.cumulative_summaries:
                return self.cumulative_summaries[cumulative_key]
            
            # 否则，获取从1月到目标月的所有月度总结并合并
            # 根据用户期望：2月5号获得1月记录，3月8号获得1-2月记录，以此类推
            months_range = [f"{year}-{m:02d}" for m in range(1, month)]
            
            # 当month=1时，months_range为空列表
            if not months_range:
                return f"{year}年1月之前没有任何重要事件记录。"
            
            available_summaries = [
                self.monthly_summaries.get(month_key, f"{month_key}月没有总结")
                for month_key in months_range
            ]
            
            # 如果没有任何总结，返回空
            if not any("没有总结" not in summary for summary in available_summaries):
                return f"{year}年1月到{month-1}月没有任何重要事件记录。"
            
            # 合并月度总结
            return "\n\n".join([
                f"{month_key}月：{summary}"
                for month_key, summary in zip(months_range, available_summaries)
            ])
    
    def build_all_summaries(self, year: int = 2025):
        """
        生成所有月度总结和累积总结
        
        参数:
            year: 年份
        """
        print("开始生成月度总结...")
        self.build_monthly_summaries(year)
        print("月度总结生成完成！")
        
        print("开始生成累积总结...")
        self.build_cumulative_summaries(year)
        print("累积总结生成完成！")
    
    @staticmethod
    def get_instance(event_data: List[Dict], persona: Dict, output_dir: str = "data/"):
        """
        创建或获取FuzzyMemoryBuilder实例（单例模式）
        
        参数:
            event_data: 事件数据
            persona: 人物画像
            output_dir: 输出目录
        
        返回:
            FuzzyMemoryBuilder: 实例
        """
        if not hasattr(FuzzyMemoryBuilder, "_instance"):
            FuzzyMemoryBuilder._instance = FuzzyMemoryBuilder(event_data, persona, output_dir)
        return FuzzyMemoryBuilder._instance