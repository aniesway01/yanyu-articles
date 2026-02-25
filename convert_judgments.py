#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
convert_judgments.py — 將 ebookhub 保險判決 PDF 轉換為 Markdown
從所有年度（2014-2025）提取保險糾紛 PDF 文字，轉為 .md 格式
"""
import os, re, sys, io, datetime, logging
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import fitz  # PyMuPDF
except ImportError:
    print("pip install PyMuPDF"); sys.exit(1)

BASE = Path(r"C:\AntiGravityFile\YanYuInc")
EB_CASES = Path(r"C:\AntiGravityFile\Project\ebookhub") / "\u4e2d\u56fd\u6cd5\u9662\u6848\u4f8b2014-2025"
OUT_DIR = BASE / "judgments" / "ebookhub"
LOG_DIR = BASE / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)
log_path = LOG_DIR / f"convert_judgments_{datetime.datetime.now():%Y%m%d_%H%M%S}.log"
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(log_path, encoding="utf-8"),
              logging.StreamHandler(sys.stdout)])
log = logging.getLogger()

def extract_pdf_to_md(pdf_path, year, out_path):
    """Extract text from PDF and save as Markdown"""
    doc = fitz.open(str(pdf_path))
    page_count = len(doc)
    log.info(f"  \u958b\u59cb\u63d0\u53d6: {pdf_path.name} ({page_count} \u9801)")

    lines = []
    lines.append(f"# \u4e2d\u570b\u6cd5\u9662{year}\u5e74\u5ea6\u6848\u4f8b \u00b7 {pdf_path.stem}")
    lines.append("")
    lines.append(f"> \u4f86\u6e90\uff1a\u4e2d\u570b\u6cd5\u9662\u5e74\u5ea6\u6848\u4f8b\u53e2\u66f8")
    lines.append(f"> \u5e74\u4efd\uff1a{year}")
    lines.append(f"> \u539f\u59cb\u6a94\u6848\uff1a{pdf_path.name}")
    lines.append(f"> \u9801\u6578\uff1a{page_count} \u9801")
    lines.append(f"> \u8f49\u63db\u6642\u9593\uff1a{datetime.datetime.now():%Y-%m-%d %H:%M}")
    lines.append("")
    lines.append("---")
    lines.append("")

    empty_pages = 0
    for i, pg in enumerate(doc):
        text = pg.get_text("text")
        if not text.strip():
            empty_pages += 1
            continue
        # Clean up common OCR artifacts
        text = re.sub(r'\n{3,}', '\n\n', text)
        lines.append(text)
        lines.append("")  # page break spacing

    doc.close()
    content = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    text_size = len(content)
    log.info(f"  \u5b8c\u6210: {page_count} \u9801, {empty_pages} \u7a7a\u9801, "
             f"{text_size/1024:.0f}KB \u6587\u5b57")
    return page_count, text_size

def main():
    log.info("=" * 50)
    log.info("\u5224\u6c7a PDF \u8f49\u63db\u958b\u59cb")
    log.info("=" * 50)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for root, _, files in os.walk(EB_CASES):
        for f in files:
            if "\u4fdd\u9669" not in f or not f.lower().endswith(".pdf"):
                continue
            src = Path(root) / f
            rel_path = str(Path(root).relative_to(EB_CASES))
            yr_m = re.search(r'20[12]\d', rel_path)
            yr = yr_m.group() if yr_m else "unknown"

            out_name = f"{yr}_{Path(f).stem}.md"
            out_path = OUT_DIR / out_name

            if out_path.exists():
                log.info(f"\u5df2\u5b58\u5728\uff0c\u8df3\u904e: {out_name}")
                results.append({"year": yr, "name": f, "out": out_name, "status": "exists"})
                continue

            try:
                pages, text_sz = extract_pdf_to_md(src, yr, out_path)
                results.append({"year": yr, "name": f, "out": out_name, "pages": pages,
                                "text_kb": round(text_sz/1024, 1), "status": "ok"})
            except Exception as e:
                log.error(f"\u5931\u6557: {f} - {e}")
                results.append({"year": yr, "name": f, "status": "failed", "error": str(e)})

    log.info("=" * 50)
    ok = sum(1 for r in results if r["status"] == "ok")
    log.info(f"\u5b8c\u6210: {ok}/{len(results)} \u6210\u529f\u8f49\u63db")
    for r in results:
        if r["status"] == "ok":
            log.info(f"  {r['out']} ({r['pages']}\u9801, {r['text_kb']}KB)")
    log.info(f"\u65e5\u8a8c: {log_path}")

if __name__ == "__main__":
    main()
