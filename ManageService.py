"""
Management Service - 管理页面后端 API

为管理页面提供所有后端接口，包括：
- 用户管理 (IP↔用户名)
- 服务器状态切换
- 服务器密码管理
- AI 用钱管理
- VIP 状态管理
- 功能开关管理
- 上课禁用 & 课表编辑
- 访问记录查看
- AI 历史记录查看
- 每日 AI 使用次数管理

所有设置统一保存在 logs/server_config.json 中，方便管理面板直接编辑。
"""
import os
import json
import datetime
import sys
from flask import request, send_from_directory

import config as config_module
from config import (
    root, log_dir, pages_dir, serverStatus, userlist,
    forbidden_time, forbidden_time1, DEFAULT_WEEK_SCHEDULE
)
from tools import verifier, change_userlist, base_route

# ─── 统一配置文件 ────────────────────────────────────
# 所有可编辑的设置全部保存在这一个 JSON 文件里
SERVER_CONFIG_FILE = os.path.join(log_dir, "server_config.json")

# 访问日志单独保存（日志量大，不混入配置）
ACCESS_VISITS_FILE = os.path.join(log_dir, "access_visits.json")

# AI 每日使用次数独立文件（从 server_config.json 中分离）
DAILY_AI_USAGE_FILE = os.path.join(log_dir, "daily_ai_usage.json")

# ─── 默认配置 ────────────────────────────────────

_DEFAULT_CONFIG = {
    "features": {
        "ai": True,
        "talk": True,
        "music": True,
        "games": True,
        "file_sharing": True,
        "game_class_ban": True,
        "ai_daily_limit": True,
        "guest_access": False,
    },
    "schedule_active": "default",
    "ai_limit_per_day": 10,
}


def _load_json(filepath, default=None):
    """安全加载 JSON 文件，不存在或损坏时返回 default"""
    if default is None:
        default = {}
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return default


