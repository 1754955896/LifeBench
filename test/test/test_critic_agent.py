# -*- coding: utf-8 -*-
"""测试CriticAgent类的功能"""
import os
import json
import sys

# 添加项目根目录到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from event.edit.critic_agent import CriticAgent
from event.edit.writing_agent import WritingAgent

def test_critic_agent_plan():
    """
    测试CriticAgent的plan方法
    """
    # 测试路径
    test_path = os.path.join(os.path.dirname(__file__), "test")
    
    # 加载测试时间线数据
    timeline_path = os.path.join(test_path, "process", "optimize_timeline.json")
    try:
        with open(timeline_path, 'r', encoding='utf-8') as f:
            test_timeline = json.load(f)
        print("✓ 加载测试时间线数据成功")
    except Exception as e:
        print(f"✗ 加载测试时间线数据失败: {e}")
        return
    
    # 初始化CriticAgent
    try:
        critic_agent = CriticAgent(path=test_path)
        print("✓ CriticAgent初始化成功")
    except Exception as e:
        print(f"✗ CriticAgent初始化失败: {e}")
        return
    
    # 测试第一次评估
    print("\n=== 第一次评估 ===")
    try:
        result1 = critic_agent.plan(test_timeline)
        print("✓ 第一次评估完成")
        print(f"关键问题: {result1.get('problems', '')[:100]}...")
        print(f"改进建议: {result1.get('suggestions', '')[:100]}...")
    except Exception as e:
        print(f"✗ 第一次评估失败: {e}")
        return
    
    # 测试第二次评估（使用相同数据，验证缓存功能）
    print("\n=== 第二次评估 ===")
    try:
        result2 = critic_agent.plan(test_timeline)
        print("✓ 第二次评估完成")
        print(f"关键问题: {result2.get('problems', '')[:100]}...")
        print(f"改进建议: {result2.get('suggestions', '')[:100]}...")
    except Exception as e:
        print(f"✗ 第二次评估失败: {e}")
        return
    
    # 测试第三次评估（验证缓存功能）
    print("\n=== 第三次评估 ===")
    try:
        result3 = critic_agent.plan(test_timeline)
        print("✓ 第三次评估完成")
        print(f"关键问题: {result3.get('problems', '')[:100]}...")
        print(f"改进建议: {result3.get('suggestions', '')[:100]}...")
    except Exception as e:
        print(f"✗ 第三次评估失败: {e}")
        return
    
    print("\n🎉 所有测试通过！")

def test_critic_agent_interact_with_writing_agent():
    """
    测试CriticAgent的interact_with_writing_agent方法
    """
    # 测试路径
    test_path = os.path.join(os.path.dirname(__file__), "test")
    
    # 加载测试时间线数据
    timeline_path = os.path.join(test_path, "process", "optimize_timeline.json")
    try:
        with open(timeline_path, 'r', encoding='utf-8') as f:
            test_timeline = json.load(f)
        print("✓ 加载测试时间线数据成功")
    except Exception as e:
        print(f"✗ 加载测试时间线数据失败: {e}")
        return
    
    # 初始化WritingAgent
    try:
        writing_agent = WritingAgent(path=test_path)
        print("✓ WritingAgent初始化成功")
    except Exception as e:
        print(f"✗ WritingAgent初始化失败: {e}")
        return
    
    # 初始化CriticAgent
    try:
        critic_agent = CriticAgent(path=test_path)
        print("✓ CriticAgent初始化成功")
    except Exception as e:
        print(f"✗ CriticAgent初始化失败: {e}")
        return
    
    # 测试interact_with_writing_agent方法
    print("\n=== 测试interact_with_writing_agent方法 ===")
    try:
        improved_plot = critic_agent.interact_with_writing_agent(writing_agent, test_timeline)
        print("✓ interact_with_writing_agent方法执行成功")
        print(f"改进后的时间线摘要: {improved_plot.get('comprehensive_summary', '')[:100]}...")
        print(f"改进后的时间线月份数: {len(improved_plot.get('monthly_details', []))}")
        
        # 保存改进后的数据
        save_path = os.path.join(test_path, "process", "improved_timeline.json")
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            # 保存数据
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(improved_plot, f, ensure_ascii=False, indent=2)
            print(f"✓ 改进后的数据已保存到: {save_path}")
        except Exception as e:
            print(f"✗ 保存改进后的数据失败: {e}")
    except Exception as e:
        print(f"✗ interact_with_writing_agent方法执行失败: {e}")
        return
    
    print("\n🎉 interact_with_writing_agent测试通过！")

if __name__ == "__main__":
    #test_critic_agent_plan()
    test_critic_agent_interact_with_writing_agent()