"""Explicit map construction and destination-aware routing for international runs."""
from copy import deepcopy
from threading import RLock
from .locale_context import address_country, current_locale, map_settings, target_address
from .maptool import MapMaintenanceTool
from .overseas_maptool import OverseasMapMaintenanceTool, wait_for_map_host


class _InternationalAMapBackend(MapMaintenanceTool):
    def _wait_for_request_slot(self):
        wait_for_map_host("restapi.amap.com", self._request_interval)


class _CountryCity(str):
    """Country-qualified city that remains compatible with legacy string APIs."""
    def __new__(cls, value, country_code):
        instance = super().__new__(cls, value or "")
        instance.country_code = country_code
        return instance

    def strip(self, chars=None):
        return _CountryCity(super().strip(chars), self.country_code)

    def __reduce__(self):
        return _CountryCity, (str(self), self.country_code)


_OSM_CATEGORIES = {
    "cafe": "meal", "restaurant": "meal", "fast_food": "meal", "pub": "meal",
    "supermarket": "shopping", "convenience": "shopping", "mall": "shopping",
    "pharmacy": "medical", "hospital": "medical", "clinic": "medical",
    "school": "education", "university": "education", "kindergarten": "education",
    "library": "education", "fitness_centre": "fitness", "sports_centre": "fitness",
    "swimming_pool": "fitness", "park": "leisure", "museum": "leisure", "cinema": "leisure",
    "apartments": "home", "residential": "home", "office": "work", "industrial": "work",
}


def _convert_location(location, reverse=False):
    from src.lifebench.event.simulation.geolocation.coordinates import gcj02_to_wgs84
    lon, lat = map(float, str(location).split(","))
    converted = gcj02_to_wgs84(lon, lat)
    if reverse:
        converted = (2 * lon - converted[0], 2 * lat - converted[1])
    return "%.6f,%.6f" % converted


def _canonical(poi, code, source):
    if not poi:
        return poi
    result = deepcopy(poi)
    if source == "amap" and result.get("location"):
        result["provider_location"] = result["location"]
        result["provider_coordinate_system"] = "GCJ-02"
        result["location"] = _convert_location(result["location"])
    result.update(country_code=code, coordinate_system="WGS-84", source=source)
    if source == "openstreetmap":
        tag = str(result.get("type") or "")
        result["lifebench_category"] = _OSM_CATEGORIES.get(tag.split("=")[-1], "work" if tag.startswith("office=") else "other")
    if isinstance(result.get("geocode"), dict):
        result["geocode"] = _canonical(result["geocode"], code, source)
        result["geocode"]["location"] = result.get("location", result["geocode"].get("location", ""))
    return result


