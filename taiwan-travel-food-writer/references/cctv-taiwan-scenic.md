# 台灣景區 CCTV 即時影像嵌入指南

> 研究來源：tw.live 網站逆向分析（2026-07-15 第一批, 2026-07-16 大規模掃描）
> 目標平台：Blogger（17uu.tw）— 透過 HTML 編輯模式嵌入

---

## 一、CCTV 來源類型

tw.live 整合三種影像類型，嵌入方式各異：

| 類型 | 技術 | 更新方式 | 適用地點 | Blogger 可否嵌入 |
|------|------|----------|----------|:---:|
| **YouTube 直播** 🎥 | `<iframe>` YouTube embed | 串流（即時） | 國家風景區、熱門景點 | ✅ **最簡單、首選** |
| **公路局 CCTV** 🛣️ | `<img>` JPEG 快照（數秒更新） | 定期刷新圖片 | 省道、太魯閣、一般道路 | ✅ 但非影片，靜態圖 |
| **高公局 CCTV** 🛣️ | MJPEG 串流 | 串流 | 國道即時路況 | ⚠️ 需透過 HLS 轉接 |

**實務建議：優先使用 YouTube 直播類型** — 順暢影片、嵌入簡單、手機相容。公路局快照僅在無 YouTube 選項時使用。

---

## 二、掃描方法（對抗 Cloudflare）

tw.live 使用 Cloudflare 防護，以下方法經實測有效：

### 方法 A：curl 靜態分析（無封鎖時）

```bash
# 從景點分類頁面抓 camera ID 列表
curl -sL "https://tw.live/sunmoonlake/" | grep -oP '/cam/\?id=[^"&]+'

# 從 camera 頁面抓 YouTube ID
curl -sL "https://tw.live/cam/?id=<camera-id>" | grep -oP 'youtube-nocookie\.com/embed/[^?"]+'
```

### 方法 B：Wayback Machine 繞過 Cloudflare（推薦 — 實測有效）

當 Cloudflare 封鎖直接請求時，利用 Wayback Machine 快取取得歷史頁面中的 YouTube embed：

```bash
curl -sL "https://web.archive.org/web/2025/https://tw.live/cam/?id=<camera-id>" \
  | grep -oP 'youtube-nocookie\.com/embed/[^?"]+' | head -1
```

Wayback Machine 的快取通常保留最近數月的頁面，足夠擷取 YouTube embed iframe。注意某些 camera 回傳 `live_stream`（動態 Video ID），需跳過或另尋管道。

### 方法 C：YouTube 搜尋比對

當 A/B 都失敗時，直接用 YouTube 搜尋景點名稱：

```bash
encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('七星潭即時影像 live'))")
curl -sL -H 'User-Agent: Mozilla/5.0' "https://www.youtube.com/results?search_query=$encoded" \
  | grep -oP '"videoId":"[^"]*"' | sort -u | head -3
```

### 方法 D：批次掃描腳本

```bash
for page in travel sunmoonlake hhs alishan taroko kenting yms; do
  curl -sL "https://tw.live/$page/" | grep -oP '/cam/\?id=[^"&]+'
done | sort -u | while read path; do
  id=$(echo "$path" | sed 's|/cam/?id=||')
  yt=$(curl -sL "https://web.archive.org/web/2025/https://tw.live$path" 2>/dev/null \
    | grep -oP 'youtube-nocookie\.com/embed/[^?"]+' | grep -v live_stream | head -1)
  echo "$id → $yt"
done
```

---

## 三、景區 YouTube 直播完整對照表（100+ 鏡頭）

### 🌲 阿里山國家公園

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `alishan` | 阿里山森林遊樂區 | `QkoV41_kk7s` |
| `fenqihu` | 奮起湖 | `B6eki-0-w0g` |
| `eryanping` | 二延平步道（雲海） | `j2L_559nCjc` |
| `ckykzx` | 觸口遊客中心 | `8KnqJBf_dow` |
| `forestrailway` | 阿里山林業鐵路 | `8cq-t5yKjvs` |
| `shenglifarm` | 阿里山生力農場 | `agEzlv9n9Eg` |

