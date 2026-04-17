# -*- coding: utf-8 -*-
"""测试 event_gen.py 中的 EventGenerator 类"""
import os
import json
import sys

# 添加项目根目录到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from event.draft.event_gen import EventGenerator


def test_event_generator_basic():
    """
    测试 EventGenerator 类的基本功能
    """
    print("\n" + "="*60)
    print("EventGenerator 基本功能测试")
    print("="*60)
    
    # 使用指定的测试数据路径
    test_path = os.path.join(os.path.dirname(__file__), "test")
    persona_path = os.path.join(test_path, "persona.json")
    
    if not os.path.exists(persona_path):
        print(f"✗ 测试数据不存在：{persona_path}")
        return
    
    # 加载画像数据
    try:
        with open(persona_path, 'r', encoding='utf-8') as f:
            persona = json.load(f)
        print("✓ 加载画像数据成功")
    except Exception as e:
        print(f"✗ 加载画像数据失败：{e}")
        return
    
    # 创建 EventGenerator 实例
    try:
        generator = EventGenerator(persona)
        print("✓ EventGenerator 初始化成功")
    except Exception as e:
        print(f"✗ EventGenerator 初始化失败：{e}")
        return
    
    # 测试生成事件
    print("\n开始生成事件...")
    try:
        events = generator.generate_events()
        print(f"\n✓ 事件生成成功，共生成 {len(events)} 个事件")
        
        # 打印部分事件示例
        if events:
            print(f"\n事件示例（前 3 个）：")
            for i, event in enumerate(events[:3], 1):
                print(f"\n{i}. {event[:100]}..." if len(event) > 100 else f"\n{i}. {event}")
        
        # 验证事件数量
        print(f"\n事件数量统计:")
        print(f"  - 总事件数：{len(events)}")
        print(f"  - 预期范围：26-39 个（基础 10-15 + 发展 8-12 + 他人 8-12）")
        
        if 26 <= len(events) <= 39:
            print("  ✓ 事件数量符合预期范围")
        elif len(events) < 26:
            print("  ⚠️  事件数量偏少，但可接受")
        else:
            print("  ⚠️  事件数量偏多，但可接受")
            
    except Exception as e:
        print(f"✗ 事件生成失败：{e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n🎉 EventGenerator 基本功能测试完成！")


def test_event_generator_prompts():
    """
    测试 EventGenerator 类的三个 prompt 创建方法
    """
    print("\n" + "="*60)
    print("EventGenerator Prompt 创建测试")
    print("="*60)
    
    # 使用简化的测试画像
    test_persona = {
        "name": "张三",
        "age": 25,
        "gender": "男",
        "occupation": "软件工程师",
        "city": "北京",
        "interests": ["编程", "阅读", "运动"]
    }
    
    try:
        generator = EventGenerator(test_persona)
        print("✓ EventGenerator 初始化成功")
    except Exception as e:
        print(f"✗ EventGenerator 初始化失败：{e}")
        return
    
    # 测试基础事件 prompt
    print("\n测试 1：基础事件 prompt")
    try:
        base_prompt = generator._create_base_events_prompt()
        print("✓ 基础事件 prompt 创建成功")
        print(f"  Prompt 长度：{len(base_prompt)} 字符")
        if "人群特征导向" in base_prompt and "常识性年度事件" in base_prompt:
            print("  ✓ Prompt 包含预期的创作方向")
        else:
            print("  ✗ Prompt 内容可能不完整")
    except Exception as e:
        print(f"✗ 基础事件 prompt 创建失败：{e}")
    
    # 测试发展事件 prompt
    print("\n测试 2：变化发展事件 prompt")
    try:
        development_prompt = generator._create_development_events_prompt()
        print("✓ 变化发展事件 prompt 创建成功")
        print(f"  Prompt 长度：{len(development_prompt)} 字符")
        if "变化和发展" in development_prompt and "个人成长" in development_prompt:
            print("  ✓ Prompt 聚焦于变化和发展主题")
        else:
            print("  ✗ Prompt 主题可能不明确")
    except Exception as e:
        print(f"✗ 变化发展事件 prompt 创建失败：{e}")
    
    # 测试他人事件 prompt
    print("\n测试 3：身边人/他人相关事件 prompt")
    try:
        others_prompt = generator._create_others_events_prompt()
        print("✓ 他人事件 prompt 创建成功")
        print(f"  Prompt 长度：{len(others_prompt)} 字符")
        if "身边人和他人的事件" in others_prompt and "家庭成员" in others_prompt:
            print("  ✓ Prompt 聚焦于他人事件主题")
        else:
            print("  ✗ Prompt 主题可能不明确")
    except Exception as e:
        print(f"✗ 他人事件 prompt 创建失败：{e}")
    
    print("\n🎉 Prompt 创建测试完成！")


