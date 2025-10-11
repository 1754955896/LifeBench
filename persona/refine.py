import re

from utils.llm_call import *
from template import *
from utils.random_ref import *

def generate(profile):
    result = template_refine.format(JSON=profile)
    result = llm_call_reason(result)
    print(result)
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

# 读取JSON文件
file_path = "../data_persona/personal_profile（2）.json"
# 解析JSON数据为列表
with open(file_path, 'r', encoding='utf-8') as f:
    # 解析JSON数据为列表
    people_list = json.load(f)
json_data = []
try:

    # 处理每条数据
    for i, person in enumerate(people_list):
        # if i==0:
        #     continue
        person["relation"]=[]
        person_str = json.dumps(person, ensure_ascii=False, indent=2)
        llm_str = generate(person_str)

        # # 保存llm_str到txt文件（追加模式）
        # with open("llm_responses.txt", "a", encoding="utf-8") as txt_f:
        #     # 第一次写入不添加开头的分隔符
        #     if i > 0:
        #         txt_f.write(separator)
        #     txt_f.write(llm_str)

        # 解析并收集用于最终JSON的数据
        try:
            json_data.append(parse_llm_json_response(llm_str))
            print(f"已处理第{i + 1}条数据")
        except json.JSONDecodeError as e:
            print(f"第{i + 1}条数据JSON转换失败：", e)

    # 最后统一存入JSON文件
    with open("../data_persona/personal_profile_refine.json", "w", encoding="utf-8") as json_f:
        json.dump(json_data, json_f, ensure_ascii=False, indent=4)
    print("所有数据处理完成，JSON文件已生成")

except Exception as e:
    print("处理过程出错，错误原因：", e)

# try:
#     with open("personal_profile.json", "w", encoding="utf-8") as f:
#
#         # 遍历每个个人信息并转换为字符串
#         for i, person in enumerate(people_list):
#             # 使用json.dumps将字典转为字符串，ensure_ascii=False保证中文正常显示
#             person_str = json.dumps(person, ensure_ascii=False, indent=2)
#             llm_str = generate(person_str)
#
#             try:
#                 json_data.append(parse_llm_json_response(llm_str)) # 核心函数：字符串转JSON（dict）
#                 json.dump(json_data, f, ensure_ascii=False, indent=4)
#             except json.JSONDecodeError as e:
#                 print("JSON转换失败，错误原因：", e)  # 捕获格式错误，便于调试
#
#
# except Exception as e:
#     print("保存失败，错误原因：", e)
