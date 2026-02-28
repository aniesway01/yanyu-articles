#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ocr_judgments.py — OCR 掃描型保險判決 PDF → Markdown
主引擎：PaddleOCR (http://127.0.0.1:8080/ocr)
後備：百度 OCR (accurate_basic, 500 次/月)
斷點續傳：judgments/_ocr_state.json

用法：
  python ocr_judgments.py                # 處理全部
  python ocr_judgments.py --test         # 只跑 2021 前 3 頁驗證
  python ocr_judgments.py --status       # 查看進度
"""

import json, os, re, sys, io, time, datetime, base64, traceback
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import requests
    import fitz  # PyMuPDF
except ImportError as e:
    print(f"缺少套件: {e}\npip install requests pymupdf")
    sys.exit(1)

# === 路徑 ===
BASE = Path(r"C:\AntiGravityFile\YanYuInc")
JDG_EB_DIR = BASE / "judgments" / "ebookhub"
STATE_FILE = BASE / "judgments" / "_ocr_state.json"
LOG_DIR = BASE / "logs"
APIKEY_FILE = Path(r"C:\AntiGravityFile\Docs\Standards\Credentials\APIkeyBase.md")
PDF_ROOT = Path(r"C:\AntiGravityFile\Project\ebookhub\中国法院案例2014-2025")

PADDLE_URL = "http://127.0.0.1:8080/ocr"
BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"

# 5 份掃描 PDF 定義
SCAN_PDFS = [
    {"year": "2014", "subdir": r"1.中国法院2014年度案例18册", "filename": "中国法院2014年度案例_保险纠纷.pdf"},
    {"year": "2015", "subdir": r"2.中国法院2015年度案例19册", "filename": "中国法院2015年度案例（15）保险纠纷（291页）.pdf"},
    {"year": "2017", "subdir": r"4.中国法院2017年度案例21册", "filename": "中国法院2017年度案例 保险.pdf"},
    {"year": "2021", "subdir": r"8.中国法院2021年度案例23册", "filename": "中国法院2021年度案例：保险纠纷.pdf"},
    {"year": "2024", "subdir": r"中国法院2024年度案例23册全", "filename": "15.保险纠纷.pdf"},
]

# === Logger ===
class Logger:
    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.datetime.now().strftime("%Y%m%d")
        self.log_file = LOG_DIR / f"ocr_judgments_{today}.log"

    def log(self, level, msg):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {level}: {msg}"
        print(line)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def info(self, msg): self.log("INFO", msg)
    def error(self, msg): self.log("ERROR", msg)
    def ok(self, msg): self.log("OK", msg)

logger = Logger()

# === API Key 載入 ===
def load_baidu_keys():
    """從 APIkeyBase.md 讀取百度 OCR key"""
    if not APIKEY_FILE.exists():
        return None, None
    with open(APIKEY_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    ak_val, sk_val = None, None
    for line in text.split('\n'):
        ll = line.lower()
        if 'baiduocr_api_key' in ll or 'baidu_ocr_api_key' in ll:
            m = re.search(r'`([^`]+)`', line)
            if m:
                ak_val = m.group(1)
        elif 'baiduocr_secret_key' in ll or 'baidu_ocr_secret_key' in ll:
            m = re.search(r'`([^`]+)`', line)
            if m:
                sk_val = m.group(1)
    return ak_val, sk_val

# === OCR 引擎 ===
class PaddleOCREngine:
    def __init__(self):
        self.url = PADDLE_URL
        self.available = False
        self.session = requests.Session()

    def check(self):
        try:
            resp = self.session.get(self.url.replace('/ocr', '/'), timeout=3)
            self.available = True
            return True
        except Exception:
            self.available = False
            return False

    def ocr(self, image_bytes):
        """返回 (text, avg_confidence)"""
        try:
            files = {"image": ("page.png", image_bytes, "image/png")}
            resp = self.session.post(self.url, files=files, timeout=120)
            if resp.status_code == 200:
                result = resp.json()
                results = result.get("results", [])
                if not results:
                    return "", 0.0
                texts = []
                confs = []
                for r in results:
                    conf = r.get("confidence", 0)
                    confs.append(conf)
                    if conf > 0.3:
                        texts.append(r.get("text", ""))
                avg_conf = sum(confs) / len(confs) if confs else 0
                return "\n".join(texts), avg_conf
            return "", 0.0
        except Exception as e:
            logger.error(f"  PaddleOCR 錯誤: {e}")
            return "", 0.0


class BaiduOCREngine:
    def __init__(self):
        self.ak, self.sk = load_baidu_keys()
        self.token = None
        self.available = bool(self.ak and self.sk)
        self.call_count = 0

    def _refresh_token(self):
        if not self.available:
            return False
        if self.token:
            return True
        try:
            url = f"{BAIDU_TOKEN_URL}?grant_type=client_credentials&client_id={self.ak}&client_secret={self.sk}"
            resp = requests.post(url, timeout=10)
            data = resp.json()
            if 'access_token' in data:
                self.token = data['access_token']
                return True
            logger.error(f"  百度 token 失敗: {data}")
            return False
        except Exception as e:
            logger.error(f"  百度 token 錯誤: {e}")
            return False

    def ocr(self, image_bytes):
        """返回 (text, 1.0)，百度 OCR 不返回信心度，預設高精度"""
        if not self._refresh_token():
            return "", 0.0
        try:
            b64 = base64.b64encode(image_bytes).decode('utf-8')
            params = {"image": b64, "language_type": "CHN_ENG"}
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            url = f"{BAIDU_OCR_URL}?access_token={self.token}"
            resp = requests.post(url, data=params, headers=headers, timeout=30)
            result = resp.json()
            if 'words_result' in result:
                lines = [item['words'] for item in result['words_result']]
                self.call_count += 1
                return "\n".join(lines), 0.95
            if 'error_code' in result:
                logger.error(f"  百度 OCR 錯誤: {result['error_code']} {result.get('error_msg', '')}")
                if result['error_code'] == 110:  # token 過期
                    self.token = None
            return "", 0.0
        except Exception as e:
            logger.error(f"  百度 OCR 異常: {e}")
            return "", 0.0


# === 狀態管理 ===
def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"pdfs": {}}

def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# === 主 OCR 流程 ===
def ocr_single_pdf(pdf_info, paddle, baidu, state, max_pages=None):
    """OCR 一份 PDF，產出 Markdown"""
    year = pdf_info["year"]
    pdf_path = PDF_ROOT / pdf_info["subdir"] / pdf_info["filename"]
    out_name = f"{year}_{pdf_info['filename'].replace('.pdf', '')}.md"
    out_path = JDG_EB_DIR / out_name

    if not pdf_path.exists():
        logger.error(f"PDF 不存在: {pdf_path}")
        return False

    pdf_key = pdf_info["filename"]
    pdf_state = state["pdfs"].setdefault(pdf_key, {
        "status": "pending", "pages_done": 0, "total_pages": 0,
        "out_file": out_name, "engine_stats": {"paddle": 0, "baidu": 0}
    })

    if pdf_state["status"] == "done" and out_path.exists():
        logger.info(f"[{year}] 已完成，跳過: {out_name}")
        return True

    logger.info(f"[{year}] 開始 OCR: {pdf_info['filename']}")
    doc = fitz.open(str(pdf_path))
    total = doc.page_count
    pdf_state["total_pages"] = total
    start_page = pdf_state["pages_done"]

    if max_pages:
        end_page = min(start_page + max_pages, total)
    else:
        end_page = total

    logger.info(f"  總頁數: {total}, 從第 {start_page + 1} 頁開始, 目標到第 {end_page} 頁")

    # 讀取已有的文字（如果是續傳）
    lines = []
    if start_page > 0 and out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            existing = f.read()
        # 找到 header 結尾之後的內容
        header_end = existing.find("\n---\n")
        if header_end > 0:
            lines = [existing[header_end + 5:]]

    pdf_state["status"] = "processing"
    save_state(state)

    for i in range(start_page, end_page):
        page = doc[i]
        # 高解析度渲染 (200 DPI)
        mat = fitz.Matrix(200 / 72, 200 / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        text, conf = "", 0.0

        # 嘗試 PaddleOCR
        if paddle.available:
            text, conf = paddle.ocr(img_bytes)
            if text:
                pdf_state["engine_stats"]["paddle"] += 1

        # 信心度低 or PaddleOCR 失敗 → 百度 OCR
        if conf < 0.6 and baidu.available:
            logger.info(f"  第 {i+1}/{total} 頁: PaddleOCR 信心度 {conf:.2f}, 切換百度 OCR")
            text_b, conf_b = baidu.ocr(img_bytes)
            if conf_b > conf:
                text = text_b
                conf = conf_b
                pdf_state["engine_stats"]["baidu"] += 1

        if not text.strip():
            lines.append(f"\n<!-- 第 {i+1} 頁：無法識別文字 -->\n")
        else:
            # 清理
            text = re.sub(r'\n{3,}', '\n\n', text)
            lines.append(f"\n\n## 第 {i+1} 頁\n\n{text}")

        pdf_state["pages_done"] = i + 1

        # 每 10 頁保存一次狀態和文件
        if (i + 1) % 10 == 0 or i == end_page - 1:
            save_state(state)
            _write_md(out_path, pdf_info, total, pdf_state, "\n".join(lines))
            logger.info(f"  進度: {i+1}/{total} 頁 (PaddleOCR: {pdf_state['engine_stats']['paddle']}, 百度: {pdf_state['engine_stats']['baidu']})")

    if pdf_state["pages_done"] >= total:
        pdf_state["status"] = "done"
        pdf_state["done_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_state(state)

    doc.close()
    logger.ok(f"[{year}] 完成 OCR: {out_name} ({pdf_state['pages_done']}/{total} 頁)")
    return True


def _write_md(out_path, pdf_info, total, pdf_state, content):
    """寫入 Markdown 檔案"""
    header = f"""# {pdf_info['year']} 年 — {pdf_info['filename'].replace('.pdf', '')}

> **來源**：中國法院年度案例叢書
> **原始檔案**：{pdf_info['filename']}
> **總頁數**：{total}
> **OCR 引擎**：PaddleOCR {pdf_state['engine_stats']['paddle']} 頁 + 百度 OCR {pdf_state['engine_stats']['baidu']} 頁
> **轉換時間**：{datetime.datetime.now():%Y-%m-%d %H:%M}

---
"""
    JDG_EB_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + content)


def show_status():
    state = load_state()
    if not state["pdfs"]:
        print("尚無 OCR 記錄")
        return
    for key, info in state["pdfs"].items():
        status = info["status"]
        done = info["pages_done"]
        total = info["total_pages"]
        pct = f"{done/total*100:.0f}%" if total > 0 else "N/A"
        print(f"  {key}: {status} ({done}/{total} = {pct})")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="OCR 掃描判決 PDF")
    parser.add_argument("--test", action="store_true", help="只跑 2021 前 3 頁做品質驗證")
    parser.add_argument("--status", action="store_true", help="查看進度")
    parser.add_argument("--year", default=None, help="只處理指定年份")
    parser.add_argument("--no-paddle", action="store_true", help="跳過 PaddleOCR，只用百度")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    logger.info("=" * 50)
    logger.info("OCR 掃描判決 PDF 開始")
    logger.info("=" * 50)

    # 初始化引擎
    paddle = PaddleOCREngine()
    if args.no_paddle:
        paddle.available = False
        logger.info("PaddleOCR: 已跳過 (--no-paddle)")
    elif paddle.check():
        logger.info("PaddleOCR: 可用")
    else:
        logger.info("PaddleOCR: 不可用，將嘗試百度 OCR")

    baidu = BaiduOCREngine()
    if baidu.available:
        logger.info("百度 OCR: 可用")
    else:
        logger.info("百度 OCR: 不可用（缺少 API Key）")

    if not paddle.available and not baidu.available:
        logger.error("沒有可用的 OCR 引擎！請啟動 PaddleOCR 或配置百度 OCR Key")
        sys.exit(1)

    state = load_state()

    if args.test:
        # 測試模式：只跑 2021 年前 3 頁
        target = [p for p in SCAN_PDFS if p["year"] == "2021"][0]
        logger.info(f"測試模式: {target['filename']} 前 3 頁")
        ocr_single_pdf(target, paddle, baidu, state, max_pages=3)
        return

    targets = SCAN_PDFS
    if args.year:
        targets = [p for p in SCAN_PDFS if p["year"] == args.year]

    for pdf_info in targets:
        ocr_single_pdf(pdf_info, paddle, baidu, state)
        logger.info("")

    logger.info("=" * 50)
    logger.info("OCR 全部完成")
    if baidu.call_count > 0:
        logger.info(f"百度 OCR 本次使用: {baidu.call_count} 次")


if __name__ == "__main__":
    main()
