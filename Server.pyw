from flask import Flask
import urllib3
from tools import list_files
from VAService import *
from ControlService import *
from WebsiteService import *

app = Flask(__name__)           #初始化flask服务器
app.config['JSON_AS_ASCII'] = False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

services = {'/':                            list_files,
            '/net/bili/<videoName>/<list>': download_bili_file,     #B站视频
            '/net/bilibv/<bv>':             download_bili_video,    #B站指定bv视频
            '/local/<filename>':            serve_file,             #服务器端文件传输
            '/start':                       start,                  #启动对外服务
            '/exit':                        tmpexit,                #暂停对外服务
            '/restart':                     restart,                #重启整台电脑
            '/faq':                         Browser,                #打开跳转链接的输入框
            '/dsb':                         dsb,                    #arc定数表（？
            '/stop':                        stop,                   #关掉整台电脑
            '/clean':                       clean,                  #清理下载的文件
            '/cmd/<path:cmdstr>':           run_cmd,                #运行cmd命令
            '/blog':                        blog,                   #爬取b站操作的日志
            '/llog':                        llog,                   #服务器端视频传输日志
            '/end':                         end,                    #结束所有服务，关闭服务器程序
            '/ai':                          ai,                     #AI对话页面
            '/api/get':                     getaiapi,               #获取AI对话接口
            '/api/history/<id>':            gethistory,             #获取AI对话历史，未完成
            '/res/<path:file>':             sendres,                #传输资源文件，如js，css等，用于render的html
            '/render':                      render,                 #渲染LaTeX和markdown
            '/contact/<path:a>':            contact,                #向电脑发送文本，并存储在根目录下的contacts.txt中
            '/view/<path:path>':            view,                   #浏览根目录下的文件，也可以后面跟路径
            '/message':                     read_message,           #返回消息列表，用于talk
            '/sendmsg':                     send_msg,               #发送消息，用于talk
            '/announce':                    announce,               #发布公告，用于talk
            '/login':                       login,                  #登录，用于talk，使用cookie存储账户名，并且只能设定一次，修改的功能还没做：）
            '/talk':                        talker,                 #talk主页面
            '/changeip/<mode>':             changeip,               #更改允许访问的IP地址，mode为模式，可选"add"（添加）和"remove"（去除），ip地址通过请求参数ip传递，服务器重启后留存
            '/loadips':                     load_allowed_ips,       #重新加载允许访问的IP地址列表
            '/changevip/<mode>':            changeVIP,              #更改用户VIP状态，mode为模式，可选"add"（添加）和"remove"（去除），用户名通过请求参数username传递
            '/api/getmoney':                getMoney                #获取用户余额，用于AI对话页面显示
            }

for path, func in services.items():
    app.route(path)(func)


# fun main() {
if __name__ == "__main__":
    print(
        "\n"
        "Download file from local                          /local/filename.extra\n"
        "Download file from Neteasemusic                   /net/wyy/<songName>/<list>\n"
        "Download file from QQmusic                        /net/qq/<songName>/<list>\n"
        "Download file from Bilibili                       /net/bili/<keyword>/<list>\n"
        "Download specified file from Bilibili             /net/bilibv/<bvid>\n"
    )

    app.run(
        host="0.0.0.0",
        port=1145,
        threaded=True,
        debug=True
    )

# }

