#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本 - 为项目表添加status和updated_at字段
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.utils.logger import get_logger
from app.database.database import DatabaseManager
from app.utils.enhanced_config import get_enhanced_config
from sqlalchemy import text

logger = get_logger(__name__)

def run_migration():
    """执行数据库迁移"""
    try:
        # 获取数据库配置
        config = get_enhanced_config()
        db_config = config.get_database_config()
        db_url = db_config['url']
        
        if not db_url.startswith('sqlite:///'):
            db_url = f"sqlite:///{config.get_absolute_path(db_url)}"
        
        # 创建数据库管理器
        db_manager = DatabaseManager(db_url)
        
        logger.info("开始执行项目表迁移...")
        
        with db_manager.engine.connect() as conn:
            # 检查是否已经存在status字段
            result = conn.execute(text("PRAGMA table_info(projects)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'status' not in columns:
                logger.info("添加status字段...")
                conn.execute(text("ALTER TABLE projects ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'active'"))
                conn.commit()
                logger.info("status字段添加成功")
            else:
                logger.info("status字段已存在，跳过")
            
            if 'updated_at' not in columns:
                logger.info("添加updated_at字段...")
                # SQLite不支持非常量默认值，先添加可空字段
                conn.execute(text("ALTER TABLE projects ADD COLUMN updated_at DATETIME"))
                conn.commit()
                
                # 更新现有项目的updated_at字段为created_at的值
                logger.info("更新现有项目的updated_at字段...")
                conn.execute(text("UPDATE projects SET updated_at = created_at WHERE updated_at IS NULL"))
                conn.commit()
                
                logger.info("updated_at字段添加成功")
            else:
                logger.info("updated_at字段已存在，跳过")
                
                # 确保现有记录的updated_at字段有值
                logger.info("检查并更新updated_at字段...")
                conn.execute(text("UPDATE projects SET updated_at = created_at WHERE updated_at IS NULL"))
                conn.commit()
            
        logger.info("项目表迁移完成")
        return True
        
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("项目表迁移脚本")
    print("=" * 60)
    
    success = run_migration()
    
    if success:
        print("✅ 迁移成功完成")
        return 0
    else:
        print("❌ 迁移失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())