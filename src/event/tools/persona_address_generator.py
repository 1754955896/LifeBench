import json
import os
from typing import List, Dict, Optional

from utils.maptool import MapMaintenanceTool
from utils.llm_call import llm_call


class PersonaAddressGenerator:
    """
    基于画像生成画像地址数据的类
    功能：根据人物画像数据生成该人物的核心地址和周边场所信息，并保存到location.json文件
    """
    
    def __init__(self):
        """初始化画像地址生成器"""
        # 加载配置文件
        self.config = self._load_config()
        # 初始化地图工具
        self.map_tool = self._init_map_tool()
        
        # 查询模板
        self.template_first_round_query = '''
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
6. 若画像提供的地址信息不合理可进行修正调整
7. 构建查询关键词的规则：
   - 对于一般地址（如居住地、工作地），使用"地址（具体到区）+POI类型（最好具体到建筑类型如商场而非商圈）"的组合方式，例如：
     - "北京市朝阳区 小区"（居住地）
     - "上海市浦东新区 万达"（工作地）
     - "广州市天河区 商场"（其他）
   - 对于著名公共地点（如故宫、天安门、东方明珠、等确定存在的地标），可以直接使用名称查询
   - 不要完全依赖画像中可能存在的具体街道或门牌号信息或招牌名，因为这些可能是虚假的
   - 绝对不要生成直接查询品牌名的查询，确保查询结果限定在特定区域内

## 输出要求：
仅输出JSON格式内容，直接以[]作为开头结尾，不添加任何额外文本、注释或代码块标记：
[{{
    "query_type": "keyword",
    "keyword": 查询的关键词（必须）,
    "city": 查询的城市（可选）,
    "address_type": 地址类型（如"工作地"、"居住地"、"其他"）,
    "description": 该地点对人物的用途描述（必须，如"日常居住的小区"、"工作的办公楼"、"常去的购物商场"）
}}]
'''
        
        self.template_second_round_query = '''
请基于以下核心地址查询结果和人物画像数据，分析并生成需要查询的周边场所信息。

## 核心地址查询结果：
{core_addresses}

## 人物画像信息：
{persona_data}

## 任务要求：
1. 分析画像数据思考用户可能的**常去的周边场所**，包括：
   - 居住地周边可能常去的场所（如超市、餐厅、公园、健身房等）
   - 工作地周边可能常去的场所（如咖啡馆、快餐店、便利店等）
   - 画像中提到的其他可能常去的场所（如学校、固定的兴趣班地址等）
   - 根据习惯，爱好，和生活合理思考推断一些常去场所
2. 每个周边查询必须明确基于第一轮查询到的**具体核心地址**
3. 忽略**不常去的周边场所**
4. 为每个周边场所确定合适的POI类型
6. 确保查询结果**严格限定在核心地址的周边**，而不是整个城市范围


## 输出要求：
仅输出JSON格式内容，直接以[]作为开头结尾，不添加任何额外文本、注释或代码块标记：
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
        
        self.template_address_naming = '''
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
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            raise
    
    def _init_map_tool(self) -> MapMaintenanceTool:
        """初始化地图工具"""
        map_config = self.config.get('map_tool', {})
        api_key = map_config.get('api_key', '')
        return MapMaintenanceTool(api_key=api_key)
    
    def _load_persona_data(self, persona_path: str) -> Dict:
        """加载画像数据"""
        try:
            with open(persona_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载画像数据失败: {str(e)}")
            raise
    
    def _generate_first_round_queries(self, persona_data: Dict) -> List[Dict]:
        """生成第一轮查询指令（核心地址）"""
        prompt = self.template_first_round_query.format(persona_data=json.dumps(persona_data, ensure_ascii=False, indent=2))
        from utils.llm_call import llm_call_j
        response = llm_call_j(prompt)
        
        # 解析LLM返回的JSON
        try:
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
                return []
        except json.JSONDecodeError as e:
            print("解析LLM返回的JSON失败:", e)
            print("LLM返回内容:", response)
            return []
    
    def _generate_second_round_queries(self, persona_data: Dict, first_round_results: List[Dict]) -> List[Dict]:
        """生成第二轮查询指令（周边场所）"""
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

        prompt = self.template_second_round_query.format(
            core_addresses=json.dumps(core_addresses, ensure_ascii=False, indent=2),
            persona_data=json.dumps(persona_data, ensure_ascii=False, indent=2)
        )
        from utils.llm_call import llm_call_j
        response = llm_call_j(prompt)

        # 解析LLM返回的JSON
        try:
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
                return []
        except json.JSONDecodeError as e:
            print("解析LLM返回的JSON失败:", e)
            print("LLM返回内容:", response)
            return []
    
    def _name_address(self, address_info: Dict) -> str:
        """为地址命名"""
        prompt = self.template_address_naming.format(address_info=json.dumps(address_info, ensure_ascii=False, indent=2))
        response = llm_call(prompt, context="你是一个地址命名专家，擅长为地址分配简短、明确且有意义的名称，重点体现地点类型而非品牌名。")
        return response.strip()
    
    def _execute_address_queries(self, queries: List[Dict], round_number: int = 1) -> tuple:
        """执行地址查询"""
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
                        base_poi = self.map_tool.get_poi(keyword=base_location, city=city)
                        if not base_poi or 'location' not in base_poi:
                            print(f"无法获取基础地址{base_location}的坐标，周边查询失败")
                            error_summary.append(f"第{idx+1}个周边查询：无法获取基础地址{base_location}的坐标")
                            continue
                        location = base_poi['location']

                    # 执行周边查询
                    result = self.map_tool.search_around_poi_random(
                        location=location,
                        keywords=keyword,
                        types=poi_type,
                        city=city
                    )
                else:
                    print(f"\n执行关键字查询：{keyword}（城市：{city}，类型：{address_type}，描述：{description}）")
                    result = self.map_tool.get_poi(keyword=keyword, city=city)

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
    
    def _build_persona_address_data(self, persona_data: Dict) -> List[Dict]:
        """构建画像地址数据"""
        print("\n=== 第一轮查询：获取核心地址 ===")
        # 生成第一轮查询指令
        first_round_queries = self._generate_first_round_queries(persona_data)
        
        if not first_round_queries:
            print("生成第一轮查询指令失败")
            return []
        
        #print("第一轮生成的查询指令:", json.dumps(first_round_queries, ensure_ascii=False, indent=2))
        
        # 执行第一轮地址查询
        first_round_results, first_error_summary = self._execute_address_queries(first_round_queries, round_number=1)

        if first_error_summary:
            print("\n第一轮查询错误汇总:", first_error_summary)

        if not first_round_results:
            print("第一轮查询无结果，无法进行第二轮查询")
            return []

        print("\n=== 第二轮查询：获取周边场所 ===")
        # 生成第二轮查询指令
        second_round_queries = self._generate_second_round_queries(persona_data, first_round_results)

        all_results = first_round_results
        
        if second_round_queries:
            #print("第二轮生成的查询指令:", json.dumps(second_round_queries, ensure_ascii=False, indent=2))

            # 执行第二轮地址查询
            second_round_results, second_error_summary = self._execute_address_queries(second_round_queries, round_number=2)

            if second_error_summary:
                print("\n第二轮查询错误汇总:", second_error_summary)

            # 合并两轮查询结果
            all_results = first_round_results + second_round_results

        # 构建画像地址数据
        print("\n=== 构建画像地址数据 ===")
        persona_address_data = []

        for poi in all_results:
            # 为地址命名
            address_name = self._name_address(poi)

            # 构建地址数据
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
    
    def generate_and_save_address_data(self, persona_path: str, output_path: str) -> None:
        """
        生成画像地址数据并保存到location.json文件
        
        Args:
            persona_path: 画像数据文件路径
            output_path: 输出目录路径（location.json将保存在此目录下）
        """
        try:
            # 加载画像数据
            persona_data = self._load_persona_data(persona_path)
            
            # 构建画像地址数据
            persona_address_data = self._build_persona_address_data(persona_data)
            
            if not persona_address_data:
                print("\n构建画像地址数据失败")
                return
            
            # 确保输出目录存在
            os.makedirs(output_path, exist_ok=True)
            
            # 保存画像地址数据到location.json
            location_file_path = os.path.join(output_path, 'location.json')
            with open(location_file_path, 'w', encoding='utf-8') as f:
                json.dump(persona_address_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n=== 画像地址数据生成完成 ===")
            print(f"地址数据已保存到: {location_file_path}")
            print(f"共生成{len(persona_address_data)}个地址")
            
        except Exception as e:
            print(f"生成画像地址数据失败: {str(e)}")
            raise


# 测试代码（可选）
if __name__ == "__main__":
    # 示例用法
    generator = PersonaAddressGenerator()
    
    # 使用示例画像数据路径
    example_persona_path = "data/xujing/persona.json"
    example_output_path = "output/xujing"
    
    generator.generate_and_save_address_data(example_persona_path, example_output_path)