#!/usr/bin/env python3
"""
查询数据库中的任务分布情况
"""

import sys
import os
from pathlib import Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.database import DatabaseManager
from app.database.models import *
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

def main():
    # 初始化数据库连接
    project_root = Path(__file__).parent.parent.parent
    db_path = project_root / 'data' / 'twitter_publisher.db'
    db_url = f'sqlite:///{db_path}'
    db = DatabaseManager(db_url)
    db.create_tables()
    
    Session = sessionmaker(bind=db.engine)
    session = Session()
    
    try:
        print("=" * 60)
        print("数据库任务分布查询报告")
        print("=" * 60)
        
        # 1. 任务总数统计
        print("\n=== 任务总数统计 ===")
        total_tasks = session.query(PublishingTask).count()
        print(f"总任务数: {total_tasks}")
        
        # 2. 按状态分布
        print("\n=== 按状态分布 ===")
        status_stats = session.query(
            PublishingTask.status, 
            func.count(PublishingTask.id)
        ).group_by(PublishingTask.status).all()
        
        for status, count in status_stats:
            percentage = (count / total_tasks * 100) if total_tasks > 0 else 0
            print(f"{status}: {count} 个任务 ({percentage:.1f}%)")
        
        # 3. 按项目分布
        print("\n=== 按项目分布 ===")
        project_stats = session.query(
            Project.name, 
            func.count(PublishingTask.id)
        ).join(PublishingTask).group_by(Project.name).all()
        
        for project_name, count in project_stats:
            percentage = (count / total_tasks * 100) if total_tasks > 0 else 0
            print(f"{project_name}: {count} 个任务 ({percentage:.1f}%)")
        
        # 4. 按优先级分布
        print("\n=== 按优先级分布 ===")
        priority_stats = session.query(
            PublishingTask.priority, 
            func.count(PublishingTask.id)
        ).group_by(PublishingTask.priority).all()
        
        for priority, count in priority_stats:
            percentage = (count / total_tasks * 100) if total_tasks > 0 else 0
            print(f"优先级 {priority}: {count} 个任务 ({percentage:.1f}%)")
        
        # 5. 任务创建时间分布（最近创建的任务）
        print("\n=== 最近创建的任务 ===")
        recent_tasks = session.query(PublishingTask).order_by(
            PublishingTask.created_at.desc()
        ).limit(5).all()
        
        for task in recent_tasks:
            project = session.query(Project).filter(Project.id == task.project_id).first()
            print(f"ID: {task.id}, 项目: {project.name if project else 'Unknown'}, "
                  f"状态: {task.status}, 优先级: {task.priority}, "
                  f"创建时间: {task.created_at}")
        
        # 6. 项目详细信息
        print("\n=== 项目详细信息 ===")
        projects = session.query(Project).all()
        for project in projects:
            task_count = session.query(PublishingTask).filter(
                PublishingTask.project_id == project.id
            ).count()
            
            pending_count = session.query(PublishingTask).filter(
                PublishingTask.project_id == project.id,
                PublishingTask.status == 'pending'
            ).count()
            
            print(f"项目: {project.name}")
            print(f"  - 总任务数: {task_count}")
            print(f"  - 待处理任务: {pending_count}")
            print(f"  - 项目描述: {project.description}")
            print(f"  - 最后扫描: {project.last_scanned}")
            print(f"  - 创建时间: {project.created_at}")
            print()
        
        print("=" * 60)
        print("查询完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"查询失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    main()