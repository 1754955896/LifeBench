import sys
import os
import json
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入所需模块
from event.phone_data_gen import Data_extract, FitnessHealthOperationGenerator, PushOperationGenerator, ChatOperationGenerator, extool

def main():
    """
    测试智能体对话生成功能
    """
    # 读取数据
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output', 'outputs.json')
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print("数据读取完成！")
    
    persona_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output', 'persona.json')
    with open(persona_path, 'r', encoding='utf-8') as f:
        persona = json.load(f)
    
    # 设置全局数据
    extool.events = data
    extool.persona = persona
    
    # 创建输出目录
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output', 'phone_data')
    os.makedirs(output_dir, exist_ok=True)
    
    # ------------------------------
    # 生成智能体对话数据
    # ------------------------------
    print("\n开始生成智能体对话数据...")
    chat_generator = ChatOperationGenerator()
    
    # 设置日期范围
    start_date = datetime(2025, 10, 1)
    end_date = datetime(2025, 10, 10)
    
    all_chat_results = []
    
    # 循环生成每一天的智能体对话数据
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        print(f"\n生成{date_str}的智能体对话数据...")
        
        # 生成智能体对话数据
        chat_results = chat_generator.phone_gen_agent_chat(
            date=date_str,
            contact=None,
            file_path=output_dir,
            c=[]
        )
        
        # 保存当天数据
        output_file = os.path.join(output_dir, f'event_agent_chat_{date_str}.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chat_results, f, ensure_ascii=False, indent=2)
        print(f"{date_str}的智能体对话数据已保存到{output_file}")
        
        # 累加数据到汇总列表
        all_chat_results.extend(chat_results)
        
        # 移动到下一天
        current_date += timedelta(days=1)
    
    # 保存所有日期的智能体对话数据
    all_output_file = os.path.join(output_dir, 'event_agent_chat.json')
    with open(all_output_file, 'w', encoding='utf-8') as f:
        json.dump(all_chat_results, f, ensure_ascii=False, indent=2)
    
    print("\n所有日期的智能体对话数据生成完成！")
    print(f"完整数据已保存到{all_output_file}")

if __name__ == "__main__":
    main()