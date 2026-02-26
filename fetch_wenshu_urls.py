"""裁判文書網批量獲取 docId/URL — 透過 CDP 連接已登入的 Chrome
Usage:
    python fetch_wenshu_urls.py --limit 3 --source featured
    python fetch_wenshu_urls.py --source all
    python fetch_wenshu_urls.py --source annual --start-from 100
"""
import sys, io, os, json, re, time, argparse, random
from datetime import datetime

# ── Windows UTF-8 ──────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

# ── 路徑常量 ───────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
JUDGE_DIR  = os.path.join(BASE_DIR, "judgments")
INDEX_FILE = os.path.join(JUDGE_DIR, "cases", "_index.json")
OUT_FILE   = os.path.join(JUDGE_DIR, "_wenshu_urls.json")
ERR_FILE   = os.path.join(JUDGE_DIR, "_wenshu_urls_errors.json")

CDP_URL    = "http://127.0.0.1:9222"
HOMEPAGE   = "https://wenshu.court.gov.cn/"
WENSHU_BASE = "https://wenshu.court.gov.cn/website/wenshu/181107ANFZ0BXSK4/index.html"

# ── 11 個精選判決案號（judgments/ 根目錄 001-011） ─────────────
FEATURED_CASES = [
    "(2026)辽13民终102号",
    "(2025)苏民再281号",
    "(2025)甘民申4263号",
    "(2024)粤民申17778号",
    "(2025)渝民申2048号",
    "(2024)陕民申7769号",
    "(2025)吉民申1046号",
    "(2024)晋民申4296号",
    "(2024)甘民申4231号",
    "(2024)闽民申3655号",
    "(2024)陕民申7166号",
]


def extract_case_number(raw: str) -> str:
    """
    從完整 case_no 提取括號內核心案號。
    例: '江苏省扬州市中级人民法院（2016）苏10民终字第2629号民事判决书'
      -> '(2016)苏10民终字第2629号'
    支援全形括號和半形括號。
    """
    m = re.search(r'[（(]\d{4}[）)][^号號]*[号號]', raw)
    if m:
        s = m.group(0)
        s = s.replace('（', '(').replace('）', ')').replace('號', '号')
        return s
    return re.sub(r'\s*\|.*$', '', raw).strip()


def load_progress() -> dict:
    """讀取已保存的進度檔。"""
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"updated": "", "urls": {}, "errors": {}}


def save_progress(data: dict):
    """寫入進度檔。"""
    data["updated"] = datetime.now().isoformat(timespec='seconds')
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_errors(errors: dict):
    """寫入錯誤檔。"""
    with open(ERR_FILE, 'w', encoding='utf-8') as f:
        json.dump({"updated": datetime.now().isoformat(timespec='seconds'),
                    "errors": errors}, f, ensure_ascii=False, indent=2)


def build_case_list(source: str) -> list:
    """
    依 source 參數建立待處理案號清單。
    - featured: 11 個精選
    - annual:   _index.json 中 606 個年度案例
    - all:      featured + annual（去重）
    """
    cases = []

    if source in ("featured", "all"):
        cases.extend(FEATURED_CASES)

    if source in ("annual", "all"):
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            idx = json.load(f)
        for c in idx.get("cases", []):
            raw = c.get("case_no", "")
            cn = extract_case_number(raw)
            if cn and cn not in cases:
                cases.append(cn)

    return cases


def random_delay(lo=5.0, hi=10.0):
    """隨機延遲，模擬人類操作。"""
    time.sleep(random.uniform(lo, hi))


def normalize_case_no(raw: str) -> str:
    """將舊格式案號轉為可搜索格式，去掉 '字第'。"""
    # (2016)苏10民终字第2629号 -> (2016)苏10民终2629号
    return re.sub(r'字第', '', raw)


def human_like_delay(lo=1.0, hi=3.0):
    """短延遲，模擬人類操作節奏。"""
    time.sleep(random.uniform(lo, hi))


