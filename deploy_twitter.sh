#!/bin/bash

# Twitter Trend 项目部署和运维脚本
# 支持 macOS 和 Ubuntu 系统
# 作者: Twitter Trend Team
# 版本: 1.0

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# 配置文件路径
CONFIG_FILE="$PROJECT_ROOT/config/enhanced_config.yaml"
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
VENV_DIR="$PROJECT_ROOT/.venv"
LOGS_DIR="$PROJECT_ROOT/logs"
DATA_DIR="$PROJECT_ROOT/data"
PID_FILE="$PROJECT_ROOT/twitter_trend.pid"
LOG_FILE="$LOGS_DIR/deploy.log"
ENV_FILE="$PROJECT_ROOT/.env"

# 默认配置参数
DEFAULT_MODE="continuous"
DEFAULT_PROJECT=""
DEFAULT_LANGUAGE=""
DEFAULT_LIMIT=""
DEFAULT_BATCH_SIZE="3"
DEFAULT_INTERVAL_HOURS="48"
DEFAULT_MAX_WORKERS="2"
DEFAULT_CHECK_INTERVAL="60"
DEFAULT_CONFIG_FILE="$CONFIG_FILE"
DEFAULT_API_HOST="127.0.0.1"
DEFAULT_API_PORT="8050"

# 运行时配置参数
RUN_MODE="$DEFAULT_MODE"
PROJECT_NAME="$DEFAULT_PROJECT"
LANGUAGE="$DEFAULT_LANGUAGE"
TASK_LIMIT="$DEFAULT_LIMIT"
BATCH_SIZE="$DEFAULT_BATCH_SIZE"
INTERVAL_HOURS="$DEFAULT_INTERVAL_HOURS"
MAX_WORKERS="$DEFAULT_MAX_WORKERS"
CHECK_INTERVAL="$DEFAULT_CHECK_INTERVAL"
CUSTOM_CONFIG_FILE="$DEFAULT_CONFIG_FILE"
API_HOST="$DEFAULT_API_HOST"
API_PORT="$DEFAULT_API_PORT"

# 检测操作系统
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        PYTHON_CMD="python3"
        PIP_CMD="pip3"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="ubuntu"
        PYTHON_CMD="python3"
        PIP_CMD="pip3"
    else
        echo -e "${RED}不支持的操作系统: $OSTYPE${NC}"
        exit 1
    fi
    echo -e "${GREEN}检测到操作系统: $OS${NC}"
}

# 日志函数
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() {
    log "INFO" "${GREEN}$*${NC}"
}

log_warn() {
    log "WARN" "${YELLOW}$*${NC}"
}

log_error() {
    log "ERROR" "${RED}$*${NC}"
}

# 创建必要的目录
create_directories() {
    log_info "创建必要的目录..."
    mkdir -p "$LOGS_DIR" "$DATA_DIR"
    mkdir -p "$DATA_DIR/backups"
    mkdir -p "$PROJECT_ROOT/project"
    log_info "目录创建完成"
}

# 检查系统依赖
check_system_dependencies() {
    log_info "检查系统依赖..."
    if ! command -v $PYTHON_CMD &> /dev/null; then
        log_error "Python3 未安装，请先安装 Python3"
        exit 1
    fi
    local python_version=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    log_info "Python 版本: $python_version"
    
    if ! command -v $PIP_CMD &> /dev/null; then
        log_error "pip3 未安装，请先安装 pip3"
        exit 1
    fi
    
    if ! command -v git &> /dev/null; then
        log_warn "Git 未安装，建议安装 Git 用于版本控制"
    fi
    log_info "系统依赖检查完成"
}

# 安装系统包（如果需要）
install_system_packages() {
    log_info "检查并安装系统包..."
    if [[ "$OS" == "ubuntu" ]]; then
        if ! dpkg -l | grep -q python3-venv; then
            log_info "安装 python3-venv..."
            sudo apt-get update
            sudo apt-get install -y python3-venv python3-pip
        fi
        sudo apt-get install -y curl wget unzip
    elif [[ "$OS" == "macos" ]]; then
        if command -v brew &> /dev/null; then
            log_info "检测到 Homebrew，检查必要包..."
        else
            log_warn "未检测到 Homebrew，请手动确保系统依赖已安装"
        fi
    fi
    log_info "系统包检查完成"
}

