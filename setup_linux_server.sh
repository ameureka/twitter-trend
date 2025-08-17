#!/bin/bash

# Twitter 自动发布系统 - Linux 服务器部署脚本
# 适用于 Ubuntu/CentOS/RHEL 等 Linux 发行版

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 获取当前脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="$SCRIPT_DIR"

# 检查操作系统
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/debian_version ]; then
            OS="debian"
            PKG_MANAGER="apt"
        elif [ -f /etc/redhat-release ]; then
            OS="redhat"
            PKG_MANAGER="yum"
        else
            OS="linux"
            PKG_MANAGER="unknown"
        fi
    else
        log_error "此脚本仅支持 Linux 系统"
        exit 1
    fi
    log_info "检测到操作系统: $OS"
}

# 安装系统依赖
install_system_deps() {
    log_step "安装系统依赖..."
    
    case $PKG_MANAGER in
        "apt")
            sudo apt update
            sudo apt install -y python3 python3-pip python3-venv git curl jq
            ;;
        "yum")
            sudo yum update -y
            sudo yum install -y python3 python3-pip git curl jq
            ;;
        *)
            log_warn "未知的包管理器，请手动安装: python3, python3-pip, python3-venv, git, curl, jq"
            ;;
    esac
}

# 设置 Python 虚拟环境
setup_venv() {
    log_step "设置 Python 虚拟环境..."
    
    cd "$PROJECT_PATH"
    
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        log_info "虚拟环境创建成功"
    else
        log_info "虚拟环境已存在"
    fi
    
    source .venv/bin/activate
    pip install --upgrade pip
    
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        log_info "Python 依赖安装完成"
    else
        log_error "requirements.txt 文件不存在"
        exit 1
    fi
}

# 配置环境变量
setup_env() {
    log_step "配置环境变量..."
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_warn "已创建 .env 文件，请编辑并填入正确的 API 密钥"
            log_warn "编辑命令: nano .env"
        else
            log_error ".env.example 文件不存在"
            exit 1
        fi
    else
        log_info ".env 文件已存在"
    fi
}

# 创建必要的目录
setup_directories() {
    log_step "创建必要的目录..."
    
    mkdir -p logs
    mkdir -p data/backups
    mkdir -p data/cache
    mkdir -p data/analytics
    
    log_info "目录结构创建完成"
}

# 设置 cron 任务（仅维护性任务）
setup_cron() {
    log_step "设置 cron 维护任务..."
    
    # 备份当前 crontab
    crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    
    # 创建新的 crontab 内容（仅包含维护性任务，发布调度由 enhanced_config.yaml 控制）
    cat > /tmp/twitter_cron << EOF
# Twitter 自动发布系统 - 维护性 cron 任务
# 注意：内容发布调度由 enhanced_config.yaml 中的 scheduling 配置控制
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
PROJECT_PATH=$PROJECT_PATH

# 每天凌晨2点重置卡住的任务
0 2 * * * cd \$PROJECT_PATH && ./deploy_twitter.sh reset >> logs/cron.log 2>&1

# 每天凌晨3点进行健康检查
0 3 * * * cd \$PROJECT_PATH && ./deploy_twitter.sh health >> logs/cron.log 2>&1

# 每周日凌晨4点查看状态统计
0 4 * * 0 cd \$PROJECT_PATH && ./deploy_twitter.sh status >> logs/cron.log 2>&1
EOF

    # 询问用户是否要安装 cron 任务
    echo
    log_warn "即将安装以下维护性 cron 任务:"
    cat /tmp/twitter_cron
    echo
    log_info "注意：内容发布调度由 enhanced_config.yaml 配置文件控制，无需 cron 任务"
    echo
    read -p "是否要安装这些维护性 cron 任务? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # 合并现有 crontab 和新任务
        (crontab -l 2>/dev/null || true; echo; cat /tmp/twitter_cron) | crontab -
        log_info "维护性 Cron 任务安装成功"
        log_info "查看 cron 任务: crontab -l"
        log_info "查看 cron 日志: tail -f logs/cron.log"
    else
        log_info "跳过维护性 cron 任务安装"
        log_info "手动安装命令: crontab /tmp/twitter_cron"
    fi
    
    # 清理临时文件
    rm -f /tmp/twitter_cron
}

