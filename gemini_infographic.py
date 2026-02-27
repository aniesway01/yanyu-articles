#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gemini_infographic.py — 用 Gemini API 為判決生成 infographic（資訊圖表）

繞過 NotebookLM 的 CJK 亂碼問題，直接從 AI 分析 JSON 生成。

用法：
  python gemini_infographic.py --test 3        # 測試 3 張
  python gemini_infographic.py --status         # 查看進度
  python gemini_infographic.py                  # 跑全部未生成的
  python gemini_infographic.py --limit 50       # 批次 50 張
  python gemini_infographic.py --repair         # 修復現有亂碼圖片
"""
import sys, io, os, json, argparse, time, re, base64, logging
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
        logging.FileHandler(LOG_DIR / "gemini_infographic.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("gemini_ig")

# ── API Keys (from APIkeyBase.md) ─────────────────────
GEMINI_KEYS = [
    "AIzaSyCWSi37k9x6JVw0Hre_X9NJ0cdp-w_I6_k",
    "AIzaSyB32wgQx6QfWO2Olo_w-N1X9FCwGGwDdOk",
    "AIzaSyD8gRSSjqJmDgonsMRwMa1DA7a2AIHaoGA",
    "AIzaSyBh1xyclIhGS3zRRiosVoig8D0uDJJAzHY",
    "AIzaSyDi58x_uyQIPVq9RuPXx2T1FRh4ez7nyDI",
    "AIzaSyDNJffEiIdxtpLfqi4diKjja3-SfH3EQvI",
]
# Image generation model
MODEL = "gemini-3-pro-image-preview"

def _set_model(m):
    global MODEL
    MODEL = m


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


def build_file_list():
    """Build ordered list matching nlm_batch.py structure."""
    files = []
    # Featured
    for f in sorted(AI_DIR.glob("featured/*.json")):
        key = f"featured/{f.stem}"
        files.append({"ai_json": str(f), "key": key, "type": "featured"})
    # Annual cases
    cases_dir = AI_DIR / "cases"
    if cases_dir.exists():
        for yr_dir in sorted(cases_dir.iterdir()):
            if yr_dir.is_dir() and yr_dir.name.isdigit():
                for f in sorted(yr_dir.glob("*.json")):
                    if f.name == "_progress.json":
                        continue
                    key = f"cases/{yr_dir.name}/{f.stem}"
                    files.append({"ai_json": str(f), "key": key, "type": "annual"})
    return files


def build_prompt(analysis, title):
    """Construct infographic generation prompt from AI analysis data."""
    summary = analysis.get("summary", "")
    key_points = analysis.get("key_points", [])
    legal_insights = analysis.get("legal_insights", "")

    kp_text = "\n".join(f"  {i+1}. {kp}" for i, kp in enumerate(key_points))

    # Truncate legal_insights if too long (keep first ~500 chars)
    if len(legal_insights) > 600:
        legal_insights = legal_insights[:580] + "……"

    prompt = f"""請生成一張精美的法律案件資訊圖表（infographic），主題如下：

案件：{title}

案情摘要：
{summary}

爭議焦點：
{kp_text}

法學見解：
{legal_insights}

