# 单词召回 & 造句模块架构

## 一、整体架构

```
用户输入单词 "effect"
        │
        ▼
┌─────────────────────────────────────┐
│          Recall Engine              │
│  (recall.py)                        │
│                                     │
│  ① C标签精确匹配 ──── 命中 → 最高优先级 │
│  ② 搭配映射匹配 ──── 命中 → 高优先级   │
│  ③ F场景批量召回 ──── 命中 → 中优先级   │
│  ④ 核心句型模糊匹配 ── 命中 → 低优先级   │
│  ⑤ 语义兜底 ──────── 通用句型           │
└──────────────┬──────────────────────┘
               │ 召回结果：[(sid, score, match_type), ...]
               ▼
┌─────────────────────────────────────┐
│        Sentence Builder             │
│  (builder.py)                       │
│                                     │
│  可模板化？──是──→ 本地填空生成（0 token）│
│              │                      │
│              └──否──→ AI Prompt 生成   │
└─────────────────────────────────────┘
               │
               ▼
        格式化输出
```

## 二、数据层

### 2.1 索引文件 (`index_data.json`)

由 `build_index.py` 从 `句型.md` 自动构建，包含：

| 索引 | 结构 | 用途 |
|------|------|------|
| `c_index` | C标签 → [句型列表] | C标签精确匹配 |
| `f_index` | F标签 → [句型列表] | 场景批量召回 |
| `g_index` | G标签 → [句型列表] | 语法点批量召回 |
| `collocation_map` | 搭配短语 → [C标签列表] | 搭配映射匹配 |
| `word_to_f` | 单词 → [F标签列表] | 单词→场景映射 |
| `all_patterns` | SID → 句型完整信息 | 最终输出查询 |

### 2.2 模板规则 (`templates.json`)

定义哪些句型可以本地填空生成（0 token），以及填空规则：

```json
{
  "S089": {
    "template": "I suggest that you ___.",
    "type": "verb_phrase",
    "slot_pos": "after_that",
    "grammar": "虚拟语气，动词用原形"
  },
  "S063": {
    "template": "I believe that ___ has a ___ effect on ___.",
    "type": "multi_slot",
    "slots": ["noun_phrase", "adjective", "noun_phrase"]
  }
}
```

## 三、召回流程（recall.py）

### 3.1 输入
- `word`: 用户输入的单词（如 "effect"）
- `pos` (可选): 词性（n/v/adj/adv）
- `difficulty` (可选): 目标难度 L001-L006
- `limit` (可选): 最大返回句型数，默认 5

### 3.2 召回步骤

```
Step 1: C标签精确匹配
  ├── 查 word_to_c[word] → 直接命中 C 标签
  ├── 查 collocation_map 中的包含匹配
  │    如 "effect" → "have an effect on" → [C063, C218, ...]
  └── 得分: 100

Step 2: F场景批量匹配
  ├── 查 word_to_f[word] → 获得 F 标签列表
  ├── 通过 f_index 批量召回句型
  └── 得分: 70

Step 3: 核心句型模糊匹配
  ├── 对 pattern_en 做分词 + 去停用词
  ├── 计算单词与 pattern 的 Jaccard 相似度
  └── 得分: 50 * similarity

Step 4: 语义兜底
  ├── 按词性推荐通用句型
  ├── 按难度筛选
  └── 得分: 30
```

### 3.3 去重 & 排序

```
合并所有召回结果 → 按 SID 去重 → 按得分降序 → 取 top N
```

## 四、造句引擎（builder.py）

### 4.1 模板填空（0 token）

```
输入: word="effect", sid="S063", pattern="I believe that..."
     ↓
查 templates.json → S063 有模板定义
     ↓
替换填空位 → "I believe that reading has a positive effect on writing."
     ↓
输出: 0 token 消耗
```

**可模板化条件：**
- 句型有固定框架（建议类、观点类、条件句等）
- 填空位是名词短语、动词原形、形容词等简单成分
- 无需处理复杂时态/语态变化

### 4.2 AI 生成（压缩 prompt）

```
输入: word="effect", sid="S167", pattern="It is believed that..."
     ↓
无模板定义 → 走 AI
     ↓
构建压缩 prompt:
  word=effect | pattern="It is believed that..." | scene=environment | n=2
     ↓
AI 返回:
  - It is believed that the new policy will take effect next month.
  - It is believed that this medicine has a positive effect on patients.
     ↓
输出: ~50 tokens
```

## 五、调用接口

### Python 调用

```python
from recall import RecallEngine
from builder import SentenceBuilder

engine = RecallEngine("index_data.json")
builder = SentenceBuilder("templates.json")

# 召回
results = engine.recall("effect", limit=5)
# → [("S063", 100, "collocation"), ("S218", 100, "collocation"), ...]

# 造句
sentences = builder.build("effect", results)
# → [{"sid": "S063", "text": "I believe that...", "cost": 0}, ...]
```

### CLI 调用

```bash
python recall.py effect
# 输出召回结果 + 造句
```

## 六、文件清单

| 文件 | 用途 |
|------|------|
| `build_index.py` | 从 句型.md 构建 index_data.json |
| `index_data.json` | 预构建的索引数据 |
| `templates.json` | 可模板化句型的填空规则 |
| `recall.py` | 召回引擎 |
| `builder.py` | 造句引擎（模板 + AI） |
| `recall_architecture.md` | 本文档 |
