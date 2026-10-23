"""Normalize provider administrative levels without assuming all levels are districts."""
from copy import deepcopy
import re
import unicodedata

from src.lifebench.utils.locale_context import address_country


def region_key(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold().strip()
    text = re.sub(r'^(?:london borough of|royal borough of|borough of|city of)\s+', '', text)
    return re.sub(r'[^\w]+', ' ', text).strip()


def normalize_address(address):
    result = deepcopy(address)
    code = address_country(address)
    if code:
        result['country_code'] = code
    if code != 'GB':
        result.setdefault('administrative_area', result.get('district') or '')
        return result
    raw = address.get('raw_provider_address') or {
        k: address.get(k, '') for k in ('country_code', 'province', 'city', 'district', 'county', 'state_district', 'formatted_address')}
    result['raw_provider_address'] = deepcopy(raw)
    city, district = str(address.get('city') or ''), str(address.get('district') or '')
    borough = next((str(raw.get(key) or '') for key in ('city', 'county', 'state_district', 'district')
                    if re.match(r'^(?:London Borough of|Royal Borough of|Borough of)\s+', str(raw.get(key) or ''), re.I)), '')
    admin = str(address.get('administrative_area') or '')
    if borough:
        admin = re.sub(r'^(?:London Borough of|Royal Borough of|Borough of)\s+', '', borough, flags=re.I)
        if district and region_key(district) != region_key(admin):
            result['neighbourhood'] = district
        if city.casefold().startswith('london borough of'):
            result['city'] = 'London'
        result['administrative_area_source'] = 'provider'
    # A model/input address can already explicitly use district as its borough.
    admin = admin or district
    result.update(administrative_area=admin, district=admin)
    return result


def region_relationship(expected, actual):
    """Unknown administrative coverage is not proof of a contradiction."""
    left, right = normalize_address(expected), normalize_address(actual)
    if not address_country(left) or not address_country(right):
        return 'unknown'
    if address_country(left) != address_country(right):
        return 'conflict'
    for key in ('province',):
        if left.get(key) and right.get(key) and region_key(left[key]) != region_key(right[key]):
            return 'conflict'
    if same_region(left, right):
        return 'match'
    if right.get('administrative_area_source') == 'provider' and left.get('district'):
        return 'conflict'
    return 'unknown'


def same_region(expected, actual):
    left, right = normalize_address(expected), normalize_address(actual)
    if address_country(left) != address_country(right):
        return False
    return bool(region_key(left.get('administrative_area')) and
                region_key(left.get('administrative_area')) == region_key(right.get('administrative_area')))


def region_matches(expected, actual):
    left, right = normalize_address(expected), normalize_address(actual)
    if address_country(left) and address_country(left) != address_country(right):
        return False
    return region_relationship(left, right) != 'conflict'
