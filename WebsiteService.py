import os
import datetime
import hashlib
import json

import requests
from flask import send_from_directory, request, redirect
from flask import jsonify
from tools import (
    WSAvailable as available,
    OnlyAvailable,
    GameAvailable,
    userlist,
    change_userlist,
    pics_dir,
    KeyDecoder,
    track_visit,
    base_route,
    web_page,
    args_route,
    get_user_password_hash,
    set_user_password_hash,
)
from ControlService import run_cmd
from config import *

@base_route
def entry():
    """
    服务器入口 (/faq, /client-lzysso/h5-sso)。
    始终显示 access.html（密码输入页）。
    设了密码 → 输入密码验证后跳 /jump。
    没设密码 → access.html 自己会跳 /jump。
    """
    track_visit('跳转链接')
    return send_from_directory(pages_dir, 'access.html')

@base_route
def jump():
    """
    跳转输入框页面 (/jump)
    """
    track_visit('浏览器页')
    return web_page('browser.html')

@base_route
def seewo():
    '''链接到希沃vnc'''
    return redirect("http://192.168.40.99:9000/vnc.html")

@base_route
def access_page():
    """密码验证页面"""
    return send_from_directory(pages_dir, 'access.html')

@base_route
def setpass_page():
    """密码设置页面"""
    return send_from_directory(pages_dir, 'setpass.html')



def xkl():
    track_visit('游戏')
    return GameAvailable('xkl.html')

@base_route
def music_page():
    track_visit('音乐')
    try: 
            requests.get('http://192.168.40.114:1919/started')
    except:
            run_cmd("java -jar ./LocaalServerKt-1.0.jar")
    return web_page("tomusic.html")

@base_route
def dsb():
    track_visit('定数表')
    return web_page('dsb.jpeg')

@base_route
def suggest():
    if not os.path.exists(os.path.join(log_dir,"suggestions.json")):
        with open(os.path.join(log_dir,"suggestions.json"),"x") as file:
            file.write("[]")
    if request.method == "POST":
        data = request.get_json()
        with open(os.path.join(log_dir,"suggestions.json"),"r", encoding="utf-8") as file:
            old=json.loads(file.read())
        old.append({"suggester":data["suggester"],"suggestion":data["content"]})
        with open(os.path.join(log_dir,"suggestions.json"),"w",encoding="utf-8") as file:
            json.dump(old,file,ensure_ascii=False)
    return web_page("suggest.html")
    

def setName():
    username = str(request.args.get('username'))
    ip = request.remote_addr
    if (not username) or (username.strip() in userlist.values()) or (not userlist.get(ip,'')):
        return "sth went wrong", 400
    change_userlist('add', ip, username, self_call=True)
    return "Username set successfully"

@base_route
def getName():
    username = userlist.get(str(request.remote_addr),'')
    if not username:
        return "No username provided", 400
    return username

@args_route
def sendres(file):
    print(os.path.join(res_dir, os.path.dirname(file)), os.path.basename(file))
    return send_from_directory(os.path.join(res_dir, os.path.dirname(file)), os.path.basename(file))

@base_route
def render():
    track_visit('编辑页')
    return available('render.html')

@base_route
def read():
    file=request.args.get('name','README.md')
    with open(os.path.join(root,file),'r',encoding='utf-8') as f:
        content=f.read()
        print(content)
        return content

@base_route
def save():
    request_content = request.get_json().get('content','')
    if not request_content:
        return "No content provided", 400
    file = request.args.get('name','README.md')
    with open(os.path.join(root,file),'w',encoding='utf-8') as f:
        f.write(request_content)
    return "Saved successfully"
    
@args_route
def serve_file(filename):
    track_visit('文件串流')
    directory=os.path.join(root, os.path.dirname(filename))
    print(directory)
    return send_from_directory(directory, os.path.basename(filename))

@args_route
def serve_pics(filename):
    """
    读取 pics/ 下加密的图片文件，解密后返回给前端。
    图片存盘时经过了 XOR 加密，请求时实时解密输出。
    """
    filepath = os.path.join(pics_dir, filename)
    if not os.path.exists(filepath):
        return "图片不存在", 404

    # 读取加密的图片数据，解密后得到原始字节
    with open(filepath, 'rb') as f:
        encrypted = f.read()
    decrypted = KeyDecoder(encrypted, request.args.get('key','default'))

    # 根据扩展名判断 MIME 类型
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'png'
    mimetype = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'webp': 'image/webp',
    }.get(ext, 'application/octet-stream')

    return decrypted, 200, {'Content-Type': mimetype}

# API Routes
@base_route
def api_setpass():
    """
    设置/修改当前 IP 的跳转密码。
    POST JSON: {password: "明文密码"}
    服务端计算 SHA-256 后存储，兼容 Chrome 64 等不支持 crypto.subtle 的浏览器。
    """
    data = request.get_json() or {}
    pwd = data.get('password', '')
    if not pwd:
        return jsonify({"success": False, "error": "密码不能为空"}), 400
    pwd_hash = hashlib.sha256(pwd.encode('utf-8')).hexdigest()
    ip = str(request.remote_addr)
    set_user_password_hash(ip, pwd_hash)
    return jsonify({"success": True})

@base_route
def ispass():
    """检查当前 IP 是否已设置跳转密码（ispass=true → 需要输入密码，false → 直接放行）"""
    ip = str(request.remote_addr)
    has_pass = bool(get_user_password_hash(ip))
    return jsonify({"ispass": has_pass})

@base_route
def api_verifypass():
    """验证密码是否正确。POST JSON: {password: "明文密码"}，服务端自行哈希后比对。"""
    data = request.get_json() or {}
    pwd = data.get('password', '')
    ip = str(request.remote_addr)
    stored_hash = get_user_password_hash(ip)
    if not stored_hash:
        return jsonify({"isRight": True})
    pwd_hash = hashlib.sha256(pwd.encode('utf-8')).hexdigest()
    return jsonify({"isRight": pwd_hash == stored_hash})
