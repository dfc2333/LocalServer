import os
from config import deepseek_api_key_encoded, log_dir, pages_dir, date, res_dir, message_dir
from flask import send_from_directory, request, jsonify
from tools import decoder, WSAvaliable as avaliable, isVIP
import json,requests,datetime

def Browser():
    return avaliable('browser.html')


def dsb():
    return avaliable('dsb.jpeg')


def ai():
    return avaliable('ai.html')

def execute_web_search(query, max_results=5):
    """执行实际的联网搜索"""
    result=[]
    try:
        payload = json.dumps({
        "query": query,
        "summary": True,
        "count": 10
        })
        headers = {
        'Content-Type': 'application/json'
        }

        response = requests.request("POST", 'https://api.bocha.cn/v1/ai-search', headers=headers, data=payload)
        response = response.json()
        print(response)
        search_results = response['messages']
        for i in search_results:
            if i['type']=='answer':
                return i['content']
        return 'nth searched'
    except Exception as e:
            print(e)
            return f"搜索时出错: {str(e)}"

def getaiapi():
    user = str(request.args.get('user'))
    hisid = request.args.get('hisid')
    modelName = str(request.args.get('model')) if request.args.get('model') else 'deepseek-chat'
    username = str(request.args.get('username')) if request.args.get('username') else 'guest'
    result=''
    content=''
    # 添加工具调用相关参数
    use_search = request.args.get('search', 'false').lower() == 'true'
    max_search_results = int(request.args.get('max_results', 5))

    if not username:
        return "No username provided"
    if isVIP(username)==False and modelName=='deepseek-reasoner':
        return "思考的话太烧钱了，需要你赞助一点点啦~"
    
    # 加载历史记录
    history = []
    history_file = None
    if hisid:
        history_file = os.path.join(log_dir, f"{hisid}'smemory.log")
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                content = f.read()
                history = json.loads(content) if content else []
                if request.args.get("system"):
                    history.insert(0, {"role": "system", "content": str(request.args.get("system"))})
        else:
                history = [{"role": "system", "content": str(request.args.get("system"))}] if request.args.get("system") else []
    else:
        history = [{"role": "system", "content": str(request.args.get("system"))}] if request.args.get("system") else []

    # 添加当前用户输入到历史记录
    history.append({"role": "user", "content": user})
    
    # 准备用于API调用的消息列表（可能包含工具调用中间步骤）
    api_messages = history.copy()
    
    # 定义联网搜索工具
    search_tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "使用联网搜索功能获取最新信息。当用户询问需要最新数据、新闻、实时信息或网络搜索相关内容时使用此功能。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询关键词，要具体明确"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "最多返回的结果数量",
                            "minimum": 1,
                            "maximum": 10
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                },
                "strict": False
            }
        }
    ]
    
    # 实际执行搜索的函数
    
    
    # 设置是否使用工具
    tools = search_tools if use_search else None
    tool_choice = "auto" if use_search else "none"
    
    # 处理工具调用的循环
    max_iterations = 5  # 防止无限循环
    total_cost = 0
    
    for iteration in range(max_iterations):
        print("reached loop 1")
        # 准备API请求数据
        api_data = {
            "model": modelName,
            "messages": api_messages,
            "stream": False,
            "temperature": float(str(request.args.get("temp"))) if request.args.get("temp") else 1.3
        }
        
        # 只在有工具时才添加tools和tool_choice参数
        if tools:
            api_data["tools"] = tools
            api_data["tool_choice"] = tool_choice
        
        # 调用AI接口

        with requests.post(
            url='https://api.deepseek.com/chat/completions',
            headers={
                "Authorization": f"Bearer {decoder(deepseek_api_key_encoded)}",
                "Content-Type": "application/json"
            },
            data=json.dumps(api_data)
        ) as req:
            print("reached loop 2")
            # 获取AI回复
            response = json.loads(req.content.decode())
            message = response['choices'][0]['message']
            print(message)
            
            # 计算本次调用的费用
            cost = (response.get('usage', {}).get('completion_tokens', 0) / 1000000 * 3 
                  + response.get('usage', {}).get('prompt_cache_hit_tokens', 0) / 1000000 * 0.2 
                  + response.get('usage', {}).get('prompt_cache_miss_tokens', 0) / 1000000 * 2)
            total_cost += cost
            
            # 检查是否有工具调用
            if message.get('tool_calls', None):
                print("tool calls")
                # 添加AI的工具调用请求到api_messages（不保存到历史记录）
                api_messages.append(message)
                
                # 处理每个工具调用
                for tool_call in message['tool_calls']:
                    if tool_call['function']['name'] == "web_search":
                        # 解析参数
                        args = json.loads(tool_call['function']['arguments'])
                        query = args.get("query", "")
                        max_results = args.get("max_results", max_search_results)
                        
                        # 执行搜索
                        search_result = execute_web_search(query, max_results)
                        print(search_result)
                        # 将工具调用结果添加到api_messages（不保存到历史记录）
                        api_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call['id'],
                            "content": search_result,
                        })  # 继续循环，让AI处理搜索结果
            else:
                # 如果没有工具调用，处理最终回复
                print("no tool calls")
                reasoning=''
                api_messages.append(message)
                print(api_messages)
                for i in api_messages:
                    if i.get('role','')=='assistant':
                        content+=i.get('content','') if i.get('content','') else ''
                        reasoning+=i.get('reasoning_content','') if i.get('reasoning_content','') else ''

                if reasoning:
                    result = f'<strong>思考：</strong>\n<i>{reasoning}</i>\n<strong>回答：</strong>\n{content}'
                else:
                    result = content
                
            # 注意：这里我们只将最终的assistant回复保存到历史记录
            # 不保存工具调用相关的消息
                history.append({"role": "assistant", "content": content})
            
            # 保存更新后的历史记录（不包含工具调用信息）
                if hisid and history_file:
                    with open(history_file, 'w', encoding='utf-8') as f:
                        f.write(json.dumps(history, ensure_ascii=False))
            
                break  # 退出工具调用循环
    
    # 更新费用记录
    money_file = os.path.join(log_dir, "moneys.log")
    try:
        with open(money_file, 'r', encoding='utf-8') as f:
            data = json.loads(f.read())
    except FileNotFoundError:
        data = {}
    
    if username not in data:
        data[username] = {"money": 0, "isVIP": False}
    
    data[username]['money'] += total_cost
    
    with open(money_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False))

    return result if result else "No response from AI"


