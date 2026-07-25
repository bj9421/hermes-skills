#!/usr/bin/env python3
"""Enriched batch backfill: import all past Hermes sessions into Obsidian daily log files
with content extraction (主旨/討論/結論 per session).

Usage:
    python3 scripts/enrich_daily_logs.py

Writes to: /opt/data/obsidian-vault/Hermes/日誌/YYYY-MM-DD.md
"""
import sqlite3, datetime, os, re

VAULT_LOG_DIR = '/opt/data/obsidian-vault/Hermes/日誌'
TZ = datetime.timezone(datetime.timedelta(hours=8))
NOW = datetime.datetime.now(TZ).strftime('%Y-%m-%d %H:%M')

conn = sqlite3.connect('/opt/data/state.db')
conn.row_factory = sqlite3.Row

def get_session_details(sid):
    """Extract 主旨, key topics, and 結論 from a session."""
    cur = conn.execute("""
        SELECT role, content FROM messages
        WHERE session_id = ? ORDER BY id
    """, (sid,))
    msgs = cur.fetchall()
    if not msgs:
        return None, None, None

    # 主旨: first meaningful user message
    first_user = None
    for m in msgs:
        if m['role'] == 'user':
            c = m['content']
            if c.startswith('[System note') or c.startswith('[CONTEXT COMPACTION') or c.startswith('[OUT-OF-BAND'):
                continue
            first_user = c[:300]
            break

    # 結論: last meaningful assistant message
    last_asst = None
    for m in reversed(msgs):
        if m['role'] == 'assistant' and m['content'] and len(m['content']) > 50:
            last_asst = m['content'][:500]
            break

    # 討論: key topic lines from user messages
    topics = set()
    for m in msgs:
        if m['role'] == 'user':
            first_line = m['content'].split('\n')[0].strip()
            if first_line and len(first_line) > 10 and not first_line.startswith('[System'):
                topics.add(first_line[:80])
    meaningful = [t for t in topics if not t.startswith('你好') and len(t) > 5][:5]

    return first_user, meaningful, last_asst


# Collect sessions by date
sessions_by_date = {}
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
    sid = row['id']; title = row['title'] or '(無標題)'; source = row['source']
    started_at = row['started_at']; msg_count = row['msg_count']
    first_ts = row['first_ts']; last_ts = row['last_ts']
    date_str = datetime.datetime.fromtimestamp(started_at).strftime('%Y-%m-%d')
    if date_str not in sessions_by_date:
        sessions_by_date[date_str] = []
    first_t = datetime.datetime.fromtimestamp(first_ts, TZ).strftime('%H:%M') if first_ts else '??'
    last_t = datetime.datetime.fromtimestamp(last_ts, TZ).strftime('%H:%M') if last_ts else '??'
    sessions_by_date[date_str].append({
        'id': sid, 'title': title, 'source': source,
        'msgs': msg_count, 'time_range': f'{first_t}-{last_t}'
    })

os.makedirs(VAULT_LOG_DIR, exist_ok=True)

for date_str, session_list in sorted(sessions_by_date.items()):
    telegrams = [s for s in session_list if s['source'] == 'telegram']
    tuis = [s for s in session_list if s['source'] == 'tui']
    clis = [s for s in session_list if s['source'] == 'cli']
    total_msgs = sum(s['msgs'] for s in session_list)

    lines = [
        '---',
        f'date: {date_str}',
        f'sessions: {len(session_list)}',
        f'messages: {total_msgs}',
        f'sources: telegram={len(telegrams)}, tui={len(tuis)}, cli={len(clis)}',
        '---\n',
        f'# {date_str} 對話日誌\n',
        '## 概覽\n',
        '| 項目 | 數值 |',
        '|------|------|',
        f'| 總 Session 數 | {len(session_list)} |',
        f'| 總訊息數 | {total_msgs} |',
        f'| Telegram 對話 | {len(telegrams)} |',
        f'| TUI 對話 | {len(tuis)} |',
        f'| CLI 對話 | {len(clis)} |\n',
        '## 對話內容\n',
    ]

    for s in session_list:
        emoji = {'telegram': chr(0x1f4ac), 'tui': chr(0x1f5a5), 'cli': chr(0x1f4bb)}.get(s['source'], chr(0x1f4cb))
        lines.append(f'### {emoji} {s["source"].upper()} | {s["time_range"]} | {s["title"]} ({s["msgs"]} 則訊息)\n')

        first_user, topics, last_asst = get_session_details(s['id'])
        if first_user or topics or last_asst:
            text = first_user.strip() if first_user else ''
            text = re.sub(r'\n{3,}', '\n\n', text)
            if len(text) > 150:
                text = text[:147] + '...'
            if text:
                lines.append(f'> 主旨：{text}')
            if topics:
                lines.append(f'> 討論：{" | ".join(topics[:3])}')
            if last_asst:
                text = last_asst.strip()
                text = re.sub(r'\n{3,}', '\n\n', text)
                if len(text) > 200:
                    text = text[:197] + '...'
                lines.append(f'> 結論：{text}')
        else:
            lines.append('> *（簡短對話，無詳細內容可萃取）*')
        lines.append('')

    lines.append('---')
    lines.append(f'*內容萃取於 {NOW}*')

    filepath = os.path.join(VAULT_LOG_DIR, f'{date_str}.md')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'OK {date_str}: {len(session_list)} sessions enriched')

conn.close()
print(f'\n完成！共 {len(sessions_by_date)} 天')

# Fix permissions for Syncthing
for root, dirs, files in os.walk(VAULT_LOG_DIR):
    for name in dirs:
        os.chmod(os.path.join(root, name), 0o777)
    for name in files:
        os.chmod(os.path.join(root, name), 0o777)
print('Permissions set to 777.')
