# 测试感知数据生成器
from event.phone_data_gen import PerceptionDataGenerator, extool
import json
import os

if __name__ == "__main__":
    # 示例一天的日期
    date = "2025-01-01"
    
    # 尝试加载示例事件数据（如果存在）
    data_dir = 'output/xujing/output/outputs.json'
    with open(data_dir, 'r', encoding='utf-8') as f:
        events = json.load(f)
    data_dir = 'output/xujing/persona.json'
    with open(data_dir, 'r', encoding='utf-8') as f:
        persona = json.load(f)
    data_dir = 'output/xujing/daily_draft.json'
    with open(data_dir, 'r', encoding='utf-8') as f:
        daily_draft = json.load(f)
    extool.load_from_json(events, persona, daily_draft)
    print(extool.getstatus('2025-01-01'))
    # # 创建感知数据生成器实例（使用默认的事件类型列表）
    # perception_generator = PerceptionDataGenerator()
    #
    # # 生成感知数据
    # perception_data = perception_generator.generate_perception_data(date)
    #
    # # 打印生成的感知数据
    # print("生成的感知数据：")
    # print(json.dumps(perception_data, ensure_ascii=False, indent=2))