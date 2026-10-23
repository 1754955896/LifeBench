from .common import render as common


def render(stage, body, inputs):
    return common(stage, body, inputs,
        '同时检查当地背景、币种与周期、工作模式、交通方式、办公 POI 与雇主关系、活动时段。'
        '合成租赁关系、学校和组织允许存在；检查其内部一致性，不要求这些实体可检索。'
        '禁止把未验证的公交耗时称为地图结果。圈名使用当地合理称谓；'
        '只修复既定输出契约允许的字段，其他事实问题应报告，不得为通过检查更换冻结地址或国家。')
