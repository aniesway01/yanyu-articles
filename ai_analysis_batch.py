#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ai_analysis_batch.py — 用 Gemini Flash 批量生成判決「摘要/重點/法學見解」

用法：
  python ai_analysis_batch.py --test          # 跑 3 個樣本驗證
  python ai_analysis_batch.py                 # 跑全部
  python ai_analysis_batch.py --status        # 查看進度
  python ai_analysis_batch.py --start-from 50 # 從第 50 個開始
"""
import sys, io, json, time, re, argparse, random
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

# ─── Paths ───
BASE = Path(r"C:\AntiGravityFile\YanYuInc")
JUDGE_DIR = BASE / "judgments"
CASES_DIR = JUDGE_DIR / "cases"
OUT_DIR = JUDGE_DIR / "_ai_analysis"
PROGRESS_FILE = OUT_DIR / "_progress.json"

# ─── API Keys (Gemini Flash, rotated) ───
API_KEYS = [
    "AIzaSyAH1zyXj_bTykb23LV1q0LRq6vM3ROkSp0",
    "AIzaSyDy752wb7IxzSxkUxFD6RULKY0dGjIkidA",
    "AIzaSyAFIlhS7a1mVx3no9-FvJ_sj4CJMmAa5Ic",
    "AIzaSyA0-uyQkkqqhlgoh5McX1LGsVo9Xx1ufPc",
    "AIzaSyCxIItktl7wq1ZqFrrE9beIFb-b4dtZKQI",
    "AIzaSyBcG4OmFOrL3ktD5FuQ1BW8sKww8EtLOOQ",
]
MODEL = "gemini-2.0-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

# Rate limiting
RPM_PER_KEY = 15
DELAY_BASE = 60.0 / (RPM_PER_KEY * len(API_KEYS))  # ~0.67s between requests

PROMPT_TEMPLATE = """你是一位資深保險法律分析師。請分析以下保險糾紛判決，用繁體中文輸出以下三個部分：

1. **摘要**（summary）：用2-3句話概述案件當事人、爭議事實和判決結果。
2. **重點**（key_points）：列出3-5個爭議焦點或關鍵裁判要旨，每個不超過30字。
3. **法學見解**（legal_insights）：分析本案的裁判理由、適用的法律條文、以及對保險實務的啟示（200-400字）。

嚴格以JSON格式回覆（不要加 markdown code fence），結構如下：
{
  "summary": "...",
  "key_points": ["...", "...", "..."],
  "legal_insights": "..."
}

判決全文如下：

