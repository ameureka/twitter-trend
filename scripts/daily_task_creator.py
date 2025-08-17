#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日任务创建脚本

该脚本负责每日定时创建任务，实现全局任务数量控制。
建议通过cron job每天运行一次，例如每天早上8点。

使用方法:
    python3 scripts/daily_task_creator.py
    python3 scripts/daily_task_creator.py --dry-run  # 仅显示将要创建的任务，不实际创建
    python3 scripts/daily_task_creator.py --force    # 强制创建任务，即使今天已经创建过
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.global_task_creator import GlobalTaskCreator
from app.database.db_manager import EnhancedDatabaseManager
from app.utils.logger import setup_logger, get_logger
from app.utils.enhanced_config import get_enhanced_config

# 初始化日志系统
setup_logger()

# 临时设置为DEBUG级别
import logging
logging.getLogger().setLevel(logging.DEBUG)
for handler in logging.getLogger().handlers:
    handler.setLevel(logging.DEBUG)

logger = get_logger(__name__)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='每日任务创建脚本')
    parser.add_argument('--dry-run', action='store_true', 
                       help='仅显示将要创建的任务，不实际创建')
    parser.add_argument('--force', action='store_true',
                       help='强制创建任务，即使今天已经创建过')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='显示详细日志')
    
    args = parser.parse_args()
    
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # 初始化数据库管理器
        logger.info("初始化数据库连接...")
        db_manager = EnhancedDatabaseManager()
        
        # 初始化全局任务创建器
        logger.info("初始化全局任务创建器...")
        global_task_creator = GlobalTaskCreator()
        
        # 显示当前配置
        config = get_enhanced_config()
        global_config = config.get('global_task_creator', {})
        logger.info(f"全局每日任务限制: {global_config.get('daily_total_limit', 6)}")
        
        if args.dry_run:
            logger.info("=== 干运行模式 - 仅显示计划创建的任务 ===")
            # TODO: 实现干运行模式，显示将要创建的任务
            result = global_task_creator.preview_daily_tasks(force=args.force)
        else:
            logger.info("=== 开始创建每日任务 ===")
            # 创建每日任务
            result = global_task_creator.create_daily_tasks(force=args.force)
        
        # 显示结果
        if result.get('success'):
            # 处理不同方法返回的不同字段名
            if args.dry_run:
                created_count = result.get('created_count', 0)
                total_today = result.get('total_today', 0)
                logger.info(f"计划创建 {created_count} 个任务")
            else:
                created_count = result.get('total_tasks_created', 0)
                # 对于实际创建模式，需要重新计算今日总任务数
                from app.database.repository import PublishingTaskRepository as TaskRepo
                import pytz
                
                try:
                    temp_db_manager = EnhancedDatabaseManager()
                    timezone = pytz.timezone('Asia/Shanghai')
                    today_start = datetime.now(timezone).replace(hour=0, minute=0, second=0, microsecond=0)
                    tomorrow_start = today_start + timedelta(days=1)
                    
                    with temp_db_manager.get_session_context() as session:
                        task_repo = TaskRepo(session)
                        # 使用与GlobalTaskCreator相同的查询逻辑
                        from app.database.models import PublishingTask
                        total_today = task_repo.session.query(PublishingTask).filter(
                            PublishingTask.scheduled_at >= today_start,
                            PublishingTask.scheduled_at < tomorrow_start
                        ).count()
                except Exception as e:
                    logger.warning(f"无法获取今日总任务数: {e}")
                    total_today = 0
                
                logger.info(f"成功创建 {created_count} 个任务")
            
            logger.info(f"今日总任务数: {total_today}")
            
            # 显示各项目的任务分配
            project_allocations = result.get('project_allocations', {})
            if project_allocations:
                logger.info("各项目任务分配:")
                for project_name, allocation in project_allocations.items():
                    logger.info(f"  {project_name}: {allocation}")
        else:
            logger.warning(f"任务创建失败: {result.get('message', '未知错误')}")
            return 1
            
    except Exception as e:
        logger.error(f"脚本执行失败: {e}", exc_info=True)
        return 1
    
    logger.info("脚本执行完成")
    return 0

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)