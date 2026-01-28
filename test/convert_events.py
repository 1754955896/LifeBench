import json

# 输入文件路径
input_file = r"D:\pyCharmProjects\pythonProject4\output\xujing\daily_status\all_months_event_refine_20260120162043.json"
# 输出文件路径
output_file = r"D:\pyCharmProjects\pythonProject4\events_array.json"

# 读取输入JSON文件
with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 初始化事件数组
events_array = []

# 遍历每个月份
for month, days in data.items():
    # 遍历每天的数据
    for day in days:
        date = day["date"]
        # 遍历当天的每个事件
        for event in day["events"]:
            # 提取事件信息
            event_info = {
                "date": [date],
                "name": event["name"],
                "description": event["description"]
            }
            # 添加到事件数组
            events_array.append(event_info)

# 将事件数组写入输出JSON文件
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(events_array, f, ensure_ascii=False, indent=2)

print(f"转换完成！共转换了 {len(events_array)} 个事件。")
print(f"结果已保存到：{output_file}")