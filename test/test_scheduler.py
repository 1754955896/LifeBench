import os
import json
from event.scheduler import Scheduler
# 加载persona文件
persona_path = "data/xujing/persona.json"
if os.path.exists(persona_path):
    with open(persona_path, "r", encoding="utf-8") as f:
        persona_data = json.load(f)
    print("成功加载persona文件")
else:
    print("persona文件不存在")
    persona_data = {}

#创建调度器实例
file_path = "output/"
scheduler = Scheduler(persona=persona_data, file_path=file_path)


# #res = scheduler.extract_important_nodes(persona_data)
# with open("output/new/test8.json", "r", encoding="utf-8") as f:
#          analysis = json.load(f)
# analysis = analysis["analysis_results"]
# with open("output/new/test9.json", "r", encoding="utf-8") as f:
#     event = json.load(f)
# #res = scheduler.generate_and_insert_events(analysis['timeline_data'], analysis['events_by_theme'])
#res = scheduler.parallel_daily_event_refine(analysis,persona_data,event,'output/newnew')
scheduler.generate_yearly_timeline_draft(persona_data,'output/xujing')
# with open("output/new/test9.json", "w", encoding="utf-8") as f:
#         json.dump(res, f, ensure_ascii=False, indent=4)

# from event.scheduler import EventTree
#
# # 使用加载的persona数据初始化EventTree
# e = EventTree(json.dumps(persona_data, ensure_ascii=False))
#
# # 创建测试事件列表
# test_events = [
#     {
#         "event_id": "1",
#         "name": "2025年1月项目开发",
#         "date": ["2025-01-01至2025-01-31"],
#         "type": "Career",
#         "description": "2025年1月进行的软件项目开发工作",
#         "participant": [{"name": "马小枚", "relation": "自己"}],
#         "location": "北京市-公司",
#         "decompose": 1
#     },
#     {
#         "event_id": "2",
#         "name": "2025年1月健身计划",
#         "date": ["2025-01-01至2025-01-31"],
#         "type": "Health",
#         "description": "2025年1月的健身计划",
#         "participant": [{"name": "马小枚", "relation": "自己"}],
#         "location": "北京市-健身房",
#         "decompose": 1
#     },
#     {
#         "event_id": "3",
#         "name": "2025年1月阅读计划",
#         "date": ["2025-01-01至2025-01-31"],
#         "type": "Personal Life",
#         "description": "2025年1月的阅读计划",
#         "participant": [{"name": "马小枚", "relation": "自己"}],
#         "location": "北京市-家中",
#         "decompose": 1
#     }
# ]
#
# # 调用event_decomposer方法分解事件
# try:
#     # 结果将保存到test_output目录
#     e.event_decomposer(events=test_events, file="test_output", max_workers=4)
#     print("\n事件分解测试成功完成！")
# except Exception as ex:
#     print(f"\n事件分解测试失败：{str(ex)}")
#     import traceback
#     traceback.print_exc()

