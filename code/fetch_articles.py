#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WeChat Article Fetcher — 抓取微信文章全文 + 圖片
支援：斷點續傳、log 記錄、標籤自動分類、原文連結保留

用法：
  python fetch_articles.py              # 抓取所有 pending 文章
  python fetch_articles.py --retry      # 重試 failed 文章
  python fetch_articles.py --id art_003 # 只抓指定文章
  python fetch_articles.py --status     # 查看進度
"""

import json, os, re, sys, io, time, datetime, hashlib, traceback
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
BASE_DIR = Path(r"C:\AntiGravityFile\YanYuInc")
STATE_FILE = BASE_DIR / "wechat_articles" / "_state.json"
ARTICLES_DIR = BASE_DIR / "wechat_articles" / "articles"
RAW_DIR = BASE_DIR / "wechat_articles" / "_raw"
LOG_DIR = BASE_DIR / "logs"

# === 標籤規則 ===
TAG_RULES = [
    ("保險理賠", [
        "保险", "理赔", "拒赔", "保单", "保司", "医疗险", "重疾险",
        "寿险", "惠民保", "投保", "保额", "免赔", "条款", "保障",
        "保费", "赔付", "承保", "核保", "退保", "百万医疗",
        "好医保", "众安", "太平洋", "人保", "元保", "百保君",
        "代理人", "保险公司", "犯罪行为", "带病投保",
    ]),
    ("醫療健康", [
        "医疗", "健康", "药品", "医生", "阿福", "好大夫", "用药",
        "适应症", "药械", "就医", "病历", "肿瘤", "乳腺癌",
        "DRG", "医保", "药品目录", "蚂蚁阿福", "健康险",
        "食品", "治病", "戒糖",
    ]),
    ("AI科技", [
        "AI", "Claude", "GPT", "人工智能", "笔记工具", "Cowork",
        "科技", "软件业",
    ]),
    ("行業分析", [
        "银行", "诈骗", "金融", "招商银行", "科技节", "分子",
        "手回", "中介", "双向奔赴", "超级个体", "保险科技",
        "镁信", "米加", "生态合作",
    ]),
    ("生活其他", []),  # fallback
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# === Logger ===
class Logger:
    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.datetime.now().strftime("%Y%m%d")
        self.log_file = LOG_DIR / f"wechat_fetch_{today}.log"

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

# === 工具函數 ===
def load_state():
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def make_slug(title, date_str):
    """生成目錄名：YYYY-MM-DD_簡短標題"""
    clean = re.sub(r'[<>:"/\\|?*\n\r]', '', title)
    clean = clean.strip()[:40].strip()
    return f"{date_str}_{clean}"

def auto_tag(title):
    """根據標題自動分配標籤"""
    tags = []
    title_lower = title.lower()
    for tag_name, keywords in TAG_RULES:
        if keywords and any(kw.lower() in title_lower for kw in keywords):
            tags.append(tag_name)
    if not tags:
        tags.append("生活其他")
    return tags

def download_image(img_url, save_path, session):
    """下載圖片，返回 True/False"""
    try:
        if not img_url or img_url.startswith("data:"):
            return False
        # 微信圖片常見域名
        resp = session.get(img_url, headers=HEADERS, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 100:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return True
    except Exception as e:
        logger.error(f"  圖片下載失敗: {img_url[:80]} → {e}")
    return False

def fetch_article(article, session):
    """抓取單篇文章：HTML + 圖片 → Markdown + TXT"""
    url = article["url"]
    art_id = article["id"]
    title = article.get("title", "untitled")

    logger.info(f"[{art_id}] 開始抓取: {title[:50]}")
    logger.info(f"  URL: {url}")

    # 1. 下載 HTML
    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.encoding = "utf-8"

    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}")

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # 2. 提取元數據
    og_title = soup.find("meta", property="og:title")
    real_title = og_title["content"] if og_title and og_title.get("content") else title
    real_title = real_title.strip()

    og_author = soup.find("meta", {"name": "author"})
    author = og_author["content"] if og_author and og_author.get("content") else ""

    pub_time_el = soup.find("em", id="publish_time")
    pub_time = pub_time_el.text.strip() if pub_time_el else ""

    # 3. 建立文章目錄
    date_str = article["chat_time"][:10]
    slug = make_slug(real_title, date_str)
    art_dir = ARTICLES_DIR / slug
    assets_dir = art_dir / "assets"
    art_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 4. 提取正文
    content_div = soup.find("div", id="js_content")
    if not content_div:
        # 有些文章結構不同
        content_div = soup.find("div", class_="rich_media_content")
    if not content_div:
        raise Exception("找不到文章正文 (#js_content)")

    # 5. 下載圖片並替換路徑
    img_count = 0
    for img in content_div.find_all("img"):
        img_url = img.get("data-src") or img.get("src") or ""
        if not img_url or img_url.startswith("data:"):
            continue
        if not img_url.startswith("http"):
            img_url = urljoin(url, img_url)

        # 生成文件名
        img_count += 1
        ext_match = re.search(r'wx_fmt=(\w+)', img_url)
        ext = ext_match.group(1) if ext_match else "jpg"
        if ext == "jpeg":
            ext = "jpg"
        img_name = f"img_{img_count:03d}.{ext}"
        img_path = assets_dir / img_name

        if download_image(img_url, img_path, session):
            img["src"] = f"assets/{img_name}"
            img["data-src"] = ""
        else:
            img["src"] = img_url  # 保留原始連結作為 fallback

    logger.info(f"  下載圖片: {img_count} 張")

    # 6. 轉換為 Markdown
    # 先清理一些微信特有的元素
    for el in content_div.find_all(["script", "style", "iframe"]):
        el.decompose()

    md_content = markdownify.markdownify(
        str(content_div),
        heading_style="ATX",
        strip=["span"],
    )
    # 清理多餘空行
    md_content = re.sub(r'\n{3,}', '\n\n', md_content).strip()

    # 7. 組裝完整 Markdown
    tags = auto_tag(real_title)
    article["tags"] = tags

    md_full = f"""# {real_title}

