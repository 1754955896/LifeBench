#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 Interface_1.py 接口
"""

import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_interface_1_main():
    """测试直接调用 Interface_1 的 main() 函数"""
    print("\n测试直接调用 Interface_1 的 main() 函数...")
    # 导入 Interface_1 模块
    from event.edit.Interface_1 import main as interface_main
    # 注意：这个测试会启动交互式命令行，需要手动输入 'exit' 退出
    print("注意：此测试会启动交互式命令行，请输入 'exit' 退出测试")
    print("=" * 60)
    try:
        # 调用 Interface_1 的 main() 函数
        interface_main()
        print("✓ 测试通过")
    except Exception as e:
        print(f"✗ 测试失败: {e}")


if __name__ == "__main__":
    test_interface_1_main()