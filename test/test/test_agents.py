# -*- coding: utf-8 -*-
"""
Agent 测试入口
数据来源：D:/pyCharmProjects/pythonProject4/fenghaoran/fenghaoran
"""

import os
import json
from event.data_edit import DataEditorAgent
from event.edit.planning_agent import PlanningAgent
from event.edit.execution_agent import ExecutionAgent
from event.edit.reflection_agent import ReflectionAgent
from event.edit.data_query_tool import DataQueryTool

# 数据根目录
BASE_DIR = r"D:\pyCharmProjects\pythonProject4\yuxiaowen"


# ========== 工具函数 ==========

def sep(title: str = "", width: int = 60):
    """打印分隔线"""
    if title:
        pad = (width - len(title) - 2) // 2
        print("\n" + "=" * pad + f" {title} " + "=" * pad)
    else:
        print("\n" + "=" * width)


def print_plan(plan):
    """打印执行计划摘要"""
    print(f"  计划摘要    : {plan.summary}")
    print(f"  预计步骤    : {plan.estimated_steps}")
    print(f"  需要确认    : {plan.requires_confirmation}")
    print(f"  操作数量    : {len(plan.operations)}")
    for i, op in enumerate(plan.operations, 1):
        print(f"    [{i}] {op.operation_type.value:8s} | {op.data_type.value:15s} | {op.description}")


def print_results(results):
    """打印执行结果摘要"""
    for i, r in enumerate(results, 1):
        status = "✓" if r.success else "✗"
        print(f"  [{status}] [{i}] {r.operation_type:8s} | 影响 {r.affected_count} 条 | {r.message}")


def print_reflection(ref):
    """打印反思结果摘要"""
    print(f"  状态        : {ref.status.value}")
    print(f"  完成率      : {ref.completion_rate:.0%}")
    print(f"  分析        : {ref.analysis}")
    if ref.issues:
        print(f"  问题        : {'; '.join(ref.issues)}")
    if ref.suggestions:
        print(f"  建议        : {'; '.join(ref.suggestions)}")
    print(f"  下一步      : {ref.next_action}")


# ========== 查询工具测试 ==========

