"""OSM-backed replacement for MapMaintenanceTool (all coordinates are WGS-84).

Requires an explicitly configured Nominatim/Photon geocoder and Overpass/Photon
POI backend. No requests are sent to community demo servers by default.
Valhalla is optional; missing routing
or public-transit coverage returns None, never a made-up journey time.
"""
from copy import deepcopy
import json
import logging
import math
import re
import time
import threading
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from .maptool import MapMaintenanceTool as _AMapMaintenanceTool

logger = logging.getLogger(__name__)

# Aliases are deliberately finite: unknown categories must not broaden to all POIs.
# Explicit OSM tags can be supplied through types="amenity=cafe|shop=bakery".
CATEGORIES = [
    (("住宅小区", "住宅", "公寓", "residential", "apartments"), ("building=apartments", "building=residential", "landuse=residential")),
    (("写字楼", "办公楼", "office"), ("building=office", "office=*")),
    (("产业园", "工业园", "工厂", "industrial", "factory"), ("landuse=industrial", "man_made=works")),
    (("咖啡馆", "咖啡店", "咖啡", "cafe", "coffee"), ("amenity=cafe",)),
    (("餐厅", "饭店", "餐饮", "中式快餐", "restaurant"), ("amenity=restaurant", "amenity=fast_food")),
    (("超市", "supermarket"), ("shop=supermarket",)),
    (("便利店", "convenience"), ("shop=convenience",)),
    (("菜市场", "市场", "market"), ("amenity=marketplace",)),
    (("药店", "pharmacy"), ("amenity=pharmacy",)),
    (("健身房", "健身中心", "健身", "gym", "fitness"), ("leisure=fitness_centre",)),
    (("游泳馆", "游泳池", "swimming pool"), ("leisure=swimming_pool",)),
    (("体育中心", "体育馆", "sports centre"), ("leisure=sports_centre",)),
    (("羽毛球", "badminton"), ("sport=badminton",)),
    (("篮球", "basketball"), ("sport=basketball",)),
    (("网球", "tennis"), ("sport=tennis",)),
    (("足球", "soccer"), ("sport=soccer",)),
    (("城市公园", "公园", "park"), ("leisure=park",)),
    (("博物馆", "museum"), ("tourism=museum",)),
    (("图书馆", "library"), ("amenity=library",)),
    (("电影院", "cinema"), ("amenity=cinema",)),
    (("商场", "购物中心", "mall"), ("shop=mall",)),
    (("大学", "university"), ("amenity=university",)),
    (("学校", "school"), ("amenity=school",)),
    (("幼儿园", "kindergarten"), ("amenity=kindergarten",)),
    (("医院", "hospital"), ("amenity=hospital",)),
    (("诊所", "clinic"), ("amenity=clinic",)),
    (("酒店", "hotel"), ("tourism=hotel",)),
    (("银行", "bank"), ("amenity=bank",)),
    (("机场", "airport"), ("aeroway=aerodrome",)),
    (("火车站", "railway station"), ("railway=station",)),
    (("地铁站", "subway station"), ("station=subway",)),
    (("景点", "attraction"), ("tourism=attraction",)),
]


class MapServiceError(RuntimeError):
    """Sanitized service error: never includes a URL or response body."""


def _coordinates(value):
    lon, lat = map(float, str(value).split(","))
    if not math.isfinite(lon) or not math.isfinite(lat) or not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("Invalid WGS-84 coordinates")
    return lon, lat


def _distance(a, b):
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


