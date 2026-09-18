# Please install OpenAI SDK first: `pip3 install openai`
import os
import json
import re
import threading
import atexit
import time

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


# ==================== Token 统计 ====================
# 每个进程把累计 token 用量增量写入自己的文件（以 PID 区分），供上层 run_all.py
# 聚合多个子进程 / worker 进程的统计。即便进程被强杀（例如 ProcessPoolExecutor 在
# Windows 下 spawn 出的 worker），增量落盘也能保留已完成调用的用量。
_token_usage_lock = threading.Lock()
_token_usage = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "call_count": 0,
    "models": {},
}

# 本进程 token 统计文件的落盘路径（惰性初始化）
_token_dump_path = None


def _get_token_dump_path():
    """返回当前进程的 token 统计文件路径；未设置环境变量时仅做内存统计"""
    global _token_dump_path
    if _token_dump_path is None:
        token_dir = os.environ.get("LIFEBENCH_TOKEN_DIR")
        if token_dir:
            os.makedirs(token_dir, exist_ok=True)
            _token_dump_path = os.path.join(token_dir, f"token_{os.getpid()}.json")
        else:
            _token_dump_path = ""
    return _token_dump_path or None


def _flush_token_usage_locked():
    """在已持有 _token_usage_lock 的前提下，把累计用量原子写入本进程的统计文件"""
    path = _get_token_dump_path()
    if not path:
        return
    snapshot = json.loads(json.dumps(_token_usage))
    snapshot["pid"] = os.getpid()
    snapshot["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        pass


def _record_usage(response):
    """从一次 chat.completions 响应中提取并累计 token 用量"""
    usage = getattr(response, "usage", None)
    if usage is None:
        return

    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    total = getattr(usage, "total_tokens", 0) or 0
    model = getattr(response, "model", None) or "unknown"

    with _token_usage_lock:
        _token_usage["prompt_tokens"] += prompt
        _token_usage["completion_tokens"] += completion
        _token_usage["total_tokens"] += total
        _token_usage["call_count"] += 1

        model_stats = _token_usage["models"].setdefault(model, {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "call_count": 0,
        })
        model_stats["prompt_tokens"] += prompt
        model_stats["completion_tokens"] += completion
        model_stats["total_tokens"] += total
        model_stats["call_count"] += 1

        _flush_token_usage_locked()


def get_token_usage():
    """返回当前进程累计的 token 用量快照（线程安全）"""
    with _token_usage_lock:
        return json.loads(json.dumps(_token_usage))


def reset_token_usage():
    """清空当前进程累计的 token 用量"""
    global _token_usage
    with _token_usage_lock:
        _token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "call_count": 0,
            "models": {},
        }


def _flush_on_exit():
    """进程退出时的兜底落盘（正常流程已在每次调用时增量落盘）"""
    if not os.environ.get("LIFEBENCH_TOKEN_DIR"):
        return
    with _token_usage_lock:
        _flush_token_usage_locked()


atexit.register(_flush_on_exit)


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
    _record_usage(response)
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

    _record_usage(response)
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

    _record_usage(response)
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

    _record_usage(response)
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

    _record_usage(response)
    return strip_think_content(response.choices[0].message.content)


def llm_agent(messages, tools, dispatch, model=None, max_turns=12):
    """带工具调用（function calling）的 agent 循环：执行工具直到模型停止请求工具。

    :param messages: 对话消息列表（与 chat.completions 的 messages 一致）
    :param tools: OpenAI function-calling 的 tools 列表
    :param dispatch: callable(tool_name, args_dict) -> 序列化结果（str 或 dict/list）
    :param model: 覆盖默认模型；缺省用 DEFAULT_MODEL
    :param max_turns: 工具循环最大轮数，防止失控
    :return: 模型最终文本内容；若超轮数未收敛返回 None
    """
    client = _get_thread_client()
    model = model or DEFAULT_MODEL
    transcript = list(messages)
    for _turn in range(max(int(max_turns), 1)):
        response = client.chat.completions.create(
            model=model,
            messages=transcript,
            tools=tools,
            stream=False,
        )
        _record_usage(response)
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            return strip_think_content(getattr(message, "content", None) or "")
        transcript.append({
            "role": "assistant",
            "content": getattr(message, "content", None) or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in tool_calls
            ],
        })
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
            result = dispatch(tc.function.name, args)
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False)
            transcript.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
    return None