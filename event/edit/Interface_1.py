#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
用户循环对话接口
实现与用户的交互，调用 WritingAgent 实现时间线情节数据的协作创作
"""

import os
import sys
import json

# 添加项目根目录到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from event.edit.writing_agent import WritingAgent


def get_base_path():
    """获取基础路径"""
    # 默认路径 - 使用绝对路径
    default_path = r"D:\pyCharmProjects\pythonProject4\test"
    
    # 检查默认路径是否存在
    if os.path.exists(default_path):
        return default_path
    
    # 如果不存在，提示用户输入
    print(f"默认基础路径不存在: {default_path}")
    user_input = input("请输入基础路径: ").strip()
    if user_input and os.path.exists(user_input):
        return user_input
    
    # 如果用户输入的路径也不存在，使用默认路径
    print("使用默认路径，可能会导致错误")
    return default_path


def save_plot(plot, file_path):
    """保存情节数据到文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(plot, f, ensure_ascii=False, indent=2)
        print(f"情节数据已保存到: {file_path}")
    except Exception as e:
        print(f"保存情节数据失败: {e}")


def display_plot(plot):
    """显示情节数据"""
    print("\n当前时间线情节:")
    print("=" * 60)
    
    # 显示综合摘要
    print("综合摘要:")
    print(plot.get("comprehensive_summary", "无"))
    print()
    
    # 显示月度详情
    print("月度详情:")
    for month in plot.get("monthly_details", []):
        month_str = month.get("month", "未知")
        events = month.get("events", [])
        main_topics = month.get("main topics", [])
        changes = month.get("changes", "")
        
        print(f"{month_str}:")
        print(f"  事件: {', '.join(events) if events else '无'}")
        print(f"  主题: {', '.join(main_topics) if main_topics else '无'}")
        print(f"  变化: {changes if changes else '无'}")
        print()
    
    print("=" * 60)


def main():
    """主函数"""
    print("=" * 60)
    print("欢迎使用时间线情节协作创作系统")
    print("输入您的创作指令，或输入 'exit' 退出，输入 'undo' 撤销上一次修改")
    print("输入 '帮我自动优化' 自动优化当前情节")
    print("=" * 60)
    
    # 获取基础路径
    base_path = get_base_path()
    print(f"使用基础路径: {base_path}")
    
    # 初始化 WritingAgent
    try:
        writing_agent = WritingAgent(path=base_path)
        print("WritingAgent 初始化成功")
    except Exception as e:
        print(f"WritingAgent 初始化失败: {e}")
        return
    
    # 初始化当前情节
    current_plot = writing_agent.initial_plot.copy()
    
    # 显示初始情节
    display_plot(current_plot)
    
    while True:
        # 获取用户输入
        user_input = input("\n请输入创作指令: ").strip()
        
        if user_input.lower() == 'exit':
            print("退出系统")
            # 询问是否保存
            save_input = input("是否保存当前情节? (y/n): ").strip().lower()
            if save_input == 'y':
                save_path = input("请输入保存路径: ").strip()
                if not save_path:
                    save_path = os.path.join(os.path.dirname(__file__), '..', '..', 'plot_result.json')
                save_plot(current_plot, save_path)
            break
        
        if not user_input:
            continue
        
        # 处理用户输入
        print(f"\n处理指令: {user_input}")
        print("-" * 60)
        
        try:
            # 调用 WritingAgent 进行交互
            result = writing_agent.interact_with_user(user_input, current_plot)
            
            # 检查是否为结束指令
            if result is None:
                print("退出系统")
                # 询问是否保存
                save_input = input("是否保存当前情节? (y/n): ").strip().lower()
                if save_input == 'y':
                    save_path = input("请输入保存路径: ").strip()
                    if not save_path:
                        save_path = os.path.join(os.path.dirname(__file__), '..', '..', 'plot_result.json')
                    save_plot(current_plot, save_path)
                break
            
            # 更新当前情节并显示
            current_plot = result
            display_plot(current_plot)
        except Exception as e:
            print(f"处理指令时出错: {e}")


if __name__ == "__main__":
    main()