import json
import os
import threading
from utils.llm_call import llm_call

class EventTreeClassifier:
    def __init__(self):
        # Define the schema from scheduler.py
        self.schema = {
            "运动": ["游泳",
                     "健身锻炼",
                     "跑步",
                     "骑行",
                     "户外步行",
                     "武术",
                     "舞蹈",
                     "羽毛球",
                     "棒球",
                     "滑雪",
                     "足球",
                     "篮球",
                     "轮滑",
                     "户外探险",
                     "健美操",
                     "漫步机",
                     "射箭",
                     "羽毛球",
                     "芭蕾舞",
                     "沙滩足球",
                     "沙滩排球",
                     "肚皮舞",
                     "冬季两项",
                     "BMX自行车",
                     "搏击操",
                     "保龄球",
                     "拳击",
                     "闭气测试",
                     "闭气训练",
                     "蹦极",
                     "皮划艇",
                     "核心训练",
                     "板球",
                     "越野滑雪",
                     "Crossfit",
                     "冰壶",
                     "飞镖",
                     "自由潜水",
                     "躲避球",
                     "龙舟",
                     "漂流",
                     "椭圆机",
                     "电子竞技",
                     "击剑",
                     "钓鱼", "跳伞",
                     "双杠",
                     "跑酷",
                     "体能训练",
                     "普拉提",
                     "操场赛跑",
                     "广场舞",
                     "台球",
                     "泳池游泳",
                     "赛车",
                     "攀岩",
                     "轮滑",
                     "划船机",
                     "赛艇",
                     "橄榄球",
                     "帆船",
                     "水肺潜水",
                     "体感运动",
                     "藤球",
                     "毽球",
                     "单杠",
                     "滑板",
                     "滑冰",
                     "滑雪",
                     "滑雪橇",
                     "单板滑雪",
                     "雪地摩托",
                     "垒球",
                     "动感单车",
                     "壁球",
                     "爬楼",
                     "踏步机",
                     "街舞",
                     "力量训练",
                     "桨板冲浪",
                     "冲浪",
                     "秋千",
                     "乒乓球",
                     "跆拳道",
                     "太极拳",
                     "网球",
                     "越野跑",
                     "铁人三项",
                     "拔河",
                     "排球",
                     "瑜伽"],
            "工作": [
                "出差",
                "上班通勤",
                "下班通勤",
                "办公",
                "会议研讨",
                "出差 - 那年今日",
                "请假",
                "加班",
                "工作总结",
                "工作交流",
                "培训",
                "报销"
            ],
            "社交动作": [
                "与某人通话",
                "与某人视频通话",
                "向某人发送即时消息",
                "接收某人发送的即时消息",
                "向某人发送邮件",
                "接收某人发送的工作邮件",
                "邀请某人参加日历事件",
                "接受某人发起的日历邀请",
                "与某人同处一地（短时）",
                "与某人参加同一会议",
                "与某人参加同一培训 / 讲座",
                "在通讯录中新增联系人",
                "更新某人联系信息",
                "删除 / 屏蔽某人"
            ],
            "人际交往": [
                "参加聚餐",
                "参加婚礼",
                "参加生日派对",
                "参加公司团建",
                "参加社区活动",
                "拜访他人住所",
                "探望住院人员",
                "参加节日庆典",
                "参加宗教仪式",
                "参加慈善活动",
                "参加政治集会",
                "参加亲子活动",
                "陪同前往学校 / 培训机构",
                "组织活动",
                "预订餐厅 / 场地",
                "宠物照料"
            ],
            "教育": [
                "作业",
                "会议研讨",
                "课程",
                "请假",
                "上班通勤",
                "下班通勤",
                "背单词",
                "预约考试",
                "参加考试",
                "成绩查询"
            ],
            "便捷生活": [
                "家政",
                "政务和公共服务",
                "生活缴费",
                "跑腿代办",
                "3C 数码维修",
                "行李寄存"
            ],
            "财务管理": [
                "银行入账",
                "银行出账",
                "金融 app 入账",
                "金融 app 出账",
                "记账",
                "理财",
                "保险",
                "支付订单",
                "房产装修",
                "房产交易",
                "汽车交易"
            ],
            "健康管理": [
                "运动记录",
                "体检",
                "挂号",
                "查看电子病历或检查报告",
                "服药",
                "心理咨询",
                "睡眠管理",
                "饮食管理",
                "精神健康管理"
            ],
            "出行旅游": [
                "旅游",
                "行走",
                "跑",
                "骑车",
                "乘飞机",
                "乘火车",
                "乘地铁",
                "开车",
                "乘车",
                "乘交通工具",
                "行程规划",
                "购票",
                "检票",
                "退票",
                "改签",
                "景点浏览",
                "购物",
                "逛街",
                "城市漫游",
                "出海游船",
                "露营",
                "度假村放松",
                "酒店休息",
                "就餐",
                "出发",
                "城市切换",
                "达到",
                "城市旅游",
                "旅程",
                "游玩主题乐园",
                "参观动物园",
                "参观博物馆",
                "参观美术馆",
                "参观海洋馆",
                "节假日回乡",
                "居家拜访",
                "扫墓",
                "探亲"
            ],
            "休闲娱乐": [
                "看演唱会",
                "看话剧",
                "看音乐剧",
                "看展览",
                "看脱口秀",
                "看相声",
                "看演唱会",
                "看音乐会",
                "看音乐节",
                "看戏曲",
                "看电竞赛事",
                "看舞蹈",
                "看体育赛事",
                "看魔术",
                "看电影",
                "看亲子演出",
                "划船",
                "射击射箭",
                "溜冰",
                "马术",
                "钓鱼",
                "按摩足疗",
                "洗浴汗蒸",
                "密室逃脱",
                "游戏厅",
                "网吧",
                "采摘农家乐",
                "撸宠",
                "K 歌",
                "酒吧",
                "轰趴",
                "剧本杀",
                "逛街",
                "电子游戏",
                "做 SPA",
                "桌游",
                "茶馆棋牌",
                "DIY 手工"
            ]
        }
        
    def load_event_tree(self, file_path):
        """Load event tree data from JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def extract_bottom_events(self, events):
        """Extract all bottom-level events (decompose=0) from the event tree"""
        bottom_events = []
        
        def recursive_extract(event_list):
            for event in event_list:
                if event.get("decompose") == 0:
                    bottom_events.append(event)
                elif "subevent" in event and event["subevent"]:
                    recursive_extract(event["subevent"])
        
        recursive_extract(events)
        return bottom_events
    
    def classify_event(self, event):
        """Classify a single event using LLM and return the matching schema category"""
        prompt = f"""
        你是一位事件分类专家，请根据以下事件信息和事件类别列表，将事件分类到最合适的最底层类别中。
        
        事件类别列表：{json.dumps(self.schema, ensure_ascii=False)}
        
        事件信息：
        事件名称：{event.get('name', '')}
        事件描述：{event.get('description', '')}
        事件类型：{event.get('type', '')}
        
        输出要求：
        1. 仅输出最底层的类别名称，直接作为文本输出
        2. 如果事件与schema数据中的所有类别都不匹配，请基于schema的类别描述风格（描述动作），自定义一个事件的类别。
        3. 只返回类别名称，不要包含任何解释、JSON格式或其他文本
        """
        
        try:
            response = llm_call(prompt)
            # Clean the response
            response = response.strip()
            # Remove any markdown formatting
            if response.startswith('```'):
                response = response.split('```')[1]
                if response.startswith('json'):
                    response = response[4:].strip()
            
            return response
        except Exception as e:
            print(f"Error classifying event {event.get('event_id')}: {e}")
            return ""
    
    def process_events(self, file_path, output_path=None):
        """Process all events in the event tree file"""
        print("Loading event tree data...")
        event_tree = self.load_event_tree(file_path)
        
        print("Extracting bottom-level events...")
        bottom_events = self.extract_bottom_events(event_tree)
        total_events = len(bottom_events)
        print(f"Found {total_events} bottom-level events.")
        
        # Calculate events per thread
        num_threads = 24
        events_per_thread = total_events // num_threads
        remainder = total_events % num_threads
        
        # Split events into chunks
        event_chunks = []
        start = 0
        for i in range(num_threads):
            end = start + events_per_thread
            if i < remainder:
                end += 1  # Distribute remaining events
            event_chunks.append(bottom_events[start:end])
            start = end
        
        # Counter for processed events
        processed_count = 0
        processed_lock = threading.Lock()
        
        def worker(events):
            nonlocal processed_count
            for event in events:
                try:
                    # Classify the event
                    classification = self.classify_event(event)
                    # Replace the type field with new classification
                    event["type"] = classification
                    
                    # Update processed count
                    with processed_lock:
                        processed_count += 1
                        if processed_count % 10 == 0 or processed_count == total_events:
                            print(f"Processed {processed_count}/{total_events} events")
                except Exception as e:
                    print(f"Error processing event {event.get('event_id')}: {e}")
                    # Keep original type if error occurs
                    pass
        
        print(f"Classifying events with {num_threads} threads...")
        # Create and start threads
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(event_chunks[i],))
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        print(f"All {total_events} events processed successfully.")
        
        # Save the classified results with original event tree structure
        if output_path is None:
            output_path = "classified_event_tree.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(event_tree, f, ensure_ascii=False, indent=2)
        
        print(f"Classification completed. Results saved to {output_path}")
        return event_tree

if __name__ == "__main__":
    classifier = EventTreeClassifier()
    input_file = r"D:\pyCharmProjects\pythonProject4\data\fenghaoran\event_tree2.json"
    classifier.process_events(input_file)