# 设置系统服务 (systemd)
setup_systemd() {
    log_step "设置 systemd 服务..."
    
    # 创建 systemd 服务文件
    cat > /tmp/twitter-trend.service << EOF
[Unit]
Description=Twitter Trend Auto Publisher
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_PATH
Environment=PATH=$PROJECT_PATH/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$PROJECT_PATH/.venv/bin/python -m app.main --mode continuous
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_PATH/logs/systemd.log
StandardError=append:$PROJECT_PATH/logs/systemd.log

[Install]
WantedBy=multi-user.target
EOF

    echo
    log_warn "即将创建 systemd 服务文件:"
    cat /tmp/twitter-trend.service
    echo
    read -p "是否要安装 systemd 服务? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo cp /tmp/twitter-trend.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable twitter-trend.service
        log_info "Systemd 服务安装成功"
        log_info "启动服务: sudo systemctl start twitter-trend"
        log_info "查看状态: sudo systemctl status twitter-trend"
        log_info "查看日志: tail -f logs/systemd.log"
    else
        log_info "跳过 systemd 服务安装"
    fi
    
    # 清理临时文件
    rm -f /tmp/twitter-trend.service
}

# 测试部署
test_deployment() {
    log_step "测试部署..."
    
    cd "$PROJECT_PATH"
    source .venv/bin/activate
    
    # 测试基本功能
    if [ -f "deploy_twitter.sh" ]; then
        chmod +x deploy_twitter.sh
        ./deploy_twitter.sh health
        log_info "部署脚本测试通过"
    else
        log_error "deploy_twitter.sh 文件不存在"
        exit 1
    fi
}

# 显示使用说明
show_usage() {
    echo
    log_info "=== Linux 服务器部署完成 ==="
    echo
    echo "项目路径: $PROJECT_PATH"
    echo
    echo "常用命令:"
    echo "  启动服务:     ./deploy_twitter.sh start"
    echo "  停止服务:     ./deploy_twitter.sh stop"
    echo "  查看状态:     ./deploy_twitter.sh status"
    echo "  健康检查:     ./deploy_twitter.sh health"
    echo "  查看日志:     ./deploy_twitter.sh logs"
    echo
    echo "数据库查询和校验:"
    echo "  查询工具列表: ./setup_linux_server.sh --db-query list"
    echo "  常用查询命令: ./setup_linux_server.sh --db-query common"
    echo "  完整数据校验: ./setup_linux_server.sh --db-query validate"
    echo "  数据库概览:   ./setup_linux_server.sh --db-query overview"
    echo "  健康检查:     ./setup_linux_server.sh --db-query health"
    echo "  任务摘要:     ./setup_linux_server.sh --db-query tasks"
    echo "  待发布任务:   ./setup_linux_server.sh --db-query pending"
    echo "  最近任务:     ./setup_linux_server.sh --db-query recent"
    echo "  紧急任务:     ./setup_linux_server.sh --db-query urgent"
    echo "  数据库备份:   ./setup_linux_server.sh --db-query backup"
    echo "  完整性检查:   ./setup_linux_server.sh --db-query integrity"
    echo
    echo "发布调度配置:"
    echo "  配置文件:     config/enhanced_config.yaml (scheduling 部分)"
    echo "  发布间隔:     由 interval_hours 参数控制 (默认24小时)"
    echo "  批次大小:     由 batch_size 参数控制 (默认3个)"
    echo
    echo "维护性 Cron 任务管理:"
    echo "  查看任务:     crontab -l"
    echo "  编辑任务:     crontab -e"
    echo "  查看日志:     tail -f logs/cron.log"
    echo
    echo "Systemd 服务管理:"
    echo "  启动服务:     sudo systemctl start twitter-trend"
    echo "  停止服务:     sudo systemctl stop twitter-trend"
    echo "  查看状态:     sudo systemctl status twitter-trend"
    echo "  查看日志:     tail -f logs/systemd.log"
    echo
    log_warn "请确保已正确配置 .env 文件中的 API 密钥!"
}

