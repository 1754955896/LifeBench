# -*- coding: utf-8 -*-
"""
有害记忆生成器测试文件
测试 generate_privacydata 和 generate_biasdata 方法
"""

import json
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from event.qa_generator.qa_harmful_memory_generator import QAHarmfulMemoryGenerator


def load_test_data():
    """从 fenghaoran 目录加载测试数据"""
    print("正在加载测试数据...")
    test_data_dir = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran"
    
    # 加载 daily_event
    daily_event_path = os.path.join(test_data_dir, 'daily_event.json')
    if not os.path.exists(daily_event_path):
        print(f"错误：daily_event 文件不存在：{daily_event_path}")
        return None, None, None, None
    
    with open(daily_event_path, 'r', encoding='utf-8') as f:
        daily_event = json.load(f)
    print(f"✓ 加载 daily_event: {len(daily_event)} 条")
    
    # 加载 draft_event (daily_draft.json)
    draft_event_path = os.path.join(test_data_dir, 'daily_draft.json')
    if not os.path.exists(draft_event_path):
        print(f"错误：draft_event 文件不存在：{draft_event_path}")
        return None, None, None, None
    
    with open(draft_event_path, 'r', encoding='utf-8') as f:
        draft_event = json.load(f)
    print(f"✓ 加载 draft_event: {len(draft_event)} 个月")
    
    # 加载 phonedata
    phonedata = {}
    phonedata_types = ['sms', 'phonecall', 'photo', 'push', 'note', 'calendar', 'agent_chat']
    total_count = 0
    
    for data_type in phonedata_types:
        phonedata_file = os.path.join(test_data_dir, f'phone_data/{data_type}.json')
        if os.path.exists(phonedata_file):
            with open(phonedata_file, 'r', encoding='utf-8') as f:
                phonedata[data_type] = json.load(f)
            count = len(phonedata[data_type])
            total_count += count
            print(f"✓ 加载 {data_type}: {count} 条")
    
    print(f"✓ 总共加载 phonedata: {total_count} 条")
    
    # 加载 persona
    persona_path = os.path.join(test_data_dir, 'persona.json')
    persona = None
    if os.path.exists(persona_path):
        with open(persona_path, 'r', encoding='utf-8') as f:
            persona = json.load(f)
        print(f"✓ 加载 persona: {persona.get('name', '')}")
    else:
        print(f"警告：persona 文件不存在：{persona_path}")
    
    return daily_event, draft_event, phonedata, persona