# 创建和激活虚拟环境
setup_virtual_environment() {
    log_info "设置 Python 虚拟环境..."
    if [[ ! -d "$VENV_DIR" ]]; then
        log_info "创建虚拟环境: $VENV_DIR"
        $PYTHON_CMD -m venv "$VENV_DIR"
    else
        log_info "虚拟环境已存在: $VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"
    log_info "升级 pip..."
    pip install --upgrade pip
    log_info "虚拟环境设置完成"
}

# 安装 Python 依赖
install_python_dependencies() {
    log_info "安装 Python 依赖..."
    if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
        log_error "requirements.txt 文件不存在: $REQUIREMENTS_FILE"
        exit 1
    fi
    source "$VENV_DIR/bin/activate"
    pip install -r "$REQUIREMENTS_FILE"
    log_info "Python 依赖安装完成"
}

# 检查配置文件
check_configuration() {
    log_info "检查配置文件..."
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_warn "配置文件不存在: $CONFIG_FILE"
        log_info "将使用默认配置"
    fi
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "环境变量文件不存在: $ENV_FILE"
        log_info "请确保 .env 文件已正确配置"
        exit 1
    fi
    log_info "配置文件检查完成"
}

# 运行配置验证
validate_configuration() {
    log_info "验证配置文件..."
    source "$VENV_DIR/bin/activate"
    cd "$PROJECT_ROOT"
    if $PYTHON_CMD -c "from app.utils.config_validator import ConfigValidator; validator = ConfigValidator(); validator.validate_all()"; then
        log_info "配置验证通过"
    else
        log_warn "配置验证有警告，请检查配置文件"
    fi
}

# 启动API服务
start_api_service() {
    log_info "启动 Twitter Trend API 服务..."
    
    # 检查并清理旧进程
    local existing_pids=$(pgrep -f "start_api.py" 2>/dev/null)
    if [ -n "$existing_pids" ]; then
        log_warn "发现已存在的start_api.py进程: $existing_pids"
        log_info "尝试停止旧进程..."
        stop_service
        sleep 2
        
        # 再次检查
        existing_pids=$(pgrep -f "start_api.py" 2>/dev/null)
        if [[ -n "$existing_pids" ]]; then
            log_error "无法清理旧进程，请手动处理: $existing_pids"
            return 1
        fi
    fi
    
    # 确保PID文件不存在
    if [[ -f "$PID_FILE" ]]; then
        log_warn "清理旧的PID文件"
        rm -f "$PID_FILE"
    fi
    
    # 启动API服务
    source "$VENV_DIR/bin/activate"
    cd "$PROJECT_ROOT"
    
    # 构建启动命令
    local start_cmd="$VENV_DIR/bin/python scripts/server/start_api.py --host $API_HOST --port $API_PORT"
    log_info "执行命令: $start_cmd"
    
    # 设置环境变量
    export API_HOST="$API_HOST"
    export API_PORT="$API_PORT"
    
    nohup $start_cmd > "$LOGS_DIR/api_service.log" 2>&1 &
    local api_pid=$!
    
    # 保存PID
    echo $api_pid > "$PID_FILE"
    
    # 等待服务启动
    local count=0
    while [[ $count -lt 30 ]]; do
        sleep 1
        ((count++))
        
        if kill -0 "$api_pid" 2>/dev/null; then
            log_info "API服务启动成功 (PID: $api_pid)"
            return 0
        fi
        
        echo -n "."
    done
    echo
    
    log_error "API服务启动失败，请检查日志: $LOGS_DIR/api_service.log"
    return 1
}