def _save_json(filepath, data):
    """安全保存 JSON 文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── 统一配置读写 ────────────────────────────────

def _load_config():
    """加载统一配置 server_config.json，不存在则用默认值"""
    cfg = _load_json(SERVER_CONFIG_FILE, _DEFAULT_CONFIG)
    # 确保所有默认字段存在，防止旧配置缺字段
    for key, val in _DEFAULT_CONFIG.items():
        if key not in cfg:
            cfg[key] = val
    return cfg


def _save_config(cfg):
    """保存统一配置"""
    _save_json(SERVER_CONFIG_FILE, cfg)


def _get_feature(key, default=True):
    """取某个功能开关的值"""
    cfg = _load_config()
    return cfg.get("features", {}).get(key, default)


def _get_active_schedule():
    """获取当前激活的课表 ID ('default' 或 'backup')"""
    cfg = _load_config()
    return cfg.get("schedule_active", "default")


def _set_active_schedule(name):
    """设置当前激活的课表"""
    cfg = _load_config()
    cfg["schedule_active"] = name
    _save_config(cfg)


def _get_daily_usage():
    """获取每日 AI 使用次数字典（独立文件）"""
    return _load_json(DAILY_AI_USAGE_FILE, {})


def _save_daily_usage(usage):
    """保存每日 AI 使用次数到独立文件 daily_ai_usage.json"""
    _save_json(DAILY_AI_USAGE_FILE, usage)


def _get_limit_per_day():
    """获取每日 AI 限制次数"""
    cfg = _load_config()
    return cfg.get("ai_limit_per_day", 10)


# ─── 工具函数 ────────────────────────────────────

def _admin_required():
    """检查是否为管理员（需要密码参数 ?p=xxx）"""
    level = verifier(str(request.args.get("p", "")), str(request.remote_addr))
    return level == 2


def _require_admin():
    """装饰器风格的权限检查，不通过时返回 404"""
    if not _admin_required():
        return None
    return True


# ─── 01. 管理页面 ────────────────────────────────

@base_route
def manage_page():
    """返回管理页面 HTML"""
    if not os.path.exists(os.path.join(pages_dir, "manage.html")):
        return "manage.html not found", 404
    return send_from_directory(pages_dir, "manage.html")


# ─── 02. 用户管理 ────────────────────────────────

def api_get_users():
    """获取用户列表 [{ip, username}, ...]"""
    if not _require_admin():
        return "Illegal request", 404
    users = []
    for ip, username in userlist.items():
        users.append({"ip": ip, "username": username})
    return json.dumps(users, ensure_ascii=False)


def api_update_user():
    """更新单个用户：PUT JSON {ip, username}"""
    if not _require_admin():
        return "Illegal request", 404
    data = request.get_json()
    ip = data.get("ip", "")
    username = data.get("username", "")
    if not ip:
        return '{"error": "IP required"}', 400
    change_userlist("add", ip, username, self_call=True)
    return json.dumps({"success": True, "ip": ip, "username": username}, ensure_ascii=False)


def api_delete_user():
    """删除用户：DELETE JSON {ip}"""
    if not _require_admin():
        return "Illegal request", 404
    data = request.get_json()
    ip = data.get("ip", "")
    if not ip:
        return '{"error": "IP required"}', 400
    change_userlist("remove", ip, "", self_call=True)
    return json.dumps({"success": True, "ip": ip}, ensure_ascii=False)


# ─── 03. 服务器状态 ────────────────────────────────

def api_get_server_status():
    """获取服务器状态 {status: 0|1}"""
    if not _require_admin():
        return "Illegal request", 404
    return json.dumps({"status": serverStatus()}, ensure_ascii=False)


def api_set_server_status():
    """设置服务器状态：POST JSON {status: 0|1}"""
    if not _require_admin():
        return "Illegal request", 404
    data = request.get_json()
    new_status = data.get("status", 1)
    serverStatus.set_value(1 if new_status else 0)
    return json.dumps({"success": True, "status": serverStatus()}, ensure_ascii=False)


# ─── 04. 密码管理 ────────────────────────────────

def api_change_password():
    """修改管理密码：POST JSON {new_password}"""
    if not _require_admin():
        return "Illegal request", 404
    data = request.get_json()
    new_pw = data.get("new_password", "")
    if not new_pw or len(new_pw) < 4:
        return '{"error": "密码至少 4 位"}', 400

    pw_file = os.path.join(root, ".admin_password")
    with open(pw_file, "w", encoding="utf-8") as f:
        f.write(new_pw)
    config_module.password = new_pw

    return json.dumps({
        "success": True,
        "message": "密码已更新（重启后仍有效）"
    }, ensure_ascii=False)


# ─── 05. 用钱管理 / VIP ────────────────────────────────

def api_get_money_data():
    """获取所有用户的用钱数据"""
    if not _require_admin():
        return "Illegal request", 404
    data = _load_json(os.path.join(log_dir, "moneys.json"), {})
    return json.dumps(data, ensure_ascii=False)


def api_update_money():
    """更新用户用钱：POST JSON {username, money}"""
    if not _require_admin():
        return "Illegal request", 404
    data = request.get_json()
    username = data.get("username", "")
    new_money = float(data.get("money", 0))
    if not username:
        return '{"error": "username required"}', 400

    MONEY_FILE = os.path.join(log_dir, "moneys.json")
    money_data = _load_json(MONEY_FILE, {})
    if username not in money_data:
        money_data[username] = {"money": 0, "isVIP": False}
    money_data[username]["money"] = round(new_money, 6)
    _save_json(MONEY_FILE, money_data)
    return json.dumps({
        "success": True,
        "username": username,
        "money": money_data[username]["money"]
    }, ensure_ascii=False)


def api_set_vip():
    """设置/取消 VIP：POST JSON {username, vip: true|false}"""
    if not _require_admin():
        return "Illegal request", 404
    data = request.get_json()
    username = data.get("username", "")
    is_vip = bool(data.get("vip", False))
    if not username:
        return '{"error": "username required"}', 400

    MONEY_FILE = os.path.join(log_dir, "moneys.json")
    money_data = _load_json(MONEY_FILE, {})
    if username not in money_data:
        money_data[username] = {"money": 0, "isVIP": False}
    money_data[username]["isVIP"] = is_vip
    _save_json(MONEY_FILE, money_data)
    return json.dumps({
        "success": True,
        "username": username,
        "isVIP": is_vip
    }, ensure_ascii=False)


# ─── 06. 功能开关管理 ────────────────────────────────

def api_get_features():
    """获取功能开关状态"""
    if not _require_admin():
        return "Illegal request", 404
    cfg = _load_config()
    return json.dumps(cfg.get("features", {}), ensure_ascii=False)


def api_set_features():
    """设置功能开关：POST JSON {feature_name: true|false, ...}"""
    if not _require_admin():
        return "Illegal request", 404
    data = request.get_json()
    cfg = _load_config()
    for key, value in data.items():
        cfg["features"][key] = bool(value)
    _save_config(cfg)
    return json.dumps({"success": True, "features": cfg["features"]}, ensure_ascii=False)


# ─── 07. 上课禁用课表 ────────────────────────────────

def api_get_schedule():
    """获取上课禁用课表
    返回: {"schedule": {...}, "backup_schedule": {...}, "active": "default"|"backup"}
    """
    if not _require_admin():
        return "Illegal request", 404
    active = _get_active_schedule()
    schedule = {s: e for s, e in forbidden_time.items()}
    backup = {s: e for s, e in forbidden_time1.items()}
    return json.dumps({
        "schedule": schedule,
        "backup_schedule": backup,
        "active": active
    }, ensure_ascii=False)


def api_set_schedule():
    """设置上课禁用课表：POST JSON {schedule: {...}, active: "default"|"backup"}"""
    if not _require_admin():
        return "Illegal request", 404
    data = request.get_json() or {}

    # 更新激活状态
    if "active" in data:
        _set_active_schedule(data["active"])
        cur = data["active"]
    else:
        cur = _get_active_schedule()

    # 更新课表内容
    if "schedule" in data:
        new_sched = dict(data["schedule"])
        if cur == "default":
            forbidden_time.set_value(new_sched)
        else:
            forbidden_time1.set_value(new_sched)

    active = _get_active_schedule()
    schedule = {s: e for s, e in forbidden_time.items()}
    backup = {s: e for s, e in forbidden_time1.items()}
    return json.dumps({
        "success": True,
        "schedule": schedule,
        "backup_schedule": backup,
        "active": active
    }, ensure_ascii=False)


# ─── 08. 访问记录 ────────────────────────────────

def api_get_access_log():
    """
    获取访问记录
    GET: ?page=1&per_page=50&sort=time_desc
    返回: {total, page, total_pages, records[{time, page, username, ip, raw}]}
    """
    if not _require_admin():
        return "Illegal request", 404

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    sort = request.args.get("sort", "time_desc")

    records = []

    # access_visits.json
    visits = _load_json(ACCESS_VISITS_FILE, [])
    for v in visits:
        records.append({
            "time": v.get("time", ""),
            "page": v.get("page", ""),
            "username": v.get("username", ""),
            "ip": v.get("ip", ""),
            "raw": f"[{v.get('time','')}] {v.get('page','')} - {v.get('username','')} ({v.get('ip','')})"
        })

    if sort == "time_desc":
        records.sort(key=lambda r: r.get("time", ""), reverse=True)
    elif sort == "time_asc":
        records.sort(key=lambda r: r.get("time", ""))

    total = len(records)
    start = (page - 1) * per_page
    end = start + per_page

    return json.dumps({
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
        "records": records[start:end]
    }, ensure_ascii=False)


# ─── 09. AI 历史记录 ────────────────────────────────

def api_get_ai_history():
    """
    获取 AI 历史记录列表
    GET: ?sort=time_desc&page=1&per_page=20
    返回: {total, page, total_pages, sessions[{username, msg_count, total_chars, mtime, ...}]}
    """
    if not _require_admin():
        return "Illegal request", 404

    sort = request.args.get("sort", "time_desc")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    sessions = []
    if os.path.exists(log_dir):
        for fname in os.listdir(log_dir):
            if fname.endswith("'smemory.log"):
                filepath = os.path.join(log_dir, fname)
                stat = os.stat(filepath)
                username = fname.split("'")[0]
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        history = json.loads(content) if content else []
                except Exception:
                    history = []

                msg_count = len([m for m in history if m.get("role") != "system"])
                total_chars = sum(len(m.get("content", "")) for m in history if m.get("role") != "system")
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                with open(filepath, "r", encoding="utf-8") as f:
                    raw_content = f.read()

                sessions.append({
                    "id": username,
                    "filename": fname,
                    "username": username,
                    "msg_count": msg_count,
                    "total_chars": total_chars,
                    "mtime": mtime,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "preview_content": raw_content
                })

    if sort == "time_desc":
        sessions.sort(key=lambda x: x["mtime"], reverse=True)
    elif sort == "time_asc":
        sessions.sort(key=lambda x: x["mtime"])
    elif sort == "length_desc":
        sessions.sort(key=lambda x: x["total_chars"], reverse=True)
    elif sort == "length_asc":
        sessions.sort(key=lambda x: x["total_chars"])

    total = len(sessions)
    start = (page - 1) * per_page
    end = start + per_page

    return json.dumps({
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
        "sessions": sessions[start:end]
    }, ensure_ascii=False)


# ─── 10. 每日 AI 使用次数管理 ────────────────────────────────

def api_get_daily_usage():
    """获取每日 AI 使用次数统计"""
    if not _require_admin():
        return "Illegal request", 404
    usage = _get_daily_usage()
    return json.dumps(usage, ensure_ascii=False)


def api_update_daily_usage():
    """修改每日 AI 使用次数：POST JSON {date, username, count}"""
    if not _require_admin():
        return "Illegal request", 404
    data = request.get_json()
    target_date = data.get("date", "")
    username = data.get("username", "")
    count = int(data.get("count", 0))
    if not target_date or not username:
        return '{"error": "date and username required"}', 400

    usage = _get_daily_usage()
    if target_date not in usage:
        usage[target_date] = {}
    usage[target_date][username] = max(0, count)
    _save_daily_usage(usage)
    return json.dumps({
        "success": True,
        "date": target_date,
        "username": username,
        "count": usage[target_date][username]
    }, ensure_ascii=False)


def api_reset_daily_usage():
    """重置某用户/所有用户今日使用次数：POST JSON {username?}"""
    if not _require_admin():
        return "Illegal request", 404
    data = request.get_json() or {}
    username = data.get("username", "")
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    usage = _get_daily_usage()

    if username:
        if today_str in usage and username in usage[today_str]:
            usage[today_str][username] = 0
        result = {"reset_for": username}
    else:
        if today_str in usage:
            for u in usage[today_str]:
                usage[today_str][u] = 0
        result = {"reset_for": "all"}

    _save_daily_usage(usage)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


# ─── 10b. 每日 AI 限制次数设置 ──────────────────────────

def api_save_limit():
    """修改每日 AI 限制次数：POST JSON {ai_limit_per_day: 10}"""
    if not _require_admin():
        return "Illegal request", 404
    data = request.get_json() or {}
    limit = int(data.get("ai_limit_per_day", 10))
    if limit < 1:
        limit = 1
    if limit > 999:
        limit = 999
    cfg = _load_config()
    cfg["ai_limit_per_day"] = limit
    _save_config(cfg)
    return json.dumps({"success": True, "ai_limit_per_day": limit}, ensure_ascii=False)


# ─── 11. AI 可用性查询（前台页面调用，无需管理员权限） ─────────

def api_check_ai_available():
    """
    前台 AI 页面的预检接口，返回当前用户是否可以继续使用 AI。
    不需要管理员密码，按 IP 识别用户。

    GET: ?username=xxx
    返回: {allowed: bool, count: int, limit: int, limit_enabled: bool}
    """
    username = request.args.get("username", "")
    ip_username = userlist.get(str(request.remote_addr), "")
    # 优先用参数提供的用户名，其次用 IP 对应的用户名
    username = username or ip_username

    if not username:
        return json.dumps({
            "allowed": False,
            "count": 0,
            "limit": _get_limit_per_day(),
            "limit_enabled": True,
            "error": "未知用户"
        }, ensure_ascii=False)

    limit_enabled = _get_feature("ai_daily_limit", True)
    limit = _get_limit_per_day()
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    usage = _get_daily_usage()
    today_data = usage.get(today_str, {})
    current = today_data.get(username, 0)

    allowed = not (limit_enabled and current >= limit)

    return json.dumps({
        "allowed": allowed,
        "count": current,
        "limit": limit,
        "limit_enabled": limit_enabled,
    }, ensure_ascii=False)


# ─── 12. 获取完整配置概览 ────────────────────────────────

def api_get_all_config():
    """获取所有配置（一次调用返回所有数据）"""
    if not _require_admin():
        return "Illegal request", 404

    users = [{"ip": ip, "username": uname} for ip, uname in userlist.items()]
    money_data = _load_json(os.path.join(log_dir, "moneys.json"), {})
    cfg = _load_config()
    features = cfg.get("features", _DEFAULT_CONFIG["features"])
    schedule_active = _get_active_schedule()
    schedule = {s: e for s, e in forbidden_time.items()}
    backup_schedule = {s: e for s, e in forbidden_time1.items()}
    daily_usage = _get_daily_usage()
    limit_per_day = cfg.get("ai_limit_per_day", 10)

    return json.dumps({
        "users": users,
        "money_data": money_data,
        "features": features,
        "schedule": schedule,
        "backup_schedule": backup_schedule,
        "schedule_active": schedule_active,
        "daily_usage": daily_usage,
        "server_status": serverStatus(),
        "ai_limit_per_day": limit_per_day,
    }, ensure_ascii=False)


# ─── 13. 建议课表管理 ────────────────────────────────

COMPANION_CONFIG_FILE = os.path.join(log_dir, 'companion_configs.json')


def _load_companion_configs():
    if not os.path.exists(COMPANION_CONFIG_FILE):
        return {}
    try:
        with open(COMPANION_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}


def _save_companion_configs(configs):
    os.makedirs(log_dir, exist_ok=True)
    with open(COMPANION_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)


def api_get_all_week_schedules():
    """获取所有用户的周课表配置"""
    if not _require_admin():
        return "Illegal request", 404
    configs = _load_companion_configs()
    result = {}
    for username, cfg in configs.items():
        result[username] = cfg.get('week_schedule', {})
    return json.dumps({
        "users": result,
        "default_schedule": DEFAULT_WEEK_SCHEDULE
    }, ensure_ascii=False)


def api_apply_default_week_schedule():
    """
    将建议课表应用到所有用户（或指定用户）。
    POST JSON: {}
    POST JSON: {username: "xxx"}  只应用给指定用户
    """
    if not _require_admin():
        return "Illegal request", 404
    data = request.get_json() or {}
    target_username = data.get('username', None)
    import copy
    default_schedule = copy.deepcopy(DEFAULT_WEEK_SCHEDULE)
    
    configs = _load_companion_configs()
    affected = []
    
    if target_username:
        if target_username not in configs:
            configs[target_username] = {}
        configs[target_username]['week_schedule'] = copy.deepcopy(default_schedule)
        affected.append(target_username)
    else:
        # 应用到所有用户
        for username in configs:
            configs[username]['week_schedule'] = copy.deepcopy(default_schedule)
            affected.append(username)
        # 也应用到 userlist 中所有有用户名的用户（但还没有 companion_config 的）
        for ip, uname in userlist.items():
            if uname and uname not in configs:
                configs[uname] = {'week_schedule': copy.deepcopy(default_schedule)}
                affected.append(uname)
    
    _save_companion_configs(configs)
    return json.dumps({
        "success": True,
        "affected_users": affected,
        "count": len(affected)
    }, ensure_ascii=False)


# ─── 日常使用追踪（在 ai.py 中调用） ────────────────

def track_daily_ai_usage(username):
    """
    记录用户当天的 AI 使用次数，并检查是否超过限制。
    数据读取/写入 daily_ai_usage.json。

    返回: (allowed: bool, today_count: int, limit: int)
    """
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    usage = _get_daily_usage()

    if today_str not in usage:
        usage[today_str] = {}

    current = usage[today_str].get(username, 0)
    limit_enabled = _get_feature("ai_daily_limit", True)
    limit = _get_limit_per_day()

    if limit_enabled and current >= limit:
        return False, current, limit
    return True, current, limit

def plus_ai_usage(username):
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    usage = _get_daily_usage()
    if today_str not in usage:
        usage[today_str] = {}
    if username not in usage[today_str]:
        usage[today_str][username] = 1
    usage[today_str][username] += 1
    _save_daily_usage(usage)