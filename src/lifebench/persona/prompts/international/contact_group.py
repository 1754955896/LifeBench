from .common import render as common


def render(stage, body, inputs):
    return common(stage, body, inputs,
        '联系人姓名、教育与单位名称按自身国家背景生成。所有 home_address/birth_place 均含 country_code。'
        'neighborhood 联系人的居住行政区必须与圈子共享行政区一致；当地街区与 borough 分开记录。'
        'household 使用共同住宅；current_work 使用固定雇主；学校同学的当前雇主可以不同。'
        '学校与组织可合理虚构并保持共享设定；门牌不必精确，不能以虚构名称冒充已核验实体。')
