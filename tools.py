import builtins
import datetime
import hashlib
import json
import os
import sys
import uuid
from functools import wraps
from typing import Union

import requests
from flask import (request, 
                   send_from_directory, 
                   redirect)

import config as _cfg
from base_tools import _parse_userlist_line
from config import *



# region replace open with a thread-safe version that locks files on Unix and Windows
# 保存原始 open
_original_open = builtins.open

def _is_write_mode(mode: str) -> bool:
    """判断是否为写入/读写模式。"""
    return ('+' in mode) or ((mode and mode[0]) in ('w', 'a', 'x'))

def _lock_file(fileobj, write_mode):
    """
    根据平台对文件对象加锁。
    返回是否成功加锁（用于调试，实际忽略）。
    """
    try:
        fd = fileobj.fileno()
    except (AttributeError, OSError):
        return False
    # ---------- Unix 系 ----------
    if sys.platform.startswith(('linux', 'darwin', 'freebsd', 'openbsd')):
        try:
            import fcntl
            lock_type = fcntl.LOCK_EX if write_mode else fcntl.LOCK_SH
            fcntl.flock(fd, lock_type)   # 阻塞直到锁可用
            return True
        except ImportError:
            pass  # 降级到下面的 Windows 尝试

    # ---------- Windows ----------
    if sys.platform == 'win32':
        try:
            import msvcrt
            # msvcrt 只支持排他锁（LOCK_EX），且需文件以写权限打开
            # 若为只读模式，跳过加锁（因为无法获得排他锁）
            if not write_mode:
                # 只读无法加排他锁，且无共享锁机制，忽略
                return False
            # 锁定整个文件（从当前文件指针开始，长度设为最大）
            # 注意：调用后文件指针会移动？msvcrt.locking 不会改变指针
            msvcrt.locking(fd, msvcrt.LK_LOCK, 0x7fffffff)
            return True
        except ImportError:
            pass

    # 其他平台或不支持锁，静默忽略
    return False

def open(*args, **kwargs):
    """
    包装后的 open，自动加建议锁（Unix）或排他锁（Windows 仅写模式）。
    所有原参数保持不变。
    """
    # 提取 mode
    if 'mode' in kwargs:
        mode = kwargs['mode']
    elif len(args) >= 2:
        mode = args[1]
    else:
        mode = 'r'

    # 调用原始 open
    fileobj = _original_open(*args, **kwargs)

    # 尝试加锁（异常被忽略，不影响程序）
    try:
        write_mode = _is_write_mode(mode)
        _lock_file(fileobj, write_mode)
    except Exception:
        # 任何锁错误（如权限、不支持）均忽略，保证原有逻辑正常运行
        pass

    return fileobj

# 替换内置 open
builtins.open = open
# endregion


user_passwords = _cfg.user_passwords

def load_userlist():
    global userlist, user_passwords
    with open(os.path.join(root, "userlist.txt"), "r", encoding='utf-8') as f:
        userlist.set_value(dict())
        user_passwords.set_value(dict())
        for line in f.readlines():
            ip, username, pwd_hash = _parse_userlist_line(line)
            if ip:
                userlist[ip] = username or ''
                if pwd_hash:
                    user_passwords[ip] = pwd_hash
        print("Userlists reloaded:", userlist)

def get_user_password_hash(ip):
    """获取 IP 对应的密码哈希（可能为空）"""
    return user_passwords.get(str(ip), '')


def set_user_password_hash(ip, sha256_hex):
    """设置 IP 对应的密码哈希，并持久化到 userlist.txt"""
    ip = str(ip)
    if sha256_hex:
        user_passwords[ip] = sha256_hex
    else:
        user_passwords.pop(ip, None)
    # 持久化：重写 userlist.txt，保留哈希字段
    _save_userlist_with_passwords()


def _save_userlist_with_passwords():
    """将 userlist + user_passwords 持久化到 userlist.txt"""
    from config import root
    lines = userlist.copy()
    with open(os.path.join(root, "userlist.txt"), "w", encoding='utf-8') as f:
        for ip, username in lines.items():
            pwd_hash = user_passwords.get(ip, '')
            if pwd_hash:
                f.write(f"{ip}:{username}:{pwd_hash}\n")
            else:
                f.write(f"{ip}:{username}:\n")
            print(f"Saved: {ip}:{username}")


