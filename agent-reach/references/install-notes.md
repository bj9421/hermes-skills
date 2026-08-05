# Agent-Reach 本機安裝狀態（2026-08-05）

> 安裝環境：RPi4 Docker 容器（非 root），HOME=/opt/data

## 安裝摘要

- **版本**：v1.5.0（GitHub 主線，非 PyPI 0.1.0 精簡版）
  - PyPI 版只有 rss/youtube 兩 channel — 不滿足需求
  - 安裝指令：`uv pip install --python /opt/data/.venv/bin/python3 --upgrade https://github.com/Panniantong/agent-reach/archive/main.zip`
- **位置**：`/opt/data/.venv/bin/agent-reach`
- **配置目錄**：`/opt/data/.agent-reach/`（HOME 指向 /opt/data，避免 /root 權限問題）

## 已安裝渠道（5/15 可用，實測通過）

| 渠道 | 狀態 | 後端 |
|---|---|---|
| 網頁 | ✅ | Jina Reader（curl https://r.jina.ai/URL）|
| YouTube | ✅ | 既有 yt-dlp 複用（/opt/data/.venv/bin/yt-dlp）|
| RSS | ✅ | feedparser（agent-reach 依賴已裝）|
| V2EX | ✅ | 公開 API |
| B站搜尋 | ✅ | B站搜尋 API 直連（無 bili-cli）|
| Exa 搜尋 | ✅ | mcporter → https://mcp.exa.ai/mcp |
| GitHub | ⚠️ | gh CLI 缺（容器非 root 無法 apt）；替代：GITHUB_PAT + curl API（bookmark-manager 備份在用）|

## 環境特殊處理（重要！）

1. **HOME 必須設 /opt/data**，否則 agent-reach 嘗試訪問 /root/.agent-reach → PermissionError
   ```bash
   export HOME=/opt/data
   ```
2. **npm 全域安裝無權限**（/usr/local/lib/node_modules EACCES）→ 改用使用者 prefix：
   ```bash
   npm config set prefix /opt/data/.local
   npm install -g mcporter   # 裝到 /opt/data/.local/bin/
   ```
3. **mcporter Exa 配置**：
   ```bash
   mcporter config add exa https://mcp.exa.ai/mcp --scope home
   # 配置檔：/opt/data/.mcporter/mcporter.json
   ```
4. **yt-dlp JS runtime**（agent-reach 安裝時補的設定）：
   ```
   /opt/data/.config/yt-dlp/config → --js-runtimes node
   ```
5. **SKILL.md 安裝位置**：`agent-reach skill --install` 裝到 `/opt/data/.agents/skills/agent-reach/`，需複製到 Hermes 的 `/opt/data/skills/agent-reach/`（含 references/）

## 未安裝（刻意維持）

8 個選配渠道需 cookie/登入態，使用者安全偏好不裝：
Twitter/X、Reddit、Facebook、Instagram、小紅書、小宇宙、雪球、LinkedIn

## 常用驗證

```bash
export HOME=/opt/data; export PATH=/opt/data/.venv/bin:/opt/data/.local/bin:$PATH
agent-reach doctor        # 檢查渠道狀態
agent-reach doctor --json # 詳細 active_backend
```
