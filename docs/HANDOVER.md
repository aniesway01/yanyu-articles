# YanYu 保險知識庫 — 交接文件

> 最後更新：2026-02-27
> 線上網址：https://aniesway01.github.io/yanyu-articles/site/

---

## 一、專案概覽

五大模組的保險理賠知識庫靜態網站：

| 模組 | 內容 | 數量 |
|------|------|------|
| 微信文章庫 | ShawnCH 轉發的保險/AI 文章 | 47 篇 |
| 保險判決庫 | 精選判決 + 年度案例 + AI 分析產物 | 618 篇 |
| Prompt 庫 | 角色扮演/開發/行銷等 AI 提示詞 | 661 個 |
| AI 使用技巧 | 電腦王阿達 AI 工具教學 | 20 篇 |
| AI 心得社群 | GitHub Repo 推薦 | 22 個 |

---

## 二、目錄結構

```
YanYuInc/
├── code/                    # 腳本工具
│   ├── build_all.py         # 主建構（全站 5 模組）
│   ├── gemini_infographic.py
│   ├── gen_slides_mindmap.py
│   ├── ai_analysis_batch.py
│   ├── tag_generator.py
│   ├── fetch_articles.py
│   ├── fetch_ai_tips.py
│   ├── convert_judgments.py
│   ├── ocr_judgments.py
│   ├── split_judgments.py
│   ├── scrape_v2.py
│   ├── fetch_wenshu_urls.py
│   └── prepare_prompts_v2.py
├── docs/                    # 文檔
│   ├── HANDOVER.md          # 本文件
│   ├── demand.md            # 需求文件
│   ├── 保户就医前实用指南.md
│   └── 保险理赔胜败因素分析报告.md
├── judgments/                # 判決源數據
│   ├── 001~011_*.md         # 11 篇精選判決
│   ├── cases/YYYY/*.md      # 607 篇年度案例
│   ├── _ai_analysis/        # 618 個 AI 分析 JSON
│   ├── _nlm_output/         # infographic / slides / mindmap
│   └── _tags.json           # 標籤分類
├── wechat_articles/          # 微信文章
├── ai_tips/                  # AI 技巧文章
├── community_ai/             # 社群分享
├── prompts/                  # Prompt 庫
├── site/                     # 靜態網站輸出
├── logs/                     # 執行日誌
├── index.html                # redirect → site/
└── .gitignore
```

---

## 三、目前狀態（截至 2026-02-27）

| 產物 | 完成數 | 百分比 | 狀態 |
|------|--------|--------|------|
| AI 分析 JSON | 618/618 | 100% | 完成 |
| Infographic | 502/618 | 81% | **待完成 116 張** |
| Slides | 618/618 | 100% | 完成 |
| Mind Map | 618/618 | 100% | 完成 |
| 標籤分類 | 618/618 | 100% | 完成 |
| 裁判文書網 URL | 251/618 | 41% | 部分 |

---

## 四、待辦事項

### P0 — 必須做

1. **完成剩餘 116 張 Infographic**
   ```bash
   python code/gemini_infographic.py
   ```
   - Gemini API RPD 配額每日重置（太平洋時間午夜 ≈ 台灣下午 3-4 點）
   - 完成後重建網站 + 推送

2. **重建 + 推送**
   ```bash
   python code/build_all.py
   git add -A && git commit -m "完成所有 infographic" && git push
   ```

### P1 — 建議做

3. 防止 `_progress.json` 競爭條件（加 filelock 或分離進度檔）
4. Slides 品質微調（slide_04 留白）
5. Mind Map 前端視覺化（D3.js / markmap）

---

## 五、腳本索引

| 檔案 | 用途 | 依賴 |
|------|------|------|
| `code/build_all.py` | 全站建構 | markdown, pagefind |
| `code/gemini_infographic.py` | Gemini API 生成 infographic | google-genai |
| `code/gen_slides_mindmap.py` | 本地生成 slides + mind map | playwright, img2pdf, pillow |
| `code/ai_analysis_batch.py` | DeepSeek AI 分析批處理 | DeepSeek API |
| `code/tag_generator.py` | 標籤分類生成 | DeepSeek API |
| `code/fetch_articles.py` | 微信文章抓取 | requests, bs4 |
| `code/fetch_ai_tips.py` | 電腦王阿達文章抓取 | requests, bs4 |
| `code/convert_judgments.py` | PDF → Markdown | pymupdf |
| `code/ocr_judgments.py` | 掃描 PDF OCR | PaddleOCR, 百度 OCR |
| `code/split_judgments.py` | 合集 MD → 一案一檔 | — |
| `code/scrape_v2.py` | CDP 抓裁判文書網 | playwright |
| `code/fetch_wenshu_urls.py` | 批量獲取裁判文書網 URL | playwright |
| `code/prepare_prompts_v2.py` | Prompt 素材準備 | yaml |

---

## 六、常用指令

```bash
# 查看進度
python code/gemini_infographic.py --status
python code/gen_slides_mindmap.py --status

# 生成 infographic
python code/gemini_infographic.py

# 生成 slides + mind map
python code/gen_slides_mindmap.py

# 重建網站
python code/build_all.py

# 推送
git add -A && git commit -m "update" && git push
```

---

## 七、API Key

- Gemini API：6 把 key，定義在 `code/gemini_infographic.py`
- 來源：`Docs/Standards/Credentials/APIkeyBase.md`（Testing Project, Tier 1）

---

## 八、已知限制

1. **Gemini RPD 限流**：6 個 Tier 1 key 每日合計配額有限，大批量需分多天跑
2. **Slides 字體依賴**：Playwright 使用 Google Fonts CDN 載入 Noto Sans TC
3. **精選判決無原文**：11 篇精選判決只有案情分析；年度案例是案例評析體裁
4. **progress.json 非併發安全**：兩個腳本不可同時執行
