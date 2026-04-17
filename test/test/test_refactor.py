# -*- coding: utf-8 -*-
"""
测试脚本：验证所有 QA 生成器的功能
测试范围：
1. QASingleGenerator - 单跳问题生成器
2. QAMultiHopGenerator - 多跳问题生成器
3. QAPatternRecognitionGenerator - 模式识别问题生成器
4. QAReasoningGenerator - 推理问题生成器
"""

import os
import sys
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event.qa_generator.qa_single_generator import QASingleGenerator
from event.qa_generator.qa_multi_hop_generator import QAMultiHopGenerator
from event.qa_generator.qa_pattern_recognition_generator import QAPatternRecognitionGenerator
from event.qa_generator.qa_reasoning_generator import QAReasoningGenerator
from event.qa_generator.base_generator import BaseQAGenerator


def create_test_data():
    """创建测试数据"""
    persona = {
        "basic_info": {
            "name": "测试用户",
            "age": 25,
            "gender": "男",
            "occupation": "软件工程师"
        },
        "relation": [
            [
                {"name": "张三", "relation": "朋友", "birth_date": "1995-01-01", "occupation": "教师"},
                {"name": "李四", "relation": "同事", "birth_date": "1996-02-02", "occupation": "产品经理"}
            ]
        ],
        "habit": ["早起", "运动", "阅读"],
        "preference": ["咖啡", "篮球", "科技"]
    }
    
    event_tree = [
        {
            "event_id": 1,
            "title": "项目开发",
            "date": ["2025-01-01 至 2025-01-20"],
            "subevent": [
                {
                    "event_id": 2,
                    "title": "需求分析",
                    "date": ["2025-01-01 至 2025-01-05"]
                },
                {
                    "event_id": 3,
                    "title": "编码实现",
                    "date": ["2025-01-06 至 2025-01-15"]
                }
            ]
        }
    ]
    
    daily_event = [
        {
            "id": 1,
            "date": ["2025-01-01 上午"],
            "title": "开会讨论项目",
            "content": "与团队讨论新项目的开发计划"
        },
        {
            "id": 2,
            "date": ["2025-01-02 下午"],
            "title": "编写代码",
            "content": "实现核心功能模块"
        }
    ]
    
    draft_event = {
        "2025-01": [
            {
                "date": "2025-01-01",
                "events": [{"title": "新年聚会", "time": "晚上"}]
            }
        ]
    }
    
    special_event = {
        "unique_events": [
            {"event_id": 100, "title": "特殊事件", "date": "2025-01-15"}
        ]
    }
    
    return persona, event_tree, daily_event, draft_event, special_event


def load_real_data(data_path: str):
    """从指定路径加载真实数据"""
    print(f"正在从 {data_path} 加载真实数据...")
    
    # 加载用户画像
    persona_path = os.path.join(data_path, "persona.json")
    if os.path.exists(persona_path):
        with open(persona_path, 'r', encoding='utf-8') as f:
            persona = json.load(f)
        print(f"✓ 已加载 persona.json")
    else:
        print(f"✗ 未找到 persona.json")
        persona = {}
    
    # 加载事件树数据
    event_tree_path = os.path.join(data_path, "event_tree.json")
    if os.path.exists(event_tree_path):
        with open(event_tree_path, 'r', encoding='utf-8') as f:
            event_tree = json.load(f)
        print(f"✓ 已加载 event_tree.json")
    else:
        print(f"✗ 未找到 event_tree.json")
        event_tree = []
    
    # 加载每日事件数据
    daily_event_path = os.path.join(data_path, "daily_event.json")
    if os.path.exists(daily_event_path):
        with open(daily_event_path, 'r', encoding='utf-8') as f:
            daily_event = json.load(f)
        print(f"✓ 已加载 daily_event.json")
    else:
        print(f"✗ 未找到 daily_event.json")
        daily_event = []
    
    # 加载草稿事件数据
    draft_event_path = os.path.join(data_path, "daily_draft.json")
    if os.path.exists(draft_event_path):
        with open(draft_event_path, 'r', encoding='utf-8') as f:
            draft_event = json.load(f)
        print(f"✓ 已加载 daily_draft.json")
    else:
        print(f"✗ 未找到 daily_draft.json")
        draft_event = {}
    
    # 加载特殊事件数据
    special_event_path = os.path.join(data_path, "special_event.json")
    if os.path.exists(special_event_path):
        with open(special_event_path, 'r', encoding='utf-8') as f:
            special_event = json.load(f)
        print(f"✓ 已加载 special_event.json")
    else:
        print(f"✗ 未找到 special_event.json")
        special_event = {}
    
    # 检查手机数据目录
    phone_data_dir = os.path.join(data_path, "phone_data")
    if os.path.exists(phone_data_dir):
        print(f"✓ 找到 phone_data 目录")
    else:
        print(f"✗ 未找到 phone_data 目录")
        phone_data_dir = None
    
    return persona, event_tree, daily_event, draft_event, special_event, phone_data_dir


