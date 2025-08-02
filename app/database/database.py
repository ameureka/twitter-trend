# app/database/database.py

import os
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import SQLAlchemyError

from .models import Base, User
from .repository import DatabaseRepository
from ..utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseManager:
    """强化版数据库管理器 - 支持迁移、备份和维护"""
    
    def __init__(self, database_url: str = None):
        if database_url is None:
            # 默认使用SQLite数据库
            db_dir = Path(__file__).parent.parent.parent / 'data'
            db_dir.mkdir(exist_ok=True)
            self.db_path = db_dir / 'twitter_publisher.db'
            database_url = f"sqlite:///{self.db_path}"
        else:
            self.db_path = None
        
        self.database_url = database_url
        # For SQLite, use NullPool to prevent connection sharing across threads
        poolclass = NullPool if 'sqlite' in self.database_url else None

        self.engine = create_engine(
            self.database_url,
            echo=False,
            poolclass=poolclass,
            connect_args={'check_same_thread': False} if 'sqlite' in self.database_url else {}
        )
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.SessionLocal = scoped_session(session_factory)
        
    def create_tables(self):
        """创建所有数据库表"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("数据库表创建成功")
            
            # 检查是否需要创建默认用户
            self._ensure_default_user()
            
        except SQLAlchemyError as e:
            logger.error(f"创建数据库表失败: {e}")
            raise
    
    def _ensure_default_user(self):
        """确保存在默认用户"""
        try:
            with self.get_repository() as repo:
                # 检查是否已有用户
                users = repo.users.list_users()
                if not users:
                    # 创建默认管理员用户
                    default_user = repo.users.create_user(
                        username='admin',
                        role='admin'
                    )
                    repo.commit()
                    logger.info(f"创建默认用户: {default_user.username}")
        except SQLAlchemyError as e:
            logger.error(f"创建默认用户失败: {e}")
    
    def get_session(self):
        """获取数据库会话"""
        return self.SessionLocal

    def remove_session(self):
        """移除数据库会话"""
        self.SessionLocal.remove()
    
    def get_repository(self) -> DatabaseRepository:
        """获取数据库仓库（上下文管理器）"""
        return DatabaseRepository(self.get_session())
    
    def backup_database(self, backup_dir: str = None) -> str:
        """备份数据库"""
        if not self.db_path or not self.db_path.exists():
            raise ValueError("只支持SQLite数据库备份")
        
        if backup_dir is None:
            backup_dir = self.db_path.parent / 'backups'
        
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"backup_{timestamp}.db"
        
        try:
            # 使用SQLite的备份API
            source = sqlite3.connect(str(self.db_path))
            backup = sqlite3.connect(str(backup_file))
            source.backup(backup)
            backup.close()
            source.close()
            
            logger.info(f"数据库备份成功: {backup_file}")
            return str(backup_file)
            
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            raise
    
    def restore_database(self, backup_file: str):
        """从备份恢复数据库"""
        if not self.db_path:
            raise ValueError("只支持SQLite数据库恢复")
        
        backup_path = Path(backup_file)
        if not backup_path.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_file}")
        
        try:
            # 关闭当前连接
            self.close()
            
            # 备份当前数据库
            if self.db_path.exists():
                current_backup = f"{self.db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(self.db_path, current_backup)
                logger.info(f"当前数据库已备份到: {current_backup}")
            
            # 恢复数据库
            shutil.copy2(backup_path, self.db_path)
            
            # 重新初始化连接
            self.engine = create_engine(
                self.database_url,
                echo=False,
                pool_pre_ping=True,
                connect_args={'check_same_thread': False}
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            logger.info(f"数据库恢复成功: {backup_file}")
            
        except Exception as e:
            logger.error(f"数据库恢复失败: {e}")
            raise
    
    def vacuum_database(self):
        """优化数据库（VACUUM和ANALYZE）"""
        try:
            with self.engine.connect() as conn:
                # 执行VACUUM命令
                conn.execute(text("VACUUM;"))
                logger.info("数据库VACUUM完成")
                
                # 执行ANALYZE命令
                conn.execute(text("ANALYZE;"))
                logger.info("数据库ANALYZE完成")
                
                conn.commit()
                
        except SQLAlchemyError as e:
            logger.error(f"数据库优化失败: {e}")
            raise
    
    def purge_old_logs(self, days: int = 180):
        """清理旧的发布日志"""
        try:
            with self.get_repository() as repo:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                # 删除旧日志
                deleted_count = repo.session.query(PublishingLog).filter(
                    PublishingLog.published_at < cutoff_date
                ).delete()
                
                repo.commit()
                logger.info(f"清理了 {deleted_count} 条旧日志记录")
                
        except SQLAlchemyError as e:
            logger.error(f"清理旧日志失败: {e}")
            raise
    
    def get_database_stats(self) -> dict:
        """获取数据库统计信息"""
        try:
            with self.get_repository() as repo:
                stats = {
                    'users_count': repo.session.query(User).count(),
                    'projects_count': repo.session.query(Project).count(),
                    'content_sources_count': repo.session.query(ContentSource).count(),
                    'tasks_count': repo.session.query(PublishingTask).count(),
                    'logs_count': repo.session.query(PublishingLog).count(),
                    'analytics_count': repo.session.query(AnalyticsHourly).count()
                }
                
                # 获取数据库文件大小（仅SQLite）
                if self.db_path and self.db_path.exists():
                    stats['database_size_mb'] = round(self.db_path.stat().st_size / (1024 * 1024), 2)
                
                return stats
                
        except SQLAlchemyError as e:
            logger.error(f"获取数据库统计失败: {e}")
            return {}
    
    def check_database_health(self) -> dict:
        """检查数据库健康状态"""
        health = {
            'status': 'healthy',
            'issues': [],
            'recommendations': []
        }
        
        try:
            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # 检查表完整性（仅SQLite）
            if 'sqlite' in self.database_url:
                with self.engine.connect() as conn:
                    result = conn.execute(text("PRAGMA integrity_check;")).fetchone()
                    if result[0] != 'ok':
                        health['status'] = 'warning'
                        health['issues'].append(f"数据库完整性检查失败: {result[0]}")
            
            # 检查锁定的任务
            with self.get_repository() as repo:
                locked_tasks = repo.session.query(PublishingTask).filter(
                    PublishingTask.status == 'locked'
                ).count()
                
                if locked_tasks > 0:
                    health['issues'].append(f"发现 {locked_tasks} 个锁定状态的任务")
                    health['recommendations'].append("运行 reset-locked-tasks 命令清理超时任务")
            
            # 检查数据库大小
            stats = self.get_database_stats()
            if stats.get('database_size_mb', 0) > 1000:  # 大于1GB
                health['recommendations'].append("数据库文件较大，建议运行清理和优化命令")
            
        except Exception as e:
            health['status'] = 'error'
            health['issues'].append(f"数据库连接失败: {e}")
        
        return health
    
    def reset_locked_tasks(self, timeout_minutes: int = 30):
        """重置超时的锁定任务"""
        try:
            with self.get_repository() as repo:
                repo.tasks.reset_locked_tasks(timeout_minutes)
                repo.commit()
                logger.info(f"重置了超时 {timeout_minutes} 分钟的锁定任务")
                
        except SQLAlchemyError as e:
            logger.error(f"重置锁定任务失败: {e}")
            raise
    
    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'engine'):
            self.engine.dispose()
            logger.debug("数据库连接已关闭")

# 导入必要的模型（避免循环导入）
from .models import Project, ContentSource, PublishingTask, PublishingLog, AnalyticsHourly
from datetime import timedelta