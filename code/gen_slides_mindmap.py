#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gen_slides_mindmap.py — 從 AI analysis 自動生成 Slides (HTML→JPG→PDF) 和 Mind Map (JSON)

不需要外部 AI API，純腳本轉換。使用 Playwright 截圖生成投影片圖片。

用法：
  python gen_slides_mindmap.py --test 3        # 測試 3 個
  python gen_slides_mindmap.py --status        # 查看進度
  python gen_slides_mindmap.py                 # 跑全部未生成的
  python gen_slides_mindmap.py --limit 50      # 批次 50 個
  python gen_slides_mindmap.py --only mindmap  # 只生成 mind map
  python gen_slides_mindmap.py --only slides   # 只生成 slides
"""
import sys, io, os, json, re, argparse, time, logging, textwrap
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── Paths ──────────────────────────────────────────────
BASE = Path(r"C:\AntiGravityFile\YanYuInc")
JDG_DIR = BASE / "judgments"
AI_DIR = JDG_DIR / "_ai_analysis"
NLM_DIR = JDG_DIR / "_nlm_output"
PROGRESS_FILE = NLM_DIR / "_progress.json"
LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ── Logging ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "gen_slides_mindmap.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("gen_sm")

# ── Slide HTML Template ────────────────────────────────
SLIDE_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&display=swap');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    width: 1024px; height: 768px;
    font-family: 'Noto Sans TC', 'Microsoft JhengHei', sans-serif;
    background: #f8fafc;
    overflow: hidden;
  }
  .slide {
    width: 1024px; height: 768px;
    padding: 50px 60px;
    display: flex; flex-direction: column;
    position: relative;
  }
  .slide-title {
    background: linear-gradient(135deg, #1e3a5f, #2563eb);
    color: white;
    justify-content: center;
    align-items: center;
    text-align: center;
  }
  .slide-title h1 {
    font-size: 36px; font-weight: 700;
    line-height: 1.5; max-width: 800px;
    text-shadow: 0 2px 4px rgba(0,0,0,0.2);
  }
  .slide-title .subtitle {
    font-size: 18px; opacity: 0.85;
    margin-top: 20px; font-weight: 300;
  }
  .slide-title .badge {
    position: absolute; bottom: 40px; right: 60px;
    font-size: 14px; opacity: 0.6;
  }
  .slide-content {
    background: white;
  }
  .slide-content h2 {
    font-size: 28px; font-weight: 700;
    color: #1e3a5f;
    padding-bottom: 15px;
    border-bottom: 3px solid #2563eb;
    margin-bottom: 25px;
  }
  .slide-content .body-text {
    font-size: 20px; line-height: 1.8;
    color: #334155;
  }
  .slide-content ul {
    list-style: none; padding: 0;
  }
  .slide-content ul li {
    font-size: 19px; line-height: 1.7;
    color: #334155;
    padding: 10px 0 10px 35px;
    position: relative;
    border-bottom: 1px solid #f1f5f9;
  }
  .slide-content ul li:last-child { border-bottom: none; }
  .slide-content ul li::before {
    content: '';
    position: absolute; left: 0; top: 18px;
    width: 20px; height: 20px;
    background: #2563eb; border-radius: 50%;
    opacity: 0.15;
  }
  .slide-content ul li .num {
    position: absolute; left: 4px; top: 19px;
    font-size: 13px; font-weight: 700;
    color: #2563eb;
  }
  .slide-end {
    background: linear-gradient(135deg, #1e3a5f, #2563eb);
    color: white;
    justify-content: center;
    align-items: center;
    text-align: center;
  }
  .slide-end .logo { font-size: 32px; font-weight: 700; }
  .slide-end .tagline { font-size: 18px; opacity: 0.7; margin-top: 15px; }
  .page-num {
    position: absolute; bottom: 20px; right: 30px;
    font-size: 12px; color: #94a3b8;
  }
  .icon { font-size: 48px; margin-bottom: 20px; }
</style>
"""


