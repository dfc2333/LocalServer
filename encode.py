def base58_encode(bytes):
    """
    将字节数组进行Base58编码
    """
    # 定义Base58字符集
    chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    
    # 初始化编码后的字符串
    encoded = ''
    
    # 计算字节数组的总数值
    int_val = int.from_bytes(bytes, 'big')
    
    # 进行Base58编码
    while int_val:
        int_val, idx = divmod(int_val, 58)
        encoded = chars[idx] + encoded
    
    return encoded
data = b'hello'
encoded = base58_encode(data)
print(encoded)