### 🏖️ 墾丁國家公園

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `nanwanbay` | 南灣海灘 | `jUnFuJSj0OU` |
| `sailrockbeach` | 船帆石 | `A9TWsoAuvqE` |
| `houbihumarina` | 後壁湖 | `tK-z2UlPfA0` |
| `kdwlthbfq` | 貓鼻頭 | `hW3sTVQHIOg` |
| `oceanviewtower` | 觀海樓 | `wRleP2_WaPc` |

### ⛰️ 合歡山

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `hehuanfourseasons` | 合歡山四季 | `ix9BKNaRtEk` |

> 合歡山武嶺即時影像為公路局 CCTV（JPEG 每數秒更新），非 YouTube。URL 範例：`https://cctv-ss06.thb.gov.tw/T14A-006K-950/snapshot`

### 🌺 陽明山國家公園

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `dtzrgy` | 大屯自然公園 | `6ghffcNt3Nw` |
| `ezptcc` | 二子坪停車場 | `d9KuXrPCWYU` |
| `lsktcc` | 大屯山 | `GB64WeZZQPQ` |
| `qtgcy` | 擎天崗 | `yF2LAyOvq0Q` |
| `xyktcc` | 小油坑 | `kKD-ZBLs8-4` |
| `ymsabtcc` | 中山樓 ~~CCTV 失效~~ | 🚫 `vRwRi30NDl4` |
| `ymswyttbpd` | 陽明山無名亭 | `RttyIGHbN_w` |
| `ytqxs` | 陽明山 | `PvJr2efA6n0` |

### 🛶 日月潭

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `itathaopier` | 伊達邵碼頭 | `aub2lWUiRx8` |
| `xsykzx` | 玄光寺 | `JVnPFZbwcMs` |
| — | **九蛙疊像平台縮時** | `IZlB2NKZUI8` | ✅ 本波新增 |
| — | **達克拉哈自行車道縮時** | `hd20XV2AtGk` | ✅ 本波新增 |

### 🌸 福壽山農場（11 鏡頭 — 全台最豐富）

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `fssncbyy` | 百櫻園 | `CHJ4I5w5WtQ` |
| `fssnccyy` | 千櫻園 | `uEij55cXE6o` |
| `fssncgsgcq` | 果樹觀察區 | `hybftjM41Mw` |
| `fssnclyfwzx` | 旅遊服務中心 | `reUph_ggZdo` |
| `fssncpgw` | 蘋果王 | `Kgsfq7ih85w` |
| `fssncslfq` | 松廬楓情 | `cY3tr4kbB5Q` |
| `fssnctcjgkt` | 天池景觀步道 | `xYBaAtK9CHs` |
| `fssncyyhbd` | 鴛鴦湖步道 | `_2mrPUNxxGI` |
| `fssncxgqkxs` | 製茶廠波斯菊 | `NVMyghzBWv8` |
| `fssnczghblyq` | 最高海拔露營區 | `b13vSUxXCzs` |
| `fssnczccbsjhh` | 製茶廠波斯菊全景 | `z76_8trCLlM` |

### 🦩 台江國家公園

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `PJShujjuUEI` | 北汕尾水鳥生態保護區 | `643hBRTEIEo` |
| `UcTGee9_epA` | 六孔碼頭 | `kBwsZrEcfCo` |
| `dMEwrdRBeos` | 七股賞鳥亭黑琵 | `sJyKI--gdnA` |

### 🏝️ 澎湖國家風景區

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `aimenbeach` | 隘門沙灘 | `u3g1cwBS1Fs` |
| `beiliaoscenicarea` | 北寮奎壁山摩西分海 | `zgPJbQzlQmw` |
| `neianbeach` | 內垵沙灘 ~~CCTV 失效~~ | 🚫 `WKKsky9i8ug` |
| `nanhaifloatingpier` | 南海浮動碼頭 | `9HD_sCAIyWk` |
| `qimeipier` | 七美碼頭 | `CAZ-CbzrIs0` |