# scheduler.generate_yearly_timeline_draft(persona_data,'output/new')
#检查文件是否存在
# if os.path.exists("output/new/all_months_analysis_20260113134815_updated.json"):
#     with open("output/new/all_months_analysis_20260113134815_updated.json", "r", encoding="utf-8") as f:
#         analysis = json.load(f)
# else:
#     print("文件不存在: output/new/all_months_analysis_20260113134815_updated.json")
#     timeline = None
# if os.path.exists("output/new/event_decompose_dfs.json"):
#     with open("output/new/event_decompose_dfs.json", "r", encoding="utf-8") as f:
#        timeline = json.load(f)
# else:
#     print("文件不存在: output/new/event_decompose_dfs.json")
#     timeline = None
# scheduler.parallel_daily_event_refine(analysis,persona_data, timeline, "output/new/refine/")
#scheduler.monthly_analysis(timeline,persona_data,'output/new')
# # 检查是否存在保存的重要节点结果
# if os.path.exists(important_nodes_file):
#     print("\n检测到已保存的重要节点结果，正在读取...")
#     try:
#         with open(important_nodes_file, "r", encoding="utf-8") as f:
#             important_nodes = json.load(f)
#         print("成功读取已保存的重要节点结果！")
#     except Exception as e:
#         print(f"读取已保存的重要节点结果失败：{str(e)}")
#         important_nodes = None
#
# # 如果没有保存的结果，则重新生成
# if important_nodes is None:
#     print("\n开始测试extract_important_nodes方法...")
#     if persona_data:
#         try:
#             important_nodes = scheduler.extract_important_nodes(persona=persona_data)
#             print("重要节点提取测试成功！结果：")
#             print(json.dumps(important_nodes, ensure_ascii=False, indent=2))
#
#             # 保存重要节点结果
#             print("\n正在保存重要节点结果到文件...")
#             try:
#                 # 确保output目录存在
#                 os.makedirs("output", exist_ok=True)
#                 with open(important_nodes_file, "w", encoding="utf-8") as f:
#                     json.dump(important_nodes, f, ensure_ascii=False, indent=2)
#                 print(f"重要节点结果已成功保存到{important_nodes_file}")
#             except Exception as e:
#                 print(f"保存重要节点结果失败：{str(e)}")
#         except Exception as e:
#             print(f"重要节点提取测试失败：{str(e)}")
#             import traceback
#             traceback.print_exc()
#
#
# # 测试generate_event_timeline方法（多线程版本）
# if important_nodes is not None:
#     # 检查是否已有事件时间线文件
#     output_file = "output/event_timelines.json"
#     if not os.path.exists(output_file):
#         print("\n开始测试generate_event_timeline方法（多线程版本）...")
#         try:
#             # 测试多线程功能，设置max_workers=4
#             event_timelines = scheduler.generate_event_timeline(important_nodes, max_workers=4)
#             print("事件变动时间线生成测试成功！结果：")
#
#             # 验证返回结果格式
#             if not isinstance(event_timelines, dict):
#                 raise TypeError("返回结果应为字典类型")
#
#             for event_type, topic_timelines in event_timelines.items():
#                 print(f"\n=== {event_type} 主题时间线 ===")
#
#                 # 验证主题时间线为列表类型
#                 if not isinstance(topic_timelines, list):
#                     raise TypeError(f"{event_type}的主题时间线应为列表类型")
#
#                 # 遍历每个主题时间线
#                 for i, timeline in enumerate(topic_timelines, 1):
#                     print(f"\n主题 {i}: {timeline.get('topic', '未知主题')}")
#                     print(f"详细描述: {timeline.get('detailed_description', '无')}")
#
#                     # 输出月度描述
#                     print("月度描述:")
#                     for month_desc in timeline.get('monthly_description', []):
#                         print(f"  {month_desc.get('month', '未知月份')}:")
#                         print(f"    内容: {month_desc.get('content', '无')}")
#                         print(f"    影响: {month_desc.get('impact', '无')}")
#                         print(f"    核心事件: {', '.join(month_desc.get('core_events', []))}")
#         except Exception as e:
#             print(f"事件变动时间线生成测试失败：{str(e)}")
#             import traceback
#             traceback.print_exc()
#     else:
#         print(f"\n事件时间线文件 {output_file} 已存在，跳过generate_event_timeline测试")
# else:
#     print("\n重要节点数据为空，无法测试事件变动时间线生成")
#
# # 测试save_event_timelines方法
# if important_nodes is not None:
#     # 检查是否已有事件时间线文件
#     output_file = "output/event_timelines.json"
#     if not os.path.exists(output_file):
#         print("\n开始测试save_event_timelines方法...")
#         try:
#             if 'event_timelines' in locals():
#                 # 保存基本时间线（直接保存主题时间线，不再包含冲突消解和时间线统一结果）
#                 scheduler.save_event_timelines(event_timelines, output_file)
#                 print(f"事件时间线已成功保存到 {output_file}")
#
#                 # 额外保存每个事件类型的主题时间线
#                 for event_type, topic_timelines in event_timelines.items():
#                     event_type_file = f"output/event_timelines_{event_type.replace('&', '_and').replace(' ', '_')}.json"
#                     scheduler.save_event_timelines({event_type: topic_timelines}, event_type_file)
#                     print(f"{event_type}主题时间线已成功保存到 {event_type_file}")
#
#             else:
#                 print("需要先生成事件时间线，才能测试保存功能")
#         except Exception as e:
#             print(f"保存事件时间线测试失败：{str(e)}")
#             import traceback
#             traceback.print_exc()
#     else:
#         print(f"\n事件时间线文件 {output_file} 已存在，跳过save_event_timelines测试")
#
# # 测试merge_similar_timelines方法（不分类别）
# import os
# merged_output_file = "output/merged_from_file_event_timelines.json"
# if important_nodes is not None:
#     if not os.path.exists(merged_output_file):
#         print("\n开始测试merge_similar_timelines方法（不分类别）...")
#         try:
#             if 'event_timelines' in locals():
#                 # 调用merge_similar_timelines方法合并相似主题时间线
#                 merged_timelines = scheduler.merge_similar_timelines(event_timelines)
#                 print("相似主题时间线合并测试成功！结果：")
#
#                 # 验证返回结果格式
#                 if not isinstance(merged_timelines, list):
#                     raise TypeError("返回结果应为列表类型")
#
#                 # 计算原始时间线总数
#                 original_total = sum(len(timelines) for timelines in event_timelines.values())
#
#                 # 输出合并前后的数量对比
#                 print(f"\n合并前后主题时间线数量对比：")
#                 print(f"所有类别总计: {original_total} → {len(merged_timelines)} ({'减少' if len(merged_timelines) < original_total else '不变'})")
#
#                 # 输出合并后的详细信息
#                 print(f"\n=== 合并后主题时间线 ===")
#
#                 # 遍历每个主题时间线
#                 for i, timeline in enumerate(merged_timelines[:10], 1):  # 只输出前10个以避免输出过多
#                     print(f"\n主题 {i}: {timeline.get('topic', '未知主题')}")
#                     print(f"详细描述: {timeline.get('detailed_description', '无')[:200]}...")
#
#                 if len(merged_timelines) > 10:
#                     print(f"\n... 还有{len(merged_timelines) - 10}个主题时间线未显示")
#
#                 # 保存合并后的时间线
#                 import json
#                 import os
#                 os.makedirs(os.path.dirname(merged_output_file), exist_ok=True)
#                 with open(merged_output_file, 'w', encoding='utf-8') as f:
#                     json.dump(merged_timelines, f, ensure_ascii=False, indent=2)
#                 print(f"\n合并后的事件时间线已成功保存到 {merged_output_file}")
#
#             else:
#                 print("需要先生成事件时间线，才能测试相似主题合并功能")
#         except Exception as e:
#             print(f"相似主题时间线合并测试失败：{str(e)}")
#             import traceback
#             traceback.print_exc()
#     else:
#         print(f"\n合并后的时间线文件 {merged_output_file} 已存在，跳过merge_similar_timelines测试")
#         # 从文件读取已有的合并时间线，以便后续测试使用
#         import json
#         with open(merged_output_file, 'r', encoding='utf-8') as f:
#             merged_timelines = json.load(f)
# else:
#     print("\n重要节点数据为空，无法测试相似主题时间线合并")
#
# # 测试optimize_merged_timelines方法
# if important_nodes is not None:
#     optimized_output_file = "output/optimized_event_timelines.json"
#     if not os.path.exists(optimized_output_file):
#         print("\n开始测试optimize_merged_timelines方法...")
#         try:
#             if 'merged_timelines' in locals() and merged_timelines:
#                 # 调用optimize_merged_timelines方法优化合并后的时间线
#                 optimized_timelines = scheduler.optimize_merged_timelines(merged_timelines)
#                 print("时间线优化测试成功！")
#
#                 # 验证返回结果格式
#                 if not isinstance(optimized_timelines, list):
#                     raise TypeError("返回结果应为列表类型")
#
#                 # 输出优化前后的数量对比
#                 print(f"\n优化前后时间线数量对比：")
#                 print(f"合并后: {len(merged_timelines)} → 优化后: {len(optimized_timelines)}")
#
#                 # 输出优化后的详细信息
#                 print(f"\n=== 优化后主题时间线 ===")
#
#                 # 遍历每个主题时间线
#                 for i, timeline in enumerate(optimized_timelines[:5], 1):  # 只输出前5个以避免输出过多
#                     print(f"\n主题 {i}: {timeline.get('topic', '未知主题')}")
#                     print(f"详细描述: {timeline.get('detailed_description', '无')[:250]}...")
#
#                 if len(optimized_timelines) > 5:
#                     print(f"\n... 还有{len(optimized_timelines) - 5}个主题时间线未显示")
#
#                 # 保存优化后的时间线
#                 import json
#                 import os
#
#                 os.makedirs(os.path.dirname(optimized_output_file), exist_ok=True)
#                 with open(optimized_output_file, 'w', encoding='utf-8') as f:
#                     json.dump(optimized_timelines, f, ensure_ascii=False, indent=2)
#                 print(f"\n优化后的事件时间线已成功保存到 {optimized_output_file}")
#         except Exception as e:
#             print(f"时间线优化测试失败：{str(e)}")
#             import traceback
#             traceback.print_exc()
#     else:
#         gi_file = "output/gi.json"
#         if not os.path.exists(gi_file):
#             print(f"\n优化后的时间线文件 {optimized_output_file} 已存在，跳过optimize_merged_timelines测试")
#             data = []
#             with open(optimized_output_file, 'r', encoding='utf-8') as f:
#                 data = json.load(f)
#             res = scheduler.generate_and_insert_events(data[-1])
#             with open('output/gi.json', 'w', encoding='utf-8') as f:
#                 json.dump(res, f, ensure_ascii=False, indent=2)
#         else:
#             print(f"\nGI文件 {gi_file} 已存在，跳过event测试")
# if not os.path.exists('output/gi2.json'):
#     with open('output/gi.json', 'r', encoding='utf-8') as f:
#         data = json.load(f)
#     res = scheduler.monthly_event_planning(data)
#     with open('output/gi2.json', 'w', encoding='utf-8') as f:
#         json.dump(res, f, ensure_ascii=False, indent=2)
# if not os.path.exists('output/monthly_details.jsonevent_decompose_dfs.json'):
#     with open('output/gi2.json', 'r', encoding='utf-8') as f:
#         data = json.load(f)
#     scheduler.process_monthly_details( data['monthly_details'], 'output/')
#
#
# from event.event_refiner import *
# with open('output/xujing/final_timeline.json', 'r', encoding='utf-8') as f:
#     data = json.load(f)
# event_refiner = EventRefiner(persona_data,{})
# #event_refiner.parallel_monthly_health_report_generation(persona_data)
# with open('output/new/test8.json', 'r', encoding='utf-8') as f:
#     data2 = json.load(f)
# res = event_refiner.month_transition_analysis(data["monthly_details"][0],persona_data)
# print( res)
# res = event_refiner.daily_event_refine(data,'2025-02-01','2025-02-28',persona_data,'2025-02-15',data2["analysis_results"]["2025-02"]['health_analysis'],data2["analysis_results"]["2025-02"]['life_analysis'],data2["analysis_results"]["2025-02"]["transition_analysis"])
# with open('output/new/dd.json', 'w', encoding='utf-8') as f:
#     json.dump(res, f, ensure_ascii=False, indent=2)