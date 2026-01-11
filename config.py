import datetime
import os

global serverStatu

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

serverStatu = True             #服务状态默认设为关，可根据需要自行调整
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
bili_cookie = decoder(b"4cMqtCFjRXgZaFACXRapCQ6gnHG81kBs4pMBhkLBkLsMWvSZd4fJH6s3ZmRSsWWueWz3HLzXxpsDcV7pHBeo3LWufwiMxcWWFSi7hcBtXm1f86j8dd9Btu64Zvw5qy76Nf8QLKTToz38BW7cYxU7qbkgZtXXyJSqZrhZHwrgCYyXA1AxqKVmK3ZQxKSRSkmSxKAbBQnmssVtpJzF6EGWAaDw1yWy5XSgs39qpdzs7J5Qx1McDLVfBXWCCC5jbJNHYEwU5a7VfCxfQfQVhGFPyZQb6SDAozoL3cFdowdavmgYRt4jGcpUgcFDk3AWVZZUGu8zrYLJBnVaFE2ShupMzobpPqQU162kqBgtZ76qNsXpwdAJZtv55C8oZiJQuW4wNWVcxvW6XhdVCczECgXsArfmqTVpy6y5NfUbsSZFJnJgCdQNT7HwRW2d5n7sQyc7ynkyB9hk2Yv3trKFKHwHafeiz3bXKPw9acZk6u8DQwhDcpqknsYQK3CxwjBsPVmbJ6KqQBU8aBP3BFFEKeNCiQohG2vvjrohssXrYGfAp2BLv74JSxrb89vNBRXSJopuCvmCtJKgy5n32MVTaoCSxpAxZtgDvTrZpDfKkCafLUN5yJnJEhT67uESc8dP9X8w5iKxbD2ASMi5U8WY57BSE9oz3Dh5gcvPU9tGxNqkLXTQEwpuYXDtnS65fXmmYbXt6yB74XUrVLCEx3sW1Uh8D4cS8wtauDSQJ4dCcYpjwNF85nBCQWvPHD177md8c4vkNqdtU3oE9xCDJtkBv1C1Qt9bo2fgWbBkXUF5FQD1rwcCqf7LvEMf8xjdrLmcJTEHHe279jExxeSGr9nGCJZHSDiCqvnidZXgsWyckd55AM1Zn43St3S3HcJYdULLRFvCG6yxCEzrecSmwntwuzsK6VawLhuwTJP5kxnbHNj4GtAPBmGNTUWSXEX2BE6DWznziqrtEcwxgUejio7GDebtkfvE5HpuTbeP6rUkdFSKZJuZjqGJ8Xj2G9CyBhGGCxQQBKPyFR21s1TXdeEcEBHAy8k2yVbh23DvxRBg3zAAe47s3i7MgjZKY5A3ei7UPxW7X5piZStf77sNAcH51G62aJGZSJGHoN6VMazRfWv5FcFToixQ5s4PzN73qwbHaLA2noiNqpcV4ytusHu9E3zJBJPgNDREEBc63Pyx34PoRNaHdZNQ34Cnd2yHtZ8KSNx5JsZyJPuBhLi6Cp1pJsXgNaAUJj5mSnGQo5Qeb7EYW4cACJP8HzB9x7vmVyDMnEQNccAkBGiyJ4euMyoA9TTW8FcPJS8oWfG6nHaR5FUpn9G3X5rJazXf1AUDLpGzW2zZMVeSdhSkjwHAMjnh38zZwPCYLouUijbYYC3L8tdxyaFyqh3KLoS6vWCRBsQeRxPF9a91PbEdD3F4hWHKqBnHnCrFQjGbZkcWUfZK1AtYgUczDupYXApm4w4NGTH1CiiLAfnFcK8pqVXsJW3XNVDiWBEGxWb8w3RK4DJcwTUJ9DwWxA3M5NkK4X85dEbtsjWVfdSdZDfYP8Smn73FDebccWEAPWjx73D7r45EY3ned7Mu7X3HAQioqPijxZDPt14fy")
bili_headers = { "User-Agent": defaultUA, "Cookie": bili_cookie }
#qq_cookie = requests.get("https://intellqc.com/user/getCookie?id="+decoder(b"hmdb4jwHChAP"), headers=headers, verify=False).json()["data"]["cookie"]
qq_cookie=''

# Directory Setup

root = os.path.dirname(os.path.abspath(__file__))
res_dir = os.path.join(root, "res")
down_dir = os.path.join(root, "downloaded")
loc_dir = os.path.join(down_dir, "local")
net_dir = os.path.join(down_dir, "net")
pages_dir = os.path.join(res_dir, "WebPages")
log_dir = os.path.join(root, "logs")
message_dir = os.path.join(root, "messages")
for i in [message_dir, log_dir, pages_dir, loc_dir, net_dir, os.path.join(net_dir, "wyy"), os.path.join(net_dir, "qq"), os.path.join(net_dir, "bili")]:
    if not os.path.exists(i):
        os.makedirs(i, exist_ok=True)
with open(log_dir+'\\local.log','w') as llog:
    llog.write('service started at {}<br/>\n'.format(str(datetime.datetime.now())))

#Authentication Setup

passwordEncoded=b'Ho1JuQQ6Jq7'

if not os.path.exists(os.path.join(root, "allowed_ips.txt")):
    with open(os.path.join(root, "allowed_ips.txt"), "w") as f:
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
            f.truncate()

#other things
pt=''