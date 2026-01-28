import json
import os

# 定义文件路径
xujing_dir = "D:\pyCharmProjects\pythonProject4\\xujing"
output_file = os.path.join(xujing_dir, "QA.json")

# 定义需要合并的qa.json文件列表
qa_files = [
    "muti_hop_qa.json",
    "reasoning_qa.json",
    "single_hop_qa.json",
    "updating_qa.json",
    "user_modeling_qa.json"
]

# 初始化合并后的QA列表
merged_qa = []

# 初始化统计字典
statistics = {
    "file_distribution": {},  # 每个文件的问答对数量
    "type_distribution": {},  # 不同类型问答对的分布（基于question_type字段）
    "total_count": 0  # 总问答对数量
}

# 遍历每个qa.json文件
for qa_file in qa_files:
    file_path = os.path.join(xujing_dir, qa_file)
    
    try:
        # 打开并读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查数据类型是否为列表
        if isinstance(data, list):
            # 处理single_hop_qa.json文件，确保每个问答对都有question_type字段
            if qa_file == "single_hop_qa.json":
                print(f"正在为 {qa_file} 中的所有问答对添加question_type:'single_hop'字段...")
                processed_data = []
                for qa in data:
                    # 添加或更新question_type字段
                    qa["question_type"] = "single_hop"
                    processed_data.append(qa)
                merged_qa.extend(processed_data)
                file_data = processed_data
            else:
                merged_qa.extend(data)
                file_data = data
            
            # 更新文件分布统计
            file_name = os.path.splitext(qa_file)[0]  # 获取不带扩展名的文件名
            statistics["file_distribution"][file_name] = len(data)
            
            # 统计当前文件中不同类型的问答对
            for qa in file_data:
                # 检查问答对是否有question_type字段
                if "question_type" in qa:
                    qa_type = qa["question_type"]
                    if qa_type in statistics["type_distribution"]:
                        statistics["type_distribution"][qa_type] += 1
                    else:
                        statistics["type_distribution"][qa_type] = 1
            
            print(f"成功合并 {qa_file}，添加了 {len(data)} 个问答对")
        else:
            print(f"警告：{qa_file} 的数据类型不是列表，跳过该文件")
            
    except FileNotFoundError:
        print(f"警告：{qa_file} 文件不存在，跳过该文件")
    except json.JSONDecodeError:
        print(f"警告：{qa_file} 不是有效的JSON文件，跳过该文件")
    except Exception as e:
        print(f"处理 {qa_file} 时出错：{str(e)}")

# 更新总问答对数量
statistics["total_count"] = len(merged_qa)

# 按照ask_time字段排序（升序）
print("\n正在按ask_time字段对问答对进行排序...")
merged_qa_sorted = sorted(merged_qa, key=lambda x: x.get("ask_time", "9999-99"))

# 将排序后的QA列表写入新的JSON文件
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(merged_qa_sorted, f, ensure_ascii=False, indent=2)

# 打印详细统计信息
print(f"\n合并完成！")
print(f"所有问答对已合并到 {output_file}")
print(f"总共合并了 {len(merged_qa)} 个问答对\n")

print("=== 数据分布统计 ===")
print("\n1. 按文件分布：")
for file_name, count in statistics["file_distribution"].items():
    percentage = (count / statistics["total_count"]) * 100 if statistics["total_count"] > 0 else 0
    print(f"   {file_name}: {count} 个 ({percentage:.2f}%)")

print("\n2. 按类型分布：")
if statistics["type_distribution"]:
    for qa_type, count in statistics["type_distribution"].items():
        percentage = (count / statistics["total_count"]) * 100 if statistics["total_count"] > 0 else 0
        print(f"   {qa_type}: {count} 个 ({percentage:.2f}%)")
else:
    print("   未找到带有question_type字段的问答对")

# 统计没有question_type字段的问答对数量
no_type_count = statistics["total_count"] - sum(statistics["type_distribution"].values())
if no_type_count > 0:
    percentage = (no_type_count / statistics["total_count"]) * 100 if statistics["total_count"] > 0 else 0
    print(f"   无类型标识: {no_type_count} 个 ({percentage:.2f}%)")

print("\n=== 统计结束 ===")