# Please install OpenAI SDK first: `pip3 install openai`
import copy
import threading
import os
import json
from datetime import datetime

from openai import OpenAI

# 读取配置文件
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# 获取LLM配置
llm_config = config.get('llm', {})
API_KEY = llm_config.get('api_key', '')
BASE_URL = llm_config.get('base_url', 'https://api.deepseek.com')

# 创建线程本地存储，用于保存每个线程的OpenAI客户端实例
thread_local = threading.local()

# 获取或创建当前线程的OpenAI客户端实例
def _get_thread_client():
    """获取当前线程的OpenAI客户端实例，如果不存在则创建"""
    if not hasattr(thread_local, "client"):
        thread_local.client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    return thread_local.client

# 用于保存每个线程的对话历史（已在上文定义）

# 日志写入线程锁，确保多线程环境下的日志记录安全
# log_lock = threading.Lock()  # 已禁用以提升并行性能

# 默认系统上下文
DEFAULT_CONTEXT = "你是一个人物分析师、故事创作者、数据补全与清洗专家。"

# 日志文件路径
LOG_FILE_PATH = "llm_call_log.txt"

# 确保日志文件目录存在
log_dir = os.path.dirname(LOG_FILE_PATH)
if log_dir:  # 只有当目录名不为空时才创建目录
    os.makedirs(log_dir, exist_ok=True)


def _get_thread_history():
    """获取当前线程的共享对话历史，如果不存在则初始化"""
    if not hasattr(thread_local, "shared_history"):
        thread_local.shared_history = [{"role": "system", "content": DEFAULT_CONTEXT}]
    return thread_local.shared_history


def _reset_thread_history(context):
    """重置当前线程的共享对话历史"""
    thread_local.shared_history = [{"role": "system", "content": context}]


def llm_call(prompt, context="你是一个人物分析师、故事创作者、数据补全与清洗专家。", record=0):
    """
    调用LLM聊天模型（与llm_call_reason共享对话历史）
    
    :param prompt: 用户提示词
    :param context: 系统角色上下文
    :param record: 是否记录对话到历史（1=记录，0=不记录/重置）
    :return: LLM响应内容
    """
    # 获取当前线程的共享对话历史
    shared_history = _get_thread_history()
    
    # 更新系统上下文
    shared_history[0]["content"] = context
    
    # 创建当前请求的消息副本
    current_messages = copy.deepcopy(shared_history)
    current_messages.append({"role": "user", "content": prompt})
    
    # 记录调用信息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n{'-'*50}\n"  
    log_entry += f"时间: {timestamp}\n"
    log_entry += f"函数: llm_call\n"
    log_entry += f"模型: deepseek-chat\n"
    log_entry += f"上下文: {context[:100]}...\n" if len(context) > 100 else f"上下文: {context}\n"
    log_entry += f"提示词: {prompt[:100]}...\n" if len(prompt) > 100 else f"提示词: {prompt}\n"
    log_entry += f"记录历史: {'是' if record == 1 else '否'}\n"
    
    # 获取当前线程的OpenAI客户端实例
    client = _get_thread_client()
    
    # 调用LLM
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=current_messages,
        stream=False

    )
    
    assistant_message = response.choices[0].message
    response_content = assistant_message.content
    
    # 记录响应
    log_entry += f"响应: {response_content[:100]}...\n"
    log_entry += f"{'='*50}\n"
    
    # 写入日志文件（线程安全）
    # with log_lock:
    #     with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
    #         f.write(log_entry)
    
    # 处理对话历史
    if record == 1:
        # 记录助手回复到共享历史
        shared_history.append({"role": "user", "content": prompt})
        shared_history.append({"role": assistant_message.role, "content": response_content})
    elif record == 0:
        # 重置共享对话历史
        _reset_thread_history(context)
    
    return response_content


