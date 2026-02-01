from flask import send_from_directory, request
import os, requests, datetime
from tools import *
from config import *

def serve_file(filename):
    global pt
    if VAAvaliable(filename,'L'):
        return '<script>window.location.replace("https://mx.j2inter.corn/faq")</script>'
    t = str(datetime.datetime.now())
    if t[-12:-10]!=pt:
      with open(os.path.join(loc_dir,'local.log'),'a') as llog:
        llog.write('{0}:{1},__{2}<br/>'.format(request.remote_addr,request.headers.get('User-Agent'),filename))
    pt=t[:]
    return send_from_directory(loc_dir, filename)

def download_bili_file(videoName,list):
    try:
        servedVideoName=videoName.encode('iso-8859-1')
        print(servedVideoName)
        videoName=servedVideoName.decode('utf-8')
        print(videoName)
    except:
        pass
    if VAAvaliable(list,'N'):
        return '<script>window.location.replace("https://mx.j2inter.corn/faq")</script>'
    ua=request.headers.get('User-Agent')
    ip=request.remote_addr
    fileName = videoName+str(list)+".mp4"
    if os.path.exists(os.path.join(bili_dir, fileName)):
        return send_from_directory(bili_dir, fileName)
    print(videoName)
    if int(os.path.getsize(bili_dir)) >= 4294967296:
        a = os.system('rmdir /s /q {0}'.format(bili_dir))
        for i in [bili_dir, qq_dir, wyy_dir]:
            if not os.path.exists(i):
                os.makedirs(i, exist_ok=True)
    requestJson = requests.get(bili_avid_api_url, headers=bili_headers, params={"keyword": videoName}, timeout=10).json()
    avid = aidResover(requestJson, int(list))
    cid = requests.get(bili_cid_api_url+"aid="+str(avid), headers=bili_headers).json()["data"]["cid"]
    videoUrl = requests.get(bili_video_api_url+"avid="+str(avid)+"&cid="+str(cid)+"&qn=127&platform=html5&high_quality=1", headers=bili_headers).json()["data"]["durl"][0]["url"]
    resGet(videoUrl,fileName,bili_dir)
    with open(net_dir+'\\bili.log','a') as a:
        a.write('[{0}] {1} {2}<br/>'.format(ip,ua,videoName))
    return send_from_directory(bili_dir, fileName)

def download_bili_video(bv):
    if VAAvaliable(bv,'N'):
        return '<script>window.location.replace("https://mx.j2inter.corn/faq")</script>'
    fileName = bv+".mp4"
    if os.path.exists(os.path.join(bili_dir, fileName)):
        return send_from_directory(bili_dir, fileName)
    requests.get("https://bilibili.com", headers=bili_headers, timeout=10)
    cid = requests.get(bili_cid_api_url+"bvid="+str(bv), headers=bili_headers).json()["data"]["cid"]
    videoUrl = requests.get(bili_video_api_url+"bvid="+str(bv)+"&cid="+str(cid)+"&qn=127&platform=html5&high_quality=1", headers=bili_headers).json()["data"]["durl"][0]["url"]
    resGet(videoUrl,fileName,bili_dir)
    return send_from_directory(bili_dir, fileName)