# Please install OpenAI SDK first: `pip3 install openai`
import os
import json
import threading
from datetime import datetime

from openai import OpenAI

# 读取配置文件
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# 获取LLM配置
llm_config = config.get('llm', {})
API_KEY = llm_config.get('api_key', '')
BASE_URL = llm_config.get('base_url', 'https://api.deepseek.com')

_client = None
_client_lock = threading.Lock()

# 获取全局唯一的 OpenAI 客户端实例（线程安全）
def _get_thread_client():
    """
    获取全局唯一的 OpenAI 客户端实例（线程安全）
    避免在高并发及线程频繁创建/销毁场景下的httpx连接和SSL FD泄漏
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = OpenAI(
                    api_key=API_KEY,
                    base_url=BASE_URL
                )
    return _client

# 默认系统上下文
DEFAULT_CONTEXT = "你是一个人物分析师、故事创作者、数据补全与清洗专家。"

# 日志文件路径
LOG_FILE_PATH = "llm_call_log.txt"

# 确保日志文件目录存在
log_dir = os.path.dirname(LOG_FILE_PATH)
if log_dir:  # 只有当目录名不为空时才创建目录
    os.makedirs(log_dir, exist_ok=True)


def llm_call(prompt, context="你是一个人物分析师、故事创作者、数据补全与清洗专家。",record=0):
    """
    调用LLM聊天模型（不保留对话历史）
    
    :param prompt: 用户提示词
    :param context: 系统角色上下文
    :return: LLM响应内容
    """
    # 创建独立的消息列表，不使用任何历史记录
    messages = [
        {"role": "system", "content": context},
        {"role": "user", "content": prompt}
    ]
    
    # 记录调用信息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n{'-'*50}\n"  
    log_entry += f"时间: {timestamp}\n"
    log_entry += f"函数: llm_call\n"
    log_entry += f"模型: deepseek-chat\n"
    log_entry += f"上下文: {context[:100]}...\n" if len(context) > 100 else f"上下文: {context}\n"
    log_entry += f"提示词: {prompt[:100]}...\n" if len(prompt) > 100 else f"提示词: {prompt}\n"
    
    # 获取全局唯一的OpenAI客户端实例
    client = _get_thread_client()
    
    # 调用LLM
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
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
    
    return response_content


def llm_call_reason(prompt, context="你是一个人物分析师、故事创作者、数据补全与清洗专家。",record=0):
    """
    调用LLM推理模型（不保留对话历史）
    
    :param prompt: 用户提示词
    :param context: 系统角色上下文
    :return: LLM响应内容
    """
    # 创建独立的消息列表，不使用任何历史记录
    messages = [
        {"role": "system", "content": context},
        {"role": "user", "content": prompt}
    ]
    
    # 记录调用信息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n{'-'*50}\n"  
    log_entry += f"时间: {timestamp}\n"
    log_entry += f"函数: llm_call_reason\n"
    log_entry += f"模型: deepseek-reasoner\n"
    log_entry += f"上下文: {context[:100]}...\n" if len(context) > 100 else f"上下文: {context}\n"
    log_entry += f"提示词: {prompt[:100]}...\n" if len(prompt) > 100 else f"提示词: {prompt}\n"
    
    # 获取全局唯一的OpenAI客户端实例
    client = _get_thread_client()
    
    # 调用LLM
    response = client.chat.completions.create(
        model="deepseek-reasoner",
        messages=messages,
        stream=False
    )
    
    response_content = response.choices[0].message.content
    
    # 记录响应
    log_entry += f"响应: {response_content}\n"
    log_entry += f"{'='*50}\n"
    
    # # 写入日志文件
    # with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
    #     f.write(log_entry)
    
    return response_content


def llm_call_j(prompt,record=0):
    """
    调用LLM聊天模型并要求返回JSON格式（不保留对话历史）
    
    :param prompt: 用户提示词
    :return: LLM响应的JSON内容
    """
    context = "你是一个人物分析师、故事创作者、数据补全与清洗专家。"
    # 创建独立的消息列表，不使用任何历史记录
    messages = [
        {"role": "system", "content": context},
        {"role": "user", "content": prompt}
    ]
    
    # 记录调用信息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n{'-'*50}\n"  
    log_entry += f"时间: {timestamp}\n"
    log_entry += f"函数: llm_call_j\n"
    log_entry += f"模型: deepseek-chat\n"
    log_entry += f"上下文: {context[:100]}...\n" if len(context) > 100 else f"上下文: {context}\n"
    log_entry += f"提示词: {prompt[:100]}...\n" if len(prompt) > 100 else f"提示词: {prompt}\n"
    
    # 获取全局唯一的OpenAI客户端实例
    client = _get_thread_client()
    
    # 调用LLM，增加response_format参数以确保返回JSON格式
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
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
    
    return response_content


def llm_call_reason_j(prompt,record=0):
    """
    调用LLM推理模型并要求返回JSON格式（不保留对话历史）
    
    :param prompt: 用户提示词
    :return: LLM响应的JSON内容
    """
    context = "你是一个人物分析师、故事创作者、数据补全与清洗专家。"
    # 创建独立的消息列表，不使用任何历史记录
    messages = [
        {"role": "system", "content": context},
        {"role": "user", "content": prompt}
    ]
    
    # 记录调用信息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n{'-'*50}\n"  
    log_entry += f"时间: {timestamp}\n"
    log_entry += f"函数: llm_call_reason_j\n"
    log_entry += f"模型: deepseek-reasoner\n"
    log_entry += f"上下文: {context[:100]}...\n" if len(context) > 100 else f"上下文: {context}\n"
    log_entry += f"提示词: {prompt[:100]}...\n" if len(prompt) > 100 else f"提示词: {prompt}\n"
    
    # 获取全局唯一的OpenAI客户端实例
    client = _get_thread_client()
    
    # 调用LLM，增加response_format参数以确保返回JSON格式
    response = client.chat.completions.create(
        model="deepseek-reasoner",
        messages=messages,
        stream=False,
        response_format={'type': 'json_object'}
    )
    
    response_content = response.choices[0].message.content
    
    # 记录响应
    log_entry += f"响应: {response_content}\n"
    log_entry += f"{'='*50}\n"
    
    # # 写入日志文件
    # with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
    #     f.write(log_entry)
    
    return response_content


def llm_call_skip(prompt, context="你是一个人物分析师、故事创作者、数据补全与清洗专家。",record=0):
    """
    调用LLM模型（不保留对话历史）
    
    :param prompt: 用户提示词
    :param context: 系统角色上下文
    :return: LLM响应内容
    """
    # 创建独立的消息列表，不使用任何历史记录
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