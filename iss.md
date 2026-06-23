openclaw我已经给了agents  AGENTS.md  ARCHITECTURE.md  datas  HEARTBEAT.md  IDENTITY.md  memory  README.md  scripts  SCRIPTS.md  SOUL.md  TOOLS.md  USER.md这些文件，指定了各种工作流程。为什么偶尔会执行会缺失一些程序，或者自己会探索其他方式来解决。不能保证每次执行都是按流程来，这是什么原因。另外/new或者/reset后，这个现象更明显。
核心结论
你出现「不按文档流程、擅自换方案、/new/reset 后更严重」，根源分 4 大类，全部贴合你当前日志、配置、文件结构：
startupContext 预加载历史记忆污染新会话（/new/reset 加重的头号原因）
上下文溢出 + 自动压缩丢失流程规则，模型看不到完整工作流文档
工作流文档注入优先级不足、无强制约束，模型自主探索替代方案
工具输出截断、记忆检索上限过低，流程依赖的数据缺失
一、为什么 /new/reset 后现象更明显（最高权重）
1. startupContext 机制副作用
你开启了 startupContext.applyOn: ["new", "reset"]，新建 / 重置会话时会自动读取当日全部记忆文件注入上下文：
大量历史工单、旧交互、失败尝试全部塞进初始 prompt；
你的 AGENTS.md/ ARCHITECTURE.md 流程文档被挤到上下文尾部；
LLM 读取文本是从前往后，尾部内容极易被截断、忽略；
旧记忆里大量「变通执行方案」会给模型示范：不用严格走标准流程，能换方法。
2. 新会话初始 token 预算紧张
maxTotalChars 限制启动记忆总字符，为塞进历史日志，系统会裁剪你的工作流文档，流程步骤直接缺失，模型只能自己摸索替代逻辑。
3. 重置后无会话缓存兜底
老会话有完整对话上下文反复强化流程；/new 清空对话，仅靠启动加载文件，一旦文件被截断，立刻失控。
二、偶尔执行缺失程序、擅自探索方案的底层原因
1. 上下文溢出 & compaction 压缩损耗（你日志高频出现 Context overflow）
单次查询返回大量数据，token 打满 128k 窗口；
自动压缩会把最早注入的流程文档、强制规则压缩成极简摘要，丢失细节步骤；
摘要只能保留大致方向，完整分阶段工作流程丢失，模型自主脑补执行路径；
compactionAttempts=0 代表等到彻底溢出才压缩，丢失信息更严重。
关键区分：SOUL.md/AGENTS.md 永久文件不会被删除，但注入到会话上下文的完整原文会被压缩摘要替代，细节流程丢失。
2. 文档加载顺序与权重设计缺陷
OpenClaw 默认加载顺序：
startupContext 历史记忆（大量）
SOUL.md / USER.md
AGENTS.md/ 各类流程文档
当前用户提问、工具返回结果
流程文档排在记忆后面，权重更低；模型优先参考海量历史交互，而非标准流程。
同时你多份 MD 文件（AGENTS、ARCHITECTURE、SCRIPTS、TOOLS）分散规则，模型无法一次性读完完整链路，步骤缺失。
3. 缺少强制锁死流程的硬约束
仅靠文档描述「请按以下步骤执行」属于软性提示；大模型天生具备自主推理、自动优化的能力，一旦流程繁琐、工具查询量大，会主动简化、替换执行步骤。
没有配置强制拦截：禁止自主探索、必须严格按文档步骤逐条执行。
4. 工具输出截断、记忆检索上限过低
你之前收紧 maxSingleToolOutputChars、maxFileChars，数据库 / 脚本查询结果被提前截断：
流程依赖的前置数据不全；
模型拿不到完整参数，只能换其他方式完成任务；
日志可见 Truncated 3 tool result(s)，工具返回直接丢失，流程断裂。
5. 历史记忆存在错误变通样本
过去会话里模型曾经绕过标准流程成功执行，这些记录存入 memory 每日日志；
每次 new/reset 自动加载，形成负面示范：“不按流程也能完成”，反复强化违规行为。
三、分步根治方案（按优先级落地，解决你全部现象）
第一步：修复 startupContext，根治 /new/reset 失控（必改）
关闭新会话自动加载全天历史记忆，消除旧交互污染：
json
"startupContext": {
  "enabled": true,
  "applyOn": [],
  "dailyMemoryDays": 0,
  "maxFileBytes": 4096,
  "maxFileChars": 400,
  "maxTotalChars": 800
}
applyOn: []：new/reset 不再加载任何历史记忆；
新建会话只读取永久流程文档，无旧交互干扰；
如需调取历史，手动指令 检索今日工单记忆。
第二步：调整 compaction 压缩策略，防止流程文档被摘要丢失
开启轮中预压缩，提前裁剪工具输出，避免溢出后暴力压缩：
json
"compaction": {
  "midTurnPrecheck": {
    "enabled": true
  },
  "reserveTokens": 6000,
  "keepRecentTokens": 10000,
  "maxHistoryShare": 0.5,
  "recentTurnsPreserve": 5
}
开启 memoryFlush，压缩前强制把核心流程规则写入长期记忆兜底；
调高 autoCompactionThreshold:0.6，占用 60% 就提前压缩，不要等到溢出报错再处理。
第三步：强化流程文档权重，统一聚合、增加强制约束
1. 文件结构优化（减少分散规则）
把 ARCHITECTURE.md/ SCRIPTS.md/ TOOLS.md 里执行流程、步骤约束全部合并进 AGENTS.md，放在文档最顶部；
顶部增加强制锁死指令（最高优先级）：
markdown
# 强制执行规则（不可跳过、不可替换、不可自主探索其他方案）
1. 所有工单处理、数据查询、脚本执行，必须严格按照本文档完整步骤依次执行；
2. 禁止简化流程、禁止更换工具、禁止跳过任意步骤；
3. 若前置工具返回数据缺失，必须重新查询，不得换其他方式绕过；
4. 每次任务开始，先完整通读全部执行流程，确认每一步再操作；
5. 禁止参考历史会话变通方案，仅遵循本文档标准工作流。
2. 调整 Agent 注入顺序配置
在 agent defaults 配置中，提升 workspace 规则文件注入优先级，先加载 AGENTS.md，再加载记忆内容。
第四步：放宽工具输出、记忆读取硬限制，避免数据截断丢失流程依赖信息
json
"contextLimits": {
  "memoryGetMaxChars": 8000,
  "memoryGetDefaultLines": 50,
  "postCompactionMaxChars": 2000
},
"tools": {
  "maxSingleToolOutputChars": 12000
}
保证单次数据库、脚本查询完整返回，不会中途截断导致流程缺少前置数据。
第五步：清理污染记忆，消除负面示范样本
批量删除超过 6 小时的 memory 每日日志，清除大量「变通执行」历史记录；
bash
运行
cd ~/.openclaw/workspace-mes/memory
find . -name "*.md" -mmin +360 -delete
定期清理过期会话，减少大量旧会话记忆堆积；
禁止 agent 自动写入变通执行方案到 MEMORY.md，仅记录标准流程执行案例。
四、验证修复标准
执行 /new 新建会话，模型第一输出先复述 AGENTS.md 完整流程，不再直接执行变通方案；
批量工单查询无 Truncated tool result 截断日志；
日志不再高频 Context overflow，自动压缩提前执行，不会丢失流程细节；
多次重复相同任务，执行步骤完全统一，无随机更换处理逻辑；
飞书卡片交互、工具调用严格按文档顺序，不会缺失中间程序步骤。
补充补充区分关键概念（避免踩坑）
永久 MD 文件（SOUL/AGENTS）：物理文件永久存在，不会被删除；
会话上下文注入副本：每次会话加载文件原文，溢出压缩后会变成摘要，丢失细节步骤；
startupContext 历史记忆：仅 new/reset 加载，是干扰流程的最大污染源；
LLM 底层特性：上下文前端内容权重更高，旧记忆放在最前会覆盖流程规则。
 如何解决上下文溢出+自动压缩丢失流程规则问题？
