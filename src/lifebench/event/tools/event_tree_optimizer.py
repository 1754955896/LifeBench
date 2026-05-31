# -*- coding: utf-8 -*-
"""event_tree 优化脚本：清理孤立事件并修复描述一致性"""
import json
import os
import sys
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# 添加项目根目录到 sys.path
sys_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_all_event_ids(base_path):
    """从 daily_event.json 和 phone_data 中收集所有出现过的 event_id"""
    all_ids = set()

    # 1. 从 daily_event.json 的 atomic_id 收集 id（只收集 atomic_id）
    daily_path = os.path.join(base_path, 'daily_event.json')
    if os.path.exists(daily_path):
        daily_data = load_json(daily_path)
        for event in daily_data:
            # atomic_id 列表中的所有 id
            for atomic_id in event.get('atomic_id', []):
                all_ids.add(str(atomic_id))

    # # 2. 从 phone_data 收集 event_id
    # phone_data_dir = os.path.join(base_path, 'phone_data')
    # if os.path.exists(phone_data_dir):
    #     for fname in os.listdir(phone_data_dir):
    #         if fname.endswith('.json'):
    #             try:
    #                 phone_data = load_json(os.path.join(phone_data_dir, fname))
    #                 for record in phone_data:
    #                     for eid in record.get('event_id', []):
    #                         all_ids.add(str(eid))
    #             except:
    #                 pass

    print(f"共收集到 {len(all_ids)} 个有效 event_id")
    return all_ids

def extract_bottom_events(event_tree):
    """提取所有底层事件"""
    bottom = []
    def traverse(events):
        for event in events:
            if event.get('subevent') and event['subevent']:
                traverse(event['subevent'])
            else:
                bottom.append(event)
    traverse(event_tree)
    return bottom

def is_date_in_2025(event):
    """检查事件日期是否在2025年"""
    dates = event.get('date', [])
    if isinstance(dates, str):
        dates = [dates]
    for date_range in dates:
        if '至' in date_range:
            date_str = date_range.split('至')[0].strip()
        else:
            date_str = date_range.strip()
        date_only = date_str.split(' ')[0] if ' ' in date_str else date_str
        if date_only.startswith('2025'):
            return True
    return False

def clean_event_tree(event_tree, valid_ids):
    """清理事件树：先收集所有底层事件，确定删除列表后执行删除"""
    def collect_bottom_events(events, parent_id=None):
        """收集所有底层事件"""
        bottoms = []
        for event in events:
            if event.get('subevent') and event['subevent']:
                bottoms.extend(collect_bottom_events(event['subevent'], event.get('event_id')))
            else:
                bottoms.append({'event': event, 'parent_id': parent_id})
        return bottoms

    def delete_events_from_tree(events, events_to_delete, deleted_set):
        """从事件树中删除指定事件"""
        new_tree = []
        for event in events:
            event_id = str(event.get('event_id', ''))
            if event_id in events_to_delete and event_id not in deleted_set:
                deleted_set.add(event_id)
                print(f"删除: {event_id} - {event.get('name', '')[:30]}")
                continue

            new_event = event.copy()
            if new_event.get('subevent'):
                new_event['subevent'] = delete_events_from_tree(new_event['subevent'], events_to_delete, deleted_set)
            new_tree.append(new_event)
        return new_tree

    # 收集所有底层事件
    all_bottom = collect_bottom_events(event_tree)

    # 确定需要删除的事件
    events_to_delete = set()
    for item in all_bottom:
        event = item['event']
        event_id = str(event.get('event_id', ''))
        is_orphan = event_id not in valid_ids
        not_in_2025 = not is_date_in_2025(event)

        if is_orphan or not_in_2025:
            events_to_delete.add(event_id)

    print(f"需要删除的底层事件数: {len(events_to_delete)}")

    # 执行删除
    deleted_set = set()
    cleaned_tree = delete_events_from_tree(event_tree, events_to_delete, deleted_set)

    return cleaned_tree

