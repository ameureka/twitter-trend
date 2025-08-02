#!/bin/bash

# Twitter 自动发布系统安装脚本

echo "=== Twitter 自动发布系统安装脚本 ==="
echo

# 检查Python版本
echo "检查Python版本..."
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
    echo "✓ Python版本检查通过: $python_version"
else
    echo "✗ Python版本过低，需要3.9+，当前版本: $python_version"
    exit 1
fi

echo

# 安装依赖
echo "安装Python依赖包..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✓ 依赖包安装成功"
else
    echo "✗ 依赖包安装失败"
    exit 1
fi

echo

# 创建必要目录
echo "创建必要目录..."
mkdir -p data logs
echo "✓ 目录创建完成"

echo

# 检查配置文件
echo "检查配置文件..."
if [ ! -f ".env" ]; then
    echo "⚠ .env文件不存在，从模板复制..."
    cp .env.example .env
    echo "✓ .env文件已创建，请编辑填写API密钥"
else
    echo "✓ .env文件已存在"
fi

if [ ! -f "config.yaml" ]; then
    echo "✗ config.yaml文件不存在"
    exit 1
else
    echo "✓ config.yaml文件已存在"
fi

echo

# 检查增强版配置文件
echo "检查增强版配置文件..."
if [ ! -f "config/enhanced_config.yaml" ]; then
    echo "✗ config/enhanced_config.yaml文件不存在"
    exit 1
else
    echo "✓ config/enhanced_config.yaml文件已存在"
fi

# 创建增强版必要目录
echo "创建增强版必要目录..."
mkdir -p data logs projects backups/config backups/database data/analytics data/cache
echo "✓ 增强版目录创建完成"

# 运行增强版系统健康检查
echo "运行增强版系统健康检查..."
python3 app/main.py --mode health 2>/dev/null || echo "⚠ 增强版健康检查需要完整配置"

echo
echo "=== 增强版安装完成 ==="
echo
echo "下一步操作:"
echo "1. 编辑 .env 文件，填写Twitter API密钥和Gemini API密钥"
echo "2. (可选) 编辑 config/enhanced_config.yaml 调整高级配置"
echo "3. 运行单次处理: python3 app/main.py --mode single"
echo "4. 启动调度器: python3 app/main.py --mode scheduler"
echo "5. 查看状态: python3 app/main.py --mode status"
echo "6. 启动API服务: python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8050"
echo
echo "增强版功能:"
echo "- AI内容生成 (Gemini)"
echo "- 智能任务调度"
echo "- 性能监控"
echo "- 详细分析报告"
echo "- Web管理界面"
echo
echo "详细使用说明请查看 README.md 和 docs/enhanced_system_architecture.md"