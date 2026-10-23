from .common import render as common


def render(stage, body, inputs):
    return common(stage, body, inputs,
        '圈名、姓名和教育经历符合实际所在地，允许跨国亲友。工作圈只继承 employer_anchor，'
        '不得替换成真实工作 POI 的运营公司。neighborhood 的范围以人物居住行政区为准，'
        '不得自行将 neighbourhood 和 borough 合并。学校、运动场馆和社区只在合理生活半径内选择，'
        '不要为孤立爱好强建圈子；不强制使用微信群、大学同班或中国式单位组织。')
