import os
from config import deepseek_api_key_encoded, log_dir, pages_dir, date, res_dir, message_dir
from flask import send_from_directory, request
from tools import decoder, WSAvaliable as avaliable, isVIP
import json,requests,datetime

def Browser():
    return avaliable('browser.html')


def dsb():
    return avaliable('dsb.jpeg')


def ai():
    return avaliable('ai.html')


def getaiapi():
    user = str(request.args.get('user'))
    hisid = request.args.get('hisid')
    modelName = str(request.args.get('model')) if request.args.get('model') else 'deepseek-chat'
    username = str(request.args.get('username')) if request.args.get('username') else 'guest'

    if not username:
        return "No username provided"
    if isVIP(username)==False and modelName=='deepseek-reasoner':
        return "思考的话太烧钱了，需要你赞助一点点啦~"
    
    # 加载历史记录
    history = []
    history_file = None
    if hisid:
        history_file = os.path.join(log_dir, f"{hisid}'smemory.log")
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                content = f.read()
                history = json.loads(content) if content else []

    # 添加当前用户输入到历史记录
    history.append({"role": "user", "content": user})

    # 调用 AI 接口
    with requests.post(
        url='https://api.deepseek.com/chat/completions',
        headers = {
        "Authorization": f"Bearer {decoder(deepseek_api_key_encoded)}",
        "Content-Type": "application/json"
        },
        data = json.dumps({
            "model": modelName,
            "messages": history,
            "stream": False,
            "temperature": float(str(request.args.get("temp"))) if request.args.get("temp") else 1.3
        })
    ) as req:
        # 获取 AI 回复
        response = json.loads(req.content.decode())
        message = response['choices'][-1]['message']
        content = message['content']
        reasoning = message.get('reasoning_content',None)
        if reasoning:
            result='# 思考：\n'+reasoning+'\n# 回答：\n'+content
        else:
            result=content

        # 将 AI 回复追加到历史记录
        history.append({"role": "assistant", "content": content})

        # 保存更新后的历史记录
        if hisid and history_file:
            with open(history_file, 'w', encoding='utf-8') as f:
                f.write(json.dumps(history, ensure_ascii=False))

        # 计算费用
        cost = (response.get('usage', {}).get('completion_tokens', 0) / 1000000 * 3 
              + response.get('usage', {}).get('prompt_cache_hit_tokens', 0) / 1000000 * 0.2 
              + response.get('usage', {}).get('prompt_cache_miss_tokens', 0) / 1000000 * 2)
        money_file = os.path.join(log_dir, "moneys.log")
        try:
            with open(money_file, 'r', encoding='utf-8') as f:
                data = json.loads(f.read())
        except FileNotFoundError:
            data = {}
        if username not in data:
            data[username] = {"money": 0.0, "isVIP": False}
        data[username]['money'] += cost
        with open(money_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False))

        return result


def gethistory(id):
    with open(os.path.join(log_dir,f'{id}\'smemory.log'),'r',encoding='utf-8') as file:
        content=file.read()
        print(content)
        if not content: return '{"content":"ID Not Found"}'
        return content

def getMoney():
    username = str(request.args.get('username'))
    if not username:
        return "No username provided"
    money_file = os.path.join(log_dir, f"moneys.log")
    try:
        with open(money_file, 'r', encoding='utf-8') as f:
            user_data = json.loads(f.read())[username]
            if user_data['isVIP']:
                result = f'尊敬的{username}，你已经花了￥{user_data["money"]}'
            else:
                result = '你花了￥' + str(user_data["money"])
            return result
    except FileNotFoundError:
        return "0"

def sendres(file):
    print(os.path.join(res_dir, os.path.dirname(file)), os.path.basename(file))
    return send_from_directory(os.path.join(res_dir, os.path.dirname(file)), os.path.basename(file))


def render():
    return send_from_directory(pages_dir,'render.html')

def read_message():
    global date
    targetFile=''
    targetuser=str(request.args.get('targetuser'))
    user=str(request.args.get('username'))
    if not targetuser:
        targetFile=f'msg{date}.json'
    else:
        for i in os.scandir(message_dir):
            if (targetuser in i.name)and(user in i.name):
                targetFile=i.name
                break
        if not targetFile:
            targetFile=f'msg{user+"_"+targetuser}.json'

    try:
        with open(os.path.join(message_dir,targetFile),'r',encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        with open(os.path.join(message_dir,targetFile),'w',encoding='utf-8') as file:
            time = str(datetime.datetime.now())
            file.write('{"content":[{"sender":"system","time":"none","content":"Newfilecreated'+time+'"}]}')
        return '{"content":[{"sender":"system","time":"none","content":"Newfilecreated'+time+'"}]}'


def send_msg():
        global date
        sender=str(request.args.get('sender'))
        content=str(request.args.get('content'))
        targetuser=str(request.args.get('targetuser'))
        targetFile=''
        if not targetuser:
            targetFile=f'msg{date}.json'
        else:
            for i in os.scandir(message_dir):
                if (targetuser in i.name)and(sender in i.name):
                    targetFile=i.name
                    break
            if not targetFile:
                targetFile=f'msg{sender+"_"+targetuser}.json'
        with open(os.path.join(message_dir,targetFile),'r',encoding='utf-8') as f:
            file=json.loads(f.read())
        with open(os.path.join(message_dir,targetFile),'w',encoding='utf-8') as f:
            for key,value in {'sender':sender,'time':str(datetime.datetime.now())[-15:-7],'content':content}.items():
                file['content'].append(dict())
                file['content'][-1][key]=value
            f.write(json.dumps(file,ensure_ascii=False))
        return 'ok'


def announce():
    ctnt= request.args.get('content')
    if ctnt:
        with open(os.path.join(message_dir,'announcement.data'),'w',encoding='utf-8') as f:
            f.write(ctnt)
    else:
        with open(os.path.join(message_dir,'announcement.data'),'r',encoding='utf-8') as f:
            return f.read()


def login():
    return avaliable('login.html')


def talker():
    return avaliable('talk.html')