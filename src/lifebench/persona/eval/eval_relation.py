import json
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from collections import defaultdict
import matplotlib.ticker as ticker

# 设置中文显示
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题


def process_relation_array(relation_data):
    """
    处理relation字段，若为二维数组则转为一维数组

    参数:
    - relation_data: 原始的relation数据
    返回:
    - 处理后的一维数组
    """
    # 检查是否为列表（数组）
    if not isinstance(relation_data, list):
        # 如果不是列表，返回空列表或根据需求处理
        return []

    # 检查是否为二维数组（列表中的元素也是列表）
    if len(relation_data) > 0 and isinstance(relation_data[0], list):
        # 是二维数组，取第一个元素作为一维数组
        # 这里假设二维数组的第一个元素是需要的一维数组
        return relation_data[0] if len(relation_data[0]) > 0 else []
    else:
        # 已经是一维数组，直接返回
        return relation_data


def analyze_relations(json_data):
    """分析关系数据，返回统计结果"""
    relation_counts = defaultdict(int)

    for person in json_data:
        for group in person.get("relation", []):
            for related in group:
                relation = related.get("social circle", "未知圈")
                relation_counts[relation] += 1
                relation = related.get("social_circle", "未知圈")
                relation_counts[relation] += 1

    # 转换为排序后的DataFrame
    df = pd.DataFrame(
        relation_counts.items(),
        columns=["关系", "数量"]
    ).sort_values(by="数量", ascending=False).reset_index(drop=True)

    return df


def plot_relation_distribution(df, top_n=15, figsize=(12, 8)):
    """
    绘制关系分布图表

    参数:
    - df: 包含"关系"和"数量"的DataFrame
    - top_n: 显示前N个最常见的关系，其余归为"其他"
    - figsize: 图表大小
    """
    # 处理数据：前N个 + 其他
    if len(df) > top_n:
        top_relations = df.head(top_n)
        other_count = df.iloc[top_n:]["数量"].sum()
        top_relations = pd.concat([
            top_relations,
            pd.DataFrame([["其他", other_count]], columns=["关系", "数量"])
        ], ignore_index=True)
    else:
        top_relations = df

    # 创建子图
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
    fig.suptitle(f"关系类型分布 (共{len(df)}种)", fontsize=16)

    # 1. 水平条形图 - 适合比较数量
    bars = ax1.barh(top_relations["关系"], top_relations["数量"], color='skyblue')
    ax1.set_xlabel("数量")
    ax1.set_title(f"前{min(top_n, len(df))}种关系及其他")
    ax1.invert_yaxis()  # 数量多的在上面

    # 在条形末端添加数值
    for bar in bars:
        width = bar.get_width()
        ax1.annotate(f'{width}',
                     xy=(width, bar.get_y() + bar.get_height() / 2),
                     xytext=(3, 0),  # 3点偏移
                     textcoords="offset points",
                     ha='left', va='center')

    # 2. 饼图 - 适合展示占比（只显示占比超过1%的类别标签）
    sizes = top_relations["数量"]
    labels = top_relations["关系"]

    # 确定哪些标签需要显示（占比超过1%）
    total = sum(sizes)
    autopct = lambda p: f'{p:.1f}%' if p > 1 else ''

    wedges, texts, autotexts = ax2.pie(
        sizes,
        labels=labels if len(labels) <= 10 else None,  # 太多类别时不显示标签
        autopct=autopct,
        startangle=140,
        pctdistance=0.85,
        wedgeprops=dict(width=0.3)  # 环形图，更美观
    )

    # 美化饼图文字
    plt.setp(autotexts, size=8, weight="bold")
    ax2.set_title("关系类型占比分布")

    # 添加图例（当类别较多时）
    if len(labels) > 10:
        ax2.legend(wedges, labels, title="关系类型",
                   loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))

    plt.tight_layout()
    return fig


def plot_relation_wordcloud(df):
    """生成关系类型词云图"""
    from wordcloud import WordCloud

    # 准备词云数据：关系类型重复出现其数量次
    relation_text = ' '.join([relation for relation, count in zip(df["关系"], df["数量"]) for _ in range(count)])

    # 生成词云
    wordcloud = WordCloud(
        font_path="simhei.ttf",  # 确保有中文字体
        width=800,
        height=400,
        background_color='white',
        colormap='viridis'
    ).generate(relation_text)

    # 显示词云
    plt.figure(figsize=(12, 6))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.title("关系类型词云图（字体大小表示数量）")
    plt.axis('off')
    plt.tight_layout()
    return plt.gcf()

