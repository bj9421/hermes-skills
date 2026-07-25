#!/usr/bin/env python3
"""
Blogger Email 發文工具（Gmail SMTP 認證）

使用方式:
  1. 設定密碼:  uv run python3 blogger_auth.py setup
      → 用戶貼上 16 碼 App Password（存在本機檔案，權限 600）
  2. 寄送文章:  uv run python3 blogger_auth.py post /path/to/文章.md
      → 轉 HTML → 嵌入圖片 → smtp.gmail.com:587 → Blogger 草稿
"""

import argparse
import base64
import json
import os
import re
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import markdown


# Docker 環境 HOME=/root 不可寫，固定用可寫路徑
CONFIG_DIR = "/opt/data/.config/blogger"
PASS_FILE = os.path.join(CONFIG_DIR, "smtp_pass.txt")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

GMAIL_USER = "bj9421@gmail.com"
BLOGGER_EMAIL = "bj9421.217uu@blogger.com"


def _guess_image_type(data):
    sigs = {
        b'\x89PNG\r\n\x1a\n': 'png',
        b'\xff\xd8\xff': 'jpeg',
        b'GIF87a': 'gif',
        b'GIF89a': 'gif',
        b'RIFF': 'webp',
        b'BM': 'bmp',
    }
    for sig, fmt in sigs.items():
        if data.startswith(sig):
            return fmt
    return None


def save_password():
    os.makedirs(CONFIG_DIR, exist_ok=True)

    print("=" * 60)
    print("🔑 Blogger 寄信設定 — 應用程式密碼")
    print("=" * 60)
    print()
    print("密碼只存在本機檔案，不會進聊天紀錄或記憶。")
    print()
    print("👉 請到 https://myaccount.google.com/apppasswords 產生")
    print()
    print("   步驟：")
    print("   1. 登入 bj9421@gmail.com")
    print("   2. 開啟兩步驟驗證（若尚未開啟）")
    print("   3. 回到 App Passwords 頁面")
    print("   4. 選「其他（自訂名稱）」→ 輸入「Hermes Pi」")
    print("   5. 複製產生的 16 碼密碼")
    print()

    password = input("請貼上 16 碼 App Password（輸入時不會顯示）: ").strip()

    if len(password.replace(" ", "")) < 10:
        print("❌ 看起來不像有效的 App Password（應為 16 碼）")
        sys.exit(1)

    with open(PASS_FILE, "w") as f:
        f.write(password.strip())
    os.chmod(PASS_FILE, 0o600)
    print(f"\n✅ 密碼已存到 {PASS_FILE}")

    config = {
        "gmail_user": GMAIL_USER,
        "blogger_email": BLOGGER_EMAIL,
        "from_name": "Hermes Pi 旅遊美食",
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    print("✅ 設定完成！現在可以用 'post' 指令發文了")


def load_config():
    if not os.path.isfile(PASS_FILE):
        print("❌ 尚未設定密碼")
        print(f"   請先執行: uv run python3 {__file__} setup")
        sys.exit(1)

    with open(PASS_FILE) as f:
        password = f.read().strip()

    config = {"gmail_user": GMAIL_USER, "blogger_email": BLOGGER_EMAIL}
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            config.update(json.load(f))

    return password, config


def extract_title_and_body(md_text):
    lines = md_text.split("\n")
    title = ""
    body_lines = []
    for line in lines:
        if line.startswith("# ") and not title:
            title = line.lstrip("# ").strip()
        else:
            body_lines.append(line)
    if not title:
        title = f"文章 {datetime.now().strftime('%Y-%m-%d')}"
    return title, "\n".join(body_lines)


def resolve_images(md_text, md_dir):
    def replace_img(match):
        img_path = match.group(1)
        candidates = [
            os.path.join(md_dir, img_path),
            os.path.join(os.path.dirname(md_dir), img_path) if md_dir else "",
        ]
        if img_path.startswith("images/"):
            parent = os.path.dirname(md_dir)
            candidates.append(os.path.join(parent, img_path))
        for c in candidates:
            if c and os.path.isfile(c):
                try:
                    with open(c, "rb") as f:
                        img_data = f.read()
                    img_type = _guess_image_type(img_data) or "png"
                    b64 = base64.b64encode(img_data).decode("ascii")
                    return (f'<img src="data:image/{img_type};base64,{b64}" '
                            f'alt="image" style="max-width:100%;border-radius:8px;margin:16px 0;">')
                except Exception as e:
                    return f'<!-- 圖片錯誤: {e} -->'
        return f'<!-- 圖片未找到: {img_path} -->'
    return re.sub(r'!\[\[([^\]]+)\]\]', replace_img, md_text)


def md_to_html(md_text):
    return markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "sane_lists"],
    )


def build_email(title, html_body, config):
    msg = MIMEMultipart("alternative")
    msg["From"] = f'{config.get("from_name", "")} <{config["gmail_user"]}>'
    msg["To"] = config["blogger_email"]
    msg["Subject"] = title
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def send_authenticated(msg, password, config):
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(config["gmail_user"], password)
        server.send_message(msg)
    return True


def cmd_setup(args):
    save_password()


def cmd_post(args):
    password, config = load_config()

    md_path = os.path.abspath(args.file)
    if not os.path.isfile(md_path):
        print(f"❌ 找不到檔案: {md_path}")
        sys.exit(1)

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    md_dir = os.path.dirname(md_path)
    print(f"📄 讀取: {os.path.basename(md_path)}")

    title, md_body = extract_title_and_body(md_text)
    print(f"📌 標題: {title}")

    print("🖼️ 處理圖片...")
    md_body = resolve_images(md_body, md_dir)

    print("🔄 轉換 HTML ...")
    html_body = md_to_html(md_body)

    msg = build_email(title, html_body, config)

    print(f"📧 寄送到 {config['blogger_email']}（587 STARTTLS 認證）...")

    try:
        send_authenticated(msg, password, config)
        print("✅ 成功！文章已到草稿匣")
        print("   👉 https://draft.blogger.com")
    except smtplib.SMTPAuthenticationError:
        print("❌ 認證失敗，密碼不正確或已過期")
        print("   請重新執行: uv run python3 blogger_auth.py setup")
        sys.exit(1)
    except smtplib.SMTPException as e:
        print(f"❌ SMTP 錯誤: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Blogger 郵件發文工具")
    sub = parser.add_subparsers(dest="command", help="指令")

    sub.add_parser("setup", help="設定 Gmail App Password（存在本機）")
    p_post = sub.add_parser("post", help="寄送文章到 Blogger")
    p_post.add_argument("file", help="Markdown 檔案路徑")
    p_post.add_argument("--publish", action="store_true", help="直接發布（若 Blogger 設定為草稿則無效）")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "post":
        cmd_post(args)
    else:
        parser.print_help()
        print()
        print("快速開始:")
        print(f"  1. uv run python3 {__file__} setup")
        print(f"  2. uv run python3 {__file__} post 筆記.md")


if __name__ == "__main__":
    main()
