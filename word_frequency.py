#!/usr/bin/env python3
"""
word_frequency.py - 单词频率统计模块

功能：
- 输入一段英文文本，统计每个单词出现的次数
- 处理标点符号，将单词转为小写统一统计
- 按出现频率从高到低排序返回结果
"""

import re
from typing import List, Tuple


def clean_text(text: str) -> str:
    """去除标点符号，只保留字母、数字和空格"""
    # 将标点符号替换为空格
    cleaned = re.sub(r'[^\w\s\'-]', ' ', text)
    # 将连续空格合并为单个空格
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


def tokenize(text: str) -> List[str]:
    """将文本分词为单词列表，转为小写"""
    cleaned = clean_text(text)
    if not cleaned:
        return []
    return cleaned.lower().split()


def count_words(text: str) -> dict:
    """统计文本中每个单词出现的次数

    Args:
        text: 输入的英文文本

    Returns:
        dict: 单词 -> 出现次数
    """
    words = tokenize(text)
    freq = {}
    for word in words:
        freq[word] = freq.get(word, 0) + 1
    return freq


def sort_by_frequency(freq: dict, descending: bool = True) -> List[Tuple[str, int]]:
    """按频率排序

    Args:
        freq: 单词频率字典
        descending: 是否降序排列（默认 True）

    Returns:
        List[Tuple[str, int]]: 排序后的 (单词, 次数) 列表
    """
    return sorted(freq.items(), key=lambda x: x[1], reverse=descending)


def word_frequency(text: str) -> List[Tuple[str, int]]:
    """完整流程：输入文本 -> 统计 -> 按频率降序返回

    Args:
        text: 输入的英文文本

    Returns:
        List[Tuple[str, int]]: 按频率从高到低排序的 (单词, 次数) 列表
    """
    freq = count_words(text)
    return sort_by_frequency(freq)


def word_frequency_report(text: str) -> str:
    """生成可读的频率统计报告

    Args:
        text: 输入的英文文本

    Returns:
        str: 格式化的统计报告
    """
    results = word_frequency(text)
    if not results:
        return "（无有效单词）"

    total_words = sum(count for _, count in results)
    unique_words = len(results)

    lines = [f"总单词数: {total_words} | 不重复单词数: {unique_words}", ""]
    lines.append(f"{'单词':<20} {'次数':<6} {'占比'}")
    lines.append("-" * 40)

    for word, count in results:
        pct = f"{count / total_words * 100:.1f}%"
        lines.append(f"{word:<20} {count:<6} {pct}")

    return "\n".join(lines)


if __name__ == "__main__":
    # 测试用例
    test_text = (
        "Hello world! This is a test. Hello again, world! "
        "The quick brown fox jumps over the lazy dog. "
        "Hello, hello, hello! How many times can we say hello?"
    )

    print("=" * 50)
    print("单词频率统计测试")
    print("=" * 50)
    print(f"\n输入文本:\n{test_text}\n")

    results = word_frequency(test_text)
    print(f"\n统计结果 (按频率降序):")
    print("-" * 40)
    for word, count in results:
        print(f"  {word:<15} {count} 次")

    print("\n" + "=" * 50)
    print("详细报告:")
    print("=" * 50)
    print(word_frequency_report(test_text))

    # 边界测试
    print("\n" + "=" * 50)
    print("边界测试")
    print("=" * 50)

    # 空文本
    assert word_frequency("") == [], "空文本应返回空列表"
    print("  ✓ 空文本处理正确")

    # 只有标点
    assert word_frequency("!!! ??? ,,, ...") == [], "只有标点应返回空列表"
    print("  ✓ 纯标点文本处理正确")

    # 大小写统一
    result = word_frequency("Apple apple APPLE")
    assert len(result) == 1 and result[0][1] == 3, "大小写应统一统计"
    print("  ✓ 大小写统一统计正确")

    # 带数字
    result = word_frequency("test 123 test 456")
    assert dict(result) == {"test": 2, "123": 1, "456": 1}, "数字应保留"
    print("  ✓ 数字处理正确")

    # 单次文本
    result = word_frequency("hello")
    assert result == [("hello", 1)], "单次文本应正确统计"
    print("  ✓ 单次文本处理正确")

    print("\n" + "=" * 50)
    print("所有测试通过！")
    print("=" * 50)
