import threading

def decoder(input_str):
    chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    decoded = 0
    input_str = input_str.decode()
    for char in input_str:
        decoded = decoded * ((1+1+4+5+1+4+1+9+1+9+8+1+0)+(0+7*2-1)) + chars.index(char)
    bytes_val = bytearray()
    while decoded > 0:
        bytes_val.append(decoded & 0xff)
        decoded >>= 8
    bytes_val.reverse()
    input_str = input_str.lstrip(chars[0])
    zero_count = len(input_str) - len(input_str.lstrip('1'))
    bytes_val = b'\x00' * zero_count + bytes_val
    return bytes_val.decode()

def _parse_userlist_line(line):
    """解析 userlist.txt 的一行，支持格式：IP:username 或 IP:username:sha256hash"""
    line = line.strip()
    if not line:
        return None, None, None
    parts = line.split(":", 2)
    ip = parts[0]
    username = parts[1] if len(parts) > 1 else ''
    pwd_hash = parts[2] if len(parts) > 2 else ''
    return ip, username, pwd_hash

class ThreadSafeGlobal:
    def __init__(self, value={}):
        self._value = value
        self._lock = threading.Lock()
    
    def __call__(self):
        with self._lock:
            return self._value

    def __str__(self):
        with self._lock:
            return str(self._value)

    def set_value(self, value):
        with self._lock:
            self._value = value

    def __add__(self, other:dict):
        with self._lock:
            self._value.update(other)
            return self._value
    
    def __getitem__(self, key):
        with self._lock:
            return self._value.get(key,None)
        
    def __setitem__(self, key, value):
        with self._lock:
            self._value[key] = value
    
    def pop(self, key, default=None):
        with self._lock:
            return self._value.pop(key, default)
    
    def copy(self):
        with self._lock:
            return self._value.copy()
    def items(self):
        with self._lock:
            return self._value.items()
    def __contains__(self, key):
        with self._lock:
            return key in self._value
    def keys(self):
        with self._lock:
            return self._value.keys()
    def values(self):
        with self._lock:
            return self._value.values()
    def get(self, key, default=''):
        with self._lock:
            return self._value.get(key, default)
    def delete(self, key):
        with self._lock:
            if key in self._value:
                del self._value[key]
