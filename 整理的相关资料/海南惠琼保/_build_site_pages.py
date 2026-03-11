#!/usr/bin/env python3
"""
把海南惠琼保的主题 Markdown 转为 HTML，输出到 site/海南惠琼保/
并生成一个 huiminbao.html 索引页。
"""
import sys, io, os, re
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import markdown

HERE = Path(__file__).resolve().parent
SITE = HERE.parents[1] / "site"
OUT  = SITE / "海南惠琼保"
OUT.mkdir(parents=True, exist_ok=True)

# 复用 build_all.py 的 CSS（读取现有首页提取）
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
.content h4{margin:15px 0 8px;font-size:15px}
.content blockquote{border-left:3px solid #1a73e8;padding-left:15px;color:#555;margin:15px 0;font-size:14px}
.content table{border-collapse:collapse;width:100%;margin:15px 0}
.content th,.content td{border:1px solid #ddd;padding:8px 12px;text-align:left}
.content th{background:#f5f5f5;font-weight:600}
.content ul,.content ol{margin:10px 0 15px 20px}
.content li{margin-bottom:6px}
.content strong{color:#1a73e8}
.content hr{border:none;border-top:1px solid #eee;margin:25px 0}
"""

TOPIC_DESCRIPTIONS = {
    "01_产品保障方案": "产品方案、免赔额、费用构成、除外责任",
    "02_理赔指南": "理赔方式、所需材料、时效、常见问题",
    "03_理赔案例集": "20+ 真实理赔案例（按保单年度分类）",
    "04_特药保障": "特药直付、2026版国内50种+国外65种共115种药品目录",
    "05_异地就医": "异地就医赔付规则、备案流程、真实案例",
    "06_参保须知_2026版": "2026版各款产品完整参保须知原文",
    "07_参保须知_2025版": "2025版各款产品完整参保须知原文",
    "08_参保须知_2024版": "2024版各款产品完整参保须知原文",
}


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
    return markdown.markdown(text, extensions=["tables", "fenced_code"])


def main():
    md_files = sorted(HERE.glob("0*.md"))
    print(f"Found {len(md_files)} topic files")

    cards = []
    for md_file in md_files:
        stem = md_file.stem
        with open(md_file, "r", encoding="utf-8") as f:
            md_text = f.read()

        # 提取标题（第一行 # 开头）
        title = stem
        m = re.match(r'^#\s+(.+)', md_text)
        if m:
            title = m.group(1)

        html_body = md2html(md_text)
        page_html = wrap_page(
            title,
            f'<article><div class="content">{html_body}</div></article>',
            back="../huiminbao.html"
        )

        out_file = OUT / f"{stem}.html"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(page_html)
        print(f"  -> {out_file.name}")

        desc = TOPIC_DESCRIPTIONS.get(stem, "")
        cards.append(f"""<div class="card"><h3><a href="海南惠琼保/{stem}.html">{esc(title)}</a></h3><p>{esc(desc)}</p></div>""")

    # 生成索引页
    body = f"""
<header>
  <h1>海南惠琼保</h1>
  <p>城市定制型商业补充医疗保险 | 产品资料整理</p>
</header>
<nav><a href="index.html">&larr; 返回首页</a></nav>
<h2 style="font-size:18px;margin-bottom:15px">主题文档（{len(md_files)} 篇）</h2>
{"".join(cards)}
"""
    idx_html = wrap_page("海南惠琼保", body)
    with open(SITE / "huiminbao.html", "w", encoding="utf-8") as f:
        f.write(idx_html)
    print(f"  -> huiminbao.html (index)")
    print("Done!")


if __name__ == "__main__":
    main()
