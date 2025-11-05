import requests
import time
from typing import List, Dict, Optional, Tuple


class MapMaintenanceTool:
    """地图维护工具类，支持跨城市路线查询，确保所有函数出错时有明确输出"""

    def __init__(self, api_key: str, cache_expire_seconds: int = 3600):
        self.api_key = api_key
        self.cache_expire_seconds = cache_expire_seconds  # 缓存有效期
        self.transport_apis = {
            "driving": "https://restapi.amap.com/v3/direction/driving",
            "walking": "https://restapi.amap.com/v3/direction/walking",
            "transit": "https://restapi.amap.com/v3/direction/transit/integrated",
            "bicycling": "https://restapi.amap.com/v4/direction/bicycling"
        }
        self.poi_cache: Dict[str, Tuple[float, Dict]] = {}  # {关键词+城市: (缓存时间, POI数据)}
        self.duration_cache: Dict[str, Tuple[float, int]] = {}  # {起点+终点+交通方式: (缓存时间, 耗时秒数)}

    def _is_cache_valid(self, cache_time: float) -> bool:
        """检查缓存是否有效，出错时返回False"""
        try:
            return time.time() - cache_time < self.cache_expire_seconds
        except Exception as e:
            print(f"缓存有效性检查失败: {str(e)}")
            return False

    def get_poi(self, keyword: str, city: Optional[str] = None) -> Optional[Dict]:
        """获取POI，出错时返回None（但确保函数有输出）"""
        try:
            cache_key = f"{keyword}_{city or '全国'}"
            # 检查缓存
            if cache_key in self.poi_cache:
                cache_time, poi_data = self.poi_cache[cache_key]
                if self._is_cache_valid(cache_time):
                    print(f"POI缓存命中: {keyword}@{city}")
                    return poi_data
            # 调用API
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
                timeout=10  # 超时保护
            )
            response.raise_for_status()
            result = response.json()
            # 解析结果
            if result.get("status") == "1" and int(result.get("count", 0)) > 0:
                first_poi = result["pois"][0]
                if "location" not in first_poi:
                    print(f"POI缺少经纬度: {keyword}@{city}")
                    return None
                self.poi_cache[cache_key] = (time.time(), first_poi)
                return first_poi
            else:
                print(f"未找到POI: {keyword}@{city}")
                return None
        except Exception as e:
            print(f"get_poi执行失败({keyword}@{city}): {str(e)}")
            return None  # 出错时明确返回None，确保有输出

    def get_duration_between_pois(self, origin_poi: Dict, dest_poi: Dict, transport: str,
                                  origin_city: Optional[str] = None, dest_city: Optional[str] = None) -> Optional[int]:
        """计算通行时间，出错时返回None（确保函数有输出）"""
        try:
            # 提取经纬度
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
            return None  # 出错时明确返回None，确保有输出

    def process_route(self, keywords: List[str], cities: List[Optional[str]], transports: List[str]) -> Tuple[List[Dict], List[Optional[int]]]:
        """主函数：确保任何错误都返回([], [])，且所有子函数出错时有输出"""
        # 确保输入参数可迭代（避免类型错误）
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
                print(f"交通方式数量不匹配（需{len(keywords)-1}个，实际{len(transports)}个）")
                return [], []

            # 获取POI列表（任何POI失败则整体返回空）
            poi_list = []
            for i, (keyword, city) in enumerate(zip(keywords, cities)):
                poi = self.get_poi(keyword, city)
                if not poi:
                    print(f"第{i+1}个POI获取失败，终止路线处理")
                    return [], []
                poi_list.append(poi)

            # 计算耗时列表（任何一段失败则整体返回空）
            duration_list = []
            for i in range(len(poi_list) - 1):
                duration = self.get_duration_between_pois(
                    origin_poi=poi_list[i],
                    dest_poi=poi_list[i+1],
                    transport=transports[i],
                    origin_city=cities[i],
                    dest_city=cities[i+1]
                )
                if duration is None:
                    print(f"第{i+1}段耗时获取失败，终止路线处理")
                    return [], []
                duration_list.append(duration)
                print(f"路段{i+1}计算完成: {duration//60}分钟")

            return poi_list, duration_list

        except Exception as e:
            print(f"process_route整体执行失败: {str(e)}")
            return [], []  # 最终兜底：任何未捕获的错误都返回空数组

    def clear_expired_cache(self) -> None:
        """清理缓存，出错时仅打印日志不中断"""
        try:
            current_time = time.time()
            self.poi_cache = {k: (t, d) for k, (t, d) in self.poi_cache.items() if current_time - t < self.cache_expire_seconds}
            self.duration_cache = {k: (t, d) for k, (t, d) in self.duration_cache.items() if current_time - t < self.cache_expire_seconds}
            print(f"缓存清理完成（POI: {len(self.poi_cache)}, 耗时: {len(self.duration_cache)}）")
        except Exception as e:
            print(f"缓存清理失败: {str(e)}")  # 确保出错时有输出，不中断程序


# 使用示例
if __name__ == "__main__":
    API_KEY = ""
    map_tool = MapMaintenanceTool(api_key=API_KEY)

    # 正常测试
    pois, durations = map_tool.process_route(
        keywords=["北京大学", "天安门"],
        cities=["beijing", "beijing"],
        transports=["walking"]
    )
    print(f"正常调用结果: POI={pois}, 耗时={durations}")

    # 错误测试（关键词不足）
    pois, durations = map_tool.process_route(
        keywords=["单个地点"],
        cities=["beijing"],
        transports=["driving"]
    )
    print(f"关键词不足结果: POI={len(pois)}, 耗时={len(durations)}")  # 应返回0,0

    # 错误测试（API失效）
    map_tool.api_key = "invalid_key"  # 模拟无效API
    pois, durations = map_tool.process_route(
        keywords=["北京大学", "天安门"],
        cities=["beijing", "beijing"],
        transports=["walking"]
    )
    print(f"API失效结果: POI={len(pois)}, 耗时={len(durations)}")  # 应返回0,0