def ensure_homepage(page):
    """確保在首頁，只在必要時導航。"""
    current = page.url or ""
    if 'wenshu.court.gov.cn' in current and '/181107ANFZ0BXSK4/' not in current:
        # 已在首頁或非結果頁，不需要重新導航
        sb = page.query_selector('input.search-inp')
        if sb:
            return
    # 需要回首頁
    page.goto(HOMEPAGE, timeout=30000)
    time.sleep(random.uniform(3, 5))


def search_and_extract(page, case_no: str, retry=0):
    """
    在裁判文書網首頁搜索一個案號，提取第一個結果的 URL / docId / 標題。
    回傳 dict 或 None（表示找不到）。最多重試 2 次。
    改良版：減少不必要的頁面導航，加入人類行為模擬。
    """
    search_term = normalize_case_no(case_no)

    try:
        # ── 1. 確保在首頁（避免每次都 goto） ──
        ensure_homepage(page)

        # ── 2. 模擬人類：輕微滾動 ──
        page.evaluate("window.scrollTo(0, Math.random() * 100)")
        human_like_delay(0.5, 1.5)

        # ── 3. 找搜索框 ──
        sb = page.query_selector('input.search-inp')
        if not sb:
            sb = page.query_selector('input[placeholder*="案由"]')
        if not sb:
            sb = page.query_selector('input[placeholder*="关键词"]')
        if not sb:
            raise RuntimeError("找不到搜索框")

        # ── 4. 清空 + 輸入（模擬人類打字） ──
        sb.click()
        human_like_delay(0.3, 0.8)
        # 三擊全選再刪除，比 fill("") 更像人類
        sb.click(click_count=3)
        human_like_delay(0.2, 0.4)
        sb.press("Backspace")
        human_like_delay(0.3, 0.6)
        sb.type(search_term, delay=random.randint(60, 120))
        human_like_delay(0.5, 1.0)

        # ── 5. Enter 觸發搜索 + 等待導航 ──
        try:
            with page.expect_navigation(timeout=20000):
                sb.press("Enter")
        except Exception:
            try:
                page.click('div.search-rightBtn', timeout=5000)
                time.sleep(8)
            except Exception:
                pass

        time.sleep(random.uniform(4, 7))

        # ── 6. 提取第一個 docId 結果 ──
        result = page.evaluate("""() => {
            var links = document.querySelectorAll('a[href*="docId"]');
            if (links.length > 0) {
                return { url: links[0].href, title: links[0].textContent.trim() };
            }
            var allLinks = document.querySelectorAll('a');
            for (var i = 0; i < allLinks.length; i++) {
                var h = allLinks[i].href || '';
                var t = allLinks[i].textContent.trim();
                if (h.indexOf('181107ANFZ0BXSK4') > -1 && t.length > 10) {
                    return { url: h, title: t };
                }
            }
            return null;
        }""")

    except Exception as e:
        if retry < 2:
            print(f"         [RETRY {retry+1}] {str(e)[:60]}...", flush=True)
            time.sleep(random.uniform(15, 25))
            # 重試前強制回首頁
            try:
                page.goto(HOMEPAGE, timeout=30000)
                time.sleep(random.uniform(5, 8))
            except Exception:
                pass
            return search_and_extract(page, case_no, retry=retry+1)
        raise

    if not result:
        return None

    # 將相對路徑轉為完整 URL
    url = result['url']
    if url.startswith('..'):
        url = WENSHU_BASE + '?' + url.split('?', 1)[1] if '?' in url else url

    # 提取 docId
    doc_id = ""
    m = re.search(r'docId=([A-Za-z0-9/+=]+)', url)
    if m:
        doc_id = m.group(1)

    return {
        "wenshu_url": url,
        "doc_id": doc_id,
        "title": result['title'],
        "fetched_at": datetime.now().isoformat(timespec='seconds'),
    }


