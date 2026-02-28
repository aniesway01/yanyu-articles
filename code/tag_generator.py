#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tag_generator.py — 為 618 個判決批量生成標籤

用法：
  python tag_generator.py --phase1              # Regex 規則標籤（零成本）
  python tag_generator.py --phase2 --test       # LLM 語義標籤（3 樣本驗證）
  python tag_generator.py --phase2              # LLM 語義標籤（全部）
  python tag_generator.py --status              # 查看進度
"""
import sys, io, json, re, time, argparse, random
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ─── Paths ───
BASE = Path(r"C:\AntiGravityFile\YanYuInc")
JDG_DIR = BASE / "judgments"
CASE_IDX = JDG_DIR / "cases" / "_index.json"
AI_DIR = JDG_DIR / "_ai_analysis"
TAGS_FILE = JDG_DIR / "_tags.json"

# ─── Phase 1: Regex Rules ───

# 審級 from case_no
def extract_court_level(case_no):
    """從案號提取審級"""
    if not case_no:
        return "未知"
    if re.search(r'民初|初字', case_no):
        return "一審"
    if re.search(r'民终|民終|终字', case_no):
        return "二審"
    if re.search(r'民再|再字|民提', case_no):
        return "再審"
    if re.search(r'民申|申字', case_no):
        return "再審審查"
    if re.search(r'行初|行终|行再|行申', case_no):
        # 行政案件
        if '行初' in case_no: return "一審"
        if '行终' in case_no or '行終' in case_no: return "二審"
        if '行再' in case_no: return "再審"
        if '行申' in case_no: return "再審審查"
    return "未知"

# 案件性質 from case_type
LABOR_KW = ['劳动', '劳务', '工伤', '人事', '竞业', '职工破产', '社会保险',
            '经济补偿', '追索劳动报酬', '行政复议', '劳动关系']

def extract_case_nature(case_type, source_pdf=""):
    """區分保險糾紛 vs 勞動糾紛"""
    ct = case_type.strip().lstrip(';；')
    for kw in LABOR_KW:
        if kw in ct:
            return "勞動糾紛"
    if '保险' in ct or '保險' in ct or '保赔' in ct:
        return "保險糾紛"
    # Edge cases: check source PDF
    if '劳动' in source_pdf or '勞動' in source_pdf:
        return "勞動糾紛"
    if '保险' in source_pdf or '保險' in source_pdf:
        return "保險糾紛"
    return "其他"

# 險種 from case_type (粗分)
INSURANCE_TYPE_MAP = [
    (r'财产保险|财产损失保险', '財產保險'),
    (r'人身保险', '人身保險'),
    (r'意外伤害保险', '意外傷害保險'),
    (r'健康保险', '健康保險'),
    (r'人寿保险', '壽險'),
    (r'责任保险', '責任保險'),
    (r'保证保险', '保證保險'),
    (r'海上保险|海上保赔', '海上保險'),
    (r'信用保险', '信用保險'),
    (r'机动车交通事故', '交強險/車險'),
    (r'代位求偿|追偿|迫偿', '代位求償'),
]

def extract_insurance_type_rough(case_type):
    """從 case_type 粗略提取險種"""
    ct = case_type.strip().lstrip(';；')
    for pat, label in INSURANCE_TYPE_MAP:
        if re.search(pat, ct):
            return label
    if '保险' in ct:
        return "保險（通用）"
    return ""

# 省份 from case_no
PROVINCE_MAP = {
    '京': '北京', '沪': '上海', '津': '天津', '渝': '重庆',
    '冀': '河北', '豫': '河南', '云': '云南', '辽': '辽宁',
    '黑': '黑龙江', '湘': '湖南', '皖': '安徽', '鲁': '山东',
    '新': '新疆', '苏': '江苏', '浙': '浙江', '赣': '江西',
    '鄂': '湖北', '桂': '广西', '甘': '甘肃', '晋': '山西',
    '蒙': '内蒙古', '陕': '陕西', '吉': '吉林', '闽': '福建',
    '贵': '贵州', '粤': '广东', '川': '四川', '青': '青海',
    '藏': '西藏', '琼': '海南', '宁': '宁夏',
}

def extract_province(case_no):
    """從案號提取省份"""
    # Pattern: (2016)苏10民终...  or (2016)京02民终...
    m = re.search(r'[（(]\d{4}[）)]\s*([^\d\s])', case_no)
    if m:
        ch = m.group(1)
        if ch in PROVINCE_MAP:
            return PROVINCE_MAP[ch]
    # Fallback: extract from court name
    for prov in ['北京', '上海', '天津', '重庆', '河北', '河南', '云南', '辽宁',
                 '黑龙江', '湖南', '安徽', '山东', '新疆', '江苏', '浙江', '江西',
                 '湖北', '广西', '甘肃', '山西', '内蒙古', '陕西', '吉林', '福建',
                 '贵州', '广东', '四川', '青海', '西藏', '海南', '宁夏']:
        if prov in case_no:
            return prov
    return ""


def run_phase1():
    """Phase 1: Regex 規則標籤"""
    print("[Phase 1] Regex 規則標籤提取...")

    # Load case index
    with open(CASE_IDX, 'r', encoding='utf-8') as f:
        idx = json.load(f)
    cases = idx.get("cases", [])

    # Load existing tags or create new
    tags = {}
    if TAGS_FILE.exists():
        with open(TAGS_FILE, 'r', encoding='utf-8') as f:
            tags = json.load(f)

    stats = {"total": 0, "insurance": 0, "labor": 0}

    # Tag annual cases
    for c in cases:
        case_stem = Path(c["filename"]).stem
        key = f'cases/{c["year"]}/{case_stem}'
        if key not in tags:
            tags[key] = {}

        cn = c.get("case_no", "")
        ct = c.get("case_type", "")
        sp = c.get("source_pdf", "")

        tags[key]["year"] = c["year"]
        tags[key]["court_level"] = extract_court_level(cn)
        tags[key]["case_nature"] = extract_case_nature(ct, sp)
        tags[key]["insurance_type_rough"] = extract_insurance_type_rough(ct)
        tags[key]["province"] = extract_province(cn)
        tags[key]["case_type_raw"] = ct.strip().lstrip(';；')

        stats["total"] += 1
        if tags[key]["case_nature"] == "保險糾紛":
            stats["insurance"] += 1
        elif tags[key]["case_nature"] == "勞動糾紛":
            stats["labor"] += 1

    # Tag featured cases
    for mf in sorted(JDG_DIR.glob("*.md")):
        key = f'featured/{mf.stem}'
        if key not in tags:
            tags[key] = {}
        # Featured are all 人身保險合同糾紛 from wenshu
        tags[key]["year"] = ""
        tags[key]["court_level"] = ""
        tags[key]["case_nature"] = "保險糾紛"
        tags[key]["insurance_type_rough"] = "人身保險"
        tags[key]["province"] = ""
        tags[key]["case_type_raw"] = "人身保險合同糾紛"
        # Try to extract from filename
        cn_match = re.search(r'[（(]?\d{4}[）)]?[\u4e00-\u9fff]+\d+[\u53f7号]', mf.stem)
        if cn_match:
            tags[key]["court_level"] = extract_court_level(mf.stem)
            tags[key]["province"] = extract_province(mf.stem)

    # Save
    tags["_meta"] = {
        "updated": datetime.now().isoformat(timespec='seconds'),
        "phase1_done": True,
        "total": stats["total"],
        "insurance": stats["insurance"],
        "labor": stats["labor"],
    }
    with open(TAGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tags, f, ensure_ascii=False, indent=2)

    print(f"  總共: {stats['total']} 筆年度案例 + {len(list(JDG_DIR.glob('*.md')))} 筆精選")
    print(f"  保險糾紛: {stats['insurance']}  勞動糾紛: {stats['labor']}")

    # Show court_level distribution
    levels = {}
    for k, v in tags.items():
        if k == "_meta":
            continue
        lv = v.get("court_level", "")
        levels[lv] = levels.get(lv, 0) + 1
    print(f"  審級分布: {dict(sorted(levels.items(), key=lambda x:-x[1]))}")

    # Show insurance_type_rough distribution
    itypes = {}
    for k, v in tags.items():
        if k == "_meta":
            continue
        it = v.get("insurance_type_rough", "") or "待分類"
        itypes[it] = itypes.get(it, 0) + 1
    print(f"  險種粗分: {dict(sorted(itypes.items(), key=lambda x:-x[1]))}")

    print(f"  已儲存: {TAGS_FILE}")
    return tags


# ─── Phase 2: LLM Semantic Tags ───

def _load_ds_keys():
    key_file = Path(r"C:\AntiGravityFile\Docs\Standards\Credentials\APIkeyBase.md")
    keys = []
    if key_file.exists():
        text = key_file.read_text(encoding='utf-8')
        for m in re.finditer(r'deepseek\d*\s*\|\s*`(sk-[a-f0-9]+)`', text):
            keys.append(m.group(1))
    if not keys:
        print("[ERROR] 無法從 APIkeyBase.md 讀取 DeepSeek key"); sys.exit(1)
    return keys

TAG_PROMPT = """你是保險法律分類專家。請根據以下資料，為此判決生成精確的標籤。

