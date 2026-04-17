# -*- coding: utf-8 -*-
"""大纲优化器，负责月度总结生成、全年一致性检查和月度合理性分析"""
import os
import json
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.llm_call import llm_call_j, llm_call


class OutlineOptimizer:
    """大纲优化器，对年度事件大纲进行优化和检查"""
    
    def __init__(self, filepath: str, year: int = 2025, isprint: bool = True):
        """
        初始化大纲优化器
        
        Args:
            filepath: 基础路径，包含 daily_draft.json 和 persona.json 文件
            year: 目标年份，默认为 2025
            isprint: 是否打印日志，默认为 True
        """
        self.filepath = filepath
        self.year = year
        self.draft_path = os.path.join(filepath, "daily_draft.json")
        self.persona_path = os.path.join(filepath, "persona.json")
        self.isprint = isprint
        
        self.persona = self._load_persona()
        self.daily_draft = self._load_daily_draft()
        
        # 从 daily_draft 中提取月份数据
        self.monthly_data = self._extract_monthly_data()
    
    def _print(self, message: str):
        """根据 isprint 参数控制是否打印"""
        if self.isprint:
            print(message)
    
    def _load_persona(self) -> Dict:
        """加载画像信息"""
        if os.path.exists(self.persona_path):
            try:
                with open(self.persona_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载 persona.json 失败：{e}")
                return {}
        else:
            print(f"persona.json 文件不存在：{self.persona_path}")
            return {}
    
    def _load_daily_draft(self) -> Dict:
        """加载每日草稿数据"""
        if os.path.exists(self.draft_path):
            try:
                with open(self.draft_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载 daily_draft.json 失败：{e}")
                return {}
        else:
            print(f"daily_draft.json 文件不存在：{self.draft_path}")
            return {}
    
    def _extract_monthly_data(self) -> Dict[str, List[Dict]]:
        """
        从 daily_draft 中提取按月份组织的数据
        
        Returns:
            月份到事件列表的映射，格式：{"2025-01": [...], "2025-02": [...]}
        """
        monthly_data = {}
        
        # 遍历所有日期的事件
        for date, day_events in self.daily_draft.items():
            if isinstance(day_events, list) and day_events:
                # 提取月份（YYYY-MM）
                if len(date) >= 7:
                    month = date[:7]
                    
                    if month not in monthly_data:
                        monthly_data[month] = []
                    
                    # 添加日期信息到每个事件
                    for event in day_events:
                        event_with_date = event.copy()
                        event_with_date["date"] = date
                        monthly_data[month].append(event_with_date)
        
        # 按月份排序
        sorted_months = sorted(monthly_data.keys())
        self._print(f"✓ 提取月份数据完成，共 {len(sorted_months)} 个月份")
        for month in sorted_months:
            self._print(f"  - {month}: {len(monthly_data[month])} 个事件")
        
        return monthly_data
    
    def generate_monthly_summaries_parallel(self, months: List[str] = None) -> Dict[str, Dict]:
        """
        并行生成指定月份的总结报告
        
        Args:
            months: 月份列表，格式为 ["YYYY-MM", ...]，默认为当年所有月份
        
        Returns:
            所有月份的总结报告汇总
        """
        if months is None:
            months = sorted(self.monthly_data.keys())
        
        self._print(f"\n{'='*60}")
        self._print(f"开始并行生成 {len(months)} 个月份的总结报告")
        self._print(f"{'='*60}")
        
        all_summaries = {}
        
        # 并行处理每个月份
        with ThreadPoolExecutor(max_workers=6) as executor:
            # 提交所有月份的处理任务
            future_to_month = {}
            for month in months:
                month_events = self.monthly_data.get(month, [])
                future = executor.submit(
                    self._generate_single_month_summary, 
                    month, 
                    month_events
                )
                future_to_month[future] = month
            
            # 收集结果
            for future in as_completed(future_to_month):
                month = future_to_month[future]
                try:
                    result = future.result()
                    all_summaries[month] = result
                    self._print(f"✓ {month} 总结完成")
                except Exception as e:
                    self._print(f"⚠️  {month} 总结失败：{e}")
                    all_summaries[month] = {
                        "status": "error",
                        "month": month,
                        "message": str(e)
                    }
        
        self._print(f"\n✓ 所有月份总结生成完成！")
        return all_summaries
    
    def _generate_single_month_summary(self, month: str, events: List[Dict]) -> Dict:
        """
        生成单个月份的总结
        
        Args:
            month: 月份
            events: 本月事件列表
        
        Returns:
            该月份的总结
        """
        from event.templates.template_MR import generate_monthly_summary_template
        
        prompt = generate_monthly_summary_template(
            month=month,
            final_events=events,
            original_persona=self.persona
        )
        
        try:
            result_str = llm_call_j(prompt)
            # 匹配字符串的第一个和最后一个{}，确保解析完整的JSON对象
            start_idx = result_str.find('{')
            end_idx = result_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                result_str = result_str[start_idx:end_idx+1]
            # 解析JSON字符串
            result = json.loads(result_str)
            
            return {
                "status": "success",
                "month": month,
                "data": result
            }
            
        except json.JSONDecodeError as e:
            self._print(f"      ⚠️  生成月份总结失败（JSON解析）：{e}")
            return {
                "status": "error",
                "month": month,
                "message": f"生成月份总结失败（JSON解析）：{e}"
            }
        except Exception as e:
            self._print(f"      ⚠️  生成月份总结失败：{e}")
            return {
                "status": "error",
                "month": month,
                "message": f"生成月份总结失败：{e}"
            }
    
    def analyze_yearly_consistency(self, monthly_summaries: Dict[str, Dict]) -> Dict:
        """
        以全年视角分析月度总结的一致性，识别错误和不合理之处
        
        Args:
            monthly_summaries: 所有月份的总结报告
        
        Returns:
            全年一致性分析报告，包含发现的问题和建议
        """
        self._print(f"\n{'='*60}")
        self._print(f"开始全年一致性分析")
        self._print(f"{'='*60}")
        
        from event.templates.template_MR import yearly_consistency_analysis_template
        
        prompt = yearly_consistency_analysis_template(
            year=self.year,
            monthly_summaries=monthly_summaries,
            persona=self.persona
        )
        
        try:
            result_str = llm_call_j(prompt)
            # 匹配字符串的第一个和最后一个{}，确保解析完整的JSON对象
            start_idx = result_str.find('{')
            end_idx = result_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                result_str = result_str[start_idx:end_idx+1]
            # 解析JSON字符串
            result = json.loads(result_str)
            
            self._print(f"✓ 全年一致性分析完成")
            
            # 打印发现的问题
            issues = result.get("issues", [])
            if issues:
                self._print(f"  发现 {len(issues)} 个问题：")
                for idx, issue in enumerate(issues, 1):
                    self._print(f"    [{idx}] {issue.get('type', 'Unknown')}: {issue.get('description', '')}")
            else:
                self._print(f"  ✓ 未发现明显问题")
            
            return {
                "status": "success",
                "analysis": result
            }
            
        except json.JSONDecodeError as e:
            self._print(f"⚠️  全年一致性分析失败（JSON解析）：{e}")
            return {
                "status": "error",
                "message": f"全年一致性分析失败（JSON解析）：{e}"
            }
        except Exception as e:
            self._print(f"⚠️  全年一致性分析失败：{e}")
            return {
                "status": "error",
                "message": f"全年一致性分析失败：{e}"
            }
    
    def analyze_monthly_reasonableness_parallel(self, months: List[str] = None) -> Dict[str, Dict]:
        """
        并行分析每月数据的合理性，判断是否有不合理的地方
        
        Args:
            months: 月份列表，格式为 ["YYYY-MM", ...]，默认为当年所有月份
        
        Returns:
            所有月份的合理性分析报告
        """
        if months is None:
            months = sorted(self.monthly_data.keys())
        
        self._print(f"\n{'='*60}")
        self._print(f"开始并行分析 {len(months)} 个月份的合理性")
        self._print(f"{'='*60}")
        
        all_analyses = {}
        
        # 并行处理每个月份
        with ThreadPoolExecutor(max_workers=6) as executor:
            # 提交所有月份的分析任务
            future_to_month = {}
            for month in months:
                month_events = self.monthly_data.get(month, [])
                future = executor.submit(
                    self._analyze_single_month_reasonableness, 
                    month, 
                    month_events
                )
                future_to_month[future] = month
            
            # 收集结果
            for future in as_completed(future_to_month):
                month = future_to_month[future]
                try:
                    result = future.result()
                    all_analyses[month] = result
                    self._print(f"✓ {month} 合理性分析完成")
                except Exception as e:
                    self._print(f"⚠️  {month} 合理性分析失败：{e}")
                    all_analyses[month] = {
                        "status": "error",
                        "month": month,
                        "message": str(e)
                    }
        
        self._print(f"\n✓ 所有月份合理性分析完成！")
        return all_analyses
    
    def _analyze_single_month_reasonableness(self, month: str, events: List[Dict]) -> Dict:
        """
        分析单个月份数据的合理性
        
        Args:
            month: 月份
            events: 本月事件列表
        
        Returns:
            该月份的合理性分析报告，包含需要修改的日期
        """
        from event.templates.template_MR import monthly_reasonableness_analysis_template
        
        prompt = monthly_reasonableness_analysis_template(
            month=month,
            events=events,
            persona=self.persona
        )
        
        try:
            result_str = llm_call_j(prompt)
            # 匹配字符串的第一个和最后一个{}，确保解析完整的JSON对象
            start_idx = result_str.find('{')
            end_idx = result_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                result_str = result_str[start_idx:end_idx+1]
            # 解析JSON字符串
            result = json.loads(result_str)
            
            # 提取需要修改的日期
            dates_to_modify = result.get("dates_to_modify", [])
            
            analysis_result = {
                "status": "success",
                "month": month,
                "data": result,
                "dates_to_modify": dates_to_modify
            }
            
            # 打印需要修改的日期
            if dates_to_modify:
                self._print(f"  📝 {month} 发现 {len(dates_to_modify)} 个需要修改的日期：")
                for date_info in dates_to_modify:
                    date = date_info.get("date", "Unknown")
                    reason = date_info.get("reason", "未说明原因")
                    self._print(f"     - {date}: {reason}")
            else:
                self._print(f"  ✓ {month} 未发现需要修改的地方")
            
            return analysis_result
            
        except json.JSONDecodeError as e:
            self._print(f"      ⚠️  月份合理性分析失败（JSON解析）：{e}")
            return {
                "status": "error",
                "month": month,
                "message": f"月份合理性分析失败（JSON解析）：{e}",
                "dates_to_modify": []
            }
        except Exception as e:
            self._print(f"      ⚠️  月份合理性分析失败：{e}")
            return {
                "status": "error",
                "month": month,
                "message": f"月份合理性分析失败：{e}",
                "dates_to_modify": []
            }
    
    def run_full_optimization(self, output_dir: str = None) -> Dict:
        """
        执行完整的大纲优化流程：
        1. 并行生成每月总结
        2. 全年一致性分析
        3. 并行分析每月合理性
        
        Args:
            output_dir: 输出目录，默认为 filepath/process/refined
        
        Returns:
            包含所有分析结果的字典
        """
        if output_dir is None:
            output_dir = os.path.join(self.filepath, "process", "refined")
        
        os.makedirs(output_dir, exist_ok=True)
        
        summaries_file = os.path.join(output_dir, "monthly_summaries.json")
        consistency_file = os.path.join(output_dir, "yearly_consistency.json")
        reasonableness_file = os.path.join(output_dir, "monthly_reasonableness.json")
        
        results = {}
        
        # Step 1: 并行生成每月总结
        self._print("\n" + "="*80)
        self._print("[Step 1] 并行生成每月总结")
        self._print("="*80)
        
        if os.path.exists(summaries_file):
            self._print(f"  ⏭️  跳过，已存在文件：{summaries_file}")
            with open(summaries_file, 'r', encoding='utf-8') as f:
                results["summaries"] = json.load(f)
        else:
            results["summaries"] = self.generate_monthly_summaries_parallel()
            self._save_json(results["summaries"], summaries_file)
        
        # Step 2: 全年一致性分析
        self._print("\n" + "="*80)
        self._print("[Step 2] 全年一致性分析")
        self._print("="*80)
        
        if os.path.exists(consistency_file):
            self._print(f"  ⏭️  跳过，已存在文件：{consistency_file}")
            with open(consistency_file, 'r', encoding='utf-8') as f:
                results["consistency"] = json.load(f)
        else:
            results["consistency"] = self.analyze_yearly_consistency(results["summaries"])
            self._save_json(results["consistency"], consistency_file)
        
        # Step 3: 并行分析每月合理性
        self._print("\n" + "="*80)
        self._print("[Step 3] 并行分析每月合理性")
        self._print("="*80)
        
        if os.path.exists(reasonableness_file):
            self._print(f"  ⏭️  跳过，已存在文件：{reasonableness_file}")
            with open(reasonableness_file, 'r', encoding='utf-8') as f:
                results["reasonableness"] = json.load(f)
        else:
            results["reasonableness"] = self.analyze_monthly_reasonableness_parallel()
            self._save_json(results["reasonableness"], reasonableness_file)
        
        # 汇总所有需要修改的日期
        all_dates_to_modify = []
        for month, analysis in results["reasonableness"].items():
            if analysis.get("status") == "success":
                dates = analysis.get("dates_to_modify", [])
                all_dates_to_modify.extend(dates)
        
        self._print("\n" + "="*80)
        self._print("优化流程完成！")
        self._print("="*80)
        self._print(f"\n📊 统计信息：")
        self._print(f"  - 月份总结数：{len(results['summaries'])}")
        self._print(f"  - 全年一致性问题数：{len(results['consistency'].get('analysis', {}).get('issues', []))}")
        self._print(f"  - 需要修改的日期数：{len(all_dates_to_modify)}")
        
        if all_dates_to_modify:
            self._print(f"\n📝 需要修改的日期列表：")
            for date_info in all_dates_to_modify:
                self._print(f"  - {date_info.get('date', 'Unknown')}: {date_info.get('reason', '')}")
        
        return results
    
    def optimize_outline(self, output_dir: str = None) -> Dict:
        """
        优化每日大纲的完整流程：
        1. 调用 run_full_optimization 分析合理性
        2. 生成每个月的修改操作（目标日期和重新生成的指导）
        3. 执行指定日期的数据重新生成，更新 daily_draft.json
        
        Args:
            output_dir: 输出目录，默认为 filepath/process/refined
        
        Returns:
            优化后的 daily_draft 数据
        """
        if output_dir is None:
            output_dir = os.path.join(self.filepath, "process", "refined")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Step 1: 执行完整优化流程，获取分析结果
        self._print("\n" + "="*80)
        self._print("开始优化每日大纲")
        self._print("="*80)
        
        optimization_results = self.run_full_optimization(output_dir)
        
        # Step 2: 提取需要修改的日期列表
        all_dates_to_modify = []
        for month, analysis in optimization_results.get("reasonableness", {}).items():
            if analysis.get("status") == "success":
                dates = analysis.get("dates_to_modify", [])
                for date_info in dates:
                    date_info["month"] = month
                    all_dates_to_modify.append(date_info)
        
        if not all_dates_to_modify:
            self._print("\n✓ 没有需要修改的日期，大纲已合理")
            return self.daily_draft
        
        self._print(f"\n📝 发现 {len(all_dates_to_modify)} 个需要重新生成的日期")
        
        # Step 3: 按月份分组需要修改的日期
        dates_by_month = {}
        for date_info in all_dates_to_modify:
            month = date_info.get("month", "")
            if month not in dates_by_month:
                dates_by_month[month] = []
            dates_by_month[month].append(date_info)
        
        # Step 4: 对每个月份执行重新生成
        optimized_draft = self.daily_draft.copy()
        
        for month, dates in dates_by_month.items():
            self._print(f"\n{'='*60}")
            self._print(f"处理月份：{month}，共 {len(dates)} 个日期需要重新生成")
            self._print(f"{'='*60}")
            
            # 获取该月份的原始事件数据
            month_events = self.monthly_data.get(month, [])
            
            # 构建重新生成的指导信息
            regeneration_instructions = []
            for date_info in dates:
                instruction = {
                    "target_date": date_info.get("date"),
                    "reason": date_info.get("reason", ""),
                    "suggestions": date_info.get("suggestions", "")
                }
                regeneration_instructions.append(instruction)
            
            # 调用 LLM 重新生成该月份指定日期的数据
            regenerated_days = self._regenerate_month_days(
                month=month,
                month_events=month_events,
                instructions=regeneration_instructions
            )
            
            # 更新 optimized_draft
            for day_data in regenerated_days:
                date = day_data.get("date", "")
                if date:
                    optimized_draft[date] = day_data.get("events", [])
                    self._print(f"  ✓ 已更新 {date}")
        
        # Step 5: 保存优化后的 daily_draft
        optimized_draft_path = os.path.join(self.filepath, "daily_draft_optimized.json")
        try:
            with open(optimized_draft_path, 'w', encoding='utf-8') as f:
                json.dump(optimized_draft, f, ensure_ascii=False, indent=2)
            self._print(f"\n💾 优化后的大纲已保存到：{optimized_draft_path}")
        except Exception as e:
            self._print(f"\n⚠️  保存优化后的大纲失败：{e}")
        
        self._print("\n🎉 大纲优化完成！")
        return optimized_draft
    
    def _regenerate_month_days(self, month: str, month_events: List[Dict], 
                                instructions: List[Dict]) -> List[Dict]:
        """
        重新生成指定月份中特定日期的数据
        
        Args:
            month: 月份，格式为 "YYYY-MM"
            month_events: 该月份的所有事件列表
            instructions: 重新生成的指导信息列表，包含 target_date、reason、suggestions
        
        Returns:
            重新生成后的日期数据列表
        """
        from event.templates.template_scheduler import template_regenerate_daily_draft
        
        regenerated_days = []
        
        # 对每个需要重新生成的日期单独处理
        for instruction in instructions:
            target_date = instruction.get("target_date", "")
            if not target_date:
                continue
            
            # 从 daily_draft 中查找该日期的数据（daily_draft 的 key 是月份，value 是天数数组）
            original_day_data = None
            for date_key, day_list in self.daily_draft.items():
                if isinstance(day_list, list):
                    for day_item in day_list:
                        if isinstance(day_item, dict) and day_item.get("date") == target_date:
                            original_day_data = day_item
                            break
                if original_day_data:
                    break
            
            if not original_day_data:
                self._print(f"  ⚠️  未找到日期 {target_date} 的原始数据")
                continue
            
            # 获取前一天的数据
            previous_date = self._get_previous_date(target_date)
            previous_day_data = None
            if previous_date:
                for date_key, day_list in self.daily_draft.items():
                    if isinstance(day_list, list):
                        for day_item in day_list:
                            if isinstance(day_item, dict) and day_item.get("date") == previous_date:
                                previous_day_data = day_item
                                break
                    if previous_day_data:
                        break
            
            # 获取后一天的数据
            next_date = self._get_next_date(target_date)
            next_day_data = None
            if next_date:
                for date_key, day_list in self.daily_draft.items():
                    if isinstance(day_list, list):
                        for day_item in day_list:
                            if isinstance(day_item, dict) and day_item.get("date") == next_date:
                                next_day_data = day_item
                                break
                    if next_day_data:
                        break
            
            # 构建提示词
            prompt = template_regenerate_daily_draft.format(
                original_day_data=json.dumps(original_day_data, ensure_ascii=False),
                previous_day_data=json.dumps(previous_day_data, ensure_ascii=False) if previous_day_data else "无",
                next_day_data=json.dumps(next_day_data, ensure_ascii=False) if next_day_data else "无",
                instructions=json.dumps(instruction, ensure_ascii=False)
            )
            
            try:
                result_str = llm_call_j(prompt)
                # 解析 JSON 对象
                start_idx = result_str.find('{')
                end_idx = result_str.rfind('}')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_str = result_str[start_idx:end_idx+1]
                    regenerated_day = json.loads(json_str)
                    regenerated_days.append(regenerated_day)
                    self._print(f"  ✓ 成功重新生成 {target_date}")
                else:
                    self._print(f"  ⚠️  无法解析 {target_date} 的重新生成数据")
            
            except json.JSONDecodeError as e:
                self._print(f"  ⚠️  重新生成 {target_date} 失败（JSON解析）：{e}")
            except Exception as e:
                self._print(f"  ⚠️  重新生成 {target_date} 失败：{e}")
        
        return regenerated_days
    
    def _get_previous_date(self, date_str: str) -> Optional[str]:
        """
        获取指定日期的前一天
        
        Args:
            date_str: 日期字符串，格式为 "YYYY-MM-DD"
        
        Returns:
            前一天的日期字符串，如果是最早日期则返回 None
        """
        from datetime import datetime, timedelta
        
        try:
            current_date = datetime.strptime(date_str, "%Y-%m-%d")
            previous_date = current_date - timedelta(days=1)
            return previous_date.strftime("%Y-%m-%d")
        except Exception:
            return None
    
    def _get_next_date(self, date_str: str) -> Optional[str]:
        """
        获取指定日期的后一天
        
        Args:
            date_str: 日期字符串，格式为 "YYYY-MM-DD"
        
        Returns:
            后一天的日期字符串，如果是最后日期则返回 None
        """
        from datetime import datetime, timedelta
        
        try:
            current_date = datetime.strptime(date_str, "%Y-%m-%d")
            next_date = current_date + timedelta(days=1)
            return next_date.strftime("%Y-%m-%d")
        except Exception:
            return None
    
    def _save_json(self, data: Any, filepath: str):
        """保存 JSON 数据到文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._print(f"  💾 已保存：{filepath}")
        except Exception as e:
            self._print(f"  ⚠️  保存文件失败：{e}")
