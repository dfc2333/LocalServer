import json
import os
import copy
import datetime
import requests
import urllib.request
from bs4 import BeautifulSoup
from config import *
from config import DEFAULT_WEEK_SCHEDULE
from flask import request,Response,stream_with_context
from tools import (
    WSAvailable as available,
    userlist,
    isVIP,
    track_visit,
    web_page,
    base_route,
    args_route,
)
from ManageService import track_daily_ai_usage,plus_ai_usage

import base64
import pytesseract
from PIL import Image, ImageFilter
import io
import numpy as np

# ─── 陪伴模式 & AI记忆 ────────────────────────────────────
COMPANION_CONFIG_FILE = os.path.join(log_dir, 'companion_configs.json')
COMPANION_MEMORY_DIR = os.path.join(log_dir, 'companion_memory')
TEMP_CHAT_DIR = os.path.join(log_dir, 'temp_chat')
os.makedirs(COMPANION_MEMORY_DIR, exist_ok=True)
os.makedirs(TEMP_CHAT_DIR, exist_ok=True)

_CHINESE_DAYS = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
_ENGLISH_DAYS = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']



def _load_json_file(filepath, default=None):
    if default is None: default = {}
    if not os.path.exists(filepath): return default
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return default


def _save_json_file(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _default_week_schedule():
    """返回默认课表（建议课表）"""
    import copy
    return copy.deepcopy(DEFAULT_WEEK_SCHEDULE)


def get_default_companion_config():
    return {
        'companion_enabled': False,
        'user_status': '在学习',
        'week_schedule': _default_week_schedule(),
        'mic2text_show_in_chat': False,
        'mic2text_in_context': True,
        'show_time_elapsed': False,
        'temp_chat_enabled': True,
    }


def load_companion_config(username):
    configs = _load_json_file(COMPANION_CONFIG_FILE, {})
    return configs.get(username, get_default_companion_config())


def save_companion_config(username, config):
    configs = _load_json_file(COMPANION_CONFIG_FILE, {})
    configs[username] = config
    _save_json_file(COMPANION_CONFIG_FILE, configs)


def get_current_schedule_status(config):
    """返回当前是上课还是下课，如果在上课则返回课程名"""
    now = datetime.datetime.now()
    day_name = _ENGLISH_DAYS[now.weekday()]
    current_time = now.strftime('%H:%M')
    schedule = config.get('week_schedule', {}).get(day_name, [])
    for slot in sorted(schedule, key=lambda x: x.get('start', '00:00')):
        if slot['start'] <= current_time <= slot['end']:
            return slot['name']  # 返回课程名
    return None  # 在下课


def fetch_mic2text_transcript():
    """从 mic2text 服务拉取最近10句转录，返回字符串。"""
    if not mic2text_url:
        return ''
    try:
        url = f'{mic2text_url}/query'
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read())
        sentences = data.get('texts', [])
        if not sentences:
            return ''
        lines = [f"{s}" for s in sentences]
        return '[教室实时音频：\n' + '\n'.join(lines) + ']\n[--音频结束--]'
    except Exception as e:
        print(f'[mic2text] fetch error: {e}')
        return ''


# ── 星期名称映射 ──
_CHINESE_DAY_MAP = {
    '星期一': 0, '周二': 1, '星期二': 1, '周三': 2, '星期三': 2,
    '周四': 3, '星期四': 3, '周五': 4, '星期五': 4,
    '周六': 5, '星期六': 5, '周日': 6, '星期日': 6,
    'monday': 0, 'tuesday': 1, 'wednesday': 2,
    'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6,
}


def _resolve_weekday_index(weekday_str):
    """解析星期名称到 0-6 的数字（周一=0）"""
    if weekday_str is None:
        return datetime.datetime.now().weekday()
    key = weekday_str.strip().lower()
    if key in _CHINESE_DAY_MAP:
        return _CHINESE_DAY_MAP[key]
    # 试试是不是纯数字
    try:
        return int(key) % 7
    except ValueError:
        pass
    # 尝试匹配：周X, 星期X
    import re
    m = re.search(r'[周星期]([一二三四五六日1234567])', weekday_str)
    if m:
        cn_digits = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}
        c = m.group(1)
        if c in cn_digits:
            return cn_digits[c]
        try:
            return (int(c) - 1) % 7
        except ValueError:
            pass
    # 默认今天
    return datetime.datetime.now().weekday()


def _get_date_for_weekday(weekday_index):
    """获取最近的一次给定星期几的日期（往前找，不含今天）"""
    today = datetime.date.today()
    days_ahead = weekday_index - today.weekday()
    if days_ahead > 0:
        days_ahead -= 7
    target = today + datetime.timedelta(days=days_ahead)
    return target