設計要求：
1. 直向排版（portrait），寬約 800px、高約 1200px
2. 使用專業、現代的設計風格，配色為深藍+灰白色系
3. 頂部放置案件標題，下方分區塊展示：摘要、爭議焦點（列表）、法學見解
4. 每個區塊有清晰的標題和分隔
5. 適當使用圖標（天秤、法槌、盾牌等法律相關圖標）
6. 所有文字必須使用清晰正確的繁體中文
7. 文字大小適中、可讀性高，避免文字重疊或模糊
8. 底部標註「YanYu 保險判決知識庫」"""

    return prompt


def generate_infographic(client, prompt, output_path, model=MODEL):
    """Call Gemini API to generate an infographic image."""
    from google.genai import types

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            temperature=0.8,
        ),
    )

    # Extract image from response
    for part in response.candidates[0].content.parts:
        if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(part.inline_data.data)
            size_kb = len(part.inline_data.data) / 1024
            log.info(f"  -> 已保存 {output_path.name} ({size_kb:.0f} KB)")
            return True

    # No image in response — log text parts for debugging
    for part in response.candidates[0].content.parts:
        if hasattr(part, 'text') and part.text:
            log.warning(f"  -> 模型回覆文字（無圖片）: {part.text[:200]}")
    return False


def repair_infographic(client, image_path, output_path, model=MODEL):
    """Upload an existing garbled infographic and ask Gemini to fix CJK text."""
    from google.genai import types

    with open(image_path, "rb") as f:
        image_data = f.read()

    img_part = types.Part.from_bytes(data=image_data, mime_type="image/png")

    response = client.models.generate_content(
        model=model,
        contents=[
            img_part,
            "請將這張資訊圖表用最高解析度重新生成，修復所有中文字的亂碼和渲染錯誤。"
            "確保所有繁體中文文字清晰正確、可讀性高。保持原始的佈局和設計風格不變。",
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            temperature=0.4,
        ),
    )

    for part in response.candidates[0].content.parts:
        if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(part.inline_data.data)
            size_kb = len(part.inline_data.data) / 1024
            log.info(f"  -> 修復完成 {output_path.name} ({size_kb:.0f} KB)")
            return True
    return False


class KeyRotator:
    """Round-robin API key rotation with per-key rate limiting."""

    def __init__(self, keys, rpm_per_key=14):
        self.keys = keys
        self.rpm = rpm_per_key
        self.idx = 0
        self.call_times = {k: [] for k in keys}

    def get_client(self):
        from google import genai
        key = self.keys[self.idx]
        self.idx = (self.idx + 1) % len(self.keys)
        return genai.Client(api_key=key), key

    def wait_if_needed(self, key):
        """Enforce per-key RPM limit."""
        now = time.time()
        times = self.call_times[key]
        # Remove entries older than 60s
        self.call_times[key] = [t for t in times if now - t < 60]
        times = self.call_times[key]
        if len(times) >= self.rpm:
            wait = 60 - (now - times[0]) + 1
            if wait > 0:
                log.info(f"  (key ...{key[-6:]} RPM limit, wait {wait:.0f}s)")
                time.sleep(wait)
        self.call_times[key].append(time.time())


def run_generate(args):
    """Main generation loop."""
    files = build_file_list()
    total = len(files)
    log.info(f"共 {total} 個判決")

    progress = load_progress()
    completed = progress["completed"]

    # Filter to items that need infographic
    todo = []
    for item in files:
        key = item["key"]
        c = completed.get(key, {})
        # Skip if already has a Gemini-generated infographic
        out_path = NLM_DIR / key / "infographic.png"
        if out_path.exists() and c.get("infographic"):
            continue
        todo.append(item)

    if args.start_from > 0:
        todo = todo[args.start_from:]
    if args.limit > 0:
        todo = todo[:args.limit]

    log.info(f"待生成: {len(todo)} / {total}")
    if not todo:
        log.info("全部已生成，無需處理")
        return

    rotator = KeyRotator(GEMINI_KEYS)
    ok_count = 0
    err_count = 0

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

        title = Path(ai_json).stem
        prompt = build_prompt(analysis, title)
        out_path = NLM_DIR / key / "infographic.png"

        log.info(f"{label} 生成: {title[:50]}...")

        client, api_key = rotator.get_client()
        rotator.wait_if_needed(api_key)

        try:
            success = generate_infographic(client, prompt, out_path)
            if success:
                # Update progress
                if key not in completed:
                    completed[key] = {}
                completed[key]["infographic"] = True
                completed[key]["infographic_source"] = "gemini"
                completed[key]["infographic_at"] = datetime.now().isoformat(timespec='seconds')
                ok_count += 1
            else:
                log.warning(f"{label} 模型未返回圖片")
                err_count += 1
        except Exception as e:
            err_msg = str(e)[:200]
            log.error(f"{label} 錯誤: {err_msg}")
            err_count += 1
            # If rate limited, add extra delay
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                log.info("  -> 遇到限流，等待 30s")
                time.sleep(30)

        # Auto-save progress every 5 items
        if (i + 1) % 5 == 0 or i == len(todo) - 1:
            progress["completed"] = completed
            save_progress(progress)

    # Final save
    progress["completed"] = completed
    save_progress(progress)

    log.info("=" * 50)
    log.info(f"完成！成功: {ok_count}, 失敗: {err_count}")
    log.info(f"累計 infographic: {sum(1 for v in completed.values() if v.get('infographic'))}/{total}")
    log.info("=" * 50)


def run_repair(args):
    """Repair existing NLM infographics with garbled Chinese text."""
    progress = load_progress()
    completed = progress["completed"]

    # Find infographics that exist and were generated by NLM (not Gemini)
    targets = []
    for key, info in completed.items():
        if info.get("infographic") and info.get("infographic_source") != "gemini":
            ig_path = NLM_DIR / key / "infographic.png"
            if ig_path.exists():
                targets.append((key, ig_path))

    if args.limit > 0:
        targets = targets[:args.limit]

    log.info(f"待修復: {len(targets)} 張 NLM infographic")
    if not targets:
        log.info("無需修復")
        return

    rotator = KeyRotator(GEMINI_KEYS)
    ok_count = 0

    for i, (key, ig_path) in enumerate(targets):
        label = f"[{i+1}/{len(targets)}]"
        log.info(f"{label} 修復: {key}")

        # Backup original
        backup = ig_path.with_suffix(".nlm_backup.png")
        if not backup.exists():
            import shutil
            shutil.copy2(ig_path, backup)

        client, api_key = rotator.get_client()
        rotator.wait_if_needed(api_key)

        try:
            success = repair_infographic(client, ig_path, ig_path)
            if success:
                completed[key]["infographic_source"] = "gemini_repaired"
                completed[key]["infographic_at"] = datetime.now().isoformat(timespec='seconds')
                ok_count += 1
        except Exception as e:
            log.error(f"{label} 修復失敗: {str(e)[:200]}")

    progress["completed"] = completed
    save_progress(progress)
    log.info(f"修復完成: {ok_count}/{len(targets)}")


def show_status():
    files = build_file_list()
    total = len(files)
    progress = load_progress()
    completed = progress.get("completed", {})

    has_ig = sum(1 for v in completed.values() if v.get("infographic"))
    gemini_ig = sum(1 for v in completed.values() if v.get("infographic_source") in ("gemini", "gemini_repaired"))
    nlm_ig = has_ig - gemini_ig
    no_ig = total - has_ig

    log.info(f"總判決數:       {total}")
    log.info(f"有 infographic: {has_ig} ({has_ig*100//max(total,1)}%)")
    log.info(f"  - Gemini 生成: {gemini_ig}")
    log.info(f"  - NLM 生成:    {nlm_ig}")
    log.info(f"待生成:         {no_ig}")
    log.info(f"上次更新:       {progress.get('updated', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(description="Gemini API 批量生成判決 infographic")
    parser.add_argument('--test', type=int, metavar='N', help='測試模式：只生成 N 張')
    parser.add_argument('--limit', type=int, default=0, help='限制處理數量')
    parser.add_argument('--start-from', type=int, default=0, help='從第 N 個開始')
    parser.add_argument('--repair', action='store_true', help='修復現有 NLM 亂碼圖片')
    parser.add_argument('--status', action='store_true', help='查看進度')
    parser.add_argument('--model', default=None, help='模型名稱')
    args = parser.parse_args()

    if args.model:
        _set_model(args.model)

    if args.status:
        show_status()
    elif args.repair:
        run_repair(args)
    elif args.test is not None:
        args.limit = args.test
        run_generate(args)
    else:
        run_generate(args)


if __name__ == "__main__":
    main()
