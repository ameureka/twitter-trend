#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版主启动脚本
整合所有增强功能的统一入口
"""

import asyncio
import signal
import sys
import os
import time
from pathlib import Path
from typing import Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.db_manager import EnhancedDatabaseManager
from app.core.enhanced_scheduler import EnhancedTaskScheduler
from app.utils.enhanced_config import get_enhanced_config
from app.utils.error_handler import ErrorHandler
from app.utils.performance_monitor import PerformanceMonitor
from app.core.publisher import TwitterPublisher
from app.core.content_generator import ContentGenerator
from app.utils.logger import setup_logger, get_logger

# 导入脚本管理器
try:
    from scripts.script_manager import ScriptManager
except ImportError:
    ScriptManager = None

# 全局变量
scheduler: Optional[EnhancedTaskScheduler] = None
running = False
logger = None


def signal_handler(signum, frame):
    """信号处理器"""
    global running, scheduler
    logger.info(f"接收到信号 {signum}，开始优雅关闭...")
    running = False
    
    if scheduler:
        scheduler.stop()
    
    # 停止性能监控
    # monitor.stop() # 性能监控停止逻辑
    
    logger.info("系统已优雅关闭")
    sys.exit(0)


def setup_signal_handlers():
    """设置信号处理器"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def initialize_system():
    """初始化系统"""
    global logger
    
    # 加载环境变量
    from dotenv import load_dotenv
    load_dotenv()
    
    # 获取增强配置
    config = get_enhanced_config()
    
    # 设置日志
    log_file = config.get('logging', {}).get('file', 'logs/main.log')
    log_level = config.get('logging', {}).get('level', 'INFO')
    setup_logger(log_path=log_file, log_level=log_level)
    logger = get_logger('main')
    
    logger.info("=== 启动增强版Twitter自动发布系统 ===")
    
    # 初始化错误处理器
    error_handler = ErrorHandler()
    logger.info("错误处理器已初始化")
    
    # 启动性能监控
    performance_monitor = PerformanceMonitor()
    logger.info("性能监控已启动")
    
    # 初始化数据库
    db_manager = EnhancedDatabaseManager()
    init_result = db_manager.initialize_database()
    if not init_result['success']:
        logger.error(f"数据库初始化失败: {init_result['message']}")
        sys.exit(1)
    logger.info("增强数据库管理器已初始化")
    
    # 检查系统健康状态
    health = db_manager.check_health()
    if not health['healthy']:
        logger.warning(f"系统健康检查警告: {health.get('issues', [])}")
    
    return config, db_manager


def create_scheduler(config, db_manager):
    """创建增强调度器"""
    import os
    
    # 从环境变量读取Twitter配置
    twitter_config = {
        'api_key': os.getenv('TWITTER_API_KEY'),
        'api_secret': os.getenv('TWITTER_API_SECRET'),
        'access_token': os.getenv('TWITTER_ACCESS_TOKEN'),
        'access_token_secret': os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
    }
    
    missing_keys = [k for k, v in twitter_config.items() if not v]
    if missing_keys:
        logger.error(f"缺少Twitter API配置: {', '.join(missing_keys)}")
        logger.error("请在.env文件中设置以下环境变量:")
        logger.error("TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET, TWITTER_BEARER_TOKEN")
        sys.exit(1)
    
    # 创建发布器
    publisher = TwitterPublisher(**twitter_config)
    logger.info("Twitter发布器已创建")
    
    # 创建内容生成器
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    use_ai = config.get('publishing', {}).get('use_ai_enhancement', True) and bool(gemini_api_key)
    content_generator = ContentGenerator(
        use_ai=use_ai,
        gemini_api_key=gemini_api_key
    )
    logger.info(f"内容生成器已创建 (AI增强: {use_ai})")
    
    # 创建调度器
    scheduler = EnhancedTaskScheduler(
        db_manager=db_manager,
        content_generator=content_generator,
        publisher=publisher
    )
    
    logger.info("增强任务调度器已创建")
    return scheduler


