import json
import os

# 定义要处理的文件列表（分为两类：需要合并的和仅内部排序的）
merge_files = [
    "event_call.json",
    "event_gallery.json",
    "event_note.json",
    "event_push.json"
]

# 仅需要内部排序的文件，不参与合并
internal_sort_files = {
    "event_perception.json": {
        "keys": ["date", "time"],
        "description": "依据date和time排序"
    },
    "event_fitness_health.json": {
        "keys": ["日期"],
        "description": "依据日期排序"
    },
    "event_chat.json": {
        "keys": ["date"],
        "description": "依据date排序"
    }
}

# 定义输入目录和输出文件路径
input_dir = r"D:\pyCharmProjects\pythonProject4\output\xujing\phone_data"
output_file = os.path.join(input_dir, "sorted_unified_data.json")

# 存储所有合并后的数据
all_data = []

try:
    # 第一步：对需要合并的文件内部按datetime字段排序并保存回原文件
    print("=== 第一步：对需要合并的文件内部排序并保存 ===")
    for file_name in merge_files:
        file_path = os.path.join(input_dir, file_name)
        print(f"正在处理文件: {file_name}")
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"  原文件有 {len(data)} 条记录")
        
        # 对文件内部数据按datetime排序
        sorted_file_data = sorted(data, key=lambda x: x.get('datetime', ''))
        
        # 保存排序后的内容回原文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(sorted_file_data, f, ensure_ascii=False, indent=2)
        
        print(f"  文件内部排序完成并保存")
    
    # 第二步：对仅需要内部排序的文件进行排序
    print("\n=== 第二步：对仅内部排序的文件进行排序 ===")
    for file_name, sort_info in internal_sort_files.items():
        file_path = os.path.join(input_dir, file_name)
        print(f"正在处理文件: {file_name} ({sort_info['description']})")
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"  原文件有 {len(data)} 条记录")
        
        # 根据不同文件使用不同的排序键
        keys = sort_info['keys']
        
        if file_name == "event_perception.json":
            # 先按date排序，再按time数组的第一个元素（开始时间）排序
            sorted_file_data = sorted(data, key=lambda x: (x.get('date', ''), x.get('time', [''])[0]))
        elif file_name == "event_fitness_health.json":
            # 按日期排序
            sorted_file_data = sorted(data, key=lambda x: x.get('日期', ''))
        elif file_name == "event_chat.json":
            # 按date排序
            sorted_file_data = sorted(data, key=lambda x: x.get('date', ''))
        else:
            # 默认排序
            sorted_file_data = sorted(data, key=lambda x: tuple(x.get(key, '') for key in keys))
        
        # 保存排序后的内容回原文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(sorted_file_data, f, ensure_ascii=False, indent=2)
        
        print(f"  文件内部排序完成并保存")
    
    # 第三步：合并所有排序后的文件并生成统一文件
    print("\n=== 第三步：合并需要合并的文件并生成统一文件 ===")
    all_data = []
    
    for file_name in merge_files:
        file_path = os.path.join(input_dir, file_name)
        print(f"正在读取排序后的文件: {file_name}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_data.extend(data)
    
    print(f"\n总共合并了 {len(all_data)} 条记录")
    
    # 再次按datetime字段排序（确保跨文件的时间顺序正确）
    print("正在对合并后的数据进行最终排序...")
    sorted_unified_data = sorted(all_data, key=lambda x: x.get('datetime', ''))
    
    # 写入排序后的统一文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(sorted_unified_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n处理完成！")
    print(f"1. 每个文件已内部排序并保存")
    print(f"2. 已生成统一排序文件: {output_file}")
    
except Exception as e:
    print(f"处理过程中出现错误: {e}")