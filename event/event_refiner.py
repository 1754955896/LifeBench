# -*- coding: utf-8 -*-
import json
import copy
from datetime import datetime, timedelta
import holidays
from typing import List, Dict, Optional
from event.templates import template_event_update, template_biweekly_event_schedule_analysis
from event.template2 import template_daily_event_refine, template_daily_diversity_optimization, template_format_validation, template_monthly_health_report
from utils.llm_call import llm_call
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from utils.llm_call import llm_call


class EventRefiner:
    """
    事件数据处理类，主要功能是接受一年事件数据和画像数据，经多线程处理后返回优化调整后的一年数据
    """
    
    def __init__(self, persona: Dict, events: List[Dict], context: str = ""):
        """
        初始化事件精炼器
        
        参数:
            persona: 人物画像数据
            events: 事件列表
            context: 用于LLM调用的上下文信息
        """
        self.persona = persona
        self.events = events
        self.context = context
        self.bottom_events: Optional[List[Dict]] = None
        # 初始化时更新底层事件
        self.update_bottom_events()
    
    def get_date_string(self, date_str: str, country: str = "CN") -> str:
        """
        生成包含日期、周几和节日（如有）的字符串
        
        参数:
            date_str: 公历日期字符串，格式"YYYY-MM-DD"
            country: 国家/地区代码（默认中国"CN"）
        
        返回:
            str: 格式化字符串，例："2025-10-01，星期三，国庆节" 或 "2025-05-15，星期四"
        """
        try:
            # 解析日期
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")

            # 获取星期几
            weekday_map = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            weekday = weekday_map[date_obj.weekday()]

            # 获取节日（多个节日用顿号分隔）
            country_holidays = holidays.CountryHoliday(country)
            holidays_list = []
            if date_obj in country_holidays:
                raw_holidays = country_holidays.get(date_obj)
                holidays_list = raw_holidays if isinstance(raw_holidays, list) else [raw_holidays]
            festival_str = "，".join(holidays_list) if holidays_list else ""

            # 拼接结果（无节日则省略最后一个逗号）
            parts = [date_str, weekday]
            if festival_str:
                parts.append(festival_str)
            return "，".join(parts)

        except ValueError:
            return "日期格式错误，请使用'YYYY-MM-DD'格式"
    

    
    def extract_start_date(self, date_str: str) -> str:
        """
        提取起始日期
        
        参数:
            date_str: 日期字符串，格式可能为"YYYY-MM-DD"、"YYYY-MM-DD HH:MM:SS"或"YYYY-MM-DD 至 YYYY-MM-DD"
            
        返回:
            str: 起始日期，格式为"YYYY-MM-DD"
        """
        if " " in date_str:
            return date_str.split()[0]
        elif "至" in date_str:
            return date_str.split("至")[0].strip()
        return date_str

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

    def filter_by_date(self, events: List[Dict], target_date: str) -> List[Dict]:
        """
        按日期筛选事件
        
        参数:
            events: 事件列表
            target_date: 目标日期，格式为"YYYY-MM-DD"
            
        返回:
            List[Dict]: 筛选出的事件列表
        """
        all_events = self._get_bottom_level_events(events)
        return [e for e in all_events if self.extract_start_date(e["date"]) == [target_date]]

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
            if str(event["event_id"]) == event_id or event["event_id"] == event_id:
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
    
    def llm_call_s(self, prompt: str, record: int = 0) -> str:
        """
        调用大模型
        
        参数:
            prompt: 提示词
            record: 是否记录调用（默认0：不记录）
        
        返回:
            str: 大模型返回结果
        """
        from utils.llm_call import llm_call
        res = llm_call(prompt, self.context, record=record)
        return res
    
    
    def get_date_string(self, date_str: str) -> str:
        """
        生成带星期和节日的日期字符串
        
        参数:
            date_str: 日期字符串，格式为"YYYY-MM-DD"
            
        返回:
            str: 带星期和节日的日期字符串
        """
        # 解析日期
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

        # 获取星期几
        weekday_map = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekday_map[date_obj.weekday()]

        # 获取节日（多个节日用顿号分隔）
        country_holidays = holidays.CountryHoliday("CN")
        holidays_list = []
        if date_obj in country_holidays:
            raw_holidays = country_holidays.get(date_obj)
            holidays_list = raw_holidays if isinstance(raw_holidays, list) else [raw_holidays]
        festival_str = "，".join(holidays_list) if holidays_list else ""

        # 拼接结果（无节日则省略最后一个逗号）
        parts = [date_obj.strftime("%Y年%m月%d日"), weekday]
        if festival_str:
            parts.append(festival_str)
        return "".join(parts)

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

    def llm_call_sr(self, prompt: str, record: int = 0) -> str:
        """
        调用大模型
        
        参数:
            prompt: 提示词
            record: 是否记录调用（默认0：不记录）
        
        返回:
            str: 大模型返回结果
        """
        from utils.llm_call import llm_call_reason
        res = llm_call_reason(prompt, self.context, record=record)
        return res

    def date_range_event_refine(self, events: List[Dict], start_date: str, end_date: str, context: str = "") -> Dict[str, any]:
        """
        基于指定时间范围批量调整事件的内容、时间、地点，使其发生更合理
        
        参数:
            events: 事件列表
            start_date: 时间范围的开始日期（格式：YYYY-MM-DD）
            end_date: 时间范围的结束日期（格式：YYYY-MM-DD）
            context: 用于LLM调用的上下文信息（可选）
            
        返回:
            Dict[str, any]: 包含事件更新操作列表和每日生活数据的字典
                - event_updates: List[Dict] 事件更新操作列表
                - dailylife: List[Dict] 每日生活数据列表
        """
        # 如果提供了新的上下文，则更新
        if context:
            self.context = context
        
        try:
            # 生成两周内的所有日期
            def get_all_dates_in_range(start_date: str, end_date: str) -> List[str]:
                """获取指定日期范围内的所有日期"""
                dates = []
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()
                delta = timedelta(days=1)
                current = start
                while current <= end:
                    dates.append(current.strftime("%Y-%m-%d"))
                    current += delta
                return dates
            
            # 获取两周内的所有日期
            all_dates = get_all_dates_in_range(start_date, end_date)
            
            # 获取两周内的所有底层事件
            event_sequence = []
            for date in all_dates:
                date_events = self.filter_by_date(events, date)
                #print(len(date_events))
                event_sequence.extend(date_events)
            
            # 如果没有事件，直接返回
            if not event_sequence:
                print(f"在{start_date}至{end_date}范围内没有找到事件")
                return {"event_updates": [], "dailylife": []}
            
            # 获取事件背景并去重
            event_background_set = set()
            event_background = []
            
            for event in event_sequence:
                event_id = event["event_id"]
                # 获取父事件ID（处理子事件的情况）
                parent_id = event_id.rsplit('-')[0]
                #print(parent_id)
                if parent_id not in event_background_set:
                    # 获取完整事件作为背景
                    background_event = self.get_event_by_id(events, parent_id)
                    event_background.append(background_event)
                    event_background_set.add(parent_id)
            
            # 构建两周日期范围描述
            date_range_desc = self.get_holidays_and_weekends_in_range(start_date, end_date)
            
            # 使用模板调用LLM进行批量分析
            prompt = template_biweekly_event_schedule_analysis.format(
                events=event_sequence,
                event_background=event_background,
                date_range=date_range_desc,
                persona=self.persona
            )
            print(prompt)
            res = self.llm_call_sr(prompt, 0)
            print("时间范围事件批量分析思考-----------------------------------------------------------------------")
            print(res)

            prompt = template_event_update.format(
                result=res,
                date_range=date_range_desc
            )
            from utils.llm_call import llm_call_reason_j
            res = llm_call_reason_j(prompt)
            print("时间范围事件批量调整-----------------------------------------------------------------------")
            print(res)
            # 提取并解析JSON响应
            start_index = res.find('{')
            end_index = res.rfind('}')
            if start_index != -1 and end_index != -1 and start_index < end_index:
                json_str = res[start_index:end_index+1]
                data = json.loads(json_str)
            else:
                # 尝试直接解析整个响应
                data = json.loads(res)
            
            # 提取事件更新操作和每日生活数据
            event_updates = data.get('event_update', [])
            dailylife = data.get('dailylife', [])
            
            return {"event_updates": event_updates, "dailylife": dailylife}
                
        except Exception as e:
            print(f"时间范围事件批量调整过程中出错: {type(e).__name__}: {e}")
            # 发生错误时，返回空列表
            return {"event_updates": [], "dailylife": []}

    def find_and_update_event(self, events: List[Dict], event_id: str, new_date: str) -> bool:
        """
        递归查找事件并更新日期
        
        参数:
            events: 事件列表
            event_id: 要更新的事件ID
            new_date: 新的日期
            
        返回:
            bool: 是否找到并更新了事件
        """
        for event in events:
            if event['event_id'] == event_id:
                # 更新事件日期
                event['date'] = [new_date]
                print(f"已更新事件 {event_id} 的日期为 {new_date}")
                return True
            
            # 递归查找子事件
            if 'subevent' in event and event['subevent']:
                if self.find_and_update_event(event['subevent'], event_id, new_date):
                    return True
        
        return False
    
    def apply_event_updates(self, events: List[Dict], updates: List[Dict]) -> List[Dict]:
        """
        应用事件更新操作到事件列表
        
        参数:
            events: 原始事件列表
            updates: 事件更新操作列表
            
        返回:
            List[Dict]: 更新后的事件列表
        """
        updated_count = 0
        
        for update in updates:
            event_id = update.get('event_id')
            new_date = update.get('new_date')
            
            if not event_id or not new_date:
                print(f"更新操作缺少必要字段: {update}")
                continue
            
            # 查找并更新事件
            if self.find_and_update_event(events, event_id, new_date):
                updated_count += 1
            else:
                print(f"未找到事件 {event_id}")
        
        print(f"共更新了 {updated_count} 个事件")
        return events
    
    def save_dailylife_to_json(self, dailylife_data: List[Dict], output_path: str = "output/daily_state.json"):
        """
        将每日生活数据保存到JSON文件
        
        参数:
            dailylife_data: 每日生活数据列表
            output_path: 输出文件路径，默认保存到output文件夹下的daily_state.json
        """
        import os
        import json
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 按日期排序
        dailylife_data.sort(key=lambda x: x.get('date', ''))
        
        # 保存到JSON文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dailylife_data, f, ensure_ascii=False, indent=2)
        
        print(f"每日生活数据已保存到: {output_path}")

    def daily_event_refine(self, events: List[Dict], start_date: str, end_date: str, persona: Dict, split_date: str, health_result: Dict, life_result: Dict, month_transition_analysis: Dict = None, context: str = "") -> Dict[
        str, any]:
        """
        基于指定时间范围批量调整事件的内容、时间、地点，使其发生更合理，并加入健康分析结果

        参数:
            events: 事件列表
            start_date: 时间范围的开始日期（格式：YYYY-MM-DD）
            end_date: 时间范围的结束日期（格式：YYYY-MM-DD）
            month_data: 包含一个月事件数据的字典
            persona: 人物画像信息
            split_date: 分割日期，用于生成两组数据（格式：YYYY-MM-DD）
            health_result: 健康分析结果字符串，包含初始状态、中间状态和最终状态
            life_result: 生活分析结果
            month_transition_analysis: 月变化分析结果，包含前一日status和final_day_status等信息
            context: 用于LLM调用的上下文信息（可选）

        返回:
            Dict[str, any]: 包含事件更新操作列表和每日生活数据的字典
                - event_updates: List[Dict] 事件更新操作列表
                - dailylife: List[Dict] 每日生活数据列表
        """
        # 如果提供了新的上下文，则更新
        if context:
            self.context = context

        try:
            # 生成指定日期范围内的所有日期
            def get_all_dates_in_range(start_date: str, end_date: str) -> List[str]:
                """获取指定日期范围内的所有日期"""
                dates = []
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()
                delta = timedelta(days=1)
                current = start
                while current <= end:
                    dates.append(current.strftime("%Y-%m-%d"))
                    current += delta
                return dates

            health_result_dict = health_result
            # 解析健康分析结果字符串
            health_initial_state = health_result_dict["initial_state"]
            health_mid_state = health_result_dict["mid_month_state"]
            health_end_state = health_result_dict["end_of_month_state"]
            #print('here')
            # 导入copy模块用于深拷贝
            import copy
            
            # 准备用于LLM的通用提示词参数
            persona_str = json.dumps(persona, ensure_ascii=False, indent=2)

            # 处理月变化分析结果
            previous_day_status = ""
            final_day_status = {}
            change_persona = ""  # 初始化change_persona变量，防止在内部函数中引用未定义的变量
            
            if month_transition_analysis:
                # 提取前一日status和final_day_status
                previous_day_status = month_transition_analysis.get("previous_day_status", "")
                final_day_status = month_transition_analysis.get("final_day_status", {})
                change_persona = month_transition_analysis.get("profile_changes", "")
            # 辅助函数：处理单个日期范围的逻辑
            def process_date_range(range_start: str, range_end: str, health_start_state: Dict, health_end_state: Dict, life_result: Dict):
                """处理单个日期范围的数据生成"""
                print(f"处理日期范围: {range_start} 至 {range_end}")
                
                # 获取该日期范围内的所有日期
                range_dates = get_all_dates_in_range(range_start, range_end)
                
                # 获取该日期范围内的所有底层事件
                event_sequence = []
                for date in range_dates:
                    date_events = self.filter_by_date(events, date)
                    event_sequence.extend(date_events)

                # 如果没有事件，直接返回空结果
                if not event_sequence:
                    print(f"在{range_start}至{range_end}范围内没有找到事件")
                    return []

                # 先调用date_range_event_refine进行事件调整
                date_range_result = self.date_range_event_refine(events, range_start, range_end, context)
                event_updates = date_range_result.get("event_updates", [])
                
                # 应用事件更新
                updated_events = self.apply_event_updates(copy.deepcopy(events), event_updates)

                # 构建日期范围描述
                date_range_desc = self.get_holidays_and_weekends_in_range(range_start, range_end)

                # 准备用于LLM的健康状态参数
                health_start_state_str = json.dumps(health_start_state, ensure_ascii=False, indent=2)
                health_end_state_str = json.dumps(health_end_state, ensure_ascii=False, indent=2)
                life_analysis_str = json.dumps(life_result["summary"], ensure_ascii=False, indent=2)
                
                # 准备月变化分析参数
                previous_day_status_str = json.dumps(previous_day_status, ensure_ascii=False, indent=2) if previous_day_status else "无前一日状态信息"
                final_day_status_str = json.dumps(final_day_status, ensure_ascii=False, indent=2) if final_day_status else "无最终日状态信息"
                change_persona_str = json.dumps(change_persona, ensure_ascii=False, indent=2)
                
                # 为daily_life数据添加事件字段
                daily_life_data = []
                for date in range_dates:
                    date_events = self.filter_by_date(updated_events, date)
                    event_descriptions = []
                    for event in date_events:
                        event_descriptions.append(event.get("description", ""))
                    
                    daily_life_entry = {
                        "date": date,
                        "events": event_descriptions  # 添加事件描述的数组
                    }
                    daily_life_data.append(daily_life_entry)

                # 精简persona数据，只保留relation中的name、relation、relation_description字段
                simplified_persona = {}
                for key, value in persona.items():
                    if key == "relation" and isinstance(value, list):
                        # 处理嵌套的社交圈数组结构，保留每个元素的name、relation、relation_description字段
                        simplified_persona[key] = []
                        for outer_item in value:  # 外层数组的每个元素也是一个数组
                            if isinstance(outer_item, list):
                                simplified_outer_item = []
                                for inner_item in outer_item:  # 内层数组中的每个人
                                    simplified_inner_item = {
                                        "name": inner_item.get("name", ""),
                                        "relation": inner_item.get("relation", ""),
                                        "relation_description": inner_item.get("relation_description", "")
                                    }
                                    simplified_outer_item.append(simplified_inner_item)
                                simplified_persona[key].append(simplified_outer_item)
                            else:  # 如果不是嵌套数组，按照原来的方式处理
                                simplified_item = {
                                    "name": outer_item.get("name", ""),
                                    "relation": outer_item.get("relation", ""),
                                    "relation_description": outer_item.get("relation_description", "")
                                }
                                simplified_persona[key].append(simplified_item)
                    else:
                        # 其他字段保持不变
                        simplified_persona[key] = value
                
                simplified_persona_str = json.dumps(simplified_persona, ensure_ascii=False, indent=2)
                # with open("daily_life_data.json", "w") as f:
                #     json.dump(daily_life_data, f, ensure_ascii=False, indent=2)
                # 使用模板调用LLM进行批量分析，使用daily_life_data作为event_data
                prompt = template_daily_event_refine.format(
                    persona=simplified_persona_str,
                    event_data=daily_life_data,  # 使用daily_life_data替代原来的event_sequence
                    date_range_description=date_range_desc,
                    previous_day_status=previous_day_status_str,
                    final_day_status=final_day_status_str,
                    life_analysis_str=life_analysis_str
                )
                #print(f"发送给LLM的prompt长度: {len(prompt)}")
                res = self.llm_call_sr(prompt, 0)
                print(f"日期范围{range_start}至{range_end}的事件批量分析思考-----------------------------------------------------------------------")
                print(f"LLM响应长度: {len(res)}",print(res[:100]))

                # 使用多样性优化模板对每日数据进行优化
                print(f"执行日期范围{range_start}至{range_end}的每日数据多样性优化...")

                optimization_prompt = template_daily_diversity_optimization.format(
                    persona=simplified_persona_str,
                    date_range_description=date_range_desc,
                    health_initial_state=health_start_state_str,
                    health_end_state=health_end_state_str,
                    daily_events=res
                )
                from utils.llm_call import llm_call_reason_j
                optimization_res = llm_call_reason_j(optimization_prompt)
                print(f"日期范围{range_start}至{range_end}的每日数据多样性优化-----------------------------------------------------------------------")
                #print(res)
                print(f"优化后响应长度: {len(optimization_res)}")
                
                
                
                # 添加格式验证步骤
                # 先尝试将optimization_res解析为JSON数组，以便分成两部分
                print(f"开始解析optimization_res...")
                optimization_data = []
                try:
                    # 找到JSON数组的边界
                    opt_start_index = optimization_res.find('[')
                    opt_end_index = optimization_res.rfind(']')
                    if opt_start_index != -1 and opt_end_index != -1 and opt_start_index < opt_end_index:
                        opt_json_str = optimization_res[opt_start_index:opt_end_index+1]
                        optimization_data = json.loads(opt_json_str)
                        print(f"成功将optimization_res解析为JSON数组，包含{len(optimization_data)}条记录")
                    else:
                        # 如果没有找到数组边界，尝试直接解析整个响应
                        optimization_data = json.loads(optimization_res)
                        print(f"直接解析optimization_res成功，包含{len(optimization_data)}条记录")
                except json.JSONDecodeError as e:
                    print(f"解析optimization_res失败: {str(e)}")
                    # 如果解析失败，尝试清理字符串并再次解析
                    try:
                        cleaned_optimization = self.clean_json_string(optimization_res)
                        optimization_data = json.loads(cleaned_optimization)
                        print(f"清理后解析optimization_res成功，包含{len(optimization_data)}条记录")
                    except json.JSONDecodeError as e2:
                        print(f"清理后解析optimization_res仍然失败: {str(e2)}")
                        # 再次清理，更严格地移除控制字符
                        try:
                            # 使用正则表达式移除所有控制字符
                            import re
                            stricter_cleaned = re.sub(r'[\x00-\x1f\x7f]', '', cleaned_optimization)
                            optimization_data = json.loads(stricter_cleaned)
                            print(f"严格清理后解析optimization_res成功，包含{len(optimization_data)}条记录")
                        except Exception as e3:
                            print(f"严格清理后解析optimization_res仍然失败: {str(e3)}")
                            # 如果所有解析尝试都失败，记录错误并继续执行降级逻辑
                            print(f"所有解析尝试均失败，将使用降级逻辑处理")
                except Exception as e:
                    print(f"处理optimization_res时发生错误: {str(e)}")
                    print(f"将使用降级逻辑处理")
                
                # 如果直接解析成功且数据不为空，直接使用解析后的结果
                if optimization_data:
                    optimized_dailylife = optimization_data
                    print(f"直接使用解析成功的optimization_res，包含{len(optimized_dailylife)}条记录")
                else:
                    # 如果解析失败或数据为空，使用日期范围控制两次输出
                    print(f"optimization_data为空，需要进行格式验证")
                    
                    # 将日期范围分成两部分：第一部分为range_start加7天，剩下的为第二部分
                    first_end_date = datetime.strptime(range_start, "%Y-%m-%d") + timedelta(days=7)
                    first_end_date_str = first_end_date.strftime("%Y-%m-%d")
                    
                    # 分割日期列表
                    first_half_dates = []
                    second_half_dates = []
                    
                    for date in range_dates:
                        if date <= first_end_date_str:
                            first_half_dates.append(date)
                        else:
                            second_half_dates.append(date)
                    
                    # 生成第一部分的日期范围描述
                    if first_half_dates:
                        first_date_range = f"{first_half_dates[0]} 至 {first_half_dates[-1]}"
                    else:
                        first_date_range = ""
                    
                    # 生成第二部分的日期范围描述
                    if second_half_dates:
                        second_date_range = f"{second_half_dates[0]} 至 {second_half_dates[-1]}"
                    else:
                        second_date_range = ""
                    
                    print(f"将日期范围分为两部分: 第一部分{first_date_range}，第二部分{second_date_range}")
                    
                    # 分别对两部分进行格式验证
                    validated_first_half = []
                    validated_second_half = []
                    
                    if first_date_range:
                        # 调用格式验证模板，只验证第一部分日期范围的数据
                        first_validation_prompt = template_format_validation.format(
                            json_string=optimization_res,
                            date_range=first_date_range
                        )
                        first_validated_res = llm_call_reason_j(first_validation_prompt, 0)
                        print(f"第一部分验证后响应长度: {len(first_validated_res)}")
                        
                        # 解析第一部分验证结果
                        try:
                            first_start = first_validated_res.find('[')
                            first_end = first_validated_res.rfind(']')
                            if first_start != -1 and first_end != -1 and first_start < first_end:
                                first_valid_json = first_validated_res[first_start:first_end+1]
                                validated_first_half = json.loads(first_valid_json)
                                print(f"成功解析第一部分验证结果，包含{len(validated_first_half)}条记录")
                            else:
                                # 尝试清理后解析
                                cleaned_first = self.clean_json_string(first_validated_res)
                                validated_first_half = json.loads(cleaned_first)
                                print(f"清理后成功解析第一部分，包含{len(validated_first_half)}条记录")
                        except json.JSONDecodeError as e:
                            print(f"解析第一部分验证结果失败: {str(e)}")
                            validated_first_half = []
                    
                    if second_date_range:
                        # 调用格式验证模板，只验证第二部分日期范围的数据
                        second_validation_prompt = template_format_validation.format(
                            json_string=optimization_res,
                            date_range=second_date_range
                        )
                        second_validated_res = llm_call_reason_j(second_validation_prompt, 0)
                        print(f"第二部分验证后响应长度: {len(second_validated_res)}")
                        
                        # 解析第二部分验证结果
                        try:
                            second_start = second_validated_res.find('[')
                            second_end = second_validated_res.rfind(']')
                            if second_start != -1 and second_end != -1 and second_start < second_end:
                                second_valid_json = second_validated_res[second_start:second_end+1]
                                validated_second_half = json.loads(second_valid_json)
                                print(f"成功解析第二部分验证结果，包含{len(validated_second_half)}条记录")
                            else:
                                # 尝试清理后解析
                                cleaned_second = self.clean_json_string(second_validated_res)
                                validated_second_half = json.loads(cleaned_second)
                                print(f"清理后成功解析第二部分，包含{len(validated_second_half)}条记录")
                        except json.JSONDecodeError as e:
                            print(f"解析第二部分验证结果失败: {str(e)}")
                            validated_second_half = []
                    
                    # 合并两部分结果
                    optimized_dailylife = validated_first_half + validated_second_half
                    print(f"合并两部分后得到{len(optimized_dailylife)}条记录")
                return optimized_dailylife

            # 导入并行处理模块
            from concurrent.futures import ThreadPoolExecutor

            # 计算第二阶段的开始日期（split_date + 1）
            split_date_obj = datetime.strptime(split_date, "%Y-%m-%d")
            second_stage_start = (split_date_obj + timedelta(days=1)).strftime("%Y-%m-%d")

            # 使用并行处理生成两组数据
            with ThreadPoolExecutor(max_workers=2) as executor:
                # 提交两个任务：第一组（start_date到split_date）使用初始状态和中间状态；第二组（split_date+1到end_date）使用中间状态和最终状态
                future1 = executor.submit(process_date_range, start_date, split_date, health_initial_state, health_mid_state, life_result)
                future2 = executor.submit(process_date_range, second_stage_start, end_date, health_mid_state, health_end_state, life_result)

                # 获取两个任务的结果
                result1 = future1.result()
                result2 = future2.result()

            # 合并两组结果
            combined = result1 + result2

            # 返回合并后的结果，包含月份衔接分析
            return combined

        except json.JSONDecodeError as e:
            print(f"JSON解码错误: {e}")
            print(f"错误位置: 行 {e.lineno} 列 {e.colno} (字符 {e.pos})")
            import traceback
            traceback.print_exc()
            raise e
        except Exception as e:
            print(f"生成每日事件/状态列表时出错: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise e

    def clean_json_string(self, json_str: str) -> str:
        """
        清理JSON字符串，移除多余的引号转义和提取JSON数组部分，特别处理控制字符
        """
        import re
        
        # 首先移除所有控制字符（ASCII 0-31和127）
        # 这些字符在JSON中是非法的，包括制表符、换行符和回车符
        cleaned_str = ''.join(char for char in json_str if ord(char) >= 32 and ord(char) != 127)
        
        # 移除最外层的引号和转义字符
        if len(cleaned_str) > 1 and cleaned_str.startswith('"') and cleaned_str.endswith('"'):
            # 去掉首尾引号并处理转义字符
            cleaned_str = cleaned_str[1:-1].replace('\"', '"')
        
        # 尝试找到JSON数组的开始和结束
        start_idx = cleaned_str.find('[')
        end_idx = cleaned_str.rfind(']')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            # 提取JSON数组部分
            json_array_str = cleaned_str[start_idx:end_idx+1]
            return json_array_str
        else:
            # 如果找不到数组，尝试作为普通对象处理
            start_idx = cleaned_str.find('{')
            end_idx = cleaned_str.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_obj_str = cleaned_str[start_idx:end_idx+1]
                return json_obj_str
        
        return cleaned_str

    def health_analysis(self, month_data: Dict, persona: Dict, initial_state: str = ""):
        """
        根据给定时间段的事件输出，分析人物的健康相关信息，并进行多样性分析，同时将新增健康事件插入到每月事件数据中
        
        参数:
            month_data: 包含时间段内每月事件的字典
            persona: 人物画像信息
            initial_state: 初始健康状态（可选），如果提供则使用，否则生成新的初始状态
            
        返回:
            包含初始状态、中间状态和最终状态的字符串
        """
        from event.template2 import template_impact_events_analysis, template_health_diversity_analysis, template_initial_health_state
        import json
        from datetime import datetime


        # 准备输入数据
        persona_str = json.dumps(persona, ensure_ascii=False, indent=2)

        # 1. 如果提供了初始状态则使用，否则生成初始健康状态数据
        if initial_state:
            initial_health_state = initial_state
            #print("使用提供的初始健康状态: ", initial_health_state)
        else:
            initial_prompt = template_initial_health_state.format(
                        persona=persona_str
                )

            initial_health_state = self.llm_call_sr(initial_prompt, record=1)
            #print("初始健康状态生成结果: ", initial_health_state)

        # 2. 再进行影响事件分析
        impact_prompt = template_impact_events_analysis.format(
                    persona=persona_str,
                    initial_health_state=initial_health_state,
                    daily_data=month_data
                )

        health_response = self.llm_call_sr(impact_prompt, record=1)
        #print("健康分析结果: ", health_response)
        
        # 解析响应以提取中间状态和最终状态
        health_response_dict = {}
        try:
            # 先匹配第一个{和最后一个}，确保只解析有效的JSON部分
            start_index = health_response.find('{')
            end_index = health_response.rfind('}')
            if start_index != -1 and end_index != -1 and start_index < end_index:
                json_str = health_response[start_index:end_index+1]
                health_response_dict = json.loads(json_str)
            else:
                # 如果没有找到有效的JSON结构，尝试直接解析整个响应
                health_response_dict = json.loads(health_response)
        except json.JSONDecodeError as e:
            # JSON解析失败时的处理
            print(f"健康分析JSON解析失败: {e}")
            #print(f"原始响应: {health_response}")
        except Exception as e:
            # 其他可能的异常处理
            print(f"健康分析处理异常: {e}")
            #print(f"原始响应: {health_response}")
        
        # 即使解析失败，也要确保返回合理的默认值
        mid_month_state = health_response_dict.get('mid_month_state', "月度中间信息获取失败，需基于已有信息合理推断")
        end_of_month_state = health_response_dict.get('end_of_month_state', "月度结束信息获取失败，需基于已有信息合理推断")
        
        # 返回包含所有状态的结果
        return {
            "initial_state": initial_health_state,
            "mid_month_state": mid_month_state,
            "end_of_month_state": end_of_month_state,
        }

    def life_analysis(self, month_data: Dict, persona: Dict, initial_state: str = None):
        """
        根据给定时间段的事件输出，分析生活相关信息并提供优化建议
        
        参数:
            month_data: 包含时间段内每月事件的字典
            persona: 人物画像信息
            initial_state: 初始状态字符串，如果为空则自动生成
            
        返回:
            包含总结和最终状态的字典
        """
        from event.templates import template_life_analysis, template_life_initial_state
        from event.template2 import template_life_optimization, template_life_analysis_summary
        import json
        from datetime import datetime
        
        # 准备输入数据
        persona_str = json.dumps(persona, ensure_ascii=False, indent=2)
            
        # 获取初始状态
        if initial_state is None:
            # 生成生活初始状态
            initial_state_prompt = template_life_initial_state.format(
                    persona=persona_str
                )
            
            initial_state_response = self.llm_call_sr(initial_state_prompt, record=1)
            #print("生成的生活初始状态: ", initial_state_response)
        else:
            # 使用提供的初始状态
            initial_state_response = initial_state
            #print("使用提供的生活初始状态: ", initial_state_response)
            
        # 第二步：使用初始状态和事件数据生成完整的生活分析
        life_prompt = template_life_analysis.format(
                persona=persona_str,
                initial_state=initial_state_response,
                daily_data=month_data
            )
            
        life_response = self.llm_call_sr(life_prompt, record=1)
        #print("生活分析结果: ", life_response)
        
        # 提取并解析JSON内容
        life_response_json = None
        try:
            # 找到第一个{和最后一个}的位置
            start_idx = life_response.find('{')
            end_idx = life_response.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                # 提取JSON字符串
                json_str = life_response[start_idx:end_idx+1]
                # 解析JSON
                life_response_json = json.loads(json_str)
            else:
                print("未找到有效的JSON格式内容")
        except Exception as e:
            print(f"解析JSON时出错: {e}")
        
        # 3. 生成生活总结报告
        month_data_str = json.dumps(month_data, ensure_ascii=False, indent=2)
        summary_prompt = template_life_analysis_summary.format(
            persona=persona_str,
            month_data=month_data_str,
            life_analysis=life_response_json or life_response
        )
        
        life_summary = self.llm_call_sr(summary_prompt, record=1)
        print("生活总结报告生成完成")
        #print("生活总结报告: ", life_summary)
        
        # 提取最终状态
        final_state = None
        if life_response_json:
            # 从分析结果中提取最终状态（根据模板结构可能需要调整路径）
            final_state = life_response_json.get('final_state', {})
            # 如果没有final_state字段，尝试从其他可能的字段获取
            if not final_state:
                # 检查是否有状态相关的字段
                for key, value in life_response_json.items():
                    if isinstance(value, dict) and ('state' in key.lower() or 'status' in key.lower()):
                        final_state = value
                        break
            # 如果仍然没有找到，使用整个分析结果作为最终状态
            if not final_state:
                final_state = life_response_json
        else:
            # 如果解析失败，使用初始状态作为最终状态
            final_state = initial_state_response
        
        # 返回总结和最终状态
        return {
            "summary": life_summary,
            "final_state": final_state
        }
        
    def month_transition_analysis(self, month_data: Dict, persona: Dict, previous_analysis: Dict = None):
        """
        分析月度事件的连贯性和延续性，总结下个月数据生成需要和上个月连贯的地方
        
        参数:
            month_data: 包含月度事件数据的字典
            persona: 人物画像信息
            previous_analysis: 以往的月份衔接分析结果（可选），用于整合历史变化信息
            
        返回:
            包含三个关键点的字典：
            1. final_day_status: 该月份最后一天的最终状态（位置和活动）
            2. continuing_events: 需要延续到下个月的事件列表
            3. profile_changes: 整合后的画像变化信息（包含本月变化和历史变化的延续）
        """
        from event.template2 import template_month_transition_analysis
        import json
        from datetime import datetime
        
        try:
            print("执行月份衔接分析...")
            
            # 准备输入数据
            persona_str = json.dumps(persona, ensure_ascii=False, indent=2)
            month_data_str = json.dumps(month_data, ensure_ascii=False, indent=2)
            
            # 处理以往分析结果
            previous_analysis_str = json.dumps(previous_analysis, ensure_ascii=False, indent=2) if previous_analysis else "{}"
            
            # 使用模板调用LLM进行月份衔接分析
            prompt = template_month_transition_analysis.format(
                persona=persona_str,
                month_data=month_data_str,
                previous_analysis=previous_analysis_str
            )
            
            transition_response = self.llm_call_sr(prompt)
            #print("月份衔接分析结果: ", transition_response)
            
            # 解析响应
            try:
                # 找到第一个{和最后一个}的位置
                start_idx = transition_response.find('{')
                end_idx = transition_response.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    # 提取JSON字符串
                    json_str = transition_response[start_idx:end_idx+1]
                    # 解析JSON
                    transition_result = json.loads(json_str)

                else:
                    print("未找到有效的JSON格式内容")
                    transition_result = {}
            except Exception as e:
                print(f"解析月份衔接分析结果JSON时出错: {e}")
                transition_result = {}
            
            return transition_result
            
        except Exception as e:
            print(f"执行月份衔接分析时出错: {e}")
            # 获取上上月的profile_changes信息（如果有）
            previous_profile_changes = previous_analysis.get("profile_changes", {"changes": [], "month_summary": ""}) if previous_analysis else {"changes": [], "month_summary": ""}
            
            return {
                "final_day_status": {"location": "上月信息获取失败，需自行推理", "activity": "上月信息获取失败，需自行推理"},
                "continuing_events": "上月信息获取失败，需自行推理",
                "profile_changes": previous_profile_changes,
                "previous_day_status": "上月信息获取失败，需自行推理"
            }

    def annual_event_refine(self, events: List[Dict], start_date: str, end_date: str, context: str = "", max_workers: int = 5, output_path: str = "output/daily_state.json") -> List[Dict]:
        """
        处理整个年度的事件调整，内部使用多线程并统一合并结果
        
        参数:
            events: 事件列表
            start_date: 开始日期（格式：YYYY-MM-DD）
            end_date: 结束日期（格式：YYYY-MM-DD）
            context: 用于LLM调用的上下文信息（可选）
            max_workers: 最大线程数
            
        返回:
            List[Dict]: 调整后的事件列表
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import copy
        
        # 如果提供了新的上下文，则更新
        if context:
            self.context = context
        
        # 生成所有两周区间
        def get_biweekly_intervals(start_date: str, end_date: str) -> List[tuple]:
            """将日期范围划分为两周（14天）的区间"""
            intervals = []
            current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            while current_date <= end_date_obj:
                interval_end = current_date + timedelta(days=13)
                if interval_end > end_date_obj:
                    interval_end = end_date_obj
                intervals.append((current_date.strftime("%Y-%m-%d"), interval_end.strftime("%Y-%m-%d")))
                current_date += timedelta(days=14)
            
            return intervals
        
        # 获取所有两周区间
        biweekly_intervals = get_biweekly_intervals(start_date, end_date)
        print(f"共划分为{len(biweekly_intervals)}个两周区间")
        
        # 定义每个线程要执行的任务函数
        def process_interval(interval_idx, interval_start, interval_end, events_copy, context):
            """处理单个区间的事件调整"""
            try:
                print(f"区间 {interval_idx}/{len(biweekly_intervals)}: 调整{interval_start}至{interval_end}的事件...")
                results = self.date_range_event_refine(
                        events_copy, 
                        interval_start, 
                        interval_end, 
                        context
                    )
                print(f"    区间 {interval_idx}/{len(biweekly_intervals)} 调整完成")
                return interval_idx, results["event_updates"], results["dailylife"], None
            except Exception as e:
                error_msg = f"处理区间 {interval_idx} ({interval_start}至{interval_end}) 时出错：{e}"
                print(error_msg)
                return interval_idx, [], [], error_msg

        try:
            # 提交所有任务到线程池
            results = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_interval = {}
                for idx, (start, end) in enumerate(biweekly_intervals):
                    # 为每个线程创建独立的事件数据副本，确保线程安全
                    thread_events_copy = copy.deepcopy(events)
                    future = executor.submit(process_interval, idx+1, start, end, thread_events_copy, self.context)
                    future_to_interval[future] = (idx+1, start, end)

                # 收集所有结果
                for future in as_completed(future_to_interval):
                    interval_idx, interval_event_updates, interval_dailylife, error = future.result()
                    if error:
                        print(error)
                    results.append((interval_idx, interval_event_updates, interval_dailylife))

            # 按区间顺序合并结果
            results.sort(key=lambda x: x[0])
            merged_updates = []
            all_dailylife = []
            for _, event_updates, dailylife in results:
                merged_updates.extend(event_updates)
                all_dailylife.extend(dailylife)
            
            # 应用更新操作到事件列表
            updated_events = self.apply_event_updates(events, merged_updates)
            
            # 保存每日生活数据到JSON文件
            if all_dailylife:
                self.save_dailylife_to_json(all_dailylife, output_path)

            return updated_events
        except Exception as e:
            print(f"年度事件调整过程中出错：{e}")
            return events

    @staticmethod
    def monthly_health_report_generation(persona: Dict, 
                                         month_num: int, 
                                         event_data_path: str, 
                                         health_analysis_file: str = "output/new/all_months_analysis_20260113134815_updated.json",
                                         context: str = "") -> str:
        """
        生成月度运动健康报告
        
        参数:
            persona: 不带联系人的画像数据
            month_num: 月份编号 (1-12)
            event_data_path: 事件数据文件路径
            health_analysis_file: 健康分析数据文件路径 (支持final_timeline.json格式)
            context: 用于LLM调用的上下文信息
            
        返回:
            str: 月度运动健康报告的JSON字符串
        """
        import json
        from datetime import datetime
        from utils.llm_call import llm_call_reason
        
        # 读取事件数据文件
        try:
            with open(event_data_path, 'r', encoding='utf-8') as f:
                all_event_data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"未找到事件数据文件: {event_data_path}")
        except json.JSONDecodeError:
            raise ValueError(f"事件数据文件格式错误: {event_data_path}")
        
        # 获取本月事件数据
        month_key = f"2025-{month_num:02d}"
        if month_key not in all_event_data:
            raise ValueError(f"事件数据中未找到 {month_key} 月份的数据")
        
        month_event_data = all_event_data[month_key]
        
        # 初始化健康状态数据
        health_initial_state = {}
        health_end_state = {}
        
        # 读取健康分析数据
        try:
            with open(health_analysis_file, 'r', encoding='utf-8') as f:
                health_analysis_data = json.load(f)
            
            # 检查是否是final_timeline.json格式
            if 'monthly_details' in health_analysis_data:
                # 从final_timeline.json格式中提取健康数据
                month_str = f"2025-{month_num:02d}"
                
                # 查找对应的月份数据
                month_data = None
                for item in health_analysis_data['monthly_details']:
                    if item['month'] == month_str:
                        month_data = item
                        break
                
                if month_data:
                    # 提取本月的健康相关事件
                    health_events = [event for event in month_data['events'] if event.get('type') == 'Health']
                    
                    # 这里可以根据需要从健康事件中提取初始状态和结束状态
                    # 目前我们只是简单地创建一个包含所有健康事件的结构
                    if health_events:
                        # 假设第一个健康事件是初始状态，最后一个是结束状态
                        # 这只是一个简单的实现，实际可能需要更复杂的逻辑
                        health_initial_state = {"events": [health_events[0]]} if health_events else {}
                        health_end_state = {"events": [health_events[-1]]} if health_events else {}
                    else:
                        print(f"{month_str} 月份没有找到健康相关事件")
                else:
                    print(f"健康分析数据中未找到 {month_str} 月份的数据")
            else:
                # 传统格式：以月份为键的JSON对象
                month_key = f"2025-{month_num:02d}"
                if month_key in health_analysis_data:
                    month_health_data = health_analysis_data[month_key]
                    
                    # 从health_analysis字符串中解析初始状态和结束状态
                    try:
                        health_analysis_json = json.loads(month_health_data['health_analysis'])
                        
                        # 解析initial_state和end_of_month_state
                        initial_state_str = health_analysis_json.get('initial_state', '{}')
                        if isinstance(initial_state_str, str):
                            # 如果initial_state是字符串，需要进一步解析
                            if initial_state_str.startswith('```json'):
                                # 如果是代码格式的JSON，提取其中的JSON部分
                                import re
                                json_match = re.search(r'```json\s*\n(.*)\n```', initial_state_str, re.DOTALL)
                                if json_match:
                                    initial_state_str = json_match.group(1)
                            
                            initial_health_data = json.loads(initial_state_str)
                            # 获取initial_health_state
                            health_initial_state = initial_health_data.get('initial_health_state', {})
                        else:
                            health_initial_state = initial_state_str.get('initial_health_state', {})
                        
                        # 解析end_of_month_state作为健康结束状态
                        end_state_data = health_analysis_json.get('end_of_month_state', {})
                        health_end_state = end_state_data
                        
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"解析健康分析数据时出错: {e}")
                        # 如果解析失败，使用空字典
                        health_initial_state = {}
                        health_end_state = {}
                else:
                    raise ValueError(f"健康分析数据中未找到 {month_key} 月份的数据")
                    
        except FileNotFoundError:
            raise FileNotFoundError(f"未找到健康分析数据文件: {health_analysis_file}")
        except json.JSONDecodeError:
            raise ValueError(f"健康分析数据文件格式错误: {health_analysis_file}")
        
        # 创建persona副本并去除relation字段
        persona_without_relation = {k: v for k, v in persona.items() if k != 'relation'}
        persona_str = json.dumps(persona_without_relation, ensure_ascii=False, indent=2)
        month_event_data_str = json.dumps(month_event_data, ensure_ascii=False, indent=2)
        health_initial_state_str = json.dumps(health_initial_state, ensure_ascii=False, indent=2)
        health_end_state_str = json.dumps(health_end_state, ensure_ascii=False, indent=2)

        # 使用模板调用LLM生成月度报告
        prompt = template_monthly_health_report.format(
            persona=persona_str,
            initial_state=health_initial_state_str,
            end_of_month_state=health_end_state_str,
            month_data=month_event_data_str
        )
        
        # 直接调用llm_call_reason函数，传入context参数
        report = llm_call_reason(prompt, context, record=0)
        return report

    @staticmethod
    def parallel_monthly_health_report_generation(persona: Dict, 
                                                 event_data_path: str,
                                                 health_analysis_file: str = "output/new/all_months_analysis_20260113134815_updated.json",
                                                 output_dir: str = "output/monthly_health_reports",
                                                 context: str = "") -> Dict[str, str]:
        """
        并行生成12个月的健康报告并保存
        
        参数:
            persona: 不带联系人的画像数据
            event_data_path: 事件数据文件路径
            health_analysis_file: 健康分析数据文件路径
            output_dir: 输出目录路径
            context: 用于LLM调用的上下文信息
            
        返回:
            Dict[str, str]: 包含所有月份健康报告的字典
        """
        import json
        from datetime import datetime
        import os
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 定义生成单个月份报告的内部函数
        def generate_single_month_report(month_num):
            try:
                report = EventRefiner.monthly_health_report_generation(persona, month_num, event_data_path, health_analysis_file, context)
                return f"2025-{month_num:02d}", report
            except Exception as e:
                error_msg = f"生成{2025}-{month_num:02d}月健康报告时出错: {e}"
                print(error_msg)
                return f"2025-{month_num:02d}", error_msg
        
        # 使用线程池并行处理
        monthly_reports = {}
        with ThreadPoolExecutor(max_workers=4) as executor:  # 限制线程数以避免资源过度消耗
            # 提交所有任务
            future_to_month = {
                executor.submit(generate_single_month_report, month_num): month_num 
                for month_num in range(1, 13)  # 1到12月
            }
            
            # 收集结果
            for future in as_completed(future_to_month):
                month_key, report = future.result()
                monthly_reports[month_key] = report
                
                # 保存当月报告到单独文件（使用txt格式，因为报告内容是字符串）
                report_file_path = os.path.join(output_dir, f"{month_key}_month_report.txt")
                try:
                    with open(report_file_path, 'w', encoding='utf-8') as f:
                        f.write(report)
                    print(f"已保存 {month_key} 月健康报告到: {report_file_path}")
                except Exception as e:
                    print(f"保存 {month_key} 月健康报告时出错: {e}")
        
        # 按月份排序确保顺序
        sorted_reports = {key: monthly_reports[key] for key in sorted(monthly_reports.keys())}
        
        # 保存所有报告到一个汇总文件
        summary_file_path = os.path.join(output_dir, "all_monthly_health_reports.json")
        try:
            with open(summary_file_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_reports, f, ensure_ascii=False, indent=2)
            print(f"已保存所有月度健康报告汇总到: {summary_file_path}")
        except Exception as e:
            print(f"保存月度健康报告汇总时出错: {e}")
        
        return sorted_reports

# 如果直接运行此文件，则执行测试
if __name__ == "__main__":
    # 导入必要的模块
    import json
    
    # 从output文件夹读取测试数据
    print("\n=== 开始测试两周事件调整功能 ===")
    
    # 读取画像数据
    persona_path = "output/persona.json"
    event_decompose_path = "output/event_decompose_dfs.json"
    
    try:
        # 加载画像数据
        with open(persona_path, 'r', encoding='utf-8') as f:
            persona_data = json.load(f)
        print(f"成功加载画像数据: {persona_path}")
        
        # 加载事件分解数据
        with open(event_decompose_path, 'r', encoding='utf-8') as f:
            event_data = json.load(f)
        print(f"成功加载事件分解数据: {event_decompose_path}")

        events = event_data
        print(f"共加载 {len(events)} 个事件")
        
        # 创建EventRefiner实例，传入persona和events
        refiner = EventRefiner(persona_data, events)

        print(f"共加载 {len(refiner.bottom_events)} 个底部事件")

        # 设置测试时间范围（两周）
        start_date = "2025-10-01"
        end_date = "2025-10-14"
        print(f"测试时间范围: {start_date} 至 {end_date}")
        
        # 调用date_range_event_refine函数进行测试
            # 注意：这里仍然传入events参数以保持兼容性，虽然类已经持有events数据
        results = refiner.date_range_event_refine(events, start_date, end_date)

            # 打印测试结果
        print("\n=== 两周事件调整结果 ===")
        print(f"共生成 {len(results['event_updates'])} 个事件更新操作")
        for i, update in enumerate(results['event_updates']):
                print(f"更新 {i+1}: {update}")

            # 打印每日生活数据
        if results['dailylife']:
                print("\n=== 每日生活数据 ===")
                for i, daily in enumerate(results['dailylife']):
                    print(f"日期 {i+1}: {daily}")

            # 保存每日生活数据到测试文件
        if results['dailylife']:
                refiner.save_dailylife_to_json(results['dailylife'], "output/test_daily_state.json")
        
        # 测试健康分析功能
        print("\n=== 健康分析测试 ===")
        health_results = refiner.health_analysis(results, persona_data)
        print(f"健康分析结果: {health_results}")
        
        # 保存健康分析结果到文件
        with open("output/test_health_analysis.txt", 'w', encoding='utf-8') as f:
            f.write(health_results)
        print("健康分析结果已保存到: output/test_health_analysis.txt")

    except Exception as e:
        print(f"测试过程中出错: {type(e).__name__}: {e}")