def test_base_class_data_loading():
    """测试基类的数据读取函数"""
    print("\n" + "=" * 80)
    print("测试：BaseQAGenerator 数据读取函数")
    print("=" * 80)
    
    try:
        # 使用真实数据路径
        real_data_path = r"/fenghaoran/fenghaoran"
        
        if not os.path.exists(real_data_path):
            print(f"✗ 数据路径不存在：{real_data_path}")
            return False
        
        # 创建基类实例（通过子类）
        from event.qa_generator.base_generator import BaseQAGenerator
        
        # 使用 QASingleGenerator 来测试基类方法
        gen = QASingleGenerator()
        
        # 测试 load_data_from_path
        print("\n1. 测试 load_data_from_path...")
        gen.load_data_from_path(real_data_path)
        
        # 验证数据是否加载成功
        assert gen.persona_data is not None, "persona_data 应该被加载"
        assert len(gen.persona_data) > 0, "persona_data 不应该为空"
        print(f"✓ persona_data 加载成功，包含 {len(gen.persona_data)} 个字段")
        
        assert gen.event_tree is not None, "event_tree 应该被加载"
        if isinstance(gen.event_tree, list):
            print(f"✓ event_tree 加载成功，包含 {len(gen.event_tree)} 个事件树")
        else:
            print(f"✓ event_tree 加载成功，类型：{type(gen.event_tree)}")
        
        assert gen.daily_event is not None, "daily_event 应该被加载"
        if isinstance(gen.daily_event, list):
            print(f"✓ daily_event 加载成功，包含 {len(gen.daily_event)} 条每日事件")
        else:
            print(f"⚠ daily_event 格式可能不正确，类型：{type(gen.daily_event)}")
        
        assert gen.draft_event is not None, "draft_event 应该被加载"
        if isinstance(gen.draft_event, dict):
            draft_months = [k for k in gen.draft_event.keys() if isinstance(k, str) and len(k) == 7]
            print(f"✓ draft_event 加载成功，包含 {len(draft_months)} 个月份的数据")
        else:
            print(f"⚠ draft_event 格式可能不正确，类型：{type(gen.draft_event)}")
        
        assert gen.special_event is not None, "special_event 应该被加载"
        if gen.special_event:
            unique_events_count = len(gen.special_event.get('unique_events', []))
            print(f"✓ special_event 加载成功，包含 {unique_events_count} 个独特事件")
        else:
            print(f"⚠ special_event 为空")
        
        # 测试 get_draft_event_by_month
        print("\n2. 测试 get_draft_event_by_month...")
        test_month = "2025-01"  # 假设数据中有这个月份
        draft_events = gen.get_draft_event_by_month(test_month)
        if draft_events:
            print(f"✓ get_draft_event_by_month('{test_month}') 成功，返回 {len(draft_events)} 条数据")
        else:
            print(f"⚠ get_draft_event_by_month('{test_month}') 返回空列表，可能是该月份没有数据")
            # 尝试获取第一个可用月份
            if isinstance(gen.draft_event, dict):
                available_months = [k for k in gen.draft_event.keys() if isinstance(k, str) and len(k) == 7]
                if available_months:
                    first_month = available_months[0]
                    draft_events = gen.get_draft_event_by_month(first_month)
                    print(f"✓ get_draft_event_by_month('{first_month}') 成功，返回 {len(draft_events)} 条数据")
        
        # 测试 _get_daily_event_data
        print("\n3. 测试 _get_daily_event_data...")
        if isinstance(gen.daily_event, list) and len(gen.daily_event) > 0:
            daily_events = gen._get_daily_event_data(count=5)
            print(f"✓ _get_daily_event_data(count=5) 成功，返回 {len(daily_events)} 条数据")
            
            # 测试 continuous 模式
            daily_events_continuous = gen._get_daily_event_data(count=5, continuous=True)
            print(f"✓ _get_daily_event_data(count=5, continuous=True) 成功，返回 {len(daily_events_continuous)} 条数据")
        else:
            print(f"⚠ daily_event 不是列表或为空，跳过此测试")
        
        # 测试 _get_persona_data
        print("\n4. 测试 _get_persona_data...")
        persona_data = gen._get_persona_data()
        assert persona_data is not None, "_get_persona_data 应该返回数据"
        print(f"✓ _get_persona_data 成功，返回 {len(persona_data)} 个字段的画像数据")
        
        # 测试 _get_event_tree_data
        print("\n5. 测试 _get_event_tree_data...")
        if isinstance(gen.event_tree, list) and len(gen.event_tree) > 0:
            event_tree_data = gen._get_event_tree_data(count=3)
            print(f"✓ _get_event_tree_data(count=3) 成功，返回 {len(event_tree_data)} 个事件树")
        else:
            print(f"⚠ event_tree 不是列表或为空，跳过此测试")
        
        # 测试手机数据加载（如果存在）
        print("\n6. 测试手机数据加载...")
        phone_data_path = os.path.join(real_data_path, "phone_data")
        if os.path.exists(phone_data_path):
            assert len(gen.phonedata) > 0, "phonedata 应该被加载"
            print(f"✓ 手机数据加载成功，包含 {len(gen.phonedata)} 种数据类型：{list(gen.phonedata.keys())}")
            
            # 测试 get_phone_operations_by_event_id
            if gen.phonedata:
                # 随便找一个 event_id 测试
                test_event_id = None
                for data_type, data_list in gen.phonedata.items():
                    if isinstance(data_list, list) and len(data_list) > 0:
                        first_item = data_list[0]
                        if isinstance(first_item, dict) and 'event_id' in first_item:
                            test_event_id = first_item['event_id']
                            break
                
                if test_event_id:
                    phone_ops = gen.get_phone_operations_by_event_id(test_event_id)
                    print(f"✓ get_phone_operations_by_event_id('{test_event_id}') 成功，返回 {len(phone_ops)} 个操作")
                else:
                    print(f"⚠ 没有找到包含 event_id 的手机数据，跳过此测试")
        else:
            print(f"⚠ phone_data 目录不存在，跳过手机数据测试")
        
        # 测试 sync_data_from
        print("\n7. 测试 sync_data_from...")
        gen2 = QASingleGenerator()
        gen2.sync_data_from(gen)
        
        assert gen2.persona_data == gen.persona_data, "sync_data_from 应该同步 persona_data"
        assert gen2.event_tree == gen.event_tree, "sync_data_from 应该同步 event_tree"
        assert gen2.daily_event == gen.daily_event, "sync_data_from 应该同步 daily_event"
        assert gen2.draft_event == gen.draft_event, "sync_data_from 应该同步 draft_event"
        assert gen2.special_event == gen.special_event, "sync_data_from 应该同步 special_event"
        print(f"✓ sync_data_from 成功，所有数据已同步到另一个生成器")
        
        # 测试 clear_phonedata
        print("\n8. 测试 clear_phonedata...")
        original_phonedata_count = len(gen.phonedata)
        if original_phonedata_count > 0:
            gen.clear_phonedata()
            assert len(gen.phonedata) == 0, "clear_phonedata 应该清空所有手机数据"
            print(f"✓ clear_phonedata 成功，清空了 {original_phonedata_count} 种数据类型")
        else:
            print(f"⚠ phonedata 为空，跳过此测试")
        
        print("\n✓ 所有基类数据读取函数测试通过！")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_base_class():
    """测试抽象基类"""
    print("=" * 80)
    print("测试 1: 抽象基类 BaseQAGenerator")
    print("=" * 80)
    
    try:
        # 检查是否是抽象类
        assert hasattr(BaseQAGenerator, 'QAGen'), "BaseQAGenerator 应该有 QAGen 抽象方法"
        print("✓ BaseQAGenerator 定义了 QAGen 抽象方法")
        
        # 尝试实例化抽象类（应该失败）
        try:
            base_gen = BaseQAGenerator()
            print("✗ 抽象类不应该被实例化")
            return False
        except TypeError:
            print("✓ BaseQAGenerator 是抽象类，不能被实例化")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败：{e}")
        return False


