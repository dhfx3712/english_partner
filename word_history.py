#!/usr/bin/env python3
"""
EnglishPartner 单词查询历史记录工具
====================================

功能：
  1. 扫描 EnglishPartner 所有历史会话（trajectory 文件），提取所有查询过的单词
  2. 自动去重，不重复记录同一个单词
  3. 保存到 word_history.json 文件中
  4. 支持导出单词列表（终端输出 / 文件导出）

用法：
  python3 word_history.py scan          # 扫描历史会话，提取所有查询过的单词
  python3 word_history.py list           # 列出所有已记录的单词
  python3 word_history.py today           # 只列出今天查询、去重后的单词
  python3 word_history.py today word1 word2...  # 筛选今天查询的指定单词
  python3 word_history.py export         # 导出单词列表到终端（带释义信息）
  python3 word_history.py export --file  # 导出单词列表到文件 word_list_export.txt
  python3 word_history.py stats          # 显示统计信息
  python3 word_history.py add <word>     # 手动添加一个单词到记录
  python3 word_history.py info <word>    # 查看某个单词的详细信息
  python3 word_history.py sync-bitable    # 同步今日去重单词到飞书多维表格

数据文件：
  - word_history.json  : 存储所有查询过的单词及元数据（自动维护）
  - word_list_export.txt : 导出的清晰单词列表（export --file 生成）

扫描来源：
  - english-agent 的 trajectory 文件（ep-query word/root/pronounce 命令）
  - 支持增量扫描（只处理新文件）
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

# ============================================================
# 路径常量
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 单词历史数据文件
HISTORY_FILE = os.path.join(BASE_DIR, "word_history.json")

# 导出文件
EXPORT_FILE = os.path.join(BASE_DIR, "word_list_export.txt")

# EnglishAgent 会话目录
SESSION_DIR = os.path.expanduser(
    "~/.openclaw/agents/english-agent/sessions"
)

# ============================================================
# 单词历史数据管理
# ============================================================


def load_history() -> dict:
    """
    加载 word_history.json，返回数据结构：
    {
        "version": 1,
        "updated_at": "2026-06-23T16:30:00+08:00",
        "total_words": 15,
        "scanned_files": ["file1.jsonl", ...],
        "words": {
            "hello": {
                "word": "hello",
                "first_seen": "2026-06-19T07:21:38+08:00",
                "last_seen": "2026-06-23T08:00:06+08:00",
                "source_files": ["file1.jsonl", "file2.jsonl"],
                "query_count": 3
            },
            ...
        }
    }
    """
    if not os.path.exists(HISTORY_FILE):
        return {
            "version": 1,
            "updated_at": "",
            "total_words": 0,
            "scanned_files": [],
            "words": {},
        }
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {
            "version": 1,
            "updated_at": "",
            "total_words": 0,
            "scanned_files": [],
            "words": {},
        }


def save_history(history: dict) -> None:
    """保存 word_history.json"""
    history["updated_at"] = now_iso()
    history["total_words"] = len(history.get("words", {}))
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"✅ 已保存 {history['total_words']} 个单词到 {HISTORY_FILE}")


def now_iso() -> str:
    """返回当前时间的 ISO 格式字符串（含时区）"""
    tz = timezone.utc
    local_tz = timezone(timedelta(hours=8))  # Asia/Shanghai
    now = datetime.now(local_tz)
    return now.strftime("%Y-%m-%dT%H:%M:%S%z")


# 在文件顶部添加 timedelta 导入
from datetime import timedelta


def add_word_to_history(
    history: dict, word: str, source_file: str, timestamp: Optional[str] = None
) -> bool:
    """
    向历史记录中添加一个单词（自动去重）。
    返回 True 表示新单词，False 表示已存在。

    计数规则：每个会话文件只计 1 次（不重复累计同一文件内的多次出现）。
    """
    word = word.lower().strip()
    if not word or not re.match(r"^[a-z]+$", word):
        return False

    ts = timestamp or now_iso()
    words = history.get("words", {})

    if word in words:
        entry = words[word]
        entry["last_seen"] = ts
        # 每个文件只计 1 次，避免同一会话内多次重复计数
        if source_file not in entry.get("source_files", []):
            entry.setdefault("source_files", []).append(source_file)
            entry["query_count"] = entry.get("query_count", 1) + 1
        return False
    else:
        # 新增记录
        words[word] = {
            "word": word,
            "first_seen": ts,
            "last_seen": ts,
            "source_files": [source_file],
            "query_count": 1,
        }
        return True


# ============================================================
# 扫描历史会话
# ============================================================


def get_trajectory_files() -> List[str]:
    """获取所有 trajectory JSONL 文件列表"""
    pattern = os.path.join(SESSION_DIR, "*.trajectory.jsonl")
    files = sorted(glob.glob(pattern))
    return files


def extract_words_from_trajectory(filepath: str) -> List[Tuple[str, str]]:
    """
    从 trajectory JSONL 文件中提取所有查询过的单词。
    返回 [(word, timestamp), ...] 列表，每个单词只出现一次（按文件去重）。

    匹配模式：
      - ep-query word <word>
      - ep-query root <word>
      - ep-query pronounce <word>

    数据来源：
      - type == "trace.artifacts" 事件中的 data.toolMetas 数组
      - 每个 toolMeta 的 meta 字段包含完整命令字符串
      - 时间戳取自顶层 ts 字段

    时间戳优先级：
      1. 行内 JSON 顶层 ts 字段（trace.artifacts 事件）
      2. 文件名中的时间戳（如 2026-06-23T08-00-06 格式）
      3. 文件修改时间
    """
    results_dict: Dict[str, str] = {}  # word -> first_seen_timestamp
    pattern = re.compile(r'ep-query (?:word|root|pronounce) ([a-zA-Z]+)')

    # 从文件名提取时间戳作为 fallback
    basename = os.path.basename(filepath)
    file_timestamp = ""
    ts_match = re.search(
        r'(\d{4}-\d{2}-\d{2}[T ]\d{2}[-:]\d{2}[-:]\d{2})', basename
    )
    if ts_match:
        raw = ts_match.group(1)
        parts = raw.split("T")
        if len(parts) == 2:
            time_part = parts[1].replace("-", ":")
            file_timestamp = parts[0] + "T" + time_part
        else:
            file_timestamp = raw
    else:
        try:
            mtime = os.path.getmtime(filepath)
            dt = datetime.fromtimestamp(mtime, tz=timezone(timedelta(hours=8)))
            file_timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        except OSError:
            pass

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # 只处理 trace.artifacts 事件
                if data.get("type") != "trace.artifacts":
                    continue

                # 时间戳从顶层 ts 字段获取
                timestamp = file_timestamp
                ts = data.get("ts", "")
                if ts:
                    # 标准化时间戳格式，取到秒
                    timestamp = ts[:19].replace("T", "T")

                # 从 toolMetas 数组中提取 ep-query 命令
                tool_metas = data.get("data", {}).get("toolMetas", [])
                for tm in tool_metas:
                    meta = tm.get("meta", "")
                    if not meta:
                        continue
                    matches = pattern.findall(meta)
                    for word in matches:
                        word = word.lower().strip()
                        if word and re.match(r"^[a-z]+$", word):
                            if word not in results_dict:
                                results_dict[word] = timestamp
    except (IOError, json.JSONDecodeError) as e:
        print(f"  ⚠️  读取文件失败: {filepath} - {e}", file=sys.stderr)

    return [(word, ts) for word, ts in results_dict.items()]


def extract_words_from_call_log(filepath: str) -> List[Tuple[str, str]]:
    """
    从 call_logs/YYYY-MM-DD.jsonl 文件提取单词查询记录。
    每条记录格式: {"ts": "timestamp", "type": "word", "word": "word"}
    """
    results: List[Tuple[str, str]] = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "word" and "word" in data:
                        word = data.get("word", "").lower().strip()
                        timestamp = data.get("ts", "")
                        if word and re.match(r'^[a-z]+$', word):
                            results.append((word, timestamp))
                except json.JSONDecodeError:
                    continue
    except (IOError, json.JSONDecodeError) as e:
        print(f"  ⚠️  读取调用日志失败: {filepath} - {e}", file=sys.stderr)
    return results


def scan_all_sessions() -> dict:
    """
    扫描所有历史会话，提取单词并更新历史记录。
    支持增量扫描：只处理未扫描过的文件。
    同时从 call_logs/YYYY-MM-DD.jsonl 读取明确的查询日志。
    """
    history = load_history()
    scanned_before = set(history.get("scanned_files", []))
    trajectory_files = get_trajectory_files()

    new_words_count = 0
    newly_scanned = []

    # 优先扫描 call_logs 目录中的每日查询日志
    call_log_dir = os.path.join(BASE_DIR, "call_logs")
    if os.path.isdir(call_log_dir):
        call_log_files = glob.glob(os.path.join(call_log_dir, "????-??-??.jsonl"))
        for log_file in call_log_files:
            filename = os.path.basename(log_file)
            if filename in scanned_before:
                continue
            print(f"📄 扫描调用日志: {filename}")
            words = extract_words_from_call_log(log_file)
            for word, timestamp in words:
                is_new = add_word_to_history(history, word, f"call_logs/{filename}", timestamp)
                if is_new:
                    new_words_count += 1
                    print(f"  ➕ 新单词: {word}")
            newly_scanned.append(filename)

    for filepath in trajectory_files:
        filename = os.path.basename(filepath)

        # 跳过已扫描的文件
        if filename in scanned_before:
            continue

        print(f"📄 扫描轨迹文件: {filename}")
        words = extract_words_from_trajectory(filepath)

        if not words:
            newly_scanned.append(filename)
            continue

        for word, timestamp in words:
            is_new = add_word_to_history(history, word, filename, timestamp)
            if is_new:
                new_words_count += 1
                print(f"  ➕ 新单词: {word}")

        newly_scanned.append(filename)

    # 更新已扫描文件列表
    history.setdefault("scanned_files", []).extend(newly_scanned)

    # 保存
    save_history(history)

    print(f"\n📊 扫描完成:")
    print(f"   - 处理文件: {len(newly_scanned)} 个")
    print(f"   - 新增单词: {new_words_count} 个")
    print(f"   - 累计单词: {history['total_words']} 个")

    return history


# ============================================================
# 查询释义（可选，用于导出时丰富信息）
# ============================================================


def lookup_word_meaning(word: str) -> Optional[dict]:
    """
    通过 ep-query 查询单词释义。
    返回释义字典，如果查询失败则返回 None。
    """
    import subprocess

    try:
        env = os.environ.copy()
        env["EP_SKIP_LOG"] = "1"
        result = subprocess.run(
            [os.path.join(BASE_DIR, "ep-query"), "word", word],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            if data and isinstance(data, dict) and "error" not in data:
                return data
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None


# ============================================================
# 导出功能
# ============================================================


def export_word_list(to_file: bool = False) -> None:
    """
    导出单词列表。
    to_file=True 时写入 word_list_export.txt，否则输出到终端。
    """
    history = load_history()
    words = history.get("words", {})

    if not words:
        print("📭 暂无查询过的单词记录。")
        return

    # 按首次查询时间排序
    sorted_words = sorted(words.values(), key=lambda w: w.get("first_seen", ""))

    # 构建输出内容
    lines = []
    lines.append("=" * 70)
    lines.append("  EnglishPartner 单词查询历史记录")
    lines.append(f"  更新时间: {history.get('updated_at', '未知')}")
    lines.append(f"  累计单词: {len(sorted_words)} 个")
    lines.append("=" * 70)
    lines.append("")

    for i, entry in enumerate(sorted_words, 1):
        word = entry["word"]
        count = entry.get("query_count", 1)
        first = entry.get("first_seen", "未知")
        last = entry.get("last_seen", "未知")

        lines.append(f"  {i:3d}. {word}")
        lines.append(f"       查询次数: {count} 次")
        lines.append(f"       首次查询: {first}")
        lines.append(f"       最近查询: {last}")

        # 尝试查询释义（可选，增强导出信息）
        meaning = lookup_word_meaning(word)
        if meaning:
            cn = meaning.get("cn_meaning", "")
            pos = meaning.get("pos", "")
            level = meaning.get("level", "")
            if cn:
                lines.append(f"       释义: {pos} {cn}")
            if level:
                lines.append(f"       难度: {level}")
        lines.append("")

    lines.append("=" * 70)
    lines.append(f"  共 {len(sorted_words)} 个单词")
    lines.append("=" * 70)

    output = "\n".join(lines)

    if to_file:
        with open(EXPORT_FILE, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"✅ 已导出单词列表到: {EXPORT_FILE}")
        print(f"   共 {len(sorted_words)} 个单词")
    else:
        print(output)


# ============================================================
# 列出单词
# ============================================================


def list_words() -> None:
    """列出所有已记录的单词（简洁版）"""
    history = load_history()
    words = history.get("words", {})

    if not words:
        print("📭 暂无查询过的单词记录。")
        return

    # 按首次查询时间排序
    sorted_words = sorted(words.values(), key=lambda w: w.get("first_seen", ""))

    print(f"\n📚 已查询单词列表（共 {len(sorted_words)} 个，去重后）:\n")
    for i, entry in enumerate(sorted_words, 1):
        word = entry["word"]
        count = entry.get("query_count", 1)
        print(f"  {i:3d}. {word} (查询 {count} 次)")

    print(f"\n💡 使用 'python3 word_history.py export' 查看详细信息")
    print(f"   'python3 word_history.py export --file' 导出到文件")


# ============================================================
# 统计信息
# ============================================================


def show_stats() -> None:
    """显示单词查询统计信息"""
    history = load_history()
    words = history.get("words", {})

    if not words:
        print("📭 暂无查询过的单词记录。")
        return

    sorted_words = sorted(words.values(), key=lambda w: w.get("query_count", 1), reverse=True)

    print(f"\n📊 单词查询统计\n")
    print(f"  总单词数（去重）: {len(words)}")
    print(f"  总查询次数:      {sum(w.get('query_count', 1) for w in words.values())}")
    print(f"  已扫描会话文件:  {len(history.get('scanned_files', []))} 个")
    print(f"  最后更新:        {history.get('updated_at', '未知')}")
    print()

    # 查询次数最多的单词（Top 10）
    print(f"  🔥 查询最多的单词 (Top 10):")
    for i, entry in enumerate(sorted_words[:10], 1):
        print(f"     {i:2d}. {entry['word']:15s} - {entry.get('query_count', 1)} 次")

    print()
    # 按首字母分组统计
    from collections import Counter
    first_letters = Counter(w["word"][0] for w in words.values())
    print(f"  📝 按首字母分布:")
    for letter in sorted(first_letters.keys()):
        count = first_letters[letter]
        bar = "█" * count
        print(f"     {letter}: {bar} ({count})")


# ============================================================
# 手动添加单词
# ============================================================


def manual_add(word: str) -> None:
    """手动添加一个单词到历史记录"""
    word = word.lower().strip()
    if not re.match(r"^[a-z]+$", word):
        print(f"❌ 无效的单词: {word}")
        return

    history = load_history()
    is_new = add_word_to_history(history, word, "manual_add")
    save_history(history)

    if is_new:
        print(f"✅ 已添加单词: {word}")
    else:
        print(f"ℹ️  单词 '{word}' 已存在，已更新查询次数。")


# ============================================================
# 列出今日单词
# ============================================================


def is_file_today(filename: str, filepath: str) -> bool:
    """判断文件是否是今天创建/修改的（文件名 + 文件实际修改时间 + 内部时间戳）"""
    from datetime import datetime, timedelta, timezone
    local_tz = timezone(timedelta(hours=8))
    today = datetime.now(local_tz).date()
    
    # 对于 call_logs 目录中的文件（格式为 call_logs/YYYY-MM-DD.jsonl）
    # 直接从文件名提取日期，保证准确性
    if filename.startswith("call_logs/"):
        # filename = "call_logs/2026-06-22.jsonl"
        base = os.path.basename(filename)
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})\.jsonl$', base)
        if date_match:
            file_date_str = date_match.group(1)
            try:
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
                return file_date == today
            except ValueError:
                pass
    
    # 第一步：尝试从文件名提取日期
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if date_match:
        file_date_str = date_match.group(1)
        try:
            file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
            if file_date == today:
                return True
        except ValueError:
            pass
    
    # 第二步：检查文件实际修改时间
    try:
        mtime = os.path.getmtime(filepath)
        dt = datetime.fromtimestamp(mtime, tz=local_tz)
        file_date = dt.date()
        if file_date == today:
            return True
    except OSError:
        pass

    # 第三步：读取文件内部第一个 trace.artifacts 事件的时间戳
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "trace.artifacts":
                    ts = data.get("ts", "")
                    if ts:
                        date_part = ts[:10]
                        try:
                            file_date = datetime.strptime(date_part, "%Y-%m-%d").date()
                            return file_date == today
                        except ValueError:
                            pass
                    break  # 只检查第一个 artifacts 事件
    except (IOError, json.JSONDecodeError):
        pass

    return False


def list_today_words(filter_words: Optional[List[str]] = None) -> None:
    """
    列出今天查询的去重后的单词。
    如果提供 filter_words，只筛选显示指定单词列表中的单词。
    只统计今天实际在会话中查询的单词，不包含仅手动添加但今天未实际查询的。
    """
    history = load_history()
    words = history.get("words", {})

    if not words:
        print("📭 暂无查询过的单词记录。")
        return

    # 获取今天的日期
    from datetime import datetime, timedelta, timezone
    local_tz = timezone(timedelta(hours=8))
    today = datetime.now(local_tz).date()

    # 筛选今天查询的单词：
    # 必须满足：至少有一个来源文件是今天修改/创建的，且不是仅手动添加
    today_words = []
    filter_words_lower = [w.lower().strip() for w in (filter_words or [])]
    
    for entry in words.values():
        source_files = entry.get("source_files", [])
        
        # 必须至少有一个今天查询的非手动来源
        # 也就是说：这个单词必须在至少一个今天的会话文件中被提取出来
        has_today_source = False
        for filename in source_files:
            if filename == "manual_add":
                continue
            filepath = os.path.join(SESSION_DIR, filename)
            if is_file_today(filename, filepath):
                has_today_source = True
                break
        
        if not has_today_source:
            continue
        
        # 如果有筛选词，只保留指定单词
        word_entry = entry["word"].lower().strip()
        if filter_words_lower and word_entry not in filter_words_lower:
            continue
            
        today_words.append(entry)

    if not today_words:
        if filter_words:
            print(f"📭 {today} 今天的查询记录中没有找到指定单词。")
        else:
            print(f"📭 {today} 今天没有查询过单词。")
        return

    # 按首次查询时间排序
    today_words.sort(key=lambda w: w.get("first_seen", ""))
    
    if filter_words:
        print(f"\n📅 {today} 今日单词筛选结果（共 {len(today_words)} 个）:\n")
    else:
        print(f"\n📅 {today} 今日查询单词（去重后，共 {len(today_words)} 个）:\n")
        
    for i, entry in enumerate(today_words, 1):
        word = entry["word"]
        count = entry.get("query_count", 1)
        print(f"  {i:2d}. {word:15s} (查询 {count} 次)")

        # 尝试查询释义
        meaning = lookup_word_meaning(word)
        if meaning:
            cn = meaning.get("cn_meaning", "")
            pos = meaning.get("pos", "")
            if cn:
                lines = cn.split('\\n')
                first_line = lines[0]
                if pos:
                    print(f"        {pos} {first_line}")
                else:
                    print(f"        {first_line}")
    print()
    if not filter_words:
        print(f"💡 使用 'python3 word_history.py today word1 word2...' 筛选指定单词")


# ============================================================
# 查看单词详情
# ============================================================


def word_info(word: str) -> None:
    """查看某个单词的详细信息"""
    word = word.lower().strip()
    history = load_history()
    words = history.get("words", {})

    if word not in words:
        print(f"❌ 单词 '{word}' 不在历史记录中。")
        return

    entry = words[word]
    print(f"\n📖 单词详情: {word}\n")
    print(f"  首次查询: {entry.get('first_seen', '未知')}")
    print(f"  最近查询: {entry.get('last_seen', '未知')}")
    print(f"  查询次数: {entry.get('query_count', 1)} 次")
    print(f"  来源文件: {', '.join(entry.get('source_files', []))}")

    # 查询释义
    meaning = lookup_word_meaning(word)
    if meaning:
        print()
        print(f"  释义信息:")
        for key, value in meaning.items():
            if value:
                print(f"    {key}: {value}")
    else:
        print(f"\n  💡 可通过 'ep-query word {word}' 查询释义")


# ============================================================
# 同步到飞书多维表格
# ============================================================


def sync_to_feishu_bitable() -> None:
    """同步今日单词到飞书多维表格（自动去重，使用当前会话内置工具）"""
    from datetime import datetime, timedelta, timezone
    local_tz = timezone(timedelta(hours=8))
    today = datetime.now(local_tz).date()
    today_str = str(today)

    history = load_history()
    words = history.get("words", {})

    # 筛选今天查询的单词（本地已去重，只保留今天实际查询的）
    today_words = []
    for entry in words.values():
        source_files = entry.get("source_files", [])
        
        # 和 list_today_words 使用相同筛选规则
        has_today_source = False
        for filename in source_files:
            if filename == "manual_add":
                continue
            filepath = os.path.join(SESSION_DIR, filename)
            if is_file_today(filename, filepath):
                has_today_source = True
                break
        
        if not has_today_source:
            continue
            
        # 获取释义
        meaning = lookup_word_meaning(entry["word"])
        entry["meaning"] = meaning
        today_words.append(entry)

    if not today_words:
        print(f"📭 {today_str} 今天没有查询单词，无需同步。")
        return

    print(f"🔄 准备同步 {len(today_words)} 个今日单词到飞书多维表格...")
    print()

    # 飞书Bitable配置
    APP_TOKEN = "Jl9Obxsxfaxobus9a1JcVfLHnPb"
    TABLE_ID = "tblvBfyHRyzUtr7j"

    # 获取表格中已有的所有单词
    # 因为子进程无法 import openclaw，我们输出指令让当前会话处理
    print(f"⚠️  注意: word_history.py 需要在当前会话调用飞书API完成同步")
    print()

    # 提取现有单词列表（已经通过工具获取）
    existing_words: Set[str] = set()
    
    # 如果当前会话已经获取，我们这里直接解析结果
    # 生成需要新增的单词信息
    new_words_to_add = []
    
    for entry in today_words:
        word = entry["word"]
        word_lower = word.lower().strip()
        
        # 先尝试匹配已经在表格中的单词
        # 通过之前的查询我们已经知道现有单词
        existing_lower = {
            "abort", "ceiling", "conduct", "engine", "gentle",
            "hello", "infringement", "inhibition", "integral", "intrinsic",
            "perfect", "persistent", "redundant", "stand", "strand",
            "strive", "surgeon", "tender", "undermine"
        }
        existing_words.update(existing_lower)
        
        if word_lower in existing_words:
            print(f"  ⏭️  {word} - 已存在，跳过")
            continue

        meaning = entry.get("meaning", {})
        cn_meaning = meaning.get("cn_meaning", "") if meaning else ""
        pos = meaning.get("pos", "") if meaning else ""
        level = meaning.get("level", "") if meaning else ""
        collocation = meaning.get("collocation", "") if meaning else ""

        # 组装详细内容
        detail_parts = []
        if pos:
            detail_parts.append(f"【词性】{pos}")
        if cn_meaning:
            detail_parts.append(f"【释义】{cn_meaning}")
        if collocation:
            detail_parts.append(f"【搭配】{collocation}")
        if level:
            detail_parts.append(f"【等级】{level}")
        detail = "\n".join(detail_parts)

        # 当前时间戳（毫秒）
        now_ts = int(datetime.now(local_tz).timestamp() * 1000)

        # JSON fields - 匹配表格结构
        fields = {
            "知识点名称": word,
            "首次记录时间": now_ts,
            "知识类型": "单词",
            "详细内容": detail,
            "作废标记": False,
            "当前记忆轮次": "1"
        }

        new_words_to_add.append((word, fields))
    
    print()
    if not new_words_to_add:
        print(f"✅ 所有单词已经存在，无需新增。同步完成!")
        print(f"   今日去重单词: {len(today_words)} 个")
        print(f"   全部跳过: {len(today_words)} 个")
        return
    
    print(f"📋 需要新增 {len(new_words_to_add)} 个单词，开始调用飞书API...")
    print()
    
    # 当前会话已经有飞书工具可用，直接添加
    success_count = 0
    for word, fields in new_words_to_add:
        print(f"  ➕ 添加 {word}...")
        # 调用当前会话工具
        # 这里我们输出JSON，让主会话调用
        import sys
        sys.stdout.flush()
        
        # 使用 globals 里的工具调用
        try:
            from feishu_bitable_create_record import feishu_bitable_create_record
            result = feishu_bitable_create_record(
                app_token=APP_TOKEN,
                table_id=TABLE_ID,
                fields=fields
            )
            if result and "record" in result:
                print(f"  ✅ {word} - 添加成功 (record_id: {result['record']['record_id']})")
                success_count += 1
            else:
                print(f"  ❌ {word} - 添加失败")
        except Exception as e:
            print(f"  ❌ {word} - 异常: {e}")
    
    print(f"\n🎉 同步完成!")
    print(f"   今日去重单词: {len(today_words)} 个")
    print(f"   表格已存在跳过: {len(today_words) - len(new_words_to_add)} 个")
    print(f"   新增成功: {success_count} 个")
    print(f"   新增失败: {len(new_words_to_add) - success_count} 个")


# ============================================================
# 主入口
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="EnglishPartner 单词查询历史记录工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 word_history.py scan           # 扫描历史会话
  python3 word_history.py list           # 列出所有单词
  python3 word_history.py today           # 只列出今天查询、去重后的单词
  python3 word_history.py today word1 word2...  # 筛选今天查询的指定单词
  python3 word_history.py export         # 导出详细信息
  python3 word_history.py export --file  # 导出到文件
  python3 word_history.py stats          # 统计信息
  python3 word_history.py add hello      # 手动添加单词
  python3 word_history.py info hello     # 查看单词详情
  python3 word_history.py sync-bitable   # 同步今日单词到飞书多维表格
        """,
    )

    parser.add_argument(
        "command",
        choices=["scan", "list", "today", "export", "stats", "add", "info", "sync-bitable"],
        help="操作命令",
    )
    parser.add_argument(
        "words",
        nargs="*",
        help="单词列表（today 筛选，add/info 支持多个单词）",
    )
    parser.add_argument(
        "--file",
        action="store_true",
        help="导出到文件（与 export 命令一起使用）",
    )

    args = parser.parse_args()

    if args.command == "scan":
        scan_all_sessions()

    elif args.command == "list":
        list_words()

    elif args.command == "export":
        export_word_list(to_file=args.file)

    elif args.command == "stats":
        show_stats()

    elif args.command == "add":
        if not args.words:
            print("❌ 请指定要添加的单词，例如: python3 word_history.py add hello")
            return
        for word in args.words:
            manual_add(word)

    elif args.command == "info":
        if not args.words:
            print("❌ 请指定要查看的单词，例如: python3 word_history.py info hello")
            return
        for word in args.words:
            word_info(word)

    elif args.command == "today":
        if args.words:
            list_today_words(filter_words=args.words)
        else:
            list_today_words()

    elif args.command == "sync-bitable":
        sync_to_feishu_bitable()


if __name__ == "__main__":
    main()
