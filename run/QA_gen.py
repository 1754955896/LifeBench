import os
import sys
import argparse
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入qa_generator模块
from event.qa_generator import QAGenerator

def main():
    # 创建参数解析器
    parser = argparse.ArgumentParser(description='问答生成器 - 生成各类问答对')
    
    # 添加参数，支持默认值
    parser.add_argument('--data-path', type=str, default='output/fenghaoran/', help='用户数据路径，包含persona.json、event_tree.json等文件')
    parser.add_argument('--year', type=int, default=2025, help='生成问答的年份，例如：2025')
    
    # 解析参数
    args = parser.parse_args()
    
    try:
        # 初始化问答生成器
        print(f"正在初始化问答生成器，数据路径：{args.data_path}")
        qa_generator = QAGenerator(data_path=args.data_path)
        
        # 从rich_timeline.json文件中加载themes和event_id_groups数据
        rich_timeline_path = os.path.join(args.data_path, "process", "rich_timeline.json")
        themes = None
        event_id_groups = None
        
        if os.path.exists(rich_timeline_path):
            print(f"正在从 {rich_timeline_path} 加载数据...")
            with open(rich_timeline_path, 'r', encoding='utf-8') as f:
                rich_timeline_data = json.load(f)
            
            # 读取same_theme_arr数据
            if "same_theme_arr" in rich_timeline_data:
                themes = rich_timeline_data["same_theme_arr"]
                print(f"已加载same_theme_arr数据，共 {len(themes)} 个主题")
            else:
                print("警告：rich_timeline.json中没有找到same_theme_arr字段")
            
            # 读取frequency_id_groups数据
            if "frequency_id_groups" in rich_timeline_data:
                event_id_groups = rich_timeline_data["frequency_id_groups"]
                print(f"已加载frequency_id_groups数据，共 {len(event_id_groups)} 个事件组")
            else:
                print("警告：rich_timeline.json中没有找到frequency_id_groups字段")
        else:
            print(f"警告：rich_timeline.json文件不存在: {rich_timeline_path}")
        
        # 生成所有问答对
        qa_generator.generate_all_qa(year=args.year, themes=themes, event_id_groups=event_id_groups)
        
        print("\n问答生成任务已完成！")
        
    except Exception as e:
        print(f"执行过程中发生错误：{str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()