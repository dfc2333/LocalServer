"""
WebSocket talk module for real-time chat using Flask-SocketIO
This module integrates with the existing talk system but uses WebSocket for real-time communication.
"""
import os
import json
import datetime
import base64

from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room, send

from config import date, message_dir, userlist, headers
from tools import KeyDecoder, extract_and_save_image_from_pdf, save_image_to_pics, web_page, base_route

# Initialize SocketIO will be done in Server.pyw
socketio = None

# WebSocket talk page
@base_route
def talker_ws():
    """Serve WebSocket version of talk page"""
    return web_page('talk_ws.html')

def init_socketio(app):
    """Initialize SocketIO with the Flask app"""
    global socketio
    # max_http_buffer_size=50MB 确保大图（base64 编码后）能通过 WebSocket 传输
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading',
                        max_http_buffer_size=50 * 1024 * 1024)
    return socketio

# Reuse group functions from talk.py
GROUPS_FILE = os.path.join(message_dir, 'groups.json')


def build_message_id(username, timestamp=None):
    """生成消息 ID，格式为时间戳_用户名。"""
    if timestamp is None:
        timestamp = datetime.datetime.now()
    ts = timestamp.strftime('%Y%m%d%H%M%S%f')
    user_id = username.replace(' ', '_')
    return f'{ts}_{user_id}'


def normalize_message_ids(messages):
    """兼容旧版数字 ID，并统一为新的时间戳_用户名格式。"""
    if not isinstance(messages, dict):
        return messages

    content = messages.get('content', [])
    if not isinstance(content, list):
        return messages

    for msg in content:
        if not isinstance(msg, dict):
            continue

        msg_id = msg.get('id')
        if isinstance(msg_id, (int, float)) or (isinstance(msg_id, str) and msg_id.isdigit()):
            time_value = msg.get('time')
            parsed_time = None
            if isinstance(time_value, str):
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
                    try:
                        parsed_time = datetime.datetime.strptime(time_value, fmt)
                        break
                    except ValueError:
                        continue
            msg['id'] = build_message_id(msg.get('sender', 'system'), parsed_time)
        elif not msg.get('id'):
            msg['id'] = build_message_id(msg.get('sender', 'system'))
    return messages


def load_groups():
    """Load group data"""
    if not os.path.exists(GROUPS_FILE):
        return {}
    try:
        with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_groups(groups):
    """Save group data"""
    with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)

# ── 待通知持久化 ──
PENDING_NOTIFICATIONS_FILE = os.path.join(message_dir, 'pending_notifications.json')