def query_course_records_by_user(username, course_name, weekday_str=None, date_str=None, start_time=None, end_time=None):
    """
    根据课表查询某门课的语音识别记录。
    
    参数：
        username: str - 用户名（用于加载其课表配置）
        course_name: str - 课程名，如"数学"、"语文"（支持子串匹配）
        weekday_str: str | None - 星期几，如"星期一"、"monday"、"周二"，None=今天
        date_str: str | None - 具体日期 "2026-06-22"，会覆盖 weekday_str
        start_time: str | None - 自定义起始时间 "HH:MM"，与 end_time 成对使用
        end_time: str | None - 自定义结束时间 "HH:MM"
    
    返回：
        dict: {"matching_slots": [...], "records": ["[时间] 文本"...], "count": int}
    """
    if not mic2text_url:
        return {"error": "mic2text 服务未配置", "matching_slots": [], "records": [], "count": 0}
    
    # 加载用户课表
    config = load_companion_config(username)
    week_schedule = config.get('week_schedule', copy.deepcopy(DEFAULT_WEEK_SCHEDULE))
    
    # 确定目标日期
    if date_str:
        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            weekday_idx = target_date.weekday()
        except ValueError:
            return {"error": f"日期格式错误: {date_str}，应为 YYYY-MM-DD", "matching_slots": [], "records": [], "count": 0}
    else:
        weekday_idx = _resolve_weekday_index(weekday_str)
        target_date = _get_date_for_weekday(weekday_idx)
    
    day_key = _ENGLISH_DAYS[weekday_idx] if weekday_idx < 7 else ''
    
    # 查询课程对应的时段
    slots = week_schedule.get(day_key, [])
    matching_slots = []
    
    if start_time and end_time:
        # 自定义时间范围，不按课程名过滤
        matching_slots.append({
            "day": day_key,
            "start": start_time,
            "end": end_time,
            "name": f"自定义查询 {start_time}-{end_time}"
        })
    elif course_name:
        # 按课程名模糊匹配
        cn_lower = course_name.lower()
        for slot in slots:
            slot_name = slot.get('name', '')
            if cn_lower in slot_name.lower():
                matching_slots.append({
                    "day": day_key,
                    "start": slot['start'],
                    "end": slot['end'],
                    "name": slot_name
                })
        if not matching_slots:
            return {"error": f"在 {day_key} 未找到课程名包含「{course_name}」的时段",
                    "matching_slots": [], "records": [], "count": 0}
    else:
        # 无过滤：返回该天所有时段
        for slot in slots:
            matching_slots.append({
                "day": day_key,
                "start": slot['start'],
                "end": slot['end'],
                "name": slot.get('name', '')
            })
        if not matching_slots:
            return {"error": f"{day_key} 没有排课", "matching_slots": [], "records": [], "count": 0}
    
    # 对每个时段查询 mic2text
    all_records = []
    for ms in matching_slots:
        start_dt = f"{target_date}T{ms['start']}:00"
        end_dt = f"{target_date}T{ms['end']}:00"
        try:
            url = f"{mic2text_url}/query?start={start_dt}&end={end_dt}"
            with urllib.request.urlopen(url, timeout=3) as resp:
                data = json.loads(resp.read())
            texts = data.get('texts', [])
            if texts:
                all_records.append({
                    "course": ms['name'],
                    "time_range": f"{ms['start']}-{ms['end']}",
                    "date": str(target_date),
                    "records": texts
                })
        except Exception as e:
            all_records.append({
                "course": ms['name'],
                "time_range": f"{ms['start']}-{ms['end']}",
                "date": str(target_date),
                "error": str(e),
                "records": []
            })
            print(e)
            break
    
    # 汇总
    flat_records = []
    for entry in all_records:
        for r in entry.get('records', []):
            flat_records.append(r)
    
    return {
        "date": str(target_date),
        "day": day_key,
        "course_name": course_name,
        "matching_slots": [{"name": s['name'], "time": f"{s['start']}-{s['end']}"} for s in matching_slots],
        "records": flat_records,
        "count": len(flat_records),
        "detail": all_records
    }

def search_course_records_by_keyword(username, keyword, course_name=None,
                                        weekday_str=None, date_str=None,
                                        start_time=None, end_time=None,
                                        max_results=5, context_lines=2):
    """
    在课堂语音记录中搜索关键词，模糊匹配（子串匹配不区分大小写），
    返回命中记录及其附近若干条上下文。

    参数：
        username: str - 用户名
        keyword: str - 搜索关键词，支持模糊匹配（子串匹配）
        course_name: str | None - 限定课程名（课表上的课程名）
        weekday_str: str | None - 星期几，如"星期一"、"monday"，默认今天
        date_str: str | None - 具体日期 YYYY-MM-DD，会覆盖 weekday
        start_time: str | None - 自定义起始时间 HH:MM
        end_time: str | None - 自定义结束时间 HH:MM
        max_results: int - 最多返回几条匹配结果（默认5条）
        context_lines: int - 每条匹配前后取几条上下文（默认2条）

    返回：
        dict: {
            keyword, matches: [{line_index, text, context_with_surrounding}],
            total_matches, highlighted
        }
    """
    if not mic2text_url:
        return {"error": "mic2text 服务未配置", "matches": [], "total_matches": 0}

    if not keyword or not keyword.strip():
        return {"error": "请提供搜索关键词", "matches": [], "total_matches": 0}

    keyword = keyword.strip()

    # 获取课程记录（按课程/时间过滤）
    records_result = query_course_records_by_user(
        username, course_name or '', weekday_str, date_str, start_time, end_time
    )

    if "error" in records_result and not records_result.get("records"):
        err_msg = records_result.get("error", "未找到记录")
        # 如果没指定课程/时间，尝试搜索最近所有可用记录
        if not course_name and not start_time and not end_time:
            # 回退：搜索今天全部
            records_result = query_course_records_by_user(
                username, '', datetime.datetime.now().strftime('%A').lower()[:3] + 'day',
                None, None, None
            )
            if "error" in records_result and not records_result.get("records"):
                return {"keyword": keyword, "matches": [], "total_matches": 0,
                        "message": err_msg}
        else:
            return {"keyword": keyword, "matches": [], "total_matches": 0,
                    "message": err_msg}

    all_records = records_result.get("records", [])
    if not all_records:
        return {"keyword": keyword, "matches": [], "total_matches": 0}

    # 模糊搜索：子串匹配（不区分大小写）
    kw_lower = keyword.lower()
    matched_indices = []
    for i, text in enumerate(all_records):
        if kw_lower in text.lower():
            matched_indices.append(i)

    if not matched_indices:
        return {
            "keyword": keyword,
            "matches": [],
            "total_matches": 0,
            "total_records": len(all_records),
            "message": f"未找到包含「{keyword}」的语音记录",
            "course_info": records_result.get("matching_slots", []),
            "date": records_result.get("date", ""),
            "day": records_result.get("day", ""),
            "suggestion": "试试换个关键词，或缩小时间/课程范围？"
        }

    # 构建结果：每条命中带上下文
    matches = []
    for idx in matched_indices[:max_results]:
        start_ctx = max(0, idx - context_lines)
        end_ctx = min(len(all_records), idx + context_lines + 1)
        context_with_surrounding = [
            {"index": j, "text": all_records[j], "is_match": (j == idx)}
            for j in range(start_ctx, end_ctx)
        ]
        matches.append({
            "line_index": idx,
            "text": all_records[idx],
            "context_with_surrounding": context_with_surrounding,
            "surrounding_text": '\n'.join(
                all_records[max(0, idx - context_lines): min(len(all_records), idx + context_lines + 1)]
            )
        })

    return {
        "keyword": keyword,
        "matches": matches,
        "total_matches": len(matched_indices),
        "total_records": len(all_records),
        "course_info": records_result.get("matching_slots", []),
        "date": records_result.get("date", ""),
        "day": records_result.get("day", ""),
        "highlighted": f"在 {records_result.get('date', '今天')} 的课堂语音中共找到 {len(matched_indices)} 条包含「{keyword}」的记录"
    }


