# -*- coding: utf-8 -*-
"""数据规范化类，负责将时间线数据规范化为标准格式"""
import os
import json
from typing import Dict, List, Any
from utils.llm_call import llm_call_j, llm_call_reason_j


class Normalizer:
    """数据规范化类，负责将时间线数据规范化为标准格式"""
    
    def __init__(self, optimize_timeline_path: str, persona: Dict = None, isprint: bool = True):
        """
        初始化规范化器
        
        Args:
            optimize_timeline_path: 优化后的时间线数据文件路径
            persona: 人物画像数据
            isprint: 是否打印日志，默认为True
        """
        self.optimize_timeline_path = optimize_timeline_path
        self.normalized_file_path = os.path.join(os.path.dirname(self.optimize_timeline_path), "normalized_timeline.json")
        # 简化画像数据
        self.persona = self._simplify_persona(persona) if persona else {}
        self.isprint = isprint
    
    def _print(self, message: str):
        """
        根据isprint属性判断是否打印消息
        
        Args:
            message: 要打印的消息
        """
        if self.isprint:
            print(message)
    
    def _simplify_persona(self, persona: Dict) -> Dict:
        """
        简化画像信息，只保留relation字段中每个人物的必要信息
        
        Args:
            persona: 原始人物画像数据
        
        Returns:
            简化后的人物画像数据
        """
        simplified_persona = persona.copy()
        
        # 处理relation字段
        if "relation" in simplified_persona:
            simplified_relation = []
            for group in simplified_persona["relation"]:
                simplified_group = []
                for person in group:
                    # 只保留必要字段
                    simplified_person = {
                        "name": person.get("name", ""),
                        "relation": person.get("relation", ""),
                        "occupation": person.get("occupation", ""),
                        "relation_description": person.get("relation_description", "")
                    }
                    # 只保留home_address中的city字段
                    if "home_address" in person and isinstance(person["home_address"], dict):
                        simplified_person["city"] = person["home_address"].get("city", "")
                    else:
                        simplified_person["city"] = ""
                    simplified_group.append(simplified_person)
                simplified_relation.append(simplified_group)
            simplified_persona["relation"] = simplified_relation
        
        return simplified_persona
    
    def load_and_normalize_data(self) -> Dict:
        """
        加载并规范化时间线数据
        
        Returns:
            规范化后的时间线数据字典
        """
        self._print(f"开始加载和规范化数据...")
        self._print(f"原始文件路径: {self.optimize_timeline_path}")
        self._print(f"规范化文件路径: {self.normalized_file_path}")
        
        # 检测是否存在规范化文件
        if os.path.exists(self.normalized_file_path):
            try:
                with open(self.normalized_file_path, 'r', encoding='utf-8') as f:
                    self._print(f"直接加载规范化文件: {self.normalized_file_path}")
                    data = json.load(f)
                    self._print(f"规范化文件加载成功，包含{len(data.get('monthly_details', []))}个月的数据")
                    return data
            except Exception as e:
                self._print(f"加载规范化文件失败: {e}")
        
        # 如果没有规范化文件，加载原始文件并进行规范化
        if os.path.exists(self.optimize_timeline_path):
            try:
                with open(self.optimize_timeline_path, 'r', encoding='utf-8') as f:
                    self._print(f"加载原始文件: {self.optimize_timeline_path}")
                    raw_data = json.load(f)
                    self._print(f"原始文件加载成功，包含{len(raw_data.get('monthly_details', []))}个月的数据")
                
                # 规范化数据
                self._print("开始规范化数据...")
                normalized_data = self.normalize_timeline_data(raw_data)
                self._print(f"数据规范化完成，包含{len(normalized_data.get('monthly_details', []))}个月的数据")
                
                # 保存规范化后的数据
                try:
                    with open(self.normalized_file_path, 'w', encoding='utf-8') as f:
                        json.dump(normalized_data, f, ensure_ascii=False, indent=2)
                    self._print(f"规范化后的数据已保存到: {self.normalized_file_path}")
                except Exception as e:
                    self._print(f"保存规范化后的数据失败: {e}")
                
                return normalized_data
            except Exception as e:
                self._print(f"加载optimize_timeline.json失败: {e}")
                return {"comprehensive_summary": "", "monthly_details": []}
        else:
            self._print(f"optimize_timeline.json文件不存在: {self.optimize_timeline_path}")
            return {"comprehensive_summary": "", "monthly_details": []}
    
    def _assign_ids(self, monthly_details: List[Dict]) -> List[Dict]:
        """
        为所有事件统一分配唯一ID
        
        Args:
            monthly_details: 月度详情列表
        
        Returns:
            分配ID后的月度详情列表
        """
        current_id = 1000
        
        for month_data in monthly_details:
            events = month_data.get("events", [])
            for event in events:
                event["id"] = current_id
                current_id += 1
        
        return monthly_details
    
    def _get_holidays_and_weekends(self, month: str) -> Dict:
        """
        获取指定月份的节假日和周日
        
        Args:
            month: 月份，格式为 "YYYY-MM"
        
        Returns:
            包含节假日和周日的字典
        """
        import holidays
        from datetime import datetime, timedelta
        
        try:
            year, month_num = map(int, month.split("-"))
        except ValueError:
            return {"holidays": [], "weekends": []}
        
        # 初始化中国节假日数据集
        cn_holidays = holidays.China(years=year)
        
        holidays_list = []
        weekends_list = []
        
        # 获取当月第一天和最后一天
        first_day = datetime(year, month_num, 1)
        if month_num == 12:
            next_month_first = datetime(year + 1, 1, 1)
        else:
            next_month_first = datetime(year, month_num + 1, 1)
        last_day = (next_month_first - timedelta(days=1)).day
        
        # 遍历当月所有日期
        for day in range(1, last_day + 1):
            current_date = datetime(year, month_num, day)
            date_str = current_date.strftime("%Y-%m-%d")
            
            # 检查是否为节假日
            holiday_name = cn_holidays.get(current_date, "")
            if holiday_name:
                holidays_list.append({"date": date_str, "name": holiday_name})
            
            # 检查是否为周日
            if current_date.weekday() == 6:  # 0是周一，6是周日
                weekends_list.append(date_str)
        
        return {"holidays": holidays_list, "weekends": weekends_list}
    
    def normalize_timeline_data(self, raw_data: Dict) -> Dict:
        """
        规范化时间线数据格式
        
        Args:
            raw_data: 原始时间线数据
        
        Returns:
            规范化后的时间线数据
        """
        import concurrent.futures
        
        # 直接从数据中获取comprehensive_summary
        comprehensive_summary = raw_data.get("comprehensive_summary", "")
        
        # 并行处理每个月的数据
        monthly_details = raw_data.get("monthly_details", [])
        self._print(f"开始处理{len(monthly_details)}个月的数据...")
        normalized_monthly_details = []
        
        # 使用线程池并行处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            # 提交所有任务
            future_to_month = {
                executor.submit(self.normalize_month_data, month_data, raw_data): month_data 
                for month_data in monthly_details
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_month):
                try:
                    normalized_month = future.result()
                    if normalized_month:
                        normalized_monthly_details.append(normalized_month)
                        self._print(f"成功处理月份: {normalized_month.get('month')}")
                    else:
                        self._print("处理月份数据返回空结果")
                except Exception as e:
                    self._print(f"处理月份数据时发生错误: {e}")
        
        self._print(f"处理完成，成功处理{len(normalized_monthly_details)}个月的数据")
        
        # 按月份排序
        def get_month_key(month_data):
            month = month_data.get("month", "")
            return month
        
        normalized_monthly_details.sort(key=get_month_key)
        self._print("月份数据排序完成")
        
        # 统一分配ID
        normalized_monthly_details = self._assign_ids(normalized_monthly_details)
        self._print("事件ID分配完成")
        
        return {
            "comprehensive_summary": comprehensive_summary,
            "monthly_details": normalized_monthly_details
        }
    
    def normalize_month_data(self, month_data: Dict, year_data: Dict) -> Dict:
        """
        规范化单个月份数据
        
        Args:
            month_data: 原始月份数据
            year_data: 全年数据，作为背景参考
        
        Returns:
            规范化后的月份数据
        """
        month = month_data.get("month", "")
        events = month_data.get("events", [])
        
        # 获取当月节假日和周日
        calendar_info = self._get_holidays_and_weekends(month)
        
        self._print(f"开始处理月份: {month}")
        self._print(f"原始事件数量: {len(events)}")
        self._print(f"节假日数量: {len(calendar_info['holidays'])}")
        self._print(f"周日数量: {len(calendar_info['weekends'])}")
        
        # 构建提示词，让LLM生成规范化的事件数据
        prompt = f"""
        请将以下月份的事件数据规范化为指定格式：
        
        【本月数据】
        月份：{month}
        原始事件：{json.dumps(events, ensure_ascii=False)}
        
        【当月节假日】
        {json.dumps(calendar_info['holidays'], ensure_ascii=False)}
        
        【当月周日】
        {json.dumps(calendar_info['weekends'], ensure_ascii=False)}
        
        【全年数据背景】
        {json.dumps(year_data, ensure_ascii=False)}
        
        要求输出格式：
        {{
            "month": "2025-01",
            "events": [{{
                "name": "事件名称",
                "description": "事件描述。",
                "date": ["2025-01-26至2025-01-27"],
                "type": "事件类型"
            }}],
            "summary": "月度总结",
            "habits_preferences": "习惯偏好总结"
        }}
        
        重要要求：
        - 请严格按照上述JSON格式输出，不要包含任何额外的文本或解释
        - 确保输出是有效的JSON格式，可以被直接解析
        
        处理要求：
        1. 从本月原始事件数据中提取事件，并合理充实事件的详细信息
        2. 基于事件的性质和逻辑关系，推理分配合理的事件发生时间
        3. 确保本月内事件之间的时间安排协调合理，避免冲突
        4. 参考全年数据背景，确保事件与整体年度规划一致
        5. 考虑与其他相关事件的关联性，特别是与下个月开始和结束的协调
        6. 事件的发生日期可以跨月，确保跨月事件的时间安排合理
        7. 为每个事件生成合适的名称、详细描述、日期范围和类型
        8. 生成月度总结，概括当月的主要事件和变化
        9. 生成习惯偏好总结，主要描述本月个体的一些常规习惯活动/作息/身体情感状态，偏好，以及上述内容有没有发生变化
        10. 事件类型可参考：Family&Living Situation、Career、Health、Education、Relationships、Personal Life、Finance等
        11. 确保日期格式正确，使用YYYY-MM-DD格式，时间段必须使用"XXXX-XX-XX至XXXX-XX-XX"格式
        12. 如果事件多次发生，date数组内应该包含多个时间段，每个时间段都必须使用"XXXX-XX-XX至XXXX-XX-XX"格式
        13. 可根据已有原始事件数据适当合并或拆分事件
        14. 参考人物画像数据，确保事件与人物特点相符，但你需要注意，用户的画像特征会在一年中发生变化，所以不需要严格遵循原画像。
        15. 考虑事件可能对应产生的画像变化，在描述中体现这种关联
        16. 分配事件发生和执行时间时，要协调工作、节假日和周日的关系，合理安排时间
        
        【人物画像】
        {json.dumps(self.persona, ensure_ascii=False)}
        """
        
        try:
            self._print(f"调用LLM处理月份: {month}")
            result = llm_call_j(prompt)
            self._print(f"LLM返回结果: {result}")
            
            # 确保result是字典类型
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                    self._print("成功将字符串解析为JSON")
                except json.JSONDecodeError as e:
                    self._print(f"解析JSON失败: {e}")
                    return {
                        "month": month,
                        "events": [],
                        "summary": "",
                        "habits_preferences": ""
                    }
            
            # 确保返回的数据包含必要字段
            if isinstance(result, dict):
                if "month" not in result:
                    result["month"] = month
                if "events" not in result:
                    result["events"] = []
                if "summary" not in result:
                    result["summary"] = ""
                if "habits_preferences" not in result:
                    result["habits_preferences"] = ""
                
                return result
            else:
                self._print(f"LLM返回非字典类型: {type(result)}")
                return {
                    "month": month,
                    "events": [],
                    "summary": "",
                    "habits_preferences": ""
                }
        except Exception as e:
            self._print(f"规范化月份数据失败: {e}")
            # 返回原始数据的基本结构
            return {
                "month": month,
                "events": [],
                "summary": "",
                "habits_preferences": ""
            }