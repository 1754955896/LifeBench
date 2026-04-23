# -*- coding: utf-8 -*-
import os
from datetime import datetime, timedelta
import holidays
import json
from typing import List, Dict, Optional

from utils.llm_call import llm_call_j


class DailyRefiner:
    """
    每日事件优化类，负责基于画像、每月状态和事件列表对每日事件进行精细化处理
    """

    def __init__(self, persona: Dict, events: List[Dict], monthly_status: Dict = None, yearly_trends: Dict = None, record_folder: str = None):
        """
        初始化每日优化器
        
        参数:
            persona: 人物画像数据
            events: 事件列表（通常为某个月的事件）
            monthly_status: 每月状态信息（可选）
            yearly_trends: 年度趋势数据（yearly_trends.json 的内容，可选）
            record_folder: 记录文件夹路径，用于保存和读取分析结果缓存
        """
        self.persona = persona
        self.events = events
        self.monthly_status = monthly_status or {}
        self.yearly_trends = yearly_trends or {}
        self.record_folder = record_folder
        self.bottom_events: Optional[List[Dict]] = None
        # 保存当前的事件更新操作
        self.current_event_updates = []
        # 缓存各月份的分析数据 {month: {health_result, life_result, month_transition_analysis}}
        self.monthly_analyses_cache = {}
        # 初始化时更新底层事件
        self.update_bottom_events()
        # 初始化时串行生成所有月份的分析数据
        self._precompute_all_month_analyses()

    def _generate_month_analysis(self, month: str, prev_health_end_state: Dict = None, prev_final_day_status: str = None) -> Dict:
        """
        为指定月份生成分析数据
        
        参数:
            month: 月份字符串 (YYYY-MM)
            prev_health_end_state: 上个月的健康结束状态
            prev_final_day_status: 上个月的月末状态描述
            
        返回:
            Dict: 包含 health_result, life_result, month_transition_analysis 的字典
        """
        from utils.llm_call import llm_call_reason_j



        # 获取当月事件
        month_events = []
        # optimized_months.json 格式: {"2025-01": {"final_events": [...]}, ...}
        if isinstance(self.monthly_status, dict):
            month_data = self.monthly_status.get(month, {})
            if isinstance(month_data, dict):
                month_events = month_data.get("final_events", [])
        
        # 如果没有 monthly_status 或没找到，尝试从 self.events 中过滤（简化处理）
        if not month_events and self.events:
            month_events = self.events

        try:
            analysis_prompt = f"""
            你是一位专业的个人生活与健康分析师。请根据以下信息，为该月份生成详细的分析报告。
            
            【人物画像】
            {json.dumps(self.persona, ensure_ascii=False)}
            
            【年度趋势背景】
            {json.dumps(self.yearly_trends.get(month, {}), ensure_ascii=False)}
            
            【上月衔接信息】
            - 上月健康结束状态: {json.dumps(prev_health_end_state, ensure_ascii=False) if prev_health_end_state else '无'}
            - 上月月末状态: {prev_final_day_status or '无'}
            
            【当月已知事件列表（非全量）】
            {json.dumps(month_events, ensure_ascii=False)}
            
            【任务要求】
            请注意：提供的事件列表仅代表该月发生的部分关键事件，**不代表全貌**。请在不违背已知事件的前提下，基于常识、季节变化、人物性格及社会规律，**合理推测并补充**该月可能发生的其他生活细节、微小变动或偶发事件，以体现真实世界的复杂性与丰富性。
            
            请输出一个 JSON 对象，包含以下三个部分：
            1. "health_result": 对应健康分析。必须包含：
               - "initial_state": 月初（1号）的健康状况、体重及运动表现（需参考上月结束状态保持连贯）。
               - "mid_month_state": 月中（15号左右）的健康状况、体重及运动表现。
               - "end_of_month_state": 月末（最后一天）的健康状况、体重及运动表现。
            2. "life_result": 对应生活分析。必须包含：
               - "summary": 对该月整体生活状态的总结。包括主要事件，以及基于常识合理推测的周围人变化（如假期、季节性活动等）。
            3. "month_transition_analysis": 对应月度变化分析。必须包含：
               - "previous_day_status": 上月月末的状态描述（直接填入提供的上月信息）。
               - "final_day_status": 本月最后一天的状态描述（位置、心情等）。
               - "profile_changes": 本月人物画像或习惯发生的具体变化。
            
            请确保分析结果既符合人物的长期发展趋势，又具有生动的生活气息和合理的随机波动。
            """
            
            res = llm_call_j(analysis_prompt)
            print(f"LLM Analysis Prompt: {analysis_prompt}，"f"LLM 输出: {res}")
            # 如果返回的是字符串，尝试解析 JSON
            if isinstance(res, str):
                try:
                    import re
                    match = re.search(r'\{.*\}', res, re.DOTALL)
                    if match:
                        res = json.loads(match.group())
                    else:
                        res = json.loads(res)
                except Exception as e:
                    print(f"⚠️  解析 {month} LLM 返回的 JSON 失败: {e}")
                    return {"health_result": {}, "life_result": {}, "month_transition_analysis": {}}
            
            if isinstance(res, dict):
                return {
                    "health_result": res.get("health_result", {}),
                    "life_result": res.get("life_result", {}),
                    "month_transition_analysis": res.get("month_transition_analysis", {})
                }
        except Exception as e:
            print(f"⚠️  生成 {month} 分析数据失败: {e}")
        
        return {"health_result": {}, "life_result": {}, "month_transition_analysis": {}}

    def _precompute_all_month_analyses(self):
        """
        在初始化时串行生成所有月份的分析数据，确保月份间连贯性。
        如果 record_folder 存在且 analyse.json 已存在，则直接读取缓存。
        """
        # 1. 检查缓存文件
        if self.record_folder:
            cache_path = os.path.join(self.record_folder, "analyse.json")
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        self.monthly_analyses_cache = json.load(f)
                    print(f"✓ 已从 {cache_path} 加载预计算的分析数据")
                    return
                except Exception as e:
                    print(f"⚠️  读取分析缓存失败: {e}，将重新生成")

        if not self.monthly_status:
            return
            
        # 适配 optimized_months.json 格式: {"2025-01": {...}, ...}
        months = []
        if isinstance(self.monthly_status, dict):
            # 尝试提取并排序月份键
            months = sorted([k for k in self.monthly_status.keys() if len(k) == 7 and k[4] == '-'])
        
        if not months:
            print("⚠️  未能在 monthly_status 中识别出有效的月份格式 (YYYY-MM)")
            return
            
        prev_health_end_state = None
        prev_final_day_status = None
        
        print("\n[Init] 正在预计算所有月份的分析数据...")
        for month in months:
            print(f"  - 正在生成 {month} 的分析数据...")
            analysis = self._generate_month_analysis(month, prev_health_end_state, prev_final_day_status)
            self.monthly_analyses_cache[month] = analysis
            
            # 更新下个月的衔接信息
            health_res = analysis.get("health_result", {})
            transition = analysis.get("month_transition_analysis", {})
            prev_health_end_state = health_res.get("end_of_month_state")
            prev_final_day_status = transition.get("final_day_status")
        
        print("[Init] ✓ 所有月份分析数据预计算完成")

        # 2. 保存结果到缓存文件
        if self.record_folder:
            try:
                os.makedirs(self.record_folder, exist_ok=True)
                cache_path = os.path.join(self.record_folder, "analyse.json")
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(self.monthly_analyses_cache, f, ensure_ascii=False, indent=2)
                print(f"✓ 分析数据已保存到: {cache_path}")
            except Exception as e:
                print(f"⚠️  保存分析缓存失败: {e}")

    def _get_bottom_level_events(self, events: List[Dict]) -> List[Dict]:
        """
        递归地获取所有底层事件
        
        参数:
            events: 事件列表
            
        返回:
            List[Dict]: 所有底层事件的列表
        """
        res = []
        for event in events:
            if event.get("subevent") and event["subevent"]:
                res.extend(self._get_bottom_level_events(event["subevent"]))
            else:
                res.append(event)
        return res

    def get_event_by_id(self, events: List[Dict], event_id: str) -> Dict:
        """
        根据事件ID获取事件
        
        参数:
            events: 事件列表
            event_id: 事件ID
            
        返回:
            Dict: 事件字典
        """
        for event in events:
            # 确保event_id是字符串类型后再比较
            if str(event.get("event_id", "")) == str(event_id) or event.get("event_id") == event_id:
                return event
            if event.get("subevent"):
                result = self.get_event_by_id(event["subevent"], event_id)
                if result:
                    return result
        return {}

    def update_bottom_events(self):
        """
        重新从事件中抽取底层事件（清空缓存并重新计算）
        """
        self.bottom_events = self._get_bottom_level_events(self.events)

    def update_bottom_event(self, event_id: str, updated_data: Dict) -> bool:
        """
        更新指定的底层事件
        
        参数:
            event_id: 要更新的事件ID
            updated_data: 包含更新字段的字典
            
        返回:
            bool: 是否成功更新
        """
        def _recursive_update(events_list):
            for event in events_list:
                if str(event.get("event_id", "")) == str(event_id):
                    event.update(updated_data)
                    return True
                if event.get("subevent"):
                    if _recursive_update(event["subevent"]):
                        return True
            return False

        success = _recursive_update(self.events)
        if success:
            # 更新成功后刷新底层事件缓存
            self.update_bottom_events()
        return success

    def get_holidays_and_weekends_in_range(self, start_date: str, end_date: str, country: str = "CN") -> str:
        """
        获取指定日期范围内的节假日和周末日期
        
        参数:
            start_date: 开始日期，格式"YYYY-MM-DD"
            end_date: 结束日期，格式"YYYY-MM-DD"
            country: 国家/地区代码（默认中国"CN"）
        
        返回:
            str: 包含节假日和周末日期的描述字符串
        """
        try:
            start_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            # 获取国家法定节假日
            country_holidays = holidays.CountryHoliday(country)
            
            holidays_list = []
            weekends_list = []
            
            current_date = start_obj
            while current_date <= end_obj:
                # 检查是否为节假日
                if current_date in country_holidays:
                    holiday_name = country_holidays.get(current_date)
                    if isinstance(holiday_name, list):
                        holiday_name = "、".join(holiday_name)
                    holidays_list.append(f"{current_date.strftime('%Y年%m月%d日')}({holiday_name})")
                
                # 检查是否为周末（周六或周日）
                weekday = current_date.weekday()
                if weekday == 5 or weekday == 6:  # 5代表周六，6代表周日
                    weekends_list.append(current_date.strftime('%Y年%m月%d日'))
                
                current_date += timedelta(days=1)
            
            # 生成描述字符串
            desc_parts = []
            if holidays_list:
                desc_parts.append(f"这段时间有的节假日为: {', '.join(holidays_list)}，没有任何其他节假日！")
            else:
                desc_parts.append("节假日: 这段期间没有任何节假日！！")
            if weekends_list:
                desc_parts.append(f"周日: {', '.join(weekends_list)}")
            
            return f"{start_date} 至 {end_date}, {'; '.join(desc_parts)}"
        except Exception as e:
            print(f"获取节假日信息失败: {e}")
            return f"{start_date} 至 {end_date}"

    def daily_event_refine(self, month: str) -> Dict[str, any]:
        """
        每日事件优化主函数：适配 EventRefiner.daily_event_refine 接口
        
        参数:
            month: 月份字符串，格式为 "YYYY-MM"
            
        返回:
            Dict[str, any]: 包含该月每日大纲数据的字典
        """
        from event.draft.event_refiner import EventRefiner
        import json
        
        print(f"\n开始对 {month} 进行每日事件精细化处理...")

        # 1. 准备日期参数
        year, mon = map(int, month.split("-"))
        start_date = f"{year}-{mon:02d}-01"
        
        # 计算该月的最后一天作为结束日期
        if mon == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, mon + 1, 1)
        end_date_obj = next_month - timedelta(days=1)
        end_date = end_date_obj.strftime('%Y-%m-%d')
        
        # 计算分割日期（月中，15号）
        split_date = f"{year}-{mon:02d}-15"
        
        # 2. 从缓存中获取预计算的分析数据
        print(f"[Step 0] 正在获取 {month} 的预计算分析数据...")
        analysis_data = self.monthly_analyses_cache.get(month, {})
        health_result = analysis_data.get("health_result", {})
        life_result = analysis_data.get("life_result", {})
        month_transition_analysis = analysis_data.get("month_transition_analysis", {})

        # 3. 初始化 EventRefiner 并调用
        try:
            refiner = EventRefiner(
                persona=self.persona,
                events=self.events,
                context=f"Daily Refinement for {month}"
            )
            result = refiner.daily_event_refine(
                events=self.events,
                start_date=start_date,
                end_date=end_date,
                persona=self.persona,
                split_date=split_date,
                health_result=health_result,
                life_result=life_result,
                month_transition_analysis=month_transition_analysis
            )
            
            # 对返回的大纲进行排序（如果返回的是包含 daily_outline 的结构）
            if isinstance(result, dict) and "daily_outline" in result:
                result["daily_outline"].sort(key=lambda x: x.get("date", ""))
                return result
            elif isinstance(result, list):
                result.sort(key=lambda x: x.get("date", ""))
                return {"month": month, "daily_outline": result}
            else:
                return result
                
        except Exception as e:
            print(f"✗ 调用 EventRefiner.daily_event_refine 失败: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _validate_and_optimize_monthly_outline(self, month: str, outline_data: List[Dict], summary: str) -> List[Dict]:
        """
        对一个月的大纲数据进行逻辑校验，并针对不合理处重新生成当日数据
        
        参数:
            month: 月份字符串
            outline_data: 每日大纲数据列表
            summary: 月度总结
            
        返回:
            List[Dict]: 优化后的每日大纲数据列表
        """
        from utils.llm_call import llm_call_reason_j
        from event.templates.template_refiner import template_daily_event_refine
        import re

        # Step 1: LLM 分析不合理之处
        validation_prompt = f"""
        你是一位严谨的生活逻辑审计专家。请检查以下 {month} 的每日大纲数据，找出其中存在的逻辑漏洞、时空冲突或不合理之处。
        
        【月度背景】
        {summary}
        
        【待检查的大纲数据】
        {json.dumps(outline_data, ensure_ascii=False)}
        
        【检查维度】
        1. **时空连贯性**：人物位置是否出现瞬移？交通时间是否充足？
        2. **状态连续性**：体重、心情、健康状态的变化是否符合生理规律和事件影响？
        3. **精力分配**：是否存在连续多日高强度活动导致的不合理疲劳？
        4. **事件一致性**：每日事件是否与月度总结和人物画像冲突？
        
        【输出要求】
        请输出一个 JSON 对象，包含一个 "issues" 数组。每个元素包含：
        - "date": 需要修改的日期 (YYYY-MM-DD)
        - "reason": 不合理的原因描述
        - "suggestion": 具体的修改指导建议
        
        如果没有发现明显问题，请返回空数组 []。
        """
        
        try:
            validation_res = llm_call_reason_j(validation_prompt)
            issues = []
            if isinstance(validation_res, dict):
                issues = validation_res.get("issues", [])
            elif isinstance(validation_res, list):
                issues = validation_res
            
            if not issues:
                print("✓ 逻辑校验通过，未发现明显不合理之处")
                return outline_data
            
            print(f"⚠️  发现 {len(issues)} 处逻辑问题，开始针对性修复...")
            
            # Step 2: 针对有问题的日期重新生成
            issue_dates = {item["date"] for item in issues if "date" in item}
            optimized_outline = []
            
            for day_data in outline_data:
                current_date = day_data.get("date", "")
                if current_date in issue_dates:
                    # 找到对应的修改建议
                    suggestions = [item.get("suggestion", "") for item in issues if item.get("date") == current_date]
                    suggestion_str = "; ".join(suggestions)
                    
                    print(f"  - 正在重生成 {current_date} 的数据 (原因: {suggestion_str[:50]}...)")
                    
                    # 构造重生成 Prompt
                    refine_prompt = template_daily_event_refine.format(
                        persona=json.dumps(self.persona, ensure_ascii=False),
                        event_data=json.dumps([day_data], ensure_ascii=False),
                        date_range_description=self.get_holidays_and_weekends_in_range(current_date, current_date),
                        previous_day_status="请参考前一日数据的结束状态",
                        final_day_status="请参考后一日数据的起始状态",
                        life_analysis_str=f"{summary}\n\n【修改指导】\n{suggestion_str}"
                    )
                    
                    try:
                        new_day_res = llm_call_reason_j(refine_prompt)
                        if isinstance(new_day_res, list) and len(new_day_res) > 0:
                            optimized_outline.append(new_day_res[0])
                        else:
                            optimized_outline.append(day_data) # 失败则保留原数据
                    except Exception as e:
                        print(f"    ⚠️  重生成失败: {e}，保留原数据")
                        optimized_outline.append(day_data)
                else:
                    optimized_outline.append(day_data)
                    
            return optimized_outline
            
        except Exception as e:
            print(f"⚠️  逻辑校验过程出错: {e}，返回原始大纲数据")
            return outline_data
