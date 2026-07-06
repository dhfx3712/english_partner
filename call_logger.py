#!/usr/bin/env python3
"""
EnglishPartner 调用记录日志工具
================================

功能：
  1. 每次查词实时记录到 call_logs/YYYY-MM-DD.jsonl（按日期分文件）
  2. 自动清理 7 天前的日志文件
  3. 支持按日期读取记录，供飞书同步使用

用法：
  python3 call_logger.py record word <word>       # 记录单词查询
  python3 call_logger.py record root <word>       # 记录词根查询
  python3 call_logger.py record pronounce <word>  # 记录发音查询
  python3 call_logger.py get [YYYY-MM-DD]         # 获取某天的记录（默认今天）
  python3 call_logger.py cleanup                  # 手动清理旧文件
  python3 call_logger.py list                     # 列出所有日志文件
  python3 call_logger.py words [YYYY-MM-DD]       # 获取某天去重单词列表（默认今天）

数据文件：
  call_logs/YYYY-MM-DD.jsonl  — 每天一个文件，每行一条 JSON 记录
  自动保留最近 7 天，超期自动删除
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "call_logs")
RETENTION_DAYS = 7
LOCAL_TZ = timezone(timedelta(hours=8))


# ============================================================
# 基础工具
# ============================================================


def ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)


def today_str() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")


def log_file_path(date_str: str) -> str:
    return os.path.join(LOG_DIR, f"{date_str}.jsonl")


# ============================================================
# 核心：记录查询
# ============================================================


def record_call(cmd_type: str, word: str) -> None:
    """
    记录一次查询调用。
    写入当天的 call_logs/YYYY-MM-DD.jsonl 文件，每行一条 JSON。
    写入后自动清理 7 天前的旧文件。
    """
    ensure_log_dir()
    date = today_str()
    filepath = log_file_path(date)

    record = {
        "ts": now_iso(),
        "type": cmd_type,  # word, root, pronounce
        "word": word.lower().strip(),
    }

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 自动清理旧文件
    deleted = cleanup_old_files()
    if deleted:
        print(f"  🧹 已清理 {deleted} 个旧日志文件", file=sys.stderr)


# ============================================================
# 读取记录
# ============================================================


def get_records(date_str: Optional[str] = None) -> List[dict]:
    """获取某天的所有调用记录"""
    date = date_str or today_str()
    filepath = log_file_path(date)

    if not os.path.exists(filepath):
        return []

    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def get_words(date_str: Optional[str] = None) -> List[dict]:
    """
    获取某天查询的去重单词列表（含查询次数）。
    只统计 word 类型（root 和 pronounce 不单独计数）。
    返回按首次查询时间排序的列表。
    """
    records = get_records(date_str)

    # 只统计 word 类型的查询
    word_records = [r for r in records if r.get("type") == "word"]

    # 去重并统计
    word_map: Dict[str, dict] = {}
    for r in word_records:
        w = r.get("word", "")
        if not w:
            continue
        if w not in word_map:
            word_map[w] = {
                "word": w,
                "first_seen": r.get("ts", ""),
                "last_seen": r.get("ts", ""),
                "query_count": 0,
            }
        word_map[w]["last_seen"] = r.get("ts", "")
        word_map[w]["query_count"] += 1

    # 按首次查询时间排序
    result = sorted(word_map.values(), key=lambda x: x.get("first_seen", ""))
    return result


# ============================================================
# 清理旧文件
# ============================================================


def cleanup_old_files() -> int:
    """删除超过 RETENTION_DAYS 天的日志文件，返回删除数量"""
    ensure_log_dir()
    now = datetime.now(LOCAL_TZ)
    cutoff = now - timedelta(days=RETENTION_DAYS)
    deleted = 0

    for filename in os.listdir(LOG_DIR):
        if not filename.endswith(".jsonl"):
            continue
        date_part = filename[:-6]  # remove .jsonl
        try:
            file_date = datetime.strptime(date_part, "%Y-%m-%d").replace(tzinfo=LOCAL_TZ)
            if file_date < cutoff:
                os.remove(os.path.join(LOG_DIR, filename))
                deleted += 1
        except ValueError:
            continue

    return deleted


# ============================================================
# 列出日志文件
# ============================================================


def list_log_files() -> List[dict]:
    """列出所有日志文件及其信息"""
    ensure_log_dir()
    files = []
    for f in sorted(os.listdir(LOG_DIR)):
        if not f.endswith(".jsonl"):
            continue
        filepath = os.path.join(LOG_DIR, f)
        size = os.path.getsize(filepath)
        date_part = f[:-6]
        records_count = 0
        try:
            with open(filepath, "r") as fh:
                records_count = sum(1 for _ in fh)
        except IOError:
            pass
        files.append({
            "file": f,
            "date": date_part,
            "size": size,
            "records": records_count,
        })
    return files


# ============================================================
# 主入口
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="EnglishPartner 调用记录日志工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 call_logger.py record word hello       # 记录单词查询
  python3 call_logger.py get                     # 获取今天所有记录
  python3 call_logger.py get 2026-06-23          # 获取指定日期记录
  python3 call_logger.py words                   # 获取今天去重单词
  python3 call_logger.py words 2026-06-23        # 获取指定日期去重单词
  python3 call_logger.py list                    # 列出所有日志文件
  python3 call_logger.py cleanup                 # 手动清理旧文件
        """,
    )

    parser.add_argument(
        "command",
        choices=["record", "get", "words", "cleanup", "list"],
        help="操作命令",
    )
    parser.add_argument(
        "args",
        nargs="*",
        help="参数",
    )

    parsed = parser.parse_args()

    if parsed.command == "record":
        if len(parsed.args) < 2:
            print('{"error":"Usage: record <type> <word>"}', file=sys.stderr)
            sys.exit(1)
        cmd_type = parsed.args[0]
        word = parsed.args[1]
        if cmd_type not in ("word", "root", "pronounce"):
            print(f'{{"error":"Invalid type: {cmd_type}"}}', file=sys.stderr)
            sys.exit(1)
        record_call(cmd_type, word)

    elif parsed.command == "get":
        date_str = parsed.args[0] if parsed.args else None
        records = get_records(date_str)
        print(json.dumps(records, ensure_ascii=False, indent=2))

    elif parsed.command == "words":
        date_str = parsed.args[0] if parsed.args else None
        words = get_words(date_str)
        print(json.dumps(words, ensure_ascii=False, indent=2))

    elif parsed.command == "cleanup":
        deleted = cleanup_old_files()
        print(f"已清理 {deleted} 个旧日志文件")

    elif parsed.command == "list":
        files = list_log_files()
        if not files:
            print("暂无日志文件")
        else:
            total_records = sum(f["records"] for f in files)
            print(f"日志文件列表（共 {len(files)} 个，{total_records} 条记录）:")
            print()
            for f in files:
                size_kb = f["size"] / 1024
                print(f"  {f['file']:30s}  {f['records']:4d} 条  {size_kb:.1f} KB")
            print()
            print(f"💡 使用 'python3 call_logger.py get <日期>' 查看某天记录")
            print(f"   'python3 call_logger.py words <日期>' 查看某天去重单词")


if __name__ == "__main__":
    main()