### 🌅 大鵬灣國家風景區

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `bayfunland` | 潮口平台 | `sJ8q1aOQAPU` |
| `dapengbaymarina` | 濱灣碼頭 | `rB0Nw8JmTXg` |
| `dapengbaymarinazonec` | 濱灣碼頭 C 堤 | `2NMrGvTYqN4` |
| `dapengbaymarinazoned` | 濱灣碼頭 D 堤 | `fLYOccOgG8A` |
| `dafuxi` | 小琉球大福西 | `zXYwAdPTLls` |
| `dapengbaymarinazonec` | 高雄大鵬灣濱灣之心 | `DK-AW0K9bcg` |

### 🌊 東部海岸國家風景區

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `AKl3F6cAY2Q` | 加路蘭遊憩區 | `AKl3F6cAY2Q` |
| `JhQuR77AR7U` | 都歷遊客中心 | `JhQuR77AR7U` |
| `JkoXcXI04Qk` | 大石鼻山 | `JkoXcXI04Qk` |
| `fv1yFousBvc` | 綠島帆船鼻 | `fv1yFousBvc` |
| `ZdqHgQwvZOw` | 金樽遊憩區 | `ZdqHgQwvZOw` |
| `4VBfBgnhJUE` | 鼻頭角服務區 | `4VBfBgnhJUE` |
| `Rhkr8qJOFO4` | 福隆海水浴場 | `Rhkr8qJOFO4` |
| `R1dzTS0xH3g` | 龍洞灣觀景台 | `R1dzTS0xH3g` |
| `IZBAoy4OR-s` | 馬崗哨所（原馬崗觀海亭） | `IZBAoy4OR-s` |

### 🏄 花東

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `aaKOV4qkDHw` | 花蓮鯉魚潭 | `aaKOV4qkDHw` |
| `qg-aHp2mvS8` | 七星潭（北埔安檢所） | `qg-aHp2mvS8` |
| `0uYCj5d4_uo` | 和南寺 | `0uYCj5d4_uo` |
| `D945F_dauls` | 台東富岡漁港 | `D945F_dauls` |
| `UCG1aXVO8H8` | 台東多良車站 | `UCG1aXVO8H8` |
| `6kUEK3LVrro` | 台東池上天堂路 | `6kUEK3LVrro` |
| `Rsq95SQ26bY` | 台東富山 | `Rsq95SQ26bY` |
| `9QqBz3kNHis` | 金崙大橋 | `9QqBz3kNHis` |
| `j3l32VFi5M8` | 七星潭安檢所 | `j3l32VFi5M8` |
| `BUJJaW0vkJs` | 鯉魚山 | `BUJJaW0vkJs` |

### 🌺 高雄市

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `C03Itx8iSC0` | 壽山情人觀景台 | `C03Itx8iSC0` |
| `BnPoNatG-HE` | 蓮池潭 | `BnPoNatG-HE` |
| `HqrPgNErSOA` | 高雄燈塔 | `HqrPgNErSOA` |
| `S7uQCrCX4kM` | 高雄港第二港口 | `S7uQCrCX4kM` |
| `7H2KWnKHuy8` | 棧貳庫 | `7H2KWnKHuy8` |
| `F22CtjpGeaU` | 洲仔濕地公園 | `F22CtjpGeaU` |
| `-Of409y9f9k` | 大社青雲宮 | `-Of409y9f9k` |
| `1vVCtk5OXVk` | 典寶溪楠梓聖興橋 | `1vVCtk5OXVk` |
| `Tb6bay3UB18` | 二仁溪田寮崇德橋 | `Tb6bay3UB18` |
| `UGAtpr8Rbtk` | 高雄機場國內線候補室 | `UGAtpr8Rbtk` |

### 🏝️ 馬祖

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `EaUVZ49xKQ4` | 北竿航空站 | `EaUVZ49xKQ4` |
| `HwUzhqm259g` | 南竿航空站 | `HwUzhqm259g` |
| `v2A5oU4PhZ0` | 東引中柱港 | `v2A5oU4PhZ0` |
| `g-UAUkDsRSs` | 南竿福澳港 | `g-UAUkDsRSs` |
| `o1k0wrJPuqA` | 南竿航空站到站入口 | `o1k0wrJPuqA` |

