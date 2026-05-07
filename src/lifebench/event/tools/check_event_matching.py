import json
import os
import sys
import concurrent.futures
from collections import defaultdict
from datetime import datetime, timedelta

# 添加项目根目录到sys.path，确保可以导入src模块
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from src.lifebench.utils.llm_call import llm_call_j

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
        print("错误: file_path 不能为 None，请提供 event_tree.json 文件路径")
        exit(1)
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# 读取每日草稿数据
def load_daily_draft(file_path=None):
    if file_path is None:
        print("错误: file_path 不能为 None，请提供 daily_draft.json 文件路径")
        exit(1)
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# 读取每日事件数据
def load_daily_event(file_path=None):
    if file_path is None:
        print("错误: file_path 不能为 None，请提供 daily_event.json 文件路径")
        exit(1)
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# 提取所有最底层事件（decompose为0的事件）
def extract_bottom_events(event_data):
    bottom_events = []

    def traverse_events(events):
        for event in events:
            if event.get('decompose') == 1 and 'subevent' in event:
                traverse_events(event['subevent'])
            else:
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


# 构建每日事件映射（日期 -> 当日事件列表），用于daily_event匹配
def build_daily_event_map(daily_event_list):
    """从daily_event列表构建日期到事件的映射"""
    daily_map = defaultdict(list)
    for event in daily_event_list:
        dates = event.get('date', [])
        if isinstance(dates, str):
            dates = [dates]
        for date_range in dates:
            # 处理日期范围格式（如"2025-01-01 06:28:00至2025-01-01 07:55:00"）
            if '至' in date_range:
                start, end = date_range.split('至')
                date = start.strip()[:10]  # 取日期部分
            else:
                date = date_range.strip()[:10]
            daily_map[date].append(event)
    return daily_map


