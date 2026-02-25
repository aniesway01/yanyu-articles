#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_all.py — 建置 YanYu 知識庫完整靜態網站（4 分類）
  1. 微信文章庫  2. 保險判決庫  3. Prompt 庫  4. AI 使用技巧
用法：python build_all.py
"""

import json, os, re, sys, io, datetime, shutil, logging
from pathlib import Path
from urllib.parse import quote

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import markdown
except ImportError:
    print("pip install markdown"); sys.exit(1)

# ─── Paths ───
BASE       = Path(r"C:\AntiGravityFile\YanYuInc")
SITE       = BASE / "site"
LOG_DIR    = BASE / "logs"
WC_STATE   = BASE / "wechat_articles" / "_state.json"
WC_ARTS    = BASE / "wechat_articles" / "articles"
JDG_DIR    = BASE / "judgments"
JDG_EB_DIR = JDG_DIR / "ebookhub"
PROMPT_DIR = BASE / "prompts"
PROMPT_SRC = Path(r"C:\AntiGravityFile\Project\facebookPrompt\_legacy_prompt_collection")
EBOOK_SRC  = Path(r"C:\AntiGravityFile\Project\ebookhub\library")


# ─── Logging ───
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_path = LOG_DIR / f"build_all_{datetime.datetime.now():%Y%m%d_%H%M%S}.log"
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(log_path, encoding="utf-8"),
              logging.StreamHandler(sys.stdout)])
log = logging.getLogger()

# ─── Shared CSS ───
CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f5f5;color:#333;line-height:1.6}
.ctn{max-width:960px;margin:0 auto;padding:20px}
a{color:#1a73e8;text-decoration:none}a:hover{text-decoration:underline}
header{background:#1a73e8;color:#fff;padding:40px 20px;text-align:center;margin-bottom:30px;border-radius:8px}
header h1{font-size:28px;margin-bottom:8px}header p{opacity:.9;font-size:14px}
nav{margin-bottom:20px}nav a{font-size:14px}
footer{text-align:center;padding:30px;color:#999;font-size:13px}
.stats{display:flex;gap:15px;justify-content:center;margin-top:15px;flex-wrap:wrap}
.stat{background:rgba(255,255,255,.2);padding:5px 15px;border-radius:20px;font-size:13px}
.cats{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin-bottom:30px}
.cc{background:#fff;border-radius:12px;padding:30px;text-align:center;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.1);transition:all .3s}
.cc:hover{transform:translateY(-4px);box-shadow:0 8px 24px rgba(0,0,0,.15)}
.cc-icon{font-size:48px;margin-bottom:15px}
.cc h2{font-size:20px;margin-bottom:8px}.cc p{font-size:14px;color:#666;margin-bottom:12px}
.cc .num{font-size:13px;color:#1a73e8;font-weight:500}
.card{background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.1);margin-bottom:12px;transition:transform .2s}
.card:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.1)}
.card h3{font-size:17px;margin-bottom:8px}.card h3 a{color:#1a73e8}
.meta{font-size:13px;color:#666;margin-bottom:8px}
.dl a{color:#1a73e8;margin-right:12px;font-size:13px}
.search{width:100%;padding:10px 15px;border:1px solid #ddd;border-radius:6px;font-size:14px;margin-bottom:15px}
.tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px}
.tag-\u4fdd\u96aa\u7406\u8ce0{background:#e8f0fe;color:#1a73e8}
.tag-\u91ab\u7642\u5065\u5eb7{background:#e6f4ea;color:#137333}
.tag-AI\u79d1\u6280{background:#fce8e6;color:#c5221f}
.tag-\u884c\u696d\u5206\u6790{background:#fef7e0;color:#e37400}
.tag-\u751f\u6d3b\u5176\u4ed6{background:#f3e8fd;color:#7627bb}
.hidden{display:none!important}
.tg-btns{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:15px}
.tg-btn{padding:5px 12px;border:1px solid #ddd;border-radius:15px;background:#fff;cursor:pointer;font-size:13px}
.tg-btn:hover,.tg-btn.active{background:#1a73e8;color:#fff;border-color:#1a73e8}
article{background:#fff;border-radius:8px;padding:30px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
article h1{font-size:24px;margin-bottom:15px;line-height:1.4}
.content{font-size:16px;line-height:1.8}
.content img{max-width:100%;height:auto;border-radius:4px;margin:15px 0}
.content p{margin-bottom:15px}
.content h2,.content h3{margin:25px 0 10px}
.content blockquote{border-left:3px solid #1a73e8;padding-left:15px;color:#555;margin:15px 0}
.content table{border-collapse:collapse;width:100%;margin:15px 0}
.content th,.content td{border:1px solid #ddd;padding:8px 12px;text-align:left}
.content th{background:#f5f5f5}
.content pre{background:#f8f8f8;padding:15px;border-radius:6px;overflow-x:auto;margin:15px 0}
.content code{font-size:14px}
.dl-btn{display:inline-block;padding:6px 14px;background:#1a73e8;color:#fff;border-radius:5px;margin-right:8px;font-size:13px;text-decoration:none}
.dl-btn:hover{background:#1557b0;text-decoration:none}
.dl-btn.sec{background:#5f6368}.dl-btn.sec:hover{background:#3c4043}
.yg{margin-bottom:20px}
.yg h3{font-size:16px;color:#1a73e8;margin-bottom:10px}
.fi{display:flex;justify-content:space-between;align-items:center;padding:10px 15px;background:#fafafa;border-radius:6px;margin-bottom:6px;flex-wrap:wrap;gap:8px}
.fi .sz{font-size:12px;color:#999}
.sec-title{font-size:20px;margin:30px 0 15px;padding-bottom:8px;border-bottom:2px solid #1a73e8}
"""

