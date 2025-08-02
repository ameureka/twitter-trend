#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重置数据库并动态扫描项目文件夹创建任务

功能:
1. 清空数据库内容（保留表结构）
2. 动态扫描project文件夹下的所有项目
3. 为每个项目创建发布任务
4. 统计创建的任务数量
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database.database import DatabaseManager
from app.core.project_manager import ProjectManager
from app.utils.config import get_config
from app.utils.logger import get_logger, setup_logger
from app.database.models import User, Project, ContentSource, PublishingTask, PublishingLog, AnalyticsHourly


def get_project_folders(project_base_path: str) -> List[str]:
    """
    动态获取项目文件夹列表
    
    Args:
        project_base_path: 项目基础路径
        
    Returns:
        项目文件夹名称列表
    """
    project_folders = []
    base_path = Path(project_base_path)
    
    if not base_path.exists():
        raise FileNotFoundError(f"项目基础路径不存在: {project_base_path}")
    
    # 遍历所有子文件夹
    for item in base_path.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            # 检查是否包含必要的子文件夹结构
            video_dir = item / "output_video_music"
            json_dir = item / "uploader_json"
            
            if video_dir.exists() and json_dir.exists():
                project_folders.append(item.name)
                
    return sorted(project_folders)


def clear_database_content(db_manager: DatabaseManager) -> Dict[str, int]:
    """
    清空数据库内容，保留表结构
    
    Args:
        db_manager: 数据库管理器
        
    Returns:
        清理统计信息
    """
    logger = get_logger(__name__)
    stats = {
        'publishing_logs': 0,
        'analytics_hourly': 0,
        'publishing_tasks': 0,
        'content_sources': 0,
        'projects': 0,
        'users': 0
    }
    
    try:
        with db_manager.get_session() as session:
            # 按照外键依赖顺序删除数据
            
            # 1. 删除发布日志
            logs_count = session.query(PublishingLog).count()
            session.query(PublishingLog).delete()
            stats['publishing_logs'] = logs_count
            logger.info(f"清理发布日志: {logs_count} 条")
            
            # 2. 删除分析数据
            analytics_count = session.query(AnalyticsHourly).count()
            session.query(AnalyticsHourly).delete()
            stats['analytics_hourly'] = analytics_count
            logger.info(f"清理分析数据: {analytics_count} 条")
            
            # 3. 删除发布任务
            tasks_count = session.query(PublishingTask).count()
            session.query(PublishingTask).delete()
            stats['publishing_tasks'] = tasks_count
            logger.info(f"清理发布任务: {tasks_count} 条")
            
            # 4. 删除内容源
            sources_count = session.query(ContentSource).count()
            session.query(ContentSource).delete()
            stats['content_sources'] = sources_count
            logger.info(f"清理内容源: {sources_count} 条")
            
            # 5. 删除项目
            projects_count = session.query(Project).count()
            session.query(Project).delete()
            stats['projects'] = projects_count
            logger.info(f"清理项目: {projects_count} 条")
            
            # 6. 删除用户（除了admin用户）
            users_count = session.query(User).filter(User.username != 'admin').count()
            session.query(User).filter(User.username != 'admin').delete()
            stats['users'] = users_count
            logger.info(f"清理用户: {users_count} 条（保留admin用户）")
            
            session.commit()
            logger.info("数据库内容清理完成")
            
    except Exception as e:
        logger.error(f"清理数据库内容失败: {e}")
        session.rollback()
        raise
        
    return stats


def scan_all_projects(project_manager: ProjectManager, project_folders: List[str], language: str = "en") -> Dict[str, Any]:
    """
    扫描所有项目文件夹并创建任务
    
    Args:
        project_manager: 项目管理器
        project_folders: 项目文件夹列表
        language: 语言代码
        
    Returns:
        扫描结果统计
    """
    logger = get_logger(__name__)
    results = {
        'total_projects': len(project_folders),
        'successful_projects': 0,
        'failed_projects': 0,
        'total_tasks_created': 0,
        'project_details': {}
    }
    
    for project_name in project_folders:
        try:
            logger.info(f"正在扫描项目: {project_name}")
            
            # 扫描项目并创建任务
            tasks_created = project_manager.scan_and_create_tasks(project_name, language)
            
            results['successful_projects'] += 1
            results['total_tasks_created'] += tasks_created
            results['project_details'][project_name] = {
                'status': 'success',
                'tasks_created': tasks_created
            }
            
            logger.info(f"项目 '{project_name}' 扫描完成，创建了 {tasks_created} 个任务")
            
        except Exception as e:
            logger.error(f"扫描项目 '{project_name}' 失败: {e}")
            results['failed_projects'] += 1
            results['project_details'][project_name] = {
                'status': 'failed',
                'error': str(e)
            }
    
    return results


