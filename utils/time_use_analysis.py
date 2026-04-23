"""
时间利用统计分析脚本
基于《第三次全国时间利用调查方案》对指定人员的日常活动时间分配进行分析
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from utils.llm_call import llm_call_j


# 时间利用分类定义
TIME_USE_CATEGORIES = {
    "personal_physiological": {
        "code": "[2]",
        "name": "个人生理必需活动",
        "description": "包括睡觉休息、个人卫生护理、用餐或其他饮食、看病就医等活动"
    },
    "paid_work": {
        "code": "[7]",
        "name": "有酬劳动",
        "description": "包括劳动就业活动大类中除无酬实习等就业活动外的其他活动类别"
    },
    "unpaid_work": {
        "code": "[8]",
        "name": "无酬劳动",
        "description": "包括家务劳动、陪伴照料家人、购买商品或服务等活动大类以及劳动就业活动大类中的无酬实习等就业活动、社会交往大类中的公益志愿活动"
    },
    "leisure": {
        "code": "[9]",
        "name": "个人自由支配活动",
        "description": "包括运动健身、文化休闲娱乐等活动大类以及社会交往大类中除公益志愿活动外的其他活动类别"
    },
    "education": {
        "code": "[10]",
        "name": "学习培训",
        "description": "包括学习培训活动大类"
    },
    "transportation": {
        "code": "[11]",
        "name": "交通活动",
        "description": "包括交通出行活动大类"
    }
}


def parse_time_duration(date_str):
    """
    解析时间字符串并计算持续时间（分钟）
    格式: "2025-01-01 06:40:00至2025-01-01 08:00:00"
    """
    try:
        if '至' in date_str:
            start_str, end_str = date_str.split('至')
            start_time = datetime.strptime(start_str.strip(), "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(end_str.strip(), "%Y-%m-%d %H:%M:%S")
            duration_minutes = (end_time - start_time).total_seconds() / 60
            return duration_minutes
        else:
            # 如果只有一个时间点，返回0
            return 0
    except Exception as e:
        print(f"时间解析错误: {date_str}, 错误: {e}")
        return 0


def analyze_day_with_llm(day_events, persona_info=None, next_day_first_event=None):
    """
    使用LLM对一天的所有活动进行整体分析，直接返回时间分布统计
    
    Args:
        day_events: 一天的事件列表
        persona_info: 个人画像信息字典，包含 job, hobbies, description 字段
        next_day_first_event: 下一日的第一个事件（用于计算睡眠时间）
    """
    # 构建个人画像描述
    persona_text = ""
    if persona_info:
        persona_parts = []
        if persona_info.get('job'):
            persona_parts.append(f"职业: {persona_info['job']}")
        if persona_info.get('hobbies'):
            persona_parts.append(f"兴趣爱好: {persona_info['hobbies']}")
        if persona_info.get('description'):
            persona_parts.append(f"个人描述: {persona_info['description']}")
        if persona_parts:
            persona_text = "\n个人画像信息：\n" + "\n".join(persona_parts) + "\n"
    
    # 计算睡眠时间并创建睡眠活动
    sleep_event = None
    if day_events:
        try:
            # 获取今日最后一个事件的结束时间
            last_event = day_events[-1]
            last_date_str = last_event.get('date', [''])[0]
            if '至' in last_date_str:
                _, last_end_str = last_date_str.split('至')
                last_end_time = datetime.strptime(last_end_str.strip(), "%Y-%m-%d %H:%M:%S")
                
                # 获取下一日第一个事件的开始时间，如果没有则默认为第二天7点
                next_start_time = None
                if next_day_first_event:
                    next_date_str = next_day_first_event.get('date', [''])[0]
                    if '至' in next_date_str:
                        next_start_str, _ = next_date_str.split('至')
                        next_start_time = datetime.strptime(next_start_str.strip(), "%Y-%m-%d %H:%M:%S")
                
                # 如果没有下一日事件，默认为第二天7点
                if next_start_time is None:
                    from datetime import timedelta
                    next_start_time = last_end_time.replace(hour=7, minute=0, second=0) + timedelta(days=1)
                    print(f"未获取到下一日事件，默认使用第二天7:00作为起床时间")
                
                # 计算时间差（分钟）
                sleep_duration = (next_start_time - last_end_time).total_seconds() / 60
                
                if sleep_duration > 0:
                    # 创建睡眠活动
                    sleep_event = {
                        'name': f'睡觉休息',
                        'date': [f'{last_end_time.strftime("%Y-%m-%d %H:%M:%S")}至{next_start_time.strftime("%Y-%m-%d %H:%M:%S")}'],
                        'duration': sleep_duration,
                        'description': f'从今日{last_end_time.strftime("%H:%M")}到次日{next_start_time.strftime("%H:%M")}的睡眠时间',
                        'type': 'Sleep'
                    }
        except Exception as e:
            print(f"计算睡眠时间失败: {e}")
    
    # 构建一天的活动描述（包含睡眠活动）
    events_to_analyze = day_events.copy()
    if sleep_event:
        events_to_analyze.append(sleep_event)
    
    events_description = []
    for event in events_to_analyze:
        date_str = event.get('date', [''])[0]
        duration = parse_time_duration(date_str)
        events_description.append(
            f"- 活动: {event.get('name', '')}\n"
            f"  时间: {date_str}\n"
            f"  时长: {duration}分钟\n"
            f"  描述: {event.get('description', '')}\n"
            f"  类型: {event.get('type', '')}"
        )
    
    events_text = "\n\n".join(events_description)
    
    prompt = f"""请分析以下一天中所有活动的时间分配情况。
{persona_text}
当日事件列表：
{events_text}