def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def page(title, body, back=None, extra_css="", extra_js=""):
    n = f'<nav><a href="{back}">&larr; \u8fd4\u56de</a></nav>' if back else ''
    sc = f'<script>{extra_js}</script>' if extra_js else ''
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{esc(title)} - YanYu \u77e5\u8b58\u5eab</title>
<style>{CSS}{extra_css}</style></head><body><div class="ctn">
{n}{body}
<footer><p><a href="https://github.com/aniesway01/yanyu-articles">GitHub Repo</a> | YanYu \u77e5\u8b58\u5eab</p></footer>
</div>{sc}</body></html>"""

def wf(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def md2html(text):
    return markdown.markdown(text, extensions=["tables","fenced_code"])

# ════════ Phase 1: Prepare Content ════════

def prepare_judgments():
    """Scan converted ebookhub markdown files (from convert_judgments.py)"""
    JDG_EB_DIR.mkdir(parents=True, exist_ok=True)
    eb_files = []
    # Scan existing converted markdown files
    for mf in sorted(JDG_EB_DIR.glob("*.md")):
        sz = mf.stat().st_size
        yr_m = re.search(r'^(\d{4})_', mf.name)
        yr = yr_m.group(1) if yr_m else "unknown"
        eb_files.append({"year": yr, "slug": mf.stem, "name": mf.name, "size_kb": round(sz/1024, 1)})
        log.info(f"\u5224\u6c7a MD: {mf.name} ({sz/1024:.0f}KB)")
    # Note image-only PDFs that couldn't be extracted
    scan_only = [
        {"year": "2014", "name": "\u4e2d\u56fd\u6cd5\u96622014\u5e74\u5ea6\u6848\u4f8b_\u4fdd\u9669\u7ea0\u7eb7.pdf", "note": "\u6383\u63cf\u5716\u7247\uff0c\u7121\u6cd5\u63d0\u53d6\u6587\u5b57"},
        {"year": "2015", "name": "\u4e2d\u56fd\u6cd5\u96622015\u5e74\u5ea6\u6848\u4f8b\u4fdd\u9669\u7ea0\u7eb7\uff08291\u9801\uff09.pdf", "note": "\u6383\u63cf\u5716\u7247\uff0c\u7121\u6cd5\u63d0\u53d6\u6587\u5b57"},
        {"year": "2017", "name": "\u4e2d\u56fd\u6cd5\u96622017\u5e74\u5ea6\u6848\u4f8b \u4fdd\u9669.pdf", "note": "\u6383\u63cf\u5716\u7247\uff0c\u7121\u6cd5\u63d0\u53d6\u6587\u5b57"},
        {"year": "2021", "name": "\u4e2d\u56fd\u6cd5\u96622021\u5e74\u5ea6\u6848\u4f8b\uff1a\u4fdd\u9669\u7ea0\u7eb7.pdf", "note": "\u6383\u63cf\u5716\u7247\uff0c\u7121\u6cd5\u63d0\u53d6\u6587\u5b57"},
        {"year": "2024", "name": "15.\u4fdd\u9669\u7ea0\u7eb7.pdf", "note": "\u6383\u63cf\u5716\u7247\uff0c\u7121\u6cd5\u63d0\u53d6\u6587\u5b57"},
    ]
    log.info(f"\u5224\u6c7a: {len(eb_files)} \u500b\u5df2\u8f49\u63db, {len(scan_only)} \u500b\u7121\u6cd5\u63d0\u53d6")
    return eb_files, scan_only

def prepare_prompts():
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    ebook_dir = PROMPT_DIR / "ebooks"
    ebook_dir.mkdir(exist_ok=True)
    materials = {
        "knowledge_base.md": PROMPT_SRC / "Artifacts" / "AI_Golden_Knowledge_Base.md",
        "url_report.md": PROMPT_SRC / "_Archive" / "AI_URL_Report.md",
        "compact_digest.md": PROMPT_SRC / "_Archive" / "AI_Compact_Digest.md",
        "rich_digest.md": PROMPT_SRC / "_Archive" / "AI_Rich_Digest.md",
        "related_data.md": PROMPT_SRC / "_Archive" / "AI_Related_Data.md",
        "group_list.md": PROMPT_SRC / "grouplist.md",
    }
    copied = []
    for dest_name, src in materials.items():
        if src.exists():
            dest = PROMPT_DIR / dest_name
            if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
                shutil.copy2(src, dest)
            copied.append({"slug": dest_name, "size_kb": round(src.stat().st_size / 1024, 1)})
            log.info(f"Prompt: {dest_name} ({src.stat().st_size/1024:.0f}KB)")
        else:
            log.warning(f"\u627e\u4e0d\u5230: {src}")
    # Ebooks — pick largest file per slug to avoid duplicates
    ebook_candidates = {}  # slug -> (path, size)
    if EBOOK_SRC.exists():
        for d in EBOOK_SRC.iterdir():
            if not d.is_dir():
                continue
            nm = d.name.lower()
            if "prompt" not in nm and "\u63d0\u793a\u5de5\u7a0b" not in nm:
                continue
            md_dir = d / "md"
            if not md_dir.exists():
                continue
            for mf in md_dir.glob("*.md"):
                if "bible" in nm: slug = "prompt_bible.md"
                elif "handbook" in nm and "\u63d0\u793a" not in nm: slug = "prompt_handbook.md"
                elif "ultimate" in nm or "mastering" in nm: slug = "prompt_guide.md"
                elif "\u63d0\u793a" in nm or "\u624b\u518c" in nm: slug = "prompt_handbook_zh.md"
                else: slug = re.sub(r'[^\w]', '_', d.name)[:40] + ".md"
                sz = mf.stat().st_size
                if slug not in ebook_candidates or sz > ebook_candidates[slug][1]:
                    ebook_candidates[slug] = (mf, sz)
    for slug, (mf, sz) in ebook_candidates.items():
        dest = ebook_dir / slug
        if not dest.exists() or mf.stat().st_mtime > dest.stat().st_mtime:
            shutil.copy2(mf, dest)
        copied.append({"slug": f"ebooks/{slug}", "size_kb": round(sz / 1024, 1)})
        log.info(f"Ebook: {slug} ({sz/1024:.0f}KB)")
    log.info(f"Prompt \u7d20\u6750: {len(copied)} \u500b")
    return copied

# ════════ Phase 2: Build Site ════════

def build_main_page(wc_n, wc_img, jdg_n, prm_n, tip_n):
    body = f"""
