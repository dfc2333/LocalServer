"""
邮件服务模块 - 检查指定邮箱，筛选标题含"给server的附件"的邮件并下载附件
改进: 记录已下载附件指纹，避免重复下载；使用普通密码认证（QQ邮箱/常规IMAP）
"""

import os
import json
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import datetime
import threading
import hashlib

from config import (
    root,
    mail_dir,
    mail_imap_server,
    mail_imap_port,
    mail_account,
    mail_password,
    log_dir,
)

# 上次检查日期追踪文件，用于每日首次启动判断
_last_check_file = os.path.join(log_dir, "mail_last_check.txt")
# 已下载附件数据库（记录指纹 -> 本地文件名）
_attachment_db_file = os.path.join(mail_dir, ".downloaded_attachments.json")


def _get_last_check_date():
    """获取上次检查邮件的日期，返回 date 对象或 None"""
    try:
        if os.path.exists(_last_check_file):
            with open(_last_check_file, "r", encoding="utf-8") as f:
                date_str = f.read().strip()
                return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        pass
    return None


def _set_last_check_date(d):
    """记录本次检查日期"""
    os.makedirs(os.path.dirname(_last_check_file), exist_ok=True)
    with open(_last_check_file, "w", encoding="utf-8") as f:
        f.write(d.strftime("%Y-%m-%d"))


def _decode_mime_words(s):
    """解码 MIME 编码的邮件标题"""
    if s is None:
        return ""
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or "utf-8", errors="replace"))
            except Exception:
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(str(part))
    return "".join(result)


