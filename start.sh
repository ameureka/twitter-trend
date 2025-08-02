#!/bin/bash
# 启动增强版Twitter自动发布系统

set -e

echo "启动增强版Twitter自动发布系统..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3"
    exit 1
fi

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv .venv
fi

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

# 初始化数据库
echo "初始化数据库..."
python app/main.py init-enhanced-db

# 启动系统
echo "启动系统..."
python app/main.py --mode continuous
