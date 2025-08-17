#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查content_sources表中的路径数据
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.db_manager import EnhancedDatabaseManager
from app.utils.enhanced_config import get_enhanced_config
from app.database.models import ContentSource

def main():
    try:
        config = get_enhanced_config()
        db_url = config.get('database.url', 'sqlite:///data/twitter_publisher.db')
        db = EnhancedDatabaseManager(db_url)
        
        with db.get_session() as session:
            sources = session.query(ContentSource).all()
            print(f'总共找到 {len(sources)} 个内容源:')
            print('\n前10个内容源的路径信息:')
            for i, s in enumerate(sources[:10], 1):
                print(f'{i}. ID: {s.id}, 项目ID: {s.project_id}, 路径: {s.path_or_identifier}')
            
            # 检查是否有绝对路径
            absolute_paths = []
            for s in sources:
                if s.path_or_identifier and (s.path_or_identifier.startswith('/Users/') or s.path_or_identifier.startswith('/home/')):
                    absolute_paths.append(s)
            
            if absolute_paths:
                print(f'\n发现 {len(absolute_paths)} 个包含绝对路径的内容源:')
                for s in absolute_paths[:5]:
                    print(f'  ID: {s.id}, 项目ID: {s.project_id}, 路径: {s.path_or_identifier}')
            else:
                print('\n✅ 所有内容源路径都是相对路径')
                
    except Exception as e:
        print(f'错误: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()