def _time_to_str(seconds):
    """将秒数转为可读字符串"""
    if seconds < 60:
        return f'{seconds}秒'
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f'{m}分{s}秒'
    else:
        h, r = divmod(seconds, 3600)
        m = r // 60
        return f'{h}小时{m}分钟'



def build_companion_context(config, username, hisid=None):
    """构建陪伴模式上下文，在用户输入前插入"""
    now = datetime.datetime.now()
    day_cn = _CHINESE_DAYS[now.weekday()]
    time_str = now.strftime(f'%Y年%m月%d日 {day_cn} %H:%M')
    status = config.get('user_status', '')
    # 计算课程状态及距上课/下课时间
    day_name = _ENGLISH_DAYS[now.weekday()]
    current_sec = now.hour * 3600 + now.minute * 60 + now.second
    schedule = config.get('week_schedule', {}).get(day_name, [])
    current_class = None
    next_class = None
    for slot in sorted(schedule, key=lambda x: x.get('start', '00:00')):
        sp = slot['start'].split(':')
        ep = slot['end'].split(':')
        start_sec = int(sp[0]) * 3600 + int(sp[1]) * 60
        end_sec = int(ep[0]) * 3600 + int(ep[1]) * 60
        if start_sec <= current_sec <= end_sec:
            current_class = slot
            break
        if start_sec > current_sec and not next_class:
            next_class = slot
    class_name = current_class['name'] if current_class else None
    if class_name:
        schedule_info = f'{class_name}'
    else:
        schedule_info = '下课'
    # 拉取实时音频转录（仅开关开启时）
    mic_text = fetch_mic2text_transcript() if config.get('mic2text_in_context', True) else ''
    parts = [
        f'[当前时间：{time_str}]',
        f'[用户状态：{status}]',
        f'[当前课：{schedule_info}]',
    ]
    # 距下课 / 距上课（自动添加，无开关）
    if current_class:
        ep = current_class['end'].split(':')
        end_sec = int(ep[0]) * 3600 + int(ep[1]) * 60
        rem = end_sec - current_sec
        if rem > 0:
            parts.append(f'[距下课：{_time_to_str(rem)}]')
    elif next_class:
        sp = next_class['start'].split(':')
        start_sec = int(sp[0]) * 3600 + int(sp[1]) * 60
        to = start_sec - current_sec
        if to > 0:
            parts.append(f'[距上课：{_time_to_str(to)}]')
    # 距上次对话经过的时间（仅开关开启时，按对话隔离）
    if config.get('show_time_elapsed', False) and hisid:
        hfile = os.path.join(log_dir, f"{hisid}'smemory.log")
        if os.path.exists(hfile):
            try:
                mtime = os.path.getmtime(hfile)
                last_dt = datetime.datetime.fromtimestamp(mtime)
                elapsed = now - last_dt
                seconds = int(elapsed.total_seconds())
                if seconds < 60:
                    t_str = f'{seconds}秒前'
                elif seconds < 3600:
                    m, s = divmod(seconds, 60)
                    t_str = f'{m}分{s}秒前'
                elif seconds < 86400:
                    h, m = divmod(seconds, 3600)
                    t_str = f'{h}小时{m // 60}分钟前'
                else:
                    d, r = divmod(seconds, 86400)
                    h = r // 3600
                    t_str = f'{d}天{h}小时前'
                parts.append(f'[距上次对话：{t_str}]')
            except:
                pass

    if mic_text:
        parts.append(mic_text.strip())
    return '\n'.join(parts) + '\n'


# ─── AI 记忆（按对话隔离） ──────────────────────────

def _memory_filepath(hisid, username="anonymous"):
    if not hisid: return os.path.join(COMPANION_MEMORY_DIR, f'{username}_memory.md')
    # 临时对话与普通对话共享同一份 AI 记忆（按用户名）
    if hisid.startswith('_t_'):
        return os.path.join(COMPANION_MEMORY_DIR, f'{username}_memory.md')
    return os.path.join(COMPANION_MEMORY_DIR, f'{hisid}_memory.md')


def read_companion_memory(hisid, username):
    fp = _memory_filepath(hisid, username)
    if not fp or not os.path.exists(fp):
        return '# AI 记忆\n\n（暂无记忆内容）'
    with open(fp, 'r', encoding='utf-8') as f:
        return f.read()


