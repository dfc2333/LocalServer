# config.example.py — 配置模板
# 复制此文件为 config.py，使用 encode.py 编码你的密钥后填入

import datetime
import os

from base_tools import decoder, ThreadSafeGlobal, _parse_userlist_line

date=str(datetime.datetime.now())[0:-16]

# ── Web API 密钥 ──

defaultUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
headers = { "User-Agent": defaultUA }
mic2text_url = "http://192.168.40.99:5000"  # 修改为你的 mic2text 服务地址

# 使用 encode.py 对以下密钥进行 Base58 编码，将输出字符串填入 decoder(b'...') 中
try:
    deepseek_api_key = decoder(b'<encoded_deepseek_api_key>')  # DeepSeek API Key
except ValueError:
    deepseek_api_key = ""
    print("deepseek api key not set or encoded key is invalid")

try:
    bocha_api_key = decoder(b'<encoded_bocha_api_key>')  # 博查联网搜索 API Key
except ValueError:
    bocha_api_key = ""
    print("bocha api key not set or encoded key is invalid")

# ── 邮件服务配置（可选） ──

try:
    mail_imap_server = decoder(b'<encoded_imap_server>')  # 如 imap.qq.com
except:
    mail_imap_server = ''
    print('mail server not set')

mail_imap_port = 993

try:
    mail_account = decoder(b'<encoded_mail_account>')
except ValueError:
    mail_account = ""
    print('mail account not set')

try:
    mail_password = decoder(b'<encoded_mail_password>')
except ValueError:
    mail_password = ""
    print('mail password not set')


# ── 目录初始化 ──

root = os.path.dirname(os.path.abspath(__file__))
res_dir = os.path.join(root, "res")
down_dir = os.path.join(root, "downloaded")
loc_dir = os.path.join(down_dir, "local")
net_dir = os.path.join(down_dir, "net")
mail_dir = os.path.join(down_dir, "mail")
pages_dir = os.path.join(res_dir, "WebPages")
log_dir = os.path.join(root, "logs")
message_dir = os.path.join(root, "messages")
bili_dir = os.path.join(net_dir,"bili")
for i in [bili_dir, message_dir, log_dir, pages_dir, loc_dir, net_dir, down_dir, mail_dir]:
    if not os.path.exists(i):
        os.makedirs(i, exist_ok=True)
with open(os.path.join(log_dir,'local.log'),'w') as locallog:
    locallog.write('service started at {}<br/>\n'.format(str(datetime.datetime.now())))

# ── 管理员密码 ──

try:
    password=decoder(b'<encoded_admin_password>')
except ValueError:
    print("password not given or encoded passwd is invalid, set to default:abc123")
    password="abc123"

# ── 服务器状态 & 用户列表 ──

serverStatus = ThreadSafeGlobal()
serverStatus.set_value(1)        # 0: 默认暂停服务, 1: 默认开启服务
userlist = ThreadSafeGlobal()
userlist.set_value(dict())
user_passwords = ThreadSafeGlobal()
user_passwords.set_value(dict())  # {ip: sha256_hex}

if not os.path.exists(os.path.join(root, "userlist.txt")):
    with open(os.path.join(root, "userlist.txt"), "x") as f:
        print("Creating userlist.txt file.")

with open(os.path.join(root, "userlist.txt"), "r", encoding='utf-8') as f:
    for line in f.readlines():
        ip, username, pwd_hash = _parse_userlist_line(line)
        if ip:
            userlist[ip] = username or ''
            if pwd_hash:
                user_passwords[ip] = pwd_hash
            else:
                user_passwords.pop(ip, None)

    print("Userlists loaded:", userlist)

# ── 上课时间限制（在此修改课表） ──

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
                                  "17:00:00":"17:40:00"})        # 备用课表

def is_not_game_time():
    now = datetime.datetime.now().time()
    for start_str, end_str in forbidden_time.items():
        print(start_str, end_str)
        start_time = datetime.datetime.strptime(start_str, "%H:%M:%S").time()
        end_time = datetime.datetime.strptime(end_str, "%H:%M:%S").time()
        print(start_time, end_time)
        if start_time <= now <= end_time:
            print("in forbidden time:", now, start_time, end_time)
            return True
    print("not in forbidden time:", now)
    return False



# ── 默认建议课表 ──
DEFAULT_WEEK_SCHEDULE = {
    "monday": [],
    "tuesday": [],
    "wednesday": [],
    "thursday": [],
    "friday": [],
    "saturday": [],
    "sunday": []
}
