#!/usr/bin/env python3
"""将 split/xxx/index.json 压缩为 index_compact.json（两段式紧凑格式）"""

import json
import os

LIBS = ["word", "pronounce", "root"]
SPLIT_BASE = "datas/split"


def build_compact(lib_name):
    idx_path = os.path.join(SPLIT_BASE, lib_name, "index.json")
    out_path = os.path.join(SPLIT_BASE, lib_name, "index_compact.json")

    if not os.path.exists(idx_path):
        print(f"  ⚠️ {idx_path} 不存在，跳过")
        return

    with open(idx_path, "r", encoding="utf-8") as f:
        idx = json.load(f)

    # 文件名去重编号
    file_names = sorted(set(idx.values()))
    fn_map = {fn: i for i, fn in enumerate(file_names)}

    # 排序条目（可选，方便 diff）
    entries = sorted([[k, fn_map[v]] for k, v in idx.items()])

    compact = {"f": file_names, "e": entries}

    # 紧凑输出（无多余空格）
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(compact, f, separators=(",", ":"), ensure_ascii=False)

    orig_size = len(json.dumps(idx, separators=(",", ":"), ensure_ascii=False))
    new_size = os.path.getsize(out_path)
    print(f"  ✅ {lib_name}: {orig_size/1e6:.1f}MB → {new_size/1e6:.1f}MB "
          f"(节省 {(1-new_size/orig_size)*100:.1f}%)")


if __name__ == "__main__":
    for lib in LIBS:
        build_compact(lib)
    print("\n🎉 全部紧凑索引生成完成")
