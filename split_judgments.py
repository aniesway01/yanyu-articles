#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
split_judgments.py — 將年度案例合集 MD 拆分為一案一檔
輸入：judgments/ebookhub/*.md
輸出：judgments/cases/YYYY/NN_标题.md + judgments/cases/_index.json

用法：
  python split_judgments.py           # 拆分全部
  python split_judgments.py --status  # 查看統計
"""

import json, os, re, sys, io, datetime
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = Path(r"C:\AntiGravityFile\YanYuInc")
EB_DIR = BASE / "judgments" / "ebookhub"
CASE_DIR = BASE / "judgments" / "cases"
INDEX_FILE = CASE_DIR / "_index.json"
LOG_DIR = BASE / "logs"

# OCR artifacts to clean
PAGE_MARKER_RE = re.compile(r'^##\s*第\s*\d+\s*頁\s*$')
PAGE_FOOTER_RE = re.compile(r'^\d{1,3}中国法院\d{4}年度案例[·.].*$')
RUNNING_HEADER_RE = re.compile(r'^[一二三四五六七八九十]+[、.]\s*\S+纠纷\s*$')
EMPTY_COMMENT_RE = re.compile(r'^<!--\s*第\s*\d+\s*頁[：:]\s*無法識別文字\s*-->\s*$')
# v2: additional OCR cleanup patterns (2026-02-26)
RUNNING_PAGE_NUM_RE = re.compile(r'^\s*\d{1,3}\s*$')
RUNNING_HEADER_V2_RE = re.compile(r'^中国法院\d{4}年度案例[·.·].*$')
SECTION_TITLE_RE = re.compile(
    r'^[一二三四五六七八九十]+[、.．]\s*\S{2,8}(?:纠纷|案例)?\s*$'
)
# Punctuation that naturally ends a Chinese sentence/clause
_END_PUNCT = set('。，；：？！」）》】、…—')
# Patterns for lines that should NOT be merged with the previous line
_LIST_ITEM_RE = re.compile(r'^\s*(?:\d{1,2}[.、．)]|[（(]\d{1,2}[)）]|[（(][一二三四五六七八九十]+[)）]|[一二三四五六七八九十]+[、.．])')
_HEADING_PREFIX_RE = re.compile(r'^\s*(?:【|##|---|\*\*\*)')


def clean_ocr_line(line, is_ocr):
    """Remove OCR artifacts from a single line.

    v2 (2026-02-26): added rules for:
      - standalone page numbers (1~3 digit lines)
      - running headers like '中国法院20XX年度案例·...'
      - stray section headings like '一、确认劳动关系'
    """
    if not is_ocr:
        return line
    s = line.strip()
    if PAGE_MARKER_RE.match(s):
        return None
    if PAGE_FOOTER_RE.match(s):
        return None
    if EMPTY_COMMENT_RE.match(s):
        return None
    # v2 rules -------------------------------------------------------
    # Standalone page number (e.g. "54", "120")
    if RUNNING_PAGE_NUM_RE.match(s):
        return None
    # Running header at top of each page
    # e.g. "中国法院2025年度案例·保险纠纷"
    if RUNNING_HEADER_V2_RE.match(s):
        return None
    # Stray section heading that leaked into case body
    # e.g. "一、确认劳动关系", "二、保险纠纷"
    if SECTION_TITLE_RE.match(s):
        return None
    return line


def clean_case_content(text, is_ocr):
    """Clean a block of case content.

    v2 (2026-02-26): added OCR line-break merging — if a line does not end
    with sentence-ending punctuation and the next line is a plain continuation
    (not a heading / list item), merge them into one line.
    """
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        result = clean_ocr_line(line, is_ocr)
        if result is not None:
            cleaned.append(result)

    # --- v2: OCR line-break merging ---
    if is_ocr:
        merged = []
        i = 0
        while i < len(cleaned):
            cur = cleaned[i]
            cur_stripped = cur.rstrip()
            # Try merging with next line if:
            #   1) current line is non-empty
            #   2) current line does NOT end with sentence-ending punctuation
            #   3) next line exists, is non-empty, does not start with spaces (indent)
            #   4) next line is not a heading / list item / structural marker
            if (cur_stripped
                    and cur_stripped[-1] not in _END_PUNCT
                    and i + 1 < len(cleaned)):
                nxt = cleaned[i + 1]
                nxt_stripped = nxt.strip()
                if (nxt_stripped
                        and not nxt.startswith(' ')
                        and not nxt.startswith('\t')
                        and not _HEADING_PREFIX_RE.match(nxt_stripped)
                        and not _LIST_ITEM_RE.match(nxt_stripped)):
                    # Merge: append next line content to current
                    merged.append(cur_stripped + nxt_stripped)
                    i += 2
                    continue
            merged.append(cur)
            i += 1
        cleaned = merged

    # Remove excessive blank lines
    out = '\n'.join(cleaned)
    out = re.sub(r'\n{4,}', '\n\n\n', out)
    return out.strip()


def detect_is_ocr(text):
    """Check if file was OCR'd.

    v2 (2026-02-26): also detects files without '## 第X頁' markers but with
    running page-headers like '中国法院20XX年度案例·...', which appear in
    "超高清" PDF conversions.
    """
    if re.search(r'##\s*第\s*\d+\s*頁', text):
        return True
    # Count running page headers — if >=3, treat as OCR source
    headers = re.findall(r'^中国法院\d{4}年度案例[·.·]', text, re.MULTILINE)
    if len(headers) >= 3:
        return True
    return False


def extract_case_meta(info_block):
    """Extract case number, type, and parties from 【案件基本信息】 block"""
    case_no = ""
    case_type = ""
    plaintiff = ""
    defendant = ""

    # 裁判书字号
    m = re.search(r'裁判书字号[：:\s]*\n?\s*(.+?)(?:\n|$)', info_block)
    if m:
        case_no = m.group(1).strip()
        # Clean the case number
        case_no = re.sub(r'^[\d.]+\s*', '', case_no)

    # 案由
    m = re.search(r'案由[：:\s]*(.+?)(?:\n|$)', info_block)
    if m:
        case_type = m.group(1).strip()
        case_type = re.sub(r'^[\d.]+\s*', '', case_type)

    # 当事人
    m = re.search(r'原告[（(]?[^)）]*[)）]?[：:\s]*(.+?)(?:\n|$)', info_block)
    if m:
        plaintiff = m.group(1).strip()
    m = re.search(r'被告[（(]?[^)）]*[)）]?[：:\s]*(.+?)(?:\n|$)', info_block)
    if m:
        defendant = m.group(1).strip()

    return case_no, case_type, plaintiff, defendant


def find_cases_in_text(text, is_ocr):
    """Find all case boundaries in a single file's text"""
    lines = text.split('\n')
    marker = '【案件基本信息】'

    # Find all line numbers with the marker
    marker_lines = []
    for i, line in enumerate(lines):
        if marker in line.strip():
            marker_lines.append(i)

    if not marker_lines:
        return []

    cases = []
    for idx, ml in enumerate(marker_lines):
        # Look backwards from marker to find case header
        case_num_str = ""
        case_title = ""
        case_parties = ""
        header_start = ml  # default

        search_start = max(ml - 20, 0)
        # Collect candidate lines (skip page markers, empty, comments)
        candidates = []
        for j in range(ml - 1, search_start - 1, -1):
            s = lines[j].strip()
            if not s:
                continue
            if is_ocr and (PAGE_MARKER_RE.match(s) or PAGE_FOOTER_RE.match(s) or EMPTY_COMMENT_RE.match(s)):
                continue
            candidates.append((j, s))

        # Look for parties line (——...案)
        parties_line_idx = None
        for j, s in candidates:
            if s.startswith('——') or s.startswith('—') or s.startswith('--'):
                case_parties = re.sub(r'^[—\-–\s]+', '', s).strip()
                parties_line_idx = j
                break

        # Look for title and number
        # Title is usually the line before parties
        # Number is the line before title (or at the start of title)
        found_title = False
        for j, s in candidates:
            if parties_line_idx is not None and j >= parties_line_idx:
                continue
            # Skip section headers
            if re.match(r'^[一二三四五六七八九十]+[、.]', s):
                continue
            if re.match(r'^[（(][一二三四五六七八九十]+[)）]', s):
                continue

            # Check for "number.title" pattern
            m = re.match(r'^(\d{1,3})\s*[.、]?\s*(.+)', s)
            if m:
                case_num_str = m.group(1)
                rest = m.group(2).strip()
                if rest and not rest.startswith('裁判') and not rest.startswith('案由'):
                    case_title = rest
                header_start = j
                found_title = True
                break

            # Check for standalone number
            if re.match(r'^\d{1,3}$', s):
                case_num_str = s
                header_start = j
                continue  # title should be on next non-empty line

            # If we already found a number, this line is the title
            if case_num_str and not found_title:
                case_title = s
                found_title = True
                break

            # This might be the title (if no number found)
            # Must be >5 chars, not a page footer, not from TOC (no ......page_num pattern)
            if not found_title and len(s) > 5 and not s.startswith('编写人'):
                # Skip TOC-style entries (title.....page_number)
                if re.search(r'\.{3,}\d{1,3}$', s):
                    continue
                case_title = s
                header_start = j
                found_title = True
                # Keep looking for number above
                continue

        # Determine content range
        content_start = header_start
        if idx < len(marker_lines) - 1:
            # Content ends at next case's header
            next_ml = marker_lines[idx + 1]
            # Find the next case's header_start by looking backwards from next marker
            next_header = next_ml
            for j in range(next_ml - 1, max(next_ml - 20, content_start), -1):
                s = lines[j].strip()
                if not s or (is_ocr and PAGE_MARKER_RE.match(s)):
                    continue
                if s.startswith('编写人'):
                    next_header = j + 1
                    break
                m = re.match(r'^(\d{1,3})\s*[.、]?\s*\S', s)
                if m and int(m.group(1)) <= 99:
                    next_header = j
                    break
                if s.startswith('——') or s.startswith('—'):
                    continue
                if re.match(r'^[一二三四五六七八九十]+[、.]', s):
                    next_header = j
                    break
                if re.match(r'^[（(][一二三四五六七八九十]+[)）]', s):
                    next_header = j
                    break
            content_end = next_header
        else:
            content_end = len(lines)

        # Extract the content
        content_lines = lines[content_start:content_end]
        content = '\n'.join(content_lines)

        # Extract metadata from 【案件基本信息】 block
        info_end = content.find('【基本案情】')
        if info_end == -1:
            info_end = min(len(content), 500)
        info_block = content[content.find(marker):info_end] if marker in content else ""
        case_no, case_type, plaintiff, defendant = extract_case_meta(info_block)

        # Find section context
        section = ""
        for j in range(header_start - 1, max(header_start - 30, 0), -1):
            s = lines[j].strip()
            if is_ocr and (PAGE_MARKER_RE.match(s) or PAGE_FOOTER_RE.match(s)):
                continue
            m1 = re.match(r'^[一二三四五六七八九十]+[、.]\s*(.+)', s)
            if m1:
                section = m1.group(1).strip()
                break
            m2 = re.match(r'^[（(]([一二三四五六七八九十]+)[)）]\s*(.+)', s)
            if m2 and section:
                section = section + " > " + m2.group(2).strip()
                break

        # Clean title: remove TOC dots, page numbers, trailing noise
        if case_title:
            case_title = re.sub(r'\.{2,}\d*$', '', case_title).strip()
            case_title = re.sub(r'…+\d*$', '', case_title).strip()
        # Skip entries with very short/numeric titles (likely false positives)
        if case_title and len(case_title) <= 2 and case_title.isdigit():
            case_title = ""
        # If no good title, try to extract from first non-empty content line after marker
        if not case_title:
            for k in range(ml + 1, min(ml + 5, len(lines))):
                s2 = lines[k].strip()
                if s2.startswith('1.裁判') or s2.startswith('1．裁判'):
                    # look for the case title from the 裁判书字号 below
                    continue
                if s2 and len(s2) > 8 and not s2.startswith('【'):
                    case_title = s2[:50]
                    break

        cases.append({
            "num": case_num_str or str(idx + 1),
            "title": case_title or f"案例{case_num_str or idx+1}",
            "parties": case_parties,
            "case_no": case_no,
            "case_type": case_type,
            "plaintiff": plaintiff,
            "defendant": defendant,
            "section": section,
            "content": content,
        })

    return cases


def sanitize_filename(title, max_len=50):
    """Create a safe filename from a title"""
    # Remove chars not safe for filenames
    safe = re.sub(r'[<>:"/\\|?*\n\r]', '', title)
    safe = safe.strip('. ')
    if len(safe) > max_len:
        safe = safe[:max_len].rstrip()
    return safe or "untitled"


def split_single_file(md_path):
    """Split a single year-collection file into individual case files"""
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()

    yr_m = re.search(r'^(\d{4})_', md_path.name)
    year = yr_m.group(1) if yr_m else "unknown"
    is_ocr = detect_is_ocr(text)

    # Extract source info from header
    source_pdf = md_path.name.replace(f"{year}_", "").replace(".md", ".pdf")
    header_m = re.search(r'原始檔案[：:]\s*(.+)', text)
    if header_m:
        source_pdf = header_m.group(1).strip()

    cases = find_cases_in_text(text, is_ocr)
    if not cases:
        print(f"  {md_path.name}: 0 個案例，跳過")
        return []

    print(f"  {md_path.name}: 找到 {len(cases)} 個案例")

    # Write individual case files
    year_dir = CASE_DIR / year
    year_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for case in cases:
        num_str = case["num"].zfill(2)
        title_safe = sanitize_filename(case["title"])
        filename = f"{num_str}_{title_safe}.md"
        out_path = year_dir / filename

        # Clean content
        content = clean_case_content(case["content"], is_ocr)

        # Build header
        header = f"""# {case['title'] or '（未識別標題）'}

> **來源**：《中國法院{year}年度案例》保險糾紛
> **原始文件**：{source_pdf}"""
        if case["case_no"]:
            header += f"\n> **案號**：{case['case_no']}"
        if case["case_type"]:
            header += f"\n> **案由**：{case['case_type']}"
        if case["parties"]:
            header += f"\n> **當事人**：{case['parties']}"
        if case["section"]:
            header += f"\n> **分類**：{case['section']}"
        header += "\n\n---\n"

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(header + "\n" + content)

        results.append({
            "year": year,
            "num": int(case["num"]) if case["num"].isdigit() else 0,
            "title": case["title"],
            "parties": case["parties"],
            "case_no": case["case_no"],
            "case_type": case["case_type"],
            "section": case["section"],
            "filename": filename,
            "source_pdf": source_pdf,
        })

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="拆分年度案例合集為一案一檔")
    parser.add_argument("--status", action="store_true", help="查看統計")
    args = parser.parse_args()

    if args.status:
        if INDEX_FILE.exists():
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                idx = json.load(f)
            print(f"生成時間: {idx['generated']}")
            print(f"總案例數: {idx['total_cases']}")
            for yr, info in sorted(idx.get("by_year", {}).items()):
                print(f"  {yr} 年: {info['count']} 個案例 ({info['source_file']})")
        else:
            print("尚未執行拆分")
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CASE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("拆分年度案例合集為一案一檔")
    print("=" * 50)

    all_cases = []
    by_year = {}

    for md_path in sorted(EB_DIR.glob("*.md")):
        results = split_single_file(md_path)
        if results:
            year = results[0]["year"]
            by_year[year] = {
                "count": len(results),
                "source_file": md_path.name,
            }
            all_cases.extend(results)

    # Write index
    index = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_cases": len(all_cases),
        "by_year": by_year,
        "cases": all_cases,
    }
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n拆分完成: {len(all_cases)} 個案例")
    for yr in sorted(by_year):
        print(f"  {yr} 年: {by_year[yr]['count']} 個")
    print(f"索引: {INDEX_FILE}")


if __name__ == "__main__":
    main()
