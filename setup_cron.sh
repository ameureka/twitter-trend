#!/bin/bash

# Twitter自动发布管理系统 - Cron任务设置脚本
# 用于设置每日自动任务创建

set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Twitter自动发布管理系统 - Cron任务设置 ===${NC}"
echo

# 检查是否在虚拟环境中
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}警告: 当前不在虚拟环境中${NC}"
    echo "建议先激活虚拟环境: source .venv/bin/activate"
    echo
fi

# 获取Python和项目路径
PYTHON_PATH=$(which python3)
if [[ "$VIRTUAL_ENV" != "" ]]; then
    PYTHON_PATH="$VIRTUAL_ENV/bin/python"
fi

echo "项目目录: $PROJECT_DIR"
echo "Python路径: $PYTHON_PATH"
echo

# 检查daily_task_creator.py是否存在
TASK_CREATOR="$PROJECT_DIR/scripts/daily_task_creator.py"
if [[ ! -f "$TASK_CREATOR" ]]; then
    echo -e "${RED}错误: 找不到 daily_task_creator.py 脚本${NC}"
    echo "请确保脚本位于: $TASK_CREATOR"
    exit 1
fi

# 测试脚本是否能正常运行
echo -e "${BLUE}测试脚本运行...${NC}"
cd "$PROJECT_DIR"
if ! "$PYTHON_PATH" "$TASK_CREATOR" --dry-run > /dev/null 2>&1; then
    echo -e "${RED}错误: daily_task_creator.py 脚本测试失败${NC}"
    echo "请先确保脚本能正常运行"
    exit 1
fi
echo -e "${GREEN}✓ 脚本测试通过${NC}"
echo

# 生成cron任务条目
CRON_COMMAND="cd $PROJECT_DIR && $PYTHON_PATH $TASK_CREATOR --verbose >> $PROJECT_DIR/logs/cron_daily_tasks.log 2>&1"

echo -e "${BLUE}建议的Cron任务设置:${NC}"
echo
echo "1. 每天凌晨2点自动创建任务:"
echo "0 2 * * * $CRON_COMMAND"
echo
echo "2. 每天凌晨2点和下午2点创建任务:"
echo "0 2,14 * * * $CRON_COMMAND"
echo
echo "3. 每6小时创建一次任务:"
echo "0 */6 * * * $CRON_COMMAND"
echo

# 询问用户选择
echo -e "${YELLOW}请选择要设置的Cron任务:${NC}"
echo "1) 每天凌晨2点 (推荐)"
echo "2) 每天凌晨2点和下午2点"
echo "3) 每6小时一次"
echo "4) 自定义时间"
echo "5) 仅显示命令，不自动设置"
echo "0) 退出"
echo
read -p "请输入选择 (0-5): " choice

case $choice in
    1)
        CRON_SCHEDULE="0 2 * * *"
        DESCRIPTION="每天凌晨2点"
        ;;
    2)
        CRON_SCHEDULE="0 2,14 * * *"
        DESCRIPTION="每天凌晨2点和下午2点"
        ;;
    3)
        CRON_SCHEDULE="0 */6 * * *"
        DESCRIPTION="每6小时一次"
        ;;
    4)
        echo "请输入自定义的cron时间表达式 (例如: 0 8 * * *):"
        read -p "时间表达式: " CRON_SCHEDULE
        DESCRIPTION="自定义时间: $CRON_SCHEDULE"
        ;;
    5)
        echo
        echo -e "${GREEN}完整的Cron命令:${NC}"
        echo "$CRON_COMMAND"
        echo
        echo "手动添加到crontab的步骤:"
        echo "1. 运行: crontab -e"
        echo "2. 添加以下行 (选择合适的时间):"
        echo "   0 2 * * * $CRON_COMMAND"
        echo "3. 保存并退出"
        exit 0
        ;;
    0)
        echo "退出设置"
        exit 0
        ;;
    *)
        echo -e "${RED}无效选择${NC}"
        exit 1
        ;;
esac

# 确认设置
echo
echo -e "${YELLOW}即将设置以下Cron任务:${NC}"
echo "时间: $DESCRIPTION"
echo "命令: $CRON_COMMAND"
echo
read -p "确认设置? (y/N): " confirm

if [[ $confirm != [yY] ]]; then
    echo "取消设置"
    exit 0
fi

# 备份现有crontab
echo -e "${BLUE}备份现有crontab...${NC}"
crontab -l > "$PROJECT_DIR/logs/crontab_backup_$(date +%Y%m%d_%H%M%S).txt" 2>/dev/null || true

# 添加新的cron任务
echo -e "${BLUE}添加Cron任务...${NC}"
(
    crontab -l 2>/dev/null || true
    echo "# Twitter自动发布管理系统 - 每日任务创建"
    echo "$CRON_SCHEDULE $CRON_COMMAND"
) | crontab -

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✓ Cron任务设置成功!${NC}"
    echo
    echo "设置详情:"
    echo "- 执行时间: $DESCRIPTION"
    echo "- 日志文件: $PROJECT_DIR/logs/cron_daily_tasks.log"
    echo "- 备份文件: $PROJECT_DIR/logs/crontab_backup_*.txt"
    echo
    echo "查看当前crontab: crontab -l"
    echo "删除cron任务: crontab -e (手动删除对应行)"
    echo "查看执行日志: tail -f $PROJECT_DIR/logs/cron_daily_tasks.log"
else
    echo -e "${RED}✗ Cron任务设置失败${NC}"
    exit 1
fi

echo
echo -e "${GREEN}设置完成!${NC}"
echo "系统将在指定时间自动创建每日发布任务。"