<header>
  <h1>YanYu \u77e5\u8b58\u5eab</h1>
  <p>\u4fdd\u96aa\u7406\u8ce0\u8aee\u8a62 \u00b7 \u5224\u6c7a\u7814\u7a76 \u00b7 AI \u63d0\u793a\u8a5e \u00b7 AI \u5de5\u5177\u6559\u5b78</p>
  <div class="stats"><span class="stat">\u66f4\u65b0\u65bc {datetime.datetime.now():%Y-%m-%d}</span></div>
</header>
<div class="cats">
  <div class="cc" onclick="location.href='wechat.html'">
    <div class="cc-icon">\U0001f4f0</div><h2>\u5fae\u4fe1\u6587\u7ae0\u5eab</h2>
    <p>ShawnCH \u8f49\u767c\u7684\u4fdd\u96aa\u7406\u8ce0\u3001\u91ab\u7642\u5065\u5eb7\u76f8\u95dc\u6587\u7ae0</p>
    <div class="num">{wc_n} \u7bc7\u6587\u7ae0 \u00b7 {wc_img} \u5f35\u5716\u7247</div>
  </div>
  <div class="cc" onclick="location.href='judgments.html'">
    <div class="cc-icon">\u2696\ufe0f</div><h2>\u4fdd\u96aa\u5224\u6c7a\u5eab</h2>
    <p>\u4e2d\u570b\u6cd5\u9662\u4fdd\u96aa\u7cfe\u7d1b\u5224\u6c7a\u6848\u4f8b\u96c6\uff082014-2025\uff09</p>
    <div class="num">{jdg_n} \u4efd\u5224\u6c7a\u8cc7\u6599</div>
  </div>
  <div class="cc" onclick="location.href='prompts.html'">
    <div class="cc-icon">\U0001f916</div><h2>Prompt \u5eab</h2>
    <p>AI \u63d0\u793a\u8a5e\u6848\u4f8b\u3001\u6559\u5b78\u8cc7\u6e90\u8207\u96fb\u5b50\u66f8</p>
    <div class="num">{prm_n} \u4efd\u8cc7\u6599</div>
  </div>
  <div class="cc" onclick="location.href='ai-tips.html'">
    <div class="cc-icon">\U0001f4a1</div><h2>AI \u4f7f\u7528\u6280\u5de7</h2>
    <p>AI \u5de5\u5177\u6559\u5b78\u6587\u7ae0\uff08\u96fb\u8166\u738b\u963f\u9054\u7b49\uff09</p>
    <div class="num">{tip_n} \u7bc7\u6587\u7ae0</div>
  </div>
