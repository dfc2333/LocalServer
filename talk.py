import os
import json
import datetime
from flask import request
from config import date, message_dir
from tools import (
    userlist,
    WSAvaliable as avaliable,
    KeyDecoder
)

GROUPS_FILE = os.path.join(message_dir, 'groups.json')

def load_groups():
    """加载群聊数据"""
    if not os.path.exists(GROUPS_FILE):
        return {}
    try:
        with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_groups(groups):
    """保存群聊数据"""
    with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)

def is_group_target(targetuser):
    """判断targetuser是否为群聊ID（以@开头）"""
    print("Checking if targetuser is group:", targetuser)
    result = targetuser and targetuser.startswith('@')
    print("Result:", result)
    return result

def get_group_name(targetuser):
    """从targetuser中提取群聊ID（去除@前缀）"""
    if is_group_target(targetuser):
        return targetuser[1:]
    return None

def is_user_in_group(username, group_name):
    """检查用户是否在群聊中"""
    groups = load_groups()
    group = groups.get(group_name)
    if not group:
        return False
    return username in group.get('members', [])

def read_message():
    global date
    targetuser = str(request.args.get('targetuser')) if request.args.get('targetuser') else ''
    user = userlist.get(str(request.remote_addr), "")
    key = request.args.get("key")
    if not key:
        key = 'default'
    print("key:", key)
    if not user:
        return '{"content":"No username provided"}'
    
    # 检查是否为群聊
    if is_group_target(targetuser):
        group_name = get_group_name(targetuser)
        if not group_name:
            return '{"content":"Invalid group ID"}'
        if not is_user_in_group(user, group_name):
            return '{"content":"You are not a member of this group"}'
        targetFile = f'msg_group_{group_name}.json'
    elif (not targetuser in userlist.values()) or not targetuser:
        # 公共聊天
        targetFile = f'msg{date}.json'
    else:
        # 一对一私聊
        targetFile = ''
        for i in os.scandir(message_dir):
            users = i.name[3:-5].split('_')
            if (targetuser in users) and (user in users):
                targetFile = i.name
                break
        if not targetFile:
            targetFile = f'msg{user}_{targetuser}.json'
    if not os.path.exists(os.path.join(message_dir, targetFile)):
        with open(os.path.join(message_dir, targetFile), 'w', encoding='utf-8') as f:
            f.write('')
    with open(os.path.join(message_dir, targetFile), 'rb') as file:
        filecontent = file.read()
        if not filecontent:
            with open(os.path.join(message_dir, targetFile), 'wb') as file:
                time = str(datetime.datetime.now())
                file.write(KeyDecoder('{"content":[{"sender":"system","time":"none","content":"Newfilecreated'+time+'","id":0}]}', key))
            return '{"content":[{"sender":"system","time":"none","content":"Newfilecreated'+time+'","id":0}]}'
        return KeyDecoder(filecontent, key)

def send_msg():
    global date
    sender = userlist.get(str(request.remote_addr), '')
    if not sender:
        return '{"content":"No username provided"}'
    content = str(request.args.get('content'))
    targetuser = str(request.args.get('targetuser'))
    key = request.args.get('key', "default")
    if not key:
        key = 'default'
    
    # 检查是否为群聊
    if is_group_target(targetuser):
        group_name = get_group_name(targetuser)
        if not group_name:
            return '{"content":"Invalid group ID"}'
        if not is_user_in_group(sender, group_name):
            return '{"content":"You are not a member of this group"}'
        targetFile = f'msg_group_{group_name}.json'
    elif not targetuser:
        # 公共聊天
        targetFile = f'msg{date}.json'
    else:
        # 一对一私聊
        targetFile = ''
        for i in os.scandir(message_dir):
            users = i.name[3:-5].split('_')
            if (targetuser in users) and (sender in users):
                targetFile = i.name
                break
        if not targetFile:
            targetFile = f'msg{sender}_{targetuser}.json'
    
    with open(os.path.join(message_dir, targetFile), 'rb') as f:
        file = json.loads(KeyDecoder(f.read(), key))
    with open(os.path.join(message_dir, targetFile), 'wb') as f:
        id = file["content"][-1]["id"]
        file['content'].append({'sender': sender, 'time': str(datetime.datetime.now())[-15:-7], 'content': content, "id": id+1})
        f.write(KeyDecoder(json.dumps(file, ensure_ascii=False), key))
    return 'ok'

def announce():
    ctnt = request.args.get('content')
    if ctnt:
        with open(os.path.join(message_dir, 'announcement.data'), 'w', encoding='utf-8') as f:
            f.write(ctnt)
    else:
        with open(os.path.join(message_dir, 'announcement.data'), 'r', encoding='utf-8') as f:
            return f.read()

def talker():
    return avaliable('talk.html')

# 群聊管理函数
def create_group():
    """创建群聊"""
    user = userlist.get(str(request.remote_addr), "")
    if not user:
        return '{"error":"No username provided"}'
    
    group_name = request.args.get('name')
    if not group_name:
        return '{"error":"Group name required"}'
    
    groups = load_groups()
    
    groups[group_name] = {
        'creator': user,
        'members': [user],
        'created_at': str(datetime.datetime.now())
    }
    save_groups(groups)
    
    # 创建群聊消息文件
    targetFile = f'msg_group_{group_name}.json'
    with open(os.path.join(message_dir, targetFile), 'wb') as f:
        time = str(datetime.datetime.now())
        f.write(KeyDecoder('{"content":[{"sender":"system","time":"none","content":"Group created '+time+'","id":0}]}', 'default'))
    
    return json.dumps({'success': True,'group_name': group_name})

def join_group():
    """加入群聊"""
    user = userlist.get(str(request.remote_addr), "")
    if not user:
        return '{"error":"No username provided"}'
    
    group_name = request.args.get('group_name')
    if not group_name:
        return '{"error":"Group ID required"}'
    
    groups = load_groups()
    if group_name not in groups:
        return '{"error":"Group not found"}'
    
    if user not in groups[group_name]['members']:
        groups[group_name]['members'].append(user)
        save_groups(groups)
    
    return json.dumps({'success': True, 'group_name': group_name})

def list_groups():
    """获取用户所在的群聊列表"""
    user = userlist.get(str(request.remote_addr), "")
    if not user:
        return '{"error":"No username provided"}'
    
    groups = load_groups()
    user_groups = []
    for group_name, group_info in groups.items():
        if user in group_info['members']:
            user_groups.append({
                'group_name': group_name,
                'creator': group_info['creator'],
                'member_count': len(group_info['members']),
                'created_at': group_info['created_at']
            })
    
    return json.dumps({'groups': user_groups})

def group_info():
    """获取群聊详细信息"""
    group_name = request.args.get('group_name')
    if not group_name:
        return '{"error":"Group ID required"}'
    
    groups = load_groups()
    if group_name not in groups:
        return '{"error":"Group not found"}'
    
    return json.dumps(groups[group_name])