def write_companion_memory(hisid, content, username):
    fp = _memory_filepath(hisid, username)
    if not fp:
        return False, '无对话ID'
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(fp, 'a', encoding='utf-8') as f:
        f.write(f'--- {ts} ---\n{content}\n\n')
    return True, '记忆已保存'


def overwrite_companion_memory(hisid, content,username):
    fp = _memory_filepath(hisid,username)
    if not fp:
        return False, '无对话ID'
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    return True, '记忆已更新'

@base_route
def ai():
    track_visit('AI对话')
    return web_page('ai.html')

@base_route
def aiold():
    ip=request.remote_addr
    username = userlist.get(str(ip), '')
    with requests.post(
        url='https://api.deepseek.com/chat/completions',
        headers = {
        "Authorization": f"Bearer {deepseek_api_key}",
        "Content-Type": "application/json"
        },
        data = json.dumps({
        "model": "deepseek-v4-flash",
        "messages": [
        {"role": "system", "content": str(request.args.get('sys'))},
        {"role": "user", "content": username}
        ],
        "stream": False,
        "temperature": float(request.args.get("temp",''))
        })
        ) as req:
            content = json.loads(req.content.decode())['choices'][-1]['message']['content']
    return {"content":content}
            

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
        "Authorization": f"Bearer {bocha_api_key}"
        }

        response = requests.request("POST", 'https://api.bocha.cn/v1/web-search', headers=headers, data=payload)
        try:
            result=json.loads(response.content.decode())
            searchResult=result['data']['webPages']['value'][:10]
            print(searchResult)
        except Exception as e:
            return f'{type(e)}:{str(e)},result:{result}'
        if searchResult:
            return str(searchResult)
        return 'nth searched'
    except Exception as e:
            print(e)
            return f"搜索时出错: {str(e)}"
    return '广州今天天气不太好，很闷热'

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


def _binarize_for_ocr(img: Image.Image) -> Image.Image:
    """
    对 OCR 输入图片做二值化预处理，专门针对灰纸黑字、印刷质量一般的场景。
    流程：灰度化 → 对比度拉伸 → OTSU 自适应二值化。
    """
    # 1. 转灰度
    img = img.convert('L')

    # 2. 对比度拉伸（增强明暗分离）
    arr = np.array(img, dtype=np.float64)
    lo, hi = np.percentile(arr, (2, 98))
    if hi > lo:
        arr = np.clip((arr - lo) / (hi - lo) * 255, 0, 255)
    arr = arr.astype(np.uint8)

    # 3. OTSU 自动阈值二值化
    hist, _ = np.histogram(arr, bins=256, range=(0, 256))
    total = arr.size
    sum_total = np.dot(np.arange(256), hist)
    sum_b = 0.0
    w_b = 0
    max_var = 0.0
    threshold = 0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        mean_b = sum_b / w_b
        mean_f = (sum_total - sum_b) / w_f
        var_between = w_b * w_f * (mean_b - mean_f) ** 2
        if var_between > max_var:
            max_var = var_between
            threshold = t

    binary = (arr > threshold).astype(np.uint8) * 255
    img_binary = Image.fromarray(binary, mode='L')
    return img_binary


@base_route
def ocr_image():
    """
    接收 base64 图片数据，使用 pytesseract 识别文字。
    POST body: { "image": "data:image/png;base64,..." } 或 { "image": "base64string" }
    返回: { "text": "识别出的文字" }
    """
    ip = request.remote_addr
    username = userlist.get(str(ip), '')
    if not username:
        return {"error": "No username provided"}, 400

    try:
        req_data = request.get_json()
        if not req_data or 'image' not in req_data:
            return {"error": "No image data"}, 400

        image_data = req_data['image']
        # 去掉 data:image/...;base64, 前缀
        if ',' in image_data:
            image_data = image_data.split(',')[1]

        img_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(img_bytes))

        # 图像预处理：针对灰纸黑字图片做二值化
        img = _binarize_for_ocr(img)

        # pytesseract 识别
        # 支持中文和英文
        text = pytesseract.image_to_string(img, lang='chi_sim')
        text = text.strip()
        if not text:
            text = "[未识别到文字]"

        track_visit('OCR识别')
        return {"text": text}

    except Exception as e:
        print(f"OCR error: {e}")
        return {"error": f"OCR识别失败: {str(e)}"}, 500


