# -*- coding: utf-8 -*-
"""事件生成器，负责基于人物画像并行生成多种类型的随机事件"""
import json
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.llm_call import llm_call_j


class EventGenerator:
    """事件生成器类，负责基于人物画像生成多样化的随机事件"""
    
    def __init__(self, persona: Dict):
        """
        初始化事件生成器
        
        Args:
            persona: 人物画像字典
        """
        self.persona = persona
    
    def generate_events(self) -> List[str]:
        """
        并行生成多种类型的随机事件
        
        Returns:
            生成的事件描述列表
        """
        # 定义四个不同的 prompt
        prompts = {
            "base": self._create_base_events_prompt(),
            "development": self._create_development_events_prompt(),
            "others": self._create_others_events_prompt(),
            "challenges": self._create_challenges_events_prompt()
        }
        
        all_events = []
        
        # 并行调用 LLM 生成不同类型的事件
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_type = {
                executor.submit(self._call_llm_for_events, prompt): event_type 
                for event_type, prompt in prompts.items()
            }
            
            for future in as_completed(future_to_type):
                event_type = future_to_type[future]
                try:
                    events = future.result()
                    print(f"✓ {event_type} 类型事件生成了 {len(events)} 个")
                    all_events.extend(events)
                except Exception as e:
                    print(f"✗ {event_type} 类型事件生成失败：{e}")
        
        print(f"\n总共收集了 {len(all_events)} 个灵感事件")
        return all_events
    
    def _create_base_events_prompt(self) -> str:
        """
        创建基础事件 prompt（基于人群特征和常识）
        
        Returns:
            提示词字符串
        """
        return f"""
请充分发挥想象力和发散思维，基于人物画像生成 10-15 个富有创意的重要事件。

## 核心目标
**生成具有一定重要性或时间跨度的事件，这些事件会产生后续影响或发展，形成完整的时间线。**

## 输入数据

### 人物画像
{json.dumps(self.persona, ensure_ascii=False, indent=2)}

## 创作方向

### 1. 人群特征导向
根据性别、年龄、职业、地域等特征，思考该人群可能经历的重要事件。

### 2. 常识性年度事件
基于一年的自然周期和生活规律，如四季变化、周期性事件、节日庆祝等。

### 3. 全新体验与突破
鼓励跳出舒适圈，尝试从未经历过的事物。

## 事件要求

**重要特质（至少满足一项）**：
1. **重要性**：对个人有显著意义的事件（如升职、转行、搬家、结婚等）
2. **时间跨度**：持续数周、数月甚至更长时间的事件（如学习课程、健身计划、项目研发等）
3. **后续影响**：会引发连锁反应或产生长期影响的事件（如认识贵人、培养爱好、建立习惯等）
4. **发展性**：可以作为起点，后续能发展出更多相关事件（如开始健身→参加马拉松→成为教练）

## 输出要求

**只需要输出事件描述数组**，每个描述应包含：
- **事件的详细过程**（时间、地点、人物、活动内容）
- **事件的持续时间**（明确说明是单次事件还是持续性事件，持续多久）
- **可能的发展和后续影响**（这个事件会带来什么变化、引发什么新事件）
- **具体生动的细节**（让事件真实可信）

示例格式：
[
  "张三在 2025 年 3 月报名参加了北京半程马拉松比赛。他从 1 月开始制定训练计划，每周跑步 4 次，从最初的 5 公里逐渐增加到 15 公里。训练过程中，他加入了本地的跑友群，结识了一群热爱跑步的朋友。比赛当天，他以 2 小时 10 分钟的成绩完成了比赛。这次经历不仅让他养成了长期跑步的习惯，还激发了他对长跑的热爱，计划在下半年挑战全程马拉松。",
  
  "李四在 2025 年夏天报名学习了陶艺制作。她在艺术工作室选择了为期三个月的系统课程，从零开始学习拉坯、修坯、上釉等技法。第一个月她只能做出简单的杯子，到第三个月已经能制作精美的茶具套装。课程结束后，她购买了一套家用陶艺设备，在家里建立了小型工作室。这个爱好让她在忙碌的工作之余找到了内心的平静，还通过朋友圈分享作品获得了不少关注，甚至有朋友开始向她定制茶具。"
]

## 注意事项
1. 仅输出 JSON 格式的字符串数组
2. 不需要事件名称、日期、类型等其他字段
3. 每个描述应是一个完整的故事，有起因、经过、结果和后续发展
4. 事件应分布在 2025 年的不同月份
5. **避免日常琐事**（如每天上班、购物、吃饭等），聚焦有重要意义的事件
6. **强调时间跨度**，多描述持续性的活动而非单次行为
7. **突出后续影响**，说明这个事件如何改变了人物的生活或引发了新的发展
8. 发挥创意，产生一些意想不到的好点子
        """
    
    def _create_development_events_prompt(self) -> str:
        """
        创建变化发展事件 prompt（个人成长、转折点）
        
        Returns:
            提示词字符串
        """
        return f"""
请聚焦于人物的**变化和发展**，生成 8-12 个展现个人成长、转折点或重要变化的事件。

## 核心目标
**关注人物在 2025 年可能经历的重要变化和成长节点，这些变化应具有持续性和深远影响。**

## 输入数据

### 人物画像
{json.dumps(self.persona, ensure_ascii=False, indent=2)}

## 变化类型参考

### 1. 个人成长类
- 技能提升：学习新技能、获得证书、能力突破（应说明学习过程和后续应用）
- 认知转变：观念改变、价值观重塑、思维方式升级（应描述转变契机和影响）
- 习惯养成：建立新习惯、戒除旧毛病、生活方式优化（应说明坚持过程和长期效果）

### 2. 职业发展类
- 工作变动：升职、跳槽、转岗、创业（应描述准备过程、适应期和长远影响）
- 项目成就：完成重要项目、获得表彰、业绩突破（应说明项目周期和带来的机会）
- 人际网络：结识导师、建立合作、拓展人脉（应描述关系发展和持续互动）

### 3. 关系建立类
- 新朋友：认识志同道合的伙伴、加入新圈子（应说明相识过程和后续交往）
- 深化关系：友谊升温、恋爱关系、合作伙伴关系（应描述关系发展阶段）
- 社交突破：从内向到外向、学会沟通、建立影响力（应说明改变过程和持续影响）

### 4. 健康与生活类
- 身体变化：减肥成功、健身成果、康复好转（应描述训练/治疗周期和保持计划）
- 心理成长：克服恐惧、建立自信、情绪管理（应说明成长历程和长期改变）
- 生活状态：搬迁、独立生活、生活环境改善（应描述适应过程和新生活的展开）

## 事件要求

**重要特质**：
1. **转折性**：代表人生的重要转折点或里程碑
2. **持续性**：变化不是一蹴而就，而是经历了时间的积累
3. **影响力**：对人物的生活、观念、行为产生深远影响
4. **发展性**：为后续更多的变化和发展奠定基础

## 输出要求

**只需要输出事件描述数组**，每个描述应包含：
- **变化的起因和背景**（为什么会有这个变化）
- **变化的详细过程**（经历了哪些阶段，持续了多长时间）
- **带来的影响和后续发展**（这个变化如何改变了生活，引发了什么新的发展）

示例格式：
[
  "王五在 2025 年初决定转行做产品经理。他从 2 月开始利用下班时间系统学习产品知识，参加了线上课程和线下工作坊，每周投入 15 个小时学习。3 月份，他开始尝试做一个小型产品项目——为一个公益组织设计志愿者管理小程序，在实践中积累经验。在这个过程中，他结识了一位资深产品经理作为导师，定期交流请教。6 月，他成功入职一家互联网公司担任产品助理。虽然起薪比之前低，但这个转变为他的职业发展打开了新的方向。入职后他继续深入学习，计划在两年内成长为独当一面的产品经理，并开始关注教育科技领域的产品机会。",
  
  "赵六原本是个害怕公开演讲的人，每次在会议上发言都会紧张得手心出汗。2025 年 4 月，他在团队会议上第一次主动要求做项目汇报，为此准备了整整一周。之后他有意识地争取发言机会，并在 5 月参加了 Toastmasters 演讲俱乐部，制定了半年的提升计划。在俱乐部里，他从最初的小组分享开始，逐步挑战即兴演讲和备稿演讲。到 9 月，他已经能在部门大会上从容分享项目经验。12 月，他代表公司参加了行业演讲比赛并获得三等奖。这个变化让他在职场中更加自信，开始主动承担需要对外沟通的工作，并计划在明年挑战更大规模的演讲活动。"
]

## 注意事项
1. 仅输出 JSON 格式的字符串数组
2. 不需要事件名称、日期、类型等其他字段
3. **重点描述变化的时间跨度和过程**，不是简单的结果
4. **突出变化的阶段性**，说明是如何一步步发展的
5. **强调长期影响**，这个变化如何持续地改变了人物的生活轨迹
6. 变化可以是渐进的（量变到质变），也可以是转折性的（重大决定）
7. 避免过于突然或不合理的转变，要体现成长的逻辑性
        """
    
    def _create_challenges_events_prompt(self) -> str:
        """
        创建困难挑战波折意外事件 prompt
        
        Returns:
            提示词字符串
        """
        return f"""
请聚焦于人物可能遇到的**困难、挑战、波折和意外事件**，生成 8-12 个具有戏剧性和成长意义的事件。

## 核心目标
**生成生活中的挫折、困难、挑战和意外事件，这些事件虽然艰难但能促进人物成长，并引发后续的发展和转变。**

## 输入数据

### 人物画像
{json.dumps(self.persona, ensure_ascii=False, indent=2)}

## 事件类型参考

### 1. 职业/学业挑战类
- 工作失误：项目失败、决策错误、被领导批评（应说明原因、后果和反思改进）
- 职场挫折：晋升失败、裁员风险、同事矛盾、被排挤孤立（应描述心理变化和应对过程）
- 学业困难：考试失利、论文被拒、研究瓶颈、挂科重修（应说明如何克服或接受）
- 创业波折：资金断裂、合伙人分歧、产品失败、客户流失（应描述坚持或转型的过程）

### 2. 健康/安全意外类
- 突发疾病：急性病住院、慢性病确诊、手术康复（应说明治疗过程和心态调整）
- 意外伤害：交通事故、运动受伤、工伤事故（应描述治疗周期和恢复训练）
- 心理健康：焦虑抑郁、压力过大、失眠困扰、 burnout（应说明寻求帮助和康复历程）
- 安全隐患：家中被盗、财物损失、遇到危险（应说明如何应对和加强防范）

### 3. 人际关系波折类
- 友情危机：朋友背叛、信任破裂、价值观冲突、渐行渐远（应说明关系的变化和修复）
- 恋爱挫折：表白被拒、分手痛苦、异地恋考验、家庭反对（应描述情感历程和成长）
- 家庭矛盾：与父母争吵、代际冲突、家庭变故（应说明理解、和解或独立的过程）
- 社交困境：被误解、被排斥、社交恐惧发作（应说明如何面对和突破）

### 4. 生活/经济困难类
- 经济压力：失业、降薪、投资失败、债务危机（应说明如何度过难关）
- 居住问题：被迫搬家、租房纠纷、房屋损坏、邻居矛盾（应描述解决过程）
- 生活变故：宠物走失或生病、重要物品丢失、计划泡汤（应说明心态调整）
- 期望落差：努力没有回报、梦想破灭、理想与现实差距（应说明重新定位的过程）

### 5. 成长转折类
- 认知冲击：发现真相、信念动摇、世界观颠覆（应说明思想斗争和新的认知）
- 重大选择：两难困境、放弃与坚持、舍与得的抉择（应描述思考过程和最终决定）
- 自我怀疑：能力质疑、方向迷茫、价值困惑（应说明如何重建信心）
- 逆境成长：从失败中学习、在挫折中坚强、化压力为动力（应说明具体的成长收获）

## 事件要求

**重要特质**：
1. **真实性**：困难和挫折是生活的一部分，要真实可信，不要过于戏剧化
2. **成长性**：虽然是负面事件，但最终能促进人物的成长和转变
3. **过程性**：详细描述应对困难的过程，而不是简单的结果
4. **后续影响**：这个困难如何改变了人物，引发了什么新的发展或机会
5. **时间跨度**：应说明困难的持续时间和克服过程的阶段性

## 输出要求

**只需要输出事件描述数组**，每个描述应包含：
- **事件的起因和背景**（为什么会发生这个困难/挑战/意外）
- **详细的应对过程**（经历了哪些阶段，持续了多长时间，采取了什么行动）
- **心理变化历程**（从最初的反应到后来的调整，心态如何变化）
- **结果和后续发展**（最终如何解决或接受，这个经历带来了什么成长和改变）

示例格式：
[
  "2025 年 4 月，张三负责的公司重点项目因为他的一个关键决策失误而失败，给公司造成了 50 万的损失。消息传来时他整个人都懵了，连续几天失眠，反复回想如果当时做了不同选择会怎样。领导找他谈话，虽然没有辞退他，但明确指出了他的问题，并暂停了他的项目管理权限。那段时间是他工作以来最低落的时期，他开始怀疑自己的能力是否适合这个岗位。在家人的支持下，他主动参加了问题分析与决策的培训，并在接下来的两个月里主动向有经验的同事请教，学习系统性的工作方法。6 月，当另一个小项目出现问题时，他主动请缨参与解决，运用学到的方法成功找到了症结所在。这次经历让他深刻认识到谨慎决策的重要性，也学会了如何在失败中学习和成长。年底时，他重新获得了领导的信任，负责一个新的项目，并且做得更加稳健。",
  
  "李四在 2025 年夏天遭遇了职业生涯的第一次裁员。7 月初，公司以业务调整为由通知他被优化，给了他一个月的缓冲期。这个消息对他来说如同晴天霹雳，他在这家公司工作了三年，一直兢兢业业，没想到会是这样的结局。最初的一周他陷入了自我怀疑和焦虑，投了很多简历却少有回音。第二周，大学室友约他吃饭，听他倾诉后鼓励他把这次经历当作重新思考职业方向的机会。李四开始梳理自己的技能和兴趣，发现自己对数据分析很有热情。他利用离职后的空档期报名参加了数据分析培训班，每天投入 8 个小时学习。9 月，他完成了一个数据分析项目作为作品集，并开始面试相关岗位。虽然起薪比之前低了 20%，但他对新领域充满期待。这次裁员虽然痛苦，却让他找到了真正感兴趣的职业方向。",
  
  "王五原本是个乐观开朗的人，但在 2025 年秋天经历了一次严重的信任危机。他一直视为知己的朋友在关键时刻背叛了他——把他私下说的抱怨话传给了当事人，导致他和多年的好友产生严重矛盾。当他得知真相时，感到前所未有的愤怒和失望，甚至开始怀疑自己看人的眼光。之后的一个月里，他变得沉默寡言，不愿与人深交，害怕再次受到伤害。直到 11 月，他参加了一个心理学讲座，讲师说'别人的背叛反映的是他们的品格，不是你的问题'，这句话点醒了他。他开始反思自己在友谊中的边界感问题，学会更成熟地处理人际关系。虽然失去了一段友谊，但他学会了识人和保护自己，也明白了真正的友谊需要建立在相互尊重的基础上。"
]

## 注意事项
1. 仅输出 JSON 格式的字符串数组
2. 不需要事件名称、日期、类型等其他字段
3. **重点描述困难带来的成长**，而不是渲染负面情绪
4. **突出应对过程**，人物是如何一步步走出困境的
5. **强调后续积极影响**，这个挫折如何让人物变得更强大或更成熟
6. 困难应该是可以通过努力克服或接受的，避免过于绝望的情境
7. 要体现时间的推移和阶段的转换，不是突然就解决了
8. 可以包含一些意外的转机和启发，增加故事的戏剧性
        """
    
    def _create_others_events_prompt(self) -> str:
        """
        创建困难挑战波折意外事件 prompt
        
        Returns:
            提示词字符串
        """
        return f"""
请聚焦于人物可能遇到的**困难、挑战、波折和意外事件**，生成 8-12 个具有戏剧性和成长意义的事件。

## 核心目标
**生成生活中的挫折、困难、挑战和意外事件，这些事件虽然艰难但能促进人物成长，并引发后续的发展和转变。**

## 输入数据

### 人物画像
{json.dumps(self.persona, ensure_ascii=False, indent=2)}

## 事件类型参考

### 1. 职业/学业挑战类
- 工作失误：项目失败、决策错误、被领导批评（应说明原因、后果和反思改进）
- 职场挫折：晋升失败、裁员风险、同事矛盾、被排挤孤立（应描述心理变化和应对过程）
- 学业困难：考试失利、论文被拒、研究瓶颈、挂科重修（应说明如何克服或接受）
- 创业波折：资金断裂、合伙人分歧、产品失败、客户流失（应描述坚持或转型的过程）

### 2. 健康/安全意外类
- 突发疾病：急性病住院、慢性病确诊、手术康复（应说明治疗过程和心态调整）
- 意外伤害：交通事故、运动受伤、工伤事故（应描述治疗周期和恢复训练）
- 心理健康：焦虑抑郁、压力过大、失眠困扰、 burnout（应说明寻求帮助和康复历程）
- 安全隐患：家中被盗、财物损失、遇到危险（应说明如何应对和加强防范）

### 3. 人际关系波折类
- 友情危机：朋友背叛、信任破裂、价值观冲突、渐行渐远（应说明关系的变化和修复）
- 恋爱挫折：表白被拒、分手痛苦、异地恋考验、家庭反对（应描述情感历程和成长）
- 家庭矛盾：与父母争吵、代际冲突、家庭变故（应说明理解、和解或独立的过程）
- 社交困境：被误解、被排斥、社交恐惧发作（应说明如何面对和突破）

### 4. 生活/经济困难类
- 经济压力：失业、降薪、投资失败、债务危机（应说明如何度过难关）
- 居住问题：被迫搬家、租房纠纷、房屋损坏、邻居矛盾（应描述解决过程）
- 生活变故：宠物走失或生病、重要物品丢失、计划泡汤（应说明心态调整）
- 期望落差：努力没有回报、梦想破灭、理想与现实差距（应说明重新定位的过程）

### 5. 成长转折类
- 认知冲击：发现真相、信念动摇、世界观颠覆（应说明思想斗争和新的认知）
- 重大选择：两难困境、放弃与坚持、舍与得的抉择（应描述思考过程和最终决定）
- 自我怀疑：能力质疑、方向迷茫、价值困惑（应说明如何重建信心）
- 逆境成长：从失败中学习、在挫折中坚强、化压力为动力（应说明具体的成长收获）

## 事件要求

**重要特质**：
1. **真实性**：困难和挫折是生活的一部分，要真实可信，不要过于戏剧化
2. **成长性**：虽然是负面事件，但最终能促进人物的成长和转变
3. **过程性**：详细描述应对困难的过程，而不是简单的结果
4. **后续影响**：这个困难如何改变了人物，引发了什么新的发展或机会
5. **时间跨度**：应说明困难的持续时间和克服过程的阶段性

## 输出要求

**只需要输出事件描述数组**，每个描述应包含：
- **事件的起因和背景**（为什么会发生这个困难/挑战/意外）
- **详细的应对过程**（经历了哪些阶段，持续了多长时间，采取了什么行动）
- **心理变化历程**（从最初的反应到后来的调整，心态如何变化）
- **结果和后续发展**（最终如何解决或接受，这个经历带来了什么成长和改变）

示例格式：
[
  "2025 年 4 月，张三负责的公司重点项目因为他的一个关键决策失误而失败，给公司造成了 50 万的损失。消息传来时他整个人都懵了，连续几天失眠，反复回想如果当时做了不同选择会怎样。领导找他谈话，虽然没有辞退他，但明确指出了他的问题，并暂停了他的项目管理权限。那段时间是他工作以来最低落的时期，他开始怀疑自己的能力是否适合这个岗位。在家人的支持下，他主动参加了问题分析与决策的培训，并在接下来的两个月里主动向有经验的同事请教，学习系统性的工作方法。6 月，当另一个小项目出现问题时，他主动请缨参与解决，运用学到的方法成功找到了症结所在。这次经历让他深刻认识到谨慎决策的重要性，也学会了如何在失败中学习和成长。年底时，他重新获得了领导的信任，负责一个新的项目，并且做得更加稳健。",
  
  "李四在 2025 年夏天遭遇了职业生涯的第一次裁员。7 月初，公司以业务调整为由通知他被优化，给了他一个月的缓冲期。这个消息对他来说如同晴天霹雳，他在这家公司工作了三年，一直兢兢业业，没想到会是这样的结局。最初的一周他陷入了自我怀疑和焦虑，投了很多简历却少有回音。第二周，大学室友约他吃饭，听他倾诉后鼓励他把这次经历当作重新思考职业方向的机会。李四开始梳理自己的技能和兴趣，发现自己对数据分析很有热情。他利用离职后的空档期报名参加了数据分析培训班，每天投入 8 个小时学习。9 月，他完成了一个数据分析项目作为作品集，并开始面试相关岗位。虽然起薪比之前低了 20%，但他对新领域充满期待。这次裁员虽然痛苦，却让他找到了真正感兴趣的职业方向。",
  
  "王五原本是个乐观开朗的人，但在 2025 年秋天经历了一次严重的信任危机。他一直视为知己的朋友在关键时刻背叛了他——把他私下说的抱怨话传给了当事人，导致他和多年的好友产生严重矛盾。当他得知真相时，感到前所未有的愤怒和失望，甚至开始怀疑自己看人的眼光。之后的一个月里，他变得沉默寡言，不愿与人深交，害怕再次受到伤害。直到 11 月，他参加了一个心理学讲座，讲师说'别人的背叛反映的是他们的品格，不是你的问题'，这句话点醒了他。他开始反思自己在友谊中的边界感问题，学会更成熟地处理人际关系。虽然失去了一段友谊，但他学会了识人和保护自己，也明白了真正的友谊需要建立在相互尊重的基础上。"
]

## 注意事项
1. 仅输出 JSON 格式的字符串数组
2. 不需要事件名称、日期、类型等其他字段
3. **重点描述困难带来的成长**，而不是渲染负面情绪
4. **突出应对过程**，人物是如何一步步走出困境的
5. **强调后续积极影响**，这个挫折如何让人物变得更强大或更成熟
6. 困难应该是可以通过努力克服或接受的，避免过于绝望的情境
7. 要体现时间的推移和阶段的转换，不是突然就解决了
8. 可以包含一些意外的转机和启发，增加故事的戏剧性
        """
    
    def filter_events(self, events: List[str], summary_text: str) -> List[str]:
        """
        基于一年总结文本，批量过滤掉不适合插入的事件
        
        Args:
            events: 待过滤的事件列表
            summary_text: 一年的总结文本，用于判断事件是否适合插入
        
        Returns:
            通过过滤的事件列表
        """
        filtered_events = []
        batch_size = 10
        
        # 将事件分批处理，每批 10 个
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            print(f"\n正在过滤第 {i//batch_size + 1} 批事件（{len(batch)} 个）...")
            
            try:
                prompt = self._create_filter_prompt(batch, summary_text)
                result = llm_call_j(prompt)
                
                # 解析结果，获取通过过滤的事件索引
                passed_indices = self._parse_filter_result(result, len(batch))
                
                # 添加通过过滤的事件
                for idx in passed_indices:
                    if 0 <= idx < len(batch):
                        filtered_events.append(batch[idx])
                        
                print(f"✓ 本批通过 {len(passed_indices)} 个事件")
                
            except Exception as e:
                print(f"✗ 本批过滤失败：{e}")
                # 如果过滤失败，保留所有事件（保守策略）
                filtered_events.extend(batch)
        
        print(f"\n过滤完成：原始 {len(events)} 个事件 → 通过 {len(filtered_events)} 个事件")
        return filtered_events
    
    def _create_filter_prompt(self, events: List[str], summary_text: str) -> str:
        """
        创建事件过滤的 prompt
        
        Args:
            events: 待过滤的事件列表（一批，最多 10 个）
            summary_text: 一年的总结文本
        
        Returns:
            提示词字符串
        """
        events_str = "\n\n".join([f"事件{i+1}: {event}" for i, event in enumerate(events)])
        
        return f"""
请根据以下一年总结文本，判断给定的事件中哪些**不适合插入**到这一年中。

## 一年总结文本
{summary_text}

## 待判断的事件
{events_str}

## 过滤标准

**应该被过滤掉（不适合插入）的事件**：
1. **时间冲突**：事件发生的时间与总结中明确提到的安排相矛盾
2. **逻辑冲突**：事件与总结中描述的事实、状态或关系相矛盾
3. **重复事件**：事件已经在总结中出现过，或是已有事件的简单重复
4. **不合理事件**：事件在当前情境下明显不合理或不可能发生
5. **无关事件**：事件与总结中的生活轨迹完全无关，显得突兀

**应该保留的事件**：
1. **补充事件**：能够丰富和补充总结中未详细描述的时期或方面
2. **合理延伸**：是总结中提到的事件的合理前因后果或延伸
3. **丰富细节**：为总结中提到的重要节点提供具体的过程和细节
4. **填补空白**：发生在总结中较少涉及的月份或领域

## 输出要求

请输出一个 JSON 数组，包含**应该保留的事件的索引**（从 0 开始）。

示例格式：
[0, 2, 3, 5]

这表示保留索引为 0、2、3、5 的事件，过滤掉其他事件。

## 注意事项

1. 仅输出 JSON 格式的整数数组
2. 不需要任何解释或其他文本
3. 如果不确定是否应该保留，倾向于保留（避免误删）
4. 重点关注明显的冲突和不合理，不要过于严格
        """
    
    def _parse_filter_result(self, result: str, expected_count: int) -> List[int]:
        """
        解析 LLM 返回的过滤结果
        
        Args:
            result: LLM 返回的文本
            expected_count: 预期的最大索引值 +1
        
        Returns:
            通过过滤的事件索引列表
        """
        try:
            # 提取 JSON 部分
            start_idx = result.find('[')
            end_idx = result.rfind(']')
            
            if start_idx == -1 or end_idx == -1 or start_idx > end_idx:
                print("⚠️  无法解析 JSON 数组，返回空列表")
                return []
            
            json_str = result[start_idx:end_idx + 1]
            indices = json.loads(json_str)
            
            # 验证是否为整数列表
            if not isinstance(indices, list):
                print("⚠️  返回结果不是数组格式，返回空列表")
                return []
            
            # 过滤掉超出范围的索引
            valid_indices = [idx for idx in indices if isinstance(idx, int) and 0 <= idx < expected_count]
            
            if len(valid_indices) != len(indices):
                print(f"⚠️  有 {len(indices) - len(valid_indices)} 个索引超出范围，已过滤")
            
            return valid_indices
            
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON 解析失败：{e}")
            return []
        except Exception as e:
            print(f"⚠️  解析失败：{e}")
            return []
    
    def main(self, target_count: int = 20, sample_ratio: float = 0.5, summary_text: str = None) -> List[str]:
        """
        主函数：执行完整的事件生成、采样、过滤流程
        
        Args:
            target_count: 最终目标事件个数
            sample_ratio: 采样比例（0-1），用于在过滤前随机丢弃一部分事件
            summary_text: 一年的总结文本，用于过滤冲突事件
        
        Returns:
            最终筛选出的 target_count 个事件
        """
        import random
        
        print("="*60)
        print("开始执行事件生成与筛选流程")
        print("="*60)
        
        # Step 1: 生成事件（4 个类别）
        print("\n[Step 1] 生成初始事件...")
        all_events_dict = {
            "base": [],
            "development": [],
            "others": [],
            "challenges": []
        }
        
        # 定义四个 prompt
        prompts = {
            "base": self._create_base_events_prompt(),
            "development": self._create_development_events_prompt(),
            "others": self._create_others_events_prompt(),
            "challenges": self._create_challenges_events_prompt()
        }
        
        # 并行生成事件
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_type = {
                executor.submit(self._call_llm_for_events, prompt): event_type 
                for event_type, prompt in prompts.items()
            }
            
            for future in as_completed(future_to_type):
                event_type = future_to_type[future]
                try:
                    events = future.result()
                    all_events_dict[event_type] = events
                    print(f"✓ {event_type} 类型生成了 {len(events)} 个事件")
                except Exception as e:
                    print(f"✗ {event_type} 类型生成失败：{e}")
        
        # 合并所有事件，保留类别信息
        all_events = []
        event_types = []
        for event_type, events in all_events_dict.items():
            all_events.extend(events)
            event_types.extend([event_type] * len(events))
        
        print(f"\n初始事件总数：{len(all_events)} 个")
        
        # Step 2: 按比例采样，保留每个类别至少 1 个事件
        print(f"\n[Step 2] 随机采样（目标：{int(target_count * 2)} 个事件，保留比例：{sample_ratio}）...")
        
        # 确保每个类别至少有 1 个事件
        sampled_indices = set()
        for event_type in ["base", "development", "others", "challenges"]:
            type_indices = [i for i, t in enumerate(event_types) if t == event_type]
            if type_indices:
                # 从每个类别中随机选 1 个
                sampled_indices.add(random.choice(type_indices))
        
        # 计算还需要多少个事件
        remaining_count = int(target_count * 2) - len(sampled_indices)
        
        if remaining_count > 0 and len(all_events) > len(sampled_indices):
            # 从剩余事件中随机选择
            available_indices = [i for i in range(len(all_events)) if i not in sampled_indices]
            additional_count = min(remaining_count, len(available_indices))
            additional_indices = random.sample(available_indices, additional_count)
            sampled_indices.update(additional_indices)
        
        # 创建采样后的事件列表
        sampled_events = [all_events[i] for i in sorted(sampled_indices)]
        sampled_types = [event_types[i] for i in sorted(sampled_indices)]
        
        print(f"✓ 采样后事件数：{len(sampled_events)} 个")
        print(f"  各类别分布：")
        for event_type in ["base", "development", "others", "challenges"]:
            count = sampled_types.count(event_type)
            print(f"    - {event_type}: {count} 个")
        
        # Step 3: 基于总结文本过滤
        if summary_text:
            print(f"\n[Step 3] 基于总结文本过滤...")
            filtered_events = self.filter_events(sampled_events, summary_text)
            print(f"✓ 过滤后事件数：{len(filtered_events)} 个")
        else:
            print(f"\n[Step 3] 跳过过滤（未提供总结文本）")
            filtered_events = sampled_events
        
        # Step 4: 选择最终的 target_count 个事件
        print(f"\n[Step 4] 选择最终的 {target_count} 个事件...")
        
        if len(filtered_events) <= target_count:
            final_events = filtered_events
            print(f"⚠️  过滤后事件不足 {target_count} 个，保留全部 {len(filtered_events)} 个")
        else:
            # 再次确保每个类别至少有 1 个
            final_indices = set()
            for event_type in ["base", "development", "others", "challenges"]:
                type_indices = [i for i, (event, etype) in enumerate(zip(filtered_events, sampled_types)) 
                               if i < len(filtered_events) and etype == event_type]
                # 只考虑在 filtered_events 范围内的索引
                type_indices = [i for i in type_indices if i < len(filtered_events)]
                if type_indices:
                    final_indices.add(random.choice(type_indices))
            
            # 从剩余事件中随机选择
            remaining = target_count - len(final_indices)
            if remaining > 0:
                available = [i for i in range(len(filtered_events)) if i not in final_indices]
                additional = random.sample(available, min(remaining, len(available)))
                final_indices.update(additional)
            
            final_events = [filtered_events[i] for i in sorted(final_indices)]
        
        print(f"\n" + "="*60)
        print(f"流程完成！")
        print(f"  初始生成：{len(all_events)} 个")
        print(f"  采样后：{len(sampled_events)} 个")
        print(f"  过滤后：{len(filtered_events)} 个")
        print(f"  最终结果：{len(final_events)} 个")
        print("="*60)
        
        return final_events
    
    def _call_llm_for_events(self, prompt: str) -> List[str]:
        """
        调用 LLM 生成事件
        
        Args:
            prompt: 提示词
        
        Returns:
            事件描述列表
        """
        try:
            response = llm_call_j(prompt).strip()
            # 提取 JSON 部分
            start_idx = response.find('[')
            end_idx = response.rfind(']')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = response[start_idx:end_idx + 1]
                result = json.loads(json_response)
                return result
            else:
                print("无法解析 LLM 返回的 JSON")
                return []
        except Exception as e:
            print(f"LLM 调用失败：{e}")
            return []
