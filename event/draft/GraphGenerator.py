# -*- coding: utf-8 -*-
"""事件图生成类，负责构建事件图谱"""
import json
from typing import Dict, List, Any, Tuple
import networkx as nx
from pyvis.network import Network
from utils.llm_call import llm_call_j, llm_call_reason_j, llm_call


class EventGraphGenerator:
    """事件图生成类，负责构建事件图谱"""
    
    def __init__(self, events_data: List[Dict] = None, event_graph: Dict = None, yearly_summary: str = None):
        """
        初始化事件图生成器
            
        Args:
            events_data: 事件数据列表，每个事件包含 id、name、description、date 等字段
            event_graph: 事件图谱数据，包含 nodes 和 edges
            yearly_summary: 全年总结文本，用于事件插入计划生成
        """
        self.events_data = events_data or []
        self.event_graph = event_graph or {"nodes": [], "edges": []}
        self.yearly_summary = yearly_summary or ""
    
    def build_event_graph(self, events_data: List[Dict] = None) -> Dict:
        """
        构建事件图谱
            
        Args:
            events_data: 事件数据列表，每个事件包含 id、name、description、date 等字段
            
        Returns:
            事件图谱数据
        """
        print("开始构建事件图谱...")
            
        # 使用传入的数据或初始化时的数据
        data = events_data or self.events_data
            
        if not data:
            print("事件数据为空，无法构建事件图谱")
            return {}
            
        # 构建事件图谱（只有节点，没有边）
        event_graph = self._generate_event_graph(data)
            
        # 获取所有子连通图
        subgraphs = self._get_subgraphs(event_graph)
        print(f"成功提取{len(subgraphs)}个子连通图")
                
        # 并行分析前 3 个子连通图的主题相关性，并分解
        refined_subgraphs = self._analyze_and_decompose_subgraphs(subgraphs)
        
        # 迭代进行优化与合并（三轮）
        current_subgraphs = refined_subgraphs
        for iteration in range(1, 4):
            print(f"\n{'='*60}")
            print(f"开始第{iteration}轮迭代优化与合并")
            print(f"\n{'='*60}")
            
            # 并行分析优化子连通图
            optimized_subgraphs = self._parallel_analyze_subgraphs(current_subgraphs)
            
            # 分析是否需要合并子连通图
            merged_graph = self._analyze_merge_subgraphs(optimized_subgraphs, event_graph)
            
            # 更新当前子图列表用于下一轮迭代
            current_subgraphs = merged_graph
            
            print(f"第{iteration}轮完成，当前有{len(merged_graph)}个子图\n")
        
        # 对最终确定的连通子图进行边的重生成（节点数大于 1 的子图）
        final_graph = self._regenerate_edges_for_subgraphs(merged_graph)
            
        # 更新实例属性
        self.event_graph = final_graph
            
        print("事件图谱构建完成！")
        return final_graph
    
    def _generate_event_graph(self, events_data: List[Dict]) -> Dict:
        """
        生成事件图谱，使用LLM提取事件间的关系
        
        Args:
            events_data: 事件数据列表
            
        Returns:
            事件图谱数据，包含nodes和edges
        """
        nodes = []
        edges = []
        
        # 构建事件节点
        for event in events_data:
            node = {
                "id": event.get("id", ""),
                "name": event.get("name", ""),
                "description": event.get("description", ""),
                "time": event.get("date", []),
                "type": event.get("type", "")
            }
            nodes.append(node)
        
        # 使用LLM生成事件边
        edges = self._generate_edges_with_llm(events_data)
        return {
            "nodes": nodes,
            "edges": edges
        }
    
    def _generate_edges_with_llm(self, events_data: List[Dict]) -> List[Dict]:
        """
        使用LLM生成事件边，确定事件间的关系
        
        Args:
            events_data: 事件数据列表
            
        Returns:
            事件边列表
        """
        prompt = f"""
        你是一位专业的事件关系分析专家，请分析以下事件之间的关系，并生成事件边数据。
        
        事件数据：
        {json.dumps(events_data, ensure_ascii=False, indent=2)}
        
        分析要求：
        **请按以下步骤逐步思考和分析：**
                
        **第一步：识别同主题事件**
        找到相似的、相关性强、同主题的事件，分析彼此之间的关联性。
                
        **第二步：分析发展过程**
        分析是否有发展过程关系的事件（如项目的启动、进行、完成，关系的变化发展等），并识别关联。
                
        **第三步：识别共同提及**
        分析描述中提到同一件事情或主题的事件，并识别它们之间的关联。或描述中明确提及了原因的事件，一定要建立对应关系。
                
        **第四步：分析时序邻近关系**
        分析时序邻近的事件间是否有明显的影响关联。
                
        **第五步：全局关系捕捉**
        以全年的视角捕捉事件之间的其他重要关系。
                
        **第六步：生成边数据**
        基于以上分析，为每对相关事件生成一条边，包含 source（源事件 ID）、target（目标事件 ID）、type（关系类型）、description（关系描述）。
                
        **注意事项：**
        1. 关系类型可以是：因果关系、时间顺序、影响关系、关联关系、前置后置流程关系等
        2. 确保关系描述准确反映事件之间的联系
        3. 尽可能分析到所有事件，不要遗漏重要的事件关系。
        4. 请注意关系只会由之前发生的事件指向之后发生的事件，因为未来不会影响过去
        5. 只有具有明确的因果关系、发展演化关系，才需要生成关系，对于因果不强的关系，不要强行推理关系。
        
        输出格式：
        仅返回JSON格式的事件边列表，示例：
        [
            {{ 
                "source": "1001",
                "target": "1002",
                "type": "因果关系",
                "description": "因为项目启动，所以需要开始健身计划保持精力"
            }},
            {{ 
                "source": "1002",
                "target": "1003",
                "type": "时间顺序",
                "description": "健身计划之后开始学习Python"
            }}
        ]
        """
        
        try:
            response = llm_call_reason_j(prompt).strip()
            # 提取JSON部分
            start_idx = response.find('[')
            end_idx = response.rfind(']')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = response[start_idx:end_idx + 1]
                edges = json.loads(json_response)
                print(f"成功生成{len(edges)}条事件边")
                return edges
            else:
                print("无法提取事件边JSON")
                return []
        except Exception as e:
            print(f"生成事件边失败：{str(e)}")
            return []
    
    def visualize_event_graph(self, event_graph: Dict, output_file: str = "event_graph.html"):
        """
        使用PyVis可视化事件图谱
        
        Args:
            event_graph: 事件图谱数据
            output_file: 输出HTML文件路径
        """
        if not event_graph or "nodes" not in event_graph or "edges" not in event_graph:
            print("事件图谱数据不完整，无法可视化")
            return
        
        # 创建PyVis网络
        net = Network(height="750px", width="100%", bgcolor="white", font_color="black", directed=True)
        
        # 定义事件类型对应的颜色
        type_colors = {
            'Career': '#3498db',      # 蓝色
            'Health': '#2ecc71',       # 绿色
            'Relationships': '#e74c3c', # 红色
            'Education': '#9b59b6',     # 紫色
            'Finance': '#f1c40f',       # 黄色
            'Personal Life': '#1abc9c', # 青色
            'Family&Living Situation': '#34495e' # 深灰色
        }
        
        # 辅助函数：获取标准化的时间字符串
        def get_standard_time(time_data):
            if isinstance(time_data, list) and time_data:
                first_time = time_data[0]
                # 去除"至"，获取开始日期
                if "至" in first_time:
                    return first_time.split("至")[0]
                return first_time
            return "9999-99-99"
        
        # 收集所有节点并按时间排序
        nodes = event_graph["nodes"].copy()
        # 按时间排序节点
        nodes.sort(key=lambda x: get_standard_time(x.get("time", [])))
        
        # 收集所有节点ID
        node_ids = set()
        
        # 提取所有月份并排序
        months = set()
        for node in nodes:
            time = node.get("time", [])
            standard_time = get_standard_time(time)
            if standard_time != "9999-99-99":
                # 提取月份（YYYY-MM）
                month = standard_time[:7]
                months.add(month)
        
        # 排序月份
        sorted_months = sorted(months)
        num_months = len(sorted_months)
        
        # 为每个月份分配横坐标区域
        month_to_x_range = {}
        if num_months > 0:
            # 每个月占50单位宽度
            month_width = 200
            
            for i, month in enumerate(sorted_months):
                # 为每个月份分配固定的横坐标范围
                start_x = 10 + i * (month_width + 10)  # 月份之间留出10单位的间距
                end_x = start_x + month_width
                month_to_x_range[month] = (start_x, end_x)
        
        # 为每个月份的事件分配y坐标
        month_event_count = {}
        for node in nodes:
            time = node.get("time", [])
            standard_time = get_standard_time(time)
            if standard_time != "9999-99-99":
                month = standard_time[:7]
                if month not in month_event_count:
                    month_event_count[month] = 0
                month_event_count[month] += 1
        
        # 计算每个月份内事件的y坐标
        month_event_index = {}
        for month in sorted_months:
            month_event_index[month] = 0
        
        # 添加节点
        for node in nodes:
            node_id = node.get("id", "")
            node_ids.add(str(node_id))  # 确保ID是字符串
            node_name = node.get("name", "")
            node_type = node.get("type", "")
            node_time = node.get("time", [])
            node_description = node.get("description", "")
            
            # 设置节点颜色
            node_color = type_colors.get(node_type, '#95a5a6')  # 默认为灰色
            
            # 设置节点标题（悬停时显示的信息）
            time_display = ", ".join(node_time) if isinstance(node_time, list) else str(node_time)
            node_title = f"ID: {node_id}<br>名称: {node_name}<br>时间: {time_display}<br>类型: {node_type}<br>描述: {node_description}"
            
            # 计算节点位置
            x = 50  # 默认x坐标
            y = 50  # 默认y坐标
            
            standard_time = get_standard_time(node_time)
            if standard_time != "9999-99-99":
                month = standard_time[:7]
                if month in month_to_x_range:
                    # 计算月份区域内的x坐标
                    start_x, end_x = month_to_x_range[month]
                    x = start_x + (end_x - start_x) / 2  # 居中放置
                    
                    # 计算y坐标
                    if month in month_event_count:
                        total_events = month_event_count[month]
                        if total_events > 0:
                            # 垂直排列事件，从顶部开始依次排列
                            fixed_gap = 60
                            # 从顶部开始，留出15单位的上边距
                            start_y = 15
                            
                            # 检查是否为偶数月（2、4、6、8、10、12月）
                            month_num = int(month.split('-')[1]) if '-' in month else 0
                            is_even_month = month_num % 2 == 0
                            
                            # 计算当前事件的y坐标
                            current_index = month_event_index[month]
                            y = start_y + current_index * fixed_gap
                            
                            # 为偶数月的事件增加30的y偏移量
                            if is_even_month:
                                y += 30
                            
                            month_event_index[month] += 1
            
            # 添加节点，减小节点大小
            net.add_node(str(node_id), label=node_name, color=node_color, title=node_title, 
                         shape="box", size=80, font={"size": 12},
                         x=x, y=y, fixed=True)  # 固定节点位置
        
        # 添加边
        edge_count = 0
        for edge in event_graph["edges"]:
            source = edge.get("source", "")
            target = edge.get("target", "")
            edge_type = edge.get("type", "")
            edge_description = edge.get("description", "")
            
            # 确保源节点和目标节点都存在
            if str(source) in node_ids and str(target) in node_ids:
                # 设置边的标题（悬停时显示的信息）
                edge_title = f"关系类型: {edge_type}<br>描述: {edge_description}"
                
                # 添加边
                net.add_edge(str(source), str(target), title=edge_title, color="#888888", width=2, arrowStrikethrough=False)
                edge_count += 1
            else:
                print(f"跳过无效边: 源节点 {source} 或目标节点 {target} 不存在")
        
        print(f"成功添加 {edge_count} 条边")
        
        # 保存为HTML文件
        net.write_html(output_file)
        print(f"事件图谱可视化已保存到：{output_file}")
    
    def save_event_graph(self, event_graph: Dict, output_path: str = "event_graph.json"):
        """
        保存事件图谱到文件
        
        Args:
            event_graph: 事件图谱数据
            output_path: 输出路径，默认为event_graph.json
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(event_graph, f, ensure_ascii=False, indent=2)
            print(f"事件图谱已保存到：{output_path}")
        except Exception as e:
            print(f"保存事件图谱失败：{str(e)}")

    
    def _get_subgraphs(self, event_graph: Dict) -> List[Dict]:
        """
        获取事件图谱中的所有子连通图
        
        Args:
            event_graph: 事件图谱数据
        
        Returns:
            子连通图列表
        """
        if not event_graph or "nodes" not in event_graph or "edges" not in event_graph:
            return []
        
        # 创建无向图用于分析连通性
        G = nx.Graph()
        
        # 添加节点
        for node in event_graph["nodes"]:
            G.add_node(str(node["id"]))
        
        # 添加边（转换为无向边）
        for edge in event_graph["edges"]:
            G.add_edge(str(edge["source"]), str(edge["target"]))
        
        # 找出所有连通分量
        connected_components = list(nx.connected_components(G))
        
        subgraphs = []
        for component in connected_components:
            # 提取子连通图的节点和边
            sub_nodes = [node for node in event_graph["nodes"] if str(node["id"]) in component]
            sub_edges = [edge for edge in event_graph["edges"] if 
                        str(edge["source"]) in component and str(edge["target"]) in component]
            
            if sub_nodes:
                subgraphs.append({
                    "nodes": sub_nodes,
                    "edges": sub_edges
                })
        
        return subgraphs
    
    def _analyze_and_decompose_subgraphs(self, subgraphs: List[Dict]) -> List[Dict]:
        """
        并行分析节点数前三多的子连通图的主题相关性，如果主题过多则分解为新的连通图
        
        Args:
            subgraphs: 子连通图列表
        
        Returns:
            分解后的子连通图列表
        """
        import concurrent.futures
        
        # 按节点数排序，选择节点数最多的前 3 个子连通图
        sorted_subgraphs = sorted(subgraphs, key=lambda x: len(x.get("nodes", [])), reverse=True)
        top_3_subgraphs = sorted_subgraphs[:3]
        remaining_subgraphs = [s for s in subgraphs if s not in top_3_subgraphs]
        
        print(f"开始分析节点数前三多的子连通图（共{len(top_3_subgraphs)}个）...")
        for i, sg in enumerate(top_3_subgraphs, 1):
            print(f"  Top{i}: {len(sg.get('nodes', []))}个节点")
        
        decomposed_subgraphs = []
        
        def analyze_subgraph_theme(subgraph):
            """分析单个子连通图的主题并判断是否需要分解"""
            prompt = f"""
            你是一位专业的事件图谱分析专家，请分析以下子连通图的主题构成。
            
            子连通图数据：
            {json.dumps(subgraph, ensure_ascii=False, indent=2)}
            
            分析要求：
            1. 识别该子连通图包含的主要主题（如职业发展、健康生活、人际关系、学习教育等）
            2. 判断主题是否过于复杂或分散
            3. 如果需要分解，请按主题将节点分组到不同的新连通图中
            4. 每个新连通图应该聚焦于一个明确的主题
            5. **重要：必须确保所有节点都被分配到某个主题组中，不能遗漏任何一个节点！**
            6. 请检查您的分组是否包含了原始子连通图中的所有节点
            
            输出格式：
            仅返回 JSON 格式，包含：
            {{
                "themes": ["主题 1", "主题 2", ...],  // 识别出的主题列表
                "need_decompose": true/false,  // 是否需要分解
                "decompose_groups": [  // 如果需要分解，按主题分组节点
                    {{
                        "theme": "主题名称",
                        "node_ids": ["节点 ID1", "节点 ID2", ...]  // 属于该主题的节点 ID 列表
                        
                    }}
                ]
            }}
            """
            
            try:
                response = llm_call_reason_j(prompt).strip()
                # 提取 JSON 部分
                start_idx = response.find('{')
                end_idx = response.rfind('}')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_response = response[start_idx:end_idx + 1]
                    result = json.loads(json_response)
                    return subgraph, result
                else:
                    print("无法提取主题分析 JSON")
                    return subgraph, {"themes": ["未分类"], "need_decompose": False}
            except Exception as e:
                print(f"分析子连通图主题失败：{str(e)}")
                return subgraph, {"themes": ["错误"], "need_decompose": False}
        
        # 并行分析节点数前三多的子连通图
        print(f"\n开始并行分析前 3 个子连通图...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_subgraph = {executor.submit(analyze_subgraph_theme, subgraph): subgraph 
                                 for subgraph in top_3_subgraphs}
            
            processed_count = 0
            for future in concurrent.futures.as_completed(future_to_subgraph):
                subgraph, analysis = future.result()
                processed_count += 1
                
                if analysis.get("need_decompose", False) and analysis.get("decompose_groups"):
                    # 需要分解，为每个主题创建新的子连通图
                    decompose_groups = analysis["decompose_groups"]
                    print(f"\n[处理第{processed_count}个子图] 需要分解为{len(decompose_groups)}个主题：{[g['theme'] for g in decompose_groups]}")
                    
                    # 收集所有已分配的节点 ID
                    assigned_node_ids = set()
                    
                    for group in decompose_groups:
                        theme_nodes = [node for node in subgraph["nodes"] 
                                      if str(node["id"]) in group["node_ids"]]
                        
                        if theme_nodes:
                            # 提取该主题内部的边
                            theme_node_ids = set(group["node_ids"])
                            assigned_node_ids.update(theme_node_ids)  # 记录已分配的节点
                            theme_edges = [edge for edge in subgraph.get("edges", []) 
                                          if str(edge["source"]) in theme_node_ids 
                                          and str(edge["target"]) in theme_node_ids]
                            
                            new_subgraph = {
                                "nodes": theme_nodes,
                                "edges": theme_edges,
                                "theme": group["theme"]
                            }
                            decomposed_subgraphs.append(new_subgraph)
                    
                    # 检查是否有未被分配的节点
                    all_node_ids = {str(node["id"]) for node in subgraph["nodes"]}
                    unassigned_node_ids = all_node_ids - assigned_node_ids
                    
                    if unassigned_node_ids:
                        print(f"   ⚠️  发现{len(unassigned_node_ids)}个未分配的节点，LLM 分解结果不完整，拒绝分解")
                        print(f"   → 保持原子连通图不变（当前共有{len(decomposed_subgraphs)}个子图）")
                        # 保持原子连通图不变
                        themes = analysis.get("themes", ["未分类"])
                        subgraph["theme"] = themes[0] if themes else "未分类"
                        decomposed_subgraphs.append(subgraph)
                    else:
                        print(f"   ✓ 所有节点都已正确分配，原{len(subgraph['nodes'])}个节点的子图被分解为{len(decompose_groups)}个子图（当前共有{len(decomposed_subgraphs)}个子图）")
                else:
                    # 不需要分解，保持原子连通图
                    themes = analysis.get("themes", ["未分类"])
                    subgraph["theme"] = themes[0] if themes else "未分类"
                    decomposed_subgraphs.append(subgraph)
                    print(f"\n[处理第{processed_count}个子图] 主题：{themes}，无需分解（当前共有{len(decomposed_subgraphs)}个子图）")
        
        # 添加剩余的子连通图（第 4 个及以后）
        decomposed_subgraphs.extend(remaining_subgraphs)
        
        print(f"分解统计：前 3 个子图处理后得到{len(decomposed_subgraphs) - len(remaining_subgraphs)}个 + 剩余{len(remaining_subgraphs)}个 = 共{len(decomposed_subgraphs)}个子连通图")
        
        # 为每个子连通图添加主题标签
        for subgraph in decomposed_subgraphs:
            if "theme" not in subgraph:
                subgraph["theme"] = "未分类"
        
        print(f"分解完成，共有{len(decomposed_subgraphs)}个子连通图")
        return decomposed_subgraphs
    

    def _parallel_analyze_subgraphs(self, subgraphs: List[Dict]) -> List[Dict]:
        """
        并行分析优化子连通图
            
        Args:
            subgraphs: 子连通图列表
            
        Returns:
            优化后的子连通图列表
        """
        import concurrent.futures
            
        optimized_subgraphs = []
            
        def analyze_subgraph(subgraph):
            """分析单个子连通图"""
            # 为子连通图生成分析提示
            prompt = f"""
            你是一位专业的事件分析专家，请分析以下子连通图并给出总结。
                
            子连通图数据：
            {json.dumps(subgraph, ensure_ascii=False, indent=2)}
                
            分析要求：
            1. 分析子连通图中事件的主题和关联性
            2. 为子连通图提供一个总结，概括主要内容和意义以及其中的主要事件
            3. 保持时间顺序的正确性
                
            输出格式：
            仅返回 JSON 格式，包含 summary（总结）
            示例：
            {{ 
                "summary": "这个子连通图描述了项目启动与健身计划之间的关系..."
            }}
            """
                
            try:
                response = llm_call_j(prompt).strip()
                print(f"分析结果：{response}")
                # 提取 JSON 部分
                start_idx = response.find('{')
                end_idx = response.rfind('}')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_response = response[start_idx:end_idx + 1]
                    result = json.loads(json_response)
                    # 只添加总结，不修改边
                    subgraph["summary"] = result.get("summary", "")
                return subgraph
            except Exception as e:
                print(f"分析子连通图失败：{str(e)}")
                return subgraph
            
        # 并行处理子连通图
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_subgraph = {executor.submit(analyze_subgraph, subgraph): subgraph for subgraph in subgraphs}
            for future in concurrent.futures.as_completed(future_to_subgraph):
                optimized_subgraph = future.result()
                optimized_subgraphs.append(optimized_subgraph)
            
        return optimized_subgraphs
    
    def _regenerate_edges_for_subgraphs(self, merged_subgraphs: List[Dict]) -> Dict:
        """
        对每个子图并行重生成（可能需要扩展节点），然后重生成边
        
        Args:
            merged_subgraphs: 合并后的子图列表
        
        Returns:
            重生成后的事件图谱
        """
        import concurrent.futures
        
        print(f"开始重生成{len(merged_subgraphs)}个子图...")
        
        # 筛选出节点数大于 1 的子图
        multi_node_subgraphs = [sg for sg in merged_subgraphs if len(sg.get("nodes", [])) > 1]
        single_node_subgraphs = [sg for sg in merged_subgraphs if len(sg.get("nodes", [])) <= 1]
        
        print(f"  - 多节点子图：{len(multi_node_subgraphs)}个（需要重生成）")
        print(f"  - 单节点子图：{len(single_node_subgraphs)}个（无需重生成）")
        
        regenerated_subgraphs = []
        
        def process_subgraph(subgraph):
            """处理单个子连通图：可能需要扩展节点，然后重生成边"""
            nodes = subgraph.get("nodes", [])
            
            node_count = len(nodes)
            theme = subgraph.get("theme", "未知主题")
            summary = subgraph.get("summary", "")
            
            # # 如果节点数少于 20，思考是否需要扩展
            # if node_count < 20:
            #     print(f"  子图有{node_count}个节点（<{20}），思考是否需要扩展...")
            #     extended_nodes = self._think_and_expand_nodes(nodes, theme, summary)
            #     if extended_nodes:
            #         print(f"  ✓ 扩展了{len(extended_nodes)}个新节点")
            #         # 添加新节点到子图
            #         existing_ids = set(node["id"] for node in nodes)
            #         for new_node in extended_nodes:
            #             if new_node["id"] not in existing_ids:
            #                 nodes.append(new_node)
            #         print(f"  现在共有{len(nodes)}个节点")
            
            # 构建临时事件数据用于生成边
            events_data = []
            for node in nodes:
                events_data.append({
                    "id": node.get("id", ""),
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                    "date": node.get("time", []),
                    "type": node.get("type", "")
                })
            
            # 调用 LLM 生成边
            print(f"  为{len(nodes)}个节点的子图重生成边...")
            new_edges = self._generate_edges_with_llm(events_data)
            
            # 更新子图的边和节点
            subgraph["edges"] = new_edges
            subgraph["nodes"] = nodes
            print(f"  ✓ 生成了{len(new_edges)}条边")
            return subgraph
        
        # 并行处理所有多节点子图
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_subgraph = {executor.submit(process_subgraph, subgraph): subgraph 
                                 for subgraph in multi_node_subgraphs}
            
            for future in concurrent.futures.as_completed(future_to_subgraph):
                regenerated_subgraph = future.result()
                regenerated_subgraphs.append(regenerated_subgraph)
        
        # 合并所有子图（包括单节点子图）
        final_subgraphs = regenerated_subgraphs + single_node_subgraphs
        
        print(f"\n合并子图统计：")
        print(f"  - 重生成后的多节点子图：{len(regenerated_subgraphs)}个")
        print(f"  - 单节点子图：{len(single_node_subgraphs)}个")
        print(f"  - 总计：{len(final_subgraphs)}个子图")
        
        # 构建最终的事件图谱
        final_nodes = []
        final_edges = []
        node_ids = set()
        
        # 先添加多节点子图的节点和边
        for subgraph in regenerated_subgraphs:
            for node in subgraph.get("nodes", []):
                if node["id"] not in node_ids:
                    final_nodes.append(node)
                    node_ids.add(node["id"])
            final_edges.extend(subgraph.get("edges", []))
        
        print(f"\n多节点子图贡献：{len([n for sg in regenerated_subgraphs for n in sg.get('nodes', [])])}个节点，{len([e for sg in regenerated_subgraphs for e in sg.get('edges', [])])}条边")
        
        # 再添加单节点子图的节点（没有边）
        single_node_count = 0
        for subgraph in single_node_subgraphs:
            for node in subgraph.get("nodes", []):
                if node["id"] not in node_ids:
                    final_nodes.append(node)
                    node_ids.add(node["id"])
                    single_node_count += 1
        
        print(f"单节点子图贡献：{single_node_count}个节点")
        print(f"\n最终统计：共{len(final_nodes)}个节点，{len(final_edges)}条边")
        
        print(f"✓ 子图重生成完成，共{len(final_nodes)}个节点，{len(final_edges)}条边")
        
        return {
            "nodes": final_nodes,
            "edges": final_edges
        }
    
    def _think_and_expand_nodes(self, existing_nodes: List[Dict], theme: str, summary: str) -> List[Dict]:
        """
        思考是否需要扩展子图的节点，使其更丰富完整
        
        Args:
            existing_nodes: 现有节点列表
            theme: 子图主题
            summary: 子图总结
        
        Returns:
            新生成的节点列表
        """
        prompt = f"""
