# -*- coding: utf-8 -*-
import json
import copy
from datetime import datetime, timedelta
import holidays
from typing import List, Dict, Optional
from event.templates import template_event_update, template_biweekly_event_schedule_analysis
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
            date_range_desc = f"{self.get_date_string(start_date)} 至 {self.get_date_string(end_date)}"
            
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
                result=res
            )

            res = self.llm_call_sr(prompt, 0)
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
    
    def save_dailylife_to_json(self, dailylife_data: List[Dict], output_path: str = "D:\\pyCharmProjects\\pythonProject4\\output\\daily_state.json"):
        """
        将每日生活数据保存到JSON文件
        
        参数:
            dailylife_data: 每日生活数据列表
            output_path: 输出文件路径，默认保存到output文件夹下的daily_state.json
        """
        import os
        
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

    def annual_event_refine(self, events: List[Dict], start_date: str, end_date: str, context: str = "", max_workers: int = 5) -> List[Dict]:
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
                self.save_dailylife_to_json(all_dailylife)

            return updated_events
        except Exception as e:
            print(f"年度事件调整过程中出错：{e}")
            return events

# 如果直接运行此文件，则执行测试
if __name__ == "__main__":
    # 导入必要的模块
    import json
    
    # 从output文件夹读取测试数据
    print("\n=== 开始测试两周事件调整功能 ===")
    
    # 读取画像数据
    persona_path = "D:\pyCharmProjects\pythonProject4\output\persona.json"
    event_decompose_path = "D:\pyCharmProjects\pythonProject4\output\event_decompose_dfs.json"
    
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
                refiner.save_dailylife_to_json(results['dailylife'], "D:\\pyCharmProjects\\pythonProject4\\output\\test_daily_state.json")

    except Exception as e:
        print(f"测试过程中出错: {type(e).__name__}: {e}")