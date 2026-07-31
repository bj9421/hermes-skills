#!/usr/bin/env python3
"""本地 edge-tts 直接產出 MP3（繞過 NVIDIA API）

NVIDIA API 掛掉時，只要 script.md 口播稿已存在，就直接用 edge-tts 本地生成 MP3。
分段 ≤180 chars + 段間 sleep + 3 retries（edge-tts 間歇 NoAudioReceived 對策），
ffmpeg concat 合併（比 pydub 快）。

用法:
    /opt/data/.venv/bin/python gen_tts.py <script.md> <out_dir> <mp3_name>

實測 (2026-07-31): 634 chars → 9 段 → 133s / 1MB MP3，<1 分鐘，0 API 呼叫。
"""
import asyncio
import os
import re
import sys
import tempfile
import subprocess

VOICE = 'zh-TW-HsiaoChenNeural'  # 台女（solo）。dual 時改成 A/B 交替。


def read_script(path):
    """讀 script.md，跳過 YAML frontmatter 與 markdown 標題/引用，回傳口播稿正文。"""
    text = open(path, encoding='utf-8').read()
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            text = parts[2]
    lines = []
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('#') or stripped.startswith('>'):
            continue
        if re.match(r'^[#>*\-\s]*$', stripped):
            continue
        lines.append(stripped)
    return '\n'.join(lines)


def split_paragraphs(text, max_len=180):
    """切成 ≤max_len 的段落（盡量在句號/驚嘆/問號斷點切，避免 edge-tts 長段失敗）。"""
    chunks = []
    paras = [p.strip() for p in re.split(r'\n+', text) if p.strip()]
    for para in paras:
        while len(para) > max_len:
            cut = -1
            for m in re.finditer(r'[。！？!?]', para[:max_len]):
                cut = m.end()
            if cut < max_len * 0.4:
                cut = max_len
            chunks.append(para[:cut])
            para = para[cut:].strip()
        if para:
            chunks.append(para)
    return chunks


async def tts_one(text, voice, out_path, max_retries=3):
    """單段 TTS，失敗重試（edge-tts 間歇 NoAudioReceived 對策）。"""
    import edge_tts
    for attempt in range(max_retries):
        try:
            c = edge_tts.Communicate(text, voice, rate='+5%')
            await c.save(out_path)
            if os.path.getsize(out_path) > 0:
                return True
        except Exception as e:
            print(f'  [retry {attempt+1}] {e}')
        await asyncio.sleep(2)
    return False


async def main(script_path, out_dir, mp3_name):
    text = read_script(script_path)
    print(f'口播稿 {len(text)} chars')
    chunks = split_paragraphs(text)
    print(f'切成 {len(chunks)} 段')

    with tempfile.TemporaryDirectory() as tmp:
        seg_files = []
        for i, chunk in enumerate(chunks):
            seg = os.path.join(tmp, f'seg_{i:03d}.mp3')
            ok = await tts_one(chunk, VOICE, seg)
            if not ok:
                print(f'  ✗ seg {i} 失敗，跳過')
                continue
            seg_files.append(seg)
            print(f'  ✓ seg {i} ({len(chunk)} chars)')
            await asyncio.sleep(2)  # 避免 edge-tts 間歇失敗

        if not seg_files:
            print('ERROR: 所有分段都失敗')
            sys.exit(1)

        list_path = os.path.join(tmp, 'list.txt')
        with open(list_path, 'w') as f:
            for s in seg_files:
                f.write(f"file '{s}'\n")
        final = os.path.join(out_dir, mp3_name)
        subprocess.run(
            ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_path,
             '-acodec', 'libmp3lame', '-q:a', '2', final],
            capture_output=True, check=True)
        print(f'✅ MP3 產出: {final} ({os.path.getsize(final)//1024} KB)')


if __name__ == '__main__':
    script_path, out_dir, mp3_name = sys.argv[1], sys.argv[2], sys.argv[3]
    asyncio.run(main(script_path, out_dir, mp3_name))