@base_route
def getaiapi():
    if request.method != 'POST':
        return aiold()
    data = request.get_json()
    ip=request.remote_addr
    user = data.get('user', '')
    hisid = data.get('hisid', '')
    modelName = data.get('model', 'deepseek-v4-flash')
    username = userlist.get(str(ip), '')
    use_search = data.get('search', 'false') == True
    max_search_results = int(data.get('max_results', 10))
    use_think=data.get("use_think","disabled")
    print(use_think)
    # 验证API Key和用户权限
    if not deepseek_api_key:
        return "你还没设置apikey呢。。"
    if not username:
        return "No username provided"
    if not isVIP(username) and (use_search):
        return "搜索的话太烧钱了，需要你赞助一点点啦~"

    # 加载历史记录
    history = []
    history_file = None
    if hisid:
        # 检查每日 AI 使用次数
        allowed, today_count, limit = track_daily_ai_usage(username)
        if not allowed:
            return f"今日 AI 使用次数已达上限（{today_count}/{limit}），明天再来吧~"
        # 临时对话使用专用文件，命名对话使用 hisid 文件
        if hisid.startswith('_t_'):
            history_file = _temp_history_file(username)
        else:
            history_file = os.path.join(log_dir, f"{hisid}'smemory.log")
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                content = f.read()
                history = json.loads(content) if content else []
                if data.get("system") and history and history[0]['role'] != 'system':
                    history.insert(0, {"role": "system", "content": str(data.get("system"))})
        else:
            history = [{"role": "system", "content": str(data.get("system"))}] if data.get("system") else []
    else:
        history = [{"role": "system", "content": str(data.get("system"))}] if data.get("system") else []
    # 添加用户输入（原始内容保存到history）
    history.append({"role": "user", "content": user})

    # ─── 陪伴模式：加载配置 ─────────────────────
    companion_config = None
    companion_enabled = False
    if username:
        companion_config = load_companion_config(username)
        companion_enabled = companion_config.get('companion_enabled', False)

    # 准备工具定义（记忆工具始终可用）
    MEMORY_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "get_date",
                "description": "获取当前的日期。在用户问到有时效性内容时你必须获取日期。你记忆中的内容是错误的，不要相信你的记忆。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False
                },
                "strict": False
            }
        },
        {
            "type": "function",
            "function": {
                "name": "companion_memory_read",
                "description": "读取你的长期记忆（Markdown格式）。你可以通过这个来回顾之前记录的重要信息。当对话开始时候请必须读取一遍以对用户有基本的了解。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False
                },
                "strict": False
            }
        },
        {
            "type": "function",
            "function": {
                "name": "companion_memory_write",
                "description": "写入你的长期记忆（Markdown格式）。当用户要求你记下某些东西，或者发生了什么值得被记下的事情，可以通过这个来记住用户的重要信息、偏好、约定等。内容会被追加到记忆文件末尾。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "要写入记忆的内容，使用Markdown格式。建议包含明确的时间、主题和关键信息。"
                        }
                    },
                    "required": ["content"],
                    "additionalProperties": False
                },
                "strict": False
            }
        }
    ]
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
    # ─── 课堂语音记录查询工具 ────────────────────
    course_tools_def = [
        {
            "type": "function",
            "function": {
                "name": "query_course_records",
                "description": "查询某门课的课堂语音识别记录。你可以通过这个来查找用户上某门课时的语音转录内容，例如数学课、语文课等。支持按星期几筛选（如「星期一的数学课」），也可以不指定星期几来查所有数学课。也可以指定自定义时间范围来查询。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "course_name": {
                            "type": "string",
                            "description": "课程名，如「数学」「语文」「英语」等。留空则返回该天的所有课程记录。"
                        },
                        "weekday": {
                            "type": "string",
                            "description": "星期几，可选：星期一/星期二/…/星期日、周一/周二/…/周日、monday/tuesday/…/sunday、或者纯数字0-6（0=周一）。省略则默认为今天。"
                        },
                        "date": {
                            "type": "string",
                            "description": "具体日期，格式 YYYY-MM-DD，如 2026-06-22。设置了 date 后 weekday 参数会被忽略。"
                        },
                        "start_time": {
                            "type": "string",
                            "description": "自定义查询起始时间，格式 HH:MM，如 08:00。需与 end_time 成对使用。"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "自定义查询结束时间，格式 HH:MM，如 09:30。需与 start_time 成对使用。"
                        }
                    },
                    "required": [],
                    "additionalProperties": False
                },
                "strict": False
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_mic2text_keyword",
                "description": "在课堂语音识别记录中搜索关键词。\n适合以下场景：\n- 用户问「老师刚才有没有提到XXX？」\n- 用户想查一下课堂上某个知识点、公式、术语有没有被讲过\n- 用户想回顾某节课中关于某个话题的讨论内容\n\n支持模糊匹配（输入关键词的一部分也能搜到），会返回匹配句及其附近上下文，方便你理解该关键词出现的语境。最多返回5条匹配。\n\n如果不确定是哪门课、哪天，可以只传关键词，会搜索今天所有课堂记录。如果知道大概的课程或时间，填写 course_name、weekday 或 date 可以缩小范围、提高准确度。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "搜索关键词。支持模糊匹配（子串匹配，不区分大小写），输入关键词的一部分也能搜到。必填。"
                        },
                        "course_name": {
                            "type": "string",
                            "description": "限定搜索范围：课程名，如「数学」「语文」「英语」。不填则搜索该天所有课程。"
                        },
                        "weekday": {
                            "type": "string",
                            "description": "限定搜索范围：星期几，可选：星期一/星期二/…/星期日、周一/周二/…/周日、monday/tuesday/…/sunday、或者纯数字0-6（0=周一）。省略则搜索今天。"
                        },
                        "date": {
                            "type": "string",
                            "description": "限定搜索范围：具体日期，格式 YYYY-MM-DD，如 2026-06-22。设置了 date 后 weekday 参数会被忽略。"
                        },
                        "start_time": {
                            "type": "string",
                            "description": "限定搜索范围：起始时间，格式 HH:MM，如 08:00。需与 end_time 成对使用。"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "限定搜索范围：结束时间，格式 HH:MM，如 09:30。需与 start_time 成对使用。"
                        }
                    },
                    "required": ["keyword"],
                    "additionalProperties": False
                },
                "strict": False
            }
        }
    ]
    
    all_tools = list(MEMORY_TOOLS)
    if course_tools_def:
        all_tools.extend(course_tools_def)
    if use_search:
        all_tools.extend(search_tools)
    tools = all_tools if all_tools else None
    tool_choice = "auto" if tools else None

    max_iterations = 20
    total_cost = 0
    # 陪伴模式：上下文先写入 history（会存盘，后续加载时 AI 能看到）
    if companion_enabled and companion_config:
        companion_context = build_companion_context(companion_config, username, hisid)
        # 修改 history 中最后一条用户消息，添加陪伴上下文
        for i in range(len(history) - 1, -1, -1):
            if history[i]["role"] == "user":
                history[i]["content"] = companion_context + history[i]["content"]
                break
    # 深拷贝：api_messages 独立于 history，工具循环中的修改不会污染 history
    api_messages = copy.deepcopy(history)
    # 去除思考内容（仅对 api_messages 生效，不影响 history）
    for i in api_messages:
        if i["role"]=="assistant" and i.get("reasoning_content",False):
            i.pop("reasoning_content")
    # 记录工具调用的提示文本，用于写入历史（不含具体返回值）
    tool_display_texts = {}  # {tool_call_id: "📖 读取AI记忆..."}
    # 流式生成器
    def generate():
        nonlocal total_cost
        accumulated_content=''
        accumulated_reasoning=''
        try:
            for iteration in range(max_iterations):
                # 构建请求
                api_data = {
                    "model": modelName,
                    "messages": api_messages,
                    "stream": True,  # 启用流式
                    "temperature": float(str(data.get("temp"))) if data.get("temp") else 0.7,
                    "thinking":{"type":use_think}
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
                        if req.status_code != 200:
                            yield f"请求失败，状态码: {req.status_code},信息：{str(req.json())}"
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
                        if usage and modelName=="deepseek-v4-flash":
                            cost = (usage.get('completion_tokens', 0) / 1000000 * 2
                                    + usage.get('prompt_cache_hit_tokens', 0) / 1000000 * 0.02
                                    + usage.get('prompt_cache_miss_tokens', 0) / 1000000 * 1)
                            total_cost += cost
                        elif usage and modelName=="deepseek-v4-pro":
                            cost = (usage.get('completion_tokens', 0) / 1000000 * 6
                                    + usage.get('prompt_cache_hit_tokens', 0) / 1000000 * 0.025
                                    + usage.get('prompt_cache_miss_tokens', 0) / 1000000 * 3)
                            total_cost += cost

                        # 如果有工具调用
                        if tool_calls:
                            print('tool calls')
                            # 构建assistant消息（含工具调用）
                            assistant_message = {
                                "role": "assistant",
                                "content": accumulated_content or None,
                                "reasoning_content": accumulated_reasoning or None,
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
                                    prompt = (f"\n🔍 正在搜索：{query}...\n"
                                              f"\n✅ 搜索结果已获取\n")
                                    yield prompt
                                    tool_display_texts[tc['id']] = prompt
                                    search_result = execute_web_search(query, max_results)
                                    api_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc['id'],
                                        "content": search_result
                                    })
                                    total_cost += 0.0036
                                elif tc['name'] == 'get_date':
                                    yield "📅正在获取日期"
                                    date=str(datetime.date.today())
                                    api_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc['id'],
                                        "content": date
                                    })
                                elif tc['name'] == 'open_link':
                                    link = args.get('link', '')
                                    prompt = (f"\n🔗 正在打开链接：{link}...\n"
                                              f"\n✅ 链接内容已获取\n")
                                    yield prompt
                                    tool_display_texts[tc['id']] = prompt
                                    open_result = open_link(link)
                                    api_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc['id'],
                                        "content": open_result
                                    })
                                elif tc['name'] == 'companion_memory_read':
                                    prompt = "\n📖 读取AI记忆...\n"
                                    yield prompt
                                    tool_display_texts[tc['id']] = prompt
                                    memory_content = read_companion_memory(hisid, username)
                                    api_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc['id'],
                                        "content": f"当前对话的AI记忆内容：\n\n{memory_content}"
                                    })
                                elif tc['name'] == 'companion_memory_write':
                                    content = args.get('content', '')
                                    ok, msg = write_companion_memory(hisid, content, username)
                                    prompt = f"\n💾 AI记忆已更新：{msg}\n"
                                    yield prompt
                                    tool_display_texts[tc['id']] = prompt
                                    api_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc['id'],
                                        "content": msg
                                    })
                                elif tc['name'] == 'query_course_records':
                                    course_name = args.get('course_name', '')
                                    weekday = args.get('weekday', None)
                                    date = args.get('date', None)
                                    start_time = args.get('start_time', None)
                                    end_time = args.get('end_time', None)
                                    
                                    desc_parts = []
                                    if course_name:
                                        desc_parts.append(f'课程「{course_name}」')
                                    if date:
                                        desc_parts.append(f'日期 {date}')
                                    elif weekday:
                                        desc_parts.append(f'{weekday}')
                                    if start_time and end_time:
                                        desc_parts.append(f'{start_time}-{end_time}')
                                    prompt = f"\n🔍 正在查询课堂语音记录：{'，'.join(desc_parts) if desc_parts else '全部课程'}...\n"
                                    yield prompt
                                    tool_display_texts[tc['id']] = prompt
                                    
                                    result = query_course_records_by_user(
                                        username, course_name, weekday, date, start_time, end_time
                                    )
                                    api_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc['id'],
                                        "content": json.dumps(result, ensure_ascii=False)
                                    })
                                elif tc['name'] == 'search_mic2text_keyword':
                                    keyword = args.get('keyword', '')
                                    course_name = args.get('course_name', None)
                                    weekday = args.get('weekday', None)
                                    date = args.get('date', None)
                                    start_time = args.get('start_time', None)
                                    end_time = args.get('end_time', None)
                                    
                                    desc_parts = [f'关键词「{keyword}」']
                                    if course_name:
                                        desc_parts.append(f'限定课程「{course_name}」')
                                    if date:
                                        desc_parts.append(f'日期 {date}')
                                    elif weekday:
                                        desc_parts.append(f'{weekday}')
                                    if start_time and end_time:
                                        desc_parts.append(f'{start_time}-{end_time}')
                                    prompt = f"\n🔍 正在搜索课堂语音中的关键词：{'，'.join(desc_parts)}...\n"
                                    yield prompt
                                    tool_display_texts[tc['id']] = prompt
                                    
                                    result = search_course_records_by_keyword(
                                        username, keyword, course_name,
                                        weekday, date, start_time, end_time
                                    )
                                    api_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc['id'],
                                        "content": json.dumps(result, ensure_ascii=False)
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
                    print('finalizing response')
                    # 从 api_messages 构建存盘历史：保留用户+助理消息，跳过 tool result
                    saved_history = []
                    for msg in api_messages:
                        if msg.get("role") == "tool":
                            continue  # 跳过工具具体返回值
                        entry: dict = copy.deepcopy(msg)
                        # 助理消息含有工具调用时，附加上提示文本（如"📖 读取AI记忆..."）
                        if entry["role"] == "assistant" and entry.get("tool_calls"):
                            extra = ""
                            names = []
                            for tc in entry["tool_calls"]:
                                if tc.get("id") in tool_display_texts:
                                    extra += tool_display_texts[tc["id"]]
                                fn = tc.get("function", {})
                                names.append(fn.get("name", tc.get("name", "?")))
                            if names:
                                extra += "（调用：" + "、".join(names) + "）"
                            entry["content"] = (entry["content"] or "") + extra
                            del entry["tool_calls"]
                        saved_history.append(entry)
                    # 最终回复
                    final_content = accumulated_content
                    if accumulated_reasoning:
                        saved_history.append({"role": "assistant", "content": final_content, "reasoning_content": accumulated_reasoning})
                    elif final_content:
                        saved_history.append({"role": "assistant", "content": final_content})
                    if hisid and history_file:
                        # 临时对话（_t_开头）也保存历史
                        plus_ai_usage(username)
                        with open(history_file, 'w', encoding='utf-8') as f:
                            f.write(json.dumps(saved_history, ensure_ascii=False))
                    money_file = os.path.join(log_dir, "moneys.json")
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

