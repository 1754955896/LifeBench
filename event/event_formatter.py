import os
import json
import glob
import re
from typing import List, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from event.templates import template_event_format_sequence
from event.mind import llm_call

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
            from utils.llm_call import llm_call_reason
            # 调用LLM获取格式化后的事件
            formatted_content = llm_call_reason(prompt, "你是一位事件格式化专家", 0)
            #print(formatted_content)
            # 清理JSON格式
            cleaned_content = self.remove_json_wrapper(formatted_content, json_type='array')
            
            # 解析JSON
            formatted_events = json.loads(cleaned_content)
            
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