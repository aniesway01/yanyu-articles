#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build GitHub Pages Site — 從抓取結果生成靜態網站
生成：index.html（文章索引）+ 各文章獨立頁面 + 下載檔案

用法：python build_site.py
"""

import json, os, re, sys, io, datetime, shutil
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import markdown
except ImportError:
    print("安裝 markdown: pip install markdown")
    sys.exit(1)

BASE_DIR = Path(r"C:\AntiGravityFile\YanYuInc")
STATE_FILE = BASE_DIR / "wechat_articles" / "_state.json"
ARTICLES_DIR = BASE_DIR / "wechat_articles" / "articles"
SITE_DIR = BASE_DIR / "site"

# === HTML 模板 ===
INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YanYu 微信文章庫</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }
.container { max-width: 960px; margin: 0 auto; padding: 20px; }
header { background: #1a73e8; color: white; padding: 40px 20px; text-align: center; margin-bottom: 30px; border-radius: 8px; }
header h1 { font-size: 28px; margin-bottom: 8px; }
header p { opacity: 0.9; font-size: 14px; }
.stats { display: flex; gap: 15px; justify-content: center; margin-top: 15px; flex-wrap: wrap; }
.stat { background: rgba(255,255,255,0.2); padding: 5px 15px; border-radius: 20px; font-size: 13px; }
.filters { margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.filters input { flex: 1; min-width: 200px; padding: 10px 15px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
.tag-filters { display: flex; gap: 8px; flex-wrap: wrap; }
.tag-btn { padding: 5px 12px; border: 1px solid #ddd; border-radius: 15px; background: white; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.tag-btn:hover, .tag-btn.active { background: #1a73e8; color: white; border-color: #1a73e8; }
.article-list { display: flex; flex-direction: column; gap: 12px; }
.article-card { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); transition: transform 0.2s; }
.article-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.article-card h3 { font-size: 17px; margin-bottom: 8px; }
.article-card h3 a { color: #1a73e8; text-decoration: none; }
.article-card h3 a:hover { text-decoration: underline; }
.meta { font-size: 13px; color: #666; margin-bottom: 8px; }
.tags { display: flex; gap: 6px; flex-wrap: wrap; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.tag-保險理賠 { background: #e8f0fe; color: #1a73e8; }
.tag-醫療健康 { background: #e6f4ea; color: #137333; }
.tag-AI科技 { background: #fce8e6; color: #c5221f; }
.tag-行業分析 { background: #fef7e0; color: #e37400; }
.tag-生活其他 { background: #f3e8fd; color: #7627bb; }
.downloads { margin-top: 8px; font-size: 13px; }
.downloads a { color: #1a73e8; text-decoration: none; margin-right: 12px; }
.downloads a:hover { text-decoration: underline; }
footer { text-align: center; padding: 30px; color: #999; font-size: 13px; }
.hidden { display: none !important; }
</style>
</head>
<body>
<div class="container">
<header>
  <h1>YanYu 微信文章庫</h1>
  <p>ShawnCH（何智翔）轉發的保險理賠、醫療健康相關文章整理</p>
  <div class="stats">
    <span class="stat">共 {total} 篇文章</span>
    <span class="stat">{img_count} 張圖片</span>
    <span class="stat">更新於 {update_date}</span>
  </div>
</header>

<div class="filters">
  <input type="text" id="search" placeholder="搜尋文章標題..." oninput="filterArticles()">
</div>
<div class="tag-filters" style="margin-bottom: 15px;">
  <button class="tag-btn active" onclick="filterByTag(this, '')" data-tag="">全部</button>
  {tag_buttons}
</div>

<div class="article-list" id="articles">
{article_cards}
</div>

<footer>
  <p>資料來源：微信聊天記錄自動提取 | <a href="https://github.com/aniesway01/yanyu-articles">GitHub Repo</a></p>
</footer>
</div>

<script>
let currentTag = '';
function filterByTag(btn, tag) {
  currentTag = tag;
  document.querySelectorAll('.tag-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  filterArticles();
}
function filterArticles() {
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('.article-card').forEach(card => {
    const title = card.dataset.title.toLowerCase();
    const tags = card.dataset.tags;
    const matchSearch = !q || title.includes(q);
    const matchTag = !currentTag || tags.includes(currentTag);
    card.classList.toggle('hidden', !(matchSearch && matchTag));
  });
}
</script>
</body>
</html>"""

