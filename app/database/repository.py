# app/database/repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func
from datetime import datetime, timedelta
import hashlib
import secrets
import json

from .models import (
    User, ApiKey, Project, ContentSource, 
    PublishingTask, PublishingLog, AnalyticsHourly
)

class UserRepository:
    """用户数据访问层"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_user(self, username: str, role: str = 'editor') -> User:
        """创建用户"""
        user = User(username=username, role=role)
        self.session.add(user)
        self.session.flush()  # 获取ID但不提交
        return user
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        return self.session.query(User).filter(User.id == user_id).first()
    
    def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        return self.session.query(User).filter(User.username == username).first()
    
    def get_all(self) -> List[User]:
        """获取所有用户"""
        return self.session.query(User).all()
    
    def list_users(self) -> List[User]:
        """获取所有用户"""
        return self.session.query(User).order_by(User.created_at.desc()).all()
    
    def create(self, user_data: dict) -> User:
        """创建用户（接受字典参数）"""
        return self.create_user(
            username=user_data['username'],
            role=user_data.get('role', 'editor')
        )

class ApiKeyRepository:
    """API密钥数据访问层"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_api_key(self, user_id: int, permissions: Dict[str, Any]) -> tuple[ApiKey, str]:
        """创建API密钥，返回(ApiKey对象, 原始密钥字符串)"""
        # 生成32字节的随机密钥
        raw_key = secrets.token_urlsafe(32)
        # 计算SHA-256哈希
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        api_key = ApiKey(
            user_id=user_id,
            key_hash=key_hash,
            permissions=json.dumps(permissions)
        )
        self.session.add(api_key)
        self.session.flush()
        return api_key, raw_key
    
    def verify_api_key(self, raw_key: str) -> Optional[ApiKey]:
        """验证API密钥"""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = self.session.query(ApiKey).filter(
            and_(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
        ).first()
        
        if api_key:
            # 更新最后使用时间
            api_key.last_used = datetime.utcnow()
            self.session.flush()
        
        return api_key
    
    def deactivate_api_key(self, api_key_id: int) -> bool:
        """停用API密钥"""
        api_key = self.session.query(ApiKey).filter(ApiKey.id == api_key_id).first()
        if api_key:
            api_key.is_active = False
            self.session.flush()
            return True
        return False
    
    def get_all(self) -> List[ApiKey]:
        """获取所有API密钥"""
        return self.session.query(ApiKey).all()

class ProjectRepository:
    """项目数据访问层"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_project(self, user_id: int, name: str, description: str = None) -> Project:
        """创建项目"""
        project = Project(
            user_id=user_id,
            name=name,
            description=description
        )
        self.session.add(project)
        self.session.flush()
        return project
    
    def get_project_by_id(self, project_id: int) -> Optional[Project]:
        """根据ID获取项目"""
        return self.session.query(Project).filter(Project.id == project_id).first()
    
    def get_project_by_name(self, user_id: int, name: str) -> Optional[Project]:
        """根据用户ID和项目名获取项目"""
        return self.session.query(Project).filter(
            and_(Project.user_id == user_id, Project.name == name)
        ).first()
    
    def list_user_projects(self, user_id: int) -> List[Project]:
        """获取用户的所有项目"""
        return self.session.query(Project).filter(
            Project.user_id == user_id
        ).order_by(Project.created_at.desc()).all()
    
    def get_by_name_and_user(self, name: str, user_id: int) -> Optional[Project]:
        """根据项目名和用户ID获取项目（别名方法）"""
        return self.get_project_by_name(user_id, name)
    
    def get_all(self) -> List[Project]:
        """获取所有项目"""
        return self.session.query(Project).all()
    
    def count_all(self) -> int:
        """获取所有项目数量"""
        return self.session.query(Project).count()
    
    def create(self, project_data: dict) -> Project:
        """创建项目（接受字典参数）"""
        return self.create_project(
            user_id=project_data['user_id'],
            name=project_data['name'],
            description=project_data.get('description')
        )
    
    def update(self, project_id: int, update_data: dict) -> Optional[Project]:
        """更新项目"""
        project = self.get_project_by_id(project_id)
        if project:
            for key, value in update_data.items():
                if hasattr(project, key):
                    setattr(project, key, value)
            self.session.flush()
        return project
    
    def get_paginated(self, user_id: int, page: int = 1, page_size: int = 20, filters: Dict[str, Any] = None) -> tuple[List[Project], int]:
        """分页获取项目列表"""
        query = self.session.query(Project).filter(Project.user_id == user_id)
        
        # 应用过滤器
        if filters:
            if 'is_active' in filters:
                query = query.filter(Project.is_active == filters['is_active'])
            if 'name' in filters:
                query = query.filter(Project.name.ilike(f"%{filters['name']}%"))
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        projects = query.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return projects, total

class ContentSourceRepository:
    """内容源数据访问层"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_content_source(self, project_id: int, source_type: str, 
                            path_or_identifier: str) -> ContentSource:
        """创建内容源"""
        source = ContentSource(
            project_id=project_id,
            source_type=source_type,
            path_or_identifier=path_or_identifier
        )
        self.session.add(source)
        self.session.flush()
        return source
    
    def get_source_by_id(self, source_id: int) -> Optional[ContentSource]:
        """根据ID获取内容源"""
        return self.session.query(ContentSource).filter(
            ContentSource.id == source_id
        ).first()
    
    def list_project_sources(self, project_id: int) -> List[ContentSource]:
        """获取项目的所有内容源"""
        return self.session.query(ContentSource).filter(
            ContentSource.project_id == project_id
        ).order_by(ContentSource.created_at.desc()).all()
    
    def update_source_stats(self, source_id: int, total_items: int, used_items: int):
        """更新内容源统计信息"""
        source = self.get_source_by_id(source_id)
        if source:
            source.total_items = total_items
            source.used_items = used_items
            source.last_scanned = datetime.utcnow()
            self.session.flush()
    
    def create(self, source_data: dict) -> ContentSource:
        """创建内容源（接受字典参数）"""
        return self.create_content_source(
            project_id=source_data['project_id'],
            source_type=source_data['source_type'],
            path_or_identifier=source_data['path_or_identifier']
        )
    
    def get_by_project(self, project_id: int) -> List[ContentSource]:
        """获取项目的所有内容源（别名方法）"""
        return self.list_project_sources(project_id)
    
    def get_all(self) -> List[ContentSource]:
        """获取所有内容源"""
        return self.session.query(ContentSource).all()
    
    def count_all(self) -> int:
        """获取所有内容源数量"""
        return self.session.query(ContentSource).count()

