# -*- coding: utf-8 -*-
"""
MonthlyRefiner 完整流程测试脚本
调用 run_full_pipeline 主函数执行完整的月度优化流程
"""

import os
from event.draft.monthly_refine import MonthlyRefiner

# 数据根目录 - 使用 fenghaoran 数据
BASE_DIR = r"D:\pyCharmProjects\pythonProject4\test"


def test_get_month_holidays():
    """测试 get_month_holidays 方法"""
    print("=" * 80)
    print("测试 get_month_holidays 方法")
    print("=" * 80)
    
    # 创建 MonthlyRefiner 实例
    refiner = MonthlyRefiner(filepath=BASE_DIR, year=2025, isprint=True)
    
    print(f"\n[节假日数据初始化检查]")
    print(f"  节假日数据：{'✓ 已初始化' if refiner.holidays else '✗ 初始化失败'}")
    
    if refiner.holidays:
        total_holidays = sum(len(v) for v in refiner.holidays.values())
        print(f"  节假日总数：{total_holidays}")
        
        # 测试几个月份的节假日
        test_months = ["01", "02", "05", "10"]  # 元旦、春节、劳动节、国庆节
        
        print(f"\n[测试月份节假日查询]")
        for month in test_months:
            holidays = refiner.get_month_holidays(month)
            print(f"\n  {month}月节假日（共 {len(holidays)} 个）：")
            if holidays:
                for holiday in holidays:
                    print(f"    - {holiday['name']}: {holiday['date']} ({holiday['type']})")
            else:
                print(f"    （无节假日）")
        
        # 测试边界情况
        print(f"\n[边界情况测试]")
        invalid_month = "13"
        holidays = refiner.get_month_holidays(invalid_month)
        print(f"  无效月份 {invalid_month}：返回 {len(holidays)} 个节假日（应为 0）")
        
        empty_month = "04"  # 通常没有法定节假日
        holidays = refiner.get_month_holidays(empty_month)
        print(f"  无节假日月份 {empty_month}：返回 {len(holidays)} 个节假日")
    
    print("\n" + "=" * 80)


def main():
    """执行完整的月度优化流程"""
    print("=" * 80)
    print("MonthlyRefiner 完整流程测试")
    print("=" * 80)
    print(f"数据目录：{BASE_DIR}")
    print("=" * 80)
    
    # 创建 MonthlyRefiner 实例
    refiner = MonthlyRefiner(filepath=BASE_DIR, year=2025, isprint=True)
    
    # 检查数据加载
    print("\n[数据加载检查]")
    print(f"  画像数据：{'✓ 已加载' if refiner.persona else '✗ 加载失败'}")
    print(f"  时间线数据：{'✓ 已加载' if refiner.timeline_data else '✗ 加载失败'}")
    print(f"  事件图谱：{'✓ 已加载' if refiner.event_graph else '✗ 加载失败'}")
    print(f"  月份映射：{'✓ 已初始化' if refiner.monthly_events_map else '✗ 初始化失败'}")
    
    # 执行完整流程
    print("\n" + "=" * 80)
    print("开始执行完整流程")
    print("=" * 80)
    
    try:
        results = refiner.run_full_pipeline(skip_existing=True)
        
        print("\n" + "=" * 80)
        print("流程执行完成！")
        print("=" * 80)
        
        # 输出结果摘要
        print("\n[结果摘要]")
        if results.get("summaries"):
            summaries_count = len(results["summaries"])
            print(f"  ✓ 月度总结报告：{summaries_count} 个月份")
        
        if results.get("trends"):
            trends_count = len([k for k in results["trends"].keys() if k not in ['status', 'message']])
            print(f"  ✓ 年度趋势分析：{trends_count} 个月份")
        
        if results.get("optimized"):
            optimized_count = len(results["optimized"])
            success_count = sum(1 for r in results["optimized"].values() if r.get('status') == 'success')
            print(f"  ✓ 月度优化结果：{success_count}/{optimized_count} 个月份成功")
        
        print("\n" + "=" * 80)
        return results
        
    except Exception as e:
        print(f"\n[错误] 流程执行失败：{e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import sys
    
    # 可通过命令行参数选择运行哪个测试
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    
    if mode == "holidays":
        test_get_month_holidays()
    elif mode == "full":
        main()
    else:
        print(f"未知模式：{mode}")
        print("可用模式:")
        print("  holidays - 测试节假日查询功能")
        print("  full     - 执行完整流程（默认）")