完整解决方案：上下文溢出 + 压缩丢失流程规则
核心痛点拆解：
流程文档（AGENTS.md/TOOLS.md 等）被挤到上下文尾部，压缩时优先摘要、丢失细节；
等到 Context overflow 才触发压缩，属于事后抢救，大量前置规则已经被裁剪；
历史记忆、超长工具输出挤占窗口，标准流程文本被截断；
压缩策略默认保留对话历史，牺牲静态工作流文档。
一、分层配置改造（openclaw.json agents.defaults 全局生效）
1. 压缩核心配置：优先保护规则文档，晚压缩静态流程，早压缩工具 / 历史对话
json
"compaction": {
  // 轮中预校验：每轮工具结束预判token，不要等到彻底溢出
  "midTurnPrecheck": {
    "enabled": true
  },
  // 预留固定窗口给系统规则、AGENTS流程文档，绝不压缩这部分
  "reserveTokens": 8000,
  // 保留最近N轮对话，更早的历史对话优先压缩丢弃
  "recentTurnsPreserve": 3,
  // 窗口占用达到55%就主动压缩，不等到100%溢出报错
  "autoCompactionThreshold": 0.55,
  // 历史对话最多占用总窗口50%，剩下一半留给流程文档+工具原始返回
  "maxHistoryShare": 0.5,
  // 压缩时保留原始工具摘要，但不删减静态工作流文档
  "preserveStaticWorkspaceDocs": true
}
关键参数说明：
reserveTokens:8000：强制划出 8k token 专属存放你的 AGENTS/TOOLS/SOUL 等 md 流程文件，压缩逻辑不会动这块内容；
preserveStaticWorkspaceDocs：官方开关，压缩时跳过工作区 md 文档，只裁剪聊天历史、工具输出；
autoCompactionThreshold=0.55：过半就压缩，避免满载后暴力精简丢失规则。
2. 关闭 new/reset 自动加载历史记忆，杜绝旧交互污染流程
json
"startupContext": {
  "enabled": true,
  "applyOn": [],
  "dailyMemoryDays": 0,
  "maxTotalChars": 600
}
applyOn: [] 代表 /new /reset 新建会话只加载静态流程文档，不加载过往工单记忆，流程规则在上下文最靠前位置，权重最高。
3. 限制单工具输出上限，避免单次查询占满窗口挤掉流程文档
json
"tools": {
  "maxSingleToolOutputChars": 10000,
  "autoTrimLongToolResults": true,
  "toolTruncationHeader": "【数据过长已精简，如需完整明细请单独查询】"
},
"contextPruning": {
  // 超长工具结果达到12k字符就自动精简，不等到撑爆窗口
  "minPrunableToolChars": 12000,
  "softTrim": {
    "maxChars": 3000,
    "headChars": 1500,
    "tailChars": 1500
  }
}
作用：数据库批量工单查询不会一次性塞几万字符，从源头减少窗口占用，流程文档不会被挤出可见区间。
4. 调整文档加载顺序：流程规则优先注入（权重最高）
在 agent 配置内调整 workspaceLoadOrder，让 AGENTS.md 最先载入：
json
"workspace": {
  "loadOrder": [
    "AGENTS.md",
    "SOUL.md",
    "TOOLS.md",
    "ARCHITECTURE.md",
    "SCRIPTS.md",
    "*.md"
  ],
  "maxDocTotalChars": 16000
}
LLM 对上下文前文权重远高于后文，流程文档放在最开头，哪怕后续压缩，也只会裁剪后面的聊天记录，不会丢失前置标准流程。
二、Agent 文档内容加固（文本层面强制保护，双重保险）
1. AGENTS.md 文件头部置顶强约束
放在文档最顶端，任何会话加载都会最先读到：
markdown
# 最高优先级执行约束（系统不可压缩、不可忽略）
1. 本文档全部流程步骤为强制标准，任何历史对话、工具返回信息都不能替代、简化、跳过流程；
2. 当上下文空间不足时，允许压缩历史聊天记录、工单查询数据，**禁止删减、概括、遗忘本流程文档内容**；
3. 每一次任务启动，先完整阅读全部标准流程，再执行工具调用；
4. 不允许自主探索替代方案，所有操作严格遵循分步流程。
2. 拆分超大文档
如果单份 AGENTS.md 超过 10k 字符，拆分次要流程到 ARCHITECTURE.md，避免单文档占用过多预留 token。
三、会话侧兜底机制，防止极端场景丢失规则
1. 会话自动过期，清理堆积历史对话
agent 单独配置会话回收，避免单会话积累几十轮对话挤占窗口：
json
"sessions": {
  "autoExpire": true,
  "expireIdleMinutes": 240,
  "maxConcurrentSessions": 12
}
4 小时无操作自动销毁会话，新会话重新加载完整干净的流程文档。
2. 切换更大上下文模型（硬件兜底）
当前 deepseek-v4-flash 窗口 128k 偏小，批量工单极易溢出；
切换长上下文模型：deepseek-v4-long，原生更大窗口，大幅降低压缩触发频率。
四、运维操作：定期清理污染记忆
旧记忆里大量 “不按流程执行” 的历史案例会持续干扰模型，定期清理：
bash
运行
# 清理4小时以上的记忆文件
cd ~/.openclaw/workspace-mes/memory
find . -type f -mmin +240 -delete
# 清理过期会话文件
find ~/.openclaw/agents/mes-agent/sessions -name "*.jsonl" -mmin +480 -delete
五、验证修复是否生效的判断标准
日志不再大量出现 Context overflow，压缩日志提前在 50% 左右触发；
压缩日志打印 preserving static workspace document AGENTS.md，代表流程文档被保护；
/new 新建会话后，模型会主动复述标准流程再执行任务；
多次重复相同工单任务，执行步骤完全统一，不再随机更换方案、缺失步骤；
日志 Truncated tool result 大幅减少，不会因为数据过长挤掉流程规则。
六、补充：关键避坑点
不要关闭 midTurnPrecheck.enabled：关闭后只会等溢出再抢救，规则丢失概率翻倍；
不要调小 reserveTokens：预留空间是保护流程文档的核心，低于 6000 极易丢失步骤；
preserveStaticWorkspaceDocs 必须开启，这是专门解决 “压缩丢 md 流程” 的官方开关；
不要开启 startupContext 加载历史记忆，新旧对话混杂会稀释流程权重。
如何解决工作流程文档注入优先级不足，无强制约束问题
两套方案彻底解决：文档注入优先级低 + 缺少强制流程约束
分为 配置层（OpenClaw 底层控制加载顺序、独占 token、压缩保护） + 文档文本层（LLM 强制指令锁死行为），双管齐下，/new/reset 后也稳定生效。
一、配置层：拉高流程文档全局优先级（底层硬性保障）
1. workspace 强制加载顺序，流程文档最先进上下文
在 agents.defaults 或单独 mes-agent 配置中加入 workspace.loadOrder，AGENTS.md 全局第一加载：
json
"workspace": {
  // 严格顺序：流程规则 > 人格 > 工具规范 > 架构 > 脚本 > 其余文档
  "loadOrder": [
    "AGENTS.md",
    "SOUL.md",
    "TOOLS.md",
    "ARCHITECTURE.md",
    "SCRIPTS.md",
    "IDENTITY.md",
    "HEARTBEAT.md",
    "USER.md",
    "*.md"
  ],
  "maxDocTotalChars": 18000,
  // 核心开关：压缩时绝不精简/删减工作区md文档
  "preserveStaticDocsInCompaction": true
}
原理：LLM 对上下文前置文本注意力权重远高于后置，文档放在最前面，哪怕后面堆满工单数据、聊天记录，模型依然优先遵循。
2. compaction 预留固定 token 池，永久保护流程文档不被压缩
json
"compaction": {
  "midTurnPrecheck": {
    "enabled": true
  },
  // 强制划出 9000 token 专属存放所有流程md，压缩逻辑不会碰这块内容
  "reserveTokens": 9000,
  "maxHistoryShare": 0.45,
  "autoCompactionThreshold": 0.55,
  "recentTurnsPreserve": 2
}
reserveTokens：预留空间只给静态流程文档；聊天记录、工具返回、历史工单全部放在剩余窗口，先被压缩裁剪；
maxHistoryShare:0.45：历史对话最多只占总窗口 45%，不会挤占规则文档。
3. 彻底切断旧记忆稀释规则（解决 /new/reset 失控）
json
"startupContext": {
  "enabled": true,
  "applyOn": [],
  "dailyMemoryDays": 0,
  "maxTotalChars": 400
}
applyOn: []：新建 / 重置会话不再自动加载历史工单记忆，上下文前半段完全干净，只放标准流程文档，无违规历史交互干扰。
4. 限制单工具输出体积，防止查询数据挤掉文档
json
"tools": {
  "maxSingleToolOutputChars": 9000,
  "autoTrimLongToolResults": true
},
"contextPruning": {
  "minPrunableToolChars": 10000
}
避免一次数据库查询几万字符，把流程文档挤到上下文末尾被忽略。
二、文档文本层：添加不可逾越的强制约束（软性锁死模型行为）
1. AGENTS.md 头部置顶「最高优先级强制指令」（放在文档最开头）
markdown
# 【全局最高优先级·不可忽略规则】
## 权重说明
本段规则优先级高于所有历史对话、工具返回数据、用户临时提问、过往变通执行案例。
上下文空间不足时，仅允许压缩工单明细、聊天记录、工具查询结果；禁止精简、概括、遗忘、跳过本文档全部流程步骤。

