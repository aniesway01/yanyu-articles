#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
nlm_batch.py — 批量用 NotebookLM 為判決生成 Slides / Infographic / Mind Map

用法：
  python nlm_batch.py                    # 跑全部
  python nlm_batch.py --limit 5          # 只跑 5 個（測試）
  python nlm_batch.py --start-from 20    # 從第 20 個開始
  python nlm_batch.py --status           # 查看進度
"""
import sys, io, os, json, asyncio, argparse, time, random
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE = Path(r"C:\AntiGravityFile\YanYuInc")
JUDGE_DIR = BASE / "judgments"
CASES_DIR = JUDGE_DIR / "cases"
OUT_DIR = JUDGE_DIR / "_nlm_output"
PROGRESS_FILE = OUT_DIR / "_progress.json"

# Artifact generation timeout (seconds)
GEN_TIMEOUT = 600
# Delay between notebooks (seconds) to avoid rate limiting
DELAY_BETWEEN = (15, 30)


def build_file_list():
    """Build ordered list of all judgment MD files."""
    files = []
    # 1. Featured (root judgments/*.md)
    for f in sorted(JUDGE_DIR.glob("*.md")):
        files.append({"path": str(f), "key": f"featured/{f.stem}", "type": "featured"})
    # 2. Annual (cases/YYYY/*.md)
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


async def process_one(client, md_path, key, out_subdir):
    """Process a single judgment: create notebook → upload → generate artifacts → download."""
    from notebooklm import (
        SlideDeckFormat, InfographicOrientation, InfographicDetail,
    )

    out_subdir.mkdir(parents=True, exist_ok=True)
    title = Path(md_path).stem[:80]
    result = {"notebook_id": "", "slides": False, "infographic": False, "mind_map": False}

    # 1. Create notebook
    nb = await client.notebooks.create(f"判決分析：{title}")
    nb_id = nb.id
    result["notebook_id"] = nb_id

    # 2. Upload MD
    src = await client.sources.add_file(nb_id, md_path, wait=True, wait_timeout=120)
    if not src.is_ready:
        raise RuntimeError(f"Source not ready: {src.title}")

    # 3. Generate Slide Deck
    try:
        sd = await client.artifacts.generate_slide_deck(
            nb_id,
            language='zh-TW',
            instructions='用繁體中文，聚焦案情摘要、爭議焦點、法院裁判理由和實務啟示',
            slide_format=SlideDeckFormat.DETAILED_DECK,
        )
        sd_final = await client.artifacts.wait_for_completion(nb_id, sd.task_id, timeout=GEN_TIMEOUT)
        if sd_final.is_complete:
            await client.artifacts.download_slide_deck(nb_id, str(out_subdir / "slides.pdf"))
            result["slides"] = True
    except Exception as e:
        result["slides_error"] = str(e)[:200]

    # 4. Generate Infographic
    try:
        ig = await client.artifacts.generate_infographic(
            nb_id,
            language='zh-TW',
            instructions='包含案情流程、爭議焦點和判決結果',
            orientation=InfographicOrientation.PORTRAIT,
            detail_level=InfographicDetail.DETAILED,
        )
        ig_final = await client.artifacts.wait_for_completion(nb_id, ig.task_id, timeout=GEN_TIMEOUT)
        if ig_final.is_complete:
            await client.artifacts.download_infographic(nb_id, str(out_subdir / "infographic.png"))
            result["infographic"] = True
    except Exception as e:
        result["infographic_error"] = str(e)[:200]

    # 5. Generate Mind Map
    try:
        mm = await client.artifacts.generate_mind_map(nb_id)
        if mm and mm.get('note_id'):
            await client.artifacts.download_mind_map(nb_id, str(out_subdir / "mindmap.json"))
            result["mind_map"] = True
    except Exception as e:
        result["mind_map_error"] = str(e)[:200]

    return result


async def run_batch(args):
    from notebooklm import NotebookLMClient

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

    async with await NotebookLMClient.from_storage() as client:
        for i, item in enumerate(files):
            global_idx = args.start_from + i
            key = item["key"]
            label = f"[{global_idx+1}/{total}]"

            # Skip already completed
            if key in completed:
                progress["stats"]["skip"] += 1
                print(f"  {label} [SKIP] {key}", flush=True)
                continue

            # Clear previous error for retry
            errors.pop(key, None)

            md_path = item["path"]
            out_subdir = OUT_DIR / key
            print(f"  {label} 處理: {Path(md_path).name[:60]}...", flush=True)

            try:
                result = await process_one(client, md_path, key, out_subdir)
                completed[key] = {
                    "notebook_id": result["notebook_id"],
                    "slides": result["slides"],
                    "infographic": result["infographic"],
                    "mind_map": result["mind_map"],
                    "processed_at": datetime.now().isoformat(timespec='seconds'),
                }
                arts = sum([result["slides"], result["infographic"], result["mind_map"]])
                progress["stats"]["ok"] += 1
                print(f"         -> OK ({arts}/3 artifacts)", flush=True)
                if not result["slides"]:
                    print(f"         [!] Slides: {result.get('slides_error','?')[:80]}", flush=True)
                if not result["infographic"]:
                    print(f"         [!] Infographic: {result.get('infographic_error','?')[:80]}", flush=True)
            except Exception as e:
                msg = str(e)[:300]
                errors[key] = msg
                progress["stats"]["err"] += 1
                print(f"         -> ERROR: {msg[:100]}", flush=True)

            # Auto-save progress
            progress["completed"] = completed
            progress["errors"] = errors
            save_progress(progress)

            # Delay between requests
            delay = random.uniform(*DELAY_BETWEEN)
            print(f"         (delay {delay:.0f}s)", flush=True)
            await asyncio.sleep(delay)

    # Final stats
    print("\n" + "=" * 60)
    print(f"  完成！")
    print(f"  本次成功: {progress['stats']['ok']}")
    print(f"  本次失敗: {progress['stats']['err']}")
    print(f"  跳過已有: {progress['stats']['skip']}")
    print(f"  累計完成: {len(completed)}")
    print(f"  累計錯誤: {len(errors)}")
    print(f"  輸出目錄: {OUT_DIR}")
    print("=" * 60)


def show_status():
    progress = load_progress()
    completed = progress.get("completed", {})
    errors = progress.get("errors", {})
    files = build_file_list()

    total = len(files)
    done = len(completed)
    errs = len(errors)
    remaining = total - done

    # Count artifact types
    slides_ok = sum(1 for v in completed.values() if v.get("slides"))
    info_ok = sum(1 for v in completed.values() if v.get("infographic"))
    mm_ok = sum(1 for v in completed.values() if v.get("mind_map"))

    print(f"總判決數:    {total}")
    print(f"已完成:      {done} ({done*100//total}%)")
    print(f"錯誤:        {errs}")
    print(f"待處理:      {remaining}")
    print(f"")
    print(f"Slides:      {slides_ok}/{done}")
    print(f"Infographic: {info_ok}/{done}")
    print(f"Mind Map:    {mm_ok}/{done}")
    print(f"")
    print(f"上次更新:    {progress.get('updated', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(description="NotebookLM 批量生成判決 artifacts")
    parser.add_argument('--limit', type=int, default=0, help='只處理前 N 個（0=全部）')
    parser.add_argument('--start-from', type=int, default=0, help='從第 N 個開始')
    parser.add_argument('--status', action='store_true', help='查看進度')
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    asyncio.run(run_batch(args))


if __name__ == "__main__":
    main()