# def test_single_hop_generator():
#     """测试单跳问题生成器"""
#     print("\n" + "=" * 80)
#     print("测试 2: QASingleGenerator (单跳问题生成器)")
#     print("=" * 80)
#
#     try:
#         # 使用真实数据
#         real_data_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran"
#         persona, event_tree, daily_event, draft_event, special_event, phone_data_dir = load_real_data(real_data_path)
#
#         # 初始化
#         gen = QASingleGenerator(
#             persona_data=persona,
#             event_tree=event_tree,
#             daily_event=daily_event,
#             draft_event=draft_event,
#             special_event=special_event,
#             phone_data_dir=phone_data_dir
#         )
#         print("✓ 初始化成功")
#
#         # 检查是否继承自 BaseQAGenerator
#         assert isinstance(gen, BaseQAGenerator), "应该继承自 BaseQAGenerator"
#         print("✓ 继承自 BaseQAGenerator")
#
#         # 检查 QAGen 方法
#         assert hasattr(gen, 'QAGen'), "应该有 QAGen 方法"
#         print("✓ 有 QAGen 方法")
#
#         # 测试 QAGen 方法（使用默认年份和默认输出路径）
#         questions = gen.QAGen(year=2025, output_path='fenghaoran/')
#         assert isinstance(questions, list), "QAGen 应该返回列表"
#         print(f"✓ QAGen 返回了 {len(questions)} 个问题")
#
#         # 检查其他关键方法
#         methods = ['generate_yearly_single_hop_qa']
#         for method in methods:
#             assert hasattr(gen, method), f"缺少方法：{method}"
#         print(f"✓ 有其他关键方法：{', '.join(methods)}")
#
#         return True
#     except Exception as e:
#         print(f"✗ 测试失败：{e}")
#         import traceback
#         traceback.print_exc()
#         return False


