#!/usr/bin/env python3
"""
build_index.py — 从 句型.md 构建 index_data.json

用法：python build_index.py
输出：index_data.json（供 recall.py 使用）
"""

import re
import json

STOP_WORDS = {
    'a', 'an', 'the', 'to', 'for', 'of', 'in', 'on', 'at', 'by', 'with',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'do', 'does', 'did',
    'have', 'has', 'had', 'will', 'would', 'shall', 'should', 'may', 'might',
    'can', 'could', 'must', 'need', 'dare', 'not', 'no', 'nor', 'if', 'as',
    'but', 'or', 'and', 'so', 'yet', 'it', 'its', 'that', 'this', 'these',
    'those', 'i', 'you', 'he', 'she', 'we', 'they', 'me', 'him', 'her',
    'us', 'them', 'my', 'your', 'his', 'their', 'our', 'what', 'which',
    'who', 'whom', 'when', 'where', 'why', 'how', 'all', 'each', 'every',
    'some', 'any', 'many', 'much', 'more', 'most', 'few', 'little', 'less',
    'than', 'very', 'just', 'only', 'also', 'too', 'really', 'quite', 'rather',
    'then', 'now', 'here', 'there', 'about', 'into', 'over', 'up', 'down',
    'out', 'off', 'well', 'even', 'still', 'always', 'never', 'ever', 'once',
    'thing', 'things', 'one', 'two', 'other', 'another', 'such', 'same',
    'own', 'doing', 'going', 'get', 'got', 'make', 'made', 'take', 'took',
    'come', 'came', 'know', 'think', 'see', 'say', 'tell', 'give', 'find',
    'let', 'like', 'want', 'look', 'use', 'used', 'put', 'set', 'mean',
    'meant', 'seem', 'feel', 'felt', 'become', 'became', 'leave', 'left',
    'work', 'need', 'try', 'ask', 'show', 'keep', 'start', 'bring', 'brought',
}


