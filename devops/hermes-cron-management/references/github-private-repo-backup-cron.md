# GitHub 私 repo 備份 cron（push-only、不 auto-commit）

實戰驗證 2026-08-02：bookmark-manager → `bj9421/bookmark-manager`（🔒 private）。
無 gh CLI、容器 SSL CA 損壞（`curl -k`）、PAT 在 `/opt/data/.env`。

> 註：bundled `github-repo-management` skill 只教基礎 repo 建立；本文件補上「私 repo 安全 push + 備份 cron」的硬化變體。

## 1. 建立私 repo（GitHub API）

```bash
PAT=$(grep -oP 'GITHUB_PAT=\K.*' /opt/data/.env | tr -d '"' | tr -d "'")
# 身份驗證（回 login 即 OK）
curl -sk -H "Authorization: token $PAT" https://api.github.com/user | grep '"login"'
# 名稱可用性：HTTP 404 = 可建
curl -sk -o /dev/null -w "%{http_code}" -H "Authorization: token $PAT" \
     https://api.github.com/repos/<owner>/<repo>
# 建立（回 full_name + private:true = 成功）
curl -sk -X POST https://api.github.com/user/repos \
  -H "Authorization: token $PAT" -H "Content-Type: application/json" \
  -d '{"name":"<repo>","private":true,"description":"...","auto_init":false}'
```

## 2. 🔴 Push 不把 PAT 寫進 remote config（安全關鍵）

```bash
git remote add origin https://github.com/<owner>/<repo>.git        # 乾淨 URL
git push "https://oauth2:${PAT}@github.com/<owner>/<repo>.git" main  # 一次性 URL
```
之後 `git remote -v` 仍顯示乾淨 URL。反例：`git remote set-url origin "https://${PAT}@..."`（skills_backup.sh 用）會把 PAT 寫進 config — 舊腳本能跑但不乾淨，新專案一律用一次性 URL。

## 3. Push 後驗證（trees API 掃敏感檔）

```bash
curl -sk -H "Authorization: token $PAT" \
  "https://api.github.com/repos/<owner>/<repo>/git/trees/main?recursive=1" \
  | grep -cE '\.db|\.env|token|secret|\.pem|\.key'    # 0 = 乾淨
```

## 4. 🔒 上傳前安全檢查清單（私 repo 也一樣）

1. `git ls-files` — 確認追蹤清單無 `.db` / `.env` / token 檔。
2. **git 歷史掃描**（.gitignore 只擋未來，歷史才是關鍵）：
   `git log --all --oneline --name-only | grep -E '\.db$|\.env$|token|secret'`
3. 硬編碼掃描：`grep -nEi '(api[_-]?key|token|secret|password|bearer|authorization)'` 所有追蹤檔 —
   確認 key 都是 `os.environ.get()` 讀環境變數，不是寫死在 code。
4. **DB 刻意排除**：私人資料庫（尤其含 xsec_token / 個人 URL）即使私 repo 也會進 git history —
   `.gitignore` 排除、永遠不上傳。DB 備份走 rsync 等本地/其他通道。
5. **用戶授權**：外部網路請求（push）先取得同意；用戶說「先評估」就只做唯讀盤點，不推任何東西。

## 5. 自動備份 cron（no_agent，push-only）

模式與 skills_backup.sh 的關鍵差別：**只 push 已 commit 的 code，不 auto-commit**。
正式專案 commit 由 agent 手動做，cron 只負責把「未 push 的 commit」送上雲 — 用戶要掌控權。

```bash
#!/bin/bash
# scripts/<repo>-backup.sh — 雙副本：/opt/data/scripts/ + /opt/data/.hermes/scripts/ + chmod +x
set -e
cd /opt/data/projects/<repo>
export $(grep "^GITHUB_PAT=" /opt/data/.env | xargs)
PAT="$GITHUB_PAT"; [ -z "$PAT" ] && { echo "ERROR: no PAT"; exit 1; }
AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
[ "$AHEAD" -eq 0 ] && exit 0        # 無未 push → 安靜（watchdog 模式）
git -c user.name="Hermes_Pi" -c user.email="hermes@dietpi4.local" \
    push "https://oauth2:${PAT}@github.com/<owner>/<repo>.git" main 2>&1
echo "✅ <repo> 已同步 ${AHEAD} 個 commit 到私 repo"
```

cron：`cronjob action=create name=<repo>-github-backup script="<repo>-backup.sh" no_agent=true schedule="every 2h"`。
- 0 未 push → exit 0 無 stdout → 安靜（沿用 no_agent Watchdog Pattern）。
- 有 push → 輸出 ✅ → 用戶收到確認。
- push 失敗 → exit ≠ 0 → 排程器通知。
- 頻率與 skills backup 一致（2h）；`deliver: origin`。

## 6. 公開/私有隔離原則（用戶硬性要求）

- 每個專案獨立 git repo、獨立 remote；備份腳本**寫死路徑**，不會跨 repo push。
- 私專案（如 bookmark-manager）**永遠只進私 repo**；公開 repo（hermes-skills / HA-POWERS-Docs）維持現狀。
- 回報時用表格列出公開 vs 私有 repo 清單，讓用戶一眼確認隔離。

## 已知無害現象

- git 警告 `unable to access '/root/.config/git/attributes': Permission denied` — 容器權限，不影響 commit/push。
- `pkill -f "python app.py"` 只殺 bash 外殼、python child 變孤兒繼續跑舊 code → 重啟 server 用精確 PID kill。
