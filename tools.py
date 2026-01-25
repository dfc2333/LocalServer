import requests, os, json
from config import headers, password, allowed_ips, loc_dir, net_dir,pages_dir, serverStatus, log_dir
from flask import request, send_from_directory, redirect
from typing import Dict, Any


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

def apiGet(url,name,platform) -> Dict[str,Any]:
    if platform == "wyy": Key = "keywords"
    elif platform == "qq": Key = "key"
    else: 
        print('Platform Error')
        return {"result": {"songs": [{"id": 0}]},"data": {"list": [{"songmid": 0}]}}
    result = requests.get(url, headers=headers, params={Key: name}, timeout=10).json()
    return result

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
    elif ip in allowed_ips:
        return 1
    else:
        print('Unauthorized access attempt from IP: {}'.format(ip))
        return 0
        
def list_files():
    try:
        filesL = os.listdir(loc_dir)
        filesN = os.listdir(net_dir+'/bili')
    except FileNotFoundError:
        return "No such directory", 404
    except Exception as e:
        return f"Error: {str(e)}", 500
    print(filesL,filesN)
    html = """<h1>Avaliable files list:</h1>
            <ul style="font-size: 1.2em; padding: 20px;">
            <p>FilesL:</p>"""
    for file in filesL:
        file_path = os.path.join(loc_dir, file)
        if os.path.isfile(file_path):
            html += f'<li><a href="/local/{file}">{file}</a></li>'
    html += "<p>FilesN:</p><br/>"
    for file in filesN:
        file_path = os.path.join(net_dir+'/bili', file)
        if os.path.isfile(file_path):
            html += f'<li><a href="/net/bili/{file}">{file}</a></li>'
    html += "</ul>"
    return html

def VAAvaliable(filename,LorN=''):
    global serverStatus
    if (not verifier(str(request.args.get('p')),str(request.remote_addr))) or \
       (not serverStatus()) or \
       ((not (filename.lower().endswith('.mp4') or filename.lower().endswith('.mov'))) if LorN=='L' else \
       dot_checker(filename)):
        return True
    else:
        return False

def WSAvaliable(service):
    global serverStatus
    print(serverStatus())
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