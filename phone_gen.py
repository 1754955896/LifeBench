import json
import os.path

from event.phone_data_gen import *

file_path = 'data/'
start_time = '2025-03-13'
end_time = '2025-12-31'
persona = read_json_file(file_path+'persona.json')

contact = {}
if os.path.exists(file_path + "phone_data/contact.json"):
    contact = read_json_file(file_path + "phone_data/contact.json")
else:
    contact = contact_gen(persona)
    contact = remove_json_wrapper(contact)
    contact = json.loads(contact)
    with open(file_path + "phone_data/contact.json", "w", encoding="utf-8") as f:
        json.dump(contact, f, ensure_ascii=False, indent=2)

a = []
b = []
c = []
d = []
if os.path.exists(file_path + "phone_data/event_gallery.json"):
    a = read_json_file(file_path + "phone_data/event_gallery.json")
if os.path.exists(file_path + "phone_data/event_push.json"):
    b = read_json_file(file_path + "phone_data/event_push.json")
if os.path.exists(file_path + "phone_data/event_call.json"):
    c = read_json_file(file_path + "phone_data/event_call.json")
if os.path.exists(file_path + "phone_data/event_note.json"):
    d = read_json_file(file_path + "phone_data/event_note.json")
extool.load_from_json(read_json_file(file_path+'event_update.json'),persona)
for i in iterate_dates(start_time,end_time):
    phone_gen(i,contact,file_path,a,b,c,d)

# for i in iterate_dates(start_time,end_time):
#
#     g1 = CommunicationOperationGenerator()
#     a = g1.phone_gen_callandmsm(i,contact,file_path,a)
#
#     g2 = NoteCalendarOperationGenerator(random_seed=42)
#     # 生成2023-10-05的日历和笔记数据（总数≤4）
#     b = g2.phone_gen_noteandcalendar(i,contact,file_path,b)
#
#     g3 = GalleryOperationGenerator(random_seed=42)
#     c = g3.phone_gen_gallery(i,contact,file_path,c)
#
#     g4 = PushOperationGenerator(random_seed=42)
#     d = g4.phone_gen_push(i,contact,file_path,d)
#
#     with open(file_path + "phone_data/event_note.json", "w", encoding="utf-8") as f:
#         json.dump(d, f, ensure_ascii=False, indent=2)
#     with open(file_path + "phone_data/event_call.json", "w", encoding="utf-8") as f:
#         json.dump(c, f, ensure_ascii=False, indent=2)
#     with open(file_path + "phone_data/event_gallery.json", "w", encoding="utf-8") as f:
#         json.dump(a, f, ensure_ascii=False, indent=2)
#     with open(file_path + "phone_data/event_push.json", "w", encoding="utf-8") as f:
#         json.dump(b, f, ensure_ascii=False, indent=2)


