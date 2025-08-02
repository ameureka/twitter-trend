#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API数据模型定义
使用Pydantic定义请求和响应的数据结构
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union, Generic, TypeVar
from enum import Enum

from pydantic import BaseModel, Field, validator

# 泛型类型变量
T = TypeVar('T')

# 枚举类型定义
class TaskStatusEnum(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ContentTypeEnum(str, Enum):
    """内容类型枚举"""
    VIDEO = "video"
    IMAGE = "image"
    TEXT = "text"

class LogLevelEnum(str, Enum):
    """日志级别枚举"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

# 基础响应模型
class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class ErrorResponse(BaseResponse):
    """错误响应模型"""
    success: bool = False
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

# 分页模型
class PaginationInfo(BaseModel):
    """分页信息"""
    total_items: int
    total_pages: int
    current_page: int
    per_page: int
    has_next: bool
    has_prev: bool

class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应基类"""
    pagination: PaginationInfo
    data: List[T]

# 认证相关模型
class APIKeyRequest(BaseModel):
    """API密钥请求"""
    name: str = Field(..., description="API密钥名称")
    description: Optional[str] = Field(None, description="API密钥描述")

class APIKeyResponse(BaseModel):
    """API密钥响应"""
    id: int
    name: str
    key: str
    description: Optional[str]
    created_at: datetime
    is_active: bool

# 仪表盘相关模型
class DashboardStats(BaseModel):
    """仪表盘统计数据"""
    total_tasks: int = Field(..., description="总任务数")
    pending_tasks: int = Field(..., description="待处理任务数")
    running_tasks: int = Field(..., description="运行中任务数")
    completed_tasks: int = Field(..., description="已完成任务数")
    failed_tasks: int = Field(..., description="失败任务数")
    total_projects: int = Field(..., description="项目总数")
    total_sources: int = Field(..., description="内容源总数")
    today_tasks: int = Field(..., description="今日任务数")
    today_published: int = Field(..., description="今日发布数")
    recent_published: int = Field(..., description="最近发布数")
    success_rate: float = Field(..., description="成功率")
    
class HourlyActivity(BaseModel):
    """每小时活动数据"""
    hour: datetime = Field(..., description="小时时间戳")
    successful: int = Field(..., description="成功任务数")
    failed: int = Field(..., description="失败任务数")
    total: int = Field(..., description="总任务数")

class DashboardResponse(BaseResponse):
    """仪表盘响应"""
    stats: DashboardStats
    hourly_activity: List[HourlyActivity]

class ActivityItem(BaseModel):
    """活动项目"""
    id: int
    type: str
    status: str
    message: str
    created_at: datetime
    task_id: Optional[int] = None

class RecentActivityResponse(BaseModel):
    """最近活动响应"""
    success: bool = True
    activities: List[ActivityItem]
    total: int

class QuickStatsData(BaseModel):
    """快速统计数据"""
    running_tasks: int
    pending_tasks: int
    today_published: int
    last_updated: datetime

class QuickStatsResponse(BaseModel):
    """快速统计响应"""
    success: bool = True
    stats: QuickStatsData

# 任务相关模型
class TaskBase(BaseModel):
    """任务基础模型"""
    media_file: str = Field(..., description="媒体文件路径")
    metadata_file: str = Field(..., description="元数据文件路径")
    language: str = Field(..., description="语言代码")
    priority: int = Field(0, description="优先级")
    scheduled_time: Optional[datetime] = Field(None, description="计划执行时间")

class Task(BaseModel):
    """任务详细信息"""
    id: int
    project_id: int
    content_source_id: Optional[int] = None
    content_type: str
    content_data: Optional[Dict[str, Any]] = None
    scheduled_time: Optional[datetime] = None
    status: TaskStatusEnum
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    project_name: Optional[str] = None
    source_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class TaskCreate(BaseModel):
    """创建任务请求"""
    project_id: int
    content_source_id: Optional[int] = None
    content_type: str
    content_data: Optional[Dict[str, Any]] = None
    scheduled_time: Optional[datetime] = None
    max_retries: int = 3

class TaskUpdate(BaseModel):
    """更新任务请求"""
    status: Optional[TaskStatusEnum] = None
    priority: Optional[int] = None
    scheduled_time: Optional[datetime] = None
    error_message: Optional[str] = None

class BulkTaskAction(BaseModel):
    """批量任务操作"""
    task_ids: List[int]
    action: str  # 'cancel', 'retry', 'delete'
    reason: Optional[str] = None

class TaskListResponse(PaginatedResponse[Task]):
    """任务列表响应"""
    pass

class TaskResponse(BaseResponse):
    """单个任务响应"""
    task: Task

# 项目相关模型
class ProjectBase(BaseModel):
    """项目基础模型"""
    name: str = Field(..., description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    base_path: str = Field(..., description="项目基础路径")
    default_language: str = Field("en", description="默认语言")
    is_active: bool = Field(True, description="是否激活")

class Project(ProjectBase):
    """项目详细信息"""
    id: int
    user_id: int
    source_count: int = Field(..., description="内容源数量")
    total_tasks: int = Field(..., description="总任务数")
    pending_tasks: int = Field(..., description="待处理任务数")
    success_tasks: int = Field(..., description="成功任务数")
    failed_tasks: int = Field(..., description="失败任务数")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ProjectCreate(ProjectBase):
    """创建项目请求"""
    pass

class ProjectUpdate(BaseModel):
    """更新项目请求"""
    description: Optional[str] = None
    default_language: Optional[str] = None
    is_active: Optional[bool] = None

class ProjectSettings(BaseModel):
    """项目设置"""
    project_id: int
    ai_enhancement_enabled: bool = True
    publishing_interval_min: int = 15
    publishing_interval_max: int = 30
    target_languages: List[str] = ["en"]
    auto_hashtags: List[str] = []
    content_templates: Dict[str, str] = {}

class ProjectListResponse(PaginatedResponse[Project]):
    """项目列表响应"""
    pass

class ProjectResponse(BaseResponse):
    """单个项目响应"""
    project: Project

# 内容源相关模型
class ContentSourceBase(BaseModel):
    """内容源基础模型"""
    content_type: ContentTypeEnum
    source_path: str = Field(..., description="源文件路径")
    metadata_path: str = Field(..., description="元数据路径")
    config: Dict[str, Any] = Field(default_factory=dict, description="配置信息")
    is_active: bool = Field(True, description="是否激活")

class ContentSource(ContentSourceBase):
    """内容源详细信息"""
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ContentSourceCreate(ContentSourceBase):
    """创建内容源请求"""
    project_id: int

class ContentSourceUpdate(BaseModel):
    """更新内容源请求"""
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

# 日志相关模型
class PublishingLogBase(BaseModel):
    """发布日志基础模型"""
    level: LogLevelEnum
    message: str
    details: Optional[Dict[str, Any]] = None

class PublishingLog(PublishingLogBase):
    """发布日志详细信息"""
    id: int
    task_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class LogListResponse(PaginatedResponse):
    """日志列表响应"""
    logs: List[PublishingLog]

# 分析数据相关模型
class AnalyticsBase(BaseModel):
    """分析数据基础模型"""
    event_type: str
    metrics: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

class Analytics(AnalyticsBase):
    """分析数据详细信息"""
    id: int
    task_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class AnalyticsResponse(BaseResponse):
    """分析数据响应"""
    analytics: List[Analytics]

# 系统状态相关模型
class SystemHealth(BaseModel):
    """系统健康状态"""
    status: str = Field(..., description="系统状态")
    cpu_usage: float = Field(..., description="CPU使用率（%）")
    memory_usage: float = Field(..., description="内存使用率（%）")
    disk_usage: float = Field(..., description="磁盘使用率（%）")
    database_status: str = Field(..., description="数据库状态")
    config_status: str = Field(..., description="配置状态")
    task_status: str = Field(..., description="任务状态")
    last_check: datetime = Field(..., description="最后检查时间")

class SystemHealthResponse(BaseResponse):
    """系统健康响应"""
    health: SystemHealth

# 批量操作模型
class BulkTaskAction(BaseModel):
    """批量任务操作"""
    task_ids: List[int] = Field(..., description="任务ID列表")
    action: str = Field(..., description="操作类型")
    
    @validator('action')
    def validate_action(cls, v):
        allowed_actions = ['cancel', 'retry', 'delete', 'reset']
        if v not in allowed_actions:
            raise ValueError(f'Action must be one of: {allowed_actions}')
        return v

class BulkActionResponse(BaseResponse):
    """批量操作响应"""
    affected_count: int = Field(..., description="受影响的记录数")
    failed_ids: List[int] = Field(default_factory=list, description="操作失败的ID列表")