</div>"""
    wf(SITE / "index.html", page("\u9996\u9801", body))
    log.info("\u5efa\u7f6e: \u9996\u9801 index.html")

def build_wechat():
    with open(WC_STATE, "r", encoding="utf-8") as f:
        state = json.load(f)
    articles = sorted([a for a in state["articles"] if a["status"] == "fetched"],
                      key=lambda x: x.get("chat_time", ""), reverse=True)
    total_imgs, cards, tag_set = 0, [], set()
    for art in articles:
        slug = art.get("slug", "")
        if not slug: continue
        md_file = WC_ARTS / slug / "index.md"
        if not md_file.exists(): continue
        with open(md_file, "r", encoding="utf-8") as f:
            md_text = f.read()
        ch = md2html(md_text)
        ch = ch.replace('src="assets/', f'src="../../wechat_articles/articles/{slug}/assets/')
        ch = re.sub(r'<h1>.*?</h1>\s*<blockquote>.*?</blockquote>\s*<hr\s*/?>', '', ch, count=1, flags=re.DOTALL)
        title = art.get("real_title", art.get("title", "untitled"))
        author = art.get("author", "\u672a\u77e5")
        tags = art.get("tags", [])
        ct = art.get("chat_time", "")
        url = art.get("url", "")
        for t in tags: tag_set.add(t)
        th = " ".join(f'<span class="tag tag-{t}">{t}</span>' for t in tags)
        assets = WC_ARTS / slug / "assets"
        if assets.exists(): total_imgs += len(list(assets.iterdir()))
        # Article page
        ab = f"""<article><h1>{esc(title)}</h1>
<div class="meta"><strong>\u4f5c\u8005</strong>\uff1a{esc(author)} | <strong>\u8f49\u767c\u6642\u9593</strong>\uff1a{ct}\uff08by ShawnCH\uff09<br>
<a href="{url}" target="_blank">\u67e5\u770b\u539f\u6587</a><div style="margin-top:8px">{th}</div></div>
<div class="content">{ch}</div>
<div style="margin-top:25px;padding-top:20px;border-top:1px solid #eee"><h3 style="font-size:15px;margin-bottom:10px">\u4e0b\u8f09</h3>
<a class="dl-btn" href="../../wechat_articles/articles/{slug}/index.md" download>Markdown</a>
<a class="dl-btn sec" href="../../wechat_articles/articles/{slug}/article.txt" download>\u7d14\u6587\u5b57</a></div></article>"""
        wf(SITE / slug / "index.html", page(title, ab, back="../wechat.html"))
        cards.append(f'<div class="card" data-title="{esc(title)}" data-tags="{",".join(tags)}">'
            f'<h3><a href="{slug}/index.html">{esc(title)}</a></h3>'
            f'<div class="meta">{ct} | {esc(author)}</div><div>{th}</div>'
            f'<div class="dl"><a href="../wechat_articles/articles/{slug}/index.md" download>MD</a>'
            f' <a href="../wechat_articles/articles/{slug}/article.txt" download>TXT</a>'
            f' <a href="{url}" target="_blank">\u539f\u6587</a></div></div>')
    tg = '<button class="tg-btn active" onclick="ft(this,\'\')">\u5168\u90e8</button>\n'
    for t in sorted(tag_set):
        tg += f'<button class="tg-btn" onclick="ft(this,\'{t}\')">{t}</button>\n'
    body = f"""<header><h1>\U0001f4f0 \u5fae\u4fe1\u6587\u7ae0\u5eab</h1>
