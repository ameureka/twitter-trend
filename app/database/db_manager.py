#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库管理器 - 优化的数据库初始化、清理和维护功能

主要功能:
1. 智能数据库初始化
2. 数据清理和重置
3. 数据库健康检查
4. 自动备份和恢复
5. 性能优化
"""

import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database.database import DatabaseManager as BaseDBManager
from app.database.models import Base, User, Project, PublishingTask, PublishingLog
from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config
from app.utils.path_manager import get_path_manager

logger = get_logger(__name__)


class EnhancedDatabaseManager(BaseDBManager):
    def remove_session(self):
        """移除数据库会话，传递给基类"""
        super().remove_session()
    """数据库管理器"""
    
    def __init__(self, database_url: str = None):
        super().__init__(database_url)
        self.config = get_enhanced_config()
        self.path_manager = get_path_manager()
        self.db_url = database_url or self._get_default_database_url()
        
    def _get_default_database_url(self) -> str:
        """获取默认数据库URL"""
        # 使用路径管理器获取数据库路径
        return self.path_manager.create_database_url()
        
    def initialize_database(self, force_reset: bool = False) -> Dict[str, Any]:
        """
        智能数据库初始化
        
        Args:
            force_reset: 是否强制重置数据库
            
        Returns:
            初始化结果信息
        """
        result = {
            'action': 'initialize',
            'success': False,
            'message': '',
            'details': {}
        }
        
        try:
            # 检查数据库是否存在
            db_exists = self._check_database_exists()
            
            if force_reset and db_exists:
                logger.info("强制重置数据库")
                self._backup_database()
                self._drop_all_tables()
                db_exists = False
                result['details']['backup_created'] = True
                
            if not db_exists:
                logger.info("创建新数据库")
                self._create_all_tables()
                self._create_default_data()
                result['details']['tables_created'] = True
                result['details']['default_data_created'] = True
            else:
                logger.info("数据库已存在，检查完整性")
                integrity_check = self._check_database_integrity()
                result['details']['integrity_check'] = integrity_check
                
                if not integrity_check['valid']:
                    logger.warning("数据库完整性检查失败，尝试修复")
                    self._repair_database()
                    result['details']['repair_attempted'] = True
                    
            # 运行数据库优化
            self._optimize_database()
            result['details']['optimization_completed'] = True
            
            result['success'] = True
            result['message'] = '数据库初始化成功'
            logger.info("数据库初始化完成")
            
        except Exception as e:
            result['message'] = f'数据库初始化失败: {str(e)}'
            logger.error(f"数据库初始化失败: {e}", exc_info=True)
            
        return result
        
    def clean_database(self, 
                      clean_tasks: bool = True,
                      clean_logs: bool = True,
                      days_to_keep: int = 30) -> Dict[str, Any]:
        """
        清理数据库中的过期数据
        
        Args:
            clean_tasks: 是否清理已完成的任务
            clean_logs: 是否清理旧日志
            days_to_keep: 保留多少天的数据
            
        Returns:
            清理结果信息
        """
        result = {
            'action': 'clean',
            'success': False,
            'message': '',
            'details': {}
        }
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            with self.get_repository() as repo:
                cleaned_count = 0
                
                if clean_tasks:
                    # 清理已完成的旧任务
                    completed_tasks = repo.session.query(PublishingTask).filter(
                        PublishingTask.status == 'completed',
                        PublishingTask.executed_time < cutoff_date
                    ).count()
                    
                    repo.session.query(PublishingTask).filter(
                        PublishingTask.status == 'completed',
                        PublishingTask.executed_time < cutoff_date
                    ).delete()
                    
                    cleaned_count += completed_tasks
                    result['details']['cleaned_tasks'] = completed_tasks
                    
                if clean_logs:
                    # 清理旧日志
                    old_logs = repo.session.query(PublishingLog).filter(
                        PublishingLog.created_at < cutoff_date
                    ).count()
                    
                    repo.session.query(PublishingLog).filter(
                        PublishingLog.created_at < cutoff_date
                    ).delete()
                    
                    cleaned_count += old_logs
                    result['details']['cleaned_logs'] = old_logs
                    
                repo.commit()
                
            # 运行VACUUM优化
            self._vacuum_database()
            result['details']['vacuum_completed'] = True
            
            result['success'] = True
            result['message'] = f'清理完成，删除了 {cleaned_count} 条记录'
            logger.info(f"数据库清理完成，删除了 {cleaned_count} 条记录")
            
        except Exception as e:
            result['message'] = f'数据库清理失败: {str(e)}'
            logger.error(f"数据库清理失败: {e}", exc_info=True)
            
        return result
        
    def backup_database(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """
        备份数据库
        
        Args:
            backup_name: 备份文件名，如果不提供则自动生成
            
        Returns:
            备份结果信息
        """
        result = {
            'action': 'backup',
            'success': False,
            'message': '',
            'backup_path': ''
        }
        
        try:
            backup_path = self._backup_database(backup_name)
            result['success'] = True
            result['message'] = '数据库备份成功'
            result['backup_path'] = backup_path
            logger.info(f"数据库备份成功: {backup_path}")
            
        except Exception as e:
            result['message'] = f'数据库备份失败: {str(e)}'
            logger.error(f"数据库备份失败: {e}", exc_info=True)
            
        return result
        
    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息
        
        Returns:
            数据库统计信息
        """
        stats = {
            'tables': {},
            'size': {},
            'performance': {}
        }
        
        try:
            with self.get_repository() as repo:
                # 获取表记录数
                stats['tables']['users'] = repo.session.query(User).count()
                stats['tables']['projects'] = repo.session.query(Project).count()
                stats['tables']['tasks'] = repo.session.query(PublishingTask).count()
                stats['tables']['logs'] = repo.session.query(PublishingLog).count()
                
                # 获取任务状态分布
                task_status = repo.session.execute(text("""
                    SELECT status, COUNT(*) as count 
                    FROM publishing_tasks 
                    GROUP BY status
                """)).fetchall()
                
                stats['tasks_by_status'] = {row[0]: row[1] for row in task_status}
                
            # 获取数据库文件大小
            db_path = self._get_database_path()
            if db_path and os.path.exists(db_path):
                size_bytes = os.path.getsize(db_path)
                stats['size']['bytes'] = size_bytes
                stats['size']['mb'] = round(size_bytes / (1024 * 1024), 2)
                
            # 获取性能指标
            stats['performance'] = self._get_performance_stats()
            
        except Exception as e:
            logger.error(f"获取数据库统计信息失败: {e}")
            stats['error'] = str(e)
            
        return stats
        
    def check_health(self) -> Dict[str, Any]:
        """检查数据库健康状态"""
        health = {
            'healthy': True,
            'status': 'healthy',
            'issues': [],
            'recommendations': []
        }
        
        try:
            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # 检查表完整性
            integrity = self._check_database_integrity()
            if not integrity['valid']:
                health['healthy'] = False
                health['status'] = 'unhealthy'
                health['issues'].extend(integrity['issues'])
                
            # 检查数据库大小
            stats = self.get_database_stats()
            if 'size' in stats and 'mb' in stats['size']:
                size_mb = stats['size']['mb']
                if size_mb > 1000:  # 大于1GB
                    health['recommendations'].append('数据库文件较大，建议清理旧数据')
                    
        except Exception as e:
            health['healthy'] = False
            health['status'] = 'unhealthy'
            health['issues'].append(f'数据库连接失败: {str(e)}')
            logger.error(f"数据库健康检查失败: {e}")
            
        return health
        
    def _check_database_exists(self) -> bool:
        """检查数据库是否存在"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables = [row[0] for row in result.fetchall()]
                return len(tables) > 0
        except Exception:
            return False
            
    def _check_database_integrity(self) -> Dict[str, Any]:
        """检查数据库完整性"""
        integrity = {
            'valid': True,
            'issues': []
        }
        
        try:
            with self.engine.connect() as conn:
                # 检查表是否存在
                required_tables = ['users', 'projects', 'content_sources', 
                                 'publishing_tasks', 'publishing_logs']
                
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                existing_tables = [row[0] for row in result.fetchall()]
                
                for table in required_tables:
                    if table not in existing_tables:
                        integrity['valid'] = False
                        integrity['issues'].append(f'缺少表: {table}')
                        
                # 检查外键约束
                result = conn.execute(text("PRAGMA foreign_key_check"))
                fk_errors = result.fetchall()
                if fk_errors:
                    integrity['valid'] = False
                    integrity['issues'].append(f'外键约束错误: {len(fk_errors)} 个')
                    
        except Exception as e:
            integrity['valid'] = False
            integrity['issues'].append(f'完整性检查失败: {str(e)}')
            
        return integrity
        
    def _create_all_tables(self):
        """创建所有表"""
        Base.metadata.create_all(bind=self.engine)
        
    def _drop_all_tables(self):
        """删除所有表"""
        Base.metadata.drop_all(bind=self.engine)
        
    def _create_default_data(self):
        """创建默认数据"""
        with self.get_repository() as repo:
            # 创建默认用户
            default_user = User(
                username='admin',
                role='admin'
            )
            repo.session.add(default_user)
            repo.commit()
            logger.info("创建默认用户")
            
    def _backup_database(self, backup_name: Optional[str] = None) -> str:
        """备份数据库文件"""
        db_path = self._get_database_path()
        if not db_path or not os.path.exists(db_path):
            raise FileNotFoundError("数据库文件不存在")
            
        # 创建备份目录
        backup_dir = Path(self.config.get('database', {}).get('backup_path', 'data/backups'))
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成备份文件名
        if not backup_name:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f'database_backup_{timestamp}.db'
            
        backup_path = backup_dir / backup_name
        
        # 复制数据库文件
        shutil.copy2(db_path, backup_path)
        
        return str(backup_path)
        
    def _get_database_path(self) -> Optional[str]:
        """获取数据库文件路径"""
        if self.db_url.startswith('sqlite:///'):
            return self.db_url.replace('sqlite:///', '')
        return None
        
    def _repair_database(self):
        """修复数据库"""
        try:
            with self.engine.connect() as conn:
                # 重建索引
                conn.execute(text("REINDEX"))
                # 分析表统计信息
                conn.execute(text("ANALYZE"))
                conn.commit()
                logger.info("数据库修复完成")
        except Exception as e:
            logger.error(f"数据库修复失败: {e}")
            
    def _optimize_database(self):
        """优化数据库性能"""
        try:
            with self.engine.connect() as conn:
                # 启用外键约束
                conn.execute(text("PRAGMA foreign_keys = ON"))
                # 设置DELETE模式（避免WAL模式的并发锁定问题）
                conn.execute(text("PRAGMA journal_mode = DELETE"))
                # 设置同步模式
                conn.execute(text("PRAGMA synchronous = NORMAL"))
                # 设置缓存大小
                conn.execute(text("PRAGMA cache_size = 10000"))
                # 设置忙等待超时
                conn.execute(text("PRAGMA busy_timeout = 30000"))
                conn.commit()
                logger.info("数据库优化完成")
        except Exception as e:
            logger.error(f"数据库优化失败: {e}")
            
    def _vacuum_database(self):
        """清理数据库碎片"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("VACUUM"))
                conn.commit()
                logger.info("数据库VACUUM完成")
        except Exception as e:
            logger.error(f"数据库VACUUM失败: {e}")
            
    def _get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        stats = {}
        
        try:
            with self.engine.connect() as conn:
                # 获取页面统计
                result = conn.execute(text("PRAGMA page_count")).fetchone()
                if result:
                    stats['page_count'] = result[0]
                    
                result = conn.execute(text("PRAGMA page_size")).fetchone()
                if result:
                    stats['page_size'] = result[0]
                    
                # 获取缓存统计
                result = conn.execute(text("PRAGMA cache_size")).fetchone()
                if result:
                    stats['cache_size'] = result[0]
                    
        except Exception as e:
            logger.error(f"获取性能统计失败: {e}")
            stats['error'] = str(e)
            
        return stats