ARTICLE_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - YanYu 文章庫</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f5f5f5; color: #333; line-height: 1.8; }}
.container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
nav {{ margin-bottom: 20px; }}
nav a {{ color: #1a73e8; text-decoration: none; font-size: 14px; }}
nav a:hover {{ text-decoration: underline; }}
article {{ background: white; border-radius: 8px; padding: 30px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
article h1 {{ font-size: 24px; margin-bottom: 15px; line-height: 1.4; }}
.meta {{ font-size: 13px; color: #666; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #eee; }}
.meta a {{ color: #1a73e8; }}
.content {{ font-size: 16px; }}
.content img {{ max-width: 100%; height: auto; border-radius: 4px; margin: 15px 0; }}
.content p {{ margin-bottom: 15px; }}
.content h2, .content h3 {{ margin: 25px 0 10px; }}
.content blockquote {{ border-left: 3px solid #1a73e8; padding-left: 15px; color: #555; margin: 15px 0; }}
.downloads {{ margin-top: 25px; padding-top: 20px; border-top: 1px solid #eee; }}
.downloads h3 {{ font-size: 15px; margin-bottom: 10px; }}
.dl-btn {{ display: inline-block; padding: 8px 16px; background: #1a73e8; color: white; text-decoration: none; border-radius: 5px; margin-right: 10px; font-size: 14px; }}
.dl-btn:hover {{ background: #1557b0; }}
.dl-btn.secondary {{ background: #5f6368; }}
.dl-btn.secondary:hover {{ background: #3c4043; }}
.tags {{ margin-top: 10px; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; }}
.tag-保險理賠 {{ background: #e8f0fe; color: #1a73e8; }}
.tag-醫療健康 {{ background: #e6f4ea; color: #137333; }}
.tag-AI科技 {{ background: #fce8e6; color: #c5221f; }}
.tag-行業分析 {{ background: #fef7e0; color: #e37400; }}
.tag-生活其他 {{ background: #f3e8fd; color: #7627bb; }}
footer {{ text-align: center; padding: 30px; color: #999; font-size: 13px; }}
</style>
</head>
<body>
<div class="container">
<nav><a href="../index.html">&larr; 返回文章列表</a></nav>
<article>
  <h1>{title}</h1>
  <div class="meta">
    <strong>作者</strong>：{author} | <strong>轉發時間</strong>：{chat_time}（by ShawnCH）<br>
    <a href="{original_url}" target="_blank">查看原文</a>
    <div class="tags" style="margin-top: 8px;">
      {tag_html}
    </div>
  </div>
  <div class="content">
    {content_html}
  </div>
  <div class="downloads">
    <h3>下載</h3>
    <a class="dl-btn" href="{md_path}" download>Markdown</a>
    <a class="dl-btn secondary" href="{txt_path}" download>純文字</a>
  </div>
</article>
<footer>
  <p>原文連結：<a href="{original_url}">{original_url_short}</a></p>
</footer>
</div>
</body>
</html>"""


def build():
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    articles = [a for a in state["articles"] if a["status"] == "fetched"]
    articles.sort(key=lambda x: x.get("chat_time", ""), reverse=True)

    SITE_DIR.mkdir(parents=True, exist_ok=True)

    # Count images
    total_imgs = 0

    # Build individual pages + collect cards
    cards_html = []
    tag_set = set()

    for art in articles:
        slug = art.get("slug", "")
        if not slug:
            continue

        art_src = ARTICLES_DIR / slug
        md_file = art_src / "index.md"
        if not md_file.exists():
            continue

        # Read markdown
        with open(md_file, "r", encoding="utf-8") as f:
            md_text = f.read()

        # Convert to HTML
        content_html = markdown.markdown(md_text, extensions=["tables", "fenced_code"])

        # Fix image paths: page is at site/slug/index.html, images at wechat_articles/articles/slug/assets/
        # Need ../../ to go from site/slug/ up to repo root
        content_html = content_html.replace('src="assets/', f'src="../../wechat_articles/articles/{slug}/assets/')

        # Strip the markdown-generated header (title + metadata block) to avoid duplication
        # The template already renders title/author/tags, so remove them from content
        content_html = re.sub(
            r'<h1>.*?</h1>\s*<blockquote>.*?</blockquote>\s*<hr\s*/?>',
            '',
            content_html,
            count=1,
            flags=re.DOTALL
        )

        title = art.get("real_title", art.get("title", "untitled"))
        author = art.get("author", "未知")
        tags = art.get("tags", [])
        chat_time = art.get("chat_time", "")
        url = art.get("url", "")

        for t in tags:
            tag_set.add(t)

        tag_html = " ".join(f'<span class="tag tag-{t}">{t}</span>' for t in tags)

        # Count images
        assets_dir = art_src / "assets"
        if assets_dir.exists():
            total_imgs += len(list(assets_dir.iterdir()))

        # Build article page
        page_dir = SITE_DIR / slug
        page_dir.mkdir(parents=True, exist_ok=True)

        page_html = ARTICLE_PAGE_TEMPLATE.format(
            title=title,
            author=author,
            chat_time=chat_time,
            original_url=url,
            original_url_short=url[:80] + "..." if len(url) > 80 else url,
            content_html=content_html,
            tag_html=tag_html,
            md_path=f"../../wechat_articles/articles/{slug}/index.md",
            txt_path=f"../../wechat_articles/articles/{slug}/article.txt",
        )

        page_file = page_dir / "index.html"
        with open(page_file, "w", encoding="utf-8") as f:
            f.write(page_html)

        # Build card for index
        card = f"""<div class="article-card" data-title="{title}" data-tags="{','.join(tags)}">
  <h3><a href="{slug}/index.html">{title}</a></h3>
  <div class="meta">{chat_time} | {author}</div>
  <div class="tags">{tag_html}</div>
  <div class="downloads">
    <a href="../wechat_articles/articles/{slug}/index.md" download>MD</a>
    <a href="../wechat_articles/articles/{slug}/article.txt" download>TXT</a>
    <a href="{url}" target="_blank">原文</a>
  </div>
</div>"""
        cards_html.append(card)

    # Tag buttons
    tag_buttons = ""
    for t in sorted(tag_set):
        tag_buttons += f'<button class="tag-btn" onclick="filterByTag(this, \'{t}\')" data-tag="{t}">{t}</button>\n'

    # Build index (use replace instead of .format to avoid CSS brace conflicts)
    index_html = INDEX_TEMPLATE
    index_html = index_html.replace("{total}", str(len(articles)))
    index_html = index_html.replace("{img_count}", str(total_imgs))
    index_html = index_html.replace("{update_date}", datetime.datetime.now().strftime("%Y-%m-%d"))
    index_html = index_html.replace("{tag_buttons}", tag_buttons)
    index_html = index_html.replace("{article_cards}", "\n".join(cards_html))

    with open(SITE_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"網站建置完成：{len(articles)} 篇文章, {total_imgs} 張圖片")
    print(f"  索引頁：site/index.html")
    print(f"  文章頁：site/<slug>/index.html")


if __name__ == "__main__":
    build()