时间利用分类标准：
- 个人生理必需活动：睡觉休息、个人卫生护理、用餐或其他饮食、看病就医等活动
- 有酬劳动：本职工作、正式就业活动（获得薪酬的工作），不包括无酬实习
- 无酬劳动：家务劳动、陪伴照料家人、购买商品或服务、帮朋友或他人做事、无酬实习、公益志愿活动、自己做饭、整理东西等非其他大类的各种杂务
- 个人自由支配活动：运动健身、文化休闲娱乐等活动大类以及社会交往大类中除公益志愿活动外的其他活动类别
- 学习培训：学习培训活动大类
- 交通活动：交通出行活动大类，不包括散步，步行，逛街

重要说明：
1. 每个事件可能包含多个不同类型的活动（例如"前往咖啡厅并享用早餐"包含交通和用餐）
2. 你需要仔细分析事件描述，将一个事件的总时长合理拆分到不同的时间利用类别中
3. 如果一个事件包含多种活动类型，请按实际活动内容拆分时长
4. 确保所有事件的总时长被完全分配，不要遗漏或重复计算
5. 交通出行应单独归类为"交通活动"，即使它是为了工作或社交
6. 工作相关的通勤也应归类为"交通活动"
7. 在家办公、会议等工作活动归类为"有酬劳动"
8. 运动健身归类为"个人自由支配活动"
9. 学习、备考、培训归类为"学习培训"
10. 用餐、洗漱、睡觉归类为"个人生理必需活动"
11. 家务、购物、照顾家人归类为"无酬劳动"
12. 社交聚会、娱乐休闲归类为"个人自由支配活动"

【关键规则：复合事件的时间分割】
当一个事件涉及多个类别的活动时，需要根据活动的重要性和持续时间进行合理分割：

规则A - 次要活动可忽略（持续时间 < 15分钟）：
如果某个活动在整个事件中占比较小且持续时间很短（小于15分钟），可以将其忽略，整个事件归入主要活动类别。
示例："8:00-12:00在西湖游览时同时处理突发工作信息"
- 分析：游览是主要活动（4小时），处理工作信息是次要活动（假设<14分钟）
- 决策：忽略短暂的工作处理，整个事件归类为"个人自由支配活动"，时长240分钟

