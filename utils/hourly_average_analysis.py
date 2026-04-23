"""
基于时间分析结果计算各领域的每日每小时平均数据
"""
import json
import os
import glob


def analyze_all_reports(input_dir):
    """
    分析所有人员的时间分析报告
    
    Args:
        input_dir: 时间分析报告目录
    
    Returns:
        包含所有人员统计数据的列表
    """
    # 查找所有时间分析JSON文件
    pattern = os.path.join(input_dir, '*_time_analysis.json')
    files = glob.glob(pattern)
    
    if not files:
        print(f"未找到时间分析文件: {pattern}")
        return []
    
    print(f"找到 {len(files)} 个时间分析报告")
    
    categories = [
        '个人生理必需活动',
        '有酬劳动',
        '无酬劳动',
        '个人自由支配活动',
        '学习培训',
        '交通活动'
    ]
    
    all_results = []
    
    for file_path in sorted(files):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            person_name = data.get('person_name', '')
            total_days = data.get('total_days', 0)
            analyzed_days = data.get('analyzed_days', 0)
            category_distribution = data.get('category_distribution', {})
            
            # 计算每个人的统计数据
            person_result = {
                'person_name': person_name,
                'total_days': total_days,
                'analyzed_days': analyzed_days
            }
            
            overall_total_hours = 0
            overall_participation_days = 0
            
            for cat in categories:
                if cat in category_distribution:
                    stats = category_distribution[cat]
                    total_hours = stats.get('total_hours', 0)
                    daily_average_hours = stats.get('daily_average_hours', 0)
                    days_involved = stats.get('days_involved', 0)
                    
                    # 计算参与时长（总小时/参与天数）
                    participation_hours = round(total_hours / days_involved, 2) if days_involved > 0 else 0
                    
                    # 计算占比（参与天数/总天数）
                    participation_ratio = round((days_involved / total_days) * 100, 2) if total_days > 0 else 0
                    
                    person_result[f'{cat}_average'] = daily_average_hours
                    person_result[f'{cat}_participation'] = participation_hours
                    person_result[f'{cat}_ratio'] = participation_ratio
                    
                    overall_total_hours += total_hours
                    overall_participation_days += days_involved
                else:
                    person_result[f'{cat}_average'] = 0
                    person_result[f'{cat}_participation'] = 0
                    person_result[f'{cat}_ratio'] = 0
            
            # 计算overall统计
            if analyzed_days > 0:
                person_result['overall_average'] = round(overall_total_hours / analyzed_days, 2)
            else:
                person_result['overall_average'] = 0
            
            if overall_participation_days > 0:
                person_result['overall_participation'] = round(overall_total_hours / overall_participation_days, 2)
            else:
                person_result['overall_participation'] = 0
            
            if total_days > 0:
                person_result['overall_ratio'] = round((overall_participation_days / (total_days * len(categories))) * 100, 2)
            else:
                person_result['overall_ratio'] = 0
            
            all_results.append(person_result)
            print(f"已处理: {person_name}")
            
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
    
    return all_results


