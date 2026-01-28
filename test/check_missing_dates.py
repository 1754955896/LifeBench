import json
from datetime import datetime, timedelta
import os

# 定义文件路径
file_path = "D:\pyCharmProjects\pythonProject4\output\\fenghaoran\daily_draft.json"

# 检查文件是否存在
if not os.path.exists(file_path):
    print(f"文件不存在: {file_path}")
    exit(1)

# 读取JSON文件
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
except json.JSONDecodeError as e:
    print(f"JSON文件解析错误: {e}")
    exit(1)

# 提取所有日期
file_dates = set()
for entry in data:
    if 'date' in entry:
        file_dates.add(entry['date'])

# 生成2025年所有日期
start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 12, 31)
delta = timedelta(days=1)

all_2025_dates = set()
current_date = start_date
while current_date <= end_date:
    all_2025_dates.add(current_date.strftime('%Y-%m-%d'))
    current_date += delta

# 计算缺失的日期
missing_dates = sorted(all_2025_dates - file_dates)

# 输出结果
print("=== 2025年日期检查结果 ===")
print(f"总记录数: {len(file_dates)}")
print(f"2025年总天数: {len(all_2025_dates)}")
print(f"缺失天数: {len(missing_dates)}")

if missing_dates:
    print("\n缺失的日期:")
    # 按月份分组显示
    missing_by_month = {}
    for date in missing_dates:
        month = date[:7]  # 获取YYYY-MM格式
        if month not in missing_by_month:
            missing_by_month[month] = []
        missing_by_month[month].append(date)
    
    for month in sorted(missing_by_month.keys()):
        dates = missing_by_month[month]
        print(f"{month}: {len(dates)}天，日期: {', '.join(dates)}")
else:
    print("\n✅ 2025年所有日期数据都已存在！")