def analyze_node_consistency(node, children_info):
    """使用 LLM 分析节点描述是否与子节点一致"""
    if not children_info:
        return None

    node_json = json.dumps(node, ensure_ascii=False)

    prompt = f"""你是一名事件分析专家，请基于子事件分析父事件的一致性与合理性。

父事件（完整JSON）：
{node_json}

子事件列表：
{children_info}

字段说明：
- name：父事件名称，简短概括事件核心内容
- description：父事件详细描述，包含时间、地点、人物、事件经过等完整信息
- date：父事件日期，可能为单个日期或日期范围（如 ["2025-01-15"] 或 ["2025-01-15至2025-01-20"]）

分析流程（分两阶段）：

【阶段一：子事件完整性检查 - 删除决策】
将所有子事件视为一个整体，分析：
1. 这些子事件能否串联成一个连贯的整体事件？事件发展是否顺畅合理？
2. 整个过程是否基本充分（允许缺少一些细节，但主要步骤不能缺失）？
3. 若子事件明显缺少主要步骤，不能构成一个完整的事件逻辑链，则标记 delete

若存在上述问题，输出：
{{
    "action": "delete",
    "reason": "具体说明为什么子事件不能构成连贯整体事件"
}}

【阶段二：父事件优化决策 - 重写/保持】
在子事件能构成连贯整体（无删除）的前提下：
1. 判断父事件的 name、description、date 是否与子事件集合信息一致
2. 若不一致，选择 rewrite；否则选择 keep

若无需删除，输出：
{{
    "action": "rewrite"/"keep",
    "reason": "分析原因",
    "rewritten_node": {{
        "name": "重写后的父事件名称（仅 rewrite 时填写）",
        "description": "重写后的父事件描述（仅 rewrite 时填写）",
        "date": ["重写后的日期（仅 rewrite 时填写）"]
    }}
}}
"""

    try:
        from src.lifebench.utils.llm_call import llm_call_reason_j
        response = llm_call_reason_j(prompt)
        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1 and start < end:
            return json.loads(response[start:end+1])
    except Exception as e:
        print(f"LLM调用失败: {e}")
    return None

