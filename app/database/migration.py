# app/database/migration.py

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

from .database import DatabaseManager
from .models import User, Project, ContentSource, PublishingTask, PublishingLog
from ..utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseMigration:
    """数据库迁移工具"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.migration_dir = Path(__file__).parent / 'migrations'
        self.migration_dir.mkdir(exist_ok=True)
    
    def get_current_schema_version(self) -> str:
        """获取当前数据库架构版本"""
        try:
            with self.db_manager.engine.connect() as conn:
                # 检查是否存在版本表
                inspector = inspect(self.db_manager.engine)
                if 'schema_version' not in inspector.get_table_names():
                    # 创建版本表
                    conn.execute(text("""
                        CREATE TABLE schema_version (
                            id INTEGER PRIMARY KEY,
                            version VARCHAR(50) NOT NULL,
                            applied_at DATETIME NOT NULL
                        )
                    """))
                    conn.execute(text("""
                        INSERT INTO schema_version (version, applied_at) 
                        VALUES ('1.0.0', ?)
                    """), (datetime.utcnow(),))
                    conn.commit()
                    return '1.0.0'
                
                # 获取最新版本
                result = conn.execute(text("""
                    SELECT version FROM schema_version 
                    ORDER BY applied_at DESC LIMIT 1
                """)).fetchone()
                
                return result[0] if result else '1.0.0'
                
        except SQLAlchemyError as e:
            logger.error(f"获取数据库版本失败: {e}")
            return '1.0.0'
    
    def migrate_from_legacy(self) -> bool:
        """从旧版数据库结构迁移到新版本"""
        logger.info("开始数据库迁移...")
        
        try:
            with self.db_manager.get_repository() as repo:
                # 检查是否是旧版本数据库
                inspector = inspect(self.db_manager.engine)
                table_names = inspector.get_table_names()
                
                # 如果已经是新版本，跳过迁移
                if 'users' in table_names and 'content_sources' in table_names:
                    logger.info("数据库已是最新版本，跳过迁移")
                    return True
                
                # 备份旧数据
                legacy_data = self._backup_legacy_data(repo)
                
                # 创建新表结构
                self.db_manager.create_tables()
                
                # 迁移数据
                self._migrate_legacy_data(repo, legacy_data)
                
                # 更新版本号
                self._update_schema_version('2.0.0')
                
                repo.commit()
                logger.info("数据库迁移完成")
                return True
                
        except Exception as e:
            logger.error(f"数据库迁移失败: {e}")
            return False
    
    def _backup_legacy_data(self, repo) -> Dict[str, List[Dict]]:
        """备份旧版数据"""
        legacy_data = {
            'projects': [],
            'tasks': [],
            'logs': []
        }
        
        try:
            # 备份项目数据
            projects = repo.session.execute(text("SELECT * FROM projects")).fetchall()
            for project in projects:
                legacy_data['projects'].append(dict(project._mapping))
            
            # 备份任务数据
            tasks = repo.session.execute(text("SELECT * FROM publishing_tasks")).fetchall()
            for task in tasks:
                legacy_data['tasks'].append(dict(task._mapping))
            
            # 备份日志数据
            logs = repo.session.execute(text("SELECT * FROM publishing_logs")).fetchall()
            for log in logs:
                legacy_data['logs'].append(dict(log._mapping))
            
            # 保存备份文件
            backup_file = self.migration_dir / f"legacy_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(legacy_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"旧数据备份完成: {backup_file}")
            
        except Exception as e:
            logger.warning(f"备份旧数据时出错: {e}")
        
        return legacy_data
    
    def _migrate_legacy_data(self, repo, legacy_data: Dict[str, List[Dict]]):
        """迁移旧版数据到新结构"""
        # 创建默认用户
        admin_user = repo.users.create_user('admin', 'admin')
        repo.session.flush()
        
        # 迁移项目数据
        project_mapping = {}  # 旧ID -> 新对象
        for old_project in legacy_data.get('projects', []):
            # 创建内容源
            content_source = repo.content_sources.create_content_source(
                project_id=None,  # 稍后设置
                source_type='local_folder',
                path_or_identifier=old_project.get('path', '')
            )
            
            # 创建新项目
            new_project = repo.projects.create_project(
                user_id=admin_user.id,
                name=old_project.get('name', f"Project_{old_project.get('id')}"),
                description=f"从旧版本迁移的项目"
            )
            
            # 更新内容源的项目ID
            content_source.project_id = new_project.id
            
            project_mapping[old_project['id']] = {
                'project': new_project,
                'content_source': content_source
            }
            
            repo.session.flush()
        
        # 迁移任务数据
        task_mapping = {}  # 旧ID -> 新对象
        for old_task in legacy_data.get('tasks', []):
            old_project_id = old_task.get('project_id')
            if old_project_id in project_mapping:
                project_info = project_mapping[old_project_id]
                
                # 构建内容数据
                content_data = {
                    'language': old_task.get('language', 'en'),
                    'metadata_path': old_task.get('metadata_path', ''),
                    'migrated_from_legacy': True
                }
                
                new_task = repo.tasks.create_task(
                    project_id=project_info['project'].id,
                    source_id=project_info['content_source'].id,
                    media_path=old_task.get('media_path', ''),
                    content_data=content_data,
                    scheduled_at=old_task.get('scheduled_at') or datetime.utcnow()
                )
                
                # 保持原有状态和重试次数
                new_task.status = old_task.get('status', 'pending')
                new_task.retry_count = old_task.get('retry_count', 0)
                new_task.created_at = old_task.get('created_at') or datetime.utcnow()
                
                task_mapping[old_task['id']] = new_task
                repo.session.flush()
        
        # 迁移日志数据
        for old_log in legacy_data.get('logs', []):
            old_task_id = old_log.get('task_id')
            if old_task_id in task_mapping:
                new_task = task_mapping[old_task_id]
                
                # 计算总耗时（从毫秒转换为秒）
                duration_seconds = None
                if old_log.get('total_duration'):
                    duration_seconds = old_log['total_duration'] / 1000.0
                
                repo.logs.create_log(
                    task_id=new_task.id,
                    status=old_log.get('status', 'unknown'),
                    tweet_id=old_log.get('tweet_id'),
                    tweet_content=old_log.get('tweet_content'),
                    error_message=old_log.get('error_message'),
                    duration_seconds=duration_seconds
                )
        
        logger.info(f"迁移完成: {len(project_mapping)} 个项目, {len(task_mapping)} 个任务")
    
    def _update_schema_version(self, version: str):
        """更新数据库版本"""
        try:
            with self.db_manager.engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO schema_version (version, applied_at) 
                    VALUES (?, ?)
                """), (version, datetime.utcnow()))
                conn.commit()
                
        except SQLAlchemyError as e:
            logger.error(f"更新数据库版本失败: {e}")
            raise
    
    def export_data(self, output_file: str = None) -> str:
        """导出数据库数据为JSON格式"""
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"database_export_{timestamp}.json"
        
        export_data = {
            'export_time': datetime.utcnow().isoformat(),
            'schema_version': self.get_current_schema_version(),
            'users': [],
            'projects': [],
            'content_sources': [],
            'tasks': [],
            'logs': [],
            'analytics': []
        }
        
        try:
            with self.db_manager.get_repository() as repo:
                # 导出用户
                users = repo.users.list_users()
                for user in users:
                    export_data['users'].append({
                        'id': user.id,
                        'username': user.username,
                        'role': user.role,
                        'created_at': user.created_at.isoformat()
                    })
                
                # 导出项目
                for user in users:
                    projects = repo.projects.list_user_projects(user.id)
                    for project in projects:
                        export_data['projects'].append({
                            'id': project.id,
                            'user_id': project.user_id,
                            'name': project.name,
                            'description': project.description,
                            'created_at': project.created_at.isoformat()
                        })
                        
                        # 导出内容源
                        sources = repo.content_sources.list_project_sources(project.id)
                        for source in sources:
                            export_data['content_sources'].append({
                                'id': source.id,
                                'project_id': source.project_id,
                                'source_type': source.source_type,
                                'path_or_identifier': source.path_or_identifier,
                                'total_items': source.total_items,
                                'used_items': source.used_items,
                                'last_scanned': source.last_scanned.isoformat() if source.last_scanned else None,
                                'created_at': source.created_at.isoformat()
                            })
                
                # 导出任务（最近1000条）
                tasks = repo.session.query(PublishingTask).order_by(
                    PublishingTask.created_at.desc()
                ).limit(1000).all()
                
                for task in tasks:
                    export_data['tasks'].append({
                        'id': task.id,
                        'project_id': task.project_id,
                        'source_id': task.source_id,
                        'media_path': task.media_path,
                        'content_data': task.get_content_data(),
                        'status': task.status,
                        'scheduled_at': task.scheduled_at.isoformat(),
                        'priority': task.priority,
                        'retry_count': task.retry_count,
                        'created_at': task.created_at.isoformat(),
                        'updated_at': task.updated_at.isoformat()
                    })
                
                # 导出日志（最近1000条）
                logs = repo.logs.get_recent_logs(limit=1000)
                for log in logs:
                    export_data['logs'].append({
                        'id': log.id,
                        'task_id': log.task_id,
                        'tweet_id': log.tweet_id,
                        'tweet_content': log.tweet_content,
                        'published_at': log.published_at.isoformat(),
                        'status': log.status,
                        'error_message': log.error_message,
                        'duration_seconds': log.duration_seconds
                    })
            
            # 保存导出文件
            output_path = Path(output_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"数据导出完成: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"数据导出失败: {e}")
            raise
    
    def import_data(self, import_file: str) -> bool:
        """从JSON文件导入数据"""
        import_path = Path(import_file)
        if not import_path.exists():
            raise FileNotFoundError(f"导入文件不存在: {import_file}")
        
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            with self.db_manager.get_repository() as repo:
                # 导入用户
                user_mapping = {}
                for user_data in import_data.get('users', []):
                    existing_user = repo.users.get_user_by_username(user_data['username'])
                    if not existing_user:
                        new_user = repo.users.create_user(
                            username=user_data['username'],
                            role=user_data['role']
                        )
                        user_mapping[user_data['id']] = new_user.id
                    else:
                        user_mapping[user_data['id']] = existing_user.id
                
                repo.session.flush()
                
                # 导入项目和内容源
                project_mapping = {}
                source_mapping = {}
                
                for project_data in import_data.get('projects', []):
                    if project_data['user_id'] in user_mapping:
                        new_project = repo.projects.create_project(
                            user_id=user_mapping[project_data['user_id']],
                            name=project_data['name'],
                            description=project_data.get('description')
                        )
                        project_mapping[project_data['id']] = new_project.id
                
                for source_data in import_data.get('content_sources', []):
                    if source_data['project_id'] in project_mapping:
                        new_source = repo.content_sources.create_content_source(
                            project_id=project_mapping[source_data['project_id']],
                            source_type=source_data['source_type'],
                            path_or_identifier=source_data['path_or_identifier']
                        )
                        source_mapping[source_data['id']] = new_source.id
                
                repo.commit()
                logger.info(f"数据导入完成: {len(user_mapping)} 用户, {len(project_mapping)} 项目")
                return True
                
        except Exception as e:
            logger.error(f"数据导入失败: {e}")
            return False