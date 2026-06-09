import re
import json

# ===================== 全量正则（直接使用你提供的全套语法）=====================
PATTERNS = [
    # 一、英语五大基本句型
    r"sb\s+vi",
    r"sb\s+vt\s+sth",
    r"sb\s+link\s+adj",
    r"sb\s+vt\s+sb\s+sth",
    r"sb\s+vt\s+sth\s+complement",
    r"there\s+be",

    # 二、名词性从句
    r"that\s+从句",
    r"whether\s+从句",
    r"if\s+从句",
    r"what\s+从句",
    r"who\s+从句",
    r"whose\s+从句",
    r"where\s+从句",
    r"when\s+从句",
    r"why\s+从句",
    r"how\s+从句",
    r"the\s+fact\s+that",
    r"the\s+news\s+that",

    # 三、定语从句
    r"who\s+that",
    r"which\s+that",
    r"whose",
    r"in\s+which",
    r"on\s+which",
    r"at\s+which",
    r"where",
    r"when",
    r"why",
    r"as\s+引导定语从句",

    # 四、九大状语从句
    r"when", r"while", r"as", r"before", r"after", r"since", r"until", r"as\s+soon\s+as",
    r"if", r"unless", r"as\s+long\s+as", r"on\s+condition\s+that",
    r"because", r"since", r"now\s+that",
    r"although", r"though", r"even\s+if", r"even\s+though",
    r"so\s+that", r"such\s+that",
    r"in\s+order\s+that", r"so\s+that",
    r"as\s+as", r"more\s+than", r"the\s+more",
    r"where", r"wherever",
    r"as\s+if", r"as\s+though",

    # 五、特殊句式
    r"it\s+is\s+that", r"it\s+was\s+that",
    r"only\s+状语", r"never", r"hardly", r"rarely", r"no\s+sooner\s+than",

    # 六、非谓语动词
    r"to\s+do",
    r"doing",
    r"done",
    r"having\s+done",
    r"being\s+done",

    # 七、be+形容词固定搭配
    r"be\s+adj\s+of", r"be\s+adj\s+for", r"be\s+adj\s+with",
    r"be\s+adj\s+to", r"be\s+adj\s+in", r"be\s+adj\s+at",
    r"be\s+made\s+of", r"be\s+made\s+from", r"be\s+filled\s+with",

    # 八、使役动词
    r"make\s+sb\s+do",
    r"let\s+sb\s+do",
    r"have\s+sb\s+do",
    r"get\s+sb\s+to\s+do",

    # 九、并列结构 & 高级句型
    r"not\s+only\s+but\s+also",
    r"both\s+and",
    r"either\s+or",
    r"neither\s+nor",
    r"rather\s+than",
    r"there\s+is\s+no\s+doubt\s+that",
    r"as\s+far\s+as\s+i\s+am\s+concerned",
    r"when\s+it\s+to",
    r"with\s+复合结构"
]

REGEX = re.compile("|".join(PATTERNS), re.IGNORECASE)

