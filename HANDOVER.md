# YanYu 保險判決知識庫 — 交接文件

> 最後更新：2026-02-27
> 線上網址：https://aniesway01.github.io/yanyu-articles/site/judgments.html

---

## 一、專案概覽

618 篇中國法院保險糾紛判決案例的知識庫網站，包含：
- **11 篇精選判決**：來自裁判文書網，人工整理的案情分析（非判決書原文）
- **607 篇年度案例**：來自《中國法院年度案例》叢書 PDF（2018-2025），案例評析體裁

每篇判決頁面包含：AI 分析摘要、爭議焦點、法學見解、Infographic 資訊圖表、Slides 投影片、Mind Map 心智圖、標籤分類、裁判文書網連結。

---

## 二、2026-02-27 完成的工作

### 2.1 Gemini Infographic 自動化 (`gemini_infographic.py`)

**問題**：NotebookLM 生成的 infographic 有 CJK 中文亂碼問題。
**方案**：改用 Gemini API 直接從 AI 分析 JSON 生成 infographic 圖片。

- 新建 `gemini_infographic.py`
- 使用 `gemini-3-pro-image-preview` 模型
- 6 把 Gemini API Key 輪換 + RPM 限流（14/key/min）
- **完成 250/618**（40%），剩餘 368 張因 RPD（每日配額）限流暫停
- 每張約 30-40 秒，800-990 KB
- 進度自動記錄在 `_progress.json`

### 2.2 Slides + Mind Map 自動化 (`gen_slides_mindmap.py`)

**問題**：NLM 只完成 9 篇的 slides/mindmap，剩餘 609 篇缺失。
**方案**：純腳本方案，不需外部 API。

- **Slides**：HTML 模板 + Playwright 截圖為 JPG + img2pdf 合成 PDF
  - 每篇 6 頁：標題頁 → 案情摘要 → 爭議焦點（1-2頁）→ 法學見解 → 結尾頁
  - 設計風格：深藍漸層、Noto Sans TC 字體、法律圖標
- **Mind Map**：從 AI 分析 JSON 程式化轉換為階層式 JSON
  - 結構：基本資訊 → 案情摘要 → 爭議焦點 → 法學見解
- **完成 618/618（100%）**，每個約 4-5 秒

### 2.3 網站重建

- 執行 `python build_all.py`，619 筆 NLM artifacts 成功整合
- 每個判決頁面完整顯示：infographic + slides 圖片 + PDF 下載 + Mind Map JSON

### 2.4 發現並修復的問題

| 問題 | 原因 | 修復 |
|------|------|------|
| `_progress.json` 競爭條件 | `gemini_infographic.py` 和 `gen_slides_mindmap.py` 同時寫同一檔案 | 寫了磁碟掃描修復腳本同步實際檔案狀態 |
| Windows 路徑尾點錯誤 | 檔名 `64_从船舶全损...........................json` 結尾有大量「.」| 加入 `sanitize_path_component()` 去除尾點 |
| Gemini 模型名稱 404 | 初始用的 `gemini-2.0-flash-preview-image-generation` 不存在 | 改為 `gemini-3-pro-image-preview` |

---

## 三、目前狀態（截至 2026-02-27）

| 產物 | 完成數 | 百分比 | 狀態 |
|------|--------|--------|------|
| AI 分析 JSON | 618/618 | 100% | 完成 |
| Infographic | 250/618 | 40% | **待完成** |
| Slides | 618/618 | 100% | 完成 |
| Mind Map | 618/618 | 100% | 完成 |
| 標籤分類 | 618/618 | 100% | 完成 |
| 裁判文書網 URL | 251/618 | 41% | 部分（精選+部分年度） |

---

## 四、待辦事項（優先順序）

### P0 — 必須做

1. **完成剩餘 368 張 Infographic**
   ```bash
   python gemini_infographic.py
   ```
   - Gemini API RPD 配額每日重置，直接重跑即可
   - 6 個 key 每日合計約可生成 ~300 張，可能需 2 天
   - 完成後重建網站：`python build_all.py`

2. **修正「展開判決原文」按鈕名稱**
   - 精選判決和年度案例都不含判決書原文
   - 精選是案情分析摘要，年度是案例評析
   - 建議改為「展開分析全文」或「展開案例評析」
   - 修改位置：`build_all.py` 中搜尋 `展開判決原文`