规则B - 重要活动需分割（持续时间 >= 15分钟）：
如果某个活动在事件中占据显著时间（>=15分钟），必须将该事件分割为多个活动，分别归类。
示例："8:00-12:00在西湖游览时受伤去医务室处理"
- 分析：游览是主要活动，但健康护理也持续了较长时间
- 决策：分割为两个活动：
  * "西湖游览" -> "个人自由支配活动"，约180分钟（3小时）
  * "医务室处理伤口" -> "个人生理必需活动"，约60分钟（1小时）
  * 总时长保持240分钟不变

分割原则：
1. 根据事件描述推测各部分活动的合理时长占比
2. 短时间的附带活动（<15分钟）可以忽略，归入主要活动
3. 长时间的并行或串行活动（>=15分钟）必须分割统计
4. 分割后各类别时长之和必须等于原事件总时长
5. 在events列表中，该事件名称会出现在多个类别中

请以JSON格式返回时间分布统计结果，必须包含所有6个类别，没有活动的类别时长为0：
{{
    "个人生理必需活动": {{
        "total_minutes": 数值,
        "event_count": 数值,
        "events": ["活动名称1", "活动名称2"]
    }},
    "有酬劳动": {{
        "total_minutes": 数值,
        "event_count": 数值,
        "events": ["活动名称1"]
    }},
    "无酬劳动": {{
        "total_minutes": 数值,
        "event_count": 数值,
        "events": []
    }},
    "个人自由支配活动": {{
        "total_minutes": 数值,
        "event_count": 数值,
        "events": ["活动名称1", "活动名称2"]
    }},
    "学习培训": {{
        "total_minutes": 数值,
        "event_count": 数值,
        "events": []
    }},
    "交通活动": {{
        "total_minutes": 数值,
        "event_count": 数值,
        "events": ["活动名称1"]
    }}
}}

