import os
import json
import datetime
from flask import request
from config import date, message_dir
from tools import (
    userlist,
    WSAvaliable as avaliable,
    decoder,
    KeyDecoder
)
from encode import base58_encode

def read_message():
    global date
    targetFile=''
    targetuser=str(request.args.get('targetuser')) if request.args.get('targetuser') else ''
    user=userlist.get(str(request.remote_addr),"")
    key = request.args.get("key","")
    
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
            return KeyDecoder(bytes(file.read(),encoding='utf-8'))
    except Exception as e:
        with open(os.path.join(message_dir,targetFile),'w',encoding='utf-8') as file:
            time = str(datetime.datetime.now())
            file.write(base58_encode(bytes('{"content":[{"sender":"system","time":"none","content":"Newfilecreated'+time+'"}]}',encoding='utf-8')))
        return '{"content":[{"sender":"system","time":"none","content":"Newfilecreated'+time+'","id":0}]}'


def send_msg():
        global date
        sender=userlist.get(str(request.remote_addr),'')
        if not sender:
            return '{"content":"No username provided"}'
        content=str(request.args.get('content'))
        targetuser=str(request.args.get('targetuser'))
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
            file=json.loads(decoder(bytes(f.read(),encoding='utf-8')))
        with open(os.path.join(message_dir,targetFile),'w',encoding='utf-8') as f:
            id = file["content"][-1]["id"]
            file['content'].append({'sender':sender,'time':str(datetime.datetime.now())[-15:-7],'content':content, "id":id+1})
            f.write(base58_encode(bytes(json.dumps(file,ensure_ascii=False),encoding='utf-8')))
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