你是一位专业的事件图谱完善专家，请分析以下子图并思考是否需要扩展新的事件节点。

子图主题：{theme}

子图总结：{summary}

现有事件节点（共{{len(existing_nodes)}}个）：
{{json.dumps(existing_nodes, ensure_ascii=False, indent=2)}}

**核心任务：识别关键节点并进行多步持续扩展，丰富已有事件的发展脉络**

**需要扩展的两种情况：**

1. **未完待续的节点**：只有开始没有后续的事件
   - 例："结识新朋友" → 应有互动、合作、共同经历等后续
   - 例："学习技能" → 应有学习过程、成果、应用实践等后续
   - 例："启动项目" → 应有进展、挑战、成果、收获等后续

2. **可能产生多分支影响的节点**：重要事件引发的多个发展方向
   - 例："换工作" → 工作适应线、人际关系线、生活变化线

**分析流程：**

**第一步：判断是否需要扩展**
以下情况**不扩展**：
- 一次性事件（如参加会议、参观展览）
- 特定日期的纪念性事件（如生日庆祝、节日活动）
- 已经完整的事件链（已有起因 - 经过 - 结果）

**第二步：寻找关键节点并多步扩展**
检查现有节点，思考：
1. 哪些节点只有开始没有后续？应该有哪些自然发展？
2. 哪些节点可能产生多方面影响？会在哪些方向产生新事件？
3. 哪些重要人物或关系值得展开？可能有哪些互动和发展？
4. 哪些项目或计划需要补充过程？是否有缺失的关键环节？
5. 哪些节点可以进一步推理制造因果（如比赛获奖→被邀请分享经验）？

