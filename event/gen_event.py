# -*- coding: utf-8 -*-
import json
from utils.IO import *
from utils.llm_call import *
from event.templates import *

def gen_event1(persona):

    prompt = template1_1.format(persona=persona)
    res = llm_call_reason(prompt, context, record=1)
    print(res)
    data = json.loads(res)

    prompt = template1_2
    res2 = llm_call(prompt,context,record=1)
    print(res2)
    data2 = json.loads(res2)

    prompt = template1_3
    res3 = llm_call(prompt, context, record=0)
    print(res3)
    data3 = json.loads(res3)

    return data+data2+data3

def gen_event2(persona):

    prompt = template2.format(persona=persona)
    res = llm_call_reason(prompt, context, record=0)

    return res

def gen_event3(persona,content):

    prompt = template3_1.format(persona=persona)
    res = llm_call(prompt, context, record=1)
    print(res)
    prompt = template3_2.format(content = content)
    res = llm_call(prompt, context, record=1)
    print(res)
    prompt = template3_3
    res = llm_call(prompt, context, record=0)
    print(res)
    return json.loads(res)

persona = '''
 {
        "name": "徐静",
        "birth": "1993-07-10",
        "age": 28,
        "nationality": "汉",
        "home_address": {
            "province": "上海市",
            "city": "上海市",
            "district": "浦东新区",
            "street_name": "张杨路",
            "street_number": "123号"
        },
        "birth_place": {
            "province": "上海市",
            "city": "上海市",
            "district": "浦东新区"
        },
        "gender": "女",
        "education": "普通高中",
        "job": "服装店销售主管",
        "occupation": "时尚服饰零售企业",
        "workplace": {
            "province": "上海市",
            "city": "上海市",
            "district": "浦东新区",
            "street_name": "世纪大道",
            "street_number": "88号"
        },
        "belief": "不信仰宗教",
        "salary": 100000.0,
        "body": {
            "height": 158,
            "weight": 62.5,
            "BMI": 25.04
        },
        "family": "未婚",
        "personality": {
            "mbti": "ESFJ",
        },
        "hobbies": [
            "逛街购物",
            "听音乐",
            "羽毛球",
            “收藏纪念币”
        ],
        "favorite_foods": [
            "上海小笼包",
            "抹茶拿铁",
            "草莓蛋糕"
        ],
        "memory_date": [
            "2012-06-15：第一份工作入职纪念日",
            "2020-08-20：晋升销售主管日"
        ],
        "healthy_desc": "个人整体健康状况良好，无慢性病史，不定期进行健康体检，每年就医几次主要是常规检查。保持每周三次的体育锻炼习惯，注重个人护理和作息规律。",
        "lifestyle_desc": "日常生活高度依赖互联网，尤其喜欢使用社交媒体和购物APP获取信息。休闲活动包括每周两到三次逛街购物、在家听流行音乐、以及参加瑜伽锻炼。每月与朋友聚餐或看电影一次，每年会有一到两次短途旅行探亲或度假，生活风格偏向现代都市休闲型。",
        "economic_desc": "家庭年收入约10万元，拥有1处房产和家用汽车，目前没有股票、基金等投资活动，消费习惯偏谨慎，注重基本生活保障。",
        "work_desc": "在家族经营的服装零售企业工作，每周工作48小时，担任销售主管职务，负责店面管理和客户服务工作，工作稳定且与家庭生活紧密结合。",
        "experience_desc": "徐静自出生起便生活在上海浦东新区，2012年高中毕业后加入家族经营的服装零售企业，从基层销售员做起，通过努力逐步晋升为销售主管，负责店面运营和团队管理。她的工作经历稳定，与家庭事业深度绑定，积累了丰富的客户服务经验。",
        "description": "徐静是一位28岁的上海本地女性，高中毕业后在家族服装零售企业工作，现任销售主管。作为ESFJ人格类型，她重视家庭关系和社会和谐，性格热情负责。日常生活中，她喜欢逛街购物、听音乐和体育锻炼，收藏纪念币是她的独特爱好。健康状况良好，注重规律作息。经济状况稳定，拥有房产和汽车，消费观念务实。工作与家庭生活紧密结合，未来计划开设自己的服装店并保持家庭旅行传统。她与家人关系密切，在工作中善于与客户沟通，生活中注重与朋友保持联系。",
        "relation": [
            [
                {
                    "name": "徐明",
                    "relation": "父亲",
                    "social circle": "家庭圈",
                    "gender": "男",
                    "age": 58,
                    "birth_date": "1965-03-12",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "浦东新区",
                        "street_name": "张杨路",
                        "street_number": "123号"
                    },
                    "birth_place": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "黄浦区"
                    },
                    "personality": "ISTJ",
                    "economic_level": "中产",
                    "occupation": "服装零售企业主",
                    "organization": "明芳服饰有限公司",
                    "nickname": "老爸",
                    "relation_description": "徐静的父亲，与妻子共同经营家族服装企业。年轻时从裁缝学徒做起，1990年创办服装店并逐步发展成连锁企业。现在虽已半退休，仍会每周到店里巡视指导。与女儿关系亲密，每周至少三次家庭聚餐，经常一起讨论店铺经营。支持女儿开设分店的计划，时常传授商业经验。"
                },
                {
                    "name": "李芳",
                    "relation": "母亲",
                    "social circle": "家庭圈",
                    "gender": "女",
                    "age": 56,
                    "birth_date": "1967-08-25",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "浦东新区",
                        "street_name": "张杨路",
                        "street_number": "123号"
                    },
                    "birth_place": {
                        "province": "江苏省",
                        "city": "苏州市",
                        "district": "姑苏区"
                    },
                    "personality": "ISFJ",
                    "economic_level": "中产",
                    "occupation": "服装企业财务主管",
                    "organization": "明芳服饰有限公司",
                    "nickname": "妈妈",
                    "relation_description": "徐静的母亲，负责家族企业的财务管理工作。原籍苏州，年轻时来上海打工认识徐明后结婚。性格温柔细心，不仅管理公司账务，还包办全家饮食起居。每天都会为女儿准备午餐便当，周末常一起逛街选购新款服装。母女关系融洽，经常交流生活琐事和情感问题。"
                },
                {
                    "name": "徐强",
                    "relation": "哥哥",
                    "social circle": "家庭圈",
                    "gender": "男",
                    "age": 32,
                    "birth_date": "1991-11-03",
                    "home_address": {
                        "province": "浙江省",
                        "city": "杭州市",
                        "district": "西湖区",
                        "street_name": "文三路",
                        "street_number": "456号"
                    },
                    "birth_place": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "浦东新区"
                    },
                    "personality": "ENTJ",
                    "economic_level": "中产",
                    "occupation": "电商运营总监",
                    "organization": "杭州某电商平台",
                    "nickname": "强哥",
                    "relation_description": "徐静的哥哥，大学毕业后选择在杭州发展电商事业。虽然不在家族企业工作，但经常为妹妹提供线上销售建议。每月会回上海探望父母，与妹妹见面聚餐。兄妹关系良好，通过微信保持日常联系，主要讨论工作发展和家庭事务。徐静计划开设分店时也会征求哥哥的意见。"
                }
            ],
            [
                {
                    "name": "王丽",
                    "relation": "闺蜜",
                    "social circle": "高中同学圈",
                    "gender": "女",
                    "age": 28,
                    "birth_date": "1993-03-15",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "徐汇区",
                        "street_name": "淮海中路",
                        "street_number": "456号"
                    },
                    "birth_place": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "徐汇区"
                    },
                    "personality": "ENFP",
                    "economic_level": "中产",
                    "occupation": "市场专员",
                    "organization": "上海某广告公司",
                    "nickname": "丽丽",
                    "relation_description": "王丽是徐静高中时期的同桌，两人从学生时代就建立了深厚的友谊。现在同在上海工作，每周会约一次逛街或下午茶，经常分享工作和生活琐事。她们保持着密切的微信联系，节假日会一起聚餐或看电影，偶尔还会约上其他高中同学聚会。"
                },
                {
                    "name": "张婷",
                    "relation": "闺蜜",
                    "social circle": "高中同学圈",
                    "gender": "女",
                    "age": 29,
                    "birth_date": "1992-11-22",
                    "home_address": {
                        "province": "浙江省",
                        "city": "杭州市",
                        "district": "西湖区",
                        "street_name": "文三路",
                        "street_number": "789号"
                    },
                    "birth_place": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "静安区"
                    },
                    "personality": "ISFJ",
                    "economic_level": "中产",
                    "occupation": "小学教师",
                    "organization": "杭州市某实验小学",
                    "nickname": "婷婷",
                    "relation_description": "张婷是徐静高中时期的好友，大学毕业后选择到杭州发展。虽然分隔两地，但她们每月都会视频通话两到三次，分享各自的生活近况。每年春节张婷回上海探亲时，她们必定会见面聚餐，平时通过微信保持密切联系，互相支持对方的事业发展。"
                },
                {
                    "name": "赵小美",
                    "relation": "高中同学",
                    "social circle": "高中同学圈",
                    "gender": "女",
                    "age": 28,
                    "birth_date": "1993-09-08",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "闵行区",
                        "street_name": "虹梅路",
                        "street_number": "321号"
                    },
                    "birth_place": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "闵行区"
                    },
                    "personality": "ISTJ",
                    "economic_level": "小康",
                    "occupation": "会计",
                    "organization": "上海某会计师事务所",
                    "nickname": "小美",
                    "relation_description": "赵小美是徐静高中同学，现在同在上海工作。她们保持着每月一次的聚会频率，通常是在周末一起吃饭或逛街。作为高中同学圈的核心成员，赵小美经常组织同学聚会，与徐静及其他同学保持着稳定的联系，彼此在工作中也会互相提供建议和支持。"
                },
                {
                    "name": "钱多多",
                    "relation": "高中同学",
                    "social circle": "高中同学圈",
                    "gender": "女",
                    "age": 28,
                    "birth_date": "1993-12-03",
                    "home_address": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "南山区",
                        "street_name": "科技园路",
                        "street_number": "654号"
                    },
                    "birth_place": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "黄浦区"
                    },
                    "personality": "ENTP",
                    "economic_level": "中产",
                    "occupation": "互联网产品经理",
                    "organization": "深圳某科技公司",
                    "nickname": "多多",
                    "relation_description": "钱多多是徐静的高中同学，大学毕业后选择到深圳发展。她们主要通过微信保持联系，每季度会视频通话一次。钱多多每年回上海探亲时会与徐静见面，平时在同学群里活跃互动。虽然距离较远，但她们仍保持着深厚的同学情谊，经常分享职场经验和生活趣事。"
                }
            ],
            [
                {
                    "name": "陈丽",
                    "relation": "同事",
                    "social circle": "工作圈",
                    "gender": "女",
                    "age": 26,
                    "birth_date": "1997-03-15",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "浦东新区",
                        "street_name": "金桥路",
                        "street_number": "456号"
                    },
                    "birth_place": {
                        "province": "江苏省",
                        "city": "南京市"
                    },
                    "personality": "ENFP",
                    "economic_level": "中等",
                    "occupation": "服装销售员",
                    "organization": "时尚服饰零售企业",
                    "nickname": "丽丽",
                    "relation_description": "陈丽是徐静在服装店的同事，两人相识于2019年工作期间。作为销售团队的核心成员，她们每天共同处理店面事务，配合默契。工作之余会一起在商场餐厅吃午餐，周末偶尔相约逛街淘货。两人居住在同一城区，保持每周5天的工作接触和每月1-2次的私人聚会。"
                },
                {
                    "name": "刘伟",
                    "relation": "同事",
                    "social circle": "工作圈",
                    "gender": "男",
                    "age": 30,
                    "birth_date": "1993-11-22",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "闵行区",
                        "street_name": "虹梅路",
                        "street_number": "789号"
                    },
                    "birth_place": {
                        "province": "浙江省",
                        "city": "杭州市"
                    },
                    "personality": "ISTJ",
                    "economic_level": "中等",
                    "occupation": "仓储管理员",
                    "organization": "时尚服饰零售企业",
                    "nickname": "伟哥",
                    "relation_description": "刘伟负责店铺的仓储管理工作，与徐静在工作中密切配合已有3年。他做事严谨认真，经常协助徐静处理货品调配和库存盘点。两人主要在工作场合交流，偶尔参加公司组织的团建活动。虽然私下交往不多，但工作关系稳定可靠，保持每天工作时间的常规互动。"
                },
                {
                    "name": "赵敏",
                    "relation": "同事",
                    "social circle": "工作圈",
                    "gender": "女",
                    "age": 29,
                    "birth_date": "1994-05-08",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "徐汇区",
                        "street_name": "淮海中路",
                        "street_number": "321号"
                    },
                    "birth_place": {
                        "province": "上海市",
                        "city": "上海市"
                    },
                    "personality": "ESFP",
                    "economic_level": "中等",
                    "occupation": "销售助理",
                    "organization": "时尚服饰零售企业",
                    "nickname": "敏敏",
                    "relation_description": "赵敏是徐静最亲密的同事之一，两人既是工作搭档也是朋友。她们经常一起讨论销售策略，下班后偶尔相约喝咖啡聊天。赵敏性格活泼开朗，与徐静在工作上形成良好互补。两人保持每周工作日的密切合作，每月会有2-3次私人聚会，关系融洽而稳定。"
                },
                {
                    "name": "孙老板",
                    "relation": "供应商",
                    "social circle": "工作圈",
                    "gender": "男",
                    "age": 45,
                    "birth_date": "1978-09-12",
                    "home_address": {
                        "province": "广东省",
                        "city": "广州市",
                        "district": "天河区",
                        "street_name": "体育西路",
                        "street_number": "668号"
                    },
                    "birth_place": {
                        "province": "广东省",
                        "city": "潮州市"
                    },
                    "personality": "ENTJ",
                    "economic_level": "富裕",
                    "occupation": "服装厂老板",
                    "organization": "广州时尚制衣厂",
                    "nickname": "孙总",
                    "relation_description": "孙老板是服装店的主要供应商，与徐静保持业务往来已有5年。他每季度会来上海考察市场，徐静负责接待和洽谈订单。两人主要通过电话和微信沟通业务，见面频率较低但合作稳定。孙老板注重产品质量和商业信誉，与徐静建立了相互信任的工作关系。"
                },
                {
                    "name": "周经理",
                    "relation": "商场经理",
                    "social circle": "工作圈",
                    "gender": "男",
                    "age": 38,
                    "birth_date": "1985-12-03",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "静安区",
                        "street_name": "南京西路",
                        "street_number": "1000号"
                    },
                    "birth_place": {
                        "province": "上海市",
                        "city": "上海市"
                    },
                    "personality": "ESTJ",
                    "economic_level": "中高",
                    "occupation": "商场运营经理",
                    "organization": "世纪商场管理公司",
                    "nickname": "周经理",
                    "relation_description": "周经理是店铺所在商场的运营负责人，与徐静在工作上有频繁的业务往来。他负责商场的日常管理和商户协调，徐静经常需要与他沟通店铺运营事宜。两人每月会有1-2次正式会议，平时通过商场内部系统保持联系。周经理处事专业严谨，与徐静保持着良好的工作关系。"
                }
            ],
            [
                {
                    "name": "孙秀英",
                    "relation": "邻居",
                    "social circle": "社区圈",
                    "gender": "女",
                    "age": 65,
                    "birth_date": "1959-03-22",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "浦东新区",
                        "street_name": "张杨路",
                        "street_number": "121号"
                    },
                    "birth_place": {
                        "province": "江苏省",
                        "city": "南通市"
                    },
                    "personality": "ISFJ",
                    "economic_level": "中等",
                    "occupation": "退休教师",
                    "organization": "浦东新区实验小学（已退休）",
                    "nickname": "孙阿姨",
                    "relation_description": "孙阿姨是徐静家对门的老邻居，退休前在附近小学任教。两人因社区活动相识，孙阿姨经常关心徐静的工作生活，会分享自己做的家常菜。现在主要通过微信保持联系，每周会碰面两三次，一起在小区散步或喝茶聊天。孙阿姨把徐静当作自家晚辈般照顾，逢年过节会互相赠送小礼物。"
                }
            ],
            [
                {
                    "name": "周晓雯",
                    "relation": "瑜伽教练",
                    "social circle": "瑜伽圈",
                    "gender": "女",
                    "age": 32,
                    "birth_date": "1991-03-15",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "徐汇区",
                        "street_name": "淮海中路",
                        "street_number": "356号"
                    },
                    "birth_place": {
                        "province": "浙江省",
                        "city": "杭州市"
                    },
                    "personality": "ENFJ",
                    "economic_level": "中产",
                    "occupation": "瑜伽馆",
                    "organization": "静心瑜伽工作室",
                    "nickname": "周老师",
                    "relation_description": "周晓雯是徐静在静心瑜伽工作室的专职教练，拥有8年瑜伽教学经验。两人通过2019年的团体课程相识，现在保持每周三次的私教课联系。上课时周教练会针对徐静的身体状况设计个性化训练方案，课后偶尔会交流健康饮食心得。虽然周教练住在徐汇区，但工作室距离徐静工作地点仅15分钟车程，教学关系稳定持续。"
                },
                {
                    "name": "李娜",
                    "relation": "瑜伽伙伴",
                    "social circle": "瑜伽圈",
                    "gender": "女",
                    "age": 29,
                    "birth_date": "1994-09-22",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "浦东新区",
                        "street_name": "陆家嘴环路",
                        "street_number": "188号"
                    },
                    "birth_place": {
                        "province": "江苏省",
                        "city": "苏州市"
                    },
                    "personality": "ISFP",
                    "economic_level": "中产",
                    "occupation": "银行职员",
                    "organization": "浦东发展银行",
                    "nickname": "娜娜",
                    "relation_description": "李娜是徐静在瑜伽课上认识的固定练习伙伴，同在周教练的早课班练习两年。作为银行柜员，李娜下班后常与徐静结伴练习瑜伽，周末偶尔一起逛商场喝下午茶。两人住在同一行政区，每月会约两三次课后聚餐，交流工作和生活近况。李娜性格内向但体贴，经常与徐静分享护肤心得，是瑜伽圈里最亲近的练习搭档。"
                },
                {
                    "name": "王芳",
                    "relation": "瑜伽伙伴",
                    "social circle": "瑜伽圈",
                    "gender": "女",
                    "age": 31,
                    "birth_date": "1992-12-05",
                    "home_address": {
                        "province": "江苏省",
                        "city": "南京市",
                        "district": "鼓楼区",
                        "street_name": "北京西路",
                        "street_number": "72号"
                    },
                    "birth_place": {
                        "province": "安徽省",
                        "city": "合肥市"
                    },
                    "personality": "ENTP",
                    "economic_level": "小康",
                    "occupation": "自由职业者",
                    "organization": "自媒体工作室",
                    "nickname": "芳芳",
                    "relation_description": "王芳原是上海工作的瑜伽同伴，2021年移居南京发展自媒体事业，但仍通过线上群组与徐静保持联系。两人在2018年瑜伽进修班相识，曾经常结伴参加周末瑜伽工作坊。现在主要通过微信群分享瑜伽视频和健康资讯，每年王芳回沪探亲时会与徐静、李娜小聚。虽然异地发展，但三人仍维持着瑜伽圈的友谊，经常互相关注彼此的生活动态。"
                }
            ],
            [
                {
                    "name": "张秀英",
                    "relation": "姨妈",
                    "social circle": "亲戚圈",
                    "gender": "女",
                    "age": 58,
                    "birth_date": "1965-03-22",
                    "home_address": {
                        "province": "江苏省",
                        "city": "南京市",
                        "district": "鼓楼区",
                        "street_name": "中山北路",
                        "street_number": "256号"
                    },
                    "birth_place": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "黄浦区"
                    },
                    "personality": "ISFJ",
                    "economic_level": "小康",
                    "occupation": "退休教师",
                    "organization": "南京市鼓楼区实验小学",
                    "nickname": "张阿姨",
                    "relation_description": "张秀英是徐静母亲的姐姐，退休前在南京担任小学教师。两人虽然分居上海和南京，但每月会通过视频通话联系两到三次，主要聊家常和健康话题。每年春节和国庆节徐静会去南京探望，一起逛夫子庙、品尝南京小吃。张秀英经常关心徐静的婚姻和工作情况，是徐静重要的长辈倾诉对象。"
                },
                {
                    "name": "刘建国",
                    "relation": "舅舅",
                    "social circle": "亲戚圈",
                    "gender": "男",
                    "age": 55,
                    "birth_date": "1968-09-15",
                    "home_address": {
                        "province": "浙江省",
                        "city": "杭州市",
                        "district": "西湖区",
                        "street_name": "文三路",
                        "street_number": "189号"
                    },
                    "birth_place": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "静安区"
                    },
                    "personality": "ESTP",
                    "economic_level": "富裕",
                    "occupation": "餐饮企业主",
                    "organization": "杭帮菜餐饮连锁集团",
                    "nickname": "刘叔叔",
                    "relation_description": "刘建国是徐静的舅舅，在杭州经营连锁餐饮企业。他性格开朗，经常给徐静提供创业建议。两人每季度通一次电话，主要讨论商业经营和市场趋势。每年徐静会专程到杭州品尝舅舅的新菜品，同时考察当地服装市场。刘建国曾资助徐静参加商业管理培训，是她在事业上的重要支持者。"
                },
                {
                    "name": "陈明",
                    "relation": "表弟",
                    "social circle": "亲戚圈",
                    "gender": "男",
                    "age": 25,
                    "birth_date": "1998-12-03",
                    "home_address": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "南山区",
                        "street_name": "科技园路",
                        "street_number": "66号"
                    },
                    "birth_place": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "浦东新区"
                    },
                    "personality": "ENTJ",
                    "economic_level": "中产",
                    "occupation": "互联网产品经理",
                    "organization": "深圳某科技公司",
                    "nickname": "小明",
                    "relation_description": "陈明是徐静姑姑的儿子，目前在深圳从事互联网行业。两人从小一起在上海长大，现在主要通过微信保持联系，每周会分享生活趣事和工作心得。陈明经常给徐静推荐新的购物APP和时尚资讯，徐静则向他请教数字化营销知识。每年春节家庭聚会时见面，会一起逛商场、讨论最新的科技产品。"
                }
            ],
            [
                {
                    "name": "吴明远",
                    "relation": "家庭医生",
                    "social circle": "医疗圈",
                    "gender": "男",
                    "age": 45,
                    "birth_date": "1978-03-22",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "徐汇区",
                        "street_name": "淮海中路",
                        "street_number": "568号"
                    },
                    "birth_place": {
                        "province": "江苏省",
                        "city": "南京市",
                        "district": "鼓楼区"
                    },
                    "personality": "ISTJ",
                    "economic_level": "中产",
                    "occupation": "全科医生",
                    "organization": "浦东新区社区卫生服务中心",
                    "nickname": "吴医生",
                    "relation_description": "吴医生是徐静的家庭医生，五年前通过社区健康管理项目相识。他每月为徐静提供一次健康咨询，主要通过微信进行线上沟通，偶尔在社区卫生服务中心面诊。吴医生性格严谨负责，擅长慢性病管理和健康指导，与徐静保持着专业而友好的医患关系。"
                }
            ],
            [
                {
                    "name": "郑明辉",
                    "relation": "健身教练",
                    "social circle": "健身圈",
                    "gender": "男",
                    "age": 32,
                    "birth_date": "1992-03-15",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "徐汇区",
                        "street_name": "漕溪北路",
                        "street_number": "258号"
                    },
                    "birth_place": {
                        "province": "江苏省",
                        "city": "南京市",
                        "district": "鼓楼区"
                    },
                    "personality": "ESTP",
                    "economic_level": "中产",
                    "occupation": "健身教练",
                    "organization": "力健健身俱乐部",
                    "nickname": "郑教练",
                    "relation_description": "郑明辉是徐静在力健健身俱乐部的私人教练，两人通过健身课程相识已有两年。他擅长制定个性化训练计划，每周指导徐静进行三次力量训练和有氧运动。平时主要通过微信沟通训练安排和饮食建议，每月会组织会员户外拓展活动。郑教练性格开朗务实，注重训练效果的同时也会关心会员的生活状态。"
                }
            ],
            [
                {
                    "name": "王明远",
                    "relation": "纪念币藏友",
                    "social circle": "收藏圈",
                    "gender": "男",
                    "age": 45,
                    "birth_date": "1978-03-15",
                    "home_address": {
                        "province": "北京市",
                        "city": "北京市",
                        "district": "朝阳区",
                        "street_name": "建国门外大街",
                        "street_number": "88号"
                    },
                    "birth_place": {
                        "province": "北京市",
                        "city": "北京市"
                    },
                    "personality": "ISTJ",
                    "economic_level": "中产",
                    "occupation": "金融投资顾问",
                    "organization": "北京金融投资有限公司",
                    "nickname": "老王",
                    "relation_description": "王明远是徐静在纪念币收藏展会上认识的藏友，两人因共同爱好结缘。他目前在北京市从事金融投资工作，虽然分隔两地，但每月会通过线上交流收藏心得，偶尔会互相邮寄稀有纪念币。每年徐静去北京出差时会约见面，一起参观钱币博物馆或古玩市场。"
                }
            ],
            [
                {
                    "name": "李雪梅",
                    "relation": "同行朋友",
                    "social circle": "行业圈",
                    "gender": "女",
                    "age": 32,
                    "birth_date": "1991-03-15",
                    "home_address": {
                        "province": "浙江省",
                        "city": "杭州市",
                        "district": "西湖区",
                        "street_name": "文三路",
                        "street_number": "456号"
                    },
                    "birth_place": {
                        "province": "浙江省",
                        "city": "杭州市"
                    },
                    "personality": "ENTJ",
                    "economic_level": "中产",
                    "occupation": "区域运营经理",
                    "organization": "江南时尚集团",
                    "nickname": "雪梅姐",
                    "relation_description": "李雪梅是徐静在行业交流会上认识的同行朋友，两人因对服装零售业的共同兴趣而结缘。她们平时主要通过微信交流行业动态，每季度会在上海或杭州见面一次，通常选择在商圈咖啡馆讨论市场趋势和经营管理经验。虽然分处两地，但会互相推荐优质供应商和客户资源，去年还合作举办过跨区域促销活动。"
                }
            ],
            [
                {
                    "name": "张明远",
                    "relation": "熟客",
                    "social circle": "客户圈",
                    "gender": "男",
                    "age": 35,
                    "birth_date": "1988-03-15",
                    "home_address": {
                        "province": "浙江省",
                        "city": "杭州市",
                        "district": "西湖区",
                        "street_name": "文三路",
                        "street_number": "456号"
                    },
                    "birth_place": {
                        "province": "浙江省",
                        "city": "宁波市"
                    },
                    "personality": "ENTJ",
                    "economic_level": "中产",
                    "occupation": "互联网公司市场总监",
                    "organization": "杭州某科技股份有限公司",
                    "nickname": "张总",
                    "relation_description": "张明远是徐静服装店的长期客户，五年前因工作需要购买商务服装而结识。他每季度会从杭州来上海出差时到店选购，偏好简约商务风格。两人保持着专业的客户关系，主要通过微信沟通新款到货信息，平均每两月联系一次。见面时徐静会为他提供专业的穿搭建议，偶尔会聊及各自的工作近况。"
                }
            ]
        ]
    }
'''

