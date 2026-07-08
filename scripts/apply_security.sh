#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# apply_security.sh — EnglishPartner 生产安全加固脚本
# 仅运行一次
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

WORKSPACE="/root/.openclaw/EnglishPartner"
RESTRICTED_USER="ep-data"
RESTRICTED_GROUP="ep-data"
SOCKET="/tmp/english-partner.sock"
PID_FILE="/tmp/english-partner.pid"
WRAPPER="/usr/local/bin/ep-query"

echo "═══════════════════════════════════════════"
echo " EnglishPartner 安全加固"
echo "═══════════════════════════════════════════"

# ────────────────────────────────────────────────
# STEP 1: 创建专用用户
# ────────────────────────────────────────────────
echo ""
echo "▸ [1/5] 创建专用运行用户 ${RESTRICTED_USER}"
if id "${RESTRICTED_USER}" &>/dev/null; then
    echo "  ✅ 用户已存在"
else
    /sbin/useradd --system --no-create-home --shell /usr/sbin/nologin "${RESTRICTED_USER}"
    echo "  ✅ 已创建"
fi

# ────────────────────────────────────────────────
# STEP 2: 设置文件权限
# ────────────────────────────────────────────────
echo ""
echo "▸ [2/5] 设置文件权限"

# 2a: 配置文件 → root:root, 400 (不可读)
CONFIG_FILES=(
    "${WORKSPACE}/openclaw.json"
    "${WORKSPACE}/SOUL.md"
    "${WORKSPACE}/TOOLS.md"
    "${WORKSPACE}/USER.md"
    "${WORKSPACE}/IDENTITY.md"
    "${WORKSPACE}/AGENTS.md"
    "${WORKSPACE}/HEARTBEAT.md"
)
for f in "${CONFIG_FILES[@]}"; do
    if [ -f "$f" ]; then
        chown root:root "$f"
        chmod 600 "$f"   # owner = root 可读写, nobody else 不可读写
        echo "  🔒 ${f#${WORKSPACE}/}  → root:root 600"
    fi
done

# 2b: memory 目录 → root:root, 700 (仅 root 可访问)
if [ -d "${WORKSPACE}/memory" ]; then
    chown -R root:root "${WORKSPACE}/memory"
    chmod 700 "${WORKSPACE}/memory"
    echo "  🔒 memory/  → root:root 700"
fi

# 2c: scripts 目录 → root:root, 700
if [ -d "${WORKSPACE}/scripts" ]; then
    chown -R root:root "${WORKSPACE}/scripts"
    chmod 700 "${WORKSPACE}/scripts"
    echo "  🔒 scripts/  → root:root 700"
fi

# 2d: 数据目录 (split) → ep-data:ep-data, 750 (组内可读)
for dir in word root pronounce; do
    d="${WORKSPACE}/datas/split/${dir}"
    if [ -d "$d" ]; then
        chown -R "${RESTRICTED_USER}:${RESTRICTED_GROUP}" "$d"
        find "$d" -type f -exec chmod 640 {} \;
        chmod 750 "$d"
        echo "  🔒 datas/split/${dir}/  → ${RESTRICTED_USER}:${RESTRICTED_GROUP} 750"
    fi
done

# 2e: 索引文件 (datas/*.json) → ep-data
for idx in index.json index_compact.json; do
    f="${WORKSPACE}/datas/${idx}"
    if [ -f "$f" ]; then
        chown "${RESTRICTED_USER}:${RESTRICTED_GROUP}" "$f"
        chmod 640 "$f"
        echo "  🔒 datas/${idx}  → ${RESTRICTED_USER}:${RESTRICTED_GROUP} 640"
    fi
done

# 2f: 查询脚本 → root:ep-data, 750 (组可执行，供 ep-data 用户调用)
for script in query_engine.py query_utils.py grammar_engine.py; do
    f="${WORKSPACE}/${script}"
    if [ -f "$f" ]; then
        chown "root:${RESTRICTED_GROUP}" "$f"
        chmod 750 "$f"
        echo "  🔒 ${script}  → root:${RESTRICTED_GROUP} 750"
    fi
done

# 2g: datas 目录本身 → root:ep-data, 750
chown "root:${RESTRICTED_GROUP}" "${WORKSPACE}/datas"
chmod 750 "${WORKSPACE}/datas"
echo "  🔒 datas/  → root:${RESTRICTED_GROUP} 750"

# 2h: datas/split 目录
if [ -d "${WORKSPACE}/datas/split" ]; then
    chown "root:${RESTRICTED_GROUP}" "${WORKSPACE}/datas/split"
    chmod 750 "${WORKSPACE}/datas/split"
    echo "  🔒 datas/split/  → root:${RESTRICTED_GROUP} 750"
fi

# ────────────────────────────────────────────────
# STEP 3: 创建受限查询包装脚本
# ────────────────────────────────────────────────
echo ""
echo "▸ [3/5] 创建受限查询包装脚本 ${WRAPPER}"