class PublishingTaskRepository:
    """发布任务数据访问层"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_task(self, project_id: int, source_id: int, media_path: str,
                   content_data: Dict[str, Any], scheduled_at: datetime = None,
                   priority: int = 0) -> PublishingTask:
        """创建发布任务"""
        if scheduled_at is None:
            scheduled_at = datetime.utcnow()
        
        task = PublishingTask(
            project_id=project_id,
            source_id=source_id,
            media_path=media_path,
            content_data=json.dumps(content_data, ensure_ascii=False),
            scheduled_at=scheduled_at,
            priority=priority
        )
        self.session.add(task)
        self.session.flush()
        return task
    
    def create_task_if_not_exists(self, project_id: int, source_id: int, media_path: str,
                                 content_data: Dict[str, Any], scheduled_at: datetime = None,
                                 priority: int = 0) -> tuple[PublishingTask, bool]:
        """仅在任务不存在时创建，返回(任务对象, 是否新创建)"""
        # 检查是否已存在相同的任务
        existing = self.session.query(PublishingTask).filter(
            and_(
                PublishingTask.project_id == project_id,
                PublishingTask.media_path == media_path,
                PublishingTask.status.in_(['pending', 'locked', 'in_progress', 'success'])
            )
        ).first()
        
        if existing:
            return existing, False
        
        # 创建新任务
        task = self.create_task(project_id, source_id, media_path, content_data, scheduled_at, priority)
        return task, True
    
    def get_by_id(self, task_id: int) -> Optional[PublishingTask]:
        """根据ID获取任务"""
        return self.session.query(PublishingTask).filter(
            PublishingTask.id == task_id
        ).first()

    def get_pending_tasks(self, limit: int = 10) -> List[PublishingTask]:
        """获取待处理的任务列表"""
        return self.session.query(PublishingTask).filter(
            PublishingTask.status.in_(['pending', 'retry'])
        ).order_by(
            desc(PublishingTask.priority),
            asc(PublishingTask.scheduled_at)
        ).limit(limit).all()

    def get_stuck_tasks(self, timeout_seconds: int) -> List[PublishingTask]:
        """获取卡住的任务"""
        stuck_threshold = datetime.utcnow() - timedelta(seconds=timeout_seconds)
        return self.session.query(PublishingTask).filter(
            PublishingTask.status == 'running',
            PublishingTask.updated_at < stuck_threshold
        ).all()
    
    def get_next_pending_task(self) -> Optional[PublishingTask]:
        """获取下一个待处理任务（按优先级和时间排序）"""
        now = datetime.utcnow()
        return self.session.query(PublishingTask).filter(
            and_(
                PublishingTask.status == 'pending',
                PublishingTask.scheduled_at <= now
            )
        ).order_by(
            desc(PublishingTask.priority),
            asc(PublishingTask.scheduled_at)
        ).with_for_update().first()  # 悲观锁
    
    def lock_task(self, task_id: int) -> bool:
        """锁定任务（设置为locked状态）"""
        task = self.session.query(PublishingTask).filter(
            and_(
                PublishingTask.id == task_id,
                PublishingTask.status == 'pending'
            )
        ).first()
        
        if task:
            task.status = 'locked'
            task.updated_at = datetime.utcnow()
            self.session.flush()
            return True
        return False
    
    def update(self, task_id: int, update_data: Dict[str, Any]) -> bool:
        """更新任务"""
        task = self.session.query(PublishingTask).filter(
            PublishingTask.id == task_id
        ).first()
        
        if task:
            for key, value in update_data.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = datetime.utcnow()
            self.session.flush()
            return True
        return False
    
    def complete_task(self, task_id: int, success: bool, error_message: str = None):
        """完成任务"""
        task = self.session.query(PublishingTask).filter(
            PublishingTask.id == task_id
        ).first()
        
        if task:
            task.status = 'success' if success else 'failed'
            task.updated_at = datetime.utcnow()
            if not success:
                task.retry_count += 1
            self.session.flush()
    
    def update_task_status_atomic(self, task_id: int, status: str, log_data: Dict[str, Any] = None) -> bool:
        """原子性更新任务状态和记录日志"""
        try:
            # 更新任务状态
            task = self.session.query(PublishingTask).filter(
                PublishingTask.id == task_id
            ).first()
            
            if not task:
                return False
            
            task.status = status
            task.updated_at = datetime.utcnow()
            
            # 如果提供了日志数据，同时创建日志记录
            if log_data:
                from .models import PublishingLog
                log = PublishingLog(
                    task_id=task_id,
                    tweet_id=log_data.get('tweet_id'),
                    tweet_content=log_data.get('tweet_content'),
                    published_at=datetime.utcnow(),
                    status=log_data.get('status', status),
                    error_message=log_data.get('error_message'),
                    duration_seconds=log_data.get('duration_seconds')
                )
                self.session.add(log)
            
            self.session.flush()
            return True
        except Exception:
            self.session.rollback()
            return False
    
    def reset_locked_tasks(self, timeout_minutes: int = 30):
        """重置超时的锁定任务"""
        timeout_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        self.session.query(PublishingTask).filter(
            and_(
                PublishingTask.status == 'locked',
                PublishingTask.updated_at < timeout_time
            )
        ).update({
            'status': 'pending',
            'updated_at': datetime.utcnow()
        })
        self.session.flush()
    
    def get_ready_tasks(self, filters: Dict[str, Any] = None, limit: int = None) -> List[PublishingTask]:
        """获取准备就绪的任务（支持过滤器）"""
        query = self.session.query(PublishingTask)
        
        if filters:
            # 状态过滤
            if 'status' in filters:
                if isinstance(filters['status'], list):
                    query = query.filter(PublishingTask.status.in_(filters['status']))
                else:
                    query = query.filter(PublishingTask.status == filters['status'])
            
            # 项目ID过滤
            if 'project_id' in filters:
                query = query.filter(PublishingTask.project_id == filters['project_id'])
            
            # 语言过滤
            if 'language' in filters:
                # 假设language存储在content_data的JSON中
                query = query.filter(PublishingTask.content_data.contains(f'"language": "{filters["language"]}"'))
            
            # 时间过滤
            if 'scheduled_before' in filters:
                query = query.filter(PublishingTask.scheduled_at <= filters['scheduled_before'])
        
        # 按优先级和时间排序
        query = query.order_by(
            desc(PublishingTask.priority),
            asc(PublishingTask.scheduled_at)
        )
        
        if limit:
            query = query.limit(limit)
        
        return query.all()

    def count_all(self) -> int:
        """获取所有任务数量"""
        return self.session.query(PublishingTask).count()
    
    def count_by_status(self, status: str) -> int:
        """根据状态获取任务数量"""
        return self.session.query(PublishingTask).filter(
            PublishingTask.status == status
        ).count()
    
    def count_by_project(self, project_id: int) -> int:
        """根据项目ID获取任务数量"""
        return self.session.query(PublishingTask).filter(
            PublishingTask.project_id == project_id
        ).count()
    
    def count_by_project_and_status(self, project_id: int, status: str) -> int:
        """根据项目ID和状态获取任务数量"""
        return self.session.query(PublishingTask).filter(
            and_(
                PublishingTask.project_id == project_id,
                PublishingTask.status == status
            )
        ).count()

    def get_task_stats(self, project_id: int = None) -> Dict[str, int]:
        """获取任务统计信息"""
        query = self.session.query(
            PublishingTask.status,
            func.count(PublishingTask.id).label('count')
        )
        
        if project_id:
            query = query.filter(PublishingTask.project_id == project_id)
        
        results = query.group_by(PublishingTask.status).all()
        
        stats = {'pending': 0, 'locked': 0, 'success': 0, 'failed': 0}
        for status, count in results:
            stats[status] = count
        
        return stats
    
    def get_project_stats(self, project_id: int) -> Dict[str, int]:
        """获取项目统计信息"""
        query = self.session.query(
            PublishingTask.status,
            func.count(PublishingTask.id).label('count')
        ).filter(PublishingTask.project_id == project_id)
        
        results = query.group_by(PublishingTask.status).all()
        
        stats = {
            'pending': 0, 
            'locked': 0, 
            'success': 0, 
            'failed': 0,
            'in_progress': 0,
            'retry': 0,
            'total': 0
        }
        
        for status, count in results:
            if status in stats:
                stats[status] = count
            # locked状态视为in_progress
            if status == 'locked':
                stats['in_progress'] = count
            stats['total'] += count
        
        return stats
    
    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        """获取用户的所有项目统计信息"""
        # 首先获取用户的所有项目
        from .models import Project
        from sqlalchemy import select
        user_projects = self.session.query(Project.id).filter(Project.user_id == user_id).subquery()
        
        query = self.session.query(
            PublishingTask.status,
            func.count(PublishingTask.id).label('count')
        ).filter(PublishingTask.project_id.in_(select(user_projects.c.id)))
        
        results = query.group_by(PublishingTask.status).all()
        
        stats = {
            'pending': 0, 
            'locked': 0, 
            'success': 0, 
            'failed': 0,
            'in_progress': 0,
            'retry': 0,
            'total': 0
        }
        
        for status, count in results:
            if status in stats:
                stats[status] = count
            # locked状态视为in_progress
            if status == 'locked':
                stats['in_progress'] = count
            stats['total'] += count
        
        return stats
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态信息"""
        now = datetime.utcnow()
        
        # 统计准备执行的任务数量
        ready_count = self.session.query(PublishingTask).filter(
            and_(
                PublishingTask.status == 'pending',
                PublishingTask.scheduled_at <= now
            )
        ).count()
        
        # 获取下一个调度时间
        next_task = self.session.query(PublishingTask).filter(
            and_(
                PublishingTask.status == 'pending',
                PublishingTask.scheduled_at > now
            )
        ).order_by(PublishingTask.scheduled_at.asc()).first()
        
        next_scheduled_at = next_task.scheduled_at if next_task else None
        
        return {
            'ready_to_execute': ready_count,
            'next_scheduled_at': next_scheduled_at
        }
    
    def reset_stuck_tasks(self, timeout_hours: int = 2) -> int:
        """重置卡住的任务，返回重置的任务数量"""
        timeout_time = datetime.utcnow() - timedelta(hours=timeout_hours)
        
        stuck_tasks = self.session.query(PublishingTask).filter(
            and_(
                or_(
                    PublishingTask.status == 'locked',
                    PublishingTask.status == 'in_progress'
                ),
                PublishingTask.updated_at < timeout_time
            )
        )
        
        count = stuck_tasks.count()
        
        if count > 0:
            stuck_tasks.update({
                'status': 'pending',
                'updated_at': datetime.utcnow()
            })
            self.session.flush()
        
        return count
    
    def get_all(self) -> List[PublishingTask]:
        """获取所有发布任务"""
        return self.session.query(PublishingTask).all()
    
    def create(self, task_data: dict) -> PublishingTask:
        """创建发布任务（接受字典参数）"""
        return self.create_task(
            project_id=task_data['project_id'],
            source_id=task_data['source_id'],
            media_path=task_data['media_path'],
            content_data=task_data['content_data'],
            scheduled_at=task_data.get('scheduled_at'),
            priority=task_data.get('priority', 0)
        )
    
    def get_paginated(self, user_id: int, page: int = 1, page_size: int = 20, filters: Dict[str, Any] = None) -> tuple[List[PublishingTask], int]:
        """分页获取任务列表"""
        query = self.session.query(PublishingTask).join(Project).filter(Project.user_id == user_id)
        
        # 应用过滤器
        if filters:
            if 'status' in filters:
                query = query.filter(PublishingTask.status == filters['status'])
            if 'project_id' in filters:
                query = query.filter(PublishingTask.project_id == filters['project_id'])
            if 'content_type' in filters:
                # 假设content_type存储在content_data的JSON中
                query = query.filter(PublishingTask.content_data.contains(f'"content_type": "{filters["content_type"]}"'))
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        tasks = query.order_by(PublishingTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return tasks, total

class PublishingLogRepository:
    """发布日志数据访问层"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, log_data: dict) -> PublishingLog:
        """创建发布日志（接受字典参数）"""
        return self.create_log(
            task_id=log_data['task_id'],
            status=log_data['status'],
            tweet_id=log_data.get('tweet_id'),
            tweet_content=log_data.get('tweet_content'),
            error_message=log_data.get('error_message'),
            duration_seconds=log_data.get('metrics', {}).get('total_duration', 0) / 1000.0 if log_data.get('metrics') else None
        )
    
    def create_log(self, task_id: int, status: str, tweet_id: str = None,
                  tweet_content: str = None, error_message: str = None,
                  duration_seconds: float = None) -> PublishingLog:
        """创建发布日志"""
        log = PublishingLog(
            task_id=task_id,
            tweet_id=tweet_id,
            tweet_content=tweet_content,
            published_at=datetime.utcnow(),
            status=status,
            error_message=error_message,
            duration_seconds=duration_seconds
        )
        self.session.add(log)
        self.session.flush()
        return log
    
    def create_publishing_log(self, **kwargs) -> PublishingLog:
        """创建发布日志（兼容测试）"""
        return self.create_log(**kwargs)
    
    def get_task_logs(self, task_id: int) -> List[PublishingLog]:
        """获取任务日志"""
        return self.session.query(PublishingLog).filter(
            PublishingLog.task_id == task_id
        ).order_by(PublishingLog.published_at.desc()).all()
    
    def get_project_logs(self, project_id: int, page: int = 1, page_size: int = 50):
        """分页获取项目日志"""
        query = self.session.query(PublishingLog).join(PublishingTask).filter(
            PublishingTask.project_id == project_id
        ).order_by(PublishingLog.published_at.desc())
        
        total = query.count()
        logs = query.offset((page - 1) * page_size).limit(page_size).all()
        
        return logs, total
    
    def cleanup_old_logs(self, days: int = 30) -> int:
        """清理旧日志"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted = self.session.query(PublishingLog).filter(
            PublishingLog.published_at < cutoff_date
        ).delete()
        self.session.flush()
        return deleted
    
    def get_recent_logs(self, project_id: int = None, limit: int = 100) -> List[PublishingLog]:
        """获取最近的发布日志"""
        query = self.session.query(PublishingLog).join(PublishingTask)
        
        if project_id:
            query = query.filter(PublishingTask.project_id == project_id)
        
        return query.order_by(
            desc(PublishingLog.published_at)
        ).limit(limit).all()
    
    def get_all(self) -> List[PublishingLog]:
        """获取所有发布日志"""
        return self.session.query(PublishingLog).all()

