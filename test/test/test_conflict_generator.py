#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
冲突问题生成器测试
"""

import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from event.qa_generator.qa_conflict_generator import QAConflictGenerator


def load_test_data():
    """从 fenghaoran 目录加载测试数据"""
    test_data_dir = r"/fenghaoran/fenghaoran"
    
    print("=" * 60)
    print("加载测试数据...")
    print("=" * 60)
    
    # 加载 daily_event
    daily_event_path = os.path.join(test_data_dir, 'daily_event.json')
    if not os.path.exists(daily_event_path):
        print(f"错误：daily_event 文件不存在：{daily_event_path}")
        return None, None, None
    
    with open(daily_event_path, 'r', encoding='utf-8') as f:
        daily_event = json.load(f)
    print(f"✓ 加载 daily_event: {len(daily_event)} 条事件")
    
    # 加载 draft_event (daily_draft.json)
    draft_event_path = os.path.join(test_data_dir, 'daily_draft.json')
    if not os.path.exists(draft_event_path):
        print(f"错误：draft_event 文件不存在：{draft_event_path}")
        return None, None, None
    
    with open(draft_event_path, 'r', encoding='utf-8') as f:
        draft_event = json.load(f)
    month_count = len([k for k in draft_event.keys() if isinstance(draft_event[k], list)])
    print(f"✓ 加载 draft_event: {month_count} 个月份的数据")
    
    # 加载 phonedata
    phonedata_path = os.path.join(test_data_dir, 'phone_data.json')
    if os.path.exists(phonedata_path):
        with open(phonedata_path, 'r', encoding='utf-8') as f:
            phonedata = json.load(f)
        sms_count = len(phonedata.get('sms', []))
        agent_chat_count = len(phonedata.get('agent_chat', []))
        print(f"✓ 加载 phonedata: SMS {sms_count} 条, Agent Chat {agent_chat_count} 条")
    else:
        print(f"警告：phonedata 文件不存在，使用空数据")
        phonedata = {
            'sms': [],
            'phonecall': [],
            'photo': [],
            'push': [],
            'note': [],
            'calendar': [],
            'agent_chat': []
        }
    
    return daily_event, draft_event, phonedata


def test_conflict_qa_generation():
    """测试冲突问答生成"""
    print("\n" + "=" * 60)
    print("测试冲突问答生成")
    print("=" * 60)
    
    try:
        # 加载测试数据
        daily_event, draft_event, phonedata = load_test_data()
        
        if not daily_event or not draft_event:
            print("\n✗ 测试数据不足，无法继续测试")
            return False
        
        # 创建生成器实例
        print("\n创建 QAConflictGenerator 实例...")
        generator = QAConflictGenerator(
            daily_event=daily_event,
            draft_event=draft_event,
            phonedata=phonedata,
            phone_data_dir=r"/fenghaoran/fenghaoran/phone_data",
            is_print=True
        )
        print("✓ 生成器创建成功")

        
        # 测试完整的 QA 生成流程（小规模）
        print("\n" + "-" * 60)
        print("测试 4: 完整 QA 生成流程（采样 2 个事件）")
        print("-" * 60)
        qa_pairs = generator.QAGen(year=2025, num_samples=1)

        if qa_pairs:
            print(f"\n✓ QA 生成成功，共生成 {len(qa_pairs)} 个问答对")

            # 显示第一个 QA 对的详细信息
            if qa_pairs:
                first_qa = qa_pairs[0]
                print(f"\n第一个 QA 对示例:")
                print(f"  问题: {first_qa.get('question', '')[:100]}...")
                print(f"  答案: {first_qa.get('answer', '')[:100]}...")
                print(f"  提问时间: {first_qa.get('ask_time', '')}")
                print(f"  问题类型: {first_qa.get('question_type', '')}")

            # 检查生成的手机数据
            generated_sms = len(phonedata.get('sms', []))
            generated_agent_chat = len(phonedata.get('agent_chat', []))
            print(f"\n生成的手机数据:")
            print(f"  - SMS: {generated_sms} 条")
            print(f"  - Agent Chat: {generated_agent_chat} 条")

            return True
        else:
            print("\n✗ QA 生成失败")
            return False
            
    except Exception as e:
        print(f"\n✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = test_conflict_qa_generation()
        if success:
            print("\n" + "=" * 60)
            print("✓ 所有测试通过！")
            print("=" * 60)
            sys.exit(0)
        else:
            print("\n" + "=" * 60)
            print("✗ 测试未通过")
            print("=" * 60)
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
