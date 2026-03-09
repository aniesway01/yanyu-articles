#!/usr/bin/env python3
"""
烟台市民健康保 — 把主题 Markdown 转为 HTML，输出到 site/山东烟台/
支持：文字内容在前 + 可展开的原文图片区。
"""
import sys, io, os, re, shutil, json
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import markdown

HERE = Path(__file__).resolve().parent
SITE = HERE.parents[1] / "site"
OUT  = SITE / "山东烟台"
IMG_OUT = OUT / "images"
OUT.mkdir(parents=True, exist_ok=True)
IMG_OUT.mkdir(parents=True, exist_ok=True)

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
    "01_产品保障方案": "产品方案、免赔额、费用构成、报销比例",
    "02_理赔指南": "理赔方式、所需材料、一站式结算",
    "03_理赔案例集": "真实理赔案例与赔付数据",
    "04_特药保障": "特药目录、直赔服务、用药指南",
    "05_异地就医": "异地备案、转诊流程、赔付规则",
    "06_参保须知": "参保条件、投保流程、注意事项",
    "07_医保政策解读": "基本医保政策、门诊住院报销规则",
}

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
MIN_IMG_SIZE = 20 * 1024  # 20KB


def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")


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


def copy_images_for_article(article_info, topic_stem):
    """Copy article images to site output, return list of relative paths"""
    if not article_info['image_files']:
        return []
    dir_slug = re.sub(r'[^\w]', '_', article_info['dir'][:40])
    dest_dir = IMG_OUT / topic_stem / dir_slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for img_name in article_info['image_files']:
        src = article_info['img_dir'] / img_name
        dst = dest_dir / img_name
        if not dst.exists():
            shutil.copy2(src, dst)
        # Relative path from the topic HTML file (in 山东烟台/)
        rel = f'images/{topic_stem}/{dir_slug}/{img_name}'
        paths.append(rel)
    return paths


def inject_image_details(html_body, md_text, article_index, topic_stem):
    """After each <h2> section, inject collapsible image gallery if available"""
    # Extract h2 titles from markdown to match with article index
    h2_pattern = re.compile(r'^##\s+(.+)$', re.MULTILINE)
    h2_titles = h2_pattern.findall(md_text)

    for h2_title in h2_titles:
        # Find matching article in index
        matched = None
        for title, info in article_index.items():
            if title == h2_title or h2_title in title or title in h2_title:
                if info['image_files']:
                    matched = info
                    break
        if not matched:
            continue

        # Copy images and get relative paths
        img_paths = copy_images_for_article(matched, topic_stem)
        if not img_paths:
            continue

        # Build the <details> HTML
        img_tags = '\n'.join(
            f'<img src="{p}" alt="原文图片" loading="lazy">'
            for p in img_paths
        )
        details_html = f"""<details>
<summary>查看原文图片（{len(img_paths)} 张）</summary>
<div class="img-gallery">
{img_tags}
</div>
</details>"""

        # Find the h2 in HTML and insert details before the NEXT h2 or at end
        esc_title = re.escape(esc(h2_title))
        # Look for this h2's closing section (before next h2 or end)
        h2_html_pattern = re.compile(
            rf'(<h2>{esc_title}</h2>)(.*?)(?=<h2>|$)',
            re.DOTALL
        )
        match = h2_html_pattern.search(html_body)
        if match:
            section_end = match.end()
            html_body = html_body[:section_end] + '\n' + details_html + '\n' + html_body[section_end:]

    return html_body


def main():
    article_index = load_article_index()
    print(f"Article index: {len(article_index)} articles")

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
        # Inject collapsible image galleries
        html_body = inject_image_details(html_body, md_text, article_index, stem)

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