def esc(text):
    """HTML-escape text."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_slide_html(title, summary, key_points, legal_insights, case_meta):
    """Generate a multi-page HTML document with one .slide div per page."""
    pages = []
    page_num = 0

    # ── Slide 1: Title ──
    page_num += 1
    meta_line = ""
    if case_meta.get("case_no"):
        meta_line += esc(case_meta["case_no"])
    if case_meta.get("category"):
        meta_line += f" | {esc(case_meta['category'])}"
    pages.append(f"""
    <div class="slide slide-title">
      <div class="icon">⚖️</div>
      <h1>{esc(title)}</h1>
      <div class="subtitle">{meta_line}</div>
      <div class="badge">YanYu 保險判決知識庫</div>
    </div>""")

    # ── Slide 2: Summary ──
    page_num += 1
    # Split summary into reasonable paragraphs
    paras = [p.strip() for p in summary.split("\n") if p.strip()]
    if len(paras) == 1 and len(paras[0]) > 200:
        # Split long single paragraph at sentence boundaries
        text = paras[0]
        chunks = re.split(r'(?<=[。；！？])', text)
        paras = []
        current = ""
        for chunk in chunks:
            if len(current) + len(chunk) > 180 and current:
                paras.append(current)
                current = chunk
            else:
                current += chunk
        if current:
            paras.append(current)

    para_html = "".join(f"<p style='margin-bottom:15px'>{esc(p)}</p>" for p in paras[:4])
    pages.append(f"""
    <div class="slide slide-content">
      <h2>📋 案情摘要</h2>
      <div class="body-text">{para_html}</div>
      <div class="page-num">{page_num}</div>
    </div>""")

    # ── Slides 3+: Key Points (2-3 per slide) ──
    kps = key_points or []
    chunk_size = 3 if len(kps) <= 6 else 2
    for ci in range(0, len(kps), chunk_size):
        page_num += 1
        chunk = kps[ci:ci + chunk_size]
        li_html = ""
        for j, kp in enumerate(chunk):
            idx = ci + j + 1
            li_html += f'<li><span class="num">{idx}</span>{esc(kp)}</li>\n'
        start_label = f"（{ci + 1}/{len(kps)}）" if len(kps) > chunk_size else ""
        pages.append(f"""
    <div class="slide slide-content">
      <h2>🔍 爭議焦點與裁判要旨 {start_label}</h2>
      <ul>{li_html}</ul>
      <div class="page-num">{page_num}</div>
    </div>""")

    # ── Slide: Legal Insights ──
    if legal_insights:
        page_num += 1
        li_parts = re.split(r'(?<=[。；])\s*', legal_insights)
        li_parts = [p.strip() for p in li_parts if p.strip() and len(p.strip()) > 5]
        if len(li_parts) <= 1:
            body = f"<div class='body-text'><p>{esc(legal_insights)}</p></div>"
        else:
            items = "".join(f'<li><span class="num">{i+1}</span>{esc(p)}</li>'
                           for i, p in enumerate(li_parts[:5]))
            body = f"<ul>{items}</ul>"
        pages.append(f"""
    <div class="slide slide-content">
      <h2>💡 法學見解與實務啟示</h2>
      {body}
      <div class="page-num">{page_num}</div>
    </div>""")

    # ── End Slide ──
    page_num += 1
    pages.append(f"""
    <div class="slide slide-end">
      <div class="logo">YanYu 保險判決知識庫</div>
      <div class="tagline">讓保險判決看得見、用得上</div>
      <div class="page-num" style="color:rgba(255,255,255,0.4)">{page_num}</div>
    </div>""")

    html = f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="utf-8">
<title>{esc(title)}</title>
{SLIDE_CSS}
</head><body>
{"".join(pages)}
</body></html>"""
    return html, page_num