# 解析命令行参数
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --mode)
                RUN_MODE="$2"
                shift 2
                ;;
            --project)
                PROJECT_NAME="$2"
                shift 2
                ;;
            --language)
                LANGUAGE="$2"
                shift 2
                ;;
            --limit)
                TASK_LIMIT="$2"
                shift 2
                ;;
            --batch-size)
                BATCH_SIZE="$2"
                shift 2
                ;;
            --interval-hours)
                INTERVAL_HOURS="$2"
                shift 2
                ;;
            --max-workers)
                MAX_WORKERS="$2"
                shift 2
                ;;
            --check-interval)
                CHECK_INTERVAL="$2"
                shift 2
                ;;
            --config-file)
                CUSTOM_CONFIG_FILE="$2"
                shift 2
                ;;
            --host)
                API_HOST="$2"
                shift 2
                ;;
            --port)
                API_PORT="$2"
                shift 2
                ;;
            *)
                # 忽略未知参数，传递给主命令
                shift
                ;;
        esac
    done
}

# 构建启动命令参数
build_main_command() {
    local cmd="$VENV_DIR/bin/python -m app.main --mode $RUN_MODE"
    
    if [[ -n "$PROJECT_NAME" ]]; then
        cmd="$cmd --project $PROJECT_NAME"
    fi
    
    if [[ -n "$LANGUAGE" ]]; then
        cmd="$cmd --language $LANGUAGE"
    fi
    
    if [[ -n "$TASK_LIMIT" ]]; then
        cmd="$cmd --limit $TASK_LIMIT"
    fi
    
    if [[ "$CUSTOM_CONFIG_FILE" != "$CONFIG_FILE" ]]; then
        cmd="$cmd --config-file $CUSTOM_CONFIG_FILE"
    fi
    
    echo "$cmd"
}

# 启动主应用服务
start_main_service() {
    log_info "启动 Twitter Trend 主应用服务..."
    log_info "运行模式: $RUN_MODE"
    
    if [[ -n "$PROJECT_NAME" ]]; then
        log_info "指定项目: $PROJECT_NAME"
    fi
    
    if [[ -n "$LANGUAGE" ]]; then
        log_info "指定语言: $LANGUAGE"
    fi
    
    if [[ -n "$TASK_LIMIT" ]]; then
        log_info "任务限制: $TASK_LIMIT"
    fi
    
    # 检查并清理旧进程
    local existing_pids=$(pgrep -f "app/main.py" 2>/dev/null)
    if [[ -n "$existing_pids" ]]; then
        log_warn "发现已存在的main.py进程: $existing_pids"
        log_info "尝试停止旧进程..."
        stop_service
        sleep 2
    fi
    
    # 构建启动命令
    local main_command=$(build_main_command)
    
    # 启动主应用服务
    source "$VENV_DIR/bin/activate"
    cd "$PROJECT_ROOT"
    log_info "执行命令: $main_command"
    nohup $main_command > "$LOGS_DIR/main_service.log" 2>&1 &
    local main_pid=$!
    
    # 保存PID（追加到文件）
    echo $main_pid >> "$PID_FILE"
    
    # 等待服务启动
    local count=0
    while [[ $count -lt 30 ]]; do
        sleep 1
        ((count++))
        
        if kill -0 "$main_pid" 2>/dev/null; then
            log_info "主应用服务启动成功 (PID: $main_pid)"
            return 0
        fi
        
        echo -n "."
    done
    echo
    
    log_error "主应用服务启动失败，请检查日志: $LOGS_DIR/main_service.log"
    return 1
}

# 启动服务
start_service() {
    log_info "启动 Twitter Trend 服务..."
    
    # 启动API服务
    if start_api_service; then
        log_info "API服务启动成功"
    else
        log_error "API服务启动失败"
        return 1
    fi
    
    # 等待一段时间
    sleep 3
    
    # 检查数据库中是否有任务，如果没有则执行扫描
    log_info "检查数据库任务状态..."
    source "$VENV_DIR/bin/activate"
    cd "$PROJECT_ROOT"
    
    if python scripts/check_and_scan.py; then
        log_info "任务检查和扫描完成"
    else
        log_warn "任务检查和扫描过程中出现问题，但继续启动服务"
    fi
    
    # 启动主应用服务
    if start_main_service; then
        log_info "主应用服务启动成功"
        log_info "所有服务启动完成"
        return 0
    else
        log_error "主应用服务启动失败"
        return 1
    fi
}

