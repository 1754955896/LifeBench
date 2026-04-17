"""
测试 QAGenerator 类的功能
"""

import json
import os
import sys

# 添加项目根目录到 Python 路径
project_root = r"D:\pyCharmProjects\pythonProject4"
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from event.QaGenerator import QAGenerator


def main(generator_names=None):
    """
    主函数：调用 QAGenerator 并打印输出
    
    Args:
        generator_names: 要测试的生成器名称列表，例如 ['single_hop', 'multi_hop']
                        如果为 None，则测试所有已注册的生成器
    """
    print("\n" + "="*80)
    print("开始运行 QAGenerator 测试")
    print("="*80 + "\n")
    
    # 使用真实测试数据路径（绝对路径）
    data_path = r"/fenghaoran/fenghaoran"
    
    # 验证数据路径是否存在
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"测试数据路径不存在：{data_path}")
    
    # 初始化 QAGenerator（不自动发现）
    qa_generator = QAGenerator(data_path=data_path, auto_discover=True)

    
    # 打印初始化的生成器信息
    print("\n" + "="*80)
    print("QAGenerator 初始化完成")
    print("="*80)
    registered_generators = qa_generator.get_registered_generators()
    print(f"已注册的生成器：{registered_generators}")
    print(f"生成器数量：{len(registered_generators)}")
    print(f"数据路径：{qa_generator.data_path}")
    print(f"手机数据目录：{qa_generator.phone_data_dir}")
    
    # 确定要测试的生成器
    if not generator_names:
        generator_names = ['qa_single_generator']
        print(f"\n未指定生成器名称，将测试所有已注册的生成器：{generator_names}")
    else:
        print(f"\n将测试以下生成器：{generator_names}")
    
    print("\n" + "="*80)
    print("开始生成问答对")
    print("="*80 + "\n")
    
    # 调用 generate_all_qa，只执行指定的生成器
    qa_generator.generate_all_qa(
        year=2025,
        generator_orders=generator_names
    )
    
    print("\n" + "="*80)
    print("QAGenerator 测试完成")
    print("="*80 + "\n")


if __name__ == '__main__':
    # ============================================
    # 在这里配置要测试的生成器名称列表
    # ============================================
    # 可用的生成器：'single_hop', 'multi_hop', 'pattern_recognition', 'reasoning'
    # 示例：generator_names = ['single_hop', 'multi_hop']
    # 设置为 None 则测试所有已注册的生成器
    generator_names = None  # 修改这里来控制要调用的生成器
    # ============================================
    
    main(generator_names)