案由: {case_type}
摘要: {summary}
爭議焦點: {key_points}

請以 JSON 格式回覆（不要 code fence），欄位如下：
{{
  "insurance_type": ["險種1"],
  "dispute_type": ["爭議類型1", "爭議類型2"],
  "verdict": "裁判結果",
  "key_statutes": ["法條1", "法條2"]
}}

各欄位選項：

insurance_type（選1-2個最主要的）：
人身保險, 壽險, 健康保險, 意外傷害保險, 重大疾病保險,
財產保險, 車險, 交強險, 責任保險, 雇主責任保險,
保證保險, 海上保險, 信用保險, 農業保險,
工傷保險, 社會保險, 養老保險, 醫療保險（社保）,
不適用

dispute_type（選1-3個）：
理賠糾紛, 拒賠爭議, 保險金計算,
免責條款, 格式條款/提示說明義務,
如實告知義務, 合同效力, 合同解除,
代位求償, 保險利益, 受益人認定,
舉證責任, 因果關係認定, 近因原則,
保險欺詐/道德風險, 重複保險,
勞動關係確認, 工傷認定, 勞動報酬, 競業限制, 經濟補償,
其他

verdict（選1個）：
支持投保人/被保險人, 支持保險公司, 部分支持, 維持原判, 改判, 發回重審, 駁回申請, 確認關係, 其他

