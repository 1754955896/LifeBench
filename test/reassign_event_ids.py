"""基于连续性ID重新分配2级和3级ID"""
import json
import os
from typing import Dict, List


def load_id_mapping(file_path: str) -> Dict[str, str]:
    """加载ID映射表"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_continuance_id(continuance_id: str) -> tuple:
    """
    解析连续性ID
    
    Args:
        continuance_id: 格式如 "120-a"
    
    Returns:
        (root_id, suffix) 元组，如 ("120", "a")
    """
    if '-' in continuance_id:
        parts = continuance_id.split('-')
        root_id = parts[0]
        suffix = parts[-1]
        return root_id, suffix
    return continuance_id, ''


def reassign_sub_ids(id_mapping: Dict[str, str]) -> Dict[str, str]:
    """
    重新分配2级和3级ID
    
    规则：
    - 相同字母后缀的属于同一个2级ID组
    - 2级ID用数字表示：1, 2, 3...
    - 3级ID格式：{root_id}-{group_number}-{sub_number}
    - 如果某组只有1个节点，不分配3级ID（使用2级ID）
    - 如果某个根ID下只有1个2级组，该组的节点也不分配3级ID
    
    Args:
        id_mapping: 原ID映射 {event_id: continuance_id}
    
    Returns:
        新的ID映射 {event_id: new_id}
    """
    # 按根ID和字母后缀分组
    groups = {}  # {(root_id, suffix): [event_ids]}
    
    for event_id, continuance_id in id_mapping.items():
        root_id, suffix = parse_continuance_id(continuance_id)
        key = (root_id, suffix)
        
        if key not in groups:
            groups[key] = []
        groups[key].append(event_id)
    
    # 为每个根ID下的不同字母组分配数字编号
    root_groups = {}  # {root_id: [(suffix, event_ids), ...]}
    for (root_id, suffix), event_ids in groups.items():
        if root_id not in root_groups:
            root_groups[root_id] = []
        root_groups[root_id].append((suffix, event_ids))
    
    # 生成新ID
    new_id_mapping = {}
    
    for root_id, suffix_groups in root_groups.items():
        # 按字母顺序排序
        suffix_groups.sort(key=lambda x: x[0])
        
        # 检查该根ID下是否只有1个组
        is_single_group = len(suffix_groups) == 1
        
        # 为每个字母组分配数字编号（从1开始）
        for group_idx, (suffix, event_ids) in enumerate(suffix_groups, start=1):
            group_size = len(event_ids)
            
            # 为组内每个事件分配新ID
            for sub_idx, event_id in enumerate(event_ids, start=1):
                if is_single_group and group_size == 1:
                    # 根ID下只有1个组且该组只有1个节点，只使用根ID
                    new_id = f"{root_id}"
                elif is_single_group:
                    # 根ID下只有1个组但有多个节点，直接使用 {root_id}-{sub_idx}
                    new_id = f"{root_id}-{sub_idx}"
                elif group_size == 1:
                    # 多个组但该组只有1个节点，使用2级ID
                    new_id = f"{root_id}-{group_idx}"
                else:
                    # 多个组且多节点，分配2级和3级ID
                    new_id = f"{root_id}-{group_idx}-{sub_idx}"
                
                new_id_mapping[event_id] = new_id
    
    return new_id_mapping


def save_new_id_mapping(new_id_mapping: Dict[str, str], output_path: str) -> None:
    """保存新的ID映射表"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_id_mapping, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 新ID映射表已保存到: {output_path}")
    print(f"  共 {len(new_id_mapping)} 个节点映射")


def print_statistics(new_id_mapping: Dict[str, str]) -> None:
    """打印统计信息"""
    # 统计不同格式的ID数量
    single_level = 0  # 只有根ID+字母，如 "120-a"
    multi_level = 0   # 有3级ID，如 "120-a-1"
    
    for new_id in new_id_mapping.values():
        parts = new_id.split('-')
        if len(parts) == 2:
            single_level += 1
        elif len(parts) >= 3:
            multi_level += 1
    
    print(f"\n{'='*60}")
    print(f"ID重分配统计:")
    print(f"  - 总节点数: {len(new_id_mapping)}")
    print(f"  - 单节点组（无3级ID）: {single_level}")
    print(f"  - 多节点组（有3级ID）: {multi_level}")
    print(f"{'='*60}")


def main():
    """主函数"""
    # 输入文件路径
    input_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_reorganized\event_id_mapping.json"
    
    # 输出文件路径
    output_dir = os.path.dirname(input_path)
    output_path = os.path.join(output_dir, "event_id_mapping_reassigned.json")
    
    print("="*60)
    print("事件树ID重分配工具")
    print("="*60)
    
    # 1. 加载ID映射表
    print("\n[1/3] 加载ID映射表...")
    try:
        id_mapping = load_id_mapping(input_path)
        print(f"  ✓ 成功加载 {len(id_mapping)} 个节点映射")
    except Exception as e:
        print(f"  ✗ 加载失败: {e}")
        return
    
    # 2. 重新分配ID
    print("\n[2/3] 重新分配2级和3级ID...")
    new_id_mapping = reassign_sub_ids(id_mapping)
    print(f"  ✓ ID重分配完成")
    
    # 3. 打印统计信息
    print_statistics(new_id_mapping)
    
    # 4. 保存结果
    print("\n[3/3] 保存新ID映射表...")
    try:
        save_new_id_mapping(new_id_mapping, output_path)
        print(f"  ✓ 保存成功")
    except Exception as e:
        print(f"  ✗ 保存失败: {e}")
        return
    
    print("\n" + "="*60)
    print("完成！")
    print("="*60)


if __name__ == "__main__":
    main()