def main():
    parser = argparse.ArgumentParser(description="裁判文書網批量獲取 docId/URL")
    parser.add_argument('--limit', type=int, default=0,
                        help='只處理前 N 個（測試用），0=不限')
    parser.add_argument('--start-from', type=int, default=0,
                        help='從第 N 個開始（0-indexed）')
    parser.add_argument('--source', choices=['featured', 'annual', 'all'],
                        default='all', help='處理哪些案例 (featured|annual|all)')
    args = parser.parse_args()

    # ── 建立案號清單 ──
    cases = build_case_list(args.source)
    total_all = len(cases)
    print(f"[INFO] 來源={args.source}，共 {total_all} 個案號")

    # ── 截取範圍 ──
    cases = cases[args.start_from:]
    if args.limit > 0:
        cases = cases[:args.limit]
    print(f"[INFO] 本次處理 {len(cases)} 個（start={args.start_from}, limit={args.limit}）")

    if not cases:
        print("[WARN] 沒有待處理案號，結束。")
        return

    # ── 讀取已有進度 ──
    progress = load_progress()
    existing_urls = progress.get("urls", {})
    existing_errors = progress.get("errors", {})
    skip_count = 0

    # ── 連接 Chrome ──
    with sync_playwright() as p:
        print(f"[INFO] 連接 Chrome CDP: {CDP_URL}")
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]

        # 找到或建立工作頁面
        page = None
        for pg in ctx.pages:
            if 'wenshu' in pg.url:
                page = pg
                break
        if not page:
            page = ctx.new_page()

        ok_count = 0
        err_count = 0

        for i, case_no in enumerate(cases):
            global_idx = args.start_from + i
            label = f"[{global_idx+1}/{total_all}]"

            # 跳過已有
            if case_no in existing_urls:
                skip_count += 1
                print(f"  {label} [SKIP] {case_no} （已有結果）", flush=True)
                continue
            # 之前失敗的案號不跳過，重試
            if case_no in existing_errors:
                del existing_errors[case_no]

            print(f"  {label} 搜索: {case_no} ...", flush=True)

            try:
                result = search_and_extract(page, case_no)
                if result:
                    existing_urls[case_no] = result
                    ok_count += 1
                    print(f"         -> OK: {result['title'][:50]}  docId={result['doc_id'][:20]}", flush=True)
                else:
                    existing_errors[case_no] = "no results found"
                    err_count += 1
                    print(f"         -> 未找到結果", flush=True)
            except Exception as e:
                msg = str(e)[:200]
                existing_errors[case_no] = msg
                err_count += 1
                print(f"         -> ERROR: {msg}", flush=True)

            # 每次成功都保存（防止進度丟失）
            if ok_count > 0 and ok_count % 5 == 0:
                progress["urls"] = existing_urls
                progress["errors"] = existing_errors
                save_progress(progress)
                save_errors(existing_errors)
                print(f"  [AUTO-SAVE] 已保存進度 (ok={ok_count}, err={err_count})", flush=True)

            # 隨機延遲（更長，降低觸發反爬風險）
            random_delay(6.0, 12.0)

    # ── 最終保存 ──
    progress["urls"] = existing_urls
    progress["errors"] = existing_errors
    save_progress(progress)
    if existing_errors:
        save_errors(existing_errors)

    # ── 統計 ──
    print("\n" + "=" * 60)
    print(f"  完成！")
    print(f"  本次成功:  {ok_count}")
    print(f"  本次失敗:  {err_count}")
    print(f"  跳過已有:  {skip_count}")
    print(f"  累計 URL:  {len(existing_urls)}")
    print(f"  累計錯誤:  {len(existing_errors)}")
    print(f"  輸出檔案:  {OUT_FILE}")
    if existing_errors:
        print(f"  錯誤檔案:  {ERR_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
