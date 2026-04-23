"""为事件树节点按时间连续性分配ID"""
import json
import os
from typing import List, Dict


def load_events(file_path: str) -> List[Dict]:
    """加载事件数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_all_leaf_nodes(tree: Dict) -> List[Dict]:
    """递归获取树的所有最底层节点（叶子节点）"""
    leaf_nodes = []
    
    def traverse(node):
        decompose = node.get('decompose', 0)
        subevents = node.get('subevent', [])
        
        if decompose == 0 or not subevents:
            # 没有子节点或不再分解，是叶子节点
            leaf_nodes.append(node)
        else:
            # 有子节点，继续遍历
            for child in subevents:
                traverse(child)
    
    traverse(tree)
    return leaf_nodes


def extract_all_leaf_nodes_from_trees(trees: List[Dict]) -> List[Dict]:
    """从所有树中提取最底层节点，并保留树的引用信息"""
    all_leaves = []
    
    for tree_idx, tree in enumerate(trees):
        # 获取根节点的event_id（作为父ID）
        root_event_id = str(tree.get('event_id', f'tree_{tree_idx}'))
        
        leaves = get_all_leaf_nodes(tree)
        for leaf in leaves:
            # 为每个叶子节点标记所属的树索引和根节点event_id
            leaf['_tree_index'] = tree_idx
            leaf['_root_event_id'] = root_event_id
            all_leaves.append(leaf)
    
    return all_leaves


def sort_events_by_time(events: List[Dict]) -> List[Dict]:
    """按时间顺序排列事件
    
    排序规则：
    1. 首先按树叶节点的date字段起始时间的日期排序
    2. 如果日期相同，则按最顶层节点的event_id大小排序
    """
    def get_start_date(event):
        """获取事件的起始日期"""
        date_data = event.get('date', [])
        if isinstance(date_data, list) and date_data:
            first_date = date_data[0]
            # 处理 "至" 分隔的日期范围
            if '至' in first_date:
                start_date = first_date.split('至')[0].strip()
            else:
                start_date = first_date.strip()
            return start_date
        return ''
    
    def get_root_event_id(event):
        """获取最顶层节点的event_id（用于二级排序）"""
        root_event_id = event.get('_root_event_id', '')
        return root_event_id
    
    # 按起始日期排序，如果日期相同则按根节点event_id排序
    sorted_events = sorted(events, key=lambda x: (get_start_date(x), get_root_event_id(x)))
    return sorted_events


def get_parent_id(event_id: str) -> str:
    """获取父节点ID（173-1的父id为173）"""
    if '-' in event_id:
        parts = event_id.split('-')
        return parts[0]
    return event_id


def assign_ids_to_trees(trees: List[Dict], sorted_leaves: List[Dict]) -> None:
    """
    为每个树的节点按时间连续性分配ID
    
    规则：
    - 遍历排序后的叶子节点，提取其树ID（根节点的event_id）
    - 维护每个父ID的状态数组：{parent_id: {'current_suffix': 'a', 'should_increment': False}}
    - 当遇到其他父ID时，将所有父ID的 should_increment 设为 True
    - 当 should_increment 为 True 时，字母加一，然后设为 False
    """
    # 跟踪每个父ID的状态
    parent_states = {}  # {parent_id: {'current_suffix': char, 'should_increment': bool}}
    
    # 记录上一个处理的父ID
    last_parent_id = None
    
    # 遍历排序后的叶子节点
    for position, leaf in enumerate(sorted_leaves):
        # 获取叶子节点的event_id，提取父ID（根节点event_id）
        full_event_id = leaf.get('event_id', '')
        if not full_event_id:
            continue
        
        parent_id = get_parent_id(str(full_event_id))
        
        # 如果这是新的父ID，标记所有其他父ID需要递增
        if last_parent_id is not None and parent_id != last_parent_id:
            for pid in parent_states:
                if pid != parent_id:
                    parent_states[pid]['should_increment'] = True
        
        # 初始化当前父ID的状态（如果不存在）
        if parent_id not in parent_states:
            parent_states[parent_id] = {
                'current_suffix': 'a',
                'should_increment': False
            }
        
        # 检查是否需要递增
        state = parent_states[parent_id]
        if state['should_increment']:
            # 字母加一
            current_char = state['current_suffix']
            next_char = chr(ord(current_char) + 1)
            state['current_suffix'] = next_char
            state['should_increment'] = False
            print(f"  [位置 {position}] 父ID {parent_id} 递增为 {next_char}")
        
        # 生成新的连续ID
        new_continuance_id = f"{parent_id}-{state['current_suffix']}"
        leaf['continuance_id'] = new_continuance_id
        
        print(f"  位置 {position}: 父ID={parent_id}, 后缀={state['current_suffix']} -> continuance_id={new_continuance_id} (事件: {leaf.get('name', 'N/A')[:30]})")
        
        # 更新上一个父ID
        last_parent_id = parent_id


def propagate_ids_to_tree_roots(trees: List[Dict]) -> None:
    """
    将叶子节点的assigned_id向上传播到整棵树
    同一棵树的所有节点共享相同的ID前缀
    """
    for tree_idx, tree in enumerate(trees):
        # 找到该树的第一个assigned_id后缀
        first_suffix = 'a'  # 默认值
        
        def find_first_assigned_id(node):
            nonlocal first_suffix
            if 'assigned_id' in node:
                # 提取后缀字符
                assigned_id = node['assigned_id']
                if '-' in assigned_id:
                    parts = assigned_id.split('-')
                    if len(parts) >= 2:
                        first_suffix = parts[-1]  # 提取 'a', 'b', 'c' 等
                return True
            
            subevents = node.get('subevent', [])
            for child in subevents:
                if find_first_assigned_id(child):
                    return True
            return False
        
        find_first_assigned_id(tree)
        
        # 为整棵树分配统一的ID前缀
        def assign_id_to_node(node, suffix):
            if 'assigned_id' not in node:
                root_event_id = node.get('event_id', '')
                if root_event_id:
                    node['assigned_id'] = f"{root_event_id}-{suffix}"
            
            subevents = node.get('subevent', [])
            for child in subevents:
                assign_id_to_node(child, suffix)
        
        assign_id_to_node(tree, first_suffix)


def collect_id_mapping(trees: List[Dict]) -> Dict[str, str]:
    """
    收集所有节点的ID映射关系
    
    Args:
        trees: 事件树列表
    
    Returns:
        ID映射字典 {原event_id: continuance_id}
    """
    id_mapping = {}
    
    def traverse_node(node):
        event_id = node.get('event_id', '')
        continuance_id = node.get('continuance_id', '')
        
        if event_id and continuance_id:
            id_mapping[str(event_id)] = continuance_id
        
        # 递归遍历子节点
        subevents = node.get('subevent', [])
        for child in subevents:
            traverse_node(child)
    
    for tree in trees:
        traverse_node(tree)
    
    return id_mapping


def save_id_mapping(id_mapping: Dict[str, str], output_path: str) -> None:
    """保存ID映射表"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(id_mapping, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ ID映射表已保存到: {output_path}")
    print(f"  共 {len(id_mapping)} 个节点映射")


