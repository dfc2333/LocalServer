import os
from config import down_dir, log_dir, pages_dir,date, res_dir, message_dir
from flask import send_from_directory, request
import json,requests,datetime


def Browser():
    return send_from_directory(pages_dir, 'browser.html')


def dsb():
    return send_from_directory(pages_dir,'dsb.jpeg')


def ai():
    return send_from_directory(pages_dir,'ai.html')

def getaiapi():
    user=str(request.args.get('user'))
    hisid=request.args.get('hisid')
    with requests.post(
        url='https://api.deepseek.com/chat/completions',
        headers = {
        "Authorization": "Bearer <YOUR_DEEPSEEK_API_KEY>",
        "Content-Type": "application/json"
        },
        data = json.dumps({
        "model": "deepseek-chat",
        "messages": [
        {"role": "system", "content": str(request.args.get('sys'))},
        {"role": "user", "content": user}
        ],
        "stream": False,
        "temperature": float(request.args.get("temp"))
        })
        ) as req:
        if hisid:
          with open(log_dir+"\\{}'smemory.log".format(hisid),'a',encoding='utf-8') as f:
            content=json.loads(req.content.decode())['choices'][-1]['message']['content']
            print(content)
            f.write(',,,{"User":"'+user+'","Assistant":"'+content+'"}')
        return req.content


def gethistory(id):
    with open(log_dir+f'\\{id}\'smemory.log','r',encoding='utf-8') as file:
        content=file.read()[3:].split(',,,')
        result='{"content":"'
        print(content)
        if not content: return '{"content":"ID Not Found"}'
        for i in content:
            print(i)
            i=json.loads(i)
            result += '\n'+i['User']+'\n'+i['Assistant']
        print(result)
        return result+'"}'


def sendres(file):
    return send_from_directory(res_dir,file)


def render():
    return send_from_directory(pages_dir,'render.html')

def read_message():
    global date
    try:
        with open(os.path.join(message_dir,f'msg{date}.json'),'r',encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        with open(os.path.join(message_dir,f'msg{date}.json'),'w',encoding='utf-8') as file:
            file.write('{"content":[{"sender":"system","time":"none","content":"Newfilecreated'+str(datetime.datetime.now())+'"}]}')
        return '{"sender":"system","time":"none","content":"Newfilecreated"}'


def send_msg():
        global date
        sender=request.args.get('sender')
        print(sender)
        content=request.args.get('content')
        print(content)
        with open(os.path.join(message_dir,f'msg{date}.json'),'r',encoding='utf-8') as f:
            file=f.read()
        with open(os.path.join(message_dir,f'msg{date}.json'),'w',encoding='utf-8') as f:
            file=file[0:-2]+(',{"sender":"'+sender+' from '+request.remote_addr+'","time":"'+str(datetime.datetime.now())[-15:-7]+'","content":"'+content+'"}')
            file=file+']}'
            f.write(file)
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
    return send_from_directory(pages_dir,'login.html')


def talker():
    return send_from_directory(pages_dir,'talk.html')