要求：
1. total_minutes是该类别所有活动时长的总和（包括从复合事件中拆分出来的部分）
2. event_count是涉及该类别的活动事件数量（一个事件如果包含多类活动，在各类别中都计数）
3. events列出涉及该类别的所有活动名称
4. 所有6个类别都必须出现在结果中，即使时长为0
5. 确保所有事件的时长都被正确统计和分配，各类别时长之和应等于所有事件总时长
6. 对于复合事件，要根据上述规则合理判断是否需要分割，并估算各部分活动的时长占比
7. 分割时要考虑活动的实际性质和持续时间，避免过度分割或遗漏重要活动
8. **重要：一天的总时长不能超过24小时（1440分钟），请合理推测和分配各活动的时长，确保所有类别时长之和不超过1440分钟**
"""
    
    try:
        #print("LLM调用开始...",prompt)
        response = llm_call_j(prompt)
        result = json.loads(response)
        return result
    except Exception as e:
        print(f"LLM调用失败: {e}")
        return None





def aggregate_daily_results(daily_results):
    """
    汇总多天的分析结果
    """
    # 初始化各分类的统计
    categories = [
        '个人生理必需活动',
        '有酬劳动',
        '无酬劳动',
        '个人自由支配活动',
        '学习培训',
        '交通活动'
    ]
    
    category_stats = {}
    for cat in categories:
        category_stats[cat] = {
            'total_minutes': 0,
            'total_hours': 0,
            'percentage': 0,
            'event_count': 0,
            'days_involved': 0,
            'daily_average_minutes': 0,
            'daily_average_hours': 0
        }
    
    total_minutes = 0
    total_days = len(daily_results)
    
    # 累加每天的结果
    for date, day_result in daily_results.items():
        for cat in categories:
            if cat in day_result:
                cat_data = day_result[cat]
                category_stats[cat]['total_minutes'] += cat_data.get('total_minutes', 0)
                category_stats[cat]['event_count'] += cat_data.get('event_count', 0)
                if cat_data.get('total_minutes', 0) > 0:
                    category_stats[cat]['days_involved'] += 1
                total_minutes += cat_data.get('total_minutes', 0)
    
    # 计算百分比、小时数和每日平均时长
    for cat in categories:
        category_stats[cat]['total_hours'] = round(float(category_stats[cat]['total_minutes']) / 60, 2)
        if total_minutes > 0:
            category_stats[cat]['percentage'] = round(
                (float(category_stats[cat]['total_minutes']) / float(total_minutes)) * 100, 2
            )
        # 计算每日平均时长
        if total_days > 0:
            category_stats[cat]['daily_average_minutes'] = round(
                float(category_stats[cat]['total_minutes']) / total_days, 2
            )
            category_stats[cat]['daily_average_hours'] = round(
                category_stats[cat]['daily_average_minutes'] / 60, 2
            )
    
    return category_stats


def process_person(person_name: str, data_root_path: str):
    """
    处理单个人的数据
    """
    print(f"\n{'='*60}")
    print(f"开始处理: {person_name}")
    print(f"{'='*60}")
    
    # 构建文件路径
    person_dir = os.path.join(data_root_path, person_name)
    daily_event_file = os.path.join(str(person_dir), 'daily_event.json')
    persona_file = os.path.join(str(person_dir), 'persona.json')
    
    # 检查文件是否存在
    if not os.path.exists(daily_event_file):
        print(f"错误: 文件不存在 - {daily_event_file}")
        return None
    
    # 读取个人画像信息
    persona_info = None
    if os.path.exists(persona_file):
        try:
            with open(persona_file, 'r', encoding='utf-8') as f:
                persona_data = json.load(f)
            # 提取需要的字段
            persona_info = {
                'job': persona_data.get('job', ''),
                'hobbies': persona_data.get('hobbies', ''),
                'description': persona_data.get('description', '')
            }
            print(f"成功加载个人画像信息")
        except Exception as e:
            print(f"读取个人画像失败: {e}")
    
    # 读取数据
    try:
        with open(daily_event_file, 'r', encoding='utf-8') as f:
            daily_events = json.load(f)
        print(f"成功加载 {len(daily_events)} 个活动记录")
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None
    
    # 按日期分组活动
    events_by_date = {}
    for event in daily_events:
        if event.get('date'):
            # 提取日期部分（YYYY-MM-DD）
            date_str = event['date'][0].split(' ')[0] if ' ' in event['date'][0] else event['date'][0]
            if date_str not in events_by_date:
                events_by_date[date_str] = []
            events_by_date[date_str].append(event)
    
    print(f"共涉及 {len(events_by_date)} 天的活动数据")
    
    # 准备每一天的下一日事件
    sorted_dates = sorted(events_by_date.keys())
    date_to_next_event = {}
    for i, date in enumerate(sorted_dates):
        if i + 1 < len(sorted_dates):
            next_date = sorted_dates[i + 1]
            # 获取下一日的第一个事件
            next_day_events = events_by_date[next_date]
            if next_day_events:
                date_to_next_event[date] = next_day_events[0]
    
    # 使用20线程并行分析每一天
    all_daily_results = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_date = {
            executor.submit(analyze_day_with_llm, day_events, persona_info, date_to_next_event.get(date)): date
            for date, day_events in sorted(events_by_date.items())
        }
        
        for future in as_completed(future_to_date):
            date = future_to_date[future]
            try:
                day_result = future.result()
                if day_result:
                    all_daily_results[date] = day_result
                    print(f"完成分析: {date}")
                else:
                    print(f"分析失败: {date}")
            except Exception as e:
                print(f"处理 {date} 时出错: {e}")
    
    # 汇总所有天的结果
    category_stats = aggregate_daily_results(all_daily_results)
    
    # 计算总时长
    total_minutes = sum(stats['total_minutes'] for stats in category_stats.values())
    
    # 生成报告
    report = {
        'person_name': person_name,
        'total_days': len(events_by_date),
        'analyzed_days': len(all_daily_results),
        'total_events': len(daily_events),
        'total_minutes': round(total_minutes, 2),
        'total_hours': round(total_minutes / 60, 2),
        'category_distribution': category_stats,
        'daily_details': all_daily_results
    }
    
    return report


def print_report(report):
    """
    打印分析报告
    """
    print(f"\n{'='*80}")
    print(f"时间利用分析报告 - {report['person_name']}")
    print(f"{'='*80}")
    print(f"统计天数: {report['total_days']} 天")
    print(f"已分析天数: {report['analyzed_days']} 天")
    print(f"活动总数: {report['total_events']} 个")
    print(f"总时长: {report['total_hours']} 小时 ({report['total_minutes']} 分钟)")
    print(f"{'-'*80}")
    print(f"{'分类名称':<20} {'时长(小时)':<12} {'时长(分钟)':<12} {'占比(%)':<10} {'活动数量':<10} {'涉及天数'}")
    print(f"{'-'*80}")
    
    for cat_name, stats in report['category_distribution'].items():
        print(f"{cat_name:<18} {stats['total_hours']:<12} {stats['total_minutes']:<12} "
              f"{stats['percentage']:<10} {stats['event_count']:<10} {stats['days_involved']}")
    
    print(f"{'='*80}\n")


def save_report(report, output_dir):
    """
    保存报告到文件
    """
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{report['person_name']}_time_analysis.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"报告已保存至: {output_file}")
    return output_file


def test_single_day(person_name: str, date: str, data_root_path: str):
    """
    测试单个人某一天的时间分配分析
    
    Args:
        person_name: 人员拼音名称
        date: 日期字符串，格式 YYYY-MM-DD
        data_root_path: 数据根路径
    """
    print(f"\n{'='*80}")
    print(f"测试单日分析 - {person_name} - {date}")
    print(f"{'='*80}")
    
    # 构建文件路径
    person_dir = os.path.join(data_root_path, person_name)
    daily_event_file = os.path.join(str(person_dir), 'daily_event.json')
    persona_file = os.path.join(str(person_dir), 'persona.json')
    
    # 检查文件是否存在
    if not os.path.exists(daily_event_file):
        print(f"错误: 文件不存在 - {daily_event_file}")
        return None
    
    # 读取个人画像信息
    persona_info = None
    if os.path.exists(persona_file):
        try:
            with open(persona_file, 'r', encoding='utf-8') as f:
                persona_data = json.load(f)
            # 提取需要的字段
            persona_info = {
                'job': persona_data.get('job', ''),
                'hobbies': persona_data.get('hobbies', ''),
                'description': persona_data.get('description', '')
            }
            print(f"成功加载个人画像信息")
            if persona_info['job']:
                print(f"职业: {persona_info['job']}")
            if persona_info['hobbies']:
                print(f"兴趣爱好: {persona_info['hobbies']}")
        except Exception as e:
            print(f"读取个人画像失败: {e}")
    
    # 读取数据
    try:
        with open(daily_event_file, 'r', encoding='utf-8') as f:
            daily_events = json.load(f)
        print(f"成功加载 {len(daily_events)} 个活动记录")
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None
    
    # 筛选指定日期的活动
    day_events = []
    for event in daily_events:
        if event.get('date'):
            event_date = event['date'][0].split(' ')[0] if ' ' in event['date'][0] else event['date'][0]
            if event_date == date:
                day_events.append(event)
    
    if not day_events:
        print(f"未找到 {date} 的活动数据")
        return None
    
    # 获取下一日的第一个事件
    next_day_first_event = None
    try:
        from datetime import timedelta
        current_date = datetime.strptime(date, "%Y-%m-%d")
        next_date = current_date + timedelta(days=1)
        next_date_str = next_date.strftime("%Y-%m-%d")
        
        for event in daily_events:
            if event.get('date'):
                event_date = event['date'][0].split(' ')[0] if ' ' in event['date'][0] else event['date'][0]
                if event_date == next_date_str:
                    next_day_first_event = event
                    break
        
        if next_day_first_event:
            print(f"找到下一日({next_date_str})的第一个事件: {next_day_first_event.get('name')}")
        else:
            print(f"警告: 未找到下一日({next_date_str})的事件，无法计算睡眠时间")
    except Exception as e:
        print(f"获取下一日事件失败: {e}")
    
    print(f"找到 {len(day_events)} 个活动")
    print(f"\n活动列表:")
    for i, event in enumerate(day_events, 1):
        duration = parse_time_duration(event['date'][0])
        print(f"{i}. {event.get('name')} ({duration}分钟)")
    
    # 调用LLM分析
    print(f"\n正在调用LLM分析...")
    result = analyze_day_with_llm(day_events, persona_info, next_day_first_event)
    
    if not result:
        print("LLM分析失败")
        return None
    
    # 打印结果
    print(f"\n{'='*80}")
    print(f"时间分配分析结果")
    print(f"{'='*80}")
    print(f"{'分类名称':<20} {'时长(分钟)':<12} {'时长(小时)':<12} {'活动数量'}")
    print(f"{'-'*80}")
    
    total_minutes = 0
    categories = [
        '个人生理必需活动',
        '有酬劳动',
        '无酬劳动',
        '个人自由支配活动',
        '学习培训',
        '交通活动'
    ]
    
    for cat in categories:
        if cat in result:
            cat_data = result[cat]
            minutes = cat_data.get('total_minutes', 0)
            hours = round(minutes / 60, 2)
            count = cat_data.get('event_count', 0)
            total_minutes += minutes
            print(f"{cat:<18} {minutes:<12} {hours:<12} {count}")
    
    print(f"{'-'*80}")
    print(f"{'总计':<18} {total_minutes:<12} {round(total_minutes/60, 2):<12}")
    print(f"{'='*80}")
    
    # 打印详细的活动归属
    print(f"\n各类别包含的活动:")
    for cat in categories:
        if cat in result and result[cat].get('events'):
            print(f"\n{cat}:")
            for event_name in result[cat]['events']:
                print(f"  - {event_name}")
    
    return result


def main():
    """
    主函数
    """
    # 配置参数
    data_root_path = r"D:\pyCharmProjects\pythonProject4\life_bench_data\data"
    output_dir = r"D:\pyCharmProjects\pythonProject4\output\time_analysis"
    
    # 输入要分析的人员名单（拼音）
    print("请输入要分析的人员名单（拼音），多个人员用逗号分隔")
    print("可用人员: fenghaoran, leimingxuan, lumingqiang, maxiulan, songyajing, sunyuwei, yemingxuan, yinhao, yuxiaowei, yuxiaowen")
    print("示例输入: fenghaoran,leimingxuan,lumingqiang")
    
    user_input = input("\n请输入人员名单: ").strip()
    
    if not user_input:
        print("未输入人员名单，退出程序")
        return
    
    # 解析人员名单
    person_names = [name.strip() for name in user_input.split(',') if name.strip()]
    
    if not person_names:
        print("无效的人员名单，退出程序")
        return
    
    print(f"\n即将分析 {len(person_names)} 位人员: {', '.join(person_names)}")
    confirm = input("确认开始分析？(y/n): ").strip().lower()
    
    if confirm != 'y':
        print("已取消分析")
        return
    
    # 处理每个人
    reports = []
    for person_name in person_names:
        try:
            report = process_person(person_name, data_root_path)
            if report:
                reports.append(report)
                print_report(report)
                save_report(report, output_dir)
        except Exception as e:
            print(f"处理 {person_name} 时发生错误: {e}")
            import traceback
            traceback.print_exc()
    
    # 汇总报告
    if len(reports) > 1:
        print(f"\n{'#'*80}")
        print(f"多人员对比汇总")
        print(f"{'#'*80}")
        print(f"{'人员姓名':<15} {'天数':<8} {'活动数':<10} {'总时长(小时)':<15}")
        print(f"{'-'*80}")
        for report in reports:
            print(f"{report['person_name']:<15} {report['total_days']:<8} "
                  f"{report['total_events']:<10} {report['total_hours']:<15}")
        print(f"{'#'*80}\n")


if __name__ == "__main__":
    #test_single_day("fenghaoran", "2025-01-01", r"D:\pyCharmProjects\pythonProject4\life_bench_data\data")
    main()