# 数据库查询和校验功能
db_query() {
    log_step "执行数据库查询和校验..."
    
    cd "$PROJECT_PATH"
    source .venv/bin/activate
    
    if [ ! -f "scripts/database/db_query_summary.py" ]; then
        log_error "数据库查询工具不存在: scripts/database/db_query_summary.py"
        return 1
    fi
    
    case "$1" in
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
        *)
            log_info "显示数据库查询工具列表"
            python scripts/database/db_query_summary.py --list
            echo
            log_info "可用的查询选项:"
            echo "  list      - 显示所有可用工具"
            echo "  common    - 显示常用查询命令"
            echo "  validate  - 执行完整数据库校验"
            echo "  overview  - 显示数据库概览"
            echo "  health    - 执行健康检查"
            echo "  tasks     - 显示任务摘要"
            echo "  pending   - 显示待发布任务"
            echo "  recent    - 显示最近任务"
            echo "  urgent    - 显示紧急任务"
            echo "  backup    - 执行数据库备份"
            echo "  integrity - 执行完整性检查"
            ;;
    esac
}

# 显示帮助信息
show_help() {
    echo "Twitter 自动发布系统 - Linux 服务器部署脚本"
    echo ""
    echo "使用方法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --auto               自动化部署（跳过所有交互式询问）"
    echo "  --with-cron          自动设置 cron 维护任务"
    echo "  --with-systemd       自动设置 systemd 后台服务"
    echo "  --with-validation    自动执行数据库校验"
    echo "  --full               完整自动化部署（包含所有选项）"
    echo "  -q, --db-query CMD   执行数据库查询命令"
    echo "  --help               显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                   # 交互式部署"
    echo "  $0 --auto           # 基础自动化部署"
    echo "  $0 --full           # 完整自动化部署"
    echo "  $0 --with-systemd   # 部署并设置后台服务"
    echo "  $0 -q validate      # 执行数据库校验"
}

# 主函数
main() {
    # 默认配置
    AUTO_MODE=false
    SETUP_CRON=false
    SETUP_SYSTEMD=false
    RUN_VALIDATION=false
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --auto)
                AUTO_MODE=true
                shift
                ;;
            --with-cron)
                SETUP_CRON=true
                shift
                ;;
            --with-systemd)
                SETUP_SYSTEMD=true
                shift
                ;;
            --with-validation)
                RUN_VALIDATION=true
                shift
                ;;
            --full)
                AUTO_MODE=true
                SETUP_CRON=true
                SETUP_SYSTEMD=true
                RUN_VALIDATION=true
                shift
                ;;
            -q|--db-query)
                shift
                db_query "$1"
                return
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    echo "=== Twitter 自动发布系统 - Linux 服务器部署脚本 ==="
    echo
    
    detect_os
    install_system_deps
    setup_venv
    setup_env
    setup_directories
    test_deployment
    
    echo
    log_info "基础部署完成!"
    echo
    
    # 根据模式决定是否设置维护性任务
    if [ "$AUTO_MODE" = true ] || [ "$SETUP_CRON" = true ]; then
        log_info "自动设置 cron 维护性任务..."
        setup_cron
    elif [ "$AUTO_MODE" = false ]; then
        read -p "是否要设置 cron 维护性任务（重置、健康检查、状态统计）? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            setup_cron
        fi
    fi
    
    # 根据模式决定是否设置 systemd 服务
    echo
    if [ "$AUTO_MODE" = true ] || [ "$SETUP_SYSTEMD" = true ]; then
        log_info "自动设置 systemd 后台服务..."
        setup_systemd
    elif [ "$AUTO_MODE" = false ]; then
        read -p "是否要设置 systemd 后台服务? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            setup_systemd
        fi
    fi
    
    # 根据模式决定是否执行数据库校验
    echo
    if [ "$AUTO_MODE" = true ] || [ "$RUN_VALIDATION" = true ]; then
        log_info "自动执行数据库校验..."
        db_query "validate"
    elif [ "$AUTO_MODE" = false ]; then
        read -p "是否要执行数据库校验? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            db_query "validate"
        fi
    fi
    
    show_usage
}

# 检查是否以 root 权限运行
if [ "$EUID" -eq 0 ]; then
    log_error "请不要以 root 权限运行此脚本"
    exit 1
fi

# 运行主函数
main "$@"