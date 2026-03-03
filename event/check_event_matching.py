import json
import os
import concurrent.futures
from collections import defaultdict
from datetime import datetime, timedelta
from utils.llm_call import llm_call_reason_j, llm_call_j

# 分析日期范围
START_DATE = datetime.strptime("2025-01-01", "%Y-%m-%d")
END_DATE = datetime.strptime("2025-12-31", "%Y-%m-%d")

# 判断日期是否在分析范围内
def is_date_in_range(date_str):
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return START_DATE <= date <= END_DATE
    except ValueError:
        return False

# 读取事件树数据
def load_event_decompose_dfs(file_path=None):
    if file_path is None:
        file_path = r"D:\pyCharmProjects\pythonProject4\data\fenghaoran\event_tree.json"
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 读取每日草稿数据
def load_daily_draft(file_path=None):
    if file_path is None:
        file_path = r"D:\pyCharmProjects\pythonProject4\data\fenghaoran\daily_draft.json"
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 提取所有最底层事件（decompose为0的事件）
def extract_bottom_events(event_data):
    bottom_events = []
    
    def traverse_events(events):
        for event in events:
            if event.get('decompose') == 1 and 'subevent' in event:
                # 递归处理子事件
                traverse_events(event['subevent'])
            else:
                # 这是一个最底层事件
                bottom_events.append(event)
    
    traverse_events(event_data)
    return bottom_events

# 构建每日事件映射（日期 -> 当日事件列表）
def build_daily_events_map(daily_data):
    daily_map = {}
    
    for month, days in daily_data.items():
        for day in days:
            date = day['date']
            daily_map[date] = day['events']
    
    return daily_map

