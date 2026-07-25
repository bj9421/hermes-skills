# iframe 測試頁面模板

## 用途
快速測試網頁是否能在 iframe 中正確顯示（響應式、CSS 衝突、X-Frame-Options 等）。

## 建立方式
```bash
# 在 Flask templates/ 目錄下建立
# 或直接訪問 http://localhost:5000/iframe-test
```

## 功能
- 滑桿調整 iframe 寬度（320px ~ 1200px）
- 自動計算高度（寬度 × 0.75）
- 深色背景方便對比

## 注意事項
- 若目標網站設定 X-Frame-Options: DENY/SAMEORIGIN → iframe 會被阻擋
- Flask debug mode 下 CSS/JS 熱重載在 iframe 內可能不正常
- 跨域資源（圖片、字體）可能在 iframe 中被瀏覽器 CORS 政策攔截
