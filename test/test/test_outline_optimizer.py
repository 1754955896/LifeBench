# -*- coding: utf-8 -*-
"""
OutlineOptimizer 测试脚本
"""

import os
from event.draft.outline_optimizer import OutlineOptimizer

# 数据路径
BASE_DIR = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran"


def main():
    """执行完整的大纲优化流程"""
    print("=" * 80)
    print("OutlineOptimizer 完整流程测试")
    print("=" * 80)
    print(f"数据目录：{BASE_DIR}")
    print("=" * 80)
    
    # 创建 OutlineOptimizer 实例
    optimizer = OutlineOptimizer(filepath=BASE_DIR, year=2025, isprint=True)
    
    # 检查数据加载
    print("\n[数据加载检查]")
    print(f"  画像数据：{'✓ 已加载' if optimizer.persona else '✗ 加载失败'}")
    print(f"  草稿数据：{'✓ 已加载' if optimizer.daily_draft else '✗ 加载失败'}")
    print(f"  月份数据：{'✓ 已初始化' if optimizer.monthly_data else '✗ 初始化失败'}")
    
    # 执行完整流程
    print("\n" + "=" * 80)
    print("开始执行完整优化流程")
    print("=" * 80)
    
    try:
        results = optimizer.run_full_optimization()
        
        print("\n" + "=" * 80)
        print("流程执行完成！")
        print("=" * 80)
        
        # 输出结果摘要
        print("\n[结果摘要]")
        if results.get("summaries"):
            summaries_count = len(results["summaries"])
            print(f"  ✓ 月度总结报告：{summaries_count} 个月份")
        
        if results.get("consistency"):
            issues_count = len(results["consistency"].get("analysis", {}).get("issues", []))
            print(f"  ✓ 全年一致性问题：{issues_count} 个")
        
        if results.get("reasonableness"):
            total_dates = sum(
                len(analysis.get("dates_to_modify", []))
                for analysis in results["reasonableness"].values()
                if analysis.get("status") == "success"
            )
            print(f"  ✓ 需要修改的日期：{total_dates} 个")
        
        print("\n" + "=" * 80)
        return results
        
    except Exception as e:
        print(f"\n[错误] 流程执行失败：{e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    main()