<p>ShawnCH\uff08\u4f55\u667a\u7fd4\uff09\u8f49\u767c\u7684\u4fdd\u96aa\u7406\u8ce0\u3001\u91ab\u7642\u5065\u5eb7\u76f8\u95dc\u6587\u7ae0</p>
<div class="stats"><span class="stat">\u5171 {len(articles)} \u7bc7\u6587\u7ae0</span><span class="stat">{total_imgs} \u5f35\u5716\u7247</span></div></header>
<input class="search" type="text" id="q" placeholder="\u641c\u5c0b\u6587\u7ae0\u6a19\u984c..." oninput="fa()">
<div class="tg-btns">{tg}</div><div id="arts">{"".join(cards)}</div>"""
    js = "let ct='';function ft(b,t){ct=t;document.querySelectorAll('.tg-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');fa();}function fa(){const q=document.getElementById('q').value.toLowerCase();document.querySelectorAll('.card').forEach(c=>{const m=(!q||c.dataset.title.toLowerCase().includes(q))&&(!ct||c.dataset.tags.includes(ct));c.classList.toggle('hidden',!m);});}"
    wf(SITE / "wechat.html", page("\u5fae\u4fe1\u6587\u7ae0\u5eab", body, back="index.html", extra_js=js))
    log.info(f"\u5efa\u7f6e: \u5fae\u4fe1\u6587\u7ae0\u5eab ({len(articles)} \u7bc7, {total_imgs} \u5716)")
    return len(articles), total_imgs

def build_judgments(eb_files, scan_only):
    # 1. Original curated judgments (11 markdown files in judgments/)
    md_jdgs = []
    for mf in sorted(JDG_DIR.glob("*.md")):
        with open(mf, "r", encoding="utf-8") as f:
            text = f.read()
        m = re.search(r'^#\s+(.+)', text)
        title = m.group(1) if m else mf.stem
        m2 = re.search(r'\u6848\u865f[^\|]*\|\s*(.+)', text)
        case_no = m2.group(1).strip() if m2 else ""
        slug = mf.stem
        md_jdgs.append({"slug": slug, "title": title, "case_no": case_no, "text": text})
    # Individual curated judgment pages
    for j in md_jdgs:
        ch = md2html(j["text"])
        ab = f'<article><div class="content">{ch}</div><div style="margin-top:25px;padding-top:20px;border-top:1px solid #eee"><a class="dl-btn" href="../../../judgments/{quote(j["slug"])}.md" download>\u4e0b\u8f09 Markdown</a></div></article>'
        wf(SITE / "judgment" / j["slug"] / "index.html", page(j["title"], ab, back="../../judgments.html"))
    # 2. Ebookhub converted markdown files - organize by year
    eb_by_year = {}
    for ef in eb_files:
        eb_by_year.setdefault(ef["year"], []).append(ef)
    # Build individual ebookhub judgment pages
    for ef in eb_files:
        md_path = JDG_EB_DIR / ef["name"]
        with open(md_path, "r", encoding="utf-8") as f:
            text = f.read()
        ch = md2html(text)
        ab = f'<article><div class="content">{ch}</div><div style="margin-top:25px;padding-top:20px;border-top:1px solid #eee"><a class="dl-btn" href="../../../judgments/ebookhub/{quote(ef["name"])}" download>\u4e0b\u8f09 Markdown</a></div></article>'
        wf(SITE / "judgment" / ef["slug"] / "index.html", page(ef["slug"], ab, back="../../judgments.html"))
    # 3. Build listing page
    md_cards = ""
    for j in md_jdgs:
        md_cards += f'<div class="card"><h3><a href="judgment/{j["slug"]}/index.html">{esc(j["title"])}</a></h3><div class="meta">{esc(j["case_no"])}</div><div class="dl"><a href="../judgments/{quote(j["slug"])}.md" download>MD</a></div></div>\n'
    eb_html = ""
    for yr in sorted(eb_by_year):
        eb_html += f'<div class="yg"><h3>{yr} \u5e74</h3>\n'
        for ef in eb_by_year[yr]:
            eb_html += f'<div class="fi"><span><a href="judgment/{ef["slug"]}/index.html">{esc(ef["name"])}</a> <span class="sz">({ef["size_kb"]}KB)</span></span><a class="dl-btn" href="../judgments/ebookhub/{quote(ef["name"])}" download>\u4e0b\u8f09 MD</a></div>\n'
        eb_html += '</div>\n'
    # Add scan-only entries
    scan_html = ""
    if scan_only:
        scan_html = '<div class="yg"><h3>\u672a\u80fd\u63d0\u53d6\u6587\u5b57\uff08\u539f\u59cb PDF \u70ba\u6383\u63cf\u5716\u7247\uff09</h3>\n'
        for s in scan_only:
            scan_html += f'<div class="fi"><span>{s["year"]} \u5e74 \u2014 {esc(s["name"])} <span class="sz">({s["note"]})</span></span></div>\n'
        scan_html += '</div>\n'
    total = len(md_jdgs) + len(eb_files) + len(scan_only)
    body = f"""<header><h1>\u2696\ufe0f \u4fdd\u96aa\u5224\u6c7a\u5eab</h1>