class OverseasMapMaintenanceTool(_AMapMaintenanceTool):
    """Same public map methods and legacy result keys, backed by OSM services.

    The first six arguments match MapMaintenanceTool. api_key is accepted only
    for compatibility and is never sent. country_code is a required ISO alpha-2
    code. nominatim_url is a base URL; overpass_url is the interpreter endpoint;
    valhalla_url is an optional base URL. Services should cover the target region.
    """

    coordinate_system = "WGS-84"

    def __init__(self, api_key: str = "", cache_expire_seconds: int = 3600,
                 persona_address_data: Optional[List[Dict]] = None,
                 requests_per_second: float = 2.0, rate_limit_retries: int = 2,
                 *, country_code: str, overpass_url: Optional[str] = None, nominatim_url: Optional[str] = None,
                 valhalla_url: Optional[str] = None, language: str = "en",
                 user_agent: str = "LifeBench/1.0", timeout_seconds: float = 30,
                 enable_transit: bool = False, photon_url: Optional[str] = None,
                 overpass_method: str = "POST", poi_backend: str = "overpass",
                 city_aliases: Optional[Dict[str, str]] = None):
        if not re.fullmatch(r"[A-Za-z]{2}", country_code):
            raise ValueError("country_code must be an ISO alpha-2 country code")
        if not (nominatim_url or photon_url):
            raise ValueError("A geocoder (Nominatim or Photon) is required")
        if poi_backend not in {"overpass", "photon"}:
            raise ValueError("poi_backend must be overpass or photon")
        if (poi_backend == "overpass" and not overpass_url) or (poi_backend == "photon" and not photon_url):
            raise ValueError("The selected POI backend requires its endpoint")
        if nominatim_url and photon_url:
            raise ValueError("Configure exactly one geocoder")
        if overpass_method.upper() not in {"GET", "POST"}:
            raise ValueError("overpass_method must be GET or POST")
        for endpoint in (nominatim_url, photon_url, overpass_url, valhalla_url):
            if endpoint is not None and (urlparse(endpoint).scheme not in {"http", "https"} or not urlparse(endpoint).netloc):
                raise ValueError("Map service endpoints must be HTTP(S) URLs")
        if timeout_seconds <= 0 or not user_agent.strip():
            raise ValueError("A positive timeout and identifying user_agent are required")
        # Community Nominatim is unsuitable as the backend of a batch generator.
        if nominatim_url and (urlparse(nominatim_url).hostname or "").lower() == "nominatim.openstreetmap.org":
            raise ValueError("Use a self-hosted or managed Nominatim instance for batch synthesis; see its public usage policy")
        super().__init__("", cache_expire_seconds, persona_address_data,
                         requests_per_second, rate_limit_retries)
        self.country_code = country_code.lower()
        self.nominatim_url = nominatim_url.rstrip("/") if nominatim_url else None
        self.photon_url = photon_url.rstrip("/") if photon_url else None
        self.overpass_url = overpass_url
        self.overpass_method = overpass_method.upper()
        self.poi_backend = poi_backend
        self.city_aliases = dict(city_aliases or {})
        self.valhalla_url = valhalla_url.rstrip("/") if valhalla_url else None
        self.language = language
        self.user_agent = user_agent
        self.timeout_seconds = float(timeout_seconds)
        self.enable_transit = enable_transit
        self._cache_guard = threading.RLock()
        self._service_cache = {}
        for point in self.persona_address_data:
            if point.get("coordinate_system", "WGS-84") not in {"WGS-84", "WGS84"}:
                raise ValueError("persona_address_data must use WGS-84 coordinates")
        self.transport_apis = {"driving": "auto", "walking": "pedestrian", "bicycling": "bicycle"}
        if enable_transit:
            self.transport_apis["transit"] = "multimodal"

    def _cached(self, cache, key):
        with self._cache_guard:
            hit = cache.get(key)
            if hit is not None and self._is_cache_valid(hit[0]):
                return deepcopy(hit[1])
        return None

    def _save(self, cache, key, value):
        with self._cache_guard:
            cache[key] = (time.time(), deepcopy(value))
        return value

    def _fetch(self, service, method, url, **kwargs):
        cache_key = json.dumps([service, method, url, kwargs], sort_keys=True, ensure_ascii=False)
        cached = self._cached(self._service_cache, cache_key)
        if cached is not None:
            return cached
        for attempt in range(self.rate_limit_retries + 1):
            self._wait_for_request_slot()
            try:
                response = requests.request(method, url, timeout=self.timeout_seconds,
                                            headers={"User-Agent": self.user_agent, "Accept-Language": self.language,
                                                     "X-Client-Id": "lifebench"}, **kwargs)
                if response.status_code in {429, 502, 503, 504} and attempt < self.rate_limit_retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                response.raise_for_status()
                value = response.json()
                return self._save(self._service_cache, cache_key, value)
            except (requests.RequestException, ValueError) as exc:
                # Do not log requests exceptions: they can contain endpoint tokens.
                raise MapServiceError("%s request failed (%s)" % (service, type(exc).__name__)) from None
        raise MapServiceError("%s unavailable" % service)

    def _request_json(self, url, params):
        raise MapServiceError("AMap requests are disabled in the overseas tool")

    def _search(self, query, limit=20, bbox=None):
        if self.photon_url:
            return self._photon_search(query, limit, bbox)
        params = dict(q=query, format="jsonv2", addressdetails=1, namedetails=1,
                      countrycodes=self.country_code, limit=min(40, max(1, int(limit))))
        if bbox:
            south, north, west, east = bbox
            params.update(viewbox="%s,%s,%s,%s" % (west, north, east, south), bounded=1)
        data = self._fetch("Nominatim", "GET", self.nominatim_url + "/search", params=params)
        if not isinstance(data, list):
            raise MapServiceError("Invalid Nominatim search response")
        # Country filtering is also enforced on responses, not just request params.
        return [p for p in data if isinstance(p, dict) and isinstance(p.get("address"), dict)
                and str(p["address"].get("country_code", "")).lower() == self.country_code]

    def _photon_search(self, query, limit=20, bbox=None):
        params = dict(q=query, countrycode=self.country_code.upper(),
                      limit=min(40, max(1, int(limit))), lang=self.language)
        if bbox:
            params["bbox"] = "%s,%s,%s,%s" % (bbox[2], bbox[0], bbox[3], bbox[1])
        data = self._fetch("Photon", "GET", self.photon_url + "/api/", params=params)
        return self._photon_places(data)

    def _photon_places(self, data):
        if not isinstance(data, dict) or not isinstance(data.get("features"), list):
            raise MapServiceError("Invalid Photon response")
        places = []
        for feature in data["features"]:
            try:
                props = feature["properties"]
                if str(props.get("countrycode", "")).lower() != self.country_code:
                    continue
                lon, lat = feature["geometry"]["coordinates"]
                address = {k: props[k] for k in ("country", "state", "city", "county", "district", "postcode") if props.get(k)}
                address.update(country_code=self.country_code, road=props.get("street", ""),
                               house_number=props.get("housenumber", ""), suburb=props.get("locality", ""))
                kind = props.get("type", "")
                if props.get("osm_key") == "place" and props.get("osm_value") in {"city", "town", "village"}:
                    kind = props["osm_value"]
                place = dict(name=props.get("name", ""), lon=lon, lat=lat, address=address,
                             osm_type={"N": "node", "W": "way", "R": "relation"}.get(props.get("osm_type"), props.get("osm_type")),
                             osm_id=props.get("osm_id"), addresstype=kind,
                             category=props.get("osm_key", "place"), type=props.get("osm_value", ""))
                if props.get("extent"):
                    west, north, east, south = props["extent"]
                    place["boundingbox"] = [south, north, west, east]
                places.append(place)
            except (ValueError, TypeError, KeyError):
                continue
        return places

    def _photon_pois(self, selectors, bbox, limit, center=None, radius=5000, keyword=None):
        params = dict(countrycode=self.country_code.upper(), limit=limit, lang=self.language)
        if bbox:
            params["bbox"] = "%s,%s,%s,%s" % (bbox[2], bbox[0], bbox[3], bbox[1])
        if selectors:
            categories = []
            for selector in selectors:
                key, value = selector.split("=", 1)
                if not re.fullmatch(r"[\w-]+", key) or (value != "*" and not re.fullmatch(r"[\w-]+", value)):
                    raise ValueError("Tag is not indexed as a Photon category")
                categories.append("osm.%s%s" % (key, "." + value if value != "*" else ""))
            params["include"] = ",".join(categories)
        elif keyword:
            params["q"] = keyword
        else:
            return []
        endpoint = "/api/"
        if center:
            params.update(lon=center[0], lat=center[1])
            if selectors:
                endpoint = "/reverse"
                # Photon reverse does not accept countrycode/bbox; enforce
                # those constraints on the returned points below instead.
                params.pop("countrycode", None)
                params.pop("bbox", None)
                params["radius"] = max(0.001, radius / 1000)
            elif not bbox:
                # A bounding box prevents a named nearby query becoming global.
                delta_lat = radius / 111000
                delta_lon = radius / (111000 * max(0.001, math.cos(math.radians(center[1]))))
                params["bbox"] = "%s,%s,%s,%s" % (max(-180, center[0]-delta_lon), max(-90, center[1]-delta_lat), min(180, center[0]+delta_lon), min(90, center[1]+delta_lat))
        elif not bbox:
            raise ValueError("Category search requires a city")
        data = self._fetch("Photon", "GET", self.photon_url + endpoint, params=params)
        results = []
        for place in self._photon_places(data):
            try:
                candidate = self._normalize(place)
                if not self._inside(candidate["location"], bbox):
                    continue
                if center:
                    candidate["distance_m"] = round(_distance(center, _coordinates(candidate["location"])))
                    if candidate["distance_m"] > radius:
                        continue
                results.append(candidate)
            except (ValueError, TypeError, KeyError):
                continue
        return results

    def _city_bbox(self, city):
        if not city:
            return None
        for place in self._search(self.city_aliases.get(city, city), 5):
            # A shop with the same name must not define the city's search scope.
            if place.get("addresstype") not in {"city", "town", "village", "municipality", "borough", "county", "state", "administrative"}:
                continue
            try:
                south, north, west, east = map(float, place["boundingbox"])
                if all(map(math.isfinite, (south, north, west, east))) and -90 <= south < north <= 90 and -180 <= west < east <= 180:
                    return south, north, west, east
            except (ValueError, KeyError, TypeError):
                continue
        raise MapServiceError("City could not be resolved within configured country")

    @staticmethod
    def _inside(location, bbox):
        lon, lat = _coordinates(location)
        return not bbox or (bbox[0] <= lat <= bbox[1] and bbox[2] <= lon <= bbox[3])

    def _normalize(self, place, *, overpass=False):
        tags = place.get("tags", {}) if overpass else place.get("address", {})
        position = place.get("center", place) if overpass else place
        if not isinstance(tags, dict) or not isinstance(position, dict):
            raise ValueError("Invalid OSM object")
        lon, lat = _coordinates("%s,%s" % (position.get("lon"), position.get("lat")))
        location = "%.6f,%.6f" % (lon, lat)
        def field(*keys):
            return next((str(tags[k]) for k in keys if tags.get(k)), "")
        province = field("addr:state", "state", "region")
        city = field("addr:city", "city", "town", "village", "municipality")
        district = field("addr:suburb", "city_district", "district", "borough", "suburb", "county")
        street = field("addr:street", "road", "pedestrian", "footway")
        number = field("addr:housenumber", "house_number")
        country = field("addr:country", "country") or self.country_code.upper()
        name = (tags.get("name:" + self.language) or tags.get("name") or tags.get("name:en")) if overpass else place.get("name")
        category = next(("%s=%s" % (k, tags[k]) for k in ("amenity", "shop", "leisure", "tourism", "office", "building", "landuse", "railway") if tags.get(k)), "") if overpass else "%s=%s" % (place.get("category", place.get("class", "place")), place.get("type", ""))
        address = place.get("display_name") if not overpass else None
        address = address or ", ".join(x for x in (" ".join(x for x in (number, street) if x), district, city, province, country) if x)
        geocode = dict(country=country, country_code=self.country_code, province=province,
                       city=city, citycode="", district=district, street=street, number=number,
                       adcode="", postcode=field("addr:postcode", "postcode"), location=location,
                       formatted_address=address, level=place.get("addresstype", "poi"), coordinate_system="WGS-84")
        osm_type = place.get("type") if overpass else place.get("osm_type")
        osm_id = place.get("id") if overpass else place.get("osm_id", place.get("place_id"))
        return dict(id="osm:%s:%s" % (osm_type, osm_id), name=name or " ".join(x for x in (street, number) if x) or category,
                    location=location, address=address, structured_address=address, formatted_address=address,
                    country=country, country_code=self.country_code, pname=province, cityname=city,
                    adname=district, type=category, typecode=category, distance_m=0,
                    geocode=geocode, coordinate_system="WGS-84", source="openstreetmap",
                    attribution="© OpenStreetMap contributors (ODbL)",
                    position_kind="geometry_center" if overpass and "center" in place else "point")

    def amap_geocode(self, address: str, city: Optional[str] = None) -> Optional[Dict]:
        """Compatibility name; uses Nominatim and never calls AMap."""
        try:
            if not isinstance(address, str) or not address.strip():
                return None
            bbox = self._city_bbox(city)
            places = self._search(", ".join(x for x in (address, city) if x), 5, bbox)
            for place in places:
                candidate = self._normalize(place)
                if self._inside(candidate["location"], bbox):
                    return candidate["geocode"]
        except (MapServiceError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Overseas geocoding failed (%s)", type(exc).__name__)
        return None

    geocode = amap_geocode

    @staticmethod
    def _selectors(keyword, types=None, city=None):
        text = str(types or "").strip()
        if "=" in text:
            selectors = text.split("|")
            if not all(re.fullmatch(r"[a-zA-Z0-9_:]+=[a-zA-Z0-9_:*.-]+", s) for s in selectors):
                raise ValueError("Invalid OSM tag selector")
            return selectors
        if text and text.isdigit():
            raise ValueError("AMap numeric type codes are not OSM categories")
        query = str(keyword or "").strip()
        if city and query.casefold().startswith(str(city).casefold()):
            query = query[len(city):].strip(" ,，")
        result = []
        for aliases, selectors in CATEGORIES:
            for value in (text, query):
                if any(value.casefold() == a.casefold() or (
                    re.search(r"[\u4e00-\u9fff]", a) and value.endswith(a)
                    and re.fullmatch(r".+[市区县]", value[:-len(a)].strip())
                ) for a in aliases):
                    result.extend(selectors)
                    break
        if text and not result:
            raise ValueError("Unknown POI type; use OSM key=value selectors")
        return list(dict.fromkeys(result))

    def _overpass(self, keyword, selectors, bbox=None, center=None, radius=5000):
        if center:
            scope = "(around:%s,%s,%s)" % (radius, center[1], center[0])
        elif bbox:
            scope = "(%s,%s,%s,%s)" % (bbox[0], bbox[2], bbox[1], bbox[3])
        else:
            raise ValueError("Category search requires a city or coordinates")
        filters = []
        for selector in selectors:
            key, value = selector.split("=", 1)
            filters.append('[%s]' % json.dumps(key) if value == "*" else '[%s=%s]' % (json.dumps(key), json.dumps(value)))
        if not filters:
            if not keyword or not str(keyword).strip():
                return []
            # Treat user text as a literal regexp, never as Overpass code.
            filters = ['[~"^(name(:.*)?|brand)$"~%s,i]' % json.dumps(re.escape(str(keyword)), ensure_ascii=False)]
        query = '[out:json][timeout:25];area["ISO3166-1"="%s"]["boundary"="administrative"]["admin_level"="2"]->.country;(%s);out center tags 500;' % (
            self.country_code.upper(), "".join("nwr(area.country)%s%s;" % (scope, f) for f in filters))
        arguments = {"params" if self.overpass_method == "GET" else "data": {"data": query}}
        data = self._fetch("Overpass", self.overpass_method, self.overpass_url, **arguments)
        if not isinstance(data, dict) or not isinstance(data.get("elements"), list) or data.get("remark"):
            raise MapServiceError("Invalid or incomplete Overpass response")
        results = []
        seen = set()
        for element in data["elements"]:
            if not isinstance(element, dict):
                continue
            try:
                candidate = self._normalize(element, overpass=True)
                # Service-side areas restrict country; recheck all available tags.
                tagged_country = str(element.get("tags", {}).get("addr:country", ""))
                if tagged_country and len(tagged_country) == 2 and tagged_country.lower() != self.country_code:
                    continue
                if candidate["id"] in seen or not self._inside(candidate["location"], bbox):
                    continue
                if center:
                    candidate["distance_m"] = round(_distance(center, _coordinates(candidate["location"])))
                    if candidate["distance_m"] > radius:
                        continue
                seen.add(candidate["id"])
                results.append(candidate)
            except (ValueError, TypeError, KeyError):
                continue
        return results

    def search_poi_candidates(self, keyword: str, city: Optional[str] = None,
                              limit: int = 20, types: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            if not isinstance(keyword, str) or not keyword.strip():
                return []
            limit = max(1, min(int(limit), 50))
            selectors = self._selectors(keyword, types, city)
            bbox = self._city_bbox(city)
            if selectors:
                candidates = (self._photon_pois(selectors, bbox, limit) if self.poi_backend == "photon"
                              else self._overpass(keyword, selectors, bbox=bbox))
            else:
                candidates = []
                for place in self._search(", ".join(x for x in (keyword, city) if x), limit, bbox):
                    try:
                        candidate = self._normalize(place)
                        if self._inside(candidate["location"], bbox):
                            candidates.append(candidate)
                    except (ValueError, TypeError, KeyError):
                        continue
            return candidates[:limit]
        except (MapServiceError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Overseas POI search failed (%s)", type(exc).__name__)
            return []

    def search_around_candidates(self, location: str, keywords: Optional[str] = None,
                                 types: Optional[str] = None, city: Optional[str] = None,
                                 radius: int = 5000, limit: int = 20,
                                 sortrule: str = "distance") -> List[Dict[str, Any]]:
        try:
            center = _coordinates(location)
            radius = max(0, min(int(radius), 50000))
            limit = max(1, min(int(limit), 50))
            bbox = self._city_bbox(city)
            selectors = self._selectors(keywords, types, city)
            candidates = (self._photon_pois(selectors, bbox, limit, center, radius, keywords)
                          if self.poi_backend == "photon" else self._overpass(keywords, selectors, bbox, center, radius))
            # Stable tie-breaking makes seeded random selection reproducible.
            candidates.sort(key=lambda p: (p["distance_m"], p["id"]))
            return candidates[:limit]
        except (MapServiceError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Overseas nearby search failed (%s)", type(exc).__name__)
            return []

    def get_poi(self, keyword: str, city: Optional[str] = None) -> Optional[Dict]:
        candidates = self.search_poi_candidates(keyword, city=city)
        return candidates[0] if candidates else None

    def route_between_pois(self, origin_poi: Dict, dest_poi: Dict, transport: str,
                           origin_city: Optional[str] = None, dest_city: Optional[str] = None) -> Optional[Dict]:
        try:
            if not self.valhalla_url or transport not in self.transport_apis:
                return None
            points = []
            for point in (origin_poi, dest_poi):
                if point.get("coordinate_system", "WGS-84") not in {"WGS-84", "WGS84"}:
                    raise ValueError("Overseas routes require WGS-84 coordinates")
                lon, lat = _coordinates(point["location"])
                points.append(dict(lon=lon, lat=lat))
            payload = dict(locations=points, costing=self.transport_apis[transport], units="kilometers")
            data = self._fetch("Valhalla", "POST", self.valhalla_url + "/route", json=payload)
            trip = data.get("trip", {})
            if trip.get("status") != 0 or trip.get("units") != "kilometers":
                return None
            summary = trip["summary"]
            duration, distance = float(summary["time"]), float(summary["length"]) * 1000
            if not all(math.isfinite(v) and v >= 0 for v in (duration, distance)):
                return None
            return dict(duration_seconds=round(duration), distance_meters=round(distance),
                        mode=transport, source="valhalla", coordinate_system="WGS-84")
        except (MapServiceError, ValueError, TypeError, KeyError, AttributeError) as exc:
            logger.warning("Overseas route failed (%s)", type(exc).__name__)
            return None

    def get_duration_between_pois(self, origin_poi: Dict, dest_poi: Dict, transport: str,
                                  origin_city: Optional[str] = None, dest_city: Optional[str] = None) -> Optional[int]:
        route = self.route_between_pois(origin_poi, dest_poi, transport, origin_city, dest_city)
        return route["duration_seconds"] if route else None

    def process_instruction_route(self, instruction_data: Dict[str, Any]):
        result, errors = super().process_instruction_route(instruction_data)
        # The legacy method rebuilds type-1 POIs and route endpoints; restore
        # coordinate metadata that would otherwise be lost by that adapter.
        result["coordinate_system"] = "WGS-84"
        for point in result.get("success_poi_list", []):
            point["coordinate_system"] = "WGS-84"
        for leg in result.get("route_details", []):
            for endpoint in ("origin", "destination"):
                leg[endpoint]["coordinate_system"] = "WGS-84"
        return result, errors

    def clear_expired_cache(self) -> None:
        with self._cache_guard:
            super().clear_expired_cache()
            self._service_cache = {k: v for k, v in self._service_cache.items() if self._is_cache_valid(v[0])}


# Allows changing only the module in existing MapMaintenanceTool imports.
OSMMapMaintenanceTool = OverseasMapMaintenanceTool
MapMaintenanceTool = OverseasMapMaintenanceTool
