#!/usr/bin/env python3
"""
惠琼保 — 按产品×年度拆分为独立完整文件。
每个产品方案（A款/A款升级版/B款/B款升级版/惠学保A/B/C）× 年度 = 1个文件。
"""
import sys, io, os, re
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = Path(__file__).resolve().parent
OUT = HERE / "各产品参保须知"
OUT.mkdir(exist_ok=True)

# Map: directory name pattern → output filename
PRODUCT_MAP = [
    # 2026
    ('2026版A款升级版参保须知', '2026_A款升级版'),
    ('2026版A款参保须知', '2026_A款'),
    ('2026版B款升级版参保须知', '2026_B款升级版'),
    ('2026版B款参保须知', '2026_B款'),
    # 2025
    ('2025"惠琼保"A款升级版参保须知', '2025_A款升级版'),
    ('2025"惠琼保"A款参保须知', '2025_A款'),
    ('2025"惠琼保"B款升级版参保须知', '2025_B款升级版'),
    ('2025"惠琼保"B款参保须知', '2025_B款'),
    # 2024
    ('2024"惠琼保A款（升级版）"参保须知', '2024_A款升级版'),
    ('2024"惠琼保A款"参保须知', '2024_A款'),
    ('2024"惠琼保B款（升级版）"参保须知', '2024_B款升级版'),
    ('2024"惠琼保B款"参保须知', '2024_B款'),
    # 惠学保
    ('惠学保A款', '2026_惠学保A款'),
    ('惠学保B款', '2026_惠学保B款'),
    ('惠学保C款', '2026_惠学保C款'),
]


def find_article(pattern):
    """Find article directory matching pattern"""
    base = HERE / '手动补充文章'
    for d in os.listdir(base):
        if pattern in d:
            txt = base / d / 'article.txt'
            if txt.exists():
                return d, txt
    return None, None


def extract_url(content):
    for line in content.split('\n')[:5]:
        m = re.search(r'https?://[^\s]+', line)
        if m:
            return m.group(0)
    return ''


def clean_body(content):
    """Extract body after separator, clean up"""
    sep = '=' * 20
    body = content.split(sep, 1)[1].strip() if sep in content else content
    # Remove lines after first 5
    lines = body.split('\n')
    out = []
    for line in lines:
        s = line.strip()
        if any(k in s for k in ['点击下图', '立即参保', '点击"阅读原文"',
                                  '置顶公众号', '👇', '👆']):
            continue
        out.append(line)
    return '\n'.join(out).strip()


def format_须知(text):
    """Add Markdown structure to raw policy text"""
    lines = text.split('\n')
    out = []
    for line in lines:
        s = line.strip()
        if not s:
            out.append('')
            continue
        if s.startswith('#') or s.startswith('>'):
            out.append(line)
            continue
        # 「一、xxx」→ ##
        if re.match(r'^[一二三四五六七八九十]+、', s):
            out.append(f'\n## {s}\n')
            continue
        if re.match(r'^\d+[、.]\s*【', s) or re.match(r'^\d+[、.]\s*保障责任', s):
            out.append(f'\n### {s}\n')
            continue
        if re.match(r'^保障责任[一二三四五六七八九十]', s):
            out.append(f'\n### {s}\n')
            continue
        if re.match(r'^关于.{2,20}(的约定|的重要提示|的说明)', s):
            out.append(f'\n### {s}\n')
            continue
        if s.startswith('●'):
            out.append(f'- {s[1:].strip()}')
            continue
        if s.startswith('Ø'):
            out.append(f'  - {s[1:].strip()}')
            continue
        m = re.match(r'^[（(](\d+)[）)](.+)', s)
        if m:
            out.append(f'\n**（{m.group(1)}）**{m.group(2)}')
            continue
        m = re.match(r'^([①②③④⑤⑥⑦⑧⑨⑩])(.+)', s)
        if m:
            out.append(f'**{m.group(1)}** {m.group(2)}')
            continue
        if len(s) > 80:
            if out and out[-1].strip() != '':
                out.append('')
            out.append(s)
            out.append('')
            continue
        out.append(line)
    result = '\n'.join(out)
    result = re.sub(r'\n{4,}', '\n\n\n', result)
    return result


def main():
    count = 0
    for pattern, name in PRODUCT_MAP:
        dirname, txt_path = find_article(pattern)
        if not txt_path:
            print(f'[SKIP] {pattern} — not found')
            continue

        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        url = extract_url(content)
        body = clean_body(content)
        body = format_须知(body)

        # Build output file
        year = name.split('_')[0]
        product = name.split('_', 1)[1]
        title = f'海南惠琼保 {year}版 {product} — 参保须知（完整版）'

        md = f'# {title}\n\n'
        md += f'> 来源: [{dirname}]({url})\n\n'
        md += body

        out_path = OUT / f'{name}_参保须知.md'
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(md)
        print(f'Written: {name}_参保须知.md ({len(md)//1024} KB)')
        count += 1

    print(f'\nDone! {count} files created in 各产品参保须知/')


if __name__ == '__main__':
    main()