def run_continuous_mode(scheduler, config):
    """运行连续模式"""
    global running
    running = True
    
    scheduling_config = config.get('scheduling', {})
    interval_minutes = scheduling_config.get('interval_minutes', 60)
    batch_size = scheduling_config.get('batch_size', 10)
    
    logger.info(f"开始连续运行模式 (间隔: {interval_minutes}分钟, 批量大小: {batch_size})")
    
    while running:
        try:
            stats = scheduler.run_batch(limit=batch_size)
            logger.info(f"批次执行完成 - 已处理: {stats['processed']}, 成功: {stats['successful']}, 失败: {stats['failed']}")
            
            logger.info(f"等待 {interval_minutes} 分钟后进行下一轮...")
            # 分段睡眠以响应信号
            sleep_interval = 5
            for _ in range(int(interval_minutes * 60 / sleep_interval)):
                if not running:
                    break
                time.sleep(sleep_interval)

        except KeyboardInterrupt:
            logger.info("接收到中断信号，停止运行")
            break
        except Exception as e:
            logger.error(f"运行过程中发生错误: {e}", exc_info=True)
            if running:
                time.sleep(300)  # 错误后等待5分钟


def run_single_batch(scheduler, config, project=None, language=None, limit=None):
    """运行单次批处理"""
    batch_size = limit or config.get('scheduling', {}).get('batch_size', 10)
    
    logger.info(f"开始单次批处理 (项目: {project or '全部'}, 语言: {language or '全部'}, 限制: {batch_size})")
    
    try:
        stats = scheduler.run_batch(
            limit=batch_size, 
            project_filter=project, 
            language_filter=language
        )
        
        logger.info(f"批处理完成:")
        logger.info(f"  已处理: {stats['processed']}")
        logger.info(f"  成功: {stats['successful']}")
        logger.info(f"  失败: {stats['failed']}")
        
        return stats
        
    except Exception as e:
        logger.error(f"批处理执行失败: {e}", exc_info=True)
        raise


def show_system_status(config, db_manager):
    """显示系统状态"""
    logger.info("=== 系统状态报告 ===")
    
    # 数据库状态
    health = db_manager.check_health()
    logger.info(f"数据库状态: {'健康' if health['healthy'] else '异常'}")
    if health.get('issues'):
        for issue in health['issues']:
            logger.warning(f"  问题: {issue}")
    
    # 性能状态
    try:
        monitor = PerformanceMonitor()
        metrics = monitor.get_current_metrics()
        if metrics:
            logger.info(f"系统性能:")
            logger.info(f"  CPU使用率: {metrics.cpu_percent:.1f}%")
            logger.info(f"  内存使用率: {metrics.memory_percent:.1f}%")
            logger.info(f"  磁盘使用率: {metrics.disk_usage_percent:.1f}%")
        else:
            logger.info("系统性能: 监控未启动")
    except Exception as e:
        logger.warning(f"无法获取性能指标: {e}")
    
    # 配置状态
    logger.info(f"配置状态:")
    logger.info(f"  发布间隔: {config.get('scheduling', {}).get('interval_hours', 24)}小时")
    logger.info(f"  批量大小: {config.get('scheduling', {}).get('batch_size', 5)}")
    logger.info(f"  AI增强: {'启用' if config.get('publishing', {}).get('use_ai_enhancement', True) else '禁用'}")
    logger.info(f"  性能监控: {'启用' if config.get('performance', {}).get('monitoring_enabled', True) else '禁用'}")


def run_management_mode(command: str, **kwargs):
    """运行管理模式"""
    if not ScriptManager:
        print("错误: 脚本管理器不可用，请检查scripts模块")
        return False
    
    try:
        manager = ScriptManager()
        result = manager.execute_command(command, **kwargs)
        
        # 打印结果
        manager.print_result(result, kwargs.get('format', 'text'))
        
        return result['success']
        
    except Exception as e:
        print(f"错误: 管理命令执行失败: {e}")
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='增强版Twitter自动发布系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式:
  continuous    连续运行模式（默认）
  single        单次批处理模式
  status        显示系统状态
  management    管理模式（数据库和分析操作）

