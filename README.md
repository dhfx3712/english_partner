# EnglishPartner

英语学习伙伴 · 智能离线词典 + 词根教练 + 发音指导 + 语法解析

基于 OpenClaw 架构运行，全离线、零外部依赖。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt  # 如有

# 2. 构建数据（从大 JSON 拆分为小文件）
venv/bin/python3 split_all_libs.py

# 3. 生成紧凑索引
venv/bin/python3 build_compact_index.py

# 4. 启动守护进程
venv/bin/python3 query_engine.py daemon

# 5. 测试查询
venv/bin/python3 query_engine.py word hello
venv/bin/python3 query_engine.py root conduct
venv/bin/python3 query_engine.py pronounce hello
```

## 查询单词

```bash
ep-query word <单词>       # 查释义
ep-query root <单词>       # 查词根
ep-query pronounce <单词>  # 查发音
ep-query grammar <句子>    # 语法分析
```

## 守护进程管理

```bash
venv/bin/python3 query_engine.py status   # 查看状态
venv/bin/python3 query_engine.py stop     # 停止
```

首次查询会自动启动守护进程，无需手动操作。

## 安全加固

```bash
bash scripts/apply_security.sh
```

## 数据源

- 英汉词库：ECDICT
- 词根词缀：开源中文词根数据集
- 发音音标：cmudict
- 语法规则：本地正则引擎（零 Token 消耗）

## 环境要求

- Python 3.10+
- OpenClaw v0.5.x
- Linux
- 磁盘 1GB+ / 内存 512MB+
