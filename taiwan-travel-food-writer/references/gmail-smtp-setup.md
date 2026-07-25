# Blogger Mail2Blogger — MX 直接投遞實戰記錄

## 結論（2026-07-14 修正）

**Mail2Blogger 發文有兩種方式，適用不同情境：**

| 方法 | 純文字 | 含圖 HTML | 需要密碼 | 實際結果 |
|------|--------|-----------|---------|---------|
| 直接 MX (port 25) | ✅ 可送達 | ❌ 大圖被吞 | 不用 | 純文字信件直接進入草稿匣 👍 |
| Gmail SMTP 認證 (587) | ✅ 可送達 | ✅ 可送達 | App Password | 任何內容均可，但有密碼管理成本 |

> ⚠️ **關鍵修正（2026-07-14）：** 先前錯誤假設「直接 MX 一定失敗」。實測證明：**純文字信件經由 `gmr-smtp-in.l.google.com:25` 直送完全可行**，使用者確認收到。失敗案例是含 2.1MB base64 圖片的 HTML 信件才被無聲丟棄。

## 實測記錄（2026-07-14）

### 環境
- Docker 容器（Hermes 在 Raspberry Pi 4 上）
- Python 3.13 + smtplib + markdown 套件
- 目標：`bj9421.217uu@blogger.com`
- 寄件 From header：`bj9421@gmail.com`（不需認證）

### 測試一：純文字直接 MX（成功 ✅）
```python
msg = MIMEText("測試內容", "plain", "utf-8")
with smtplib.SMTP("gmr-smtp-in.l.google.com", 25, timeout=30) as server:
    server.send_message(msg)  # 回傳 250 OK
# 使用者從 Blogger 草稿匣確實收到！
```

SMTP 完整交談：EHLO → MAIL FROM → RCPT TO → DATA → 250 OK。使用者確認有收到。

### 測試二：含圖片 HTML 直接 MX（被吞 ❌）
同一流程，但信件為 HTML + base64 圖片（2.1MB PNG，base64 膨脹後 ~2.8MB）。SMTP 回傳 250 OK，但信件未進入 Blogger 草稿匣。使用者回報「沒有收到」。

### 測試三：認證 SMTP 寄送（成功 ✅）
```python
with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login("bj9421@gmail.com", app_password)
    server.send_message(msg)  # 含圖 HTML 也能送達
```

### 推論
Google MX 對於來自**陌生 IP、無 SPF/DKIM 簽章**的連線，會根據信件內容特徵（大小、格式、附件）綜合評分。純文字小信件通過 spam filter，大 HTML + 圖片的電子報形式信件被攔截。**決策因子是內容特徵，而非 SMTP 層級的認證狀態。**

## 使用者偏好

- **❌ 不帶圖片** — 文章中不要嵌入圖片。純文字即可。
- **❌ 不要 Google 帳密** — 不需要 App Password 或 OAuth 授權。
- 因此首選方案：**直接 MX（port 25）+ 純文字/無圖 HTML**。

## 腳本

| 腳本 | 用途 | 認證 |
|------|------|------|
| `/opt/data/scripts/blogger_direct.py` | 直接 MX 投遞（無密碼） | 無 |
| `/opt/data/scripts/blogger_send.sh` | 一鍵發文（比對文件名） | 無 |
| `/opt/data/scripts/blogger_auth.py` | SMTP 587 認證（備用，需密碼） | App Password |

## 安全設計

使用者偏好：**「不要給 Google 帳密」**
- 密碼存在本機檔案 `/opt/data/.config/blogger/smtp_pass.txt`，權限 600
- 密碼不經由聊天或記憶傳輸
- 使用者可隨時到 https://myaccount.google.com/apppasswords 撤銷密碼

## 設定檔路徑陷阱

Docker 環境中 `~` 指向 `/root`，但在容器內不可寫。所有 Blogger 設定檔固定在 `/opt/data/.config/blogger/`，由腳本寫死。

## 指令速查

```bash
# 直接 MX（一鍵，推薦）
bash /opt/data/scripts/blogger_send.sh 東港

# 直接 MX（底層，不帶圖）
uv run python3 /opt/data/scripts/blogger_direct.py /path/to/文章.md --no-images

# 直接 MX（帶圖 — 不保證送達）
uv run python3 /opt/data/scripts/blogger_direct.py /path/to/文章.md

# SMTP 認證（需密碼，可帶圖）
uv run python3 /opt/data/scripts/blogger_auth.py post /path/to/文章.md