# 使用LLM分析事件匹配情况
def analyze_event_matching(bottom_event, expanded_events, original_date):
    # 准备提示词
    try:
        prompt = """
        你是一名事件匹配分析专家，请严格按照以下要求分析事件匹配情况：
        
        ## 分析任务
         判断需要匹配的事件是否在指定日期范围的事件集合中存在对应的相似事件，并严格返回匹配到的事件的**完整原始名称**。
        
        ## 输入数据
        1. **需要匹配的事件**：
           - 事件名称：{event_name}
           - 事件描述：{event_desc}
        
        2. **原始目标日期**：{original_date}
        
        3. **扩展日期范围的事件集合**（包含原始日期前后3天内的所有事件）：
           {expanded_events_json}
        
        ## 分析标准
        - **匹配条件**：在扩展日期范围内存在与需要匹配的事件在**核心内容、主要人物、关键活动**等核心要素上相似或相关联的事件。
          - 重点关注事件的**核心活动内容**和**主要参与人物**
          - 可以忽略**具体的执行时间**（如下午跑步改为晚上跑步视为匹配）
          - 可以忽略**具体的执行方式**（如室内跑步改为户外跑步视为匹配）
          - 可以忽略**细节描述的差异，一些环节的缺失，或有相关平替事件，不需要再安排该事件（如某日已经有运动事件，可代替原运动事件，避免不合理重复）**
        - **不匹配条件**：扩展日期范围内所有事件与需要匹配的事件在核心要素上无关联或关联度极低
        
        ## 关键要求：严格的事件名称匹配
        - **必须严格返回扩展日期事件集合中存在的**完整原始事件名称**，不能进行任何修改、简化或概括**
        - 例如：如果扩展日期事件集合中有"晚上在健身房跑步30分钟"，就必须返回完整的"晚上在健身房跑步30分钟"，而不能返回"跑步"或"健身房跑步"
        - 如果没有找到匹配，返回null
        
        ## 输出要求
        请以JSON格式返回分析结果，包含以下字段：
        - `matched`：布尔值，表示是否找到匹配的事件
        - `reason`：字符串，详细说明匹配或不匹配的判断依据，包括：
          - 核心要素的匹配情况
          - 匹配事件的完整名称（如果找到）
          - 匹配事件所在的具体日期
        - `matched_event_name`：字符串或null，**必须严格返回扩展日期事件集合中匹配事件的完整原始名称**，不能做任何修改；否则返回null
        - `actual_date`：字符串或null，如果找到匹配，返回匹配事件发生的实际日期；否则返回null
        - `action`：字符串，可选值为"keep"、"rewrite"、"delete"或"keep_important"
          - `keep`：保留原底层事件（匹配成功且内容方式无重大变化）
          - `rewrite`：需要重写原底层事件（匹配成功但发生的内容方式发生明显变化，或发生时间、地点发生变化，若发生日期出现不同则必须重写日期）
          - `delete`：需要删除原底层事件（匹配失败且该事件在这段时间附近发生不合理或没必要）
          - `keep_important`：虽然匹配失败，但该事件具有一定重要性所以不删除
        - `rewrite_suggestion`：JSON对象或null，如果需要重写，提供完整的重写后事件JSON；否则返回null。格式必须与原事件结构一致，包含所有必要字段。
        - `match_details`：对象，提供详细的匹配信息：
          - `matched_date`：字符串，匹配事件所在的具体日期
          - `matched_event_full_info`：对象，匹配事件的完整信息（从扩展日期事件集合中直接复制）
        
        ## 输出示例
        ```json
        {{
            "matched": true,
            "reason": "日期'2025-01-02'的事件'与家人的新年视频通话'与需要匹配的事件'与母亲的视频通话'核心内容一致，都包含与母亲的视频通话行为，且人物要素匹配",
            "matched_event_name": "与家人的新年视频通话",
            "actual_date": "2025-01-02",
            "action": "keep",
            "rewrite_suggestion": null,
            "match_details": {{
                "matched_date": "2025-01-02",
                "matched_event_full_info": {{
                    "name": "与家人的新年视频通话",
                    "description": "与家人进行视频通话，庆祝新年",
                    "participant": [
                        {{
                            "name": "冯浩然",
                            "relation": "自己"
                        }}
                    ],
                    "location": "家中"
                }}
            }}
        }}
        ```
        
        ```json
        {{
            "matched": true,
            "reason": "日期'2025-03-15'的事件'晚上在健身房跑步30分钟'与需要匹配的事件'下午户外跑步30分钟'核心活动都是跑步，但执行时间和地点发生重大变化",
            "matched_event_name": "晚上在健身房跑步30分钟",
            "actual_date": "2025-03-15",
            "action": "rewrite",
            "rewrite_suggestion": {{
                "event_id": "1-2-3",
                "name": "晚上在健身房跑步30分钟",
                "date": ["2025-03-15"],
                "type": "Health",
                "description": "晚上在健身房跑步30分钟，保持健康锻炼习惯",
                "participant": [
                    {{
                        "name": "冯浩然",
                        "relation": "自己"
                    }}
                ],
                "location": "健身房",
                "decompose": 0
            }},
            "match_details": {{
                "matched_date": "2025-03-15",
                "matched_event_full_info": {{
                    "name": "晚上在健身房跑步30分钟",
                    "description": "晚上在健身房进行了30分钟的跑步锻炼",
                    "participant": [
                        {{
                            "name": "冯浩然",
                            "relation": "自己"
                        }}
                    ],
                    "location": "健身房"
                }}
            }}
        }}
        ```
        
        ```json
        {{
            "matched": false,
            "reason": "原始日期'2025-01-15'前后3天内的所有事件都不包含需要匹配的事件'与朋友聚餐'，且该事件在这段时间发生不合理",
            "matched_event_name": null,
            "actual_date": null,
            "action": "delete",
            "rewrite_suggestion": null,
            "match_details": null
        }}
        ```
        
        ```json
        {{
            "matched": false,
            "reason": "原始日期'2025-01-20'前后3天内的所有事件都不包含需要匹配的事件'项目重要会议'，但该会议具有重要性需要保留",
            "matched_event_name": null,
            "actual_date": null,
            "action": "keep_important",
            "rewrite_suggestion": null,
            "match_details": null
        }}
        ```
        """
        
        # 使用字符串格式化避免f-string的转义问题
        prompt = prompt.format(
            event_name=bottom_event['name'],
            event_desc=bottom_event['description'],
            original_date=original_date,
            expanded_events_json=json.dumps(expanded_events, ensure_ascii=False, indent=2)
        )
        
        response = llm_call_j(prompt)
        
        # 清理响应，移除可能的代码块标记
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        if response.endswith('```'):
            response = response[:-3]
        response = response.strip()
        
        result = json.loads(response)
        
        # 确保返回结果包含所有必要字段
        if 'actual_date' not in result:
            result['actual_date'] = None
        
        if 'matched_event_name' not in result:
            result['matched_event_name'] = None
        
        # 确保action字段存在且有效
        if 'action' not in result or result['action'] not in ['keep', 'rewrite', 'delete', 'keep_important']:
            # 默认值：匹配成功则keep，失败则delete
            result['action'] = 'keep' if result['matched'] else 'delete'
        
        # 当发现事件发生在其他日期时，一定要执行rewrite操作
        if result['matched'] and result['actual_date'] and result['actual_date'] != original_date:
            result['action'] = 'rewrite'
            # 如果需要重写，确保rewrite_suggestion存在
            if not result.get('rewrite_suggestion'):
                result['rewrite_suggestion'] = {}
            # 确保rewrite_suggestion中的日期为实际日期
            if 'date' in bottom_event:
                if isinstance(bottom_event['date'], list):
                    result['rewrite_suggestion']['date'] = [result['actual_date']]
                else:
                    result['rewrite_suggestion']['date'] = result['actual_date']
        
        # 确保rewrite_suggestion字段存在
        if 'rewrite_suggestion' not in result:
            result['rewrite_suggestion'] = None
        
        # 处理rewrite_suggestion，确保保留全部字段，对于缺失的字段取原值填入，且不要改写event_id
        if result.get('action') == 'rewrite':
            # 如果LLM返回了rewrite_suggestion，使用它作为基础
            if 'rewrite_suggestion' in result and result['rewrite_suggestion']:
                rewrite_suggestion = result['rewrite_suggestion']
            else:
                # 如果LLM没有返回rewrite_suggestion，创建一个空对象
                rewrite_suggestion = {}
            
            # 确保保留原事件的所有字段，对于缺失的字段取原值填入
            for key, value in bottom_event.items():
                if key not in rewrite_suggestion:
                    rewrite_suggestion[key] = value
            
            # 确保event_id与原事件一致，不要改写
            if 'event_id' in bottom_event:
                rewrite_suggestion['event_id'] = bottom_event['event_id']
            
            # 更新result中的rewrite_suggestion
            result['rewrite_suggestion'] = rewrite_suggestion
        
        # 确保match_details字段存在
        if 'match_details' not in result:
            result['match_details'] = None
        
        return result
    except json.JSONDecodeError as e:
        error_msg = f"JSON解析错误: {str(e)}"
        print(f"分析事件时出错 ({bottom_event['name']}): {error_msg}")
        print(f"原始响应: {response[:200]}...")
        return {
            "matched": False,
            "reason": error_msg,
            "matched_event_name": None,
            "actual_date": None,
            "action": "delete",  # 解析错误时默认删除
            "rewrite_suggestion": None,
            "match_details": None
        }
    except Exception as e:
        error_msg = f"分析过程中发生错误: {str(type(e).__name__)}: {str(e)}"
        print(f"分析事件时出错 ({bottom_event['name']}): {error_msg}")
        return {
            "matched": False,
            "reason": error_msg,
            "matched_event_name": None,
            "actual_date": None,
            "action": "delete",  # 发生错误时默认删除
            "rewrite_suggestion": None,
            "match_details": None
        }