persona2 = """
{
        "name": "马晓梅",
        "birth": "1980-09-12",
        "age": 41,
        "nationality": "汉",
        "home_address": {
            "province": "天津市",
            "city": "天津市",
            "district": "西青区",
            "street_name": "杨柳青镇",
            "street_number": "古运河路15号"
        },
        "birth_place": {
            "province": "天津市",
            "city": "天津市",
            "district": "西青区"
        },
        "gender": "女",
        "education": "初中",
        "job": "家庭主妇",
        "occupation": "无",
        "workplace": {
            "province": "",
            "city": "",
            "district": "",
            "street_name": "",
            "street_number": ""
        },
        "belief": "不信仰宗教",
        "salary": 0.0,
        "body": {
            "height": 165,
            "weight": 55.0,
            "BMI": 20.2
        },
        "family": "初婚有配偶,育有3个孩子",
        "personality": {
            "mbti": "ISFJ",
        },
        "hobbies": [
            "做手工（刺绣，擅长传统京津绣法）",
            "与朋友聚会",
            "在家听音乐",
            "看电视"
        ],
        "favorite_foods": [
            "天津包子",
            "糖醋里脊",
            "家常豆腐"
        ],
        "memory_date": [
            "2005-08-20 结婚纪念日",
            "2010-06-01 第一个孩子出生日"
        ],
        "healthy_desc": "个人整体健康状况良好，无慢性病史，过去三年未进行系统体检，但日常会关注身体基本状况。没有规律运动习惯，主要以家务活动维持日常体能，个人护理习惯简单务实。",
        "lifestyle_desc": "日常生活以家庭为中心，每天固定看电视获取信息，每月数次与朋友聚会和做手工刺绣，偶尔上网浏览。休闲活动偏好室内，几乎不参与体育锻炼和户外活动，生活风格偏向传统保守，注重家庭互动。",
        "economic_desc": "家庭年收入约4万元，拥有一处房产，无家用汽车。消费习惯节俭，无任何投资活动，经济状况稳定但较为紧张，主要支出用于子女教育和家庭日常开销。",
        "work_desc": "目前全职照顾家庭，无固定工作安排。早年曾从事农业劳动，现已将重心完全转向家庭事务管理。",
        "experience_desc": "出生于天津西青区并始终在当地生活，青少年时期协助家庭从事蔬菜种植和家禽养殖等农活，培养了勤劳节俭的习惯。20岁与同乡结婚后，逐步从农业劳动转型为全职家庭主妇，先后生育三个孩子，长期专注于子女照料和家务管理，积累了丰富的家庭经营经验。人生经历以家庭为核心，形成了稳定务实的生活模式。",
        "description": "马晓梅是一位41岁的天津女性，初中文化程度，现为全职家庭主妇，育有三个孩子。作为ISFJ人格类型，她重视家庭稳定和安全，价值观偏向保守和家庭导向。日常以家务管理和子女照料为主，爱好手工刺绣和亲友聚会，生活节奏规律且注重传统。她长期扎根天津西青区，早年有过务农经历，如今将全部精力投入家庭建设，经常组织家庭活动并关注子女教育发展。未来希望继续深化家庭凝聚力，并通过种植菜园等生活化方式提升家庭生活质量。",
        "relation": [
            [
                {
                    "name": "马建国",
                    "relation": "丈夫",
                    "social circle": "家庭圈",
                    "gender": "男",
                    "age": 43,
                    "birth_date": "1978-05-23",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "杨柳青镇",
                        "street_number": "古运河路15号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ISTJ",
                    "economic_level": "小康",
                    "occupation": "货车司机",
                    "organization": "天津物流运输公司",
                    "nickname": "老马",
                    "relation_description": "马晓梅的丈夫，两人于2005年结婚。马建国长期从事物流运输工作，经常往返于京津冀地区。夫妻二人共同抚养三个孩子，平时主要通过电话联系，周末马建国回家后一起吃饭、看电视。马建国性格稳重务实，负责家庭主要经济来源，马晓梅则负责家务和子女教育。"
                },
                {
                    "name": "马小芳",
                    "relation": "女儿",
                    "social circle": "家庭圈",
                    "gender": "女",
                    "age": 14,
                    "birth_date": "2007-11-18",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "杨柳青镇",
                        "street_number": "古运河路15号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ENFP",
                    "economic_level": "学生",
                    "occupation": "初中生",
                    "organization": "西青区实验中学",
                    "nickname": "芳芳",
                    "relation_description": "马晓梅的大女儿，现就读初中二年级。性格活泼开朗，喜欢绘画和音乐。每天放学回家后与母亲一起做家务，周末常陪母亲去菜市场。马晓梅经常辅导她的作业，母女关系亲密。马小芳与弟弟妹妹相处融洽，经常帮助照顾弟弟妹妹的学习。"
                },
                {
                    "name": "马小刚",
                    "relation": "儿子",
                    "social circle": "家庭圈",
                    "gender": "男",
                    "age": 12,
                    "birth_date": "2009-08-03",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "杨柳青镇",
                        "street_number": "古运河路15号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ISTP",
                    "economic_level": "学生",
                    "occupation": "小学生",
                    "organization": "杨柳青第一小学",
                    "nickname": "刚子",
                    "relation_description": "马晓梅的独子，小学六年级学生。性格内向但动手能力强，喜欢拼装模型。马晓梅每天接送他上下学，周末带他去公园玩耍。马小刚与两个姐姐关系很好，经常一起做作业。马晓梅注重培养他的独立性，让他参与简单的家务劳动。"
                },
                {
                    "name": "马小丽",
                    "relation": "女儿",
                    "social circle": "家庭圈",
                    "gender": "女",
                    "age": 9,
                    "birth_date": "2012-12-25",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "杨柳青镇",
                        "street_number": "古运河路15号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ISFP",
                    "economic_level": "学生",
                    "occupation": "小学生",
                    "organization": "杨柳青第一小学",
                    "nickname": "丽丽",
                    "relation_description": "马晓梅的小女儿，小学三年级学生。性格温柔乖巧，喜欢跟着母亲学习刺绣。马晓梅每天接送她上下学，晚上陪她写作业。马小丽与哥哥姐姐关系亲密，经常一起玩耍。马晓梅特别关注她的成长，经常带她参加社区儿童活动。"
                },
                {
                    "name": "张秀英",
                    "relation": "母亲",
                    "social circle": "家庭圈",
                    "gender": "女",
                    "age": 68,
                    "birth_date": "1953-03-15",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "李七庄街道",
                        "street_number": "津涞公路28号"
                    },
                    "birth_place": {
                        "province": "河北省",
                        "city": "沧州市"
                    },
                    "personality": "ESFJ",
                    "economic_level": "退休",
                    "occupation": "退休工人",
                    "organization": "原天津纺织厂",
                    "nickname": "妈",
                    "relation_description": "马晓梅的母亲，现居住在距离女儿家3公里处。张秀英退休前是纺织厂工人，现在独居生活。马晓梅每周探望母亲2-3次，帮忙采购生活用品和打扫卫生。母女二人经常电话联系，周末有时一起包饺子。张秀英偶尔来女儿家帮忙照看孙子孙女，传授马晓梅传统刺绣技艺。"
                },
                {
                    "name": "马志强",
                    "relation": "父亲",
                    "social circle": "家庭圈",
                    "gender": "男",
                    "age": 70,
                    "birth_date": "1951-07-08",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "李七庄街道",
                        "street_number": "津涞公路28号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ISTJ",
                    "economic_level": "退休",
                    "occupation": "退休农民",
                    "organization": "无",
                    "nickname": "爸",
                    "relation_description": "马晓梅的父亲，与妻子张秀英同住。马志强年轻时务农，现在退休在家养花种草。马晓梅每周探望父母时都会与父亲聊天，听取生活建议。马志强偶尔来女儿家帮忙修理家具，教授外孙们种植技巧。父女关系融洽，马晓梅遇到重大事情时会征求父亲意见。"
                }
            ],
            [
                {
                    "name": "王美玲",
                    "relation": "闺蜜",
                    "social circle": "发小圈",
                    "gender": "女",
                    "age": 41,
                    "birth_date": "1980-03-15",
                    "home_address": {
                        "province": "北京市",
                        "city": "北京市",
                        "district": "朝阳区",
                        "street_name": "望京街道",
                        "street_number": "阜通东大街6号院"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ESFJ",
                    "economic_level": "中产",
                    "occupation": "幼儿园教师",
                    "organization": "北京市朝阳区实验幼儿园",
                    "nickname": "玲玲",
                    "relation_description": "王美玲与马晓梅是自幼一起长大的发小，两人在西青区同一所小学和初中就读。王美玲大学毕业后到北京发展，现为幼儿园教师。她们每月通过视频通话联系2-3次，聊家庭生活和子女教育话题，每年春节王美玲回天津时会与马晓梅见面聚餐，一起回忆童年趣事。"
                },
                {
                    "name": "李红梅",
                    "relation": "闺蜜",
                    "social circle": "发小圈",
                    "gender": "女",
                    "age": 42,
                    "birth_date": "1979-12-08",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "中北镇",
                        "street_number": "星光路88号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ISFP",
                    "economic_level": "小康",
                    "occupation": "超市收银员",
                    "organization": "永辉超市西青店",
                    "nickname": "红姐",
                    "relation_description": "李红梅与马晓梅、王美玲是初中同学，三人组成发小闺蜜圈。李红梅一直在西青区生活，目前在超市工作。她与马晓梅保持密切往来，每周会相约一起做手工刺绣或看电视，周末经常带着孩子互相串门。三人每年会在马晓梅家组织一次发小聚会，分享生活近况。"
                }
            ],
            [
                {
                    "name": "赵秀英",
                    "relation": "邻居",
                    "social circle": "社区圈",
                    "gender": "女",
                    "age": 58,
                    "birth_date": "1966-03-15",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "杨柳青镇古运河路",
                        "street_number": "12号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ESFJ",
                    "economic_level": "小康",
                    "occupation": "退休教师",
                    "organization": "西青区实验小学",
                    "nickname": "赵阿姨",
                    "relation_description": "赵阿姨是住在隔壁单元的退休教师，与马晓梅相识已有十年。两人经常在小区花园偶遇聊天，每周会相约一起买菜或做手工刺绣。赵阿姨擅长北方剪纸，经常指导马晓梅传统手工艺，逢年过节会互相赠送自制点心。虽然年龄相差较大，但两人因共同爱好成为忘年交，保持着每周见面2-3次的亲密邻里关系。"
                },
                {
                    "name": "刘美兰",
                    "relation": "邻居",
                    "social circle": "社区圈",
                    "gender": "女",
                    "age": 49,
                    "birth_date": "1975-08-22",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "杨柳青镇古运河路",
                        "street_number": "18号"
                    },
                    "birth_place": {
                        "province": "河北省",
                        "city": "沧州市",
                        "district": "运河区"
                    },
                    "personality": "ISFP",
                    "economic_level": "中等",
                    "occupation": "超市收银员",
                    "organization": "物美超市西青店",
                    "nickname": "刘大妈",
                    "relation_description": "刘大妈是五年前搬来的邻居，在附近超市工作。两人因孩子在同一所小学读书而熟识，经常一起接送孩子上下学。周末时常相约在小区凉亭喝茶聊天，分享育儿经验和家常菜做法。刘大妈性格温和内向，但和马晓梅很投缘，每月会组织一次小型邻里聚餐。虽然刘大妈原籍河北，但已在天津生活多年，两人保持着每周见面1-2次的稳定邻里交往。"
                },
                {
                    "name": "高玉珍",
                    "relation": "邻居",
                    "social circle": "社区圈",
                    "gender": "女",
                    "age": 62,
                    "birth_date": "1962-11-30",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "杨柳青镇古运河路",
                        "street_number": "9号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "南开区"
                    },
                    "personality": "ENFJ",
                    "economic_level": "小康",
                    "occupation": "退休护士",
                    "organization": "天津市第一中心医院",
                    "nickname": "高阿姨",
                    "relation_description": "高阿姨是社区里的热心人，退休前在医院工作。她与马晓梅通过社区活动相识，经常组织邻里健康知识分享会。高阿姨精通养生之道，常教马晓梅一些简单的保健方法，两人还一起参加社区的刺绣兴趣小组。作为社区圈的活跃分子，高阿姨经常协调赵阿姨、刘大妈等邻居聚会，每月固定组织一次手工活动。三人虽然年龄不同，但因住在同一条街上，形成了密切的邻里互助网络。"
                }
            ],
            [
                {
                    "name": "陈晓红",
                    "relation": "家长",
                    "social_circle": "子女教育圈",
                    "gender": "女",
                    "age": 39,
                    "birth_date": "1984-05-18",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "张家窝镇",
                        "street_number": "学府花园12号楼3单元"
                    },
                    "birth_place": {
                        "province": "河北省",
                        "city": "沧州市"
                    },
                    "personality": "ESFJ",
                    "economic_level": "中等",
                    "occupation": "超市收银员",
                    "organization": "永旺超市西青店",
                    "nickname": "陈姐",
                    "relation_description": "陈晓红是马晓梅大儿子同班同学的母亲，两人通过家长会相识已有三年。由于同住西青区，她们每月会相约在学校门口接送孩子时聊天，偶尔周末带孩子一起逛公园。陈晓红性格热情外向，经常分享育儿经验，两人主要通过微信和家长群保持联系，每周会有2-3次互动。"
                },
                {
                    "name": "张丽华",
                    "relation": "家长",
                    "social_circle": "子女教育圈",
                    "gender": "女",
                    "age": 42,
                    "birth_date": "1981-12-03",
                    "home_address": {
                        "province": "北京市",
                        "city": "北京市",
                        "district": "海淀区",
                        "street_name": "中关村大街",
                        "street_number": "甲68号院5号楼"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市"
                    },
                    "personality": "ISTJ",
                    "economic_level": "中上",
                    "occupation": "小学教师",
                    "organization": "北京市海淀区实验小学",
                    "nickname": "张老师",
                    "relation_description": "张丽华是马晓梅二女儿的班主任，原籍天津后来到北京发展。两人通过家长微信群建立联系，每学期家长会时见面交流。张老师做事严谨认真，经常通过电话和微信向马晓梅反馈孩子在校情况。由于异地原因，她们主要通过线上方式联系，每月沟通1-2次，寒暑假张老师回天津时会相约喝茶。"
                },
                {
                    "name": "杨美玲",
                    "relation": "家长",
                    "social_circle": "子女教育圈",
                    "gender": "女",
                    "age": 38,
                    "birth_date": "1985-08-22",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "李七庄街道",
                        "street_number": "津涞花园8号楼2单元"
                    },
                    "birth_place": {
                        "province": "山东省",
                        "city": "德州市"
                    },
                    "personality": "ISFP",
                    "economic_level": "中等",
                    "occupation": "家政服务员",
                    "organization": "天津好阿姨家政公司",
                    "nickname": "小杨",
                    "relation_description": "杨美玲是马晓梅小儿子幼儿园同学的母亲，两人在幼儿园接送时结识。同住西青区的她们经常相约带孩子去社区游乐场玩耍，杨美玲性格温和内向，擅长手工制作，与马晓梅有共同的刺绣爱好。她们每周见面2-3次，平时通过微信分享育儿心得和手工技巧，形成了稳定的家长互助关系。"
                }
            ],
            [
                {
                    "name": "周秀英",
                    "relation": "亲戚",
                    "social circle": "亲戚圈",
                    "gender": "女",
                    "age": 58,
                    "birth_date": "1966-03-15",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "杨柳青镇",
                        "street_number": "古运河路28号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ESFJ",
                    "economic_level": "温饱",
                    "occupation": "退休工人",
                    "organization": "原天津纺织厂",
                    "nickname": "周大姐",
                    "relation_description": "周秀英是马晓梅的堂姐，两人从小在同一个胡同长大。现在住在同一条街上，每周会相约一起买菜、做手工刺绣。周末经常带着自己做的点心去马晓梅家串门，帮忙照看孩子。两人保持着密切的亲戚往来，逢年过节都会互相走动。"
                },
                {
                    "name": "马建军",
                    "relation": "兄弟",
                    "social circle": "亲戚圈",
                    "gender": "男",
                    "age": 45,
                    "birth_date": "1979-12-08",
                    "home_address": {
                        "province": "北京市",
                        "city": "北京市",
                        "district": "朝阳区",
                        "street_name": "望京街道",
                        "street_number": "阜通东大街6号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ISTJ",
                    "economic_level": "小康",
                    "occupation": "出租车司机",
                    "organization": "北京出租汽车公司",
                    "nickname": "建军",
                    "relation_description": "马建军是马晓梅的弟弟，年轻时到北京打工定居。每月会通过视频通话联系两三次，过年时一定会回天津团聚。虽然分隔两地，但姐弟感情深厚，马建军经常给姐姐寄北京特产，马晓梅也会托人带天津小吃给弟弟。"
                },
                {
                    "name": "王淑芬",
                    "relation": "亲戚",
                    "social circle": "亲戚圈",
                    "gender": "女",
                    "age": 62,
                    "birth_date": "1962-07-22",
                    "home_address": {
                        "province": "河北省",
                        "city": "石家庄市",
                        "district": "长安区",
                        "street_name": "建北街道",
                        "street_number": "和平东路32号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ISFJ",
                    "economic_level": "温饱",
                    "occupation": "退休教师",
                    "organization": "原石家庄市第二中学",
                    "nickname": "王阿姨",
                    "relation_description": "王淑芬是马晓梅的远房姑姑，年轻时嫁到石家庄。两人主要通过微信保持联系，每逢重要节日会互致问候。王阿姨退休后经常回天津探亲，每次回来都会给马晓梅的孩子带礼物，两人见面时会一起回忆家乡往事。"
                },
                {
                    "name": "林美华",
                    "relation": "亲戚",
                    "social circle": "亲戚圈",
                    "gender": "女",
                    "age": 49,
                    "birth_date": "1975-05-18",
                    "home_address": {
                        "province": "山东省",
                        "city": "青岛市",
                        "district": "市南区",
                        "street_name": "香港中路",
                        "street_number": "86号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ENFP",
                    "economic_level": "小康",
                    "occupation": "海鲜批发商",
                    "organization": "青岛海鲜批发市场",
                    "nickname": "林大姐",
                    "relation_description": "林美华是马晓梅的表姐，在青岛经营海鲜生意。虽然距离较远，但两人感情很好，每年夏天林美华都会寄新鲜海产给马晓梅一家。通过微信群与周秀英等亲戚保持联系，经常在群里分享生活趣事，形成了活跃的亲戚社交圈。"
                }
            ],
            [
                {
                    "name": "孙小妹",
                    "relation": "手工友",
                    "social circle": "刺绣圈",
                    "gender": "女",
                    "age": 38,
                    "birth_date": "1985-03-15",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "杨柳青镇",
                        "street_number": "运河东路32号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ESFJ",
                    "economic_level": "中等",
                    "occupation": "手工艺品店店员",
                    "organization": "杨柳青手工艺坊",
                    "nickname": "小妹",
                    "relation_description": "孙小妹是马晓梅在社区刺绣班认识的同好，两人因对传统刺绣的共同热爱成为好友。她们每周三下午固定参加刺绣班活动，经常交流京津绣法的技巧心得。孙小妹性格开朗热情，经常组织小型手工艺聚会，马晓梅是她最固定的参与伙伴。两人居住在同一社区，除了刺绣活动外，偶尔会相约逛集市购买布料，平时通过微信分享刺绣作品照片。"
                },
                {
                    "name": "钱大姐",
                    "relation": "手工友",
                    "social circle": "刺绣圈",
                    "gender": "女",
                    "age": 52,
                    "birth_date": "1971-08-22",
                    "home_address": {
                        "province": "河北省",
                        "city": "沧州市",
                        "district": "运河区",
                        "street_name": "解放西路",
                        "street_number": "88号"
                    },
                    "birth_place": {
                        "province": "河北省",
                        "city": "沧州市",
                        "district": "运河区"
                    },
                    "personality": "ISFP",
                    "economic_level": "中等",
                    "occupation": "退休教师",
                    "organization": "沧州实验小学（已退休）",
                    "nickname": "钱姐",
                    "relation_description": "钱大姐是马晓梅通过孙小妹介绍认识的资深刺绣爱好者，退休前是美术教师，精通多种刺绣技法。虽然住在沧州，但每月会来天津参加一次刺绣交流活动，与马晓梅等人聚会。钱大姐性格温和耐心，经常指导马晓梅改进刺绣技巧，两人通过微信视频定期交流创作心得。她们三人组成的刺绣小团体每年会合作完成一幅大型刺绣作品，钱大姐负责设计构图，马晓梅和孙小妹负责具体制作。"
                },
                {
                    "name": "黄阿姨",
                    "relation": "手工友",
                    "social circle": "刺绣圈",
                    "gender": "女",
                    "age": 58,
                    "birth_date": "1965-12-03",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "杨柳青镇",
                        "street_number": "古运河路8号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "INFJ",
                    "economic_level": "小康",
                    "occupation": "传统刺绣传承人",
                    "organization": "西青区非物质文化遗产保护中心",
                    "nickname": "黄老师",
                    "relation_description": "黄阿姨是社区刺绣班的指导老师，与马晓梅相识多年。作为非物质文化遗产传承人，她不仅教授刺绣技艺，还经常组织学员参加文化展览活动。黄阿姨住在马晓梅同一条街上，两人经常在买菜途中相遇闲聊。她欣赏马晓梅对传统刺绣的坚持，经常邀请她参与社区文化活动的筹备工作。这个刺绣圈的三位成员虽然年龄、背景不同，但都因对传统手工艺的热爱而紧密联系，黄阿姨作为长辈和导师，为这个小团体提供艺术指导和精神支持。"
                }
            ],
            [
                {
                    "name": "吴秀英",
                    "relation": "聚会友",
                    "social circle": "亲友聚会圈",
                    "gender": "女",
                    "age": 58,
                    "birth_date": "1966-03-15",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区",
                        "street_name": "杨柳青镇",
                        "street_number": "运河东路28号"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "西青区"
                    },
                    "personality": "ESFJ",
                    "economic_level": "小康",
                    "occupation": "退休教师",
                    "organization": "西青区实验小学",
                    "nickname": "吴姐",
                    "relation_description": "吴秀英是马晓梅在社区活动中认识的聚会好友，两人因共同的刺绣爱好结缘。作为退休教师，她经常组织社区手工活动，每月会邀请马晓梅和其他朋友到家中喝茶刺绣。她们见面时主要交流育儿经验和手工技巧，偶尔会一起逛菜市场。虽然同住西青区，但因各自家庭事务繁忙，主要通过微信保持联系，每周会视频通话一次讨论手工花样。"
                },
                {
                    "name": "郑玉华",
                    "relation": "聚会友",
                    "social circle": "亲友聚会圈",
                    "gender": "女",
                    "age": 49,
                    "birth_date": "1975-08-22",
                    "home_address": {
                        "province": "河北省",
                        "city": "唐山市",
                        "district": "路北区",
                        "street_name": "建设大街",
                        "street_number": "幸福小区6栋302"
                    },
                    "birth_place": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "河西区"
                    },
                    "personality": "ISFP",
                    "economic_level": "中等",
                    "occupation": "服装店店主",
                    "organization": "华美服装店",
                    "nickname": "华姐",
                    "relation_description": "郑玉华是马晓梅通过吴秀英介绍认识的聚会朋友，原籍天津后嫁到唐山经营服装店。她每季度回天津探亲时会组织小型聚会，三人常一起品尝天津小吃并交流刺绣心得。因异地居住，她们主要通过微信群保持联系，郑玉华经常寄送布料样品供马晓梅参考。见面时喜欢逛古文化街挑选刺绣材料，平均两三个月能聚一次，平时每周在群里分享生活趣事。"
                },
                {
                    "name": "徐美玲",
                    "relation": "聚会友",
                    "social circle": "亲友聚会圈",
                    "gender": "女",
                    "age": 53,
                    "birth_date": "1971-12-05",
                    "home_address": {
                        "province": "天津市",
                        "city": "天津市",
                        "district": "南开区",
                        "street_name": "水上公园西路",
                        "street_number": "学府花园12号楼"
                    },
                    "birth_place": {
                        "province": "山东省",
                        "city": "德州市",
                        "district": "德城区"
                    },
                    "personality": "ENFP",
                    "economic_level": "小康",
                    "occupation": "社区工作者",
                    "organization": "南开区社区服务中心",
                    "nickname": "玲子",
                    "relation_description": "徐美玲是社区文艺活动的积极分子，与马晓梅在传统手工艺展演中相识。作为社区工作者，她经常组织邻里活动，每月末会召集聚会圈的朋友开展手工沙龙。三人中最擅长京津绣法的徐美玲常指导马晓梅新的刺绣技法，聚会时喜欢研究传统纹样并记录整理。同城居住让她们可以随时相约，平均每月见面2-3次，平时通过电话交流社区新鲜事，形成了稳定的闺蜜圈子。"
                }
            ]
        ]
    }
"""

