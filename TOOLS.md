# 本地知识库工具
1. Skill_WordQuery
   - 功能：单词查询
   - 数据源：datas/word_lib.json
   - 字段：word, pos, cn_meaning, collocation, example_sentence

2. Skill_RootAnalyze
   - 功能：词根词缀解析
   - 数据源：datas/root_lib.json
   - 字段：root, prefix, suffix, affix_desc, relative_words

3. Skill_Pronounce
   - 功能：发音与拼读
   - 数据源：datas/pronounce_lib.json
   - 字段：phonetic_uk, phonetic_us, syllable, stress_pos, pronounce_tip

# 调用规则
- 全部小写匹配（word_lower）
- 优先精准匹配，无结果则模糊匹配
- 全部本地离线运行，无网络请求
