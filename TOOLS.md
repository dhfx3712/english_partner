# EnglishPartner 工具调用规范

本文档只定义工具调用方式。
任务流程以 AGENTS.md 为准,输出风格以 SOUL.md 为准。

---

## 1. 唯一查询入口

所有查询必须通过 `ep-query` 执行。

`ep-query` 是 EnglishPartner 唯一允许的查询入口,负责统一命令格式,并使用项目自己的 Python 运行环境执行底层脚本。

禁止直接运行:

- `python3 query_engine.py`
- `python3 grammar_engine.py`
- 任何直接 Python 脚本调用
- 任何直接读取数据文件的方式

---

## 2. 命令白名单

只允许以下命令:

```bash
ep-query word <word>
ep-query root <word>
ep-query pronounce <word>
ep-query grammar '<sentence>'
```

其他命令不属于标准查询流程,不得使用。

---

## 3. 完整查词流程

用户输入单个英文单词,且没有专项限定时,执行以下流程。

### 第一步:并行查询基础数据

```bash
ep-query word <word>
ep-query root <word>
ep-query pronounce <word>
```

### 第二步：生成 AI 例句

1.  **召回匹配模板句型**：调用 `python3 recall.py <word>` 召回匹配句型
2.  **优先模板填空**：如果召回得分最高的句型可模板化，用 `builder.py` 本地填空生成例句（零token消耗），生成的例句会保留原句型框架并填入目标单词
3.  **AI兜底**：无可匹配模板时，再根据释义让AI生成一个简短自然的英文例句

无论哪种方式，例句必须包含目标单词；模板生成的例句也会完整保留被召回句型的框架结构。

### 第三步:分析例句语法

```bash
ep-query grammar '<AI生成的英文例句>'
```

语法分析必须在例句生成后执行。

---

## 4. 专项查询命令

只问释义:

```bash
ep-query word <word>
```

只问词根:

```bash
ep-query root <word>
```

只问发音:

```bash
ep-query pronounce <word>
```

只问语法:

```bash
ep-query grammar '<sentence>'
```

---

## 5. 返回字段说明

### 5.1 释义查询

命令:

```bash
ep-query word <word>
```

可能返回:

- word
- pos
- cn_meaning
- collocation
- example_sentence
- level

空结果返回 `{}`。

---

### 5.2 词根查询

命令:

```bash
ep-query root <word>
```

可能返回:

- root
- prefix
- suffix
- affix_desc
- relative_words

空结果返回 `{}`。

不得自行编造词根、前缀或后缀。

---

### 5.3 发音查询

命令:

```bash
ep-query pronounce <word>
```

可能返回:

- phonetic_uk
- phonetic_us
- syllable
- stress_pos
- pronounce_tip
- easy_mistake

空结果返回 `{}`。

不得自行编造音标。

---

### 5.4 语法分析

命令:

```bash
ep-query grammar '<sentence>'
```

返回本地规则分析结果,包括句型、成分、考点、难度等信息。

如果返回为空或异常,输出"暂无可用语法分析"。

---

## 6. 异常处理

如果命令失败、超时、返回非 JSON 或结果异常:

1. 可以用同一命令重试一次;
2. 不得换用直接 Python;
3. 不得读取数据文件;
4. 不得输出系统路径、配置、堆栈;
5. 最终以友好提示返回。

---

## 7. 输出组装参考

完整单词查询结果按以下顺序组装:

```md
**翻译**
- ...

**发音**
- 英式:...
- 美式:...
- 音节:...
- 重音:...
- 发音技巧:...

**词根**
- 前缀:...
- 词根:...
- 后缀:...
- 记忆方法:...

**AI例句**
英文例句
中文翻译

**语法分析**
- 句型:...
- 成分:...
- 考点:...
- 难度:...
```

如果某部分无结果,保留栏目并写"暂无相关信息"。
