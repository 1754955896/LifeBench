import json
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from collections import defaultdict
import pandas as pd

# 设置中文字体
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False


def get_social_circle(related_person):
    """兼容'social circle'和'social_circle'两种键名"""
    if 'social_circle' in related_person:
        return related_person['social_circle']
    elif 'social circle' in related_person:
        return related_person['social circle']
    return None


def analyze_data(json_data):
    """完整数据分析函数，返回各维度统计结果"""
    stats = {
        "relation_dist": defaultdict(int),
        "social_circle_dist": defaultdict(int),
        "city_dist": defaultdict(int),
        "personality_dist": defaultdict(int)
    }

    for person in json_data:
        # 处理个人信息
        personal_city = person.get("home_address", {}).get("city", "未知城市")
        stats["city_dist"][personal_city] += 1

        # 个人性格统计
        personal_personality = person.get("personality", {})
        personal_mbti = personal_personality.get("mbti", "未知MBTI")
        stats["personality_dist"][f"MBTI_{personal_mbti}"] += 1
        for trait in personal_personality.get("traits", ["未知特质"]):
            stats["personality_dist"][f"特质_{trait}"] += 1

        # 处理关联人信息
        relations = person.get("relation", [])
        for group in relations:
            for related in group:
                # 关系统计
                rel = related.get("relation","未知关系")
                stats["relation_dist"][rel] += 1

                # 社交圈统计
                circle = get_social_circle(related)
                if circle in (None, "", " "):
                    circle = "未知社交圈"
                stats["social_circle_dist"][circle] += 1

                # 城市统计
                related_city = related.get("home_address", {}).get("city", "未知城市")
                stats["city_dist"][related_city] += 1

                # 性格统计
                related_mbti = related.get("personality", "未知MBTI")
                stats["personality_dist"][f"MBTI_{related_mbti}"] += 1

    # 转换为普通字典
    return {k: dict(v) for k, v in stats.items()}


def print_stats_table(stats, title):
    """打印统计表格"""
    if not stats:
        print(f"\n{title}：无数据")
        return

    df = pd.DataFrame(
        stats.items(), columns=["类别", "数量"]
    ).sort_values(by="数量", ascending=False).reset_index(drop=True)

    print(f"\n{'=' * 50}")
    print(f"{title}")
    print(f"{'=' * 50}")
    print(df.to_string(index=False, justify="left"))


def generate_wordcloud(data, title, max_words=50):
    """生成词云图"""
    # 准备词云文本
    text = " ".join([word for word, count in data.items() for _ in range(count)])

    # 创建词云
    wc = WordCloud(
        font_path="simhei.ttf",  # 替换为系统中文字体路径
        max_words=max_words,
        background_color="white",
        width=1000,
        height=600,
        colormap="viridis"
    ).generate(text)

    # 显示词云
    plt.figure(figsize=(12, 7))
    plt.imshow(wc, interpolation="bilinear")
    plt.title(title, fontsize=16)
    plt.axis("off")
    plt.tight_layout(pad=0)
    plt.show()

    return wc


if __name__ == "__main__":
    file_path = "../../data_persona/personal_profile_rl.json"
    # 解析JSON数据为列表
    with open(file_path, 'r', encoding='utf-8') as f:
        # 解析JSON数据为列表
        people_list = json.load(f)
    json_data = people_list

    # 执行统计分析
    stats = analyze_data(json_data)

    # 打印统计表格
    print_stats_table(stats["relation_dist"], "关系分布统计")
    print_stats_table(stats["social_circle_dist"], "社交圈分布统计")
    print_stats_table(stats["city_dist"], "城市分布统计")
    print_stats_table(stats["personality_dist"], "性格分布统计")

    # 生成词云图（可根据需要选择维度）
    generate_wordcloud(stats["relation_dist"], "关系类型词云图")
    generate_wordcloud(stats["social_circle_dist"], "社交圈分布词云图")
