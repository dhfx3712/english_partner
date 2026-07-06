#!/usr/bin/env python3
"""
recall.py — 单词召回引擎

从 index_data.json 中召回与单词匹配的句型。
支持多级匹配策略，返回按得分排序的 (sid, score, match_type) 列表。

用法：
    python recall.py <word> [--limit N] [--difficulty L00X]
"""

import re
import json
import sys


class RecallEngine:
    """单词召回引擎"""

    def __init__(self, index_path='index_data.json'):
        with open(index_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.c_index = self.data['c_index']
        self.f_index = self.data['f_index']
        self.g_index = self.data['g_index']
        self.word_to_c = self.data['word_to_c']
        self.word_to_f = self.data['word_to_f']
        self.collocation_map = self.data['collocation_map']
        self.all_patterns = self.data['all_patterns']

    def recall(self, word, limit=5, difficulty=None):
        """
        召回主入口

        参数:
            word: 用户输入的单词
            limit: 最大返回句型数
            difficulty: 可选难度过滤 L001-L006

        返回:
            [(sid, score, match_type), ...]
        """
        word = word.lower().strip()
        results = {}  # sid → (score, match_type)

        # Step 1: C标签精确匹配（得分 100）
        self._match_c_tag(word, results)

        # Step 2: 搭配映射匹配（得分 90）
        self._match_collocation(word, results)

        # Step 3: F场景批量匹配（得分 70）
        self._match_f_tag(word, results)

        # Step 4: 核心句型模糊匹配（得分 30-50）
        self._match_pattern_fuzzy(word, results)

        # Step 5: 语义兜底（得分 20）
        if not results:
            self._fallback(word, results)

        # 难度过滤
        if difficulty:
            results = {
                sid: (score, mtype)
                for sid, (score, mtype) in results.items()
                if self.all_patterns.get(sid, {}).get('difficulty') == difficulty
            }

        # 排序：按得分降序，同分按 SID 升序
        sorted_results = sorted(
            results.items(),
            key=lambda x: (-x[1][0], x[0])
        )

        return sorted_results[:limit]

    def _match_c_tag(self, word, results):
        """Step 1: C标签精确匹配"""
        # 直接查 word_to_c
        if word in self.word_to_c:
            for match in self.word_to_c[word]:
                sid = match['sid']
                if sid not in results or results[sid][0] < 100:
                    results[sid] = (100, 'c_tag')

    def _match_collocation(self, word, results):
        """Step 2: 搭配映射匹配"""
        for collocation, ctags in self.collocation_map.items():
            # 检查单词是否包含在搭配中
            if word in collocation.split():
                for ctag in ctags:
                    if ctag in self.c_index:
                        for pattern in self.c_index[ctag]:
                            sid = pattern['sid']
                            if sid not in results or results[sid][0] < 90:
                                results[sid] = (90, f'collocation:{collocation}')

    def _match_f_tag(self, word, results):
        """Step 3: F场景批量匹配"""
        if word in self.word_to_f:
            for ftag in self.word_to_f[word]:
                if ftag in self.f_index:
                    for pattern in self.f_index[ftag]:
                        sid = pattern['sid']
                        if sid not in results or results[sid][0] < 70:
                            results[sid] = (70, f'f_tag:{ftag}')

    def _match_pattern_fuzzy(self, word, results):
        """Step 4: 核心句型模糊匹配"""
        word_lower = word.lower()
        for sid, pattern in self.all_patterns.items():
            pattern_en = pattern['pattern_en'].lower()
            # 检查单词是否出现在句型英文部分
            if word_lower in pattern_en:
                if sid not in results or results[sid][0] < 50:
                    results[sid] = (50, 'pattern_fuzzy')
            # 检查是否出现在例句中
            else:
                for ex in pattern.get('examples', []):
                    if word_lower in ex.lower():
                        if sid not in results or results[sid][0] < 30:
                            results[sid] = (30, 'example_match')
                            break

    def _fallback(self, word, results):
        """Step 5: 语义兜底 — 按词性推荐通用句型"""
        # 动词 → 建议类、观点类
        # 名词 → 描述评价类
        # 形容词 → 比较类、评价类
        # 副词 → 总结类
        # 默认推荐最高频的 5 个句型
        fallback_sids = ['S053', 'S142', 'S089', 'S264', 'S251']
        for sid in fallback_sids:
            results[sid] = (20, 'fallback')

    def explain(self, word, limit=5, difficulty=None):
        """返回带详细信息的召回结果"""
        results = self.recall(word, limit, difficulty)
        output = []
        for sid, (score, mtype) in results:
            info = self.all_patterns.get(sid, {})
            output.append({
                'sid': sid,
                'score': score,
                'match_type': mtype,
                'pattern_en': info.get('pattern_en', ''),
                'pattern_cn': info.get('pattern_cn', ''),
                'function': info.get('function', ''),
                'difficulty': info.get('difficulty', ''),
                'examples': info.get('examples', []),
                'tags': info.get('tags', []),
            })
        return output


def main():
    if len(sys.argv) < 2:
        print("用法: python recall.py <word> [--limit N] [--difficulty L00X]")
        sys.exit(1)

    word = sys.argv[1]
    limit = 5
    difficulty = None

    if '--limit' in sys.argv:
        idx = sys.argv.index('--limit')
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])
    if '--difficulty' in sys.argv:
        idx = sys.argv.index('--difficulty')
        if idx + 1 < len(sys.argv):
            difficulty = sys.argv[idx + 1]

    engine = RecallEngine()
    results = engine.explain(word, limit, difficulty)

    print(f"\n📌 单词: {word}")
    print(f"   召回结果: {len(results)} 条\n")

    for r in results:
        score_bar = '█' * (r['score'] // 10) + '░' * (10 - r['score'] // 10)
        print(f"  [{score_bar}] {r['sid']} ({r['score']}分)")
        print(f"      匹配: {r['match_type']}")
        print(f"      句型: {r['pattern_en']}  {r['pattern_cn']}")
        print(f"      功能: {r['function']}")
        print(f"      难度: {r['difficulty']}")
        if r['examples']:
            print(f"      例句: {r['examples'][0]}")
        print()


if __name__ == '__main__':
    main()
