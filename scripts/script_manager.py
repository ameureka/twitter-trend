#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本管理器
统一管理所有数据库和分析脚本的入口
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config

# 导入各个脚本模块
from scripts.database.reset_and_scan import DatabaseResetManager
from scripts.database.task_query import TaskQueryManager
from scripts.analysis.task_analyzer import TaskAnalyzer


class ScriptManagerError(Exception):
    """脚本管理器异常"""
    pass


class ScriptManager:
    """脚本管理器"""
    
    def __init__(self):
        self.logger = get_logger('script_manager')
        self.config = get_enhanced_config()
        
        # 初始化各个管理器
        self.reset_manager = DatabaseResetManager()
        self.query_manager = TaskQueryManager()
        self.analyzer = TaskAnalyzer()
    
    def reset_database(self, **kwargs) -> Dict[str, Any]:
        """重置数据库"""
        try:
            self.logger.info("开始重置数据库...")
            
            # 执行数据库重置
            result = self.reset_manager.reset_and_scan()
            
            self.logger.info("数据库重置完成")
            return {
                'success': True,
                'message': '数据库重置成功',
                'result': result
            }
            
        except Exception as e:
            self.logger.error(f"数据库重置失败: {e}")
            return {
                'success': False,
                'message': f'数据库重置失败: {e}',
                'error': str(e)
            }
    
    def query_tasks(self, **kwargs) -> Dict[str, Any]:
        """查询任务"""
        try:
            self.logger.info("开始查询任务...")
            
            # 获取综合摘要
            summary = self.query_manager.get_comprehensive_summary()
            
            self.logger.info("任务查询完成")
            return {
                'success': True,
                'message': '任务查询成功',
                'summary': summary
            }
            
        except Exception as e:
            self.logger.error(f"任务查询失败: {e}")
            return {
                'success': False,
                'message': f'任务查询失败: {e}',
                'error': str(e)
            }
    
    def analyze_tasks(self, detailed: bool = True, **kwargs) -> Dict[str, Any]:
        """分析任务"""
        try:
            self.logger.info("开始分析任务...")
            
            # 生成分析报告
            report = self.analyzer.generate_comprehensive_report(detailed=detailed)
            
            if 'error' in report:
                raise ScriptManagerError(report['error'])
            
            self.logger.info("任务分析完成")
            return {
                'success': True,
                'message': '任务分析成功',
                'report': report
            }
            
        except Exception as e:
            self.logger.error(f"任务分析失败: {e}")
            return {
                'success': False,
                'message': f'任务分析失败: {e}',
                'error': str(e)
            }
    
    def get_system_status(self, **kwargs) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            self.logger.info("获取系统状态...")
            
            # 获取基础统计信息
            query_result = self.query_tasks()
            if not query_result['success']:
                raise ScriptManagerError(f"获取任务信息失败: {query_result['message']}")
            
            summary = query_result['summary']
            
            # 构建系统状态
            status = {
                'database_status': 'connected',
                'total_tasks': summary.get('total_tasks', 0),
                'total_projects': len(summary.get('project_distribution', [])),
                'status_distribution': summary.get('status_distribution', []),
                'recent_activity': len(summary.get('recent_tasks', [])) > 0
            }
            
            self.logger.info("系统状态获取完成")
            return {
                'success': True,
                'message': '系统状态正常',
                'status': status
            }
            
        except Exception as e:
            self.logger.error(f"获取系统状态失败: {e}")
            return {
                'success': False,
                'message': f'获取系统状态失败: {e}',
                'error': str(e)
            }
    
    def execute_command(self, command: str, **kwargs) -> Dict[str, Any]:
        """执行命令"""
        commands = {
            'reset': self.reset_database,
            'query': self.query_tasks,
            'analyze': self.analyze_tasks,
            'status': self.get_system_status
        }
        
        if command not in commands:
            return {
                'success': False,
                'message': f'未知命令: {command}',
                'available_commands': list(commands.keys())
            }
        
        try:
            return commands[command](**kwargs)
        except Exception as e:
            self.logger.error(f"执行命令 {command} 失败: {e}")
            return {
                'success': False,
                'message': f'执行命令失败: {e}',
                'error': str(e)
            }
    
    def print_result(self, result: Dict[str, Any], format_type: str = 'text'):
        """打印结果"""
        if format_type == 'json':
            import json
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return
        
        # 文本格式输出
        if result['success']:
            print(f"✅ {result['message']}")
            
            # 根据结果类型打印详细信息
            if 'summary' in result:
                self.query_manager.print_summary(result['summary'])
            elif 'report' in result:
                self.analyzer.print_report(result['report'], format_type)
            elif 'status' in result:
                self._print_system_status(result['status'])
            elif 'result' in result:
                self._print_reset_result(result['result'])
        else:
            print(f"❌ {result['message']}")
            if 'error' in result:
                print(f"错误详情: {result['error']}")
    
    def _print_system_status(self, status: Dict[str, Any]):
        """打印系统状态"""
        print("\n=== 系统状态 ===")
        print(f"数据库状态: {status.get('database_status', 'unknown')}")
        print(f"总任务数: {status.get('total_tasks', 0)}")
        print(f"总项目数: {status.get('total_projects', 0)}")
        print(f"最近活动: {'有' if status.get('recent_activity') else '无'}")
        
        status_dist = status.get('status_distribution', [])
        if status_dist:
            print("\n任务状态分布:")
            for item in status_dist:
                print(f"  {item['status']}: {item['count']} 个任务")
    
    def _print_reset_result(self, result: Dict[str, Any]):
        """打印重置结果"""
        print("\n=== 重置结果 ===")
        if 'projects_scanned' in result:
            print(f"扫描项目数: {result['projects_scanned']}")
        if 'total_tasks_created' in result:
            print(f"创建任务数: {result['total_tasks_created']}")
        if 'project_details' in result:
            print("\n项目详情:")
            for detail in result['project_details']:
                print(f"  {detail['name']}: {detail['tasks_created']} 个任务")


