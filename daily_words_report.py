#!/usr/bin/env python3
"""
每日单词报告
============
读取最近 5 天的 call_logs 查询记录，去重后按查询时间倒序排列，
剔除测试数据，输出到 recent_words.md 文件。

用法:
  venv/bin/python3 daily_words_report.py
  venv/bin/python3 daily_words_report.py --days 7
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "call_logs")
OUTPUT_FILE = os.path.join(BASE_DIR, "recent_words.md")
LOCAL_TZ = timezone(timedelta(hours=8))

TEST_KEYWORDS = ["test", "regression", "debug", "dummy"]


def is_test_word(word: str) -> bool:
    word_lower = word.lower().strip()
    for kw in TEST_KEYWORDS:
        if kw in word_lower:
            return True
    return False


def get_recent_words(days: int = 5) -> list:
    today = datetime.now(LOCAL_TZ).date()
    word_map = {}

    for i in range(days):
        date = today - timedelta(days=i)
        date_str = str(date)
        filepath = os.path.join(LOG_DIR, f"{date_str}.jsonl")
        if not os.path.exists(filepath):
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                word = record.get("word", "").lower().strip()
                if not word or record.get("type") != "word":
                    continue

                ts = record.get("ts", "")
                if word not in word_map:
                    word_map[word] = {
                        "word": word,
                        "last_seen": ts,
                        "query_count": 0,
                        "dates": set(),
                    }
                else:
                    if ts > word_map[word]["last_seen"]:
                        word_map[word]["last_seen"] = ts

                word_map[word]["query_count"] += 1
                word_map[word]["dates"].add(date_str)

    result = []
    for word, info in word_map.items():
        if is_test_word(word):
            continue
        info["dates"] = sorted(info["dates"])
        result.append(info)

    result.sort(key=lambda x: x["last_seen"], reverse=True)
    return result


def generate_report(words: list, days: int) -> str:
    today = datetime.now(LOCAL_TZ)
    start = today - timedelta(days=days - 1)

    lines = []
    lines.append(f"# 📖 近期查询单词汇总")
    lines.append(f"")
    lines.append(f"> 统计范围：{start.strftime('%Y-%m-%d')} ~ {today.strftime('%Y-%m-%d')}")
    lines.append(f"> 生成时间：{today.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> 去重单词数：{len(words)} 个")
    lines.append(f"")

    if not words:
        lines.append("暂无查询记录。")
        return "\n".join(lines)

    lines.append(f"| # | 单词 | 查询次数 | 出现日期 |")
    lines.append(f"|---|------|---------|---------|")
    for idx, w in enumerate(words, 1):
        dates_str = ", ".join(w["dates"])
        lines.append(f"| {idx} | {w['word']} | {w['query_count']} | {dates_str} |")

    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*单词列表按最后查询时间倒序排列*")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="每日单词报告")
    parser.add_argument("--days", type=int, default=5, help="统计最近几天（默认 5）")
    args = parser.parse_args()

    words = get_recent_words(days=args.days)
    report = generate_report(words, args.days)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ 已生成报告: {OUTPUT_FILE}")
    print(f"   共 {len(words)} 个去重单词")
    for w in words:
        print(f"   - {w['word']} (查询{w['query_count']}次, 最后{w['last_seen']})")


if __name__ == "__main__":
    main()
