import random
import threading

import requests
import time
from typing import List, Dict, Optional, Tuple, Union, Any
from xml.etree import ElementTree


class MapMaintenanceTool:
    """地图维护工具类，支持POI查询、地理编码、跨城市路线查询，确保所有函数出错时有明确输出"""

    def __init__(self, api_key: str, cache_expire_seconds: int = 3600):
        self.api_key = api_key
        self.cache_expire_seconds = cache_expire_seconds  # 缓存有效期
        self.transport_apis = {
            "driving": "https://restapi.amap.com/v3/direction/driving",
            "walking": "https://restapi.amap.com/v3/direction/walking",
            "transit": "https://restapi.amap.com/v3/direction/transit/integrated",
            "bicycling": "https://restapi.amap.com/v4/direction/bicycling"
        }
        # 初始化缓存
        self.poi_cache: Dict[str, Tuple[float, Dict]] = {}
        self.duration_cache: Dict[str, Tuple[float, int]] = {}
        self.geocode_cache: Dict[str, Tuple[float, Dict]] = {}
        # 新增：全局锁（保护所有共享状态操作）
        self._lock = threading.Lock()
        # 线程安全的随机数实例（替代全局random）
        self._random = random.Random()
        self._random.seed(time.time())

    def _is_cache_valid(self, cache_time: float) -> bool:
        """检查缓存是否有效，出错时返回False"""
        try:
            return time.time() - cache_time < self.cache_expire_seconds
        except Exception as e:
            print(f"缓存有效性检查失败: {str(e)}")
            return False

    def amap_geocode(self, address: str, city: Optional[str] = None) -> Optional[Dict]:
        """
        高德地图地理编码API封装，补充结构化地址信息
        Args:
            address: 待编码地址（可是POI名称或模糊地址）
            city: 指定查询城市（中文/全拼/citycode/adcode）
        Returns:
            地理编码字典（包含省份、城市、区县、街道、门牌、坐标等），失败返回None
        """
        try:
            # 验证参数
            if not address or not isinstance(address, str):
                print(f"地理编码地址无效: {address}")
                return None

            # 缓存键（地址+城市）
            cache_key = f"{address}_{city or '全国'}"
            if cache_key in self.geocode_cache:
                cache_time, geocode_data = self.geocode_cache[cache_key]
                if self._is_cache_valid(cache_time):
                    print(f"地理编码缓存命中: {address}@{city}")
                    return geocode_data

            # 构建请求
            base_url = "https://restapi.amap.com/v3/geocode/geo"
            params = {
                "key": self.api_key,
                "address": address,
                "output": "JSON",
                "city": city
            }
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()

            # 解析结果
            if result.get("status") != "1" or int(result.get("count", 0)) == 0:
                print(f"地理编码未找到结果: {address}@{city}（错误信息：{result.get('info', '未知')}）")
                return None

            # 提取第一个地理编码结果（最匹配）
            geocode_info = result["geocodes"][0]
            # 结构化返回数据（统一字段格式，避免空值）
            structured_data = {
                "country": geocode_info.get("country", ""),
                "province": geocode_info.get("province", ""),
                "city": geocode_info.get("city", ""),
                "citycode": geocode_info.get("citycode", ""),
                "district": geocode_info.get("district", ""),
                "street": geocode_info.get("street", ""),
                "number": geocode_info.get("number", ""),
                "adcode": geocode_info.get("adcode", ""),
                "location": geocode_info.get("location", ""),
                "level": geocode_info.get("level", ""),
                "formatted_address": f"{geocode_info.get('province', '')}{geocode_info.get('city', '')}{geocode_info.get('district', '')}{geocode_info.get('street', '')}{geocode_info.get('number', '')}"
            }

            # 缓存结果
            self.geocode_cache[cache_key] = (time.time(), structured_data)
            return structured_data

        except Exception as e:
            print(f"地理编码执行失败({address}@{city}): {str(e)}")
            return None

    def get_poi(self, keyword: str, city: Optional[str] = None) -> Optional[Dict]:
        """
        获取POI，融合地理编码补充结构化地址信息，出错时返回None
        增强点：POI结果中添加geocode字段，包含完整的行政区域和地址信息
        """
        try:
            cache_key = f"{keyword}_{city or '全国'}"
            # 检查缓存（缓存中已包含地理编码信息）
            if cache_key in self.poi_cache:
                cache_time, poi_data = self.poi_cache[cache_key]
                if self._is_cache_valid(cache_time):
                    print(f"POI缓存命中: {keyword}@{city}")
                    return poi_data

            # 调用POI API
            response = requests.get(
                url="https://restapi.amap.com/v3/place/text",
                params={
                    "key": self.api_key,
                    "keywords": keyword,
                    "city": city,
                    "offset": 1,
                    "page": 1,
                    "extensions": "base"
                },
                timeout=10
            )
            response.raise_for_status()
            result = response.json()

            # 解析POI基础信息
            if result.get("status") != "1" or int(result.get("count", 0)) == 0:
                print(f"未找到POI: {keyword}@{city}")
                return None

            first_poi = result["pois"][0]
            poi_location = first_poi.get("location", "")

            # 调用地理编码补充结构化地址（优先用POI的address字段，无则用keyword）
            poi_address = first_poi.get("address", keyword)
            geocode_data = self.amap_geocode(address=poi_address, city=city)

            # 融合POI和地理编码信息（geocode字段存储完整地理编码数据）
            enhanced_poi = {
                **first_poi,  # 保留原有POI字段
                "geocode": geocode_data or {},  # 地理编码补充信息
                "structured_address": geocode_data["formatted_address"] if geocode_data else poi_address  # 统一结构化地址字段
            }

            # 处理经纬度优先级：地理编码的location更精准，优先使用
            if geocode_data and geocode_data["location"]:
                enhanced_poi["location"] = geocode_data["location"]
            elif not poi_location:
                print(f"POI缺少经纬度: {keyword}@{city}")
                return None

            # 缓存增强后的POI数据
            self.poi_cache[cache_key] = (time.time(), enhanced_poi)
            return enhanced_poi

        except Exception as e:
            print(f"get_poi执行失败({keyword}@{city}): {str(e)}")
            return None

    def get_duration_between_pois(self, origin_poi: Dict, dest_poi: Dict, transport: str,
                                  origin_city: Optional[str] = None, dest_city: Optional[str] = None) -> Optional[int]:
        """计算通行时间，出错时返回None（逻辑不变，兼容增强后的POI格式）"""
        try:
            # 提取经纬度（兼容原有POI格式和增强格式）
            origin_loc = origin_poi.get("location", "").strip()
            dest_loc = dest_poi.get("location", "").strip()

            if len(origin_loc.split(',')) != 2 or len(dest_loc.split(',')) != 2:
                print("经纬度格式错误(需'X,Y')")
                return None

            # 检查交通方式
            if transport not in self.transport_apis:
                print(f"不支持的交通方式: {transport}")
                return None

            # 缓存检查
            cache_key = f"{origin_loc}_{dest_loc}_{transport}_{origin_city or '未知'}_{dest_city or '未知'}"
            if cache_key in self.duration_cache:
                cache_time, duration = self.duration_cache[cache_key]
                if self._is_cache_valid(cache_time):
                    print(f"耗时缓存命中: {origin_city}->{dest_city}({transport})")
                    return duration

            # 调用API
            url = self.transport_apis[transport]
            params = {"key": self.api_key, "origin": origin_loc, "destination": dest_loc}
            if transport == "transit":
                params["city"] = origin_city or dest_city or "010"
                params["cityd"] = dest_city or origin_city or "010"
                params["nightflag"] = 0

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()

            # 解析结果
            duration = None
            if transport in ["driving", "walking"]:
                if result.get("status") == "1" and "route" in result and result["route"]["paths"]:
                    duration = int(result["route"]["paths"][0]["duration"])
            elif transport == "transit":
                if result.get("status") == "1" and "route" in result and result["route"]["transits"]:
                    duration = int(result["route"]["transits"][0]["duration"])
            elif transport == "bicycling":
                if result.get("code") == "0" and "data" in result and result["data"]["paths"]:
                    duration = int(result["data"]["paths"][0]["duration"])

            if duration is None:
                print(f"未获取到耗时: {origin_city}->{dest_city}({transport})")
                return None

            self.duration_cache[cache_key] = (time.time(), duration)
            return duration

        except Exception as e:
            print(f"get_duration_between_pois执行失败: {str(e)}")
            return None

    def process_route(self, keywords: List[str], cities: List[Optional[str]], transports: List[str]) -> Tuple[
        List[Dict], List[Optional[int]]]:
        """主函数：处理完整路线，返回增强后的POI列表和通行时间列表，出错返回([], [])"""
        transports = transports[0:len(keywords) - 1]
        # 确保输入参数可迭代
        try:
            keywords = list(keywords) if keywords else []
            cities = list(cities) if cities else []
            transports = list(transports) if transports else []
        except Exception as e:
            print(f"输入参数转换失败: {str(e)}")
            return [], []

        try:
            # 输入校验
            if len(keywords) < 2:
                print(f"关键词数量不足（需≥2，实际{len(keywords)}）")
                return [], []
            if len(cities) != len(keywords):
                print(f"城市数量不匹配（关键词{len(keywords)}个，城市{len(cities)}个）")
                return [], []
            if len(transports) != len(keywords) - 1:
                print(f"交通方式数量不匹配（需{len(keywords) - 1}个，实际{len(transports)}个）")
                return [], []

            # 获取增强后的POI列表（含地理编码信息）
            poi_list = []
            for i, (keyword, city) in enumerate(zip(keywords, cities)):
                poi = self.get_poi(keyword, city)
                if not poi:
                    print(f"第{i + 1}个POI获取失败，终止路线处理")
                    return [], []
                poi_list.append(poi)

            # 计算通行时间列表
            duration_list = []
            for i in range(len(poi_list) - 1):
                duration = self.get_duration_between_pois(
                    origin_poi=poi_list[i],
                    dest_poi=poi_list[i + 1],
                    transport=transports[i],
                    origin_city=cities[i],
                    dest_city=cities[i + 1]
                )
                if duration is None:
                    print(f"第{i + 1}段耗时获取失败，终止路线处理")
                    return [], []
                duration_list.append(duration)
                print(f"路段{i + 1}计算完成: {duration // 60}分钟（{poi_list[i]['name']} -> {poi_list[i + 1]['name']}）")

            return poi_list, duration_list

        except Exception as e:
            print(f"process_route整体执行失败: {str(e)}")
            return [], []

        # ------------------------------
        # 新增：process_route_bycode 方法
        # ------------------------------
    def process_route_bycode(self, keywords: List[str], cities: List[Optional[str]], transports: List[str]) -> Tuple[List[Optional[Dict]], List[Optional[int]]]:
            """
            直接通过关键词+城市获取地理编码，计算路线通行时间（跳过POI查询）
            Args:
                keywords: 地址关键词列表（如["北京大学", "天安门广场"]）
                cities: 对应城市列表（与关键词数量一致，支持中文/全拼/citycode/adcode）
                transports: 交通方式列表（与路段数量一致，即关键词数量-1）
            Returns:
                Tuple[地理编码列表, 通行时间列表]
                - 地理编码列表：每个元素是对应关键词的地理编码完整数据（失败为None）
                - 通行时间列表：每个元素是对应路段的通行时间（秒），失败为None
            """
            # 截取有效交通方式（避免数量过多）
            transports = transports[0:len(keywords) - 1]

            # 确保输入参数可迭代（容错处理）
            try:
                keywords = list(keywords) if keywords else []
                cities = list(cities) if cities else []
                transports = list(transports) if transports else []
            except Exception as e:
                print(f"输入参数转换失败: {str(e)}")
                return [], []

            try:
                # 1. 输入参数校验（与原有process_route保持一致）
                if len(keywords) < 2:
                    print(f"关键词数量不足（需≥2，实际{len(keywords)}）")
                    return [], []
                if len(cities) != len(keywords):
                    print(f"城市数量不匹配（关键词{len(keywords)}个，城市{len(cities)}个）")
                    return [], []
                if len(transports) != len(keywords) - 1:
                    print(f"交通方式数量不匹配（需{len(keywords) - 1}个，实际{len(transports)}个）")
                    return [], []

                # 2. 批量获取地理编码（核心步骤：跳过POI，直接编码关键词）
                geocode_list = []
                for i, (keyword, city) in enumerate(zip(keywords, cities)):
                    print(f"正在获取第{i + 1}个地址的地理编码: {keyword}@{city}")
                    geocode_data = self.amap_geocode(address=keyword, city=city)

                    # 校验地理编码是否有效（重点检查经纬度）
                    if not geocode_data:
                        print(f"第{i + 1}个地址地理编码获取失败，终止路线处理")
                        return geocode_list, []  # 返回已获取的地理编码，便于排查
                    geocode_list.append(geocode_data)
                # 3. 计算各路段通行时间（复用原有get_duration_between_pois方法）
                duration_list = []
                for i in range(len(geocode_list) - 1):
                    origin_geocode = geocode_list[i]
                    dest_geocode = geocode_list[i + 1]
                    transport = transports[i]
                    origin_city = cities[i]
                    dest_city = cities[i + 1]

                    print(f"\n正在计算路段{i + 1}耗时: {keywords[i]} -> {keywords[i + 1]}（{transport}）")
                    duration = self.get_duration_between_pois(
                        origin_poi=origin_geocode,  # 直接传入地理编码数据（已包含location）
                        dest_poi=dest_geocode,
                        transport=transport,
                        origin_city=origin_city,
                        dest_city=dest_city
                    )

                    if duration is None:
                        print(f"第{i + 1}段耗时获取失败，终止路线处理")
                        return geocode_list, duration_list  # 返回已计算的结果

                    duration_list.append(duration)
                    print(f"路段{i + 1}计算完成: {duration // 60}分钟（{duration}秒）")

                # 4. 成功返回完整结果
                print("\n=== 路线计算全部完成 ===")
                return geocode_list, duration_list

            except Exception as e:
                print(f"process_route_bycode整体执行失败: {str(e)}")
                return [], []  # 兜底返回空列表

    def clear_expired_cache(self) -> None:
        """清理所有过期缓存（POI、耗时、地理编码）"""
        try:
            current_time = time.time()
            # 清理POI缓存
            self.poi_cache = {k: (t, d) for k, (t, d) in self.poi_cache.items() if
                              current_time - t < self.cache_expire_seconds}
            # 清理耗时缓存
            self.duration_cache = {k: (t, d) for k, (t, d) in self.duration_cache.items() if
                                   current_time - t < self.cache_expire_seconds}
            # 清理地理编码缓存
            self.geocode_cache = {k: (t, d) for k, (t, d) in self.geocode_cache.items() if
                                  current_time - t < self.cache_expire_seconds}
            print(
                f"缓存清理完成（POI: {len(self.poi_cache)}, 耗时: {len(self.duration_cache)}, 地理编码: {len(self.geocode_cache)}）")
        except Exception as e:
            print(f"缓存清理失败: {str(e)}")
    # ------------------------------
    # 优化：解析用户指令，支持降级机制和失败不终止
    # ------------------------------
    def search_around_poi_random(self,
                                 location: str,
                                 keywords: Optional[str] = None,
                                 types: Optional[str] = None,
                                 city: Optional[str] = None,
                                 radius: int = 5000,
                                 sortrule: str = "distance",
                                 offset: int = 20,
                                 extensions: str = "base") -> Optional[Dict]:
        try:
            if not location or not isinstance(location, str):
                print(f"周边搜索失败：中心点坐标无效（{location}）")
                return None
            lon_lat = location.split(",")
            if len(lon_lat) != 2:
                print(f"周边搜索失败：坐标格式错误（需'经度,纬度'，实际{location}）")
                return None
            try:
                lon = float(lon_lat[0])
                lat = float(lon_lat[1])
                if len(lon_lat[0].split(".")[-1]) > 6 or len(lon_lat[1].split(".")[-1]) > 6:
                    print(f"周边搜索失败：经纬度小数点后超过6位（{location}）")
                    return None
            except ValueError:
                print(f"周边搜索失败：经纬度非数字（{location}）")
                return None
            if not isinstance(radius, int) or radius < 0:
                print(f"周边搜索失败：半径无效（{radius}，需≥0的整数）")
                return None
            radius = min(radius, 50000)
            if sortrule not in ["distance", "weight"]:
                print(f"周边搜索失败：排序规则无效（{sortrule}，仅支持distance/weight）")
                return None
            if not isinstance(offset, int) or offset < 10 or offset > 50:
                offset = 20
                print(f"周边搜索警告：每页记录数无效，自动调整为{offset}（需10-50的整数）")
            if extensions not in ["base", "all"]:
                print(f"周边搜索失败：返回结果控制无效（{extensions}，仅支持base/all）")
                return None
            base_url = "https://restapi.amap.com/v3/place/around"
            params = {
                "key": self.api_key,
                "location": location,
                "keywords": keywords,
                "types": types,
                "city": city,
                "radius": radius,
                "sortrule": sortrule,
                "page": 1,
                "offset": offset,
                "extensions": extensions,
                "output": "JSON"
            }
            params = {k: v for k, v in params.items() if v is not None}
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()
            if result.get("status") != "1":
                error_info = result.get("info", "未知错误")
                error_code = result.get("infocode", "无错误码")
                print(f"周边搜索API返回失败：{error_info}（错误码：{error_code}）")
                return None
            poi_list = result.get("pois", [])
            total_count = len(poi_list)
            if total_count == 0:
                print(f"周边搜索失败：未找到符合条件的POI")
                return None
            top10_poi = poi_list[:10]
            print(f"周边搜索成功：找到{total_count}个POI，从排名前十中随机选择一个")
            enhanced_top10 = []
            for poi in top10_poi:
                poi_address = poi.get("address", poi.get("name", ""))
                poi_city = poi.get("city", city)
                geocode_data = self.amap_geocode(address=poi_address, city=poi_city)
                enhanced_poi = {
                    **poi,
                    "geocode": geocode_data or {},
                    "structured_address": geocode_data["formatted_address"] if geocode_data else poi_address,
                    "distance_m": int(poi.get("distance", 0))
                }
                # 优先使用地理编码的location
                if geocode_data and geocode_data["location"]:
                    enhanced_poi["location"] = geocode_data["location"]
                elif not poi.get("location"):
                    print(f"周边POI缺少经纬度：{poi.get('name')}")
                    continue
                enhanced_top10.append(enhanced_poi)
            if not enhanced_top10:
                print(f"周边POI均缺少有效经纬度")
                return None
            random_poi = random.choice(enhanced_top10)
            print(f"随机选中POI：{random_poi['name']}（距离：{random_poi['distance_m']}米）")
            return random_poi
        except requests.exceptions.RequestException as e:
            print(f"周边搜索网络错误：{str(e)}")
        except Exception as e:
            print(f"周边搜索执行失败：{str(e)}")
        return None

    # ------------------------------
    # 最终优化：类型1指令通过POI获取精准Location，地理编码降级
    # ------------------------------
    def process_instruction_route(self, instruction_data: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        with self._lock:
            """
            解析用户POI查询指令，生成POI列表并计算通行时间（最终优化版）
            核心优化：
            1. 类型1（画像地址）：优先通过POI查询获取精准Location，地理编码仅作为降级
            2. 类型3（附近POI）：失败降级为类型2（baseKeyword+poiType）
            3. 单个指令失败不终止，记录失败信息
            4. 通行时间计算仅使用有效经纬度，确保准确性
            Args:
                instruction_data: 用户指令字典（格式不变）
            Returns:
                Tuple[结构化结果, 错误汇总信息]
            """
            # 初始化结果容器
            success_poi_list = []  # 成功执行的POI数据（均含有效location）
            failed_instructions = []  # 失败的指令记录
            route_details = []  # 成功的路段详细信息
            total_duration_seconds = 0
            actual_cities = set()

            try:
                # 1. 解析输入参数
                instructions = instruction_data.get("instruction", [])
                input_cities = instruction_data.get("city", [])
                transports = instruction_data.get("transport", [])

                # 2. 基础参数校验（仅记录，不终止）
                global_errors = []
                if not instructions:
                    global_errors.append("instruction数组不能为空")
                if len(transports) != len(instructions) - 1:
                    global_errors.append(f"transport数组长度需为instruction长度-1（实际{len(transports)}个）")
                for idx, transport in enumerate(transports):
                    if transport not in self.transport_apis:
                        global_errors.append(
                            f"第{idx + 1}个交通方式{transport}不支持（仅支持driving, walking, transit, bicycling）")

                # 3. 处理每个指令（核心优化：类型1优先POI）
                for idx, instr in enumerate(instructions):
                    instr_type = instr.get("type")
                    city = instr.get("city") or (input_cities[idx] if idx < len(input_cities) else None)
                    instr_desc = f"第{idx + 1}个指令（类型{instr_type}）"
                    try:
                        # 3.1 类型1：画像地址（直接进行地理编码搜索）
                        if instr_type == "1":
                            location = instr.get("location", "").strip()
                            c = instr.get("city", city).strip()
                            if not location:
                                raise ValueError("缺少location字段")
                            print(f"\n{instr_desc}：画像地址处理 -> 直接地理编码搜索：{location}@{city}")

                            # 直接调用地理编码API
                            geocode_data = self.amap_geocode(address=location, city=c)
                            if not geocode_data or not geocode_data.get("location"):
                                raise ValueError("地理编码失败，无有效Location")
                                
                            # 地理编码成功，包装为POI格式（统一数据结构）
                            enhanced_geocode = {
                                "name": location,
                                "location": geocode_data["location"],
                                "structured_address": geocode_data["formatted_address"],
                                "geocode": geocode_data,
                                "instruction_type": "1",
                                "original_location": location,
                                "is_poi_fallback": False,  # 直接使用地理编码，无降级
                                "instruction_index": idx
                            }
                            success_poi_list.append(enhanced_geocode)
                            print(f"{instr_desc}：地理编码成功，Location：{geocode_data['location']}")

                            # 添加城市信息
                            current_poi = success_poi_list[-1]
                            city_val = city or current_poi.get("geocode", {}).get("city") or current_poi.get("city")
                            if city_val:
                                actual_cities.add(city_val)

                        # 3.2 类型2：直接POI搜索（逻辑不变，确保Location有效）
                        elif instr_type == "2":
                            keyword = instr.get("keyword", "").strip()
                            if not keyword:
                                raise ValueError("缺少keyword字段")
                            print(f"\n{instr_desc}：直接POI搜索 -> {keyword}@{city}")
                            poi_data = self.get_poi(keyword=keyword, city=city)
                            if not poi_data or not poi_data.get("location"):
                                raise ValueError("POI搜索失败或无有效Location")
                            poi_data["instruction_type"] = "2"
                            poi_data["original_keyword"] = keyword
                            poi_data["instruction_index"] = idx
                            success_poi_list.append(poi_data)
                            # 添加城市信息
                            city_val = city or poi_data.get("geocode", {}).get("city") or poi_data.get("city")
                            if city_val:
                                actual_cities.add(city_val)

                        # 3.3 类型3：附近POI搜索（降级逻辑不变，确保Location有效）
                        elif instr_type == "3":
                            base_keyword = instr.get("baseKeyword", "").strip()
                            poi_type = instr.get("poiType", "").strip()
                            keyw = instr.get("Keyword", "").strip()
                            if not base_keyword or not poi_type:
                                raise ValueError("缺少baseKeyword或poiType字段")
                            print(f"\n{instr_desc}：附近POI搜索 -> 基础地址={base_keyword}，POI类型={poi_type}@{city}")

                            # 第一步：尝试周边POI搜索
                            base_geocode = self.amap_geocode(address=base_keyword, city=city)
                            around_poi = None
                            if base_geocode and base_geocode.get("location"):
                                around_poi = self.search_around_poi_random(
                                    location=base_geocode["location"],
                                    types=poi_type,
                                    city=city,
                                    radius=3000
                                )

                            if around_poi and around_poi.get("location"):
                                # 周边POI成功
                                around_poi["instruction_type"] = "3"
                                around_poi["original_baseKeyword"] = base_keyword
                                around_poi["original_poiType"] = poi_type
                                around_poi["base_location"] = base_geocode["location"]
                                around_poi["is_fallback"] = False
                                around_poi["instruction_index"] = idx
                                success_poi_list.append(around_poi)
                                print(f"{instr_desc}：周边POI成功，Location：{around_poi['location']}")
                            else:
                                # 降级为类型2：拼接关键词搜索
                                fallback_keyword = f"{keyw}"
                                print(f"{instr_desc}：周边POI失败，降级为直接POI搜索（关键词：{fallback_keyword}）")
                                poi_data = self.get_poi(keyword=fallback_keyword, city=city)
                                if not poi_data or not poi_data.get("location"):
                                    raise ValueError(f"降级搜索失败，无有效Location")
                                poi_data["instruction_type"] = "3"
                                poi_data["original_baseKeyword"] = base_keyword
                                poi_data["original_poiType"] = poi_type
                                poi_data["fallback_keyword"] = fallback_keyword
                                poi_data["is_fallback"] = True
                                poi_data["instruction_index"] = idx
                                success_poi_list.append(poi_data)
                                print(f"{instr_desc}：降级POI成功，Location：{poi_data['location']}")

                            # 添加城市信息
                            current_poi = success_poi_list[-1]
                            city_val = city or current_poi.get("geocode", {}).get("city") or current_poi.get("city")
                            if city_val:
                                actual_cities.add(city_val)


                        # 未知类型
                        else:
                            raise ValueError(f"类型无效（{instr_type}），仅支持1/2/3")
                        #print(success_poi_list)
                        # 最终校验：确保添加的POI有有效Location
                        current_poi = success_poi_list[-1]
                        if not current_poi.get("location") or len(current_poi["location"].split(',')) != 2:
                            raise ValueError(f"Location无效：{current_poi.get('location')}")

                    except Exception as e:
                        # 记录失败指令
                        failed_instructions.append({
                            "instruction_index": idx,
                            "type": instr_type,
                            "original_instruction": instr,
                            "error": str(e),
                            "description": instr_desc
                        })
                        print(f"{instr_desc}执行失败：{str(e)}（已记录，继续处理后续指令）")
                        continue

                # 4. 计算通行时间（仅对连续成功且有有效Location的POI）
                print(f"\n=== 开始计算通行时间（成功获取{len(success_poi_list)}个有效地址）===")
                if len(success_poi_list) >= 2:
                    # 遍历所有原始路段（i→i+1）
                    for i in range(len(success_poi_list) - 1):

                        origin_poi = success_poi_list[i]
                        dest_poi = success_poi_list[i + 1]
                        transport = transports[i]
                        origin_city = origin_poi.get("geocode", {}).get("city") or origin_poi.get("city")
                        dest_city = dest_poi.get("geocode", {}).get("city") or dest_poi.get("city")

                        print(f"\n计算路段{i + 1}：{origin_poi['name']} -> {dest_poi['name']}（{transport}）")
                        print(f"  起点Location：{origin_poi['location']} | 终点Location：{dest_poi['location']}")
                        duration = self.get_duration_between_pois(
                            origin_poi=origin_poi,
                            dest_poi=dest_poi,
                            transport=transport,
                            origin_city=origin_city,
                            dest_city=dest_city
                        )
                        if duration is not None:
                            route_details.append({
                                "segment": i + 1,
                                "original_instruction_segment": f"{i + 1}→{i + 2}",
                                "origin": {
                                    "name": origin_poi["name"],
                                    "structured_address": origin_poi.get("structured_address", ""),
                                    "location": origin_poi["location"],
                                    "instruction_type": origin_poi["instruction_type"],
                                    "instruction_index": origin_poi["instruction_index"]
                                },
                                "destination": {
                                    "name": dest_poi["name"],
                                    "structured_address": dest_poi.get("structured_address", ""),
                                    "location": dest_poi["location"],
                                    "instruction_type": dest_poi["instruction_type"],
                                    "instruction_index": dest_poi["instruction_index"]
                                },
                                "transport": transport,
                                "duration_seconds": duration,
                                "duration_minutes": round(duration / 60, 1)
                            })
                            total_duration_seconds += duration
                            print(f"路段{i + 1}：计算成功，耗时{round(duration / 60, 1)}分钟")
                        else:
                            print(f"路段{i + 1}：计算失败，跳过")

                # 5. 构建最终结果
                final_result = {
                    "input_instruction": instruction_data,
                    "global_errors": global_errors,
                    "success_summary": {
                        "total_input_instructions": len(instructions),
                        "success_instructions_count": len(success_poi_list),
                        "failed_instructions_count": len(failed_instructions),
                        "total_segments": len(route_details),
                        "total_duration_seconds": total_duration_seconds,
                        "total_duration_minutes": round(total_duration_seconds / 60, 1),
                        "actual_cities": list(actual_cities)
                    },
                    "route_details": route_details,
                    "success_poi_list": success_poi_list,  # 所有成功的POI（含类型1降级的地理编码包装）
                    "failed_instructions": failed_instructions
                }

                # 生成错误汇总
                error_summary = ""
                if global_errors:
                    error_summary += "全局错误：" + "；".join(global_errors) + "；"
                if failed_instructions:
                    error_summary += f"失败指令数：{len(failed_instructions)}（详情见failed_instructions字段）"

                print(f"\n=== 指令处理完成 ===")
                print(
                    f"输入指令数：{len(instructions)} | 成功数：{len(success_poi_list)} | 失败数：{len(failed_instructions)}")
                print(
                    f"成功路段数：{len(route_details)} | 总通行时间：{final_result['success_summary']['total_duration_minutes']}分钟")
                return final_result, error_summary

            except Exception as e:
                # 全局异常捕获（确保返回结构化结果）
                global_error = f"整体处理异常：{str(e)}"
                failed_instructions.append(
                    {"instruction_index": -1, "type": "global", "error": global_error, "description": "全局异常"})
                final_result = {
                    "input_instruction": instruction_data,
                    "global_errors": [global_error],
                    "success_summary": {
                        "total_input_instructions": len(instructions) if 'instructions' in locals() else 0,
                        "success_instructions_count": len(success_poi_list),
                        "failed_instructions_count": len(failed_instructions),
                        "total_segments": len(route_details),
                        "total_duration_seconds": total_duration_seconds,
                        "total_duration_minutes": round(total_duration_seconds / 60, 1),
                        "actual_cities": list(actual_cities)
                    },
                    "route_details": route_details,
                    "success_poi_list": success_poi_list,
                    "failed_instructions": failed_instructions
                }
                print(f"\n=== 处理异常终止 ===")
                print(f"全局错误：{global_error}")
                return final_result, global_error


    def extract_route_summary(self,route_result: Dict[str, Any]) -> str:
        """
        从 process_instruction_route 的输出结果中提取核心信息，生成字符串摘要
        Args:
            route_result: process_instruction_route 的返回结果（第一个元素）
        Returns:
            包含POI信息、通行方式时长、失败详情的字符串
        """
        if not isinstance(route_result, dict):
            return "输入结果格式无效，无法提取摘要"

        # 初始化各模块字符串
        header = "\n=== 路线规划结果摘要 ===\n"
        poi_section = "一、成功获取的POI信息：\n"
        route_section = "二、POI之间通行信息：\n"
        fail_section = "三、失败详情：\n"

        # 1. 头部摘要（总览信息）
        success_summary = route_result.get("success_summary", {})
        total_input = success_summary.get("total_input_instructions", 0)
        success_cnt = success_summary.get("success_instructions_count", 0)
        fail_cnt = success_summary.get("failed_instructions_count", 0)
        total_segments = success_summary.get("total_segments", 0)
        total_duration = success_summary.get("total_duration_minutes", 0.0)
        actual_cities = success_summary.get("actual_cities", [])

        header += (
            f"总输入指令数：{total_input} | 成功指令数：{success_cnt} | 失败指令数：{fail_cnt}\n"
            f"成功路段数：{total_segments} | 总通行时长：{total_duration}分钟\n"
            f"涉及城市：{', '.join(actual_cities) if actual_cities else '无'}\n"
            f"全局错误：{'; '.join(route_result.get('global_errors', [])) if route_result.get('global_errors') else '无'}\n"
        )

        # 2. 成功POI信息提取（关键字段：索引、类型、名称、地址、经纬度）
        success_pois = route_result.get("success_poi_list", [])
        if success_pois:
            for idx, poi in enumerate(success_pois, 1):
                instr_idx = poi.get("instruction_index", -1)
                instr_type = poi.get("instruction_type", "未知")
                name = poi.get("name", "未知名称")
                address = poi.get("structured_address", "未知地址")
                location = poi.get("location", "未知经纬度")
                # 补充类型1的降级标记、类型3的降级标记
                fallback_note = ""
                if instr_type == "1":
                    fallback_note = "（已降级为地理编码）" if poi.get("is_poi_fallback", False) else "（POI搜索成功）"
                elif instr_type == "3":
                    fallback_note = "（已降级为直接POI搜索）" if poi.get("is_fallback", False) else "（周边POI搜索成功）"

                poi_section += (
                    f"     名称：{name}\n"
                    f"     地址：{address}\n"
                    f"     经纬度：{location}\n"
                )
        else:
            poi_section += "  无成功获取的POI信息\n"

        # 3. 通行信息提取（路段、起点终点、交通方式、时长）
        routes = route_result.get("route_details", [])
        if routes:
            for route in routes:
                segment = route.get("segment", 0)
                origin_name = route.get("origin", {}).get("name", "未知起点")
                dest_name = route.get("destination", {}).get("name", "未知终点")
                transport = route.get("transport", "未知方式")
                duration = route.get("duration_minutes", 0.0)
                origin_idx = route.get("origin", {}).get("instruction_index", -1)
                dest_idx = route.get("destination", {}).get("instruction_index", -1)

                route_section += (
                    f"  路段{segment}：\n"
                    f"     路线：{origin_name} → {dest_name}\n"
                    f"     交通方式：{transport} | 通行时长：{duration}分钟\n"
                )
        else:
            route_section += "  无成功计算的通行路段\n"

        # 4. 失败详情提取（指令索引、类型、原始内容、错误原因）
        failed_instrs = route_result.get("failed_instructions", [])
        if failed_instrs:
            for fail in failed_instrs:
                instr_idx = fail.get("instruction_index", -1)
                instr_type = fail.get("type", "未知类型")
                original = fail.get("original_instruction", {})
                error = fail.get("error", "未知错误")
                desc = fail.get("description", "无描述")

                # 格式化原始指令（避免过长）
                original_str = str(original)[:100] + "..." if len(str(original)) > 100 else str(original)

                fail_section += (
                    f"  {desc}：\n"
                    f"     原始指令：{original_str}\n"
                    f"     错误原因：{error}\n"
                )
        else:
            fail_section += "  无失败指令\n"

        # 拼接所有模块，返回最终字符串
        final_summary = header + "\n" + poi_section + "\n" + route_section + "\n" + fail_section
        return final_summary

    def extract_poi_route_simplified(self,route_result: Dict[str, Any]) -> str:
        """
        超精简提取：仅保留POI名称、地址及路段通行信息（无经纬度/类型）
        格式极简，专注支持LLM修改生活事件
        Args:
            route_result: process_instruction_route 的返回结果（第一个元素）
        Returns:
            超精简POI+通行信息字符串
        """
        if not isinstance(route_result, dict):
            return "无效路线结果，无法提取有效信息"

        success_pois = route_result.get("success_poi_list", [])
        routes = route_result.get("route_details", [])

        # 1. POI列表（仅名称+地址）
        poi_str = "【地点列表】\n"
        if success_pois:
            poi_index_map = {poi.get("instruction_index"): idx + 1 for idx, poi in enumerate(success_pois)}
            for seq, poi in enumerate(success_pois, 1):
                name = poi.get("name", "未知地点")
                address = poi.get("structured_address", "未知地址")
                poi_str += f"{seq}. 名称：{name} | 地址：{address}\n"
        else:
            poi_str += "无有效地点信息\n"

        # 2. 通行路线（仅核心关联信息）
        route_str = "\n【通行信息】\n"
        if routes:
            for route in routes:
                segment = route.get("segment", 0)
                origin_poi = route.get("origin", {})
                dest_poi = route.get("destination", {})
                origin_seq = poi_index_map.get(origin_poi.get("instruction_index"), "未知")
                dest_seq = poi_index_map.get(dest_poi.get("instruction_index"), "未知")
                origin_name = origin_poi.get("name", "未知起点")
                dest_name = dest_poi.get("name", "未知终点")
                transport = route.get("transport", "未知方式")
                duration = route.get("duration_minutes", 0.0)
                # 极简格式：路段+地点关联+路线+交通方式+时长
                route_str += f"路段{segment}（地点{origin_seq}→地点{dest_seq}）：{origin_name} → {dest_name} | 交通：{transport} | 时长：{duration}分钟\n"
        else:
            route_str += "无有效通行信息\n"

        return poi_str + route_str
# ------------------------------
# 使用示例（需替换有效API_KEY）
# ------------------------------
if __name__ == "__main__":
    # 从配置文件读取API密钥
    import json
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    # 获取地图工具配置
    map_config = config.get('map_tool', {})
    API_KEY = map_config.get('api_key', '')  # 从https://lbs.amap.com/申请
    map_tool = MapMaintenanceTool(api_key=API_KEY)
    # 用户输入指令（与用户提供的格式一致）
    # 用户输入指令（包含一个故意失败的指令3，测试降级机制）
    user_instruction = {
  "instruction": [
    {"type": "1", "location": "上海市浦东新区张杨路123号（住址）"},
    {"type": "2", "keyword": "上海市黄浦区鸡鸣汤包店", "city": "上海市"},
    {"type": "1", "location": "上海市浦东新区张杨路123号（住址）"},
    {"type": "1", "location": "上海市浦东新区世纪大道88号（工作地）"},
    {"type": "2", "keyword": "上海市黄浦区福州路465号上海书城", "city": "上海市"},
    {"type": "2", "keyword": "上海市黄浦区南京东路299号宏伊国际广场", "city": "上海市"},
    {"type": "1", "location": "上海市浦东新区世纪大道88号（工作地）"},
    {"type": "2", "keyword": "上海市浦东新区张杨路1515号迪卡侬金桥店", "city": "上海市"},
    {"type": "1", "location": "上海市浦东新区张杨路123号（住址）"}
  ],
  "city": ["上海市","上海市","上海市","上海市","上海市","上海市","上海市","上海市","上海市"],
  "transport": ["walking", "walking", "driving", "driving", "walking", "driving", "driving", "driving"]
}

    # 处理指令并获取结果
    result, error_summary = map_tool.process_instruction_route(user_instruction)

    # 打印结果摘要
    print(f"\n=== 结果摘要 ===")
    print(f"全局错误：{result['global_errors']}")
    print(f"成功指令数：{result['success_summary']['success_instructions_count']}")
    print(f"失败指令数：{result['success_summary']['failed_instructions_count']}")
    print(f"成功路段数：{result['success_summary']['total_segments']}")
    print(f"总通行时间：{result['success_summary']['total_duration_minutes']}分钟")

    # 打印失败指令详情
    if result["failed_instructions"]:
        print(f"\n=== 失败指令详情 ===")
        for fail in result["failed_instructions"]:
            print(f"指令{fail['instruction_index'] + 1}（类型{fail['type']}）：{fail['error']}")

    # 打印成功路段详情
    if result["route_details"]:
        print(f"\n=== 成功路段详情 ===")
        for segment in result["route_details"]:
            print(f"路段{segment['segment']}：{segment['origin']['name']} -> {segment['destination']['name']}")
            print(f"  交通方式：{segment['transport']} | 通行时间：{segment['duration_minutes']}分钟")