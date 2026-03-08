#!/usr/bin/env python3
"""
对 05/06 参保须知 Markdown 文件做排版美化：
- 「一、」「二、」等变 ## 标题
- 「保障责任一：」等变 ### 标题
- 「● 」变列表项
- 「（1）」「①」等编号加粗
- 长段落间加空行
- 「关于...的约定」「关于...的重要提示」变 ### 标题
"""
import sys, io, re
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = Path(__file__).resolve().parent


def format_须知(text):
    lines = text.split('\n')
    out = []
    for line in lines:
        stripped = line.strip()

        # 已经是 Markdown 标题/blockquote/空行 → 不动
        if stripped.startswith('#') or stripped.startswith('>') or stripped == '':
            out.append(line)
            continue

        # 「一、xxx」→ ## 一、xxx
        if re.match(r'^[一二三四五六七八九十]+、', stripped):
            out.append('')
            out.append(f'## {stripped}')
            out.append('')
            continue

        # 「保障责任一：xxx」「保障责任二：xxx」→ ###
        if re.match(r'^保障责任[一二三四五六七八九十]', stripped):
            out.append('')
            out.append(f'### {stripped}')
            out.append('')
            continue

        # 「关于xxx的约定」「关于xxx的重要提示」→ ###
        if re.match(r'^关于.{2,20}(的约定|的重要提示|的说明)', stripped):
            out.append('')
            out.append(f'### {stripped}')
            out.append('')
            continue

        # 「●」→ 列表项
        if stripped.startswith('●'):
            content = stripped[1:].strip()
            out.append(f'- {content}')
            continue

        # 「Ø」→ 子列表项
        if stripped.startswith('Ø'):
            content = stripped[1:].strip()
            out.append(f'  - {content}')
            continue

        # 「（1）」「（2）」等编号 → 加粗编号
        m = re.match(r'^[（(](\d+)[）)](.+)', stripped)
        if m:
            out.append('')
            out.append(f'**（{m.group(1)}）**{m.group(2)}')
            continue

        # 「① ② ③」等 → 加粗
        m = re.match(r'^([①②③④⑤⑥⑦⑧⑨⑩])(.+)', stripped)
        if m:
            out.append(f'**{m.group(1)}** {m.group(2)}')
            continue

        # 「1. 」「2. 」数字编号开头 → 确保前面有空行
        if re.match(r'^\d+[.、]\s', stripped):
            if out and out[-1].strip() != '':
                out.append('')
            out.append(stripped)
            continue

        # 长段落（>80字）前后加空行确保分段
        if len(stripped) > 80:
            if out and out[-1].strip() != '':
                out.append('')
            out.append(stripped)
            out.append('')
            continue

        # 其他行直接输出
        out.append(line)

    return '\n'.join(out)


def process_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    # 分离头部（# 标题 + > blockquote）和正文
    formatted = format_须知(text)

    # 清理多余空行（3个以上连续空行变2个）
    formatted = re.sub(r'\n{4,}', '\n\n\n', formatted)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(formatted)

    print(f"Formatted: {path.name}")


def main():
    for name in ['05_参保须知_2026版.md', '06_历史参保须知.md']:
        path = HERE / name
        if path.exists():
            process_file(path)
        else:
            print(f"Not found: {name}")

    print("Done!")


if __name__ == "__main__":
    main()
