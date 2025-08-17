#!/bin/bash
# 停止 Twitter 自动发布系统

set -e

# 默认配置
SYSTEM_PID_FILE="twitter_system.pid"
API_PID_FILE="twitter_api.pid"
FORCE_KILL=false

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 帮助信息
show_help() {
    echo "Twitter 自动发布系统停止脚本"
    echo ""
    echo "使用方法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --system             停止主系统服务"
    echo "  --api                停止API服务"
    echo "  --all                停止所有服务 (默认)"
    echo "  --force              强制终止进程"
    echo "  --system-pid FILE    指定系统PID文件路径"
    echo "  --api-pid FILE       指定API PID文件路径"
    echo "  --help               显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                   # 停止所有服务"
    echo "  $0 --system          # 只停止主系统"
    echo "  $0 --api             # 只停止API服务"
    echo "  $0 --force           # 强制停止所有服务"
}

# 停止进程函数
stop_process() {
    local pid_file="$1"
    local service_name="$2"
    
    if [ ! -f "$pid_file" ]; then
        echo -e "${YELLOW}$service_name 未在运行 (PID文件不存在)${NC}"
        return 0
    fi
    
    local pid=$(cat "$pid_file")
    
    if ! ps -p $pid > /dev/null 2>&1; then
        echo -e "${YELLOW}$service_name 未在运行 (进程不存在)${NC}"
        rm -f "$pid_file"
        return 0
    fi
    
    echo -e "${BLUE}正在停止 $service_name (PID: $pid)...${NC}"
    
    if [ "$FORCE_KILL" = true ]; then
        kill -9 $pid 2>/dev/null || true
        echo -e "${GREEN}✓ $service_name 已强制停止${NC}"
    else
        kill -TERM $pid 2>/dev/null || true
        
        # 等待进程优雅退出
        local count=0
        while ps -p $pid > /dev/null 2>&1 && [ $count -lt 10 ]; do
            sleep 1
            count=$((count + 1))
        done
        
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${YELLOW}进程未响应，强制终止...${NC}"
            kill -9 $pid 2>/dev/null || true
        fi
        
        echo -e "${GREEN}✓ $service_name 已停止${NC}"
    fi
    
    rm -f "$pid_file"
}

# 停止系统服务
stop_system() {
    stop_process "$SYSTEM_PID_FILE" "Twitter 自动发布系统"
}

# 停止API服务
stop_api() {
    stop_process "$API_PID_FILE" "Twitter API 服务"
}

# 停止所有服务
stop_all() {
    echo -e "${BLUE}=== 停止 Twitter 自动发布系统 ===${NC}"
    echo ""
    
    stop_system
    stop_api
    
    echo ""
    echo -e "${GREEN}✓ 所有服务已停止${NC}"
}

# 主函数
main() {
    local stop_system_only=false
    local stop_api_only=false
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --system)
                stop_system_only=true
                shift
                ;;
            --api)
                stop_api_only=true
                shift
                ;;
            --all)
                # 默认行为，不需要特殊处理
                shift
                ;;
            --force)
                FORCE_KILL=true
                shift
                ;;
            --system-pid)
                SYSTEM_PID_FILE="$2"
                shift 2
                ;;
            --api-pid)
                API_PID_FILE="$2"
                shift 2
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                echo -e "${RED}未知选项: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 执行停止操作
    if [ "$stop_system_only" = true ]; then
        stop_system
    elif [ "$stop_api_only" = true ]; then
        stop_api
    else
        stop_all
    fi
}

# 运行主函数
main "$@"
