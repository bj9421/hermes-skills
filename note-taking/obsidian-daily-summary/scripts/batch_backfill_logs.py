#!/usr/bin/env python3
"""Batch backfill: import all past Hermes sessions into Obsidian daily log files.

Usage:
    python3 scripts/batch_backfill_logs.py

Writes to: /opt/data/obsidian-vault/Hermes/日誌/YYYY-MM-DD.md
Output location can be changed by editing VAULT_LOG_DIR below.

NOTE: This script produces a simple table-list format (deprecated).
For content-enriched format (主旨/討論/結論 per session), use enrich_daily_logs.py instead.
"""
import sqlite3, datetime, os

STATE_DB = '/opt/data/state.db'
VAULT_LOG_DIR = '/opt/data/obsidian-vault/Hermes/日誌'

conn = sqlite3.connect(STATE_DB)
sessions = {}

cur = conn.execute('''
    SELECT s.id, s.title, s.source, s.started_at,
           (SELECT COUNT(*) FROM messages WHERE session_id = s.id) as msg_count,
           (SELECT MIN(timestamp) FROM messages WHERE session_id = s.id) as first_ts,
           (SELECT MAX(timestamp) FROM messages WHERE session_id = s.id) as last_ts
    FROM sessions s
    WHERE s.source IN ('telegram', 'tui', 'cli')
    ORDER BY s.started_at
''')

for row in cur:
    sid, title, source, started_at, msg_count, first_ts, last_ts = row
    date_str = datetime.datetime.fromtimestamp(started_at).strftime('%Y-%m-%d')
    if date_str not in sessions:
        sessions[date_str] = []
    first_t = datetime.datetime.fromtimestamp(first_ts).strftime('%H:%M') if first_ts else '??'
    last_t = datetime.datetime.fromtimestamp(last_ts).strftime('%H:%M') if last_ts else '??'
    sessions[date_str].append({
        'id': sid, 'title': title or '(無標題)', 'source': source,
        'msgs': msg_count, 'time_range': f'{first_t}-{last_t}'
    })

conn.close()
os.makedirs(VAULT_LOG_DIR, exist_ok=True)

for date_str, session_list in sorted(sessions.items()):
    telegrams = [s for s in session_list if s['source'] == 'telegram']
    tuis = [s for s in session_list if s['source'] == 'tui']
    clis = [s for s in session_list if s['source'] == 'cli']
    total_msgs = sum(s['msgs'] for s in session_list)

    lines = []
    lines.append('---')
    lines.append(f'date: {date_str}')
    lines.append(f'sessions: {len(session_list)}')
    lines.append(f'messages: {total_msgs}')
    lines.append(f'sources: telegram={len(telegrams)}, tui={len(tuis)}, cli={len(clis)}')
    lines.append('---\n')
    lines.append(f'# {date_str} 對話日誌\n')
    lines.append('## 概覽\n')
    lines.append('| 項目 | 數值 |')
    lines.append('|------|------|')
    lines.append(f'| 總 Session 數 | {len(session_list)} |')
    lines.append(f'| 總訊息數 | {total_msgs} |')
    lines.append(f'| Telegram 對話 | {len(telegrams)} |')
    lines.append(f'| TUI 對話 | {len(tuis)} |')
    lines.append(f'| CLI 對話 | {len(clis)} |\n')
    lines.append('## 對話列表\n')

    for s in session_list:
        icon = {'telegram': chr(0x1f4ac), 'tui': chr(0x1f5a5), 'cli': chr(0x1f4bb)}.get(s['source'], chr(0x1f4cb))
        title_clean = s['title'].replace('[', '(').replace(']', ')')
        lines.append(f'- {icon} **{s["source"].upper()}** | {s["time_range"]} | [{s["msgs"]:3d}msgs] {title_clean}')

    lines.append('')
    lines.append('---')
    lines.append(f'*批次產出於 {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}*')

    content = '\n'.join(lines)
    filepath = os.path.join(VAULT_LOG_DIR, f'{date_str}.md')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'OK  {date_str}: {len(session_list)} sessions, {total_msgs} msgs -> {date_str}.md')

print(f'\n完成！共 {len(sessions)} 天')

# Fix permissions for Syncthing
import stat as st
for root, dirs, files in os.walk(VAULT_LOG_DIR):
    for name in dirs:
        os.chmod(os.path.join(root, name), 0o777)
    for name in files:
        os.chmod(os.path.join(root, name), 0o777)
print('Permissions set to 777 for Syncthing compatibility.')
print('NOTE: For content-enriched format (主旨/討論/結論), use enrich_daily_logs.py instead.')
