from event.qa_muti_generator import QAMutiGenerator
import json

qa_muti_generator = QAMutiGenerator()
qa_muti_generator.load_data_from_path('xujing')

# 测试新的generate_yearly_multi_hop_questions方法
# 生成2025年的问题，每月6个，基于画像每次生成6个，共4次
#res = qa_muti_generator.generate_yearly_multi_hop_questions("2025",6, 6)
# print(f"\n总共生成了{len(res)}个问题")
# print(res)
#res = qa_muti_generator.generate_multi_hop_questions_from_draft("2025-01",8)
# 测试原始的generate_multi_hop_questions_from_persona方法
#res = qa_muti_generator.generate_multi_hop_questions_from_persona(6)
res = qa_muti_generator.generate_pattern_recognition_and_habit_analysis_questions('2025-01',1)
# res = qa_muti_generator.generate_yearly_pattern_recognition_questions("2025",6)
#res = qa_muti_generator.generate_unanswerable_questions(2,'2025-06')
print(res)
# 验证所有evidence手机数据是否存在
print("\n=== 验证evidence手机数据存在性 ===")
all_found = True

def check_evidence_exists(evidence_item, phonedata):
    """检查单个evidence项是否存在于phonedata中"""
    data_type = evidence_item.get('type')
    evidence_id = evidence_item.get('id')

    if not data_type or not evidence_id:
        print(f"⚠️  evidence项缺少必要字段: {evidence_item}")
        return False

    # 检查数据类型是否存在于phonedata中
    if data_type not in phonedata:
        print(f"❌  数据类型 '{data_type}' 不存在于phonedata中")
        return False

    data_list = phonedata[data_type]
    if not isinstance(data_list, list):
        print(f"❌  数据类型 '{data_type}' 的数据不是列表格式")
        return False

    # 查找ID是否存在
    for item in data_list:
        if isinstance(item, dict):
            # 检查是否有匹配的id或phone_id字段
            if item.get('id') == evidence_id or item.get('phone_id') == evidence_id:
                return True

    return False

# 遍历所有问题和evidence
for i, question_data in enumerate(res):
    question = question_data.get('question', '未知问题')
    evidence_list = question_data.get('evidence', [])

    print(f"\n问题 {i+1}: {question}")
    print(f"  验证 {len(evidence_list)} 个evidence项...")

    for j, evidence in enumerate(evidence_list):
        exists = check_evidence_exists(evidence, qa_muti_generator.phonedata)
        if exists:
            print(f"    ✅ Evidence {j+1} 存在: {evidence}")
        else:
            print(f"    ❌ Evidence {j+1} 不存在: {evidence}")
            all_found = False

# 输出验证结果
print("\n=== 验证结果总结 ===")
if all_found:
    print("✅ 所有evidence手机数据都存在于phonedata中")
else:
    print("❌ 部分evidence手机数据不存在于phonedata中")