**多步扩展策略：**
- **线性延续**：沿明确发展脉络持续扩展（学习 Python→完成课程→做项目→参与开源→社区分享）
- **阶段性发展**：划分不同阶段，每阶段有标志性事件（健身计划→适应期→提升期→突破期→维持期）
- **关系深化**：展现从初识到深交的过程（认识朋友→第一次聚餐→一起活动→成为好友→定期聚会->经历某个重要事件）
- **项目演进**：清晰的里程碑和关键节点（创业项目→调研→设计→组建→上线→反馈）

**设计要求：**
1. **逻辑连贯**：新事件应从前序事件自然发展而来
2. **体现多样性**：同一起始点可有多条不同发展线索
3. **丰富但不冗余**：每个新事件都有独特性和必要性
4. **时间合理**：安排在 2025 年合理范围内，注意季节性
5. **分布均衡**：各个月份都有适当事件，平均分布
6. **持续推进**：设计完整发展链条
7. **创作新增**：发挥想象力，基于某事件开辟新的发展方向或主题（一定要有基于的事件然后逐步推理扩展）
   - **创造新机会**：分析事件可能带来的意外机遇（如比赛获奖→被媒体报道→收到合作邀请）
   - **开辟新领域**：从原有事件延伸到全新领域（如学习编程→对 AI 产生兴趣→参加 AI 黑客松→创立科技社群）
   - **引入新人物**：因某事件结识全新圈子的人（如健身→认识艺术家→参与艺术展览→跨界合作）
   - **触发新兴趣**：偶然发现新的爱好或热情所在（如陪同朋友参加面试→对心理学产生兴趣→系统学习→成为志愿者咨询师）
