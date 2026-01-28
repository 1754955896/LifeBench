#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试parallel_process_perception_only函数的增量式写入功能
"""

import os
import shutil
import subprocess
import json
import time

def test_perception_incremental():
    """测试感知数据的增量式写入功能"""
    # 定义测试参数
    config_dir = "D:\pyCharmProjects\pythonProject4\config"
    phone_gen_path = "D:\pyCharmProjects\pythonProject4\phone_gen.py"
    output_dir = "D:\pyCharmProjects\pythonProject4\test_output"
    
    # 清理测试目录
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
        print("清理了旧的测试目录")
    
    # 创建输出目录
    os.makedirs(output_dir)
    
    # 复制配置文件
    for config_file in ["user_info.json", "location_config.json", "perception_config.json"]:
        src_path = os.path.join(config_dir, config_file)
        dst_path = os.path.join(output_dir, config_file)
        if os.path.exists(src_path):
            shutil.copy2(src_path, dst_path)
            print(f"复制配置文件: {config_file}")
    
    # 第一次运行：生成2025-01-01的数据
    print("\n=== 第一次运行：生成2025-01-01的数据 ===")
    cmd1 = [
        "python", phone_gen_path,
        "--start-time", "2025-01-01",
        "--end-time", "2025-01-01",
        "--output-path", output_dir,
        "--perception-only"
    ]
    
    result1 = subprocess.run(cmd1, capture_output=True, text=True, cwd="D:\pyCharmProjects\pythonProject4")
    print(f"命令输出: {result1.stdout}")
    if result1.stderr:
        print(f"错误信息: {result1.stderr}")
    
    # 检查生成的文件
    perception_file = os.path.join(output_dir, "phone_data", "event_perception.json")
    if os.path.exists(perception_file):
        with open(perception_file, "r", encoding="utf-8") as f:
            data1 = json.load(f)
        print(f"第一次生成的数据条目数: {len(data1)}")
    else:
        print("第一次运行未生成感知数据文件")
        return False
    
    # 等待1秒
    time.sleep(1)
    
    # 第二次运行：生成2025-01-02的数据
    print("\n=== 第二次运行：生成2025-01-02的数据 ===")
    cmd2 = [
        "python", phone_gen_path,
        "--start-time", "2025-01-02",
        "--end-time", "2025-01-02",
        "--output-path", output_dir,
        "--perception-only"
    ]
    
    result2 = subprocess.run(cmd2, capture_output=True, text=True, cwd="D:\pyCharmProjects\pythonProject4")
    print(f"命令输出: {result2.stdout}")
    if result2.stderr:
        print(f"错误信息: {result2.stderr}")
    
    # 检查合并后的数据文件
    if os.path.exists(perception_file):
        with open(perception_file, "r", encoding="utf-8") as f:
            data2 = json.load(f)
        print(f"第二次生成后的数据条目数: {len(data2)}")
    else:
        print("第二次运行未生成感知数据文件")
        return False
    
    # 验证增量式写入是否成功
    if len(data2) > len(data1):
        print(f"\n✅ 增量式写入成功！数据条目数从 {len(data1)} 增加到 {len(data2)}")
        return True
    else:
        print(f"\n❌ 增量式写入失败！数据条目数没有增加")
        return False

if __name__ == "__main__":
    test_perception_incremental()