<p>\u4e2d\u570b\u6cd5\u9662\u4fdd\u96aa\u7cfe\u7d1b\u5224\u6c7a\u6848\u4f8b\u96c6\uff082014-2025\uff09</p>
<div class="stats"><span class="stat">{len(md_jdgs)} \u4efd\u7cbe\u9078\u5224\u6c7a</span><span class="stat">{len(eb_files)} \u4efd\u5e74\u5ea6\u6848\u4f8b\uff08\u6587\u5b57\u7248\uff09</span></div></header>
<h2 class="sec-title">\u88c1\u5224\u6587\u66f8\u7db2 \u00b7 \u7cbe\u9078\u5224\u6c7a\u5206\u6790</h2>
<p style="margin-bottom:15px;color:#666;font-size:14px">\u4f86\u6e90\uff1a\u4e2d\u570b\u88c1\u5224\u6587\u66f8\u7db2\uff0c\u4eba\u8eab\u4fdd\u96aa\u5408\u540c\u7cfe\u7d1b\u6848\u4ef6</p>
{md_cards}
<h2 class="sec-title">\u4e2d\u570b\u6cd5\u9662\u5e74\u5ea6\u6848\u4f8b \u00b7 \u4fdd\u96aa\u7cfe\u7d1b\uff08PDF \u8f49\u6587\u5b57\uff09</h2>
<p style="margin-bottom:15px;color:#666;font-size:14px">\u4f86\u6e90\uff1a\u4e2d\u570b\u6cd5\u9662\u5e74\u5ea6\u6848\u4f8b\u53e2\u66f8\uff082014-2025\uff09\uff0c\u5df2\u5f9e PDF \u63d0\u53d6\u70ba\u7d14\u6587\u5b57\u683c\u5f0f</p>
{eb_html}{scan_html}"""
    wf(SITE / "judgments.html", page("\u4fdd\u96aa\u5224\u6c7a\u5eab", body, back="index.html"))
    log.info(f"\u5efa\u7f6e: \u5224\u6c7a\u5eab ({len(md_jdgs)} \u7cbe\u9078 + {len(eb_files)} \u5e74\u5ea6\u6848\u4f8b + {len(scan_only)} \u7121\u6cd5\u63d0\u53d6)")
    return total

def build_prompts(prompt_files):
    INFO = {
        "knowledge_base.md": ("\u77e5\u8b58\u7cbe\u83ef\u5eab", "13 \u7bc7\u6559\u5b78\u6587\u7ae0 + 42 \u652f\u5f71\u7247\u9023\u7d50", "T\u5ba2\u90a6\u3001\u96fb\u8166\u73a9\u7269\u3001Skye Prompts Club \u7b49", True),
        "url_report.md": ("AI \u8cc7\u6e90\u9023\u7d50\u5f59\u6574", "227 YouTube + 148 \u7db2\u7ad9\u9023\u7d50", "Facebook AI \u793e\u5718\u722c\u87f2", True),
        "compact_digest.md": ("\u793e\u7fa4\u8cbc\u6587\u6458\u8981\uff08\u7cbe\u7c21\u7248\uff09", "475 \u689d Facebook AI \u793e\u5718\u8cbc\u6587\u6458\u8981", "75 \u500b Facebook AI/\u79d1\u6280\u793e\u5718", True),
        "rich_digest.md": ("\u793e\u7fa4\u8cbc\u6587\u6458\u8981\uff08\u5b8c\u6574\u7248\uff09", "475 \u689d\u8cbc\u6587\u5b8c\u6574\u7248\u6458\u8981", "75 \u500b Facebook AI/\u79d1\u6280\u793e\u5718", True),
        "related_data.md": ("Facebook AI \u6578\u64da\u96c6", "583 \u7b46 Facebook AI \u76f8\u95dc\u8cc7\u6599", "\u500b\u4eba Facebook \u8cc7\u6599\u532f\u51fa", False),
        "group_list.md": ("Facebook \u793e\u5718\u6307\u5357", "75 \u500b AI/\u79d1\u6280\u76f8\u95dc Facebook \u793e\u5718\u5217\u8868", "\u7528\u6236\u8a02\u95b1\u793e\u5718", True),
        "ebooks/prompt_bible.md": ("The AI Prompt Bible", "\u5b8c\u6574\u96fb\u5b50\u66f8 \u2014 AI \u63d0\u793a\u8a5e\u8056\u7d93", "Anton Volney \u8457", True),
        "ebooks/prompt_handbook.md": ("AI Prompt Engineering Handbook", "\u63d0\u793a\u5de5\u7a0b\u624b\u518a\uff08\u82f1\u6587\u7248\uff09", "Roman Lahinouski \u8457", True),
        "ebooks/prompt_guide.md": ("The Ultimate AI Prompt Engineering Guide", "\u7d42\u6975\u63d0\u793a\u5de5\u7a0b\u6307\u5357", "Ink \u8457", True),
        "ebooks/prompt_handbook_zh.md": ("AI \u63d0\u793a\u5de5\u7a0b\u624b\u518a\uff08\u4e2d\u6587\u7248\uff09", "\u63d0\u793a\u5de5\u7a0b\u624b\u518a\u4e2d\u6587\u7ffb\u8b6f\u7248", "Roman Lahinouski \u8457, \u4e2d\u8b6f", True),
    }
    cards_edu, cards_community, cards_ebook = "", "", ""
    rendered = 0
    for slug, (title, desc, source, render) in INFO.items():
        src_file = PROMPT_DIR / slug
        if not src_file.exists():
            log.warning(f"Prompt \u4e0d\u5b58\u5728: {src_file}")
            continue
        sz = src_file.stat().st_size
        sz_s = f"{sz/1024:.0f}KB" if sz < 1048576 else f"{sz/1048576:.1f}MB"
        ps = slug.replace("/", "_").replace(".md", "")
        if render:
            with open(src_file, "r", encoding="utf-8") as f:
                text = f.read()
            ch = md2html(text)
            ab = f'<article><h1>{esc(title)}</h1><div class="meta"><strong>\u4f86\u6e90</strong>\uff1a{esc(source)} | <strong>\u5927\u5c0f</strong>\uff1a{sz_s}</div><div class="content">{ch}</div><div style="margin-top:25px;padding-top:20px;border-top:1px solid #eee"><a class="dl-btn" href="../../../prompts/{quote(slug)}" download>\u4e0b\u8f09\u539f\u59cb\u6a94</a></div></article>'
            wf(SITE / "prompt" / ps / "index.html", page(title, ab, back="../../prompts.html"))
            rendered += 1
            card = f'<div class="card"><h3><a href="prompt/{ps}/index.html">{esc(title)}</a></h3><div class="meta">{esc(desc)} \u00b7 {sz_s}</div><div class="meta">\u4f86\u6e90\uff1a{esc(source)}</div><div class="dl"><a href="prompt/{ps}/index.html">\u95b1\u8b80</a> <a href="../prompts/{quote(slug)}" download>\u4e0b\u8f09</a></div></div>\n'
        else:
            card = f'<div class="card"><h3>{esc(title)}</h3><div class="meta">{esc(desc)} \u00b7 {sz_s}</div><div class="meta">\u4f86\u6e90\uff1a{esc(source)}</div><div class="dl"><a href="../prompts/{quote(slug)}" download>\u4e0b\u8f09\u539f\u59cb\u6a94\uff08{sz_s}\uff09</a></div></div>\n'
        # Categorize
        if "ebook" in slug:
            cards_ebook += card
        elif slug in ("compact_digest.md", "rich_digest.md", "group_list.md", "related_data.md"):
            cards_community += card
        else:
            cards_edu += card
    body = f"""<header><h1>\U0001f916 Prompt \u5eab</h1>