> **作者**：{author or '未知'}
> **發布時間**：{pub_time or '未知'}
> **轉發時間**：{article['chat_time']}（by ShawnCH）
> **原文連結**：[點擊查看原文]({url})
> **標籤**：{', '.join(tags)}

---

{md_content}

---

*本文由 ShawnCH（何智翔）轉發，透過微信聊天記錄自動提取並整理。*
*原文連結：{url}*
"""

    # 8. 寫入文件
    md_path = art_dir / "index.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_full)

    # 9. 生成純文字版
    txt_content = f"標題：{real_title}\n作者：{author or '未知'}\n發布時間：{pub_time or '未知'}\n原文連結：{url}\n標籤：{', '.join(tags)}\n\n{'='*60}\n\n"
    txt_content += content_div.get_text(separator="\n", strip=True)
    txt_content += f"\n\n{'='*60}\n原文連結：{url}\n"

    txt_path = art_dir / "article.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt_content)

    # 10. 保存原始 HTML
    raw_path = RAW_DIR / f"{art_id}.html"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.ok(f"  完成: {slug}/ (MD + TXT + {img_count} 圖片)")

    return {
        "real_title": real_title,
        "author": author,
        "pub_time": pub_time,
        "slug": slug,
        "img_count": img_count,
        "tags": tags,
    }


def run_fetch(retry=False, target_id=None):
    """主流程：逐篇抓取，支援斷點續傳"""
    state = load_state()
    articles = state["articles"]

    if target_id:
        targets = [a for a in articles if a["id"] == target_id]
        if not targets:
            logger.error(f"找不到 {target_id}")
            return
    elif retry:
        targets = [a for a in articles if a["status"] == "failed"]
        logger.info(f"重試模式：{len(targets)} 篇 failed 文章")
    else:
        targets = [a for a in articles if a["status"] == "pending"]
        logger.info(f"待抓取：{len(targets)} 篇（共 {len(articles)} 篇）")

    if not targets:
        logger.info("沒有需要處理的文章")
        return

    session = requests.Session()
    done = 0
    failed = 0

    for i, art in enumerate(targets, 1):
        logger.info(f"--- [{i}/{len(targets)}] {art['id']} ---")

        # 更新狀態為 fetching
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
            art["tags"] = result["tags"]
            art["fetch_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            art["error"] = None
            done += 1
        except Exception as e:
            art["status"] = "failed"
            art["error"] = str(e)
            art["fetch_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.error(f"  失敗: {e}")
            failed += 1

        # 每篇處理完都保存狀態（斷點續傳核心）
        save_state(state)

        # 禮貌延遲，避免被封
        if i < len(targets):
            time.sleep(1.5)

    logger.info(f"=== 完成：成功 {done}，失敗 {failed}，共 {len(targets)} ===")

    # 統計
    status_count = {}
    for a in articles:
        s = a["status"]
        status_count[s] = status_count.get(s, 0) + 1
    logger.info(f"總進度：{status_count}")


def show_status():
    """顯示抓取進度"""
    state = load_state()
    articles = state["articles"]
    status_count = {}
    for a in articles:
        s = a["status"]
        status_count[s] = status_count.get(s, 0) + 1

    print(f"\n共 {len(articles)} 篇文章")
    for s, c in sorted(status_count.items()):
        print(f"  {s}: {c}")

    failed = [a for a in articles if a["status"] == "failed"]
    if failed:
        print(f"\n失敗的文章：")
        for a in failed:
            print(f"  {a['id']}: {a['title'][:40]} → {a['error']}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="微信文章抓取器")
    parser.add_argument("--retry", action="store_true", help="重試 failed 文章")
    parser.add_argument("--id", default=None, help="只抓指定 ID")
    parser.add_argument("--status", action="store_true", help="查看進度")
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        run_fetch(retry=args.retry, target_id=args.id)
