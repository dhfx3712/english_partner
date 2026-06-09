import json
import os
import time

# ===================== OpenClaw 智能体核心 =====================
# 索引：按需懒加载（查哪个库才加载哪个）
INDEXES = {}

# 缓存：{ 路径: { "data": ..., "time": 时间戳 } }
CACHE = {}
CACHE_EXPIRE_SECONDS = 300  # 300秒无访问自动释放内存


# 1. 按需加载索引，优先紧凑版 index_compact.json
def load_index(lib_name):
    # 尝试紧凑版
    path = f"datas/split/{lib_name}/index_compact.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            compact = json.load(f)
        # 恢复为 {word: filename} 字典
        file_names = compact["f"]
        entries = compact["e"]
        return {entry[0]: file_names[entry[1]] for entry in entries}
    except:
        pass

    # 降级到旧版
    path = f"datas/split/{lib_name}/index.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


# ===================== 智能体调度 =====================
def get_index(lib_name: str) -> dict:
    """按需获取索引，首次使用才加载"""
    if lib_name not in INDEXES:
        INDEXES[lib_name] = load_index(lib_name)
    return INDEXES[lib_name]


def get_file_by_word(lib_name: str, word: str):
    word = word.lower().strip()
    return get_index(lib_name).get(word)


def clean_expired_cache():
    """清理过期缓存，自动释放内存"""
    now = time.time()
    expired = [k for k, v in CACHE.items() if now - v["time"] > CACHE_EXPIRE_SECONDS]
    for k in expired:
        del CACHE[k]


def load_lib_file(lib_name: str, filename: str):
    if not filename:
        return None

    path = f"datas/split/{lib_name}/{filename}"

    # 自动清理过期文件
    clean_expired_cache()

    # 缓存未过期 → 直接用
    if path in CACHE:
        CACHE[path]["time"] = time.time()
        return CACHE[path]["data"]

    # 缓存不存在 → 加载
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        CACHE[path] = {"data": data, "time": time.time()}
        return data
    except:
        return None


# ===================== 你原有 OpenClaw 查询函数（完全不变） =====================
def get_word_data(word: str):
    fn = get_file_by_word("word", word)
    data = load_lib_file("word", fn)
    if not data:
        return {}
    for item in data:
        if item.get("word", "").lower() == word.lower():
            return item
    return {}


def get_pronounce_data(word: str):
    fn = get_file_by_word("pronounce", word)
    data = load_lib_file("pronounce", fn)
    if not data:
        return {}
    for item in data:
        if item.get("word", "").lower() == word.lower():
            return item
    return {}


def get_root_data(word: str):
    fn = get_file_by_word("root", word)
    data = load_lib_file("root", fn)
    if not data:
        return {}
    for item in data:
        if item.get("word", "").lower() == word.lower():
            return item
    return {}