def extract_keywords(pattern_en):
    """从句型英文部分提取关键词（去停用词）"""
    clean = re.sub(r'[\(\)\[\]{}]', '', pattern_en)
    words = re.findall(r'[a-zA-Z]+', clean.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def parse_entries(filepath):
    """解析句型.md，返回结构化数据列表"""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    entries = re.split(r'\n(?=S\d{3}\n)', text.strip())
    all_data = []

    for entry in entries:
        lines = entry.strip().split('\n')
        sid = ""
        difficulty = ""
        pattern_en = ""
        pattern_cn = ""
        function = ""
        examples = []
        tags = []

        for line in lines:
            if re.match(r'^S\d{3}$', line.strip()):
                sid = line.strip()
            elif line.strip().startswith('- 难度：'):
                difficulty = line.split('：')[1].strip()
            elif line.strip().startswith('- 核心句型：'):
                full = line.split('：')[1].strip()
                # 分离中英文
                parts = re.split(r'[ 　]+', full, maxsplit=1)
                if len(parts) >= 2:
                    if re.search(r'[a-zA-Z]', parts[0]):
                        pattern_en = parts[0]
                        pattern_cn = parts[1] if len(parts) > 1 else ""
                    else:
                        pattern_cn = parts[0]
                        pattern_en = parts[1]
                else:
                    pattern_en = full
                    pattern_cn = ""
            elif line.strip().startswith('- 功能定位：'):
                function = line.split('：')[1].strip()
            elif line.strip().startswith('- 标签：'):
                tags_str = line.split('：')[1].strip()
                tags = [t.strip() for t in tags_str.split('、')]

        # 提取例句英文部分
        in_examples = False
        for line in lines:
            if line.strip().startswith('- 经典例句：'):
                in_examples = True
                continue
            if in_examples and line.strip().startswith('- 标签：'):
                in_examples = False
            if in_examples and line.strip():
                m = re.match(r'\d+\.(.+?)(?=[\u4e00-\u9fff])', line.strip())
                if m:
                    examples.append(m.group(1).strip())

        all_data.append({
            'sid': sid,
            'difficulty': difficulty,
            'pattern_en': pattern_en,
            'pattern_cn': pattern_cn,
            'function': function,
            'examples': examples,
            'tags': tags,
        })

    return all_data


def build_c_index(all_data):
    """C标签 → [句型信息]"""
    idx = {}
    for d in all_data:
        for t in d['tags']:
            if t.startswith('C'):
                idx.setdefault(t, []).append({
                    'sid': d['sid'],
                    'pattern_en': d['pattern_en'],
                    'pattern_cn': d['pattern_cn'],
                    'function': d['function'],
                })
    return idx


def build_f_index(all_data):
    """F标签 → [句型信息]"""
    idx = {}
    for d in all_data:
        for t in d['tags']:
            if t.startswith('F'):
                idx.setdefault(t, []).append({
                    'sid': d['sid'],
                    'pattern_en': d['pattern_en'],
                    'pattern_cn': d['pattern_cn'],
                    'function': d['function'],
                })
    return idx


def build_g_index(all_data):
    """G标签 → [句型信息]"""
    idx = {}
    for d in all_data:
        for t in d['tags']:
            if t.startswith('G'):
                idx.setdefault(t, []).append({
                    'sid': d['sid'],
                    'pattern_en': d['pattern_en'],
                    'pattern_cn': d['pattern_cn'],
                    'function': d['function'],
                })
    return idx


def build_word_to_c(all_data):
    """从句型关键词建立 单词→C标签 映射"""
    mapping = {}
    for d in all_data:
        for t in d['tags']:
            if t.startswith('C'):
                keywords = extract_keywords(d['pattern_en'])
                for kw in keywords:
                    mapping.setdefault(kw, []).append({
                        'c_tag': t,
                        'sid': d['sid'],
                        'pattern_en': d['pattern_en'],
                    })
    return mapping


def build_collocation_map():
    """搭配短语 → [C标签列表]
    
    手动维护的映射表，覆盖 300 句中的核心搭配。
    可随使用持续扩展。
    """
    return {
        # === effect 相关 ===
        'have an effect on': ['C063', 'C218', 'C146', 'C053', 'C142'],
        'take effect': ['C169', 'C194', 'C153'],
        'side effect': ['C155', 'C166', 'C206'],
        'effective': ['C172', 'C210', 'C265', 'C264'],

        # === 观点表达 ===
        'think': ['C053', 'C142', 'C231', 'C262'],
        'believe': ['C053', 'C117', 'C168', 'C188', 'C262'],
        'opinion': ['C142', 'C220', 'C231', 'C247', 'C262'],
        'view': ['C034', 'C035', 'C142', 'C220', 'C247'],
        'agree': ['C048', 'C053', 'C262'],
        'disagree': ['C031', 'C073', 'C063'],

        # === 建议推荐 ===
        'suggest': ['C089', 'C111'],
        'advise': ['C088', 'C103'],
        'recommend': ['C105', 'C103'],
        'insist': ['C078', 'C079'],
        'advice': ['C088', 'C103', 'C089', 'C111'],

        # === 请求帮助 ===
        'help': ['C015', 'C163', 'C210'],
        'please': ['C013', 'C015', 'C232', 'C233', 'C241', 'C283'],
        'could': ['C013', 'C015', 'C151'],
        'would': ['C103', 'C104', 'C105', 'C106', 'C107', 'C108',
                  'C109', 'C133', 'C161', 'C283', 'C284'],
        'may': ['C002', 'C149'],
        'allow': ['C002', 'C287', 'C288'],

        # === 询问打听 ===
        'know': ['C005', 'C016', 'C018', 'C020', 'C021'],
        'wonder': ['C099', 'C110'],
        'curious': ['C118'],
        'question': ['C244'],
        'information': ['C004', 'C016', 'C018', 'C110'],

        # === 意愿打算 ===
        'plan': ['C050', 'C080', 'C219'],
        'intend': ['C080'],
        'want': ['C085', 'C097', 'C129', 'C284'],
        'hope': ['C087', 'C175', 'C219'],
        'wish': ['C087', 'C134', 'C219'],
        'dream': ['C067', 'C177', 'C219'],
        'goal': ['C219'],
        'desire': ['C068', 'C129'],
        'decide': ['C039', 'C119', 'C130'],
        'determined': ['C086', 'C119'],

        # === 情感态度 ===
        'thank': ['C049', 'C097', 'C104'],
        'sorry': ['C032', 'C127', 'C234', 'C241'],
        'apologize': ['C052', 'C127', 'C234'],
        'grateful': ['C049', 'C069', 'C104'],
        'pleasure': ['C200'],
        'happy': ['C108', 'C109', 'C161', 'C200', 'C202'],
        'excited': ['C061', 'C120'],
        'interested': ['C120', 'C121', 'C124'],
        'enjoy': ['C017', 'C081', 'C126'],
        'hate': ['C056', 'C070', 'C071', 'C073'],
        'afraid': ['C028', 'C114'],
        'surprise': ['C258'],
        'pity': ['C207'],
        'shame': ['C207'],

        # === 条件假设 ===
        'if': ['C131', 'C132', 'C133', 'C134', 'C135', 'C136',
               'C137', 'C108', 'C161', 'C163', 'C277', 'C285', 'C299'],
        'unless': ['C101'],
        'condition': ['C227'],
        'suppose': ['C290', 'C298'],

        # === 总结逻辑 ===
        'summary': ['C138', 'C139', 'C140', 'C260'],
        'conclusion': ['C138', 'C140', 'C260'],
        'general': ['C036', 'C141'],
        'example': ['C033', 'C229', 'C259'],
        'reason': ['C245', 'C212', 'C243'],
        'result': ['C245', 'C236', 'C250'],
        'fact': ['C003', 'C008'],
        'truth': ['C189', 'C261'],
        'finally': ['C138', 'C139', 'C140', 'C260'],
        'first': ['C033', 'C229', 'C259'],
        'other': ['C144'],
        'contrary': ['C228'],
        'short': ['C139'],
        'brief': ['C139'],
        'word': ['C138', 'C144', 'C260'],

        # === 引用陈述 ===
        'according': ['C001'],
        'report': ['C185', 'C236'],
        'research': ['C236'],
        'study': ['C051', 'C115', 'C125', 'C196'],
        'say': ['C187', 'C196'],
        'known': ['C008'],
        'doubt': ['C066', 'C251'],

        # === 要求义务 ===
        'must': ['C263', 'C264', 'C240'],
        'should': ['C054', 'C264', 'C265', 'C294', 'C295', 'C296', 'C297'],
        'need': ['C291', 'C292', 'C179'],
        'necessary': ['C064', 'C172', 'C179'],
        'essential': ['C172'],
        'important': ['C146', 'C176', 'C205'],
        'duty': ['C205'],
        'require': ['C186', 'C289'],
        'allow': ['C002', 'C287', 'C288'],
        'supposed': ['C290', 'C298'],

        # === 日常交际 ===
        'welcome': ['C235'],
        'congratulate': ['C069'],
        'meet': ['C069'],
        'call': ['C122'],
        'visit': ['C040', 'C111'],
        'introduce': ['C213'],
        'remind': ['C249'],
        'reminds': ['C249'],

        # === 描述评价 ===
        'good': ['C090', 'C091', 'C163', 'C171', 'C192', 'C204', 'C210'],
        'bad': ['C166', 'C199', 'C204', 'C206'],
        'great': ['C146', 'C200', 'C202', 'C203', 'C218'],
        'best': ['C096', 'C217', 'C246'],
        'better': ['C096', 'C217', 'C170'],
        'difficult': ['C190', 'C191', 'C209', 'C072'],
        'easy': ['C171'],
        'possible': ['C025', 'C135', 'C149', 'C182'],
        'impossible': ['C094', 'C182'],
        'important': ['C146', 'C176', 'C205'],
        'useful': ['C192'],
        'common': ['C184'],
        'true': ['C189'],
        'sure': ['C113', 'C123'],
        'certain': ['C113'],
        'clear': ['C193'],
        'obvious': ['C193'],
        'amazing': ['C164'],
        'unbelievable': ['C208'],
        'dangerous': ['C183'],
        'waste': ['C030', 'C092'],
        'harm': ['C160'],
        'difference': ['C158'],
        'challenge': ['C191'],

        # === 因果逻辑 ===
        'because': ['C242', 'C245'],
        'so': ['C226', 'C242'],
        'therefore': ['C226', 'C242'],
        'thanks': ['C242'],
        'due': ['C242'],
        'lead': ['C245', 'C271'],
        'cause': ['C245', 'C271'],
        'result': ['C245', 'C236', 'C250'],

        # === 比较对比 ===
        'prefer': ['C083', 'C084', 'C106', 'C107'],
        'rather': ['C084', 'C106', 'C107'],
        'more': ['C083', 'C084', 'C085', 'C106', 'C107', 'C110'],
        'most': ['C230', 'C081'],
        'than': ['C083', 'C084', 'C106', 'C107', 'C170'],
        'different': ['C083', 'C084', 'C106', 'C107'],

        # === 环境主题 ===
        'environment': ['C054', 'C205', 'C263', 'C264', 'C265', 'C240'],
        'pollution': ['C035', 'C136', 'C240', 'C263', 'C264', 'C271'],
        'nature': ['C008', 'C141', 'C201'],
        'climate': ['C008', 'C236', 'C250'],
        'protect': ['C205', 'C263', 'C264', 'C265'],
        'reduce': ['C240', 'C263', 'C264'],
        'green': ['C163', 'C210', 'C265'],

        # === 措施行动 ===
        'measure': ['C240', 'C264'],
        'action': ['C240', 'C264'],
        'effort': ['C265', 'C295'],
        'protect': ['C205', 'C263', 'C264'],
        'improve': ['C210', 'C163', 'C265'],
        'change': ['C024', 'C194', 'C239'],
        'develop': ['C050', 'C080', 'C128'],
        'support': ['C048', 'C053', 'C262'],
        'encourage': ['C088', 'C103', 'C163'],

        # === 时间频率 ===
        'always': ['C102', 'C297'],
        'never': ['C082', 'C297', 'C225'],
        'often': ['C102'],
        'usually': ['C102'],
        'sometimes': ['C102'],
        'used': ['C102', 'C253'],
        'once': ['C102', 'C248'],
        'moment': ['C248'],
        'time': ['C174', 'C196'],
        'until': ['C197', 'C225'],

        # === 方式方法 ===
        'way': ['C019', 'C150', 'C246', 'C247'],
        'method': ['C019', 'C150', 'C246'],
        'secret': ['C246'],
        'chance': ['C016', 'C018', 'C090', 'C151'],
        'opportunity': ['C051', 'C090', 'C069'],
        'experience': ['C076', 'C098'],
        'success': ['C230', 'C246', 'C285'],
        'progress': ['C043'],

        # === 强调 ===
        'no': ['C222', 'C251', 'C255'],
        'only': ['C134', 'C197', 'C225'],
        'even': ['C181'],
        'really': ['C085', 'C127', 'C208'],
        'just': ['C006', 'C214'],
    }


def build_word_to_f():
    """单词 → F场景标签 映射"""
    return {
        # F001 观点表达
        'think': ['F001'], 'believe': ['F001'], 'opinion': ['F001'],
        'view': ['F001'], 'agree': ['F001'], 'disagree': ['F001'],
        'point': ['F001'], 'perspective': ['F001'], 'seem': ['F001'],
        'appear': ['F001'], 'convince': ['F001'], 'convinced': ['F001'],

        # F002 建议推荐
        'suggest': ['F002'], 'advise': ['F002'], 'recommend': ['F002'],
        'propose': ['F002'], 'advice': ['F002'], 'suggestion': ['F002'],
        'recommendation': ['F002'], 'should': ['F002'], 'better': ['F002'],

        # F003 请求求助
        'please': ['F003'], 'could': ['F003'], 'would': ['F003'],
        'may': ['F003'], 'help': ['F003'], 'allow': ['F003'],
        'permit': ['F003'], 'mind': ['F003'], 'kind': ['F003'],

        # F004 询问打听
        'know': ['F004'], 'wonder': ['F004'], 'curious': ['F004'],
        'question': ['F004'], 'tell': ['F004'], 'explain': ['F004'],
        'information': ['F004'], 'inquire': ['F004'],

        # F005 意愿打算
        'plan': ['F005'], 'intend': ['F005'], 'want': ['F005'],
        'wish': ['F005'], 'hope': ['F005'], 'dream': ['F005'],
        'goal': ['F005'], 'will': ['F005'], 'future': ['F005'],
        'decide': ['F005'], 'determined': ['F005'],

        # F006 情感态度
        'thank': ['F006'], 'sorry': ['F006'], 'apologize': ['F006'],
        'grateful': ['F006'], 'pleasure': ['F006'], 'happy': ['F006'],
        'excited': ['F006'], 'feel': ['F006'], 'hate': ['F006'],
        'love': ['F006'], 'like': ['F006'], 'enjoy': ['F006'],
        'afraid': ['F006'], 'surprise': ['F006'], 'pity': ['F006'],
        'shame': ['F006'],

        # F007 条件假设
        'if': ['F007'], 'unless': ['F007'], 'condition': ['F007'],
        'suppose': ['F007'], 'otherwise': ['F007'], 'whether': ['F007'],

        # F008 总结逻辑
        'summary': ['F008'], 'conclusion': ['F008'], 'finally': ['F008'],
        'overall': ['F008'], 'brief': ['F008'], 'short': ['F008'],
        'word': ['F008'], 'sum': ['F008'], 'general': ['F008'],

        # F009 引用陈述
        'according': ['F009'], 'report': ['F009'], 'say': ['F009'],
        'said': ['F009'], 'believe': ['F009'], 'thought': ['F009'],
        'known': ['F009'], 'fact': ['F009'], 'study': ['F009'],
        'research': ['F009'], 'doubt': ['F009'],

        # F010 要求义务
        'must': ['F010'], 'should': ['F010'], 'need': ['F010'],
        'protect': ['F010'], 'reduce': ['F010'], 'environment': ['F010'],
        'pollution': ['F010'], 'nature': ['F010'], 'climate': ['F010'],
        'require': ['F010'], 'necessary': ['F010'], 'essential': ['F010'],
        'duty': ['F010'], 'obligation': ['F010'], 'important': ['F010'],
        'supposed': ['F010'],

        # F011 日常交际
        'hello': ['F011'], 'hi': ['F011'], 'meet': ['F011'],
        'introduce': ['F011'], 'call': ['F011'], 'visit': ['F011'],
        'welcome': ['F011'], 'greet': ['F011'], 'chat': ['F011'],
        'talk': ['F011'], 'remind': ['F011'],
    }


def build_all_patterns(all_data):
    """SID → 句型完整信息"""
    return {
        d['sid']: {
            'pattern_en': d['pattern_en'],
            'pattern_cn': d['pattern_cn'],
            'function': d['function'],
            'difficulty': d['difficulty'],
            'examples': d['examples'],
            'tags': d['tags'],
        }
        for d in all_data
    }


def main():
    print("📖 正在解析 句型.md...")
    all_data = parse_entries('句型.md')
    print(f"   ✅ 解析完成：{len(all_data)} 条句型")

    print("🔨 正在构建索引...")
    index_data = {
        'c_index': build_c_index(all_data),
        'f_index': build_f_index(all_data),
        'g_index': build_g_index(all_data),
        'word_to_c': build_word_to_c(all_data),
        'word_to_f': build_word_to_f(),
        'collocation_map': build_collocation_map(),
        'all_patterns': build_all_patterns(all_data),
    }

    with open('index_data.json', 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    print(f"   ✅ 索引构建完成")
    print(f"      C标签索引: {len(index_data['c_index'])} 条")
    print(f"      F标签索引: {len(index_data['f_index'])} 条")
    print(f"      G标签索引: {len(index_data['g_index'])} 条")
    print(f"      单词→C映射: {len(index_data['word_to_c'])} 条")
    print(f"      单词→F映射: {len(index_data['word_to_f'])} 条")
    print(f"      搭配映射: {len(index_data['collocation_map'])} 条")
    print(f"      句型完整信息: {len(index_data['all_patterns'])} 条")
    print(f"   输出: index_data.json ✅")


if __name__ == '__main__':
    main()