# ===================== 你的完整语法映射 =====================
PATTERN_FULL_MAP = {
    r"there\s+be": {
        "pattern_key": "there be 句型",
        "pattern_name": "There be 存在句",
        "grammar_type": "五大基本句型",
        "sub_type": "存在句型",
        "pattern_template": "There be + 名词 + 地点状语",
        "default_cn": "某地有某物",
        "grammar_analysis": [
            "主谓倒装结构，be动词单复数由后面名词决定",
            "遵循就近原则，中考/高考必考基础句型",
            "不与have混用"
        ],
        "sentence_structure": "There(引导词) + be(谓语) + 主语 + 地点状语",
        "similar_base": ["There is a book on the desk.", "There are many students in the classroom."],
        "imitate_examples": ["There is a park near my home.", "There are two trees beside the road."],
        "base_diff": "中考",
        "level": "基础"
    },
    r"it\s+is\s+that": {
        "pattern_key": "it is ... that 强调句",
        "pattern_name": "It型强调句型",
        "grammar_type": "特殊句式",
        "sub_type": "强调句",
        "pattern_template": "It is/was + 被强调部分 + that + 剩余成分",
        "default_cn": "正是……",
        "grammar_analysis": [
            "去掉it is/was...that，句子结构依然完整",
            "可强调主语、宾语、地点/时间状语",
            "四六级写作高分句式"
        ],
        "sentence_structure": "形式主语it + 谓语 + 被强调部分 + 引导词 + 主干",
        "similar_base": ["It is I who help you.", "It was yesterday that we met."],
        "imitate_examples": ["It is hard work that brings success.", "It is this rule that we follow."],
        "base_diff": "CET4",
        "level": "进阶"
    },
    r"that\s+从句": {
        "pattern_key": "that 宾语从句",
        "pattern_name": "that引导宾语从句",
        "grammar_type": "名词性从句",
        "sub_type": "宾语从句",
        "pattern_template": "主句 + that + 完整陈述句",
        "default_cn": "……（陈述内容）",
        "grammar_analysis": [
            "that无词义，口语/非正式文体可省略",
            "从句必须使用陈述语序",
            "初高中、四六级核心考点"
        ],
        "sentence_structure": "主句(主谓) + 引导词 + 从句(主谓宾)",
        "similar_base": ["I know that you are right.", "He says he will come soon."],
        "imitate_examples": ["I believe she can finish it.", "We think the plan is good."],
        "base_diff": "高考",
        "level": "进阶"
    },
    r"although": {
        "pattern_key": "although 让步从句",
        "pattern_name": "although引导让步状语从句",
        "grammar_type": "状语从句",
        "sub_type": "让步状语从句",
        "pattern_template": "Although + 从句 , 主句",
        "default_cn": "虽然……但是……",
        "grammar_analysis": [
            "although与but不能同时连用",
            "从句表让步关系，阅读高频考点",
            "可与yet/still搭配使用"
        ],
        "sentence_structure": "让步从句 + 主句，主从句均为完整主谓结构",
        "similar_base": ["Although it rains, we go out.", "Though he is young, he knows much."],
        "imitate_examples": ["Although tired, I keep working.", "Though difficult, we won't give up."],
        "base_diff": "高考",
        "level": "进阶"
    },
    r"make\s+sb\s+do": {
        "pattern_key": "make sb do",
        "pattern_name": "make使役结构",
        "grammar_type": "使役动词",
        "sub_type": "主动式使役结构",
        "pattern_template": "主语 + make + 宾语 + 动词原形",
        "default_cn": "使/让某人做某事",
        "grammar_analysis": [
            "make后接宾补，主动语态用动词原形",
            "被动语态需加to：be made to do",
            "中考语法填空必考搭配"
        ],
        "sentence_structure": "主谓 + 宾语 + 宾语补足语(动词原形)",
        "similar_base": ["He makes me laugh.", "The story makes us moved."],
        "imitate_examples": ["She makes me study hard.", "They make us wait here."],
        "base_diff": "中考",
        "level": "基础"
    },
    r"to\s+do": {
        "pattern_key": "动词不定式 to do",
        "pattern_name": "动词不定式结构",
        "grammar_type": "非谓语动词",
        "sub_type": "不定式",
        "pattern_template": "动词 + to do / It + to do",
        "default_cn": "（去）做某事",
        "grammar_analysis": [
            "不定式可作主语、宾语、定语、状语",
            "非谓语核心考点，区分to do/doing",
            "五大句型拓展核心成分"
        ],
        "sentence_structure": "主干 + 不定式(非谓语成分)",
        "similar_base": ["I want to go.", "It is easy to learn."],
        "imitate_examples": ["I decide to try again.", "She plans to travel."],
        "base_diff": "高考",
        "level": "进阶"
    },
    r"be\s+adj\s+of": {
        "pattern_key": "be + adj + of",
        "pattern_name": "be+形容词+of 固定搭配",
        "grammar_type": "形容词搭配",
        "sub_type": "be+adj+of结构",
        "pattern_template": "主语 + be + 形容词 + of + 宾语",
        "default_cn": "对……感到……；充满……",
        "grammar_analysis": [
            "多描述人物品质、情绪",
            "中考高频短语，写作常用",
            "区分be of / be for / be with"
        ],
        "sentence_structure": "主系表结构，of短语作状语",
        "similar_base": ["be proud of", "be afraid of"],
        "imitate_examples": ["She is proud of her family.", "We are afraid of darkness."],
        "base_diff": "中考",
        "level": "基础"
    },
    r"the\s+more": {
        "pattern_key": "the more ... the more",
        "pattern_name": "比较级叠加句型",
        "grammar_type": "状语从句",
        "sub_type": "比较状语从句",
        "pattern_template": "The+比较级, the+比较级",
        "default_cn": "越……越……",
        "grammar_analysis": [
            "前后均为倒装结构",
            "CET6/高考写作加分句型",
            "形容词、副词比较级通用"
        ],
        "sentence_structure": "比较从句 + 主句，双主谓结构",
        "similar_base": ["The more you read, the wiser you are."],
        "imitate_examples": ["The harder you work, the better result you get."],
        "base_diff": "CET6",
        "level": "高阶"
    },
    r"not\s+only\s+but\s+also": {
        "pattern_key": "not only but also",
        "pattern_name": "递进并列结构",
        "grammar_type": "并列句",
        "sub_type": "递进并列",
        "pattern_template": "Not only A , but also B",
        "default_cn": "不仅……而且……",
        "grammar_analysis": [
            "主谓一致遵循就近原则",
            "可连接主语、谓语、句子",
            "全学段通用高分句型"
        ],
        "sentence_structure": "并列双主干结构",
        "similar_base": ["He not only sings but also dances."],
        "imitate_examples": ["This plan not only saves time but cuts cost."],
        "base_diff": "高考",
        "level": "进阶"
    }
}

