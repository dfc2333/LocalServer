# LocalServer 项目介绍
基于科大讯飞平板中MX Player的多元服务器，实现了包括局域网内聊天，deepseek api 图形化调用（你需要自己的apikey，很便宜的，2块百万输入，3块百万输出），以及服务器端视频串流至平板，经过小的整改之后可以爬取b站视频和网易云音乐观看和听（其实一年前是可以的，不过可能是cookie过期了，现在用不了）。未违反任何科大讯飞政策，请放心使用。

# 使用和配置指南

## 1. 介绍
本项目是一个基于 `Flask框架` 的局域网服务器脚本，支持多种功能，包括文件传输、音乐、视频下载、AI 对话接口、消息管理等。以下是其主要功能和配置方法。

---

## 2. 配置

### 2.0 硬件要求及设置
本项目的正常使用需要三点要求：

- 你需要有一个学校发的科大讯飞C类平板（C8或C6等）
- 一个可以自定义的ap（推荐，你可以在连了你们教室的网的电脑上访问192.168.`40`（或者你的ip的这个位置的数字）.1来查看），或者平板允许你自定义dns服务器
- 一台固定放在学校的电脑，比如希沃或者左边那个畅言主机（推荐）

本项目的体验可以由以下三点提升：

- 你们的平板允许使用一个叫MX PLAYER的应用，并且点击关于页面的链接弹出connection refused（该应用可以在主页上方搜索处启动）**注意，你需要它以播放视频的画面**
- 有点钱或者同学有点钱以充deepseek和联网搜索的api
- 一群志同道合的同学们

如果你使用ap配置且有畅言主机：
1. 抓包畅言主机获取ap登录账号和密码
- 或者你可以先试试我们的：账号`admin`，密码`adminiwjB82rX`
- 抓包教程此处不赘述，请自行上网查找。大体思路就是畅言主机每次启动都会向ap发送一条网络请求以将jkinternet.changyan.com解析到该主机，这条请求包含了账号和密码数据。
2. 配置DNS代理


### 2.1 安装依赖
确保已安装:
JDK 25
Python 3，并安装以下依赖库：
```bash
pip install flask requests urllib3
```

### 2.2 配置文件
本项目依赖 `config.py` 文件进行配置。

必须要配置的项：

- `deepseek_api_key_encoded`：使用`encode.py`进行`base58`加密的deepseek api key。
- `bili_cookie`：使用`encode.py`进行`base58`加密的bilibili的cookie
- `passwordEncoded`：使用`encode.py`进行`base58`加密的服务器管理密码

可选配置的项：

- bocha博查apikey：在WebsiteService.py的execute\_web\_search中的请求体处配置

---

## 3. 使用方法

### 3.1 启动服务器程序
运行以下命令启动服务器：
```bash
python Server.pyw
```
服务器默认监听 `0.0.0.0:80`，可通过浏览器或其他客户端访问。

### 3.2 启动或停止服务器对外服务
访问以下链接以启动服务器：
```bash
http://<ip_or_mx.j2inter.com>/start?p=<your_password_here>
```
将其中 `<ip_or_mx.j2inter.com>` 和 `<your_password_here>`换成对应的东西

将`start`换成`exit`以暂停服务器对外服务，并将所有请求重定向到`mx.jrinter.com`

### 3.3 访问路径
以下是服务器支持的主要路径及其功能：

#### 文件传输
- **下载 B 站视频**: `/net/bili/<videoName>/<list>`
- **下载指定 B 站 BV 视频**: `/net/bilibv/<bv>`

#### 控制服务
- **启用对外服务**: `/start`
- **暂停对外服务**: `/exit`
- **重启整台电脑**: `/restart`
- **关闭整台电脑**: `/stop`
- **清理下载bilibili文件**: `/clean`
- **运行 CMD 命令**: `/cmd/<cmdstr>`
- **结束服务器程序**: `/end`

#### AI 对话
- **AI 对话页面**: `/ai`
- **获取 AI 对话接口（用在ai页面里）**: `/api/get`
- **获取对话历史（未完成）**: `/api/history/<id>`

#### 消息管理
- **talk页面**：`/talk`
- **读取消息**: `/message`
- **发送消息**: `/sendmsg`
- **发布公告**: `/announce`
- **音乐页面**: `/music`

#### 其他功能
- **浏览根目录文件或**: `/view/<path>`
- **渲染 LaTeX/Markdown**: `/render`
- **更改允许访问的 IP，mode为模式，add为增加，remove为减少**: `/changeip/<mode>?ip=<ip_address>`
- **arc定数表（？**: `/dsb`

---

## 4. 配置方法

### 4.1 修改监听端口
默认监听端口为 `80`，可在以下代码中修改：
```python 
#Server.py
app.run(
    host="0.0.0.0",
    port=80,
    debug=True
)
```

### 4.2 设置允许访问的 IP
在 `allowed_ips.txt`中逐行添加允许访问的 IP 地址。例如：
```python
#allowed_ips.txt
127.0.0.1
192.168.40.114
192.168.40.255
214.748.364.7 #only joking and don't add notes
```

---

## 5. 注意事项
1. **端口占用**: 如果端口 `80` 被占用，可更改为其他端口（如 `1145`）。
2. **日志管理**: 日志文件存储在 `log_dir` 中，定期清理以释放空间。
3. **音乐服务**: 音乐服务需要首次访问来启动Ktor Server，因此需要重新访问进入

---

## 6. 示例
启动服务器后，访问以下 URL 测试功能：
- 下载本地文件: `http://<server_ip>/local/test.mp4`
- 下载 B 站视频: `http://<server_ip>/net/bili/测试视频/1`
- AI 对话接口: `http://<server_ip>/api/get?user=你好&temp=0.7`

---
## 7. 作者的话
这个东西我和@sti-233花了好多个午休时间和下午放学到晚自习的时间在希沃上编写与测试，最终达到了现在的效果。总用时应该超过半年的这些时间，加起来也就差不多几周吧，我也不知道。我们技术力有限，有哪里不对的，欢迎提pr与issue。

因为我们主要是给电脑白痴们用，所以没有防御性编程，理解一下

render.html能用，有问题也不用管（？

我是个打引诱的，arcptt8.8，但是0氪，欢迎找我玩！

---

*最后更新：2026/1/11 by Foundchair Done*