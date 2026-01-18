import datetime
import os, threading

global serverStatus

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

class ThreadSafeGlobal:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()
    
    def __call__(self):
        with self._lock:
            return self._value
    
    def set_value(self, value):
        with self._lock:
            self._value = value

serverStatus = ThreadSafeGlobal()
serverStatus.set_value(0)        # 0: 默认暂停服务, 1: 默认开启服务

date=str(datetime.datetime.now())[0:-16]

#Web API Setup

defaultUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
headers = { "User-Agent": defaultUA }
wyy_songId_api_url = "https://ncm.nekogan.com/search"
wyy_songUrl_api_url = "https://ncm.nekogan.com/song/url/v1?"
qq_songId_api_url = "https://jennergray.com:3301/search"
qq_songUrl_api_url = "https://jennergray.com:3301/song/url?id="
# qq_songUrl_api_url = "https://intellqc.com/getMusicPlay?songmid="
qq_cookie_set_url = "https://jennergray.com:3301/user/setCookie?data="
bili_avid_api_url = "https://api.bilibili.com/x/web-interface/wbi/search/all/v2"
bili_cid_api_url = "https://api.bilibili.com/x/web-interface/view?"
bili_video_api_url = "https://api.bilibili.com/x/player/wbi/playurl?"
bili_cookie = decoder(b"yourbilicookiehere")
bili_headers = { "User-Agent": defaultUA, "Cookie": bili_cookie }
#qq_cookie = requests.get("https://intellqc.com/user/getCookie?id="+decoder(b"hmdb4jwHChAP"), headers=headers, verify=False).json()["data"]["cookie"]
qq_cookie=''
deepseek_api_key_encoded = b'<yourencodedapikeyhere>'

# Directory Setup

root = os.path.dirname(os.path.abspath(__file__))
res_dir = os.path.join(root, "res")
down_dir = os.path.join(root, "downloaded")
loc_dir = os.path.join(down_dir, "local")
net_dir = os.path.join(down_dir, "net")
pages_dir = os.path.join(res_dir, "WebPages")
log_dir = os.path.join(root, "logs")
message_dir = os.path.join(root, "messages")
wyy_dir = os.path.join(net_dir,"wyy")
qq_dir = os.path.join(net_dir,"qq")
bili_dir = os.path.join(net_dir,"bili")
for i in [bili_dir, qq_dir, wyy_dir, message_dir, log_dir, pages_dir, loc_dir, net_dir, down_dir]:
    if not os.path.exists(i):
        os.makedirs(i, exist_ok=True)
with open(os.path.join(log_dir,'local.log'),'w') as locallog:
    locallog.write('service started at {}<br/>\n'.format(str(datetime.datetime.now())))

#Authentication Setup

passwordEncoded=b'yourpasswordencodedhere'

if not os.path.exists(os.path.join(root, "allowed_ips.txt")):
    with open(os.path.join(root, "allowed_ips.txt"), "w+") as f:
        print("Creating allowed_ips.txt file.")
        f.write("")

with open(os.path.join(root, "allowed_ips.txt"), "r") as f:
    allowed_ips = set(line.strip() for line in f.readlines() if line.strip())
    print("Allowed IPs loaded:", allowed_ips)

def change_allowed_ips(mode,ip):
    global allowed_ips
    with open(os.path.join(root, "allowed_ips.txt"), "a+" if mode=="add" else "w+") as f:
        if mode == "add":
            allowed_ips.add(ip)
            f.write(ip + "\n")
        elif mode == "remove":
            allowed_ips.discard(ip)
            f.seek(0)
            lines = f.readlines()
            f.seek(0)
            for line in lines:
                if line.strip() != ip:
                    f.write(line)
                    print(line)
            f.truncate()

def load_allowed_ips():
    global allowed_ips
    with open(os.path.join(root, "allowed_ips.txt"), "r") as f:
        allowed_ips = set(line.strip() for line in f.readlines() if line.strip())
        print("Allowed IPs reloaded:", allowed_ips)

#other things
pt=''