# 停止服务
stop_service() {
    log_info "停止服务..."
    
    local pids_to_stop=()
    local failed_cleanup=false
    
    # 首先尝试从PID文件获取PID
    if [[ -f "$PID_FILE" ]]; then
        while IFS= read -r pid; do
            pid=$(echo "$pid" | tr -d '[:space:]')
            if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
                pids_to_stop+=("$pid")
                log_info "从PID文件找到进程: $pid"
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    
    # 多种方式查找相关进程，确保不遗漏
    # 方式1: 通过进程名特征查找
    local api_pids=$(pgrep -f "scripts/server/start_api.py" 2>/dev/null || true)
    local main_pids=$(pgrep -f "app.main" 2>/dev/null || true)
    local legacy_pids=$(pgrep -f "start_api.py\|app/main.py" 2>/dev/null || true)
    
    # 合并所有找到的PID
    for pid in $api_pids $main_pids $legacy_pids; do
        if [[ -n "$pid" ]] && [[ ! " ${pids_to_stop[@]} " =~ " ${pid} " ]]; then
            pids_to_stop+=("$pid")
            log_info "通过进程名特征找到进程: $pid"
        fi
    done
    
    if [[ ${#pids_to_stop[@]} -eq 0 ]]; then
        log_info "没有找到运行中的服务进程"
        return 0
    fi
    
    log_info "总共找到 ${#pids_to_stop[@]} 个进程需要停止: ${pids_to_stop[*]}"
    
    # 第一阶段：发送SIGTERM信号进行优雅停止
    for pid in "${pids_to_stop[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            log_info "发送SIGTERM信号到进程 $pid"
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    
    # 等待进程优雅退出（缩短等待时间到3秒）
    log_info "等待进程优雅退出..."
    sleep 3
    
    # 第二阶段：检查哪些进程仍在运行，立即强制终止
    local remaining_pids=()
    for pid in "${pids_to_stop[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            remaining_pids+=("$pid")
        fi
    done
    
    # 如果还有进程在运行，立即强制终止
    if [[ ${#remaining_pids[@]} -gt 0 ]]; then
        log_warn "以下进程未响应SIGTERM，立即发送SIGKILL强制终止: ${remaining_pids[*]}"
        for pid in "${remaining_pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                log_info "强制终止进程: $pid"
                kill -KILL "$pid" 2>/dev/null || {
                    log_error "无法终止进程 $pid，可能需要手动处理"
                    failed_cleanup=true
                }
            fi
        done
        
        # 再次等待确认进程被终止（增加等待时间）
        sleep 3
        
        # 最终验证：使用更可靠的进程检查方法
        local final_check_pids=()
        for pid in "${remaining_pids[@]}"; do
            # 使用ps命令检查进程是否真的还存在
            if ps -p "$pid" >/dev/null 2>&1; then
                final_check_pids+=("$pid")
                log_warn "进程 $pid 仍然存在，尝试再次强制终止"
                kill -KILL "$pid" 2>/dev/null || true
                sleep 1
                # 再次检查
                if ps -p "$pid" >/dev/null 2>&1; then
                    log_error "进程 $pid 无法终止"
                else
                    log_info "进程 $pid 已成功终止"
                fi
            else
                log_info "进程 $pid 已确认终止"
            fi
        done
        
        # 重新检查哪些进程真的无法清理
        local truly_failed_pids=()
        for pid in "${final_check_pids[@]}"; do
            if ps -p "$pid" >/dev/null 2>&1; then
                truly_failed_pids+=("$pid")
            fi
        done
        
        if [[ ${#truly_failed_pids[@]} -gt 0 ]]; then
            log_error "无法清理以下进程，请手动处理: ${truly_failed_pids[*]}"
            log_error "建议手动执行: kill -9 ${truly_failed_pids[*]}"
            failed_cleanup=true
        fi
    fi
    
    # 最后再次通过进程名检查是否有遗漏的进程
    local final_api_pids=$(pgrep -f "scripts/server/start_api.py" 2>/dev/null || true)
    local final_main_pids=$(pgrep -f "app.main" 2>/dev/null || true)
    
    if [[ -n "$final_api_pids" ]] || [[ -n "$final_main_pids" ]]; then
        log_warn "发现遗漏的进程，尝试清理: API($final_api_pids) Main($final_main_pids)"
        for pid in $final_api_pids $final_main_pids; do
            if [[ -n "$pid" ]]; then
                log_info "清理遗漏进程: $pid"
                kill -KILL "$pid" 2>/dev/null || true
            fi
        done
    fi
    
    if [[ "$failed_cleanup" == true ]]; then
        log_error "进程清理过程中遇到问题，部分进程可能需要手动处理"
        return 1
    else
        log_info "所有服务进程已成功停止"
        return 0
    fi
}

# 重启服务
restart_service() {
    log_info "重启 Twitter Trend 服务..."
    
    # 停止服务
    if ! stop_service; then
        log_error "停止服务时遇到问题，可能存在僵尸进程"
        log_warn "建议检查是否有残留进程需要手动清理"
        log_warn "继续尝试启动新服务..."
    fi
    
    # 等待一段时间确保资源释放
    sleep 5
    
    # 启动服务
    if start_service; then
        log_info "服务重启成功"
        return 0
    else
        log_error "服务重启失败"
        return 1
    fi
}

# 检查服务状态
check_status() {
    log_info "检查服务状态..."
    
    local api_running=false
    local main_running=false
    
    # 检查API服务（使用更精确的进程名匹配）
    local api_pids=$(pgrep -f "scripts/server/start_api.py" 2>/dev/null)
    # 兼容旧版本的进程名
    if [[ -z "$api_pids" ]]; then
        api_pids=$(pgrep -f "start_api.py" 2>/dev/null)
    fi
    if [[ -n "$api_pids" ]]; then
        log_info "API服务正在运行，PID: $api_pids"
        api_running=true
    else
        log_warn "API服务未运行"
    fi
    
    # 检查主应用服务（使用更精确的进程名匹配）
    local main_pids=$(pgrep -f "app.main" 2>/dev/null)
    # 兼容旧版本的进程名
    if [[ -z "$main_pids" ]]; then
        main_pids=$(pgrep -f "app/main.py" 2>/dev/null)
    fi
    if [[ -n "$main_pids" ]]; then
        log_info "主应用服务正在运行，PID: $main_pids"
        main_running=true
    else
        log_warn "主应用服务未运行"
    fi
    
    if [[ "$api_running" == true ]] && [[ "$main_running" == true ]]; then
        log_info "所有服务正常运行"
        return 0
    elif [[ "$api_running" == true ]] || [[ "$main_running" == true ]]; then
        log_warn "部分服务在运行"
        return 2
    else
        log_info "服务未运行"
        return 1
    fi
}

# 查看日志
view_logs() {
    local log_type=${1:-"api"}
    local lines=${2:-50}
    local log_file=""
    
    case $log_type in
        "api") log_file="$LOGS_DIR/api_service.log" ;;
        "main") log_file="$LOGS_DIR/main_service.log" ;;
        "app") log_file="$LOGS_DIR/app.log" ;;
        "deploy") log_file="$LOG_FILE" ;;
        *)
            log_error "未知的日志类型: $log_type"
            echo "可用的日志类型: api, main, app, deploy"
            return 1
            ;;
    esac
    
    if [[ -n "$log_file" ]] && [[ -f "$log_file" ]]; then
        echo -e "${BLUE}显示 $log_type 日志 (文件: $(basename "$log_file"), 最后 $lines 行):${NC}"
        tail -n "$lines" "$log_file"
    else
        log_warn "日志文件不存在: $log_type"
    fi
}

# 监控日志
monitor_logs() {
    local log_type=${1:-"api"}
    local log_file=""
    
    case $log_type in
        "api") log_file="$LOGS_DIR/api_service.log" ;;
        "main") log_file="$LOGS_DIR/main_service.log" ;;
        "app") log_file="$LOGS_DIR/app.log" ;;
        *)
            log_error "未知的日志类型: $log_type"
            return 1
            ;;
    esac
    
    if [[ -n "$log_file" ]] && [[ -f "$log_file" ]]; then
        echo -e "${BLUE}实时监控 $log_type 日志 (文件: $(basename "$log_file")), 按 Ctrl+C 退出:${NC}"
        tail -f "$log_file"
    else
        log_warn "日志文件不存在: $log_type"
    fi
}

