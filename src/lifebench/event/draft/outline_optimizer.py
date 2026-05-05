# -*- coding: utf-8 -*-
"""大纲优化器，负责月度总结生成、全年一致性检查和月度合理性分析"""
import os
import json
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.lifebench.utils.llm_call import llm_call_j, llm_call, llm_call_reason_j, llm_call_reason


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
        """加载每日草稿数据，支持数组格式和字典格式"""
        if os.path.exists(self.draft_path):
            try:
                with open(self.draft_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 如果是数组格式，转换为月份字典格式
                if isinstance(data, list):
                    self._print(f"检测到数组格式，正在转换为月份字典格式...")
                    monthly_dict = {}
                    for month_item in data:
                        if isinstance(month_item, dict):
                            month = month_item.get('month', '')
                            daily_outline = month_item.get('daily_outline', [])
                            
                            if month and isinstance(daily_outline, list):
                                # 将 daily_outline 中的每一天作为该月份的数据
                                monthly_dict[month] = daily_outline
                    
                    # 按月份排序
                    sorted_months = sorted(monthly_dict.keys())
                    self._print(f"✓ 转换完成，共 {len(sorted_months)} 个月份")
                    for month in sorted_months:
                        self._print(f"  - {month}: {len(monthly_dict[month])} 天")
                    
                    return monthly_dict
                else:
                    return data
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
            months = sorted(self.daily_draft.keys())
        
        self._print(f"\n{'='*60}")
        self._print(f"开始并行生成 {len(months)} 个月份的总结报告")
        self._print(f"{'='*60}")
        
        all_summaries = {}
        
        # 并行处理每个月份
        with ThreadPoolExecutor(max_workers=6) as executor:
            # 提交所有月份的处理任务
            future_to_month = {}
            for month in months:
                month_events = self.daily_draft.get(month, [])
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
        from src.lifebench.event.templates.template_mr import generate_monthly_summary_template
        
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
        
        from src.lifebench.event.templates.template_mr import yearly_consistency_analysis_template
        
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
    
    def analyze_monthly_reasonableness_parallel(self, months: List[str] = None, 
                                                 prompt_builder=None) -> Dict[str, Dict]:
        """
        并行分析每月数据的合理性，判断是否有不合理的地方
        
        Args:
            months: 月份列表，格式为 ["YYYY-MM", ...]，默认为当年所有月份
            prompt_builder: prompt 构建函数，输入 month，输出 prompt 字符串。
                           默认为基础合理性分析 prompt 构建函数
        
        Returns:
            所有月份的合理性分析报告
        """
        if months is None:
            months = sorted(self.daily_draft.keys())
        
        # 默认使用基础合理性分析 prompt 构建函数
        if prompt_builder is None:
            prompt_builder = self._build_basic_reasonableness_prompt
        
        self._print(f"\n{'='*60}")
        self._print(f"开始并行分析 {len(months)} 个月份的合理性")
        self._print(f"{'='*60}")
        
        all_analyses = {}
        
        # 并行处理每个月份
        with ThreadPoolExecutor(max_workers=12) as executor:
            # 提交所有月份的分析任务
            future_to_month = {}
            for month in months:
                future = executor.submit(
                    self._analyze_single_month_with_prompt_builder, 
                    month,
                    prompt_builder
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
        
        # 整合所有修改后的月份数据为 daily_draft 格式
        updated_daily_draft = {}
        for month, analysis in all_analyses.items():
            if analysis.get('status') == 'success':
                modified_data = analysis.get('data', [])
                if modified_data:
                    updated_daily_draft[month] = modified_data
            else:
                # 如果分析失败，保留原始数据
                original_data = self.daily_draft.get(month, [])
                updated_daily_draft[month] = original_data
        
        # 按月份排序
        sorted_months = sorted(updated_daily_draft.keys())
        self._print(f"\n💾 正在更新 daily_draft...")
        self._print(f"  - 共 {len(sorted_months)} 个月份")
        for month in sorted_months:
            self._print(f"  - {month}: {len(updated_daily_draft[month])} 天")
        
        # 替换现有的 daily_draft
        self.daily_draft = updated_daily_draft
        
        return all_analyses
    
    def _build_consistency_based_prompt(self, consistency_analysis: Dict):
        """
        基于全年一致性分析结果构建 prompt 的工厂函数
        
        Args:
            consistency_analysis: 全年一致性分析结果
        
        Returns:
            prompt 构建函数，输入 month，输出 prompt 字符串
        """
        def prompt_builder(month: str) -> str:
            from src.lifebench.event.templates.template_mr import consistency_based_monthly_analysis_template
            
            # 从 daily_draft 读取对应月份的数据
            month_data = self.daily_draft.get(month, [])
            
            # 提取该月份相关的一致性问题
            month_issues = []
            issues = consistency_analysis.get("issues", [])
            for issue in issues:
                # 检查问题是否涉及当前月份
                related_months = issue.get("involved_months", [])
                if month in related_months or not related_months:
                    month_issues.append(issue)
            
            prompt = consistency_based_monthly_analysis_template(
                month=month,
                events=month_data,
                consistency_issues=month_issues
            )
            
            return prompt
        
        return prompt_builder
    
    def _build_basic_reasonableness_prompt(self, month: str) -> str:
        """
        基础合理性分析 prompt 构建函数
        
        Args:
            month: 月份
        
        Returns:
            构建好的 prompt 字符串
        """
        from src.lifebench.event.templates.template_mr import monthly_reasonableness_analysis_template
        
        # 从 daily_draft 读取对应月份的数据
        month_data = self.daily_draft.get(month, [])
        
        prompt = monthly_reasonableness_analysis_template(
            month=month,
            events=month_data,
            persona=self.persona
        )
        
        return prompt
    
    def _analyze_single_month_with_prompt_builder(self, month: str, 
                                                     prompt_builder) -> Dict:
        """
        使用 prompt 构建函数分析单个月份，并直接并行重新生成需要修改的日期
        
        Args:
            month: 月份
            prompt_builder: prompt 构建函数，输入 month，输出 prompt 字符串
        
        Returns:
            重新生成后的月份数据
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from src.lifebench.event.templates.template_mr import parse_modification_instructions_template
        
        # 使用传入的 prompt 构建函数生成 prompt
        prompt = prompt_builder(month)
        print(prompt)
        try:
            # 第一轮：LLM 分析并生成原始修改指令
            result_str = llm_call_reason(prompt)
            print(f"  LLM 回复: {result_str}")
            # 匹配字符串的第一个和最后一个{}，确保解析完整的JSON对象
            start_idx = result_str.find('{')
            end_idx = result_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                result_str = result_str[start_idx:end_idx+1]
            # 解析JSON字符串
            result = json.loads(result_str)
            
            # 提取需要修改的日期
            dates_to_modify = result.get("dates_to_modify", [])
            
            if not dates_to_modify:
                self._print(f"  ✓ {month} 未发现需要修改的地方")
                month_data = self.daily_draft.get(month, [])
                return {
                    "status": "success",
                    "month": month,
                    "data": month_data,
                    "dates_modified": 0
                }
            
            # 第二轮：LLM 解析和整合跨日期修改指令
            self._print(f"  🔄 正在解析和整合跨日期修改指令...")
            parse_prompt = parse_modification_instructions_template(dates_to_modify)
            parse_result_str = llm_call_j(parse_prompt)
            print(f"  LLM 回复: {parse_result_str}")
            # 解析整合后的结果
            start_idx = parse_result_str.find('{')
            end_idx = parse_result_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                parse_result_str = parse_result_str[start_idx:end_idx+1]
            parsed_result = json.loads(parse_result_str)
            
            # 使用整合后的指令
            dates_to_modify = parsed_result.get("dates_to_modify", [])
            
            # 打印需要修改的日期
            self._print(f"  📝 {month} 发现 {len(dates_to_modify)} 个需要修改的日期：")
            for date_info in dates_to_modify:
                date = date_info.get("date", "Unknown")
                suggestion = date_info.get("suggestion", "")
                # 提取 suggestion 的前50个字符作为简要说明
                brief = suggestion[:50].replace('\n', ' ') if suggestion else "未说明"
                self._print(f"     - {date}: {brief}")
            
            # 并行重新生成需要修改的日期（20线程）
            self._print(f"  🔄 开始并行重新生成 {len(dates_to_modify)} 个日期...")
            regenerated_days = []
            
            with ThreadPoolExecutor(max_workers=20) as executor:
                # 提交所有重新生成任务
                future_to_date = {}
                for date_info in dates_to_modify:
                    target_date = date_info.get("date", "")
                    if target_date:
                        future = executor.submit(
                            self._regenerate_single_day,
                            month,
                            [],
                            date_info
                        )
                        future_to_date[future] = target_date
                
                # 收集结果
                for future in as_completed(future_to_date):
                    target_date = future_to_date[future]
                    try:
                        regenerated_day = future.result()
                        if regenerated_day:
                            regenerated_days.append(regenerated_day)
                            self._print(f"    ✓ {target_date} 重新生成成功")
                    except Exception as e:
                        self._print(f"    ⚠️  {target_date} 重新生成失败：{e}")
            
            # 获取原始月份数据用于合并
            month_data = self.daily_draft.get(month, [])
            # 将重新生成的日期合并回原数据
            updated_month_data = self._merge_regenerated_days(month_data, regenerated_days)
            
            return {
                "status": "success",
                "month": month,
                "data": updated_month_data,
                "dates_modified": len(regenerated_days)
            }
            
        except json.JSONDecodeError as e:
            self._print(f"      ⚠️  月份合理性分析失败（JSON解析）：{e}")
            month_data = self.daily_draft.get(month, [])
            return {
                "status": "error",
                "month": month,
                "message": f"月份合理性分析失败（JSON解析）：{e}",
                "data": month_data
            }
        except Exception as e:
            self._print(f"      ⚠️  月份合理性分析失败：{e}")
            month_data = self.daily_draft.get(month, [])
            return {
                "status": "error",
                "month": month,
                "message": f"月份合理性分析失败：{e}",
                "data": month_data
            }
    
    def optimize_yearly(self, output_dir: str = None) -> Dict:
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
        
        # Step 3: 基于全年一致性分析结果，并行分析每月合理性
        self._print("\n" + "="*80)
        self._print("[Step 3] 基于全年一致性的月度合理性分析")
        self._print("="*80)
        
        if os.path.exists(reasonableness_file):
            self._print(f"  ⏭️  跳过，已存在文件：{reasonableness_file}")
            with open(reasonableness_file, 'r', encoding='utf-8') as f:
                results["reasonableness"] = json.load(f)
        else:
            # 构建基于全年一致性的 prompt 构建函数
            consistency_analysis = results["consistency"].get("analysis", {})
            prompt_builder = self._build_consistency_based_prompt(consistency_analysis)
            results["reasonableness"] = self.analyze_monthly_reasonableness_parallel(
                prompt_builder=prompt_builder
            )
            self._save_json(results["reasonableness"], reasonableness_file)
        
        self._print("\n" + "="*80)
        self._print("优化流程完成！")
        self._print("="*80)
        self._print(f"\n📊 统计信息：")
        self._print(f"  - 月份总结数：{len(results['summaries'])}")
        self._print(f"  - 全年一致性问题数：{len(results['consistency'].get('analysis', {}).get('issues', []))}")
        
        return results
    
    def optimize_outline(self, output_dir: str = None) -> Dict:
        """
        优化每日大纲的完整流程：
        1. 并行分析每月合理性并更新 daily_draft
        2. 执行全年优化流程（生成总结、一致性分析）
        
        Args:
            output_dir: 输出目录，默认为 filepath/process/refined
        
        Returns:
            优化后的 daily_draft 数据
        """
        if output_dir is None:
            output_dir = os.path.join(self.filepath, "process", "refined")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Step 1: 并行分析每月合理性并更新 daily_draft
        self._print("\n" + "="*80)
        self._print("[Step 1] 并行分析每月合理性并更新 daily_draft")
        self._print("="*80)
        
        reasonableness_results = self.analyze_monthly_reasonableness_parallel()
        
        # Step 2: 执行全年优化流程（生成总结、一致性分析）
        self._print("\n" + "="*80)
        self._print("[Step 2] 执行全年优化流程")
        self._print("="*80)
        
        yearly_results = self.optimize_yearly(output_dir=output_dir)
        
        # 保存优化后的 daily_draft
        optimized_draft_path = os.path.join(self.filepath, "daily_draft.json")
        try:
            with open(optimized_draft_path, 'w', encoding='utf-8') as f:
                json.dump(self.daily_draft, f, ensure_ascii=False, indent=2)
            self._print(f"\n💾 优化后的大纲已保存到：{optimized_draft_path}")
            self._print(f"  - 共 {len(self.daily_draft)} 个月份")
            for month in sorted(self.daily_draft.keys()):
                self._print(f"  - {month}: {len(self.daily_draft[month])} 天")
        except Exception as e:
            self._print(f"\n⚠️  保存优化后的大纲失败：{e}")
        
        self._print("\n🎉 大纲优化完成！")
        return self.daily_draft
    
    def _regenerate_single_day(self, month: str, month_events: List[Dict], 
                                instruction: Dict) -> Optional[Dict]:
        """
        重新生成单个日期的数据
        
        Args:
            month: 月份，格式为 "YYYY-MM"
            month_events: 该月份的所有事件列表
            instruction: 重新生成的指导信息，包含 date、reason、suggestion
        
        Returns:
            重新生成后的日期数据，失败返回 None
        """
        from src.lifebench.event.templates.template_scheduler import template_regenerate_daily_draft
        
        target_date = instruction.get("date", "")
        if not target_date:
            return None
        
        # 从 daily_draft 中查找该日期的数据
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
            return None
        
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
            previous_day_data=json.dumps({}, ensure_ascii=False) if previous_day_data else "无",
            next_day_data=json.dumps({}, ensure_ascii=False) if next_day_data else "无",
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
                return regenerated_day
            else:
                self._print(f"  ⚠️  无法解析 {target_date} 的重新生成数据")
                return None
        
        except json.JSONDecodeError as e:
            self._print(f"  ⚠️  重新生成 {target_date} 失败（JSON解析）：{e}")
            return None
        except Exception as e:
            self._print(f"  ⚠️  重新生成 {target_date} 失败：{e}")
            return None
    
    def _merge_regenerated_days(self, original_data: List[Dict], 
                                 regenerated_days: List[Dict]) -> List[Dict]:
        """
        将重新生成的日期合并回原数据
        
        Args:
            original_data: 原始月份数据
            regenerated_days: 重新生成的日期列表
        
        Returns:
            合并后的数据
        """
        # 创建日期到数据的映射
        regenerated_map = {}
        for day in regenerated_days:
            if isinstance(day, dict) and 'date' in day:
                regenerated_map[day['date']] = day
        
        # 替换或添加重新生成的日期
        updated_data = []
        for day in original_data:
            if isinstance(day, dict) and 'date' in day:
                date_str = day['date']
                if date_str in regenerated_map:
                    # 使用重新生成的数据
                    updated_data.append(regenerated_map[date_str])
                    del regenerated_map[date_str]
                else:
                    # 保留原始数据
                    updated_data.append(day)
            else:
                updated_data.append(day)
        
        # 添加新增的日期（如果有）
        for date_str, day_data in regenerated_map.items():
            updated_data.append(day_data)
        
        # 按日期排序
        updated_data.sort(key=lambda x: x.get('date', '') if isinstance(x, dict) else '')
        
        return updated_data
    
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
        from src.lifebench.event.templates.template_scheduler import template_regenerate_daily_draft
        
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
