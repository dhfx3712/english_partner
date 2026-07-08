#!/usr/bin/env python3
"""
builder.py — 造句引擎

根据召回结果生成例句：
- 可模板化句型 → 本地填空生成（0 token）
- 不可模板化句型 → 输出压缩 Prompt 供 AI 生成

用法：
    python builder.py <word> [--limit N] [--difficulty L00X]
"""

import re
import json
import sys
import os
import random

# 当前目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class SentenceBuilder:
    """造句引擎"""

    def __init__(self, index_path=None, template_path=None):
        if index_path is None:
            index_path = os.path.join(BASE_DIR, 'index_data.json')
        if template_path is None:
            template_path = os.path.join(BASE_DIR, 'templates.json')

        with open(index_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.all_patterns = self.data['all_patterns']

        # 加载模板规则
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                self.templates = json.load(f)
        except FileNotFoundError:
            self.templates = {}

    def is_templatable(self, sid):
        """判断句型是否可模板化"""
        return sid in self.templates

    def fill_template(self, sid, word):
        """本地填空生成（0 token）"""
        if sid not in self.templates:
            return None

        tmpl = self.templates[sid]
        template_str = tmpl['template']
        slot_type = tmpl.get('type', 'verb_phrase')

        # 根据槽位类型生成合适的填充内容
        if slot_type == 'verb_phrase':
            fill = self._fill_verb_phrase(word)
        elif slot_type == 'noun_phrase':
            fill = self._fill_noun_phrase(word)
        elif slot_type == 'adjective':
            fill = self._fill_adjective(word)
        elif slot_type == 'multi_slot':
            fill = self._fill_multi_slot(tmpl.get('slots', []), word)
        else:
            fill = word

        if fill is None:
            return None

        return template_str.replace('___', fill, 1)

    def _fill_verb_phrase(self, word):
        """动词短语填充"""
        # 如果是动词，用原形
        return word

    def _fill_noun_phrase(self, word):
        """名词短语填充"""
        return word

    def _fill_adjective(self, word):
        """形容词填充"""
        return word

    def _fill_multi_slot(self, slots, word):
        """多槽位填充"""
        return word  # 简化版，只填第一个槽

    def build_prompt(self, word, sid, scene='general', extra_word=None):
        """构建压缩 AI Prompt"""
        info = self.all_patterns.get(sid, {})
        pattern_en = info.get('pattern_en', '')
        pattern_cn = info.get('pattern_cn', '')
        function = info.get('function', '')

        extra = f" | extra_word={extra_word}" if extra_word else ""
        prompt = (
            f"word={word}{extra} | "
            f"pattern=\"{pattern_en}\" | "
            f"scene={scene} | "
            f"n=2"
        )
        return prompt

    def build(self, word, recall_results, scene='general', extra_word=None):
        """
        根据召回结果生成例句

        参数:
            word: 用户输入的单词
            recall_results: recall() 返回的 [(sid, score, mtype), ...]
            scene: 场景描述
            extra_word: 可选的额外单词（从 recent_words.md 随机选取）

        返回:
            [{
                'sid': str,
                'pattern_en': str,
                'pattern_cn': str,
                'sentence': str or None,  # None 表示需 AI 生成
                'prompt': str or None,     # AI prompt（需 AI 时）
                'cost': int,               # 0 或预估 token 数
                'match_type': str,
                'score': int,
            }, ...]
        """
        output = []
        for sid, (score, mtype) in recall_results:
            info = self.all_patterns.get(sid, {})
            pattern_en = info.get('pattern_en', '')
            pattern_cn = info.get('pattern_cn', '')

            entry = {
                'sid': sid,
                'pattern_en': pattern_en,
                'pattern_cn': pattern_cn,
                'function': info.get('function', ''),
                'difficulty': info.get('difficulty', ''),
                'match_type': mtype,
                'score': score,
            }

            if self.is_templatable(sid):
                # 模板填空（0 token）
                sentence = self.fill_template(sid, word)
                entry['sentence'] = sentence
                entry['prompt'] = None
                entry['cost'] = 0
            else:
                # AI 生成（带上 extra_word）
                entry['sentence'] = None
                entry['prompt'] = self.build_prompt(word, sid, scene, extra_word)
                entry['cost'] = len(entry['prompt']) // 4  # 粗略估算 token 数

            output.append(entry)

        return output


def _pick_extra_word():
    """从 recent_words.md 随机取一个历史单词"""
    path = os.path.join(BASE_DIR, 'recent_words.md')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        words = re.findall(r'^\|\s*\d+\s*\|\s*(\w+)', text, re.M)
        return random.choice(words) if words else None
    except Exception:
        return None


def main():
    if len(sys.argv) < 2:
        print("用法: python builder.py <word> [--limit N] [--scene SCENE]")
        sys.exit(1)

    word = sys.argv[1]
    limit = 5
    scene = 'general'

    if '--limit' in sys.argv:
        idx = sys.argv.index('--limit')
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])
    if '--scene' in sys.argv:
        idx = sys.argv.index('--scene')
        if idx + 1 < len(sys.argv):
            scene = sys.argv[idx + 1]

    # 导入 recall 引擎
    sys.path.insert(0, BASE_DIR)
    from recall import RecallEngine

    engine = RecallEngine(os.path.join(BASE_DIR, 'index_data.json'))
    builder = SentenceBuilder()

    extra_word = _pick_extra_word()
    results = engine.recall(word, limit)
    sentences = builder.build(word, results, scene, extra_word)

    print(f"\n📌 单词: {word}  |  场景: {scene}", end='')
    if extra_word:
        print(f"  |  关联历史词: {extra_word}")
    else:
        print()
    print()

    for s in sentences:
        if s['cost'] == 0 and s['sentence']:
            print(f"  🟢 [填空] {s['sid']} (0 token)")
            print(f"         句型: {s['pattern_en']}  {s['pattern_cn']}")
            print(f"         生成: {s['sentence']}")
        else:
            print(f"  🔴 [AI]   {s['sid']} (~{s['cost']} tokens)")
            print(f"         句型: {s['pattern_en']}  {s['pattern_cn']}")
            print(f"         Prompt: {s['prompt']}")
        print()


if __name__ == '__main__':
    main()