# 备份数据
backup_data() {
    log_info "备份数据..."
    local backup_dir="$DATA_DIR/backups"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$backup_dir/twitter_trend_backup_$timestamp.tar.gz"
    mkdir -p "$backup_dir"
    tar -czf "$backup_file" \
        -C "$PROJECT_ROOT" \
        --exclude='.venv' \
        --exclude='logs' \
        --exclude='data/backups' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        .
    log_info "备份完成: $backup_file"
    cd "$backup_dir"
    ls -t twitter_trend_backup_*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm
    log_info "旧备份清理完成"
}

# 更新项目
update_project() {
    log_info "更新项目..."
    backup_data
    if [[ -d "$PROJECT_ROOT/.git" ]]; then
        log_info "拉取最新代码..."
        cd "$PROJECT_ROOT"
        git pull
    fi
    install_python_dependencies
    validate_configuration
    log_info "项目更新完成"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    local issues=0
    
    if check_status > /dev/null; then
        log_info "✓ 服务正在运行"
    else
        log_error "✗ 服务未运行"
        ((issues++))
    fi

    local disk_usage=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -lt 90 ]]; then
        log_info "✓ 磁盘空间充足 ($disk_usage% 已使用)"
    else
        log_warn "⚠ 磁盘空间不足 ($disk_usage% 已使用)"
        ((issues++))
    fi
    
    if [[ -f "$ENV_FILE" ]]; then
        log_info "✓ 环境变量文件存在"
    else
        log_error "✗ 环境变量文件不存在"
        ((issues++))
    fi
    
    if [[ -f "$REQUIREMENTS_FILE" ]]; then
        log_info "✓ 依赖文件存在"
    else
        log_error "✗ 依赖文件不存在"
        ((issues++))
    fi
    
    echo "--------------------"
    if [[ $issues -eq 0 ]]; then
        log_info "健康检查通过"
        return 0
    else
        log_warn "健康检查发现 $issues 个问题"
        return 1
    fi
}