key_statutes（提取文中引用的法條，如"保險法第16條"，最多5個，沒有則空陣列）
"""

_key_idx = 0

def call_tag_llm(case_type, summary, key_points, max_retries=3):
    global _key_idx
    DS_KEYS = _load_ds_keys()
    DS_URL = "https://api.deepseek.com/v1/chat/completions"

    prompt = TAG_PROMPT.format(
        case_type=case_type,
        summary=summary,
        key_points=", ".join(key_points) if isinstance(key_points, list) else str(key_points)
    )

    for attempt in range(max_retries):
        key = DS_KEYS[_key_idx % len(DS_KEYS)]
        _key_idx += 1
        try:
            import requests
            resp = requests.post(
                DS_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 512,
                    "response_format": {"type": "json_object"},
                },
                timeout=60,
            )
            if resp.status_code == 429:
                wait = (attempt + 1) * 10
                print(f"    [429] 等待 {wait}s...", flush=True)
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                print(f"    [HTTP {resp.status_code}] {resp.text[:100]}", flush=True)
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return None

            data = resp.json()
            text_out = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not text_out:
                return None
            text_out = text_out.strip()
            text_out = re.sub(r'^```(?:json)?\s*', '', text_out)
            text_out = re.sub(r'\s*```$', '', text_out)
            result = json.loads(text_out)

            # Validate
            for field in ("insurance_type", "dispute_type", "verdict"):
                if field not in result:
                    result[field] = [] if field != "verdict" else "其他"
            if "key_statutes" not in result:
                result["key_statutes"] = []
            return result

        except json.JSONDecodeError as e:
            print(f"    [JSON ERR] {str(e)[:60]}", flush=True)
            if attempt < max_retries - 1:
                continue
            return None
        except Exception as e:
            print(f"    [ERR] {str(e)[:80]}", flush=True)
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return None
    return None


def run_phase2(test_mode=False, start_from=0):
    """Phase 2: LLM 語義標籤"""
    print("[Phase 2] LLM 語義標籤生成...")

    # Load existing tags (must have phase1 done)
    if not TAGS_FILE.exists():
        print("[ERROR] 請先執行 --phase1"); sys.exit(1)
    with open(TAGS_FILE, 'r', encoding='utf-8') as f:
        tags = json.load(f)

    # Load AI analyses
    ai = {}
    if AI_DIR.exists():
        for aj in AI_DIR.rglob("*.json"):
            if aj.name == "_progress.json":
                continue
            rel = aj.relative_to(AI_DIR).with_suffix("").as_posix()
            try:
                with open(aj, 'r', encoding='utf-8') as f:
                    ai[rel] = json.load(f)
            except Exception:
                pass
    print(f"  AI 分析已載入: {len(ai)} 筆")

    # Build work list
    work = []
    for key in sorted(tags.keys()):
        if key == "_meta":
            continue
        # Skip if already has LLM tags
        if tags[key].get("insurance_type") and tags[key].get("dispute_type") and tags[key].get("verdict"):
            continue
        if key in ai:
            work.append(key)

    work = work[start_from:]
    if test_mode:
        work = work[:3]

    total_all = len([k for k in tags if k != "_meta"])
    print(f"  待處理: {len(work)} / {total_all}")

    if not work:
        print("  全部已完成！")
        return

    ok_count = 0
    err_count = 0

    for i, key in enumerate(work):
        a = ai[key]
        ct = tags[key].get("case_type_raw", "")
        summary = a.get("summary", "")
        kps = a.get("key_points", [])

        label = f"[{start_from + i + 1}/{len(work)}]"
        short = key.split("/")[-1][:40]
        print(f"  {label} {short}...", end=" ", flush=True)

        result = call_tag_llm(ct, summary, kps)
        if result:
            tags[key]["insurance_type"] = result.get("insurance_type", [])
            tags[key]["dispute_type"] = result.get("dispute_type", [])
            tags[key]["verdict"] = result.get("verdict", "")
            tags[key]["key_statutes"] = result.get("key_statutes", [])
            ok_count += 1
            dt = ", ".join(result.get("dispute_type", []))[:30]
            print(f"OK ({result.get('verdict','?')} | {dt})", flush=True)
        else:
            err_count += 1
            print("FAILED", flush=True)

        # Save every 20
        if (i + 1) % 20 == 0:
            tags["_meta"]["updated"] = datetime.now().isoformat(timespec='seconds')
            tags["_meta"]["phase2_ok"] = ok_count
            tags["_meta"]["phase2_err"] = err_count
            with open(TAGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(tags, f, ensure_ascii=False, indent=2)

        time.sleep(0.8 + random.uniform(0, 0.3))

    # Final save
    tags["_meta"]["updated"] = datetime.now().isoformat(timespec='seconds')
    tags["_meta"]["phase2_done"] = True
    tags["_meta"]["phase2_ok"] = ok_count
    tags["_meta"]["phase2_err"] = err_count
    with open(TAGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tags, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"  完成！成功: {ok_count} | 失敗: {err_count}")
    print(f"{'='*50}")


def show_status():
    if not TAGS_FILE.exists():
        print("尚未產生標籤檔案"); return
    with open(TAGS_FILE, 'r', encoding='utf-8') as f:
        tags = json.load(f)
    meta = tags.get("_meta", {})
    total = len([k for k in tags if k != "_meta"])

    # Count phase2 completion
    p2_done = sum(1 for k, v in tags.items() if k != "_meta" and v.get("insurance_type"))

    print(f"總標籤數:    {total}")
    print(f"Phase 1:     {'完成' if meta.get('phase1_done') else '未完成'}")
    print(f"Phase 2:     {p2_done}/{total} ({p2_done*100//max(total,1)}%)")
    print(f"上次更新:    {meta.get('updated', 'N/A')}")

    # Tag distribution
    if p2_done > 0:
        verdicts = {}
        ins_types = {}
        disp_types = {}
        for k, v in tags.items():
            if k == "_meta": continue
            vd = v.get("verdict", "")
            if vd: verdicts[vd] = verdicts.get(vd, 0) + 1
            for it in v.get("insurance_type", []):
                ins_types[it] = ins_types.get(it, 0) + 1
            for dt in v.get("dispute_type", []):
                disp_types[dt] = disp_types.get(dt, 0) + 1
        print(f"\n裁判結果: {dict(sorted(verdicts.items(), key=lambda x:-x[1]))}")
        print(f"\n險種 TOP10:")
        for t, n in sorted(ins_types.items(), key=lambda x: -x[1])[:10]:
            print(f"  {n:4d}  {t}")
        print(f"\n爭議類型 TOP10:")
        for t, n in sorted(disp_types.items(), key=lambda x: -x[1])[:10]:
            print(f"  {n:4d}  {t}")


def main():
    parser = argparse.ArgumentParser(description="判決標籤生成器")
    parser.add_argument('--phase1', action='store_true', help='Phase 1: Regex 規則')
    parser.add_argument('--phase2', action='store_true', help='Phase 2: LLM 語義標籤')
    parser.add_argument('--test', action='store_true', help='只跑 3 個樣本')
    parser.add_argument('--start-from', type=int, default=0, help='從第 N 個開始')
    parser.add_argument('--status', action='store_true', help='查看進度')
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.phase1:
        run_phase1()
    elif args.phase2:
        run_phase2(test_mode=args.test, start_from=args.start_from)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