def llm_call_reason(prompt, context="你是一个人物分析师、故事创作者、数据补全与清洗专家。", record=0):
    """
    调用LLM推理模型（与llm_call共享对话历史）
    
    :param prompt: 用户提示词
    :param context: 系统角色上下文
    :param record: 是否记录对话到历史（1=记录，0=不记录/重置）
    :return: LLM响应内容
    """
    # 获取当前线程的共享对话历史
    shared_history = _get_thread_history()
    
    # 更新系统上下文
    shared_history[0]["content"] = context
    
    # 创建当前请求的消息副本
    current_messages = copy.deepcopy(shared_history)
    current_messages.append({"role": "user", "content": prompt})
    
    # 记录调用信息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n{'-'*50}\n"  
    log_entry += f"时间: {timestamp}\n"
    log_entry += f"函数: llm_call_reason\n"
    log_entry += f"模型: deepseek-reasoner\n"
    log_entry += f"上下文: {context[:100]}...\n" if len(context) > 100 else f"上下文: {context}\n"
    log_entry += f"提示词: {prompt[:100]}...\n" if len(prompt) > 100 else f"提示词: {prompt}\n"
    log_entry += f"记录历史: {'是' if record == 1 else '否'}\n"
    
    # 获取当前线程的OpenAI客户端实例
    client = _get_thread_client()
    #print("deepseek-reasoner:",current_messages)
    # 调用LLM
    response = client.chat.completions.create(
        model="deepseek-reasoner",
        messages=current_messages,
        stream=False
    )
    #print("deepseek-reasoner:",response.choices[0].message.reasoning_content)
    response_content = response.choices[0].message.content
    
    # 记录响应
    log_entry += f"响应: {response_content}\n"
    log_entry += f"{'='*50}\n"
    
    # # 写入日志文件
    # with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
    #     f.write(log_entry)
    
    # 处理对话历史
    if record == 1:
        # 记录助手回复到共享历史
        shared_history.append({"role": "user", "content": prompt})
        shared_history.append({"role": "assistant", "content": response_content})
    elif record == 0:
        # 重置共享对话历史
        _reset_thread_history(context)
    
    return response_content


def llm_call_j(prompt, record=0):
    """
    调用LLM聊天模型并要求返回JSON格式（与llm_call共享对话历史）
    
    :param prompt: 用户提示词
    :param context: 系统角色上下文
    :param record: 是否记录对话到历史（1=记录，0=不记录/重置）
    :return: LLM响应的JSON内容
    """
    context = "你是一个人物分析师、故事创作者、数据补全与清洗专家。"
    # 获取当前线程的共享对话历史
    shared_history = _get_thread_history()
    
    # 更新系统上下文
    shared_history[0]["content"] = context
    
    # 创建当前请求的消息副本
    current_messages = copy.deepcopy(shared_history)
    current_messages.append({"role": "user", "content": prompt})
    
    # 记录调用信息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n{'-'*50}\n"  
    log_entry += f"时间: {timestamp}\n"
    log_entry += f"函数: llm_call_j\n"
    log_entry += f"模型: deepseek-chat\n"
    log_entry += f"上下文: {context[:100]}...\n" if len(context) > 100 else f"上下文: {context}\n"
    log_entry += f"提示词: {prompt[:100]}...\n" if len(prompt) > 100 else f"提示词: {prompt}\n"
    log_entry += f"记录历史: {'是' if record == 1 else '否'}\n"
    
    # 获取当前线程的OpenAI客户端实例
    client = _get_thread_client()
    
    # 调用LLM，增加response_format参数以确保返回JSON格式
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=current_messages,
        stream=False,
        response_format={'type': 'json_object'}
    )
    
    assistant_message = response.choices[0].message
    response_content = assistant_message.content
    
    # 记录响应
    log_entry += f"响应: {response_content[:100]}...\n" if len(response_content) > 100 else f"响应: {response_content}\n"
    log_entry += f"{'='*50}\n"
    
    # # 写入日志文件（线程安全）
    # with log_lock:
    #     with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
    #         f.write(log_entry)
    
    # 处理对话历史
    if record == 1:
        # 记录助手回复到共享历史
        shared_history.append({"role": "user", "content": prompt})
        shared_history.append({"role": assistant_message.role, "content": response_content})
    elif record == 0:
        # 重置共享对话历史
        _reset_thread_history(context)
    
    return response_content


