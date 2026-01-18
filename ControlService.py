from flask import request, send_from_directory
import os, json
from tools import verifier
from config import root, loc_dir, net_dir, change_allowed_ips, serverStatus, log_dir

def start():
    global setServerStatus
    if verifier(str(request.args.get('p')),str(request.remote_addr))!=2: return "Illegal request", 404
    serverStatus.set_value(1)
    print(f"serverStatus updated to: {serverStatus()}")
    return 'successfullly started'

def tmpexit():
    if verifier(str(request.args.get('p')),str(request.remote_addr))!=2: return "Illegal request", 404
    global serverStatus
    serverStatus.set_value(0)
    return 'successfully exited'

def restart():
    if verifier(str(request.args.get('p')),str(request.remote_addr))!=2: return 'unauth'
    os.system('shutdown /r /t 0')
    return 'success'

def stop():
    os.system('shutdown /s /t 0')
    os._exit(0)

def clean():
    a = os.system('rmdir /s /q {0}'.format(net_dir))
    if not os.path.exists(loc_dir): os.makedirs(loc_dir, exist_ok=True)
    if not os.path.exists(net_dir): os.makedirs(net_dir, exist_ok=True)
    if not os.path.exists(net_dir+"/wyy"): os.makedirs(net_dir+"/wyy", exist_ok=True)
    if not os.path.exists(net_dir+"/qq"): os.makedirs(net_dir+"/qq", exist_ok=True)
    if not os.path.exists(net_dir+"/bili"): os.makedirs(net_dir+"/bili", exist_ok=True)
    open(net_dir+'\\bili.log','w').close()
    return str(a)

def run_cmd(cmdstr):
    a = os.popen(cmdstr)
    return str(a.read())

def blog():
    with open(net_dir+'\\bili.log') as a:
        resu = a.read()
    return str(resu)

def llog():
    with open(loc_dir+'\\local.log') as a:
        resu = a.read()
    return str(resu)

def end():
    os._exit(0)

def changeip(mode):
    if verifier(str(request.args.get('p')))!=2: return "Illegal request", 404
    ip=request.args.get('ip')
    if not ip:
        return "No ip provided", 400
    if mode not in ['add','remove']:
        return "Invalid mode", 400
    change_allowed_ips(mode,ip)
    return f"Successfully {mode}ed IP: {ip}"

def view(path):
    with open(os.path.join(root,path),'r',encoding='utf-8') as file:
        result = file.read().split('\n')
    return '<br/>'.join(result)
    
def contact(a):
    with open(root+'\\contact.txt','w',encoding='utf-8') as file:
        file.write(a)

def changeVIP(mode):
    username = str(request.args.get('username'))
    if not username:
        return "No username provided", 400
    isVIP = True if mode == 'add' else False
    money_file = os.path.join(log_dir, "moneys.log")
    try:
        with open(money_file, 'r', encoding='utf-8') as f:
            data = json.loads(f.read())
    except FileNotFoundError:
        data = {}
    if username not in data:
        data[username] = {"money": 0, "isVIP": False}
    data[username]['isVIP'] = isVIP
    with open(money_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False))
    return f"User {username} VIP status changed to {isVIP}, money: {data[username]['money']}"