def analyze_person_data(json_data):
    """分析个人JSON数据，统计四大维度分布"""
    # 初始化统计容器
    stats = {
        "relation_dist": defaultdict(int),  # 关系分布
        "social_circle_dist": defaultdict(int),  # 社交圈分布
        "city_dist": defaultdict(int),  # 城市分布
        "personality_dist": defaultdict(int)  # 性格分布
    }

    # 遍历每条个人数据
    for person in json_data:

        # 统计关联人信息
        for group in person.get("relation", []):
            for related in group:
                # 关系统计
                stats["relation_dist"][related.get("relation", "未知关系")] += 1
                # 社交圈统计
                stats["social_circle_dist"][related.get("social circle", "未知社交圈")] += 1
                # 关联人城市统计
                stats["city_dist"][related.get("home_address", {}).get("city", "未知城市")] += 1
                # 关联人性格统计
                stats["personality_dist"][f"MBTI_{related.get('personality', '未知MBTI')}"] += 1

    # 转换为普通字典
    return {k: dict(v) for k, v in stats.items()}


def print_stats_table(stats, title):
    """以表格形式打印统计结果"""
    if not stats:
        print(f"\n{title}：无数据")
        return

    df = pd.DataFrame(
        data=stats.items(),
        columns=["类别", "数量"]
    ).sort_values(by="数量", ascending=False).reset_index(drop=True)

    print(f"\n{'=' * 50}")
    print(f"{title}")
    print(f"{'=' * 50}")
    print(df.to_string(index=False, justify="left"))
    print(f"总计：{df['数量'].sum()}")


def analyze_social_circles(json_data, show_unknown=True):
    """
    分析社交圈分布，并追踪未知社交圈的来源

    参数:
    - json_data: 原始JSON数据
    - show_unknown: 是否打印未知社交圈的详细信息
    """
    # 统计社交圈分布
    circle_counts = defaultdict(int)
    # 记录未知社交圈的来源
    unknown_circles = []

    for person_idx, person in enumerate(json_data):
        person_name = person.get("name", f"未知人物_{person_idx}")

        # 遍历所有关联人群组
        for group_idx, group in enumerate(person.get("relation", [])):
            group = process_relation_array(group)
            # 遍历群组内的关联人
            for related_idx, related in enumerate(group):
                related_name = related.get("name", f"未知关联人_{person_idx}_{group_idx}_{related_idx}")
                # 获取社交圈（如果不存在则标记为未知）
                social_circle = related.get("social circle")

                if social_circle in (None, "", " "):
                    # 记录未知社交圈的详细信息
                    unknown_info = {
                        "所属人物": person_name,
                        "关联人姓名": related_name,
                        "关联人关系": related.get("relation", "未知关系"),
                        "所在群组索引": group_idx,
                        "原始数据": related  # 保存完整的关联人数据
                    }
                    unknown_circles.append(unknown_info)
                    # 统计为未知社交圈
                    circle_counts["未知社交圈"] += 1
                else:
                    # 正常统计社交圈
                    circle_counts[social_circle] += 1

    # 打印统计结果
    print("社交圈分布统计:")
    for circle, count in circle_counts.items():
        print(f"- {circle}: {count}次")

    # 打印未知社交圈的来源（如果有）
    if show_unknown and unknown_circles:
        print(f"\n共发现 {len(unknown_circles)} 个未知社交圈，具体信息如下:")
        for i, info in enumerate(unknown_circles, 1):
            print(f"\n第{i}个未知社交圈:")
            print(f"  所属人物: {info['所属人物']}")
            print(f"  关联人姓名: {info['关联人姓名']}")
            print(f"  关联人关系: {info['关联人关系']}")
            print(f"  所在群组索引: {info['所在群组索引']}")
            # 可选：打印完整的原始数据（便于排查）
            # print(f"  原始数据: {json.dumps(info['原始数据'], ensure_ascii=False, indent=2)}")

    return circle_counts, unknown_circles

if __name__ == "__main__":
    # 简化的示例JSON数据
    file_path = "../../data_persona/personal_profile_rl.json"
    # 解析JSON数据为列表
    with open(file_path, 'r', encoding='utf-8') as f:
        # 解析JSON数据为列表
        people_list = json.load(f)
    json_data = people_list

    # 分析数据
    relation_df = analyze_relations(json_data)
    print(f"共统计到 {len(relation_df)} 种关系类型")
    print(relation_df.head(10))  # 显示前10种

    # 绘制组合图表（条形图+饼图）
    fig1 = plot_relation_distribution(relation_df, top_n=15)
    plt.savefig("relation_distribution.png", dpi=300, bbox_inches="tight")

    # 绘制词云图
    fig2 = plot_relation_wordcloud(relation_df)
    plt.savefig("relation_wordcloud.png", dpi=300, bbox_inches="tight")

    plt.show()

    # 执行统计
    # stats = analyze_person_data(json_data)
    #
    # # 打印结果
    # print_stats_table(stats["relation_dist"], "关系分布统计")
    # print_stats_table(stats["social_circle_dist"], "社交圈分布统计")
    # print_stats_table(stats["city_dist"], "住址城市分布统计")
    # print_stats_table(stats["personality_dist"], "性格分布统计")
    # circle_counts, unknown_circles = analyze_social_circles(json_data)