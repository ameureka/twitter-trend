#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库查询功能汇总 - 统一的数据库查询和校验工具
整合所有数据库查询脚本的功能，提供统一的接口
"""

import sys
import os
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class DatabaseQuerySummary:
    """
    数据库查询功能汇总类
    整合所有数据库查询和校验功能
    """
    
    def __init__(self, db_path: str = 'data/twitter_publisher.db'):
        self.db_path = db_path
        self.available_tools = {
            'enhanced_viewer': {
                'description': '增强版数据库查看器 - 统一的数据库查看和管理工具',
                'script': 'enhanced_db_viewer.py',
                'functions': [
                    'overview - 显示数据库概览',
                    'pending - 显示待发布任务',
                    'recent - 显示最近任务',
                    'projects - 显示项目信息',
                    'health - 健康检查',
                    'interactive - 交互模式',
                    'task-id <ID> - 显示任务详情'
                ]
            },
            'task_query': {
                'description': '任务查询工具 - 提供数据库任务查询和统计功能',
                'script': 'task_query.py',
                'functions': [
                    'summary - 显示综合摘要',
                    'status <状态> - 按状态过滤任务',
                    'project <项目名> - 按项目名称过滤任务',
                    'priority <优先级> - 按优先级过滤任务',
                    'task-id <ID> - 查询特定任务详细信息',
                    'recent <数量> - 显示最近的N个任务'
                ]
            },
            'quick_monitor': {
                'description': '快速数据库监控器 - 简化版数据库状态查看工具',
                'script': 'quick_db_monitor.py',
                'functions': [
                    'dashboard - 显示仪表板（默认）',
                    'urgent - 显示紧急任务',
                    'activity - 显示最近活动',
                    'projects - 显示项目摘要',
                    'health - 系统健康检查',
                    'all - 显示所有信息'
                ]
            },
            'db_admin': {
                'description': '数据库管理员工具 - 统一的数据库管理和维护工具',
                'script': 'db_admin.py',
                'functions': [
                    'overview - 显示数据库概览',
                    'backup <类型> - 备份数据库 (full/schema_only/data_only)',
                    'restore <文件> - 从备份恢复数据库',
                    'list-backups - 列出所有备份',
                    'maintenance <操作> - 执行维护操作 (vacuum/reindex/analyze/integrity_check/optimize)',
                    'export <表名> - 导出表数据',
                    'import <表名> - 导入表数据',
                    'schema <表名> - 显示表结构',
                    'query "<SQL>" - 执行自定义查询'
                ]
            },
            'system_monitor': {
                'description': '系统监控器 - 实时监控Twitter发布系统的运行状态',
                'script': 'system_monitor.py',
                'functions': [
                    'dashboard - 显示系统仪表板（默认）',
                    'health - 执行健康检查',
                    'processes - 显示进程详细信息',
                    'performance - 显示性能报告',
                    'watch <秒数> - 实时监控'
                ]
            }
        }
    
    def show_available_tools(self):
        """显示所有可用的数据库查询工具"""
        print("\n📊 数据库查询和校验工具汇总")
        print("=" * 60)
        
        for tool_name, tool_info in self.available_tools.items():
            print(f"\n🔧 {tool_name.upper()}")
            print(f"   描述: {tool_info['description']}")
            print(f"   脚本: {tool_info['script']}")
            print("   功能:")
            for func in tool_info['functions']:
                print(f"     • {func}")
    
    def get_common_queries(self) -> Dict[str, str]:
        """获取常用查询命令"""
        return {
            # 新的简化查询类型
            'overview': 'python scripts/database/enhanced_db_viewer.py --mode overview',
            'health': 'python scripts/database/enhanced_db_viewer.py --mode health',
            'tasks': 'python scripts/database/task_query.py --summary',
            'pending': 'python scripts/database/enhanced_db_viewer.py --mode pending',
            'recent': 'python scripts/database/enhanced_db_viewer.py --mode recent',
            'urgent': 'python scripts/database/quick_db_monitor.py --urgent',
            'backup': 'python scripts/database/db_admin.py --backup full',
            'integrity': 'python scripts/database/db_admin.py --maintenance integrity_check',
            # 保留旧的查询类型以兼容性
            'pending_tasks': 'python scripts/database/enhanced_db_viewer.py --mode pending',
            'recent_tasks': 'python scripts/database/enhanced_db_viewer.py --mode recent',
            'project_summary': 'python scripts/database/enhanced_db_viewer.py --mode projects',
            'health_check': 'python scripts/database/enhanced_db_viewer.py --mode health',
            'task_summary': 'python scripts/database/task_query.py --summary',
            'quick_dashboard': 'python scripts/database/quick_db_monitor.py',
            'urgent_tasks': 'python scripts/database/quick_db_monitor.py --urgent',
            'system_health': 'python scripts/database/system_monitor.py --health',
            'db_overview': 'python scripts/database/db_admin.py --overview',
            'backup_db': 'python scripts/database/db_admin.py --backup full',
            'integrity_check': 'python scripts/database/db_admin.py --maintenance integrity_check'
        }
    
    def show_common_queries(self):
        """显示常用查询命令"""
        print("\n🚀 常用数据库查询命令")
        print("=" * 60)
        
        queries = self.get_common_queries()
        for name, command in queries.items():
            print(f"\n📋 {name.replace('_', ' ').title()}:")
            print(f"   {command}")
    
    def execute_query(self, query_type: str, *args):
        """执行指定类型的查询"""
        queries = self.get_common_queries()
        
        if query_type in queries:
            command = queries[query_type]
            if args:
                command += ' ' + ' '.join(args)
            
            print(f"\n🔍 执行查询: {query_type}")
            print(f"命令: {command}")
            print("-" * 40)
            
            # 执行命令
            os.system(command)
        else:
            print(f"❌ 未知的查询类型: {query_type}")
            print("可用的查询类型:")
            for qt in queries.keys():
                print(f"  • {qt}")
    
    def validate_database(self):
        """执行数据库校验"""
        print("\n🔍 开始数据库校验...")
        print("=" * 60)
        
        validation_steps = [
            ('数据库概览', 'overview'),
            ('健康检查', 'health_check'),
            ('任务摘要', 'task_summary'),
            ('系统健康', 'system_health'),
            ('完整性检查', 'integrity_check')
        ]
        
        for step_name, query_type in validation_steps:
            print(f"\n📊 {step_name}...")
            self.execute_query(query_type)
            print("\n" + "-" * 40)
        
        print("\n✅ 数据库校验完成")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="数据库查询功能汇总 - 统一的数据库查询和校验工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python db_query_summary.py tools                     # 显示所有可用工具
  python db_query_summary.py commands                  # 显示常用查询命令
  python db_query_summary.py validate                  # 执行数据库校验
  python db_query_summary.py overview                  # 执行概览查询
  python db_query_summary.py pending                   # 查看待发布任务
  python db_query_summary.py health                    # 执行健康检查
  python db_query_summary.py --query overview          # 执行概览查询（旧格式）
        """
    )
    
    # 位置参数 - 查询类型
    parser.add_argument(
        'query_type',
        nargs='?',
        help='查询类型: tools, commands, validate, overview, health, tasks, pending, recent, urgent, backup, integrity'
    )
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='显示所有可用的数据库查询工具'
    )
    
    parser.add_argument(
        '--common', '-c',
        action='store_true',
        help='显示常用查询命令'
    )
    
    parser.add_argument(
        '--validate', '-v',
        action='store_true',
        help='执行完整的数据库校验'
    )
    
    parser.add_argument(
        '--query', '-q',
        help='执行指定类型的查询（旧格式）'
    )
    
    parser.add_argument(
        '--db-path',
        default='data/twitter_publisher.db',
        help='数据库文件路径'
    )
    
    args = parser.parse_args()
    
    try:
        summary = DatabaseQuerySummary(args.db_path)
        
        # 处理位置参数
        if args.query_type:
            if args.query_type == 'tools':
                summary.show_available_tools()
            elif args.query_type == 'commands':
                summary.show_common_queries()
            elif args.query_type == 'validate':
                summary.validate_database()
            elif args.query_type in ['overview', 'health', 'tasks', 'pending', 'recent', 'urgent', 'backup', 'integrity']:
                summary.execute_query(args.query_type)
            else:
                print(f"❌ 未知的查询类型: {args.query_type}")
                print("💡 可用类型: tools, commands, validate, overview, health, tasks, pending, recent, urgent, backup, integrity")
                sys.exit(1)
        # 处理旧格式的选项参数
        elif args.list:
            summary.show_available_tools()
        elif args.common:
            summary.show_common_queries()
        elif args.validate:
            summary.validate_database()
        elif args.query:
            summary.execute_query(args.query)
        else:
            # 默认显示工具列表
            summary.show_available_tools()
            print("\n💡 使用 --help 查看更多选项")
    
    except KeyboardInterrupt:
        print("\n👋 操作已取消")
    except Exception as e:
        print(f"❌ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()