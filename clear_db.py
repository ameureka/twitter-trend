#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清空数据库内容脚本
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database.db_manager import EnhancedDatabaseManager
from app.utils.logger import setup_logger, get_logger
from app.utils.enhanced_config import get_enhanced_config

def clear_database():
    """清空数据库内容（保留表结构）"""
    setup_logger(log_level='INFO')
    logger = get_logger('clear_db')
    
    try:
        config = get_enhanced_config()
        
        # 获取数据库路径
        db_path = config.get('database', {}).get('path', './data/twitter_publisher.db')
        if not os.path.isabs(db_path):
            db_path = project_root / db_path.lstrip('./')
        
        # 确保数据目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 初始化数据库管理器
        db_manager = EnhancedDatabaseManager(f"sqlite:///{db_path}")
        
        logger.info("开始清空数据库内容...")
        
        session = db_manager.get_session()()
        try:
            from app.database.models import (
                PublishingTask, PublishingLog, ContentSource, 
                Project, AnalyticsHourly
            )
            
            # 按依赖关系顺序删除
            tables_to_clear = [
                (PublishingLog, "发布日志"),
                (AnalyticsHourly, "分析数据"),
                (PublishingTask, "发布任务"),
                (ContentSource, "内容源"),
                (Project, "项目")
            ]
            
            cleared_counts = {}
            for model_class, name in tables_to_clear:
                count = session.query(model_class).count()
                if count > 0:
                    session.query(model_class).delete()
                    cleared_counts[name] = count
                    logger.info(f"清空 {name}: {count} 条记录")
            
            session.commit()
            logger.info("数据库内容清空完成")
            
            if cleared_counts:
                logger.info(f"清空统计: {cleared_counts}")
            else:
                logger.info("数据库已经是空的")
                
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"清空数据库失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    clear_database()