#!/usr/bin/env python3
"""
统一查询入口：供 OpenClaw local_script Skill 调用。
用法：query_engine.py <lib_type> <word>
  lib_type: word | root | pronounce
  word: 待查询的英文单词（自动处理大小写）
输出：JSON 字符串（查询到数据则输出该条记录，否则 {}）
"""

import sys
import json
from query_utils import get_word_data, get_pronounce_data, get_root_data

MAPPING = {
    "word": get_word_data,
    "root": get_root_data,
    "pronounce": get_pronounce_data,
}

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({}))
        sys.exit(1)

    lib_type = sys.argv[1].strip().lower()
    word = sys.argv[2].strip().lower()

    fetcher = MAPPING.get(lib_type)
    if not fetcher:
        print(json.dumps({}))
        sys.exit(1)

    result = fetcher(word)
    print(json.dumps(result, ensure_ascii=False))