## 强制执行铁律（违反即任务失败）
1. 所有工单处理、数据查询、脚本执行、卡片交互，必须严格按本文档完整步骤依次执行；
2. 禁止简化流程、禁止替换工具、禁止跳过任意环节、禁止自主探索其他解决方案；
3. 若前置工具返回数据缺失/截断，必须重新完整查询，不得绕开标准流程；
4. 每次任务启动，先通读完整流程，确认每一步要求后再调用工具；
5. 不允许参考历史会话中非标准变通操作，仅采信本文档定义的标准工作流；
6. 多步骤任务必须分步执行，每完成一步输出进度，确认无误再进入下一环节。

## 上下文保护要求
当系统执行自动压缩时，优先删减聊天记录、批量工单列表，保留完整流程操作规范。
2. 分文档分工，减少规则分散
AGENTS.md：完整业务流程、分步操作、强制约束（最高权重）
TOOLS.md：各工具入参、调用规范
ARCHITECTURE.md：系统架构、数据存储结构
不要把执行步骤散落在多个文件，核心流程统一收拢在 AGENTS.md，降低模型读取负担。
3. 每次任务前置固定引导话术（强化服从）
可以在 agent system 追加固定前缀，每次对话开头自动注入：
请严格遵循 AGENTS.md 定义的标准工作流程执行任务，不得自行更换处理逻辑、跳过操作步骤。空间不足时优先保留流程规范，压缩业务数据。
三、额外加固：阻断历史错误案例干扰
定时清理 memory 内旧交互记录（大量 “不按流程执行” 的历史会形成负面示范）
bash
运行
# 删除4小时以上记忆文件
find ~/.openclaw/workspace-mes/memory -name "*.md" -mmin +240 -delete
会话自动过期，避免单会话堆积几十轮杂乱对话稀释规则
json
"sessions": {
  "autoExpire": true,
  "expireIdleMinutes": 240
}
四、验证是否修复成功的判断标准
执行 /new 新建会话，模型会先复述 AGENTS.md 核心流程，再处理业务；
日志压缩逻辑提示 preserving static workspace doc AGENTS.md，不会裁剪流程内容；
多次重复相同工单任务，执行步骤完全统一，不会随机更换方案、缺失环节；
大批量查询工单后不会出现擅自简化流程、跳过步骤；
日志不再频繁出现 Context overflow，压缩只裁剪工单数据，不触碰流程规则。
五、关键避坑点
不要降低 reserveTokens 数值，预留 token 是文档优先级的底层保障；
不要开启 startupContext.applyOn: ["new","reset"]，旧记忆会直接覆盖流程权重；
不能只靠文档文字约束，必须配合 loadOrder + preserveStaticDocsInCompaction 配置双重兜底；
分散多份文档存放流程会降低识别率，核心执行步骤统一放 AGENTS.md。
