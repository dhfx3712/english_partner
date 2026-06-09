import json
import os
import re
from collections import defaultdict

# 你的三个库
FILES = {
    "word": "datas/word_lib.json",
    "pronounce": "datas/pronounce_lib.json",
    "root": "datas/root_lib.json"
}

OUT_BASE = "datas/split"
MAX_PER_FILE = 600

# 只允许 小写字母 + 数字
ALLOW_PREFIX = re.compile(r'^[a-z0-9]+$')

def split_lib(lib_name, input_path):
    print(f"\n正在拆分：{input_path}")
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        print(f"⚠️ {input_path} 不存在或格式错误")
        return

    if not isinstance(data, list):
        print(f"⚠️ {lib_name} 不是列表格式，跳过")
        return

    out_dir = os.path.join(OUT_BASE, lib_name)
    os.makedirs(out_dir, exist_ok=True)

    temp_group = defaultdict(list)
    group_counter = defaultdict(int)
    groups = {}

    for item in data:
        if not isinstance(item, dict) or "word" not in item:
            continue

        word = str(item["word"]).strip().lower()
        if len(word) < 1:
            continue

        # 生成安全前缀（只取字母）
        if len(word) >= 2:
            prefix = word[:2]
        else:
            prefix = word[0]

        # 过滤非法字符（核心修复！）
        if not ALLOW_PREFIX.match(prefix):
            prefix = "___unknown"

        # 加入分组
        temp_group[prefix].append(item)

        # 满了就切分
        if len(temp_group[prefix]) >= MAX_PER_FILE:
            sub_key = f"{prefix}_{group_counter[prefix]}"
            groups[sub_key] = temp_group[prefix]
            temp_group[prefix] = []
            group_counter[prefix] += 1

    # 加入剩余数据
    for prefix, items in temp_group.items():
        if items:
            sub_key = f"{prefix}_{group_counter[prefix]}"
            groups[sub_key] = items

    # 生成索引和文件
    index_map = {}
    for sub_key, items in groups.items():
        fn = f"{sub_key}.json"
        fp = os.path.join(out_dir, fn)

        with open(fp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)

        for item in items:
            if "word" in item:
                index_map[str(item["word"]).lower()] = fn

    # 保存索引（标准版 + 紧凑版）
    idx_path = os.path.join(out_dir, "index.json")
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(index_map, f, ensure_ascii=False)

    # 紧凑版：文件名去重编号
    file_names = sorted(set(index_map.values()))
    fn_map = {fn: i for i, fn in enumerate(file_names)}
    entries = sorted([[w, fn_map[fn]] for w, fn in index_map.items()])
    compact = {"f": file_names, "e": entries}
    compact_path = os.path.join(out_dir, "index_compact.json")
    with open(compact_path, "w", encoding="utf-8") as f:
        json.dump(compact, f, separators=(",", ":"), ensure_ascii=False)

    print(f"✅ {lib_name} 拆分完成：{len(index_map)} 个单词")

if __name__ == "__main__":
    for name, path in FILES.items():
        try:
            split_lib(name, path)
        except Exception as e:
            print(f"❌ {name} 失败：{str(e)}")
    print("\n🎉 全部处理完成！")
