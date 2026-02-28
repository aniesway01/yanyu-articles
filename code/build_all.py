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
PROMPT_IDX = PROMPT_DIR / "_index.json"
PROMPT_YAML_DIR = PROMPT_DIR / "roles"
PROMPT_SRC = Path(r"C:\AntiGravityFile\Project\facebookPrompt\_legacy_prompt_collection")
EBOOK_SRC  = Path(r"C:\AntiGravityFile\Project\ebookhub\library")
TIPS_DIR   = BASE / "ai_tips"
TIPS_STATE = TIPS_DIR / "_state.json"
COMM_DIR   = BASE / "community_ai"
COMM_REPOS = COMM_DIR / "github_repos.json"
COMM_MSGS  = COMM_DIR / "_raw_ai_messages.json"


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
.tag-裁定書{background:#fff3e0;color:#e65100}
.tag-判決書{background:#e3f2fd;color:#1565c0}
.tag-文書{background:#f3e8fd;color:#7627bb}
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
.bm-nav{position:sticky;top:0;z-index:100;background:#fff;padding:8px 0;border-bottom:1px solid #eee;display:flex;gap:6px;flex-wrap:wrap;margin-bottom:15px}
.bm-nav a{font-size:13px;padding:4px 12px;border:1px solid #1a73e8;border-radius:15px;color:#1a73e8;text-decoration:none;white-space:nowrap}
.bm-nav a:hover{background:#1a73e8;color:#fff;text-decoration:none}
.filter-group{margin-bottom:12px}
.filter-group summary{font-size:14px;font-weight:600;color:#333;cursor:pointer;padding:6px 0}
.filter-group summary:hover{color:#1a73e8}
.ftag{display:inline-block;padding:3px 10px;border:1px solid #ddd;border-radius:12px;font-size:12px;margin:2px;cursor:pointer;background:#fff;transition:all .2s}
.ftag:hover{border-color:#1a73e8;color:#1a73e8}
.ftag.active{background:#1a73e8;color:#fff;border-color:#1a73e8}
.ftag .cnt{font-size:10px;color:#999;margin-left:2px}
.ftag.active .cnt{color:rgba(255,255,255,.8)}
.card-tags{display:flex;gap:4px;flex-wrap:wrap;margin-top:6px}
.card-tags span{font-size:11px;padding:1px 7px;border-radius:10px;white-space:nowrap}
.ct-nature{background:#e8f5e9;color:#2e7d32}
.ct-ins{background:#e3f2fd;color:#1565c0}
.ct-disp{background:#fff3e0;color:#e65100}
.ct-verdict{background:#fce4ec;color:#c62828}
.ct-level{background:#f3e8fd;color:#7627bb}
"""

def extract_case_number(raw):
    """從完整 case_no 提取括號內核心案號，如 '江苏省...（2016）苏10民终字第2629号...' -> '(2016)苏10民终字第2629号'"""
    # 支援簡體「号」和繁體「號」
    m = re.search(r'[（(]\d{4}[）)][^号號]*[号號]', raw)
    if m:
        s = m.group(0)
        s = s.replace('（', '(').replace('）', ')').replace('號', '号')
        return s
    # fallback: 清除尾部垃圾 ( | 等)
    return re.sub(r'\s*\|.*$', '', raw).strip()

def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def page(title, body, back=None, extra_css="", extra_js=""):
    n = f'<nav><a href="{back}">&larr; \u8fd4\u56de</a></nav>' if back else ''
    sc = f'<script>{extra_js}</script>' if extra_js else ''
    # BOM download script: intercept .md download links, prepend UTF-8 BOM
    bom_js = r"""<script>document.addEventListener('click',function(e){var a=e.target.closest('a[download]');if(!a)return;var h=a.getAttribute('href')||'';if(!h.endsWith('.md')&&!h.endsWith('.txt'))return;e.preventDefault();fetch(a.href).then(function(r){return r.text()}).then(function(t){var b=new Blob(['\uFEFF'+t],{type:'text/markdown;charset=utf-8'});var u=URL.createObjectURL(b);var d=document.createElement('a');d.href=u;d.download=h.split('/').pop();document.body.appendChild(d);d.click();document.body.removeChild(d);URL.revokeObjectURL(u)}).catch(function(){window.open(a.href)})})</script>"""
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{esc(title)} - YanYu \u77e5\u8b58\u5eab</title>
<style>{CSS}{extra_css}</style></head><body><div class="ctn">
{n}{body}
<footer><p><a href="https://github.com/aniesway01/yanyu-articles">GitHub Repo</a> | YanYu \u77e5\u8b58\u5eab</p></footer>
</div>{bom_js}{sc}</body></html>"""

def wf(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def md2html(text):
    # 前處理：把【xxx】行轉為 Markdown 標題，並確保前後有空行
    text = re.sub(r'^(【.+?】)\s*$', r'\n## \1\n', text, flags=re.MULTILINE)
    return markdown.markdown(text, extensions=["tables","fenced_code"])

# ════════ Phase 1: Prepare Content ════════

def prepare_judgments():
    """Scan converted ebookhub markdown files (from convert_judgments.py + ocr_judgments.py)"""
    JDG_EB_DIR.mkdir(parents=True, exist_ok=True)
    eb_files = []
    # Scan existing converted markdown files (both text-extract and OCR)
    for mf in sorted(JDG_EB_DIR.glob("*.md")):
        sz = mf.stat().st_size
        yr_m = re.search(r'^(\d{4})_', mf.name)
        yr = yr_m.group(1) if yr_m else "unknown"
        eb_files.append({"year": yr, "slug": mf.stem, "name": mf.name, "size_kb": round(sz/1024, 1)})
        log.info(f"\u5224\u6c7a MD: {mf.name} ({sz/1024:.0f}KB)")
    # Check which scan-only PDFs now have OCR output
    converted_years = {ef["year"] for ef in eb_files}
    all_scan = [
        {"year": "2014", "name": "\u4e2d\u56fd\u6cd5\u96622014\u5e74\u5ea6\u6848\u4f8b_\u4fdd\u9669\u7ea0\u7eb7.pdf", "note": "\u6383\u63cf\u5716\u7247\uff0c\u7121\u6cd5\u63d0\u53d6\u6587\u5b57"},
        {"year": "2015", "name": "\u4e2d\u56fd\u6cd5\u96622015\u5e74\u5ea6\u6848\u4f8b\u4fdd\u9669\u7ea0\u7eb7\uff08291\u9801\uff09.pdf", "note": "\u6383\u63cf\u5716\u7247\uff0c\u7121\u6cd5\u63d0\u53d6\u6587\u5b57"},
        {"year": "2017", "name": "\u4e2d\u56fd\u6cd5\u96622017\u5e74\u5ea6\u6848\u4f8b \u4fdd\u9669.pdf", "note": "\u6383\u63cf\u5716\u7247\uff0c\u7121\u6cd5\u63d0\u53d6\u6587\u5b57"},
        {"year": "2021", "name": "\u4e2d\u56fd\u6cd5\u96622021\u5e74\u5ea6\u6848\u4f8b\uff1a\u4fdd\u9669\u7ea0\u7eb7.pdf", "note": "\u6383\u63cf\u5716\u7247\uff0c\u7121\u6cd5\u63d0\u53d6\u6587\u5b57"},
        {"year": "2024", "name": "15.\u4fdd\u9669\u7ea0\u7eb7.pdf", "note": "\u6383\u63cf\u5716\u7247\uff0c\u7121\u6cd5\u63d0\u53d6\u6587\u5b57"},
    ]
    # Only keep PDFs that don't yet have an OCR markdown output
    scan_only = []
    for s in all_scan:
        # Check if any eb_file starts with this year and relates to this PDF
        has_ocr = any(ef["name"].startswith(s["year"] + "_") and ef["size_kb"] > 5
                      for ef in eb_files
                      if ef["year"] == s["year"] and "ocr" not in ef["name"].lower()
                      # Also check by matching the PDF stem
                      ) or any(ef["name"].startswith(s["year"] + "_") for ef in eb_files if ef["year"] == s["year"])
        # More precise: check if the OCR output file exists
        pdf_stem = s["name"].replace(".pdf", "")
        ocr_out = JDG_EB_DIR / f"{s['year']}_{pdf_stem}.md"
        if not ocr_out.exists():
            # Also check by glob for any file starting with year that wasn't there before
            year_files = [ef for ef in eb_files if ef["year"] == s["year"]]
            if not year_files:
                scan_only.append(s)
            # else: already have a converted file for this year, skip
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

def build_main_page(wc_n, wc_img, jdg_n, prm_n, tip_n, comm_n):
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
  <div class="cc" onclick="location.href='community-ai.html'">
    <div class="cc-icon">\U0001f4ac</div><h2>AI \u5fc3\u5f97\u793e\u7fa4\u5206\u4eab</h2>
    <p>\u4e09\u5144\u5f1f\u7fa4 GitHub / AI \u8cc7\u8a0a\u5f59\u6574</p>
    <div class="num">{comm_n} \u500b GitHub Repo</div>
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
    CASE_IDX = JDG_DIR / "cases" / "_index.json"
    CASE_DIR = JDG_DIR / "cases"
    WENSHU_URLS_FILE = JDG_DIR / "_wenshu_urls.json"
    WENSHU_SEARCH = "https://wenshu.court.gov.cn/website/wenshu/181217BMTKHNT2W0/index.html?s21="

    # A. 讀取裁判文書網 URL 數據
    wenshu_urls = {}
    if WENSHU_URLS_FILE.exists():
        with open(WENSHU_URLS_FILE, "r", encoding="utf-8") as f:
            wu_data = json.load(f)
        wenshu_urls = wu_data.get("urls", {})
        log.info(f"裁判文書網 URL: 已載入 {len(wenshu_urls)} 筆")

    # B. 讀取 NotebookLM 生成的 artifacts
    NLM_DIR = JDG_DIR / "_nlm_output"
    NLM_PROGRESS = NLM_DIR / "_progress.json"
    nlm_completed = {}
    if NLM_PROGRESS.exists():
        with open(NLM_PROGRESS, "r", encoding="utf-8") as f:
            nlm_data = json.load(f)
        nlm_completed = nlm_data.get("completed", {})
        log.info(f"NotebookLM artifacts: 已載入 {len(nlm_completed)} 筆")

    # C. 讀取 AI 分析結果（摘要/重點/法學見解）
    AI_DIR = JDG_DIR / "_ai_analysis"
    ai_analyses = {}
    if AI_DIR.exists():
        for aj in AI_DIR.rglob("*.json"):
            if aj.name == "_progress.json":
                continue
            # Key: relative path without .json, e.g. "cases/2018/01_xxx" or "featured/001_xxx"
            rel = aj.relative_to(AI_DIR).with_suffix("").as_posix()
            try:
                with open(aj, "r", encoding="utf-8") as f:
                    ai_analyses[rel] = json.load(f)
            except Exception:
                pass
        log.info(f"AI 分析: 已載入 {len(ai_analyses)} 筆")

    # D. 讀取標籤數據
    TAGS_FILE = JDG_DIR / "_tags.json"
    all_tags = {}
    if TAGS_FILE.exists():
        with open(TAGS_FILE, "r", encoding="utf-8") as f:
            all_tags = json.load(f)
        tag_count = len([k for k in all_tags if k != "_meta"])
        log.info(f"標籤: 已載入 {tag_count} 筆")

    def get_tag_data(key):
        """Get tag data for a case key."""
        return all_tags.get(key, {})

    def build_card_tags_html(tag_data):
        """Build small tag badges for card display."""
        parts = []
        for it in tag_data.get("insurance_type", [])[:2]:
            parts.append(f'<span class="ct-ins">{esc(it)}</span>')
        for dt in tag_data.get("dispute_type", [])[:2]:
            parts.append(f'<span class="ct-disp">{esc(dt)}</span>')
        v = tag_data.get("verdict", "")
        if v:
            parts.append(f'<span class="ct-verdict">{esc(v)}</span>')
        lv = tag_data.get("court_level", "")
        if lv and lv != "未知":
            parts.append(f'<span class="ct-level">{esc(lv)}</span>')
        return f'<div class="card-tags">{"".join(parts)}</div>' if parts else ""

    def build_tag_filter_data(key, tag_data):
        """Build data attributes for tag filtering."""
        ins = ",".join(tag_data.get("insurance_type", []))
        disp = ",".join(tag_data.get("dispute_type", []))
        v = tag_data.get("verdict", "")
        lv = tag_data.get("court_level", "")
        nat = tag_data.get("case_nature", "")
        return f'data-ins="{esc(ins)}" data-disp="{esc(disp)}" data-verdict="{esc(v)}" data-level="{esc(lv)}" data-nature="{esc(nat)}"'

    def build_analysis_section(ai_key):
        """Build HTML for AI-generated summary/key_points/legal_insights."""
        if ai_key not in ai_analyses:
            return ""
        a = ai_analyses[ai_key]
        parts = []
        # 摘要
        if a.get("summary"):
            parts.append(f'<div id="summary" class="analysis-block"><h2 class="sec-title">摘要</h2>'
                         f'<p style="font-size:15px;line-height:1.8">{esc(a["summary"])}</p></div>')
        # 重點
        kps = a.get("key_points", [])
        if kps:
            li = "".join(f"<li>{esc(k)}</li>" for k in kps)
            parts.append(f'<div id="keypoints" class="analysis-block"><h2 class="sec-title">爭議焦點與裁判要旨</h2>'
                         f'<ul style="padding-left:20px;line-height:2">{li}</ul></div>')
        # 法學見解
        if a.get("legal_insights"):
            paras = a["legal_insights"].replace("\n\n", "\n").split("\n")
            body = "".join(f"<p>{esc(p)}</p>" for p in paras if p.strip())
            parts.append(f'<div id="insights" class="analysis-block"><h2 class="sec-title">法學見解</h2>'
                         f'<div style="font-size:15px;line-height:1.8">{body}</div></div>')
        if not parts:
            return ""
        return "\n".join(parts)

    def build_nlm_section(nlm_key, detail_page_dir):
        """Build HTML for NotebookLM artifacts and copy files to site."""
        if nlm_key not in nlm_completed:
            return ""
        info = nlm_completed[nlm_key]
        nlm_src = NLM_DIR / nlm_key
        if not nlm_src.exists():
            return ""

        parts = []
        # Infographic
        ig_src = nlm_src / "infographic.png"
        if ig_src.exists() and info.get("infographic"):
            ig_dest = detail_page_dir / "infographic.png"
            ig_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ig_src, ig_dest)
            parts.append('<div style="margin:20px 0">'
                         '<img src="infographic.png" alt="NotebookLM Infographic" '
                         'style="max-width:100%;border:1px solid #eee;border-radius:8px"></div>')

        # Slides: convert to inline images (JPG) + keep PDF download
        slides_img_dir = nlm_src / "slides_img"
        sl_src = nlm_src / "slides.pdf"
        if slides_img_dir.exists() and info.get("slides"):
            # Copy slide images to site
            site_slides_dir = detail_page_dir / "slides"
            site_slides_dir.mkdir(parents=True, exist_ok=True)
            slide_imgs = sorted(slides_img_dir.glob("slide_*.jpg"))
            img_html = ""
            for img in slide_imgs:
                dest = site_slides_dir / img.name
                shutil.copy2(img, dest)
                img_html += f'<img src="slides/{img.name}" alt="{img.stem}" style="max-width:100%;border:1px solid #eee;border-radius:4px;margin-bottom:8px">\n'
            if img_html:
                parts.append(f'<div style="margin:15px 0">{img_html}</div>')
            # Also keep PDF download
            if sl_src.exists():
                sl_dest = detail_page_dir / "slides.pdf"
                shutil.copy2(sl_src, sl_dest)
                parts.append('<a class="dl-btn sec" href="slides.pdf" target="_blank" style="margin-bottom:10px">下載 PDF</a> ')
        elif sl_src.exists() and info.get("slides"):
            # Fallback: no images, just PDF
            sl_dest = detail_page_dir / "slides.pdf"
            sl_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sl_src, sl_dest)
            parts.append('<a class="dl-btn" href="slides.pdf" target="_blank">下載 PPT 簡報</a> ')

        # Mind map
        mm_src = nlm_src / "mindmap.json"
        if mm_src.exists() and info.get("mind_map"):
            mm_dest = detail_page_dir / "mindmap.json"
            mm_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(mm_src, mm_dest)
            parts.append('<a class="dl-btn sec" href="mindmap.json" download>Mind Map JSON</a>')

        if not parts:
            return ""
        return '<div id="nlm" style="margin-top:25px;padding-top:20px;border-top:1px solid #eee">' + '\n'.join(parts) + '</div>'

    def get_wenshu_url(case_no_raw):
        """根據案號獲取裁判文書網 URL（真實 URL 或搜索連結）"""
        cn = extract_case_number(case_no_raw)
        if cn in wenshu_urls:
            return wenshu_urls[cn].get("wenshu_url", WENSHU_SEARCH + quote(cn))
        return WENSHU_SEARCH + quote(cn)

    def get_doc_type(title):
        """從標題提取文書類型"""
        if "裁定書" in title or "裁定书" in title:
            return "裁定書"
        if "判決書" in title or "判决书" in title:
            return "判決書"
        return "文書"

    # 1. Original curated judgments (裁判文書網精選)
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
    for j in md_jdgs:
        ch = md2html(j["text"])
        w_url = get_wenshu_url(j["case_no"])
        detail_dir = SITE / "judgment" / j["slug"]
        nlm_key = f'featured/{j["slug"]}'
        nlm_html = build_nlm_section(nlm_key, detail_dir)
        ai_key = f'featured/{j["slug"]}'
        analysis_html = build_analysis_section(ai_key)
        has_nlm = nlm_key in nlm_completed
        nav_items = '<a href="#summary">摘要</a><a href="#keypoints">爭議焦點</a><a href="#insights">法學見解</a>'
        if has_nlm:
            nav_items += '<a href="#nlm">NLM 分析</a>'
        nav_items += '<a href="#fulltext">分析全文</a>'
        bookmark_nav = f'<div class="bm-nav">{nav_items}</div>'
        ab = f'''<article>
{bookmark_nav}
<div style="margin-bottom:15px">
  <a class="dl-btn" href="{esc(w_url)}" target="_blank">裁判文書網原文</a>
  <a class="dl-btn sec" href="../../../judgments/{quote(j["slug"])}.md" download>下載 MD</a>
</div>
{analysis_html}
{nlm_html}
<div id="fulltext" class="content" style="margin-top:20px;border-top:1px solid #eee;padding-top:15px">{ch}</div></article>'''
        wf(detail_dir / "index.html", page(j["title"], ab, back="../../judgments.html"))

    # 2. Individual cases from split (一案一檔)
    split_cases = []
    cases_by_year = {}
    if CASE_IDX.exists():
        with open(CASE_IDX, "r", encoding="utf-8") as f:
            cidx = json.load(f)
        split_cases = cidx.get("cases", [])
        for c in split_cases:
            cases_by_year.setdefault(c["year"], []).append(c)
        # Build individual case pages
        for c in split_cases:
            case_path = CASE_DIR / c["year"] / c["filename"]
            if not case_path.exists():
                continue
            with open(case_path, "r", encoding="utf-8") as f:
                text = f.read()
            ch = md2html(text)
            case_slug = f'{c["year"]}_{c["num"]:0>2}'
            detail_dir = SITE / "judgment" / case_slug
            # NLM key for annual cases
            case_stem = Path(c["filename"]).stem
            nlm_key = f'cases/{c["year"]}/{case_stem}'
            nlm_html = build_nlm_section(nlm_key, detail_dir)
            ai_key = f'cases/{c["year"]}/{case_stem}'
            analysis_html = build_analysis_section(ai_key)
            w_url = get_wenshu_url(c.get("case_no", ""))
            has_nlm = nlm_key in nlm_completed
            # Bookmark nav
            nav_items = '<a href="#summary">摘要</a><a href="#keypoints">爭議焦點</a><a href="#insights">法學見解</a>'
            if has_nlm:
                nav_items += '<a href="#nlm">NLM 分析</a>'
            nav_items += '<a href="#fulltext">案例評析</a>'
            bookmark_nav = f'<div class="bm-nav">{nav_items}</div>'
            ab = f'''<article>
{bookmark_nav}
<div style="margin-bottom:15px">
  <a class="dl-btn" href="{esc(w_url)}" target="_blank">裁判文書網原文</a>
  <a class="dl-btn sec" href="../../../judgments/cases/{c["year"]}/{quote(c["filename"])}" download>下載 MD</a>
</div>
{analysis_html}
{nlm_html}
<details id="fulltext" style="margin-top:25px;border-top:1px solid #eee;padding-top:15px">
<summary style="cursor:pointer;font-size:16px;font-weight:600;color:#1a73e8;padding:10px 0">
展開案例評析</summary>
<div class="content" style="margin-top:15px">{ch}</div>
</details></article>'''
            wf(detail_dir / "index.html",
               page(c["title"] or f"案例{c['num']}", ab, back="../../judgments.html"))

    # 3. Build listing page
    # 3a. 精選判決卡片
    md_cards = ""
    for j in md_jdgs:
        doc_type = get_doc_type(j["title"])
        w_url = get_wenshu_url(j["case_no"])
        core_cn = extract_case_number(j["case_no"])
        # Title: 案號 — AI摘要第一句（如有），否則原標題
        ai_key_feat = f'featured/{j["slug"]}'
        ai_summary_feat = ""
        if ai_key_feat in ai_analyses:
            kps = ai_analyses[ai_key_feat].get("key_points", [])
            # Use first key point as concise one-liner (usually ~20 chars)
            if kps:
                ai_summary_feat = kps[0]
        one_liner = ai_summary_feat or j["title"]
        feat_title = f"{core_cn} — {one_liner}" if core_cn else one_liner
        nlm_key = f'featured/{j["slug"]}'
        has_nlm = nlm_key in nlm_completed
        nlm_badge = ' <span style="font-size:11px;background:#e8f5e9;color:#2e7d32;padding:1px 6px;border-radius:3px">NLM</span>' if has_nlm else ''
        md_cards += f'''<div class="card"><h3><a href="judgment/{j["slug"]}/index.html">{esc(feat_title)}</a></h3>
<div class="meta"><span class="tag tag-{doc_type}">{doc_type}</span>{nlm_badge}</div>
<div class="dl">
  <a href="{esc(w_url)}" target="_blank" class="dl-btn" style="font-size:12px;padding:3px 10px">裁判文書網原文</a>
  <a href="../judgments/{quote(j["slug"])}.md" download style="font-size:12px;color:#666">MD</a>
</div></div>\n'''

    # 3b. 年度案例（一案一檔卡片）
    case_cards = ""
    year_btns = '<button class="tg-btn active" onclick="fy(this,\'\')">全部</button>\n'
    for yr in sorted(cases_by_year):
        cnt = len(cases_by_year[yr])
        year_btns += f'<button class="tg-btn" onclick="fy(this,\'{yr}\')">{yr} ({cnt})</button>\n'
        for c in cases_by_year[yr]:
            case_slug = f'{c["year"]}_{c["num"]:0>2}'
            case_stem = Path(c["filename"]).stem
            raw_title = c["title"] or f"案例{c['num']}"
            case_no_raw = c.get("case_no", "")
            core_cn = extract_case_number(case_no_raw)
            # New title format: 案號 — 一句話總結
            display_title = f"{core_cn} — {raw_title}" if core_cn and core_cn != case_no_raw else raw_title
            parties_s = esc(c.get("parties", ""))
            w_url = get_wenshu_url(case_no_raw)
            ai_key = f'cases/{c["year"]}/{case_stem}'
            has_ai = ai_key in ai_analyses
            # Build comprehensive search text
            ai_summary = ai_analyses[ai_key].get("summary", "") if has_ai else ""
            ai_kps = " ".join(ai_analyses[ai_key].get("key_points", [])) if has_ai else ""
            search_text = f'{raw_title} {c.get("parties","")} {c.get("case_type","")} {case_no_raw} {ai_summary} {ai_kps}'.lower()
            # Show AI summary preview on card
            ai_preview = ""
            if ai_summary:
                s = ai_summary
                ai_preview = f'<div style="font-size:13px;color:#555;margin-top:5px;line-height:1.5">{esc(s[:150])}{"..." if len(s)>150 else ""}</div>'
            # Tags
            td = get_tag_data(ai_key)
            card_tags = build_card_tags_html(td)
            tag_attrs = build_tag_filter_data(ai_key, td)
            case_cards += f'''<div class="card" data-year="{c["year"]}" data-search="{esc(search_text)}" {tag_attrs}>
<h3><a href="judgment/{case_slug}/index.html">{esc(display_title)}</a></h3>
<div class="meta">{parties_s}</div>{card_tags}{ai_preview}
<div class="dl">
  <a href="{esc(w_url)}" target="_blank" style="font-size:12px">裁判文書網</a>
</div></div>\n'''

    # Collect tag counts for filter buttons
    ins_counts = {}
    disp_counts = {}
    verdict_counts = {}
    level_counts = {}
    nature_counts = {}
    for c in split_cases:
        case_stem = Path(c["filename"]).stem
        ai_key = f'cases/{c["year"]}/{case_stem}'
        td = get_tag_data(ai_key)
        for it in td.get("insurance_type", []):
            ins_counts[it] = ins_counts.get(it, 0) + 1
        for dt in td.get("dispute_type", []):
            disp_counts[dt] = disp_counts.get(dt, 0) + 1
        v = td.get("verdict", "")
        if v: verdict_counts[v] = verdict_counts.get(v, 0) + 1
        lv = td.get("court_level", "")
        if lv and lv != "未知": level_counts[lv] = level_counts.get(lv, 0) + 1
        nat = td.get("case_nature", "")
        if nat: nature_counts[nat] = nature_counts.get(nat, 0) + 1

    def _ftag_btns(counts, group_id, top_n=15):
        btns = ""
        for label, cnt in sorted(counts.items(), key=lambda x: -x[1])[:top_n]:
            btns += f'<span class="ftag" onclick="tf(this,\'{group_id}\')" data-val="{esc(label)}">{esc(label)} <span class="cnt">{cnt}</span></span>\n'
        return btns

    nature_btns = _ftag_btns(nature_counts, "nature")
    ins_btns = _ftag_btns(ins_counts, "ins")
    disp_btns = _ftag_btns(disp_counts, "disp")
    verdict_btns = _ftag_btns(verdict_counts, "verdict")
    level_btns = _ftag_btns(level_counts, "level")

    tag_filters_html = f'''<div id="tag-filters" style="margin-bottom:20px;background:#fff;border-radius:8px;padding:15px;box-shadow:0 1px 3px rgba(0,0,0,.1)">
<details open class="filter-group"><summary>案件性質</summary><div>{nature_btns}</div></details>
<details class="filter-group"><summary>險種</summary><div>{ins_btns}</div></details>
<details class="filter-group"><summary>爭議類型</summary><div>{disp_btns}</div></details>
<details class="filter-group"><summary>裁判結果</summary><div>{verdict_btns}</div></details>
<details class="filter-group"><summary>審級</summary><div>{level_btns}</div></details>
<div style="margin-top:8px"><button onclick="clearAllFilters()" style="font-size:12px;padding:4px 12px;border:1px solid #ddd;border-radius:12px;background:#fff;cursor:pointer">清除所有篩選</button></div>
</div>'''

    case_js = """let cy='',dt=null,af={nature:'',ins:'',disp:'',verdict:'',level:''};
function fy(b,y){cy=y;document.querySelectorAll('.tg-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');fj();}
function tf(el,g){
  const v=el.dataset.val;
  if(af[g]===v){af[g]='';el.classList.remove('active');}
  else{
    el.parentElement.querySelectorAll('.ftag').forEach(x=>x.classList.remove('active'));
    af[g]=v;el.classList.add('active');
  }
  fj();
}
function clearAllFilters(){
  af={nature:'',ins:'',disp:'',verdict:'',level:''};
  document.querySelectorAll('.ftag').forEach(x=>x.classList.remove('active'));
  fj();
}
function fj(){
  const q=document.getElementById('jq').value.toLowerCase().trim();
  const words=q?q.split(/\\s+/):[];
  let shown=0,total=0;
  document.querySelectorAll('#jcards .card').forEach(c=>{
    total++;
    const s=c.dataset.search||'';
    const ym=!cy||c.dataset.year===cy;
    const qm=!words.length||words.every(w=>s.includes(w));
    const fm=(!af.nature||c.dataset.nature===af.nature)
      &&(!af.ins||(c.dataset.ins||'').split(',').includes(af.ins))
      &&(!af.disp||(c.dataset.disp||'').split(',').includes(af.disp))
      &&(!af.verdict||c.dataset.verdict===af.verdict)
      &&(!af.level||c.dataset.level===af.level);
    const vis=ym&&qm&&fm;
    c.classList.toggle('hidden',!vis);
    if(vis)shown++;
  });
  const el=document.getElementById('jcount');
  const hasFilter=q||cy||Object.values(af).some(v=>v);
  if(el)el.textContent=hasFilter?shown+'/'+total+' 筆':total+' 筆';
}
function djq(){clearTimeout(dt);dt=setTimeout(fj,200);}
document.addEventListener('DOMContentLoaded',fj);"""

    total_cases = len(split_cases)
    total = len(md_jdgs) + total_cases
    tag_stats = f' | {len(ins_counts)} 種險種 · {len(disp_counts)} 種爭議類型' if ins_counts else ''
    body = f"""<header><h1>保險判決庫</h1>
<p>中國法院保險糾紛判決案例集（2014-2025）</p>
<div class="stats"><span class="stat">{len(md_jdgs)} 份精選判決</span><span class="stat">{total_cases} 個年度案例（一案一檔）</span><span class="stat">來源：中國裁判文書網 + 中國法院年度案例叢書</span></div></header>
<div style="margin-bottom:20px;padding:15px;background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.1)">
<h3 style="font-size:15px;margin-bottom:8px">全站搜尋（Pagefind）</h3>
<div id="pf-search"></div>
<link href="pagefind/pagefind-ui.css" rel="stylesheet">
<script src="pagefind/pagefind-ui.js"></script>
<script>window.addEventListener('DOMContentLoaded',function(){{if(typeof PagefindUI!=='undefined'){{new PagefindUI({{element:'#pf-search',showSubResults:true,showImages:false}});}}else{{document.getElementById('pf-search').innerHTML='<p style="color:#999;font-size:13px">搜尋索引載入中...</p>';}}}});</script>
</div>
<h2 class="sec-title">裁判文書網 · 精選判決分析</h2>
<p style="margin-bottom:15px;color:#666;font-size:14px">來源：中國裁判文書網，人身保險合同糾紛案件</p>
{md_cards}
<h2 class="sec-title">中國法院年度案例 · 保險糾紛（一案一檔）</h2>
<p style="margin-bottom:15px;color:#666;font-size:14px">來源：《中國法院年度案例》叢書（2018-2025），每個案例獨立成檔，含案件基本信息、案情、裁判要旨、法官后語</p>
<input class="search" type="text" id="jq" placeholder="搜尋案號、標題、當事人、案由、關鍵字（多個詞用空格分隔）..." oninput="djq()">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><span id="jcount" style="font-size:13px;color:#666"></span></div>
{tag_filters_html}
<div class="tg-btns">{year_btns}</div>
<div id="jcards">{case_cards}</div>"""
    wf(SITE / "judgments.html", page("保險判決庫", body, back="index.html", extra_js=case_js))
    log.info(f"建置: 判決庫 ({len(md_jdgs)} 精選 + {total_cases} 年度案例)")
    return total

def build_prompts(prompt_files):
    # ─── Part A: 662 YAML Prompt 卡片 ───
    yaml_count = 0
    yaml_cards = ""
    cat_set = set()
    try:
        import yaml as _yaml
    except ImportError:
        _yaml = None
    if PROMPT_IDX.exists():
        with open(PROMPT_IDX, "r", encoding="utf-8") as f:
            idx = json.load(f)
        prompts = idx.get("prompts", [])
        yaml_count = len(prompts)
        for cat_id, info in idx.get("categories", {}).items():
            cat_set.add((cat_id, info["name"]))
        # Build detail pages + cards
        for p in prompts:
            slug = p["slug"]
            name = p["name"]
            cat_id = p["category_id"]
            cat_name = p["category"]
            author = p["author"]
            source = p["source"]
            preview = p["preview"]
            plen = p["prompt_length"]
            # Read full prompt from YAML
            yaml_path = PROMPT_YAML_DIR / p["filename"]
            full_prompt = ""
            if yaml_path.exists() and _yaml:
                try:
                    with open(yaml_path, "r", encoding="utf-8") as f:
                        data = _yaml.safe_load(f)
                    if data:
                        if "metadata" in data:
                            full_prompt = data.get("system_prompt", "")
                        elif "versions" in data and data["versions"]:
                            full_prompt = data["versions"][-1].get("template", "")
                        elif "system_prompt" in data:
                            full_prompt = data["system_prompt"]
                except Exception:
                    full_prompt = preview
            if not full_prompt:
                full_prompt = preview
            # Detail page
            prompt_esc = esc(full_prompt)
            prompt_html = f'<pre style="white-space:pre-wrap;word-break:break-word;background:#f8f8f8;padding:20px;border-radius:8px;font-size:14px;line-height:1.7;max-height:70vh;overflow-y:auto">{prompt_esc}</pre>'
            copy_js = "function cp(){const t=document.getElementById('pt').textContent;navigator.clipboard.writeText(t).then(()=>{const b=document.getElementById('cb');b.textContent='已複製!';setTimeout(()=>b.textContent='複製 Prompt',1500);});}"
            tags_detail = " ".join(f'<span style="display:inline-block;padding:2px 8px;background:#e8f0fe;color:#1a73e8;border-radius:10px;font-size:12px;margin-right:4px">{esc(t)}</span>' for t in p.get("tags", []))
            ab = f'''<article><h1>{esc(name)}</h1>
<div class="meta"><strong>分類</strong>：{esc(cat_name)} | <strong>作者</strong>：{esc(author) if author else "社群貢獻"} | <strong>長度</strong>：{plen} 字元</div>
{f'<div class="meta"><strong>來源</strong>：<a href="{esc(source)}" target="_blank">{esc(source)[:80]}</a></div>' if source else '<div class="meta"><strong>來源</strong>：awesome-chatgpt-prompts 社群收集</div>'}
{f'<div style="margin:8px 0">{tags_detail}</div>' if tags_detail else ''}
<div style="margin:20px 0"><button id="cb" onclick="cp()" style="padding:8px 20px;background:#1a73e8;color:#fff;border:none;border-radius:5px;cursor:pointer;font-size:14px">複製 Prompt</button>
<a class="dl-btn sec" href="../../prompts/roles/{quote(p["filename"])}" download style="margin-left:8px">下載 YAML</a></div>
<div id="pt">{prompt_esc}</div>
{prompt_html}
</article>'''
            wf(SITE / "prompt" / slug / "index.html", page(name, ab, back="../../prompts.html", extra_js=copy_js))
            # Card for listing page — search across title + preview + tags + author
            tags = p.get("tags", [])
            tags_str = ",".join(tags)
            tags_html = " ".join(f'<span style="display:inline-block;padding:1px 6px;background:#e8f0fe;color:#1a73e8;border-radius:8px;font-size:11px;margin-right:3px">{esc(t)}</span>' for t in tags[:5])
            search_text = f"{name} {preview[:150]} {tags_str} {author} {cat_name}".lower()
            src_link = f' · <a href="{esc(source)}" target="_blank" style="font-size:12px">來源</a>' if source else ""
            yaml_cards += f'''<div class="card" data-cat="{cat_id}" data-search="{esc(search_text)}">
<h3><a href="prompt/{slug}/index.html">{esc(name)}</a></h3>
<div class="meta">{esc(cat_name)} · {plen} 字元{(" · " + esc(author)) if author else ""}{src_link}</div>
<div style="margin:4px 0">{tags_html}</div>
<div class="meta" style="color:#999">{esc(preview[:120])}...</div></div>\n'''
    # ─── Part B: 學習資源 (電子書 + 社群資料) ───
    RESOURCE_INFO = {
        "knowledge_base.md": ("知識精萃庫", "13 篇教學文章 + 42 支影片連結", "T客邦、電腦玩物等", True),
        "url_report.md": ("AI 資源連結彙整", "227 YouTube + 148 網站連結", "Facebook AI 社團", True),
        "compact_digest.md": ("社群貼文摘要（精簡版）", "475 條 Facebook AI 社團貼文摘要", "75 個 FB 社團", True),
        "rich_digest.md": ("社群貼文摘要（完整版）", "475 條貼文完整版", "75 個 FB 社團", True),
        "related_data.md": ("Facebook AI 數據集", "583 筆 Facebook AI 相關資料", "個人 FB 資料匯出", False),
        "group_list.md": ("Facebook 社團指南", "75 個 AI/科技相關社團", "用戶訂閱社團", True),
        "ebooks/prompt_bible.md": ("The AI Prompt Bible", "完整電子書 — AI 提示詞聖經", "Anton Volney 著", True),
        "ebooks/prompt_handbook.md": ("AI Prompt Engineering Handbook", "提示工程手冊（英文版）", "Roman Lahinouski 著", True),
        "ebooks/prompt_guide.md": ("The Ultimate AI Prompt Engineering Guide", "終極提示工程指南", "Ink 著", True),
        "ebooks/prompt_handbook_zh.md": ("AI 提示工程手冊（中文版）", "中文翻譯版", "Roman Lahinouski 著, 中譯", True),
    }
    resource_cards = ""
    resource_rendered = 0
    for rslug, (rtitle, rdesc, rsource, render) in RESOURCE_INFO.items():
        src_file = PROMPT_DIR / rslug
        if not src_file.exists():
            continue
        sz = src_file.stat().st_size
        sz_s = f"{sz/1024:.0f}KB" if sz < 1048576 else f"{sz/1048576:.1f}MB"
        ps = rslug.replace("/", "_").replace(".md", "")
        if render:
            with open(src_file, "r", encoding="utf-8") as f:
                text = f.read()
            ch = md2html(text)
            ab = f'<article><h1>{esc(rtitle)}</h1><div class="meta"><strong>來源</strong>：{esc(rsource)} | <strong>大小</strong>：{sz_s}</div><div class="content">{ch}</div><div style="margin-top:25px;padding-top:20px;border-top:1px solid #eee"><a class="dl-btn" href="../../../prompts/{quote(rslug)}" download>下載原始檔</a></div></article>'
            wf(SITE / "prompt" / ps / "index.html", page(rtitle, ab, back="../../prompts.html"))
            resource_rendered += 1
            resource_cards += f'<div class="card"><h3><a href="prompt/{ps}/index.html">{esc(rtitle)}</a></h3><div class="meta">{esc(rdesc)} · {sz_s}</div><div class="meta">來源：{esc(rsource)}</div><div class="dl"><a href="prompt/{ps}/index.html">閱讀</a> <a href="../prompts/{quote(rslug)}" download>下載</a></div></div>\n'
        else:
            resource_cards += f'<div class="card"><h3>{esc(rtitle)}</h3><div class="meta">{esc(rdesc)} · {sz_s}</div><div class="dl"><a href="../prompts/{quote(rslug)}" download>下載（{sz_s}）</a></div></div>\n'
    # ─── Build listing page ───
    cat_btns = '<button class="tg-btn active" onclick="fp(this,\'\')">全部</button>\n'
    for cid, cname in sorted(cat_set, key=lambda x: x[1]):
        cat_btns += f'<button class="tg-btn" onclick="fp(this,\'{cid}\')">{cname}</button>\n'
    filter_js = """let cc='';function fp(b,c){cc=c;document.querySelectorAll('.tg-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');ff();}
function ff(){const q=document.getElementById('pq').value.toLowerCase();const words=q.split(/\\s+/).filter(w=>w);document.querySelectorAll('#pcards .card').forEach(c=>{const s=c.dataset.search||'';const catOk=!cc||c.dataset.cat===cc;const searchOk=!words.length||words.every(w=>s.includes(w));c.classList.toggle('hidden',!(catOk&&searchOk));});}"""
    body = f"""<header><h1>\U0001f916 Prompt \u5eab</h1>
<p>662 \u500b AI \u63d0\u793a\u8a5e\u89d2\u8272 + \u5b78\u7fd2\u8cc7\u6e90\u8207\u96fb\u5b50\u66f8</p>
<div class="stats"><span class="stat">{yaml_count} \u500b Prompt \u89d2\u8272</span><span class="stat">{len(cat_set)} \u500b\u5206\u985e</span><span class="stat">\u542b 4 \u672c\u96fb\u5b50\u66f8</span></div></header>
<h2 class="sec-title">Prompt \u89d2\u8272\u5eab</h2>
<input class="search" type="text" id="pq" placeholder="搜尋 Prompt（名稱、內容、標籤、作者）..." oninput="ff()">
<div class="tg-btns">{cat_btns}</div>
<div id="pcards">{yaml_cards}</div>
<h2 class="sec-title">\u5b78\u7fd2\u8cc7\u6e90</h2>
{resource_cards}"""
    wf(SITE / "prompts.html", page("Prompt \u5eab", body, back="index.html", extra_js=filter_js))
    log.info(f"\u5efa\u7f6e: Prompt \u5eab ({yaml_count} YAML + {resource_rendered} \u8cc7\u6e90\u9801)")
    return yaml_count + len(RESOURCE_INFO)

def build_tips():
    if not TIPS_STATE.exists():
        log.warning("AI Tips: 狀態檔不存在，請先執行 fetch_ai_tips.py")
        wf(SITE / "ai-tips.html", page("AI 使用技巧",
            '<header><h1>\U0001f4a1 AI 使用技巧</h1><p>請先執行 fetch_ai_tips.py</p></header>',
            back="index.html"))
        return 0
    with open(TIPS_STATE, "r", encoding="utf-8") as f:
        state = json.load(f)
    articles = [a for a in state["articles"] if a["status"] == "fetched"]
    articles.sort(key=lambda x: x.get("pub_time", ""), reverse=True)
    cards = []
    total_imgs = 0
    for art in articles:
        slug = art.get("slug", "")
        if not slug:
            continue
        md_file = TIPS_DIR / slug / "index.md"
        if not md_file.exists():
            continue
        with open(md_file, "r", encoding="utf-8") as f:
            md_text = f.read()
        ch = md2html(md_text)
        # Fix image paths
        ch = ch.replace('src="assets/', f'src="../../ai_tips/{slug}/assets/')
        # Remove the H1 + metadata blockquote + hr from converted content
        ch = re.sub(r'<h1>.*?</h1>\s*<blockquote>.*?</blockquote>\s*<hr\s*/?>', '', ch, count=1, flags=re.DOTALL)
        title = art.get("real_title", art.get("title", "untitled"))
        author = art.get("author", "電腦王阿達")
        pub_time = art.get("pub_time", "")
        url = art.get("url", "")
        img_count = art.get("img_count", 0)
        total_imgs += img_count
        # Detail page
        ab = f'''<article><h1>{esc(title)}</h1>
<div class="meta"><strong>作者</strong>：{esc(author)} | <strong>發布時間</strong>：{pub_time}<br>
<a href="{url}" target="_blank">查看原文（電腦王阿達）</a></div>
<div class="content">{ch}</div>
<div style="margin-top:25px;padding-top:20px;border-top:1px solid #eee">
<a class="dl-btn" href="../../ai_tips/{quote(slug)}/index.md" download>下載 Markdown</a>
<a class="dl-btn sec" href="{url}" target="_blank">原文連結</a></div></article>'''
        wf(SITE / "tip" / slug / "index.html", page(title, ab, back="../../ai-tips.html"))
        cards.append(f'<div class="card"><h3><a href="tip/{slug}/index.html">{esc(title)}</a></h3>'
            f'<div class="meta">{pub_time} | {esc(author)} | {img_count} 張圖片</div>'
            f'<div class="dl"><a href="tip/{slug}/index.html">閱讀</a>'
            f' <a href="{url}" target="_blank">原文</a>'
            f' <a href="../ai_tips/{quote(slug)}/index.md" download>MD</a></div></div>')
    body = f"""<header><h1>\U0001f4a1 AI 使用技巧</h1>
<p>AI 工具教學文章（電腦王阿達 kocpc.com.tw）</p>
<div class="stats"><span class="stat">{len(articles)} 篇文章</span><span class="stat">{total_imgs} 張圖片</span></div></header>
<p style="margin-bottom:15px;color:#666;font-size:14px">來源：電腦王阿達（kocpc.com.tw），涵蓋 NotebookLM、ChatGPT、Gemini 等 AI 工具教學</p>
{"".join(cards)}"""
    wf(SITE / "ai-tips.html", page("AI 使用技巧", body, back="index.html"))
    log.info(f"建置: AI 使用技巧 ({len(articles)} 篇, {total_imgs} 圖)")
    return len(articles)

# ════════ Community AI ════════

# AI 嚴格關鍵字（二次驗證用）
_AI_KW = [
    'claude', 'gemini', 'gpt', 'chatgpt', 'openai', 'deepseek', 'llm',
    'notebooklm', 'prompt', 'agent', 'copilot', 'cursor', 'antigravity',
    'anthropic', 'codex', 'whisper', 'stable diffusion', 'midjourney',
    'comfyui', 'langchain', 'rag', 'embedding', 'fine-tune', 'lora',
    'transformer', 'github.com', 'huggingface', 'arxiv',
    'clawdbot', 'openclaw', 'coding', 'vibe cod', 'ai agent',
    'deepwiki', 'mcp', 'sdk',
    '人工智', '深度學', '機器學', '大模型', '語言模型',
]
_JUNK_URL = ['support.weixin.qq.com', 'wx.qlogo.cn', 'mmbiz.qpic.cn',
             'dldir1.qq.com', 'res.wx.qq.com']

def _extract_community_highlights(msgs):
    """從原始 AI 訊息中提取有價值的文字討論"""
    out = []
    for m in msgs:
        d = m['display']
        if d.startswith('[圖片]') or d.startswith('[語音]') or d.startswith('[影片]'):
            continue
        if '<?xml' in d or '<appmsg' in d or d.lstrip().startswith('<msg>'):
            tm = re.search(r'<title>(.*?)</title>', d)
            d = tm.group(1).strip() if tm and len(tm.group(1).strip()) > 3 else ''
            if not d:
                continue
        d = re.sub(r'^(wxid_\w+|F\d+):\s*', '', d).strip()
        if '<msg>' in d or '<appmsg' in d:
            tm = re.search(r'<title>(.*?)</title>', d)
            d = tm.group(1).strip() if tm and len(tm.group(1).strip()) > 3 else ''
            if not d:
                continue
        if len(d) < 50:
            continue
        text_lower = (d + ' '.join(m.get('urls', []))).lower()
        if not any(kw in text_lower for kw in _AI_KW):
            continue
        # 清理 URLs
        urls = []
        seen = set()
        for u in m.get('urls', []):
            if any(j in u for j in _JUNK_URL):
                continue
            key = re.split(r'[?&]', u)[0]
            if key not in seen:
                seen.add(key)
                urls.append(u)
        out.append({'time': m['time'], 'sender': m['sender'], 'display': d[:500], 'urls': urls[:2]})
    return out


def build_community_ai():
    if not COMM_REPOS.exists():
        log.warning("Community AI: github_repos.json 不存在")
        wf(SITE / "community-ai.html", page("AI 心得社群分享",
            '<header><h1>💬 AI 心得社群分享</h1><p>資料尚未準備</p></header>',
            back="index.html"))
        return 0
    with open(COMM_REPOS, "r", encoding="utf-8") as f:
        repos = json.load(f)
    # 讀取文字討論
    highlights = []
    if COMM_MSGS.exists():
        with open(COMM_MSGS, "r", encoding="utf-8") as f:
            raw_msgs = json.load(f)
        highlights = _extract_community_highlights(raw_msgs)

    # ── GitHub 表格 ──
    cats = {
        'AI Agent / Coding': ['claude', 'agent', 'copilot', 'cursor', 'code',
            'claw', 'skill', 'hook', 'proxy', 'bridge', 'orchestra'],
        'AI 應用 / 工具': ['ai', 'draw', 'sleep', 'yolo', 'markitdown',
            'stitch', 'clipper', 'threat', 'telegram'],
        'AI 研究 / 理論': ['wfgy', 'embedding'],
        '開發資源 / API': ['public-api', 'pageindex', 'assignment', 'quant', 'rss'],
    }
    def _cat(r):
        t = (r['url'] + ' ' + r.get('description', '') + ' ' + r.get('context', '')).lower()
        for c, kws in cats.items():
            if any(k in t for k in kws):
                return c
        return '其他'

    by_cat = {}
    for r in repos:
        if r.get('kind') not in ('repo', 'gist'):
            continue
        by_cat.setdefault(_cat(r), []).append(r)

    repo_html = []
    for cat_name in ['AI Agent / Coding', 'AI 應用 / 工具', 'AI 研究 / 理論', '開發資源 / API', '其他']:
        items = by_cat.get(cat_name, [])
        if not items:
            continue
        items.sort(key=lambda x: x.get('stars', 0), reverse=True)
        repo_html.append(f'<h3 class="sec-title">{esc(cat_name)}</h3>')
        repo_html.append('<table><thead><tr><th>Repo</th><th>說明</th>'
                         '<th>★</th><th>語言</th><th>日期</th></tr></thead><tbody>')
        for r in items:
            desc = esc(r.get('description', '') or r.get('context', '')[:60])[:80]
            stars = r.get('stars', '')
            lang = esc(r.get('language', '') or '')
            name = f"{r['owner']}/{r['name']}" if r['kind'] == 'repo' else f"gist/{r['owner']}"
            repo_html.append(
                f'<tr><td><a href="{esc(r["url"])}" target="_blank">{esc(name)}</a></td>'
                f'<td>{desc}</td><td>{stars}</td><td>{lang}</td><td>{r["date"][:10]}</td></tr>')
        repo_html.append('</tbody></table>')

    # ── 文字討論精華 ──
    disc_html = []
    if highlights:
        disc_html.append(f'<h3 class="sec-title">文字討論精華（{len(highlights)} 則）</h3>')
        for h in highlights[:60]:
            display = esc(h['display'][:300])
            disc_html.append(
                f'<div class="card"><div class="meta">{h["time"]} | {esc(h["sender"])}</div>'
                f'<p style="font-size:14px;line-height:1.7">{display}</p>')
            for u in h['urls'][:2]:
                disc_html.append(f'<div class="dl"><a href="{esc(u)}" target="_blank">{esc(u[:80])}</a></div>')
            disc_html.append('</div>')

    total_repos = sum(len(v) for v in by_cat.values())
    body = f"""<header><h1>💬 AI 心得社群分享</h1>
<p>三兄弟群 WeChat 群組的 GitHub / AI 資訊彙整</p>
<div class="stats"><span class="stat">{total_repos} 個 GitHub Repo</span>
<span class="stat">{len(highlights)} 則討論</span>
<span class="stat">2025-12 ~ 2026-02</span></div></header>
<input class="search" type="text" placeholder="搜尋 repo 或討論內容…" oninput="
var q=this.value.toLowerCase();
document.querySelectorAll('table tbody tr, .card').forEach(function(el){{
  el.style.display=el.textContent.toLowerCase().includes(q)?'':'none'}})">
<h2 style="margin:20px 0 10px">GitHub 資源索引</h2>
{"".join(repo_html)}
<h2 style="margin:30px 0 10px">社群 AI 討論</h2>
{"".join(disc_html)}"""

    extra_css = """
table{border-collapse:collapse;width:100%;margin-bottom:20px;font-size:14px}
th,td{border:1px solid #e0e0e0;padding:8px 12px;text-align:left}
th{background:#f5f5f5;font-weight:600}
tr:hover{background:#f8f9fa}
td a{word-break:break-all}
"""
    wf(SITE / "community-ai.html", page("AI 心得社群分享", body, back="index.html", extra_css=extra_css))
    log.info(f"建置: AI 心得社群分享 ({total_repos} repos, {len(highlights)} 討論)")
    return total_repos


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
    comm_n = build_community_ai()
    build_main_page(wc_n, wc_img, jdg_n, prm_n, tip_n, comm_n)
    # Phase 3: Pagefind search index
    log.info("-- Phase 3: 建置搜尋索引 (Pagefind) --")
    try:
        import asyncio
        from pagefind.index import PagefindIndex

        async def _build_pagefind():
            config = {"root_selector": "article", "verbose": False}
            async with PagefindIndex(config=config) as index:
                await index.add_directory(str(SITE))
                pf_dir = SITE / "pagefind"
                pf_dir.mkdir(parents=True, exist_ok=True)
                await index.write_files(str(pf_dir))
            return True

        asyncio.run(_build_pagefind())
        log.info("Pagefind 搜尋索引建置完成")
    except ImportError:
        log.warning("Pagefind 未安裝，跳過搜尋索引 (pip install 'pagefind[extended]')")
    except Exception as e:
        log.warning(f"Pagefind 索引建置失敗: {e}")

    log.info("=" * 50)
    log.info(f"\u5b8c\u6210: \u5fae\u4fe1{wc_n} | \u5224\u6c7a{jdg_n} | Prompt{prm_n} | AI\u6280\u5de7{tip_n} | \u793e\u7fa4{comm_n}")
    log.info(f"\u65e5\u8a8c: {log_path}")

if __name__ == "__main__":
    main()