# ===================== 兜底模板（你的原版）=====================
DEFAULT_MAP = {
    "pattern_key": "general_grammar_pattern",
    "pattern_name": "通用语法句型",
    "grammar_type": "综合句型",
    "sub_type": "通用结构",
    "pattern_template": "",
    "default_cn": "英语通用语法句式",
    "grammar_analysis": [
        "基础语法结构，适用于阅读、写作、翻译",
        "结合五大句型与从句规则分析",
        "日常应试高频句式"
    ],
    "sentence_structure": "常规主谓/主从复合结构",
    "similar_base": [],
    "imitate_examples": [],
    "base_diff": "高考",
    "level": "进阶"
}

MIN_LENGTH = 4

# ===================== OpenClaw 调用入口（严格按你的item输出）=====================
def analyze_sentence(sentence: str) -> str:
    if not sentence or len(sentence.strip()) < MIN_LENGTH:
        item = DEFAULT_MAP.copy()
        item["original_sentence"] = sentence.strip() if sentence else ""
        item["sentence_cn"] = item["default_cn"]
        item["difficulty"] = item["base_diff"]
        item["similar_sentences"] = item["similar_base"]
        return json.dumps(item, ensure_ascii=False, indent=2)

    # 匹配正则
    match_rule = None
    for pat in PATTERNS:
        if re.search(pat, sentence, re.IGNORECASE):
            match_rule = pat
            break

    # 获取配置
    cfg = PATTERN_FULL_MAP.get(match_rule, DEFAULT_MAP)
    
    # 组装你要求的标准item结构
    item = {
        "id": 1,
        "pattern_key": cfg["pattern_key"],
        "pattern_name": cfg["pattern_name"],
        "original_sentence": sentence.strip(),
        "sentence_cn": cfg["default_cn"],
        "grammar_analysis": cfg["grammar_analysis"],
        "pattern_template": cfg["pattern_template"],
        "difficulty": cfg["base_diff"],
        "grammar_type": cfg["grammar_type"],
        "sub_type": cfg["sub_type"],
        "sentence_structure": cfg["sentence_structure"],
        "similar_sentences": cfg.get("similar_base", []),
        "imitate_examples": cfg.get("imitate_examples", [])
    }

    return json.dumps(item, ensure_ascii=False, indent=2)

# 本地测试入口
if __name__ == "__main__":
    test_sentences = [
        "There is a book on the desk.",
        "He makes me study hard.",
        "I think that you are right.",
        "Although it is cold, we go out.",
        "I want to learn English."
    ]
    
    for sent in test_sentences:
        print("=" * 80)
        print(f"例句：{sent}")
        print(f"语法分析：\n{analyze_sentence(sent)}")