<p>AI \u63d0\u793a\u8a5e\u6848\u4f8b\u3001\u6559\u5b78\u8cc7\u6e90\u3001\u793e\u7fa4\u7cbe\u83ef\u8207\u96fb\u5b50\u66f8</p>
<div class="stats"><span class="stat">{len(INFO)} \u4efd\u8cc7\u6599</span><span class="stat">\u542b 4 \u672c Prompt \u5de5\u7a0b\u96fb\u5b50\u66f8</span></div></header>
<h2 class="sec-title">\u6559\u5b78\u8207\u6848\u4f8b</h2>{cards_edu}
<h2 class="sec-title">\u793e\u7fa4\u8cc7\u6e90</h2>{cards_community}
<h2 class="sec-title">Prompt \u5de5\u7a0b\u96fb\u5b50\u66f8</h2>{cards_ebook}"""
    wf(SITE / "prompts.html", page("Prompt \u5eab", body, back="index.html"))
    log.info(f"\u5efa\u7f6e: Prompt \u5eab ({rendered} \u9801\u9762)")
    return len(INFO)

def build_tips():
    body = """<header><h1>\U0001f4a1 AI \u4f7f\u7528\u6280\u5de7</h1>
<p>AI \u5de5\u5177\u6559\u5b78\u6587\u7ae0\uff08\u96fb\u8166\u738b\u963f\u9054\u7b49\uff09</p>
<div class="stats"><span class="stat">\u5efa\u7f6e\u4e2d...</span></div></header>
<div class="card"><h3>\U0001f6a7 \u5167\u5bb9\u6536\u96c6\u4e2d</h3>
<p style="margin-top:10px;color:#666">
\u8a08\u756b\u6536\u9304\u4f86\u6e90\uff1a<br>
\u00b7 <strong>\u96fb\u8166\u738b\u963f\u9054</strong>\uff08kocpc.com.tw\uff09\u2014 NotebookLM\u3001AI \u5de5\u5177\u6559\u5b78<br>
\u00b7 \u5176\u4ed6 AI \u5de5\u5177\u5be6\u7528\u6559\u5b78\u6587\u7ae0<br><br>
\u6240\u6709\u6587\u7ae0\u5c07\u9644\u4e0a\u539f\u59cb\u4f86\u6e90\u9023\u7d50\u3002</p></div>"""
    wf(SITE / "ai-tips.html", page("AI \u4f7f\u7528\u6280\u5de7", body, back="index.html"))
    log.info("\u5efa\u7f6e: AI \u4f7f\u7528\u6280\u5de7\uff08placeholder\uff09")
    return 0

# ════════ Main ════════

def main():
    log.info("=" * 50)
    log.info("YanYu \u77e5\u8b58\u5eab\u5efa\u7f6e\u958b\u59cb")
    log.info("=" * 50)
    SITE.mkdir(parents=True, exist_ok=True)
    # Phase 1
    log.info("-- Phase 1: \u6e96\u5099\u5167\u5bb9 --")
    eb_files, scan_only = prepare_judgments()
    pf = prepare_prompts()
    # Phase 2
    log.info("-- Phase 2: \u5efa\u7f6e\u7db2\u7ad9 --")
    wc_n, wc_img = build_wechat()
    jdg_n = build_judgments(eb_files, scan_only)
    prm_n = build_prompts(pf)
    tip_n = build_tips()
    build_main_page(wc_n, wc_img, jdg_n, prm_n, tip_n)
    log.info("=" * 50)
    log.info(f"\u5b8c\u6210: \u5fae\u4fe1{wc_n} | \u5224\u6c7a{jdg_n} | Prompt{prm_n} | AI\u6280\u5de7{tip_n}")
    log.info(f"\u65e5\u8a8c: {log_path}")

if __name__ == "__main__":
    main()