def build_mindmap_json(title, summary, key_points, legal_insights, case_meta):
    """Generate hierarchical mind map JSON from AI analysis."""
    children = []

    # 基本資訊
    info_items = []
    if case_meta.get("case_no"):
        info_items.append({"name": f"案號：{case_meta['case_no']}"})
    if case_meta.get("case_type"):
        info_items.append({"name": f"案由：{case_meta['case_type']}"})
    if case_meta.get("category"):
        info_items.append({"name": f"分類：{case_meta['category']}"})
    if info_items:
        children.append({"name": "基本資訊", "children": info_items})

    # 案情摘要 — split into sentence-level children
    if summary:
        sentences = re.split(r'(?<=[。；！？])', summary)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
        if len(sentences) > 5:
            sentences = sentences[:5]
        children.append({
            "name": "案情摘要",
            "children": [{"name": s} for s in sentences]
        })

    # 爭議焦點
    if key_points:
        kp_children = []
        for kp in key_points:
            # If a key point has sub-sentences, make sub-children
            subs = re.split(r'(?<=[。；])', kp)
            subs = [s.strip() for s in subs if s.strip() and len(s.strip()) > 5]
            if len(subs) > 1:
                kp_children.append({"name": subs[0], "children": [{"name": s} for s in subs[1:]]})
            else:
                kp_children.append({"name": kp})
        children.append({"name": "爭議焦點與裁判要旨", "children": kp_children})

    # 法學見解
    if legal_insights:
        li_sents = re.split(r'(?<=[。；])\s*', legal_insights)
        li_sents = [s.strip() for s in li_sents if s.strip() and len(s.strip()) > 5]
        if li_sents:
            children.append({
                "name": "法學見解與實務啟示",
                "children": [{"name": s} for s in li_sents[:6]]
            })

    return {"name": title, "children": children}


def extract_case_meta(md_path):
    """Extract case number, type, category from judgment MD header."""
    meta = {}
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[:15]
        for line in lines:
            line = line.strip()
            m = re.search(r'\*\*案號\*\*[：:]\s*(.+)', line)
            if m:
                meta["case_no"] = m.group(1).strip()
            m = re.search(r'\*\*案由\*\*[：:]\s*(.+)', line)
            if m:
                meta["case_type"] = m.group(1).strip()
            m = re.search(r'\*\*分類\*\*[：:]\s*(.+)', line)
            if m:
                meta["category"] = m.group(1).strip()
    except Exception:
        pass
    return meta


def sanitize_path_component(name):
    """Strip trailing dots/spaces that Windows forbids in directory names."""
    return name.rstrip(". ")


def build_file_list():
    """Build ordered list matching nlm_batch.py structure."""
    files = []
    # Featured
    for f in sorted(AI_DIR.glob("featured/*.json")):
        # Find corresponding MD
        md = JDG_DIR / f"{f.stem}.md"
        stem = sanitize_path_component(f.stem)
        key = f"featured/{stem}"
        files.append({"ai_json": str(f), "md": str(md) if md.exists() else None,
                       "key": key, "type": "featured"})
    # Annual cases
    cases_dir = AI_DIR / "cases"
    if cases_dir.exists():
        for yr_dir in sorted(cases_dir.iterdir()):
            if yr_dir.is_dir() and yr_dir.name.isdigit():
                for f in sorted(yr_dir.glob("*.json")):
                    if f.name == "_progress.json":
                        continue
                    md = JDG_DIR / "cases" / yr_dir.name / f"{f.stem}.md"
                    stem = sanitize_path_component(f.stem)
                    key = f"cases/{yr_dir.name}/{stem}"
                    files.append({"ai_json": str(f), "md": str(md) if md.exists() else None,
                                  "key": key, "type": "annual"})
    return files


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"updated": "", "completed": {}, "errors": {}, "stats": {"ok": 0, "err": 0, "skip": 0}}


