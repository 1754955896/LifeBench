"""Shared contracts come from existing builders; country and stage rules live here."""
import json
from ...international_policy import local_profile, supported_modes, allow_fictional_details
from src.lifebench.utils.locale_context import current_locale


def render(stage, body, inputs, rules=''):
    locale = current_locale()
    policy = local_profile()
    profile = inputs.get('profile') or inputs.get('seed_person') or inputs.get('structured_profile') or {}
    body = body.replace('用于长期生活模拟的中文用户画像', '用于长期生活模拟的人物画像')
    body = body.replace('不使用真实私人信息；姓名、机构、门牌等均为合理虚构。',
                        '不使用真实私人信息。人物与雇主可合理虚构；地点及门牌由地图验证，不编造缺失门牌。')
    body = body.replace('地址和组织均为合理虚构，避免直接使用知名真实个人信息。',
                        '人物与雇主可合理虚构；地址必须结构化，后续由地图落地，不冒用真实私人身份。')
    info = {'locale': locale.to_dict() if locale else {}, 'country_profile': policy,
            'routing_modes': supported_modes(profile), 'allow_fictional_details': allow_fictional_details()}
    return ('[PERSONA_INTERNATIONAL_STAGE:' + stage + ']\n' + json.dumps(info, ensure_ascii=False) +
            '\n地区约束：内容使用 output_language，人物和单位名字可用当地语言；字段名和类型枚举严格保持。'
            '用户明确输入为最高优先级。未知当地制度不编造，参考候选不适用时允许选择当地合理内容。'
            '每个地址保留自身 country_code；不得根据国籍推断居住地。'
            '金额注明币种和周期；收入、房租等可以作为合理合成设定，但不能自称官方核验数据。'
            'allow_fictional_details=true 时允许虚构公司、学校、租赁关系、社交活动和经历；'
            '优先保证国家背景、时间线、人物关系与地理距离自洽，不要求虚构实体真实存在。'
            '真实 POI 只证明地点存在，合成的雇主和租赁关系不能称为地图核验事实。\n' +
            body + '\n\n本阶段国际规则：\n' + rules)
