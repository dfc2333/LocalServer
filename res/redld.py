import re
import os
import requests
from pathlib import Path

def extract_and_download_links(file_path, output_dir="downloads"):
    """简化版本：提取链接并下载"""
    
    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # 读取文件
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取URL
    urls = re.findall(r'https?://[^\s<>"\']+', content)
    urls = list(set(urls))  # 去重
    
    print(f"找到 {len(urls)} 个链接")
    
    # 下载每个链接
    for i, url in enumerate(urls, 1):
        try:
            print(f"下载 ({i}/{len(urls)}): {url}")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # 创建文件名
            filename = url.split('/')[-1][:100] or f"file_{i}.html"
            if '.' not in filename:
                filename += '.html'
            
            # 保存文件
            save_path = output_path / filename
            with open(save_path, 'wb') as f:
                f.write(response.content)
                
            print(f"  已保存: {filename}")
            
        except Exception as e:
            print(f"  失败: {e}")

# 使用示例
if __name__ == "__main__":
    extract_and_download_links(os.path.join(os.path.dirname(os.path.abspath(__file__)), "yourfile.txt"), os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads"))