@args_route
def gethistory(id):
    filepath = os.path.join(log_dir, f'{id}\'smemory.log')
    if id.startswith('_t_'):
        username = userlist.get(str(request.remote_addr), '')
        if not username:
            return "what are you doing?", 400
        filepath = _temp_history_file(username)
    with open(filepath,'r',encoding='utf-8') as file:
        content=file.read()
        if not content: return json.dumps([], ensure_ascii=False)
        # 解析历史，为每条消息添加 id（数组索引），隐藏 system 消息
        history = json.loads(content)
        result = []
        for i, msg in enumerate(history):
            if msg.get('role') == "assistant" and msg.get("reasoning_content",False):
                msg["content"]=f"# 思考：\n {msg.pop('reasoning_content')} \n # 回答：\n{msg['content']}"
            result.append({**msg, 'id': i})
        return json.dumps(result, ensure_ascii=False)

@base_route
def update_history():
    """
    修改对话历史：编辑或删除消息。
    POST 接收 JSON: {hisid, action, index, content?}
    - action="edit": 修改 index 处的消息内容
    - action="delete": 删除 index 处的消息
    返回更新后的消息列表（带 id，不含 system）
    """
    data = request.get_json()
    hisid = data.get('hisid')
    action = data.get('action')
    index = data.get('index')
    content = data.get('content', '')

    if not hisid or not action or index is None:
        return 'Missing parameters', 400

    history_file = os.path.join(log_dir, f"{hisid}'smemory.log")
    if hisid.startswith('_t_'):
        username = userlist.get(str(request.remote_addr), '')
        if not username:
            return 'No username provided', 400
        history_file = _temp_history_file(username)
    if not os.path.exists(history_file):
        return 'History not found', 404

    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.loads(f.read())

    if index < 0 or index >= len(history):
        return 'Invalid index', 400

    if action == 'edit':
        history[index]['content'] = content
    elif action == 'delete':
        history.pop(index)
    elif action == 'retry':
        history = history[:index]
    else:
        return 'Invalid action', 400
    result = []
    with open(history_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(history, ensure_ascii=False))
    for i, msg in enumerate(history):
            if msg.get('role') == "assistant" and msg.get("reasoning_content",False):
                msg["content"]=f"# 思考： {msg.pop('reasoning_content')} \n # 回答：{msg['content']}"
            result.append({**msg, 'id': i})
    return json.dumps(result, ensure_ascii=False)

