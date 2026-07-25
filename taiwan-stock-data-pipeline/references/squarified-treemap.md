# Squarified Treemap — Algorithm Reference

## Why Squarified?

Squarified treemap 比 slice-and-dice treemap 更適合股市熱力圖，因為：
- 區塊形狀接近正方形（而非長條狀），閱讀性高
- 無縫填滿畫面，無空白
- 最大塊（台積電）在左上角，依市值遞減排列

## Algorithm Variants

### Variant A: Full Squarified (Bruls-Huizing-van Wijk)

**當資料分布較均勻時（前 5 名面積差異 < 3×）的最佳選擇。**

1. **排序**：依面積（市值 sqrt）由大至小
2. **遞迴分割**：對每個矩形區塊：
   - 判斷長邊方向（水平 vs 垂直）
   - 嘗試在該行加入下一項，直到 aspect ratio 開始變差
   - 固定該行，遞迴處理剩餘空間

**問題：** 當有極端值（TSMC 市值是 #2 的 10×），squarified 會把 TSMC 孤立成整排細長條。

### Variant B: Recursive Binary-Split (本專案採用)

**當資料分布極度不均（前 1~2 名遙遙領先）時的首選。**

```javascript
function treemapLayout(items, x, y, w, h) {
  if (items.length <= 1 || w < 4 || h < 4)
    return [{x, y, w, h, data: items[0]?.data}];
  const total = items.reduce((s, r) => s + r.area, 0);
  let running = 0, split = 1;
  for (let i = 0; i < items.length; i++) {
    running += items[i].area;
    if (running >= total / 2) { split = i + 1; break; }
  }
  const left = items.slice(0, split), right = items.slice(split);
  const leftSum = left.reduce((s, r) => s + r.area, 0);
  if (w >= h) {
    const sw = w * leftSum / total;
    return [...treemapLayout(left, x, y, sw, h),
            ...treemapLayout(right, x + sw, y, w - sw, h)];
  } else {
    const sh = h * leftSum / total;
    return [...treemapLayout(left, x, y, w, sh),
            ...treemapLayout(right, x, y + sh, w, h - sh)];
  }
}
```

**優點：** 保證區塊長寬比合理，程式簡單無 bug。
**缺點：** 不是最「方形」的佈局，但對 50 檔股票已足夠。

## Key Implementation Details

### 面積計算

| 方式 | 公式 | 效果 | 適用情境 |
|------|------|------|---------|
| Linear | `cap` | TSMC 獨佔 90% | ❌ 不要用 |
| Sqrt | `√cap` | TSMC ~5× #50 | 資料均勻時 |
| Log10 | `log10(cap/min+1)` | TSMC ~2× #50 | 極端值存在時 |
| **Rank-based** | `(50-i)*200+100` | 等差遞減 ~2.4× | ✅ 本專案最佳實績 |

> 規則：當排名 1 市值 > 排名 2 的 5 倍以上，直接用 rank-based。

### Variant C: d3-hierarchy 內建 treemap（目前 Web Dashboard 採用）

自 2026-07-08 起，Web Dashboard 改用 [d3-hierarchy](https://d3js.org/d3-hierarchy/treemap) 的標準 squarified treemap：

```javascript
function treemapLayout(items, x, y, w, h) {
  const root = d3.hierarchy({children: items})
    .sum(d => d.area)
    .sort((a, b) => b.value - a.value);
  
  d3.treemap()
    .size([w, h])
    .padding(1)
    .round(true)(root);
  
  return root.leaves().map(n => ({
    x: n.x0 + x, y: n.y0 + y,
    w: n.x1 - n.x0, h: n.y1 - n.y0,
    data: n.data.data
  }));
}
```

**優點：** D3 團隊維護的 battle-tested 演算法，處理邊界情況比自幹好。
**缺點：** 當有極端值（TSMC 市值遙遙領先）時仍會產出少量長條，但 50 檔內可接受。

### Canvas 渲染（Web Dashboard）

```javascript
// 目前使用接近正方形的比例，讓 squarify 產出方正區塊
const W = canvas.parentElement.clientWidth - 4;
const H = Math.round(W * 1.1);  // 高 > 寬，強調方正而非水平切分
```

### Pillow 渲染（Telegram 截圖）

```bash
python3 /opt/data/render_treemap.py  # 產出 heatmap_treemap.png
```

## Pitfalls

- **面積用 linear market cap** → TSMC 獨佔 90% 畫面。用 rank-based 或 log10
- **Canvas 長寬比**：必須寬 ≥ 高，否則垂直切出細長條。手機上設 `W * 0.65`
- **區塊最小尺寸**：低於 6px 可 skip
- **顯示上限**：手機建議 50 檔
- **⚠️ rank-based 面積公式溢出**：`(50 - i) * 200 + 100` 只對前 50 檔有效。傳入 >50 檔時 i≥50 會產生負數面積，d3.treemap 會炸掉只剩前 2 檔。務必 `slice(0, 50)`。
- **⚠️ roundRect 瀏覽器相容性**：`ctx.roundRect()` 在部分手機瀏覽器不支援，需加 `try/catch` fallback 到 `ctx.rect()`。
- **Canvas click 座標換算**：`(clientX - rect.left) * (canvasW / rect.width)`，CSS 尺寸 ≠ canvas pixel

## Related Files

- `/opt/data/render_treemap.py` — Pillow rendering script
- `taiwan-stock-cashflow-api/static/index.html` — Canvas JS implementation
- `taiwan-stock-cashflow-api/app.py` — Web dashboard API endpoint
