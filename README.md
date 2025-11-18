使用之前，现根据utils/llm_call文件修改openai api

请先删除personal_memories.json 和 record.json!!!!

使用流程：

请先在event_gen.py、simulator.py 、phone_gen.py指定存储目录。运行日期。

然后把persona.json文件存在指定目录。

之后依次运行event_gen.py、simulator.py 、phone_gen.py。

event_gen.py输出event_decompose.json代表事件树（主题事件-原子事件）

simulator.py输出event_update.json代表每日事件（前面为事件树，后面为按时间顺序整理的每日事件）

phone_gen.py输出手机数据

中间数据存储在process文件夹


event_gen.py 负责调用scheduler的功能，将生成的事件存到event.json，将调整后的事件存到event_s.json,将分解后的事件存到event_decompose.json
event_gen的输入为persona，可进行调整，格式为json字符串。



simulator.py 负责调用mind的功能，将分解事件进一步调整并存到event_decompose1.json。然后模拟并生成每天事件，存到event_update.json
simulator的输入为persona和由event_gen生成的event_decompose.json文件以及起始时间和结束时间


phone_gen.py 负责生成手机数据，将存到phone_data文件夹。
phone_gen的输入为persona，由simulator生成的event_update.json以及起始时间和结束时间。

所有数据的输入输出存储在data文件夹

data_XX文件夹存储历史版本的数据

event文件夹存储事件生成相关代码

log文件夹存储日志

persona文件夹存储画像构建代码

utils文件夹存储工具