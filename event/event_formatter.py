import os
import json
import glob
import re
from typing import List, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from event.templates import template_event_format_sequence
from event.mind import llm_call
from utils.llm_call import llm_call_reason, llm_call_reason_j


class EventFormatter:
    """
    事件格式化类，用于读取mind.py生成的中间输出文件，提取并格式化adjusted_events
    """
    
    def __init__(self, data_dir: str = "/output"):
        """
        初始化EventFormatter实例
        
        参数:
            data_dir: 数据存储目录，即mindcontroller使用的数据目录
        """
        self.data_dir = data_dir
        self.formatted_events = []
        self.event_id_counter = 1
        self.daily_draft_data = self._load_daily_draft_id()
    
    def _load_daily_draft_id(self) -> Dict:
        """
        加载daily_draft_id.json文件
        
        返回:
            Dict: daily_draft_id数据，键为完整日期（如"2025-01-01"），值为该日期的原子事件数据
        """
        # 先尝试在data_dir下查找daily_draft_id.json
        daily_draft_file = os.path.join(self.data_dir, "daily_draft_id.json")
        # 如果找不到，尝试在当前目录查找
        if not os.path.exists(daily_draft_file):
            daily_draft_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "fenghaoran", "daily_draft_id.json")
            
        date_based_data = {}
        
        try:
            if os.path.exists(daily_draft_file):
                with open(daily_draft_file, "r", encoding="utf-8") as f:
                    monthly_data = json.load(f)
                
                print(f"成功加载daily_draft_id.json，包含 {len(monthly_data)} 个月份的数据")
                
                # 将按月组织的数据转换为按天组织的数据
                total_days = 0
                total_events = 0
                
                for month, days in monthly_data.items():
                    for day_data in days:
                        date = day_data.get("date")
                        if date:
                            atomic_events = day_data.get("events", [])
                            # 提取所有原子事件并转换为统一格式
                            formatted_atomic_events = []
                            for atomic_event in atomic_events:
                                event_ids = atomic_event.get("event_id", [])
                                # 将每个event_id转换为单独的原子事件
                                for event_id in event_ids:
                                    formatted_atomic_events.append({
                                        "event_id": event_id,
                                        "content": atomic_event.get("description", "")
                                    })
                                    total_events += 1
                            
                            date_based_data[date] = formatted_atomic_events
                            total_days += 1
                
                print(f"数据转换完成：{total_days} 天，共 {total_events} 个原子事件")
            else:
                print(f"未找到daily_draft_id.json文件: {daily_draft_file}")
        except Exception as e:
            print(f"读取daily_draft_id.json时出错: {str(e)}")
        
        return date_based_data
    
    def _match_atomic_events(self, formatted_events: List[Dict], daily_draft_date_data: List[Dict], date: str, task_id: int) -> List[Dict]:
        """
        为格式化后的事件匹配原子事件ID（批量处理版本，一天只调用一次LLM）
        
        参数:
            formatted_events: 格式化后的事件列表
            daily_draft_date_data: 该日期的原子事件数据
            date: 日期
            task_id: 任务ID
            
        返回:
            List[Dict]: 添加了atomic_id字段的格式化事件列表
        """
        try:
            # 如果没有格式化事件或原子事件，直接返回
            if not formatted_events or not daily_draft_date_data:
                for event in formatted_events:
                    event["atomic_id"] = []
                return formatted_events
            
            # 准备格式化事件文本（为每个事件分配临时ID）
            formatted_events_text = "\n".join([
                f"事件临时ID {i+1}：{event.get('name', '')} - {event.get('description', '')}"
                for i, event in enumerate(formatted_events)
            ])
            
            # 准备原子事件数据文本
            atomic_events_text = "\n".join([
                f"原子事件ID {atomic_event.get('event_id', '')}: {atomic_event.get('content', '')}"
                for atomic_event in daily_draft_date_data
            ])
            
            # 生成匹配提示
            match_prompt = f"""
            请仔细比较以下所有格式化事件与原子事件列表，为每个格式化事件找出所有相关的原子事件ID：
            
            格式化事件列表（当天）：
            {formatted_events_text}
            
            原子事件列表（当天）：
            {atomic_events_text}
            
            匹配要求：
            1. 重点关注事件的核心活动和主要内容，而不是次要细节
            2. 即使事件的时间（如早晨改到晚上）、地点（如不同的跑步路线）等次要信息有差异，只要核心活动一致或高度相关，就应视为相关事件
            3. 允许一个格式化事件对应多个原子事件ID（即一个事件可能由多个原子事件组成）
            4. 分析每个格式化事件的主要内容和原子事件的内容是否相关
            5. 对于每个格式化事件，返回所有与之相关的原子事件ID
            6. 如果某个格式化事件没有相关的原子事件，请返回空列表
            7. 确保每个格式化事件都有对应的匹配结果
            
            返回格式：
            请返回JSON格式的字典，键为事件临时ID（数字，从1开始），值为相关的原子事件ID数组。
            例如：
            {{"1": ["3", "5"], "2": ["2"], "3": []}}
            
            注意：
            - 只返回JSON数据，不要包含任何额外的解释或说明
            - 确保JSON格式正确，没有语法错误
            - 原子事件ID必须是字符串格式
            """
            # 调用LLM进行批量匹配，使用llm_call_reason_j确保返回JSON格式
            from utils.llm_call import llm_call_reason_j
            match_result = llm_call_reason_j(match_prompt)
            
            # 清理匹配结果
            cleaned_match_result = self.remove_json_wrapper(match_result, json_type='object')
            try:
                match_mappings = json.loads(cleaned_match_result)
                print(match_mappings)
                # 为每个事件添加atomic_id字段
                for i, event in enumerate(formatted_events):
                    event_temp_id = str(i+1)
                    atomic_ids = match_mappings.get(event_temp_id, [])
                    
                    # 确保atomic_ids是列表格式
                    if not isinstance(atomic_ids, list):
                        atomic_ids = []
                    
                    event["atomic_id"] = atomic_ids
                    
                print(f"任务 {task_id} - 日期 {date} 批量匹配完成，为 {len(formatted_events)} 个事件分配了atomic_id")
            except Exception as e:
                print(f"任务 {task_id} - 日期 {date} 匹配原子事件时出错: {str(e)}")
                # 为所有事件添加空的atomic_id字段
                for event in formatted_events:
                    event["atomic_id"] = []
        finally:
            # 确保所有事件都有atomic_id字段，无论处理结果如何
            for event in formatted_events:
                if "atomic_id" not in event:
                    event["atomic_id"] = []
        
        return formatted_events
    
    def find_all_intermediate_files(self) -> List[str]:
        """
        查找所有中间输出文件
        
        返回:
            List[str]: 中间输出文件路径列表
        """
        # 查找所有日期文件夹，支持带前导零和不带前导零的格式（如2025-12-09和2025-12-9）
        date_folders = glob.glob(os.path.join(self.data_dir, "202*-*-*"))
        intermediate_files = []
        
        for folder in date_folders:
            # 查找该日期文件夹下的intermediate_output文件夹
            intermediate_output_folders = glob.glob(os.path.join(folder, "intermediate_output"))
            for intermediate_folder in intermediate_output_folders:
                # 查找intermediate_output文件夹中的所有中间输出文件
                files = glob.glob(os.path.join(intermediate_folder, "intermediate_outputs_thread_*.json"))
                intermediate_files.extend(files)
        
        # 如果在日期文件夹下没找到，检查根目录下是否有直接的中间输出文件
        root_files = glob.glob(os.path.join(self.data_dir, "intermediate_outputs_thread_*.json"))
        intermediate_files.extend(root_files)
        
        return intermediate_files
    
    def extract_adjusted_events(self, file_path: str) -> List[Dict]:
        """
        从中间输出文件中提取adjusted_events
        
        参数:
            file_path: 中间输出文件路径
        
        返回:
            List[Dict]: adjusted_events列表，每个元素包含日期和对应的事件
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            adjusted_events_list = []
            for date, outputs in data.items():
                if "adjusted_events" in outputs:
                    adjusted_events_list.append({
                        "date": date,
                        "events": outputs["adjusted_events"],
                        "poi_data": outputs.get("poi_data", "")
                    })
            
            return adjusted_events_list
        except Exception as e:
            print(f"读取文件 {file_path} 时出错: {str(e)}")
            return []
    
    def remove_json_wrapper(self, input_str: str, json_type: str = 'object') -> str:
        """
        移除JSON字符串的前后包装（如```json ```标签、非法转义字符等）
        并根据json_type参数提取对应的JSON内容：
        - json_type='object'：提取第一个{到最后一个}之间的内容
        - json_type='array'：提取第一个[到最后一个]之间的内容
        
        参数:
            input_str: 输入字符串
            json_type: JSON类型，'object'对应{}，'array'对应[]，默认为'object'
        
        返回:
            str: 清理后的字符串
        """
        # 步骤1：去除开头的```json（含空格/换行）和结尾的```（含空格）
        pattern = r'^\s*```json\s*\n?|\s*```\s*$'
        result = re.sub(pattern, '', input_str, flags=re.MULTILINE)

        # 步骤2：根据json_type提取对应的括号内容
        if json_type == 'array':
            first_bracket = result.find('[')
            last_bracket = result.rfind(']')
            if first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
                result = result[first_bracket:last_bracket + 1]
        else:  # 默认处理JSON对象
            first_brace = result.find('{')
            last_brace = result.rfind('}')
            if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                result = result[first_brace:last_brace + 1]

        # 步骤3：清理 JSON 非法控制字符
        # 保留：JSON 允许的控制字符（\n换行、\r回车、\t制表符、\b退格、\f换页）+ 可见ASCII字符（0x20-0x7E）+ 中文/全角字符
        valid_pattern = r'[^\x20-\x7E\n\r\t\b\f\u4E00-\u9FFF\u3000-\u303F\uFF00-\uFFEF\u2000-\u206F\u2E80-\u2EFF]'
        result = re.sub(valid_pattern, '', result)

        # 步骤4：规范空格和换行
        result = result.strip()  # 去除首尾多余空格/换行
        result = result.replace('\u3000', ' ')  # 全角空格转半角空格
        result = re.sub(r'\r\n?', '\n', result)  # 统一换行符为 \n
        return result
    
    def _format_events_task(self, events: str, poi_data: str, date: str, task_id: int) -> List[Dict]:
        """
        单个事件格式化任务，用于并行处理
        
        参数:
            events: 原始事件内容
            poi_data: POI数据
            date: 日期
            task_id: 任务ID，用于日志输出
        
        返回:
            List[Dict]: 格式化后的事件列表
        """
        try:
            # 使用template_event_format_sequence生成提示
            prompt = template_event_format_sequence.format(
                content=events,
                poi=poi_data,
                date=date
            )
            # 调用LLM获取格式化后的事件
            formatted_content = llm_call_reason_j(prompt)
            #print(formatted_content)
            # 清理JSON格式
            cleaned_content = self.remove_json_wrapper(formatted_content, json_type='array')
            
            # 解析JSON
            formatted_events = json.loads(cleaned_content)
            
            # 获取该日期的daily_draft数据
            daily_draft_date_data = self.daily_draft_data.get(date, [])
            
            # 为每个格式化后的事件匹配原子事件ID
            if daily_draft_date_data:
                formatted_events = self._match_atomic_events(formatted_events, daily_draft_date_data, date, task_id)
            
            return formatted_events
        except Exception as e:
            print(f"任务 {task_id} - 格式化日期 {date} 的事件时出错: {str(e)}")
            return []
    
    def format_events(self, events: str, poi_data: str, date: str) -> List[Dict]:
        """
        使用template_event_format_sequence格式化事件（单线程版本）
        
        参数:
            events: 原始事件内容
            poi_data: POI数据
            date: 日期
        
        返回:
            List[Dict]: 格式化后的事件列表
        """
        formatted_events = self._format_events_task(events, poi_data, date, 0)
        
        # 按日期排序事件（在同一天内按时间排序）
        def get_event_datetime(event):
            """从事件中提取日期时间用于排序"""
            if "date" in event and isinstance(event["date"], list) and len(event["date"]) > 0:
                # 解析日期时间字符串，格式如："2025-12-20 07:30:00至2025-12-20 08:00:00"
                date_str = event["date"][0].split("至")[0].strip()
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    # 如果解析失败，尝试只解析日期部分
                    try:
                        return datetime.strptime(date_str.split()[0], "%Y-%m-%d")
                    except ValueError:
                        # 如果仍然失败，返回一个很早的日期
                        return datetime.min
            return datetime.min
        
        formatted_events.sort(key=get_event_datetime)
        
        # 为每个事件添加唯一的event_id
        for event in formatted_events:
            event["event_id"] = str(self.event_id_counter)
            self.event_id_counter += 1
        
        # 获取该日期的daily_draft数据
        daily_draft_date_data = self.daily_draft_data.get(date, [])
        
        # 为每个格式化后的事件匹配原子事件ID
        if daily_draft_date_data:
            formatted_events = self._match_atomic_events(formatted_events, daily_draft_date_data, date, 0)
        
        return formatted_events
    
    def process_all_files(self, max_workers: int = 30):
        """
        处理所有中间输出文件
        
        参数:
            max_workers: 并行处理的最大线程数，默认5
        """
        # 查找所有中间输出文件
        intermediate_files = self.find_all_intermediate_files()
        print(f"找到 {len(intermediate_files)} 个中间输出文件")
        
        # 收集所有需要处理的任务
        tasks = []
        task_id = 1
        
        for file_path in intermediate_files:
            print(f"收集文件 {file_path} 的任务")
            
            # 提取adjusted_events
            adjusted_events_list = self.extract_adjusted_events(file_path)
            
            # 收集每个日期的事件处理任务
            for item in adjusted_events_list:
                date = item["date"]
                events = item["events"]
                poi_data = item["poi_data"]
                
                tasks.append({
                    'task_id': task_id,
                    'events': events,
                    'poi_data': poi_data,
                    'date': date
                })
                task_id += 1
        
        print(f"共收集到 {len(tasks)} 个处理任务")
        
        # 使用线程池并行处理所有任务
        formatted_events_list = []
        failed_count = 0  # 失败计数
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_task = {executor.submit(self._format_events_task, 
                                             task['events'], 
                                             task['poi_data'], 
                                             task['date'], 
                                             task['task_id']): task 
                             for task in tasks}
            
            # 处理完成的任务
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    formatted_events_list.append((task['task_id'], result))
                    print(f"任务 {task['task_id']} - 日期 {task['date']} 处理完成")
                except Exception as e:
                    print(f"任务 {task['task_id']} 处理失败: {str(e)}")
                    failed_count += 1
        
        # 收集所有格式化后的事件
        all_events = []
        for task_id, events in formatted_events_list:
            all_events.extend(events)
        
        # 按日期排序事件
        def get_event_datetime(event):
            """从事件中提取日期时间用于排序"""
            if "date" in event and isinstance(event["date"], list) and len(event["date"]) > 0:
                # 解析日期时间字符串，格式如："2025-12-20 07:30:00至2025-12-20 08:00:00"
                date_str = event["date"][0].split("至")[0].strip()
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    # 如果解析失败，尝试只解析日期部分
                    try:
                        return datetime.strptime(date_str.split()[0], "%Y-%m-%d")
                    except ValueError:
                        # 如果仍然失败，返回一个很早的日期
                        return datetime.min
            return datetime.min
        
        # 按日期排序所有事件
        all_events.sort(key=get_event_datetime)
        
        # 为排序后的事件添加唯一的event_id
        for event in all_events:
            event["event_id"] = str(self.event_id_counter)
            self.event_id_counter += 1
            self.formatted_events.append(event)
        
        print(f"共格式化了 {len(self.formatted_events)} 个事件")
        print(f"处理完成的任务数: {len(tasks) - failed_count}")
        print(f"处理失败的任务数: {failed_count}")
    
    def save_to_event_json(self, output_path: str = None):
        """
        将格式化后的事件保存到event.json文件
        
        参数:
            output_path: 输出文件路径，如果为None，则保存在data_dir下
        """
        if output_path is None:
            output_path = os.path.join(self.data_dir, "event.json")
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 保存到JSON文件
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.formatted_events, f, ensure_ascii=False, indent=2)
        
        print(f"格式化后的事件已保存到: {output_path}")
    
    def run(self, max_workers: int = 5):
        """
        执行完整的事件格式化流程
        
        参数:
            max_workers: 并行处理的最大线程数，默认5
        """
        print("=== 开始事件格式化流程 ===")
        
        # 处理所有文件
        self.process_all_files(max_workers=max_workers)
        
        # 保存结果
        self.save_to_event_json(self.data_dir+'daily_event.json')
        
        print("=== 事件格式化流程完成 ===")


# 使用示例
if __name__ == "__main__":
    import sys
    
    # 默认数据目录为项目根目录下的output文件夹
    data_dir = "../output"
    max_workers = 5  # 默认并行线程数
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            max_workers = int(sys.argv[2])
            if max_workers <= 0:
                max_workers = 5
        except ValueError:
            print("警告: 无效的max_workers参数，使用默认值5")
    
    formatter = EventFormatter(data_dir=data_dir)
    formatter.run(max_workers=max_workers)