# 运行测试
run_tests() {
    log_info "运行测试套件..."
    source "$VENV_DIR/bin/activate"
    cd "$PROJECT_ROOT"
    
    # 运行单元测试
    log_info "运行单元测试..."
    if python -m pytest tests/unit/ -v; then
        log_info "单元测试通过"
    else
        log_warn "单元测试有失败"
    fi
    
    # 运行集成测试
    log_info "运行集成测试..."
    if python -m pytest tests/integration/ -v; then
        log_info "集成测试通过"
    else
        log_warn "集成测试有失败"
    fi
}

# 显示帮助信息
show_help() {
    echo -e "${BLUE}Twitter Trend 项目部署和运维脚本${NC}"
    echo ""
    echo "用法: $0 [命令] [选项] [配置参数]"
    echo ""
    echo "命令:"
    echo "  install     - 完整安装和部署项目"
    echo "  start       - 启动服务"
    echo "  stop        - 停止服务"
    echo "  restart     - 重启服务"
    echo "  status      - 检查服务状态"
    echo "  logs        - 查看日志 [类型] [行数]"
    echo "  monitor     - 实时监控日志 [类型]"
    echo "  backup      - 备份数据"
    echo "  update      - 更新项目"
    echo "  health      - 健康检查"
    echo "  test        - 运行测试套件"
    echo "  config      - 显示当前配置参数"
    echo "  db-query    - 数据库查询和校验 [查询类型]"
    echo "  query       - 数据库查询和校验 [查询类型] (db-query的别名)"
    echo "  help        - 显示此帮助信息"
    echo ""
    echo "配置参数 (仅适用于 start/restart 命令):"
    echo "  --mode MODE           - 运行模式: continuous, single, status, management (默认: continuous)"
    echo "  --project PROJECT     - 指定项目名称"
    echo "  --language LANG       - 指定语言: en, cn, ja"
    echo "  --limit NUMBER        - 限制处理的任务数量"
    echo "  --batch-size NUMBER   - 批量处理大小 (默认: 3)"
    echo "  --interval-hours NUM  - 发布间隔小时数 (默认: 48)"
    echo "  --max-workers NUM     - 最大工作线程数 (默认: 2)"
    echo "  --check-interval NUM  - 检查间隔秒数 (默认: 60)"
    echo "  --config-file PATH    - 指定配置文件路径"
    echo "  --host HOST           - API服务绑定地址 (默认: 127.0.0.1, 服务器部署建议: 0.0.0.0)"
    echo "  --port PORT           - API服务端口 (默认: 8050)"
    echo ""
    echo "日志类型:"
    echo "  api         - API服务日志 (默认)"
    echo "  main        - 主应用日志"
    echo "  app         - 应用日志"
    echo "  deploy      - 部署脚本日志"
    echo ""
    echo "数据库查询类型:"
    echo "  tools       - 显示所有可用的数据库查询工具"
    echo "  commands    - 显示常用的数据库查询命令"
    echo "  validate    - 执行完整的数据库校验"
    echo "  overview    - 显示数据库概览信息"
    echo "  health      - 数据库健康检查"
    echo "  tasks       - 显示任务摘要"
    echo "  pending     - 显示待发布任务"
    echo "  recent      - 显示最近任务"
    echo "  urgent      - 显示紧急任务"
    echo "  backup      - 执行数据库备份"
    echo "  integrity   - 数据库完整性检查"
    echo ""
    echo "示例:"
    echo "  $0 install                                    # 完整安装"
    echo "  $0 start                                      # 使用默认配置启动服务"
    echo "  $0 start --host 0.0.0.0                      # 服务器部署，绑定所有网络接口"
    echo "  $0 start --host 0.0.0.0 --port 8080          # 自定义host和端口启动"
    echo "  $0 start --mode single --limit 5             # 单次处理5个任务"
    echo "  $0 start --project myproject --language en   # 指定项目和语言启动"
    echo "  $0 restart --batch-size 2 --max-workers 1   # 使用自定义配置重启"
    echo "  $0 logs main 100                             # 查看主应用日志最后100行"
    echo "  $0 monitor api                               # 实时监控API日志"
    echo "  $0 config                                    # 显示当前配置"
    echo "  $0 test                                      # 运行测试"
    echo "  $0 db-query overview                         # 查看数据库概览"
    echo "  $0 query health                              # 数据库健康检查"
    echo "  $0 db-query validate                         # 完整数据库校验"
    echo "  $0 query pending                             # 查看待发布任务"
    echo ""
}

