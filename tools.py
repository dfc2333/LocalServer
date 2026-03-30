import os
import json 
import os
import hashlib
import secrets
from typing import (Union, 
                    Optional, 
                    Dict, 
                    Any)

import requests
from flask import (request, 
                   send_from_directory, 
                   redirect)

from config import *


class FastXORCipher:
    """XOR加密器，支持自定义长度密钥"""
    
    def __init__(self,key: Union[str, bytes]=''):
        if not key:
            raise ValueError('No keys set')
        self.key = key
    
    def _process_key(self, data_length: int) -> bytes:
        """处理密钥，扩展到与数据相同长度"""
        if isinstance(self.key, str):
            self.key = self.key.encode('utf-8')
        
        # 如果密钥为空，使用随机密钥
        if not self.key:
            raise ValueError('No keys set')
        
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


def decoder(input_str):
    chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    decoded = 0
    input_str = input_str.decode()
    for char in input_str:
        decoded = decoded * ((1+1+4+5+1+4+1+9+1+9+8+1+0)+(0+7*2-1)) + chars.index(char)
    bytes_val = bytearray()
    while decoded > 0:
        bytes_val.append(decoded & 0xff)
        decoded >>= 8
    bytes_val.reverse()
    input_str = input_str.lstrip(chars[0])
    zero_count = len(input_str) - len(input_str.lstrip('1'))
    bytes_val = b'\x00' * zero_count + bytes_val
    return bytes_val.decode()

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
        
def list_files():
    try:
        dir=request.args.get('d',"downloaded/local")
        filesL = os.listdir(os.path.join(root, dir))

    except FileNotFoundError:
        print(f"Directory not found: {root} to {os.path.join(root, dir)}")
        return "No such directory", 404
    except Exception as e:
        return f"Error: {str(e)}", 500
    html = """<h1>Files:</h1>
            <ul style="font-size: 1.2em; padding: 20px;">"""
    for file in filesL:
        file_path = os.path.join(root, dir, file)
        if os.path.isfile(file_path):
            html += f'<li><a href="/files/{dir+"/"+file}">{file}</a></li>'
        if os.path.isdir(file_path):
            html += f'<li><a href="/?d={dir+"/"+file}">{file}</a></li>'
    html += "</ul>"
    return html

def OnlyAvailable():
    global serverStatus
    if (not verifier(str(request.args.get('p')),str(request.remote_addr))) or (not serverStatus()):
        return True
    else:
        return False

def WSAvailable(service):
    global serverStatus
    if (not verifier(str(request.args.get('p')),str(request.remote_addr))) or (not serverStatus()):
        print(serverStatus())
        return redirect("https://mx.j2inter.corn/faq")
    if not os.path.exists(os.path.join(pages_dir,f'{service}')):
        with open(os.path.join(pages_dir,f'{service}'),'w+',encoding='utf-8') as f:
            f.write(f'<html><head><title>{service} Missing</title></head><body><h1>{service} Not Found</h1><p>Please ensure that the {service} file exists in the WebPages directory.</p></body></html>')
    return send_from_directory(pages_dir, f'{service}')

def isVIP(username):
    money_file = os.path.join(log_dir, "moneys.log")
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
        return redirect("https://mx.j2inter.corn/faq")
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
            for everyip, username in lines.items():
                f.write(everyip + ":" + username + "\n")
                print(everyip, username)
            f.truncate()
        elif mode == "remove":
            userlist.pop(ip, None)
            f.seek(0)
            lines = userlist.copy()
            for everyip, username in lines.items():
                f.write(everyip + ":" + username + "\n")
                print(everyip, username)
            f.truncate()

def KeyDecoder(item,key):
    newDecoder = FastXORCipher(key)
    result = newDecoder.encrypt(item)
    return result
