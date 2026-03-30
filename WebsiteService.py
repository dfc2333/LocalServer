try:
    import os
    import datetime
    import requests
    from flask import send_from_directory, request, redirect
    from tools import (
        WSAvailable as available,
        OnlyAvailable,
        GameAvailable,
        userlist,
        change_userlist,
    )
    from ControlService import run_cmd
    from config import *
except ImportError as e:
    print(f"Error importing modules: {e}")


def Browser():
    return available('browser.html')

def xkl():
    return GameAvailable('xkl.html')

def music_page():
    if OnlyAvailable():
        return redirect('https://mx.j2inter.corn')
    else:
        try: 
            requests.get('http://192.168.40.114:1919/started')
        except:
            run_cmd("java -jar ./LocalServerKt-1.0.jar")
        return GameAvailable("tomusic.html")

def dsb():
    return available('dsb.jpeg')

def setName():
    username = str(request.args.get('username'))
    ip = request.remote_addr
    if (not username) or (username.strip() in userlist.values()) or (not userlist.get(ip,None)):
        return "sth went wrong", 400
    change_userlist('add', ip, username, self_call=True)
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
    return available('login.html')

def render():
    return available('render.html')

def read():
    file=request.args.get('name','README.md')
    with open(os.path.join(root,file),'r',encoding='utf-8') as f:
        content=f.read()
        print(content)
        return content

def save():
    request_content = request.get_json().get('content','')
    if not request_content:
        return "No content provided", 400
    file = request.args.get('name','README.md')
    with open(os.path.join(root,file),'w',encoding='utf-8') as f:
        f.write(request_content)
    return "Saved successfully"
    
def serve_file(filename):
    global pt
    if OnlyAvailable():
        return redirect('https://mx.j2inter.corn')
    print(f"Serving file: {filename} to {request.remote_addr}")
    t = str(datetime.datetime.now())
    if t[-12:-10]!=pt:
      with open(os.path.join(loc_dir,'local.log'),'a') as llog:
        llog.write('{0}:{1},__{2}<br/>'.format(request.remote_addr,request.headers.get('User-Agent'),filename))
    pt=t[:]
    directory=os.path.join(root, os.path.dirname(filename))
    print(directory)
    return send_from_directory(directory, os.path.basename(filename))