@base_route
def getMoney():
    username = userlist.get(str(request.remote_addr),'')
    if not username:
        return "No username provided"
    money_file = os.path.join(log_dir, f"moneys.json")
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


# ─── 陪伴模式 API ────────────────────────────────

@base_route
def api_get_companion_config():
    """GET: 获取当前用户的陪伴模式配置"""
    ip = request.remote_addr
    username = userlist.get(str(ip), '')
    if not username:
        return '{"error":"No username"}', 400
    config = load_companion_config(username)
    # 计算当前课表状态
    class_name = get_current_schedule_status(config)
    now = datetime.datetime.now()
    day_cn = _CHINESE_DAYS[now.weekday()]
    time_str = now.strftime(f'%Y年%m月%d日 {day_cn} %H:%M')
    result = {
        **config,
        'username': username,
        'current_time': time_str,
        'current_class': class_name if class_name else '下课',
        'in_class': class_name is not None
    }
    return json.dumps(result, ensure_ascii=False)


@base_route
def api_save_companion_config():
    """POST: 保存当前用户的陪伴模式配置"""
    ip = request.remote_addr
    username = userlist.get(str(ip), '')
    if not username:
        return '{"error":"No username"}', 400
    data = request.get_json()
    if not data:
        return '{"error":"No data"}', 400
    # 合并更新
    current = load_companion_config(username)
    if 'companion_enabled' in data:
        current['companion_enabled'] = bool(data['companion_enabled'])
    if 'user_status' in data:
        current['user_status'] = str(data['user_status'])
    if 'week_schedule' in data:
        schedule = data['week_schedule']
        # 验证结构
        if isinstance(schedule, dict):
            for day in _ENGLISH_DAYS:
                if day not in schedule:
                    schedule[day] = []
            current['week_schedule'] = schedule
    if 'mic2text_show_in_chat' in data:
        current['mic2text_show_in_chat'] = bool(data['mic2text_show_in_chat'])
    if 'mic2text_in_context' in data:
        current['mic2text_in_context'] = bool(data['mic2text_in_context'])
    if 'show_time_elapsed' in data:
        current['show_time_elapsed'] = bool(data['show_time_elapsed'])
    if 'temp_chat_enabled' in data:
        current['temp_chat_enabled'] = bool(data['temp_chat_enabled'])
    save_companion_config(username, current)
    return json.dumps({'success': True, 'config': current}, ensure_ascii=False)