### 🏯 金門

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `SR-6i6S8plg` | 栗喉蜂虎營巢地 | `SR-6i6S8plg` |
| `jm134gdjsyx` | 金門 134 道路 ~~CCTV 失效~~ | 🚫 `-srNHTE-Nf0` |
| `jmjgyjsyx` | 金門金龜山 | `uh_yNAE01w8` |

### 📍 其他特色景點

| Camera ID | 名稱 | YouTube Video ID |
|:---------:|------|:----------------:|
| `ZayKvJKDPWc` | 德基水庫 | `ZayKvJKDPWc` |
| `RaTbGYKMUtk` | 八卦山彰化平原 | `RaTbGYKMUtk` |
| `iDIjBc0gPSM` | 八斗子漁港（基隆） | `iDIjBc0gPSM` |
| `4sNw9XLIYfc` | 潮境公園（基隆） | `4sNw9XLIYfc` |
| `9uRumsWvvfE` | 南方澳（宜蘭） | `9uRumsWvvfE` |
| `IHpSqQ5UylQ` | 內埤海灘（宜蘭） | `IHpSqQ5UylQ` |
| `m0InHvNBESQ` | 佛光大學蘭陽平原 | `m0InHvNBESQ` |
| `cPh2vzrtG_w` | 礁溪寒沐酒店 | `cPh2vzrtG_w` |
| `X4feE60jy88` | 茂林情人谷 ~~CCTV 失效~~ | 🚫 `X4feE60jy88` |
| `zTunEnLPulM` | 武陵農場花海區 | `zTunEnLPulM` |
| `Jj1EkxDcT0k` | 武陵農場櫻花區 | `Jj1EkxDcT0k` |

---

## 四、Blogger 嵌入語法

### YouTube 直播（推薦）

**Blogger 編輯器 → HTML 模式**貼入：

```html
<div style="margin: 20px 0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
  <iframe 
    width="100%" 
    height="400" 
    src="https://www.youtube-nocookie.com/embed/QkoV41_kk7s?autoplay=1&mute=1&playsinline=1&rel=0&modestbranding=1"
    title="景區即時影像" 
    frameborder="0" 
    allow="autoplay; encrypted-media; gyroscope; picture-in-picture" 
    allowfullscreen>
  </iframe>
  <p style="text-align: center; font-size: 14px; color: #888; margin: 8px 0;">
    📡 影像來源：風景區管理處（YouTube 直播）
  </p>
</div>
```

**參數說明：** `autoplay=1&mute=1` — 自動播放但靜音（瀏覽器政策要求）；`playsinline=1` — 手機內嵌播放（不全螢幕）；`rel=0` — 不推播其他影片；`modestbranding=1` — 簡潔 YouTube 標示。

### 多鏡頭兩欄並排

```html
<table width="100%"><tr>
<td width="50%" style="vertical-align:top; padding:4px;">
  <iframe width="100%" height="250" 
    src="https://www.youtube-nocookie.com/embed/QkoV41_kk7s?autoplay=1&mute=1&playsinline=1" 
    frameborder="0" allowfullscreen></iframe>
  <p style="text-align:center;">阿里山</p>
</td>
<td width="50%" style="vertical-align:top; padding:4px;">
  <iframe width="100%" height="250" 
    src="https://www.youtube-nocookie.com/embed/B6eki-0-w0g?autoplay=1&mute=1&playsinline=1" 
    frameborder="0" allowfullscreen></iframe>
  <p style="text-align:center;">奮起湖</p>
</td>
</tr></table>
```

### 政府 CCTV 快照（非影片）

```html
<img 
  src="https://cctv-ss06.thb.gov.tw/T14A-006K-950/snapshot" 
  alt="合歡山武嶺即時影像" 
  style="width: 100%; max-width: 800px; border-radius: 8px;" 
  loading="lazy"
  onerror="this.style.display='none'">
<p style="text-align: center; font-size: 13px; color: #888;">
  📸 影像每數秒更新 · 來源：交通部公路局
</p>
```

⚠️ 政府 CCTV URL 格式類似 `https://cctv-ssNN.thb.gov.tw/CODE/snapshot`，其中 NN 和 CODE 可能變動，使用前建議測試。

