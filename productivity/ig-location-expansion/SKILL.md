---
name: ig-location-expansion
category: productivity
title: IG Taiwan 景點擴充與日常追蹤技能
description: 擴充 IG 追蹤地點至 100+ 個，使用 Tourism Bureau 官方資料搭配 Apify 抓取 Instagram 媒體數。
---
# 擴展說明

將原有 28 個現有景點保留，從 Taiwain Tourism Bureau 資料選取約 72 個額外景點（按 image_count 排序），總計 ~100 個。每月成本 <$0.03（完全在免費額度內）。

## 安全注意
DROP TABLE 為 destructive 操作，執行前需使用者明確確認。建議先 rename 保留舊表再建新表。

## References
- scripts/final_expand.py：主擴充腳本
- references/ig-location-expansion.md：技術細節（待建立）
---