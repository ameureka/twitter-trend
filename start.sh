#!/bin/bash
# 启动增强版Twitter自动发布系统

set -e

# 默认配置
DAEMON_MODE=false
PID_FILE="twitter_system.pid"
LOG_FILE="logs/system.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 帮助信息
show_help() {
    echo "Twitter自动发布系统启动脚本"
    echo ""
    echo "使用方法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -d, --daemon         后台运行模式"
    echo "  -p, --pid-file FILE  PID文件路径 (默认: twitter_system.pid)"
    echo "  -l, --log-file FILE  日志文件路径 (默认: logs/system.log)"
    echo "  --help               显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                   # 前台运行"
    echo "  $0 -d                # 后台运行"
    echo "  $0 -d -l /var/log/twitter.log  # 后台运行并指定日志文件"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--daemon)
            DAEMON_MODE=true
            shift
            ;;
        -p|--pid-file)
            PID_FILE="$2"
            shift 2
            ;;
        -l|--log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

echo -e "${BLUE}启动增强版Twitter自动发布系统...${NC}"

# 检查是否已在运行
check_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${YELLOW}系统已在运行 (PID: $pid)${NC}"
            exit 1
        else
            echo -e "${YELLOW}删除过期的PID文件${NC}"
            rm -f "$PID_FILE"
        fi
    fi
}

# 检查Python环境
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误: 未找到Python3${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Python3 已安装${NC}"
}

# 设置虚拟环境
setup_venv() {
    if [ ! -d ".venv" ]; then
        echo -e "${YELLOW}创建虚拟环境...${NC}"
        python3 -m venv .venv
    fi
    
    echo -e "${YELLOW}激活虚拟环境...${NC}"
    source .venv/bin/activate
    
    echo -e "${YELLOW}安装依赖...${NC}"
    pip install -r requirements.txt
}

# 初始化数据库
init_database() {
    echo -e "${YELLOW}初始化数据库...${NC}"
    python app/main.py --mode management --reset-db
}

# 启动系统
start_system() {
    # 确保日志目录存在
    mkdir -p "$(dirname "$LOG_FILE")"
    
    if [ "$DAEMON_MODE" = true ]; then
        echo -e "${GREEN}以后台模式启动系统...${NC}"
        echo -e "${BLUE}日志文件: $LOG_FILE${NC}"
        echo -e "${BLUE}PID文件: $PID_FILE${NC}"
        
        # 后台启动
        nohup python app/main.py --mode continuous > "$LOG_FILE" 2>&1 &
        local pid=$!
        echo $pid > "$PID_FILE"
        
        echo -e "${GREEN}✓ 系统已在后台启动 (PID: $pid)${NC}"
        echo -e "${BLUE}使用以下命令查看日志: tail -f $LOG_FILE${NC}"
        echo -e "${BLUE}使用以下命令停止系统: kill $pid 或 kill \$(cat $PID_FILE)${NC}"
    else
        echo -e "${GREEN}以前台模式启动系统...${NC}"
        python app/main.py --mode continuous
    fi
}

# 主函数
main() {
    check_running
    check_python
    setup_venv
    init_database
    start_system
}

# 信号处理
trap 'echo -e "\n${YELLOW}正在停止系统...${NC}"; [ -f "$PID_FILE" ] && rm -f "$PID_FILE"; exit 0' INT TERM

# 运行主函数
main