def _load_attachment_db():
    """
    加载已下载附件数据库。

    数据库格式:
    {
        "uid:filename:sha256[:8]": "本地文件名",
        "legacy:filename:filesize": "本地文件名",   # 旧文件的指纹兼容
        ...
    }
    """
    if os.path.exists(_attachment_db_file):
        try:
            with open(_attachment_db_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            pass
    return {}


def _save_attachment_db(db):
    """保存已下载附件数据库"""
    os.makedirs(os.path.dirname(_attachment_db_file), exist_ok=True)
    with open(_attachment_db_file, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def _build_fingerprint(email_uid, filename, payload_bytes):
    """为附件生成唯一指纹: uid:filename:sha256[:8]"""
    content_hash = hashlib.sha256(payload_bytes).hexdigest()[:8]
    return f"{email_uid}:{filename}:{content_hash}"


def _scan_existing_files(db):
    """
    扫描 mail_dir 中已有文件，将未在 db 中的记录补充进去。
    这样在首次使用改进版时，旧文件也不会被重复下载。
    """
    if not os.path.exists(mail_dir):
        return db

    for fname in os.listdir(mail_dir):
        if fname == os.path.basename(_attachment_db_file):
            continue
        fpath = os.path.join(mail_dir, fname)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            legacy_key = f"legacy:{fname}:{size}"
            if legacy_key not in db:
                db[legacy_key] = fname
    return db


def check_mail():
    """
    连接 IMAP 邮箱（普通密码认证），搜索标题含"给server的附件"的邮件，
    下载新附件到 ./downloaded/mail/ 目录。

    认证方式: 普通 IMAP 密码认证（适用于 QQ 邮箱、163 邮箱等）
    - QQ 邮箱需开启 IMAP 服务，使用授权码作为密码

    改进特性:
    - 使用 IMAP UID 追踪每封邮件，避免重复处理
    - 为每个附件计算指纹 (UID + 文件名 + 内容SHA256[:8])
    - 已在数据库中的附件跳过下载
    - 首次运行时自动扫描已有文件，兼容旧文件

    返回: (success_count, message_list)
        success_count: 新下载了附件的邮件数
        message_list: 日志消息列表
    """
    messages = []
    success_count = 0

    if not mail_account:
        msg = "[MailService] 邮箱未配置（mail_account 为空），跳过检查"
        messages.append(msg)
        print(msg)
        return 0, messages

    os.makedirs(mail_dir, exist_ok=True)

    # 加载已下载附件数据库，并扫描已有文件（兼容旧数据）
    attachment_db = _load_attachment_db()
    attachment_db = _scan_existing_files(attachment_db)
    _save_attachment_db(attachment_db)

    conn = None
    try:
        # 连接 IMAP 服务器
        messages.append(
            f"[MailService] 正在连接 {mail_imap_server}:{mail_imap_port} ..."
        )
        if mail_imap_port == 993:
            conn = imaplib.IMAP4_SSL(mail_imap_server, mail_imap_port)
        else:
            conn = imaplib.IMAP4(mail_imap_server, mail_imap_port)

        # 普通密码认证登录
        conn.login(mail_account, mail_password)
        messages.append(f"[MailService] 登录成功: {mail_account}")

        # 选择收件箱
        conn.select("INBOX")

        # 使用 UID SEARCH 搜索标题含"To Server:"的邮件
        search_criteria = 'SUBJECT "To Server:"'
        status, uid_data = conn.uid("search", search_criteria)

        if status != "OK":
            messages.append(f"[MailService] 搜索失败: {status}")
            return 0, messages

        uid_list = uid_data[0].split()
        if not uid_list:
            messages.append('[MailService] 没有找到标题含"To Server:"的邮件')
            return 0, messages

        messages.append(f"[MailService] 找到 {len(uid_list)} 封匹配的邮件")

        for uid in uid_list:
            try:
                # 通过 UID 获取邮件内容
                status, msg_data = conn.uid("fetch", uid, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # 解码标题
                subject = _decode_mime_words(msg["Subject"])
                sender = _decode_mime_words(msg.get("From", ""))
                email_uid = uid.decode()

                messages.append(
                    f"[MailService] 处理邮件(UID={email_uid}): {subject} (来自: {sender})"
                )

                # 遍历所有附件
                new_count = 0
                skip_count = 0
                if msg.is_multipart():
                    for part in msg.walk():
                        content_disposition = str(part.get("Content-Disposition", ""))
                        if "attachment" in content_disposition:
                            filename = part.get_filename()
                            if filename:
                                filename = _decode_mime_words(filename)
                                payload = part.get_payload(decode=True)
                                if payload is None:
                                    continue

                                # 生成附件指纹
                                fp = _build_fingerprint(email_uid, filename, payload)

                                # 检查是否已下载（指纹匹配则跳过）
                                if fp in attachment_db:
                                    skip_count += 1
                                    messages.append(
                                        f"[MailService]   附件已存在，跳过: {filename}"
                                    )
                                    continue

                                # 确保文件名安全
                                safe_filename = "".join(
                                    c for c in filename
                                    if c.isalnum() or c in "._- ()（）"
                                )
                                if not safe_filename:
                                    safe_filename = f"attachment_uid{email_uid}.dat"

                                filepath = os.path.join(mail_dir, safe_filename)
                                # 如果文件已存在，加时间戳避免覆盖
                                if os.path.exists(filepath):
                                    name, ext = os.path.splitext(safe_filename)
                                    timestamp = datetime.datetime.now().strftime(
                                        "%Y%m%d_%H%M%S"
                                    )
                                    filepath = os.path.join(
                                        mail_dir, f"{name}_{timestamp}{ext}"
                                    )

                                with open(filepath, "wb") as f:
                                    f.write(payload)

                                # 记录到数据库
                                attachment_db[fp] = os.path.basename(filepath)
                                _save_attachment_db(attachment_db)

                                new_count += 1
                                messages.append(
                                    f"[MailService]   新附件已保存: {safe_filename}"
                                )

                if new_count > 0:
                    success_count += 1
                elif skip_count > 0:
                    messages.append(
                        f"[MailService]   此邮件的 {skip_count} 个附件均已下载过，跳过"
                    )
                else:
                    messages.append(f"[MailService]   此邮件没有附件")

            except Exception as e:
                messages.append(
                    f"[MailService] 处理邮件(UID={uid.decode()})时出错: {str(e)}"
                )

        messages.append(
            f"[MailService] 完成: 处理了 {len(uid_list)} 封邮件，"
            f"新下载 {success_count} 封邮件的附件"
        )

    except imaplib.IMAP4.error as e:
        messages.append(
            f"[MailService] IMAP 错误: {str(e)}"
        )
    except Exception as e:
        messages.append(f"[MailService] 连接失败: {str(e)}")
    finally:
        try:
            if conn:
                conn.close()
                conn.logout()
        except Exception:
            pass

    # 记录本次检查日期
    today = datetime.date.today()
    _set_last_check_date(today)

    return success_count, messages


def check_mail_async(callback=None):
    """
    在后台线程中异步检查邮件，避免阻塞服务器。

    参数:
        callback: 可选的回调函数，接收 (success_count, messages) 参数
    """
    def _run():
        result = check_mail()
        if callback:
            callback(result)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def is_first_start_today():
    """
    判断今日是否尚未检查过邮件（即每日首次启动）。
    返回 True 表示今天还没检查过，应触发自动检查。
    """
    last = _get_last_check_date()
    today = datetime.date.today()
    return last is None or last < today