# 完整安装
full_install() {
    log_info "开始完整安装 Twitter Trend 项目..."
    detect_os
    create_directories
    check_system_dependencies
    install_system_packages
    setup_virtual_environment
    install_python_dependencies
    check_configuration
    validate_configuration
    log_info "安装完成！"
    log_info "请确保 .env 文件已正确配置，然后运行: $0 start"
}

# 显示当前配置
show_config() {
    echo -e "${BLUE}当前配置参数:${NC}"
    echo "  运行模式: $RUN_MODE"
    echo "  项目名称: ${PROJECT_NAME:-'未指定'}"
    echo "  语言设置: ${LANGUAGE:-'未指定'}"
    echo "  任务限制: ${TASK_LIMIT:-'未指定'}"
    echo "  批量大小: $BATCH_SIZE"
    echo "  发布间隔: $INTERVAL_HOURS 小时"
    echo "  最大工作线程: $MAX_WORKERS"
    echo "  检查间隔: $CHECK_INTERVAL 秒"
    echo "  API绑定地址: $API_HOST"
    echo "  API端口: $API_PORT"
    echo "  配置文件: $CUSTOM_CONFIG_FILE"
    echo ""
    echo -e "${BLUE}配置文件内容 (关键部分):${NC}"
    if [[ -f "$CUSTOM_CONFIG_FILE" ]]; then
        echo "  安全配置:"
        grep -A 5 "security:" "$CUSTOM_CONFIG_FILE" | grep -E "max_requests_per_minute|rate_limiting" | sed 's/^/    /'
        echo "  调度配置:"
        grep -A 10 "scheduling:" "$CUSTOM_CONFIG_FILE" | grep -E "interval_hours|batch_size|max_workers|check_interval" | sed 's/^/    /'
    else
        echo "  配置文件不存在: $CUSTOM_CONFIG_FILE"
    fi
}