def ensure_admin_user(db_manager: DatabaseManager) -> None:
    """
    确保admin用户存在
    
    Args:
        db_manager: 数据库管理器
    """
    logger = get_logger(__name__)
    
    try:
        with db_manager.get_session() as session:
            from app.database.repository import UserRepository
            user_repo = UserRepository(session)
            
            admin_user = user_repo.get_by_username('admin')
            if not admin_user:
                user_repo.create({
                    'username': 'admin',
                    'email': 'admin@example.com',
                    'role': 'admin'
                })
                logger.info("创建默认admin用户")
            else:
                logger.info("admin用户已存在")
                
    except Exception as e:
        logger.error(f"确保admin用户失败: {e}")
        raise


def main():
    """
    主函数
    """
    # 设置日志
    setup_logger(log_level='INFO')
    logger = get_logger(__name__)
    
    logger.info("=" * 60)
    logger.info("重置数据库并扫描项目文件夹")
    logger.info("=" * 60)
    
    try:
        # 1. 初始化配置和数据库
        config = get_config()
        
        # 使用相对路径避免硬编码
        project_root = Path(__file__).parent.parent.parent
        db_path = project_root / 'data' / 'twitter_publisher.db'
        db_url = f"sqlite:///{db_path}"
        
        db_manager = DatabaseManager(db_url)
        
        # 2. 确保数据库表存在
        db_manager.create_tables()
        logger.info("数据库表检查完成")
        
        # 3. 清空数据库内容
        logger.info("开始清空数据库内容...")
        clear_stats = clear_database_content(db_manager)
        
        logger.info("数据库清理统计:")
        for table, count in clear_stats.items():
            logger.info(f"  {table}: {count} 条记录")
        
        # 4. 确保admin用户存在
        ensure_admin_user(db_manager)
        
        # 5. 获取项目基础路径
        project_base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'project')
        logger.info(f"项目基础路径: {project_base_path}")
        
        # 6. 动态获取项目文件夹
        project_folders = get_project_folders(project_base_path)
        logger.info(f"发现 {len(project_folders)} 个项目文件夹:")
        for folder in project_folders:
            logger.info(f"  - {folder}")
        
        if not project_folders:
            logger.warning("未发现任何有效的项目文件夹")
            return
        
        # 7. 扫描所有项目并创建任务
        with db_manager.get_session() as session:
            project_manager = ProjectManager(session, project_base_path, user_id=1)
            
            logger.info("开始扫描项目并创建任务...")
            scan_results = scan_all_projects(project_manager, project_folders)
            
            # 提交事务
            session.commit()
            logger.info("任务创建事务已提交")
            
            # 8. 输出扫描结果
            logger.info("=" * 60)
            logger.info("扫描结果统计:")
            logger.info(f"  总项目数: {scan_results['total_projects']}")
            logger.info(f"  成功项目数: {scan_results['successful_projects']}")
            logger.info(f"  失败项目数: {scan_results['failed_projects']}")
            logger.info(f"  总任务创建数: {scan_results['total_tasks_created']}")
            
            logger.info("\n项目详情:")
            for project_name, details in scan_results['project_details'].items():
                if details['status'] == 'success':
                    logger.info(f"  ✓ {project_name}: {details['tasks_created']} 个任务")
                else:
                    logger.error(f"  ✗ {project_name}: {details['error']}")
            
            logger.info("=" * 60)
            logger.info(f"数据库重置和项目扫描完成！总共创建了 {scan_results['total_tasks_created']} 个任务")
            
    except Exception as e:
        logger.error(f"执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()