def llm_call_reason_j(prompt, record=0):
    """
    调用LLM推理模型并要求返回JSON格式（与llm_call共享对话历史）
    
    :param prompt: 用户提示词
    :param context: 系统角色上下文
    :param record: 是否记录对话到历史（1=记录，0=不记录/重置）
    :return: LLM响应的JSON内容
    """
    context = "你是一个人物分析师、故事创作者、数据补全与清洗专家。"
    # 获取当前线程的共享对话历史
    shared_history = _get_thread_history()
    
    # 更新系统上下文
    shared_history[0]["content"] = context
    
    # 创建当前请求的消息副本
    current_messages = copy.deepcopy(shared_history)
    current_messages.append({"role": "user", "content": prompt})
    
    # 记录调用信息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n{'-'*50}\n"  
    log_entry += f"时间: {timestamp}\n"
    log_entry += f"函数: llm_call_reason_j\n"
    log_entry += f"模型: deepseek-reasoner\n"
    log_entry += f"上下文: {context[:100]}...\n" if len(context) > 100 else f"上下文: {context}\n"
    log_entry += f"提示词: {prompt[:100]}...\n" if len(prompt) > 100 else f"提示词: {prompt}\n"
    log_entry += f"记录历史: {'是' if record == 1 else '否'}\n"
    
    # 获取当前线程的OpenAI客户端实例
    client = _get_thread_client()
    #print("deepseek-reasoner:",current_messages)
    # 调用LLM，增加response_format参数以确保返回JSON格式
    response = client.chat.completions.create(
        model="deepseek-reasoner",
        messages=current_messages,
        stream=False,
        response_format={'type': 'json_object'}
    )
    #print("deepseek-reasoner:",response.choices[0].message.reasoning_content)
    response_content = response.choices[0].message.content
    
    # 记录响应
    log_entry += f"响应: {response_content}\n"
    log_entry += f"{'='*50}\n"
    
    # # 写入日志文件
    # with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
    #     f.write(log_entry)
    
    # 处理对话历史
    if record == 1:
        # 记录助手回复到共享历史
        shared_history.append({"role": "user", "content": prompt})
        shared_history.append({"role": "assistant", "content": response_content})
    elif record == 0:
        # 重置共享对话历史
        _reset_thread_history(context)
    
    return response_content


def llm_call_skip(prompt, context="你是一个人物分析师、故事创作者、数据补全与清洗专家。"):
    """
    调用LLM模型（不使用/不修改共享对话历史）
    
    :param prompt: 用户提示词
    :param context: 系统角色上下文
    :return: LLM响应内容
    """
    # 创建独立的消息列表，不影响共享历史
    messages = [
        {"role": "system", "content": context},
        {"role": "user", "content": prompt}
    ]
    
    # 记录调用信息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n{'-'*50}\n"  
    log_entry += f"时间: {timestamp}\n"
    log_entry += f"函数: llm_call_skip\n"
    log_entry += f"模型: deepseek-chat\n"
    log_entry += f"上下文: {context[:100]}...\n" if len(context) > 100 else f"上下文: {context}\n"
    log_entry += f"提示词: {prompt[:100]}...\n" if len(prompt) > 100 else f"提示词: {prompt}\n"
    log_entry += f"记录历史: 否\n"
    
    # 获取当前线程的OpenAI客户端实例
    client = _get_thread_client()
    
    # 调用LLM
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        stream=False
    )
    
    response_content = response.choices[0].message.content
    
    # 记录响应
    log_entry += f"响应: {response_content[:100]}...\n" if len(response_content) > 100 else f"响应: {response_content}\n"
    log_entry += f"{'='*50}\n"
    
    # # 写入日志文件
    # with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
    #     f.write(log_entry)
    
    return response_content