3. **推送到 GitHub Pages**
   ```bash
   # 在 site/ 目錄或對應的 gh-pages 倉庫操作
   ```

### P1 — 建議做

4. **防止 `_progress.json` 競爭條件**
   - 如果同時跑 `gemini_infographic.py` 和 `gen_slides_mindmap.py`，會互相覆蓋進度
   - 方案 A：加檔案鎖（`filelock` 套件）
   - 方案 B：分開進度檔（各用獨立 JSON，build 時合併）
   - 方案 C：確保不同時跑兩個腳本（目前的 workaround）

5. **Slides 品質微調**
   - 目前 slide_04（爭議焦點第 2 頁）有時只有 1-2 個要點，留白較多
   - 可考慮動態調整 `chunk_size` 或合併到一頁

6. **Mind Map 視覺化**
   - 目前 Mind Map 只提供 JSON 下載
   - 可加入前端 JS 樹狀圖渲染（D3.js / markmap）

### P2 — 可選

7. **NLM 原生 Slides 替換**
   - 精選判決前 9 篇已有 NLM 生成的高品質 slides（13 頁 PDF）
   - 可保留 NLM 版本作為這 9 篇的 slides，不被腳本版覆蓋

8. **Infographic 加速**
   - 目前單進程串列，6 個 key 可改為並發
   - 預估加速 5-6 倍（~50 分鐘跑完全量）

---

## 五、關鍵檔案索引

### 腳本

| 檔案 | 用途 | 依賴 |
|------|------|------|
| `build_all.py` | 靜態網站建置主腳本 | markdown, pagefind |
| `gemini_infographic.py` | Gemini API 生成 infographic | `google-genai` |
| `gen_slides_mindmap.py` | 本地生成 slides + mind map | `playwright`, `img2pdf`, `pillow` |
| `nlm_batch.py` | NotebookLM 批量生成（舊方案） | `notebooklm-py`, `playwright` |
| `_nlm_runner.py` | NLM 批次排程守護進程 | — |
| `_nlm_login.py` | NLM Google 帳號登入 | `playwright` |

### 數據目錄

| 路徑 | 內容 |
|------|------|
| `judgments/*.md` | 11 篇精選判決（案情分析） |
| `judgments/cases/YYYY/*.md` | 607 篇年度案例（案例評析） |
| `judgments/_ai_analysis/` | 618 個 AI 分析 JSON（summary, key_points, legal_insights） |
| `judgments/_nlm_output/` | 生成的 artifacts（infographic.png, slides_img/, slides.pdf, mindmap.json） |
| `judgments/_nlm_output/_progress.json` | 所有 artifacts 的進度追蹤 |
| `judgments/_tags.json` | 618 篇的標籤分類 |
| `site/` | 建置輸出的靜態網站 |
| `logs/` | 各腳本的執行日誌 |

### API Key

- Gemini API：6 把 key，定義在 `gemini_infographic.py` 第 43-50 行
- 來源：`Docs/Standards/Credentials/APIkeyBase.md`（Testing Project, Tier 1）

---

## 六、常用指令

```bash
# 查看各產物進度
python gemini_infographic.py --status
python gen_slides_mindmap.py --status

# 生成 infographic（跑全部未完成的）
python gemini_infographic.py

# 生成 slides + mind map（跑全部未完成的）
python gen_slides_mindmap.py

# 測試模式（只跑 N 個）
python gemini_infographic.py --test 3
python gen_slides_mindmap.py --test 3

# 重建網站
python build_all.py

# 修復 progress.json（從磁碟實際檔案同步）
# → 見本文件第 2.4 節，或參考 gen_slides_mindmap.py 結尾的磁碟掃描邏輯
```

---

## 七、已知限制

1. **Gemini RPD 限流**：6 個 Tier 1 key 每日合計配額有限，大批量需分多天跑
2. **Slides 字體依賴**：Playwright 截圖使用 Google Fonts CDN 載入 Noto Sans TC，離線環境可能 fallback 到 Microsoft JhengHei
3. **精選判決無原文**：11 篇精選判決只有案情分析，無判決書全文；年度案例是書籍案例評析體裁
4. **progress.json 非併發安全**：兩個腳本不可同時執行，否則會互相覆蓋
