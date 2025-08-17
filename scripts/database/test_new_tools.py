#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新数据库工具测试脚本
演示新开发的5个数据库管理工具的功能
"""

import subprocess
import sys
import time
from datetime import datetime

def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"📝 命令: {cmd}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"❌ 错误 (退出码: {result.returncode})")
            if result.stderr:
                print(f"错误信息: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("⏰ 命令超时")
    except Exception as e:
        print(f"❌ 执行失败: {e}")

def main():
    """主测试函数"""
    print(f"🚀 Twitter 自动发布系统 - 新数据库工具测试")
    print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}")
    
    # 测试命令列表
    test_commands = [
        # 快速监控器
        ("python quick_db_monitor.py", "快速监控仪表板"),
        ("python quick_db_monitor.py --urgent", "紧急任务查看"),
        
        # 增强版数据库查看器
        ("python enhanced_db_viewer.py --mode overview", "数据库概览"),
        ("python enhanced_db_viewer.py --mode pending --limit 3", "待发布任务 (前3个)"),
        
        # 任务管理器
        ("python task_manager.py --stats", "任务统计报告"),
        ("python task_manager.py --list --limit 3", "任务列表 (前3个)"),
        
        # 数据库管理员
        ("python db_admin.py --overview", "数据库管理概览"),
        ("python db_admin.py --tables", "数据库表结构"),
        
        # 系统监控器
        ("python system_monitor.py --health", "系统健康检查"),
        ("python system_monitor.py --metrics", "系统指标"),
    ]
    
    # 执行测试
    for cmd, desc in test_commands:
        run_command(cmd, desc)
        time.sleep(1)  # 短暂延迟
    
    print(f"\n{'='*80}")
    print("✅ 所有测试完成！")
    print("\n📋 新工具功能总结:")
    print("  🔍 quick_db_monitor.py - 快速状态监控")
    print("  📊 enhanced_db_viewer.py - 全面数据库查看")
    print("  📝 task_manager.py - 高级任务管理")
    print("  🗄️ db_admin.py - 数据库维护管理")
    print("  🖥️ system_monitor.py - 系统性能监控")
    print("\n📖 详细使用说明请查看: DATABASE_TOOLS_README.md")

if __name__ == "__main__":
    main()