def test_query_tool():
    """测试 DataQueryTool 各种查询方式"""
    sep("DataQueryTool 测试")

    qt = DataQueryTool(base_dir=BASE_DIR)

    # ── 1. by_id：查询 daily_event ──────────────────────────
    sep("1. query_by_id — daily_event", width=55)
    result = qt.query_by_id("daily_event", "1")
    if result:
        print(f"  event_id : {result.get('event_id')}")
        print(f"  name     : {result.get('name')}")
        print(f"  date     : {result.get('date')}")
        print(f"  type     : {result.get('type')}")
    else:
        print("  未找到 event_id=1")

    # ── 2. by_id：查询 phone_data/call（phone_id=0）──────────
    sep("2. query_by_id — phone_data/call", width=55)
    result2 = qt.query_by_id("phone_data/call", 0)      # phone_id 是 int
    if result2:
        print(f"  phone_id    : {result2.get('phone_id')}")
        print(f"  contactName : {result2.get('contactName')}")
        print(f"  datetime    : {result2.get('datetime')}")
        print(f"  direction   : {'拨出' if result2.get('direction') == 1 else '接入'}")
    else:
        print("  未找到 phone_id=0")

    # ── 3. by_date：查询 daily_event 某天所有事件 ────────────
    sep("3. query_by_date — daily_event 2025-01-02", width=55)
    date_events = qt.query_by_date("daily_event", "2025-01-02")
    print(f"  2025-01-02 共找到 {len(date_events)} 个事件")
    for e in date_events[:4]:
        print(f"    [{e.get('event_id'):>4s}] {e.get('name')}")
    if len(date_events) > 4:
        print(f"    ... 共 {len(date_events)} 条")

    # ── 4. by_date：查询 phone_data/call 某天通话 ────────────
    sep("4. query_by_date — phone_data/call 2025-01-02", width=55)
    calls = qt.query_by_date("phone_data/call", "2025-01-02", date_field="datetime")
    print(f"  2025-01-02 通话记录共 {len(calls)} 条")
    for c in calls:
        direct = "拨出" if c.get("direction") == 1 else "接入"
        print(f"    [{c.get('phone_id')}] {c.get('datetime')} {direct} {c.get('contactName')} {c.get('call_result')}")

    # ── 5. by_condition：按 type 过滤 daily_event ────────────
    sep("5. query_by_condition — daily_event type=Health", width=55)
    health_events = qt.query_by_condition("daily_event", {"type": "Health"})
    print(f"  type=Health 共 {len(health_events)} 个事件，前3条：")
    for e in health_events[:3]:
        dates = e.get('date', ['?'])
        print(f"    [{e.get('event_id'):>4s}] {dates[0][:10] if dates else '?'} | {e.get('name')}")

    # ── 6. query_related_events：查询同日关联事件 ─────────────
    sep("6. query_related_events — event_id=1 (same_date)", width=55)
    related = qt.query_related_events("1", "same_date")
    print(f"  与 event_id=1 同日的其他事件共 {len(related)} 条，前5条：")
    for e in related[:5]:
        print(f"    [{e.get('event_id'):>4s}] {e.get('name')}")

    # ── 7. query_by_date_range ─────────────────────────────
    sep("7. query_by_date_range — daily_event 2025-01-02 ~ 2025-01-03", width=55)
    range_events = qt.query_by_date_range("daily_event", "2025-01-02", "2025-01-03")
    print(f"  2025-01-02 ~ 2025-01-03 共 {len(range_events)} 个事件")

    # ── 8. query_by_date_range_draft ───────────────────────
    sep("8. query_by_date_range_draft — daily_draft 2025-01", width=55)
    draft_data = qt.query_by_date_range_draft("2025-01-01", "2025-01-31")
    print(f"  2025-01 月草稿数据共 {len(draft_data)} 条")
    for d in draft_data[:3]:
        draft_id = d.get('draft_id', '?')
        content = d.get('content', d.get('description', 'N/A'))[:50]
        print(f"    [{draft_id}] {content}...")
    if len(draft_data) > 3:
        print(f"    ... 共 {len(draft_data)} 条")

    # ── 9. get_summary ─────────────────────────────────────
    sep("9. get_summary", width=55)
    for dtype in ["daily_event", "daily_draft", "phone_data/call", "phone_data/sms"]:
        summary = qt.get_summary(dtype)
        print(f"  {dtype:25s}: {summary}")

    print()


# ========== 单 Agent 测试 ==========

def test_planning_agent():
    """测试 PlanningAgent 独立运行（开启调试模式）"""
    sep("PlanningAgent 测试")

    agent = PlanningAgent(base_dir=BASE_DIR)
    agent.debug_mode = True  # 打开调试日志

    cases = [
        "在2025年1月2日的daily_event修改晨跑地点为红星公园。",
    ]

    for cmd in cases:
        sep(f"指令：{cmd}", width=55)
        plan = agent.plan(cmd)
        print_plan(plan)


# ========== Planning + Execution 联动测试 ==========