def main():
    """主函数"""
    # 输入文件路径
    input_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_reorganized\0_events.json"
    
    # 输出文件路径（ID映射表）
    output_dir = os.path.dirname(input_path)
    output_path = os.path.join(output_dir, "event_id_mapping.json")
    
    print("="*60)
    print("事件树节点ID分配工具")
    print("="*60)
    
    # 1. 加载数据
    print("\n[1/5] 加载事件数据...")
    trees = load_events(input_path)
    print(f"  ✓ 加载了 {len(trees)} 棵树")
    
    # 2. 提取所有叶子节点
    print("\n[2/5] 提取所有最底层节点...")
    all_leaves = extract_all_leaf_nodes_from_trees(trees)
    print(f"  ✓ 共提取 {len(all_leaves)} 个叶子节点")
    
    # 3. 按时间排序
    print("\n[3/5] 按时间顺序排列事件...")
    sorted_leaves = sort_events_by_time(all_leaves)
    print(f"  ✓ 排序完成")
    
    # 4. 分配ID
    print("\n[4/5] 为节点分配ID...")
    assign_ids_to_trees(trees, sorted_leaves)
    
    # 5. 传播ID到整棵树
    print("\n[5/5] 将ID传播到整棵树...")
    propagate_ids_to_tree_roots(trees)
    print(f"  ✓ ID分配完成")
    
    # 6. 收集并保存ID映射表
    print("\n收集ID映射关系...")
    id_mapping = collect_id_mapping(trees)
    save_id_mapping(id_mapping, output_path)
    
    print("\n" + "="*60)
    print("完成！")
    print("="*60)


if __name__ == "__main__":
    main()