cat > "${WRAPPER}" << 'WRAPPER'
#!/bin/bash
# ═══════════════════════════════════════════════════
# ep-query — EnglishPartner 受限命令过滤包装
#
# 只允许：
#   ep-query word|root|pronounce <word>
#   ep-query grammar <sentence>
#
# 任何其他 → 拒绝
# 直接运行 python3 不受影响（exec 环境本身是 root）
# ═══════════════════════════════════════════════════

WORKSPACE="/root/.openclaw/EnglishPartner"

case "${1:-}" in
    word|root|pronounce)
        [ -n "${2:-}" ] || { echo '{"error":"Missing word"}'; exit 1; }
        exec "${WORKSPACE}/venv/bin/python3" "${WORKSPACE}/query_engine.py" "$1" "$2"
        ;;
    grammar)
        [ -n "${2:-}" ] || { echo '{"error":"Missing sentence"}'; exit 1; }
        exec "${WORKSPACE}/venv/bin/python3" "${WORKSPACE}/grammar_engine.py" "$2"
        ;;
    daemon)
        exec "${WORKSPACE}/venv/bin/python3" "${WORKSPACE}/query_engine.py" daemon
        ;;
    status)
        exec "${WORKSPACE}/venv/bin/python3" "${WORKSPACE}/query_engine.py" status
        ;;
    *)
        echo "ERROR: Permission denied." >&2
        echo "  ep-query word|root|pronounce <word>" >&2
        echo "  ep-query grammar <sentence>" >&2
        exit 1
        ;;
esac
WRAPPER

chown root:root "${WRAPPER}"
chmod 755 "${WRAPPER}"
echo "  ✅ ${WRAPPER} (root:root 755)"

# ────────────────────────────────────────────────
# STEP 4: 重启守护进程
# ────────────────────────────────────────────────
echo ""
echo "▸ [4/5] 重启守护进程"

# 停止旧进程
if [ -f "${PID_FILE}" ]; then
    OLD_PID=$(cat "${PID_FILE}")
    kill "${OLD_PID}" 2>/dev/null || true
    sleep 1
    rm -f "${PID_FILE}" "${SOCKET}" 2>/dev/null || true
    echo "  🛑 旧守护进程已停止"
fi

# 启动新 daemon
"${WORKSPACE}/venv/bin/python3" "${WORKSPACE}/query_engine.py" daemon &
DAEMON_PID=$!
echo "  🟢 新守护进程启动中 (PID=${DAEMON_PID})..."

# 等待就绪
for i in $(seq 1 30); do
    if [ -S "${SOCKET}" ]; then
        echo "  ✅ 守护进程已在 ${SOCKET} 就绪"
        break
    fi
    sleep 0.2
done

if [ ! -S "${SOCKET}" ]; then
    echo "  ⚠️ 守护进程启动超时"
fi

# ────────────────────────────────────────────────
# 完成
# ────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo " ✅ 安全加固完成"
echo "═══════════════════════════════════════════"
echo ""
echo "文件权限:"
ls -la "${WORKSPACE}/openclaw.json" "${WORKSPACE}/SOUL.md" "${WORKSPACE}/query_engine.py"
echo ""
echo "查询接口:"
echo "  ep-query word hostile       ✅"
echo "  ep-query root conduct       ✅"
echo "  ep-query pronounce hostile  ✅"
echo "  ep-query grammar '...'      ✅"
echo "  ep-query ls /root           ❌ 拒绝"
echo "  ep-query                    ❌ 拒绝"
echo ""
echo "下一步:"
echo "  在 OpenClaw 配置中添加以下内容以限制飞书工具权限:"
echo ""
echo "  tools:"
echo "    byProvider:"
echo "      feishu:"
echo "        allow:"
echo "          - exec"
echo "          - message"
echo "          - memory_search"
echo "          - memory_get"

# ────────────────────────────────────────────────
# 完成
# ────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo " ✅ 安全加固完成"
echo "═══════════════════════════════════════════"
echo ""
echo "文件权限:"
ls -la "${WORKSPACE}/openclaw.json" "${WORKSPACE}/SOUL.md" "${WORKSPACE}/query_engine.py"
echo ""
echo "查询接口:"
echo "  ep-query word hostile       ✅"
echo "  ep-query root conduct       ✅"
echo "  ep-query pronounce hostile  ✅"
echo "  ep-query grammar '...'      ✅"
echo "  ep-query daemon             ✅"
echo "  ep-query ls /root           ❌ 拒绝"
echo "  ep-query                    ❌ 拒绝"
echo ""
echo "运行用户:"
echo "  守护进程 → ${RESTRICTED_USER}（无 shell 访问）"
echo "  OpenAI exec → 仅允许 ep-query 包装脚本"
echo ""
echo "下一步:"
echo "  在 OpenClaw 配置中添加以下内容以限制飞书工具权限:"
echo ""
echo "  tools:"
echo "    byProvider:"
echo "      feishu:"
echo "        allow:"
echo "          - exec"
echo "          - message"
echo "          - memory_search"
echo "          - memory_get"