def create_parser() -> argparse.ArgumentParser:
    """创建命令行解析器"""
    parser = argparse.ArgumentParser(
        description='脚本管理器 - 统一管理数据库和分析脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s reset                    # 重置数据库并扫描项目
  %(prog)s query                    # 查询任务摘要
  %(prog)s analyze                  # 分析任务分布
  %(prog)s analyze --detailed       # 详细分析任务分布
  %(prog)s status                   # 获取系统状态
  %(prog)s query --format json     # JSON格式输出
"""
    )
    
    # 主命令
    parser.add_argument(
        'command',
        choices=['reset', 'query', 'analyze', 'status'],
        help='要执行的命令'
    )
    
    # 通用选项
    parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='输出格式 (默认: text)'
    )
    
    parser.add_argument(
        '--output',
        help='输出文件路径'
    )
    
    # 分析命令特定选项
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='生成详细分析报告 (仅用于 analyze 命令)'
    )
    
    # 调试选项
    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式'
    )
    
    return parser


def main():
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        # 创建脚本管理器
        manager = ScriptManager()
        
        # 设置调试模式
        if args.debug:
            import logging
            logging.getLogger().setLevel(logging.DEBUG)
        
        # 准备命令参数
        command_kwargs = {}
        if args.command == 'analyze':
            command_kwargs['detailed'] = args.detailed
        
        # 执行命令
        result = manager.execute_command(args.command, **command_kwargs)
        
        # 输出结果
        if args.output:
            # 保存到文件
            with open(args.output, 'w', encoding='utf-8') as f:
                if args.format == 'json':
                    import json
                    json.dump(result, f, indent=2, ensure_ascii=False)
                else:
                    # 重定向标准输出到文件
                    import contextlib
                    with contextlib.redirect_stdout(f):
                        manager.print_result(result, args.format)
            print(f"结果已保存到: {args.output}")
        else:
            # 直接输出
            manager.print_result(result, args.format)
        
        # 设置退出码
        sys.exit(0 if result['success'] else 1)
        
    except KeyboardInterrupt:
        print("\n操作被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"程序执行失败: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()