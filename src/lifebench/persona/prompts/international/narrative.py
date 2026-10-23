from .common import render as common


def render(stage, body, inputs):
    return common(stage, body, inputs,
        '通勤严格使用 grounding_context.commute.commute_transport，lifestyle_desc 明确写出该方式；'
        'status=not_required 才可写无需办公室通勤。duration_source=estimate 时允许写该方式的约略时长，'
        '必须明确标注“估算”，不得声称是地图结果；commute_minutes=null 时不写确定耗时。'
        '无数据不写确定班次或换乘站。地铁、公交不能用步行路线替代。'
        '有明确地图耗时时保持一致；以后 enrich 也不得更换交通方式。'
        '办公地点使用已冻结 POI；允许合理虚构租用办公空间，但不得自称关系已获地图核验或误换雇主。'
        '活动时间与圈子名称一致，不得写晚上参加晨跑；新增经历不能晚于基准日期。')
