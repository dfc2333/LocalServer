import os
import random

from flask import (Flask, 
                   redirect, 
                   request,
                   send_from_directory)
import urllib3

from ai import *
from config import *
from ControlService import *
from ManageService import *
from mail_service import check_mail, is_first_start_today
from talk import *
from tools import *
from WebsiteService import *
from websocket_talk import *

# ------Init------

# Initialize Flask app
app = Flask(__name__) 
app.config['JSON_AS_ASCII'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Initialize SocketIO
socketio = init_socketio(app)


@base_route
def check_mail_route():
    """手动触发邮件检查的路由"""
    success_count, messages = check_mail()
    log_html = "<br/>".join(messages)
    return f"<h2>邮件检查完成</h2><p>成功下载 {success_count} 封邮件的附件</p><hr/><pre>{log_html}</pre>"

@app.route("/beta")
@base_route
def beta():
    return redirect("http://192.168.40.114:1145/jump")

@base_route
def split():
    return web_page("split.html")

@base_route
def gethelp():
    return web_page("help.txt")

services = {'/':                            list_files,
            '/music':                       music_page,             #音乐
            '/files/<path:filename>':       serve_file,             #服务器端文件传输
            '/start':                       start,                  #启动对外服务
            '/exit':                        tmpexit,                #暂停对外服务
            '/restart':                     restart,                #重启整台电脑
            '/jump':                        jump,                   #浏览器页（需密码验证）
            '/faq':                         entry,              #服务器入口（带密码验证）
            '/faq/':                        entry,              #服务器入口（带密码验证）
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
            '/view/<path:path>':            view,                   #浏览根目录下的文件，也可以后面跟路径。对每个换行符会添加一个<br>
            '/message':                     read_message,           #返回消息列表，用于talk
            '/sendmsg':                     send_msg,               #发送消息，用于talk
            '/announce':                    announce,               #发布公告，用于talk
            '/talk':                        talker,                 #talk主页面
            '/changeip/<mode>':             changeip,               #更改允许访问的IP地址，mode为模式，可选"add"（添加）和"remove"（去除），ip地址通过请求参数ip传递，服务器重启后留存
            '/loadips':                     load_userlist,          #重新加载允许访问的IP地址列表
            '/changevip/<mode>':            changeVIP,              #更改用户VIP状态，mode为模式，可选"add"（添加）和"remove"（去除），用户名通过请求参数username传递
            '/api/getmoney':                getMoney,               #获取用户余额，用于AI对话页面显示
            '/client-lzysso/h5-sso':        entry,                  #入口
            '/xkl':                         xkl,                    #dino
            '/getname':                     getName,                #获取用户名
            '/read':                        read,                   #获取文件内容
            '/group/create':                create_group,           #创建群聊
            '/group/join':                  join_group,             #加入群聊
            '/group/list':                  list_groups,            #获取群聊列表
            '/group/info':                  group_info,             #获取群聊信息
            '/pics/<filename>':             serve_pics,             #聊天图片链接
            '/checkmail':                   check_mail_route,       #手动触发邮件检查
            "/seewo":                       seewo,                  #转到希沃vnc
            
            # 管理面板路由
            '/manage':                      manage_page,            #管理页面
            '/api/manage/config':           api_get_all_config,     #获取所有配置
            '/api/manage/users':            api_get_users,          #获取用户列表
            '/api/manage/server':           api_get_server_status,  #获取服务器状态
            '/api/manage/money':            api_get_money_data,     #获取用钱数据
            '/api/manage/features':         api_get_features,       #获取功能开关
            '/api/manage/schedule':         api_get_schedule,       #获取课表
            '/api/manage/access-log':       api_get_access_log,     #获取访问记录
            '/api/manage/ai-history':       api_get_ai_history,     #获取AI历史记录
            '/api/manage/daily-usage':      api_get_daily_usage,    #获取每日AI使用次数
            '/api/manage/ai-can-use':       api_check_ai_available, #AI可用性查询（前台调用）
            
            # 陪伴模式路由
            '/companion/config':            api_get_companion_config,    #获取陪伴模式配置
            '/companion/memory':            api_get_companion_memory,    #获取AI记忆内容
            '/api/mic2text':                api_get_mic2text,            #获取实时音频转录
            '/api/mic2text/query_records':  api_query_course_records,    #按课程查询语音记录
            '/api/mic2text/search':         api_search_mic2text_keyword, #关键词搜索课堂语音
            # 临时对话路由
            '/api/temp_chat/clear':         clear_temp_history,          #清空临时对话历史
            
            "/split":                       split,                   #分屏
            "/help":                        gethelp,                 #获取帮助
            
            # 密码验证路由
            '/ispass':                      ispass,                 #检查是否已验证密码
            '/access':                      access_page,            #密码验证页面
            '/setpass':                     setpass_page,           #密码设置页面
}
for path, func in services.items():
    app.route(path)(func)

# List ai logs
@app.route("/lisssssst")
@base_route
def list_services():
    return "<br>".join([f'<a href="/view/logs/{i}">{i}</a> <a href="/cmd/del C:%5CUsers%5Ciflytek%5CDocuments%5Clcsv%5Clogs%5C{i}">删除</a> <a href="/cmd/rename C:%5CUsers%5Ciflytek%5CDocuments%5Clcsv%5Clogs%5C{i} {"dontdel"+i}">标记别删</a>' for i in os.listdir(log_dir) if (not i.startswith("dontdel") and not ("mud" in i) and (i.endswith(".log")))])



# Some post methods
app.route('/api/get',methods=["GET",'POST'])(getaiapi)
app.route('/api/history/update',methods=['POST'])(update_history)
app.route('/save',methods=['POST'])(save)
app.route('/ai/ocr',methods=['POST'])(ocr_image)

# 陪伴模式 POST 路由
app.route('/companion/config', methods=['POST'])(api_save_companion_config)
app.route('/companion/memory', methods=['POST'])(api_save_companion_memory)

# Management API routes (POST/PUT/DELETE)
app.route('/api/manage/users', methods=['PUT'])(api_update_user)
app.route('/api/manage/users', methods=['DELETE'])(api_delete_user)
app.route('/api/manage/server', methods=['POST'])(api_set_server_status)
app.route('/api/manage/password', methods=['POST'])(api_change_password)
app.route('/api/manage/money', methods=['POST'])(api_update_money)
app.route('/api/manage/vip', methods=['POST'])(api_set_vip)
app.route('/api/manage/features', methods=['POST'])(api_set_features)
app.route('/api/manage/schedule', methods=['POST'])(api_set_schedule)
app.route('/api/manage/daily-usage', methods=['POST'])(api_update_daily_usage)
app.route('/api/manage/daily-usage/reset', methods=['POST'])(api_reset_daily_usage)
app.route('/api/manage/save-limit', methods=['POST'])(api_save_limit)

# 周课表管理 API
app.route('/api/manage/week-schedules', methods=['GET'])(api_get_all_week_schedules)
app.route('/api/manage/week-schedules/apply-default', methods=['POST'])(api_apply_default_week_schedule)

# Jump 页面密码 API
app.route('/api/setpass', methods=['POST'])(api_setpass)
app.route('/api/verifypass', methods=['POST'])(api_verifypass)

# 建议页面二合一
app.route("/suggest", methods=["POST", "GET"])(suggest)

@base_route
def died():
    username=userlist.get(request.remote_addr)
    enemy=("僵尸","杂兵","猪灵","僵尸猪灵","凋零骷髅","恼鬼","卫道士","Herobrine","娜迦","toni","lhl","掠夺者","白色僵尸","铁傀儡","末影人")
    dieof = random.choice([
"掉出了这个世界",
"对于这个世界太弱小了",
"在与烈焰人的战斗中被烤的酥脆",
"，我喜欢你❤",
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
]+[f"被{i}杀死了" for i in enemy])
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
href="/jump" 
style="text-align: center; 
       display: block; 
       background-color:#bbbbbb; 
       color: white; 
       padding: 10px;">
主菜单
</a>"""

@base_route
def respawn():
    return "你的床或已充能的重生锚不存在或已被阻挡"

@base_route
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
@base_route
def showuser():
    return str(userlist)
@app.route("/ptt/<num>/<score>")
@args_route
def calcptt(num,score):
    score=int(score)
    num=float(num)
    if score>=9800000:
        ptt=num+1+(score-9800000)/200000
    elif score >= 9500000:
        ptt=num+(score-9500000)/300000
    else:
        ptt="sb"
    return str(ptt)+"""<button onClick="window.location.replace('/jump')">back</button>"""

if __name__ == "__main__":

    # 每日首次启动时自动检查邮件
    if is_first_start_today():
        print("[MailService] 今日首次启动，自动检查邮件...")
        import threading
        def _startup_mail_check():
            success_count, messages = check_mail()
            for msg in messages:
                print(msg)
            # 写入启动日志
            with open(os.path.join(log_dir, 'local.log'), 'a', encoding='utf-8') as llog:
                llog.write(f'[MailService startup check] {success_count} attachments downloaded<br/>\n')
        threading.Thread(target=_startup_mail_check, daemon=True).start()

    socketio.run(
        app,
        host="0.0.0.0",
        port=80,
        debug=True,
    )
