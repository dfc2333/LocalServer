import json
import os
import datetime
import requests
from bs4 import BeautifulSoup
from config import *
from flask import request,Response,stream_with_context
from tools import (
    WSAvailable as available,
    userlist,
    isVIP
)

def ai():
    return available('ai.html')

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
    return '广州今天天气不太好，很闷热'
def getaiapi():
    data = request.get_json()
    ip=request.remote_addr
    user = data.get('user', '')
    hisid = data.get('hisid', '')
    modelName = data.get('model', '') if data.get('model', '') else 'deepseek-chat'
    username = userlist.get(str(ip), '')
    use_search = data.get('search', 'false') == True
    max_search_results = int(data.get('max_results', 10))
    # 验证API Key和用户权限
    if not deepseek_api_key:
        return "你还没设置apikey呢。。"
    if not username:
        return "No username provided"
    if not isVIP(username) and (modelName == 'deepseek-reasoner' or use_search):
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
                if data.get("system") and history[0]['role'] != 'system':
                    history.insert(0, {"role": "system", "content": str(data.get("system"))})
        else:
            history = [{"role": "system", "content": str(data.get("system"))}] if data.get("system") else []
    else:
        history = [{"role": "system", "content": str(data.get("system"))}] if data.get("system") else []

    # 添加用户输入
    history.append({"role": "user", "content": user})

    # 准备工具定义
    search_tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "使用联网搜索功能获取最新信息。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索查询关键词"},
                        "max_results": {"type": "integer", "description": "最多返回的结果数量", "minimum": 1, "maximum": 10}
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
                "description": "打开链接获取网页body内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "link": {"type": "string", "description": "完整URL"}
                    },
                    "required": ["link"],
                    "additionalProperties": False
                },
                "strict": False
            }
        }
    ]
    tools = search_tools if use_search else None
    tool_choice = "auto" if use_search else "none"

    max_iterations = 20
    total_cost = 0
    api_messages = history.copy()  # 用于工具调用循环的消息列表

    # 流式生成器
    def generate():
        nonlocal total_cost
        accumulated_content=''
        accumulated_reasoning=''
        try:
            for iteration in range(max_iterations):
                # 构建请求
                print('reached loop 1')
                api_data = {
                    "model": modelName,
                    "messages": api_messages,
                    "stream": True,  # 启用流式
                    "temperature": float(str(data.get("temp"))) if data.get("temp") else 1.3
                }
                if tools:
                    api_data["tools"] = tools
                    api_data["tool_choice"] = tool_choice

                # 发起流式请求    
                with requests.post(
                        url='https://api.deepseek.com/chat/completions',
                        headers={
                            "Authorization": f"Bearer {deepseek_api_key}",
                            "Content-Type": "application/json"
                        },
                        data=json.dumps(api_data),
                        stream=True
                    ) as req:
                        print('started req')
                        if req.status_code != 200:
                            yield f"请求失败，状态码: {req.status_code}"
                            return

                        # 流式解析变量
                        accumulated_content = ""      # 累积assistant文本
                        accumulated_reasoning = ""    # 累积思考内容（reasoner模型）
                        tool_calls = {}               # {index: {id, name, arguments}}
                        usage = None                  # 最后可能包含usage

                        for line in req.iter_lines(decode_unicode=True):
                            if not line:
                                continue
                            if line.startswith('data: '):
                                data_str = line[6:]
                                if data_str == '[DONE]':
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                except json.JSONDecodeError:
                                    continue

                                # 提取usage（通常在最后一条）
                                if 'usage' in chunk:
                                    usage = chunk['usage']

                                delta = chunk.get('choices', [{}])[0].get('delta', {})

                                # 普通文本内容
                                if 'content' in delta and delta['content']:
                                    text = delta['content']
                                    accumulated_content += text
                                    yield text   # 实时发送给前端

                                # 思考内容（deepseek-reasoner）
                                if 'reasoning_content' in delta and delta['reasoning_content']:
                                    reasoning = delta['reasoning_content']
                                    accumulated_reasoning += reasoning
                                    yield reasoning   # 前端会追加显示

                                # 工具调用增量
                                if 'tool_calls' in delta:
                                    print('tool call detected')
                                    for tc in delta['tool_calls']:
                                        idx = tc.get('index', 0)
                                        if idx not in tool_calls:
                                            tool_calls[idx] = {'id': None, 'name': None, 'arguments': ''}
                                        if 'id' in tc:
                                            tool_calls[idx]['id'] = tc['id']
                                        if 'function' in tc:
                                            if 'name' in tc['function']:
                                                tool_calls[idx]['name'] = tc['function']['name']
                                            if 'arguments' in tc['function']:
                                                tool_calls[idx]['arguments'] += tc['function']['arguments']

                        # 处理费用
                        if usage:
                            cost = (usage.get('completion_tokens', 0) / 1000000 * 3
                                    + usage.get('prompt_cache_hit_tokens', 0) / 1000000 * 0.2
                                    + usage.get('prompt_cache_miss_tokens', 0) / 1000000 * 2)
                            total_cost += cost

                        # 如果有工具调用
                        if tool_calls:
                            print('tool calls')
                            # 构建assistant消息（含工具调用）
                            assistant_message = {
                                "role": "assistant",
                                "content": accumulated_content or None,
                                "tool_calls": []
                            }
                            for idx in sorted(tool_calls.keys()):
                                tc = tool_calls[idx]
                                assistant_message["tool_calls"].append({
                                    "id": tc['id'],
                                    "type": "function",
                                    "function": {
                                        "name": tc['name'],
                                        "arguments": tc['arguments']
                                    }
                                })
                            api_messages.append(assistant_message)

                            # 处理每个工具调用
                            for idx in sorted(tool_calls.keys()):
                                tc = tool_calls[idx]
                                args = json.loads(tc['arguments'])
                                if tc['name'] == 'web_search':
                                    query = args.get('query', '')
                                    max_results = args.get('max_results', max_search_results)
                                    yield f"\n🔍 正在搜索：{query}...\n"
                                    search_result = execute_web_search(query, max_results)
                                    yield f"\n✅ 搜索结果已获取\n"
                                    api_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc['id'],
                                        "content": search_result
                                    })
                                elif tc['name'] == 'open_link':
                                    link = args.get('link', '')
                                    yield f"\n🔗 正在打开链接：{link}...\n"
                                    open_result = open_link(link)
                                    yield f"\n✅ 链接内容已获取\n"
                                    api_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc['id'],
                                        "content": open_result
                                    })
                            # 继续下一轮循环，让AI处理工具结果
                            print('continue')
                            continue

                        else:
                            print('no calls')
                            break
        except GeneratorExit:
                    print("生成器被关闭，停止处理")
                    return
        except Exception as e:
            print(e)
            return str(e)
        finally:
                    # 无工具调用，最终回复
                    print('finalizing response')
                    final_content = accumulated_content
                    if accumulated_reasoning:
                        final_content = f"## 思考：\n * {accumulated_reasoning} * \n ## 回答：\n{final_content}"
                    # 保存历史记录（不含工具调用过程）
                    history.append({"role": "assistant", "content": final_content})
                    if hisid and history_file:
                        with open(history_file, 'w', encoding='utf-8') as f:
                            f.write(json.dumps(history, ensure_ascii=False))
                    money_file = os.path.join(log_dir, "moneys.log")
                    try:
                        with open(money_file, 'r', encoding='utf-8') as f:
                            data_money = json.loads(f.read())
                    except FileNotFoundError:
                        data_money = {}
                    if username not in data_money:
                        data_money[username] = {"money": 0, "isVIP": False}
                    data_money[username]['money'] += total_cost
                    with open(money_file, 'w', encoding='utf-8') as f:
                        f.write(json.dumps(data_money, ensure_ascii=False))

                    # 流式传输结束（可选，前端通过read完成判断）
                    return

    return Response(stream_with_context(generate()), mimetype='text/plain')
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