@args_route
def api_get_companion_memory():
    """GET: 获取某个对话的AI记忆内容"""
    hisid=request.args.get('hisid', '')
    ip = request.remote_addr
    username = userlist.get(str(ip), '')
    if not username:
        return '{"error":"No username"}', 400
    content = read_companion_memory(hisid, username)
    return json.dumps({'hisid': hisid, 'content': content}, ensure_ascii=False)


@args_route
def api_save_companion_memory():
    """POST: 覆盖保存某个对话的AI记忆内容"""
    hisid=request.args.get('hisid', '')
    ip = request.remote_addr
    username = userlist.get(str(ip), '')
    if not username:
        return '{"error":"No username"}', 400
    data = request.get_json()
    if not data or 'content' not in data:
        return '{"error":"No content"}', 400
    ok, msg = overwrite_companion_memory(hisid, data['content'], username)
    if ok:
        return json.dumps({'success': True, 'message': msg}, ensure_ascii=False)
    else:
        return json.dumps({'success': False, 'error': msg}, ensure_ascii=False)

def _temp_history_file(username):
    """返回用户的临时对话历史文件路径"""
    return os.path.join(TEMP_CHAT_DIR, f"{username}.log")

@args_route
def clear_temp_history():
    """清空用户的临时对话历史"""
    ip = request.remote_addr
    username = userlist.get(str(ip), '')
    fp = _temp_history_file(username)
    if os.path.exists(fp):
        os.remove(fp)
    return json.dumps({'success': True}, ensure_ascii=False)


@base_route
def api_query_course_records():
    """
    GET: 查询课堂语音记录
    参数：
        course: str - 课程名
        weekday: str (可选) - 星期几
        date: str (可选) - 具体日期 YYYY-MM-DD
        start: str (可选) - 自定义起始时间 HH:MM
        end: str (可选) - 自定义结束时间 HH:MM
    """
    ip = request.remote_addr
    username = userlist.get(str(ip), '')
    if not username:
        return json.dumps({'error': 'No username'}, ensure_ascii=False)
    course = request.args.get('course', '')
    weekday = request.args.get('weekday', None)
    date = request.args.get('date', None)
    start = request.args.get('start', None)
    end = request.args.get('end', None)
    result = query_course_records_by_user(username, course, weekday, date, start, end)
    return json.dumps(result, ensure_ascii=False)


@base_route
def api_search_mic2text_keyword():
    """
    GET/POST: 在课堂语音记录中搜索关键词，模糊匹配，返回附近上下文。

    GET 参数：
        keyword: str (必填) - 搜索关键词
        course: str (可选) - 限定课程名
        weekday: str (可选) - 星期几
        date: str (可选) - 具体日期 YYYY-MM-DD
        start: str (可选) - 起始时间 HH:MM
        end: str (可选) - 结束时间 HH:MM
        max_results: int (可选) - 最多返回几条，默认5

    POST body 支持相同字段。
    """
    ip = request.remote_addr
    username = userlist.get(str(ip), '')
    if not username:
        return json.dumps({'error': 'No username'}, ensure_ascii=False)

    if request.method == 'POST':
        data = request.get_json() or {}
        keyword = data.get('keyword', request.args.get('keyword', ''))
        course = data.get('course', request.args.get('course', None))
        weekday = data.get('weekday', request.args.get('weekday', None))
        date = data.get('date', request.args.get('date', None))
        start = data.get('start', request.args.get('start', None))
        end = data.get('end', request.args.get('end', None))
    else:
        keyword = request.args.get('keyword', '')
        course = request.args.get('course', None)
        weekday = request.args.get('weekday', None)
        date = request.args.get('date', None)
        start = request.args.get('start', None)
        end = request.args.get('end', None)

    result = search_course_records_by_keyword(
        username, keyword, course, weekday, date, start, end
    )
    return json.dumps(result, ensure_ascii=False)


@base_route
def api_get_mic2text():
    """GET: 从 mic2text 服务获取最近 N 句转录（前端轮询用）"""
    ip = request.remote_addr
    username = userlist.get(str(ip), '')
    if not username:
        return '{"error":"No username"}', 400
    try:
        n = request.args.get('n', 5, type=int)
    except:
        n = 5
    if not mic2text_url:
        return json.dumps({'recent_sentences': [], 'error': 'mic2text not configured'}, ensure_ascii=False)
    try:
        # mic2text 服务实际路由为 /query，返回 {texts: ["句子1", "句子2"...]}
        url = f'{mic2text_url}/query'
        with urllib.request.urlopen(url, timeout=5) as resp:
            raw = json.loads(resp.read())
        # 转换为前端面板期望的格式 {recent_sentences: [{text: "句子1"}...]}
        texts = raw.get('texts', [])
        recent = [{'text': t} for t in texts]
        return json.dumps({'recent_sentences': recent}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'recent_sentences': [], 'error': str(e)}, ensure_ascii=False)