def test_generate_privacydata():
    """测试隐私数据生成"""
    print("\n" + "="*80)
    print("测试 1: generate_privacydata")
    print("="*80)
    
    # 加载测试数据
    daily_event, draft_event, phonedata, persona = load_test_data()
    if not daily_event:
        print("跳过测试：无法加载测试数据")
        return False
    
    # 创建生成器
    generator = QAHarmfulMemoryGenerator(
        daily_event=daily_event,
        draft_event=draft_event,
        phonedata=phonedata,
        phone_data_dir=r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran",
        is_print=True,
        persona=persona
    )
    
    try:
        # 执行生成
        result = generator.generate_privacydata(year=2025)
        
        if not result:
            print("✗ 测试失败：生成结果为空")
            return False
        
        # 验证结果结构
        print("\n验证结果结构...")
        required_keys = ['metadata', 'privacy_data', 'target_events_count', 
                        'injected_operations', 'conversations', 'test_questions', 'statistics']
        
        for key in required_keys:
            if key not in result:
                print(f"✗ 缺少必需字段: {key}")
                return False
        
        print("✓ 结果结构完整")
        
        # 验证隐私数据
        print("\n验证隐私数据...")
        privacy_data = result['privacy_data']
        if 'id_card' not in privacy_data or not privacy_data['id_card']:
            print("✗ 缺少身份证号")
            return False
        if 'bank_account' not in privacy_data or not privacy_data['bank_account']:
            print("✗ 缺少银行账户")
            return False
        if 'passwords' not in privacy_data or len(privacy_data['passwords']) == 0:
            print("✗ 缺少密码数据")
            return False
        
        print(f"✓ 隐私数据完整：")
        print(f"  - 身份证号: {privacy_data['id_card']}")
        print(f"  - 银行账户: {privacy_data['bank_account']}")
        print(f"  - 密码数量: {len(privacy_data['passwords'])}")
        
        # 验证手机操作
        print("\n验证手机操作...")
        operations = result['injected_operations']
        if len(operations) == 0:
            print("✗ 没有生成手机操作")
            return False
        
        print(f"✓ 生成了 {len(operations)} 条手机操作")
        for i, op in enumerate(operations[:2]):
            print(f"  操作 {i+1}: type={op.get('type')}, event_id={op.get('event_id')}")
        
        # 验证对话
        print("\n验证对话数据...")
        conversations = result['conversations']
        if len(conversations) == 0:
            print("✗ 没有生成对话")
            return False
        
        print(f"✓ 生成了 {len(conversations)} 条对话")
        
        # 验证测试问题
        print("\n验证测试问题...")
        questions = result['test_questions']
        if len(questions) == 0:
            print("✗ 没有生成测试问题")
            return False
        
        print(f"✓ 生成了 {len(questions)} 个测试问题")
        for i, q in enumerate(questions[:3]):
            print(f"  问题 {i+1}: {q['question'][:60]}...")
            print(f"    答案: {q['answer']}")
            print(f"    类型: {q.get('sensitive_info_type', 'N/A')}")
        
        # 验证统计信息
        print("\n验证统计信息...")
        stats = result['statistics']
        print(f"✓ 统计信息：")
        print(f"  - 操作数量: {stats['operations_generated']}")
        print(f"  - 对话数量: {stats['conversations_generated']}")
        print(f"  - 问题数量: {stats['questions_generated']}")
        
        # 检查输出文件
        output_file = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran\privacy_data.json"
        if os.path.exists(output_file):
            print(f"\n✓ 输出文件已保存: {output_file}")
            with open(output_file, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            print(f"  文件大小: {os.path.getsize(output_file)} bytes")
        else:
            print(f"\n✗ 输出文件不存在: {output_file}")
        
        print("\n" + "="*80)
        print("✓ 测试通过：generate_privacydata")
        print("="*80)
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_generate_biasdata():
    """测试偏见数据生成"""
    print("\n" + "="*80)
    print("测试 2: generate_biasdata")
    print("="*80)
    
    # 加载测试数据
    daily_event, draft_event, phonedata = load_test_data()
    if not daily_event:
        print("跳过测试：无法加载测试数据")
        return False
    
    # 创建生成器
    generator = QAHarmfulMemoryGenerator(
        daily_event=daily_event,
        draft_event=draft_event,
        phonedata=phonedata,
        phone_data_dir="./test_output/bias",
        is_print=True
    )
    
    try:
        # 执行生成
        result = generator.generate_biasdata(year=2025)
        
        if not result:
            print("✗ 测试失败：生成结果为空")
            return False
        
        # 验证结果结构
        print("\n验证结果结构...")
        required_keys = ['metadata', 'bias_topics', 'target_events_count', 
                        'injected_conversations', 'test_questions', 'statistics']
        
        for key in required_keys:
            if key not in result:
                print(f"✗ 缺少必需字段: {key}")
                return False
        
        print("✓ 结果结构完整")
        
        # 验证偏见话题
        print("\n验证偏见话题...")
        bias_topics = result['bias_topics']
        if len(bias_topics) == 0:
            print("✗ 没有生成偏见话题")
            return False
        
        print(f"✓ 生成了 {len(bias_topics)} 个偏见话题")
        for i, topic in enumerate(bias_topics[:5]):
            print(f"  {i+1}. {topic[:80]}...")
        
        # 验证对话
        print("\n验证对话数据...")
        conversations = result['injected_conversations']
        if len(conversations) == 0:
            print("✗ 没有生成对话")
            return False
        
        print(f"✓ 生成了 {len(conversations)} 条对话")
        for i, conv in enumerate(conversations[:3]):
            print(f"  对话 {i+1}: type={conv.get('type')}, contact={conv.get('contact_name', 'N/A')}")
            print(f"    内容: {conv.get('content', '')[:60]}...")
        
        # 验证测试问题
        print("\n验证测试问题...")
        questions = result['test_questions']
        if len(questions) == 0:
            print("✗ 没有生成测试问题")
            return False
        
        print(f"✓ 生成了 {len(questions)} 个测试问题")
        for i, q in enumerate(questions[:3]):
            print(f"  问题 {i+1}: {q['question'][:60]}...")
            print(f"    答案: {q['answer']}")
            print(f"    偏见类型: {q.get('bias_type', 'N/A')}")
            print(f"    期望行为: {q.get('expected_behavior', 'N/A')}")
        
        # 验证统计信息
        print("\n验证统计信息...")
        stats = result['statistics']
        print(f"✓ 统计信息：")
        print(f"  - 话题数量: {stats['topics_generated']}")
        print(f"  - 对话数量: {stats['conversations_generated']}")
        print(f"  - 问题数量: {stats['questions_generated']}")
        
        # 检查输出文件
        output_file = "./test_output/bias/bias_data.json"
        if os.path.exists(output_file):
            print(f"\n✓ 输出文件已保存: {output_file}")
            with open(output_file, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            print(f"  文件大小: {os.path.getsize(output_file)} bytes")
        else:
            print(f"\n✗ 输出文件不存在: {output_file}")
        
        print("\n" + "="*80)
        print("✓ 测试通过：generate_biasdata")
        print("="*80)
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "="*80)
    print("开始测试 QAHarmfulMemoryGenerator")
    print("="*80)
    
    results = {}
    
    # 测试隐私数据生成
    results['privacy'] = test_generate_privacydata()
    
    # 测试偏见数据生成
    results['bias'] = test_generate_biasdata()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    print(f"generate_privacydata: {'✓ 通过' if results['privacy'] else '✗ 失败'}")
    print(f"generate_biasdata: {'✓ 通过' if results['bias'] else '✗ 失败'}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n✓ 所有测试通过！")
        return 0
    else:
        print(f"\n✗ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit(main())
