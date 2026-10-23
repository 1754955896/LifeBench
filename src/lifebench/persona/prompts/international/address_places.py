from .common import render as common


def render(stage, body, inputs):
    return common(stage, body, inputs,
        'keyword 使用接口可识别的中文通用类别（超市、便利店、餐厅、咖啡馆、公园、图书馆、博物馆、健身房）。'
        '这些检索类别是内部接口值，不代表人物使用中文生活。description 使用 output_language。'
        'poi_type 留空，由地图工具将通用类别映射到 OSM 标签，禁止输出高德数字类别码。'
        '门牌及具体门店由地图确定，不指定虚构门店名称。工作地周边只生成办公日需求。')
