#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志管理相关API路由
处理系统日志、任务日志和错误日志的查询和管理
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.dependencies import get_db, get_current_user_id, get_pagination_params
from api.schemas import BaseResponse, PaginatedResponse, PaginationInfo
from app.database.repository import PublishingLogRepository
from app.database.models import PublishingLog, PublishingTask
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class LogEntry:
    """日志条目模型"""
    def __init__(self, timestamp: datetime, level: str, message: str, 
                 source: str = None, task_id: int = None, details: Dict = None):
        self.timestamp = timestamp
        self.level = level
        self.message = message
        self.source = source or 'system'
        self.task_id = task_id
        self.details = details or {}

    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'message': self.message,
            'source': self.source,
            'task_id': self.task_id,
            'details': self.details
        }


@router.get("/system", summary="获取系统日志")
async def get_system_logs(
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量"),
    level: Optional[str] = Query(None, description="日志级别过滤"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    获取系统日志
    """
    try:
        # 模拟系统日志数据（实际项目中应该从日志文件或数据库读取）
        logs = []
        
        # 生成一些示例系统日志
        base_time = datetime.now()
        for i in range(50):
            log_time = base_time - timedelta(minutes=i * 5)
            
            if i % 10 == 0:
                level = 'ERROR'
                message = f'系统错误: 数据库连接失败'
            elif i % 5 == 0:
                level = 'WARNING'
                message = f'系统警告: API调用超时'
            else:
                level = 'INFO'
                message = f'系统信息: 定时任务执行完成'
            
            log_entry = LogEntry(
                timestamp=log_time,
                level=level,
                message=message,
                source='system',
                details={'component': 'scheduler', 'duration': f'{i*10}ms'}
            )
            logs.append(log_entry)
        
        # 应用过滤条件
        if level:
            logs = [log for log in logs if log.level.lower() == level.lower()]
        
        if start_time:
            logs = [log for log in logs if log.timestamp >= start_time]
        
        if end_time:
            logs = [log for log in logs if log.timestamp <= end_time]
        
        if search:
            logs = [log for log in logs if search.lower() in log.message.lower()]
        
        # 分页
        total = len(logs)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_logs = logs[start_idx:end_idx]
        
        return PaginatedResponse(
            success=True,
            data={
                'items': [log.to_dict() for log in paginated_logs],
                'pagination': PaginationInfo(
                    page=page,
                    per_page=per_page,
                    total=total,
                    pages=(total + per_page - 1) // per_page
                ).dict()
            },
            message="系统日志获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取系统日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统日志失败: {str(e)}"
        )


@router.get("/tasks", summary="获取任务日志")
async def get_task_logs(
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量"),
    task_id: Optional[int] = Query(None, description="任务ID过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    获取任务日志
    """
    try:
        log_repo = PublishingLogRepository(db)
        
        # 构建查询条件
        filters = []
        if task_id:
            filters.append(PublishingLog.task_id == task_id)
        if status:
            filters.append(PublishingLog.status == status)
        if start_time:
            filters.append(PublishingLog.created_at >= start_time)
        if end_time:
            filters.append(PublishingLog.created_at <= end_time)
        if search:
            filters.append(PublishingLog.message.contains(search))
        
        # 获取日志数据
        query = db.query(PublishingLog).join(PublishingTask)
        if filters:
            query = query.filter(and_(*filters))
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        logs = query.order_by(desc(PublishingLog.created_at)).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        # 转换为字典格式
        log_items = []
        for log in logs:
            log_items.append({
                'id': log.id,
                'task_id': log.task_id,
                'user_id': log.user_id,
                'status': log.status,
                'message': log.message,
                'published_at': log.published_at.isoformat() if log.published_at else None,
                'created_at': log.created_at.isoformat(),
                'task_title': log.task.title if log.task else None
            })
        
        return PaginatedResponse(
            success=True,
            data={
                'items': log_items,
                'pagination': PaginationInfo(
                    page=page,
                    per_page=per_page,
                    total=total,
                    pages=(total + per_page - 1) // per_page
                ).dict()
            },
            message="任务日志获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取任务日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务日志失败: {str(e)}"
        )


@router.get("/errors", summary="获取错误日志")
async def get_error_logs(
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量"),
    severity: Optional[str] = Query(None, description="严重程度过滤"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    获取错误日志
    """
    try:
        # 模拟错误日志数据
        logs = []
        
        # 生成一些示例错误日志
        base_time = datetime.now()
        for i in range(30):
            log_time = base_time - timedelta(hours=i)
            
            if i % 3 == 0:
                severity = 'CRITICAL'
                message = f'严重错误: 发布任务失败 - Twitter API限制'
            elif i % 2 == 0:
                severity = 'ERROR'
                message = f'错误: 内容源解析失败'
            else:
                severity = 'WARNING'
                message = f'警告: 网络连接不稳定'
            
            log_entry = LogEntry(
                timestamp=log_time,
                level=severity,
                message=message,
                source='error_handler',
                task_id=i + 1 if i % 4 == 0 else None,
                details={
                    'error_code': f'E{1000 + i}',
                    'stack_trace': f'File "main.py", line {100 + i}',
                    'user_agent': 'TwitterBot/1.0'
                }
            )
            logs.append(log_entry)
        
        # 应用过滤条件
        if severity:
            logs = [log for log in logs if log.level.lower() == severity.lower()]
        
        if start_time:
            logs = [log for log in logs if log.timestamp >= start_time]
        
        if end_time:
            logs = [log for log in logs if log.timestamp <= end_time]
        
        if search:
            logs = [log for log in logs if search.lower() in log.message.lower()]
        
        # 分页
        total = len(logs)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_logs = logs[start_idx:end_idx]
        
        return PaginatedResponse(
            success=True,
            data={
                'items': [log.to_dict() for log in paginated_logs],
                'pagination': PaginationInfo(
                    page=page,
                    per_page=per_page,
                    total=total,
                    pages=(total + per_page - 1) // per_page
                ).dict()
            },
            message="错误日志获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取错误日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取错误日志失败: {str(e)}"
        )


@router.post("/clear", summary="清空日志")
async def clear_logs(
    log_type: str = Query(..., description="日志类型: system, tasks, errors"),
    before_date: Optional[datetime] = Query(None, description="清空此日期之前的日志"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    清空指定类型的日志
    """
    try:
        if log_type == 'tasks':
            # 清空任务日志
            query = db.query(PublishingLog)
            if before_date:
                query = query.filter(PublishingLog.created_at < before_date)
            
            deleted_count = query.count()
            query.delete(synchronize_session=False)
            db.commit()
            
            message = f"已清空 {deleted_count} 条任务日志"
        else:
            # 对于系统日志和错误日志，这里只是模拟操作
            # 实际项目中应该清理相应的日志文件或数据库记录
            message = f"已清空 {log_type} 日志"
        
        logger.info(f"用户 {current_user_id} 清空了 {log_type} 日志")
        
        return BaseResponse(
            success=True,
            message=message
        )
        
    except Exception as e:
        logger.error(f"清空日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清空日志失败: {str(e)}"
        )


@router.get("/export", summary="导出日志")
async def export_logs(
    log_type: str = Query(..., description="日志类型: system, tasks, errors"),
    format: str = Query('csv', description="导出格式: csv, json"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    导出日志文件
    """
    try:
        import csv
        import json
        from io import StringIO
        
        # 获取日志数据（这里简化处理，实际应该调用相应的获取函数）
        if log_type == 'tasks':
            query = db.query(PublishingLog).join(PublishingTask)
            if start_time:
                query = query.filter(PublishingLog.created_at >= start_time)
            if end_time:
                query = query.filter(PublishingLog.created_at <= end_time)
            
            logs = query.order_by(desc(PublishingLog.created_at)).all()
            
            log_data = []
            for log in logs:
                log_data.append({
                    'id': log.id,
                    'task_id': log.task_id,
                    'status': log.status,
                    'message': log.message,
                    'published_at': log.published_at.isoformat() if log.published_at else '',
                    'created_at': log.created_at.isoformat(),
                    'task_title': log.task.title if log.task else ''
                })
        else:
            # 模拟其他类型的日志数据
            log_data = [{
                'timestamp': datetime.now().isoformat(),
                'level': 'INFO',
                'message': f'示例{log_type}日志',
                'source': log_type
            }]
        
        # 生成文件内容
        if format.lower() == 'csv':
            output = StringIO()
            if log_data:
                writer = csv.DictWriter(output, fieldnames=log_data[0].keys())
                writer.writeheader()
                writer.writerows(log_data)
            
            content = output.getvalue()
            media_type = 'text/csv'
            filename = f'{log_type}_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        else:
            content = json.dumps(log_data, ensure_ascii=False, indent=2)
            media_type = 'application/json'
            filename = f'{log_type}_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        # 返回文件流
        def generate():
            yield content.encode('utf-8')
        
        return StreamingResponse(
            generate(),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"导出日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出日志失败: {str(e)}"
        )


@router.get("/stats", summary="获取日志统计")
async def get_log_stats(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    获取日志统计信息
    """
    try:
        # 获取任务日志统计
        task_log_count = db.query(PublishingLog).count()
        
        # 按状态统计任务日志
        status_stats = db.query(
            PublishingLog.status,
            db.func.count(PublishingLog.id).label('count')
        ).group_by(PublishingLog.status).all()
        
        status_counts = {stat.status: stat.count for stat in status_stats}
        
        # 最近24小时的日志统计
        last_24h = datetime.now() - timedelta(hours=24)
        recent_logs = db.query(PublishingLog).filter(
            PublishingLog.created_at >= last_24h
        ).count()
        
        return BaseResponse(
            success=True,
            data={
                'total_logs': {
                    'system': 150,  # 模拟数据
                    'tasks': task_log_count,
                    'errors': 25    # 模拟数据
                },
                'status_distribution': status_counts,
                'recent_activity': {
                    'last_24h': recent_logs,
                    'last_hour': max(0, recent_logs // 24)
                },
                'log_levels': {
                    'INFO': 120,
                    'WARNING': 25,
                    'ERROR': 15,
                    'CRITICAL': 3
                }
            },
            message="日志统计获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取日志统计失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取日志统计失败: {str(e)}"
        )