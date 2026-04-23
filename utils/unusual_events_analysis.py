"""
分析每日事件中的不寻常、独特、稀少事件
"""
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.llm_call import llm_call_j


def analyze_unusual_events(day_events, persona_info=None):
    """
    使用LLM分析一天中的不寻常事件
    
    Args:
        day_events: 一天的事件列表
        persona_info: 个人画像信息（不包含relation字段）
    
    Returns:
        包含不寻常事件列表的字典
    """
    # 构建个人画像描述
    persona_text = ""
    if persona_info:
        persona_parts = []
        # 排除relation字段，只使用其他画像信息
        for key, value in persona_info.items():
            if key != 'relation' and value:
                persona_parts.append(f"{key}: {value}")
        if persona_parts:
            persona_text = "\n个人画像信息：\n" + "\n".join(persona_parts) + "\n"
    
    # 构建事件描述
    events_description = []
    for event in day_events:
        date_str = event.get('date', [''])[0]
        events_description.append(
            f"- 活动: {event.get('name', '')}\n"
            f"  时间: {date_str}\n"
            f"  描述: {event.get('description', '')}\n"
            f"  类型: {event.get('type', '')}"
        )
    
    events_text = "\n\n".join(events_description)
    
    prompt = f"""请分析以下一天中的事件，找出其中稀少、异常或意外的事件。

{persona_text}
当日事件列表：
{events_text}

判断标准（只统计以下类事件）：
1. **意外事件**：突发的、计划外的、不可预见的突发事件

需要排除的事件：
- 符合该人物画像的日常例行活动
- 常规的社交活动、休闲娱乐
- 普通的工作学习任务
- 虽然不常见但对该人群来说正常的事件

请以JSON格式返回结果：
{{
    "unusual_events": [
        {{
            "event_name": "事件名称",
            "reason": "为什么属于稀少/异常/意外事件的简短说明"
        }}
    ],
    "count": 不寻常事件的数量
}}

要求：
1. 严格基于画像信息判断稀少性，宁缺毋滥
2. reason要简明扼要，说明属于哪一类（稀少/异常/意外）及原因
3. 如果没有符合条件的事件，返回空列表和count为0
4. 重点关注与画像人群的典型行为差异较大的事件
"""
    
    try:
        response = llm_call_j(prompt)
        result = json.loads(response)
        return result
    except Exception as e:
        print(f"LLM调用失败: {e}")
        return None


def process_person_unusual_events(person_name, data_root_path):
    """
    处理一个人的所有天数，分析不寻常事件
    
    Args:
        person_name: 人员拼音名称
        data_root_path: 数据根路径
    
    Returns:
        包含统计结果的字典
    """
    print(f"\n{'='*80}")
    print(f"分析不寻常事件 - {person_name}")
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
            # 只提取指定字段
            allowed_fields = ['age', 'gender', 'education', 'job', 'belief', 'body', 'family', 'hobbies', 'description']
            persona_info = {key: persona_data.get(key, '') for key in allowed_fields if persona_data.get(key)}
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
            date_str = event['date'][0].split(' ')[0] if ' ' in event['date'][0] else event['date'][0]
            if date_str not in events_by_date:
                events_by_date[date_str] = []
            events_by_date[date_str].append(event)
    
    print(f"共涉及 {len(events_by_date)} 天的活动数据")
    print(f"开始并行分析每一天的不寻常事件...\n")
    
    # 使用20线程并行分析每一天
    all_daily_results = {}
    total_unusual_count = 0
    all_unusual_examples = []
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_date = {
            executor.submit(analyze_unusual_events, day_events, persona_info): date
            for date, day_events in sorted(events_by_date.items())
        }
        
        completed_count = 0
        for future in as_completed(future_to_date):
            date = future_to_date[future]
            completed_count += 1
            try:
                day_result = future.result()
                if day_result and day_result.get('unusual_events'):
                    unusual_events = day_result['unusual_events']
                    count = len(unusual_events)
                    total_unusual_count += count
                    
                    # 保存示例
                    for event in unusual_events:
                        all_unusual_examples.append({
                            'date': date,
                            'event_name': event.get('event_name', ''),
                            'reason': event.get('reason', '')
                        })
                    
                    all_daily_results[date] = {
                        'count': count,
                        'events': unusual_events
                    }
                    print(f"[{completed_count}/{len(events_by_date)}] {date}: 发现 {count} 个不寻常事件")
                else:
                    all_daily_results[date] = {'count': 0, 'events': []}
                    if completed_count % 10 == 0:
                        print(f"[{completed_count}/{len(events_by_date)}] {date}: 无不寻常事件")
            except Exception as e:
                print(f"处理 {date} 时出错: {e}")
    
    # 计算统计数据
    analyzed_days = len(all_daily_results)
    average_per_day = round(total_unusual_count / analyzed_days, 2) if analyzed_days > 0 else 0
    
    # 生成报告
    report = {
        'person_name': person_name,
        'total_days': len(events_by_date),
        'analyzed_days': analyzed_days,
        'total_unusual_events': total_unusual_count,
        'average_per_day': average_per_day,
        'daily_details': all_daily_results,
        'unusual_examples': all_unusual_examples[:50]  # 只保留前50个示例
    }
    
    return report


