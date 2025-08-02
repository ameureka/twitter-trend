#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务分布详细分析脚本
分析数据库中任务的分布逻辑和特征
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database.models import Project, PublishingTask, ContentSource, User

def main():
    # 数据库连接
    db_url = f'sqlite:///{project_root}/data/twitter_publisher.db'
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("=" * 80)
    print("任务分布详细分析报告")
    print("=" * 80)
    
    try:
        # 1. 基础统计
        total_tasks = session.query(PublishingTask).count()
        total_projects = session.query(Project).count()
        total_sources = session.query(ContentSource).count()
        
        print(f"\n=== 基础统计 ===")
        print(f"总任务数: {total_tasks}")
        print(f"总项目数: {total_projects}")
        print(f"总内容源数: {total_sources}")
        
        # 2. 任务状态分析
        print(f"\n=== 任务状态分析 ===")
        status_stats = session.query(
            PublishingTask.status,
            func.count(PublishingTask.id)
        ).group_by(PublishingTask.status).all()
        
        for status, count in status_stats:
            percentage = (count / total_tasks * 100) if total_tasks > 0 else 0
            print(f"{status}: {count} 个任务 ({percentage:.1f}%)")
        
        # 3. 项目任务分布分析
        print(f"\n=== 项目任务分布分析 ===")
        project_stats = session.query(
            Project.name,
            func.count(PublishingTask.id)
        ).join(PublishingTask).group_by(Project.name).all()
        
        for project_name, task_count in project_stats:
            percentage = (task_count / total_tasks * 100) if total_tasks > 0 else 0
            print(f"{project_name}: {task_count} 个任务 ({percentage:.1f}%)")
        
        # 4. 内容源分析
        print(f"\n=== 内容源分析 ===")
        sources = session.query(ContentSource).all()
        for source in sources:
            task_count = session.query(PublishingTask).filter(
                PublishingTask.source_id == source.id
            ).count()
            
            project = session.query(Project).filter(
                Project.id == source.project_id
            ).first()
            
            print(f"项目: {project.name if project else 'Unknown'}")
            print(f"  - 内容源类型: {source.source_type}")
            print(f"  - 路径: {source.path_or_identifier}")
            print(f"  - 关联任务数: {task_count}")
            print(f"  - 总项目数: {source.total_items}")
            print(f"  - 已使用项目数: {source.used_items}")
            print(f"  - 最后扫描: {source.last_scanned}")
            print(f"  - 创建时间: {source.created_at}")
            print()
        
        # 5. 媒体文件类型分析
        print(f"=== 媒体文件类型分析 ===")
        tasks_with_media = session.query(PublishingTask.media_path).all()
        
        file_extensions = {}
        for (media_path,) in tasks_with_media:
            if media_path:
                ext = Path(media_path).suffix.lower()
                file_extensions[ext] = file_extensions.get(ext, 0) + 1
        
        for ext, count in sorted(file_extensions.items()):
            percentage = (count / total_tasks * 100) if total_tasks > 0 else 0
            print(f"{ext or '无扩展名'}: {count} 个文件 ({percentage:.1f}%)")
        
        # 6. 任务创建时间分析
        print(f"\n=== 任务创建时间分析 ===")
        earliest_task = session.query(PublishingTask).order_by(
            PublishingTask.created_at.asc()
        ).first()
        
        latest_task = session.query(PublishingTask).order_by(
            PublishingTask.created_at.desc()
        ).first()
        
        if earliest_task and latest_task:
            print(f"最早任务创建时间: {earliest_task.created_at}")
            print(f"最晚任务创建时间: {latest_task.created_at}")
            time_diff = latest_task.created_at - earliest_task.created_at
            print(f"任务创建时间跨度: {time_diff}")
        
        # 7. 任务优先级分析
        print(f"\n=== 任务优先级分析 ===")
        priority_stats = session.query(
            PublishingTask.priority,
            func.count(PublishingTask.id)
        ).group_by(PublishingTask.priority).all()
        
        for priority, count in priority_stats:
            percentage = (count / total_tasks * 100) if total_tasks > 0 else 0
            print(f"优先级 {priority}: {count} 个任务 ({percentage:.1f}%)")
        
        # 8. 内容数据分析
        print(f"\n=== 内容数据分析 ===")
        tasks_with_content = session.query(PublishingTask).filter(
            PublishingTask.content_data.isnot(None)
        ).limit(5).all()
        
        print("示例任务内容数据结构:")
        for i, task in enumerate(tasks_with_content, 1):
            try:
                content_data = json.loads(task.content_data) if task.content_data else {}
                print(f"\n任务 {i} (ID: {task.id}):")
                print(f"  - 媒体文件: {Path(task.media_path).name if task.media_path else 'None'}")
                print(f"  - 内容字段: {list(content_data.keys()) if content_data else 'None'}")
                if 'title' in content_data:
                    title = content_data['title'][:50] + '...' if len(content_data['title']) > 50 else content_data['title']
                    print(f"  - 标题: {title}")
                if 'description' in content_data:
                    desc = content_data['description'][:100] + '...' if len(content_data['description']) > 100 else content_data['description']
                    print(f"  - 描述: {desc}")
            except json.JSONDecodeError:
                print(f"  - 内容数据解析失败")
        
        # 9. 任务分布逻辑总结
        print(f"\n=== 任务分布逻辑总结 ===")
        print("1. 任务创建逻辑:")
        print("   - 基于项目文件夹自动扫描")
        print("   - 每个视频文件对应一个发布任务")
        print("   - 任务内容来自JSON元数据文件")
        print("\n2. 项目结构:")
        print("   - output_video_music/: 存放视频文件")
        print("   - uploader_json/: 存放元数据JSON文件")
        print("\n3. 任务状态:")
        print("   - 新创建的任务默认状态为 'pending'")
        print("   - 优先级默认为 0")
        print("\n4. 内容源管理:")
        print("   - 每个项目有两个内容源: video 和 metadata")
        print("   - 内容源记录文件路径和使用统计")
        
    except Exception as e:
        print(f"查询失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    main()