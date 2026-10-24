"""Per-person synthesis context. Legacy CN runs retain their original behavior."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import asdict, dataclass
from functools import wraps
import hashlib
import inspect
import json
import re
from pathlib import Path


# Country-level defaults are limited to unambiguous zones. Multi-zone countries
# require a timezone on the address (or in locale_defaults).
COUNTRIES = {
    "CN": ("China", "中国", "Asia/Shanghai", "CNY", "zh-CN"),
    "GB": ("United Kingdom", "英国", "Europe/London", "GBP", "en"),
    "FR": ("France", "法国", "Europe/Paris", "EUR", "fr"),
    "DE": ("Germany", "德国", "Europe/Berlin", "EUR", "de"),
    "JP": ("Japan", "日本", "Asia/Tokyo", "JPY", "ja"),
    "KR": ("South Korea", "韩国", "Asia/Seoul", "KRW", "ko"),
    "SG": ("Singapore", "新加坡", "Asia/Singapore", "SGD", "en"),
    "US": ("United States", "美国", "", "USD", "en"),
    "CA": ("Canada", "加拿大", "", "CAD", "en"),
    "AU": ("Australia", "澳大利亚", "", "AUD", "en"),
    "NZ": ("New Zealand", "新西兰", "", "NZD", "en"),
    "IN": ("India", "印度", "Asia/Kolkata", "INR", "en"),
    "IT": ("Italy", "意大利", "Europe/Rome", "EUR", "it"),
    "NL": ("Netherlands", "荷兰", "Europe/Amsterdam", "EUR", "nl"),
    "IE": ("Ireland", "爱尔兰", "Europe/Dublin", "EUR", "en"),
}
_ALIASES = {name.casefold(): code for code, row in COUNTRIES.items() for name in row[:2]}
_ALIASES.update({"uk": "GB", "usa": "US", "united states of america": "US", "中华人民共和国": "CN"})
_SETTINGS = {"policy": "amap", "services": {}, "locale_defaults": {}}
_TIME_RANGE = ContextVar('lifebench_generation_time_range', default=None)


def configure_generation_time_range(start_date=None, end_date=None):
    """Optional scope for partial-year evidence generation; legacy full 2025 stays unchanged."""
    _TIME_RANGE.set({'start_date': start_date, 'end_date': end_date} if start_date and end_date else None)


def generation_year(default=2025):
    period = _TIME_RANGE.get()
    return int(period['start_date'][:4]) if period else default


def current_generation_time_range():
    period = _TIME_RANGE.get()
    return dict(period) if period else None


def generation_date_allowed(value):
    period = _TIME_RANGE.get()
    if not period or not value or not isinstance(value, str):
        return True
    day = value[:10] if len(value) >= 10 else value + '-01'
    return period['start_date'] <= day <= period['end_date']


def qa_ask_date_allowed(value):
    period = _TIME_RANGE.get()
    if not period or not value or not isinstance(value, str):
        return True
    day = value[:10] if len(value) >= 10 else value + '-01'
    return period['start_date'] <= day <= f'{generation_year()}-12-31'


@dataclass(frozen=True)
class PersonaLocaleContext:
    country_code: str = "CN"
    timezone: str = "Asia/Shanghai"
    currency: str = "CNY"
    salary_period: str = "annual"
    output_language: str = "zh-CN"
    local_language: str = "zh-CN"
    subdivision: str = ""

    def to_dict(self):
        return asdict(self)


_LOCALE = ContextVar("lifebench_persona_locale", default=None)
_ADDRESS = ContextVar("lifebench_target_address", default=None)
_OPTIONS = ContextVar("lifebench_task_map_options", default=None)


def configure_settings(policy="amap", services=None, locale_defaults=None):
    if policy not in {"amap", "overseas", "auto"}:
        raise ValueError("Unknown map policy")
    _SETTINGS.update(policy=policy, services=dict(services or {}), locale_defaults=dict(locale_defaults or {}))


def map_settings():
    settings = _OPTIONS.get() or _SETTINGS
    return dict(settings, services=dict(settings["services"]), locale_defaults=dict(settings["locale_defaults"]))


def country_code(value):
    if not value:
        return ""
    text = str(value).strip()
    if text.casefold() in _ALIASES:
        return _ALIASES[text.casefold()]
    if len(text) == 2 and text.isascii() and text.isalpha():
        return text.upper()
    raise ValueError("Country must be an ISO alpha-2 code or a supported country name")


def address_country(address):
    if not isinstance(address, dict):
        return ""
    code = country_code(address.get("country_code"))
    name_value = address.get("country")
    try:
        name = country_code(name_value)
    except ValueError:
        if not code:
            raise
        name = ""
    if code and name and code != name:
        raise ValueError("Address country and country_code conflict")
    return code or name


def _persona(value):
    if hasattr(value, "data") and isinstance(value.data, dict):
        return value.data
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return {}
    return value if isinstance(value, dict) else {}


def resolve_locale(persona=None, *, strict=False):
    person = _persona(persona)
    address = person.get("home_address") or {}
    if not isinstance(address, dict):
        address = {}  # Arbitrary-input records are normalized by the LLM later.
    defaults = map_settings()["locale_defaults"]
    supplied_context = person.get("locale_context")
    supplied_context = supplied_context if isinstance(supplied_context, dict) else {}
    metadata = dict(defaults, **supplied_context)
    explicit_country = address_country(address)
    if explicit_country and defaults.get("country_code") and explicit_country != country_code(defaults["country_code"]):
        for key in ("timezone", "currency", "local_language", "subdivision"):
            if key not in supplied_context:
                metadata.pop(key, None)
    metadata.update({k: address[k] for k in ("timezone", "currency", "salary_period", "output_language", "local_language", "subdivision") if address.get(k)})
    code = address_country(address) or country_code(metadata.get("country_code"))
    if not code:
        if map_settings()["policy"] == "amap":
            code = "CN"
        elif strict:
            raise ValueError("Residence country is required in home_address.country_code")
        else:
            return _LOCALE.get()
    row = COUNTRIES.get(code, (code, code, "", "", ""))
    timezone = str(metadata.get("timezone") or row[2])
    if strict and not timezone:
        raise ValueError("Explicit timezone required for this country")
    if strict and timezone:
        from zoneinfo import ZoneInfo
        ZoneInfo(timezone)
    if strict and not (metadata.get("currency") or row[3]):
        raise ValueError("Explicit currency required for this country")
    return PersonaLocaleContext(code, timezone, str(metadata.get("currency") or row[3]),
                                str(metadata.get("salary_period") or "annual"),
                                str(metadata.get("output_language") or "zh-CN"),
                                str(metadata.get("local_language") or row[4]),
                                str(metadata.get("subdivision") or ""))


def current_locale():
    return _LOCALE.get()


def target_address():
    return _ADDRESS.get() or {}


def international_run():
    return map_settings()["policy"] != "amap"


def refresh_locale(persona, strict=False):
    locale = resolve_locale(persona, strict=strict)
    _LOCALE.set(locale)
    return locale


def enrich_residence(persona):
    if not international_run():
        if address_country(persona.get("home_address") or {}) not in ("", "CN"):
            raise ValueError("Foreign residence requires --map-tool overseas or auto")
        return
    locale = refresh_locale(persona, strict=True)
    address = persona.setdefault("home_address", {})
    for key, value in locale.to_dict().items():
        if value:
            address.setdefault(key, value)


def profile_address_task(function):
    signature = inspect.signature(function)
    @wraps(function)
    def run(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        address = bound.arguments["profile"].get(bound.arguments["field"]) or {}
        with destination_scope(address):
            return function(*args, **kwargs)
    return run


def coordinate_system():
    return "WGS-84" if international_run() else "GCJ-02"


@contextmanager
def persona_scope(persona, strict=False):
    token = _LOCALE.set(resolve_locale(persona, strict=strict))
    try:
        yield _LOCALE.get()
    finally:
        _LOCALE.reset(token)


@contextmanager
def destination_scope(address):
    token = _ADDRESS.set(dict(address or {}))
    try:
        yield
    finally:
        _ADDRESS.reset(token)


def persona_task(parameter=None):
    def decorate(function):
        signature = inspect.signature(function)
        @wraps(function)
        def run(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            owner = bound.arguments.get("self")
            person = bound.arguments.get(parameter) if parameter else None
            if person is None:
                person = getattr(owner, "persona", None) or getattr(owner, "persona_data", None)
            if person is None and getattr(owner, "data_path", None):
                path = Path(owner.data_path) / "persona.json"
                if path.is_file():
                    person = json.loads(path.read_text(encoding="utf-8-sig"))
            # An explicitly injected raw overseas client also opts this task in,
            # without changing global defaults for another generator/thread.
            service = getattr(owner, "address_service", None)
            tool = getattr(service, "map_tool", None)
            override = None
            if not international_run() and getattr(tool, "country_code", None) and getattr(tool, "coordinate_system", None) == "WGS-84":
                keys = ("nominatim_url", "photon_url", "overpass_url", "valhalla_url", "poi_backend", "overpass_method", "language", "user_agent", "timeout_seconds", "enable_transit", "city_aliases", "requests_per_second", "rate_limit_retries")
                override = _OPTIONS.set({"policy": "overseas", "services": {key: getattr(tool, key) for key in keys},
                                         "locale_defaults": {"country_code": tool.country_code.upper()}})
            try:
                with persona_scope(person):
                    return function(*args, **kwargs)
            finally:
                if override is not None:
                    _OPTIONS.reset(override)
        return run
    return decorate


def address_task(parameter):
    def decorate(function):
        signature = inspect.signature(function)
        @wraps(function)
        def run(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            value = bound.arguments[parameter]
            address = value if isinstance(value, dict) else vars(value)
            with destination_scope(address):
                return function(*args, **kwargs)
        return run
    return decorate


class LocaleThreadPoolExecutor(ThreadPoolExecutor):
    def submit(self, function, /, *args, **kwargs):
        return super().submit(copy_context().run, function, *args, **kwargs)


def locale_instructions():
    locale = current_locale()
    if not international_run():
        return ""
    info = locale.to_dict() if locale else {"country_code": "extract explicit residence country from input"}
    return ("\n[LIFEBENCH_LOCALE]\n" + json.dumps(info, ensure_ascii=False) +
            "\n按上述居住地生成当地合理的教育、职业、节假日、货币、饮食和社交生活。"
            "国籍与居住国家不同；nationality 旧值可能是民族，不据此确定居住地。"
            "所有人物及联系人的 home_address/workplace/birth_place 按各自实际国家填写 country_code，"
            "地址保留 province/city/district/street_name/street_number，缺失行政层级可留空，不虚构门牌。"
            "居住地址附加 timezone/currency/salary_period/output_language，保持已有明确值。"
            "数值金额使用指定货币和收入周期；根据实际所在地选择可用应用、电话号码与支付方式。"
            "先前模板中的中国节庆、微信、支付宝、元等示例应按人物背景调整，不将示例当事实。"
            "参考池中不适用于所在地的候选可替换为合理的当地选项。"
            "输出内容使用 output_language，JSON 字段名、类型枚举和格式契约保持原样。"
            "跨时区的 stops 还必须提供带 UTC 偏移的 ISO8601 start_timestamp/end_timestamp。"
            "跨国活动明确各站国家、当地时间与时区；没有资料不编造航班或公交时刻表。"
            "地图路线默认只支持 walking/driving/bicycling；路线不可用时允许保留原交通方式的"
            "粗略合成时距估算，明确是估算、未经地图核验；不据此声称具体公交班次或航班可用。"
            "不得把公交或航班改写成驾车来凑时间。\n")


def localize_prompt(prompt):
    instruction = locale_instructions()
    result = prompt
    period = _TIME_RANGE.get()
    if period and generation_year() != 2025:
        # Update explicit legacy year constraints, never dates in the input data.
        result = re.sub(r'(年份(?:必须为|是否为|不是)\s*)2025',
                        lambda match: match[1] + str(generation_year()), str(result))
        result = re.sub(r'(?m)^([ \t]*-[^\n]*(?:格式|datetime|start_time|end_time)[^\n]*年份为\s*)2025',
                        lambda match: match[1] + str(generation_year()), str(result))
        result = re.sub(r'(所有时间必须在\s*|当前年份[：:]\s*)2025',
                        lambda match: match[1] + str(generation_year()), str(result))
    if instruction and "[LIFEBENCH_LOCALE]" not in str(result):
        result = str(result) + instruction
    if period and '[LIFEBENCH_TIME_RANGE]' not in str(result):
        result = (str(result) + '\n[LIFEBENCH_TIME_RANGE]\n' + json.dumps(period) +
                  '\n本次生活数据与手机证据只在上述范围内生成。QA可在事实之后至当年12月31日回顾这些事实。模板中的其他年份日期是示例，'
                  '不要为没有生活数据的月份补造已发生的证据。范围外的明确历史或未来计划可作为背景引用。\n')
    return result


def calendar_country(explicit=None):
    return country_code(explicit) if explicit else (current_locale().country_code if current_locale() else "CN")


def calendar_label():
    code = calendar_country()
    return "中国" if code == "CN" else code


def country_holidays(years=None, country=None):
    import holidays
    code = calendar_country(country)
    locale = current_locale()
    if code == "CN":
        return holidays.China(years=years)
    return holidays.country_holidays(code, years=years, subdiv=locale.subdivision or None if locale else None)


def context_fingerprint(persona=None):
    locale = resolve_locale(persona) if persona is not None else current_locale()
    value = {"schema": "persona_locale_v1", "locale": locale.to_dict() if locale else None,
             "map_policy": map_settings()["policy"], "services": map_settings()["services"]}
    if international_run():
        from src.lifebench.persona.international_policy import country_profile
        value['persona_prompt_version'] = 'international-stages-v1'
        value['country_profile'] = country_profile(locale.country_code if locale else '')
        value['allow_fictional_details'] = map_settings()['locale_defaults'].get('allow_fictional_details', True)
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def bind_persona_file(folder):
    """Bind one CLI process; persist context and refuse incompatible resume data."""
    if not international_run():
        return None
    folder = Path(folder)
    person = json.loads((folder / "persona.json").read_text(encoding="utf-8-sig"))
    locale = refresh_locale(person, strict=True)
    metadata = {"schema_version": "persona_locale_v1", "locale": locale.to_dict(),
                "fingerprint": context_fingerprint(person), "map_policy": map_settings()["policy"]}
    path = folder / "persona_context.json"
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("fingerprint") != metadata["fingerprint"]:
            raise ValueError("Existing synthesis context differs; use a new output directory")
    elif any((folder / name).exists() for name in ("daily_event.json", "phone_data/contact.json")) or any(folder.glob("sim/checkpoint*.json")):
        raise ValueError("Existing synthesis artifacts have no locale metadata; use a new output directory")
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return locale
