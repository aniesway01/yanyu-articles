#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
prepare_prompts_v2.py — 從 662 個 YAML prompt 建立分類索引
來源：C:\\AntiGravityFile\\Prompts\\roles\\coding\\ (661 YAML + agent.json)
輸出：YanYuInc/prompts/roles/*.yaml + _index.json

用法：
  python prepare_prompts_v2.py           # 建立索引 + 複製
  python prepare_prompts_v2.py --stats   # 只顯示統計
"""

import json, os, re, sys, io, shutil, datetime
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import yaml
except ImportError:
    print("pip install pyyaml")
    sys.exit(1)

# === 路徑 ===
SRC_DIR = Path(r"C:\AntiGravityFile\Prompts\roles\coding")
BASE = Path(r"C:\AntiGravityFile\YanYuInc")
DEST_DIR = BASE / "prompts" / "roles"
INDEX_FILE = BASE / "prompts" / "_index.json"
LOG_DIR = BASE / "logs"

# === 分類規則（根據檔名關鍵字，順序=優先級）===
# 重要：越具體的分類放越前面，越模糊的放後面
CATEGORY_RULES = [
    ("dev", "開發工具", [
        "code", "coding", "programming", "developer", "software",
        "debug", "refactor", "api", "database", "sql", "python", "javascript",
        "typescript", "react", "vue", "angular", "node", "frontend", "backend",
        "fullstack", "devops", "docker", "kubernetes", "git", "cicd",
        "architecture", "algorithm", "data_structure", "compiler",
        "html", "css", "web_dev", "mobile_dev", "ios_dev", "android_dev",
        "rust", "golang", "java", "csharp", "php", "ruby", "swift",
        "code_review", "pull_request", "commit", "terminal", "cli",
        "regex", "webhook", "microservice", "deployment",
    ]),
    ("image_gen", "圖片生成", [
        "image_gen", "photo_gen", "picture_gen", "draw", "paint",
        "illustration", "logo", "icon", "graphic", "render",
        "midjourney", "dalle", "stable_diffusion", "avatar", "portrait",
        "wallpaper", "poster", "banner", "thumbnail", "pixel",
        "3d_render", "3d_model", "3d_character", "3d_scene",
        "cartoon", "anime", "comic", "sketch",
    ]),
    ("medical", "醫療健康", [
        "medical", "doctor", "nurse", "health", "patient", "diagnos",
        "treatment", "pharma", "drug", "clinical", "hospital",
        "nutrition", "diet", "fitness", "wellness", "mental_health",
        "symptom", "therapy", "disease", "medicine",
    ]),
    ("professional", "專業領域", [
        "legal", "law", "lawyer", "attorney", "judge", "contract",
        "accountant", "tax", "audit", "compliance", "regulat",
        "architect", "civil_eng", "mechanical", "electrical",
        "scientist", "chemist", "physicist", "biologist",
        "psycholog", "therapist", "counselor", "social_work",
        "real_estate", "insurance", "patent",
    ]),
    ("education", "教育學習", [
        "teach", "tutor", "learn", "education", "student", "professor",
        "academic", "university", "school", "course", "lesson", "quiz",
        "exam", "homework", "study", "research", "paper", "thesis",
        "mentor", "instructor", "lecture", "textbook",
        "math", "science", "history", "language", "english", "chinese",
        "explain", "flashcard", "vocabulary",
    ]),
    ("creative", "創意寫作", [
        "write", "writing", "story", "novel", "poem", "poetry", "creative",
        "fiction", "narrative", "screenplay", "script", "dialogue", "lyric",
        "song", "blog", "article", "essay", "content", "copywriting",
        "journalist", "reporter", "editor", "author", "storytell",
        "fantasy", "scifi", "horror", "mystery", "drama", "romance",
    ]),
    ("business", "商業行銷", [
        "business", "market", "sales", "startup", "entrepreneur", "ceo",
        "manager", "strategy", "finance", "invest", "stock", "crypto",
        "ecommerce", "seo", "social_media", "brand", "advertis",
        "email", "pitch", "negotiat", "consult", "hr", "recruit",
        "product", "project", "agile", "scrum", "analytics",
        "budget", "revenue", "profit", "customer",
    ]),
    ("roleplay", "角色扮演", [
        "roleplay", "role_play", "character", "persona", "npc",
        "companion", "chat_bot", "virtual", "friend", "girlfriend",
        "boyfriend", "waifu", "ai_girl", "ai_boy",
        "act_as", "pretend", "simulate", "impersonat",
    ]),
    ("tool", "工具助手", [
        "tool", "assistant", "helper", "convert", "translat", "summariz",
        "extract", "format", "template", "prompt", "utility",
        "calculator", "analyzer", "optimizer", "automat",
        "spreadsheet", "excel", "pdf", "csv", "json", "xml",
        "email", "schedule", "organiz", "plan",
    ]),
    ("game", "遊戲開發", [
        "game_dev", "game_design", "gaming", "rpg_game", "adventure_game",
        "dungeon", "quest", "gameplay", "player", "level_design",
        "game_engine", "unity", "unreal", "godot",
        "puzzle_game", "trivia", "board_game", "card_game",
    ]),
]
DEFAULT_CATEGORY = ("other", "其他")


def classify_prompt(filename, name="", tags=None):
    """根據檔名和 metadata 自動分類"""
    text = filename.lower()
    if name:
        text += " " + name.lower()
    if tags:
        text += " " + " ".join(t.lower() for t in tags)

    for cat_id, cat_name, keywords in CATEGORY_RULES:
        if any(kw in text for kw in keywords):
            return cat_id, cat_name
    return DEFAULT_CATEGORY


def parse_yaml_prompt(filepath):
    """解析單個 YAML prompt 檔案"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            return None

        # 兩種 schema: simple (metadata + system_prompt) vs versioned (versions[])
        if "metadata" in data:
            meta = data["metadata"]
            return {
                "name": meta.get("name", filepath.stem),
                "source": meta.get("source", ""),
                "author": meta.get("author", ""),
                "tags": meta.get("tags", []),
                "system_prompt": data.get("system_prompt", ""),
                "schema": "simple",
            }
        elif "versions" in data:
            # 取最新版本
            versions = data["versions"]
            if versions:
                latest = versions[-1]
                return {
                    "name": data.get("name", filepath.stem),
                    "source": "",
                    "author": latest.get("author", ""),
                    "tags": [],
                    "system_prompt": latest.get("template", latest.get("content", "")),
                    "schema": "versioned",
                }
        # 嘗試直接讀 system_prompt
        if "system_prompt" in data:
            return {
                "name": data.get("name", filepath.stem),
                "source": data.get("source", ""),
                "author": data.get("author", ""),
                "tags": data.get("tags", []),
                "system_prompt": data["system_prompt"],
                "schema": "flat",
            }
        return None
    except Exception as e:
        print(f"  解析失敗: {filepath.name}: {e}")
        return None


def build_index():
    """掃描所有 YAML，建立分類索引"""
    if not SRC_DIR.exists():
        print(f"來源目錄不存在: {SRC_DIR}")
        sys.exit(1)

    yaml_files = sorted([f for f in SRC_DIR.iterdir() if f.suffix == '.yaml'])
    print(f"找到 {len(yaml_files)} 個 YAML 檔案")

    index = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": 0,
        "categories": {},
        "prompts": [],
    }

    category_counts = {}

    for yf in yaml_files:
        parsed = parse_yaml_prompt(yf)
        if not parsed:
            continue

        cat_id, cat_name = classify_prompt(
            yf.stem, parsed["name"], parsed.get("tags", [])
        )

        slug = yf.stem
        preview = parsed["system_prompt"][:200].replace("\n", " ").strip()

        entry = {
            "slug": slug,
            "filename": yf.name,
            "name": parsed["name"],
            "author": parsed["author"],
            "source": parsed["source"],
            "tags": parsed.get("tags", []),
            "category_id": cat_id,
            "category": cat_name,
            "preview": preview,
            "prompt_length": len(parsed["system_prompt"]),
        }
        index["prompts"].append(entry)

        category_counts.setdefault(cat_id, {"name": cat_name, "count": 0})
        category_counts[cat_id]["count"] += 1

    index["total"] = len(index["prompts"])
    index["categories"] = category_counts

    return index, yaml_files


def copy_yamls(yaml_files):
    """複製 YAML 到目標目錄"""
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    for yf in yaml_files:
        dest = DEST_DIR / yf.name
        if not dest.exists() or yf.stat().st_mtime > dest.stat().st_mtime:
            shutil.copy2(yf, dest)
            copied += 1

    # 也複製 agent.json
    aj = SRC_DIR / "agent.json"
    if aj.exists():
        shutil.copy2(aj, DEST_DIR / "agent.json")

    return copied


def show_stats():
    """只顯示統計"""
    if INDEX_FILE.exists():
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            idx = json.load(f)
        print(f"\n索引生成時間: {idx['generated']}")
        print(f"總 Prompt 數: {idx['total']}")
        print(f"\n分類統計:")
        for cat_id, info in sorted(idx["categories"].items(), key=lambda x: -x[1]["count"]):
            print(f"  {info['name']} ({cat_id}): {info['count']}")
    else:
        print("索引不存在，請先執行 python prepare_prompts_v2.py")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Prompt 庫建索引")
    parser.add_argument("--stats", action="store_true", help="只顯示統計")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    print("=" * 50)
    print("Prompt 庫索引建置")
    print("=" * 50)

    # 1. 建索引
    index, yaml_files = build_index()
    print(f"\n解析成功: {index['total']} 個 prompt")
    print(f"\n分類統計:")
    for cat_id, info in sorted(index["categories"].items(), key=lambda x: -x[1]["count"]):
        print(f"  {info['name']} ({cat_id}): {info['count']}")

    # 2. 複製 YAML
    copied = copy_yamls(yaml_files)
    print(f"\n複製: {copied} 個新/更新的 YAML 到 {DEST_DIR}")

    # 3. 寫索引
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"索引寫入: {INDEX_FILE}")

    print("\n完成！")


if __name__ == "__main__":
    main()
