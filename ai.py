import json
import os
import datetime
import requests
from bs4 import BeautifulSoup
from config import *
from tools import (
    WSAvaliable as avaliable,
    OnlyAvailable,
    GameAvaliable,
    VAAvaliable,
    userlist,
    change_userlist,
    isVIP
)

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
        'Content-Type': 'application/json',
        "Authorization": "Bearer sk-sth"
        }

        response = requests.request("POST", 'https://api.bocha.cn/v1/web-search', headers=headers, data=payload)
        try:
            result=json.loads(response.content.decode())
            searchResult=result['data']['webPages']['value'][:10]
            print(searchResult)
        except:
            return 'error'
        if searchResult:
            return str(searchResult)
        return 'nth searched'
    except Exception as e:
            print(e)
            return f"搜索时出错: {str(e)}"
    return '搜索暂不可用'

def open_link(link):
  try:
    with requests.get(link,headers=headers) as req:
        soup=BeautifulSoup(req.content.decode(),'html.parser')
        body = soup.body
        if not body:
            return '网页里没有内容'
        for tag in body(['script','style']):
            tag.decompose()
        text=body.get_text()

        return text
  except requests.exceptions.InvalidURL:
      print(link)
      return "格式不正确，请输入url！"
  except BaseException as e:
      print(link, e)
      return "出现未知错误"+str(e)

def getaiapi():
    user = str(request.args.get('user'))
    hisid = request.args.get('hisid')
    modelName = str(request.args.get('model')) if request.args.get('model') else 'deepseek-chat'
    username = userlist.get(str(request.remote_addr),None)
    result=''
    content1=''
    # 添加工具调用相关参数
    use_search = request.args.get('search', 'false').lower() == 'true'
    max_search_results = int(request.args.get('max_results', 10))

    if not username:
        return "No username provided"
    if isVIP(username)==False and (modelName=='deepseek-reasoner' or use_search == True):
        return "思考和搜索的话太烧钱了，需要你赞助一点点啦~"
    
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
    new_message=[]
    
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
        },
        {
            "type": "function",
            "function": {
                "name": "open_link",
                "description": "使用打开链接功能获取链接中网页的body内容以便更好的获取搜索内容，对部分链接不适用，不需要重复尝试打开同一链接。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "link": {
                            "type": "string",
                            "description": "链接URL，要完整，从http或者https开始。"
                        }
                    },
                    "required": ["link"],
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
    max_iterations = 20  # 防止无限循环
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
        print(api_data)
        
        # 只在有工具时才添加tools和tool_choice参数
        if tools:
            api_data["tools"] = tools
            api_data["tool_choice"] = tool_choice
        
        # 调用AI接口

        with requests.post(
            url='https://api.deepseek.com/chat/completions',
            headers={
                "Authorization": f"Bearer {deepseek_api_key}",
                "Content-Type": "application/json"
            },
            data=json.dumps(api_data)
        ) as req:
            print(api_data)
            print("reached loop 2",req.content)
            # 获取AI回复
            response = json.loads(req.content.decode())
            print('response:',response)
            message = response['choices'][0]['message']
            print("message:",message)
            
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
                new_message.append(message)
                print('message in tool',message)
                
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
                        }
                        )
                        # 继续循环，让AI处理搜索结果
                    elif tool_call['function']['name'] == "open_link":
                        # 解析参数
                        args = json.loads(tool_call['function']['arguments'])
                        link = args.get("link", "")
                        
                        # 执行dakai
                        open_result = open_link(link)
                        print(open_result)
                        # 将工具调用结果添加到api_messages（不保存到历史记录）
                        api_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call['id'],
                            "content": open_result,
                        })  # 继续循环，让AI处理搜索结果
            else:
                # 如果没有工具调用，处理最终回复
                print("no tool calls")
                reasoning=''
                api_messages.append(message)
                new_message.append(message)
                print('endmessage:',message)
                print('apimessages',api_messages)
                print('new_message:',new_message)
                for i in new_message:
                    if i.get('role','')=='assistant':
                        content1+=i.get('content','')
                        reasoning+=i.get('reasoning_content','') if i.get('reasoning_content','') else ''

                if reasoning:
                    result = f'## 思考：\n * {reasoning} * \n ## 回答：\n{content1}'
                else:
                    result = content1
                print('result:',result)
            # 注意：这里我们只将最终的assistant回复保存到历史记录
            # 不保存工具调用相关的消息
                history.append({"role": "assistant", "content": content1})
            
            # 保存更新后的历史记录（不包含工具调用信息）
                if hisid and history_file:
                    with open(history_file, 'w', encoding='utf-8') as f:
                        f.write(json.dumps(history, ensure_ascii=False))
            
    
    
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
    return 'Maximum tool calls reached. AI won\'t return a useful result.'


def gethistory(id):
    with open(os.path.join(log_dir,f'{id}\'smemory.log'),'r',encoding='utf-8') as file:
        content=file.read()
        print(content)
        if not content: return '{"content":"ID Not Found"}'
        return content

def getMoney():
    username = userlist.get(str(request.remote_addr),None)
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