class AnalyticsRepository:
    """分析统计数据访问层"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def update_hourly_stats(self, project_id: int, hour_timestamp: datetime):
        """更新小时级统计数据"""
        # 计算该小时的统计数据
        hour_start = hour_timestamp.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        
        stats = self.session.query(
            func.count(PublishingLog.id).label('total'),
            func.sum(func.case([(PublishingLog.status == 'success', 1)], else_=0)).label('success'),
            func.sum(func.case([(PublishingLog.status == 'failed', 1)], else_=0)).label('failed'),
            func.avg(PublishingLog.duration_seconds).label('avg_duration')
        ).join(PublishingTask).filter(
            and_(
                PublishingTask.project_id == project_id,
                PublishingLog.published_at >= hour_start,
                PublishingLog.published_at < hour_end
            )
        ).first()
        
        if stats.total > 0:
            # 更新或创建小时统计记录
            hourly_stat = self.session.query(AnalyticsHourly).filter(
                and_(
                    AnalyticsHourly.hour_timestamp == hour_start,
                    AnalyticsHourly.project_id == project_id
                )
            ).first()
            
            if hourly_stat:
                hourly_stat.successful_tasks = stats.success or 0
                hourly_stat.failed_tasks = stats.failed or 0
                hourly_stat.total_duration_seconds = stats.avg_duration
            else:
                hourly_stat = AnalyticsHourly(
                    hour_timestamp=hour_start,
                    project_id=project_id,
                    successful_tasks=stats.success or 0,
                    failed_tasks=stats.failed or 0,
                    total_duration_seconds=stats.avg_duration
                )
                self.session.add(hourly_stat)
            
            self.session.flush()
    
    def get_project_analytics(self, project_id: int, days: int = 7) -> List[AnalyticsHourly]:
        """获取项目分析数据"""
        start_time = datetime.utcnow() - timedelta(days=days)
        return self.session.query(AnalyticsHourly).filter(
            and_(
                AnalyticsHourly.project_id == project_id,
                AnalyticsHourly.hour_timestamp >= start_time
            )
        ).order_by(AnalyticsHourly.hour_timestamp.desc()).all()
    
    def record_hourly_stats(self, analytics_data: dict):
        """记录小时级统计数据"""
        try:
            # 使用当前时间作为小时时间戳
            current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
            self.update_hourly_stats(analytics_data['project_id'], current_hour)
        except Exception as e:
            # 静默处理错误，避免影响主要业务流程
            pass
    
    def update_hourly_analytics(self, project_id: int, hour_timestamp: datetime, 
                               successful_tasks: int, failed_tasks: int, 
                               total_duration_seconds: float):
        """更新小时分析数据（兼容测试）"""
        hour_start = hour_timestamp.replace(minute=0, second=0, microsecond=0)
        
        # 查找现有记录
        hourly_stat = self.session.query(AnalyticsHourly).filter(
            and_(
                AnalyticsHourly.hour_timestamp == hour_start,
                AnalyticsHourly.project_id == project_id
            )
        ).first()
        
        if hourly_stat:
            # 更新现有记录（累加）
            hourly_stat.successful_tasks += successful_tasks
            hourly_stat.failed_tasks += failed_tasks
            if hourly_stat.total_duration_seconds:
                hourly_stat.total_duration_seconds += total_duration_seconds
            else:
                hourly_stat.total_duration_seconds = total_duration_seconds
        else:
            # 创建新记录
            hourly_stat = AnalyticsHourly(
                hour_timestamp=hour_start,
                project_id=project_id,
                successful_tasks=successful_tasks,
                failed_tasks=failed_tasks,
                total_duration_seconds=total_duration_seconds
            )
            self.session.add(hourly_stat)
        
        self.session.flush()
    
    def get_project_analytics_summary(self, project_id: int, hours: int = 24):
        """获取项目分析摘要"""
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        result = self.session.query(
            func.sum(AnalyticsHourly.successful_tasks).label('total_successful'),
            func.sum(AnalyticsHourly.failed_tasks).label('total_failed'),
            func.sum(AnalyticsHourly.total_duration_seconds).label('total_duration_seconds'),
            func.avg(AnalyticsHourly.total_duration_seconds).label('average_duration_seconds')
        ).filter(
            and_(
                AnalyticsHourly.project_id == project_id,
                AnalyticsHourly.hour_timestamp >= start_time
            )
        ).first()
        
        return {
            'total_successful': result.total_successful or 0,
            'total_failed': result.total_failed or 0,
            'total_duration_seconds': result.total_duration_seconds or 0,
            'average_duration_seconds': result.average_duration_seconds or 0
        }
    
    def get_hourly_analytics_data(self, project_id: int, start_time: datetime, end_time: datetime):
        """获取小时分析数据"""
        return self.session.query(AnalyticsHourly).filter(
            and_(
                AnalyticsHourly.project_id == project_id,
                AnalyticsHourly.hour_timestamp >= start_time,
                AnalyticsHourly.hour_timestamp <= end_time
            )
        ).order_by(AnalyticsHourly.hour_timestamp.desc()).all()
    
    def cleanup_old_analytics(self, days: int = 90) -> int:
        """清理旧分析数据"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted = self.session.query(AnalyticsHourly).filter(
            AnalyticsHourly.hour_timestamp < cutoff_date
        ).delete()
        self.session.flush()
        return deleted
    
    def get_all(self) -> List[AnalyticsHourly]:
        """获取所有分析数据"""
        return self.session.query(AnalyticsHourly).all()

class DatabaseRepository:
    """数据库仓库统一入口"""
    
    def __init__(self, session: Session):
        self.session = session
        self.users = UserRepository(session)
        self.api_keys = ApiKeyRepository(session)
        self.projects = ProjectRepository(session)
        self.content_sources = ContentSourceRepository(session)
        self.tasks = PublishingTaskRepository(session)
        self.logs = PublishingLogRepository(session)
        self.analytics = AnalyticsRepository(session)
    
    def __enter__(self):
        """进入上下文管理器"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()
    
    def commit(self):
        """提交事务"""
        self.session.commit()
    
    def rollback(self):
        """回滚事务"""
        self.session.rollback()
    
    def close(self):
        """关闭会话"""
        self.session.close()