# Please install OpenAI SDK first: `pip3 install openai`
import os
import json
import re
import threading

from openai import OpenAI

# 读取配置文件
# 获取项目根目录（src/lifebench/utils的三级上级目录）
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
config_path = os.path.join(project_root, 'config', 'config.json')
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

# 获取LLM配置
llm_config = config.get('llm', {})
API_KEY = llm_config.get('api_key', '')
BASE_URL = llm_config.get('base_url', 'https://api.deepseek.com')
DEFAULT_MODEL = llm_config.get('default_model', 'deepseek-v4-flash')
REASON_MODEL = llm_config.get('reason_model', 'deepseek-v4-pro')
STRIP_THINK = llm_config.get('strip_think', False)


def strip_think_content(text):
    """
    去除文本中的 think 标签内容

    :param text: 原始文本
    :return: 去除 think 标签后的文本
    """
    if not STRIP_THINK:
        return text

    # 匹配 <think>...</think> 标签内容（包括多行）
    pattern = r'<think>[\s\S]*?</think>'
    return re.sub(pattern, '', text).strip()

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

def llm_call(prompt, context="你是一个人物分析师、故事创作者、数据补全与清洗专家。", record=0):
    """
    调用LLM聊天模型（不保留对话历史）

    :param prompt: 用户提示词
    :param context: 系统角色上下文
    :return: LLM响应内容
    """
    messages = [
        {"role": "system", "content": context},
        {"role": "user", "content": prompt}
    ]

    client = _get_thread_client()

    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        stream=False
    )
    print(response)
    return strip_think_content(response.choices[0].message.content)


def llm_call_reason(prompt, context="你是一个人物分析师、故事创作者、数据补全与清洗专家。", record=0):
    """
    调用LLM推理模型（不保留对话历史）

    :param prompt: 用户提示词
    :param context: 系统角色上下文
    :return: LLM响应内容
    """
    messages = [
        {"role": "system", "content": context},
        {"role": "user", "content": prompt}
    ]

    client = _get_thread_client()

    response = client.chat.completions.create(
        model=REASON_MODEL,
        messages=messages,
        stream=False
    )

    return strip_think_content(response.choices[0].message.content)


def llm_call_j(prompt, record=0):
    """
    调用LLM聊天模型并要求返回JSON格式（不保留对话历史）

    :param prompt: 用户提示词
    :return: LLM响应的JSON内容
    """
    context = "你是一个人物分析师、故事创作者、数据补全与清洗专家。"
    messages = [
        {"role": "system", "content": context},
        {"role": "user", "content": prompt}
    ]

    client = _get_thread_client()

    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        stream=False,
        response_format={'type': 'json_object'}
    )

    return strip_think_content(response.choices[0].message.content)


def llm_call_reason_j(prompt, record=0):
    """
    调用LLM推理模型并要求返回JSON格式（不保留对话历史）

    :param prompt: 用户提示词
    :return: LLM响应的JSON内容
    """
    context = "你是一个人物分析师、故事创作者、数据补全与清洗专家。"
    messages = [
        {"role": "system", "content": context},
        {"role": "user", "content": prompt}
    ]

    client = _get_thread_client()

    response = client.chat.completions.create(
        model=REASON_MODEL,
        messages=messages,
        stream=False,
        response_format={'type': 'json_object'}
    )

    return strip_think_content(response.choices[0].message.content)


def llm_call_skip(prompt, context="你是一个人物分析师、故事创作者、数据补全与清洗专家。", record=0):
    """
    调用LLM模型（不保留对话历史）

    :param prompt: 用户提示词
    :param context: 系统角色上下文
    :return: LLM响应内容
    """
    messages = [
        {"role": "system", "content": context},
        {"role": "user", "content": prompt}
    ]

    client = _get_thread_client()

    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        stream=False
    )

    return strip_think_content(response.choices[0].message.content)