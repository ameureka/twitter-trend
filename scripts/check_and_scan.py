#!/usr/bin/env python3
"""
检查数据库中是否有任务，如果没有则执行项目扫描和任务创建
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.database import DatabaseManager
from app.database.repository import PublishingTaskRepository
from app.core.project_manager import ProjectManager
from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config
from app.utils.path_manager import get_path_manager

logger = get_logger('check_and_scan')

def check_tasks_exist() -> bool:
    """检查数据库中是否存在任务"""
    try:
        db_manager = DatabaseManager()
        session = db_manager.get_session()
        try:
            task_repo = PublishingTaskRepository(session)
            task_count = task_repo.count_all()
            logger.info(f"数据库中当前任务数量: {task_count}")
            return task_count > 0
        finally:
            session.close()
    except Exception as e:
        logger.error(f"检查任务数量时出错: {e}")
        return False

def scan_and_create_tasks():
    """扫描项目并创建任务"""
    try:
        logger.info("开始扫描项目并创建任务...")
        
        # 获取配置
        config = get_enhanced_config()
        
        # 初始化数据库管理器
        db_manager = DatabaseManager()
        session = db_manager.get_session()
        
        try:
            # 获取项目基础路径
            project_base_path = config.get('project_base_path', './projects')
            
            # 使用路径管理器解析项目路径
            path_manager = get_path_manager()
            project_path = path_manager.get_project_path(project_base_path)
            
            # 初始化项目管理器
            project_manager = ProjectManager(session, str(project_path), user_id=1)
            
            if not project_path.exists():
                logger.error(f"项目基础路径不存在: {project_base_path} (解析为: {project_path})")
                return
            
            # 获取所有项目目录（排除隐藏文件和非目录文件）
            project_directories = [
                item.name for item in project_path.iterdir() 
                if item.is_dir() and not item.name.startswith('.') and not item.name.startswith('__')
            ]
            
            if not project_directories:
                logger.warning(f"在 {project_base_path} 中未找到任何项目目录")
                return
                
            logger.info(f"发现 {len(project_directories)} 个项目目录: {project_directories}")
            
            total_created = 0
            
            for project_name in project_directories:
                try:
                    logger.info(f"扫描项目: {project_name}")
                    # 注意：scan_and_create_tasks 方法需要 language 参数
                    # 设置较大的max_tasks_per_scan以创建更多任务（而不是默认的6个）
                    created_count = project_manager.scan_and_create_tasks(project_name, "en", max_tasks_per_scan=500)
                    
                    if isinstance(created_count, int):
                        total_created += created_count
                        logger.info(f"项目 {project_name} 创建了 {created_count} 个任务")
                    else:
                        logger.warning(f"项目 {project_name} 扫描结果异常")
                        
                except Exception as e:
                    logger.error(f"扫描项目 {project_name} 时出错: {e}")
                    continue
            
            # 提交事务
            session.commit()
            logger.info("事务已提交")
            
            logger.info(f"扫描完成，总共创建了 {total_created} 个任务")
            return total_created
            
        finally:
            session.close()
        
    except Exception as e:
        logger.error(f"扫描和创建任务时出错: {e}")
        return 0

def main():
    """主函数"""
    try:
        logger.info("开始检查数据库任务状态...")
        
        # 检查是否存在任务
        if check_tasks_exist():
            logger.info("数据库中已存在任务，无需扫描")
            return 0
        
        logger.info("数据库中没有任务，开始扫描项目...")
        
        # 扫描并创建任务
        created_count = scan_and_create_tasks()
        
        if created_count > 0:
            logger.info(f"成功创建了 {created_count} 个任务")
            return 0
        else:
            logger.warning("没有创建任何任务，可能项目目录为空或已全部处理")
            return 0
            
    except Exception as e:
        logger.error(f"执行检查和扫描时出错: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)