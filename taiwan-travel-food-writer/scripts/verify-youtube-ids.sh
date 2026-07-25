#!/usr/bin/env bash
# =============================================================================
# verify-youtube-ids.sh
# YouTube ID 驗證腳本 — 檢查即時影像來源是否有效
#
# 核心問題：HTTP 200 ≠ 影片有效。YouTube oembed/embed 頁面對已刪除/
# 私人的影片仍回 HTTP 200。本腳本使用三層實際內容檢查來辨識失效。
#
# 驗證層次：
#   1. oembed API — 連線與 metadata 基本檢查
#   2. 縮圖 HTTP 狀態 — hqdefault.jpg (200=有效, 404=失效)
#   3. Embed 頁面 videoId 出現次數 — ≥2=有效, 1=不存在
#
# Usage:
#   bash verify-youtube-ids.sh ID1 ID2 ID3 ...
#   bash verify-youtube-ids.sh < <(grep -oP '[\w-]{11}' article.md | sort -u)
#
# Output: 狀態表 + 摘要 + 失效列表（exit 1 當有失效）
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
WARN=0
FAIL=0
TOTAL=0
FAILED_IDS=""

for vid in "$@"; do
  TOTAL=$((TOTAL + 1))
  reasons=""

  # ── Layer 1: oembed API 連線與 metadata 基本檢查 ──
  oembed_json=$(curl -s --connect-timeout 5 \
    "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=$vid&format=json" 2>/dev/null)
  
  if [ -z "$oembed_json" ]; then
    reasons+="oembed 連線失敗 "
  else
    title=$(echo "$oembed_json" | python3 -c "import sys,json; print(json.load(sys.stdin).get('title','')[:80])" 2>/dev/null)
    oembed_http=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 \
      "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=$vid&format=json" 2>/dev/null)
    
    if [ "$oembed_http" != "200" ]; then
      reasons+="oembed=$oembed_http "
    fi
    if [ -z "$title" ]; then
      reasons+="oembed 無 title "
    fi
  fi

  # ── Layer 2: 縮圖檢查（最可靠的靜態訊號） ──
  thumb_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 \
    "https://img.youtube.com/vi/$vid/hqdefault.jpg" 2>/dev/null)
  if [ "$thumb_code" != "200" ]; then
    reasons+="縮圖=$thumb_code "
  fi

  # ── Layer 3: Embed 頁面 videoId 出現次數 ──
  # 有效影片的 videoId 在 embed 頁面中出現 ≥2 次
  # 不存在/已刪除/私人的影片只出現 1 次（僅 URL 本身）
  embed_html=$(curl -s --connect-timeout 5 "https://www.youtube.com/embed/$vid" 2>/dev/null)
  if [ -z "$embed_html" ]; then
    reasons+="embed 頁面空白 "
  else
    vid_count=$(echo "$embed_html" | grep -oP "$vid" | wc -l)
    if [ "$vid_count" -lt 2 ]; then
      reasons+="embed 無影片資料"
    fi
  fi

  # ── 綜合判斷 ──
  if [ -z "$reasons" ]; then
    echo -e "${GREEN}✅${NC} $vid | ${title:-N/A}"
    PASS=$((PASS + 1))
  elif echo "$reasons" | grep -q "embed 無影片資料\|縮圖=404"; then
    echo -e "${RED}❌${NC} $vid | ${title:-N/A}"
    echo -e "     ${RED}原因:${NC} $reasons"
    FAIL=$((FAIL + 1))
    FAILED_IDS+="$vid "
  else
    echo -e "${YELLOW}⚠️${NC} $vid | ${title:-N/A}"
    echo -e "     ${YELLOW}原因:${NC} $reasons"
    WARN=$((WARN + 1))
  fi
done

# ── 摘要 ──
echo ""
echo "========================================"
echo -e "Total: $TOTAL | ${GREEN}Pass: $PASS${NC} | ${YELLOW}Warn: $WARN${NC} | ${RED}Fail: $FAIL${NC}"
echo "========================================"

if [ -n "$FAILED_IDS" ]; then
  echo ""
  echo "❌ 失效 ID 列表: $FAILED_IDS"
  echo "→ 請從文章中移除後搜尋替代來源"
  echo "  優先搜尋官方頻道 /streams 頁面："
  echo "  curl -sL 'https://www.youtube.com/@trimtnsa/streams' | grep -oP 'watch\\?v=[\\w-]{11}' | sort -u"
  exit 1
fi
exit 0