class FastXORCipher:
    """XOR加密器，支持自定义长度密钥"""
    
    def __init__(self,key: str='default'):
        if not key:
            raise ValueError('No keys set')
        self.key = key.encode('utf-8')
    
    def _process_key(self, data_length: int):
        """处理密钥，扩展到与数据相同长度"""
        # 扩展密钥到数据长度
        if len(self.key) < data_length:
            # 使用哈希扩展
            expanded_key = bytearray()
            hash_obj = hashlib.sha256(self.key)
            
            while len(expanded_key) < data_length:
                hash_obj.update(hash_obj.digest())
                expanded_key.extend(hash_obj.digest())
            
            self.key = bytes(expanded_key[:data_length])
        elif len(self.key) > data_length:
            self.key = self.key[:data_length]
    
    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """
        加密数据
        
        参数:
            data: 要加密的数据（字符串或字节）
            key: 加密密钥（字符串或字节）
        
        返回:
            加密后的字节数据
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        self._process_key(len(data))
        
        # 使用内存视图和字节数组提高性能
        data_array = bytearray(data)
        key_array = bytearray(self.key)
        
        # 进行XOR
        i = 0
        length = len(data_array)
        while i < length:
            data_array[i] ^= key_array[i]
            i += 1
        
        return bytes(data_array)
    
def resGet(url,fileName,folder):
    save_path = os.path.join(folder, fileName)
    with requests.get(url, headers=headers, stream=True, timeout=10) as response:
        response.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"file save to: {os.path.abspath(save_path)}")
    return

def aidResover(json_data, index=0):
    index = index - 1
    aid_list = []
    try:
        for result in json_data.get('data', {}).get('result', []):
            if result.get('result_type') == 'video':
                for video in result.get('data', []):
                    if 'aid' in video:
                        aid_list.append(video['aid'])
        if index is not None:
            if isinstance(index, int):
                if 0 <= index < len(aid_list):
                    return aid_list[index]
                raise IndexError(f"list should in :0-{len(aid_list)-1}")
            raise TypeError("why list not int ?")
        return aid_list
    except Exception as e:
        print(f"Error: {str(e)}")
        return [] if index is None else None

def dot_checker(extra_name):
    for item in extra_name:
        if '.' in str(item):
            return True
    return False

def verifier(passwordgiven='', ip=''):
    if str(passwordgiven) == password:
        return 2
    elif ip in userlist.keys():
        return 1
    else:
        print('Unauthorized access attempt from IP: {}'.format(ip))
        return 0
        


def OnlyAvailable():
    global serverStatus
    if (not verifier(str(request.args.get('p')),str(request.remote_addr))) or (not serverStatus()):
        return True
    else:
        return False

def base_route(func):
  @wraps(func)
  def decorated():
    global serverStatus
    
    if (not verifier(str(request.args.get('p')),str(request.remote_addr))) or (not serverStatus()):
        return redirect(f"https{request.url[4:]}")
    else:
        return func()
  return decorated

def args_route(func):
  @wraps(func)
  def decorated(*args,**kwargs):
    global serverStatus
    
    if (not verifier(str(request.args.get('p')),str(request.remote_addr))) or (not serverStatus()):
        return redirect(f"https{request.url[4:]}")
    else:
        return func(*args, **kwargs)
  return decorated


def web_page(page):
    return send_from_directory(pages_dir, f'{page}')

def WSAvailable(service):
    global serverStatus
    if (not verifier(str(request.args.get('p')),str(request.remote_addr))) or (not serverStatus()):
        print(serverStatus())
        return redirect("https://mx.j2inter.corn/faq")
    if not os.path.exists(os.path.join(pages_dir,f'{service}')):
        with open(os.path.join(pages_dir,f'{service}'),'w+',encoding='utf-8') as f:
            f.write(f'<html><head><title>{service} Missing</title></head><body><h1>{service} Not Found</h1><p>Please ensure that the {service} file exists in the WebPages directory.</p></body></html>')
    return send_from_directory(pages_dir, f'{service}')

@base_route
def list_files():
    dir=request.args.get('d',"downloaded/local")
    try:
        filesL = os.listdir(os.path.join(root, dir))

    except FileNotFoundError:
        print(f"Directory not found: {root} to {os.path.join(root, dir)}")
        return "No such directory", 404
    except Exception as e:
        return f"Error: {str(e)}", 500
    html = f"""<script>navigator.clipboard.writetext("{dir}")</script><h1>Files:</h1>
            <ul style="font-size: 1.2em; padding: 20px;">"""
    html_list=""
    for file in filesL:
        file_path = os.path.join(root, dir, file)
        if os.path.isfile(file_path):
            html_list += f'<li><a href="/files/{dir+"/"+file}">{file}</a></li>'
        if os.path.isdir(file_path):
            html_list = f'<li><a href="/?d={dir+"/"+file}">{file}</a></li>' + html_list
    html += html_list + "</ul>"
    return html

def isVIP(username):
    money_file = os.path.join(log_dir, "moneys.json")
    try:
        with open(money_file, 'r', encoding='utf-8') as f:
            data = json.loads(f.read())
            if username in data and data[username]['isVIP']:
                return True
            else:
                return False
    except FileNotFoundError:
        return False

def GameAvailable(service):
    global serverStatus
    print(serverStatus())
    if (not verifier(str(request.args.get('p')),str(request.remote_addr))) or (not serverStatus()) or is_not_game_time():
        return redirect(f"https{request.url[5:]}")
    if not os.path.exists(os.path.join(pages_dir,f'{service}')):
        with open(os.path.join(pages_dir,f'{service}'),'w+',encoding='utf-8') as f:
            f.write(f'<html><head><title>{service} Missing</title></head><body><h1>{service} Not Found</h1><p>Please ensure that the {service} file exists in the WebPages directory.</p></body></html>')
    return send_from_directory(pages_dir, f'{service}')

def change_userlist(mode,ip,username,self_call=False):
    if not self_call:
        if verifier(str(request.args.get('p')))!=2: return "Illegal request", 404
    global userlist
    if username==" ":
        username=""
    with open(os.path.join(root, "userlist.txt"), "w+",encoding='utf-8') as f:
        if mode == "add":
            userlist[ip] = username
            f.seek(0)
            lines = userlist.copy()
            for everyip, everyusername in lines.items():
                pwd_hash = user_passwords.get(everyip, '')
                if pwd_hash:
                    f.write(f"{everyip}:{everyusername}:{pwd_hash}\n")
                else:
                    f.write(f"{everyip}:{everyusername}:\n")
                print(everyip, everyusername)
            f.truncate()
        elif mode == "remove":
            userlist.pop(ip, None)
            user_passwords.pop(ip, None)
            f.seek(0)
            lines = userlist.copy()
            for everyip, everyusername in lines.items():
                pwd_hash = user_passwords.get(everyip, '')
                if pwd_hash:
                    f.write(f"{everyip}:{everyusername}:{pwd_hash}\n")
                else:
                    f.write(f"{everyip}:{everyusername}:\n")
                print(everyip, everyusername)
            f.truncate()

def KeyDecoder(item,key):
    newDecoder = FastXORCipher(key)
    result = newDecoder.encrypt(item)
    return result


# 图片存放目录，用于聊天中的图片以链接形式展现
pics_dir = os.path.join(root, "pics")
os.makedirs(pics_dir, exist_ok=True)

def save_image_to_pics(image_bytes, key='default', ext='png'):
    """
    将图片字节加密保存到 pics/ 目录，返回可访问的 URL 路径 (/pics/<filename>)。
    
    参数:
        image_bytes (bytes): 图片的原始字节数据
        key (str): 用于加密的密钥，默认值为 'default'
        ext (str): 图片文件的扩展名，默认值为 'png'
    
    返回:
        str: 图片的 URL 路径，如 "/pics/20260502_153012_a1b2c3d4.png"
    """
    filename = (f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_" 
                f"{uuid.uuid4().hex[:8]}.{ext}")
    filepath = os.path.join(pics_dir, filename)
    # XOR 加密后写入磁盘，防止敏感图片直接泄露
    encrypted = KeyDecoder(image_bytes, key=key)
    with open(filepath, "wb") as f:
        f.write(encrypted)
    return f"/pics/{filename}"

def extract_and_save_image_from_pdf(link,key='default'):
    """
    从 PDF URL 的第二页提取第一张图片，保存到 pics/ 目录，返回 URL 路径。
    
    参数:
        link (str): PDF 文件的 URL
        key (str): 用于加密的密钥，默认值为 'default'
    返回:
        str | None: 图片的 URL 路径，失败则返回 None
    """
    import fitz  # PyMuPDF
    try:
        req = requests.get(link, headers=headers, timeout=15)
        doc = fitz.open(stream=req.content, filetype='pdf')

        if doc.page_count < 2:
            print("PDF 不足两页，无法获取第二页。")
            doc.close()
            return None

        page = doc[1]
        images = page.get_images(full=True)

        if not images:
            print("PDF 第二页未找到图片。")
            doc.close()
            return None

        img_info = images[0]
        xref = img_info[0]
        img_data = doc.extract_image(xref)
        img_bytes = img_data["image"]
        ext = img_data.get("ext", "png")
        doc.close()

        return save_image_to_pics(img_bytes, key=key, ext=ext)
    except Exception as e:
        print(f"提取 PDF 图片失败: {e}")
        return None


def track_visit(page_name):
    """
    记录用户对某个功能页面的访问。
    
    参数:
        page_name (str): 页面中文名，如 "AI对话"、"聊天"、"文件串流" 等
    
    写入 logs/access_visits.json，每条记录包含时间、IP、用户名、页面名。
    """
    try:
        from flask import request
        ip = request.remote_addr
        username = userlist.get(str(ip), "")
        record = {
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "page": page_name,
            "username": username or ip,
            "ip": ip
        }
        visits_file = os.path.join(log_dir, "access_visits.json")
        os.makedirs(log_dir, exist_ok=True)
        visits = []
        if os.path.exists(visits_file):
            try:
                with open(visits_file, "r", encoding="utf-8") as f:
                    visits = json.loads(f.read())
            except:
                visits = []
        if len(visits)>=2:
            if "文件串流" in visits[-1]["page"] and "文件串流" in visits[-2]["page"] and "文件串流" in record["page"]:
                visits[-1]["time"]=record["time"] # 文件串流只记录开始和结束时间
            else:
                visits.append(record)
        else:
            visits.append(record)
        # 仅保留最近 1000 条
        if len(visits) > 1000:
            visits = visits[-1000:]
        with open(visits_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(visits, ensure_ascii=False))
    except Exception as e:
        print(f"track_visit error: {e}")
