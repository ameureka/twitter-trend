#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务查询工具
提供数据库任务查询和统计功能
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.models import Project, PublishingTask, ContentSource, User
from app.database.db_manager import EnhancedDatabaseManager
from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config


class TaskQueryError(Exception):
    """任务查询异常"""
    pass


class TaskQueryManager:
    """任务查询管理器"""
    
    def __init__(self, db_manager: EnhancedDatabaseManager = None):
        self.db_manager = db_manager or EnhancedDatabaseManager()
        self.logger = get_logger('task_query')
        self.config = get_enhanced_config()
    
    def get_task_count(self, session: Session) -> int:
        """获取任务总数"""
        try:
            count = session.query(PublishingTask).count()
            self.logger.info(f"数据库中共有 {count} 个任务")
            return count
        except Exception as e:
            self.logger.error(f"获取任务总数失败: {e}")
            raise TaskQueryError(f"获取任务总数失败: {e}")
    
    def get_tasks_by_status(self, session: Session, status: str = None) -> List[Dict[str, Any]]:
        """按状态查询任务"""
        try:
            query = session.query(
                PublishingTask.status,
                func.count(PublishingTask.id).label('count')
            )
            
            if status:
                query = query.filter(PublishingTask.status == status)
            
            results = query.group_by(PublishingTask.status).all()
            
            status_distribution = []
            for status_name, count in results:
                status_distribution.append({
                    'status': status_name,
                    'count': count
                })
            
            self.logger.info(f"任务状态分布: {status_distribution}")
            return status_distribution
            
        except Exception as e:
            self.logger.error(f"按状态查询任务失败: {e}")
            raise TaskQueryError(f"按状态查询任务失败: {e}")
    
    def get_tasks_by_project(self, session: Session, project_name: str = None) -> List[Dict[str, Any]]:
        """按项目查询任务"""
        try:
            query = session.query(
                Project.name,
                func.count(PublishingTask.id).label('count')
            ).join(PublishingTask)
            
            if project_name:
                query = query.filter(Project.name == project_name)
            
            results = query.group_by(Project.name).all()
            
            project_distribution = []
            for proj_name, count in results:
                project_distribution.append({
                    'project': proj_name,
                    'task_count': count
                })
            
            self.logger.info(f"项目任务分布: {project_distribution}")
            return project_distribution
            
        except Exception as e:
            self.logger.error(f"按项目查询任务失败: {e}")
            raise TaskQueryError(f"按项目查询任务失败: {e}")
    
    def get_tasks_by_priority(self, session: Session, priority: int = None) -> List[Dict[str, Any]]:
        """按优先级查询任务"""
        try:
            query = session.query(
                PublishingTask.priority,
                func.count(PublishingTask.id).label('count')
            )
            
            if priority is not None:
                query = query.filter(PublishingTask.priority == priority)
            
            results = query.group_by(PublishingTask.priority).all()
            
            priority_distribution = []
            for prio, count in results:
                priority_distribution.append({
                    'priority': prio,
                    'count': count
                })
            
            self.logger.info(f"任务优先级分布: {priority_distribution}")
            return priority_distribution
            
        except Exception as e:
            self.logger.error(f"按优先级查询任务失败: {e}")
            raise TaskQueryError(f"按优先级查询任务失败: {e}")
    
    def get_recent_tasks(self, session: Session, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的任务"""
        try:
            tasks = session.query(PublishingTask).join(Project).order_by(
                desc(PublishingTask.created_at)
            ).limit(limit).all()
            
            recent_tasks = []
            for task in tasks:
                recent_tasks.append({
                    'id': task.id,
                    'project_name': task.project.name if task.project else 'Unknown',
                    'project_description': task.project.description if task.project else 'Unknown',
                    'status': task.status,
                    'priority': task.priority,
                    'media_path': task.media_path,
                    'created_at': task.created_at.isoformat() if task.created_at else None,
                    'updated_at': task.updated_at.isoformat() if task.updated_at else None
                })
            
            self.logger.info(f"获取到 {len(recent_tasks)} 个最近任务")
            return recent_tasks
            
        except Exception as e:
            self.logger.error(f"获取最近任务失败: {e}")
            raise TaskQueryError(f"获取最近任务失败: {e}")
    
    def get_task_details(self, session: Session, task_id: int) -> Optional[Dict[str, Any]]:
        """获取任务详细信息"""
        try:
            task = session.query(PublishingTask).filter(
                PublishingTask.id == task_id
            ).first()
            
            if not task:
                self.logger.warning(f"未找到ID为 {task_id} 的任务")
                return None
            
            task_details = {
                'id': task.id,
                'project_id': task.project_id,
                'project_name': task.project.name if task.project else 'Unknown',
                'project_description': task.project.description if task.project else 'Unknown',
                'source_id': task.source_id,
                'media_path': task.media_path,
                'content_data': task.content_data,
                'status': task.status,
                'priority': task.priority,
                'max_retries': task.max_retries,
                'retry_count': task.retry_count,
                'last_error': task.last_error,
                'scheduled_time': task.scheduled_time.isoformat() if task.scheduled_time else None,
                'published_time': task.published_time.isoformat() if task.published_time else None,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'updated_at': task.updated_at.isoformat() if task.updated_at else None
            }
            
            self.logger.info(f"获取任务 {task_id} 详细信息成功")
            return task_details
            
        except Exception as e:
            self.logger.error(f"获取任务详细信息失败: {e}")
            raise TaskQueryError(f"获取任务详细信息失败: {e}")
    
    def search_tasks(self, session: Session, **filters) -> List[Dict[str, Any]]:
        """搜索任务"""
        try:
            query = session.query(PublishingTask).join(Project)
            
            # 应用过滤条件
            if 'status' in filters:
                query = query.filter(PublishingTask.status == filters['status'])
            
            if 'priority' in filters:
                query = query.filter(PublishingTask.priority == filters['priority'])
            
            if 'project_name' in filters:
                query = query.filter(Project.name.like(f"%{filters['project_name']}%"))
            
            if 'media_path' in filters:
                query = query.filter(PublishingTask.media_path.like(f"%{filters['media_path']}%"))
            
            # 限制结果数量
            limit = filters.get('limit', 100)
            tasks = query.limit(limit).all()
            
            results = []
            for task in tasks:
                results.append({
                    'id': task.id,
                    'project_name': task.project.name if task.project else 'Unknown',
                    'status': task.status,
                    'priority': task.priority,
                    'media_path': task.media_path,
                    'created_at': task.created_at.isoformat() if task.created_at else None
                })
            
            self.logger.info(f"搜索到 {len(results)} 个匹配的任务")
            return results
            
        except Exception as e:
            self.logger.error(f"搜索任务失败: {e}")
            raise TaskQueryError(f"搜索任务失败: {e}")
    
    def get_comprehensive_summary(self) -> Dict[str, Any]:
        """获取综合摘要"""
        try:
            with self.db_manager.get_session() as session:
                summary = {
                    'total_tasks': self.get_task_count(session),
                    'status_distribution': self.get_tasks_by_status(session),
                    'project_distribution': self.get_tasks_by_project(session),
                    'priority_distribution': self.get_tasks_by_priority(session),
                    'recent_tasks': self.get_recent_tasks(session, limit=5)
                }
                
                self.logger.info("生成综合摘要成功")
                return summary
                
        except Exception as e:
            self.logger.error(f"获取综合摘要失败: {e}")
            raise TaskQueryError(f"获取综合摘要失败: {e}")
    
    def print_summary(self, summary: Dict[str, Any]):
        """打印摘要信息"""
        print("=" * 60)
        print("任务查询摘要")
        print("=" * 60)
        
        # 总任务数
        print(f"\n总任务数: {summary.get('total_tasks', 0)}")
        
        # 状态分布
        status_dist = summary.get('status_distribution', [])
        if status_dist:
            print("\n=== 任务状态分布 ===")
            for item in status_dist:
                print(f"{item['status']}: {item['count']} 个任务")
        
        # 项目分布
        project_dist = summary.get('project_distribution', [])
        if project_dist:
            print("\n=== 项目任务分布 ===")
            for item in project_dist:
                print(f"{item['project']}: {item['task_count']} 个任务")
        
        # 优先级分布
        priority_dist = summary.get('priority_distribution', [])
        if priority_dist:
            print("\n=== 任务优先级分布 ===")
            for item in priority_dist:
                print(f"优先级 {item['priority']}: {item['count']} 个任务")
        
        # 最近任务
        recent_tasks = summary.get('recent_tasks', [])
        if recent_tasks:
            print("\n=== 最近创建的任务 ===")
            for task in recent_tasks:
                print(f"ID: {task['id']}, 项目: {task['project_name']}, "
                      f"状态: {task['status']}, 优先级: {task['priority']}, "
                      f"描述: {task['project_description']}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='任务查询工具')
    parser.add_argument('--status', help='按状态过滤任务')
    parser.add_argument('--project', help='按项目名称过滤任务')
    parser.add_argument('--priority', type=int, help='按优先级过滤任务')
    parser.add_argument('--task-id', type=int, help='查询特定任务的详细信息')
    parser.add_argument('--recent', type=int, default=10, help='显示最近的N个任务')
    parser.add_argument('--summary', action='store_true', help='显示综合摘要')
    
    args = parser.parse_args()
    
    try:
        # 创建查询管理器
        query_manager = TaskQueryManager()
        
        if args.summary:
            # 显示综合摘要
            summary = query_manager.get_comprehensive_summary()
            query_manager.print_summary(summary)
        
        elif args.task_id:
            # 查询特定任务
            with query_manager.db_manager.get_session() as session:
                task_details = query_manager.get_task_details(session, args.task_id)
                if task_details:
                    print(f"任务 {args.task_id} 详细信息:")
                    for key, value in task_details.items():
                        print(f"{key}: {value}")
                else:
                    print(f"未找到ID为 {args.task_id} 的任务")
        
        else:
            # 搜索任务
            filters = {}
            if args.status:
                filters['status'] = args.status
            if args.project:
                filters['project_name'] = args.project
            if args.priority is not None:
                filters['priority'] = args.priority
            filters['limit'] = args.recent
            
            with query_manager.db_manager.get_session() as session:
                if filters:
                    tasks = query_manager.search_tasks(session, **filters)
                else:
                    tasks = query_manager.get_recent_tasks(session, args.recent)
                
                if tasks:
                    print(f"找到 {len(tasks)} 个任务:")
                    for task in tasks:
                        print(f"ID: {task['id']}, 项目: {task['project_name']}, "
                              f"状态: {task['status']}, 优先级: {task['priority']}, "
                              f"创建时间: {task['created_at']}")
                else:
                    print("未找到匹配的任务")
        
    except TaskQueryError as e:
        print(f"查询失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"程序执行失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()