"""


def build_file_list():
    """Build ordered list: featured (11) + annual (607)."""
    files = []
    # Featured
    for f in sorted(JUDGE_DIR.glob("*.md")):
        files.append({"path": str(f), "key": f"featured/{f.stem}", "type": "featured"})
    # Annual
    for yr_dir in sorted(CASES_DIR.iterdir()):
        if yr_dir.is_dir() and yr_dir.name.isdigit():
            for f in sorted(yr_dir.glob("*.md")):
                key = f"cases/{yr_dir.name}/{f.stem}"
                files.append({"path": str(f), "key": key, "type": "annual"})
    return files


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"updated": "", "completed": {}, "errors": {}, "stats": {"ok": 0, "err": 0, "skip": 0}}


def save_progress(data):
    data["updated"] = datetime.now().isoformat(timespec='seconds')
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


_key_idx = 0

def call_gemini(text, max_retries=3):
    """Call Gemini Flash API with key rotation and retry."""
    global _key_idx
    prompt = PROMPT_TEMPLATE + text

    for attempt in range(max_retries):
        key = API_KEYS[_key_idx % len(API_KEYS)]
        _key_idx += 1

        try:
            resp = requests.post(
                f"{API_URL}?key={key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 2048,
                        "responseMimeType": "application/json",
                    }
                },
                timeout=60,
            )

            if resp.status_code == 429:
                wait = (attempt + 1) * 15
                print(f"    [429 Rate limit] 等待 {wait}s...", flush=True)
                time.sleep(wait)
                continue

            if resp.status_code != 200:
                print(f"    [HTTP {resp.status_code}] {resp.text[:150]}", flush=True)
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return None

            data = resp.json()
            # Extract text from response
            candidates = data.get("candidates", [])
            if not candidates:
                print(f"    [EMPTY] No candidates", flush=True)
                return None

            text_out = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not text_out:
                print(f"    [EMPTY] No text in response", flush=True)
                return None

            # Parse JSON from response (strip code fences if any)
            text_out = text_out.strip()
            text_out = re.sub(r'^```(?:json)?\s*', '', text_out)
            text_out = re.sub(r'\s*```$', '', text_out)

            result = json.loads(text_out)

            # Validate required fields
            if not all(k in result for k in ("summary", "key_points", "legal_insights")):
                print(f"    [INVALID] Missing fields: {list(result.keys())}", flush=True)
                if attempt < max_retries - 1:
                    continue
                return None

            return result

        except json.JSONDecodeError as e:
            print(f"    [JSON ERR] {str(e)[:80]}", flush=True)
            if attempt < max_retries - 1:
                continue
            return None
        except Exception as e:
            print(f"    [ERR] {str(e)[:100]}", flush=True)
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return None

    return None


def process_batch(args):
    files = build_file_list()
    total = len(files)
    print(f"[INFO] 共 {total} 個判決")

    # Apply range
    files = files[args.start_from:]
    if args.limit > 0:
        files = files[:args.limit]
    print(f"[INFO] 本次處理 {len(files)} 個 (start={args.start_from}, limit={args.limit})")

    if not files:
        print("[WARN] 沒有待處理的判決")
        return

    progress = load_progress()
    completed = progress["completed"]
    errors = progress["errors"]

    for i, item in enumerate(files):
        global_idx = args.start_from + i
        key = item["key"]
        label = f"[{global_idx+1}/{total}]"

        # Skip completed
        if key in completed:
            progress["stats"]["skip"] += 1
            continue

        # Read MD
        md_path = item["path"]
        with open(md_path, 'r', encoding='utf-8') as f:
            text = f.read()

        # Truncate extremely long texts (shouldn't happen, max is 27KB)
        if len(text) > 60000:
            text = text[:60000] + "\n\n[...截斷...]"

        print(f"  {label} {Path(md_path).name[:50]}...", end=" ", flush=True)

        result = call_gemini(text)
        if result:
            # Save individual JSON
            out_path = OUT_DIR / key
            out_path = out_path.with_suffix('.json') if not str(out_path).endswith('.json') else out_path
            # Ensure parent dirs: _ai_analysis/cases/2018/ or _ai_analysis/featured/
            json_path = OUT_DIR / (key + ".json")
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            completed[key] = {
                "processed_at": datetime.now().isoformat(timespec='seconds'),
                "has_summary": bool(result.get("summary")),
                "key_points_count": len(result.get("key_points", [])),
            }
            progress["stats"]["ok"] += 1
            kp = len(result.get("key_points", []))
            print(f"OK (摘要+{kp}重點+見解)", flush=True)
        else:
            errors[key] = datetime.now().isoformat(timespec='seconds')
            progress["stats"]["err"] += 1
            print("FAILED", flush=True)

        # Save progress every 10
        if (i + 1) % 10 == 0:
            progress["completed"] = completed
            progress["errors"] = errors
            save_progress(progress)

        # Rate limit delay
        time.sleep(DELAY_BASE + random.uniform(0, 0.5))

    # Final save
    progress["completed"] = completed
    progress["errors"] = errors
    save_progress(progress)

    print(f"\n{'='*50}")
    print(f"  完成！成功: {progress['stats']['ok']} | 失敗: {progress['stats']['err']} | 跳過: {progress['stats']['skip']}")
    print(f"  累計完成: {len(completed)} | 累計錯誤: {len(errors)}")
    print(f"{'='*50}")


def show_status():
    progress = load_progress()
    completed = progress.get("completed", {})
    errors = progress.get("errors", {})
    files = build_file_list()

    total = len(files)
    done = len(completed)
    errs = len(errors)

    print(f"總判決數:    {total}")
    print(f"已完成:      {done} ({done*100//max(total,1)}%)")
    print(f"錯誤:        {errs}")
    print(f"待處理:      {total - done}")
    print(f"上次更新:    {progress.get('updated', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(description="Gemini Flash 批量判決分析")
    parser.add_argument('--limit', type=int, default=0, help='只處理前 N 個（0=全部）')
    parser.add_argument('--start-from', type=int, default=0, help='從第 N 個開始')
    parser.add_argument('--status', action='store_true', help='查看進度')
    parser.add_argument('--test', action='store_true', help='只跑 3 個樣本驗證')
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.test:
        args.limit = 3
        args.start_from = 11  # Skip featured, start from annual cases
        print("[TEST] 只跑 3 個年度案例做樣本驗證\n")

    process_batch(args)


if __name__ == "__main__":
    main()
