# LocalServer — 局域网多功能服务器

基于 **Flask + Flask-SocketIO** 的局域网服务器，专为科大讯飞平板（C6/C8 等）设计，在校园网络环境下实现**文件串流、AI 对话、局域网聊天、音乐播放、邮件附件下载**等多种功能。

---

## 目录

1. [功能一览](#1-功能一览)
2. [硬件与网络要求](#2-硬件与网络要求)
3. [快速开始](#3-快速开始)
4. [路由与 API 文档](#4-路由与-api-文档)
5. [配置指南](#5-配置指南)
6. [项目结构](#6-项目结构)
7. [注意事项](#7-注意事项)
8. [作者的话](#8-作者的话)
9. [致谢](#9-致谢)

---

## 1. 功能一览

| 模块 | 功能 | 技术亮点 |
|------|------|----------|
| **🤖 AI 对话** | DeepSeek API 图形化调用（流式输出） | 联网搜索、工具调用（记忆读写/课堂语音查询（需额外配置）/网页搜索与打开）、历史记录管理、每日限额 |
| **👤 陪伴模式** | AI 感知用户上下文 | 课表状态注入、教室麦克风实时转录、AI 长期记忆（按对话隔离）、距上课/下课倒计时 |
| **💬 局域网聊天** | 公共频道 + 私聊 + 群聊 | WebSocket 实时推送（主）+ HTTP 轮询（备用）、XOR 加密存盘、图片分享、消息撤回与引用、离线通知持久化 |
| **📁 文件串流** | 通过 MX Player 直接串流视频 | HTTP Range 请求、目录浏览 |
| **📧 邮件服务** | 自动下载标题含 "To Server:" 的邮件附件 | IMAP + 指纹去重（uid:filename:sha256[:8]）、每日首次启动自动检查 |
| **🎵 音乐** | Ktor Server 音乐播放页面 | Java JAR 后端，自动唤醒 |
| **🛠️ 管理面板** | 可视化 Web 管理后台 | 密码认证 + REST API，用户/功能/课表/AI历史全管理 |
| **📊 AI 限流** | 每人每天可配置次数限制 | 管理面板控制 |
| **🖥️ 远程控制** | 开关服务、重启/关机、运行 CMD 命令 | 密码 + IP 双重认证，关机与关服务器命令因安全原因不予设限 |
| **🎮 小游戏** | Dino 跑酷等 | 上课时间自动屏蔽 |
| **📝 课堂语音查询** | 按课程名/关键词搜索教室语音转录 | 对接 mic2text 服务，支持模糊搜索+上下文 |
| **🔤 OCR 识别** | 图片文字识别 | pytesseract，针对灰纸黑字做了二值化预处理 |
| **📄 文件读写** | 网页浏览/编辑服务器文件 | 在线编辑 + 保存 |

---

## 2. 硬件要求及设置

**本项目的正常使用（达成目的）需要三点要求：**

- 你需要有一个学校发的科大讯飞特定平板（C8或C6等）
- 一个可以自定义的ap（推荐，你可以在连了你们教室的网的电脑上访问网关来查看，有畅言主机的就一定有），或者你也可以买一个软路由，或者平板允许你自定义dns服务器
- 一台固定放在学校的电脑，比如希沃或者左边那个畅言主机（推荐）

<br/>

**本项目的体验可以由以下三点提升：**

- 你们的平板允许使用一个叫MX PLAYER的应用，并且点击关于页面的链接弹出connection refused（该应用可以在主页上方搜索处启动）**注意，你需要它以播放视频的画面**
- 有点钱或者同学有点钱以充deepseek和联网搜索的api
- 一群志同道合的同学们

<br/>

**如果你使用ap配置且有畅言主机：（推荐）**

1. **抓包畅言主机获取ap登录账号和密码**

> *或者你可以先试试我们的：账号`admin`，密码`adminiwjB82rX`*

抓包教程此处不赘述，请自行上网查找。大体思路就是畅言主机每次启动都会向ap发送一条网络请求以将`jkinternet.changyan.com`解析到该主机，这条http请求明文包含了账号和密码数据。

2. **配置DNS代理**

登录AP，网络设置-DNS代理。

- 如果你有MX Player，域名输入两个：`mx.j2inter.com`和`zhkt.changyan.com`
- 如果你没有，只需要输入`zhkt.changyan.com`
- 如果你刚好有一个问卷调查，那么恭喜你，获得一个更高版本的webview。再加上`www.lezhiyun.com`

<br/>

其他方法请参考dns代理设置，自行探索，如果要自建dns服务器，推荐使用python库`dnslib`

---

## 3. 快速开始

### 3.1 环境要求

- **Python** ≥ 3.9（推荐 3.11+）
- **JDK** 25（可选，仅音乐功能需要）

### 3.2 安装依赖

```bash
pip install flask flask-socketio requests beautifulsoup4 PyMuPDF pytesseract pillow numpy
```

### 3.3 配置密钥

使用 `encode.py` 对以下密钥进行 **Base58 编码**，将输出字符串填入 `config.py` 中对应位置：

```python
# 编辑 encode.py 的 __main__ 块，然后运行：
python encode.py
```

**必须设置：**

| 配置项 |说明 |
|--------|------|
| `deepseek_api_key` | DeepSeek API Key |
| `password` | 管理员密码 |
| `bocha_api+key` | 博查api key |

**可选设置（邮件服务）：**

| 配置项 |说明 |
|--------|------|
| `mail_imap_server` | IMAP 服务器地址（如 `imap.qq.com`） |
| `mail_account` | 邮箱账号 |
| `mail_password` | 邮箱密码 / 授权码 |

### 3.4 配置用户 IP 白名单

编辑 `userlist.txt`，每行格式 `IP:用户名` 或 `IP:用户名:sha256密码哈希`：

```
127.0.0.1:admin
192.168.40.114:blip_blop
192.168.40.255:foo:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

第三段为可选的 SHA-256 密码哈希，用于 `/faq` 等入口的跳转密码验证。

### 3.5 启动服务器

```bash
cd lcsv && python Server.py
```

服务器监听 `0.0.0.0:80`，局域网内访问 `http://<服务器IP>` 即可。

---

## 4. 路由与 API 文档

### 4.1 页面路由

| 路由 | 功能 | 备注 |
|------|------|------|
| `/` | 浏览下载目录文件 | 参数 `?d=path`，默认 `./downloaded/local` |
| `/ai` | AI 对话页面 | 如webview太老无法正常使用ai可将aiold.html替换为ai.html |
| `/talk` | 局域网聊天页面 | WebSocket 实时通信，无刷新按钮 |
| `/music` | 音乐播放页面 | 自动判断是否需要启动 Ktor JAR |
| `/faq` | 服务器入口 | 显示 access.html（密码验证页，若没有设置密码则自动跳转到`/jump`） |
| `/erm` | LaTeX / Markdown 渲染页，更便捷的文件编辑页（比起vnc） | |
| `/xkl` | Dino 小游戏 | 上课时间自动屏蔽 |
| `/dsb` | Arcaea 定数表图片 | XD |
| `/jump` | 跳转链接输入框 | 下面可以写服务器公告 |
| `/seewo` | 希沃 VNC 链接 | 跳转到 `192.168.40.99:9000/vnc.html`，请按需修改 |
| `/suggest` | 建议提交页面 | GET 显示页面，POST 提交建议 |
| `/split` | 分屏页面 | 2:3分屏 |
| `/help` | 帮助文本 | 没写完 |
| `/beta` | 跳转到测试版 | 重定向到 `192.168.40.114:1145/jump`，我一般用各种ai改之后会先放在这里坏掉不影响主服务器 |
| `/access` | 密码验证页面 | |
| `/setpass` | 密码设置页面 | |
| `/manage` | 管理面板 | 需管理员密码 |

### 4.2 控制服务

**需要管理员密码（`?p=<password>`）：**

| 路由 | 功能 |
|------|------|
| `/start` | 开启对外服务 |
| `/exit` | 暂停对外服务，并将所有请求重定向到https，即443端口，如果你没有运行什么东西，那默认就是Connection refused |
| `/restart` | **重启整台电脑** |
| `/changeip/<mode>` | 添加/移除 IP 白名单（mode=`add`/`remove`，参数 `ip`、`username`） |
| `/changevip/<mode>` | 设置/取消 VIP（mode=`add`/`remove`，参数 `username`）<br> vip用于ai的思考与搜索鉴权 |

**无需密码（但需 IP 在白名单中且 serverStatus=1）：**

| 路由 | 功能 |
|------|------|
| `/clean` | 清理下载文件夹 |
| `/cmd/<cmdstr>` | 执行 CMD 命令，注意反斜线要换成%5C，其他的特殊符号也要注意 |
| `/view/<path>` | 读取文件内容，换行替换为 `<br>`后返回 |
| `/contact/<text>` | 向服务器发送文本，存于根目录 `contact.txt` |
| `/loadips` | 重新加载 `userlist.txt` |

**特别注意，以下两个由于安全原因，谁都可以执行，以避免手边没有已认证设备的困境：**
| 路由 | 功能 |
|------|------|
| `/stop` | **关闭电脑** |
| `/end` | 停止服务器程序 |

### 4.3 文件服务

| 路由 | 功能 |
|------|------|
| `/files/<path>` | 下载文件（HTTP Range 支持，可配合 MX Player 串流） |
| `/pics/<filename>` | 聊天加密图片（实时 XOR 解密输出），支持 `?key=` 参数，若未指定回落到默认密钥`default` |
| `/res/<path>` | 静态资源文件（JS、CSS 等），映射到 `./res/` 目录 |
| `/read` | 读取文件内容，参数 `?name=README.md` |
| `/save` | 保存文件内容，POST JSON `{content}` + 参数 `?name=README.md` |

### 4.4 AI 对话 API

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/get` | POST | AI 对话（流式输出） |
| `/api/history/<id>` | GET | 获取对话历史 |
| `/api/history/update` | POST | 编辑/删除/重试历史消息 |
| `/api/getmoney` | GET | 查询用户累计花费 |
| `/ai/ocr` | POST | OCR 图片文字识别 |
| `/api/manage/ai-can-use` | GET | 查询当前用户 AI 是否可用（前台轮询用） |

**`/api/get` POST 参数（JSON body）：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user` | string | ✅ | 用户输入 |
| `hisid` | string | ❌ | 对话历史 ID。以 `_t_` 开头为临时对话，否则续写已有对话或创建新对话 |
| `model` | string | ❌ | `deepseek-v4-flash`（默认）/ `deepseek-v4-pro` |
| `search` | bool | ❌ | 是否启用联网搜索（需 VIP） |
| `temp` | number | ❌ | 温度参数，默认 0.7 |
| `system` | string | ❌ | 系统提示词 |
| `use_think` | string | ❌ | 思考模式：`"enabled"`（需vip） / `"disabled"`（默认） |

**对话流程：**
1. 检查每日 AI 使用次数是否超限
2. 若开启了陪伴模式，在用户消息前注入上下文（当前时间、课程状态、麦克风转录、距上下课时间等）
3. 流式请求 DeepSeek API，附带工具定义（记忆读写、联网搜索、课堂语音查询/搜索、日期获取）
4. 遇到 tool call 本地执行后继续循环（最多 20 轮）
5. 保存对话历史到 `logs/<hisid>'smemory.log`，累计费用写入 `logs/moneys.json`

### 4.5 聊天 API

#### WebSocket（主要方式）

通过 **Flask-SocketIO** 实现实时通信。

**客户端事件：**

| 事件 | 数据 | 说明 |
|------|------|------|
| `join` | `{target, key?, group_key?}` | 加入聊天频道 |
| `leave` | `{target}` | 离开频道 |
| `send_message` | `{content, target, key?, quote?}` | 发送消息 |
| `upload_image` | `{data, filename, target, key?, quote?}` | 上传图片（base64）并发送 |
| `delete_message` | `{target, message_id, key?}` | 撤回消息（2分钟内） |
| `create_group` | `{name, access_key?}` | 创建群聊（不提供密钥则自动生成6位数字） |

**服务端事件：**

| 事件 | 说明 |
|------|------|
| `connected` | 连接成功，返回用户名 |
| `joined` | 已加入频道 |
| `new_Message` | 新消息广播 |
| `message_history` | 频道历史消息 |
| `message_deleted` | 消息被撤回 |
| `message_sent` | 消息发送确认 |
| `other_new_message` | 未读通知（私聊/群聊，支持离线积压投递） |

#### HTTP 轮询（备用）

| 路由 | 方法 | 功能 |
|------|------|------|
| `/message` | GET | 读取消息（参数 `targetuser`、`key`） |
| `/sendmsg` | GET | 发送消息（参数 `targetuser`、`content`、`key`） |
| `/announce` | GET | 发布（带 `content` 参数）/ 获取公告 |
| `/group/create` | GET | 创建群聊（参数 `name`、`access_key`） |
| `/group/join` | GET | 加入群聊（参数 `group_name`、`access_key`） |
| `/group/list` | GET | 获取用户所在群聊列表 |
| `/group/info` | GET | 获取群聊详情（参数 `group_name`） |

**`targetuser` 说明：**

| 取值 | 行为 |
|------|------|
| 空 | 公共聊天（所有人可见） |
| 用户名 | 一对一私聊 |
| `@`+群聊名称 | 群聊 |

### 4.6 陪伴模式 API

| 路由 | 方法 | 功能 |
|------|------|------|
| `/companion/config` | GET | 获取当前用户的陪伴模式配置 |
| `/companion/config` | POST | 保存陪伴模式配置（JSON body） |
| `/companion/memory` | GET | 获取对话的 AI 记忆内容，参数 `?hisid=` |
| `/companion/memory` | POST | 覆盖保存 AI 记忆，JSON `{content}` + 参数 `?hisid=` |
| `/api/temp_chat/clear` | GET | 清空当前用户的临时对话历史 |

**陪伴模式配置项：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `companion_enabled` | bool | `false` | 是否启用陪伴模式 |
| `user_status` | string | `"在学习"` | 用户当前状态 |
| `week_schedule` | object | 建议课表 | 周课表，按 `monday`~`sunday` 组织 |
| `mic2text_show_in_chat` | bool | `false` | 是否在聊天中显示音频转录 |
| `mic2text_in_context` | bool | `true` | 是否将音频转录注入 AI 上下文 |
| `show_time_elapsed` | bool | `false` | 是否显示距上次对话的时间 |
| `temp_chat_enabled` | bool | `true` | 是否允许临时对话 |

### 4.7 课堂语音查询 API

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/mic2text` | GET | 获取最近 N 句教室音频转录（参数 `n`） |
| `/api/mic2text/query_records` | GET | 按课程查询语音记录（参数 `course`、`weekday`、`date`、`start`、`end`） |
| `/api/mic2text/search` | GET/POST | 关键词搜索课堂语音（参数 `keyword`、`course`、`weekday`、`date` 等） |

### 4.8 邮件服务

| 路由 | 功能 |
|------|------|
| `/checkmail` | 手动触发邮件检查 |

服务器**每日首次启动**时自动检查邮箱，下载标题含 `To Server:` 的邮件附件到 `downloaded/mail/`。基于 IMAP UID + 文件内容 SHA256 指纹去重，同一附件不会重复下载。

### 4.9 用户鉴权

| 路由 | 方法 | 功能 |
|------|------|------|
| `/ispass` | GET | 查询当前 IP 是否设置了跳转密码，access和faq调用，若未设置则直接跳转jump |
| `/api/verifypass` | POST | 验证跳转密码（JSON `{password}`，由于客户端不支持加密故采用明文传输，但服务端只存储sha256），返回 `{isRight: bool}` |
| `/api/setpass` | POST | 设置/修改跳转密码（JSON `{password}`），服务端计算 SHA-256 存储 |
| `/getname` | GET | 获取当前 IP 对应的用户名 |

### 4.10 管理面板 API

管理面板页面：`/manage`（需 `?p=<password>`）

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/manage/config` | GET | 获取所有配置概览 |
| `/api/manage/users` | GET | 获取用户列表 |
| `/api/manage/users` | PUT | 添加/更新用户 |
| `/api/manage/users` | DELETE | 删除用户 |
| `/api/manage/server` | GET | 获取服务器状态 |
| `/api/manage/server` | POST | 设置服务器状态（`{status: 0\|1}`） |
| `/api/manage/password` | POST | 修改管理员密码（`{new_password}`）不建议使用，密码明文存储在本地 |
| `/api/manage/money` | GET | 获取用钱数据 |
| `/api/manage/money` | POST | 更新用户花费 |
| `/api/manage/vip` | POST | 切换 VIP 状态 |
| `/api/manage/features` | GET | 获取功能开关 |
| `/api/manage/features` | POST | 设置功能开关 |
| `/api/manage/schedule` | GET | 获取上课课表（含默认+备用） |
| `/api/manage/schedule` | POST | 设置上课课表及切换激活项 |
| `/api/manage/access-log` | GET | 获取访问记录（分页+排序） |
| `/api/manage/ai-history` | GET | 获取 AI 历史列表（分页+排序） |
| `/api/manage/daily-usage` | GET | 获取每日 AI 使用统计 |
| `/api/manage/daily-usage` | POST | 修改某用户当日使用次数 |
| `/api/manage/daily-usage/reset` | POST | 重置使用次数（可指定用户或全量） |
| `/api/manage/save-limit` | POST | 修改每日 AI 限制次数 |
| `/api/manage/week-schedules` | GET | 获取所有用户的周课表配置 |
| `/api/manage/week-schedules/apply-default` | POST | 将建议课表应用到用户 |

**功能开关列表：**

| 开关名 | 标签 | 默认值 | 说明 |
|--------|------|--------|------|
| `ai` | AI 对话 | `true` | 控制 AI 功能是否可用 |
| `talk` | 局域网聊天 | `true` | 控制聊天功能是否可用 |
| `music` | 音乐播放 | `true` | 控制音乐功能是否可用 |
| `games` | 小游戏 | `true` | 控制游戏功能是否可用 |
| `file_sharing` | 文件串流 | `true` | 控制文件下载功能是否可用 |
| `game_class_ban` | 上课禁用游戏 | `true` | 上课时间是否自动屏蔽游戏 |
| `ai_daily_limit` | AI 每日限制 | `true` | 是否启用每日 AI 次数限制 |
| `guest_access` | 访客访问 | `false` | 是否允许未登录用户访问 |

### 4.11 其他路由

| 路由 | 功能 |
|------|------|
| `/showuser` | 显示当前 userlist 内容（调试用） |
| `/ptt/<num>/<score>` | Arcaea PTT 计算器 |
| `/lisssssst` | 列出所有 AI 对话日志，支持删除/标记 |
| `/kill` | 彩蛋：死亡页面 |
| `/respawn` | 彩蛋：重生失败 |
| `/tp` | 彩蛋：无权限提示 |

---

## 5. 配置指南

### 5.1 修改监听端口

编辑 `Server.py` 末尾：

```python
socketio.run(
    app,
    host="0.0.0.0",
    port=80,            # ← 改为你想要的端口
    debug=True,
)
```

### 5.2 用户白名单管理

**静态配置** — 编辑 `userlist.txt`：

```
127.0.0.1:admin
192.168.40.114:blip_blop
192.168.40.114:blip_blop:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

格式：`IP:用户名[:sha256密码哈希]`。密码哈希用于 `/faq` 入口的跳转密码验证，服务端自动计算 SHA-256。

**动态管理** — 通过 API 或管理面板：

```
http://<server>/changeip/add?p=<password>&ip=192.168.40.114&username=blip_blop
http://<server>/changeip/remove?p=<password>&ip=192.168.40.114
```

### 5.3 加密体系

项目中涉及两种加密：

- **Base58 编码**（`encode.py` / `decode.py` / `base_tools.py`）：用于混淆 `config.py` 中的静态密钥（API Key、密码、IMAP 凭据）。不是真正的加密，仅防止一眼看到明文。
- **XOR 加密**（`tools.py` → `FastXORCipher`）：用于聊天消息文件（`messages/`）和聊天图片（`pics/`）的存盘加密。密钥可自定义，默认为 `'default'`。

### 5.4 上课时间限制

游戏页面（`/xkl`）在上课时间自动屏蔽（效果同exit）。在 `config.py` 中维护两套课表：

- `forbidden_time` — 默认课表
- `forbidden_time1` — 备用课表

```python
forbidden_time = ThreadSafeGlobal({
    "07:28:00": "08:40:00",   # 格式：开始时间→结束时间
    "08:50:00": "09:30:00",
    # ...
})
```

当前生效的课表由 `logs/server_config.json` 中的 `schedule_active` 字段决定（`"default"` 或 `"backup"`），可通过管理面板切换。

此外，`config.py` 中的 `DEFAULT_WEEK_SCHEDULE` 定义了更详细的周课表（含课程名称、早晚修等），用于陪伴模式的课程上下文注入和课堂语音按课程查询。

### 5.5 音乐服务

音乐功能依赖 `LocalServerKt-1.0.jar`（Kotlin 编写的 Ktor 后端）。首次访问 `/music` 时会先探测 `192.168.40.114:1919/started`，若不可达则自动执行 `java -jar` 启动。

---

## 6. 项目结构

```
lcsv/
├── Server.py                      # Flask 主入口，路由注册、SocketIO 初始化
├── config.py                      # 全局配置、密钥解码、ThreadSafeGlobal 实例、目录初始化、课表定义
├── base_tools.py                  # 基础工具：decoder()、ThreadSafeGlobal、_parse_userlist_line()
├── tools.py                       # 工具库：认证装饰器、FastXORCipher、文件锁、track_visit()、change_userlist()
├── ai.py                          # AI 对话（DeepSeek 流式 API + tool calling）+ 陪伴模式 + OCR
├── talk.py                        # 局域网聊天 HTTP 轮询版 + 群聊 CRUD
├── websocket_talk.py              # WebSocket 实时聊天（Flask-SocketIO）+ 图片上传 + 离线通知
├── mail_service.py                # 邮件服务（IMAP 附件下载，指纹去重）
├── ControlService.py              # 控制功能（启动/停止/重启/关机/CMD/清理）
├── WebsiteService.py              # 页面路由（入口/音乐/游戏/密码验证/文件服务）
├── ManageService.py               # 管理面板后端 API + AI 每日限额追踪
├── encode.py                      # Base58 编码工具
├── decode.py                      # Base58 解码工具
├── LocalServerKt-1.0.jar          # Ktor 音乐服务后端（Kotlin）
├── userlist.txt                   # IP→用户名→密码哈希 映射
├── .gitignore
├── LICENSE
├── README.md
├── res/                           # 前端静态资源
│   ├── WebPages/                  #   HTML 页面
│   │   ├── ai.html                #   AI 对话页面
│   │   ├── talk.html              #   聊天页面
│   │   ├── access.html            #   密码验证/入口页面
│   │   ├── setpass.html           #   密码设置页面
│   │   ├── browser.html           #   跳转链接输入页
│   │   ├── music.html             #   音乐页面（旧版）
│   │   ├── tomusic.html           #   音乐页面
│   │   ├── xkl.html               #   Dino 小游戏
│   │   ├── render.html            #   LaTeX/Markdown 渲染
│   │   ├── suggest.html           #   建议提交页面
│   │   ├── split.html             #   分屏页面
│   │   ├── manage.html            #   管理面板
│   │   └── help.txt               #   帮助文本
│   ├── ai.css                     #   AI 页面样式
│   ├── socket.js                  #   WebSocket 客户端 JS
│   ├── markdown-it.js             #   Markdown 渲染
│   └── mathjax.js                 #   LaTeX 渲染
├── downloaded/                    # 文件下载目录（自动创建）
│   ├── local/                     #   本地文件
│   ├── net/                       #   网络下载（含 bili、wyy、qq 子目录）
│   └── mail/                      #   邮件附件
├── logs/                          # 日志与数据目录
│   ├── <id>'smemory.log           #   AI 对话历史（JSON 数组）
│   ├── moneys.json                #   用户 AI 花费及 VIP 状态
│   ├── server_config.json         #   统一配置（功能开关、课表选择、AI 限额）
│   ├── daily_ai_usage.json        #   每日 AI 使用次数统计
│   ├── companion_configs.json     #   每用户陪伴模式配置
│   ├── companion_memory/          #   AI 长期记忆文件（Markdown）
│   ├── temp_chat/                 #   临时对话历史
│   ├── access_visits.json         #   访问记录
│   ├── suggestions.json           #   用户建议
│   ├── mail_last_check.txt        #   上次邮件检查日期
│   └── local.log                  #   文件传输日志
├── messages/                      # 聊天消息文件（XOR 加密存盘）
│   ├── groups.json                #   群聊配置（明文 JSON）
│   ├── pending_notifications.json #   离线通知积压
│   └── msg*.json                  #   各频道消息文件
└── pics/                          # 聊天分享的图片（XOR 加密存盘）
```

---

## 7. 注意事项

1. **端口**：默认使用端口 `80`
2. **文件管理**：
   - AI 对话历史存储在 `logs/<ID>'smemory.log`，JSON 数组格式
   - 聊天消息存储在 `messages/`，XOR 加密。文件名规则：`msg公共频道.json`、`msg用户A_用户B.json`（私聊，字母序）、`msg_group_群名.json`

---

## 8. 作者的话

这个项目由我和 [@sti-233](https://github.com/sti-233) 在无数个午休和晚自习时间和周末回家时间，在教室希沃一体机上和自己电脑上编写与测试，最终达到现在的效果。

我们技术力有限，有哪里不对的，欢迎提 PR 与 Issue。😄

*—— Foundchair Done*

---

## 9. 致谢

- [LocalServerKt](https://github.com/sti-233/LocalServerKt/) — 音乐服务 Kotlin 后端
- [Flask](https://github.com/pallets/flask) — Python Web 框架
- [Flask-SocketIO](https://github.com/miguelgrinberg/Flask-SocketIO) — WebSocket 支持

---

*最后更新：2026-08-01 by Foundchair Done*
