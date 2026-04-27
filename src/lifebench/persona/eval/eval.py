import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import os

# 设置中文字体，确保图表中文正常显示
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题


class UserProfileAnalyzer:
    def __init__(self, json_file_path):
        """初始化分析器，加载数据"""
        self.json_file_path = json_file_path
        self.data = self.load_data()
        self.df = self.convert_to_dataframe()
        # 定义标准MBTI类型顺序
        self.mbti_types = [
            "INFP", "ESFJ", "ISFJ", "ENFP", "ISFP", "ESFP",
            "INTP", "ENFJ", "INFJ", "ESTJ", "ISTJ", "ENTP",
            "INTJ", "ISTP", "ENTJ", "ESTP"
        ]

    def load_data(self):
        """从JSON文件加载用户画像数据"""
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"成功加载数据，共包含 {len(data)} 个用户画像")
            return data
        except FileNotFoundError:
            print(f"错误：找不到文件 {self.json_file_path}")
            return []
        except json.JSONDecodeError:
            print(f"错误：文件 {self.json_file_path} 不是有效的JSON格式")
            return []
        except Exception as e:
            print(f"加载数据时发生错误：{str(e)}")
            return []

    def convert_to_dataframe(self):
        """将原始数据转换为DataFrame，提取需要分析的字段"""
        if not self.data:
            return pd.DataFrame()

        # 提取关键信息到列表
        profiles = []
        for user in self.data:
            # 处理居住城市信息
            city_info = user.get('home_address', {})
            city = f"{city_info.get('province', '')}-{city_info.get('city', '')}" if city_info else "未知"

            # 处理工作城市信息
            work_city_info = user.get('workplace', {})
            work_city = f"{work_city_info.get('province', '')}-{work_city_info.get('city', '')}" if work_city_info else "未知"

            # 处理出生地信息
            birth_place_info = user.get('birth_place', {})
            birth_place = f"{birth_place_info.get('province', '')}-{birth_place_info.get('city', '')}" if birth_place_info else "未知"

            # 处理性格信息
            personality = user.get('personality', {})
            mbti = personality.get('mbti', '未知')
            traits = personality.get('traits', [])
            traits_str = ", ".join(traits) if traits else "未知"

            # 处理爱好信息
            hobbies = user.get('hobbies', [])
            hobbies_str = ", ".join(hobbies) if hobbies else "未知"

            profile = {
                '姓名': user.get('name', '未知'),
                '年龄': user.get('age', '未知'),
                '性别': user.get('gender', '未知'),
                '居住城市': city,
                '工作城市': work_city,
                '出生地': birth_place,
                '学历': user.get('education', '未知'),
                '职业': user.get('job', '未知'),
                '公司': user.get('occupation', '未知'),
                'MBTI': mbti,
                '性格特质': traits_str,
                '爱好': hobbies_str,
                '爱好数量': len(hobbies),
                '性格特质数量': len(traits)
            }
            profiles.append(profile)

        return pd.DataFrame(profiles)

    def analyze_city_distribution(self, city_type='居住城市'):
        """分析城市分布情况"""
        if self.df.empty:
            print("没有数据可分析")
            return

        print(f"\n{city_type}分布分析:")
        city_counts = self.df[city_type].value_counts()
        city_percentage = self.df[city_type].value_counts(normalize=True) * 100

        # 打印统计结果
        for city, count in city_counts.items():
            print(f"{city}: {count}人 ({city_percentage[city]:.2f}%)")

        # 可视化
        plt.figure(figsize=(12, 6))
        ax = sns.barplot(x=city_counts.index, y=city_counts.values)
        plt.title(f'{city_type}分布')
        plt.ylabel('人数')
        plt.xlabel(city_type)
        plt.xticks(rotation=45, ha='right')

        # 在柱状图上添加数值
        for i, v in enumerate(city_counts.values):
            ax.text(i, v + 0.1, str(v), ha='center')

        plt.tight_layout()
        plt.savefig(f'{city_type}_distribution.png', dpi=300)
        print(f"{city_type}分布图表已保存为 {city_type}_distribution.png")
        plt.close()

        return city_counts

    def analyze_birth_place_distribution(self):
        """分析出生地分布情况"""
        return self.analyze_city_distribution('出生地')

    def analyze_age_distribution(self):
        """分析年龄分布情况"""
        if self.df.empty:
            print("没有数据可分析")
            return

        # 过滤掉年龄为'未知'的数据
        age_data = self.df[self.df['年龄'] != '未知']['年龄']
        if age_data.empty:
            print("没有有效的年龄数据可分析")
            return

        print("\n年龄分布分析:")
        print(f"年龄范围: {age_data.min()} - {age_data.max()} 岁")
        print(f"平均年龄: {age_data.mean():.2f} 岁")
        print(f"年龄中位数: {age_data.median()} 岁")

        # 分组统计
        bins = [0, 20, 30, 40, 50, 60, 100]
        labels = ['0-20岁', '21-30岁', '31-40岁', '41-50岁', '51-60岁', '60岁以上']
        age_groups = pd.cut(age_data.astype(int), bins=bins, labels=labels)
        age_group_counts = age_groups.value_counts().reindex(labels)

        for group, count in age_group_counts.items():
            percentage = (count / len(age_data)) * 100 if len(age_data) > 0 else 0
            print(f"{group}: {count}人 ({percentage:.2f}%)")

        # 可视化
        plt.figure(figsize=(10, 6))
        ax = sns.histplot(age_data.astype(int), bins=10, kde=True)
        plt.title('年龄分布直方图')
        plt.ylabel('人数')
        plt.xlabel('年龄')
        plt.tight_layout()
        plt.savefig('age_distribution.png', dpi=300)
        print("年龄分布图表已保存为 age_distribution.png")
        plt.close()

        # 年龄分组柱状图
        plt.figure(figsize=(10, 6))
        ax = sns.barplot(x=age_group_counts.index, y=age_group_counts.values)
        plt.title('年龄分组分布')
        plt.ylabel('人数')
        plt.xlabel('年龄组')

        # 在柱状图上添加数值
        for i, v in enumerate(age_group_counts.values):
            ax.text(i, v + 0.1, str(v), ha='center')

        plt.tight_layout()
        plt.savefig('age_group_distribution.png', dpi=300)
        print("年龄分组图表已保存为 age_group_distribution.png")
        plt.close()

        return age_group_counts

    def analyze_education_distribution(self):
        """分析学历分布情况"""
        if self.df.empty:
            print("没有数据可分析")
            return

        print("\n学历分布分析:")
        education_counts = self.df['学历'].value_counts()
        education_percentage = self.df['学历'].value_counts(normalize=True) * 100

        # 打印统计结果
        for education, count in education_counts.items():
            print(f"{education}: {count}人 ({education_percentage[education]:.2f}%)")

        # 可视化
        plt.figure(figsize=(12, 6))
        ax = sns.barplot(x=education_counts.index, y=education_counts.values)
        plt.title('学历分布')
        plt.ylabel('人数')
        plt.xlabel('学历')
        plt.xticks(rotation=45, ha='right')

        # 在柱状图上添加数值
        for i, v in enumerate(education_counts.values):
            ax.text(i, v + 0.1, str(v), ha='center')

        plt.tight_layout()
        plt.savefig('education_distribution.png', dpi=300)
        print("学历分布图表已保存为 education_distribution.png")
        plt.close()

        return education_counts

    def analyze_occupation_distribution(self):
        """分析职业分布情况"""
        if self.df.empty:
            print("没有数据可分析")
            return

        print("\n职业分布分析:")
        occupation_counts = self.df['职业'].value_counts()
        occupation_percentage = self.df['职业'].value_counts(normalize=True) * 100

        # 打印统计结果
        for occupation, count in occupation_counts.items():
            print(f"{occupation}: {count}人 ({occupation_percentage[occupation]:.2f}%)")

        # 可视化
        plt.figure(figsize=(12, 6))
        ax = sns.barplot(x=occupation_counts.index, y=occupation_counts.values)
        plt.title('职业分布')
        plt.ylabel('人数')
        plt.xlabel('职业')
        plt.xticks(rotation=45, ha='right')

        # 在柱状图上添加数值
        for i, v in enumerate(occupation_counts.values):
            ax.text(i, v + 0.1, str(v), ha='center')

        plt.tight_layout()
        plt.savefig('occupation_distribution.png', dpi=300)
        print("职业分布图表已保存为 occupation_distribution.png")
        plt.close()

        return occupation_counts

    def analyze_mbti_distribution(self):
        """分析MBTI性格类型分布情况，按指定顺序展示所有16种类型"""
        if self.df.empty:
            print("没有数据可分析")
            return

        print("\nMBTI性格类型分布分析:")

        # 统计MBTI类型出现次数
        mbti_counts = self.df['MBTI'].value_counts()

        # 确保所有指定的MBTI类型都被包含，不存在的类型计数为0
        ordered_counts = []
        for mbti in self.mbti_types:
            count = mbti_counts.get(mbti, 0)
            ordered_counts.append(count)
            percentage = (count / len(self.df)) * 100 if len(self.df) > 0 else 0
            print(f"{mbti}: {count}人 ({percentage:.2f}%)")

        # 可视化 - 按指定顺序展示所有16种类型
        plt.figure(figsize=(16, 8))  # 增大图表尺寸以适应16种类型
        ax = sns.barplot(x=self.mbti_types, y=ordered_counts)
        plt.title('MBTI性格类型分布')
        plt.ylabel('人数')
        plt.xlabel('MBTI类型')
        plt.xticks(rotation=45, ha='right')

        # 在柱状图上添加数值
        for i, v in enumerate(ordered_counts):
            ax.text(i, v + 0.1, str(v), ha='center')

        plt.tight_layout()
        plt.savefig('mbti_distribution.png', dpi=300)
        print("MBTI性格类型分布图表已保存为 mbti_distribution.png")
        plt.close()

        # 创建有序的结果字典
        result = {mbti: count for mbti, count in zip(self.mbti_types, ordered_counts)}
        return result

    def analyze_traits_distribution(self):
        """分析性格特质分布情况"""
        if self.df.empty:
            print("没有数据可分析")
            return

        print("\n性格特质分布分析:")

        # 统计所有性格特质出现的频率
        all_traits = []
        for traits in self.df['性格特质']:
            if traits != "未知":
                all_traits.extend([t.strip() for t in traits.split(',')])

        if not all_traits:
            print("没有有效的性格特质数据可分析")
            return

        trait_counts = Counter(all_traits)
        top_traits = trait_counts.most_common(10)  # 取最常见的10个性格特质

        print("最常见的10个性格特质:")
        for trait, count in top_traits:
            percentage = (count / len(self.df)) * 100
            print(f"{trait}: {count}人 ({percentage:.2f}%)")

        # 可视化
        plt.figure(figsize=(12, 6))
        traits, counts = zip(*top_traits)
        ax = sns.barplot(x=list(traits), y=list(counts))
        plt.title('最常见的10个性格特质')
        plt.ylabel('人数')
        plt.xlabel('性格特质')
        plt.xticks(rotation=45, ha='right')

        # 在柱状图上添加数值
        for i, v in enumerate(counts):
            ax.text(i, v + 0.1, str(v), ha='center')

        plt.tight_layout()
        plt.savefig('traits_distribution.png', dpi=300)
        print("性格特质分布图表已保存为 traits_distribution.png")
        plt.close()

        # 分析每人平均性格特质数量
        avg_traits = self.df['性格特质数量'].mean()
        print(f"\n人均性格特质数量: {avg_traits:.2f} 个")

        return trait_counts

    def analyze_hobbies_distribution(self):
        """分析爱好分布情况，取前20个"""
        if self.df.empty:
            print("没有数据可分析")
            return

        print("\n爱好分布分析:")

        # 统计所有爱好出现的频率
        all_hobbies = []
        for hobbies in self.df['爱好']:
            if hobbies != "未知":
                all_hobbies.extend([h.strip() for h in hobbies.split(',')])

        if not all_hobbies:
            print("没有有效的爱好数据可分析")
            return

        hobby_counts = Counter(all_hobbies)
        top_hobbies = hobby_counts.most_common(20)  # 取最常见的20个爱好

        print("最常见的20个爱好:")
        for hobby, count in top_hobbies:
            percentage = (count / len(self.df)) * 100
            print(f"{hobby}: {count}人 ({percentage:.2f}%)")

        # 可视化
        plt.figure(figsize=(14, 8))  # 增大图表尺寸以适应更多内容
        hobbies, counts = zip(*top_hobbies)
        ax = sns.barplot(x=list(hobbies), y=list(counts))
        plt.title('最常见的20个爱好')
        plt.ylabel('人数')
        plt.xlabel('爱好')
        plt.xticks(rotation=60, ha='right')  # 增加旋转角度，避免文字重叠

        # 在柱状图上添加数值
        for i, v in enumerate(counts):
            ax.text(i, v + 0.1, str(v), ha='center')

        plt.tight_layout()
        plt.savefig('hobbies_distribution.png', dpi=300)
        print("爱好分布图表已保存为 hobbies_distribution.png")
        plt.close()

        # 分析每人平均爱好数量
        avg_hobbies = self.df['爱好数量'].mean()
        print(f"\n人均爱好数量: {avg_hobbies:.2f} 个")

        return hobby_counts

    def generate_diversity_report(self):
        """生成多样性评估报告，包含新增维度"""
        if self.df.empty:
            print("没有数据可生成报告")
            return

        print("\n" + "=" * 50)
        print("用户画像多样性评估报告")
        print("=" * 50)

        # 计算各维度的多样性指数 (以不同类别的数量衡量)
        city_diversity = self.df['居住城市'].nunique()
        birth_place_diversity = self.df['出生地'].nunique()
        age_diversity = self.df[self.df['年龄'] != '未知']['年龄'].nunique()
        education_diversity = self.df['学历'].nunique()
        occupation_diversity = self.df['职业'].nunique()

        # 计算MBTI多样性（排除"未知"类型）
        valid_mbti = self.df[self.df['MBTI'] != '未知']['MBTI']
        mbti_diversity = valid_mbti.nunique()

        # 计算所有爱好和性格特质的多样性
        all_hobbies = []
        for hobbies in self.df['爱好']:
            if hobbies != "未知":
                all_hobbies.extend([h.strip() for h in hobbies.split(',')])
        hobby_diversity = len(set(all_hobbies)) if all_hobbies else 0

        all_traits = []
        for traits in self.df['性格特质']:
            if traits != "未知":
                all_traits.extend([t.strip() for t in traits.split(',')])
        trait_diversity = len(set(all_traits)) if all_traits else 0

        print(f"总用户数量: {len(self.df)}")
        print("\n多样性指标:")
        print(f"- 居住城市多样性: {city_diversity} 个不同城市")
        print(f"- 出生地多样性: {birth_place_diversity} 个不同地区")
        print(f"- 年龄多样性: {age_diversity} 个不同年龄")
        print(f"- 学历多样性: {education_diversity} 个不同学历")
        print(f"- 职业多样性: {occupation_diversity} 个不同职业")
        print(f"- MBTI性格类型多样性: {mbti_diversity} 种不同类型")
        print(f"- 性格特质多样性: {trait_diversity} 种不同特质")
        print(f"- 爱好多样性: {hobby_diversity} 种不同爱好")

        # 保存报告到文件
        with open('../../log/diversity_report.txt', 'w', encoding='utf-8') as f:
            f.write("=" * 50 + "\n")
            f.write("用户画像多样性评估报告\n")
            f.write("=" * 50 + "\n")
            f.write(f"总用户数量: {len(self.df)}\n")
            f.write("\n多样性指标:\n")
            f.write(f"- 居住城市多样性: {city_diversity} 个不同城市\n")
            f.write(f"- 出生地多样性: {birth_place_diversity} 个不同地区\n")
            f.write(f"- 年龄多样性: {age_diversity} 个不同年龄\n")
            f.write(f"- 学历多样性: {education_diversity} 个不同学历\n")
            f.write(f"- 职业多样性: {occupation_diversity} 个不同职业\n")
            f.write(f"- MBTI性格类型多样性: {mbti_diversity} 种不同类型\n")
            f.write(f"- 性格特质多样性: {trait_diversity} 种不同特质\n")
            f.write(f"- 爱好多样性: {hobby_diversity} 种不同爱好\n")

        print("\n报告已保存为 diversity_report.txt")

    def run_full_analysis(self):
        """运行完整的分析流程，包括新增的分析维度"""
        if self.df.empty:
            print("没有数据可分析")
            return

        print("\n开始进行用户画像分析...")

        # 执行各项分析
        self.analyze_city_distribution('居住城市')
        self.analyze_city_distribution('工作城市')
        self.analyze_birth_place_distribution()  # 分析出生地
        self.analyze_age_distribution()
        self.analyze_education_distribution()
        self.analyze_occupation_distribution()
        self.analyze_mbti_distribution()  # 分析MBTI
        self.analyze_traits_distribution()  # 分析性格特质
        self.analyze_hobbies_distribution()  # 分析爱好，前20个

        # 生成多样性报告
        self.generate_diversity_report()

        print("\n分析完成！所有结果已保存。")


if __name__ == "__main__":
    # 替换为你的JSON文件路径
    json_file = "../../data_persona/personal_profile_rl.json"

    # 检查文件是否存在
    if not os.path.exists(json_file):
        print(f"错误：文件 {json_file} 不存在")
    else:
        # 创建分析器实例并运行分析
        analyzer = UserProfileAnalyzer(json_file)
        # analyzer.run_full_analysis()
        analyzer.analyze_mbti_distribution()
