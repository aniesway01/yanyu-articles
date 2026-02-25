#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fetch_ai_tips.py — 抓取電腦王阿達 AI 工具教學文章
來源：kocpc.com.tw（WordPress 站，正文在 .entry-content）
輸出：ai_tips/<slug>/ (index.md + assets/)

用法：
  python fetch_ai_tips.py              # 抓取所有 pending 文章
  python fetch_ai_tips.py --retry      # 重試失敗的
  python fetch_ai_tips.py --status     # 查看進度
"""

import json, os, re, sys, io, time, datetime, traceback
from pathlib import Path
from urllib.parse import urljoin, urlparse

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import requests
    from bs4 import BeautifulSoup
    import markdownify
except ImportError as e:
    print(f"缺少套件: {e}\npip install requests beautifulsoup4 markdownify")
    sys.exit(1)

# === 路徑 ===
BASE = Path(r"C:\AntiGravityFile\YanYuInc")
TIPS_DIR = BASE / "ai_tips"
STATE_FILE = TIPS_DIR / "_state.json"
LOG_DIR = BASE / "logs"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

# 預定義的文章列表（來自搜尋結果）
DEFAULT_ARTICLES = [
    {
        "id": "tip_001",
        "url": "https://www.kocpc.com.tw/archives/571945",
        "title": "NotebookLM 使用教學：幫你快速整理消化大量資訊論文",
        "status": "pending",
    },
    {
        "id": "tip_002",
        "url": "https://www.kocpc.com.tw/archives/564691",
        "title": "Google NotebookLM Audio Overview 功能",
        "status": "pending",
    },
    {
        "id": "tip_003",
        "url": "https://www.kocpc.com.tw/archives/550239",
        "title": "Google AI 寫作與研究助理 NotebookLM 在台推出",
        "status": "pending",
    },
    {
        "id": "tip_004",
        "url": "https://www.kocpc.com.tw/archives/482357",
        "title": "ChatGPT 萬能工具箱使用教學",
        "status": "pending",
    },
    {
        "id": "tip_005",
        "url": "https://www.kocpc.com.tw/archives/560378",
        "title": "Gemini Live 正式登場！Google 版 AI 語音聊天模式",
        "status": "pending",
    },
    {
        "id": "tip_006",
        "url": "https://www.kocpc.com.tw/archives/574061",
        "title": "AIXPLORIA 集結超過 5,000 款 AI 工具資料庫",
        "status": "pending",
    },
    {
        "id": "tip_007",
        "url": "https://www.kocpc.com.tw/archives/574254",
        "title": "MixerBox AI GenPod 一鍵生成中文 Podcast",
        "status": "pending",
    },
    {
        "id": "tip_008",
        "url": "https://www.kocpc.com.tw/archives/562368",
        "title": "Gemini AI 圖片生成與特制 AI",
        "status": "pending",
    },
    {
        "id": "tip_009",
        "url": "https://www.kocpc.com.tw/archives/544756",
        "title": "Google Gemini App 動手玩",
        "status": "pending",
    },
    {
        "id": "tip_010",
        "url": "https://www.kocpc.com.tw/archives/563648",
        "title": "Google Gemini 與 Gemini Advanced 的關鍵差異",
        "status": "pending",
    },
]


# === Logger ===
class Logger:
    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.datetime.now().strftime("%Y%m%d")
        self.log_file = LOG_DIR / f"ai_tips_{today}.log"

    def log(self, level, msg):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {level}: {msg}"
        print(line)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def info(self, msg): self.log("INFO", msg)
    def error(self, msg): self.log("ERROR", msg)
    def ok(self, msg): self.log("OK", msg)

logger = Logger()


# === 狀態管理 ===
def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # 初始化
    return {"articles": list(DEFAULT_ARTICLES)}

def save_state(state):
    TIPS_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# === 工具函數 ===
def make_slug(title):
    """生成安全的目錄名"""
    clean = re.sub(r'[<>:"/\\|?*\n\r！？：]', '', title)
    clean = clean.strip()[:60].strip()
    clean = re.sub(r'\s+', '_', clean)
    return clean


def download_image(img_url, save_path, session):
    """下載圖片"""
    try:
        if not img_url or img_url.startswith("data:"):
            return False
        resp = session.get(img_url, headers=HEADERS, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 100:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return True
    except Exception as e:
        logger.error(f"  圖片下載失敗: {img_url[:80]} → {e}")
    return False


# === 文章抓取 ===
def fetch_article(article, session):
    """抓取單篇 kocpc.com.tw 文章"""
    url = article["url"]
    art_id = article["id"]

    logger.info(f"[{art_id}] 開始抓取: {article['title'][:60]}")
    logger.info(f"  URL: {url}")

    # 下載 HTML
    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.encoding = "utf-8"
    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.text, "html.parser")

    # 提取標題
    title_el = soup.find("h1", class_="entry-title") or soup.find("h1")
    real_title = title_el.get_text(strip=True) if title_el else article["title"]

    # 提取時間
    time_el = soup.find("time", class_="entry-date")
    pub_time = time_el.get("datetime", "")[:10] if time_el else ""
    if not pub_time:
        time_el2 = soup.find("meta", property="article:published_time")
        if time_el2:
            pub_time = time_el2.get("content", "")[:10]

    # 提取作者
    author_el = soup.find("span", class_="author") or soup.find("a", rel="author")
    author = author_el.get_text(strip=True) if author_el else "電腦王阿達"

    # 建立文章目錄
    slug = make_slug(real_title)
    art_dir = TIPS_DIR / slug
    assets_dir = art_dir / "assets"
    art_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 提取正文 (WordPress .entry-content)
    content_div = soup.find("div", class_="entry-content")
    if not content_div:
        content_div = soup.find("article")
    if not content_div:
        raise Exception("找不到文章正文 (.entry-content)")

    # 移除不需要的元素
    for el in content_div.find_all(["script", "style", "iframe", "ins"]):
        el.decompose()
    # 移除相關文章區塊
    for el in content_div.find_all("div", class_=re.compile(r"related|yarpp|sharedaddy|jp-relatedposts")):
        el.decompose()

    # 下載圖片
    img_count = 0
    for img in content_div.find_all("img"):
        img_url = img.get("data-lazy-src") or img.get("data-src") or img.get("src") or ""
        if not img_url or img_url.startswith("data:"):
            continue
        if not img_url.startswith("http"):
            img_url = urljoin(url, img_url)

        img_count += 1
        ext = "jpg"
        parsed_url = urlparse(img_url)
        ext_m = re.search(r'\.(\w{3,4})(?:\?|$)', parsed_url.path)
        if ext_m:
            ext = ext_m.group(1).lower()
            if ext == "jpeg": ext = "jpg"
        img_name = f"img_{img_count:03d}.{ext}"
        img_path = assets_dir / img_name

        if download_image(img_url, img_path, session):
            img["src"] = f"assets/{img_name}"
            # 清理 lazy-load 屬性
            for attr in ["data-lazy-src", "data-src", "srcset", "data-srcset"]:
                if img.has_attr(attr):
                    del img[attr]
        else:
            img["src"] = img_url

    logger.info(f"  下載圖片: {img_count} 張")

    # 轉 Markdown
    md_content = markdownify.markdownify(
        str(content_div),
        heading_style="ATX",
        strip=["span"],
    )
    md_content = re.sub(r'\n{3,}', '\n\n', md_content).strip()

    # 組裝完整 Markdown
    md_full = f"""# {real_title}

