from .common import render as common


def render(stage, body, inputs):
    return common(stage, body, inputs,
        '按实际居住地补全教育、工作和生活背景，不套用中国学制、公司形式和社会保障。'
        '将全天远程与每周部分天数居家办公区分。用户未指定交通时，只从 routing_modes 中选择通勤方式；'
        '用户已指定的交通必须保留，即使后端无法验证。国家、时区、币种和年/月收入周期保持一致。')
