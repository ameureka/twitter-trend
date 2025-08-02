#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库架构迁移工具

功能：
- 数据库架构迁移和升级
- 复合唯一约束管理
- 索引优化
- 数据完整性检查
- 自动备份和恢复
"""

import sys
import os
import argparse
import json
import time
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.models import Base, PublishingTask
from app.utils.logger import get_logger
import yaml

logger = get_logger(__name__)

class SchemaMigrator:
    """数据库架构迁移器"""
    
    def __init__(self, database_path: Optional[str] = None):
        self.database_path = database_path
        self.engine = None
        self.session = None
        
    def _get_database_url(self) -> str:
        """获取数据库连接URL"""
        if self.database_path:
            return f"sqlite:///{self.database_path}"
            
        # 加载配置文件
        config_path = project_root / 'config/enhanced_config.yaml'
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        else:
            config = {}
        
        db_path = config.get('database', {}).get('path', 'data/twitter_publisher.db')
        
        # 确保数据库目录存在
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        return f"sqlite:///{db_path}"
    
    def connect(self):
        """连接数据库"""
        database_url = self._get_database_url()
        self.engine = create_engine(database_url, echo=False)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        logger.info(f"已连接到数据库: {database_url}")
    
    def disconnect(self):
        """断开数据库连接"""
        if self.session:
            self.session.close()
        if self.engine:
            self.engine.dispose()
        logger.info("数据库连接已关闭")
    
    def backup_database(self) -> Optional[str]:
        """备份数据库"""
        try:
            db_url = str(self.engine.url)
            if db_url.startswith('sqlite:///'):
                db_path = db_url[10:]  # 移除 'sqlite:///' 前缀
                timestamp = int(time.time())
                backup_path = f"{db_path}.migration_backup_{timestamp}"
                
                if os.path.exists(db_path):
                    shutil.copy2(db_path, backup_path)
                    logger.info(f"数据库已备份到: {backup_path}")
                    return backup_path
            
            return None
        except Exception as e:
            logger.warning(f"备份数据库失败: {e}")
            return None
    
    def check_duplicate_tasks(self) -> bool:
        """检查是否存在重复任务"""
        try:
            duplicates_query = text("""
                SELECT project_id, media_path, COUNT(*) as count
                FROM publishing_tasks 
                GROUP BY project_id, media_path 
                HAVING COUNT(*) > 1
            """)
            
            result = self.session.execute(duplicates_query)
            duplicates = result.fetchall()
            
            if duplicates:
                logger.warning(f"发现 {len(duplicates)} 组重复任务:")
                for dup in duplicates:
                    logger.warning(f"  项目ID: {dup.project_id}, 媒体路径: {dup.media_path}, 数量: {dup.count}")
                return True
            else:
                logger.info("未发现重复任务")
                return False
                
        except Exception as e:
            logger.error(f"检查重复任务失败: {e}")
            return False
    
    def clean_duplicate_tasks(self) -> int:
        """清理重复任务，保留最新的"""
        try:
            cleanup_query = text("""
                DELETE FROM publishing_tasks 
                WHERE id NOT IN (
                    SELECT MAX(id) 
                    FROM publishing_tasks 
                    GROUP BY project_id, media_path
                )
            """)
            
            result = self.session.execute(cleanup_query)
            deleted_count = result.rowcount
            
            if deleted_count > 0:
                logger.info(f"清理了 {deleted_count} 个重复任务")
            
            self.session.commit()
            return deleted_count
            
        except Exception as e:
            logger.error(f"清理重复任务失败: {e}")
            self.session.rollback()
            raise
    
    def get_current_schema_info(self) -> Dict[str, Any]:
        """获取当前架构信息"""
        inspector = inspect(self.engine)
        
        return {
            'tables': inspector.get_table_names(),
            'indexes': inspector.get_indexes('publishing_tasks'),
            'constraints': inspector.get_unique_constraints('publishing_tasks'),
            'columns': [col['name'] for col in inspector.get_columns('publishing_tasks')]
        }
    
    def apply_composite_constraint_migration(self):
        """应用复合唯一约束迁移"""
        logger.info("开始应用复合唯一约束迁移...")
        
        with self.engine.connect() as conn:
            trans = conn.begin()
            
            try:
                # 创建新表结构
                logger.info("创建新表结构...")
                conn.execute(text("""
                    CREATE TABLE publishing_tasks_new (
                        id INTEGER PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        source_id INTEGER NOT NULL,
                        media_path TEXT NOT NULL,
                        content_data TEXT NOT NULL,
                        status VARCHAR(50) NOT NULL DEFAULT 'pending',
                        scheduled_at DATETIME NOT NULL,
                        priority INTEGER NOT NULL DEFAULT 0,
                        retry_count INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL,
                        started_at DATETIME,
                        completed_at DATETIME,
                        error_message TEXT,
                        result TEXT,
                        FOREIGN KEY(project_id) REFERENCES projects (id),
                        FOREIGN KEY(source_id) REFERENCES content_sources (id),
                        CONSTRAINT uq_project_media UNIQUE (project_id, media_path)
                    )
                """))
                
                # 复制数据
                logger.info("迁移数据...")
                conn.execute(text("""
                    INSERT INTO publishing_tasks_new (
                        id, project_id, source_id, media_path, content_data, 
                        status, scheduled_at, priority, retry_count, created_at,
                        started_at, completed_at, error_message, result
                    )
                    SELECT 
                        id, project_id, source_id, media_path, content_data,
                        status, scheduled_at, priority, retry_count, created_at,
                        started_at, completed_at, error_message, result
                    FROM publishing_tasks
                """))
                
                # 删除旧表并重命名
                conn.execute(text("DROP TABLE publishing_tasks"))
                conn.execute(text("ALTER TABLE publishing_tasks_new RENAME TO publishing_tasks"))
                
                # 创建优化索引
                self._create_optimized_indexes(conn)
                
                trans.commit()
                logger.info("复合唯一约束迁移完成")
                
            except Exception as e:
                trans.rollback()
                logger.error(f"迁移失败: {e}")
                raise
    
    def _create_optimized_indexes(self, conn):
        """创建优化索引"""
        logger.info("创建优化索引...")
        
        indexes = [
            ("ix_tasks_status_scheduled_priority", "status, scheduled_at, priority"),
            ("ix_tasks_project_status", "project_id, status"),
            ("ix_tasks_created_at", "created_at"),
            ("ix_tasks_project_id", "project_id"),
            ("ix_tasks_source_id", "source_id")
        ]
        
        for index_name, columns in indexes:
            try:
                conn.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS {index_name} 
                    ON publishing_tasks ({columns})
                """))
                logger.info(f"创建索引: {index_name}")
            except Exception as e:
                logger.warning(f"创建索引 {index_name} 失败: {e}")
    
    def verify_migration(self) -> bool:
        """验证迁移结果"""
        logger.info("验证迁移结果...")
        
        inspector = inspect(self.engine)
        indexes = inspector.get_indexes('publishing_tasks')
        constraints = inspector.get_unique_constraints('publishing_tasks')
        
        # 验证复合唯一约束
        has_composite_constraint = any(
            set(constraint['column_names']) == {'project_id', 'media_path'}
            for constraint in constraints
        )
        
        if has_composite_constraint:
            logger.info("✓ 复合唯一约束 (project_id, media_path) 验证成功")
        else:
            logger.error("✗ 复合唯一约束验证失败")
            return False
        
        # 验证关键索引
        required_indexes = ['ix_tasks_project_status', 'ix_tasks_status_scheduled_priority']
        for required_index in required_indexes:
            if any(idx['name'] == required_index for idx in indexes):
                logger.info(f"✓ 索引 {required_index} 验证成功")
            else:
                logger.warning(f"⚠ 索引 {required_index} 可能未创建")
        
        return True
    
    def get_migration_status(self) -> Dict[str, Any]:
        """获取迁移状态"""
        schema_info = self.get_current_schema_info()
        
        # 检查是否已应用复合约束
        has_composite_constraint = any(
            set(constraint['column_names']) == {'project_id', 'media_path'}
            for constraint in schema_info['constraints']
        )
        
        return {
            'has_composite_constraint': has_composite_constraint,
            'table_count': len(schema_info['tables']),
            'index_count': len(schema_info['indexes']),
            'constraint_count': len(schema_info['constraints']),
            'schema_info': schema_info
        }

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='数据库架构迁移工具')
    parser.add_argument('--database', '-d', help='数据库文件路径')
    parser.add_argument('--migrate', action='store_true', help='执行迁移')
    parser.add_argument('--status', action='store_true', help='显示迁移状态')
    parser.add_argument('--check-duplicates', action='store_true', help='检查重复任务')
    parser.add_argument('--clean-duplicates', action='store_true', help='清理重复任务')
    parser.add_argument('--backup', action='store_true', help='仅备份数据库')
    parser.add_argument('--json', action='store_true', help='JSON格式输出')
    
    args = parser.parse_args()
    
    migrator = SchemaMigrator(args.database)
    
    try:
        migrator.connect()
        
        if args.backup:
            backup_path = migrator.backup_database()
            result = {'backup_path': backup_path}
            
        elif args.status:
            result = migrator.get_migration_status()
            
        elif args.check_duplicates:
            has_duplicates = migrator.check_duplicate_tasks()
            result = {'has_duplicates': has_duplicates}
            
        elif args.clean_duplicates:
            deleted_count = migrator.clean_duplicate_tasks()
            result = {'deleted_count': deleted_count}
            
        elif args.migrate:
            # 备份数据库
            backup_path = migrator.backup_database()
            
            # 检查并清理重复任务
            if migrator.check_duplicate_tasks():
                deleted_count = migrator.clean_duplicate_tasks()
                logger.info(f"清理了 {deleted_count} 个重复任务")
            
            # 执行迁移
            migrator.apply_composite_constraint_migration()
            
            # 验证迁移
            success = migrator.verify_migration()
            
            result = {
                'success': success,
                'backup_path': backup_path,
                'migration_completed': True
            }
        else:
            result = migrator.get_migration_status()
        
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            logger.info("操作完成")
            
    except Exception as e:
        logger.error(f"操作失败: {e}")
        if args.json:
            print(json.dumps({'error': str(e)}, ensure_ascii=False))
        return 1
    finally:
        migrator.disconnect()
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)