def test_plan_exec_workflow():
    """测试 PlanningAgent + ExecutionAgent 完整工作流（包含保存）"""
    sep("Planning + Execution 联动测试")

    # 创建 Agent 实例
    planning_agent = PlanningAgent(base_dir=BASE_DIR)
    execution_agent = ExecutionAgent(base_dir=BASE_DIR)
    
    # 打开调试模式
    planning_agent.debug_mode = True
    
    # 加载数据
    print("\n[WORKFLOW] 正在加载数据...")
    execution_agent._load_daily_events()
    execution_agent._load_daily_drafts()
    execution_agent._load_phone_data()
    print(f"[WORKFLOW] 数据加载完成")
    
    # 测试用例
    cases = [
        {
            "command": "帮我删除手机数据call类型中phone_id为2的数据",
            "description": "单个手机数据删除"
        },
        # {
        #     "command": "添加一个日常事件，名称为'团队会议'，日期为 2025-01-02，描述为'讨论项目进度'",
        #     "description": "添加新事件"
        # }
    ]
    
    for i, case in enumerate(cases, 1):
        sep(f"测试用例 {i}: {case['description']}", width=60)
        command = case["command"]
        
        print(f"\n[WORKFLOW] 指令：{command}")
        print(f"[WORKFLOW] {'='*60}\n")
        
        # Step 1: Planning - 生成执行计划
        print("[Step 1] Planning Agent 正在解析指令...")
        plan = planning_agent.plan(command)
        
        print(f"\n[Step 1] ✓ 规划完成")
        print_plan(plan)
        
        # Step 2: Execution - 执行操作
        print(f"\n[Step 2] Execution Agent 正在执行操作...")
        results = execution_agent.execute_batch(plan.operations)
        
        # Step 3: 打印执行结果
        print(f"\n[Step 2] ✓ 执行完成")
        print_results(results)
        
        # Step 4: 检查是否需要保存
        success_count = sum(1 for r in results if r.success)
        total_count = len(results)
        
        print(f"\n[WORKFLOW] 执行统计：{success_count}/{total_count} 个操作成功")
        
        # 显示执行后的数据状态
        cache = execution_agent._cache
        if 'daily_event' in cache:
            print(f"[WORKFLOW] 当前 daily_event 缓存：{len(cache['daily_event'])} 条事件")
        
        # Step 5: 保存所有修改到文件
        if success_count > 0:
            print(f"\n[Step 3] 正在保存所有修改到文件...")
            save_results = execution_agent.save_all()
            for file_name, saved in save_results.items():
                print(f"  [{file_name}] {'✓ 已保存' if saved else '✗ 保存失败'}")
            print(f"\n[WORKFLOW] {'='*60}")
            print(f"[WORKFLOW] ✓ 所有修改已保存到文件")
            print(f"[WORKFLOW] {'='*60}\n")
        else:
            print(f"\n[WORKFLOW] {'='*60}")
            print(f"[WORKFLOW] 注意：没有成功的操作，未进行保存")
            print(f"[WORKFLOW] {'='*60}\n")