# 获取日期前后N天的所有日期
def get_date_range(date_str, days_before=3, days_after=3):
    """获取指定日期前后N天的所有日期"""
    base_date = datetime.strptime(date_str, "%Y-%m-%d")
    date_range = []
    
    # 添加前N天
    for i in range(days_before, 0, -1):
        target_date = base_date - timedelta(days=i)
        date_range.append(target_date.strftime("%Y-%m-%d"))
    
    # 添加当天
    date_range.append(date_str)
    
    # 添加后N天
    for i in range(1, days_after + 1):
        target_date = base_date + timedelta(days=i)
        date_range.append(target_date.strftime("%Y-%m-%d"))
    
    return date_range

# 单个分析任务函数
def analyze_single_task(event, date_str, daily_events_map):
    """单个分析任务的包装函数"""
    # 处理日期范围格式（如"2025-01-19至2025-01-19"）
    if '至' in date_str:
        start_date, end_date = date_str.split('至')
        # 这里简化处理，只检查开始日期
        original_date = start_date.strip()
    else:
        original_date = date_str.strip()
    
    # 获取原始日期前后各3天的日期范围
    expanded_dates = get_date_range(original_date)
    
    # 收集扩展日期范围内的所有事件，按日期分组
    expanded_events = {}
    for date in expanded_dates:
        if date in daily_events_map:
            expanded_events[date] = daily_events_map[date]
    
    if not expanded_events:
        return {
            "event": event,
            "date": original_date,
            "analysis": {
                "matched": False,
                "reason": f"原始日期 {original_date} 前后3天内没有事件数据",
                "matched_event_name": None,
                "actual_date": None
            }
        }
    
    # 使用LLM分析扩展日期范围内的事件匹配情况
    analysis_result = analyze_event_matching(event, expanded_events, original_date)
    
    return {
        "event": event,
        "date": original_date,
        "analysis": analysis_result
    }

