#!/usr/bin/env python3
"""
烟台市民健康保 — 把主题 Markdown 转为 HTML，输出到 site/山东烟台/
支持：文字内容在前 + 可展开的原文图片区。
"""
import sys, io, os, re, shutil, json
from pathlib import Path
from urllib.parse import quote

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import markdown

HERE = Path(__file__).resolve().parent
SITE = HERE.parents[1] / "site"
OUT  = SITE / "山东烟台"
IMG_OUT = OUT / "images"
OUT.mkdir(parents=True, exist_ok=True)
IMG_OUT.mkdir(parents=True, exist_ok=True)

# 外部圖床：GitHub raw URL
IMG_CDN_BASE = "https://raw.githubusercontent.com/aniesway01/yanyu-images/main/"

# OCR 結果快取
OCR_CACHE_FILE = HERE / '_ocr_results.json'

def load_ocr_cache():
    if OCR_CACHE_FILE.exists():
        with open(OCR_CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f5f5;color:#333;line-height:1.6}
.ctn{max-width:960px;margin:0 auto;padding:20px}
a{color:#1a73e8;text-decoration:none}a:hover{text-decoration:underline}
header{background:#1a73e8;color:#fff;padding:40px 20px;text-align:center;margin-bottom:30px;border-radius:8px}
header h1{font-size:28px;margin-bottom:8px}header p{opacity:.9;font-size:14px}
nav{margin-bottom:20px}nav a{font-size:14px}
footer{text-align:center;padding:30px;color:#999;font-size:13px}
.card{background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.1);margin-bottom:12px;transition:transform .2s}
.card:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.1)}
.card h3{font-size:17px;margin-bottom:8px}.card h3 a{color:#1a73e8}
.card p{font-size:14px;color:#666}
article{background:#fff;border-radius:8px;padding:30px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
article h1{font-size:24px;margin-bottom:15px;line-height:1.4}
.content{font-size:16px;line-height:1.8}
.content p{margin-bottom:15px}
.content h2{margin:30px 0 12px;font-size:20px;border-bottom:2px solid #1a73e8;padding-bottom:6px}
.content h3{margin:20px 0 10px;font-size:17px}
.content h4{margin:18px 0 8px;font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;padding-left:10px}
.content blockquote{border-left:3px solid #1a73e8;padding-left:15px;color:#555;margin:15px 0;font-size:14px}
.content table{border-collapse:collapse;width:100%;margin:15px 0}
.content th,.content td{border:1px solid #ddd;padding:8px 12px;text-align:left}
.content th{background:#f5f5f5;font-weight:600}
.content ul,.content ol{margin:10px 0 15px 20px}
.content li{margin-bottom:6px}
.content strong{color:#1a73e8}
.content hr{border:none;border-top:1px solid #eee;margin:20px 0}
details{margin:15px 0;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden}
details summary{padding:12px 16px;background:#f8f9fa;cursor:pointer;font-weight:600;font-size:14px;color:#1a73e8;user-select:none}
details summary:hover{background:#e8f0fe}
details[open] summary{border-bottom:1px solid #e0e0e0}
.img-gallery{padding:16px;display:flex;flex-direction:column;gap:12px;align-items:center}
.img-gallery img{max-width:100%;height:auto;border-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,.1)}
"""

TOPIC_DESCRIPTIONS = {
    "01_产品保障方案": "2025/2026版保费139元、四项责任、起付线、15项健管服务",
    "02_理赔指南": "理赔方式、所需材料、一站式结算（按年度分版）",
    "03_理赔案例集": "真实理赔案例（按2023/2024/2025保单年度分类）",
    "04_特药保障": "特药直付、2025版特药目录调整、增值服务",
    "05_异地就医": "异地备案流程、报销比例、转诊规则",
    "06_参保须知": "参保条件、缴费方式、集中缴费期、常见问题",
    "07_医保政策解读": "居民医保缴费标准、长护险、门诊慢特病（按年度分版）",
}

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
MIN_IMG_SIZE = 20 * 1024  # 20KB


def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")


def enhance_typography(html):
    """增强排版：加粗金额/产品名/人名；标签转小标题；修复跨行金额"""

    # 0. 预处理：合并跨 <br> 的金额（如 "318765.06\n元" → "318765.06元"）
    html = re.sub(
        r'(\d{1,3}(?:,?\d{3})*(?:\.\d+)?)\s*<br\s*/?>\s*\n?\s*(多万|余万|万余|万多|万|多元|余元|元)',
        r'\1\2', html)
    # "报销了\n199639.58\n元" 形式
    html = re.sub(
        r'(报销了?|理赔了?|产生|承担|自付|花了|花费|共计)\s*<br\s*/?>\s*\n?\s*(\d[\d,.]*)\s*<br\s*/?>\s*\n?\s*(多万|余万|万余|万多|万|多元|余元|元)',
        r'\1<strong>\2\3</strong>', html)

    # 1. 金额加粗
    html = re.sub(
        r'(?<!<strong>)(?<!">)(\d{1,3}(?:,?\d{3})*(?:\.\d+)?\s*(?:多万|余万|万余|万多|万|余)?(?:多元|余元|元|块钱))',
        r'<strong>\1</strong>', html)
    # "近/超/共计 XX万元" 形式
    html = re.sub(
        r'(?<!<strong>)((?:近|超|约|共计|累计|赔付|获赔|报销了?|理赔了?|减轻了?)\s*\d[\d,.]*\s*(?:多万|余万|万余|万多|万|多元|余元|元|块钱))',
        r'<strong>\1</strong>', html)
    # "XX%" 报销比例
    html = re.sub(
        r'(?<!<strong>)((?:报销比例|比例|减负|降低)\s*(?:为|达|约|近)?\s*\d+(?:\.\d+)?%)',
        r'<strong>\1</strong>', html)

    # 2. 产品名加粗
    html = re.sub(
        r'(?<!<strong>)(["\u201c]?烟台市民健康保["\u201d]?)',
        r'<strong>\1</strong>', html)

    # 3. 关键标签转 <h4>
    label_keywords = [
        '案例追踪', '理赔详情', '理赔心声', '温馨提示', '温馨提醒',
        '小保说', '小保提醒', '理赔结果', '案例回顾', '真实案例',
        '保障详情', '投保建议', '参保提醒', '特别提醒', '重要提醒',
    ]
    for kw in label_keywords:
        # 替换 <br> 包围的标签文字，同时清理前后 <br>
        html = re.sub(
            rf'(?:<br\s*/?>)?\s*{re.escape(kw)}\s*(?:<br\s*/?>)',
            rf'<h4>{kw}</h4>', html)
        html = re.sub(
            rf'<p>\s*{re.escape(kw)}\s*</p>',
            rf'<h4>{kw}</h4>', html)

    # 4. 人物信息加粗（通用匹配：X女士/先生，XX岁）
    SURNAMES = '赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓'
    html = re.sub(
        rf'(?<!<strong>)([{SURNAMES}][女男]士[，,]\s*\d{{1,3}}岁)',
        r'<strong>\1</strong>', html)

    # 5. 清理嵌套 <strong>
    for _ in range(3):
        html = re.sub(r'<strong>([^<]*)<strong>', r'<strong>\1', html)
        html = re.sub(r'</strong>([^<]*)</strong>', r'\1</strong>', html)
    # 空 strong
    html = re.sub(r'<strong>\s*</strong>', '', html)

    return html


def wrap_page(title, body, back=None):
    nav = f'<nav><a href="{back}">&larr; 返回</a></nav>' if back else ''
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{esc(title)} - YanYu 知识库</title>
<style>{CSS}</style></head><body><div class="ctn">
{nav}{body}
<footer><p><a href="https://github.com/aniesway01/yanyu-articles">GitHub Repo</a> | YanYu 知识库</p></footer>
</div></body></html>"""


def md2html(text):
    return markdown.markdown(text, extensions=["tables", "fenced_code", "nl2br"])


def load_article_index():
    """Build an index: article title -> article dir path + images"""
    index = {}
    for sub in ['手动补充文章', '用户补充文章']:
        subpath = HERE / sub
        if not subpath.exists():
            continue
        for d in os.listdir(subpath):
            dp = subpath / d
            txt = dp / 'article.txt'
            if not txt.exists():
                continue
            with open(txt, 'r', encoding='utf-8') as f:
                content = f.read()
            title = d
            for line in content.split('\n')[:6]:
                if line.startswith('标题:'):
                    title = line.split(':', 1)[1].strip()
            img_dir = dp / 'images'
            image_files = []
            if img_dir.exists():
                image_files = sorted([
                    f for f in os.listdir(img_dir)
                    if Path(f).suffix.lower() in IMAGE_EXTS
                    and (img_dir / f).stat().st_size >= MIN_IMG_SIZE
                ])
            index[title] = {
                'dir': d, 'path': dp, 'img_dir': img_dir,
                'image_files': image_files,
            }
    return index


def get_image_urls(article_info, topic_stem):
    """Return list of (cdn_url, local_rel_path) for article images"""
    if not article_info['image_files']:
        return []
    dir_slug = re.sub(r'[^\w]', '_', article_info['dir'][:40])
    results = []
    for img_name in article_info['image_files']:
        # GitHub raw URL (URL-encoded for Chinese chars)
        raw_path = f'山东烟台/{topic_stem}/{dir_slug}/{img_name}'
        cdn_url = IMG_CDN_BASE + quote(raw_path)
        local_rel = f'images/{topic_stem}/{dir_slug}/{img_name}'
        results.append((cdn_url, local_rel))
    return results


def inject_image_details(html_body, md_text, article_index, topic_stem, ocr_cache):
    """After each <h2> section, inject OCR text + collapsible image gallery"""
    h2_pattern = re.compile(r'^##\s+(.+)$', re.MULTILINE)
    h2_titles = h2_pattern.findall(md_text)

    for h2_title in h2_titles:
        matched = None
        for title, info in article_index.items():
            if title == h2_title or h2_title in title or title in h2_title:
                if info['image_files']:
                    matched = info
                    break
        if not matched:
            continue

        img_data = get_image_urls(matched, topic_stem)
        if not img_data:
            continue

        # OCR text section (from cache)
        dir_slug = re.sub(r'[^\w]', '_', matched['dir'][:40])
        ocr_parts = []
        for cdn_url, local_rel in img_data:
            ocr_key = f'{topic_stem}/{dir_slug}/{local_rel.split("/")[-1]}'
            ocr_text = ocr_cache.get(ocr_key, '')
            if ocr_text and len(ocr_text.strip()) > 20:
                ocr_parts.append(ocr_text.strip())

        ocr_html = ''
        if ocr_parts:
            ocr_content = '\n'.join(f'<p>{esc(p)}</p>' for p in ocr_parts)
            ocr_html = f"""<details>
<summary>图片文字内容（OCR 提取）</summary>
<div style="padding:16px;font-size:14px;color:#555;line-height:1.8">
{ocr_content}
</div>
</details>"""

        # Image gallery (lazy-loaded from CDN)
        img_tags = '\n'.join(
            f'<img src="{cdn_url}" alt="原文图片" loading="lazy">'
            for cdn_url, _ in img_data
        )
        gallery_html = f"""<details>
<summary>查看原文图片（{len(img_data)} 张）</summary>
<div class="img-gallery">
{img_tags}
</div>
</details>"""

        combined = ocr_html + '\n' + gallery_html

        esc_title = re.escape(esc(h2_title))
        h2_html_pattern = re.compile(
            rf'(<h2>{esc_title}</h2>)(.*?)(?=<h2>|$)',
            re.DOTALL
        )
        match = h2_html_pattern.search(html_body)
        if match:
            section_end = match.end()
            html_body = html_body[:section_end] + '\n' + combined + '\n' + html_body[section_end:]

    return html_body


def main():
    article_index = load_article_index()
    print(f"Article index: {len(article_index)} articles")
    ocr_cache = load_ocr_cache()
    print(f"OCR cache: {len(ocr_cache)} entries")

    md_files = sorted(HERE.glob("0*.md"))
    print(f"Found {len(md_files)} topic files")

    img_count_total = 0
    cards = []
    for md_file in md_files:
        stem = md_file.stem
        with open(md_file, "r", encoding="utf-8") as f:
            md_text = f.read()
        title = stem
        m = re.match(r'^#\s+(.+)', md_text)
        if m:
            title = m.group(1)

        # 修复微信文章中 0 和 1 等孤立换行的编号标号
        md_text = re.sub(r'(?m)^0\n(\d+)$', r'\1.', md_text)

        html_body = md2html(md_text)
        # 排版增强：加粗金额/产品名/人名，标签转小标题
        html_body = enhance_typography(html_body)
        # Inject OCR text + collapsible image galleries (CDN URLs)
        html_body = inject_image_details(html_body, md_text, article_index, stem, ocr_cache)

        page_html = wrap_page(title,
            f'<article><div class="content">{html_body}</div></article>',
            back="../yantai.html")
        out_file = OUT / f"{stem}.html"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(page_html)

        # Count images copied for this topic
        topic_img_dir = IMG_OUT / stem
        n_imgs = 0
        if topic_img_dir.exists():
            for root, dirs, files in os.walk(topic_img_dir):
                n_imgs += len(files)
        img_count_total += n_imgs
        print(f"  -> {out_file.name} ({n_imgs} images)")
        desc = TOPIC_DESCRIPTIONS.get(stem, "")
        cards.append(f"""<div class="card"><h3><a href="山东烟台/{stem}.html">{esc(title)}</a></h3><p>{esc(desc)}</p></div>""")

    body = f"""
<header>
  <h1>烟台市民健康保</h1>
  <p>城市定制型商业补充医疗保险 | 山东烟台</p>
</header>
<nav><a href="index.html">&larr; 返回首页</a></nav>
<h2 style="font-size:18px;margin-bottom:15px">主题文档（{len(md_files)} 篇）</h2>
{"".join(cards)}
"""
    idx_html = wrap_page("烟台市民健康保", body)
    with open(SITE / "yantai.html", "w", encoding="utf-8") as f:
        f.write(idx_html)
    print(f"  -> yantai.html (index)")
    print(f"Done! {img_count_total} images copied total.")


if __name__ == "__main__":
    main()