---

## 五、授權注意

- **YouTube 直播**：各風景區管理處上傳，使用 YouTube embed 為公開標準功能，不需另外授權。不建議移除 YouTube 品牌標示。
- **政府 CCTV**：政府開放資料，一般使用無限制，商業大規模使用建議標註出處。
- **tw.live FAQ 立場**：建議嵌入前確認原始來源授權（他們是整合平台）。

---

## 六、已知陷阱

1. **Cloudflare 封鎖** — tw.live 啟用 Cloudflare 防護，curl 和瀏覽器都會被擋。解法：用 Wayback Machine 快取（方法 B）或 YouTube 搜尋（方法 C）。
2. **`live_stream` 佔位符** — 某些 camera 頁面的 YouTube embed 為 `live_stream`（動態 Video ID），無法直接使用。跳過這些，改從其他管道查詢。
3. **CCTV URL 變動** — 公路局伺服器編號可能變更，建議長期監控 tw.live 或直接使用 YouTube 選項。
4. **Blogger 手機版** — YouTube iframe 在 Blogger 手機版正常顯示，但 `<img>` 政府 CCTV 需確認 responsive 設定。

---

## 七、國家風景區官方頻道即時影像（2026-07 更新）

> 此為交通部觀光署 **13 個國家風景區** 的官方分類與 YouTube 即時影像對照。
> 資料來源：直接爬取各風景區管理處官方 YouTube 頻道 `/streams` 頁面，並以 oembed API 驗證標題。
> 優點：不依賴第三方網站（tw.live），官方頻道更穩定可靠。

### 全景區統計

| 區域 | 國家風景區 | 管理處 YouTube 頻道 | 即時影像數 |
|------|-----------|-------------------|:--------:|
| 🟦 北部 | 東北角及宜蘭海岸 | `@necoastnsa2903` | 4 |
| 🟦 北部 | 北海岸及觀音山 | 北觀處（6 支 4K） | 6 |
| 🟩 中部 | 參山（獅頭山/梨山/八卦山） | `@trimtnsa` | 4 |
| 🟩 中部 | 阿里山 | 阿里山管理處 | 1 |
| 🟧 南部 | 西拉雅 | 西拉雅管理處 | 1 |
| 🟧 南部 | 茂林 | 茂林管理處 | 1 |
| 🟧 南部 | 大鵬灣 | 大鵬灣管理處 | 1 |
| 🟪 東部 | 花東縱谷 | `@ervnsa` | 4 |
| 🟪 東部 | 東部海岸 | `@eastcoastnsa0501` | 4 |
| 🩷 離島 | 澎湖 | `@ph-nsa` | 3 |
| 🩷 離島 | 馬祖 | 馬祖管理處 | 1 |
| | **合計 11 個（含直播）** | | **30 支** |
| 🟩 中部 | 日月潭 | 日管處（縮時攝影） | 2 |
| ⚠️ | 雲嘉南濱海（無 YouTube CCTV） | — | 0 |

### 各區完整 Video ID

#### 🟦 東北角及宜蘭海岸（@necoastnsa2903）

| 景點 | Video ID |
|------|:--------:|
| 鼻頭服務區 | `4VBfBgnhJUE` |
| 舊草嶺自行車隧道(南口) | `Br1w0sIvO3U` |
| 永鎮濱海驛站 | `HVcowpes0qA` |
| 馬崗哨所 | `IZBAoy4OR-s` |
| **福隆海水浴場** | `Rhkr8qJOFO4` | ✅ 本波新增 |
| **龍洞灣觀景台** | `R1dzTS0xH3g` | ✅ 本波新增 |
| **馬崗哨所 4K** | `z5K_gNWK8ZM` | ✅ 本波新增 |
| **瑞芳蝙蝠洞** | `U-nh5KGZhLg` | ✅ 本波新增 |

#### 🟦 北海岸及觀音山（北觀處）

