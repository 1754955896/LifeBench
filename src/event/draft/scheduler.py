# -*- coding: utf-8 -*-
#1）调整日程使其合理  2）消解冲突  3）事件插入+后续调整  4）事件插入  5）事件粒度对齐
import multiprocessing
from datetime import timedelta
from utils.llm_call import *
import os
import holidays  # 需安装：pip install holidays
from event.draft.event_tree import *


class Scheduler:
    def __init__(self, persona, file_path):
        """初始化日程调度器，创建空的日程存储结构"""
        # 基础配置
        self.schedule = {}  # 存储日程数据，格式如{"2025-01-01":["event1","event2"],...}
        self.raw_events = []  # 保存原始事件信息
        self.persona = persona
        self.relation = ""
        self.file_path = file_path
        self.percentage = {}

        # 线程数配置
        self.cpu_count = multiprocessing.cpu_count()
        self.max_workers = self.cpu_count * 2  # 默认最大工作线程数
        self.decompose_workers = self.max_workers  # 事件分解线程数
        self.schedule_workers = self.max_workers  # 事件规划线程数

        # 解析人物画像
        d = persona
        if isinstance(persona, str):
            d = json.loads(persona)
        self.relation = d.get('relation', '')
        self.name = d.get('name', '')
    def load_from_json(self, json_data,persona,percentage):
        """
        从JSON数据加载日程，支持起止时间为数组的格式

        参数:
            json_data: 符合指定格式的JSON数据列表
                       每个元素包含"主题事件"和"起止时间"，其中"起止时间"是数组
        """
        self.raw_events = json_data
        self.persona = persona
        self.relation = persona['relation']
        self.percentage = percentage

    def llm_call_sr(self,prompt,record=0):
        """调用大模型的函数"""
        res = llm_call_reason_j(prompt)
        return res

    def llm_call_s(self,prompt,record=0):
        """调用大模型的函数"""
        res = llm_call_j(prompt)
        return res

    def get_month_calendar(self,year, month):
        """
        生成指定年月的每日星期几和节日对照表
        :param year: 年份（如2025）
        :param month: 月份（如1-12）
        :return: 列表，每个元素为{"date": "YYYY-MM-DD", "weekday": "星期X", "holiday": "节日名称或空"}
        """
        # 初始化中国节假日数据集
        cn_holidays = holidays.China(years=year)

        # 获取当月第一天和最后一天
        first_day = datetime(year, month, 1)
        # 计算当月最后一天（下个月第一天减1天）
        if month == 12:
            next_month_first = datetime(year + 1, 1, 1)
        else:
            next_month_first = datetime(year, month + 1, 1)
        last_day = (next_month_first - timedelta(days=1)).day

        calendar = []
        for day in range(1, last_day + 1):
            current_date = datetime(year, month, day)
            date_str = current_date.strftime("%Y-%m-%d")

            # 转换星期几（0=周一，6=周日 → 调整为"星期一"至"星期日"）
            weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四",
                           4: "星期五", 5: "星期六", 6: "星期日"}
            weekday = weekday_map[current_date.weekday()]

            # 获取节日（优先法定节假日，再传统节日）
            holiday = cn_holidays.get(current_date, "")

            calendar.append({
                "date": date_str,
                "weekday": weekday,
                "holiday": holiday
            })

        return calendar

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

    def generate_and_insert_events(self, timeline_data, events_by_theme=None):
        """
        根据时间线数据生成可插入事件并进行分析和插入
        第一轮：生成25-40个基于时间线的可插入事件，参考event_schema.csv的第二列
        新增轮次：生成10个左右2025年的个人生活变化转折点事件，参考event_schema.csv的第二列
        第三轮：生成20个左右不基于个人画像的事件和人类共性事件，增加随机性以开启人物画像的新属性
        第四轮：对每个事件进行影响分析，并插入时间线
        """
        import copy
        from event.templates.template_scheduler import template_generate_insertable_events, template_generate_creative_events, template_third_round_events, template_analyze_group_events
        
        try:
            # 读取event_schema.csv的所有内容作为参考事件
            reference_events_str = ""
            schema_path = "event/event_schema.csv"
            if os.path.exists(schema_path):
                with open(schema_path, 'r', encoding='utf-8') as f:
                    content = f.read()  # 读取整个文件内容
                    # 将内容按行分割，并在每行末尾添加分号
                    lines = content.strip().split('\n')
                    # 跳过标题行（假设第一行为标题）
                    for line in lines[1:]:
                        if line.strip():  # 确保不是空行
                            reference_events_str += line.strip() + ";"
            else:
                print("警告：event_schema.csv 文件不存在，将不使用参考事件")
            # 将字符串按分号分割成列表（去除最后的空元素）
            reference_events = reference_events_str.rstrip(';').split(';') if reference_events_str else []
            
            # 将参考事件转换为字符串格式
            reference_events_str = json.dumps(reference_events, ensure_ascii=False)
            
            # 初始化事件ID计数器和相关数据结构
            event_id_counter = 1
            same_theme_arr = []
            frequency_id_groups = []
            
            # 第一轮：生成基于时间线的可插入事件
            print("开始第一轮：生成基于时间线的可插入事件...")
            
            # 获取人物画像信息
            persona_info = getattr(self, 'persona', {})
            
            # 构建生成事件的提示
            prompt_gen_events = template_generate_insertable_events.format(
                persona=json.dumps(persona_info, ensure_ascii=False),
                timeline=json.dumps(timeline_data, ensure_ascii=False),
                reference_events=reference_events_str
            )
            
            # 调用LLM生成事件
            response_gen = self.llm_call_sr(prompt_gen_events,0)
            #print("LLM生成事件结果：",response_gen)
            # 提取JSON部分 - 预处理可能的引号问题
            processed_response = response_gen.replace('\\"', '"').replace('""', '\"')
            start_idx = processed_response.find('[')
            end_idx = processed_response.rfind(']')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = processed_response[start_idx:end_idx + 1]
                try:
                    generated_events_round1 = json.loads(json_response)
                    print(f"成功生成{len(generated_events_round1)}个基于时间线的可插入事件")
                except json.JSONDecodeError as e:
                    print(f"解析第一轮生成的事件JSON失败: {str(e)}")
                    print(f"尝试解析的响应内容: {json_response}")
                    generated_events_round1 = []
            else:
                print("无法从第一轮生成事件的响应中提取JSON")
                #print(f"响应内容: {response_gen}")
                generated_events_round1 = []
            
            # 直接将第一轮生成的事件根据开始时间插入到对应月份
            print("开始第一轮：直接插入基于时间线的事件...")
            updated_timeline = copy.deepcopy(timeline_data)
            
            # 为输入数据中的原始事件分配ID
            for month_detail in updated_timeline.get('monthly_details', []):
                for event in month_detail.get('events', []):
                    event['id'] = event_id_counter
                    
                    # 检查是否与events_by_theme中的事件匹配
                    if events_by_theme:
                        event_name = event.get('name', '').strip()
                        for theme_data in events_by_theme:
                            for theme_event in theme_data.get('events', []):
                                theme_event_name = theme_event.get('name', '').strip()
                                if event_name == theme_event_name:
                                    # 如果匹配，记录主题和事件ID
                                    theme_name = theme_data.get('theme_name', '未知主题')
                                    # 检查是否已有该主题的记录
                                    existing_theme = next((item for item in same_theme_arr if item.get('theme_summary') == theme_name), None)
                                    if existing_theme:
                                        existing_theme['event_ids'].append(event_id_counter)
                                    else:
                                        same_theme_arr.append({
                                            'theme_summary': theme_name,
                                            'event_ids': [event_id_counter]
                                        })
                    
                    event_id_counter += 1
            
            # 统计事件发生频率
            event_name_count = {}
            for event in generated_events_round1:
                event_name = event.get('name', '未知事件')
                if event_name in event_name_count:
                    event_name_count[event_name] += 1
                else:
                    event_name_count[event_name] = 1
            
            for event in generated_events_round1:
                # 获取开始时间和结束时间，可能是数组
                start_times = event.get('start_time', [])
                end_times = event.get('end_time', [])
                
                # 确保start_times和end_times是列表
                if not isinstance(start_times, list):
                    start_times = [start_times] if start_times else []
                if not isinstance(end_times, list):
                    end_times = [end_times] if end_times else []
                
                # 记录同一事件的所有ID
                same_event_ids = []
                
                # 遍历所有发生时间，依次插入事件
                for idx, (start_time_str, end_time_str) in enumerate(zip(start_times, end_times)):
                    if start_time_str:
                        try:
                            event_date = datetime.strptime(start_time_str.split(' ')[0], '%Y-%m-%d')
                            month_key = f"2025-{event_date.month:02d}"
                            
                            # 查找对应的月份索引
                            month_found = False
                            for i, month_detail in enumerate(updated_timeline.get('monthly_details', [])):
                                if month_detail.get('month') == month_key:
                                    # 分配事件ID
                                    event['id'] = event_id_counter
                                    
                                    # 检查是否与events_by_theme中的事件匹配
                                    event_name = event.get('name', '').strip()
                                    if events_by_theme:
                                        for theme_data in events_by_theme:
                                            for theme_event in theme_data.get('events', []):
                                                theme_event_name = theme_event.get('name', '').strip()
                                                if event_name == theme_event_name:
                                                    # 如果匹配，记录主题和事件ID
                                                    theme_name = theme_data.get('theme_name', '未知主题')
                                                    # 检查是否已有该主题的记录
                                                    existing_theme = next((item for item in same_theme_arr if item.get('theme_summary') == theme_name), None)
                                                    if existing_theme:
                                                        existing_theme['event_ids'].append(event_id_counter)
                                                    else:
                                                        same_theme_arr.append({
                                                            'theme_summary': theme_name,
                                                            'event_ids': [event_id_counter]
                                                        })
                                                    break
                                            else:
                                                continue
                                            break
                                    
                                    # 将事件添加到该月份的事件列表中
                                    updated_timeline['monthly_details'][i]['events'].append({
                                        'id': event_id_counter,
                                        'description': event.get('description', ''),
                                        'date': f"{start_time_str}至{end_time_str}",
                                        'belongs_to_theme': event.get('type', '其他')
                                    })
                                    same_event_ids.append(event_id_counter)
                                    print(f"已将事件 '{event.get('name', '未知事件')}' (发生时间 {idx+1}) 插入到{month_key}, ID: {event_id_counter}")
                                    event_id_counter += 1
                                    month_found = True
                                    break
                            
                            if not month_found:
                                print(f"警告：未找到{month_key}的数据，无法插入事件")
                                
                        except Exception as e:
                            print(f"解析事件时间失败: {str(e)}, 事件: {event.get('name', '未知事件')}, 发生时间: {idx+1}")
                
                # 检查是否是发生频率大于1的事件，记录ID组合
                event_name = event.get('name', '未知事件')
                if len(same_event_ids) > 1:  # 同一个事件发生多次（多个时间点）
                    frequency_id_groups.append(same_event_ids)
            
            # 新增轮次：生成变化事件
            print("开始第二轮：生成变化事件...")
            
            # 构建生成变化事件的提示
            prompt_gen_creative_events = template_generate_creative_events.format(
                persona=json.dumps(persona_info, ensure_ascii=False),
                reference_events=reference_events_str,
                timeline=json.dumps(updated_timeline, ensure_ascii=False)
            )
            
            # 调用LLM生成创新事件
            response_gen_creative = self.llm_call_sr(prompt_gen_creative_events,1)
            #print("LLM生成创新事件结果：",response_gen_creative)
            # 提取JSON部分 - 预处理可能的引号问题
            processed_response = response_gen_creative.replace('\\"', '"').replace('""', '\"')
            start_idx = processed_response.find('[')
            end_idx = processed_response.rfind(']')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = processed_response[start_idx:end_idx + 1]
                try:
                    generated_events_creative = json.loads(json_response)
                    print(f"成功生成{len(generated_events_creative)}个创新性事件")
                except json.JSONDecodeError as e:
                    print(f"解析创新事件JSON失败: {str(e)}")
                    #print(f"尝试解析的响应内容: {json_response}")
                    generated_events_creative = []
            else:
                print("无法从创新事件生成响应中提取JSON")
                #print(f"响应内容: {response_gen_creative}")
                generated_events_creative = []
            
            # 第三轮：生成不基于个人画像的事件和人类共性事件
            print("开始第三轮：生成不基于个人画像的事件和人类共性事件...")
            
            # 构建第三轮事件生成的提示
            prompt_gen_third_round = template_third_round_events.format(
                persona=json.dumps(persona_info, ensure_ascii=False),
                timeline=json.dumps(updated_timeline, ensure_ascii=False)
            )
            
            # 调用LLM生成第三轮事件
            response_gen_third = self.llm_call_sr(prompt_gen_third_round)
            #print("LLM生成第三轮事件结果：", response_gen_third)
            
            # 提取JSON部分 - 预处理可能的引号问题
            processed_response = response_gen_third.replace('\\"', '"').replace('""', '\"')
            start_idx = processed_response.find('[')
            end_idx = processed_response.rfind(']')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = processed_response[start_idx:end_idx + 1]
                try:
                    generated_events_third = json.loads(json_response)
                    print(f"成功生成{len(generated_events_third)}个不基于个人画像的事件和人类共性事件")
                except json.JSONDecodeError as e:
                    print(f"解析第三轮生成的事件JSON失败: {str(e)}")
                    #print(f"尝试解析的响应内容: {json_response}")
                    generated_events_third = []
            else:
                print("无法从第三轮生成事件的响应中提取JSON")
                #print(f"响应内容: {response_gen_third}")
                generated_events_third = []
            
            # 合并第二轮和第三轮生成的事件
            combined_second_third_events = generated_events_creative + generated_events_third
            print(f"第二、三轮共生成{len(combined_second_third_events)}个待筛选事件")
            
            # 对第二轮和第三轮事件进行分组筛选分析
            print("开始第四轮：分组筛选分析并插入事件...")
            
            # 将事件分成每组5个
            group_size = 5
            grouped_events = [combined_second_third_events[i:i + group_size] 
                              for i in range(0, len(combined_second_third_events), group_size)]
            
            processed_events = 0
            
            # 定义处理单个事件组的函数
            def process_event_group(group_data):
                group_idx, event_group = group_data
                print(f"正在处理第{group_idx + 1}组事件 ({len(event_group)}个事件)...")
                
                # 构建筛选分析的提示
                event_group_json = json.dumps(event_group, ensure_ascii=False, indent=2)
                
                prompt_analyze_group = template_analyze_group_events.format(
                    persona=json.dumps(persona_info, ensure_ascii=False),
                    timeline=json.dumps(updated_timeline, ensure_ascii=False),
                    event_group=event_group_json
                )
                
                response_analyze = self.llm_call_sr(prompt_analyze_group)
                #print(f"第{group_idx + 1}组分析结果：", response_analyze[:200] + "..." if len(response_analyze) > 200 else response_analyze)
                
                # 提取分析结果JSON - 预处理可能的引号问题
                processed_response = response_analyze.replace('\\"', '"').replace('""', '\"')
                start_idx = processed_response.find('[')
                end_idx = processed_response.rfind(']')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_response = processed_response[start_idx:end_idx + 1]
                    try:
                        analyzed_group = json.loads(json_response)
                        
                        # 收集要插入的事件而不是直接插入，避免多线程写入冲突
                        events_to_insert = []
                        theme_event_mapping = []
                        
                        for analyzed_event in analyzed_group:
                            # 处理事件主题中的所有事件（新格式：theme_summary作为主题名称）
                            theme_name = analyzed_event.get('theme_summary', '其他')
                            
                            # 处理event_sequence中的事件（新格式中所有事件都在event_sequence中）
                            event_sequence = analyzed_event.get('event_sequence', [])
                            
                            # 记录当前主题的所有事件ID占位符
                            current_theme_ids = []
                            
                            # 如果event_sequence为空，但分析事件本身包含事件信息，则将其作为单独事件处理
                            if not event_sequence:
                                # 获取开始时间和结束时间，可能是数组
                                start_times = analyzed_event.get('start_time', [])
                                end_times = analyzed_event.get('end_time', [])
                                
                                # 确保start_times和end_times是列表
                                if not isinstance(start_times, list):
                                    start_times = [start_times] if start_times else []
                                if not isinstance(end_times, list):
                                    end_times = [end_times] if end_times else []
                                
                                # 遍历所有发生时间
                                for idx, (start_time_str, end_time_str) in enumerate(zip(start_times, end_times)):
                                    if start_time_str:
                                        try:
                                            event_date = datetime.strptime(start_time_str.split(' ')[0], '%Y-%m-%d')
                                            month_key = f"2025-{event_date.month:02d}"
                                            
                                            # 添加事件到待插入列表
                                            events_to_insert.append({
                                                'month_key': month_key,
                                                'event': {
                                                    'description': analyzed_event.get('description', ''),
                                                    'date': f"{start_time_str}至{end_time_str}",
                                                    'belongs_to_theme': theme_name  # 直接使用theme_summary
                                                },
                                                'event_name': f"{analyzed_event.get('name', '未知事件')} (发生时间 {idx+1})"
                                            })
                                            current_theme_ids.append(0)  # 临时占位符，后续分配实际ID
                                        except Exception as e:
                                            print(f"解析分析后事件时间失败: {str(e)}, 事件: {analyzed_event.get('name', '未知事件')}, 发生时间: {idx+1}")
                            else:
                                # 处理event_sequence中的所有事件
                                for seq_event in event_sequence:
                                    # 获取开始时间和结束时间，可能是数组
                                    start_times = seq_event.get('start_time', [])
                                    end_times = seq_event.get('end_time', [])
                                    
                                    # 确保start_times和end_times是列表
                                    if not isinstance(start_times, list):
                                        start_times = [start_times] if start_times else []
                                    if not isinstance(end_times, list):
                                        end_times = [end_times] if end_times else []
                                    
                                    # 遍历所有发生时间
                                    for idx, (start_time_str, end_time_str) in enumerate(zip(start_times, end_times)):
                                        if start_time_str:
                                            try:
                                                event_date = datetime.strptime(start_time_str.split(' ')[0], '%Y-%m-%d')
                                                month_key = f"2025-{event_date.month:02d}"
                                                
                                                # 添加序列事件到待插入列表
                                                events_to_insert.append({
                                                    'month_key': month_key,
                                                    'event': {
                                                        'description': seq_event.get('description', ''),
                                                        'date': f"{start_time_str}至{end_time_str}",
                                                        'belongs_to_theme': theme_name  # 直接使用theme_summary
                                                    },
                                                    'event_name': f"{seq_event.get('name', '未知事件')} (发生时间 {idx+1})"
                                                })
                                                current_theme_ids.append(0)  # 临时占位符，后续分配实际ID
                                            except Exception as e:
                                                print(f"解析序列事件时间失败: {str(e)}, 事件: {seq_event.get('name', '未知事件')}, 发生时间: {idx+1}")
                            
                            # 如果有事件属于当前主题，记录主题和事件ID占位符
                            if current_theme_ids:
                                theme_event_mapping.append({
                                    'theme_summary': theme_name,
                                    'event_id_placeholders': current_theme_ids
                                })
                    
                        return events_to_insert, theme_event_mapping
                    except json.JSONDecodeError as e:
                            print(f"解析第{group_idx + 1}组分析JSON失败: {str(e)}")
                            #print(f"尝试解析的响应内容: {json_response}")
                            return [], []
                else:
                    print(f"无法从第{group_idx + 1}组分析响应中提取JSON: {response_analyze[:100]}...")
                    return [], []
            
            # 准备带索引的组数据
            indexed_groups = [(i, group) for i, group in enumerate(grouped_events)]
            
            # 使用线程池并行处理所有组
            all_events_to_insert = []
            all_theme_event_mappings = []
            
            with ThreadPoolExecutor(max_workers=min(len(indexed_groups), 8)) as executor:
                # 提交所有任务
                future_to_group = {executor.submit(process_event_group, group_data): group_data[0] 
                                   for group_data in indexed_groups}
                
                # 收集结果
                for future in as_completed(future_to_group):
                    group_idx = future_to_group[future]
                    try:
                        events_batch, theme_mapping_batch = future.result()
                        all_events_to_insert.extend(events_batch)
                        all_theme_event_mappings.extend(theme_mapping_batch)
                        print(f"第{group_idx + 1}组事件处理完成")
                    except Exception as e:
                        print(f"第{group_idx + 1}组事件处理出错: {e}")
            
            # 为所有要插入的事件分配ID并更新主题事件映射
            event_id_mapping = []  # 记录占位符索引到实际ID的映射
            for idx, event_data in enumerate(all_events_to_insert):
                event_id_mapping.append(event_id_counter)
                event_data['event']['id'] = event_id_counter
                
                # 检查是否与events_by_theme中的事件匹配
                event_name = event_data.get('event_name', '').split(' (')[0].strip()  # 去除发生时间后缀
                if events_by_theme:
                    for theme_data in events_by_theme:
                        for theme_event in theme_data.get('events', []):
                            theme_event_name = theme_event.get('name', '').strip()
                            if event_name == theme_event_name:
                                # 如果匹配，记录主题和事件ID
                                theme_name = theme_data.get('theme_name', '未知主题')
                                # 检查是否已有该主题的记录
                                existing_theme = next((item for item in same_theme_arr if item.get('theme_summary') == theme_name), None)
                                if existing_theme:
                                    existing_theme['event_ids'].append(event_id_counter)
                                else:
                                    same_theme_arr.append({
                                        'theme_summary': theme_name,
                                        'event_ids': [event_id_counter]
                                    })
                                break
                        else:
                            continue
                        break
                
                event_id_counter += 1
            
            # 更新主题事件映射中的实际ID
            current_placeholder_idx = 0
            for theme_mapping in all_theme_event_mappings:
                actual_event_ids = []
                for placeholder in theme_mapping['event_id_placeholders']:
                    if current_placeholder_idx < len(event_id_mapping):
                        actual_event_ids.append(event_id_mapping[current_placeholder_idx])
                        current_placeholder_idx += 1
                
                # 将主题和实际事件ID添加到同主题数组
                if actual_event_ids:
                    same_theme_arr.append({
                        'theme_summary': theme_mapping['theme_summary'],
                        'event_ids': actual_event_ids
                    })
            
            # 统一插入所有处理好的事件
            for event_data in all_events_to_insert:
                month_key = event_data['month_key']
                event = event_data['event']
                event_name = event_data['event_name']
                
                # 查找对应的月份索引并插入事件
                month_found = False
                for i, month_detail in enumerate(updated_timeline.get('monthly_details', [])):
                    if month_detail.get('month') == month_key:
                        updated_timeline['monthly_details'][i]['events'].append(event)
                        print(f"已将事件 '{event_name}' 插入到{month_key}")
                        processed_events += 1
                        month_found = True
                        break
                
                if not month_found:
                    print(f"警告：未找到{month_key}的数据，无法插入事件")
            
            print(f"事件生成和插入完成！第一轮直接插入{len(generated_events_round1)}个事件，筛选分析后插入{processed_events}个事件")
            
            # 构造返回结果
            result = {
                'updated_timeline': updated_timeline,
                'same_theme_arr': same_theme_arr,
                'frequency_id_groups': frequency_id_groups
            }
            
            return result
            
        except Exception as e:
            print(f"生成和插入事件过程中出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'updated_timeline': timeline_data, 'same_theme_arr': [], 'frequency_id_groups': []}

    def optimize_events_by_category(self, month, events, persona, calendar_data):
        """
        按事件类别优化事件的方法

        参数:
            month: 月份（如"1月"）
            events: 原始事件列表
            persona: 人物画像数据
            calendar_data: 日历数据

        返回:
            优化后的事件列表
        """
        import os
        from event.templates.template_scheduler import (
            category_definitions,
            template_career_optimization,
            template_education_optimization,
            template_relationships_optimization,
            template_family_living_optimization,
            template_personal_life_optimization,
            template_finance_optimization,
            template_health_optimization
        )
        
        # 读取event_schema.csv文件，获取各类别的事件参考
        schema_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'event_schema.csv')
        category_schema = {}
        
        try:
            import csv
            with open(schema_file_path, 'r', encoding='utf-8-sig', newline='') as f:
                csv_reader = csv.reader(f)
                rows = list(csv_reader)
                if len(rows) > 1:  # 确保文件至少有标题行和一行数据
                    # 跳过标题行，从第二行开始处理
                    previous_category = ""  # 保存上一个非空的类别
                    for row in rows[1:]:
                        if len(row) >= 4:
                            # 检查是否是空行或只有逗号的行
                            if not any(cell.strip() for cell in row):
                                continue
                            
                            # 如果当前行类别为空，则使用上一个非空类别
                            current_category = row[0].strip()
                            if current_category:
                                previous_category = current_category
                            else:
                                current_category = previous_category
                            
                            if current_category:  # 确保类别有效
                                if current_category not in category_schema:
                                    category_schema[current_category] = []
                                
                                stage_event = row[1].strip()
                                atomic_event = row[2].strip()
                                behavior = row[3].strip()
                                
                                if stage_event or atomic_event or behavior:
                                    category_schema[current_category].append({
                                        'stage_event': stage_event,
                                        'atomic_event': atomic_event,
                                        'behavior': behavior
                                    })
        except Exception as e:
            print(f"读取event_schema.csv文件时出错: {e}")
            # 如果读取失败，使用空的事件参考
            category_schema = {}

        # 打印category_schema内容进行调试
        print("\ncategory_schema构建结果:")
        for key in category_schema:
            print(f"- {key}: {len(category_schema[key])}个事件参考")
        print("\n")
        
        # 事件类别到模板的映射（只保留7个主要类别）
        category_to_template = {
            "Health": template_health_optimization,
            "Career": template_career_optimization,
            "Education": template_education_optimization,
            "Relationships": template_relationships_optimization,
            "Family&Living Situation": template_family_living_optimization,
            "Personal Life": template_personal_life_optimization,
            "Finance": template_finance_optimization,
        }

        # 准备通用参数
        all_events_json = json.dumps(events, ensure_ascii=False)
        persona_data_str = json.dumps(persona, ensure_ascii=False)
        
        # 并行处理每个类别的函数
        def process_category(category, template):
            print(f"调用LLM从{category}类别角度优化{month}的事件...")
            
            # 获取类别定义
            category_definition = category_definitions.get(category, "")
            
            try:
                # 获取当前类别的事件参考
                category_reference = category_schema.get(category, [])
                category_reference_json = json.dumps(category_reference, ensure_ascii=False)
                print(f"{category}类别参考数据: {category_reference}")
                
                # 格式化提示词
                prompt = template.format(
                    month=month,
                    category=category,
                    category_definition=category_definition,
                    original_events=all_events_json,
                    profile_data=persona_data_str,
                    calendar_data=calendar_data,
                    category_reference=category_reference_json
                )
                
                # 调用LLM进行优化
                category_result = self.llm_call_s(prompt)
                #print(f"LLM返回的{category}类别优化结果: {category_result}")
                
                # 解析优化结果，先提取JSON部分（第一个{到最后一个}）
                try:
                    # 找到第一个{和最后一个}的位置
                    first_brace = category_result.find('{')
                    last_brace = category_result.rfind('}')
                    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                        # 提取JSON部分
                        json_str = category_result[first_brace:last_brace+1]
                        category_result_json = json.loads(json_str)
                    else:
                        # 如果没有找到有效的JSON结构，尝试直接解析
                        category_result_json = json.loads(category_result)
                except json.JSONDecodeError as e:
                    # 如果直接解析也失败，打印错误并跳过这个类别的优化
                    print(f"解析{category}类别优化结果失败: {str(e)}")
                    return []
                
                # 所有类别使用相同的处理逻辑：处理操作序列数组
                # 直接使用解析后的数组作为操作序列
                if isinstance(category_result_json, list):
                    operations = category_result_json
                else:
                    # 获取操作序列数组
                    operations = category_result_json.get("operations", [])
                
                print(f"{category}类别操作序列处理完成，共{len(operations)}个操作")
                return operations
            except Exception as e:
                print(f"处理{category}类别时发生错误: {str(e)}")
                return []
        
        # 使用多线程并行处理所有类别
        import concurrent.futures
        all_operations = []
        
        print(f"开始并行处理{len(category_to_template)}个类别...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(category_to_template)) as executor:
            # 提交所有任务
            future_to_category = {
                executor.submit(process_category, category, template): category 
                for category, template in category_to_template.items()
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_category):
                category = future_to_category[future]
                try:
                    category_operations = future.result()
                    all_operations.extend(category_operations)
                    print(f"成功获取{category}类别的{len(category_operations)}个操作")
                except Exception as e:
                    print(f"获取{category}类别操作时发生错误: {str(e)}")
        
        print(f"所有类别并行处理完成，共收集{len(all_operations)}个操作")
        
        # 创建操作分析提示词，让LLM决定保留哪些操作
        print(f"让LLM分析操作序列并决定保留哪些操作...")
        
        # 构建分析提示词
        operations_analysis_prompt = f'''
        请基于以下人物画像、该月已有原事件数据和收集到对原数据修改的建议操作序列，分析并决定保留哪些操作。
        
        人物画像：{json.dumps(persona, ensure_ascii=False)}
        
        该月已有原事件数据：{json.dumps(events, ensure_ascii=False)}
        
        收集到的操作序列：{json.dumps(all_operations, ensure_ascii=False)}
        
        操作类型说明：
        1. **add**（添加操作）：
           - 向事件列表中添加新的事件
           - 格式：{{"type": "add", "event": {{事件详细信息}}}}
           - 作用：补充缺失的事件或丰富事件数据
        
        2. **delete**（删除操作）：
           - 从事件列表中删除指定名称的事件
           - 格式：{{"type": "delete", "event_name": "事件名称"}}
           - 作用：移除冗余、错误或不合理的事件
        
        3. **rewrite**（重写操作）：
           - 修改事件列表中指定名称的事件内容
           - 格式：{{"type": "rewrite", "event_name": "事件名称", "event": {{新的事件详细信息}}}}
           - 作用：修正事件信息、更新事件内容或优化事件描述
        
        分析要求：
        1. **评估操作与原事件数据的冲突**：
           - 检查每个操作所修改的事件是否与原事件数据存在冲突（如时间冲突、内容矛盾等）
           - 若操作与原事件数据冲突，优先依据原事件数据，摒弃该操作。
        
        2. **检查操作之间的冲突**：
           - 识别操作序列中相互冲突的操作（如对同一事件的不同修改）
           - 评估冲突操作的优先级，保留更合理、更必要的操作
        
        3. **评估操作的合理性和必要性**：
           - 操作是否符合原事件的整体逻辑和发展脉络
           - 操作是否能提升事件数据的完整性和合理性多样性。
           - 避免保留冗余、不必要或与原事件主旨不符的操作
           - 考虑新增事件是否合理，是否符合原事件的发展脉络，是否重复，是否导致某时间事件过多
           - 评估该月已有事件密度，避免新增事件安排过多导致该月份的事件安排过密
           - **避免新增与已有事件相似的事件**：检查新增事件与已有事件的名称、描述、类型是否高度相似，若存在高度相似的事件，应摒弃新增操作
           - **新增事件需保持主题多样性**：检查拟保留的新增事件之间的主题是否相似，避免添加多个主题重复或高度相似的事件（如避免添加多个学习类、工作类或休闲类事件），确保新增事件能够丰富人物的活动类型，提供多样化的生活体验
           - **考虑个人化特点进行事件类型取舍**：根据人物画像的职业、身份、经济状况等特征，合理调整事件类型的比例：
             * 若人物是工作者（如职场人士、上班族），应适当减少学习类事件的比例
             * 若人物是学生（如在校学生、研究生），应适当减少工作类事件的比例
             * 若人物经济状况较差（如低收入群体、贫困人口），应适当减少消费类事件的比例
             * 其他个人化特征也应作为参考，确保事件类型与人物身份、生活状态相符
           
        4. **优先级规则**：
           - 原事件数据优先级高于新操作
           - 重要事件的操作优先级高于次要事件
           - 能增强事件连贯性和合理性的操作优先级更高
           - 解决明显矛盾或错误的操作优先级更高
           - 符合并体现人物画像特征的事件类型优先级更高
           
        
        输出要求：
        请以JSON格式输出需要保留的操作序列，格式与输入的操作序列完全一致。
        只输出JSON内容，不要添加任何额外的文本、注释或格式。
        严格遵循JSON格式规范，在JSON字符串值中避免使用双引号，如果需要表示引号，请使用[]或其他替代符号，或者使用转义字符\\"，只输出JSON对象，不要输出任何额外的文本或注释。以[]开头。
        重要限制：
        1. **新增的事件（add操作）总数不得超过7个，一个月的事件总数不得超过25个。**
        2. 在满足限制的前提下，优先保留最重要的事件
        3. 如果超过限制，选择性保留最符合上下文、逻辑和人物画像特征的事件
        '''
        
        # 调用LLM分析操作序列
        retained_operations_result = self.llm_call_sr(operations_analysis_prompt)
        #print(f"LLM返回的保留操作序列: {retained_operations_result}")
        
        # 在解析JSON之前，先匹配第一个[和最后一个]
        import re
        bracket_pattern = r'\[(.*)\]'
        matches = re.findall(bracket_pattern, retained_operations_result, re.DOTALL)
        if matches:
            # 取第一个[到最后一个]之间的内容
            json_content = f"[{matches[0]}]"
        else:
            # 如果没有找到[], 则使用原始内容
            json_content = retained_operations_result
        
        # 解析LLM返回的结果，获取保留的操作
        try:
            retained_operations = json.loads(json_content)
            if not isinstance(retained_operations, list):
                # 如果返回的不是列表，尝试从JSON中提取operations字段
                retained_operations = retained_operations.get("operations", [])
            print(f"LLM决定保留{len(retained_operations)}个操作")
        except json.JSONDecodeError as e:
            print(f"解析保留操作序列失败: {str(e)}")
            # 如果解析失败，使用所有操作
            retained_operations = all_operations
            print(f"解析失败，使用所有操作")
        
        # 执行LLM保留的操作
        optimized_events = events.copy()
        
        print(f"开始执行LLM保留的操作...")
        for op in retained_operations:
            action = op.get("action", "")
            
            if action == "add":
                # 直接添加事件到数组，新增事件id为0
                event = op.get("event", {})
                if event and "name" in event:
                    event["id"] = 0  # 新增事件id为0
                    optimized_events.append(event)
                    print(f"执行add操作：添加事件'{event['name']}'，id=0")
                else:
                    print(f"add操作事件信息不完整，跳过")
            
            elif action == "delete":
                # 从原数组匹配名字删除事件
                delete_event = op.get("event", {})
                delete_name = delete_event.get("name", "")
                if delete_name:
                    # 找到所有匹配名称的事件并删除
                    original_length = len(optimized_events)
                    optimized_events = [e for e in optimized_events if e.get("name", "") != delete_name]
                    deleted_count = original_length - len(optimized_events)
                    if deleted_count > 0:
                        print(f"执行delete操作：删除{deleted_count}个名为'{delete_name}'的事件")
                    else:
                        print(f"delete操作：未找到名为'{delete_name}'的事件，跳过")
                else:
                    print(f"delete操作事件名称缺失，跳过")
            
            elif action == "rewrite":
                # 匹配名字重写事件
                original_event = op.get("original_event", {})
                original_name = original_event.get("name", "")
                new_event = op.get("new_event", {})
                
                if original_name and new_event and "name" in new_event:
                    # 找到第一个匹配名称的事件并替换
                    found = False
                    for i, e in enumerate(optimized_events):
                        if e.get("name", "") == original_name:
                            # 保留原始事件的id，赋值给新事件
                            original_id = e.get("id", 0)
                            new_event["id"] = original_id
                            optimized_events[i] = new_event
                            print(f"执行rewrite操作：将事件'{original_name}'重写为'{new_event['name']}'，保留原id={original_id}")
                            found = True
                            break
                    if not found:
                        print(f"rewrite操作：未找到名为'{original_name}'的事件，跳过")
                else:
                    print(f"rewrite操作事件信息不完整，跳过")
            
            else:
                print(f"未知操作类型：{action}，跳过")
        
        print(f"所有保留操作执行完成，最终事件数：{len(optimized_events)}")
        final_optimized_events = optimized_events

        return final_optimized_events

    def process_single_month(self, month_data):
            """
            处理单个月数据的内部方法

            参数:
                month_data: 单个月的数据，可能包含profile_changes_context字段

            返回:
                优化后的单个月数据
            """
            from event.templates.template_scheduler import template_monthly_analysis
            import json

            month = month_data["month"]
            print(f"\n开始处理{month}的事件...")

            # 生成这个月的日历数据
            # 从"YYYY-MM"格式解析月份数字
            month_num = int(month.split('-')[1])
            # 使用现有的get_month_calendar方法获取日历数据
            calendar_data = self.get_month_calendar(2025, month_num)

            # 第一步：调用LLM分析这个月的事件，给出修改建议
            monthly_data_str = json.dumps(month_data, ensure_ascii=False)
            persona_data_str = json.dumps(self.persona, ensure_ascii=False)

            # 确保每个事件都有id字段
            for event in month_data["events"]:
                if "id" not in event:
                    event["id"] = 0  # 如果没有id，默认为0
            
            # 提取id数组
            event_ids = [event["id"] for event in month_data["events"]]
            
            # 获取profile_changes_context，如果不存在则设为空数组的JSON字符串
            profile_changes_context = month_data.get("profile_changes_context", [])
            profile_changes_context_str = json.dumps(profile_changes_context, ensure_ascii=False)
            
            # 获取previous_month_final_status，如果不存在则设为空对象的JSON字符串
            previous_month_final_status = month_data.get("previous_month_final_status", {})
            previous_month_final_status_str = json.dumps(previous_month_final_status, ensure_ascii=False)
            
            prompt_analysis = template_monthly_analysis.format(
                month=month,
                monthly_data=monthly_data_str,
                persona_data=persona_data_str,
                calendar_data=calendar_data,
                event_ids=event_ids,
                profile_changes_context=profile_changes_context_str,
                previous_month_final_status=previous_month_final_status_str
            )
            print(monthly_data_str)
            print(f"调用LLM分析{month}的事件...")
            analysis_result = self.llm_call_sr(prompt_analysis)
            #print(f"LLM返回的优化建议: {analysis_result}")
            # 解析LLM返回的结果
            try:
                # 提取第一个{到最后一个}之间的有效JSON内容
                start_idx = analysis_result.find('{')
                end_idx = analysis_result.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    valid_json_str = analysis_result[start_idx:end_idx+1]
                    analysis_result_json = json.loads(valid_json_str)
                else:
                    print(f"无法从分析结果中提取有效JSON")
                    raise json.JSONDecodeError("Invalid JSON format", analysis_result, 0)
                optimized_events = analysis_result_json.get("events", month_data["events"])
                
                # 添加事件完整性检查
                print(f"\n事件完整性检查：")
                print(f"输入事件数量：{len(month_data['events'])}")
                print(f"输出事件数量：{len(optimized_events)}")

                # 检查所有输入事件ID是否在输出中出现
                input_event_ids = set(event_ids)
                output_event_ids = set(event["id"] for event in optimized_events if event["id"] != 0)

                # 找出缺失的事件ID
                missing_event_ids = input_event_ids - output_event_ids
                if missing_event_ids:
                    print(f"警告：发现缺失的事件ID：{missing_event_ids}")
                    print(f"输入事件ID列表：{input_event_ids}")
                    print(f"输出事件ID列表：{output_event_ids}")

                    # 获取缺失的事件详情
                    # missing_events = [event for event in month_data["events"] if event["id"] in missing_event_ids]
                    # print(f"缺失的事件详情：{missing_events}")


            except json.JSONDecodeError:
                print(f"解析{month}的LLM分析结果失败，使用原始事件")
                optimized_events = month_data["events"]

            print(f"完成{month}的事件分析，最终事件：{optimized_events}")

            # 第二步：按9个事件类别进行优化
            print(f"开始按9个事件类别优化{month}的事件...")
            final_optimized_events = self.optimize_events_by_category(
                month=month,
                events=optimized_events,
                persona=self.persona,
                calendar_data=calendar_data
            )
            print(f"完成{month}的事件类别优化")

            # 更新该月的事件
            optimized_month_data = final_optimized_events
            print(f"更新{month}的事件为：{optimized_month_data}")
            
            print(f"{month}的事件处理完成")
            
            # 返回最终优化后的单个月数据
            return {
                "month": month,
                "events": optimized_month_data
            }

    def monthly_event_planning(self, timeline_data):
        """
        月度事件规划与分析整合方法（串行处理每个月的数据）

        参数:
            timeline_data: 时间线数据（gi.json格式）

        返回:
            优化后的月度事件数据和分析结果
        """
        from concurrent.futures import ThreadPoolExecutor
        import event.draft.event_refiner

        # 检查输入数据格式
        if not isinstance(timeline_data, dict) or 'monthly_details' not in timeline_data:
            raise ValueError("输入数据格式错误，缺少'monthly_details'字段")

        # 初始化EventRefiner实例
        refiner = event.draft.event_refiner.EventRefiner(self.persona, {})

        optimized_timeline = {
            "category": timeline_data.get("category", "综合事件"),
            "comprehensive_summary": timeline_data.get("comprehensive_summary", ""),
            "monthly_details": [],
            "analysis_results": {}  # 新增分析结果字段
        }

        # 支持"X月"和"2025-XX"格式
        def get_month_num(month_str):
            if "月" in month_str:
                return int(month_str.replace("月", ""))
            elif "-" in month_str:
                return int(month_str.split("-")[1])
            else:
                return 13  # 默认值，确保无法解析的月份排在最后
        
        # 按月份顺序排序
        sorted_month_details = sorted(timeline_data["monthly_details"], key=lambda x: get_month_num(x["month"]))

        # 串行处理每个月的数据
        results = []
        previous_analysis = None
        
        for month_data in sorted_month_details:
            month = month_data["month"]
            print(f"\n开始处理{month}的数据...")
            
            # 准备事件规划的输入数据
            # 如果有前一个月的分析结果，提取profile_changes和final_day_status作为背景
            if previous_analysis and 'transition_analysis' in previous_analysis:
                prev_transition_analysis = previous_analysis['transition_analysis']
                # 将profile_changes添加到month_data中作为背景信息
                month_data['profile_changes_context'] = prev_transition_analysis.get('profile_changes', [])
                # 将final_day_status添加到month_data中作为背景信息
                month_data['previous_month_final_status'] = prev_transition_analysis.get('final_day_status', {})
                print(f"使用前一个月的profile_changes和final_day_status作为{month}的背景信息")
            
            # 处理单个月的事件规划
            result = self.process_single_month(month_data)
            
            # # 将每个月的原始结果保存到record文件中
            # record_dir = os.path.join(os.path.dirname(__file__), '../output/new/refine')
            # os.makedirs(record_dir, exist_ok=True)
            #
            # # 生成唯一的record文件名
            # timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 包含毫秒的时间戳
            # record_filename = f"record_{month.replace('-', '_')}_{timestamp}.json"
            # record_filepath = os.path.join(record_dir, record_filename)
            #
            # # 保存原始结果到record文件
            # with open(record_filepath, 'w', encoding='utf-8') as f:
            #     json.dump(result, f, ensure_ascii=False, indent=2)
            # print(f"{month}的原始数据已保存到: {record_filepath}")
            
            results.append(result)
            print(f"{month}的事件规划完成")
            
            # 调用分析函数进行健康、生活和转换分析
            print(f"开始分析{month}的事件...")
            
            # 准备初始状态数据
            initial_health_state = None
            if previous_analysis and 'health_analysis' in previous_analysis:
                try:
                    prev_health_data = previous_analysis['health_analysis']
                    initial_health_state = prev_health_data.get('end_of_month_state')
                    if initial_health_state:
                        print(f"使用上个月的健康最终状态作为{month}月份的初始状态")
                except Exception as e:
                    print(f"解析上个月健康状态时出错: {e}")
            
            initial_life_state = None
            if previous_analysis and 'life_analysis' in previous_analysis:
                initial_life_state = previous_analysis['life_analysis'].get('final_state')
                if initial_life_state:
                    print(f"使用上个月的生活最终状态作为{month}月份的初始状态")
            
            prev_transition_analysis = previous_analysis['transition_analysis'] if previous_analysis and 'transition_analysis' in previous_analysis else None
            
            # 并行调用分析函数
            with ThreadPoolExecutor(max_workers=12) as executor:
                # 提交所有分析任务
                future_health = executor.submit(refiner.health_analysis, result, self.persona, initial_state=initial_health_state)
                future_life = executor.submit(refiner.life_analysis, result, self.persona, initial_state=initial_life_state)
                future_transition = executor.submit(refiner.month_transition_analysis, result, self.persona, previous_analysis=prev_transition_analysis)
                
                # 获取分析结果
                health_result = future_health.result()
                life_result = future_life.result()
                transition_result = future_transition.result()
                
            print(f"{month}的所有分析任务已完成")
            
            # 保存本月的分析结果
            month_analysis_results = {
                'month': month,
                'health_analysis': health_result,
                'life_analysis': life_result,
                'transition_analysis': transition_result
            }
            
            # 添加到分析结果字典
            optimized_timeline['analysis_results'][month] = month_analysis_results
            
            # 更新previous_analysis为当前月份的所有分析结果
            previous_analysis = {
                'health_analysis': health_result,
                'life_analysis': life_result,
                'transition_analysis': transition_result
            }

        # 为所有id为0的事件统一分配新id（从全年最大id开始递增）
        all_events = []
        for month_data in results:
            all_events.extend(month_data["events"])
        
        if len(all_events) > 0:
            # 找到全年最大id
            max_id = max(event.get("id", 0) for event in all_events)
            
            # 为所有id=0的事件重新赋值
            for month_data in results:
                for event in month_data["events"]:
                    if event.get("id", 0) == 0:
                        max_id += 1
                        event["id"] = max_id
                        print(f"为新增事件'{event.get('name', '')}'分配新id: {max_id}")
        
        optimized_timeline["monthly_details"] = results

        # # 保存分析结果
        # output_dir = os.path.join(os.path.dirname(__file__), '../analysis_results')
        # os.makedirs(output_dir, exist_ok=True)
        
        # # 保存所有月份的综合分析结果
        # all_results_file = os.path.join(output_dir, f"all_months_analysi.json")
        # with open(all_results_file, 'w', encoding='utf-8') as f:
        #     json.dump(optimized_timeline['analysis_results'], f, ensure_ascii=False, indent=2)
        # print(f"\n所有月份分析结果已保存到: {all_results_file}")

        # # 保存最终调整过ID的完整结果
        # final_output_dir = os.path.join(os.path.dirname(__file__), '../output/new')
        # os.makedirs(final_output_dir, exist_ok=True)
        
        # final_output_file = os.path.join(final_output_dir, f"final_monthly_planning_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        # with open(final_output_file, 'w', encoding='utf-8') as f:
        #     json.dump(optimized_timeline, f, ensure_ascii=False, indent=2)
        # print(f"\n最终调整过ID的月度规划结果已保存到: {final_output_file}")

        return optimized_timeline
    def process_monthly_details(self, monthly_details_data, output_file_prefix):
        """
        处理monthly_details格式的数据，对事件进行分组并调用EventTree类进行事件分解

        参数:
            monthly_details_data: 包含monthly_details字段的数组格式数据
            output_file_prefix: 输出文件的前缀

        返回:
            Dict: 分解后的事件树结构
        """
        if not isinstance(monthly_details_data, list):
            raise ValueError("输入数据格式错误，monthly_details应为数组格式")

        # 将所有月份的事件合并到一个列表中
        all_events = []

        for month_data in monthly_details_data:
            if not isinstance(month_data, dict) or 'events' not in month_data:
                continue

            for event in month_data['events']:
                # 确保每个事件都有必要的字段
                if isinstance(event, dict):
                    # 保留事件原有的event_id
                    event_copy = event.copy()

                    # 将id字段替换为event_id
                    if 'id' in event_copy:
                        event_copy['event_id'] = event_copy.pop('id')
                    # 如果没有id字段，确保event_id字段存在
                    event_copy.setdefault('event_id', 0)

                    # 确保所有必要字段都存在
                    event_copy.setdefault('name', '未命名事件')
                    event_copy.setdefault('description', '')
                    event_copy.setdefault('type', 'Other')
                    event_copy.setdefault('date', [])

                    all_events.append(event_copy)

        print(f"共处理{len(all_events)}个事件")

        # 创建EventTree实例并调用事件分解函数
        event_tree = EventTree(self.persona)
        event_tree.event_decomposer(all_events, output_file_prefix, max_workers=self.decompose_workers)

        return event_tree.decompose_schedule
    def generate_yearly_timeline_draft(self, persona, output_path="output/", meidan_path=None):
        """
        生成年度时间线草稿（优化版：添加错误处理和输出保存）

        参数:
            persona: 人物画像数据
            output_path: 每日状态数据输出路径
            meidan_path: 除每日状态外的其他数据输出路径

        返回:
            生成的年度时间线草稿数据，或在发生错误时返回None
        """
        import os
        import json
        import traceback
        from datetime import datetime

        # 如果meidan_path未指定，使用output_path加process文件夹
        if meidan_path is None:
            meidan_path = os.path.join(output_path, 'process')
        
        # 确保输出路径存在
        os.makedirs(output_path, exist_ok=True)
        os.makedirs(meidan_path, exist_ok=True)

        try:
            # 步骤1: 提取重要节点
            print("\n=== 步骤1: 提取重要节点 ===")
            important_nodes_path = os.path.join(meidan_path, "important_nodes.json")
            if os.path.exists(important_nodes_path):
                print(f"✓ 重要节点文件已存在，直接读取: {important_nodes_path}")
                with open(important_nodes_path, 'r', encoding='utf-8') as f:
                    important_nodes = json.load(f)
            else:
                important_nodes = self.extract_important_nodes(persona=persona)
                print(f"✓ 成功提取{len(important_nodes)}个重要节点")
                # 保存结果
                with open(important_nodes_path, 'w', encoding='utf-8') as f:
                    json.dump(important_nodes, f, ensure_ascii=False, indent=2)
                print(f"✓ 重要节点已保存到: {important_nodes_path}")

            # 步骤2: 生成事件时间线
            print("\n=== 步骤2: 生成事件时间线 ===")
            event_timelines_path = os.path.join(meidan_path, "event_timelines.json")
            if os.path.exists(event_timelines_path):
                print(f"✓ 事件时间线文件已存在，直接读取: {event_timelines_path}")
                with open(event_timelines_path, 'r', encoding='utf-8') as f:
                    event_timelines = json.load(f)
            else:
                event_timelines = self.generate_event_timeline(important_nodes, max_workers=12)
                print(f"✓ 成功生成{len(event_timelines)}个事件时间线")
                # 保存结果
                with open(event_timelines_path, 'w', encoding='utf-8') as f:
                    json.dump(event_timelines, f, ensure_ascii=False, indent=2)
                print(f"✓ 事件时间线已保存到: {event_timelines_path}")

            # 步骤3: 合并相似时间线
            print("\n=== 步骤3: 合并相似时间线 ===")
            merged_timelines_path = os.path.join(meidan_path, "merged_timelines.json")
            if os.path.exists(merged_timelines_path):
                print(f"✓ 合并后的时间线文件已存在，直接读取: {merged_timelines_path}")
                with open(merged_timelines_path, 'r', encoding='utf-8') as f:
                    merged_timelines = json.load(f)
            else:
                merged_timelines = self.merge_similar_timelines(event_timelines)
                print(f"✓ 成功合并为{len(merged_timelines)}个时间线")
                # 保存结果
                with open(merged_timelines_path, 'w', encoding='utf-8') as f:
                    json.dump(merged_timelines, f, ensure_ascii=False, indent=2)
                print(f"✓ 合并后的时间线已保存到: {merged_timelines_path}")

            # 步骤4: 优化合并后的时间线
            print("\n=== 步骤4: 优化合并后的时间线 ===")
            optimized_timelines_path = os.path.join(meidan_path, "optimized_timelines.json")
            if os.path.exists(optimized_timelines_path):
                print(f"✓ 优化后的时间线文件已存在，直接读取: {optimized_timelines_path}")
                with open(optimized_timelines_path, 'r', encoding='utf-8') as f:
                    optimized_timelines = json.load(f)
            else:
                optimized_timelines = self.optimize_merged_timelines(merged_timelines)
                print(f"✓ 成功优化为{len(optimized_timelines)}个时间线")
                # 保存结果
                with open(optimized_timelines_path, 'w', encoding='utf-8') as f:
                    json.dump(optimized_timelines, f, ensure_ascii=False, indent=2)
                print(f"✓ 优化后的时间线已保存到: {optimized_timelines_path}")

            # 步骤5: 生成并插入事件
            print("\n=== 步骤5: 生成并插入事件 ===")
            rich_timeline_path = os.path.join(meidan_path, "rich_timeline.json")
            if os.path.exists(rich_timeline_path):
                print(f"✓ 丰富后的时间线文件已存在，直接读取: {rich_timeline_path}")
                with open(rich_timeline_path, 'r', encoding='utf-8') as f:
                    rich_timeline = json.load(f)
            else:
                # 在这里执行convert_timeline_to_events_with_llm
                optimized_timelines = self.convert_timeline_to_events_with_llm(optimized_timelines)
                rich_timeline = self.generate_and_insert_events(optimized_timelines["timeline_data"],optimized_timelines["events_by_theme"])
                print(f"✓ 成功生成并插入事件")
                # 保存结果
                with open(rich_timeline_path, 'w', encoding='utf-8') as f:
                    json.dump(rich_timeline, f, ensure_ascii=False, indent=2)
                print(f"✓ 丰富后的时间线已保存到: {rich_timeline_path}")

            # 步骤6: 月度事件规划
            print("\n=== 步骤6: 月度事件规划 ===")
            final_timeline_path = os.path.join(meidan_path, "final_timeline.json")
            if os.path.exists(final_timeline_path):
                print(f"✓ 最终时间线文件已存在，直接读取: {final_timeline_path}")
                with open(final_timeline_path, 'r', encoding='utf-8') as f:
                    final_timeline = json.load(f)
            else:
                final_timeline = self.monthly_event_planning(rich_timeline["updated_timeline"])
                print(f"✓ 成功完成月度事件规划")
                # 保存结果
                with open(final_timeline_path, 'w', encoding='utf-8') as f:
                    json.dump(final_timeline, f, ensure_ascii=False, indent=2)
                print(f"✓ 最终时间线已保存到: {final_timeline_path}")
            #步骤7: 处理月度详情
            print("\n=== 步骤7: 处理月度详情 ===")
            event_tree_path = os.path.join(meidan_path, "event_decompose_dfs.json")
            if os.path.exists(event_tree_path):
                print(f"✓ 月度详情文件已存在，直接读取: {event_tree_path}")
                with open(event_tree_path, 'r', encoding='utf-8') as f:
                    monthly_details = json.load(f)
            else:
                self.process_monthly_details(final_timeline['monthly_details'], meidan_path)
                print(f"✓ 成功处理月度详情")
                with open(event_tree_path, 'r', encoding='utf-8') as f:
                    monthly_details = json.load(f)
            # 步骤8: 生成每日状态
            print("\n=== 步骤8: 生成每日状态 ===")
            daily_draft_file = os.path.join(output_path, 'daily_draft.json')
            if os.path.exists(daily_draft_file):
                print(f"✓ 每日状态文件已存在，跳过生成: {daily_draft_file}")
            else:
                self.parallel_daily_event_refine(final_timeline["analysis_results"],self.persona,monthly_details,daily_draft_file)
                print(f"✓ 每日状态已保存到: {daily_draft_file}")

            # 步骤9: 调用check_event_matching.py进行事件匹配分析
            print("\n=== 步骤9: 事件匹配分析 ===")
            import event.tools.check_event_matching
            event_decompose_dfs_path = os.path.join(meidan_path, "event_decompose_dfs.json")
            new_event_tree_file = os.path.join(output_path, "event_tree.json")
            
            # 检查目标文件是否存在，如果存在则跳过
            if 0:
                print(f"✓ 事件匹配分析结果文件已存在，跳过生成: {new_event_tree_file}")
            else:
                print(f"正在调用check_event_matching.py，输入文件：")
                print(f"  - event_decompose_dfs.json: {event_decompose_dfs_path}")
                print(f"  - daily_draft.json: {daily_draft_file}")
                
                # 保存原始daily_draft.json为daily_draft_raw.json到meidan_path
                import shutil
                raw_daily_draft_path = os.path.join(meidan_path, "daily_draft_raw.json")
                shutil.copy2(daily_draft_file, raw_daily_draft_path)
                print(f"✓ 已将原始daily_draft.json保存为: {raw_daily_draft_path}")
                
                # 调用check_event_matching.py的main函数，传递输出路径
                event.tools.check_event_matching.main(
                    event_decompose_dfs_path=event_decompose_dfs_path,
                    daily_draft_path=daily_draft_file,
                    output_path=output_path
                )

                # 新生成的daily_draft.json已经保存在output_path，无需替换

            # 步骤10: 调用event_tree_classify.py进行event_tree文件的分类
            print("\n=== 步骤10: 事件树分类 ===")
            import event.tools.event_tree_classify
            # 使用步骤九生成的event_tree.json文件作为分类的目标文件
            event_tree_file = os.path.join(output_path, "event_tree.json")
            
            print(f"正在调用event_tree_classify.py，处理文件：")
            print(f"  - event_tree.json: {event_tree_file}")
            
            # 创建分类器实例
            classifier = event.tools.event_tree_classify.EventTreeClassifier()
            
            # 处理event_tree文件，直接输出到原文件
            classifier.process_events(event_tree_file, output_path=event_tree_file)
            print(f"✓ 已用分类结果替换原来的event_tree.json")
            

            print("\n🎉 年度时间线草稿生成完成！")
            print(f"除每日状态外的其他数据已保存到: {meidan_path}")
            print(f"每日状态数据已保存到: {daily_draft_file}")



        except Exception as e:
            print(f"\n❌ 生成年度时间线草稿时发生错误: {str(e)}")
            traceback.print_exc()
            
            # 保存错误信息到文件
            error_info = {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            error_path = os.path.join(meidan_path, "error_log.json")
            with open(error_path, 'w', encoding='utf-8') as f:
                json.dump(error_info, f, ensure_ascii=False, indent=2)
            print(f"❌ 错误信息已保存到: {error_path}")
            
            return None
    
    def monthly_analysis(self, timeline=None, persona=None, output_dir=None):
        """
        串行生成每个月的健康分析数据、生活分析数据、月度转换分析数据并保存
        
        参数:
            timeline: rich_timeline格式的数据，参考rich_timeline.json格式
            persona: 人物画像信息
            output_dir: 分析结果保存目录
        
        返回:
            包含所有月份分析结果的字典
        """
        import event.draft.event_refiner
        import json
        import os
        from datetime import datetime
        
        # 初始化EventRefiner实例
        refiner = event.draft.event_refiner.EventRefiner(persona, {})
        
        # 存储所有月份的分析结果
        all_analysis_results = {}
        
        # 处理输入参数
        # 验证timeline参数格式
        if not timeline or not isinstance(timeline, dict) or 'monthly_details' not in timeline:
            print("timeline必须是有效的rich_timeline格式数据，包含'monthly_details'字段")
            return all_analysis_results
        
        # 将rich_timeline格式转换为timeline格式
        rich_timeline = timeline
        timeline = []
        for month_data in rich_timeline.get('monthly_details', []):
            month_str = month_data.get('month', '')
            # 假设年份为2025，将"1月"转换为"2025-01"格式
            if month_str and '月' in month_str:
                month_num = int(month_str.replace('月', ''))
                month_key = f"2025-{month_num:02d}"
                
                # 提取事件数据
                events = month_data.get('events', [])
                
                # 构建timeline元素
                timeline_item = {
                    'month': month_key,
                    'events': events
                }
                timeline.append(timeline_item)
        
        print(f"成功转换 {len(timeline)} 个月的数据")
        
        # 验证转换后的timeline参数
        if not timeline or not isinstance(timeline, list):
            print("timeline必须包含有效的'monthly_details'数据")
            return all_analysis_results
            
        if not persona or not isinstance(persona, dict):
            print("persona必须是有效的人物画像字典")
            return all_analysis_results
            
        # 设置保存目录
        if output_dir and isinstance(output_dir, str):
            # 如果提供了保存目录参数，使用该目录
            output_dir = os.path.abspath(output_dir)
        else:
            # 否则使用默认目录
            output_dir = os.path.join(os.path.dirname(__file__), '../analysis_results')
            
        # 创建保存目录
        os.makedirs(output_dir, exist_ok=True)
        print(f"分析结果将保存到: {output_dir}")
        
        # 将timeline数组转换为字典格式，方便处理
        monthly_data = {}
        for month_item in timeline:
            if not isinstance(month_item, dict) or 'month' not in month_item:
                print("timeline中的元素必须包含'month'字段")
                continue
                
            month_key = month_item['month']
            monthly_data[month_key] = month_item
            
        print(f"成功加载 {len(monthly_data)} 个月的事件数据")
        
        # 如果没有获取到有效数据，返回空结果
        if not monthly_data:
            print("没有获取到有效的月度事件数据")
            return all_analysis_results
        
        # 遍历每个月的数据
        previous_analysis = None
        from concurrent.futures import ThreadPoolExecutor
        
        for month, month_data in sorted(monthly_data.items()):
            print(f"\n开始分析 {month} 月份的数据...")
            print(month_data)
            # 确保month_data包含必要的字段
            if not isinstance(month_data, dict) or 'events' not in month_data:
                print(f"{month} 月份数据格式不正确，跳过")
                continue
            
            # 准备初始状态数据
            initial_health_state = None
            if previous_analysis and 'health_analysis' in previous_analysis:
                try:
                    # 解析上个月的健康分析结果
                    import json
                    prev_health_data = json.loads(previous_analysis['health_analysis'])
                    initial_health_state = prev_health_data.get('end_of_month_state')
                    if initial_health_state:
                        print(f"使用上个月的健康最终状态作为 {month} 月份的初始状态")
                except Exception as e:
                    print(f"解析上个月健康状态时出错: {e}")
            
            initial_life_state = None
            if previous_analysis and 'life_analysis' in previous_analysis:
                initial_life_state = previous_analysis['life_analysis'].get('final_state')
                if initial_life_state:
                    print(f"使用上个月的生活最终状态作为 {month} 月份的初始状态")
            
            prev_transition_analysis = previous_analysis['transition_analysis'] if previous_analysis and 'transition_analysis' in previous_analysis else None
            
            # 使用线程池并行执行三个分析任务
            print(f"并行执行 {month} 月份的健康分析、生活分析和转换分析...")
            
            def run_health_analysis():
                print(f"健康分析线程开始执行 {month} 月份")
                result = refiner.health_analysis(month_data, persona, initial_state=initial_health_state)
                print(f"健康分析线程完成 {month} 月份")
                return result
            
            def run_life_analysis():
                print(f"生活分析线程开始执行 {month} 月份")
                result = refiner.life_analysis(month_data, persona, initial_state=initial_life_state)
                print(f"生活分析线程完成 {month} 月份")
                return result
            
            def run_transition_analysis():
                print(f"转换分析线程开始执行 {month} 月份")
                result = refiner.month_transition_analysis(month_data, persona, previous_analysis=prev_transition_analysis)
                print(f"转换分析线程完成 {month} 月份")
                return result
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                # 提交三个分析任务
                health_future = executor.submit(run_health_analysis)
                life_future = executor.submit(run_life_analysis)
                transition_future = executor.submit(run_transition_analysis)
                
                # 获取分析结果
                health_result = health_future.result()
                life_result = life_future.result()
                transition_result = transition_future.result()
            
            # 保存本月的分析结果
            month_results = {
                'month': month,
                'health_analysis': health_result,
                'life_analysis': life_result,
                'transition_analysis': transition_result
            }
            
            # 保存到字典中
            all_analysis_results[month] = month_results
            
            # 保存到文件
            month_output_file = os.path.join(output_dir, f"{month}_analysis.json")
            with open(month_output_file, 'w', encoding='utf-8') as f:
                json.dump(month_results, f, ensure_ascii=False, indent=2)
            print(f"{month} 月份分析结果已保存到: {month_output_file}")
            
            # 更新previous_analysis为当前月份的所有分析结果
            previous_analysis = {
                'health_analysis': health_result,
                'life_analysis': life_result,
                'transition_analysis': transition_result
            }
        
        # 保存所有月份的综合分析结果
        all_results_file = os.path.join(output_dir, f"all_months_analysis_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        with open(all_results_file, 'w', encoding='utf-8') as f:
            json.dump(all_analysis_results, f, ensure_ascii=False, indent=2)
        print(f"\n所有月份分析结果已保存到: {all_results_file}")
        
        return all_analysis_results
    
    def parallel_daily_event_refine(self, monthly_analysis_results: Dict[str, Dict], persona: Dict, timeline: List[Dict], output_dir: str = None) -> Dict[str, Dict]:
        """
        读取monthly_analysis的分析结果作为输入，先调用annual_event_refine，再并行对每个月数据执行daily_event_refine
        
        参数:
            monthly_analysis_results: monthly_analysis方法的输出结果，包含每个月的分析数据
            persona: 人物画像信息
            timeline: 事件时间线数据，直接传递给daily_event_refine处理，包含所有事件数据
            output_dir: 保存结果的路径（可选），可以是目录路径或JSON文件路径
            
        返回:
            包含每个月daily_event_refine结果的字典
        """
        from concurrent.futures import ThreadPoolExecutor
        import json
        from datetime import datetime, timedelta

        # 首先调用annual_event_refine
        print("开始执行年度事件调整...")
        from event.draft.event_refiner import EventRefiner
        refiner = EventRefiner(persona=persona, events=timeline)
        
        start_date = '2025-01-01'
        end_date = '2025-12-31'
        
        # # 调用annual_event_refine方法
        # refined_timeline = refiner.annual_event_refine(
        #     events=timeline,
        #     start_date=start_date,
        #     end_date=end_date,
        #     context="",
        #     max_workers=24
        # )
        # print("年度事件调整完成")
        refined_timeline = timeline
        # 定义一个辅助函数，用于对单个月份执行daily_event_refine
        def process_monthly_refine(month: str, analysis_results: Dict, refined_timeline: List[Dict], persona: Dict):
            """对单个月份执行daily_event_refine"""
            print(f"开始处理 {month} 月份的daily_event_refine...")
            
            # 从分析结果中提取必要数据
            health_analysis = analysis_results.get('health_analysis', {})
            life_analysis = analysis_results.get('life_analysis', {})
            
            # 确保health_analysis是字典格式
            if isinstance(health_analysis, str):
                try:
                    health_analysis = json.loads(health_analysis)
                except json.JSONDecodeError:
                    print(f"解析{month}月份健康分析结果失败，使用空数据")
                    health_analysis = {}
            elif not isinstance(health_analysis, dict):
                # 如果health_analysis既不是字符串也不是字典，使用空字典
                print(f"{month}月份健康分析结果格式不正确，使用空数据")
                health_analysis = {}
            
            # 确保life_analysis是字典格式
            if isinstance(life_analysis, str):
                try:
                    life_analysis = json.loads(life_analysis)
                except json.JSONDecodeError:
                    print(f"解析{month}月份生活分析结果失败，使用空数据")
                    life_analysis = {}
            elif not isinstance(life_analysis, dict):
                # 如果life_analysis既不是字符串也不是字典，使用空字典
                print(f"{month}月份生活分析结果格式不正确，使用空数据")
                life_analysis = {}
            
            # 计算月份的开始日期和结束日期
            month_parts = month.split('-')
            if len(month_parts) != 2:
                print(f"月份格式不正确: {month}")
                return month, None
            
            year, month_num = int(month_parts[0]), int(month_parts[1])
            
            # 计算该月的第一天
            start_date = datetime(year, month_num, 1)
            
            # 计算该月的最后一天
            if month_num == 12:
                next_month = datetime(year + 1, 1, 1)
            else:
                next_month = datetime(year, month_num + 1, 1)
            end_date = next_month - timedelta(days=1)
            
            # 格式化为YYYY-MM-DD字符串
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            # 计算分割日期（月中）
            mid_month = start_date + timedelta(days=14)  # 15号作为分割日期
            split_date_str = mid_month.strftime('%Y-%m-%d')
            
            # 创建EventRefiner实例，使用已调整的timeline数据初始化
            refiner = EventRefiner(persona=persona, events=refined_timeline)
            month_transition_data = analysis_results.get('transition_analysis')
            # 将health_analysis转换为JSON字符串

            
            # 调用daily_event_refine方法，传递refined_timeline数据和控制的日期范围
            refine_result = refiner.daily_event_refine(
                events=refined_timeline,
                start_date=start_date_str,
                end_date=end_date_str,
                persona=persona,
                split_date=split_date_str,
                health_result=health_analysis,
                life_result=life_analysis,
                month_transition_analysis=month_transition_data
            )
            
            print(f"完成处理 {month} 月份的daily_event_refine")
            
            # 计算该月份的天数
            month_days = (end_date - start_date).days + 1
            
            # 处理refine_result的两种可能格式
            dailylife_data = []
            if refine_result:
                if isinstance(refine_result, dict) and 'dailylife' in refine_result:
                    # 格式1: refine_result是包含dailylife键的字典
                    dailylife_data = refine_result['dailylife']
                elif isinstance(refine_result, list):
                    # 格式2: refine_result直接是数组
                    dailylife_data = refine_result
            
            # 检查数据完整性
            if dailylife_data and isinstance(dailylife_data, list):
                # 验证并标准化每个日期对象的格式

                # 比较数据长度与月份天数
                actual_length = len(dailylife_data)
                if actual_length != month_days:
                    print(f"✗ 月份 {month} 处理不完整，实际生成 {actual_length} 天数据，预期 {month_days} 天数据")
                    return month, None, []  # 标记为失败，返回空的更新操作
                else:
                    print(f"✓ 月份 {month} 处理完成，共 {actual_length} 天数据")
                    # 返回事件更新操作而不是整个事件列表
                    return month, refine_result, refiner.current_event_updates
            else:
                print(f"✗ 月份 {month} 处理失败，返回数据格式错误")
                return month, None, []  # 标记为失败，返回空的更新操作
        
        # 使用线程池并行处理每个月的数据
        all_refine_results = {}
        
        # 计算合适的线程数，最多24个线程
        max_workers = self.max_workers  # 最多24个线程，或等于月份数（如果月份数更少）
        
        def execute_parallel_months(months_to_process):
            """并行执行指定月份的处理"""
            temp_results = {}
            all_event_updates = []  # 收集所有线程的事件更新操作
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交任务
                futures = []
                for month in months_to_process:
                    analysis_results = monthly_analysis_results[month]
                    future = executor.submit(process_monthly_refine, month, analysis_results, refined_timeline, persona)
                    futures.append(future)
                
                # 收集结果
                for future in futures:
                    try:
                        month, result, event_updates = future.result()
                        if result:
                            temp_results[month] = result
                            if event_updates:
                                all_event_updates.extend(event_updates)
                    except Exception as e:
                        print(f"处理月份数据时出错: {e}")
            
            return temp_results, all_event_updates
        
        # 第一次执行：处理所有月份
        print("第一次并行处理所有月份...")
        all_refine_results, all_event_updates = execute_parallel_months(list(monthly_analysis_results.keys()))
        
        # 检查是否有月份处理失败
        all_months = set(monthly_analysis_results.keys())
        success_months = set(all_refine_results.keys())
        failed_months = sorted(list(all_months - success_months))
        
        if failed_months:
            print(f"\n发现{len(failed_months)}个月份处理失败: {', '.join(failed_months)}")
            print("正在重新并行处理这些月份...")
            
            # 第二次执行：仅处理失败的月份
            retry_results, retry_event_updates = execute_parallel_months(failed_months)
            
            # 合并重试结果
            all_refine_results.update(retry_results)
            # 合并重试的事件更新操作
            if retry_event_updates:
                all_event_updates.extend(retry_event_updates)
            
            # 再次检查是否还有失败的月份
            final_failed_months = sorted(list(all_months - set(all_refine_results.keys())))
            if final_failed_months:
                print(f"\n重试后仍有{len(final_failed_months)}个月份处理失败: {', '.join(final_failed_months)}")
            else:
                print("\n✅ 所有月份重试成功！")
        else:
            print("\n✅ 第一次处理所有月份都成功！")
        
        # 创建EventRefiner实例，应用所有事件更新操作
        if all_event_updates:
            print(f"\n应用所有事件更新操作，共{len(all_event_updates)}个更新")
            from event.draft.event_refiner import EventRefiner
            refiner = EventRefiner(persona=persona, events=refined_timeline)
            
            # 应用所有事件更新操作到原始事件树上
            refined_timeline = refiner.apply_event_updates(refined_timeline, all_event_updates)
            
            print("✅ 所有事件更新操作已应用到事件树")
        
        # # 保存所有月份的事件细化结果
        # all_refine_file = os.path.join(output_dir, f"all_months_event_refine_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        # with open(all_refine_file, 'w', encoding='utf-8') as f:
        #     json.dump(all_refine_results, f, ensure_ascii=False, indent=2)
        # print(f"\n所有月份事件细化结果已保存到: {all_refine_file}")
        
        # 生成每日状态文件
        # 检查output_dir是否是JSON文件路径
        # if output_dir and output_dir.endswith('.json'):
        #     daily_status_file = output_dir
        # else:
        #     daily_status_file = os.path.join(output_dir, 'daily_status.json')
            
        # 直接将月份字典格式的数据写入文件
        with open(output_dir, 'w', encoding='utf-8') as f:
            json.dump(all_refine_results, f, ensure_ascii=False, indent=2)
        print(f"每日状态数据已按月份字典格式保存到: {output_dir}")
        
        # 保存更新后的事件树到event_tree.json
        import os
        import json
        
        # 构建保存路径
        if os.path.isdir(output_dir):
            event_tree_path = os.path.join(output_dir, "event_tree.json")
        else:
            # 如果output_dir是文件路径，在同一目录下保存
            output_dir_path = os.path.dirname(output_dir)
            event_tree_path = os.path.join(output_dir_path, "event_tree.json")
        
        # 保存修改后的事件树
        with open(event_tree_path, 'w', encoding='utf-8') as f:
            json.dump(refined_timeline, f, ensure_ascii=False, indent=2)
        print(f"更新后的事件树已保存到: {event_tree_path}")
        
        return all_refine_results

    def convert_timeline_to_events_with_llm(self, timeline_data):
        """使用LLM将时间线数据转换为按主题分组的事件数组

        Args:
            timeline_data: 从test5.json加载的时间线数据

        Returns:
            按主题分组的事件二维数组，每个主题数组包含多个事件对象
        """
        import json
        from event.templates.template_scheduler import template_convert_timeline_to_events

        # 将timeline_data转换为JSON字符串
        timeline_json = json.dumps(timeline_data, ensure_ascii=False)

        # 构建提示
        prompt = template_convert_timeline_to_events.format(timeline_json=timeline_json)

        try:
            # 调用LLM
            print("正在调用LLM进行事件转换...")
            llm_output = self.llm_call_sr(prompt)

            # 提取并解析JSON
            try:
                # 使用remove_json_wrapper函数处理JSON字符串
                cleaned_json_str = self.remove_json_wrapper(llm_output, 'array')
                
                if not cleaned_json_str:
                    raise ValueError("未找到JSON数组内容")

                # 解析JSON
                events_by_theme = json.loads(cleaned_json_str)

                # 验证输出格式
                if not isinstance(events_by_theme, list):
                    raise ValueError("输出不是数组格式")

                # 检查每个主题对象的结构
                for i, theme_obj in enumerate(events_by_theme):
                    if not isinstance(theme_obj, dict):
                        raise ValueError(f"第{i + 1}个主题不是对象格式")

                    # 检查主题必要字段
                    if not all(key in theme_obj for key in ['theme_name', 'theme_description', 'events']):
                        raise ValueError(f"主题缺少必要字段: {theme_obj}")

                    # 检查事件数组
                    theme_events = theme_obj['events']
                    if not isinstance(theme_events, list):
                        raise ValueError(f"主题事件不是数组格式: {theme_obj['theme_name']}")

                    # 检查每个事件的结构
                    for j, event in enumerate(theme_events):
                        if not all(key in event for key in ['name', 'description', 'date']):
                            raise ValueError(f"主题 '{theme_obj['theme_name']}' 中第{j + 1}个事件缺少必要字段: {event}")

                print("事件转换成功！")
                
                # =====================新增逻辑：生成时间线格式数据=====================
                import json
                from event.templates.template_scheduler import template_generate_timeline_summaries
                
                # 1. 收集所有事件并按月份分组
                all_events = []
                for theme_obj in events_by_theme:
                    for event in theme_obj['events']:
                        # 添加事件所属主题信息
                        event_with_theme = event.copy()
                        event_with_theme['belongs_to_theme'] = theme_obj['theme_name']
                        all_events.append(event_with_theme)
                
                # 2. 按月份分组事件
                events_by_month = {}
                for event in all_events:
                    # 提取事件的起始月份 (YYYY-MM格式)
                    try:
                        start_date = event['date'].split('至')[0].strip()
                        month = start_date[:7]  # 取YYYY-MM格式
                        if month not in events_by_month:
                            events_by_month[month] = []
                        events_by_month[month].append(event)
                    except:
                        # 如果日期格式有问题，跳过此事件
                        continue
                
                # 3. 构建时间线数据结构
                timeline_data = {
                    "comprehensive_summary": "",
                    "monthly_details": []
                }
                
                # 按月份排序
                sorted_months = sorted(events_by_month.keys())
                
                for month in sorted_months:
                    month_data = {
                        "month": month,
                        "monthly_summary": "",
                        "events": events_by_month[month],
                        "impact": ""
                    }
                    timeline_data["monthly_details"].append(month_data)
                
                # 4. 调用LLM生成总结字段
                print("正在调用LLM生成时间线总结...")
                timeline_json = json.dumps(timeline_data, ensure_ascii=False, indent=2)
                prompt = template_generate_timeline_summaries.format(timeline_json=timeline_json)
                llm_output = self.llm_call_sr(prompt)
                
                # 提取并解析带总结的时间线数据
                try:
                    # 使用remove_json_wrapper函数处理JSON字符串
                    cleaned_json_str = self.remove_json_wrapper(llm_output, 'object')
                    if not cleaned_json_str:
                        raise ValueError("未找到JSON对象内容")
                    
                    # 解析单个JSON对象
                    full_timeline = json.loads(cleaned_json_str)
                    
                    if not full_timeline:
                        # 如果没有找到完整的JSON，使用原始结构
                        full_timeline = timeline_data
                    
                    print("时间线总结生成成功！")
                    
                    # 5. 返回事件数据和时间线数据
                    return {
                        "events_by_theme": events_by_theme,
                        "timeline_data": full_timeline
                    }
                except json.JSONDecodeError as e:
                    print(f"时间线JSON解析失败: {e}")
                    print(f"LLM输出: {llm_output}")
                    # 返回原始数据结构
                    return {
                        "events_by_theme": events_by_theme,
                        "timeline_data": timeline_data
                    }

            except json.JSONDecodeError as e:
                print(f"JSON解析失败: {e}")
                print(f"LLM输出: {llm_output}")
                raise
            except ValueError as e:
                print(f"输出格式验证失败: {e}")
                print(f"LLM输出: {llm_output}")
                raise

        except Exception as e:
            print(f"事件转换过程中出错: {e}")
            raise