**原则：**
- 聚焦重要人物、关系、项目、计划的延续性发展
- 展现因果关联和演化脉络
- 让孤立事件形成有机整体
- **重点**：深度挖掘已有事件潜力，不添加无关新事件
- **目标**：每条重要事件线都有始有终，展现完整轨迹

输出格式：
仅返回 JSON 格式：
{{
    "need_expand": true/false,
    "reason": "解释为什么扩展或不扩展，说明识别到的关键节点及如何多步扩展到 12 月",
    "new_nodes": [
        {{
            "id": "新 ID（整数，从 10000 开始）",
            "name": "事件名称",
            "description": "详细描述（体现与前序事件的关联，说明该阶段特点和发展线中的位置）",
            "type": "事件类型",
            "time": ["YYYY-MM-DD 格式的起止时间"]
        }}
    ]
}}
        """
        
        try:
            response = llm_call_j(prompt).strip()
            # 提取 JSON 部分
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = response[start_idx:end_idx + 1]
                result = json.loads(json_response)
                
                if result.get("need_expand", False):
                    new_nodes = result.get("new_nodes", [])
                    print(f"    扩展原因：{result.get('reason', '')}")
                    return new_nodes
                else:
                    print(f"    不扩展原因：{result.get('reason', '')}")
                    return []
            else:
                print("    无法解析扩展建议，保持原样")
                return []
        except Exception as e:
            print(f"    思考扩展失败：{str(e)}")
            return []
    
    def _analyze_merge_subgraphs(self, optimized_subgraphs: List[Dict], original_graph: Dict) -> List[Dict]:
        """
        分析是否需要合并子连通图
        
        Args:
            optimized_subgraphs: 优化后的子连通图列表
            original_graph: 原始事件图谱
        
        Returns:
            合并后的子图列表
        """
        print(f"\n开始分析合并子图，当前有{len(optimized_subgraphs)}个子图...")
        # 提取每个子连通图的summary
        subgraph_summaries = []
        for i, subgraph in enumerate(optimized_subgraphs):
            subgraph_summaries.append({
                "id": i,
                "summary": subgraph.get("summary", "")
            })
        
        # 为初步分析生成提示，只使用summary
        prompt = f"""
        你是一位专业的事件图谱分析专家，请分析以下子连通图的摘要，判断是否需要合并某些子连通图。
        
        子连通图摘要：
        {json.dumps(subgraph_summaries, ensure_ascii=False, indent=2)}
        
        分析要求：
        1. 分析各个子连通图的主题和内容
        2. 判断是否存在主题相关、内容相似或有潜在关联的子连通图
        3. 对于需要合并的子连通图，指出它们的ID，每组合并的子连通图应该是主题相关（可能是部分的主题或事件有关联）的
        4. 保持时间顺序的正确性
        5. 确保合并后的图谱结构清晰合理
        
        输出格式：
        仅返回JSON格式，包含以下字段：
        {{ 
            "need_merge": true/false,
            "merge_groups": [[0, 1], [2, 3]],  // 需要合并的子连通图ID组
            "reason": "合并原因"
        }}
        """
        
        try:
            # 初步分析是否需要合并
            response = llm_call_reason_j(prompt).strip()
            print(f"初步分析结果：{response}")
            # 提取 JSON 部分
            start_idx = response.find('{')
            end_idx = response.rfind('}')
                    
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = response[start_idx:end_idx + 1]
                merge_decision = json.loads(json_response)
                        
                need_merge = merge_decision.get("need_merge", False)
                merge_groups = merge_decision.get("merge_groups", [])
                        
                if need_merge and merge_groups:
                    print(f"识别到{len(merge_groups)}组合并的子系统")
                    for i, group in enumerate(merge_groups):
                        print(f"  组合{i+1}: 子图{group}")
                    
                    # 实际合并需要合并的子图
                    merged_subgraphs = []
                    used_indices = set()
                    
                    # 处理每个合并组
                    for group in merge_groups:
                        if not group:
                            continue
                        
                        # 合并该组的所有子图
                        merged_nodes = []
                        merged_edges = []
                        themes = []
                        summaries = []
                        node_ids = set()
                        
                        for idx in group:
                            if 0 <= idx < len(optimized_subgraphs):
                                subgraph = optimized_subgraphs[idx]
                                
                                # 合并节点（去重）
                                for node in subgraph.get("nodes", []):
                                    if node["id"] not in node_ids:
                                        merged_nodes.append(node)
                                        node_ids.add(node["id"])
                                
                                # 合并所有边
                                merged_edges.extend(subgraph.get("edges", []))
                                
                                # 收集主题和 summary
                                if subgraph.get("theme"):
                                    themes.append(subgraph.get("theme", ""))
                                if subgraph.get("summary"):
                                    summaries.append(subgraph.get("summary", ""))
                                
                                used_indices.add(idx)
                        
                        # 创建合并后的子图
                        merged_subgraphs.append({
                            "nodes": merged_nodes,
                            "edges": merged_edges,
                            "theme": " + ".join(themes) if themes else "",
                            "summary": "。".join(summaries) if summaries else ""
                        })
                    
                    # 添加未参与合并的子图
                    for i, subgraph in enumerate(optimized_subgraphs):
                        if i not in used_indices:
                            merged_subgraphs.append({
                                "nodes": subgraph["nodes"],
                                "edges": subgraph["edges"],
                                "theme": subgraph.get("theme", ""),
                                "summary": subgraph.get("summary", "")
                            })
                    
                    print(f"✓ 合并完成：共{len(merged_subgraphs)}个子图（合并了{len(merge_groups)}组）")
                    return merged_subgraphs
                else:
                    print("无需合并子图")
            else:
                print("无法提取合并分析结果，直接组合所有子图")
        except Exception as e:
            print(f"分析合并子连通图失败：{str(e)}，直接组合所有子图")
                
        # 如果没有合并或出错，直接返回所有子图
        merged_subgraphs = []
        
        for subgraph in optimized_subgraphs:
            merged_subgraphs.append({
                "nodes": subgraph["nodes"],
                "edges": subgraph["edges"],
                "theme": subgraph.get("theme", ""),
                "summary": subgraph.get("summary", "")
            })
        
        print(f"组合完成：共{len(merged_subgraphs)}个子图")
        
        return merged_subgraphs
    
    def _dfs_chain(self, G: nx.DiGraph, current_node: str, node_dict: Dict, current_chain: List[Dict], 
                   visited: set, chains: List[List[Dict]]):
        """
        深度优先搜索找到链条
        
        Args:
            G: 有向图
            current_node: 当前节点ID
            node_dict: 节点字典
            current_chain: 当前链条
            visited: 已访问节点
            chains: 链条列表
        """
        if current_node in visited:
            # 如果节点已在当前链条中，说明形成了环
            if current_node in [n.get("id") for n in current_chain]:
                # 找到环的起点
                idx = [n.get("id") for n in current_chain].index(current_node)
                # 添加环作为链条
                cycle_chain = current_chain[idx:]
                if cycle_chain:
                    chains.append(cycle_chain)
            return
        
        # 添加当前节点到链条
        node = node_dict.get(current_node)
        if node:
            current_chain.append(node)
            visited.add(current_node)
            
            # 获取所有后继节点
            successors = list(G.successors(current_node))
            
            if not successors:
                # 没有后继节点，链条结束
                if current_chain:
                    chains.append(current_chain.copy())
            else:
                # 有多个后继节点，分叉为多个链条
                for succ in successors:
                    self._dfs_chain(G, succ, node_dict, current_chain.copy(), visited, chains)
            
            # 回溯
            current_chain.pop()
    
    def insert_events(self, insertion_suggestion: str, start_date: str = None) -> Dict:
        """
        基于输入的插入建议，通过 LLM 分析并插入新事件到现有事件图中
        
        Args:
            insertion_suggestion: 插入建议文本，描述需要添加的事件
            start_date: 起始日期（YYYY-MM-DD 或 YYYY-MM 格式），只分析此日期之后的月份
        
        Returns:
            更新后的事件图谱
        """
        # 使用 GraphRefiner 执行事件插入流程
        from event.draft.GraphRefiner import GraphRefiner
        
        refiner = GraphRefiner(
            event_graph=self.event_graph,
            yearly_summary=self.yearly_summary if hasattr(self, 'yearly_summary') else None
        )
        
        updated_graph = refiner.insert_events(insertion_suggestion, start_date)
        
        # 更新实例属性
        self.event_graph = updated_graph
        
        return updated_graph

    

    
