#!/usr/bin/env python3
"""
批量下载微信公众号合辑文章，提取文字 + OCR 图片，输出为 .md 文件。
输出目录：合辑文章/
"""
import sys, io, os, re, json, time, hashlib, base64
from pathlib import Path
from urllib.parse import urlparse

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "合辑文章"
OUT_DIR.mkdir(exist_ok=True)
IMG_DIR = OUT_DIR / "images"
IMG_DIR.mkdir(exist_ok=True)
STATE_FILE = OUT_DIR / "_fetch_state.json"

# Gemini Flash OCR（免费额度）
sys.path.insert(0, str(Path("C:/antigravityfile/000System/little-tool")))
try:
    from _core.ai.key_loader import load_api_key
    GEMINI_KEY = load_api_key("gemini")
except Exception:
    GEMINI_KEY = None
    print("WARNING: Gemini API key not found, image OCR will be skipped")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# 全部文章 URL（4个合辑，去重后14篇）
ARTICLES = [
    # 2026年度合辑 (album_id=4256271136067158028)
    {"album": "2026年度", "title": "2026年度烟台市民健康保参保须知", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247506435&idx=1&sn=07f32b2b2af828f19bdf22f67c53b4b4&chksm=cedb372bf9acbe3d0918cbd02e1bb26be3c99c6d2707e701c8600f954bca8db41f49de1eacbe#rd"},
    {"album": "2026年度", "title": "2026年度烟台市民健康保产品说明书", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247506435&idx=2&sn=9b03a66a31b657db73e85d7375aaab7b&chksm=cedb372bf9acbe3ddb74f28006de3a7aa5a71b783781fda50460fb23423f130ff58f0f714985#rd"},
    {"album": "2026年度", "title": "2026年度烟台市民健康保理赔须知", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247506435&idx=3&sn=203bc28408d20f3571e47ada9a43838c&chksm=cedb372bf9acbe3dd979dff3c9a1912b806f2f532fbdd73531fdc5ef48db4089ce5fb0243005#rd"},
    {"album": "2026年度", "title": "2026年度烟台市民健康保健康管理服务手册", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247506435&idx=4&sn=16ecb48ba63380e5fc2ae8f575c5e4dd&chksm=cedb372bf9acbe3dc3598bda980f2e30498f9bd75d9808872a261d742f0f46d06b57ea8f3d7d#rd"},
    # 2025年度合辑 (album_id=3699359579726364674)
    {"album": "2025年度", "title": "烟台市民健康保2025产品说明书", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247505773&idx=1&sn=1ad3c0458d98d1ca38de006c4b7fc5b3&chksm=cedb3a45f9acb353a3f34e18bb30f699baf70b44677edeb253e1c3d657515d70045d8554ee13#rd"},
    {"album": "2025年度", "title": "烟台市民健康保2025参保须知", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247500589&idx=1&sn=074e9c8d656853a6751f5b72bd262f7f&chksm=cedb2e05f9aca713291483d25e8142e4f2001687ee860ac1786b2b40ff0ce010099bf980b62b#rd"},
    {"album": "2025年度", "title": "烟台市民健康保2025理赔须知", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247499172&idx=1&sn=55090604dcab987ad704eeb920140dbb&chksm=cedb108cf9ac999ada585973ae5548f92fb877f5cb3fc85b369d858d4f1c51a7f7ab78c9ebd9#rd"},
    {"album": "2025年度", "title": "烟台市民健康保2025健康管理服务手册", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247498381&idx=4&sn=973203f7bcab3a65552084d0a9668cea&chksm=cedb17a5f9ac9eb3f3386776f0b8dfb571093f8c4925da64779d14ea2a63f1b8f778b42247bf#rd"},
    # 2024年度合辑 (album_id=3163674704306765829)
    {"album": "2024年度", "title": "2024年度烟台市民健康保保障详情", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247494930&idx=1&sn=7fee9225f7754f6bf9c49d31eba7a2e5&chksm=cedb003af9ac892ced63e8d36f9f4d486451e806894f39d9b21406b7c97512a55168397b284e#rd"},
    {"album": "2024年度", "title": "2024年度烟台市民健康保理赔须知", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247492010&idx=1&sn=e0bd5b835712d8b1e6dc895a248a2339&chksm=cedb0c82f9ac85949b59897f039f23cc2eeee16e429d402289fc046be93a3a51637d4d06b890#rd"},
    # 2023年度合辑 (album_id=3347433094718685190)
    {"album": "2023年度", "title": "2023年度烟台市民健康保特药理赔教程", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247489357&idx=2&sn=3a0e17a50da021017e467e9d8388c928&chksm=ced8fa65f9af737397ed7c747d401a2ea13c99f249de7ac3167c2adfdb03744cdd5abf20d05f#rd"},
    {"album": "2023年度", "title": "2023烟台市民健康保理赔指南", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247489432&idx=1&sn=bb42977543435625ebd88238bbbb9270&chksm=ced8fab0f9af73a669349f68b846df7f06e8357fba12e846b365e17fc13a69a25ecf507f8f37#rd"},
    {"album": "2023年度", "title": "2023年度理赔须知", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247488602&idx=1&sn=4ef0ef5c9d37bef8dd7e33423db4179d&chksm=ced8f972f9af706453ed5df1cb30e869194022a3111d9188603d2b5e72ace38a9464372e9810#rd"},
    {"album": "2023年度", "title": "2023年度保障详情", "url": "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1NjA3MQ==&mid=2247488720&idx=1&sn=c552fceda2e995c72bbd3c2715f842ad&chksm=ced8f9f8f9af70eef684142153a96e091fc26045524a6f521180194f5066215001b06723301b#rd"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"done": [], "ocr_cache": {}}


def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_article(url):
    """Fetch and parse WeChat article, return (text_parts, image_urls)"""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.encoding = 'utf-8'
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Find the article content div
    content = soup.find('div', id='js_content') or soup.find('div', class_='rich_media_content')
    if not content:
        return [], []

    text_parts = []
    image_urls = []

    for elem in content.descendants:
        if elem.name == 'img':
            src = elem.get('data-src') or elem.get('src') or ''
            if src and 'mmbiz.qpic.cn' in src:
                image_urls.append(src)
        elif elem.string and elem.string.strip():
            text = elem.string.strip()
            # Skip very short fragments that are just whitespace/formatting
            if len(text) > 0:
                text_parts.append(text)

    return text_parts, image_urls


def download_image(url, save_path):
    """Download image, return local path"""
    if save_path.exists():
        return save_path
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(resp.content)
            return save_path
    except Exception as e:
        print(f"  Failed to download image: {e}")
    return None


def ocr_image_gemini(image_path):
    """Use Gemini Flash to OCR an image, return text"""
    if not GEMINI_KEY:
        return ""
    try:
        with open(image_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode('utf-8')

        suffix = image_path.suffix.lower()
        mime = {'jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                '.gif': 'image/gif', '.webp': 'image/webp'}.get(suffix, 'image/jpeg')

        payload = {
            "contents": [{
                "parts": [
                    {"text": "请提取这张图片中的所有文字内容。如果是表格，用markdown表格格式输出。如果没有文字，回复'无文字内容'。只输出提取的文字，不要加任何解释。"},
                    {"inline_data": {"mime_type": mime, "data": img_data}}
                ]
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096}
        }

        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_KEY}",
            json=payload, timeout=60
        )
        if resp.status_code == 200:
            result = resp.json()
            text = result['candidates'][0]['content']['parts'][0]['text']
            if '无文字内容' in text and len(text) < 20:
                return ""
            return text.strip()
        else:
            print(f"  Gemini OCR error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"  Gemini OCR exception: {e}")
    return ""


def article_to_md(article_info, text_parts, image_urls, ocr_texts):
    """Convert article content to markdown"""
    lines = []
    lines.append(f"# {article_info['title']}")
    lines.append("")
    lines.append(f"> 合辑: {article_info['album']}")
    lines.append(f"> 来源: [{article_info['title']}]({article_info['url']})")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Text content
    if text_parts:
        lines.append("## 文字内容")
        lines.append("")
        for t in text_parts:
            lines.append(t)
            lines.append("")

    # OCR results
    if any(ocr_texts):
        lines.append("---")
        lines.append("")
        lines.append("## 图片OCR提取内容")
        lines.append("")
        for i, ocr in enumerate(ocr_texts):
            if ocr:
                lines.append(f"### 图片 {i+1}")
                lines.append("")
                lines.append(ocr)
                lines.append("")

    return "\n".join(lines)


def safe_filename(title):
    """Create a safe filename from title"""
    # Remove special chars
    name = re.sub(r'[<>:"/\\|?*\u201c\u201d]', '', title)
    name = name.strip()
    if len(name) > 80:
        name = name[:80]
    return name


def main():
    state = load_state()
    total = len(ARTICLES)

    print(f"=== 批量下载微信合辑文章 ===")
    print(f"总计: {total} 篇, 已完成: {len(state['done'])} 篇")
    print()

    for i, art in enumerate(ARTICLES):
        url_hash = hashlib.md5(art['url'].encode()).hexdigest()[:12]
        if url_hash in state['done']:
            print(f"[{i+1}/{total}] SKIP (已完成): {art['title']}")
            continue

        print(f"[{i+1}/{total}] 下载: {art['title']}")

        # Fetch article
        try:
            text_parts, image_urls = fetch_article(art['url'])
        except Exception as e:
            print(f"  ERROR fetching: {e}")
            continue

        print(f"  文字段落: {len(text_parts)}, 图片: {len(image_urls)}")

        # Download and OCR images
        ocr_texts = []
        art_img_dir = IMG_DIR / safe_filename(art['title'])
        if image_urls:
            art_img_dir.mkdir(exist_ok=True)

        for j, img_url in enumerate(image_urls):
            img_hash = hashlib.md5(img_url.encode()).hexdigest()[:12]
            img_path = art_img_dir / f"img_{j:03d}.jpg"

            # Check OCR cache
            if img_hash in state.get('ocr_cache', {}):
                ocr_texts.append(state['ocr_cache'][img_hash])
                continue

            # Download
            local = download_image(img_url, img_path)
            if not local:
                ocr_texts.append("")
                continue

            # Check file size - skip tiny images (icons, decorations)
            if local.stat().st_size < 5000:  # < 5KB
                ocr_texts.append("")
                continue

            # OCR
            print(f"  OCR 图片 {j+1}/{len(image_urls)}...")
            ocr = ocr_image_gemini(local)
            ocr_texts.append(ocr)
            state.setdefault('ocr_cache', {})[img_hash] = ocr

            # Rate limit for Gemini
            time.sleep(2)

        # Write markdown
        md_content = article_to_md(art, text_parts, image_urls, ocr_texts)
        md_filename = f"{art['album']}_{safe_filename(art['title'])}.md"
        md_path = OUT_DIR / md_filename

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"  -> {md_filename}")

        # Update state
        state['done'].append(url_hash)
        save_state(state)

        # Polite delay between articles
        time.sleep(1)

    print()
    print(f"=== 完成! {len(state['done'])}/{total} 篇 ===")
    print(f"输出目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
