# 整体说明
本文档说明查询英文单词时，如何通过 `exec` 工具调用本地 Python 脚本来获取数据。
请**优先使用脚本命令**，不要自己写代码读取 JSON 文件。

---

## 一、查词命令 exec 模板
收到英文单词时，并发执行以下几个命令获取完整数据。

### 1. 单词释义（必有）
```bash
ep-query word <word>
```
- 返回 JSON，包含字段：word, pos, cn_meaning, collocation, example_sentence, level
- 数据源：datas/split/word/ 下的小文件（已拆分）
- 找不到时返回空对象 `{}`

### 2. 词根词缀（并行）
```bash
ep-query root <word>
```
- 返回 JSON，包含字段：root, prefix, suffix, affix_desc, relative_words
- 无数据时返回空对象 `{}`

### 3. 发音音标（并行）
```bash
ep-query pronounce <word>
```
- 返回 JSON，包含字段：phonetic_uk, phonetic_us, syllable, stress_pos, pronounce_tip, easy_mistake
- 无数据时返回空对象 `{}`

### 4. 例句语法分析（串行，需要先生成例句）
```bash
ep-query grammar '<AI生成的英文例句>'
```
- 返回标准结构化 JSON：句型、成分、考点、难度等
- 纯本地正则匹配，零 Token 消耗

### ⚠️ 安全规则
- **禁止**直接运行 `python3 query_engine.py`，只能通过 `ep-query` 调用
- **禁止**运行 `cat`、`ls`、`head`、`tail` 等文件/目录操作命令
- **禁止**读取任何配置文件

---

## 二、输出结果处理规则
1. **统一匹配规则**：所有单词检索均以小写基准，自动忽略大小写
2. **空数据处理**：脚本返回空 `{}` 时，统一展示「暂无相关信息」
3. **文件规范**：空内容统一使用空数组 `[]`/空字符串 `""`，无 null 值
4. **并发顺序**：1/2/3 可并发，4 需在生成例句后串行执行
5. **容错**：旧大文件（word_lib.json 等）已改名备份，不要再尝试读取

---

## 三、输出示例（insulation）
并发执行后汇总 JSON 结果，按以下格式组装回复：

```markdown
📖 **单词** /音标/ · 难度

**🔊 发音**
- 英式 /音标/
- 美式 /音标/
- 音节划分
- 重音位置
- 发音技巧
- ⚠️ 易错点

**📝 释义**
- 词性① 中文释义
- 词性② 中文释义
- 搭配①
- 搭配②

**🌱 词根记忆**
前缀 + 词根 + 后缀 → 构词逻辑
同源词：xxx

**💡 AI 例句**
例句原文
例句翻译

**📐 语法分析**
- 句型：xxx
- 成分：xxx
- 考点：xxx
- 难度：xxx
```