def optimize_tree_single(tree, results_to_delete, deletion_logs):
    """单个事件树从下往上优化：
    1. 收集所有倒数第二层节点（子节点都是叶子节点的节点）
    2. 这些节点都调用LLM进行分析
    3. 如果某节点被删除，其父节点加入处理序列，继续处理直到序列为空
    """
    def collect_all_nodes(events, parent=None, depth=0):
        """收集所有节点"""
        nodes = []
        for event in events:
            event_id = str(event.get('event_id', ''))
            children = event.get('subevent', [])
            nodes.append({
                'event': event,
                'parent': parent,
                'children': children,
                'depth': depth,
                'event_id': event_id
            })
            if children:
                nodes.extend(collect_all_nodes(children, event, depth + 1))
        return nodes

    def collect_second_last_layer_nodes(all_nodes):
        """收集倒数第二层节点：子节点都是叶子节点（无subevent或subevent为空）的节点"""
        # 建立 id -> node_info 的映射
        id_to_node = {n['event_id']: n for n in all_nodes}

        second_last_nodes = []
        for node in all_nodes:
            children = node['children']
            if not children:
                continue  # 跳过叶子节点

            # 检查是否所有子节点都是叶子节点
            all_children_are_leaves = True
            for child in children:
                child_id = str(child.get('event_id', ''))
                child_node = id_to_node.get(child_id)
                if child_node and child_node['children']:
                    # 子节点不是叶子节点
                    all_children_are_leaves = False
                    break

            if all_children_are_leaves:
                second_last_nodes.append(node)

        return second_last_nodes

    def build_children_info(node_info):
        """构建子节点信息字符串（完整信息，不截取）"""
        children = node_info['children']
        info_parts = []
        for c in children:
            child_id = str(c.get('event_id', ''))
            # 跳过已被删除的子节点
            if child_id in results_to_delete:
                continue
            # 输出完整的子节点信息（JSON格式）
            info_parts.append(json.dumps(c, ensure_ascii=False, indent=2))
        return '\n'.join(info_parts)

    # 收集所有节点
    all_nodes = collect_all_nodes([tree])
    if not all_nodes:
        return

    # 收集倒数第二层节点
    initial_nodes = collect_second_last_layer_nodes(all_nodes)

    # 建立 id -> node_info 的映射
    id_to_node = {n['event_id']: n for n in all_nodes}

    # 处理序列：从初始节点开始
    process_queue = list(initial_nodes)
    processed = set()

    while process_queue:
        # 取出节点（从队列头部）
        node_info = process_queue.pop(0)
        event_id = node_info['event_id']

        # 跳过已处理的节点
        if event_id in processed:
            continue
        processed.add(event_id)

        # 跳过已被删除的节点
        if event_id in results_to_delete:
            continue

        # 构建当前有效的子节点信息
        children_info = build_children_info(node_info)

        # 如果所有子节点都被删除了，直接删除父节点
        remaining_children = [c for c in node_info['children'] if str(c.get('event_id', '')) not in results_to_delete]
        if not remaining_children:
            results_to_delete.add(event_id)
            deletion_logs.append({
                'event_id': event_id,
                'name': node_info['event'].get('name', ''),
                'reason': '所有子节点已被删除'
            })
            parent = node_info['parent']
            if parent:
                parent_id = str(parent.get('event_id', ''))
                if parent_id not in processed and parent_id not in results_to_delete:
                    process_queue.append(id_to_node[parent_id])
            continue

        # 调用LLM分析
        result = analyze_node_consistency(node_info['event'], children_info)
        if result:
            if result.get('action') == 'delete':
                results_to_delete.add(event_id)
                deletion_logs.append({
                    'event_id': event_id,
                    'name': node_info['event'].get('name', ''),
                    'reason': result.get('reason', 'LLM分析决定删除')
                })
                # 父节点加入处理序列
                parent = node_info['parent']
                if parent:
                    parent_id = str(parent.get('event_id', ''))
                    if parent_id not in processed and parent_id not in results_to_delete:
                        process_queue.append(id_to_node[parent_id])
            elif result.get('action') == 'rewrite' and result.get('rewritten_node'):
                # 只替换 name、description、date 字段
                rewritten = result['rewritten_node']
                if 'name' in rewritten:
                    node_info['event']['name'] = rewritten['name']
                if 'description' in rewritten:
                    node_info['event']['description'] = rewritten['description']
                if 'date' in rewritten:
                    node_info['event']['date'] = rewritten['date']


def optimize_tree_parallel(event_tree, max_workers=20):
    """并行优化事件树：每个根节点的子树并行处理，树内从下往上逐层处理"""
    # 对每个根节点的子树并行处理
    def process_single_tree(tree):
        results_to_delete = set()
        deletion_logs = []
        optimize_tree_single(tree, results_to_delete, deletion_logs)
        return tree, results_to_delete, deletion_logs  # 返回修改后的树

    # 收集每个根节点的子树
    trees = []
    for event in event_tree:
        trees.append(event)

    # 并行处理每个子树
    all_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_single_tree, tree) for tree in trees]
        for future in as_completed(futures):
            try:
                result = future.result()
                all_results.append(result)
            except Exception as e:
                print(f"处理子树出错: {e}")

    # 合并删除结果，并收集修改后的树
    merged_results_to_delete = set()
    modified_trees = []
    all_deletion_logs = []
    for tree, result_set, deletion_logs in all_results:
        modified_trees.append(tree)
        merged_results_to_delete.update(result_set)
        all_deletion_logs.extend(deletion_logs)

    # 打印所有删除操作
    print(f"\n=== 步骤4.1: LLM分析删除操作 ===")
    print(f"共删除节点数: {len(merged_results_to_delete)}")
    for log in all_deletion_logs:
        print(f"  删除: {log['event_id']} - {log['name']} - 原因: {log['reason']}")

    # 对原始event_tree应用删除（使用修改后的树）
    def remove_marked_nodes(events):
        filtered = []
        for event in events:
            event_id = str(event.get('event_id', ''))
            if event_id not in merged_results_to_delete:
                if event.get('subevent'):
                    event['subevent'] = remove_marked_nodes(event['subevent'])
                filtered.append(event)
        return filtered

    return remove_marked_nodes(modified_trees), modified_trees

