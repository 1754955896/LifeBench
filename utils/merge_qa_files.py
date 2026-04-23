"""
合并多个QA文件为一个统一的QA.json文件，并统计数目分布
"""

import json
import os
from collections import Counter


def merge_qa_files():
    """合并多个QA文件并统计分布"""
    
    # 定义源文件路径和类型标签
    source_files = {
        'multi_hop': r'D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_copy\multi_hop_qa.json',
        'conflict': r'D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_copy\conflict_qa.json',
        'pattern_recognition': r'D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_copy\pattern_recognition_qa_2025.json',
        'single_hop': r'D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_copy\single_hop_qa.json',
        'temporal': r'D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_copy\temporal_qa_2025.json',
        'unanswerable': r'D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_copy\unanswerable_qa.json'
    }
    
    # 输出文件路径
    output_path = r'D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_copy\QA.json'
    
    print("="*80)
    print("开始合并QA文件...")
    print("="*80)
    
    all_qa = []
    type_counter = Counter()
    
    # 读取并合并所有文件
    for qa_type, file_path in source_files.items():
        print(f"\n处理 {qa_type} 类型...")
        
        if not os.path.exists(file_path):
            print(f"  ⚠️  文件不存在: {file_path}")
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                qa_list = json.load(f)
            
            if not isinstance(qa_list, list):
                print(f"  ⚠️  文件格式错误，不是列表: {file_path}")
                continue
            
            # 为每个QA添加类型标签（如果没有）
            for qa in qa_list:
                if 'question_type' not in qa:
                    qa['question_type'] = qa_type
                
                # 确保有必要的字段
                if 'question' not in qa or 'answer' not in qa:
                    print(f"  ⚠️  跳过缺少question或answer字段的条目")
                    continue
                
                # 自动补全 ask_time 字段
                if not qa.get('ask_time'):
                    qa['ask_time'] = '2025-12'
                
                # 对于 unanswerable 类型，将 required_events 改名为 required_events_id，并移除 type 字段
                if qa_type == 'unanswerable':
                    if 'required_events' in qa:
                        qa['required_events_id'] = qa.pop('required_events')
                    if 'type' in qa:
                        qa.pop('type')
                    qa['evidence'] = []
                all_qa.append(qa)
            
            type_counter[qa_type] = len(qa_list)
            print(f"  ✓ 成功加载 {len(qa_list)} 个{qa_type}问题")
            
        except Exception as e:
            print(f"  ✗ 加载失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 统计总数
    total_count = len(all_qa)
    
    print(f"\n{'='*80}")
    print("合并完成统计")
    print(f"{'='*80}")
    print(f"\n各类型问题数量分布：")
    for qa_type, count in sorted(type_counter.items()):
        percentage = (count / total_count * 100) if total_count > 0 else 0
        print(f"  - {qa_type:25s}: {count:5d}  ({percentage:5.2f}%)")
    
    print(f"\n{'='*80}")
    print(f"总计: {total_count} 个问题")
    print(f"{'='*80}")
    
    # 保存合并后的文件
    print(f"\n保存到: {output_path}")
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_qa, f, ensure_ascii=False, indent=2)
        print(f"✓ 成功保存 {total_count} 个问题到 QA.json")
        
        # 验证文件大小
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        print(f"✓ 文件大小: {file_size:.2f} MB")
        
    except Exception as e:
        print(f"✗ 保存失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 额外的统计分析
    print(f"\n{'='*80}")
    print("额外统计分析")
    print(f"{'='*80}")
    
    # 统计是否有ask_time字段
    has_ask_time = sum(1 for qa in all_qa if 'ask_time' in qa)
    print(f"\n包含ask_time字段的问题: {has_ask_time}/{total_count} ({has_ask_time/total_count*100:.2f}%)")
    
    # 统计是否有evidence字段
    has_evidence = sum(1 for qa in all_qa if 'evidence' in qa and qa['evidence'])
    print(f"包含evidence字段的问题: {has_evidence}/{total_count} ({has_evidence/total_count*100:.2f}%)")
    
    # 统计是否有required_events_id字段
    has_events = sum(1 for qa in all_qa if 'required_events_id' in qa and qa['required_events_id'])
    print(f"包含required_events_id字段的问题: {has_events}/{total_count} ({has_events/total_count*100:.2f}%)")
    
    # 统计平均证据数量
    if has_evidence > 0:
        avg_evidence = sum(len(qa.get('evidence', [])) for qa in all_qa if qa.get('evidence')) / has_evidence
        print(f"平均证据数量: {avg_evidence:.2f}")
    
    print(f"\n{'='*80}")
    print("处理完成！")
    print(f"{'='*80}")


if __name__ == "__main__":
    merge_qa_files()