# 数据库查询和校验功能
db_query() {
    log_info "执行数据库查询和校验..."
    
    cd "$PROJECT_ROOT"
    
    # 检查虚拟环境
    if [[ ! -d "$VENV_DIR" ]]; then
        log_error "虚拟环境不存在，请先运行: ./deploy_twitter.sh install"
        exit 1
    fi
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    
    # 检查数据库查询工具
    if [[ ! -f "scripts/database/db_query_summary.py" ]]; then
        log_error "数据库查询工具不存在: scripts/database/db_query_summary.py"
        exit 1
    fi
    
    local query_type="${1:-list}"
    
    case "$query_type" in
        "list")
            log_info "显示所有可用的数据库查询工具"
            python scripts/database/db_query_summary.py --list
            ;;
        "common")
            log_info "显示常用查询命令"
            python scripts/database/db_query_summary.py --common
            ;;
        "validate")
            log_info "执行完整的数据库校验"
            python scripts/database/db_query_summary.py --validate
            ;;
        "overview")
            log_info "显示数据库概览"
            python scripts/database/db_query_summary.py --query overview
            ;;
        "health")
            log_info "执行数据库健康检查"
            python scripts/database/db_query_summary.py --query health_check
            ;;
        "tasks")
            log_info "显示任务摘要"
            python scripts/database/db_query_summary.py --query task_summary
            ;;
        "pending")
            log_info "显示待发布任务"
            python scripts/database/db_query_summary.py --query pending_tasks
            ;;
        "recent")
            log_info "显示最近任务"
            python scripts/database/db_query_summary.py --query recent_tasks
            ;;
        "urgent")
            log_info "显示紧急任务"
            python scripts/database/db_query_summary.py --query urgent_tasks
            ;;
        "backup")
            log_info "执行数据库备份"
            python scripts/database/db_query_summary.py --query backup_db
            ;;
        "integrity")
            log_info "执行完整性检查"
            python scripts/database/db_query_summary.py --query integrity_check
            ;;
        "interactive")
            log_info "启动交互式数据库查看器"
            python scripts/database/enhanced_db_viewer.py --mode interactive
            ;;
        "monitor")
            log_info "启动系统监控仪表板"
            python scripts/database/system_monitor.py
            ;;
        *)
            log_info "显示数据库查询工具列表"
            python scripts/database/db_query_summary.py --list
            echo
            log_info "可用的查询选项:"
            echo "  list        - 显示所有可用工具"
            echo "  common      - 显示常用查询命令"
            echo "  validate    - 执行完整数据库校验"
            echo "  overview    - 显示数据库概览"
            echo "  health      - 执行健康检查"
            echo "  tasks       - 显示任务摘要"
            echo "  pending     - 显示待发布任务"
            echo "  recent      - 显示最近任务"
            echo "  urgent      - 显示紧急任务"
            echo "  backup      - 执行数据库备份"
            echo "  integrity   - 执行完整性检查"
            echo "  interactive - 启动交互式查看器"
            echo "  monitor     - 启动系统监控仪表板"
            ;;
    esac
}

# 主函数
main() {
    mkdir -p "$LOGS_DIR"
    
    # 保存原始参数
    local original_args=("$@")
    local command="${1:-help}"
    
    # 对于需要参数解析的命令，先解析参数
    if [[ "$command" == "start" ]] || [[ "$command" == "restart" ]]; then
        shift  # 移除命令参数
        parse_arguments "$@"
    fi
    
    case "$command" in
        "install") full_install ;;
        "start") detect_os; start_service ;;
        "stop") stop_service ;;
        "restart") detect_os; restart_service ;;
        "status") check_status ;;
        "logs") view_logs "${original_args[1]:-api}" "${original_args[2]:-50}" ;;
        "monitor") monitor_logs "${original_args[1]:-api}" ;;
        "backup") backup_data ;;
        "update") detect_os; update_project ;;
        "health") health_check ;;
        "test") run_tests ;;
        "config") show_config ;;
        "db-query"|"query") db_query "${original_args[1]:-list}" ;;
        "help") show_help ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"