#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务重置脚本

功能:
1. 删除所有现有的pending任务
2. 重新扫描项目并创建符合每日限制的任务
3. 确保每天只有5-8个任务
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.database import DatabaseManager
from app.database.repository import PublishingTaskRepository, ProjectRepository
from app.core.project_manager import ProjectManager
from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config
from app.utils.path_manager import get_path_manager
from app.database.models import PublishingTask, Project

logger = get_logger('task_resetter')

def clear_pending_tasks(session) -> int:
    """清除所有pending状态的任务"""
    try:
        task_repo = PublishingTaskRepository(session)
        
        # 查询所有pending任务
        pending_tasks = session.query(PublishingTask).filter(
            PublishingTask.status == 'pending'
        ).all()
        
        count = len(pending_tasks)
        logger.info(f"找到 {count} 个pending任务，准备删除")
        
        # 删除所有pending任务
        session.query(PublishingTask).filter(
            PublishingTask.status == 'pending'
        ).delete()
        
        logger.info(f"已删除 {count} 个pending任务")
        return count
        
    except Exception as e:
        logger.error(f"清除pending任务时出错: {e}")
        raise

def get_active_projects(session) -> List[Dict[str, Any]]:
    """获取所有活跃项目"""
    try:
        project_repo = ProjectRepository(session)
        projects = session.query(Project).filter(
            Project.status == 'active'
        ).all()
        
        project_list = []
        for project in projects:
            project_list.append({
                'id': project.id,
                'name': project.name,
                'priority': project.priority or 0
            })
        
        logger.info(f"找到 {len(project_list)} 个活跃项目")
        return project_list
        
    except Exception as e:
        logger.error(f"获取活跃项目时出错: {e}")
        raise

def reset_and_create_tasks() -> Dict[str, Any]:
    """重置并创建任务"""
    try:
        logger.info("开始重置任务...")
        
        # 获取配置
        config = get_enhanced_config()
        scheduling_config = config.get('scheduling', {})
        daily_max_tasks = scheduling_config.get('daily_max_tasks', 6)
        daily_min_tasks = scheduling_config.get('daily_min_tasks', 5)
        
        logger.info(f"每日任务限制: {daily_min_tasks}-{daily_max_tasks}")
        
        # 初始化数据库管理器
        db_manager = DatabaseManager()
        session = db_manager.get_session()
        
        result = {
            'success': True,
            'deleted_tasks': 0,
            'created_tasks': 0,
            'projects_processed': 0,
            'errors': []
        }
        
        try:
            # 1. 清除所有pending任务
            deleted_count = clear_pending_tasks(session)
            result['deleted_tasks'] = deleted_count
            
            # 2. 获取活跃项目
            active_projects = get_active_projects(session)
            
            if not active_projects:
                logger.warning("没有找到活跃项目")
                result['success'] = False
                result['errors'].append("没有活跃项目")
                return result
            
            # 3. 获取项目基础路径
            project_base_path = config.get('project_base_path', './projects')
            path_manager = get_path_manager()
            project_path = path_manager.get_project_path(project_base_path)
            
            if not project_path.exists():
                logger.error(f"项目基础路径不存在: {project_base_path}")
                result['success'] = False
                result['errors'].append(f"项目基础路径不存在: {project_base_path}")
                return result
            
            # 4. 初始化项目管理器
            project_manager = ProjectManager(session, str(project_path), user_id=1)
            
            # 5. 为每个项目创建有限数量的任务
            total_created = 0
            
            # 计算每个项目应该创建的任务数
            # 使用更保守的策略，每个项目最多创建2个任务
            max_tasks_per_project = min(2, daily_max_tasks // len(active_projects) + 1)
            logger.info(f"每个项目最多创建 {max_tasks_per_project} 个任务")
            
            for project in active_projects:
                try:
                    project_name = project['name']
                    logger.info(f"处理项目: {project_name}")
                    
                    # 使用更小的任务数限制
                    created_count = project_manager.scan_and_create_tasks(
                        project_name, 
                        "en", 
                        max_tasks_per_scan=max_tasks_per_project
                    )
                    
                    if isinstance(created_count, int):
                        total_created += created_count
                        result['projects_processed'] += 1
                        logger.info(f"项目 {project_name} 创建了 {created_count} 个任务")
                    else:
                        logger.warning(f"项目 {project_name} 扫描结果异常")
                        result['errors'].append(f"项目 {project_name} 扫描结果异常")
                        
                except Exception as e:
                    error_msg = f"处理项目 {project_name} 时出错: {e}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)
                    continue
            
            result['created_tasks'] = total_created
            
            # 6. 提交事务
            session.commit()
            logger.info("事务已提交")
            
            logger.info(f"任务重置完成，删除了 {deleted_count} 个任务，创建了 {total_created} 个新任务")
            
            return result
            
        except Exception as e:
            session.rollback()
            logger.error(f"重置任务时出错: {e}")
            result['success'] = False
            result['errors'].append(str(e))
            return result
            
        finally:
            session.close()
        
    except Exception as e:
        logger.error(f"重置任务失败: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def main():
    """主函数"""
    try:
        logger.info("开始任务重置流程...")
        
        result = reset_and_create_tasks()
        
        if result['success']:
            logger.info("=" * 60)
            logger.info("任务重置完成！")
            logger.info(f"删除的任务数: {result['deleted_tasks']}")
            logger.info(f"创建的任务数: {result['created_tasks']}")
            logger.info(f"处理的项目数: {result['projects_processed']}")
            if result['errors']:
                logger.warning(f"遇到 {len(result['errors'])} 个错误:")
                for error in result['errors']:
                    logger.warning(f"  - {error}")
            logger.info("=" * 60)
            return 0
        else:
            logger.error("任务重置失败")
            if 'errors' in result:
                for error in result['errors']:
                    logger.error(f"  - {error}")
            return 1
            
    except Exception as e:
        logger.error(f"执行任务重置时出错: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)