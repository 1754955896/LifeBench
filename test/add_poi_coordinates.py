"""为相册数据中的POI地址添加经纬度信息"""
import json
import os
from utils.maptool import MapMaintenanceTool


def load_gallery_data(file_path: str) -> list:
    """加载相册数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_gallery_data(data: list, file_path: str):
    """保存相册数据"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_coordinates_to_poi(gallery_data: list, map_tool: MapMaintenanceTool) -> list:
    """
    为每个包含poi字段的数据项添加经纬度信息（20线程并行）
    
    Args:
        gallery_data: 相册数据列表
        map_tool: 地图维护工具实例
    
    Returns:
        添加了经纬度的数据列表
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    # 筛选出需要处理的数据项
    items_to_process = []
    for idx, item in enumerate(gallery_data):
        poi_data = item.get('poi', {})
        if isinstance(poi_data, dict):
            items_to_process.append((idx, item))
        else:
            skipped_count += 1
    
    print(f"\n总共 {len(gallery_data)} 条数据，需要处理 {len(items_to_process)} 条，跳过 {skipped_count} 条")
    
    # 定义单个POI处理函数
    def process_single_poi(item_idx_pair):
        idx, item = item_idx_pair
        poi_data = item.get('poi', {})
        
        # 拼接完整地址：省市区街道+POI名称
        province = poi_data.get('province', '')
        city = poi_data.get('city', '')
        district = poi_data.get('district', '')
        street_name = poi_data.get('streetName', '')
        street_number = poi_data.get('streetNumber', '')
        poi_name = poi_data.get('poi', '')
        
        # 构建完整地址字符串
        address_parts = [province, city, district, street_name, street_number, poi_name]
        full_address = ''.join([part for part in address_parts if part])
        
        if not full_address:
            return idx, item, 'skipped', None
        
        # 调用高德地图地理编码API
        geocode_result = map_tool.amap_geocode(address=full_address, city=city)
        
        # 添加延时避免触发限流
        time.sleep(0.1)
        
        if geocode_result and geocode_result.get('location'):
            # 解析经纬度 (格式: "经度,纬度")
            location = geocode_result['location']
            if ',' in location:
                lng, lat = location.split(',')
                
                # 添加经纬度字段
                item['longitude'] = float(lng)
                item['latitude'] = float(lat)
                
                # 添加结构化地址信息（可选）
                item['geocode_info'] = {
                    'province': geocode_result.get('province', ''),
                    'city': geocode_result.get('city', ''),
                    'district': geocode_result.get('district', ''),
                    'street': geocode_result.get('street', ''),
                    'formatted_address': geocode_result.get('formatted_address', '')
                }
                
                return idx, item, 'success', full_address
            else:
                return idx, item, 'error', f"位置格式错误 - {location}"
        else:
            return idx, item, 'error', "未找到地理位置信息"
    
    # 使用20线程并行处理（限制每秒2个请求）
    print(f"\n🔄 开始并行处理（限流：每秒2请求）...")
    
    # 创建信号量控制并发
    import threading
    rate_limit_semaphore = threading.Semaphore(2)
    last_request_time = [time.time()]  # 使用列表以便在闭包中修改
    time_lock = threading.Lock()
    
    def rate_limited_process(item_pair):
        """带速率限制的POI处理"""
        with rate_limit_semaphore:
            # 确保每秒最多2个请求
            with time_lock:
                current_time = time.time()
                time_since_last = current_time - last_request_time[0]
                if time_since_last < 0.5:  # 0.5秒间隔 = 每秒2个
                    wait_time = 0.5 - time_since_last
                    time.sleep(wait_time)
                last_request_time[0] = time.time()
            
            return process_single_poi(item_pair)
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        # 提交所有任务（带速率限制）
        future_to_idx = {}
        for item_pair in items_to_process:
            future = executor.submit(rate_limited_process, item_pair)
            future_to_idx[future] = item_pair[0]
        
        # 收集结果
        processed_count = 0
        for future in as_completed(future_to_idx):
            idx, item, status, message = future.result()
            processed_count += 1
            
            if status == 'success':
                updated_count += 1
                if processed_count % 10 == 0 or processed_count == len(items_to_process):
                    print(f"  进度: {processed_count}/{len(items_to_process)} | 成功: {updated_count}")
            elif status == 'error':
                error_count += 1
                if processed_count <= 5:  # 只显示前5个错误
                    print(f"  ✗ [{idx}] 失败: {message}")
            # skipped 不计数
    
    print(f"\n{'='*60}")
    print(f"处理完成统计:")
    print(f"  - 总条目数: {len(gallery_data)}")
    print(f"  - 成功添加坐标: {updated_count}")
    print(f"  - 跳过(无POI): {skipped_count}")
    print(f"  - 失败: {error_count}")
    print(f"{'='*60}")
    
    return gallery_data


def test_single_poi():
    """测试单个POI数据的经纬度添加"""
    # 初始化地图工具
    map_tool = MapMaintenanceTool(api_key="e8f87eef67cfe6f83e68e7a65b9b848b")
    
    # 测试数据
    test_item = {
        "id": "test_001",
        "poi": {
            "province": "湖南省",
            "city": "长沙市",
            "district": "岳麓区",
            "streetName": "潇湘北路",
            "streetNumber": "XX号",
            "poi": "湘江风光带（岳麓区段）"
        }
    }
    
    print("="*60)
    print("单个POI经纬度添加测试")
    print("="*60)
    print(f"\n原始数据: {json.dumps(test_item, ensure_ascii=False, indent=2)}")
    
    # 调用处理函数
    result = add_coordinates_to_poi([test_item], map_tool)
    
    print(f"\n处理后数据: {json.dumps(result[0], ensure_ascii=False, indent=2)}")
    
    # 验证结果
    if 'longitude' in result[0] and 'latitude' in result[0]:
        print(f"\n✓ 测试成功!")
        print(f"  经度: {result[0]['longitude']}")
        print(f"  纬度: {result[0]['latitude']}")
        if 'geocode_info' in result[0]:
            print(f"  结构化地址: {result[0]['geocode_info'].get('formatted_address', '')}")
    else:
        print(f"\n✗ 测试失败: 未添加经纬度信息")


def main():
    """主函数"""
    # 输入文件路径
    input_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_reorganized\json\0_aidata_gallery.json"
    
    # 输出文件路径（在原文件名后添加 _with_coords）
    output_dir = os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_with_coords.json")
    
    print("="*60)
    print("相册数据POI经纬度补充工具")
    print("="*60)
    
    # 1. 加载数据
    print("\n[1/3] 加载相册数据...")
    try:
        gallery_data = load_gallery_data(input_path)
        print(f"  ✓ 成功加载 {len(gallery_data)} 条数据")
    except Exception as e:
        print(f"  ✗ 加载失败: {e}")
        return
    
    # 2. 初始化地图工具
    print("\n[2/3] 初始化地图工具...")
    try:
        map_tool = MapMaintenanceTool(api_key="e8f87eef67cfe6f83e68e7a65b9b848b")
        print(f"  ✓ 工具初始化成功")
    except Exception as e:
        print(f"  ✗ 初始化工具失败: {e}")
        return
    
    # 3. 添加经纬度信息
    print("\n[3/3] 开始为POI添加经纬度...")
    updated_data = add_coordinates_to_poi(gallery_data, map_tool)
    
    # 4. 保存结果
    print(f"\n保存结果到: {output_path}")
    try:
        save_gallery_data(updated_data, output_path)
        print(f"  ✓ 保存成功")
    except Exception as e:
        print(f"  ✗ 保存失败: {e}")
        return
    
    print("\n" + "="*60)
    print("完成！")
    print("="*60)


if __name__ == "__main__":
    main()
