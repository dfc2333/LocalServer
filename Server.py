import random

import urllib3
from flask import (Flask, 
                   send_from_directory, 
                   request)

from tools import *
from config import *
from ControlService import *
from WebsiteService import *
from ai import *
from talk import *
from websocket_talk import *

# Initalize the Flask Server
app = Flask(__name__) 
app.config['JSON_AS_ASCII'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Needed for SocketIO sessions
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Initialize SocketIO
socketio = init_socketio(app)

services = {'/':                            list_files,
            '/music':                       music_page,             #音乐
            '/files/<path:filename>':      serve_file,             #服务器端文件传输
            '/start':                       start,                  #启动对外服务
            '/exit':                        tmpexit,                #暂停对外服务
            '/restart':                     restart,                #重启整台电脑
            '/faq':                         Browser,                #打开跳转链接的输入框
            '/faq/':                        Browser,                #打开跳转链接的输入框
            '/dsb':                         dsb,                    #arc定数表（？
            '/stop':                        stop,                   #关掉整台电脑
            '/clean':                       clean,                  #清理下载的文件
            '/cmd/<path:cmdstr>':           run_cmd,                #运行cmd命令
            '/blog':                        blog,                   #爬取b站操作的日志
            '/llog':                        llog,                   #服务器端视频传输日志
            '/end':                         end,                    #结束所有服务，关闭服务器程序
            '/ai':                          ai,                     #AI对话页面
            '/api/history/<id>':            gethistory,             #获取AI对话历史
            '/res/<path:file>':             sendres,                #传输资源文件，如js，css等
            '/erm':                         render,                 #渲染LaTeX和markdown
            '/contact/<path:a>':            contact,                #向电脑发送文本，并存储在根目录下的contacts.txt中
            '/view/<path:path>':            view,                   #浏览根目录下的文件，也可以后面跟路径
            '/message':                     read_message,           #返回消息列表，用于talk
            '/sendmsg':                     send_msg,               #发送消息，用于talk
            '/announce':                    announce,               #发布公告，用于talk
            '/login':                       login,                  #登录，用于talk，使用cookie存储账户名，并且只能设定一次，修改的功能还没做：）
            '/talk':                        talker,                 #talk主页面
            '/changeip/<mode>':             changeip,               #更改允许访问的IP地址，mode为模式，可选"add"（添加）和"remove"（去除），ip地址通过请求参数ip传递，服务器重启后留存
            '/loadips':                     load_userlist,          #重新加载允许访问的IP地址列表
            '/changevip/<mode>':            changeVIP,              #更改用户VIP状态，mode为模式，可选"add"（添加）和"remove"（去除），用户名通过请求参数username传递
            '/api/getmoney':                getMoney,               #获取用户余额，用于AI对话页面显示
            '/setname':                     setName,                #设置用户名，用于talk和ai
            '/client-lzysso/h5-sso':        Browser,                #客户端登录页面
            '/xkl':                         xkl,                    #dino
            '/getname':                     getName,                #获取用户名
            '/read':                        read,                   #获取readme文件内容
            '/group/create':                create_group,           #创建群聊
            '/group/join':                  join_group,             #加入群聊
            '/group/list':                  list_groups,            #获取群聊列表
            '/group/info':                  group_info,             #获取群聊信息
}
for path, func in services.items():
    app.route(path)(func)

# Some post methods
app.route('/api/get',methods=['POST'])(getaiapi)
app.route('/save',methods=['POST'])(save)

def died():
    username=userlist.get(request.remote_addr)
    dieof = random.choice([
"掉出了这个世界",
"被僵尸杀死了",
"对于这个世界太弱小了",
"在与烈焰人的战斗中被烤的酥脆",
"，我喜欢你❤",
"被toni杀死了",
"被lhl杀死了",
"，我们睡觉吧",
"被女巫所使用的魔法杀死了",
"被末影龙所使用的魔法杀死了",
"从高处摔了下来",
"落地过猛",
"感受到了动能",
"，你喜欢我❤",
"的决心碎了一地💔",
"被落下的铁砧压扁了",
"窒息了",
"溺水了",
"浴火焚身",
"被一道音波尖啸抹除了",
"爆炸了",
"感受到了古人的智慧",
"凋零了",
"试图在岩浆里游泳",
"发现地板是岩浆",
"向二维跌落"
])
    return f"""
<h1 style="text-align: center;">
你死了!
</h1>
<br>
<p style="text-align: center;">
{username}{dieof}
</p>
<br>
<a 
href="/respawn" 
style="text-align: center; 
       display: block; 
       background-color: #bbbbbb; 
       color: white; 
       padding: 10px;">
重生
</a>
<br>
<a 
href="/faq" 
style="text-align: center; 
       display: block; 
       background-color:#bbbbbb; 
       color: white; 
       padding: 10px;">
主菜单
</a>"""

def respawn():
    return "你的床或已充能的重生锚不存在或已被阻挡"

def tp():
    return "你没有使用该命令的权限"

easter_egg={
            "/kill": died,
            "/respawn":respawn,
            "/tp": tp
}
for path, func in easter_egg.items():
    app.route(path)(func)

# Register SocketIO event handlers
register_socketio_events(socketio)

# Other useful things
@app.route('/showuser')
def showuser():
    return str(userlist)


if __name__ == "__main__":

    socketio.run(
        app,
        host="0.0.0.0",
        port=80,
        debug=True,
    )

