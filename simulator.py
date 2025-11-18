from event.mind import *
from utils import IO

file_path = 'data/'
persona = read_json_file(file_path+'persona.json')
start_date = '2025-02-01'
end_date = '2025-03-30'
control = 1 #控制是否执行原子事件调整，若调整过可以跳过。（1代表完整执行，2代表中断后继续执行）


mind = Mind(file_path)
json_data_p = persona

if control==1:
        json_data_e = read_json_file(file_path + "event_decompose.json")
        mind.load_from_json(json_data_e, json_data_p, 0)
        print('++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
        for date in iterate_dates(start_date,end_date):
                mind.event_refine(date)
        with open(file_path+"process/event_decompose_1.json", "w", encoding="utf-8") as f:
                json.dump(mind.events, f, ensure_ascii=False, indent=2)
        #输出存在data文件里的event_decompose1
elif control==0:
        json_data_e = read_json_file(file_path + "process/event_decompose_1.json")
        mind.load_from_json(json_data_e, json_data_p, 0)
else:
        json_data_e = read_json_file(file_path + "event_update.json")
        mind.load_from_json(json_data_e, json_data_p, 1)
#请在模拟之前删除记忆库文件personal_memories
print('++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
for date in iterate_dates(start_date,end_date):
        mind.daily_event_gen1(date)
#输出存在data文件里的event_update