persona3 = """
{
        "name": "冯浩然",
        "birth": "1994-10-29",
        "age": 27,
        "nationality": "汉",
        "home_address": {
            "province": "湖南省",
            "city": "长沙市",
            "district": "岳麓区",
            "street_name": "麓山南路",
            "street_number": "156号"
        },
        "birth_place": {
                "province": "湖北省",
            "city": "武汉市",
            "district": "江岸区"
        },
        "gender": "男",
        "education": "大学本科",
        "job": "金融投资顾问",
        "occupation": "华泰证券股份有限公司",
        "workplace": {
            "province": "湖南省",
            "city": "长沙市",
            "district": "开福区",
            "street_name": "芙蓉中路",
            "street_number": "88号"
        },
        "belief": "不信仰宗教",
        "salary": 200000.0,
        "body": {
            "height": 189,
            "weight": 75.0,
            "BMI": 20.9960527421
        },
        "family": "未婚",
        "personality": {
            "mbti": "ENTJ",
        },
        "hobbies": [
            "摄影（街拍）",
            "跑步（晨跑）",
            "露营（野外）",
            "收藏邮票"
        ],
        "favorite_foods": [
            "湘菜",
            "日式拉面",
            "手冲咖啡"
        ],
        "memory_date": [
            "2018-07-01（首次入职金融行业）",
            "2020-05-20（购置首套房产）"
        ],
        "aim": [
            "3年内晋升为投资总监",
            "每年完成一次深度自驾游",
            "建立个人投资组合达到100万规模"
        ],
        "healthy_desc": "身体健康状况良好，无慢性病史，保持每日体育锻炼习惯，定期进行年度健康体检，就医频率较低。",
        "lifestyle_desc": "生活规律，每日坚持晨跑和听音乐，休闲时间以互联网为主要信息来源，经常与朋友聚会和社交活动，每年有21-30个晚上外出度假，喜欢户外活动但频率适中。",
        "economic_desc": "年收入20万元，家庭总收入20万元，拥有2处房产和家用汽车，收支状况良好，经常使用信用消费但无其他投资活动，消费习惯偏稳健。",
        "work_desc": "在民营证券公司担任投资顾问，每周工作40小时，主要从事重脑力劳动，通勤时间45分钟，工作满意度较高，职业发展稳定。",
        "experience_desc": "出生于湖北武汉，2018年大学毕业后迁居长沙并进入金融行业，从商业服务人员起步，现已在长沙定居工作四年，职业发展稳步上升，期间通过自学提升了投资分析技能。",
        "description": "冯浩然是一名27岁的金融投资顾问，身高189cm，体型匀称，ENTJ型人格的他具有强烈的成就导向和社会责任感。出生于武汉的他于2018年来到长沙发展，目前就职于华泰证券，擅长资产配置和投资分析。日常生活中他坚持晨跑和音乐欣赏，爱好摄影和户外露营，与朋友保持频繁社交。未来他计划在职业上晋升为投资总监，同时希望通过自驾游探索各地风土人情，并建立个人投资组合。作为家中的独子，他虽未婚但已购置房产，生活独立且规划清晰。",
        "relation": [
            [
                {
                    "name": "冯建国",
                    "relation": "父亲",
                    "social circle": "家庭圈",
                    "gender": "男",
                    "age": 58,
                    "birth_date": "1965-03-12",
                    "home_address": {
                        "province": "湖北省",
                        "city": "武汉市",
                        "district": "江岸区",
                        "street_name": "解放大道",
                        "street_number": "368号"
                    },
                    "birth_place": {
                        "province": "湖北省",
                        "city": "武汉市",
                        "district": "江岸区"
                    },
                    "personality": "ISTJ",
                    "economic_level": "小康",
                    "occupation": "高级工程师",
                    "organization": "武汉铁路局",
                    "nickname": "老冯",
                    "relation_description": "冯浩然的父亲，退休铁路工程师，现与妻子居住在武汉老家。每月通过视频通话联系2-3次，节假日冯浩然会回武汉探望。父子关系融洽，经常交流投资理财话题，父亲会以过来人身份给予职业发展建议。"
                },
                {
                    "name": "李秀英",
                    "relation": "母亲",
                    "social circle": "家庭圈",
                    "gender": "女",
                    "age": 56,
                    "birth_date": "1967-08-25",
                    "home_address": {
                        "province": "湖北省",
                        "city": "武汉市",
                        "district": "江岸区",
                        "street_name": "解放大道",
                        "street_number": "368号"
                    },
                    "birth_place": {
                        "province": "湖北省",
                        "city": "黄石市"
                    },
                    "personality": "ISFJ",
                    "economic_level": "小康",
                    "occupation": "退休教师",
                    "organization": "武汉市江岸区实验小学",
                    "nickname": "妈妈",
                    "relation_description": "冯浩然的母亲，原小学语文教师，现已退休。与丈夫同住武汉，每周与儿子视频通话一次，关心其生活起居和婚姻大事。擅长烹饪湖北家常菜，每次冯浩然回家都会准备他爱吃的排骨藕汤。"
                },
                {
                    "name": "冯欣然",
                    "relation": "妹妹",
                    "social circle": "家庭圈",
                    "gender": "女",
                    "age": 24,
                    "birth_date": "1999-05-18",
                    "home_address": {
                        "province": "上海市",
                        "city": "浦东新区",
                        "district": "陆家嘴街道",
                        "street_name": "世纪大道",
                        "street_number": "100号"
                    },
                    "birth_place": {
                        "province": "湖北省",
                        "city": "武汉市",
                        "district": "江岸区"
                    },
                    "personality": "ENFP",
                    "economic_level": "中产",
                    "occupation": "市场营销专员",
                    "organization": "上海某互联网公司",
                    "nickname": "小然",
                    "relation_description": "冯浩然的妹妹，现居上海从事互联网营销工作。兄妹俩关系亲密，每周通过微信保持联系，经常分享工作生活见闻。每年春节和国庆假期会一起回武汉团聚，平时会互寄当地特产，冯浩然会指导妹妹进行理财规划。"
                }
            ],
            [
                {
                    "name": "张明轩",
                    "relation": "发小",
                    "social circle": "童年玩伴圈",
                    "gender": "男",
                    "age": 28,
                    "birth_date": "1995-03-12",
                    "home_address": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "南山区",
                        "street_name": "科技园路",
                        "street_number": "36号"
                    },
                    "birth_place": {
                        "province": "湖北省",
                        "city": "武汉市",
                        "district": "江岸区"
                    },
                    "personality": "ENFP",
                    "economic_level": "中产",
                    "occupation": "互联网产品经理",
                    "organization": "腾讯科技（深圳）有限公司",
                    "nickname": "轩子",
                    "relation_description": "张明轩与冯浩然是武汉江岸区同一小区的童年玩伴，从小一起上学玩耍。2018年后两人分别前往长沙和深圳发展，现在主要通过微信保持联系，每月视频通话2-3次。见面时会一起重温家乡美食，讨论职业发展和投资理财。虽然分隔两地，但每年春节回武汉探亲时都会相约聚会，保持着深厚的发小情谊。"
                }
            ],
            [
                {
                    "name": "陈志远",
                    "relation": "小学同学",
                    "social circle": "小学同学圈",
                    "gender": "男",
                    "age": 28,
                    "birth_date": "1995-03-12",
                    "home_address": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "南山区",
                        "street_name": "科技园南区",
                        "street_number": "科技南八道18号"
                    },
                    "birth_place": {
                        "province": "湖北省",
                        "city": "武汉市",
                        "district": "洪山区"
                    },
                    "personality": "ISTP",
                    "economic_level": "中产",
                    "occupation": "软件工程师",
                    "organization": "腾讯科技（深圳）有限公司",
                    "nickname": "阿远",
                    "relation_description": "陈志远是冯浩然在武汉读小学时的同班同学，两人曾一起参加校篮球队。2014年陈志远考入华南理工大学计算机专业，毕业后留在深圳发展，现为腾讯后端开发工程师。虽然分隔两地，但两人保持每季度视频通话一次，聊工作近况和投资理财话题。每年春节回武汉探亲时会约见面，通常一起品尝家乡美食，回忆童年趣事。"
                }
            ],
            [
                {
                    "name": "王丽娜",
                    "relation": "初中同学",
                    "social circle": "初中同学圈",
                    "gender": "女",
                    "age": 28,
                    "birth_date": "1995-03-15",
                    "home_address": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "南山区",
                        "street_name": "科技园路",
                        "street_number": "36号"
                    },
                    "birth_place": {
                        "province": "湖北省",
                        "city": "武汉市",
                        "district": "江汉区"
                    },
                    "personality": "ENFP",
                    "economic_level": "中产",
                    "occupation": "互联网产品经理",
                    "organization": "腾讯科技（深圳）有限公司",
                    "nickname": "娜娜",
                    "relation_description": "王丽娜与冯浩然是武汉某中学初中同学，初中时期因共同参加数学竞赛而熟识。毕业后两人分别前往不同城市读高中，但通过社交平台保持联系。目前王丽娜在深圳从事互联网行业，两人主要通过微信朋友圈互动和每年春节返乡时的同学聚会见面，见面时会交流职业发展和投资理财话题。由于分居两地，平时每季度会视频通话一次，关系保持融洽但不算密切。"
                }
            ],
            [
                {
                    "name": "刘浩然",
                    "relation": "高中同学",
                    "social circle": "高中同学圈",
                    "gender": "男",
                    "age": 28,
                    "birth_date": "1995-03-12",
                    "home_address": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "南山区",
                        "street_name": "科技园路",
                        "street_number": "36号"
                    },
                    "birth_place": {
                        "province": "湖北省",
                        "city": "武汉市",
                        "district": "洪山区"
                    },
                    "personality": "ENFP",
                    "economic_level": "中产",
                    "occupation": "互联网产品经理",
                    "organization": "腾讯科技（深圳）有限公司",
                    "nickname": "浩子",
                    "relation_description": "两人是武汉某重点高中同班同学，高三时因共同参加数学竞赛集训而熟络。毕业后刘浩然考入深圳大学计算机专业，现定居深圳从事互联网行业。虽然分隔两地，但每月会通过视频通话交流投资和科技趋势，偶尔分享各自城市的特色美食照片。每年春节回武汉探亲时会相约聚餐，讨论职业发展并回忆高中趣事。"
                }
            ],
            [
                {
                    "name": "赵天宇",
                    "relation": "大学室友",
                    "social circle": "大学同学圈",
                    "gender": "男",
                    "age": 28,
                    "birth_date": "1995-03-12",
                    "home_address": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "南山区",
                        "street_name": "科技园路",
                        "street_number": "36号"
                    },
                    "birth_place": {
                        "province": "湖南省",
                        "city": "长沙市"
                    },
                    "personality": "ENFP",
                    "economic_level": "中产",
                    "occupation": "互联网产品经理",
                    "organization": "腾讯科技（深圳）有限公司",
                    "nickname": "天宇",
                    "relation_description": "赵天宇是冯浩然的大学室友，两人在大学期间同住四年，经常一起参加社团活动和学术竞赛。毕业后赵天宇选择南下深圳发展，现为腾讯产品经理，主要负责社交产品线。虽然分隔两地，但每月会通过视频通话保持联系，偶尔会相约在长沙或深圳聚会，见面时主要讨论职业发展和投资理财话题。"
                },
                {
                    "name": "周雨薇",
                    "relation": "大学同学",
                    "social circle": "大学同学圈",
                    "gender": "女",
                    "age": 27,
                    "birth_date": "1996-08-25",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "浦东新区",
                        "street_name": "陆家嘴环路",
                        "street_number": "188号"
                    },
                    "birth_place": {
                        "province": "江苏省",
                        "city": "南京市"
                    },
                    "personality": "INFJ",
                    "economic_level": "中产",
                    "occupation": "金融分析师",
                    "organization": "汇丰银行（中国）有限公司",
                    "nickname": "薇薇",
                    "relation_description": "周雨薇是冯浩然的大学同班同学，两人曾共同参与金融建模比赛并获得奖项。现居上海从事外资银行分析工作，与冯浩然保持专业领域的交流。每季度会通过线上会议讨论市场趋势，每年同学聚会时见面，相处时习惯分享行业动态和职业成长经历。"
                },
                {
                    "name": "吴俊杰",
                    "relation": "大学同学",
                    "social circle": "大学同学圈",
                    "gender": "男",
                    "age": 28,
                    "birth_date": "1995-11-03",
                    "home_address": {
                        "province": "湖南省",
                        "city": "长沙市",
                        "district": "雨花区",
                        "street_name": "韶山南路",
                        "street_number": "215号"
                    },
                    "birth_place": {
                        "province": "湖北省",
                        "city": "武汉市"
                    },
                    "personality": "ISTP",
                    "economic_level": "小康",
                    "occupation": "IT工程师",
                    "organization": "湖南移动通信有限公司",
                    "nickname": "阿杰",
                    "relation_description": "吴俊杰与冯浩然是大学同窗，因同属湖北老乡而关系密切。现定居长沙从事通信技术工作，与冯浩然保持每月一次的线下聚会，常相约跑步或品尝湘菜。两人会互相推荐投资机会，吴俊杰偶尔会向冯浩然咨询理财建议，形成互补型友谊关系。"
                }
            ],
            [
                {
                    "name": "郑文博",
                    "relation": "同事",
                    "social circle": "华泰证券同事圈",
                    "gender": "男",
                    "age": 28,
                    "birth_date": "1995-03-15",
                    "home_address": {
                        "province": "湖南省",
                        "city": "长沙市",
                        "district": "雨花区",
                        "street_name": "韶山南路",
                        "street_number": "233号"
                    },
                    "birth_place": {
                        "province": "广东省",
                        "city": "广州市"
                    },
                    "personality": "ESTP",
                    "economic_level": "中产",
                    "occupation": "证券分析师",
                    "organization": "华泰证券股份有限公司",
                    "nickname": "博哥",
                    "relation_description": "郑文博与冯浩然同在华泰证券投资顾问部工作，两人因业务合作相识。作为同龄人，他们经常一起讨论市场动态和投资策略，午休时常结伴去公司附近的湘菜馆用餐。虽然住在同一城市，但因工作繁忙主要靠企业微信沟通，每周会有一两次工作聚餐，周末偶尔会相约打篮球或参加行业沙龙活动。"
                },
                {
                    "name": "孙晓雅",
                    "relation": "同事",
                    "social circle": "华泰证券同事圈",
                    "gender": "女",
                    "age": 26,
                    "birth_date": "1997-08-22",
                    "home_address": {
                        "province": "浙江省",
                        "city": "杭州市",
                        "district": "西湖区",
                        "street_name": "文三路",
                        "street_number": "456号"
                    },
                    "birth_place": {
                        "province": "江苏省",
                        "city": "南京市"
                    },
                    "personality": "INFJ",
                    "economic_level": "中产",
                    "occupation": "客户经理",
                    "organization": "华泰证券股份有限公司",
                    "nickname": "晓雅",
                    "relation_description": "孙晓雅是冯浩然团队中的客户经理，负责高净值客户维护。两人在工作中配合默契，经常共同为客户制定资产配置方案。她虽在杭州远程办公，但每月会来长沙总部述职，这时三人小组总会组织团建活动。平时通过视频会议保持工作沟通，偶尔会分享各自城市的特色咖啡馆和摄影作品，保持着专业的同事友谊。"
                },
                {
                    "name": "钱永强",
                    "relation": "直属上司",
                    "social circle": "华泰证券同事圈",
                    "gender": "男",
                    "age": 35,
                    "birth_date": "1988-12-05",
                    "home_address": {
                        "province": "湖南省",
                        "city": "长沙市",
                        "district": "开福区",
                        "street_name": "湘江中路",
                        "street_number": "168号"
                    },
                    "birth_place": {
                        "province": "湖北省",
                        "city": "武汉市"
                    },
                    "personality": "ENTJ",
                    "economic_level": "富裕",
                    "occupation": "投资总监",
                    "organization": "华泰证券股份有限公司",
                    "nickname": "钱总",
                    "relation_description": "作为部门负责人，钱永强是冯浩然的职业引路人，两人同是武汉老乡且性格相似。他经常组织团队进行投资案例复盘，周末时会带着团队成员参加高端金融论坛。住在公司附近的他，下班后常与冯浩然讨论职业规划，每年会组织两次团队户外拓展活动，在工作和生活上都给予下属很多指导。"
                }
            ],
            [
                {
                    "name": "黄思琪",
                    "relation": "客户",
                    "social circle": "工作客户圈",
                    "gender": "女",
                    "age": 35,
                    "birth_date": "1988-03-15",
                    "home_address": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "南山区",
                        "street_name": "科技园路",
                        "street_number": "36号"
                    },
                    "birth_place": {
                        "province": "浙江省",
                        "city": "杭州市"
                    },
                    "personality": "INTJ",
                    "economic_level": "富裕",
                    "occupation": "科技公司创始人",
                    "organization": "深圳创新科技有限公司",
                    "nickname": "思思",
                    "relation_description": "黄思琪是冯浩然服务的高净值客户，两人通过华泰证券的业务合作相识。作为科技公司创始人，她经常就资产配置和投资策略向冯浩然咨询。虽然分居深圳和长沙两地，但每月会通过视频会议进行1-2次专业交流，偶尔冯浩然会专程飞往深圳当面汇报投资方案。两人关系专业而互信，偶尔会就行业趋势进行深入讨论。"
                },
                {
                    "name": "林志豪",
                    "relation": "客户",
                    "social circle": "工作客户圈",
                    "gender": "男",
                    "age": 42,
                    "birth_date": "1981-08-22",
                    "home_address": {
                        "province": "上海市",
                        "city": "上海市",
                        "district": "浦东新区",
                        "street_name": "陆家嘴环路",
                        "street_number": "188号"
                    },
                    "birth_place": {
                        "province": "江苏省",
                        "city": "苏州市"
                    },
                    "personality": "ESTJ",
                    "economic_level": "富裕",
                    "occupation": "房地产企业高管",
                    "organization": "上海金茂集团",
                    "nickname": "林总",
                    "relation_description": "林志豪是冯浩然服务的另一位重要客户，从事房地产行业多年。两人通过朋友介绍建立业务关系，主要就大宗资产管理和投资组合优化进行合作。虽然居住在上海，但林志豪经常因业务需要往返长沙，每次到访都会与冯浩然面谈2-3小时。平时通过微信保持每周一次的联系，偶尔会相约打高尔夫球交流投资心得。"
                }
            ],
            [
                {
                    "name": "徐佳宁",
                    "relation": "摄影伙伴",
                    "social circle": "街拍摄影圈",
                    "gender": "女",
                    "age": 26,
                    "birth_date": "1996-08-15",
                    "home_address": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "南山区",
                        "street_name": "科技园路",
                        "street_number": "32号"
                    },
                    "birth_place": {
                        "province": "湖南省",
                        "city": "长沙市",
                        "district": "雨花区"
                    },
                    "personality": "ISFP",
                    "economic_level": "中产",
                    "occupation": "视觉设计师",
                    "organization": "腾讯科技（深圳）有限公司",
                    "nickname": "佳宁",
                    "relation_description": "徐佳宁是冯浩然在长沙读大学时通过摄影社团认识的伙伴，两人因对街头摄影的共同热爱成为好友。毕业后徐佳宁前往深圳发展，现为腾讯视觉设计师，但仍保持每月线上交流摄影技巧的习惯。他们主要通过微信分享最新作品，每年冯浩然去深圳出差时会相约进行城市街拍，最近一次见面是半年前在深圳华侨城创意园拍摄夜景。"
                }
            ],
            [
                {
                    "name": "高云飞",
                    "relation": "跑友",
                    "social circle": "晨跑圈",
                    "gender": "男",
                    "age": 28,
                    "birth_date": "1995-03-12",
                    "home_address": {
                        "province": "湖南省",
                        "city": "长沙市",
                        "district": "雨花区",
                        "street_name": "韶山南路",
                        "street_number": "233号"
                    },
                    "birth_place": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "福田区"
                    },
                    "personality": "ISTJ",
                    "economic_level": "中产",
                    "occupation": "IT项目经理",
                    "organization": "腾讯科技（长沙）分公司",
                    "nickname": "云飞",
                    "relation_description": "高云飞是冯浩然在岳麓山晨跑时认识的跑友，两人因坚持清晨锻炼而结缘。作为IT项目经理的他工作节奏规律，每周三和周六早晨都会与冯浩然相约麓山南路慢跑，途中常交流投资理财和科技行业动态。虽然高云飞出生于深圳，但因工作调动已在长沙定居三年，两人居住地相距约6公里，除晨跑外每月还会约一次湘菜馆聚餐。"
                }
            ],
            [
                {
                    "name": "谢雨桐",
                    "relation": "露营伙伴",
                    "social circle": "户外露营圈",
                    "gender": "女",
                    "age": 26,
                    "birth_date": "1997-03-15",
                    "home_address": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "南山区",
                        "street_name": "科技园路",
                        "street_number": "36号"
                    },
                    "birth_place": {
                        "province": "四川省",
                        "city": "成都市",
                        "district": "武侯区"
                    },
                    "personality": "ISFP",
                    "economic_level": "中产",
                    "occupation": "用户体验设计师",
                    "organization": "腾讯科技（深圳）有限公司",
                    "nickname": "小雨",
                    "relation_description": "谢雨桐是冯浩然在2021年参加湖南户外露营协会活动时认识的伙伴，两人因对野外露营的共同热爱而结缘。虽然分居长沙和深圳两地，但每月会通过视频通话分享露营见闻，每季度相约在湖南或广东的露营地见面。相处时主要交流装备使用心得和拍摄技巧，谢雨桐经常为冯浩然的摄影作品提供构图建议。两人保持着适度而稳定的户外活动联系频率。"
                }
            ],
            [
                {
                    "name": "罗振宇",
                    "relation": "邮票藏友",
                    "social circle": "邮票收藏圈",
                    "gender": "男",
                    "age": 45,
                    "birth_date": "1979-03-12",
                    "home_address": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "南山区",
                        "street_name": "科技园路",
                        "street_number": "36号"
                    },
                    "birth_place": {
                        "province": "浙江省",
                        "city": "杭州市"
                    },
                    "personality": "ISTJ",
                    "economic_level": "中产",
                    "occupation": "互联网产品经理",
                    "organization": "腾讯科技（深圳）有限公司",
                    "nickname": "老罗",
                    "relation_description": "两人通过线上邮票收藏论坛相识已有五年，因共同对特殊邮票的鉴赏兴趣建立深厚友谊。罗振宇常驻深圳工作，冯浩然在长沙发展，主要通过微信群和视频通话保持联系，每月交流2-3次邮票市场动态和收藏心得。每年会在全国邮票展览会上见面一次，共同参观展品并分享最新收藏。两人虽异地但默契十足，偶尔会互寄特色邮票作为礼物。"
                }
            ],
            [
                {
                    "name": "彭雨晴",
                    "relation": "好友",
                    "social circle": "密友圈",
                    "gender": "女",
                    "age": 26,
                    "birth_date": "1995-08-14",
                    "home_address": {
                        "province": "湖南省",
                        "city": "长沙市",
                        "district": "雨花区",
                        "street_name": "韶山南路",
                        "street_number": "233号"
                    },
                    "birth_place": {
                        "province": "湖北省",
                        "city": "武汉市",
                        "district": "洪山区"
                    },
                    "personality": "ENFP",
                    "economic_level": "中产",
                    "occupation": "新媒体运营经理",
                    "organization": "湖南日报新媒体中心",
                    "nickname": "小雨",
                    "relation_description": "冯浩然的大学校友，两人在武汉读本科时因社团活动相识。毕业后都选择到长沙发展，经常周末一起聚餐或户外活动。彭雨晴性格开朗活泼，常组织朋友聚会，与冯浩然保持每周2-3次的联系频率，主要通过微信交流投资心得和生活趣事。"
                },
                {
                    "name": "董浩然",
                    "relation": "好友",
                    "social circle": "密友圈",
                    "gender": "男",
                    "age": 28,
                    "birth_date": "1994-03-22",
                    "home_address": {
                        "province": "广东省",
                        "city": "深圳市",
                        "district": "南山区",
                        "street_name": "科技园路",
                        "street_number": "18号"
                    },
                    "birth_place": {
                        "province": "湖北省",
                        "city": "武汉市",
                        "district": "武昌区"
                    },
                    "personality": "INTJ",
                    "economic_level": "富裕",
                    "occupation": "科技公司产品总监",
                    "organization": "腾讯科技",
                    "nickname": "浩子",
                    "relation_description": "冯浩然的高中同学，两人从小在武汉一起长大。董浩然大学毕业后前往深圳发展，虽分隔两地但保持密切联络。每月视频通话2-3次，主要讨论职业发展和投资机会。冯浩然去广东出差时会特意见面，董浩然回武汉探亲时也会约冯浩然相聚。"
                },
                {
                    "name": "蔡文静",
                    "relation": "好友",
                    "social circle": "密友圈",
                    "gender": "女",
                    "age": 27,
                    "birth_date": "1994-12-05",
                    "home_address": {
                        "province": "上海市",
                        "city": "浦东新区",
                        "district": "陆家嘴",
                        "street_name": "世纪大道",
                        "street_number": "100号"
                    },
                    "birth_place": {
                        "province": "湖南省",
                        "city": "长沙市",
                        "district": "芙蓉区"
                    },
                    "personality": "ISFJ",
                    "economic_level": "中产",
                    "occupation": "银行理财经理",
                    "organization": "招商银行上海分行",
                    "nickname": "文静",
                    "relation_description": "通过彭雨晴介绍认识的闺蜜圈好友，三人经常一起组织活动。蔡文静原籍长沙，现居上海发展，与冯浩然主要通过微信群保持联系。每年春节回长沙时必会聚会，平时每月视频聊天1-2次，交流金融行业动态和理财经验。冯浩然去上海出差时也会相约品尝美食。"
                }
            ],
            [
                {
                    "name": "陆家明",
                    "relation": "房产中介",
                    "social circle": "房产服务圈",
                    "gender": "男",
                    "age": 35,
                    "birth_date": "1989-03-18",
                    "home_address": {
                        "province": "湖南省",
                        "city": "长沙市",
                        "district": "雨花区",
                        "street_name": "韶山南路",
                        "street_number": "233号"
                    },
                    "birth_place": {
                        "province": "广东省",
                        "city": "广州市",
                        "district": "天河区"
                    },
                    "personality": "ESFJ",
                    "economic_level": "中产",
                    "occupation": "高级房产经纪人",
                    "organization": "链家地产长沙分公司",
                    "nickname": "阿明",
                    "relation_description": "陆家明是冯浩然2020年购房时认识的房产中介，为人热情周到，熟悉长沙各区域房产市场。两人因房产交易建立信任关系，后续保持不定期联系，逢年过节会互发问候。陆家明会主动分享楼市最新动态，冯浩然有朋友需要房产服务时也会推荐给他。目前两人同在长沙但见面频率不高，主要通过微信沟通，平均每季度会约一次咖啡厅交流投资和房产信息。"
                }
            ],
            [
                {
                    "name": "沈心怡",
                    "relation": "咖啡店老板",
                    "social circle": "手冲咖啡圈",
                    "gender": "女",
                    "age": 32,
                    "birth_date": "1992-05-18",
                    "home_address": {
                        "province": "湖南省",
                        "city": "长沙市",
                        "district": "芙蓉区",
                        "street_name": "解放西路",
                        "street_number": "233号"
                    },
                    "birth_place": {
                        "province": "云南省",
                        "city": "普洱市"
                    },
                    "personality": "ISFP",
                    "economic_level": "中产",
                    "occupation": "独立咖啡店主",
                    "organization": "心怡手冲咖啡馆",
                    "nickname": "沈老板",
                    "relation_description": "冯浩然是沈心怡咖啡馆的常客，因对手冲咖啡的共同爱好相识。沈心怡的咖啡馆位于冯浩然公司附近，他每周会光顾2-3次品尝新品咖啡。两人经常交流咖啡豆产地和冲泡技巧，偶尔会一起参加本地咖啡品鉴活动。沈心怡会为冯浩然预留限量咖啡豆，而冯浩然也会推荐客户到她的咖啡馆洽谈业务。"
                }
            ]
        ]
    }
"""

content = read_json_file('../data_event/event1.json')
res = gen_event1(persona)
with open("../data_event/event（1）.json", "w", encoding="utf-8") as json_f:
    json.dump(res, json_f, ensure_ascii=False, indent=4)
print("所有数据处理完成，JSON文件已生成")
# print(res)