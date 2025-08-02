#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仪表板相关API路由
提供系统概览和统计信息
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text, select
from typing import Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.dependencies import get_db, get_current_user_id
from api.schemas import DashboardStats, SystemHealth, RecentActivityResponse, QuickStatsResponse, ActivityItem, QuickStatsData
from app.database.models import PublishingTask, PublishingLog, Project, ContentSource
from app.database.repository import (
    PublishingTaskRepository, PublishingLogRepository, 
    ProjectRepository, ContentSourceRepository
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取仪表板统计信息"""
    try:
        task_repo = PublishingTaskRepository(db)
        log_repo = PublishingLogRepository(db)
        project_repo = ProjectRepository(db)
        source_repo = ContentSourceRepository(db)
        
        # 获取基本统计
        total_tasks = task_repo.count_all()
        total_projects = project_repo.count_all()
        total_sources = source_repo.count_all()
        
        # 获取任务状态统计
        pending_tasks = task_repo.count_by_status('pending')
        running_tasks = task_repo.count_by_status('in_progress')
        completed_tasks = task_repo.count_by_status('success')
        failed_tasks = task_repo.count_by_status('failed')
        
        # 获取今日统计
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # 获取用户的项目ID列表
        user_project_ids = db.query(Project.id).filter(Project.user_id == user_id).subquery()
        
        today_tasks = db.query(PublishingTask).filter(
            and_(
                PublishingTask.project_id.in_(select(user_project_ids.c.id)),
                PublishingTask.created_at >= today_start,
                PublishingTask.created_at <= today_end
            )
        ).count()
        
        today_published = db.query(PublishingLog).join(PublishingTask).filter(
            and_(
                PublishingTask.project_id.in_(select(user_project_ids.c.id)),
                PublishingLog.published_at >= today_start,
                PublishingLog.published_at <= today_end,
                PublishingLog.status == 'success'
            )
        ).count()
        
        # 获取最近7天的发布统计
        week_ago = datetime.now() - timedelta(days=7)
        recent_published = db.query(PublishingLog).join(PublishingTask).filter(
            and_(
                PublishingTask.project_id.in_(select(user_project_ids.c.id)),
                PublishingLog.published_at >= week_ago,
                PublishingLog.status == 'success'
            )
        ).count()
        
        # 计算成功率
        total_logs = db.query(PublishingLog).join(PublishingTask).filter(
            PublishingTask.project_id.in_(select(user_project_ids.c.id))
        ).count()
        
        success_logs = db.query(PublishingLog).join(PublishingTask).filter(
            and_(
                PublishingTask.project_id.in_(select(user_project_ids.c.id)),
                PublishingLog.status == 'success'
            )
        ).count()
        
        success_rate = (success_logs / total_logs * 100) if total_logs > 0 else 0
        
        return DashboardStats(
            total_tasks=total_tasks,
            pending_tasks=pending_tasks,
            running_tasks=running_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            total_projects=total_projects,
            total_sources=total_sources,
            today_tasks=today_tasks,
            today_published=today_published,
            recent_published=recent_published,
            success_rate=round(success_rate, 2)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard stats: {str(e)}"
        )

@router.get("/dashboard/health", response_model=SystemHealth)
def get_system_health(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取系统健康状态"""
    try:
        import psutil
        
        # 获取系统资源使用情况
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 检查数据库连接
        db_status = "healthy"
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            db_status = "unhealthy"
        
        # 检查配置文件
        config_status = "healthy"
        try:
            from app.utils.config import get_config
            config = get_config()
            # 简化配置检查，避免复杂的依赖
            if not config.get_env('TWITTER_API_KEY'):
                config_status = "warning"
        except Exception as e:
            config_status = "unhealthy"
            logger.error(f"Config check failed: {e}")
        
        # 检查最近的任务执行情况 - 简化版本，避免复杂的数据库查询
        task_status = "healthy"
        try:
            # 简单检查是否有任务表
            result = db.execute(text("SELECT COUNT(*) FROM publishing_tasks LIMIT 1"))
            task_status = "healthy"
        except Exception:
            task_status = "warning"
        
        # 确定整体状态
        statuses = [db_status, config_status, task_status]
        if "unhealthy" in statuses:
            overall_status = "unhealthy"
        elif "warning" in statuses:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        return SystemHealth(
            status=overall_status,
            cpu_usage=cpu_usage,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            database_status=db_status,
            config_status=config_status,
            task_status=task_status,
            last_check=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system health: {str(e)}"
        )

@router.get("/dashboard/recent-activity", response_model=RecentActivityResponse)
async def get_recent_activity(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    limit: int = 10
):
    """获取最近活动记录"""
    try:
        log_repo = PublishingLogRepository(db)
        
        # 获取用户项目ID
        user_project_ids = [p.id for p in db.query(Project.id).filter(Project.user_id == user_id).all()]
        
        # 获取最近的发布日志
        recent_logs = []
        for project_id in user_project_ids:
            logs = log_repo.get_recent_logs(project_id=project_id, limit=limit)
            recent_logs.extend(logs)
        
        # 按时间排序并限制数量
        recent_logs = sorted(recent_logs, key=lambda x: x.published_at, reverse=True)[:limit]
        
        activities = []
        for log in recent_logs:
            activity = ActivityItem(
                id=log.id,
                type="publish",
                status=log.status,
                message=log.error_message or f"Task {log.task_id} {log.status}",
                created_at=log.published_at,
                task_id=log.task_id
            )
            activities.append(activity)
        
        return RecentActivityResponse(
            success=True,
            activities=activities,
            total=len(activities)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recent activity: {str(e)}"
        )

@router.get("/dashboard/quick-stats", response_model=QuickStatsResponse)
async def get_quick_stats(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取快速统计信息（用于实时更新）"""
    try:
        # 获取用户项目ID
        user_project_ids = db.query(Project.id).filter(Project.user_id == user_id).subquery()
        
        # 获取当前运行的任务数
        running_tasks = db.query(PublishingTask).filter(
            and_(
                PublishingTask.project_id.in_(select(user_project_ids.c.id)),
                PublishingTask.status == 'in_progress'
            )
        ).count()
        
        # 获取待处理任务数
        pending_tasks = db.query(PublishingTask).filter(
            and_(
                PublishingTask.project_id.in_(select(user_project_ids.c.id)),
                PublishingTask.status == 'pending'
            )
        ).count()
        
        # 获取今日发布数
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        today_published = db.query(PublishingLog).join(PublishingTask).filter(
            and_(
                PublishingTask.project_id.in_(select(user_project_ids.c.id)),
                PublishingLog.published_at >= today_start,
                PublishingLog.published_at <= today_end,
                PublishingLog.status == 'success'
            )
        ).count()
        
        stats_data = QuickStatsData(
            running_tasks=running_tasks,
            pending_tasks=pending_tasks,
            today_published=today_published,
            last_updated=datetime.now()
        )
        
        return QuickStatsResponse(
            success=True,
            stats=stats_data
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get quick stats: {str(e)}"
        )

@router.get("/analytics/overview")
async def get_analytics_overview(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    time_range: str = Query("7d", description="时间范围: 1d, 7d, 30d, 90d, 1y"),
    project_id: Optional[int] = Query(None, description="项目ID")
):
    """获取分析概览数据"""
    try:
        # 模拟数据，实际应该从数据库查询
        return {
            "success": True,
            "data": {
                "total_tasks": 150,
                "success_rate": 95.5,
                "avg_execution_time": 45.2,
                "error_rate": 4.5,
                "tasks_change": 12.5,
                "success_rate_change": 2.1,
                "execution_time_change": -5.3,
                "error_rate_change": -1.2
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics overview: {str(e)}"
        )

@router.get("/analytics/trends")
async def get_analytics_trends(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    time_range: str = Query("7d", description="时间范围"),
    granularity: str = Query("day", description="时间粒度: hour, day, week, month"),
    project_id: Optional[int] = Query(None, description="项目ID")
):
    """获取分析趋势数据"""
    try:
        # 模拟趋势数据
        import random
        from datetime import datetime, timedelta
        
        # 生成时间标签
        now = datetime.now()
        if granularity == "hour":
            labels = [(now - timedelta(hours=i)).strftime("%H:%M") for i in range(24, 0, -1)]
        else:
            labels = [(now - timedelta(days=i)).strftime("%m-%d") for i in range(7, 0, -1)]
        
        # 生成模拟数据
        successful_tasks = [random.randint(5, 25) for _ in labels]
        failed_tasks = [random.randint(0, 3) for _ in labels]
        total_tasks = [s + f for s, f in zip(successful_tasks, failed_tasks)]
        
        return {
            "success": True,
            "data": {
                "labels": labels,
                "successful_tasks": successful_tasks,
                "failed_tasks": failed_tasks,
                "total_tasks": total_tasks
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics trends: {str(e)}"
        )

@router.get("/analytics/performance")
async def get_analytics_performance(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    time_range: str = Query("7d", description="时间范围"),
    project_id: Optional[int] = Query(None, description="项目ID")
):
    """获取性能分析数据"""
    try:
        # 模拟性能数据
        import random
        
        return {
            "success": True,
            "data": {
                "avg_response_time": round(random.uniform(200, 800), 2),
                "max_response_time": round(random.uniform(800, 1500), 2),
                "min_response_time": round(random.uniform(50, 200), 2),
                "throughput": round(random.uniform(10, 50), 2),
                "error_rate": round(random.uniform(1, 8), 2),
                "cpu_usage": round(random.uniform(20, 80), 2),
                "memory_usage": round(random.uniform(30, 70), 2),
                "disk_usage": round(random.uniform(40, 85), 2)
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics performance: {str(e)}"
        )


@router.get("/system/config")
async def get_system_config(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取系统配置"""
    try:
        # 返回默认的系统配置
        return {
            "success": True,
            "data": {
                "general": {
                    "system_name": "Twitter 自动发布系统",
                    "system_description": "智能化的Twitter内容发布和管理平台",
                    "default_language": "zh-CN",
                    "timezone": "Asia/Shanghai",
                    "date_format": "YYYY-MM-DD",
                    "enable_dark_mode": False
                },
                "scheduler": {
                    "max_concurrent_tasks": 10,
                    "task_timeout": 300,
                    "retry_attempts": 3,
                    "retry_delay": 60,
                    "enable_scheduler": True,
                    "auto_cleanup": True,
                    "cleanup_days": 30
                },
                "notifications": {
                    "enable_notifications": True,
                    "smtp_server": "",
                    "smtp_port": 587,
                    "smtp_username": "",
                    "smtp_password": "",
                    "email_from": "",
                    "enable_email_alerts": False,
                    "enable_webhook_alerts": False,
                    "webhook_url": ""
                },
                "security": {
                    "enable_api_rate_limit": True,
                    "api_rate_limit": 120,
                    "enable_request_logging": True,
                    "log_retention_days": 90,
                    "enable_audit_log": True
                },
                "advanced": {
                    "enable_debug_mode": False,
                    "log_level": "INFO",
                    "database_pool_size": 10,
                    "cache_ttl": 3600,
                    "enable_performance_monitoring": True
                }
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system config: {str(e)}"
        )