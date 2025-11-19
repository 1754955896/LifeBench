from event.scheduler import *
from utils import IO

#参数
file_path = 'data/'
persona = read_json_file(file_path+'persona.json')

scheduler = Scheduler(persona,file_path)
scheduler.main_gen_event()
#输出位于data文件中的event.json
json_data = read_json_file(file_path+'process/event_1.json')
scheduler.main_schedule_event(json_data,file_path)
#输出位于data文件中的event_s.json
json_data = read_json_file(file_path+'process/event_2.json')
scheduler.main_decompose_event(json_data,file_path)
#输出位于data文件中的event_decompose.json