def save_progress(data):
    data["updated"] = datetime.now().isoformat(timespec='seconds')
    NLM_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def screenshot_slides(html_content, out_dir, slide_count):
    """Use Playwright to screenshot each slide div as JPG."""
    from playwright.sync_api import sync_playwright
    import tempfile

    # Write HTML to temp file
    tmp = Path(tempfile.mktemp(suffix='.html'))
    tmp.write_text(html_content, encoding='utf-8')

    slides_dir = out_dir / "slides_img"
    slides_dir.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1024, "height": 768})
            page.goto(f"file:///{tmp.as_posix()}")
            # Wait for fonts to load
            page.wait_for_timeout(1500)

            slides = page.query_selector_all(".slide")
            for i, slide in enumerate(slides):
                img_path = slides_dir / f"slide_{i+1:02d}.jpg"
                slide.screenshot(path=str(img_path), type="jpeg", quality=90)

            browser.close()
    finally:
        tmp.unlink(missing_ok=True)

    return sorted(slides_dir.glob("slide_*.jpg"))


def create_pdf_from_images(image_paths, pdf_path):
    """Combine slide JPGs into a single PDF."""
    import img2pdf

    img_bytes = []
    for p in image_paths:
        with open(p, 'rb') as f:
            img_bytes.append(f.read())

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with open(pdf_path, 'wb') as f:
        f.write(img2pdf.convert(img_bytes))


def run_generate(args):
    """Main generation loop."""
    files = build_file_list()
    total = len(files)
    log.info(f"共 {total} 個判決")

    progress = load_progress()
    completed = progress["completed"]

    do_slides = args.only in (None, "slides")
    do_mindmap = args.only in (None, "mindmap")

    # Filter to items that need generation
    todo = []
    for item in files:
        key = item["key"]
        c = completed.get(key, {})
        needs_slides = do_slides and not c.get("slides")
        needs_mindmap = do_mindmap and not c.get("mind_map")
        if needs_slides or needs_mindmap:
            item["_needs_slides"] = needs_slides
            item["_needs_mindmap"] = needs_mindmap
            todo.append(item)

    if args.start_from > 0:
        todo = todo[args.start_from:]
    if args.limit > 0:
        todo = todo[:args.limit]

    log.info(f"待生成: {len(todo)} / {total}")
    if not todo:
        log.info("全部已生成，無需處理")
        return

    ok_count = 0
    err_count = 0

    # Launch Playwright browser once (reuse across all items)
    from playwright.sync_api import sync_playwright
    import tempfile

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)

    try:
        for i, item in enumerate(todo):
            key = item["key"]
            ai_json = item["ai_json"]
            label = f"[{i+1}/{len(todo)}]"

            try:
                with open(ai_json, 'r', encoding='utf-8') as f:
                    analysis = json.load(f)
            except Exception as e:
                log.error(f"{label} 無法讀取 {ai_json}: {e}")
                err_count += 1
                continue

            raw_title = Path(ai_json).stem
            # Clean filename prefix like "01_", "001_"
            title = re.sub(r'^\d+_', '', raw_title)
            summary = analysis.get("summary", "")
            key_points = analysis.get("key_points", [])
            legal_insights = analysis.get("legal_insights", "")

            # Extract case metadata from MD
            case_meta = {}
            if item.get("md"):
                case_meta = extract_case_meta(item["md"])

            out_dir = NLM_DIR / key
            out_dir.mkdir(parents=True, exist_ok=True)

            if key not in completed:
                completed[key] = {}

            log.info(f"{label} 處理: {title[:50]}...")

            # ── Mind Map ──
            if item.get("_needs_mindmap"):
                try:
                    mm = build_mindmap_json(title, summary, key_points, legal_insights, case_meta)
                    mm_path = out_dir / "mindmap.json"
                    with open(mm_path, 'w', encoding='utf-8') as f:
                        json.dump(mm, f, ensure_ascii=False, indent=2)
                    completed[key]["mind_map"] = True
                    completed[key]["mind_map_source"] = "script"
                    log.info(f"  -> mindmap.json OK")
                except Exception as e:
                    log.error(f"  -> mindmap 錯誤: {e}")
                    err_count += 1

            # ── Slides ──
            if item.get("_needs_slides"):
                try:
                    html, slide_count = build_slide_html(
                        title, summary, key_points, legal_insights, case_meta
                    )
                    # Write HTML to temp, screenshot with shared browser
                    tmp = Path(tempfile.mktemp(suffix='.html'))
                    tmp.write_text(html, encoding='utf-8')

                    slides_dir = out_dir / "slides_img"
                    slides_dir.mkdir(parents=True, exist_ok=True)

                    page = browser.new_page(viewport={"width": 1024, "height": 768})
                    page.goto(f"file:///{tmp.as_posix()}")
                    page.wait_for_timeout(800)

                    slide_elements = page.query_selector_all(".slide")
                    img_paths = []
                    for si, slide_el in enumerate(slide_elements):
                        img_path = slides_dir / f"slide_{si+1:02d}.jpg"
                        slide_el.screenshot(path=str(img_path), type="jpeg", quality=90)
                        img_paths.append(img_path)

                    page.close()
                    tmp.unlink(missing_ok=True)

                    # Create PDF
                    if img_paths:
                        pdf_path = out_dir / "slides.pdf"
                        create_pdf_from_images(img_paths, pdf_path)
                        completed[key]["slides"] = True
                        completed[key]["slides_source"] = "script"
                        log.info(f"  -> slides OK ({len(img_paths)} pages)")
                    else:
                        log.warning(f"  -> slides: 未截到任何頁面")
                        err_count += 1
                except Exception as e:
                    log.error(f"  -> slides 錯誤: {e}")
                    err_count += 1

            ok_count += 1

            # Auto-save progress every 10 items
            if (i + 1) % 10 == 0 or i == len(todo) - 1:
                progress["completed"] = completed
                save_progress(progress)

    finally:
        browser.close()
        pw.stop()

    # Final save
    progress["completed"] = completed
    save_progress(progress)

    log.info("=" * 50)
    log.info(f"完成！成功: {ok_count}, 失敗: {err_count}")
    slides_done = sum(1 for v in completed.values() if v.get("slides"))
    mm_done = sum(1 for v in completed.values() if v.get("mind_map"))
    log.info(f"累計 slides: {slides_done}/{total}, mind_map: {mm_done}/{total}")
    log.info("=" * 50)


