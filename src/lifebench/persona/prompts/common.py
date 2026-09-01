"""Common prompt fragments."""

PROMPT_VERSION = "persona-common-v2"
SYSTEM_CONTEXT = "你是人物数据合成与校验助手。"


def render_common_rules(as_of_date: str) -> str:
    return f"""
共同要求：
1. 数据基准日期为 {as_of_date}；出生日期必须使用 YYYY-MM-DD。
2. 只输出一个合法 JSON 对象，不输出 Markdown、解释或推理过程。
3. 不使用真实私人信息；姓名、机构、门牌等均为合理虚构。
4. 输入中已有的明确事实优先级最高，不得为了叙事效果擅自改变。
5. 年龄和 BMI 最终由程序确定性重算，模型应保证出生日期、身高、体重合理。
""".strip()
