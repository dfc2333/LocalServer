import os
import json
import datetime
from flask import request
from config import date, message_dir
from tools import (
    userlist,
    WSAvaliable as avaliable,
    KeyDecoder
)

def read_message():
    global date
    targetFile=''
    targetuser=str(request.args.get('targetuser')) if request.args.get('targetuser') else ''
    user=userlist.get(str(request.remote_addr),"")
    key = request.args.get("key","default")
    
    if not user:
        return '{"content":"No username provided"}'
    if (not targetuser in userlist.values()) or not targetuser:
        targetFile=f'msg{date}.json'
    else:
        for i in os.scandir(message_dir):
            users=i.name[3:-5].split('_')
            if (targetuser in users)and(user in users):
                targetFile=i.name
                break
        if not targetFile:
            targetFile=f'msg{user+"_"+targetuser}.json'

    try:
        with open(os.path.join(message_dir,targetFile),'r',encoding='utf-8') as file:
            return KeyDecoder(file.read(),key)
    except Exception as e:
        with open(os.path.join(message_dir,targetFile),'w',encoding='utf-8') as file:
            time = str(datetime.datetime.now())
            file.write(KeyDecoder('{"content":[{"sender":"system","time":"none","content":"Newfilecreated'+time+'","id":0}]}',key))
        return '{"content":[{"sender":"system","time":"none","content":"Newfilecreated'+time+'","id":0}]}'


def send_msg():
        global date
        sender=userlist.get(str(request.remote_addr),'')
        if not sender:
            return '{"content":"No username provided"}'
        content=str(request.args.get('content'))
        targetuser=str(request.args.get('targetuser'))
        key = str(request.ars.get('key',"default"))
        targetFile=''
        if not targetuser:
            targetFile=f'msg{date}.json'
        else:
            for i in os.scandir(message_dir):
                users = i.name[3:-5].split('_')
                if (targetuser in users)and(sender in users):
                    targetFile=i.name
                    break
            if not targetFile:
                targetFile=f'msg{sender+"_"+targetuser}.json'
        with open(os.path.join(message_dir,targetFile),'r',encoding='utf-8') as f:
            file=json.loads(KeyDecoder(f.read(),key))
        with open(os.path.join(message_dir,targetFile),'w',encoding='utf-8') as f:
            id = file["content"][-1]["id"]
            file['content'].append({'sender':sender,'time':str(datetime.datetime.now())[-15:-7],'content':content, "id":id+1})
            f.write(KeyDecoder(json.dumps(file,ensure_ascii=False)),key)
        return 'ok'


def announce():
    ctnt= request.args.get('content')
    if ctnt:
        with open(os.path.join(message_dir,'announcement.data'),'w',encoding='utf-8') as f:
            f.write(ctnt)
    else:
        with open(os.path.join(message_dir,'announcement.data'),'r',encoding='utf-8') as f:
            return f.read()

def talker():
    return avaliable('talk.html')