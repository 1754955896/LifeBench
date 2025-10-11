# Please install OpenAI SDK first: `pip3 install openai`

from openai import OpenAI

client = OpenAI(api_key="sk-e90f17355573420597c914ef38a58239", base_url="https://api.deepseek.com")
messages = [{"role": "system", "content": "你是一个人物分析师、故事创作者、数据补全与清洗专家。"}]

def llm_call(prompt,context="你是一个人物分析师、故事创作者、数据补全与清洗专家。",record=0):
    global messages
    print(messages)
    messages[0]["content"]=context
    messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        stream=False
    )
    #print(response)
    if record==1:
        messages.append(response.choices[0].message)
    if record==0:
        messages=[{"role": "system", "content": context}]
    return response.choices[0].message.content


def llm_call_reason(prompt,context="你是一个人物分析师、故事创作者、数据补全与清洗专家。",record=0):
    global messages
    print(messages)
    messages[0]["content"] = context
    messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model="deepseek-reasoner",
        messages=messages,
        stream=False
    )
    print(response.choices[0].message.reasoning_content)
    if record == 1:
        messages.append({'role': 'assistant', 'content': response.choices[0].message.content})
    if record == 0:
        messages = [{"role": "system", "content": context}]
    return response.choices[0].message.content
