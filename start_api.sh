#!/bin/bash

# Twitter自动发布系统 - API服务启动脚本
# 使用方法: ./start_api.sh [选项]

set -e

# 默认配置
HOST="127.0.0.1"
PORT="8050"
DEBUG="false"
ENV_FILE=".env"
DAEMON_MODE=false
PID_FILE="twitter_api.pid"
LOG_FILE="logs/api.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 帮助信息
show_help() {
    echo "Twitter自动发布系统 - API服务启动脚本"
    echo ""
    echo "使用方法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --host HOST      API服务器地址 (默认: 127.0.0.1)"
    echo "  -p, --port PORT      API服务器端口 (默认: 8050)"
    echo "  -d, --debug          启用调试模式"
    echo "  -e, --env-file FILE  环境变量文件路径 (默认: .env)"
    echo "  --daemon             后台运行模式"
    echo "  --pid-file FILE      PID文件路径 (默认: twitter_api.pid)"
    echo "  --log-file FILE      日志文件路径 (默认: logs/api.log)"
    echo "  --help               显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                           # 使用默认配置启动"
    echo "  $0 -h 0.0.0.0 -p 8050        # 在所有接口的8050端口启动"
    echo "  $0 -d                        # 启用调试模式"
    echo "  $0 --daemon                  # 后台运行"
    echo "  $0 -e .env.production        # 使用生产环境配置"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            HOST="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        --daemon)
            DAEMON_MODE=true
            shift
            ;;
        --pid-file)
            PID_FILE="$2"
            shift 2
            ;;
        --log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        -d|--debug)
            DEBUG="true"
            shift
            ;;
        -e|--env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}错误: 未知选项 $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 检查Python环境
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误: 未找到 python3${NC}"
        echo "请安装 Python 3.8 或更高版本"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo -e "${GREEN}✓${NC} Python版本: $PYTHON_VERSION"
}

# 检查依赖包
check_dependencies() {
    echo -e "${BLUE}检查依赖包...${NC}"
    
    if [ ! -f "requirements.txt" ]; then
        echo -e "${RED}错误: 未找到 requirements.txt${NC}"
        exit 1
    fi
    
    # 检查关键依赖
    python3 -c "import fastapi, uvicorn" 2>/dev/null || {
        echo -e "${YELLOW}警告: 缺少API依赖包，正在安装...${NC}"
        pip3 install fastapi uvicorn[standard] || {
            echo -e "${RED}错误: 依赖包安装失败${NC}"
            echo "请手动运行: pip3 install -r requirements.txt"
            exit 1
        }
    }
    
    echo -e "${GREEN}✓${NC} 依赖包检查完成"
}

# 检查环境配置
check_environment() {
    echo -e "${BLUE}检查环境配置...${NC}"
    
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}警告: 未找到环境文件 $ENV_FILE${NC}"
        if [ -f ".env.example" ]; then
            echo "请复制 .env.example 到 $ENV_FILE 并配置相关参数"
        fi
    else
        echo -e "${GREEN}✓${NC} 环境文件: $ENV_FILE"
    fi
}

# 检查端口是否被占用并清理
check_port() {
    if command -v lsof &> /dev/null; then
        local pids=$(lsof -ti :$PORT 2>/dev/null)
        if [ ! -z "$pids" ]; then
            echo -e "${YELLOW}警告: 端口 $PORT 已被占用${NC}"
            echo "占用进程PID: $pids"
            echo -e "${BLUE}正在清理占用端口的进程...${NC}"
            
            # 尝试优雅停止
            for pid in $pids; do
                if kill -0 $pid 2>/dev/null; then
                    echo "正在停止进程 $pid..."
                    kill -TERM $pid 2>/dev/null || true
                fi
            done
            
            # 等待进程停止
            sleep 2
            
            # 检查是否还有进程占用端口
            local remaining_pids=$(lsof -ti :$PORT 2>/dev/null)
            if [ ! -z "$remaining_pids" ]; then
                echo -e "${YELLOW}强制停止剩余进程...${NC}"
                for pid in $remaining_pids; do
                    if kill -0 $pid 2>/dev/null; then
                        kill -9 $pid 2>/dev/null || true
                    fi
                done
                sleep 1
            fi
            
            # 最终检查
            if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
                echo -e "${RED}错误: 无法清理端口 $PORT，请手动处理${NC}"
                exit 1
            else
                echo -e "${GREEN}✓${NC} 端口 $PORT 已清理完成"
            fi
        fi
    fi
}

# 检查是否已在运行
check_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${YELLOW}API服务已在运行 (PID: $pid)${NC}"
            exit 1
        else
            echo -e "${YELLOW}删除过期的PID文件${NC}"
            rm -f "$PID_FILE"
        fi
    fi
}

# 启动API服务
start_api() {
    echo -e "${BLUE}启动API服务...${NC}"
    echo ""
    echo -e "${GREEN}🚀 Twitter自动发布系统 API服务${NC}"
    echo -e "${GREEN}📍 地址: http://$HOST:$PORT${NC}"
    echo -e "${GREEN}📖 API文档: http://$HOST:$PORT/docs${NC}"
    echo -e "${GREEN}🔧 调试模式: $([ "$DEBUG" = "true" ] && echo "启用" || echo "禁用")${NC}"
    echo -e "${GREEN}📄 环境文件: $ENV_FILE${NC}"
    echo -e "${GREEN}🔄 运行模式: $([ "$DAEMON_MODE" = true ] && echo "后台" || echo "前台")${NC}"
    echo ""
    
    # 设置环境变量
    export API_HOST="$HOST"
    export API_PORT="$PORT"
    export DEBUG="$DEBUG"
    
    # 构建启动命令
    local cmd="python3 -m api.main api --host $HOST --port $PORT"
    if [ "$DEBUG" = "true" ]; then
        cmd="$cmd --debug"
    fi
    
    if [ "$DAEMON_MODE" = true ]; then
        # 确保日志目录存在
        mkdir -p "$(dirname "$LOG_FILE")"
        
        echo -e "${GREEN}以后台模式启动API服务...${NC}"
        echo -e "${BLUE}日志文件: $LOG_FILE${NC}"
        echo -e "${BLUE}PID文件: $PID_FILE${NC}"
        echo ""
        
        # 后台启动
        nohup $cmd > "$LOG_FILE" 2>&1 &
        local pid=$!
        echo $pid > "$PID_FILE"
        
        echo -e "${GREEN}✓ API服务已在后台启动 (PID: $pid)${NC}"
        echo -e "${BLUE}使用以下命令查看日志: tail -f $LOG_FILE${NC}"
        echo -e "${BLUE}使用以下命令停止服务: kill $pid 或 kill \$(cat $PID_FILE)${NC}"
    else
        echo -e "${YELLOW}按 Ctrl+C 停止服务${NC}"
        echo ""
        
        # 前台启动
        eval $cmd
    fi
}

# 主函数
main() {
    echo -e "${BLUE}=== Twitter自动发布系统 API启动器 ===${NC}"
    echo ""
    
    # 检查是否已在运行
    check_running
    
    # 检查系统环境
    check_python
    check_dependencies
    check_environment
    check_port
    
    echo ""
    
    # 启动服务
    start_api
}

# 信号处理
trap 'echo -e "\n${YELLOW}正在停止API服务...${NC}"; [ -f "$PID_FILE" ] && rm -f "$PID_FILE"; exit 0' INT TERM

# 运行主函数
main