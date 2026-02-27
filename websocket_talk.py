"""
WebSocket talk module for real-time chat using Flask-SocketIO
This module integrates with the existing talk system but uses WebSocket for real-time communication.
"""
import os
import json
import datetime
from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room, send
from config import date, message_dir, userlist
from tools import KeyDecoder

# Initialize SocketIO will be done in Server.pyw
socketio = None

def init_socketio(app):
    """Initialize SocketIO with the Flask app"""
    global socketio
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
    return socketio

# Reuse group functions from talk.py
GROUPS_FILE = os.path.join(message_dir, 'groups.json')

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

def get_username_from_request():
    """Get username from request (for WebSocket connections)"""
    # For WebSocket, we need to get username differently
    # In HTTP requests, it's from request.remote_addr
    # For WebSocket, we might need to pass it as a query parameter or in session
    # For now, use a placeholder - will need to implement proper auth
    return "anonymous"

def get_message_file_path(user, target, key='default'):
    """Determine the message file path based on user and target"""
    if not target:
        # Public chat
        return f'msg{date}.json'
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
                                         'content': f'New file created {time}', 'id': 0}]}
            f.write(KeyDecoder(json.dumps(initial_data, ensure_ascii=False), key))
        return initial_data
    
    with open(full_path, 'rb') as f:
        encrypted = f.read()
        if not encrypted:
            return {'content': []}
        decrypted = KeyDecoder(encrypted, key)
        try:
            return json.loads(decrypted)
        except:
            return {'content': []}

def save_messages(file_path, messages, key='default'):
    """Save messages to file with encryption"""
    full_path = os.path.join(message_dir, file_path)
    with open(full_path, 'wb') as f:
        f.write(KeyDecoder(json.dumps(messages, ensure_ascii=False), key))

# WebSocket event handlers
def register_socketio_events(socketio_instance=None):
    """Register all SocketIO event handlers"""
    global socketio
    if socketio_instance:
        socketio = socketio_instance
    
    @socketio.on('connect')
    def handle_connect():
        """Handle new WebSocket connection"""
        print(f"Client connected: {request.sid}")
        # Get username from userlist based on IP
        username = userlist.get(str(request.remote_addr), "")
        
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
        # 从userlist获取用户名（基于IP）
        username = userlist.get(str(request.remote_addr), "")
        key = data.get('key', 'default')
        
        if not content:
            emit('error', {'message': 'Message content is empty'})
            return
        
        if not username:
            emit('error', {'message': 'You need to set a username first (visit /talk to set)'})
            return
        
        # Check permissions for group chat
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
        
        # Add new message
        new_message = {
            'sender': username,
            'time': str(datetime.datetime.now())[-15:-7],
            'content': content,
            'id': len(messages['content'])
        }
        messages['content'].append(new_message)
        
        # Save to file
        save_messages(file_path, messages, key)
        
        # Broadcast to room
        emit('new_message', {
            'message': new_message,
            'target': target
        }, room=room)
        
        # Also send to sender for confirmation
        emit('message_sent', {'status': 'ok', 'message': new_message})
    
    @socketio.on('delete_message')
    def handle_delete_message(data):
        """Delete a message by index"""
        target = data.get('target', '')
        # 从userlist获取用户名（基于IP）
        username = userlist.get(str(request.remote_addr), "")
        key = data.get('key', 'default')
        index = data.get('index', -1)
        
        if index < 0:
            emit('error', {'message': 'Invalid message index'})
            return
        
        if not username:
            emit('error', {'message': 'You need to set a username first (visit /talk to set)'})
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
        
        # Check if index is valid
        if index >= len(messages['content']):
            emit('error', {'message': 'Message index out of range'})
            return
        
        # Check if user is allowed to delete (only own messages or admin)
        message_to_delete = messages['content'][index]
        if message_to_delete['sender'] != username and username != 'admin':
            emit('error', {'message': 'You can only delete your own messages'})
            return
        
        # Delete the message
        deleted_message = messages['content'].pop(index)
        
        # Update IDs for remaining messages
        for i, msg in enumerate(messages['content']):
            msg['id'] = i
        
        # Save to file
        save_messages(file_path, messages, key)
        
        # Broadcast deletion to room
        emit('message_deleted', {
            'index': index,
            'deleted_message': deleted_message,
            'target': target
        }, room=room)
        
        emit('delete_success', {'status': 'ok', 'index': index})
    
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
                                             'content': f'Group {group_name} created {time}', 'id': 0}]}
                f.write(KeyDecoder(json.dumps(initial_data, ensure_ascii=False), 'default'))
        
        emit('group_created', {
            'group_name': group_name,
            'creator': username,
            'members': [username],
            'access_key': access_key
        })