管理命令:
  --reset-db    重置数据库并扫描项目
  --query       查询任务摘要
  --analyze     分析任务分布
  --stats       获取系统统计信息

示例:
  %(prog)s --mode continuous              # 连续运行
  %(prog)s --mode single --limit 5        # 单次处理5个任务
  %(prog)s --mode management --reset-db   # 重置数据库
  %(prog)s --mode management --analyze --detailed  # 详细分析
"""
    )
    
    # 运行模式
    parser.add_argument('--mode', choices=['continuous', 'single', 'status', 'management'], 
                       default='continuous', help='运行模式')
    
    # 发布相关参数
    parser.add_argument('--project', help='指定项目名称')
    parser.add_argument('--language', choices=['en', 'cn', 'ja'], help='指定语言')
    parser.add_argument('--limit', type=int, help='限制处理的任务数量')
    parser.add_argument('--config-file', help='指定配置文件路径')
    
    # 管理命令参数
    parser.add_argument('--reset-db', action='store_true', help='重置数据库并扫描项目')
    parser.add_argument('--query', action='store_true', help='查询任务摘要')
    parser.add_argument('--analyze', action='store_true', help='分析任务分布')
    parser.add_argument('--stats', action='store_true', help='获取系统统计信息')
    parser.add_argument('--detailed', action='store_true', help='生成详细报告（用于analyze）')
    
    # 输出格式
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='输出格式')
    parser.add_argument('--output', help='输出文件路径')
    
    args = parser.parse_args()
    
    # 设置信号处理器
    setup_signal_handlers()
    
    try:
        # 管理模式处理
        if args.mode == 'management':
            # 确定要执行的管理命令
            management_commands = []
            if args.reset_db:
                management_commands.append('reset')
            if args.query:
                management_commands.append('query')
            if args.analyze:
                management_commands.append('analyze')
            if args.stats:
                management_commands.append('status')
            
            if not management_commands:
                print("错误: 管理模式需要指定至少一个管理命令")
                print("可用命令: --reset-db, --query, --analyze, --stats")
                sys.exit(1)
            
            # 执行管理命令
            success = True
            for command in management_commands:
                print(f"\n=== 执行管理命令: {command} ===")
                command_kwargs = {
                    'format': args.format,
                    'output': args.output if len(management_commands) == 1 else None
                }
                if command == 'analyze':
                    command_kwargs['detailed'] = args.detailed
                
                if not run_management_mode(command, **command_kwargs):
                    success = False
                    break
            
            sys.exit(0 if success else 1)
        
        # 初始化系统（非管理模式）
        config, db_manager = initialize_system()
        
        if args.mode == 'status':
            # 仅显示状态
            show_system_status(config, db_manager)
            return
        
        # 创建调度器
        global scheduler
        scheduler = create_scheduler(config, db_manager)
        
        if args.mode == 'continuous':
            # 连续运行模式
            run_continuous_mode(scheduler, config)
        elif args.mode == 'single':
            # 单次批处理模式
            stats = run_single_batch(scheduler, config, args.project, args.language, args.limit)
            
            # 显示结果
            print(f"\n批处理结果:")
            print(f"  已处理: {stats['processed']}")
            print(f"  成功: {stats['successful']}")
            print(f"  失败: {stats['failed']}")
        
    except KeyboardInterrupt:
        if logger:
            logger.info("用户中断程序")
        else:
            print("用户中断程序")
    except Exception as e:
        if logger:
            logger.error(f"程序执行失败: {e}")
        else:
            print(f"程序执行失败: {e}")
        sys.exit(1)
    finally:
        # 清理资源
        if scheduler:
            scheduler.stop()
        
        # 性能监控清理逻辑
        pass
        
        if logger:
            logger.info("程序已退出")
        else:
            print("程序已退出")


# CLI函数供测试使用
def cli():
    """CLI入口点"""
    return main


if __name__ == '__main__':
    main()