"""Country policies used exclusively by opted-in international persona tasks."""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from src.lifebench.utils.locale_context import current_locale, international_run, map_settings, address_country


@lru_cache(maxsize=32)
def country_profile(code):
    path = Path(__file__).with_name('locale_profiles') / (code + '.json')
    if path.is_file():
        return json.loads(path.read_text(encoding='utf-8'))
    return {'country_code': code, 'version': 'generic-v1',
            'address_rules': '保留当地行政层级；没有资料时留空，不将 neighbourhood 当成行政区。',
            'life_rules': '根据明确居住地生成；不确定当地制度、税率、学校或企业形式时不编造精确事实。',
            'community_rules': '每个联系人按自身居住地生成，继承圈子共享事实。'}


def local_profile():
    locale = current_locale()
    return deepcopy(country_profile(locale.country_code if locale else ''))


def allow_fictional_details():
    return international_run() and map_settings()['locale_defaults'].get('allow_fictional_details', True)


def supported_modes(profile=None):
    settings = map_settings()
    code = address_country((profile or {}).get('home_address') or {})
    code = code or (current_locale().country_code if current_locale() else '')
    if settings['policy'] == 'auto' and code == 'CN':
        return ['walking', 'bicycling', 'driving', 'transit']
    options = settings['services']
    modes = ['walking', 'bicycling', 'driving'] if options.get('valhalla_url') else []
    if modes and options.get('enable_transit'):
        modes.append('transit')
    return modes


def work_arrangement(profile):
    text = ' '.join(str(profile.get(k) or '') for k in ('work_desc', 'lifestyle_desc', 'description'))
    if any(word in text.casefold() for word in ('全远程', '完全远程', '全职远程', 'fully remote', '所有工作日均居家')):
        return 'remote'
    if any(word in text.casefold() for word in ('混合办公', 'hybrid', '每周', '部分时间', '部分工作日')) and any(
            word in text.casefold() for word in ('远程', '居家', 'remote', 'home')):
        return 'hybrid'
    return 'onsite'


def mobility_profile(profile, legacy, source_profile=None, soft_clues=None, source_description=''):
    """Do not treat model-written lifestyle details as explicit user choices."""
    from .grounding import _all_text
    source = _all_text(source_profile or {}, soft_clues or {}, source_description).casefold()
    terms = {'walking': ('步行通勤', '走路上班', 'walking commute'),
             'bicycling': ('骑行通勤', '自行车通勤', 'cycle to work', 'cycling commute'),
             'transit': ('地铁', '公交', '公共交通', '不自驾', '不开车', '无车', 'underground', 'public transport', 'subway'),
             'driving': ('自驾通勤', '开车上班', '驾车通勤', 'drive to work')}
    explicit = next(((mode, word) for mode, words in terms.items() for word in words if word in source), None)
    result = dict(legacy)
    if explicit:
        result.update(primary_transport=explicit[0], explicit=True, evidence=[explicit[1]], preference_source='user_input')
    else:
        modes = supported_modes(profile)
        choice = legacy['primary_transport']
        if choice not in modes and modes:
            choice = 'walking' if 'walking' in modes else modes[0]
        result.update(primary_transport=choice, explicit=False, preference_source='model')
    result['work_arrangement'] = work_arrangement(profile)
    result['supported_transport_modes'] = supported_modes(profile)
    return result


def employer_anchor(profile, seed=None):
    code = address_country(profile.get('home_address') or {}) or (current_locale().country_code if current_locale() else '')
    policy = country_profile(code)
    text = (str(profile.get('job') or '') + ' ' + str(profile.get('occupation') or '')).casefold()
    industry = 'services'
    for key, words in (('technology', ('软件', '开发', '数据', 'software', 'developer', 'engineer')),
                       ('education', ('教师', '教育', 'teacher')), ('health', ('医生', '护士', '医疗', 'nurse')),
                       ('engineering', ('制造', '机械', '工程')), ('creative', ('设计', '媒体', 'design'))):
        if any(word in text for word in words):
            industry = key
            break
    names = policy.get('employer_names', ['Alder', 'Cedar', 'Willow'])
    material = json.dumps([profile.get('name'), code, seed, industry], ensure_ascii=False)
    index = int(hashlib.sha256(material.encode()).hexdigest()[:8], 16) % len(names)
    sector = policy.get('employer_industries', {}).get(industry, 'Services')
    name = ' '.join(filter(None, [names[index], sector, policy.get('employer_suffix', '')]))
    return dict(name=name, industry=industry, fictional=True, relationship_verified=False,
                allow_fictional_relationship=allow_fictional_details(), relationship_source='synthetic',
                workplace_poi='', workplace_address=deepcopy(profile.get('workplace') or {}))


def validate_commute(context):
    if not international_run():
        return []
    commute, mobility = context.get('commute') or {}, context.get('mobility_profile') or {}
    errors = []
    if commute.get('status') != 'not_required' and mobility.get('explicit') and commute.get('commute_transport') != mobility.get('primary_transport'):
        errors.append('地址分配交通方式与用户明确交通偏好不一致')
    is_estimate = allow_fictional_details() and commute.get('duration_source') == 'estimate' and commute.get('estimate_method')
    if commute.get('commute_minutes') is not None and not commute.get('route_api_used') and commute.get('status') != 'not_required' and not is_estimate:
        errors.append('未验证的通勤路线不得提供确定耗时')
    return errors
