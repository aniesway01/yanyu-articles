"""裁判文書網批量抓取 v2 - 透過 CDP 連接已登入的 Chrome"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import time, re, os

OUTPUT_DIR = r"C:\AntiGravityFile\YanYuInc\judgments"
CDP_URL = "http://127.0.0.1:9222"
SEARCH_URL = "https://wenshu.court.gov.cn/website/wenshu/181217BMTKHNT2W0/index.html?pageId=4e41e7d3c24e1d572acd949d84a1727b&s8=03"

# 已抓取的案號關鍵字（跳過）
EXISTING = [
    "辽13民终102", "苏民再281", "甘民申4263", "粤民申17778",
    "渝民申2048", "陕民申7769", "吉民申1046", "晋民申4296",
    "甘民申4231", "闽民申3655", "陕民申7166"
]

def is_done(text):
    for e in EXISTING:
        if e in text:
            return True
    return False

def save_raw(idx, title, content):
    safe = re.sub(r'[<>:"/\\|?*]', '_', title[:60])
    path = os.path.join(OUTPUT_DIR, f"{idx:03d}_{safe}.md")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"# {title}\n\n---\n\n{content}")
    return path

os.makedirs(OUTPUT_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0]

    # 找到 wenshu 頁面
    page = None
    for pg in ctx.pages:
        if 'wenshu' in pg.url:
            page = pg
            break
    if not page:
        page = ctx.pages[0]

    # 導航到搜索結果
    print("Navigating to search results...")
    page.goto(SEARCH_URL, timeout=30000)
    time.sleep(5)

    # 確認登入
    body = page.text_content('body') or ''
    if '13020007723' not in body:
        print("ERROR: Not logged in!")
        sys.exit(1)
    print("OK: Logged in!")

    # 確認有搜索結果
    if '15348' in body or '共检索到' in body:
        print("OK: Search results loaded!")
    else:
        print("WARNING: Search results may not have loaded")
        print(f"Body length: {len(body)}")

    idx = 12
    extracted = 0
    target = 10  # 再抓 10 個

    for page_num in range(1, 20):  # 最多翻 20 頁
        if extracted >= target:
            break

        print(f"\n--- Page {page_num} ---")
        time.sleep(3)

        # 收集案件連結的 href
        links_data = page.evaluate("""() => {
            var results = [];
            var links = document.querySelectorAll('a');
            for (var i = 0; i < links.length; i++) {
                var text = links[i].textContent || '';
                if (text.indexOf('人身保险合同纠纷') >= 0 && text.length > 20) {
                    results.push({text: text.trim(), href: links[i].href});
                }
            }
            return results;
        }""")

        print(f"Found {len(links_data)} case links")

        for ld in links_data:
            if extracted >= target:
                break
            title = ld['text']
            href = ld['href']

            if is_done(title):
                print(f"  [SKIP] {title[:50]}")
                continue

            print(f"  [GET] {title[:60]}...")

            try:
                page.goto(href, timeout=20000)
                time.sleep(4)

                full = page.text_content('body') or ''

                if len(full) < 500:
                    print(f"    [WARN] Too short ({len(full)} chars)")
                    page.go_back()
                    time.sleep(3)
                    continue

                # 清理：找正文
                start = 0
                for m in ['民 事 裁 定 书', '民 事 判 决 书', '民事裁定书', '民事判决书']:
                    i = full.find(m)
                    if 0 < i < len(full)//2:
                        start = i
                        break

                end = len(full)
                for m in ['公 告', '概要', '基本信息']:
                    i = full.find(m, len(full)//2)
                    if i > 0:
                        end = i
                        break

                content = full[start:end].strip()

                if len(content) > 300:
                    path = save_raw(idx, title[:60], content)
                    EXISTING.append(str(idx))
                    print(f"    [SAVED] #{idx} ({len(content)} chars) -> {os.path.basename(path)}")
                    idx += 1
                    extracted += 1
                else:
                    print(f"    [WARN] Content too short after cleanup ({len(content)})")

            except Exception as e:
                print(f"    [ERROR] {e}")

            # 返回列表
            try:
                page.go_back()
                time.sleep(3)
            except:
                page.goto(SEARCH_URL, timeout=20000)
                time.sleep(4)

        # 翻頁
        if extracted < target:
            try:
                clicked = page.evaluate("""() => {
                    var links = document.querySelectorAll('a');
                    for (var i = 0; i < links.length; i++) {
                        if (links[i].textContent.trim() === '下一页') {
                            links[i].click();
                            return true;
                        }
                    }
                    return false;
                }""")
                if clicked:
                    print("  >> Next page...")
                    time.sleep(4)
                else:
                    print("  >> No next page button!")
                    break
            except Exception as e:
                print(f"  >> Pagination error: {e}")
                break

    print(f"\n=== DONE! Extracted {extracted} new cases (total: {idx-1}) ===")
