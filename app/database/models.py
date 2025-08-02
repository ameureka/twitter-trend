# app/database/models.py

from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, ForeignKey, Text, 
    Boolean, Float, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import json

Base = declarative_base()

class User(Base):
    """用户表 - 支持多用户和API化"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    role = Column(String(50), nullable=False, default='editor')  # admin, editor
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 关系
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")

class ApiKey(Base):
    """API密钥表 - 为外部服务提供认证"""
    __tablename__ = 'api_keys'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)  # SHA-256哈希
    permissions = Column(Text)  # JSON格式权限描述
    last_used = Column(DateTime)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="api_keys")
    
    def get_permissions(self):
        """获取权限字典"""
        if self.permissions:
            return json.loads(self.permissions)
        return {}
    
    def set_permissions(self, permissions_dict):
        """设置权限字典"""
        self.permissions = json.dumps(permissions_dict)

class Project(Base):
    """项目表 - 强化版，支持用户关联"""
    __tablename__ = 'projects'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), nullable=False, default='active')  # active, paused, inactive
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 唯一约束：同一用户下项目名唯一
    __table_args__ = (UniqueConstraint('user_id', 'name', name='uq_user_project_name'),)
    
    # 关系
    user = relationship("User", back_populates="projects")
    content_sources = relationship("ContentSource", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("PublishingTask", back_populates="project", cascade="all, delete-orphan")
    analytics = relationship("AnalyticsHourly", back_populates="project", cascade="all, delete-orphan")

class ContentSource(Base):
    """内容源表 - 抽象化内容来源"""
    __tablename__ = 'content_sources'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    source_type = Column(String(50), nullable=False)  # local_folder, google_drive, rss_feed
    path_or_identifier = Column(Text, nullable=False)  # 路径或唯一标识符
    total_items = Column(Integer, default=0)
    used_items = Column(Integer, default=0)
    last_scanned = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 关系
    project = relationship("Project", back_populates="content_sources")
    tasks = relationship("PublishingTask", back_populates="source")

class PublishingTask(Base):
    """发布任务表 - 强化版，支持并发控制和优先级"""
    __tablename__ = 'publishing_tasks'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    source_id = Column(Integer, ForeignKey('content_sources.id'), nullable=False)
    media_path = Column(Text, nullable=False)
    content_data = Column(Text, nullable=False)  # JSON格式的内容元数据
    status = Column(String(50), nullable=False, default='pending')  # pending, locked, in_progress, success, failed, retry
    scheduled_at = Column(DateTime, nullable=False)
    priority = Column(Integer, nullable=False, default=0)  # 数字越大优先级越高
    retry_count = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)  # 乐观锁版本号
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 复合唯一约束和索引
    __table_args__ = (
        UniqueConstraint('project_id', 'media_path', name='uq_project_media'),
        Index('ix_tasks_status_scheduled_priority', 'status', 'scheduled_at', 'priority'),
        Index('ix_tasks_project_status', 'project_id', 'status'),
    )
    
    # 关系
    project = relationship("Project", back_populates="tasks")
    source = relationship("ContentSource", back_populates="tasks")
    logs = relationship("PublishingLog", back_populates="task", cascade="all, delete-orphan")
    
    def get_content_data(self):
        """获取内容数据字典"""
        if self.content_data:
            return json.loads(self.content_data)
        return {}
    
    def set_content_data(self, content_dict):
        """设置内容数据字典"""
        self.content_data = json.dumps(content_dict, ensure_ascii=False)

class PublishingLog(Base):
    """发布日志表 - 强化版，增加性能统计"""
    __tablename__ = 'publishing_logs'
    
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('publishing_tasks.id'), nullable=False)
    tweet_id = Column(String(255))
    tweet_content = Column(Text)
    published_at = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False)  # success, failed
    error_message = Column(Text)
    duration_seconds = Column(Float)  # 总耗时（秒）
    
    # 关系
    task = relationship("PublishingTask", back_populates="logs")

class AnalyticsHourly(Base):
    """小时级分析统计表 - 用于快速报表生成"""
    __tablename__ = 'analytics_hourly'
    
    id = Column(Integer, primary_key=True)
    hour_timestamp = Column(DateTime, nullable=False)  # 小时时间戳
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    successful_tasks = Column(Integer, nullable=False, default=0)
    failed_tasks = Column(Integer, nullable=False, default=0)
    total_duration_seconds = Column(Float)  # 总耗时（秒）
    
    # 唯一约束：每个项目每小时只有一条记录
    __table_args__ = (UniqueConstraint('hour_timestamp', 'project_id', name='uq_hour_project'),)
    
    # 关系
    project = relationship("Project", back_populates="analytics")