def test_multi_hop_generator():
    """测试多跳问题生成器"""
    print("\n" + "=" * 80)
    print("测试 3: QAMultiHopGenerator (多跳问题生成器)")
    print("=" * 80)
    
    try:
        # 使用真实数据
        real_data_path = r"/fenghaoran/fenghaoran"
        persona, event_tree, daily_event, draft_event, special_event, phone_data_dir = load_real_data(real_data_path)
        
        # 初始化
        gen = QAMultiHopGenerator(
            persona_data=persona,
            event_tree=event_tree,
            daily_event=daily_event,
            draft_event=draft_event,
            special_event=special_event,
            phone_data_dir=phone_data_dir
        )
        print("✓ 初始化成功")
        
        # 检查是否继承自 BaseQAGenerator
        assert isinstance(gen, BaseQAGenerator), "应该继承自 BaseQAGenerator"
        print("✓ 继承自 BaseQAGenerator")
        
        # 检查 QAGen 方法
        assert hasattr(gen, 'QAGen'), "应该有 QAGen 方法"
        print("✓ 有 QAGen 方法")
        
        # 测试 QAGen 方法（默认年份 2025）
        questions = gen.QAGen(year="2025", num_questions_per_month=2, num_persona_questions=2)
        assert isinstance(questions, list), "QAGen 应该返回列表"
        print(f"✓ QAGen 返回了 {len(questions)} 个问题")
        
        # 检查其他关键方法（只检查年度生成方法）
        methods = [
            'generate_yearly_multi_hop_questions',
            'generate_unanswerable_questions'
        ]
        for method in methods:
            assert hasattr(gen, method), f"缺少方法：{method}"
        print(f"✓ 有其他关键方法：{', '.join(methods)}")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_pattern_recognition_generator():
    """测试模式识别问题生成器"""
    print("\n" + "=" * 80)
    print("测试 4: QAPatternRecognitionGenerator (模式识别问题生成器)")
    print("=" * 80)
    
    try:
        # 使用真实数据
        real_data_path = r"/fenghaoran/fenghaoran"
        persona, event_tree, daily_event, draft_event, special_event, phone_data_dir = load_real_data(real_data_path)
        
        # 初始化
        gen = QAPatternRecognitionGenerator(
            persona_data=persona,
            event_tree=event_tree,
            daily_event=daily_event,
            draft_event=draft_event,
            special_event=special_event,
            phone_data_dir=phone_data_dir
        )
        print("✓ 初始化成功")
        
        # 检查是否继承自 BaseQAGenerator
        assert isinstance(gen, BaseQAGenerator), "应该继承自 BaseQAGenerator"
        print("✓ 继承自 BaseQAGenerator")
        
        # 检查 QAGen 方法
        assert hasattr(gen, 'QAGen'), "应该有 QAGen 方法"
        print("✓ 有 QAGen 方法")
        
        # 测试 QAGen 方法（不指定年份，使用默认参数）
        questions = gen.QAGen(num_questions_per_month=2)
        assert isinstance(questions, list), "QAGen 应该返回列表"
        print(f"✓ QAGen 返回了 {len(questions)} 个问题")
        
        # 检查其他关键方法
        methods = [
            'generate_pattern_recognition_and_habit_analysis_questions',
            'generate_yearly_pattern_recognition_questions'
        ]
        for method in methods:
            assert hasattr(gen, method), f"缺少方法：{method}"
        print(f"✓ 有其他关键方法：{', '.join(methods)}")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_reasoning_generator():
    """测试推理问题生成器"""
    print("\n" + "=" * 80)
    print("测试 5: QAReasoningGenerator (推理问题生成器)")
    print("=" * 80)
    
    try:
        # 使用真实数据
        real_data_path = r"/fenghaoran/fenghaoran"
        persona, event_tree, daily_event, draft_event, special_event, phone_data_dir = load_real_data(real_data_path)
        
        # 初始化
        gen = QAReasoningGenerator(
            persona_data=persona,
            event_tree=event_tree,
            daily_event=daily_event,
            draft_event=draft_event,
            special_event=special_event,
            phone_data_dir=phone_data_dir
        )
        print("✓ 初始化成功")
        
        # 检查是否继承自 BaseQAGenerator
        assert isinstance(gen, BaseQAGenerator), "应该继承自 BaseQAGenerator"
        print("✓ 继承自 BaseQAGenerator")
        
        # 检查 QAGen 方法
        assert hasattr(gen, 'QAGen'), "应该有 QAGen 方法"
        print("✓ 有 QAGen 方法")
        
        # 测试 QAGen 方法（不提供参数）
        questions = gen.QAGen()
        assert isinstance(questions, list), "QAGen 应该返回列表"
        print(f"✓ QAGen 返回了 {len(questions)} 个问题（空参数）")
        
        # 测试 QAGen 方法（提供 themes）
        test_themes = [
            {
                "theme_summary": "项目开发主题",
                "event_ids": [1, 2, 3]
            }
        ]
        questions = gen.QAGen(themes=test_themes, num_questions_per_theme=1)
        assert isinstance(questions, list), "QAGen 应该返回列表"
        print(f"✓ QAGen 返回了 {len(questions)} 个问题（带 themes 参数）")
        
        # 检查其他关键方法
        methods = [
            'generate_reasoning_questions_by_themes',
            'generate_reasoning_questions_from_event_tree_id_groups'
        ]
        for method in methods:
            assert hasattr(gen, method), f"缺少方法：{method}"
        print(f"✓ 有其他关键方法：{', '.join(methods)}")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_sync():
    """测试生成器间的数据同步"""
    print("\n" + "=" * 80)
    print("测试 6: 生成器数据同步机制")
    print("=" * 80)
    
    try:
        # 使用真实数据
        real_data_path = r"/fenghaoran/fenghaoran"
        persona, event_tree, daily_event, draft_event, special_event, phone_data_dir = load_real_data(real_data_path)
        
        # 创建两个生成器
        gen1 = QASingleGenerator(
            persona_data=persona,
            event_tree=event_tree,
            daily_event=daily_event,
            draft_event=draft_event,
            special_event=special_event,
            phone_data_dir=phone_data_dir
        )
        gen2 = QAMultiHopGenerator(
            persona_data=persona,
            event_tree=event_tree,
            daily_event=daily_event,
            draft_event=draft_event,
            special_event=special_event,
            phone_data_dir=phone_data_dir
        )
        
        # 修改 gen1 的数据
        gen1.phonedata['test_type'] = [{'phone_id': '1', 'content': 'test'}]
        gen1._data_updated = True
        
        # 同步数据
        gen2.sync_data_from(gen1)
        
        # 验证同步成功
        assert 'test_type' in gen2.phonedata, "数据应该被同步"
        print("✓ 数据同步机制工作正常")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败：{e}")
        return False


