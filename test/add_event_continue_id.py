"""为JSON文件中的event_id添加映射后的continuance_id"""
import json
import os
import glob
import csv
from typing import Dict, List


def load_id_mapping(file_path: str) -> Dict[str, str]:
    """加载ID映射表"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def process_single_json_file(file_path: str, id_mapping: Dict[str, str], reassigned_mapping: Dict[str, str], output_dir: str) -> bool:
    """
    处理单个JSON文件，为event_id数组添加对应的continuance_id，并替换event_id
    
    Args:
        file_path: JSON文件路径
        id_mapping: ID映射表 {原event_id: continuance_id} - 用于event_continue_id
        reassigned_mapping: 重分配ID映射表 {原event_id: 新event_id} - 用于替换event_id
        output_dir: 输出目录
    
    Returns:
        是否成功处理
    """
    try:
        # 读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查是否为列表格式
        if not isinstance(data, list):
            print(f"  ⚠️  跳过: {os.path.basename(file_path)} (不是数组格式)")
            return False
        
        modified = False
        
        # 遍历数组中的每个对象
        for item in data:
            if not isinstance(item, dict):
                continue
            
            modified_item = False
            
            # 处理event_id数组字段
            if 'event_id' in item and isinstance(item['event_id'], list):
                event_ids = item['event_id']
                continuance_ids = []
                new_event_ids = []
                
                # 为每个event_id查找映射
                for eid in event_ids:
                    eid_str = str(eid)
                    
                    # 生成event_continue_id（使用id_mapping）
                    if eid_str in id_mapping:
                        continuance_ids.append(id_mapping[eid_str])
                    else:
                        continuance_ids.append(eid_str)
                    
                    # 替换event_id（使用reassigned_mapping）
                    if eid_str in reassigned_mapping:
                        new_eid = reassigned_mapping[eid_str]
                        # 如果新ID是纯数字则转为int，否则保持字符串
                        new_event_ids.append(int(new_eid) if new_eid.isdigit() else new_eid)
                    else:
                        new_event_ids.append(eid)
                
                # 添加新的字段
                item['event_continue_id'] = continuance_ids
                # 替换原有的event_id
                item['event_id'] = new_event_ids
                modified_item = True
            
            # 处理generation_source字段（单个值，不是数组）
            if 'generation_source' in item:
                gen_source = item['generation_source']
                gen_source_str = str(gen_source)
                
                # 生成generation_source_continue（使用id_mapping）
                if gen_source_str in id_mapping:
                    item['generation_source_continue'] = id_mapping[gen_source_str]
                else:
                    item['generation_source_continue'] = gen_source_str
                
                # 替换generation_source（使用reassigned_mapping）
                if gen_source_str in reassigned_mapping:
                    new_gen_source = reassigned_mapping[gen_source_str]
                    # 如果新ID是纯数字则转为int，否则保持字符串
                    item['generation_source'] = int(new_gen_source) if new_gen_source.isdigit() else new_gen_source
                
                modified_item = True
            
            if modified_item:
                modified = True
        
        # 保存到输出目录（不修改原文件）
        output_path = os.path.join(output_dir, os.path.basename(file_path))
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✓ 已保存: {os.path.basename(file_path)}")
        return True
            
    except Exception as e:
        print(f"  ✗ 处理失败 {os.path.basename(file_path)}: {e}")
        return False


def process_all_json_files(json_dir: str, id_mapping: Dict[str, str], reassigned_mapping: Dict[str, str], output_dir: str) -> None:
    """
    处理目录下所有JSON文件
    
    Args:
        json_dir: JSON文件目录
        id_mapping: ID映射表 - 用于event_continue_id
        reassigned_mapping: 重分配ID映射表 - 用于替换event_id
        output_dir: 输出目录
    """
    # 获取所有JSON文件
    json_files = glob.glob(os.path.join(json_dir, "*.json"))
    
    if not json_files:
        print(f"  ⚠️  未找到JSON文件: {json_dir}")
        return
    
    print(f"\n找到 {len(json_files)} 个JSON文件\n")
    
    success_count = 0
    error_count = 0
    
    # 处理每个文件
    for file_path in sorted(json_files):
        result = process_single_json_file(file_path, id_mapping, reassigned_mapping, output_dir)
        if result:
            success_count += 1
        else:
            error_count += 1
    
    print(f"\n{'='*60}")
    print(f"处理完成统计:")
    print(f"  - 总文件数: {len(json_files)}")
    print(f"  - 成功保存: {success_count}")
    print(f"  - 失败: {error_count}")
    print(f"{'='*60}")


def convert_json_to_csv(json_dir: str, csv_dir: str) -> None:
    """
    将JSON文件转换为CSV格式
    
    Args:
        json_dir: JSON文件目录
        csv_dir: CSV输出目录
    """
    # 获取所有JSON文件
    json_files = glob.glob(os.path.join(json_dir, "*.json"))
    
    if not json_files:
        print(f"  ⚠️  未找到JSON文件: {json_dir}")
        return
    
    os.makedirs(csv_dir, exist_ok=True)
    converted_count = 0
    
    for json_file in sorted(json_files):
        try:
            # 读取JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list) or len(data) == 0:
                continue
            
            # 生成CSV文件名
            base_name = os.path.splitext(os.path.basename(json_file))[0]
            csv_file = os.path.join(csv_dir, f"{base_name}.csv")
            
            # 获取所有字段名
            fieldnames = []
            for item in data:
                if isinstance(item, dict):
                    for key in item.keys():
                        if key not in fieldnames:
                            fieldnames.append(key)
            
            # 写入CSV
            with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for item in data:
                    if isinstance(item, dict):
                        # 将列表字段转为字符串
                        row = {}
                        for key in fieldnames:
                            value = item.get(key, '')
                            if isinstance(value, list):
                                row[key] = '; '.join([str(v) for v in value])
                            else:
                                row[key] = value
                        writer.writerow(row)
            
            converted_count += 1
            print(f"  ✓ 已转换: {os.path.basename(json_file)} -> {base_name}.csv")
            
        except Exception as e:
            print(f"  ✗ 转换失败 {os.path.basename(json_file)}: {e}")
    
    print(f"\n  共转换 {converted_count} 个文件为CSV格式")


def process_phone_data_file(file_path: str, id_mapping: Dict[str, str], reassigned_mapping: Dict[str, str], output_dir: str) -> bool:
    """
    处理手机数据文件（字典格式，包含多个类型的数据）
    
    Args:
        file_path: 手机数据JSON文件路径
        id_mapping: ID映射表 - 用于生成continue字段
        reassigned_mapping: 重分配ID映射表 - 用于替换原ID
        output_dir: 输出目录
    
    Returns:
        是否成功处理
    """
    try:
        # 读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, dict):
            print(f"  ⚠️  跳过: {os.path.basename(file_path)} (不是字典格式)")
            return False
        
        processed_types = 0
        
        # 遍历每个数据类型
        for data_type, items in data.items():
            if not isinstance(items, list):
                continue
            
            modified_items = []
            
            # 处理该类型下的每条数据
            for item in items:
                if not isinstance(item, dict):
                    modified_items.append(item)
                    continue
                
                modified_item = False
                
                # 处理event_id数组字段
                if 'event_id' in item and isinstance(item['event_id'], list):
                    event_ids = item['event_id']
                    continuance_ids = []
                    new_event_ids = []
                    
                    for eid in event_ids:
                        eid_str = str(eid)
                        
                        # 生成event_continue_id
                        if eid_str in id_mapping:
                            continuance_ids.append(id_mapping[eid_str])
                        else:
                            continuance_ids.append(eid_str)
                        
                        # 替换event_id
                        if eid_str in reassigned_mapping:
                            new_eid = reassigned_mapping[eid_str]
                            new_event_ids.append(int(new_eid) if new_eid.isdigit() else new_eid)
                        else:
                            new_event_ids.append(eid)
                    
                    item['event_continue_id'] = continuance_ids
                    item['event_id'] = new_event_ids
                    modified_item = True
                
                # 处理generation_source字段（单个值）
                if 'generation_source' in item:
                    gen_source = item['generation_source']
                    gen_source_str = str(gen_source)
                    
                    # 生成generation_source_continue
                    if gen_source_str in id_mapping:
                        item['generation_source_continue'] = id_mapping[gen_source_str]
                    else:
                        item['generation_source_continue'] = gen_source_str
                    
                    # 替换generation_source
                    if gen_source_str in reassigned_mapping:
                        new_gen_source = reassigned_mapping[gen_source_str]
                        item['generation_source'] = int(new_gen_source) if new_gen_source.isdigit() else new_gen_source
                    
                    modified_item = True
                
                modified_items.append(item)
            
            # 更新该类型的数据
            data[data_type] = modified_items
            if any('event_continue_id' in item or 'generation_source_continue' in item 
                   for item in modified_items if isinstance(item, dict)):
                processed_types += 1
        
        # 保存到输出目录
        output_path = os.path.join(output_dir, os.path.basename(file_path))
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 已处理 {processed_types} 种数据类型: {os.path.basename(file_path)}")
        return True
            
    except Exception as e:
        print(f"  ✗ 处理失败 {os.path.basename(file_path)}: {e}")
        return False


def main():
    """主函数"""
    # ID映射表路径（用于event_continue_id）
    id_mapping_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_reorganized\event_id_mapping.json"
    
    # 重分配ID映射表路径（用于替换event_id）
    reassigned_mapping_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_reorganized\event_id_mapping_reassigned.json"
    
    # JSON文件目录
    json_dir = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_reorganized\json"
    
    # 输出目录
    output_json_dir = r"D:\pyCharmProjects\pythonProject4\fenghaoran\example_1\json"
    output_csv_dir = r"D:\pyCharmProjects\pythonProject4\fenghaoran\example_1\csv"
    
    print("="*60)
    print("JSON文件event_id映射工具")
    print("="*60)
    
    # 1. 加载ID映射表
    print("\n[1/3] 加载ID映射表...")
    try:
        id_mapping = load_id_mapping(id_mapping_path)
        print(f"  ✓ 成功加载 {len(id_mapping)} 个continuance_id映射")
    except Exception as e:
        print(f"  ✗ 加载失败: {e}")
        return
    
    # 2. 加载重分配ID映射表
    print("\n[2/3] 加载重分配ID映射表...")
    try:
        reassigned_mapping = load_id_mapping(reassigned_mapping_path)
        print(f"  ✓ 成功加载 {len(reassigned_mapping)} 个重分配ID映射")
    except Exception as e:
        print(f"  ✗ 加载失败: {e}")
        return
    
    # # 3. 处理所有JSON文件
    # print("\n[3/3] 处理JSON文件...")
    # process_all_json_files(json_dir, id_mapping, reassigned_mapping, output_json_dir)
    #
    # # 4. 转换为CSV
    # print("\n[4/4] 转换为CSV格式...")
    # convert_json_to_csv(output_json_dir, output_csv_dir)
    #
    # print("\n" + "="*60)
    # print("完成！")
    # print("="*60)

    process_phone_data_file(r"D:\pyCharmProjects\pythonProject4\fenghaoran\example_1\0_phone_data.json", id_mapping, reassigned_mapping, r"D:\pyCharmProjects\pythonProject4\fenghaoran\example_1\0_phone_data2.json")

if __name__ == "__main__":
    main()