# 可选：添加独立的搜索函数供其他用途使用
def web_search_api():
    """独立的搜索API端点"""
    query = request.args.get('query', '')
    max_results = int(request.args.get('max_results', 3))
    
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    try:
        # 这里实现实际的搜索逻辑
        # search_results = your_search_api(query, max_results)
        
        # 模拟返回
        search_results = [
            {"title": f"关于 {query} 的结果1", "snippet": "这是搜索结果1的摘要..."},
            {"title": f"关于 {query} 的结果2", "snippet": "这是搜索结果2的摘要..."},
            {"title": f"关于 {query} 的结果3", "snippet": "这是搜索结果3的摘要..."}
        ]
        
        return jsonify({"query": query, "results": search_results[:max_results]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def gethistory(id):
    with open(os.path.join(log_dir,f'{id}\'smemory.log'),'r',encoding='utf-8') as file:
        content=file.read()
        print(content)
        if not content: return '{"content":"ID Not Found"}'
        return content

def getMoney():
    username = str(request.args.get('username'))
    if not username:
        return "No username provided"
    money_file = os.path.join(log_dir, f"moneys.log")
    try:
        with open(money_file, 'r', encoding='utf-8') as f:
            user_data = json.loads(f.read())[username]
            if user_data['isVIP']:
                result = f'尊敬的{username}，你已经花了￥{user_data["money"]}'
            else:
                result = '你花了￥' + str(user_data["money"])
            return result
    except FileNotFoundError:
        return "0"

def sendres(file):
    print(os.path.join(res_dir, os.path.dirname(file)), os.path.basename(file))
    return send_from_directory(os.path.join(res_dir, os.path.dirname(file)), os.path.basename(file))


def render():
    return send_from_directory(pages_dir,'render.html')

def read_message():
    global date
    targetFile=''
    targetuser=str(request.args.get('targetuser'))
    user=str(request.args.get('username'))
    if not targetuser:
        targetFile=f'msg{date}.json'
    else:
        for i in os.scandir(message_dir):
            if (targetuser in i.name)and(user in i.name):
                targetFile=i.name
                break
        if not targetFile:
            targetFile=f'msg{user+"_"+targetuser}.json'

    try:
        with open(os.path.join(message_dir,targetFile),'r',encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        with open(os.path.join(message_dir,targetFile),'w',encoding='utf-8') as file:
            time = str(datetime.datetime.now())
            file.write('{"content":[{"sender":"system","time":"none","content":"Newfilecreated'+time+'"}]}')
        return '{"content":[{"sender":"system","time":"none","content":"Newfilecreated'+time+'"}]}'


def send_msg():
        global date
        sender=str(request.args.get('sender'))
        content=str(request.args.get('content'))
        targetuser=str(request.args.get('targetuser'))
        targetFile=''
        if not targetuser:
            targetFile=f'msg{date}.json'
        else:
            for i in os.scandir(message_dir):
                if (targetuser in i.name)and(sender in i.name):
                    targetFile=i.name
                    break
            if not targetFile:
                targetFile=f'msg{sender+"_"+targetuser}.json'
        with open(os.path.join(message_dir,targetFile),'r',encoding='utf-8') as f:
            file=json.loads(f.read())
        with open(os.path.join(message_dir,targetFile),'w',encoding='utf-8') as f:
            for key,value in {'sender':sender,'time':str(datetime.datetime.now())[-15:-7],'content':content}.items():
                file['content'].append(dict())
                file['content'][-1][key]=value
            f.write(json.dumps(file,ensure_ascii=False))
        return 'ok'


def announce():
    ctnt= request.args.get('content')
    if ctnt:
        with open(os.path.join(message_dir,'announcement.data'),'w',encoding='utf-8') as f:
            f.write(ctnt)
    else:
        with open(os.path.join(message_dir,'announcement.data'),'r',encoding='utf-8') as f:
            return f.read()


def login():
    return avaliable('login.html')


def talker():
    return avaliable('talk.html')