def print_report(report):
    """
    打印分析报告
    """
    print(f"\n{'='*80}")
    print(f"不寻常事件分析报告 - {report['person_name']}")
    print(f"{'='*80}")
    print(f"总天数: {report['total_days']} 天")
    print(f"已分析天数: {report['analyzed_days']} 天")
    print(f"不寻常事件总数: {report['total_unusual_events']} 个")
    print(f"平均每天不寻常事件数: {report['average_per_day']} 个")
    print(f"{'='*80}\n")
    
    # 打印示例
    if report.get('unusual_examples'):
        print(f"不寻常事件示例（前{len(report['unusual_examples'])}个）:")
        print(f"{'-'*80}")
        for i, example in enumerate(report['unusual_examples'], 1):
            print(f"{i}. [{example['date']}] {example['event_name']}")
            print(f"   原因: {example['reason']}")
        print(f"{'='*80}\n")


def save_report(report, output_dir):
    """
    保存报告到文件
    """
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{report['person_name']}_unusual_events.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"报告已保存至: {output_file}")
    return output_file


def test_seven_days(person_name, start_date, data_root_path):
    """
    测试一个人七天的不寻常事件分析
    
    Args:
        person_name: 人员拼音名称
        start_date: 开始日期，格式 YYYY-MM-DD
        data_root_path: 数据根路径
    """
    from datetime import datetime, timedelta
    
    print(f"\n{'='*80}")
    print(f"测试七天不寻常事件分析 - {person_name}")
    print(f"开始日期: {start_date}")
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
    
    # 计算七天的日期
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    dates = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    
    print(f"\n分析日期范围: {dates[0]} 至 {dates[-1]}")
    print(f"{'='*80}\n")
    
    # 逐天分析
    total_unusual_count = 0
    all_unusual_examples = []
    
    for date in dates:
        print(f"\n处理日期: {date}")
        print(f"{'-'*80}")
        
        # 筛选该日期的事件
        day_events = []
        for event in daily_events:
            if event.get('date'):
                event_date = event['date'][0].split(' ')[0] if ' ' in event['date'][0] else event['date'][0]
                if event_date == date:
                    day_events.append(event)
        
        if not day_events:
            print(f"  未找到 {date} 的事件数据")
            continue
        
        print(f"  找到 {len(day_events)} 个事件")
        
        # 调用LLM分析
        result = analyze_unusual_events(day_events, persona_info)
        
        if result and result.get('unusual_events'):
            unusual_events = result['unusual_events']
            count = len(unusual_events)
            total_unusual_count += count
            
            print(f"  发现 {count} 个不寻常事件:")
            for event in unusual_events:
                print(f"    - {event.get('event_name', '')}")
                print(f"      原因: {event.get('reason', '')}")
                all_unusual_examples.append({
                    'date': date,
                    'event_name': event.get('event_name', ''),
                    'reason': event.get('reason', '')
                })
        else:
            print(f"  未发现不寻常事件")
    
    # 计算统计
    analyzed_days = len([d for d in dates if any((e.get('date', [''])[0] if isinstance(e.get('date'), list) else e.get('date', '')).split(' ')[0] == d for e in daily_events)])
    average_per_day = round(total_unusual_count / 7, 2) if analyzed_days > 0 else 0
    
    # 打印汇总
    print(f"\n{'='*80}")
    print(f"七天分析汇总")
    print(f"{'='*80}")
    print(f"分析天数: 7 天")
    print(f"不寻常事件总数: {total_unusual_count} 个")
    print(f"平均每天不寻常事件数: {average_per_day} 个")
    print(f"{'='*80}\n")
    
    return {
        'person_name': person_name,
        'start_date': start_date,
        'end_date': dates[-1],
        'total_unusual_events': total_unusual_count,
        'average_per_day': average_per_day,
        'examples': all_unusual_examples
    }


def main():
    """
    主函数
    """
    # 配置参数
    data_root_path = r"D:\pyCharmProjects\pythonProject4\life_bench_data\data"
    output_dir = r"D:\pyCharmProjects\pythonProject4\output\unusual_events"
    
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
            report = process_person_unusual_events(person_name, data_root_path)
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
        print(f"{'人员姓名':<15} {'天数':<8} {'不寻常事件总数':<15} {'平均每天'}")
        print(f"{'-'*80}")
        for report in reports:
            print(f"{report['person_name']:<15} {report['total_days']:<8} "
                  f"{report['total_unusual_events']:<15} {report['average_per_day']}")
        print(f"{'#'*80}\n")


if __name__ == "__main__":
    #test_seven_days('fenghaoran', '2025-05-01', r"D:\pyCharmProjects\pythonProject4\life_bench_data\data")
    main()