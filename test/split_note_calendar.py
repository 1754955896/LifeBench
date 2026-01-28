import json
import os

# 输入文件路径
input_file = 'D:\\pyCharmProjects\\pythonProject4\\xujing\\phone_data\\event_note.json'

# 输出文件路径
output_dir = 'D:\\pyCharmProjects\\pythonProject4\\xujing\\phone_data'
note_output = os.path.join(output_dir, 'note.json')
calendar_output = os.path.join(output_dir, 'calendar.json')

# 读取输入文件
with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 初始化分类列表
notes = []
calendars = []

# 遍历数据进行分类
for item in data:
    if item['type'] == 'note':
        notes.append(item)
    elif item['type'] == 'calendar':
        calendars.append(item)

# 保存note.json
with open(note_output, 'w', encoding='utf-8') as f:
    json.dump(notes, f, ensure_ascii=False, indent=2)

# 保存calendar.json
with open(calendar_output, 'w', encoding='utf-8') as f:
    json.dump(calendars, f, ensure_ascii=False, indent=2)

print(f"成功将数据分类保存到：")
print(f"- note.json: {len(notes)} 条记录")
print(f"- calendar.json: {len(calendars)} 条记录")