# 主函数
def main(event_decompose_dfs_path=None, daily_draft_path=None, output_path=None):
    # 加载数据
    event_data = load_event_decompose_dfs(event_decompose_dfs_path)
    daily_data = load_daily_draft(daily_draft_path)
    
    # 提取最底层事件
    bottom_events = extract_bottom_events(event_data)
    print(f"总共提取到 {len(bottom_events)} 个最底层事件")
    
    # 构建每日事件映射
    daily_events_map = build_daily_events_map(daily_data)
    print(f"总共加载了 {len(daily_events_map)} 天的每日事件")
    
    # 收集所有需要分析的任务（只处理分析日期范围内的事件）
    tasks = []
    for event in bottom_events:
        # 提取事件日期
        event_dates = event.get('date', [])
        event_id = event.get('event_id', '未知ID')
        if not event_dates:
            print(f"事件ID: {event_id} - {event['name']} 没有日期信息，跳过")
            continue
        
        # 为每个日期创建一个任务，只处理在分析范围内的日期
        for date_str in event_dates:
            # 处理日期范围格式
            if '至' in date_str:
                start_date, end_date = date_str.split('至')
                date = start_date.strip()
            else:
                date = date_str.strip()
            
            # 只处理在分析范围内的日期
            if is_date_in_range(date):
                tasks.append((event, date_str, daily_events_map))
            else:
                print(f"事件ID: {event_id} - {event['name']} 的日期 {date} 不在分析范围内 (2025-01-01 至 2025-03-31)，跳过")
    
    # 按日期排序任务
    def get_task_date(task):
        event, date_str, _ = task
        if '至' in date_str:
            start_date, end_date = date_str.split('至')
            date = start_date.strip()
        else:
            date = date_str.strip()
        return date
    
    tasks.sort(key=get_task_date)
    
    # 使用24线程并行分析
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as executor:
        # 提交所有任务
        future_to_task = {executor.submit(analyze_single_task, *task): task for task in tasks}
        
        # 收集结果
        for future in concurrent.futures.as_completed(future_to_task):
            try:
                result = future.result()
                results.append(result)
                
                # 获取事件ID
                event_id = result['event'].get('event_id', '未知ID')
                
                # 输出进度信息，包含事件ID
                if result['analysis']['matched']:
                    actual_date = result['analysis'].get('actual_date', result['date'])
                    if actual_date != result['date']:
                        print(f"✓ 事件ID: {event_id} - '{result['event']['name']}' 原计划日期 {result['date']}，实际在 {actual_date} 找到匹配")
                    else:
                        print(f"✓ 事件ID: {event_id} - '{result['event']['name']}' 在 {result['date']} 找到匹配")
                else:
                    print(f"✗ 事件ID: {event_id} - '{result['event']['name']}' 在 {result['date']} 未找到匹配")
            except Exception as e:
                print(f"分析任务出错: {e}")
    
    # 按事件ID分组统计结果，同一事件只要有一个日期匹配成功即算成功
    event_results = {}
    
    for result in results:
        event = result['event']
        event_id = event.get('event_id', '未知ID')
        
        if event_id not in event_results:
            event_results[event_id] = {
                'event': event,
                'total_dates': 0,
                'matched_dates': 0,
                'results': []
            }
        
        event_results[event_id]['total_dates'] += 1
        event_results[event_id]['results'].append(result)
        
        if result['analysis']['matched']:
            event_results[event_id]['matched_dates'] += 1
    
    # 统计按事件分组的结果
    total_events = len(event_results)
    matched_events = sum(1 for result in event_results.values() if result['matched_dates'] > 0)
    unmatched_events = total_events - matched_events
    
    # 输出统计结果
    print(f"\n分析完成！")
    print(f"总事件数: {total_events}")
    print(f"匹配成功的事件数: {matched_events}")
    print(f"未匹配的事件数: {unmatched_events}")
    print(f"总日期任务数: {len(results)}")
    print(f"匹配成功的日期数: {sum(1 for r in results if r['analysis']['matched'])}")
    
    if total_events > 0:
        print(f"事件匹配率: {matched_events / total_events * 100:.2f}%")
    else:
        print(f"事件匹配率: 0.00%")
    
    # 保存结果，包含原始详细结果和按事件分组的汇总
    output_file = "event_matching_results.json"
    
    # 创建结果结构
    final_result = {
        "summary": {
            "total_events": total_events,
            "matched_events": matched_events,
            "unmatched_events": unmatched_events,
            "total_date_tasks": len(results),
            "matched_date_tasks": sum(1 for r in results if r['analysis']['matched']),
            "event_matching_rate": (matched_events / total_events * 100) if total_events > 0 else 0.0
        },
        "event_results": event_results,
        "date_results": results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存到: {output_file}")
    print("\n结果文件包含以下内容:")
    print("- summary: 汇总统计信息")
    print("- event_results: 按事件ID分组的结果")
    print("- date_results: 原始的按日期匹配的详细结果")
    
    # 基于分析结果重写event_tree数据
    print("\n正在基于分析结果重写event_tree数据...")
    
    # 构建事件操作映射
    event_actions = {}
    for event_id, result in event_results.items():
        # 查找该事件的最终操作（如果有多个日期任务，取第一个有操作的结果）
        final_action = "keep"  # 默认保留
        final_suggestion = None
        
        for task_result in result['results']:
            if 'action' in task_result['analysis']:
                final_action = task_result['analysis']['action']
                final_suggestion = task_result['analysis'].get('rewrite_suggestion', None)
                break  # 取第一个有操作的结果
        
        event_actions[event_id] = {
            "action": final_action,
            "rewrite_suggestion": final_suggestion
        }
    
    # 重写event_tree数据
    def update_event_tree(tree_data, actions):
        """递归更新事件树"""
        updated_tree = []
        
        for item in tree_data:
            if isinstance(item, dict):
                # 检查是否是最底层事件
                if item.get('decompose') == 0:
                    event_id = item.get('event_id', '')
                    
                    if event_id in actions:
                        action = actions[event_id]['action']
                        
                        if action == "delete":
                            continue  # 删除该事件
                        elif action == "rewrite":
                            # 重写事件，使用JSON格式的建议
                            suggestion = actions[event_id]['rewrite_suggestion']
                            if suggestion and isinstance(suggestion, dict):
                                # 确保保留原事件的所有字段，对于缺失的字段取原值填入
                                for key, value in item.items():
                                    if key not in suggestion:
                                        suggestion[key] = value
                                # 确保event_id与原事件一致，不要改写
                                if 'event_id' in item:
                                    suggestion['event_id'] = item['event_id']
                                # 使用完整的重写建议JSON
                                updated_tree.append(suggestion)
                            else:
                                # 如果重写建议格式不正确，保留原事件
                                updated_tree.append(item)
                        else:  # keep 或 keep_important
                            updated_tree.append(item)
                    else:
                        updated_tree.append(item)
                else:
                    # 递归处理包含子事件的事件
                    if 'subevent' in item:
                        updated_subevents = update_event_tree(item['subevent'], actions)
                        if updated_subevents:
                            updated_item = item.copy()
                            updated_item['subevent'] = updated_subevents
                            updated_tree.append(updated_item)
                        else:
                            # 如果所有子事件都被删除，该事件也不再保留
                            continue
                    else:
                        updated_tree.append(item)
        
        return updated_tree
    
    # 应用更新
    updated_event_tree = update_event_tree(event_data, event_actions)
    
    # 保存更新后的event_tree
    if output_path:
        output_tree_file = os.path.join(output_path, "event_tree.json")
    else:
        output_tree_file = r"D:\pyCharmProjects\pythonProject4\data\fenghaoran\event_tree2.json"
    with open(output_tree_file, 'w', encoding='utf-8') as f:
        json.dump(updated_event_tree, f, ensure_ascii=False, indent=2)
    
    print(f"\nevent_tree重写完成！")
    print(f"更新后的event_tree已保存到: {output_tree_file}")
    
    # 统计操作结果
    action_counts = {"keep": 0, "rewrite": 0, "delete": 0, "keep_important": 0}
    for action_data in event_actions.values():
        action_counts[action_data['action']] += 1
    
    print(f"\n事件操作统计:")
    print(f"- 保留事件数 (匹配成功): {action_counts['keep']}")
    print(f"- 保留重要事件数 (匹配失败但重要): {action_counts['keep_important']}")
    print(f"- 重写事件数: {action_counts['rewrite']}")
    print(f"- 删除事件数: {action_counts['delete']}")
    
    # 从分析结果中提取匹配关系
    # 构建(日期, 事件名称)与event_id的映射，确保精确匹配
    event_date_name_to_id = defaultdict(list)
    
    for result in results:
        if result['analysis']['matched']:
            # 获取event_tree中的事件ID
            event_tree_id = result['event'].get('event_id', '')
            
            # 获取匹配到的事件名称和实际日期
            matched_event_name = result['analysis'].get('matched_event_name', '')
            actual_date = result['analysis'].get('actual_date', '')
            
            if matched_event_name and actual_date and event_tree_id:
                # 确保actual_date和matched_event_name都是字符串类型
                if isinstance(actual_date, list):
                    actual_date = actual_date[0] if actual_date else ''
                if isinstance(matched_event_name, list):
                    matched_event_name = matched_event_name[0] if matched_event_name else ''
                
                # 使用(日期, 事件名称)作为组合键
                key = (actual_date, matched_event_name)
                # 确保不重复添加相同的event_id
                if event_tree_id not in event_date_name_to_id[key]:
                    event_date_name_to_id[key].append(event_tree_id)
    
    # 计算映射中记录的event_id总数
    total_event_ids = sum(len(ids) for ids in event_date_name_to_id.values())
    
    # 打印构建的映射大小
    print(f"\n构建的(日期, 事件名称)到event_id的映射数量: {len(event_date_name_to_id)}")
    print(f"映射中记录的event_id总数: {total_event_ids}")
    
    # 为daily_draft中的每个事件添加event_id
    updated_daily_data = {}
    total_events = 0
    matched_events = 0
    
    # 收集所有成功匹配的(日期, 事件名称)组合
    all_matched_combinations = set(event_date_name_to_id.keys())
    # 收集在daily_draft中找到的组合
    found_combinations = set()
    # 收集匹配成功但在daily_draft中未找到的组合
    missing_in_daily_draft = []
    
    for month, days in daily_data.items():
        updated_days = []
        
        for day in days:
            updated_day = day.copy()
            updated_events = []
            
            date = day['date']
            
            for event in day['events']:
                total_events += 1
                updated_event = event.copy()
                
                # 使用(日期, 事件名称)组合键匹配
                event_name = event.get('name', '')
                # 创建组合键
                key = (date, event_name)
                
                # 如果这个组合在匹配结果中，记录为已找到
                if key in event_date_name_to_id:
                    found_combinations.add(key)
                    
                    matched_event_ids = event_date_name_to_id[key]
                    matched_events += 1
                    updated_event['event_id'] = matched_event_ids  # event_id是数组形式
                else:
                    updated_event['event_id'] = []  # 未匹配到的事件，event_id默认为空数组
                
                # 将事件添加到当天的事件列表中
                updated_events.append(updated_event)
            
            # 更新当天的事件列表
            updated_day['events'] = updated_events
            updated_days.append(updated_day)
        
        # 更新该月的天数列表
        updated_daily_data[month] = updated_days
    
    # 计算匹配成功但在daily_draft中未找到的组合
    missing_combinations = all_matched_combinations - found_combinations
    
    # 收集前5个缺失的组合示例
    for key in missing_combinations:
        if len(missing_in_daily_draft) < 5:
            date, event_name = key
            # 检查是否在日期范围内
            if is_date_in_range(date):
                missing_in_daily_draft.append({
                    'date': date,
                    'event_name': event_name,
                    'event_ids': event_date_name_to_id[key]
                })
    
    # 保存结果
    if output_path:
        output_file = os.path.join(output_path, "daily_draft.json")
    else:
        output_file = r"D:\pyCharmProjects\pythonProject4\data\fenghaoran\daily_draft_id.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(updated_daily_data, f, ensure_ascii=False, indent=2)
    
    # 打印匹配成功但在daily_draft中未找到的组合示例
    if missing_in_daily_draft:
        print(f"\n=== 匹配分析成功但在daily_draft中未找到的组合示例 (前5个) ===")
        for i, item in enumerate(missing_in_daily_draft, 1):
            print(f"示例 {i}:")
            print(f"  日期: {item['date']}")
            print(f"  事件名称: {item['event_name']}")
            print(f"  对应的event_id: {item['event_ids']}")
            print()
    
    print(f"处理完成！")
    print(f"总事件数: {total_events}")
    print(f"成功匹配的事件数: {matched_events}")
    print(f"总匹配率: {matched_events / total_events * 100:.2f}%")
    print(f"\n结果已保存到: {output_file}")

if __name__ == "__main__":
    main()