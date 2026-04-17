#!/usr/bin/env python3
# 测试 llm_call.py 中的函数

import sys
import os
import json

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.llm_call import llm_call, llm_call_reason, llm_call_j, llm_call_reason_j, llm_call_skip

def test_llm_call():
    """测试 llm_call 函数"""
    print("\n=== 测试 llm_call 函数 ===")
    try:
        prompt = "请简单介绍一下自己"
        response = llm_call(prompt)
        print(f"提示词: {prompt}")
        print(f"响应: {response[:100]}...")
        print("测试成功!")
        return True
    except Exception as e:
        print(f"测试失败: {str(e)}")
        return False

def test_llm_call_reason():
    """测试 llm_call_reason 函数"""
    print("\n=== 测试 llm_call_reason 函数 ===")
    try:
        prompt = "123 + 456 = ? 请逐步计算"
        response = llm_call_reason(prompt)
        print(f"提示词: {prompt}")
        print(f"响应: {response[:100]}...")
        print("测试成功!")
        return True
    except Exception as e:
        print(f"测试失败: {str(e)}")
        return False

def test_llm_call_j():
    """测试 llm_call_j 函数"""
    print("\n=== 测试 llm_call_j 函数 ===")
    try:
        prompt = "请返回一个包含姓名、年龄、职业的JSON对象，姓名为'测试'，年龄为25，职业为'工程师'"
        response = llm_call_j(prompt)
        print(f"提示词: {prompt}")
        print(f"响应: {response}")
        # 尝试解析 JSON
        json_data = json.loads(response)
        print("JSON 解析成功!")
        print("测试成功!")
        return True
    except Exception as e:
        print(f"测试失败: {str(e)}")
        return False

def test_llm_call_reason_j():
    """测试 llm_call_reason_j 函数"""
    print("\n=== 测试 llm_call_reason_j 函数 ===")
    try:
        prompt = "请返回一个JSON对象，包含计算结果，123 + 456 = ?"
        response = llm_call_reason_j(prompt)
        print(f"提示词: {prompt}")
        print(f"响应: {response}")
        # 尝试解析 JSON
        json_data = json.loads(response)
        print("JSON 解析成功!")
        print("测试成功!")
        return True
    except Exception as e:
        print(f"测试失败: {str(e)}")
        return False

def test_llm_call_skip():
    """测试 llm_call_skip 函数"""
    print("\n=== 测试 llm_call_skip 函数 ===")
    try:
        prompt = "请简单介绍一下人工智能"
        response = llm_call_skip(prompt)
        print(f"提示词: {prompt}")
        print(f"响应: {response[:100]}...")
        print("测试成功!")
        return True
    except Exception as e:
        print(f"测试失败: {str(e)}")
        return False

def main():
    """主测试函数"""
    print("开始测试 llm_call.py 中的函数...")
    
    tests = [
        test_llm_call,
        # test_llm_call_reason,
        # test_llm_call_j,
        # test_llm_call_reason_j,
        # test_llm_call_skip
    ]
    
    success_count = 0
    total_count = len(tests)
    
    for test in tests:
        if test():
            success_count += 1
    
    print(f"\n测试完成: {success_count}/{total_count} 个测试通过")
    
    if success_count == total_count:
        print("所有测试通过!")
    else:
        print("部分测试失败，请检查错误信息。")

if __name__ == "__main__":
    main()