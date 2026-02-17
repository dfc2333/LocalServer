import os
import datetime
import requests
from flask import send_from_directory, request, redirect
from tools import (
    WSAvaliable as avaliable,
    OnlyAvailable,
    GameAvaliable,
    VAAvaliable,
    userlist,
    change_userlist,
)
from ControlService import run_cmd
from config import *



def Browser():
    return avaliable('browser.html')

def xkl():
    return GameAvaliable('xkl.html')

def music_page():
    if OnlyAvailable():
        return redirect('https://mx.j2inter.corn')
    else:
        try: 
            requests.get('http://192.168.40.114:1919/started')
        except:
            run_cmd("java -jar ./LocalServerKt-1.0.jar")
        return redirect("http://192.168.40.114:1919/music")

def dsb():
    return avaliable('dsb.jpeg')

def setName():
    username = str(request.args.get('username'))
    if (not username) or (username.strip() in userlist.values()):
        return "sth went wrong", 400
    ip = request.remote_addr
    change_userlist('add', ip, username)
    return "Username set successfully"

def getName():
    username = userlist.get(str(request.remote_addr),None)
    if not username:
        return "No username provided", 400
    return username

def sendres(file):
    print(os.path.join(res_dir, os.path.dirname(file)), os.path.basename(file))
    return send_from_directory(os.path.join(res_dir, os.path.dirname(file)), os.path.basename(file))

def login():
    return avaliable('login.html')

def render():
    return avaliable('render.html')

def getReadme():
    with open(os.path.join(root,'README.md'),'r',encoding='utf-8') as f:
        return f.read()
    
def saveReadme():
    request_content = request.args.get('content',None)
    if not request_content:
        return "No content provided", 400
    with open(os.path.join(root,'README.md'),'w',encoding='utf-8') as f:
        f.write(request_content)
    return "Saved successfully"
    
def serve_file(filename):
    global pt
    if VAAvaliable(filename,'L'):
        return redirect('https://mx.j2inter.corn')
    t = str(datetime.datetime.now())
    if t[-12:-10]!=pt:
      with open(os.path.join(loc_dir,'local.log'),'a') as llog:
        llog.write('{0}:{1},__{2}<br/>'.format(request.remote_addr,request.headers.get('User-Agent'),filename))
    pt=t[:]
    return send_from_directory(loc_dir, filename)