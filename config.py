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
    def __init__(self, value={}):
        self._value = value
        self._lock = threading.Lock()
    
    def __call__(self):
        with self._lock:
            return self._value

    def __str__(self):
        with self._lock:
            return str(self._value)

    def set_value(self, value):
        with self._lock:
            self._value = value

    def __add__(self, other:dict):
        with self._lock:
            self._value.update(other)
            return self._value
    
    def __getitem__(self, key):
        with self._lock:
            return self._value.get(key,None)
        
    def __setitem__(self, key, value):
        with self._lock:
            self._value[key] = value
    
    def pop(self, key, default=None):
        with self._lock:
            return self._value.pop(key, default)
    
    def copy(self):
        with self._lock:
            return self._value.copy()
    def items(self):
        with self._lock:
            return self._value.items()
    def __contains__(self, key):
        with self._lock:
            return key in self._value
    def keys(self):
        with self._lock:
            return self._value.keys()
    def values(self):
        with self._lock:
            return self._value.values()
    def get(self, key, default=''):
        with self._lock:
            return self._value.get(key, default)


serverStatus = ThreadSafeGlobal()
serverStatus.set_value(0)        # 0: 默认暂停服务, 1: 默认开启服务
userlist = ThreadSafeGlobal()
userlist.set_value(dict())

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
try:
    bili_cookie = decoder(b"yourbilicookiehere")
except ValueError as e:
    print("bili cookie not filled")
    bili_cookie=""
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
try:
except ValueError:
    print("password not given, you won't be able to /start the server.")
    password=""

if not os.path.exists(os.path.join(root, "userlist.txt")):
    with open(os.path.join(root, "userlist.txt"), "w+") as f:
        print("Creating userlist.txt file.")
        f.write("")
        
with open(os.path.join(root, "userlist.txt"), "r", encoding='utf-8') as f:
    for line in f.readlines():
        if line.strip():
            try:
                ip, username = line.strip().split(":", 1)
                userlist[ip] = username
            except:
                line.replace(':','')
                userlist[line.strip()]=''

    print("Userlists loaded:", userlist)

def change_userlist(mode,ip,username):
    global userlist
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

def load_userlist():
    global userlist
    with open(os.path.join(root, "userlist.txt"), "r", encoding='utf-8') as f:
        userlist = dict()
        for line in f.readlines():
            if line.strip():
                try:
                    ip, username = line.strip().split(":", 1)
                    userlist[ip] = username
                except:
                    line.replace(':','')
                    userlist[line.strip()] = ''
        print("Userlists reloaded:", userlist)

#Games Forbidden in classes
forbidden_time=ThreadSafeGlobal({"07:28:00":"08:40:00",
                                 "08:50:00":"09:30:00",
                                 "10:00:00":"10:40:00",
                                 "10:50:00":"11:30:00",
                                 "11:40:00":"12:20:00",
                                 "14:30:00":"15:10:00",
                                 "15:20:00":"16:00:00",
                                 "16:10:00":"16:50:00",
                                 "17:00:00":"17:40:00"})
forbidden_time1=ThreadSafeGlobal({"07:28:00":"08:40:00",
                                  "08:50:00":"09:30:00",
                                  "09:40:00":"10:10:00",
                                  "10:20:00":"11:10:00",
                                  "11:20:00":"12:00:00",
                                  "14:30:00":"15:10:00",
                                  "15:20:00":"16:00:00",
                                  "16:10:00":"16:50:00",
                                  "17:00:00":"17:40:00"})        #备用课表
def is_game_time():
    now = datetime.datetime.now().time()
    for start_str, end_str in forbidden_time.items():
        start_time = datetime.datetime.strptime(start_str, "%H:%M:%S").time()
        end_time = datetime.datetime.strptime(end_str, "%H:%M:%S").time()
        if start_time <= now <= end_time:
            return False
    return True


#other things
pt=''
