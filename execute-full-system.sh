#!/bin/bash

# 🚀 完整执行多Agent系统脚本
# 使用深度思考模式和最大算力

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     🧠 深度思考模式 - 最大算力执行                        ║"
echo "║     Claude Code Multi-Agent System v2.1.0                ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "📅 开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "💪 算力模式: 3倍深度思考模式"
echo "🔄 执行策略: 始终执行，自动修复"
echo ""

# 清理旧日志
echo "🧹 清理旧日志文件..."
rm -f agent-execution-*.log 2>/dev/null

# 创建新的日志文件
LOG_FILE="agent-execution-full-$(date '+%Y%m%d-%H%M%S').log"
echo "📝 日志文件: $LOG_FILE"
echo ""

# 设置环境变量
export CLAUDE_CONTINUE=true
export NODE_ENV=production
export MAX_TOKENS=unlimited
export THINKING_MODE=deep

echo "═══════════════════════════════════════════════════════════"
echo "                    开始执行多Agent系统                     "
echo "═══════════════════════════════════════════════════════════"
echo ""

# 执行orchestrator
node agent-orchestrator.js 2>&1 | tee "$LOG_FILE"

# 检查执行结果
EXIT_CODE=$?
echo ""
echo "═══════════════════════════════════════════════════════════"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 多Agent系统执行成功！"
else
    echo "⚠️ 多Agent系统执行完成（退出代码: $EXIT_CODE）"
fi

echo "📅 结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "📁 日志保存在: $LOG_FILE"
echo "═══════════════════════════════════════════════════════════"

# 生成执行摘要
echo ""
echo "📊 执行摘要："
echo "------------"
grep -E "阶段|Phase|完成|complete" "$LOG_FILE" | tail -10

exit $EXIT_CODE