def main(base_path, output_file=None):
    print(f"处理文件夹: {base_path}")

    # 1. 收集有效 event_id
    print("\n=== 步骤1: 收集有效 event_id ===")
    valid_ids = get_all_event_ids(base_path)

    # 2. 加载 event_tree
    print("\n=== 步骤2: 加载 event_tree ===")
    event_tree_path = os.path.join(base_path, 'event_tree.json')
    event_tree = load_json(event_tree_path)

    # 提取底层事件检查
    bottom_events = extract_bottom_events(event_tree)
    print(f"原始底层事件数: {len(bottom_events)}")

    # 3. 清理孤立事件和日期不在2025年的事件
    print("\n=== 步骤3: 清理孤立事件和日期不在2025年的事件 ===")
    cleaned_tree = clean_event_tree(event_tree, valid_ids)

    # 检查清理后
    cleaned_bottom = extract_bottom_events(cleaned_tree)
    print(f"清理后底层事件数: {len(cleaned_bottom)}")

    # 4. 并行 LLM 分析优化
    print("\n=== 步骤4: LLM 分析优化（从下往上） ===")
    optimized_tree, modified_trees = optimize_tree_parallel(cleaned_tree, max_workers=20)

    # 打印被删除节点的树的示例
    print(f"\n=== 步骤4.2: 删除操作后的树示例 ===")
    for i, tree in enumerate(modified_trees[:3]):  # 只打印前3棵树
        tree_event_id = str(tree.get('event_id', ''))
        tree_name = tree.get('name', '')[:30]
        print(f"\n树 {i+1} (event_id: {tree_event_id}, 名称: {tree_name}):")
        print(json.dumps(tree, ensure_ascii=False, indent=2)[:500] + "...")

    # 步骤5: 删除只有一层（只有根节点无子节点）的树
    print(f"\n=== 步骤5: 删除单层树 ===")
    def is_single_layer(tree):
        """判断树是否只有一层（根节点无子节点）"""
        subevent = tree.get('subevent', [])
        return not subevent or len(subevent) == 0

    trees_to_delete = []
    for tree in optimized_tree:
        if is_single_layer(tree):
            trees_to_delete.append(str(tree.get('event_id', '')))
            print(f"删除单层树: {tree.get('event_id', '')} - {tree.get('name', '')[:30]}")

    final_tree = [tree for tree in optimized_tree if str(tree.get('event_id', '')) not in trees_to_delete]
    print(f"删除单层树数量: {len(trees_to_delete)}, 剩余树数量: {len(final_tree)}")

    # 保存结果
    if output_file is None:
        output_file = os.path.join(base_path, 'event_tree_clean.json')

    print(f"\n=== 保存结果到: {output_file} ===")
    save_json(output_file, final_tree)
    print("完成!")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='event_tree 优化脚本')
    parser.add_argument('--base_path', type=str, required=True, help='源文件夹路径')
    parser.add_argument('--output_file', type=str, default=None, help='输出文件路径')
    args = parser.parse_args()

    if args.output_file is None:
        args.output_file = os.path.join(args.base_path, 'event_tree_clean.json')

    main(args.base_path, args.output_file)