> **來源**：[電腦王阿達]({url})
> **作者**：{author}
> **發布時間**：{pub_time}
> **抓取時間**：{datetime.datetime.now():%Y-%m-%d %H:%M}

---

{md_content}

---

*原文連結：{url}*
*本文轉載自電腦王阿達（kocpc.com.tw），版權歸原作者所有。*
"""

    # 寫入
    with open(art_dir / "index.md", "w", encoding="utf-8") as f:
        f.write(md_full)

    logger.ok(f"  完成: {slug}/ (MD + {img_count} 圖片)")

    return {
        "real_title": real_title,
        "author": author,
        "pub_time": pub_time,
        "slug": slug,
        "img_count": img_count,
    }


# === 主流程 ===
def run_fetch(retry=False, target_id=None):
    state = load_state()
    articles = state["articles"]

    if target_id:
        targets = [a for a in articles if a["id"] == target_id]
    elif retry:
        targets = [a for a in articles if a["status"] == "failed"]
        logger.info(f"重試模式：{len(targets)} 篇")
    else:
        targets = [a for a in articles if a["status"] == "pending"]
        logger.info(f"待抓取：{len(targets)} 篇（共 {len(articles)} 篇）")

    if not targets:
        logger.info("沒有需要處理的文章")
        return

    session = requests.Session()
    done, failed = 0, 0

    for i, art in enumerate(targets, 1):
        logger.info(f"--- [{i}/{len(targets)}] {art['id']} ---")
        art["status"] = "fetching"
        save_state(state)

        try:
            result = fetch_article(art, session)
            art["status"] = "fetched"
            art["real_title"] = result["real_title"]
            art["author"] = result["author"]
            art["pub_time"] = result["pub_time"]
            art["slug"] = result["slug"]
            art["img_count"] = result["img_count"]
            art["fetch_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            art["error"] = None
            done += 1
        except Exception as e:
            art["status"] = "failed"
            art["error"] = str(e)
            art["fetch_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.error(f"  失敗: {e}")
            traceback.print_exc()
            failed += 1

        save_state(state)

        # 禮貌延遲
        if i < len(targets):
            time.sleep(2)

    logger.info(f"=== 完成：成功 {done}，失敗 {failed}，共 {len(targets)} ===")


def show_status():
    state = load_state()
    articles = state["articles"]
    status_count = {}
    for a in articles:
        s = a["status"]
        status_count[s] = status_count.get(s, 0) + 1

    print(f"\n共 {len(articles)} 篇文章")
    for s, c in sorted(status_count.items()):
        print(f"  {s}: {c}")

    fetched = [a for a in articles if a["status"] == "fetched"]
    if fetched:
        print(f"\n已抓取:")
        for a in fetched:
            print(f"  {a['id']}: {a.get('real_title', a['title'])[:50]}")

    failed = [a for a in articles if a["status"] == "failed"]
    if failed:
        print(f"\n失敗:")
        for a in failed:
            print(f"  {a['id']}: {a['title'][:50]} → {a.get('error', '')}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AI Tips 文章抓取器")
    parser.add_argument("--retry", action="store_true", help="重試失敗")
    parser.add_argument("--id", default=None, help="只抓指定 ID")
    parser.add_argument("--status", action="store_true", help="查看進度")
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        run_fetch(retry=args.retry, target_id=args.id)