def load_pending_notifications():
    """从文件加载所有待通知数据"""
    if not os.path.exists(PENDING_NOTIFICATIONS_FILE):
        return {}
    try:
        with open(PENDING_NOTIFICATIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_pending_notifications(data):
    """保存待通知数据到文件"""
    with open(PENDING_NOTIFICATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_pending_notification(target_user, sender, chat_target, notif_type):
    """
    为 target_user 添加一条待通知。
    chat_target: 私聊时为对方用户名，群聊时为 @groupname
    notif_type: 'private' 或 'group'
    """
    data = load_pending_notifications()
    if target_user not in data:
        data[target_user] = []
    # 去重：同一聊天目标的最新通知只保留一条
    before = len(data[target_user])
    data[target_user] = [
        n for n in data[target_user]
        if not (n.get('chat_target') == chat_target and n.get('type') == notif_type)
    ]
    data[target_user].append({
        'sender': sender,
        'chat_target': chat_target,
        'type': notif_type,
        'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    save_pending_notifications(data)

def clear_pending_notifications(target_user, chat_target):
    """清除某用户对某聊天目标的待通知"""
    data = load_pending_notifications()
    if target_user not in data:
        return
    data[target_user] = [
        n for n in data[target_user]
        if n.get('chat_target') != chat_target
    ]
    if not data[target_user]:
        del data[target_user]
    save_pending_notifications(data)

def deliver_pending_notifications(username):
    """向某用户投递所有待通知（通过当前 socket emit），投递完成后清除"""
    data = load_pending_notifications()
    notifs = data.get(username, [])
    if not notifs:
        return
    print(f"Delivering {len(notifs)} pending notifications to {username}")
    for n in notifs:
        # 私聊时 chat_target 是对端用户名 → 通知前端显示的是发消息的人
        # 群聊时 chat_target 是 @groupname
        emit('other_new_message', {'target': n['chat_target'], 'sender': n['sender'], 'type': n['type']})
    # 投递后从文件中清除（前端 localStorage 会保持红点）
    del data[username]
    save_pending_notifications(data)


def is_group_target(target):
    """Check if target is a group (starts with @)"""
    return target and target.startswith('@')

def get_group_name(target):
    """Extract group name from target (remove @ prefix)"""
    if is_group_target(target):
        return target[1:]
    return None

def is_user_in_group(username, group_name):
    """Check if user is in group"""
    groups = load_groups()
    group = groups.get(group_name)
    if not group:
        return False
    return username in group.get('members', [])

def get_message_file_path(user, target, key='default'):
    """Determine the message file path based on user and target"""
    if not target:
        # Public chat
        return f'msg_public.json'
    elif is_group_target(target):
        # Group chat
        group_name = get_group_name(target)
        return f'msg_group_{group_name}.json'
    else:
        # Private chat
        users=sorted([user, target])
        return f'msg{users[0]}_{users[1]}.json'

def load_messages(file_path, key='default'):
    """Load messages from file with decryption"""
    full_path = os.path.join(message_dir, file_path)
    
    # Create file if it doesn't exist
    if not os.path.exists(full_path):
        with open(full_path, 'wb') as f:
            time = str(datetime.datetime.now())
            initial_data = {'content': [{'sender': 'system', 'time': 'none', 
                                         'content': f'New file created {time}', 'id': build_message_id('system')}]}
            f.write(KeyDecoder(json.dumps(initial_data, ensure_ascii=False), key))
        return normalize_message_ids(initial_data)
    
    with open(full_path, 'rb') as f:
        encrypted = f.read()
        if not encrypted:
            return {'content': []}
        decrypted = KeyDecoder(encrypted, key)
        try:
            return normalize_message_ids(json.loads(decrypted))
        except:
            return {'content': []}

def save_messages(file_path, messages, key='default'):
    """Save messages to file with encryption"""
    full_path = os.path.join(message_dir, file_path)
    messages = normalize_message_ids(messages)
    try:
        content = KeyDecoder(json.dumps(messages, ensure_ascii=False), key)
    except Exception as e:
        print(f"Error encoding messages: {e}")
        print("falling back to no encryption")
        content = json.dumps(messages, ensure_ascii=False)
        if not content:
            print("Error: Content is empty. Aborting save.")
            return
        with open(full_path, "w", encoding='utf-8') as f:
            f.write(content)
        return
    with open(full_path, 'wb') as f:
        f.write(content)

# WebSocket event handlers
def register_socketio_events(socketio_instance):
    """Register all SocketIO event handlers"""
    global socketio
    socketio = socketio_instance
    
    @socketio.on('connect')
    def handle_connect():
        """Handle new WebSocket connection"""
        print(f"Client connected: {request.sid}")
        # Get username from userlist based on IP
        username = userlist.get(str(request.remote_addr), "")
        
        # 将用户加入个人房间，用于接收私信/群聊通知
        if username:
            join_room(f'user_{username}')
            print(f"User {username} joined personal room user_{username}")
            # 用户上线 → 投递离线期间积压的待通知
            deliver_pending_notifications(username)
        
        print(f"User {username} (IP: {request.remote_addr}) connected with SID {request.sid}")
        emit('connected', {'message': f'Connected as {username or "anonymous"}', 'username': username})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle WebSocket disconnection"""
        print(f"Client disconnected: {request.sid}")
    
    @socketio.on('join')
    def handle_join(data):
        """Join a chat room (public, private, or group)"""
        target = data.get('target', '')
        # 从userlist获取用户名（基于IP）
        username = userlist.get(str(request.remote_addr), "")
        if not username:
            emit('error', {'message': 'You need to set a username first (visit /talk to set)'})
            return
        
        key = data.get('key', 'default')
        
        print(f"User {username} (IP: {request.remote_addr}) joining target: {target}")
        
        # Determine room name
        if not target:
            room = 'public'  # Public chat room
        elif is_group_target(target):
            group_name = get_group_name(target)
            group_key = data.get('group_key', '')
            
            # 检查用户是否已经是群聊成员
            if not is_user_in_group(username, group_name):
                # 如果不是成员，需要验证群聊密钥
                groups = load_groups()
                if group_name not in groups:
                    emit('error', {'message': 'Group not found'})
                    return
                
                group = groups[group_name]
                # 验证访问密钥
                if 'access_key' in group and group['access_key']:
                    if not group_key:
                        emit('error', {'message': 'Group access key required'})
                        return
                    if group_key != group['access_key']:
                        emit('error', {'message': 'Invalid group access key'})
                        return
                
                # 密钥正确，添加用户到成员列表
                groups[group_name]['members'].append(username)
                save_groups(groups)
                print(f"User {username} added to group {group_name}")
            
            room = f'group_{group_name}'
        else:
            # Private chat - create a unique room name for the two users
            # Sort usernames to ensure same room name regardless of order
            users = sorted([username, target])
            room = f'private_{users[0]}_{users[1]}'
        
        join_room(room)
        emit('joined', {'room': room, 'target': target, 'username': username})

        # 用户进入该聊天 → 清除对应的待通知
        chat_key = target if target else 'public'
        clear_pending_notifications(username, chat_key)
        
        # Load and send existing messages
        file_path = get_message_file_path(username, target, key)
        messages = load_messages(file_path, key)
        emit('message_history', {'messages': messages['content'], 'target': target})
    
    @socketio.on('leave')
    def handle_leave(data):
        """Leave a chat room"""
        target = data.get('target', '')
        # 从userlist获取用户名（基于IP）
        username = userlist.get(str(request.remote_addr), "")
        
        if not username:
            emit('error', {'message': 'You need to set a username first (visit /talk to set)'})
            return
        
        # Determine room name (same logic as join)
        if not target:
            room = 'public'
        elif is_group_target(target):
            group_name = get_group_name(target)
            room = f'group_{group_name}'
        else:
            users = sorted([username, target])
            room = f'private_{users[0]}_{users[1]}'
        
        leave_room(room)
        emit('left', {'room': room, 'target': target, 'username': username})
    
    @socketio.on('send_message')
    def handle_send_message(data):
        """Handle sending a new message"""
        content = data.get('content', '')
        target = data.get('target', '')
        quote = data.get('quote', '')
        # 从userlist获取用户名（基于IP）
        username = userlist.get(str(request.remote_addr), "")
        key = data.get('key', 'default')

        if not content:
            emit('error', {'message': 'Message content is empty'})
            return
        
        if not username:
            emit('error', {'message': 'You need to set a username first (visit /login to set)'})
            return

        if is_group_target(target):
            group_name = get_group_name(target)
            if not is_user_in_group(username, group_name):
                emit('error', {'message': 'You are not a member of this group'})
                return

        if not target:
            room = 'public'
        elif is_group_target(target):
            group_name = get_group_name(target)
            room = f'group_{group_name}'
        else:
            users = sorted([username, target])
            room = f'private_{users[0]}_{users[1]}'
        
        file_path = get_message_file_path(username, target, key)
        messages = load_messages(file_path, key)
        
        if content.startswith("Hey there, there is an immage message!"):
            link=content[38:]
            if link:
                img_url = extract_and_save_image_from_pdf(link, key=key)
                if img_url:
                    content = f"ImageURL:{img_url}"
                else:
                    emit('error', {'message': 'Failed to extract image from the provided link'})

        # Add new message
        new_message = {
            'sender': username,
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'content': content,
            'id': build_message_id(username),
            'quote': quote
        }
        messages['content'].append(new_message)
        
        # Save to file
        save_messages(file_path, messages, key)
        
        # Broadcast to room (users currently in this chat)
        emit('new_Message', {
            'message': new_message,
            'target': target,
            'from': username
        }, room=room)
        
        # 私聊：通知接收方（排除自己）
        if target and not is_group_target(target):
            receiver = target
            if receiver != username:  # 不通知自己
                socketio.emit('other_new_message', {'target': username}, room=f'user_{receiver}')
                print(f"Notified {receiver} of new private message from {username}")
                # 持久化待通知（接收方可能在离线）
                add_pending_notification(receiver, username, username, 'private')
        # 群聊：通知所有群成员（除自己外）
        elif is_group_target(target):
            group_name = get_group_name(target)
            groups = load_groups()
            group = groups.get(group_name)
            if group:
                members = group.get('members', [])
                for member in members:
                    if member != username:
                        socketio.emit('other_new_message', {'target': target}, room=f'user_{member}')
                        print(f"Notified {member} of new group message in {target}")
                        # 持久化待通知
                        add_pending_notification(member, username, target, 'group')

        # Also send to sender for confirmation
        emit('message_sent', {'status': 'ok', 'message': new_message})
    
    @socketio.on('upload_image')
    def handle_upload_image(data):
        """Handle uploading an image file and sending it as a message"""
        image_data = data.get('data', '')
        filename = data.get('filename', 'image.png')
        target = data.get('target', '')
        quote = data.get('quote', '')
        key = data.get('key', 'default')
        username = userlist.get(str(request.remote_addr), "")

        if not image_data:
            emit('error', {'message': 'No image data provided'})
            return

        if not username:
            emit('error', {'message': 'You need to set a username first (visit /login to set)'})
            return

        # Check permissions for group chat
        if is_group_target(target):
            group_name = get_group_name(target)
            if not is_user_in_group(username, group_name):
                emit('error', {'message': 'You are not a member of this group'})
                return

        # Decode base64 (strip data:image/...;base64, prefix if present)
        try:
            raw = image_data
            if ',' in raw:
                raw = raw.split(',')[1]
            image_bytes = base64.b64decode(raw)
        except Exception as e:
            emit('error', {'message': f'Failed to decode image: {str(e)}'})
            return

        # Determine file extension from filename
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'png'
        supported = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        if ext not in supported:
            ext = 'png'

        # Save encrypted image to pics/ and get URL
        # 如果使用了非 default 密钥，URL 中携带 key 参数以便 serve_pics 解密
        img_url = save_image_to_pics(image_bytes, key=key, ext=ext)
        if key != 'default':
            img_url += f'?key={key}'
        content = f"ImageURL:{img_url}"

        # Determine room and file path
        if not target:
            room = 'public'
        elif is_group_target(target):
            group_name = get_group_name(target)
            room = f'group_{group_name}'
        else:
            users = sorted([username, target])
            room = f'private_{users[0]}_{users[1]}'

        file_path = get_message_file_path(username, target, key)
        messages = load_messages(file_path, key)

        # Add new message
        new_message = {
            'sender': username,
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'content': content,
            'id': build_message_id(username),
            'quote': quote
        }
        messages['content'].append(new_message)
        save_messages(file_path, messages, key)

        # Broadcast to ALL clients in room (including self)
        # 使用 socketio.emit（全局）代替内部 emit，确保发送者也能收到
        socketio.emit('new_Message', {
            'message': new_message,
            'target': target,
            'from': username
        }, room=room)

        # Notification logic (same as send_message)
        if target and not is_group_target(target):
            receiver = target
            if receiver != username:
                socketio.emit('other_new_message', {'target': username}, room=f'user_{receiver}')
                add_pending_notification(receiver, username, username, 'private')
        elif is_group_target(target):
            group_name = get_group_name(target)
            groups = load_groups()
            group = groups.get(group_name)
            if group:
                for member in group.get('members', []):
                    if member != username:
                        socketio.emit('other_new_message', {'target': target}, room=f'user_{member}')
                        add_pending_notification(member, username, target, 'group')

        emit('message_sent', {'status': 'ok', 'message': new_message, 'is_image': True})

    @socketio.on('delete_message')
    def handle_delete_message(data):
        """Delete a message by message_id or legacy index"""
        target = data.get('target', '')
        # 从userlist获取用户名（基于IP）
        username = userlist.get(str(request.remote_addr), "")
        key = data.get('key', 'default')
        message_id = data.get('message_id')
        index = data.get('index', -1)
        
        if message_id is None and index < 0:
            emit('error', {'message': 'Invalid message id'})
            return
        
        if not username:
            emit('error', {'message': 'You need to set a username first (talk to dfc to set)'})
            return
        
        # Check permissions
        if is_group_target(target):
            group_name = get_group_name(target)
            if not is_user_in_group(username, group_name):
                emit('error', {'message': 'You are not a member of this group'})
                return
        
        # Determine room and file path
        if not target:
            room = 'public'
        elif is_group_target(target):
            group_name = get_group_name(target)
            room = f'group_{group_name}'
        else:
            users = sorted([username, target])
            room = f'private_{users[0]}_{users[1]}'
        
        file_path = get_message_file_path(username, target, key)
        messages = load_messages(file_path, key)
        
        # 优先按消息 ID 定位，兼容旧客户端的 index 传参。
        delete_index = -1
        if message_id is not None:
            for idx, msg in enumerate(messages['content']):
                if msg.get('id') == message_id:
                    delete_index = idx
                    break
        elif index >= 0 and index < len(messages['content']):
            delete_index = index

        if delete_index < 0 or delete_index >= len(messages['content']):
            emit('error', {'message': 'Message not found, you can re enter the chat to refresh the message list'})
            return
        
        message_to_delete = messages['content'][delete_index]
        if message_to_delete['sender'] != username:
            emit('error', {'message': 'You can only delete your own messages'})
            return
        
        # Check if time limit for deletion has passed (e.g., 5 minutes)
        message_time_str = message_to_delete['time']
        if message_time_str != 'none' and len(message_time_str) == 19:  # time format: YYYY-mm-dd HH:MM:SS
            message_time = datetime.datetime.strptime(message_time_str, '%Y-%m-%d %H:%M:%S')
            time_diff = datetime.datetime.now() - message_time
            if time_diff > datetime.timedelta(minutes=2):
                emit('error', {'message': 'Message is too old to delete'})
                return
        else:
            emit('error', {'message': 'Invalid message time format'})
            return


        # Delete the message
        deleted_message = messages['content'].pop(delete_index)
        
        # Save to file
        save_messages(file_path, messages, key)
        
        # Broadcast deletion to room
        emit('message_deleted', {
            'message_id': deleted_message.get('id'),
            'index': delete_index,
            'deleted_message': deleted_message,
            'target': target
        }, room=room)
        
        emit('delete_success', {'status': 'ok', 'message_id': deleted_message.get('id')})
    
    @socketio.on('create_group')
    def handle_create_group(data):
        """Create a new group"""
        group_name = data.get('name', '')
        # 从userlist获取用户名（基于IP）
        username = userlist.get(str(request.remote_addr), "")
        access_key = data.get('access_key', '')
        
        if not group_name:
            emit('error', {'message': 'Group name is required'})
            return
        
        if not username or username == 'anonymous':
            emit('error', {'message': 'You need to set a username first'})
            return
        
        groups = load_groups()
        
        if group_name in groups:
            emit('error', {'message': f'Group {group_name} already exists'})
            return
        
        # 如果未提供密钥，生成一个随机密钥（6位数字）
        if not access_key:
            import random
            access_key = str(random.randint(100000, 999999))
        
        groups[group_name] = {
            'creator': username,
            'members': [username],
            'created_at': str(datetime.datetime.now()),
            'access_key': access_key
        }
        save_groups(groups)
        
        # Create group message file
        file_path = f'msg_group_{group_name}.json'
        full_path = os.path.join(message_dir, file_path)
        if not os.path.exists(full_path):
            with open(full_path, 'wb') as f:
                time = str(datetime.datetime.now())
                initial_data = {'content': [{'sender': 'system', 'time': 'none', 
                                             'content': f'Group {group_name} created {time}', 'id': build_message_id('system')}]}
                f.write(KeyDecoder(json.dumps(initial_data, ensure_ascii=False), 'default'))
        
        emit('group_created', {
            'group_name': group_name,
            'creator': username,
            'members': [username],
            'access_key': access_key
        })