def print_comparison_table(all_results):
    """
    打印对比表格
    """
    if not all_results:
        print("没有数据可显示")
        return
    
    import statistics
    
    categories = [
        '个人生理必需活动',
        '有酬劳动',
        '无酬劳动',
        '个人自由支配活动',
        '学习培训',
        '交通活动'
    ]
    
    print(f"\n{'='*150}")
    print(f"时间利用对比分析报告")
    print(f"{'='*150}\n")
    
    # 打印表头
    header = f"{'姓名':<12}"
    for cat in categories:
        header += f"{cat[:6]:<12} {'平均':<8} {'参与':<8} {'占比':<8}"
    header += f"{'Overall':<12} {'平均':<8} {'参与':<8} {'占比':<8}"
    print(header)
    print(f"{'-'*150}")
    
    # 打印每个人的数据
    for result in all_results:
        row = f"{result['person_name']:<12}"
        for cat in categories:
            avg = result.get(f'{cat}_average', 0)
            part = result.get(f'{cat}_participation', 0)
            ratio = result.get(f'{cat}_ratio', 0)
            row += f"{cat[:6]:<12} {avg:<8} {part:<8} {ratio:<8}"
        
        overall_avg = result.get('overall_average', 0)
        overall_part = result.get('overall_participation', 0)
        overall_ratio = result.get('overall_ratio', 0)
        row += f"{'Overall':<12} {overall_avg:<8} {overall_part:<8} {overall_ratio:<8}"
        
        print(row)
    
    print(f"{'-'*150}")
    
    # 计算所有人的overall统计
    total_persons = len(all_results)
    if total_persons > 0:
        avg_overall_avg = round(sum(r.get('overall_average', 0) for r in all_results) / total_persons, 2)
        avg_overall_part = round(sum(r.get('overall_participation', 0) for r in all_results) / total_persons, 2)
        avg_overall_ratio = round(sum(r.get('overall_ratio', 0) for r in all_results) / total_persons, 2)
        
        overall_row = f"{'Overall平均':<12}"
        for cat in categories:
            cat_avg = round(sum(r.get(f'{cat}_average', 0) for r in all_results) / total_persons, 2)
            cat_part = round(sum(r.get(f'{cat}_participation', 0) for r in all_results) / total_persons, 2)
            cat_ratio = round(sum(r.get(f'{cat}_ratio', 0) for r in all_results) / total_persons, 2)
            overall_row += f"{cat[:6]:<12} {cat_avg:<8} {cat_part:<8} {cat_ratio:<8}"
        
        overall_row += f"{'Overall':<12} {avg_overall_avg:<8} {avg_overall_part:<8} {avg_overall_ratio:<8}"
        print(overall_row)
    
    print(f"{'='*150}\n")
    
    # 新增统计表：平均值和方差
    print(f"\n{'='*150}")
    print(f"时间利用统计分析（平均值与方差）")
    print(f"{'='*150}\n")
    
    # 打印表头
    stat_header = f"{'指标':<12}"
    for cat in categories:
        stat_header += f"{cat[:6]:<12} {'均值':<10} {'方差':<10}"
    stat_header += f"{'Overall':<12} {'均值':<10} {'方差':<10}"
    print(stat_header)
    print(f"{'-'*150}")
    
    # 计算每类指标的均值和方差
    metrics = [
        ('average', '平均时长'),
        ('participation', '参与时长'),
        ('ratio', '占比')
    ]
    
    for metric_key, metric_name in metrics:
        stat_row = f"{metric_name:<12}"
        
        for cat in categories:
            values = [r.get(f'{cat}_{metric_key}', 0) for r in all_results]
            mean_val = round(statistics.mean(values), 2) if values else 0
            variance_val = round(statistics.variance(values), 2) if len(values) > 1 else 0
            stat_row += f"{cat[:6]:<12} {mean_val:<10} {variance_val:<10}"
        
        # Overall统计
        overall_values = [r.get(f'overall_{metric_key}', 0) for r in all_results]
        overall_mean = round(statistics.mean(overall_values), 2) if overall_values else 0
        overall_variance = round(statistics.variance(overall_values), 2) if len(overall_values) > 1 else 0
        stat_row += f"{'Overall':<12} {overall_mean:<10} {overall_variance:<10}"
        
        print(stat_row)
    
    print(f"{'='*150}\n")


def save_comparison_report(all_results, output_dir):
    """
    保存对比报告到文件
    """
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "all_persons_hourly_comparison.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"对比报告已保存至: {output_file}")
    return output_file


def main():
    """
    主函数
    """
    # 配置参数
    input_dir = r"D:\pyCharmProjects\pythonProject4\output\time_analysis"
    output_dir = r"D:\pyCharmProjects\pythonProject4\output\time_analysis"
    
    # 检查输入目录是否存在
    if not os.path.exists(input_dir):
        print(f"错误: 目录不存在 - {input_dir}")
        return
    
    print(f"正在分析目录: {input_dir}")
    
    # 分析所有报告
    all_results = analyze_all_reports(input_dir)
    
    if not all_results:
        print("没有可分析的报告")
        return
    
    # 打印对比表格
    print_comparison_table(all_results)
    
    # 保存报告
    save_comparison_report(all_results, output_dir)


if __name__ == "__main__":
    main()
