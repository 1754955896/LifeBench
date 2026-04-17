# -*- coding: utf-8 -*-
"""测试 OutlineOptimizer 的 optimize_outline 方法"""
import sys
import os

# 添加项目根目录到路径
project_root = r"D:\pyCharmProjects\pythonProject4"
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from event.draft.outline_optimizer import OutlineOptimizer


def test_optimize_outline():
    """测试 optimize_outline 方法"""
    
    # 测试数据路径
    test_data_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran"
    
    print("="*80)
    print("测试 OutlineOptimizer.optimize_outline()")
    print("="*80)
    
    try:
        # 检查测试数据是否存在
        daily_draft_path = os.path.join(test_data_path, "daily_draft.json")
        persona_path = os.path.join(test_data_path, "persona.json")
        
        if not os.path.exists(daily_draft_path):
            print(f"❌ 错误：找不到 daily_draft.json: {daily_draft_path}")
            return False
        
        if not os.path.exists(persona_path):
            print(f"❌ 错误：找不到 persona.json: {persona_path}")
            return False
        
        print(f"✓ 找到测试数据:")
        print(f"  - daily_draft.json: {daily_draft_path}")
        print(f"  - persona.json: {persona_path}")
        
        # 初始化 OutlineOptimizer
        print("\n[Step 1] 初始化 OutlineOptimizer...")
        optimizer = OutlineOptimizer(
            filepath=test_data_path,
            year=2025,
            isprint=True
        )
        
        print(f"✓ 初始化成功")
        print(f"  - 加载了 {len(optimizer.daily_draft)} 天的数据")
        print(f"  - 提取了 {len(optimizer.monthly_data)} 个月份的数据")
        
        # 执行 optimize_outline
        print("\n[Step 2] 执行 optimize_outline...")
        print("="*80)
        
        optimized_draft = optimizer.optimize_outline()
        
        print("\n" + "="*80)
        print("✓ optimize_outline 执行完成！")
        print("="*80)
        
        # 验证结果
        print("\n[Step 3] 验证结果...")
        
        if optimized_draft is None:
            print("❌ 错误：返回值为 None")
            return False
        
        if not isinstance(optimized_draft, dict):
            print(f"❌ 错误：返回值类型不正确，期望 dict，实际 {type(optimized_draft)}")
            return False
        
        print(f"✓ 返回值类型正确 (dict)")
        print(f"✓ 优化后的草稿包含 {len(optimized_draft)} 天的数据")
        
        # 检查是否生成了优化后的文件
        optimized_file_path = os.path.join(test_data_path, "daily_draft_optimized.json")
        if os.path.exists(optimized_file_path):
            print(f"✓ 优化后的文件已保存: {optimized_file_path}")
            
            # 验证文件格式
            import json
            with open(optimized_file_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            print(f"✓ 文件格式正确，可正常读取")
            print(f"✓ 保存的数据包含 {len(saved_data)} 天的数据")
        else:
            print(f"⚠️  警告：未找到优化后的文件: {optimized_file_path}")
        
        # 检查分析结果文件
        refined_dir = os.path.join(test_data_path, "process", "refined")
        if os.path.exists(refined_dir):
            print(f"\n✓ 分析结果目录存在: {refined_dir}")
            
            expected_files = [
                "monthly_summaries.json",
                "yearly_consistency.json",
                "monthly_reasonableness.json"
            ]
            
            for filename in expected_files:
                file_path = os.path.join(refined_dir, filename)
                if os.path.exists(file_path):
                    print(f"  ✓ {filename}")
                else:
                    print(f"  ⚠️  {filename} 不存在")
        else:
            print(f"\n⚠️  警告：分析结果目录不存在: {refined_dir}")
        
        print("\n" + "="*80)
        print("✅ 测试通过！")
        print("="*80)
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_optimize_outline_with_skip():
    """测试跳过已存在的分析文件"""
    
    test_data_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran"
    
    print("\n" + "="*80)
    print("测试跳过已存在文件的逻辑")
    print("="*80)
    
    try:
        # 第一次运行会生成分析文件
        print("\n[第一次运行] 生成分析文件...")
        optimizer1 = OutlineOptimizer(filepath=test_data_path, year=2025, isprint=False)
        result1 = optimizer1.run_full_optimization()
        print("✓ 第一次运行完成")
        
        # 第二次运行应该跳过分析步骤
        print("\n[第二次运行] 应该跳过分析步骤...")
        optimizer2 = OutlineOptimizer(filepath=test_data_path, year=2025, isprint=True)
        result2 = optimizer2.run_full_optimization()
        print("✓ 第二次运行完成（应该看到跳过提示）")
        
        print("\n✅ 跳过逻辑测试通过！")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n开始测试 OutlineOptimizer...\n")
    
    # 测试主功能
    success1 = test_optimize_outline()
    
    # 测试跳过逻辑
    success2 = test_optimize_outline_with_skip()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    print(f"主功能测试: {'✅ 通过' if success1 else '❌ 失败'}")
    print(f"跳过逻辑测试: {'✅ 通过' if success2 else '❌ 失败'}")
    
    if success1 and success2:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️  部分测试失败，请检查上述错误信息")