def test_interface_uniformity():
    """测试接口统一性"""
    print("\n" + "=" * 80)
    print("测试 7: 接口统一性检查")
    print("=" * 80)
    
    try:
        # 使用真实数据
        real_data_path = r"/fenghaoran/fenghaoran"
        persona, event_tree, daily_event, draft_event, special_event, phone_data_dir = load_real_data(real_data_path)
        
        generators = {
            'single': QASingleGenerator(
                persona_data=persona,
                event_tree=event_tree,
                daily_event=daily_event,
                draft_event=draft_event,
                special_event=special_event,
                phone_data_dir=phone_data_dir
            ),
            'multi': QAMultiHopGenerator(
                persona_data=persona,
                event_tree=event_tree,
                daily_event=daily_event,
                draft_event=draft_event,
                special_event=special_event,
                phone_data_dir=phone_data_dir
            ),
            'pattern': QAPatternRecognitionGenerator(
                persona_data=persona,
                event_tree=event_tree,
                daily_event=daily_event,
                draft_event=draft_event,
                special_event=special_event,
                phone_data_dir=phone_data_dir
            ),
            'reasoning': QAReasoningGenerator(
                persona_data=persona,
                event_tree=event_tree,
                daily_event=daily_event,
                draft_event=draft_event,
                special_event=special_event,
                phone_data_dir=phone_data_dir
            )
        }
        
        # 检查所有生成器都有 QAGen 方法
        for name, gen in generators.items():
            assert hasattr(gen, 'QAGen'), f"{name} 缺少 QAGen 方法"
            assert callable(getattr(gen, 'QAGen')), f"{name} 的 QAGen 不是可调用对象"
        
        print("✓ 所有生成器都有 QAGen 方法")
        
        # 检查 QAGen 方法的返回值类型（根据各生成器的参数规范调用）
        for name, gen in generators.items():
            if name == 'single':
                # QASingleGenerator: year, output_path 参数
                result = gen.QAGen(year=2025, output_path=None)
            elif name == 'multi':
                # QAMultiHopGenerator: year, num_questions_per_month, num_persona_questions
                result = gen.QAGen(year=None, num_questions_per_month=1, num_persona_questions=1)
            elif name == 'pattern':
                # QAPatternRecognitionGenerator: year, num_questions_per_month
                result = gen.QAGen(year=None, num_questions_per_month=1)
            else:  # reasoning
                # QAReasoningGenerator: themes, event_id_groups 等
                result = gen.QAGen()
            assert isinstance(result, list), f"{name} 的 QAGen 应该返回列表"
        
        print("✓ 所有 QAGen 方法都返回 list 类型")
        print("✓ 接口统一性检查通过")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("开始测试所有 QA 生成器")
    print("=" * 80)
    
    results = []
    
    # 运行所有测试
    results.append(("基类数据读取函数测试", test_base_class_data_loading()))
    results.append(("抽象基类测试", test_base_class()))
    #results.append(("单跳问题生成器", test_single_hop_generator()))
    #results.append(("多跳问题生成器", test_multi_hop_generator()))
    #results.append(("模式识别问题生成器", test_pattern_recognition_generator()))
    # results.append(("推理问题生成器", test_reasoning_generator()))
    results.append(("数据同步测试", test_data_sync()))
    results.append(("接口统一性测试", test_interface_uniformity()))
    
    # 打印总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总计：{passed}/{total} 个测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！所有生成器功能正常！")
        return 0
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败，请检查问题")
        return 1


if __name__ == "__main__":
    sys.exit(main())
