import re

from utils.llm_call import *
from template import *
import json

example = '''
{
        "name": "韩海生",
        "relation": "父亲",
        "social circle":"家庭圈",
        "gender": "男",
        "age": 52,
        "birth_date": "1973-11-06",
        "home_address": {
          "province": "甘肃省",
          "city": "临夏回族自治州",
          "district": "临夏市",
          "street_name": "红园街道民丰路",
          "street_number": "127号"
        },
        "birth_place": {
          "province": "陕西省",
          "city": "咸阳市"
        },
        "personality": "ESTJ",
        "economic_level": "小康",
        "occupation": "汽车整车制造人员",
        "organization": "临夏民族汽车配件厂",
        "nickname": "老爸",
        "relation_description":""
      }

'''

def generate(profile,circle):
    #print(profile)
    result = template_person.format(JSON=circle,example=example,profile=profile)
    print(result)
    result = llm_call(result)
    ##print(result)
    return result

def parse_llm_json_response(llm_response):
    """
    处理LLM返回的包含```json标记的JSON字符串

    参数:
        llm_response: LLM返回的原始字符串，格式如```json{...}```

    返回:
        解析后的JSON字典，如果解析失败返回None
    """

    # 使用正则表达式提取```json和```之间的内容
    # 匹配可能的换行和空格
    pattern = r'```json\s*(.*?)\s*```'
    match = re.search(pattern, llm_response, re.DOTALL)

    if not match:
            print("未找到JSON标记")
            return json.loads(llm_response)

    # 提取JSON部分字符串
    json_str = match.group(1)

    # 解析JSON字符串为字典
    json_data = json.loads(json_str)
    return json_data

def group_by_social_circle(data):
    # 创建一个字典用于存储分组结果
    groups = {}

    # 你的数据是嵌套列表，先获取内部列表
    people = data
    # 遍历每个人
    for person in people:
        circle = person["social circle"]

        # 如果该社交圈不在字典中，创建一个新列表
        if circle not in groups:
            groups[circle] = []

        # 将当前人员添加到对应的社交圈列表中
        groups[circle].append(person)

    return groups

def generate_person(profile,profile_rl,i):
            print(type(profile))
            print(profile)
            print(type(profile_rl))
            print(profile_rl)

            json_data = []
            relation_list = profile_rl
            grouped_data = group_by_social_circle(relation_list)
            print(grouped_data)
            person_str = profile
            for circle, people in grouped_data.items():
                relation_str = json.dumps(people, ensure_ascii=False, indent=2)
                llm_str = generate(person_str, relation_str)
                #print(llm_str)
                # # 保存llm_str到txt文件（追加模式）
                # with open("llm_responses_relation.txt", "a", encoding="utf-8") as txt_f:
                #     # 第一次写入不添加开头的分隔符
                #     if i > 0:
                #         txt_f.write(separator)
                #     txt_f.write(llm_str)
                # 解析并收集用于最终JSON的数据
                try:
                    json_data.append(parse_llm_json_response(llm_str))
                    print(f"已处理第{i + 1}条数据_person")
                except json.JSONDecodeError as e:
                    print(f"第{i + 1}条数据JSON转换失败_person：", e)

            return json_data




#
# # 读取JSON文件
# file_path = "personal_profile.json"
# # 解析JSON数据为列表
# with open(file_path, 'r', encoding='utf-8') as f:
#     # 解析JSON数据为列表
#     people_list = json.load(f)
# json_data = []
#
# file_path = "personal_profile_rl.json"
# # 解析JSON数据为列表
# with open(file_path, 'r', encoding='utf-8') as f:
#     # 解析JSON数据为列表
#     relation_list = json.load(f)
# relation_list = relation_list
#
# grouped_data = group_by_social_circle(relation_list)
#
#
# #relation_str = json.dumps(relation_list[0][0:5], ensure_ascii=False, indent=2)
#
# try:
#
#     # 处理每条数据
#     for i, person in enumerate(people_list):
#         if i<65:
#             continue
#         person["relation"]=[]
#         for circle, people in grouped_data.items():
#             #print(person)
#             person_str = json.dumps(person, ensure_ascii=False, indent=2)
#             relation_str = json.dumps(people, ensure_ascii=False, indent=2)
#             #print(type(person_str))
#             llm_str = generate(person_str,relation_str)
#             print(llm_str)
#             # # 保存llm_str到txt文件（追加模式）
#             # with open("llm_responses_relation.txt", "a", encoding="utf-8") as txt_f:
#             #     # 第一次写入不添加开头的分隔符
#             #     if i > 0:
#             #         txt_f.write(separator)
#             #     txt_f.write(llm_str)
#
#             # 解析并收集用于最终JSON的数据
#             try:
#                 json_data.append(parse_llm_json_response(llm_str))
#                 print(f"已处理第{i + 1}条数据")
#             except json.JSONDecodeError as e:
#                 print(f"第{i + 1}条数据JSON转换失败：", e)
#         break
#
#     # 最后统一存入JSON文件
#     with open("personal_profile_person.json", "w", encoding="utf-8") as json_f:
#         json.dump(json_data, json_f, ensure_ascii=False, indent=4)
#     print("所有数据处理完成，JSON文件已生成")
#
# except Exception as e:
#     print("处理过程出错，错误原因：", e)