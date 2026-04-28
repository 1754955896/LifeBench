# -*- coding: utf-8 -*-
"""月度数据优化器和年度智能体，负责月度总结生成和年度趋势分析"""
import os
import json
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import holidays
from src.lifebench.utils.llm_call import llm_call_j, llm_call, llm_call_reason_j
from src.lifebench.event.templates.template_mr import (
    habit_summary_template,
    health_summary_template,
    event_summary_template,
    initial_trends_template,
    refine_trends_template,
    monthly_issues_template,
    all_months_issues_template,
    generate_monthly_final_summary_template,
    polish_events_template,
    add_trend_based_events_template,
    select_library_events_template,
    evaluate_monthly_events_template,
    generate_month_summary_and_persona_template,
    generate_monthly_summary_template,
    update_persona_template
)


class MonthlyRefiner:
    """月度数据优化器，负责月度总结生成、年度趋势分析和每月事件优化"""
    
    def __init__(self, filepath: str, year: int = 2025, isprint: bool = True):
        """
        初始化月度优化器
        
        Args:
            filepath: 基础路径，包含 persona.json 和 process/optimize_timeline.json 文件
            year: 目标年份，默认为 2025
            isprint: 是否打印日志，默认为 True
        """
        self.filepath = filepath
        self.year = year
        self.persona_path = os.path.join(filepath, "persona.json")
        self.optimize_timeline_path = os.path.join(filepath, "process", "optimize_timeline.json")
        self.graph_path = os.path.join(filepath, "process", "graph", "inserted_event_graph.json")
        self.isprint = isprint
        
        self.persona = self._load_persona()
        self.timeline_data = self._load_timeline_data()
        self.event_graph = self._load_event_graph()
        
        # 从图谱数据初始化月份事件数组
        self.monthly_events_map = self._initialize_monthly_events_map()
        
        # 使用 holidays 库初始化当年度的中国节假日信息
        self.holidays = self._initialize_holidays()
    
    def _initialize_holidays(self) -> Dict[str, List[Dict]]:
        """
        使用 holidays 库初始化指定年份的中国法定节假日信息
        
        Returns:
            月份到节假日列表的映射，格式：{"01": [{"name": "元旦", "date": "2025-01-01", "type": "法定假日"}], ...}
        """
        try:
            import datetime as dt
            # 获取指定年份的中国法定节假日
            cn_holidays = holidays.CountryHoliday('CN', years=self.year)
            
            # 按月份组织节假日信息
            monthly_holidays = {}
            for i in range(1, 13):
                month_str = f"{i:02d}"
                monthly_holidays[month_str] = []
            
            # 遍历所有节假日
            for date, name in sorted(cn_holidays.items()):
                # holidays 库返回的是 datetime.date 对象
                if isinstance(date, (dt.date, dt.datetime)):
                    month_str = f"{date.month:02d}"
                    date_str = date.strftime("%Y-%m-%d")
                    
                    monthly_holidays[month_str].append({
                        "name": name,
                        "date": date_str,
                        "type": "法定假日"
                    })
            
            # 统计总数
            total_count = sum(len(v) for v in monthly_holidays.values())
            self._print(f"✓ 加载 {self.year} 年中国节假日信息完成，共 {total_count} 个节假日")
            return monthly_holidays
            
        except Exception as e:
            print(f"⚠️  加载节假日信息失败：{e}")
            # 返回空的节假日数据
            return {f"{i:02d}": [] for i in range(1, 13)}
    
    def get_month_holidays(self, month: str) -> List[Dict]:
        """
        获取指定月份的节假日信息
        
        Args:
            month: 月份，格式为"MM"
        
        Returns:
            该月份的节假日列表
        """
        return self.holidays.get(month, [])
    
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
    
    def _load_timeline_data(self) -> Dict:
        """加载时间线数据"""
        from normalizer import Normalizer
        
        # 创建规范化器实例
        normalizer = Normalizer(self.optimize_timeline_path, self.persona, self.isprint)
        
        # 使用规范化器加载并规范化数据
        return normalizer.load_and_normalize_data()
    
    def _load_event_graph(self) -> Dict:
        """加载事件图谱数据"""
        if os.path.exists(self.graph_path):
            try:
                with open(self.graph_path, 'r', encoding='utf-8') as f:
                    event_graph = json.load(f)
                self._print(f"✓ 加载事件图谱成功，包含 {len(event_graph.get('nodes', []))} 个节点")
                return event_graph
            except Exception as e:
                print(f"加载事件图谱失败：{e}")
                return {"nodes": [], "edges": []}
        else:
            print(f"事件图谱文件不存在：{self.graph_path}")
            return {"nodes": [], "edges": []}
    
    def _initialize_monthly_events_map(self) -> Dict[str, List[Dict]]:
        """
        从图谱数据初始化月份事件映射表，如果没有图谱文件则基于 timeline_data 构建
        
        Returns:
            月份到事件列表的映射字典
        """
        monthly_events_map = {}
        
        # 优先尝试从图谱中加载事件
        if self.event_graph and self.event_graph.get("nodes"):
            self._print("✓ 从事件图谱初始化月份事件映射表...")
            # 遍历图谱中的所有节点（事件）
            for node in self.event_graph.get("nodes", []):
                time_data = node.get("time", [])
                if isinstance(time_data, list) and time_data:
                    # 获取事件的开始时间
                    first_time = time_data[0]
                    if "至" in first_time:
                        start_date = first_time.split("至")[0]
                    else:
                        start_date = first_time
                    
                    # 提取月份（YYYY-MM）
                    if len(start_date) >= 7:
                        month = start_date[:7]
                        
                        # 如果该月份还没有列表，创建一个
                        if month not in monthly_events_map:
                            monthly_events_map[month] = []
                        
                        # 将事件添加到对应月份
                        monthly_events_map[month].append(node)
        else:
            # 如果没有图谱数据，则基于 timeline_data 构建
            self._print("⚠️  事件图谱为空，基于 timeline_data 初始化月份事件映射表...")
            
            # 从 timeline_data 中提取每月事件
            monthly_details = self.timeline_data.get("monthly_details", [])
            
            for month_detail in monthly_details:
                month = month_detail.get("month", "")
                events = month_detail.get("events", [])
                
                if month and events:
                    monthly_events_map[month] = events
        
        # 按月份排序
        sorted_months = sorted(monthly_events_map.keys())
        total_events = sum(len(events) for events in monthly_events_map.values())
        self._print(f"✓ 初始化月份事件映射表完成，共 {len(sorted_months)} 个月份，{total_events} 个事件")
        for month in sorted_months:
            self._print(f"  - {month}: {len(monthly_events_map[month])} 个事件")
        
        return monthly_events_map
    
    def get_month_data(self, month: str) -> Optional[Dict]:
        """
        获取指定月份的数据（直接从初始化的映射表中获取）
        
        Args:
            month: 月份，格式为"YYYY-MM"
        
        Returns:
            月份数据字典，包含 month 和 events 字段；如果不存在返回 None
        """
        if month in self.monthly_events_map:
            events = self.monthly_events_map[month]
            return {
                "month": month,
                "events": events
            }
        else:
            # 如果月份不存在，返回空的事件列表
            return {
                "month": month,
                "events": []
            }
    
    def analyze_yearly_trends(self, monthly_summaries: Dict[str, Dict]) -> Dict:
        """
        分析全年的偏好习惯兴趣变化趋势和运动健康变化趋势
        
        Args:
            monthly_summaries: 12 个月的总结报告
        
        Returns:
            年度趋势分析结果
        """
        self._print(f"\n{'='*60}")
        self._print(f"开始分析全年趋势")
        self._print(f"{'='*60}")
        
        # Step 1: 基于画像自行设计初步趋势
        self._print(f"\n[Step 1] 基于画像设计初步趋势...")
        initial_trends = self._design_initial_trends()
        print("  - 初步趋势：", initial_trends)
        # Step 2: 结合 12 个月总结反馈重新设计趋势
        self._print(f"\n[Step 2] 结合月度总结重新设计趋势...")
        refined_trends = self._refine_trends_with_feedback(initial_trends, monthly_summaries)
        print("  - 优化后的趋势：", refined_trends)
        
        # Step 3: 分析每月的逻辑错误和不合理之处，给出修改指导
        self._print(f"\n[Step 3] 分析每月逻辑错误并给出修改指导...")
        monthly_guidance = self._analyze_monthly_issues(refined_trends, monthly_summaries)
        print("  - 每月逻辑错误和修改建议：", monthly_guidance)

        # Step 4: 整合 refined_trends 和 monthly_guidance，生成每个月的最终优化总结
        self._print(f"\n[Step 4] 生成每个月的最终优化总结...")
        monthly_final_summaries = self._generate_monthly_final_summaries(
            refined_trends, monthly_guidance, self.monthly_events_map
        )
        
        self._print(f"\n✓ 年度趋势分析完成！")
        
        return monthly_final_summaries
    
    def _design_initial_trends(self) -> Dict:
        """
        基于画像自行设计一个多样的一年的偏好习惯兴趣变化趋势，运动健康变化趋势总结
        
        Returns:
            初步设计的年度趋势
        """
        prompt = initial_trends_template(self.persona)
        
        try:
            result_str = llm_call_j(prompt)
            # 匹配字符串的第一个和最后一个{}，确保解析完整的JSON对象
            start_idx = result_str.find('{')
            end_idx = result_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                result_str = result_str[start_idx:end_idx+1]
            # 解析JSON字符串
            result = json.loads(result_str)
            return {"status": "success", "data": result}
        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"JSON解析失败：{e}"}
        except Exception as e:
            return {"status": "error", "message": f"设计初步趋势失败：{e}"}
    
    def _refine_trends_with_feedback(self, initial_trends: Dict, monthly_summaries: Dict[str, Dict]) -> Dict:
        """
        结合 12 个月的总结反馈，重新设计一年的偏好习惯兴趣变化趋势，运动健康变化趋势总结
        
        Args:
            initial_trends: 初步设计的趋势
            monthly_summaries: 12 个月的总结报告
        
        Returns:
            优化后的年度趋势
        """
        # 提取 12 个月的关键信息
        monthly_highlights = []
        for month, summary in monthly_summaries.items():
            if summary.get("status") == "success":
                highlight = {
                    "month": month,
                    "habit_summary": summary.get("habit_summary", {}),
                    "health_summary": summary.get("health_summary", {})
                }
                monthly_highlights.append(highlight)
        
        prompt = refine_trends_template(initial_trends, monthly_highlights, self.persona)
        
        try:
            result_str = llm_call_reason_j(prompt)
            # 匹配字符串的第一个和最后一个{}，确保解析完整的JSON对象
            start_idx = result_str.find('{')
            end_idx = result_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                result_str = result_str[start_idx:end_idx+1]
            # 解析JSON字符串
            result = json.loads(result_str)
            return {"status": "success", "data": result}
        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"JSON解析失败：{e}"}
        except Exception as e:
            return {"status": "error", "message": f"优化趋势失败：{e}"}
    
    def _analyze_monthly_issues(self, refined_trends: Dict, monthly_summaries: Dict[str, Dict]) -> Dict:
        """
        分析 12 月总结的分析逻辑错误不合理之处，给出每月的修改指导
        
        Args:
            refined_trends: 优化后的年度趋势
            monthly_summaries: 12 个月的总结报告
        
        Returns:
            每月的修改指导意见
        """
        monthly_guidance = {}
        
        # 过滤出成功的月份总结
        successful_summaries = {}
        for month, summary in monthly_summaries.items():
            if summary.get("status") == "success":
                successful_summaries[month] = summary
            else:
                monthly_guidance[month] = {
                    "status": "error",
                    "message": "该月总结生成失败，无法分析"
                }
        
        if not successful_summaries:
            return monthly_guidance
        
        self._print("  - 一次性分析所有月份的问题...")
        
        # 使用新模板一次性分析所有月份
        prompt = all_months_issues_template(successful_summaries, refined_trends)
        
        try:
            result_str = llm_call_reason_j(prompt)
            # 匹配字符串的第一个和最后一个{}，确保解析完整的JSON对象
            start_idx = result_str.find('{')
            end_idx = result_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                result_str = result_str[start_idx:end_idx+1]
            # 解析JSON字符串
            result = json.loads(result_str)
            # 处理返回结果
            if isinstance(result, dict) and "monthly_guidance" in result:
                for month, guidance_data in result["monthly_guidance"].items():
                    monthly_guidance[month] = {"status": "success", "data": guidance_data}
            else:
                # 处理格式不符合预期的情况
                for month in successful_summaries:
                    monthly_guidance[month] = {
                        "status": "error",
                        "message": "分析结果格式不符合预期"
                    }
        except json.JSONDecodeError as e:
            # JSON解析失败时，为所有成功的月份设置错误状态
            for month in successful_summaries:
                monthly_guidance[month] = {
                    "status": "error",
                    "message": f"JSON解析失败：{e}"
                }
        except Exception as e:
            # 其他分析失败时，为所有成功的月份设置错误状态
            for month in successful_summaries:
                monthly_guidance[month] = {
                    "status": "error",
                    "message": f"分析失败：{e}"
                }
        
        return monthly_guidance
    
    def _generate_monthly_final_summaries(self, refined_trends: Dict, monthly_guidance: Dict, 
                                         original_events: Dict[str, List[Dict]]) -> Dict:
        """
        整合优化后的趋势和每月修改指导，生成每个月的最终优化总结
        
        Args:
            refined_trends: 优化后的年度趋势
            monthly_guidance: 每月的修改指导意见
            original_events: 原始事件
        
        Returns:
            每个月的最终优化总结
        """
        monthly_final_summaries = {}
        
        for month, events in original_events.items():
            guidance = monthly_guidance.get(month, {})
            if guidance.get("status") != "success":
                monthly_final_summaries[month] = {
                    "status": "warning",
                    "message": "该月修改指导生成失败，无法生成优化版本"
                }
                continue
            
            self._print(f"  - 生成 {month} 的最终优化总结...")
            
            # 调用模板生成 prompt
            prompt = generate_monthly_final_summary_template(
                month=month,
                original_events=events,
                guidance=guidance.get("data", {}),
                refined_trends=refined_trends.get("data", {})
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
                monthly_final_summaries[month] = {
                    "status": "success",
                    "data": result
                }
            except json.JSONDecodeError as e:
                monthly_final_summaries[month] = {
                    "status": "error",
                    "message": f"JSON解析失败：{e}"
                }
            except Exception as e:
                monthly_final_summaries[month] = {
                    "status": "error",
                    "message": f"生成优化总结失败：{e}"
                }
        
        return monthly_final_summaries
    
    def optimize_all_months(self, monthly_final_summaries: Dict[str, Dict],
                           event_library: List[Dict] = None) -> Dict:
        """
        串行优化所有月份的事件
        
        Args:
            monthly_final_summaries: 年度趋势分析返回的每月最终优化总结
            event_library: 预定义的事件库数组
        
        Returns:
            所有月份的优化结果
        """
        self._print(f"\n{'='*60}")
        self._print(f"开始逐月优化事件")
        self._print(f"{'='*60}")
        
        optimized_months = {}
        event_library = event_library or []
        
        # 按月份顺序串行处理
        sorted_months = sorted(monthly_final_summaries.keys())
        
        for month in sorted_months:
            self._print(f"\n{'='*40}")
            self._print(f"处理 {month}...")
            self._print(f"{'='*40}")
            
            try:
                result = self.optimize_single_month(
                    month, monthly_final_summaries, event_library
                )
                optimized_months[month] = result
                self.persona = result.get("updated_persona", {})
                self._print(f"✓ {month} 优化完成")
            except Exception as e:
                self._print(f"⚠️  {month} 优化失败：{e}")
                optimized_months[month] = {
                    "status": "error",
                    "month": month,
                    "message": str(e)
                }
        
        self._print(f"\n✓ 所有月份优化完成！")
        return optimized_months
    
    def optimize_single_month(self, month: str, monthly_final_summaries: Dict[str, Dict],
                             event_library: List[Dict]) -> Dict:
        """
        优化单个月份的事件
        
        Args:
            month: 月份，格式为"YYYY-MM"
            monthly_final_summaries: 年度趋势分析返回的每月最终优化总结
            event_library: 预定义的事件库数组
        
        Returns:
            优化后的月份数据和动态画像
        """
        # 获取该月的最终优化总结（已整合总结和趋势变化）
        month_summary_data = monthly_final_summaries.get(month, {})
        # 提取实际的总结数据（处理嵌套结构）
        if isinstance(month_summary_data, dict):
            final_summary = month_summary_data.get("data", month_summary_data)
        else:
            final_summary = month_summary_data
        
        # Step 1: 润色已有事件
        self._print(f"  [Step 1] 润色已有事件...")
        polished_events = self.polish_existing_events(month, final_summary)
        
        # Step 2: 基于趋势总结新增事件
        self._print(f"  [Step 2] 基于趋势新增事件...")
        trend_based_events = self.add_events_based_on_trends(month, polished_events, final_summary)
        
        # Step 3: 从事件库选择事件丰富数据
        self._print(f"  [Step 3] 从事件库选择事件...")
        enriched_events = self.select_events_from_library(month, trend_based_events, event_library)
        
        # Step 4: 评估和最终调整
        self._print(f"  [Step 4] 评估和最终调整...")
        final_events, evaluation = self.evaluate_and_adjust(month, enriched_events, final_summary)
        
        # Step 5: 生成新的月份总结和动态画像
        self._print(f"  [Step 5] 生成新的月份总结和动态画像...")
        new_summary, updated_persona = self.generate_new_summary_and_persona(month, final_events)
        
        return {
            "status": "success",
            "month": month,
            "final_events": final_events,
            "evaluation": evaluation,
            "new_summary": new_summary,
            "updated_persona": updated_persona
        }
    
    def polish_existing_events(self, month: str, final_summary: Dict) -> List[Dict]:
        """
        润色已有事件：调整时间分布、微调描述，使事件更连贯自然
        
        Args:
            month: 月份
            final_summary: 月度最终优化总结（已整合总结和趋势）
        
        Returns:
            润色后的事件列表
        """
        # 从图谱中获取该月的原始事件
        month_data = self.get_month_data(month)
        original_events = month_data.get("events", []) if month_data else []
        
        prompt = polish_events_template(
            month=month,
            original_events=original_events,
            guidance=final_summary,  # 使用 final_summary 提供指导意见
            refined_trends=final_summary  # 使用 final_summary 提供趋势背景
        )
        
        self._print(f"    [LLM Prompt]\n{prompt}")  # 完整打印 prompt
        
        try:
            result_str = llm_call_j(prompt)
            self._print(f"    [LLM Response]\n{result_str}")  # 完整打印 response
            # 匹配字符串的第一个和最后一个{}，确保解析完整的JSON对象
            start_idx = result_str.find('{')
            end_idx = result_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                result_str = result_str[start_idx:end_idx+1]
            # 解析JSON字符串
            result = json.loads(result_str)
            return result.get("polished_events", [])
        except json.JSONDecodeError as e:
            self._print(f"⚠️  润色事件失败（JSON解析）：{e}")
            return original_events
        except Exception as e:
            self._print(f"⚠️  润色事件失败：{e}")
            return original_events
    
    def add_events_based_on_trends(self, month: str, current_events: List[Dict], 
                                  final_summary: Dict) -> List[Dict]:
        """
        基于趋势总结新增事件，实现趋势变化
        
        Args:
            month: 月份
            current_events: 当前事件列表
            final_summary: 月度最终优化总结（已整合总结和趋势）
        
        Returns:
            新增事件后的事件列表
        """
        prompt = add_trend_based_events_template(
            month=month,
            current_events=current_events,
            trend_changes=final_summary,  # 使用 final_summary 提供趋势变化信息
            guidance=final_summary  # 使用 final_summary 提供指导意见
        )
        
        self._print(f"    [LLM Prompt]\n{prompt}")  # 完整打印 prompt
        
        try:
            result_str = llm_call_j(prompt)
            self._print(f"    [LLM Response]\n{result_str}")  # 完整打印 response
            # 匹配字符串的第一个和最后一个{}，确保解析完整的JSON对象
            start_idx = result_str.find('{')
            end_idx = result_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                result_str = result_str[start_idx:end_idx+1]
            # 解析JSON字符串
            result = json.loads(result_str)
            new_events = result.get("new_events", [])
            return current_events + new_events
        except json.JSONDecodeError as e:
            self._print(f"⚠️  新增趋势事件失败（JSON解析）：{e}")
            return current_events
        except Exception as e:
            self._print(f"⚠️  新增趋势事件失败：{e}")
            return current_events
    
    def select_events_from_library(self, month: str, current_events: List[Dict], 
                                  event_library: List[Dict]) -> List[Dict]:
        """
        从预定义的事件库中选择合适的事件来丰富数据
        
        Args:
            month: 月份
            current_events: 当前事件列表
            event_library: 预定义的事件库
        
        Returns:
            丰富后的事件列表
        """
        # 提取月份（MM 格式）用于查询节假日
        month_num = month.split("-")[1] if "-" in month else "01"
        holidays = self.get_month_holidays(month_num)
        
        prompt = select_library_events_template(
            month=month,
            current_events=current_events,
            event_library=event_library,
            holidays=holidays
        )
        
        self._print(f"    [LLM Prompt]\n{prompt}")  # 完整打印 prompt
        
        try:
            result_str = llm_call_j(prompt)
            self._print(f"    [LLM Response]\n{result_str}")  # 完整打印 response
            # 匹配字符串的第一个和最后一个{}，确保解析完整的JSON对象
            start_idx = result_str.find('{')
            end_idx = result_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                result_str = result_str[start_idx:end_idx+1]
            # 解析JSON字符串
            result = json.loads(result_str)
            selected_events = result.get("selected_events", [])
            
            # 将选中的事件添加到当前事件列表
            all_events = current_events.copy()
            for event in selected_events:
                all_events.append({
                    "title": event.get("title", ""),
                    "time": event.get("time", []),
                    "description": event.get("description", ""),
                    "type": event.get("type", ""),
                    "source": "library",
                    "source_id": event.get("source_id")
                })
            
            return all_events
        except json.JSONDecodeError as e:
            self._print(f"⚠️  从事件库选择失败（JSON解析）：{e}")
            return current_events
        except Exception as e:
            self._print(f"⚠️  从事件库选择失败：{e}")
            return current_events
    
    def evaluate_and_adjust(self, month: str, events: List[Dict], 
                           final_summary: Dict) -> tuple:
        """
        评估事件质量并进行最终调整
        
        Args:
            month: 月份
            events: 事件列表
            final_summary: 月度最终优化总结（已整合总结和趋势）
        
        Returns:
            (调整后的事件列表，评估报告)
        """
        prompt = evaluate_monthly_events_template(
            month=month,
            events=events,
            guidance=final_summary,  # 使用 final_summary 提供评估指导
            refined_trends=final_summary  # 使用 final_summary 提供趋势参考
        )
        
        self._print(f"    [LLM Prompt]\n{prompt}")  # 完整打印 prompt
        
        try:
            result_str = llm_call_j(prompt)
            self._print(f"    [LLM Response]\n{result_str}")  # 完整打印 response
            # 匹配字符串的第一个和最后一个{}，确保解析完整的JSON对象
            start_idx = result_str.find('{')
            end_idx = result_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                result_str = result_str[start_idx:end_idx+1]
            # 解析JSON字符串
            result = json.loads(result_str)
            evaluation = result.get("evaluation", {})
            
            # 优先使用 LLM 返回的最终事件列表
            if "final_event_list" in result:
                final_events = result["final_event_list"]
                self._print(f"    ✓ 使用 LLM 生成的最终事件列表")
            else:
                # 如果没有 final_event_list，则根据 adjustments 手动调整
                final_events = events.copy()
                adjustments = result.get("adjustments", [])
                
                if adjustments:
                    self._print(f"    应用 {len(adjustments)} 项调整...")
                    for adjustment in adjustments:
                        action = adjustment.get("action", "").lower()
                        event = adjustment.get("event", {})
                        event_id = adjustment.get("event_id")
                        
                        if action == "add" and event:
                            # 增加事件
                            final_events.append(event)
                            self._print(f"      + 添加事件：{event.get('title', 'Untitled')}")
                        
                        elif action == "delete" and event_id:
                            # 删除事件（通过 event_id 匹配）
                            original_count = len(final_events)
                            final_events = [
                                e for e in final_events 
                                if e.get("id") != event_id and e.get("title") != event_id
                            ]
                            if len(final_events) < original_count:
                                self._print(f"      - 删除事件 ID: {event_id}")
                        
                        elif action == "delete" and event:
                            # 删除事件（通过事件内容匹配）
                            event_title = event.get("title", "")
                            if event_title:
                                original_count = len(final_events)
                                final_events = [
                                    e for e in final_events 
                                    if e.get("title") != event_title
                                ]
                                if len(final_events) < original_count:
                                    self._print(f"      - 删除事件：{event_title}")
                        
                        elif action == "modify" and event:
                            # 修改事件（通过 event_id 或 title 匹配）
                            target_id = event.get("id") or event.get("title")
                            if target_id:
                                for i, e in enumerate(final_events):
                                    if e.get("id") == target_id or e.get("title") == target_id:
                                        final_events[i] = event
                                        self._print(f"      ~ 修改事件：{event.get('title', 'Untitled')}")
                                        break
            
            return final_events, evaluation
        except json.JSONDecodeError as e:
            self._print(f"⚠️  评估失败（JSON解析）：{e}")
            return events, {"status": "error", "message": str(e)}
        except Exception as e:
            self._print(f"⚠️  评估失败：{e}")
            return events, {"status": "error", "message": str(e)}
    
    def generate_new_summary_and_persona(self, month: str, events: List[Dict]) -> tuple:
        """
        基于最终确定的事件生成新的月份总结和动态画像（两步法）
        
        Args:
            month: 月份
            events: 最终事件列表
        
        Returns:
            (新的月份总结，更新后的画像)
        """
        # Step 1: 生成月份总结
        self._print(f"    [Step 1] 生成月份总结...")
        monthly_summary = self.generate_monthly_summary(month, events)
        
        # Step 2: 更新人物画像
        self._print(f"    [Step 2] 更新人物画像...")
        updated_persona = self.update_persona(month, events, monthly_summary)
        
        return monthly_summary, updated_persona
    
    def generate_monthly_summary(self, month: str, events: List[Dict]) -> Dict:
        """
        第一步：生成月份总结（三个维度）
        
        Args:
            month: 月份
            events: 最终事件列表
        
        Returns:
            月份总结字典，包含 event_summary、health_summary、habit_summary
        """
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
            
            # 提取并格式化三个维度的总结
            summary = {
                "status": "success",
                "month": month,
                "event_summary": {
                    "status": "success",
                    "data": {"summary": result.get("event_summary", "")}
                },
                "health_summary": {
                    "status": "success",
                    "data": result.get("health_summary", {})
                },
                "habit_summary": {
                    "status": "success",
                    "data": result.get("habit_summary", {})
                }
            }
            
            self._print(f"      ✓ 月份总结生成完成")
            return summary
            
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
    
    def update_persona(self, month: str, events: List[Dict], monthly_summary: Dict) -> Dict:
        """
        第二步：更新人物画像（基于修改操作增量更新）
        
        Args:
            month: 月份
            events: 最终事件列表
            monthly_summary: 月份总结报告
        
        Returns:
            更新后的人物画像
        """
        prompt = update_persona_template(
            month=month,
            final_events=events,
            monthly_summary=monthly_summary,
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
            
            # 获取修改操作列表
            modifications = result.get("modifications", [])
            
            if not modifications:
                self._print(f"      ✓ 无需更新人物画像")
                return self.persona
            
            # 深拷贝原始画像，避免直接修改
            import copy
            updated_persona = copy.deepcopy(self.persona)
            
            # 执行修改操作
            change_count = 0
            self._print(f"      📋 开始执行 {len(modifications)} 项修改操作：")
            
            for idx, mod in enumerate(modifications, 1):
                field = mod.get("field")
                reason = mod.get("reason", "未提供原因")
                
                if not field:
                    self._print(f"        [{idx}] ⚠️  跳过无效操作（缺少字段名）")
                    continue
                
                # 处理 relation 字段的特殊格式
                if field == "relation":
                    person_name = mod.get("person_name")
                    updates = mod.get("updates", {})
                    
                    if person_name and updates:
                        # 查找该人物（relation 是嵌套列表结构：[[人物组1], [人物组2]]）
                        relations = updated_persona.get("relation", [])
                        person_found = False
                        
                        # 遍历所有人物组
                        for group in relations:
                            if isinstance(group, list):
                                # 在组内查找具体人物
                                for person in group:
                                    if isinstance(person, dict) and person.get("name") == person_name:
                                        # 更新该人物的字段
                                        update_details = []
                                        for key, value in updates.items():
                                            old_value = person.get(key, "N/A")
                                            person[key] = value
                                            update_details.append(f"{key}: {old_value} → {value}")
                                        
                                        person_found = True
                                        change_count += 1
                                        self._print(f"        [{idx}] ✅ 更新关系人物 '{person_name}'")
                                        for detail in update_details:
                                            self._print(f"             - {detail}")
                                        self._print(f"             原因: {reason}")
                                        break
                                
                                if person_found:
                                    break
                            elif isinstance(group, dict) and group.get("name") == person_name:
                                # 兼容非嵌套的情况
                                update_details = []
                                for key, value in updates.items():
                                    old_value = group.get(key, "N/A")
                                    group[key] = value
                                    update_details.append(f"{key}: {old_value} → {value}")
                                
                                person_found = True
                                change_count += 1
                                self._print(f"        [{idx}] ✅ 更新关系人物 '{person_name}'")
                                for detail in update_details:
                                    self._print(f"             - {detail}")
                                self._print(f"             原因: {reason}")
                                break
                        
                        if not person_found:
                            self._print(f"        [{idx}] ❌ 未找到关系人物 '{person_name}'，跳过")
                    else:
                        self._print(f"        [{idx}] ⚠️  relation 操作缺少 person_name 或 updates，跳过")
                else:
                    # 处理普通字段
                    if "value" in mod:
                        old_value = updated_persona.get(field, "N/A")
                        new_value = mod["value"]
                        updated_persona[field] = new_value
                        change_count += 1
                        
                        # 格式化显示值（截断过长的内容）
                        if isinstance(new_value, str) and len(new_value) > 100:
                            display_new = new_value[:100] + "..."
                        elif isinstance(new_value, (list, dict)):
                            display_new = json.dumps(new_value, ensure_ascii=False)[:100] + "..."
                        else:
                            display_new = new_value
                        
                        self._print(f"        [{idx}] ✅ 更新字段 '{field}'")
                        self._print(f"             旧值: {old_value}")
                        self._print(f"             新值: {display_new}")
                        self._print(f"             原因: {reason}")
                    else:
                        self._print(f"        [{idx}] ⚠️  字段 '{field}' 缺少 value，跳过")
            
            self._print(f"\n      📊 修改统计：")
            self._print(f"         - 总操作数：{len(modifications)}")
            self._print(f"         - 成功修改：{change_count}")
            self._print(f"         - 跳过/失败：{len(modifications) - change_count}")
            
            if change_count > 0:
                self._print(f"      ✓ 人物画像更新完成")
            else:
                self._print(f"      ⚠️  无有效修改操作，保持原画像")
            
            return updated_persona
                
        except json.JSONDecodeError as e:
            self._print(f"      ⚠️  更新人物画像失败（JSON解析）：{e}")
            return self.persona
        except Exception as e:
            self._print(f"      ⚠️  更新人物画像失败：{e}")
            import traceback
            traceback.print_exc()
            return self.persona

    
    def generate_monthly_summaries(self, months: List[str] = None) -> Dict:
        """
        并行生成指定月份的多维度总结报告
        
        Args:
            months: 月份列表，格式为 ["YYYY-MM", ...]，默认为当年所有月份
        
        Returns:
            所有月份的总结报告汇总
        """
        if months is None:
            months = self._generate_month_list(f"{self.year}-01", f"{self.year}-12")
        
        self._print(f"\n{'='*60}")
        self._print(f"开始并行生成 {len(months)} 个月份的总结报告")
        self._print(f"{'='*60}")
        
        all_summaries = {}
        
        # 并行处理每个月份
        with ThreadPoolExecutor(max_workers=6) as executor:
            # 提交所有月份的处理任务
            future_to_month = {}
            for month in months:
                month_data = self.get_month_data(month)
                future = executor.submit(
                    self._generate_single_month_summary, 
                    month, 
                    month_data, 
                    self.persona
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
    
    def _generate_single_month_summary(self, month: str, month_data: Dict, persona: Dict) -> Dict:
        """
        生成单个月份的三个维度总结（串行调用三个 LLM）
        
        Args:
            month: 月份
            month_data: 月份数据
            persona: 人物画像
        
        Returns:
            该月份的三个维度总结
        """
        events = month_data.get("events", [])
        
        # 1. 事件生活总结
        event_summary = self._generate_event_summary(month, events, persona)
        
        # 2. 运动健康体重作息变化总结
        health_summary = self._generate_health_summary(month, events, persona)
        
        # 3. 偏好习惯兴趣总结
        habit_summary = self._generate_habit_summary(month, events, persona)
        
        return {
            "status": "success",
            "month": month,
            "event_summary": event_summary,
            "health_summary": health_summary,
            "habit_summary": habit_summary
        }
    

    
    def _generate_habit_summary(self, month: str, events: List[Dict], persona: Dict) -> Dict:
        """
        生成 3）偏好习惯兴趣总结
        
        Args:
            month: 月份
            events: 本月事件列表
            persona: 人物画像
        
        Returns:
            习惯偏好总结
        """
        prompt = habit_summary_template(month, persona, events)
        
        try:
            result = llm_call(prompt)
            return {"status": "success", "data": result}
        except Exception as e:
            return {"status": "error", "message": f"生成习惯总结失败：{e}"}
    
    def _generate_health_summary(self, month: str, events: List[Dict], persona: Dict) -> Dict:
        """
        生成 2）运动健康体重作息变化总结
        
        Args:
            month: 月份
            events: 本月事件列表
            persona: 人物画像
        
        Returns:
            运动健康总结
        """
        prompt = health_summary_template(month, persona, events)
        
        try:
            result = llm_call(prompt)
            return {"status": "success", "data": result}
        except Exception as e:
            return {"status": "error", "message": f"生成健康总结失败：{e}"}
    
    def _generate_event_summary(self, month: str, events: List[Dict], persona: Dict) -> Dict:
        """
        生成 1）本月事件生活总结
        
        Args:
            month: 月份
            events: 本月事件列表
            persona: 人物画像
        
        Returns:
            本月事件总结
        """
        prompt = event_summary_template(month, persona, events)
        
        try:
            result = llm_call(prompt).strip()
            return {"status": "success", "data": result}
        except Exception as e:
            return {"status": "error", "message": f"生成事件总结失败：{e}"}
    

    
    def _generate_month_list(self, start_month: str, end_month: str) -> List[str]:
        """生成月份列表"""
        from datetime import datetime
        
        months = []
        current = datetime.strptime(start_month, "%Y-%m")
        end = datetime.strptime(end_month, "%Y-%m")
        
        while current <= end:
            months.append(current.strftime("%Y-%m"))
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1)
            else:
                current = datetime(current.year, current.month + 1, 1)
        
        return months
    
    def run_full_pipeline(self, output_dir: str = None, skip_existing: bool = True):
        """
        执行完整的月度优化流程：
        1. 生成总结报告并保存
        2. 分析年度趋势并保存
        3. 优化所有月份并保存
        
        Args:
            output_dir: 输出目录，默认为 filepath/process/refined
            skip_existing: 如果目标文件已存在则跳过该步骤，默认为 True
        
        Returns:
            包含三个步骤结果的字典
        """
        if output_dir is None:
            output_dir = os.path.join(self.filepath, "process", "refined")
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 定义输出文件路径
        summaries_file = os.path.join(output_dir, "monthly_summaries.json")
        trends_file = os.path.join(output_dir, "yearly_trends.json")
        optimized_file = os.path.join(output_dir, "optimized_months.json")
        
        self._print(f"\n{'='*80}")
        self._print(f"开始执行完整的月度优化流程")
        self._print(f"输出目录: {output_dir}")
        self._print(f"{'='*80}")
        
        results = {
            "summaries": None,
            "trends": None,
            "optimized": None
        }
        
        # Step 1: 生成总结报告
        self._print(f"\n{'='*60}")
        self._print(f"Step 1: 生成月度总结报告")
        self._print(f"{'='*60}")
        
        if skip_existing and os.path.exists(summaries_file):
            self._print(f"⊙ 总结报告已存在，跳过此步骤")
            try:
                with open(summaries_file, 'r', encoding='utf-8') as f:
                    results["summaries"] = json.load(f)
                self._print(f"✓ 已加载现有总结报告")
            except Exception as e:
                self._print(f"⚠️  加载现有总结报告失败：{e}，重新生成")
                results["summaries"] = self.generate_monthly_summaries()
                self._save_json(results["summaries"], summaries_file)
        else:
            results["summaries"] = self.generate_monthly_summaries()
            self._save_json(results["summaries"], summaries_file)
            self._print(f"✓ 总结报告已保存到: {summaries_file}")
        
        # Step 2: 分析年度趋势
        self._print(f"\n{'='*60}")
        self._print(f"Step 2: 分析年度趋势")
        self._print(f"{'='*60}")
        
        if skip_existing and os.path.exists(trends_file):
            self._print(f"⊙ 年度趋势分析已存在，跳过此步骤")
            try:
                with open(trends_file, 'r', encoding='utf-8') as f:
                    results["trends"] = json.load(f)
                self._print(f"✓ 已加载现有年度趋势分析")
            except Exception as e:
                self._print(f"⚠️  加载现有年度趋势分析失败：{e}，重新生成")
                results["trends"] = self.analyze_yearly_trends(results["summaries"])
                self._save_json(results["trends"], trends_file)
        else:
            results["trends"] = self.analyze_yearly_trends(results["summaries"])
            self._save_json(results["trends"], trends_file)
            self._print(f"✓ 年度趋势分析已保存到: {trends_file}")
        
        # Step 3: 优化所有月份
        self._print(f"\n{'='*60}")
        self._print(f"Step 3: 优化所有月份")
        self._print(f"{'='*60}")
        
        if skip_existing and os.path.exists(optimized_file):
            self._print(f"⊙ 月度优化结果已存在，跳过此步骤")
            try:
                with open(optimized_file, 'r', encoding='utf-8') as f:
                    results["optimized"] = json.load(f)
                self._print(f"✓ 已加载现有月度优化结果")
            except Exception as e:
                self._print(f"⚠️  加载现有月度优化结果失败：{e}，重新生成")
                results["optimized"] = self.optimize_all_months(results["trends"])
                self._save_json(results["optimized"], optimized_file)
        else:
            results["optimized"] = self.optimize_all_months(results["trends"])
            self._save_json(results["optimized"], optimized_file)
            self._print(f"✓ 月度优化结果已保存到: {optimized_file}")
        
        self._print(f"\n{'='*80}")
        self._print(f"✓ 完整的月度优化流程执行完成！")
        self._print(f"{'='*80}")
        
        return results
    
    def _save_json(self, data: Any, filepath: str):
        """
        保存数据为 JSON 文件
        
        Args:
            data: 要保存的数据
            filepath: 文件路径
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._print(f"✓ 数据已保存到: {filepath}")
        except Exception as e:
            print(f"⚠️  保存文件失败 {filepath}: {e}")