class InternationalMapTool(MapMaintenanceTool):
    """Legacy interface with immutable, request-scoped destination countries.

    All international-mode outputs use WGS-84; AMap conversion happens at the
    adapter boundary. Backend country codes are never mutated between requests.
    """
    coordinate_system = "WGS-84"
    requires_api_key = False

    def __init__(self, api_key="", persona=None, **kwargs):
        super().__init__(api_key, **kwargs)
        settings = map_settings()
        self.policy, self.options = settings["policy"], settings["services"]
        self.persona = persona
        self._backends, self._backend_lock = {}, RLock()
        if any(p.get("coordinate_system") not in (None, "", "WGS-84", "WGS84") for p in self.persona_address_data):
            raise ValueError("International synthesis requires WGS-84 location assets")
        for point in self.persona_address_data:
            code = address_country(point) or address_country(point.get("geocode") or {})
            if not code:
                raise ValueError("International persona locations require country_code")
            point["city"] = _CountryCity(point.get("city") or "", code)

    def _country(self, city=None, point=None):
        if getattr(city, "country_code", None):
            return city.country_code
        for address in (city, point, (point or {}).get("geocode") if isinstance(point, dict) else None, target_address()):
            code = address_country(address)
            if code:
                return code
        if isinstance(self.persona, dict):
            code = address_country(self.persona.get("home_address") or {})
            if code:
                return code
        locale = current_locale()
        if locale:
            return locale.country_code
        code = map_settings()["locale_defaults"].get("country_code")
        if code:
            return str(code).upper()
        raise ValueError("Map query requires an explicit residence or destination country")

    def _backend(self, code):
        source = "amap" if self.policy == "auto" and code == "CN" else "openstreetmap"
        with self._backend_lock:
            if (source, code) not in self._backends:
                if source == "amap":
                    if not self.api_key:
                        raise ValueError("AMap key required for a CN destination in auto mode")
                    backend = _InternationalAMapBackend(self.api_key)
                else:
                    backend = OverseasMapMaintenanceTool(country_code=code, **self.options)
                self._backends[source, code] = backend
            return self._backends[source, code], source

    @staticmethod
    def _city(city):
        return city.get("city") if isinstance(city, dict) else city

    def amap_geocode(self, address, city=None):
        code = self._country(city)
        backend, source = self._backend(code)
        return _canonical(backend.amap_geocode(address, self._city(city)), code, source)

    geocode = amap_geocode

    def search_poi_candidates(self, keyword, city=None, limit=20, types=None):
        code = self._country(city)
        backend, source = self._backend(code)
        if source == "openstreetmap" and types and str(types).isdigit():
            types = None  # Semantic keyword remains mandatory on the OSM side.
        return [_canonical(p, code, source) for p in backend.search_poi_candidates(keyword, self._city(city), limit, types)]

    def get_poi(self, keyword, city=None):
        items = self.search_poi_candidates(keyword, city=city)
        return items[0] if items else None

    def search_around_candidates(self, location, keywords=None, types=None, city=None,
                                 radius=5000, limit=20, sortrule="distance"):
        code = self._country(city)
        backend, source = self._backend(code)
        if source == "amap":
            location = _convert_location(location, reverse=True)
        elif types and str(types).isdigit():
            types = None
        return [_canonical(p, code, source) for p in backend.search_around_candidates(
            location, keywords, types, self._city(city), radius, limit, sortrule)]

    def route_between_pois(self, origin_poi, dest_poi, transport, origin_city=None, dest_city=None):
        code = self._country(origin_city, origin_poi)
        destination_country = self._country(dest_city, dest_poi)
        if code == destination_country and origin_poi.get("location") == dest_poi.get("location"):
            return dict(duration_seconds=0, distance_meters=0, mode=transport,
                        source="same_location", coordinate_system="WGS-84")
        if destination_country != code:
            with self._backend_lock:
                if ("cross", code) not in self._backends:
                    self._backends["cross", code] = OverseasMapMaintenanceTool(country_code=code, **self.options)
                backend, source = self._backends["cross", code], "openstreetmap"
        else:
            backend, source = self._backend(code)
        points = [deepcopy(origin_poi), deepcopy(dest_poi)]
        if source == "amap":
            for point in points:
                point["location"] = _convert_location(point["location"], reverse=True)
                point["coordinate_system"] = "GCJ-02"
        route = backend.route_between_pois(points[0], points[1], transport, self._city(origin_city), self._city(dest_city))
        if route:
            route.update(coordinate_system="WGS-84", map_provider=source)
            route.setdefault("source", source)
        return route

    def get_duration_between_pois(self, origin_poi, dest_poi, transport, origin_city=None, dest_city=None):
        route = self.route_between_pois(origin_poi, dest_poi, transport, origin_city, dest_city)
        return route["duration_seconds"] if route else None

    def process_instruction_route(self, instruction_data):
        data = deepcopy(instruction_data)
        for instruction in data.get("instruction", []):
            code = address_country(instruction)
            if code:
                instruction["city"] = _CountryCity(instruction.get("city") or "", code)
                if str(instruction.get("type")) == "1":
                    key = instruction.get("location") or instruction.get("name")
                    point = self._persona_address_index.get(key) or {}
                    known = address_country(point)
                    if known and known != code:
                        raise ValueError("Requested anchor belongs to another country")
        result, errors = super().process_instruction_route(data)
        points = result.get("success_poi_list", [])
        for point in points:
            instruction = data["instruction"][point["instruction_index"]]
            code = address_country(point) or address_country(instruction) or self._country(point.get("city"))
            point.update(country_code=code, coordinate_system="WGS-84")
        by_index = {p["instruction_index"]: p for p in points}
        for leg in result.get("route_details", []):
            for role in ("origin", "destination"):
                point = by_index.get(leg[role].get("instruction_index"), {})
                leg[role].update(country_code=point.get("country_code", ""), coordinate_system="WGS-84")
        result["coordinate_system"] = "WGS-84"
        if len(points) > 1 and len(result.get("route_details", [])) < len(points) - 1:
            raise RuntimeError("International instruction route has unverified segments")
        return result, errors


def create_map_tool(api_key="", persona=None, **kwargs):
    if map_settings()["policy"] == "amap":
        code = address_country((persona or {}).get("home_address") or {}) if isinstance(persona, dict) else ""
        if code and code != "CN":
            raise ValueError("Foreign residence requires --map-tool overseas or auto")
        return MapMaintenanceTool(api_key, **kwargs)
    return InternationalMapTool(api_key, persona=persona, **kwargs)
