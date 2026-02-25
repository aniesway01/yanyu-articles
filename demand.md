# YanYuInc 需求文件

> 建立日期：2026-02-25
> 需求提出者：anies
> 狀態：進行中

---

## 一、專案概述

本 repo 服務於大陸保險理賠諮詢業務，資料分為兩大類別：

| 分類 | 說明 | 現狀 |
|------|------|------|
| **判決書整理** | 裁判文書網抓取的保險糾紛判決 | 已完成 11 份（`judgments/`） |
| **微信文章整理** | shawnCH（何智翔）轉發的有價值微信文章 | 進行中 — 已提取 53 個 URL |

兩者獨立分類，互不混雜。

---

## 二、微信文章整理 — 核心需求

### 2.1 資料來源

- 來自 shawnCH（微信 ID `F1487329976`，備註「何智翔」）的私聊訊息
- 透過本地已解密的微信 4.x 資料庫提取（`WeChatReader` 工具）
- 私聊共 2918 條訊息，提取到 53 個微信文章 URL

### 2.2 抓取要求

- **全文抓取**：文章標題、正文、作者、發布日期
- **圖片下載**：文章內所有圖片必須下載到本地，不依賴微信伺服器（微信圖片連結會過期）
- **圖片嵌入**：Markdown 中使用本地相對路徑引用圖片

### 2.3 GitHub 託管要求

- 公開 repo，有公開 URL 即可
- GitHub Pages 靜態網站，一個網址就能瀏覽所有文章
- 索引頁列出所有文章（按時間/分類）

### 2.4 下載功能

每篇文章頁面需支援下載為：
- **PDF** — 排版完整，含圖片
- **Markdown (.md)** — 原始格式
- **純文字 (.txt)** — 無格式版本

### 2.5 Log 記錄（必要）

- 所有工作過程必須有 log 紀錄，存放在 `YanYuInc/logs/` 目錄
- 記錄內容：時間戳、操作類型、URL、成功/失敗、錯誤訊息
- 格式：結構化日誌（JSON Lines 或帶時間戳的純文字）

### 2.6 斷點續傳機制（必要）

- 使用狀態檔追蹤每篇文章的處理進度
- 狀態檔：`YanYuInc/wechat_articles/_state.json`
- 每篇文章的狀態：`pending` → `fetching` → `fetched` → `uploaded` → `done`
- 中斷後重啟，自動跳過已完成的文章，從中斷點繼續
- 失敗的文章標記為 `failed`，附帶錯誤原因，可單獨重試

### 2.7 目錄結構（規劃）

```
YanYuInc/
├── judgments/                    # 判決書（已有，獨立分類）
├── wechat_articles/             # 微信文章整理（新建）
│   ├── articles/                # 各篇文章
│   │   ├── YYYY-MM-DD_slug/
│   │   │   ├── index.md        # 文章 Markdown（含本地圖片路徑）
│   │   │   ├── assets/         # 該文章的圖片
│   │   │   └── article.txt     # 純文字版
│   │   └── ...
│   ├── _state.json              # 斷點續傳狀態檔
│   └── _raw/                    # 原始抓取數據備份
├── logs/                         # 工作日誌
│   └── wechat_fetch_YYYYMMDD.log
├── site/                        # GitHub Pages 靜態網站
│   ├── index.html               # 首頁（文章索引 + 下載連結）
│   └── ...
├── demand.md                    # 本文件
└── ...
```

---

## 三、已確認事項

### 3.1 聊天記錄來源 ✅ 已確認

- [x] C. 微信 PC 端已解密資料庫
- 路徑：`C:\AntiGravityFile\WeChatMsg\decrypted_db\db_storage\`
- 工具：`WeChatReader`（`000System/Mid-tools/WeChatReader/wechat_reader.py`）
- ShawnCH wxid：`F1487329976`，DB 表：`Msg_6787328a8b910b6cae385c7c3750ca22`

### 3.2 待確認

- [ ] GitHub repo 名稱（建議 `yanyu-articles`）
- [ ] 是否建在 `aniesway01` 帳號下？
- [ ] 是否需要自訂域名？
- [ ] 是否所有 53 篇都收錄？還是只收保險/醫療相關？
- [ ] 是否需要 AI 生成摘要？

---

## 四、技術方案

### 4.1 管線流程

```
Step 1: URL 提取（✅ 已完成）
  WeChatReader → 解析私聊 → 提取 mp.weixin.qq.com 連結 → 53 個 URL

Step 2: 文章抓取 + 圖片下載（待執行）
  Playwright → 逐篇訪問 → 提取 HTML → 下載圖片到本地 → 轉 Markdown
  - 斷點續傳：_state.json 追蹤每篇進度
  - Log：logs/wechat_fetch_YYYYMMDD.log

Step 3: 格式轉換（待執行）
  Markdown → TXT（strip formatting）
  Markdown → PDF（weasyprint 或 md-to-pdf）

Step 4: 靜態網站建置（待執行）
  生成 index.html（文章列表 + 搜尋 + 下載按鈕）
  各文章頁面（閱讀 + PDF/MD/TXT 下載）

Step 5: GitHub 部署（待執行）
  git init → gh repo create → push → enable GitHub Pages
```

### 4.2 關鍵工具

| 工具 | 用途 |
|------|------|
| `WeChatReader` | 從本地 DB 提取聊天中的文章 URL |
| Playwright | 訪問微信文章頁、抓取 HTML + 圖片 |
| markdownify / BeautifulSoup | HTML → Markdown 轉換 |
| weasyprint / md-to-pdf | Markdown → PDF |
| GitHub Pages | 靜態網站託管 |

---

## 五、已提取的文章 URL（53 篇）

來源：ShawnCH（何智翔）私聊，時間範圍 2020-10 ~ 2026-02

有效文章（排除小程序跳轉等無效連結後）約 44 篇，主要分布：
- **保險理賠/條款**：~20 篇（核心內容）
- **行業分析/趨勢**：~10 篇
- **AI/科技相關**：~5 篇
- **醫療健康**：~5 篇
- **其他**：~4 篇

完整 URL 列表見 `wechat_articles/_state.json`。

---

## 六、變更紀錄

| 日期 | 變更 |
|------|------|
| 2026-02-25 | 初始需求建立 |
| 2026-02-25 | 確認資料來源為本地已解密微信 DB，ShawnCH wxid = F1487329976 |
| 2026-02-25 | 新增要求：log 記錄 + 斷點續傳機制 |
| 2026-02-25 | 完成 URL 提取：53 個微信文章 URL |
