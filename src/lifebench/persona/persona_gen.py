import json
import re
import shutil
from src.lifebench.utils.llm_call import llm_call, llm_call_reason
from persona.gen_utils.template import template, template_refine, template_relation_1, template_person
from src.lifebench.utils.random_ref import JSONRandomSelector, convert_list_to_string


class PersonaGenerator:
    def __init__(self, ref_json_file_path="../persona/persona_file/refer.json"):
        """初始化个人画像生成器"""
        self.selector = JSONRandomSelector(ref_json_file_path)
        self.example_relation = '''
        [
          {"name":"","relation":""，“social circle”：“”},
          {"name":"","relation":""，“social circle”：“”}
        ]
            - **name**：该联系人的姓名。
            - **relation**：联系人与个体之间的关系。
            - **social circle**：该联系人所属社交圈。
        '''
        self.example_person = '''
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

    def refer_const(self):
        """生成参考数据"""
        hobby = self.selector.random_select("兴趣", 12)
        aim = self.selector.random_select("目标规划", 6)
        value = self.selector.random_select("价值观", 6)

        ref = ""
        ref += f"\"hobbies\":{convert_list_to_string(hobby)} ，选取4-8个符合用户特征的合理爱好，同时根据上下文补充一个其他爱好；\n"
        ref += f"\"aim\":{convert_list_to_string(aim)}，可选取一到两个目标并具体化（若无合理目标可不选）；\n"
        ref += f"\"traits\":{convert_list_to_string(value)}，可选取2-4个合理且符合该用户的价值观；\n"
        return ref

    def generate_profile(self, profile_str, variant_instruction=None):
        """生成基础个人画像"""
        variant_suffix = ""
        if variant_instruction:
            variant_suffix = f"\n\n**额外指令**: {variant_instruction}"
        result = template.format(JSON=profile_str, Ref=self.refer_const()) + variant_suffix
        result = llm_call(result)
        print(result)
        return result

    def generate_refine(self, profile):
        """优化个人画像"""
        result = template_refine.format(JSON=profile)
        result = llm_call_reason(result)
        print(result)
        return result

    def generate_relation(self, profile):
        """生成人际关系"""
        result = template_relation_1.format(JSON=profile, example=self.example_relation)
        result = llm_call(result)
        print(result)
        return result

    def generate_people(self, profile, circle):
        """生成具体人物信息"""
        result = template_person.format(
            JSON=circle,
            example=self.example_person,
            profile=profile
        )
        result = llm_call(result)
        print(result)
        return result

    def group_by_social_circle(self, data):
        """按社交圈分组"""
        groups = {}
        for person in data:
            circle = person["social circle"]
            if circle not in groups:
                groups[circle] = []
            groups[circle].append(person)
        return groups

    def generate_person(self, profile, profile_rl, index):
        """生成人物关系详情"""
        json_data = []
        relation_list = json.loads(profile_rl)
        grouped_data = self.group_by_social_circle(relation_list)

        person_str = profile
        for circle, people in grouped_data.items():
            relation_str = json.dumps(people, ensure_ascii=False, indent=2)
            llm_str = self.generate_people(person_str, relation_str)
            try:
                json_data.append(self.parse_llm_json_response(llm_str))
                # print(f"已处理第{index + 1}条数据_person")
            except json.JSONDecodeError as e:
                print(f"第{index + 1}条数据JSON转换失败_person：", e)
        return json_data

    def parse_llm_json_response(self, llm_response):
        """解析LLM返回的JSON数据"""
        pattern = r'```json\s*(.*?)\s*```'
        match = re.search(pattern, llm_response, re.DOTALL)

        if not match:
            return json.loads(llm_response)

        json_str = match.group(1)
        return json.loads(json_str)

    def _process_single_person(self, person, index, variant_strength=0.3):
        """
        处理单个人物的基础画像生成

        参数:
            person: 人物信息字典
            index: 人物索引
            variant_strength: 变体强度 (0.0-1.0)，控制与原始模板的差异程度

        返回:
            dict: 生成的基础画像数据
        """
        print(f"正在处理第{index + 1}条数据", person)
        person_str = json.dumps(person, ensure_ascii=False, indent=2)
        print('-----------------')
        print(person_str)
        # 构建变体指令
        variant_instruction = None
        if variant_strength > 0:
            if variant_strength >= 0.7:
                instruct = "大幅度变体：对原始人物模板进行显著改变，包括年龄±5年、职业重新推演、性格特征随机重组、爱好大幅调整，生成与模板差异明显的新人物。"
            elif variant_strength >= 0.4:
                instruct = "中等变体：对原始人物模板进行适度改变，包括调整职业细节、重塑部分爱好、改变生活地点到同省其他城市，生成与模板有明显差异但合理的人物。"
            else:
                instruct = "轻度变体：保持原始人物模板的主体框架，仅对非核心字段（爱好顺序、描述措辞、次要细节）做微调，生成与模板高度相似的人物。"
        llm_str = self.generate_profile(person_str, variant_instruction=instruct)
        llm_str = self.generate_refine(llm_str)
        print('-----------------')
        print(llm_str)
        # 解析生成的基础画像
        basic_data = self.parse_llm_json_response(llm_str)
        if 'note' in basic_data:
            del basic_data['note']
        
        # 保存原始person信息和索引，以便后续处理
        basic_data['_original_person'] = person
        basic_data['_index'] = index
        
        print(f"已生成第{index + 1}条基础画像数据")
        return basic_data

    def generate_basic_profile(self, start_id, end_id, in_file_path, basic_out_file_path, max_workers=None, variant_strength=0.3):
        """
        生成基础个人画像数据（执行到generate_refine后保存），支持并行处理

        参数:
            start_id: 开始处理的索引
            end_id: 结束处理的索引（不包含）
            in_file_path: 输入文件路径
            basic_out_file_path: 基础画像输出文件路径
            max_workers: 并行处理的最大线程数，默认为None（根据系统自动调整）
            variant_strength: 变体强度 (0.0-1.0)

        返回:
            list: 生成的基础画像数据列表
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        basic_profiles = []
        try:
            with open(in_file_path, 'r', encoding='utf-8') as f:
                people_list = json.load(f)

            # 获取需要处理的人物子集
            people_to_process = []
            for i, person in enumerate(people_list):
                if i < start_id:
                    continue
                if i >= end_id:
                    break
                people_to_process.append((person, i))

            # 使用线程池并行处理
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_person = {
                    executor.submit(self._process_single_person, person, i, variant_strength): (person, i)
                    for person, i in people_to_process
                }
                
                # 收集结果
                for future in as_completed(future_to_person):
                    try:
                        result = future.result()
                        basic_profiles.append(result)
                    except Exception as e:
                        person, i = future_to_person[future]
                        print(f"处理第{i + 1}条数据时出错: {e}")

            # 按原始顺序排序
            basic_profiles.sort(key=lambda x: x['_index'])

            # 保存基础画像数据
            with open(basic_out_file_path, "w", encoding="utf-8") as f:
                json.dump(basic_profiles, f, ensure_ascii=False, indent=2)

            print(f"基础画像数据已保存到 {basic_out_file_path}")
            return basic_profiles

        except Exception as e:
            print("生成基础画像过程出错，错误原因：", e)
            # 尝试保存已处理的数据
            if basic_profiles:
                # 按原始顺序排序
                basic_profiles.sort(key=lambda x: x['_index'])
                with open(basic_out_file_path, "w", encoding="utf-8") as f:
                    json.dump(basic_profiles, f, ensure_ascii=False, indent=2)
                print(f"已保存部分基础画像数据到 {basic_out_file_path}")
            return None
            
    def _process_single_relation(self, basic_data):
        """
        处理单个人物的关系数据生成和完整画像构建
        
        参数:
            basic_data: 基础画像数据字典
            
        返回:
            dict: 完整的个人画像数据
        """
        # 从基础数据中提取必要信息
        llm_str = json.dumps(basic_data, ensure_ascii=False, indent=2)
        i = basic_data.get('_index', 0)
        
        # 生成关系数据
        rl = self.generate_relation(llm_str)
        rl_data = self.generate_person(llm_str, rl, i)
        
        # 构建完整画像
        complete_data = basic_data.copy()
        # 移除临时字段
        if '_original_person' in complete_data:
            del complete_data['_original_person']
        # 保留 _index 用于排序，输出时再删除

        complete_data['relation'] = rl_data
        
        print(f"已完成第{i + 1}条完整画像数据")
        return complete_data

    def generate_relation_and_complete(self, basic_profile_file, final_out_file_path, max_workers=None):
        """
        根据基础画像生成关系数据并完成最终个人画像，支持并行处理
        
        参数:
            basic_profile_file: 基础画像文件路径
            final_out_file_path: 最终输出文件路径
            max_workers: 并行处理的最大线程数，默认为None（根据系统自动调整）
            
        返回:
            list: 完整的个人画像数据列表
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        complete_profiles = []
        try:
            # 读取基础画像数据
            with open(basic_profile_file, 'r', encoding='utf-8') as f:
                basic_profiles = json.load(f)

            # 使用线程池并行处理
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_basic = {
                    executor.submit(self._process_single_relation, basic_data): basic_data
                    for basic_data in basic_profiles
                }
                
                # 收集结果
                for future in as_completed(future_to_basic):
                    try:
                        result = future.result()
                        complete_profiles.append(result)
                    except Exception as e:
                        basic_data = future_to_basic[future]
                        i = basic_data.get('_index', 0)
                        print(f"处理第{i + 1}条关系数据时出错: {e}")

            # 按原始顺序排序（如果存在_index字段）
            if complete_profiles and basic_profiles and '_index' in basic_profiles[0]:
                index_map = {bd.get('_index'): i for i, bd in enumerate(basic_profiles)}
                complete_profiles.sort(key=lambda x: index_map.get(x.get('_index'), 0))

            # 移除内部排序字段再输出
            for cp in complete_profiles:
                cp.pop('_index', None)

            # 保存完整画像数据
            with open(final_out_file_path, "w", encoding="utf-8") as f:
                json.dump(complete_profiles, f, ensure_ascii=False, indent=2)

            print(f"完整画像数据已保存到 {final_out_file_path}")
            return complete_profiles

        except Exception as e:
            print("生成关系和完整画像过程出错，错误原因：", e)
            # 尝试保存已处理的数据
            if complete_profiles:
                # 按原始顺序排序（如果存在_index字段）
                if basic_profiles and '_index' in basic_profiles[0]:
                    index_map = {bd.get('_index'): i for i, bd in enumerate(basic_profiles)}
                    complete_profiles.sort(key=lambda x: index_map.get(x.get('_index'), 0))
                for cp in complete_profiles:
                    cp.pop('_index', None)
                with open(final_out_file_path, "w", encoding="utf-8") as f:
                    json.dump(complete_profiles, f, ensure_ascii=False, indent=2)
                print(f"已保存部分完整画像数据到 {final_out_file_path}")
            return None
            
    def gen_profile(self, start_id, end_id, in_file_path, out_file_path, median_path=None, max_workers=None):
        """
        生成完整个人画像数据（原始完整流程，保持向后兼容）

        参数:
            start_id: 开始处理的索引
            end_id: 结束处理的索引（不包含）
            in_file_path: 输入文件路径
            out_file_path: 最终输出文件路径
            median_path: 中间文件路径
            max_workers: 并行处理的最大线程数，默认为None（根据系统自动调整）
        """
        import os
        # 创建临时文件路径
        if median_path is None:
            median_path = out_file_path.replace('.json', '_basic_temp.json')
        basic_temp_file = median_path

        # 第一步：生成基础画像
        basic_profiles = self.generate_basic_profile(start_id, end_id, in_file_path, basic_temp_file, max_workers=max_workers)
        if not basic_profiles:
            print("生成基础画像失败，无法继续")
            return None

        # 第二步：生成关系并完成画像
        complete_profiles = self.generate_relation_and_complete(basic_temp_file, out_file_path, max_workers=max_workers)

        # 清理临时文件
        if os.path.exists(basic_temp_file):
            os.remove(basic_temp_file)

        return complete_profiles

    def sample_from_ref(self, ref_file_path, target_count, required_indices=None, exclude_indices=None):
        """
        从参考文件中有策略地采样目标人数

        参数:
            ref_file_path: 参考JSON文件路径
            target_count: 目标采样人数
            required_indices: 必须包含的索引列表（这些序号的人一定被采样）
            exclude_indices: 必须排除的索引列表

        返回:
            list: 采样后的人物模板列表，每项包含 {'person': ..., 'ref_index': ...}
        """
        import os
        if not os.path.exists(ref_file_path):
            raise FileNotFoundError(f"参考文件不存在: {ref_file_path}")

        with open(ref_file_path, 'r', encoding='utf-8') as f:
            ref_pool = json.load(f)

        total = len(ref_pool)
        print(f"参考池共 {total} 个人物模板")

        if required_indices is None:
            required_indices = []
        if exclude_indices is None:
            exclude_indices = []

        # 校验索引范围
        for idx in required_indices:
            if idx < 0 or idx >= total:
                raise ValueError(f"required_indices 包含无效索引 {idx}，参考池大小为 {total}")
        for idx in exclude_indices:
            if idx < 0 or idx >= total:
                raise ValueError(f"exclude_indices 包含无效索引 {idx}，参考池大小为 {total}")

        # 构建候选池：排除 exclude_indices
        candidate_indices = [i for i in range(total) if i not in exclude_indices]
        # 移除 required_indices 中的重复
        required_set = set(required_indices)

        # 计算还需采样多少
        remain_count = target_count - len(required_set)
        if remain_count < 0:
            print(f"警告: required_indices 数量({len(required_set)}) >= target_count({target_count})，将只使用 required_indices")

        # 从候选池中随机采样（排除已强制纳入的）
        available_indices = [i for i in candidate_indices if i not in required_set]
        if remain_count > 0:
            if remain_count > len(available_indices):
                print(f"警告: 候选人数不足，期望 {remain_count}，实际可用 {len(available_indices)}，将采样所有可用候选人")
                sampled_indices = available_indices
            else:
                import random
                sampled_indices = random.sample(available_indices, remain_count)
        else:
            sampled_indices = []

        # 合并强制索引和采样索引，保持采样顺序
        final_indices = list(required_indices) + sampled_indices
        sampled_templates = [{'person': ref_pool[i], 'ref_index': i} for i in final_indices]

        print(f"采样完成: 强制纳入 {len(required_set)} 人，随机采样 {len(sampled_indices)} 人，共 {len(sampled_templates)} 人")
        print(f"采样索引: {final_indices}")

        return sampled_templates

    def generate_from_ref(self, ref_file_path, target_count, out_file_path,
                         required_indices=None, exclude_indices=None,
                         variant_strength=0.3, max_workers=None):
        """
        从参考文件采样并生成完整画像

        流程: sample_from_ref → 逐个做变体生成 → generate_refine → generate_relation

        参数:
            ref_file_path: 参考JSON文件路径
            target_count: 目标生成人数
            out_file_path: 最终输出文件路径
            required_indices: 必须包含的索引列表
            exclude_indices: 必须排除的索引列表
            variant_strength: 变体强度 (0.0-1.0)，控制 LLM 改变原始模板的程度
            max_workers: 并行线程数
        """
        import os
        # Step 1: 采样
        sampled = self.sample_from_ref(ref_file_path, target_count, required_indices, exclude_indices)

        # Step 2: 构造临时输入文件（采样后的人物模板）
        import tempfile
        temp_dir = tempfile.mkdtemp()
        sampled_input_path = os.path.join(temp_dir, 'sampled_input.json')
        with open(sampled_input_path, 'w', encoding='utf-8') as f:
            json.dump([s['person'] for s in sampled], f, ensure_ascii=False, indent=2)

        # Step 3: 构造 ref_index 映射（用于后续追踪来源）
        ref_index_map = {i: s['ref_index'] for i, s in enumerate(sampled)}

        # Step 4: 生成基础画像
        temp_median = os.path.join(temp_dir, 'basic_temp.json')
        basic_profiles = self.generate_basic_profile(
            start_id=0, end_id=len(sampled),
            in_file_path=sampled_input_path,
            basic_out_file_path=temp_median,
            max_workers=max_workers,
            variant_strength=variant_strength
        )
        if not basic_profiles:
            print("生成基础画像失败，无法继续")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

        # 恢复 ref_index（generate_basic_profile 会重排，但映射在 ref_index_map）
        for bp in basic_profiles:
            orig_idx = bp.get('_index', 0)
            bp['_ref_index'] = ref_index_map.get(orig_idx, orig_idx)

        # Step 5: 生成关系并完成画像
        # 临时保存带 _ref_index 的 basic_profiles
        basic_with_ref = os.path.join(temp_dir, 'basic_with_ref.json')
        with open(basic_with_ref, 'w', encoding='utf-8') as f:
            json.dump(basic_profiles, f, ensure_ascii=False, indent=2)

        complete_profiles = self.generate_relation_and_complete(
            basic_with_ref, out_file_path, max_workers=max_workers
        )

        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)

        if complete_profiles:
            print(f"\n🎉 共生成 {len(complete_profiles)} 个完整画像，已保存到: {out_file_path}")
        return complete_profiles

