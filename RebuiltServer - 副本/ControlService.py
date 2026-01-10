from flask import request, send_from_directory
import os
from tools import verifier
from config import root, serverStatu, loc_dir, net_dir, change_allowed_ips, date, serverStatu

def start():
    global serverStatu
    if verifier(request.args.get('p'),request.remote_addr)!=2: return "Illegal request", 404
    serverStatu = True
    print(f"serverStatu updated to: {serverStatu}")
    return 'successfullly started'

def tmpexit():
    if verifier(request.args.get('p'),request.remote_addr)!=2: return "Illegal request", 404
    global serverStatu
    serverStatu = False
    return 'successfully exited'

def restart():
    if verifier(request.args.get('p'),request.remote_addr)!=2: return 'unauth'
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
    if verifier(request.args.get('p'))!=2: return "Illegal request", 404
    ip=request.args.get('ip')
    if not ip:
        return "No ip provided", 400
    if mode not in ['add','remove']:
        return "Invalid mode", 400
    change_allowed_ips(mode,ip)
    return f"Successfully {mode}ed IP: {ip}"

def view(path):
    with open(os.path.join(root,path),'r',encoding='utf-8') as file:
        return file.read()
    
def contact(a):
    with open(root+'\\contact.txt','w',encoding='utf-8') as file:
        file.write(a)