def show_status():
    files = build_file_list()
    total = len(files)
    progress = load_progress()
    completed = progress.get("completed", {})

    slides_ok = sum(1 for v in completed.values() if v.get("slides"))
    mm_ok = sum(1 for v in completed.values() if v.get("mind_map"))
    ig_ok = sum(1 for v in completed.values() if v.get("infographic"))

    no_slides = total - slides_ok
    no_mm = total - mm_ok

    log.info(f"總判決數:       {total}")
    log.info(f"Slides:         {slides_ok} ({slides_ok*100//max(total,1)}%)")
    log.info(f"Mind Map:       {mm_ok} ({mm_ok*100//max(total,1)}%)")
    log.info(f"Infographic:    {ig_ok} ({ig_ok*100//max(total,1)}%)")
    log.info(f"待生成 Slides:  {no_slides}")
    log.info(f"待生成 MindMap: {no_mm}")
    log.info(f"上次更新:       {progress.get('updated', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(description="批量生成判決 Slides 和 Mind Map")
    parser.add_argument('--test', type=int, metavar='N', help='測試模式：只處理 N 個')
    parser.add_argument('--limit', type=int, default=0, help='限制處理數量')
    parser.add_argument('--start-from', type=int, default=0, help='從第 N 個開始')
    parser.add_argument('--only', choices=['slides', 'mindmap'], default=None, help='只生成指定類型')
    parser.add_argument('--status', action='store_true', help='查看進度')
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.test is not None:
        args.limit = args.test
        run_generate(args)
    else:
        run_generate(args)


if __name__ == "__main__":
    main()