def test_reflection_agent():
    """测试 ReflectionAgent 独立运行"""
    sep("ReflectionAgent 测试")

    # 导入必要的类
    from event.edit.planning_agent import ExecutionPlan, OperationPlan, OperationType, DataType, IndexMethod
    from event.edit.execution_agent import ExecutionResult
    
    # 创建 Agent 实例
    reflection_agent = ReflectionAgent(base_dir=BASE_DIR)
    
    # 测试用例 1: 成功操作 - 修改晨跑地点
    test_case_1 = {
        "original_command": "在2025年1月2日的daily_event修改晨跑地点为红星公园。",
        "execution_plan": {
            "summary": "修改2025-01-02的晨跑事件地点为红星公园",
            "estimated_steps": 1,
            "requires_confirmation": False,
            "operations": [
                {
                    "operation_type": "UPDATE",
                    "data_type": "daily_event",
                    "description": "修改2025-01-02的晨跑事件地点",
                    "params": {
                        "date": "2025-01-02",
                        "updates": {"location": "红星公园"}
                    }
                }
            ]
        },
        "execution_results": [
            {
                "success": True,
                "operation_type": "UPDATE",
                "data_type": "daily_event",
                "message": "修改成功",
                "data_after": {"location": "红星公园"},
                "affected_count": 1
            }
        ]
    }
    
    # 测试用例 2: 失败操作 - 删除事件但data after仍保留该事件
    test_case_2 = {
        "original_command": "删除2025年1月2日的晨跑事件",
        "execution_plan": {
            "summary": "删除2025-01-02的晨跑事件",
            "estimated_steps": 1,
            "requires_confirmation": True,
            "operations": [
                {
                    "operation_type": "DELETE",
                    "data_type": "daily_event",
                    "description": "删除2025-01-02的晨跑事件",
                    "params": {
                        "date": "2025-01-02",
                        "condition": {"name": "晨跑"}
                    }
                }
            ]
        },
        "execution_results": [
            {
                "success": True,
                "operation_type": "DELETE",
                "data_type": "daily_event",
                "message": "修改成功",
                "data_after": [{"name": "晨跑", "date": "2025-01-02", "location": "公园"}],
                "affected_count": 1
            }
        ]
    }
    
    # 测试用例 3: 失败操作 - 重写添加情节但前后矛盾
    test_case_3 = {
        "original_command": "重写2025年1月2日，添加下午3点的会议情节，同时保持上午10点的晨跑",
        "execution_plan": {
            "summary": "重写2025-01-02的事件，添加会议情节",
            "estimated_steps": 1,
            "requires_confirmation": False,
            "operations": [
                {
                    "operation_type": "whole_day_rewrite",
                    "data_type": "daily_event",
                    "description": "重写2025-01-02的事件",
                    "params": {
                        "date": "2025-01-02",
                        "guidance": "添加下午3点的会议情节，同时保持上午10点的晨跑"
                    }
                }
            ]
        },
        "execution_results": [
            {
                "success": True,
                "operation_type": "whole_day_rewrite",
                "data_type": "daily_event",
                "message": "修改成功",
                "data_after": [
                    {"name": "晨跑", "date": "2025-01-02", "start_time": "10:00"},
                    {"name": "会议", "date": "2025-01-02", "start_time": "10:00"}  # 时间冲突
                ],
                "affected_count": 2
            }
        ]
    }
    
    # 测试用例 4: 失败操作 - 修改事件但修改了不在目标日期的事件
    test_case_4 = {
        "original_command": "修改2025年1月2日的晨跑时间为9点",
        "execution_plan": {
            "summary": "修改2025-01-02的晨跑时间为9点",
            "estimated_steps": 1,
            "requires_confirmation": False,
            "operations": [
                {
                    "operation_type": "UPDATE",
                    "data_type": "daily_event",
                    "description": "修改2025-01-02的晨跑时间",
                    "params": {
                        "date": "2025-01-02",
                        "updates": {"start_time": "09:00"}
                    }
                }
            ]
        },
        "execution_results": [
            {
                "success": True,
                "operation_type": "UPDATE",
                "data_type": "daily_event",
                "message": "修改成功",
                "data_after": [
                    {"name": "晨跑", "date": "2025-01-01", "start_time": "09:00"},  # 错误的日期
                    {"name": "晨跑", "date": "2025-01-02", "start_time": "10:00"}  # 未修改
                ],
                "affected_count": 1
            }
        ]
    }
    
    # 运行测试用例
    test_cases = [test_case_1, test_case_2, test_case_3, test_case_4]
    
    for i, case in enumerate(test_cases, 1):
        sep(f"测试用例 {i}", width=55)
        
        print(f"\n[Reflection] 原始指令：{case['original_command']}")
        print(f"[Reflection] 执行计划类型：{type(case['execution_plan']).__name__}")
        print(f"[Reflection] 执行结果类型：{type(case['execution_results'][0]).__name__}")
        
        # 执行反思
        reflection_result = reflection_agent.reflect(
            original_command=case['original_command'],
            execution_plan=case['execution_plan'],
            execution_results=case['execution_results']
        )
        
        # 打印反思结果
        print(f"\n[Reflection] ✓ 反思完成")
        print_reflection(reflection_result)