| 景點 | Video ID |
|------|:--------:|
| 觀音山 4K | `Kbkn-TGoa_0` |
| 白沙灣 4K | `FbB8WDUXXqU` |
| 野柳地質公園 4K | `ZjuY4qKaj40` |
| 老梅綠石槽 | `Wefj3zbl-tI` |
| 和平島公園 4K | `g-T8NbF9xlQ` |
| 中角灣 4K | `iJphhU-iaTA` |

#### 🟩 參山（@trimtnsa）

| 景點 | Video ID |
|------|:--------:|
| 峨眉湖（獅頭山） | `L9y1pwGktQg` |
| 梨山-櫻緣丘 | `NhzycUzqwV8` |
| 梨山-攬勝樓 | `R1RjtxkkxPw` |
| 梨山-攬勝樓 | `R1RjtxkkxPw` |
| 梨山-梨山賓館 | `v3Pbbu6v_is` |

#### 🟪 花東縱谷（@ervnsa）

| 景點 | Video ID |
|------|:--------:|
| 鯉魚潭 4K | `aaKOV4qkDHw` |
| 赤科山 | `5GTFLN9gZrc` |
| 六十石山 | `DliL9uMtPrI` |
| 鹿野高台 4K | `rvc1klNIgQc` |

#### 🟪 東部海岸（@eastcoastnsa0501）

| 景點 | Video ID |
|------|:--------:|
| 加路蘭遊憩區 | `AKl3F6cAY2Q` |
| 都歷遊客中心 | `JhQuR77AR7U` |
| 大石鼻山 | `JkoXcXI04Qk` |
| 三仙台 | `dQ7Sd6PGLdA` |

#### 其他國家風景區

| 風景區 | 景點 | Video ID |
|--------|------|:--------:|
| 阿里山 | 觸口遊客中心 | `8KnqJBf_dow` |
| 西拉雅 | 曾文水庫 | `EH4V8IwFIp4` |
| 茂林 | 屏東平原眺景 | `iW2P7TM9SaY` |
| 大鵬灣 | 小琉球花瓶岩 | `tHAeigBuzSQ` |
| 澎湖 | 觀音亭 360 4K | `tJSJMfxfivY` |
| 澎湖 | 七美南滬港碼頭 | `CAZ-CbzrIs0` | ✅ 本波新增 |
| 澎湖 | 南海遊客中心浮動碼頭 | `9HD_sCAIyWk` | ✅ 本波新增 |
| 馬祖 | 南竿鐵堡 | `ifk2LtOKjSk` |

---

## 八、Blogger 多鏡頭文章範本（CSS Grid 布局）

當文章含大量 iframe（如國家風景區總整理），使用 CSS Grid 取代 `<table>` 以獲得更好手機 RWD。

### CSS 樣式（貼入 Blogger HTML 頂部的 `<style>` 區塊）

```html
<style>
.cam-grid { display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; }
.cam-item { width: 400px; max-width: 100%; background: #f5f5f5; border-radius: 12px; padding: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.cam-item h4 { margin: 0 0 8px 0; font-size: 15px; }
.cam-item iframe { width: 100%; height: 225px; border-radius: 8px; }
@media (max-width: 480px) { .cam-item { width: 100%; } .cam-item iframe { height: 200px; } }
.section-title { font-size: 20px; font-weight: bold; margin: 32px 0 16px 0; padding: 10px 16px; border-radius: 8px; color: white; display: inline-block; }
.section-north { background: #2c6e9c; }
.section-central { background: #4a7c4f; }
.section-south { background: #c47a3a; }
.section-east { background: #6b4c8a; }
.section-island { background: #a05070; }
</style>
```

### 一個鏡頭區塊範本

```html
<div class="section-title section-north">北海岸及觀音山國家風景區</div>

<div class="cam-grid">
<div class="cam-item"><h4>⛰️ 觀音山 4K</h4><iframe src="https://www.youtube.com/embed/Kbkn-TGoa_0" frameborder="0" allowfullscreen></iframe></div>
<div class="cam-item"><h4>🏖️ 白沙灣 4K</h4><iframe src="https://www.youtube.com/embed/FbB8WDUXXqU" frameborder="0" allowfullscreen></iframe></div>
</div>
```

### 手機斷行建議

每行一個 `<div class="cam-item">`，手機（≤480px）會自動堆疊為一欄。
