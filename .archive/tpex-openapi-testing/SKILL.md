---
name: tpex-openapi-testing
description: Test TPEX OpenAPI endpoint availability and detect Cloudflare blocking.
version: 1.0
author: Hermes Agent
metadata:
  hermes:
    tags: [tpex, openapi, cloudflare, testing]
---

# TPEX OpenAPI 測試技能

## Overview

TPEX OpenAPI 目前受 Cloudflare 保護，所有端點返回 302 redirect。
此技能提供快速測試腳本和調查記錄。

## 快速測試

```bash
python3 skills/taiwan-stock-data-pipeline/scripts/test_tpex_openapi.py
```

## 已知限制

- Swagger JSON 可下載（476KB）
- 所有 API 端點 302 → `/errors`
- Cloudflare IP: 172.65.90.66/67