import json
import os
from event.draft.timeline_gen import TimelineGen


def test_timeline_gen():
    """
    测试TimelineGen类的功能
    使用位于D:\pyCharmProjects\pythonProject4\test\persona.json的画像数据
    """
    print("开始测试TimelineGen类...")
    
    # 读取画像数据
    persona_file_path = r"/test/persona.json"
    
    try:
        with open(persona_file_path, 'r', encoding='utf-8') as f:
            persona_data = json.load(f)
        print(f"✓ 成功加载画像数据，人物姓名: {persona_data.get('name', '未知')}")
    except FileNotFoundError:
        print(f"✗ 找不到画像数据文件: {persona_file_path}")
        return
    except json.JSONDecodeError:
        print(f"✗ 画像数据文件格式错误: {persona_file_path}")
        return
    except Exception as e:
        print(f"✗ 加载画像数据时发生错误: {str(e)}")
        return
    
    # 创建TimelineGen实例
    timeline_gen = TimelineGen(persona=persona_data, file_path='..')
    print("✓ TimelineGen实例创建成功")
    
    # 设置输出路径
    output_path = "../"
    media_path = "../process/"
    
    # 确保输出目录存在
    os.makedirs(output_path, exist_ok=True)
    os.makedirs(media_path, exist_ok=True)
    
    print("\n开始执行generate_yearly_timeline_draft方法...")
    
    try:
        # 调用主要方法生成年度时间线草稿
        # result = timeline_gen.generate_yearly_timeline_draft(
        #     persona=persona_data,
        #     output_path=output_path,
        #     meidan_path=media_path
        # )

        # 测试enhance_main_timeline方法
        print("\n开始测试enhance_main_timeline方法...")
        
        # 读取merged_timelines.json作为参考数据
        merged_timelines_path = os.path.join(media_path, "merged_timelines.json")
        if os.path.exists(merged_timelines_path):
            print(f"✓ 找到merged_timelines.json文件: {merged_timelines_path}")
            with open(merged_timelines_path, 'r', encoding='utf-8') as f:
                merged_timelines = json.load(f)
            print(f"✓ 成功加载{len(merged_timelines)}个时间线")
            
            # 选择第一个时间线作为主要时间线
            if merged_timelines:
                main_timeline = merged_timelines[0]
                print(f"✓ 选择主要时间线: {main_timeline.get('topic', '未知')}")
                
                # 选择其余时间线作为参考时间线
                reference_timelines = merged_timelines[1:3]
                print(f"✓ 选择{len(reference_timelines)}个参考时间线")
                
                # 调用enhance_main_timeline方法
                enhanced_timeline = timeline_gen.enhance_main_timeline(main_timeline, reference_timelines)
                print("✓ 成功增强主要时间线")
                
                # 打印增强后的结果
                print("\n增强后的时间线:")
                print(f"主题: {enhanced_timeline.get('topic', '未知')}")
                print(f"详细描述: {enhanced_timeline.get('detailed_description', '未知')}")
                print(f"主题类型: {enhanced_timeline.get('theme', '未知')}")
            else:
                print("✗ merged_timelines.json文件为空")
        else:
            print(f"✗ 找不到merged_timelines.json文件: {merged_timelines_path}")
            
    except Exception as e:
        print(f"✗ 执行测试时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
    



if __name__ == "__main__":
    test_timeline_gen()