# 使用LLM分析事件匹配情况
def analyze_event_matching(bottom_event, expanded_events, original_date):
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
        - `reason`：字符串，详细说明匹配或不匹配的判断依据
        - `matched_event_name`：字符串或null，**必须严格返回扩展日期事件集合中匹配事件的完整原始名称**
        - `actual_date`：字符串或null，如果找到匹配，返回匹配事件发生的实际日期
        - `action`：字符串，可选值为"keep"、"rewrite"、"delete"或"keep_important"
        - `rewrite_suggestion`：JSON对象或null，如果需要重写，提供完整的重写后事件JSON
        - `match_details`：对象，提供详细的匹配信息

        ## 输出示例
        ```json
        {{
            "matched": true,
            "reason": "日期'2025-01-02'的事件'与家人的新年视频通话'与需要匹配的事件'与母亲的视频通话'核心内容一致",
            "matched_event_name": "与家人的新年视频通话",
            "actual_date": "2025-01-02",
            "action": "keep",
            "rewrite_suggestion": null,
            "match_details": {{
                "matched_date": "2025-01-02",
                "matched_event_full_info": {{}}
            }}
        }}
        ```

        ```json
        {{
            "matched": false,
            "reason": "原始日期'{original_date}'前后3天内的所有事件都不包含需要匹配的事件",
            "matched_event_name": null,
            "actual_date": null,
            "action": "delete",
            "rewrite_suggestion": null,
            "match_details": null
        }}
        ```
        """

        prompt = prompt.format(
            event_name=bottom_event['name'],
            event_desc=bottom_event['description'],
            original_date=original_date,
            expanded_events_json=json.dumps(expanded_events, ensure_ascii=False, indent=2)
        )

        response = llm_call_j(prompt)

        response = response.strip()
        if not response:
            print(f"分析事件时出错 ({bottom_event['name']}): LLM返回空响应")
            return {
                "matched": False,
                "reason": "LLM返回空响应",
                "matched_event_name": None,
                "actual_date": None,
                "action": "delete",
                "rewrite_suggestion": None,
                "match_details": None
            }

        if response.startswith('```json'):
            response = response[7:]
        if response.endswith('```'):
            response = response[:-3]
        response = response.strip()

        if not response:
            print(f"分析事件时出错 ({bottom_event['name']}): LLM返回空响应")
            return {
                "matched": False,
                "reason": "LLM返回空响应",
                "matched_event_name": None,
                "actual_date": None,
                "action": "delete",
                "rewrite_suggestion": None,
                "match_details": None
            }

        result = json.loads(response)

        if 'actual_date' not in result:
            result['actual_date'] = None

        if 'matched_event_name' not in result:
            result['matched_event_name'] = None

        if 'action' not in result or result['action'] not in ['keep', 'rewrite', 'delete', 'keep_important']:
            result['action'] = 'keep' if result['matched'] else 'delete'

        if result['matched'] and result['actual_date'] and result['actual_date'] != original_date:
            result['action'] = 'rewrite'
            if not result.get('rewrite_suggestion'):
                result['rewrite_suggestion'] = {}
            if 'date' in bottom_event:
                if isinstance(bottom_event['date'], list):
                    result['rewrite_suggestion']['date'] = [result['actual_date']]
                else:
                    result['rewrite_suggestion']['date'] = result['actual_date']

        if 'rewrite_suggestion' not in result:
            result['rewrite_suggestion'] = None

        if result.get('action') == 'rewrite':
            if 'rewrite_suggestion' in result and result['rewrite_suggestion']:
                rewrite_suggestion = result['rewrite_suggestion']
            else:
                rewrite_suggestion = {}

            for key, value in bottom_event.items():
                if key not in rewrite_suggestion:
                    rewrite_suggestion[key] = value

            if 'event_id' in bottom_event:
                rewrite_suggestion['event_id'] = bottom_event['event_id']

            result['rewrite_suggestion'] = rewrite_suggestion

        if 'match_details' not in result:
            result['match_details'] = None

        return result
    except json.JSONDecodeError as e:
        error_msg = f"JSON解析错误: {str(e)}"
        print(f"分析事件时出错 ({bottom_event['name']}): {error_msg}")
        return {
            "matched": False,
            "reason": error_msg,
            "matched_event_name": None,
            "actual_date": None,
            "action": "delete",
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
            "action": "delete",
            "rewrite_suggestion": None,
            "match_details": None
        }


# 使用LLM分析daily_event与daily_draft的事件匹配
def analyze_daily_event_matching(daily_event, daily_draft_events, original_date):
    """分析daily_event中的事件与daily_draft中对应日期事件的匹配"""
    try:
        prompt = """
        你是一名事件匹配分析专家，请分析每日事件与计划事件的匹配关系。

        ## 分析任务
        判断需要匹配的每日事件是否与计划事件集合中存在对应的相似事件。

        ## 输入数据
        1. **需要匹配的每日事件（完整信息）**：
           {daily_event_json}

        2. **原始日期**：{original_date}

        3. **当日计划事件集合**：
           {daily_draft_events_json}

        ## 分析标准（宽松匹配原则）
        - **匹配条件**：只要计划事件集合中存在与需要匹配的事件**类型相似、主题相关**的事件，就可以认为是匹配
        - **核心判断**：关注事件的**核心活动类型**（如去医院看病、去超市购物、运动健身等），而不是具体细节
        - **可以忽略的差异**：
          - 具体人物不同（如都是去医院，但一个是"陪父亲看病"一个是"自己看病"）
          - 具体地点不同（如都是去超市，但一个是"永辉超市"一个是"沃尔玛"）
          - 具体时间不同
          - 具体执行方式细节不同（如都是运动，一个是"健身房跑步"一个是"户外跑步"）
        - **示例**：
          - ✓ 匹配："去医院看病" 可以匹配 "陪母亲去医院体检"
          - ✓ 匹配："去超市购物" 可以匹配 "在沃尔玛买食材"
          - ✓ 匹配："和朋友吃饭" 可以匹配 "与同事聚餐"
          - ✗ 不匹配：去医院看病 vs 去银行办业务（类型完全不同）

        ## 输出要求
        请以JSON格式返回分析结果：
        - `matched`：布尔值，表示是否找到匹配
        - `matched_event_name`：字符串或null，匹配到的计划事件名称
        - `matched_event`：对象或null，匹配到的计划事件完整信息

        ## 输出示例
        ```json
        {{
            "matched": true,
            "matched_event_name": "与家人的新年视频通话",
            "matched_event": {{"name": "与家人的新年视频通话", ...}}
        }}
        ```

        ```json
        {{
            "matched": false,
            "matched_event_name": null,
            "matched_event": null
        }}
        ```
        """

        prompt = prompt.format(
            daily_event_json=json.dumps(daily_event, ensure_ascii=False, indent=2),
            original_date=original_date,
            daily_draft_events_json=json.dumps(daily_draft_events, ensure_ascii=False, indent=2)
        )

        response = llm_call_j(prompt)

        response = response.strip()
        if not response:
            print(f"分析daily_event时出错 ({daily_event.get('name', 'unknown')}): LLM返回空响应")
            return {
                "matched": False,
                "matched_event_name": None,
                "matched_event": None
            }

        if response.startswith('```json'):
            response = response[7:]
        if response.endswith('```'):
            response = response[:-3]
        response = response.strip()

        if not response:
            print(f"分析daily_event时出错 ({daily_event.get('name', 'unknown')}): LLM返回空响应")
            return {
                "matched": False,
                "matched_event_name": None,
                "matched_event": None
            }

        result = json.loads(response)
        return result
    except Exception as e:
        print(f"分析daily_event时出错 ({daily_event.get('name', 'unknown')}): {str(e)}")
        return {
            "matched": False,
            "matched_event_name": None,
            "matched_event": None
        }


# 获取日期前后N天的所有日期
def get_date_range(date_str, days_before=3, days_after=3):
    """获取指定日期前后N天的所有日期"""
    base_date = datetime.strptime(date_str, "%Y-%m-%d")
    date_range = []

    for i in range(days_before, 0, -1):
        target_date = base_date - timedelta(days=i)
        date_range.append(target_date.strftime("%Y-%m-%d"))

    date_range.append(date_str)

    for i in range(1, days_after + 1):
        target_date = base_date + timedelta(days=i)
        date_range.append(target_date.strftime("%Y-%m-%d"))

    return date_range


# 单个分析任务函数
def analyze_single_task(event, date_str, daily_events_map):
    """单个分析任务的包装函数"""
    if '至' in date_str:
        start_date, end_date = date_str.split('至')
        original_date = start_date.strip()
    else:
        original_date = date_str.strip()

    expanded_dates = get_date_range(original_date)

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

    analysis_result = analyze_event_matching(event, expanded_events, original_date)

    return {
        "event": event,
        "date": original_date,
        "analysis": analysis_result
    }


# daily_event与daily_draft的单个匹配任务
def analyze_daily_event_single_task(daily_event, date, daily_event_list):
    """daily_event与daily_draft的单个匹配任务"""
    analysis_result = analyze_daily_event_matching(daily_event, daily_event_list, date)
    return {
        "daily_event": daily_event,
        "date": date,
        "analysis": analysis_result
    }


def main(base_path=None, output_path=None, resume=True):
    # 验证必要参数
    if base_path is None:
        print("错误: base_path 不能为 None")
        exit(1)

    # 标准化路径并构建输入文件路径
    base_path_normalized = os.path.normpath(os.path.abspath(base_path))
    if output_path is None:
        output_path = base_path_normalized
    output_path_normalized = os.path.normpath(os.path.abspath(output_path))

    event_decompose_dfs_path = os.path.join(base_path_normalized, "event_tree.json")
    daily_draft_path = os.path.join(base_path_normalized, "daily_draft.json")
    daily_event_path = os.path.join(base_path_normalized, "daily_event.json")

    # 创建中间文件存储目录（基于输入文件路径的eventmatching文件夹）
    event_matching_dir = os.path.join(base_path_normalized, "eventmatching")
    os.makedirs(event_matching_dir, exist_ok=True)

    # 检查是否存在已保存的中间结果（支持断点重跑）
    intermediate_result_file = os.path.join(event_matching_dir, "event_matching_results.json")

    # 加载数据
    print(f"\n=== 加载数据 ===")
    event_data = load_event_decompose_dfs(event_decompose_dfs_path)
    daily_data = load_daily_draft(daily_draft_path)
    daily_event_data = load_daily_event(daily_event_path)

    # 检查daily_event是否已经包含atomic_id字段，如果是则跳过所有处理
    if daily_event_data and len(daily_event_data) > 0 and 'atomic_id' in daily_event_data[0]:
        print(f"daily_event数据已包含atomic_id字段，跳过所有处理流程")
        return

    # 提取最底层事件
    bottom_events = extract_bottom_events(event_data)
    print(f"总共提取到 {len(bottom_events)} 个最底层事件")

    # 构建每日事件映射（用于event_tree与daily_draft匹配）
    daily_events_map = build_daily_events_map(daily_data)
    print(f"总共加载了 {len(daily_events_map)} 天的每日事件")

    # 构建每日事件映射（用于daily_event与daily_draft匹配）
    daily_event_date_map = build_daily_event_map(daily_event_data)
    print(f"总共加载了 {len(daily_event_date_map)} 天的daily_event数据")

    # ==================== 第一阶段：event_tree 与 daily_draft 匹配 ====================
    print(f"\n=== 第一阶段：event_tree 与 daily_draft 匹配 ===")

    # 检查是否需要从断点恢复
    if resume and os.path.exists(intermediate_result_file):
        print(f"检测到已存在的中间结果文件: {intermediate_result_file}")
        print("从断点恢复，跳过第一阶段计算...")
        with open(intermediate_result_file, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
            results = saved_data.get('date_results', [])
            event_results = saved_data.get('event_results', {})
            total_events = saved_data.get('summary', {}).get('total_events', 0)
            matched_events = saved_data.get('summary', {}).get('matched_events', 0)
            unmatched_events = saved_data.get('summary', {}).get('unmatched_events', 0)
        print(f"已恢复 {len(results)} 个任务结果")
    else:
        # 收集所有需要分析的任务（只处理分析日期范围内的事件）
        tasks = []
        for event in bottom_events:
            event_date = event.get('date', '')
            event_id = event.get('event_id', '未知ID')
            if not event_date:
                print(f"事件ID: {event_id} - {event['name']} 没有日期信息，跳过")
                continue

            event_dates = []
            if isinstance(event_date, list):
                event_dates = event_date
            else:
                event_dates = [event_date]

            for date_str in event_dates:
                if '至' in date_str:
                    start_date, end_date = date_str.split('至')
                    date = start_date.strip()
                else:
                    date = date_str.strip()

                if is_date_in_range(date):
                    tasks.append((event, date_str, daily_events_map))
                else:
                    print(f"事件ID: {event_id} - {event['name']} 的日期 {date} 不在分析范围内，跳过")

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
            future_to_task = {executor.submit(analyze_single_task, *task): task for task in tasks}

            for future in concurrent.futures.as_completed(future_to_task):
                try:
                    result = future.result()
                    results.append(result)

                    event_id = result['event'].get('event_id', '未知ID')

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

        # 按事件ID分组统计结果
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

        print(f"\n分析完成！")
        print(f"总事件数: {total_events}")
        print(f"匹配成功的事件数: {matched_events}")
        print(f"未匹配的事件数: {unmatched_events}")
        print(f"总日期任务数: {len(results)}")
        print(f"匹配成功的日期数: {sum(1 for r in results if r['analysis']['matched'])}")

        if total_events > 0:
            print(f"事件匹配率: {matched_events / total_events * 100:.2f}%")

        # 保存结果
        output_file = os.path.join(event_matching_dir, "event_matching_results.json")
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

        print(f"\n第一阶段结果已保存到: {output_file}")
        print(f"中间文件存储目录: {event_matching_dir}")

    # 基于分析结果重写event_tree数据
    print("\n=== 重写event_tree数据 ===")

    event_actions = {}
    for event_id, result in event_results.items():
        final_action = "keep"
        final_suggestion = None

        for task_result in result['results']:
            if 'action' in task_result['analysis']:
                final_action = task_result['analysis']['action']
                final_suggestion = task_result['analysis'].get('rewrite_suggestion', None)
                break

        event_actions[event_id] = {
            "action": final_action,
            "rewrite_suggestion": final_suggestion
        }

    def update_event_tree(tree_data, actions):
        """递归更新事件树"""
        updated_tree = []

        for item in tree_data:
            if isinstance(item, dict):
                if item.get('decompose') == 0:
                    event_id = item.get('event_id', '')

                    if event_id in actions:
                        action = actions[event_id]['action']

                        if action == "delete":
                            continue
                        elif action == "rewrite":
                            suggestion = actions[event_id]['rewrite_suggestion']
                            if suggestion and isinstance(suggestion, dict):
                                for key, value in item.items():
                                    if key not in suggestion:
                                        suggestion[key] = value
                                if 'event_id' in item:
                                    suggestion['event_id'] = item['event_id']
                                updated_tree.append(suggestion)
                            else:
                                updated_tree.append(item)
                        else:
                            updated_tree.append(item)
                    else:
                        updated_tree.append(item)
                else:
                    if 'subevent' in item:
                        updated_subevents = update_event_tree(item['subevent'], actions)
                        if updated_subevents:
                            updated_item = item.copy()
                            updated_item['subevent'] = updated_subevents
                            updated_tree.append(updated_item)
                        else:
                            continue
                    else:
                        updated_tree.append(item)

        return updated_tree

    updated_event_tree = update_event_tree(event_data, event_actions)

    # 保存更新后的event_tree
    output_tree_file = os.path.join(output_path_normalized, "event_tree.json")

    with open(output_tree_file, 'w', encoding='utf-8') as f:
        json.dump(updated_event_tree, f, ensure_ascii=False, indent=2)

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

    # ==================== 更新daily_draft，为每个事件添加event_id ====================
    print("\n=== 更新daily_draft数据 ===")

    event_date_name_to_id = defaultdict(list)

    for result in results:
        if result['analysis']['matched']:
            event_tree_id = result['event'].get('event_id', '')
            matched_event_name = result['analysis'].get('matched_event_name', '')
            actual_date = result['analysis'].get('actual_date', '')

            if matched_event_name and actual_date and event_tree_id:
                if isinstance(actual_date, list):
                    actual_date = actual_date[0] if actual_date else ''
                if isinstance(matched_event_name, list):
                    matched_event_name = matched_event_name[0] if matched_event_name else ''

                key = (actual_date, matched_event_name)
                if event_tree_id not in event_date_name_to_id[key]:
                    event_date_name_to_id[key].append(event_tree_id)

    updated_daily_data = {}
    total_draft_events = 0
    matched_draft_events = 0

    for month, days in daily_data.items():
        updated_days = []

        for day in days:
            updated_day = day.copy()
            updated_events = []

            date = day['date']

            for event in day['events']:
                total_draft_events += 1
                updated_event = event.copy()

                event_name = event.get('name', '')
                key = (date, event_name)

                if key in event_date_name_to_id:
                    matched_event_ids = event_date_name_to_id[key]
                    matched_draft_events += 1
                    updated_event['event_id'] = matched_event_ids
                else:
                    updated_event['event_id'] = []

                updated_events.append(updated_event)

            updated_day['events'] = updated_events
            updated_days.append(updated_day)

        updated_daily_data[month] = updated_days

    # 保存更新后的daily_draft
    output_draft_file = os.path.join(output_path_normalized, "daily_draft.json")
    with open(output_draft_file, 'w', encoding='utf-8') as f:
        json.dump(updated_daily_data, f, ensure_ascii=False, indent=2)

    print(f"更新后的daily_draft已保存到: {output_draft_file}")
    print(f"daily_draft总事件数: {total_draft_events}")
    print(f"daily_draft匹配成功的事件数: {matched_draft_events}")
    if total_draft_events > 0:
        print(f"daily_draft匹配率: {matched_draft_events / total_draft_events * 100:.2f}%")

    # ==================== 第二阶段：daily_event 与 daily_draft 匹配 ====================
    print(f"\n=== 第二阶段：daily_event 与 daily_draft 匹配 ===")

    # 构建event_tree底部事件ID到事件信息的映射
    bottom_event_id_map = {}
    for event in bottom_events:
        event_id = event.get('event_id', '')
        if event_id:
            bottom_event_id_map[event_id] = event

    # 构建(日期, 事件名称)到event_tree底部event_id的映射
    draft_event_to_bottom_ids = defaultdict(list)
    for result in results:
        if result['analysis']['matched']:
            event_tree_id = result['event'].get('event_id', '')
            matched_event_name = result['analysis'].get('matched_event_name', '')
            actual_date = result['analysis'].get('actual_date', '')

            if matched_event_name and actual_date and event_tree_id:
                if isinstance(actual_date, list):
                    actual_date = actual_date[0] if actual_date else ''
                if isinstance(matched_event_name, list):
                    matched_event_name = matched_event_name[0] if matched_event_name else ''

                key = (actual_date, matched_event_name)
                if event_tree_id not in draft_event_to_bottom_ids[key]:
                    draft_event_to_bottom_ids[key].append(event_tree_id)

    # 收集所有daily_event与daily_draft的匹配任务
    daily_event_tasks = []

    for daily_event in daily_event_data:
        dates = daily_event.get('date', [])
        if isinstance(dates, str):
            dates = [dates]

        for date_range in dates:
            if '至' in date_range:
                start, end = date_range.split('至')
                date = start.strip()[:10]
            else:
                date = date_range.strip()[:10]

            if date in daily_events_map:
                daily_event_list = daily_events_map[date]
                daily_event_tasks.append((daily_event, date, daily_event_list))

    print(f"总共有 {len(daily_event_tasks)} 个daily_event匹配任务")

    # 使用24线程并行分析
    daily_event_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as executor:
        future_to_task = {executor.submit(analyze_daily_event_single_task, *task): task for task in daily_event_tasks}

        for future in concurrent.futures.as_completed(future_to_task):
            try:
                result = future.result()
                daily_event_results.append(result)
            except Exception as e:
                print(f"daily_event分析任务出错: {e}")

    print(f"daily_event匹配完成，共 {len(daily_event_results)} 个结果")

    # 更新daily_event，为每个事件添加atomic_id字段
    # 构建(日期, 事件名称)到event_tree底部event_id的映射用于daily_event匹配
    daily_event_atomic_ids = defaultdict(list)

    for result in daily_event_results:
        if result['analysis']['matched']:
            daily_event_obj = result['daily_event']
            matched_event_name = result['analysis'].get('matched_event_name', '')
            date = result['date']

            if matched_event_name:
                key = (date, matched_event_name)
                if key in draft_event_to_bottom_ids:
                    atomic_ids = draft_event_to_bottom_ids[key]
                    daily_event_id = daily_event_obj.get('event_id', '')
                    if daily_event_id:
                        daily_event_atomic_ids[daily_event_id].extend(atomic_ids)

    # 为daily_event添加atomic_id字段
    updated_daily_event_data = []
    total_daily_events = len(daily_event_data)
    matched_daily_events = 0

    for daily_event in daily_event_data:
        updated_event = daily_event.copy()
        daily_event_id = daily_event.get('event_id', '')

        if daily_event_id in daily_event_atomic_ids:
            unique_atomic_ids = list(set(daily_event_atomic_ids[daily_event_id]))
            updated_event['atomic_id'] = unique_atomic_ids
            matched_daily_events += 1
        else:
            updated_event['atomic_id'] = []

        updated_daily_event_data.append(updated_event)

    # 保存更新后的daily_event
    output_event_file = os.path.join(output_path_normalized, "daily_event.json")
    with open(output_event_file, 'w', encoding='utf-8') as f:
        json.dump(updated_daily_event_data, f, ensure_ascii=False, indent=2)

    print(f"更新后的daily_event已保存到: {output_event_file}")
    print(f"daily_event总事件数: {total_daily_events}")
    print(f"daily_event匹配成功的事件数: {matched_daily_events}")
    if total_daily_events > 0:
        print(f"daily_event匹配率: {matched_daily_events / total_daily_events * 100:.2f}%")

    # ==================== 最终统计 ====================
    print("\n" + "=" * 50)
    print("全部处理完成！")
    print("=" * 50)
    print(f"最终输出目录: {output_path_normalized}")
    print(f"- event_tree.json: 更新后的事件树")
    print(f"- daily_draft.json: 更新后的每日草稿（已添加event_id）")
    print(f"- daily_event.json: 更新后的每日事件（已添加atomic_id）")
    print(f"中间文件目录: {event_matching_dir}")
    print(f"- event_matching_results.json: 详细匹配结果")


if __name__ == "__main__":
    main(base_path='D:\pyCharmProjects\pythonProject4\\tests\\tests\yuxiaowen')