def test_event_generator_parallel():
    """
    测试 EventGenerator 类的并行生成能力
    """
    print("\n" + "="*60)
    print("EventGenerator 并行生成测试")
    print("="*60)
    
    # 使用测试数据
    test_path = os.path.join(os.path.dirname(__file__), "test")
    persona_path = os.path.join(test_path, "persona.json")
    
    if not os.path.exists(persona_path):
        print(f"✗ 测试数据不存在：{persona_path}")
        return
    
    try:
        with open(persona_path, 'r', encoding='utf-8') as f:
            persona = json.load(f)
        generator = EventGenerator(persona)
    except Exception as e:
        print(f"✗ 初始化失败：{e}")
        return
    
    # 测试并行生成
    print("\n开始并行生成事件（使用 ThreadPoolExecutor）...")
    import time
    start_time = time.time()
    
    try:
        events = generator.generate_events()
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        print(f"\n✓ 并行生成完成，耗时：{elapsed_time:.2f} 秒")
        print(f"✓ 生成事件总数：{len(events)}")
        print(f"✓ 平均每个事件耗时：{elapsed_time / len(events):.2f} 秒（如果串行会更长）")
        
        # 打印所有事件
        print("\n" + "="*60)
        print("生成的所有事件")
        print("="*60)
        print(f"\n共 {len(events)} 个事件:\n")
        
        for i, event in enumerate(events, 1):
            event_preview = event[:150] + "..." if len(event) > 150 else event
            print(f"{i:3d}. {event_preview}")
            print()
        
    except Exception as e:
        print(f"✗ 并行生成失败：{e}")
        import traceback
        traceback.print_exc()
    
    print("\n🎉 并行生成测试完成！")


def test_event_generator_output_format():
    """
    测试 EventGenerator 输出格式的正确性
    """
    print("\n" + "="*60)
    print("EventGenerator 输出格式测试")
    print("="*60)
    
    # 使用测试数据
    test_path = os.path.join(os.path.dirname(__file__), "test")
    persona_path = os.path.join(test_path, "persona.json")
    
    if not os.path.exists(persona_path):
        print(f"✗ 测试数据不存在：{persona_path}")
        return
    
    try:
        with open(persona_path, 'r', encoding='utf-8') as f:
            persona = json.load(f)
        generator = EventGenerator(persona)
    except Exception as e:
        print(f"✗ 初始化失败：{e}")
        return
    
    # 生成事件
    try:
        events = generator.generate_events()
        print(f"\n✓ 生成了 {len(events)} 个事件")
    except Exception as e:
        print(f"✗ 事件生成失败：{e}")
        return
    
    # 验证输出格式
    print("\n验证输出格式：")
    
    # 测试 1：检查是否为列表
    if isinstance(events, list):
        print("✓ 输出类型为列表（list）")
    else:
        print(f"✗ 输出类型错误，应为 list，实际为 {type(events)}")
        return
    
    # 测试 2：检查每个元素是否为字符串
    all_strings = True
    non_string_indices = []
    for i, event in enumerate(events):
        if not isinstance(event, str):
            all_strings = False
            non_string_indices.append(i)
    
    if all_strings:
        print("✓ 所有事件都是字符串格式")
    else:
        print(f"✗ 有 {len(non_string_indices)} 个事件不是字符串：索引 {non_string_indices[:5]}")
    
    # 测试 3：检查字符串内容的完整性
    valid_events = []
    for i, event in enumerate(events):
        if len(event.strip()) > 20:  # 至少应该有 20 个字符
            valid_events.append(event)
        else:
            print(f"⚠️  事件 {i} 内容过短：'{event[:30]}'")
    
    print(f"✓ 有效事件数量：{len(valid_events)}/{len(events)}")
    
    # 测试 4：检查是否包含关键信息
    print("\n抽样检查事件内容质量：")
    sample_size = min(3, len(valid_events))
    for i in range(sample_size):
        event = valid_events[i]
        has_time = any(time_word in event for time_word in ["2025 年", "月", "日", "年初", "年底", "春天", "夏天", "秋天", "冬天"])
        has_person = any(person_word in event for person_word in ["他", "她", "人物", "朋友", "家人", "同事"])
        has_detail = len(event) >= 50  # 详细描述至少 50 字
        
        print(f"  事件 {i+1}:")
        print(f"    - 包含时间信息：{'✓' if has_time else '✗'}")
        print(f"    - 包含人物信息：{'✓' if has_person else '✗'}")
        print(f"    - 描述详细：{'✓' if has_detail else '✗'}")
    
    print("\n🎉 输出格式测试完成！")


if __name__ == "__main__":
    # 运行所有测试
    print("\n" + "="*60)
    print("开始执行 EventGenerator 完整测试套件")
    print("="*60)
    
    # test_event_generator_basic()
    # test_event_generator_prompts()
    test_event_generator_parallel()
    #test_event_generator_output_format()
    
    print("\n" + "="*60)
    print("所有测试执行完毕！")
    print("="*60)
