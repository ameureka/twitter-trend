#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 publishing_tasks 表中的媒体文件路径
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.db_manager import EnhancedDatabaseManager
from app.utils.enhanced_config import get_enhanced_config
from app.database.models import PublishingTask
from app.database.repository import PublishingTaskRepository

def main():
    try:
        config = get_enhanced_config()
        db_url = config.get('database.url', 'sqlite:///data/twitter_publisher.db')
        db = EnhancedDatabaseManager(db_url)
        
        # 获取所有发布任务
        with db.get_session_context() as session:
            task_repo = PublishingTaskRepository(session)
            tasks = task_repo.get_all()
            
            print(f'总共找到 {len(tasks)} 个发布任务:')
            
            if tasks:
                print('\n前10个发布任务的媒体文件路径信息:')
                for i, task in enumerate(tasks[:10], 1):
                    print(f'{i}. ID: {task.id}, 项目ID: {task.project_id}, 状态: {task.status}')
                    print(f'   媒体文件: {task.media_path}')
                    print(f'   内容数据: {task.content_data[:100]}...' if len(task.content_data) > 100 else f'   内容数据: {task.content_data}')
                    print()
                
                # 检查是否有绝对路径
                absolute_media_paths = [t for t in tasks if t.media_path and (t.media_path.startswith('/Users/') or t.media_path.startswith('/home/'))]
                
                if absolute_media_paths:
                    print(f'\n❌ 发现 {len(absolute_media_paths)} 个包含绝对媒体文件路径的任务:')
                    for task in absolute_media_paths[:5]:
                        print(f'  ID: {task.id}, 项目ID: {task.project_id}, 媒体文件: {task.media_path}')
                else:
                    print('\n✅ 所有媒体文件路径都是相对路径')
            else:
                print('\n没有找到任何发布任务')
            
    except Exception as e:
        print(f'错误: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()