def test_plan_exec_reflect_workflow():
    """测试完整的规划-执行-反思循环流程"""
    sep("完整规划-执行-反思循环测试")

    # 创建 Agent 实例
    planning_agent = PlanningAgent(base_dir=BASE_DIR)
    execution_agent = ExecutionAgent(base_dir=BASE_DIR)
    reflection_agent = ReflectionAgent(base_dir=BASE_DIR)
    
    # 打开调试模式
    planning_agent.debug_mode = True
    
    # 加载数据
    print("\n[WORKFLOW] 正在加载数据...")
    execution_agent._load_daily_events()
    execution_agent._load_daily_drafts()
    execution_agent._load_phone_data()
    print(f"[WORKFLOW] 数据加载完成")
    
    # 测试用例
    cases = [
        # {
        #     "command": "在2025年1月2日的daily_event增加突发意外摔伤被送往医院住院3天。",
        #     "description": "修改晨跑地点（成功操作）"
        # },
        {
            "command": "修改event_id为12的每日事件",
            "description": "删除手机通话数据（成功操作）"
        }
    ]
    
    for i, case in enumerate(cases, 1):
        sep(f"测试用例 {i}: {case['description']}", width=60)
        command = case["command"]
        
        print(f"\n[WORKFLOW] 指令：{command}")
        print(f"[WORKFLOW] {'='*60}\n")
        
        # Step 1: Planning - 生成执行计划
        print("[Step 1] Planning Agent 正在解析指令...")
        plan = planning_agent.plan(command)
        
        print(f"\n[Step 1] ✓ 规划完成")
        print_plan(plan)
        
        # Step 2: Execution - 执行操作
        print(f"\n[Step 2] Execution Agent 正在执行操作...")
        results = execution_agent.execute_batch(plan.operations)
        
        # Step 3: 打印执行结果
        print(f"\n[Step 2] ✓ 执行完成")
        print_results(results)
        
        # Step 4: Reflection - 反思评估
        print(f"\n[Step 3] Reflection Agent 正在评估执行效果...")
        # 执行反思
        reflection_result = reflection_agent.reflect(
            original_command=command,
            execution_plan=plan.to_dict(),
            execution_results=[r.to_dict() for r in results]
        )
        
        # 打印反思结果
        print(f"\n[Step 3] ✓ 反思完成")
        print_reflection(reflection_result)
        
        # Step 5: 检查是否需要保存
        success_count = sum(1 for r in results if r.success)
        total_count = len(results)
        
        print(f"\n[WORKFLOW] 执行统计：{success_count}/{total_count} 个操作成功")
        
        # 显示执行后的数据状态
        cache = execution_agent._cache
        if 'daily_event' in cache:
            print(f"[WORKFLOW] 当前 daily_event 缓存：{len(cache['daily_event'])} 条事件")
        
        # Step 6: 保存所有修改到文件
        if success_count > 0:
            print(f"\n[Step 4] 正在保存所有修改到文件...")
            save_results = execution_agent.save_all()
            for file_name, saved in save_results.items():
                print(f"  [{file_name}] {'✓ 已保存' if saved else '✗ 保存失败'}")
            print(f"\n[WORKFLOW] {'='*60}")
            print(f"[WORKFLOW] ✓ 所有修改已保存到文件")
            print(f"[WORKFLOW] {'='*60}\n")
        else:
            print(f"\n[WORKFLOW] {'='*60}")
            print(f"[WORKFLOW] 注意：没有成功的操作，未进行保存")
            print(f"[WORKFLOW] {'='*60}\n")

# ========== 数据预览 ==========

def preview_data():
    """预览 fenghaoran 数据，快速了解数据结构"""
    sep("数据预览")

    def peek_json(filepath, label, n=2):
        if not os.path.exists(filepath):
            print(f"  [{label}] 文件不存在：{filepath}")
            return
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            print(f"  [{label}] 共 {len(data)} 条，前 {n} 条：")
            for item in data[:n]:
                print(f"    {json.dumps(item, ensure_ascii=False)[:120]}")
        elif isinstance(data, dict):
            keys = list(data.keys())[:n]
            print(f"  [{label}] dict，共 {len(data)} 个key，前几个：{keys}")

    peek_json(os.path.join(BASE_DIR, "daily_event.json"), "daily_event")
    peek_json(os.path.join(BASE_DIR, "daily_draft.json"), "daily_draft")

    phone_dir = os.path.join(BASE_DIR, "phone_data")
    if os.path.isdir(phone_dir):
        for fname in sorted(os.listdir(phone_dir)):
            if fname.endswith(".json"):
                peek_json(os.path.join(phone_dir, fname), f"phone/{fname.replace('.json','')}", n=1)


# ========== 入口 ==========

if __name__ == "__main__":
    import sys

    # 可通过命令行参数选择运行哪个测试，默认运行全部
    # 例：python test_agents.py preview
    #     python test_agents.py plan
    #     python test_agents.py exec
    #     python test_agents.py reflect
    #     python test_agents.py cycle
    #     python test_agents.py workflow
    #     python test_agents.py all（默认）

    mode = sys.argv[1] if len(sys.argv) > 1 else "cycle"

    if mode in ("preview", "all"):
        preview_data()

    if mode in ("query", "all"):
        test_query_tool()

    if mode in ("plan", "all"):
        test_planning_agent()

    if mode in ("exec", "workflow", "all"):
        test_plan_exec_workflow()

    if mode in ("reflect", "all"):
        test_reflection_agent()

    if mode in ("cycle", "all"):
        test_plan_exec_reflect_workflow()