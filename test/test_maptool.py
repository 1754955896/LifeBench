import json
import os

# 导入工具类
from utils.maptool import MapMaintenanceTool
from utils.llm_call import llm_call


# 读取配置文件
def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)


# 加载画像数据
def load_persona_data(file_path='data/xujing/persona.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# 第一轮查询模板：工作地、居住地和其他独立地址
template_first_round_query = '''
请基于以下人物画像数据，分析并生成需要查询的核心地址信息。

## 人物画像信息：
{persona_data}

## 任务要求：
1. 只分析画像中提到的**完全独立的核心常去地址**，包括：
   - 常住住址（居住地）
   - 日常工作地
   - 其他不依赖于任何特定地点的独立常去地址（如学校、固定的兴趣班地址等）
2. **严格排除所有具有依赖关系的地址**：
   - 如"家附近的健身房"、"公司旁边的咖啡厅"、"学校周边的书店"等依赖于其他核心地址的场所
   - 这些场所应在第二轮查询中基于核心地址的周边场所进行查询
3. 忽略**不常去的地址**（如偶尔去过一次的地方、仅提及一次的陌生地址等）
4. 忽略**他人的地址**（如朋友家、亲戚家、他人的工作地址等，除非可能是自己常去的）
5. 每个查询都使用关键字查询类型
6. 构建查询关键词的规则：
   - 对于一般地址（如居住地、工作地），使用"地址（具体到区）+POI类型（最好具体到建筑类型如商场而非商圈）"的组合方式，例如：
     - "北京市朝阳区 小区"（居住地）
     - "上海市浦东新区 万达"（工作地）
     - "广州市天河区 商场"（其他）
   - 对于著名公共地点（如故宫、天安门、东方明珠、等确定存在的地标），可以直接使用名称查询
   - 不要完全依赖画像中可能存在的具体街道或门牌号信息或招牌名，因为这些可能是虚假的
   - 绝对不要生成直接查询品牌名的查询，确保查询结果限定在特定区域内

## 输出要求：
仅输出JSON格式内容，直接以{{}}作为开头结尾，不添加任何额外文本、注释或代码块标记：
[{{
    "query_type": "keyword",
    "keyword": 查询的关键词（必须）,
    "city": 查询的城市（可选）,
    "address_type": 地址类型（如"工作地"、"居住地"、"其他"）,
    "description": 该地点对人物的用途描述（必须，如"日常居住的小区"、"工作的办公楼"、"常去的购物商场"）
}}]
'''
# 第二轮查询模板：基于核心地址的周边场所
template_second_round_query = '''
请基于以下核心地址查询结果和人物画像数据，分析并生成需要查询的周边场所信息。

## 核心地址查询结果：
{core_addresses}

## 人物画像信息：
{persona_data}

## 任务要求：
1. 分析画像中提到的**常去的周边场所**，包括：
   - 居住地周边可能常去的场所（如超市、餐厅、公园、健身房等）
   - 工作地周边可能常去的场所（如咖啡馆、快餐店、便利店等）
2. 每个周边查询必须明确基于第一轮查询到的**具体核心地址**
3. 忽略**不常去的周边场所**
4. 为每个周边场所确定合适的POI类型
6. 确保查询结果**严格限定在核心地址的周边**，而不是整个城市范围


## 输出要求：
仅输出JSON格式内容，直接以{{}}作为开头结尾，不添加任何额外文本、注释或代码块标记：
[{{
    "query_type": "around",
    "keyword": 查询的关键词（必须，描述场所类型而非品牌名）,
    "city": 查询的城市（可选，可从核心地址获取）,
    "base_location": 周边查询的基础地址（必须，从第一轮结果中选择）,
    "base_address_type": 基础地址类型（"工作地"或"居住地"）,
    "poi_type": 周边查询的POI类型（可选）,
    "description": 该地点对人物的用途描述（必须，如"居住小区附近的超市"、"工作楼下的咖啡馆"、"学校旁边的餐厅"）
}}]
'''


# 生成第一轮查询指令（核心地址）
def generate_first_round_queries(persona_data):
    prompt = template_first_round_query.format(persona_data=json.dumps(persona_data, ensure_ascii=False, indent=2))
    response = llm_call(prompt, context="你是一个地址信息分析师，擅长根据人物画像分析并提取需要查询的核心地址信息。")

    # 解析LLM返回的JSON
    try:
        # 移除可能的额外文本，只保留JSON部分
        if response.startswith('[') and ']' in response:
            json_start = response.index('[')
            json_end = response.rindex(']') + 1
            json_str = response[json_start:json_end]
            queries = json.loads(json_str)
            return queries
        elif response.startswith('{') and '}' in response:
            json_start = response.index('{')
            json_end = response.rindex('}') + 1
            json_str = response[json_start:json_end]
            queries = json.loads(json_str)
            # 如果返回的是单个对象，转换为数组
            return [queries] if isinstance(queries, dict) else queries
        else:
            print("LLM返回的内容不是有效的JSON格式")
            print("LLM返回内容:", response)
            return None
    except json.JSONDecodeError as e:
        print("解析LLM返回的JSON失败:", e)
        print("LLM返回内容:", response)
        return None

# 生成第二轮查询指令（周边场所）
def generate_second_round_queries(persona_data, first_round_results):
    # 准备核心地址数据
    core_addresses = []
    for result in first_round_results:
        core_address = {
            'name': result.get('name', ''),
            'structured_address': result.get('structured_address', ''),
            'location': result.get('location', ''),
            'address_type': result.get('address_type', '其他')
        }
        core_addresses.append(core_address)

    prompt = template_second_round_query.format(
        core_addresses=json.dumps(core_addresses, ensure_ascii=False, indent=2),
        persona_data=json.dumps(persona_data, ensure_ascii=False, indent=2)
    )
    response = llm_call(prompt, context="你是一个地址信息分析师，擅长根据核心地址分析并提取需要查询的周边场所信息。")

    # 解析LLM返回的JSON
    try:
        # 移除可能的额外文本，只保留JSON部分
        if response.startswith('[') and ']' in response:
            json_start = response.index('[')
            json_end = response.rindex(']') + 1
            json_str = response[json_start:json_end]
            queries = json.loads(json_str)
            return queries
        elif response.startswith('{') and '}' in response:
            json_start = response.index('{')
            json_end = response.rindex('}') + 1
            json_str = response[json_start:json_end]
            queries = json.loads(json_str)
            # 如果返回的是单个对象，转换为数组
            return [queries] if isinstance(queries, dict) else queries
        else:
            print("LLM返回的内容不是有效的JSON格式")
            print("LLM返回内容:", response)
            return None
    except json.JSONDecodeError as e:
        print("解析LLM返回的JSON失败:", e)
        print("LLM返回内容:", response)
        return None


# 为地址命名的模板
template_address_naming = '''
请为以下地址信息分配一个简短、明确且有意义的名称，名称应：
1. 反映地点的类型加名称（如小区、办公楼、商场、餐厅等）
2. 清晰表达地址的用途或特征
4. 格式示例：
   - 正确："南京万达茂商场"
   - 正确："世纪公园地铁站"
   - 正确："徐州云龙万达商场"


地址信息：{address_info}

输出要求：仅输出名称，不包含任何额外文本。
'''


# 为地址命名
def name_address(address_info):
    prompt = template_address_naming.format(address_info=json.dumps(address_info, ensure_ascii=False, indent=2))
    response = llm_call(prompt, context="你是一个地址命名专家，擅长为地址分配简短、明确且有意义的名称，重点体现地点类型而非品牌名。")
    return response.strip()


# 执行地址查询
def execute_address_queries(queries, map_tool, round_number=1):
    """
    执行地址查询
    
    Args:
        queries: 查询列表
        map_tool: MapMaintenanceTool实例
        round_number: 查询轮数
    
    Returns:
        tuple: (查询结果列表, 错误汇总列表)
    """
    print(f"\n=== 执行第{round_number}轮地址查询 ===")
    results = []
    error_summary = []
    
    for idx, query in enumerate(queries):
        query_type = query.get('query_type', 'keyword')
        keyword = query.get('keyword', '')
        city = query.get('city', '')
        base_location = query.get('base_location', '')
        poi_type = query.get('poi_type', '')
        address_type = query.get('address_type', '其他')
        description = query.get('description', '')

        if not keyword:
            print(f"第{idx+1}个查询缺少关键字，跳过")
            error_summary.append(f"第{idx+1}个查询缺少关键字")
            continue

        try:
            if query_type == 'around':
                print(f"\n执行周边查询：以{base_location}为中心，搜索{keyword}（类型：{poi_type}，描述：{description}）")

                # 检查base_location是否已经是坐标格式
                is_coordinate = False
                if base_location:
                    lon_lat = base_location.split(",")
                    if len(lon_lat) == 2:
                        try:
                            float(lon_lat[0])
                            float(lon_lat[1])
                            is_coordinate = True
                        except ValueError:
                            pass

                # 获取基础地址的坐标
                if is_coordinate:
                    # 直接使用坐标
                    location = base_location
                else:
                    # 通过地址获取坐标
                    base_poi = map_tool.get_poi(keyword=base_location, city=city)
                    if not base_poi or 'location' not in base_poi:
                        print(f"无法获取基础地址{base_location}的坐标，周边查询失败")
                        error_summary.append(f"第{idx+1}个周边查询：无法获取基础地址{base_location}的坐标")
                        continue
                    location = base_poi['location']

                # 执行周边查询
                result = map_tool.search_around_poi_random(
                    location=location,
                    keywords=keyword,
                    types=poi_type,
                    city=city
                )
            else:
                print(f"\n执行关键字查询：{keyword}（城市：{city}，类型：{address_type}，描述：{description}）")
                result = map_tool.get_poi(keyword=keyword, city=city)

            if result:
                print(f"查询成功：{result.get('name', '')} - {result.get('structured_address', '')}")
                # 保存地址类型和描述信息
                result['address_type'] = address_type
                result['description'] = description
                results.append(result)
            else:
                print(f"查询失败：{keyword}（类型：{address_type}，描述：{description}）")
                error_summary.append(f"第{idx+1}个查询失败：{keyword}")
        except Exception as e:
            print(f"查询出错：{keyword}，错误信息：{str(e)}")
            error_summary.append(f"第{idx+1}个查询出错：{keyword} - {str(e)}")
    
    return results, error_summary


# 构建画像地址数据
def build_persona_address_data(persona_data, map_tool):
    print("\n=== 第一轮查询：获取核心地址 ===")
    # 生成第一轮查询指令
    first_round_queries = generate_first_round_queries(persona_data)
    
    if not first_round_queries:
        print("生成第一轮查询指令失败")
        return None
    
    print("第一轮生成的查询指令:", json.dumps(first_round_queries, ensure_ascii=False, indent=2))
    
    # 执行第一轮地址查询
    first_round_results, first_error_summary = execute_address_queries(first_round_queries, map_tool, round_number=1)

    if first_error_summary:
        print("\n第一轮查询错误汇总:", first_error_summary)

    if not first_round_results:
        print("第一轮查询无结果，无法进行第二轮查询")
        return None

    print("\n=== 第二轮查询：获取周边场所 ===")
    # 生成第二轮查询指令
    second_round_queries = generate_second_round_queries(persona_data, first_round_results)

    if not second_round_queries:
        print("生成第二轮查询指令失败，仅保留第一轮查询结果")
        all_results = first_round_results
    else:
        print("第二轮生成的查询指令:", json.dumps(second_round_queries, ensure_ascii=False, indent=2))

        # 执行第二轮地址查询
        second_round_results, second_error_summary = execute_address_queries(second_round_queries, map_tool, round_number=2)

        if second_error_summary:
            print("\n第二轮查询错误汇总:", second_error_summary)

        # 合并两轮查询结果
        all_results = first_round_results + second_round_results

    # 构建画像地址数据
    print("\n=== 构建画像地址数据 ===")
    persona_address_data = []

    for poi in all_results:
        # 为地址命名
        address_name = name_address(poi)

        # 构建地址数据（按照用户要求的格式）
        address_data = {
            'name': address_name,
            'location': poi.get('location', ''),  # 直接使用经纬度
            'formatted_address': poi.get('structured_address', ''),
            'city': poi.get('geocode', {}).get('city', ''),
            'district': poi.get('geocode', {}).get('district', ''),
            'streetName': poi.get('geocode', {}).get('street', ''),
            'streetNumber': poi.get('geocode', {}).get('number', ''),
            'description': poi.get('description', '')  # 添加描述字段
        }

        persona_address_data.append(address_data)

    return persona_address_data


# 测试函数
def test_persona_address_query():
    print("=== 开始测试画像地址查询功能 ===")
    
    # 加载配置
    config = load_config()
    map_config = config.get('map_tool', {})
    api_key = map_config.get('api_key', '')
    
    # 初始化地图工具
    map_tool = MapMaintenanceTool(api_key=api_key)
    
    # 加载画像数据
    persona_data = load_persona_data()
    
    # 构建画像地址数据
    persona_address_data = build_persona_address_data(persona_data, map_tool)

    if persona_address_data:
        print("\n=== 最终构建的画像地址数据 ===")
        print(json.dumps(persona_address_data, ensure_ascii=False, indent=2))

        # 保存画像地址数据
        # save_path = 'data/fenghaoran/persona_address_data.json'
        # with open(save_path, 'w', encoding='utf-8') as f:
        #     json.dump(persona_address_data, f, ensure_ascii=False, indent=2)
        #
        # print(f"\n画像地址数据已保存到: {save_path}")
    else:
        print("\n构建画像地址数据失败")


# 测试process_instruction_route方法
from utils.maptool import MapMaintenanceTool
import json

def test_process_instruction_route():
    print("=== 开始测试process_instruction_route方法 ===")
    
    # 加载配置
    config = load_config()
    map_config = config.get('map_tool', {})
    api_key = map_config.get('api_key', '')
    
    # 用户提供的地址数据
    test_address_data = [
        {
            "name": "上港小区",
            "location": "121.513638,31.237805",
            "formatted_address": "上海市上海市浦东新区浦东大道136弄2-51号",
            "city": "上海市",
            "district": "浦东新区",
            "streetName": "浦东大道136弄",
            "streetNumber": "2-51号",
            "description": "徐静的常住家庭住址，位于浦东新区张杨路附近。"
        },
        {
            "name": "航头镇石辰商场",
            "location": "121.580002,31.077599",
            "formatted_address": "上海市上海市浦东新区[][]",
            "city": "上海市",
            "district": "浦东新区",
            "streetName": [],
            "streetNumber": [],
            "description": "徐静工作的服装店所在商场，位于浦东新区世纪大道附近。"
        },
        {
            "name": "嘉善路瑜伽会所",
            "location": "121.460338,31.206275",
            "formatted_address": "上海市上海市徐汇区嘉善路[]",
            "city": "上海市",
            "district": "徐汇区",
            "streetName": "嘉善路",
            "streetNumber": [],
            "description": "徐静每周固定进行瑜伽锻炼的静心瑜伽工作室所在地。"
        },
        {
            "name": "TPY中心攀岩馆",
            "location": "121.439352,31.192121",
            "formatted_address": "上海市上海市徐汇区肇嘉浜路1117号",
            "city": "上海市",
            "district": "徐汇区",
            "streetName": "肇嘉浜路",
            "streetNumber": "1117号",
            "description": "徐静每周固定进行力量训练的力健健身俱乐部所在地。"
        },
        {
            "name": "潍坊社区卫生服务中心",
            "location": "121.524227,31.223525",
            "formatted_address": "上海市上海市浦东新区崂山路639号",
            "city": "上海市",
            "district": "浦东新区",
            "streetName": "崂山路",
            "streetNumber": "639号",
            "description": "徐静定期进行健康咨询和体检的社区卫生服务中心，家庭医生在此工作。"
        },
        {
            "name": "南泉北路日杂店",
            "location": "121.515688,31.237285",
            "formatted_address": "南泉北路160号(浦东南路地铁站2号口步行360米)",
            "city": "",
            "district": "",
            "streetName": "",
            "streetNumber": "",
            "description": "居住地（上港小区）附近的超市，用于满足日常购物需求"
        },
        {
            "name": "招远小区面馆",
            "location": "121.514938,31.237064",
            "formatted_address": "上海市上海市浦东新区招远路19弄1-48号",
            "city": "上海市",
            "district": "浦东新区",
            "streetName": "招远路19弄",
            "streetNumber": "1-48号",
            "description": "居住地（上港小区）附近的餐厅，用于日常用餐或与家人朋友聚餐"
        },
        {
            "name": "链轮体育公园",
            "location": "121.514066,31.241254",
            "formatted_address": "上海市上海市浦东新区昌邑路55弄22号",
            "city": "上海市",
            "district": "浦东新区",
            "streetName": "昌邑路55弄",
            "streetNumber": "22号",
            "description": "居住地（上港小区）附近的公园，用于日常散步、休闲"
        },
        {
            "name": "陆家嘴社区卫生服务中心",
            "location": "121.527111,31.237686",
            "formatted_address": "上海市上海市浦东新区乳山路235弄1号",
            "city": "上海市",
            "district": "浦东新区",
            "streetName": "乳山路235弄",
            "streetNumber": "1号",
            "description": "居住地（上港小区）附近的社区卫生服务中心，用于常规健康检查或就医"
        },
        {
            "name": "瑞幸咖啡车市店",
            "location": "121.586004,31.072074",
            "formatted_address": "上海市上海市浦东新区[][]",
            "city": "上海市",
            "district": "浦东新区",
            "streetName": [],
            "streetNumber": [],
            "description": "工作地（石辰商场）附近的咖啡馆，用于工作间隙休息或与同事、客户交流"
        },
        {
            "name": "航头浦乐汇锅贴店",
            "location": "121.593058,31.077818",
            "formatted_address": "上海市上海市浦东新区航瑞路[]",
            "city": "上海市",
            "district": "浦东新区",
            "streetName": "航瑞路",
            "streetNumber": [],
            "description": "工作地（石辰商场）附近的快餐店，用于工作日快速解决午餐"
        },
        {
            "name": "昱星家园便利店",
            "location": "121.589512,31.081682",
            "formatted_address": "上海市上海市浦东新区鹤沙路688弄1-46号",
            "city": "上海市",
            "district": "浦东新区",
            "streetName": "鹤沙路688弄",
            "streetNumber": "1-46号",
            "description": "工作地（石辰商场）附近的便利店，用于购买日常用品、零食或应急物品"
        },
        {
            "name": "福旺家具商场",
            "location": "121.582074,31.088740",
            "formatted_address": "沪南公路4388号(沈梅路地铁站3号口步行240米)",
            "city": "",
            "district": "",
            "streetName": "",
            "streetNumber": "",
            "description": "工作地（石辰商场）附近的其他商场，用于工作相关的市场考察或个人购物休闲"
        },
        {
            "name": "之俊大厦瑜伽中心",
            "location": "121.464415,31.199882",
            "formatted_address": "上海市上海市徐汇区斜土路1221号",
            "city": "上海市",
            "district": "徐汇区",
            "streetName": "斜土路",
            "streetNumber": "1221号",
            "description": "常去的瑜伽会所（Y+瑜伽会所）附近的其他瑜伽馆，作为备选或体验场所"
        },
        {
            "name": "徐汇万科广场攀岩馆",
            "location": "121.431757,31.157874",
            "formatted_address": "上海市上海市徐汇区沪闵路[]",
            "city": "上海市",
            "district": "徐汇区",
            "streetName": "沪闵路",
            "streetNumber": [],
            "description": "常去的攀岩俱乐部（GOAT攀岩俱乐部）附近的其他攀岩馆，作为备选或体验场所"
        },
        {
            "name": "东明社区卫生服务站",
            "location": "121.518738,31.218749",
            "formatted_address": "上海市上海市浦东新区浦东南路1678号",
            "city": "上海市",
            "district": "浦东新区",
            "streetName": "浦东南路",
            "streetNumber": "1678号",
            "description": "常去的社区卫生服务中心（潍坊社区卫生服务中心）附近的其他医院，用于专科诊疗或紧急就医"
        }
    ]
    
    # 初始化地图工具，传入测试地址数据
    map_tool = MapMaintenanceTool(api_key=api_key, persona_address_data=test_address_data)
    
    # 创建测试指令数据
    test_instruction_data = {
        "instruction": [
            # 类型1：通过name匹配画像地址
            {
                "type": "1",
                "name": "上港小区",
                "city": "上海市"
            },
            # 类型1：通过location匹配画像地址
            {
                "type": "1",
                "location": "121.460338,31.206275",
                "city": "上海市"
            },
            # 类型2：直接POI搜索
            {
                "type": "2",
                "keyword": "上海市浦东新区 世纪大道 商场"
            },
            # 类型3：附近POI搜索
            {
                "type": "3",
                "baseKeyword": "上港小区",
                "poiType": "餐厅",
                "Keyword": "上海市浦东新区 上港小区 餐厅"
            }
        ],
        "city": ["上海市", "上海市", "上海市", "上海市"],
        "transport": ["driving", "walking", "bicycling"]
    }
    
    print("测试指令数据:")
    print(json.dumps(test_instruction_data, ensure_ascii=False, indent=2))
    
    # 执行测试
    print("\n=== 执行process_instruction_route方法 ===")
    route_result, error_summary = map_tool.process_instruction_route(test_instruction_data)
    
    # 打印结果
    print("\n=== 执行结果 ===")
    print("\n1. 结构化结果:")
    print(json.dumps(route_result, ensure_ascii=False, indent=2))
    
    print("\n2. 错误汇总信息:")
    print(error_summary)
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_persona_address_query()
    # 测试process_instruction_route方法
    #test_process_instruction_route()