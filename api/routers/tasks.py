#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务管理相关API路由
处理发布任务的CRUD操作
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.dependencies import get_db, get_current_user_id, get_pagination_params
from api.schemas import (
    BaseResponse, PaginatedResponse, TaskCreate, TaskUpdate, 
    Task, TaskStatusEnum, BulkTaskAction, PaginationInfo
)
from app.database.repository import PublishingTaskRepository, PublishingLogRepository
from app.core.task_scheduler import TaskScheduler

router = APIRouter()

@router.get("/stats", response_model=Dict[str, Any])
async def get_task_stats(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    days: int = Query(30, description="Number of days for statistics")
):
    """获取任务统计信息"""
    try:
        task_repo = PublishingTaskRepository(db)
        
        # 获取用户的任务统计
        stats = task_repo.get_user_stats(user_id)
        
        return {
            "success": True,
            "stats": stats,
            "period_days": days
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task stats: {str(e)}"
        )

@router.get("/", response_model=PaginatedResponse[Task])
async def list_tasks(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    pagination: Dict[str, int] = Depends(get_pagination_params),
    status_filter: Optional[str] = Query(None, description="Filter by task status"),
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    content_type: Optional[str] = Query(None, description="Filter by content type")
):
    """获取任务列表"""
    try:
        task_repo = PublishingTaskRepository(db)
        
        # 构建过滤条件
        filters = {}
        if status_filter:
            filters['status'] = status_filter
        if project_id:
            filters['project_id'] = project_id
        if content_type:
            filters['content_type'] = content_type
        
        # 获取任务列表
        tasks, total = task_repo.get_paginated(
            user_id=user_id,
            page=pagination['page'],
            page_size=pagination['per_page'],
            filters=filters
        )
        
        # 转换为响应格式
        task_details = []
        for task in tasks:
            task_detail = Task(
                id=task.id,
                project_id=task.project_id,
                content_source_id=task.source_id,
                content_type="video",  # 默认类型
                content_data=task.get_content_data(),
                scheduled_time=task.scheduled_at,
                status=task.status,
                retry_count=task.retry_count,
                max_retries=3,  # 默认值
                error_message=None,
                created_at=task.created_at,
                updated_at=task.updated_at,
                project_name=task.project.name if task.project else None,
                source_name=task.source.path_or_identifier if task.source else None
            )
            task_details.append(task_detail)
        
        pagination_info = PaginationInfo(
            total_items=total,
            total_pages=(total + pagination['per_page'] - 1) // pagination['per_page'],
            current_page=pagination['page'],
            per_page=pagination['per_page'],
            has_next=pagination['page'] < (total + pagination['per_page'] - 1) // pagination['per_page'],
            has_prev=pagination['page'] > 1
        )
        
        return PaginatedResponse[Task](
            pagination=pagination_info,
            data=task_details
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}"
        )

@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取单个任务详情"""
    try:
        task_repo = PublishingTaskRepository(db)
        task = task_repo.get_by_id(task_id)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        return Task(
            id=task.id,
            project_id=task.project_id,
            content_source_id=task.source_id,
            content_type="video",  # 默认类型
            content_data=task.get_content_data(),
            scheduled_time=task.scheduled_at,
            status=task.status,
            retry_count=task.retry_count,
            max_retries=3,  # 默认值
            error_message=None,
            created_at=task.created_at,
            updated_at=task.updated_at,
            project_name=task.project.name if task.project else None,
            source_name=task.source.path_or_identifier if task.source else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task: {str(e)}"
        )

@router.post("/", response_model=Task)
async def create_task(
    task_data: TaskCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """创建新任务"""
    try:
        task_repo = PublishingTaskRepository(db)
        
        # 创建任务
        task = task_repo.create({
            'project_id': task_data.project_id,
            'source_id': task_data.content_source_id,
            'media_path': '/tmp/test.mp4',  # 临时路径
            'content_data': task_data.content_data or {},
            'scheduled_at': task_data.scheduled_time,
        })
        
        return Task(
            id=task.id,
            project_id=task.project_id,
            content_source_id=task.source_id,
            content_type="video",
            content_data=task.get_content_data(),
            scheduled_time=task.scheduled_at,
            status=task.status,
            retry_count=task.retry_count,
            max_retries=3,
            error_message=None,
            created_at=task.created_at,
            updated_at=task.updated_at,
            project_name=task.project.name if task.project else None,
            source_name=task.content_source.name if task.content_source else None
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )

@router.put("/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """更新任务"""
    try:
        task_repo = PublishingTaskRepository(db)
        
        # 检查任务是否存在
        existing_task = task_repo.get_by_id(task_id)
        if not existing_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        # 准备更新数据
        update_data = {}
        if task_data.content_data is not None:
            update_data['content_data'] = task_data.content_data
        if task_data.scheduled_time is not None:
            update_data['scheduled_time'] = task_data.scheduled_time
        if task_data.max_retries is not None:
            update_data['max_retries'] = task_data.max_retries
        if task_data.status is not None:
            update_data['status'] = task_data.status
        
        # 更新任务
        task = task_repo.update(task_id, update_data)
        
        return Task(
            id=task.id,
            project_id=task.project_id,
            content_source_id=task.content_source_id,
            content_type=task.content_type,
            content_data=task.content_data,
            scheduled_time=task.scheduled_time,
            status=task.status,
            retry_count=task.retry_count,
            max_retries=task.max_retries,
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at,
            project_name=task.project.name if task.project else None,
            source_name=task.content_source.name if task.content_source else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update task: {str(e)}"
        )

@router.delete("/{task_id}", response_model=BaseResponse)
async def delete_task(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """删除任务"""
    try:
        task_repo = PublishingTaskRepository(db)
        
        # 检查任务是否存在
        existing_task = task_repo.get_by_id(task_id)
        if not existing_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        # 检查任务状态，运行中的任务不能删除
        if existing_task.status == 'in_progress':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete running task"
            )
        
        # 删除任务
        task_repo.delete(task_id)
        
        return BaseResponse(
            success=True,
            message="Task deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete task: {str(e)}"
        )

@router.post("/{task_id}/execute", response_model=BaseResponse)
async def execute_task(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """立即执行任务"""
    try:
        task_repo = PublishingTaskRepository(db)
        
        # 检查任务是否存在
        task = task_repo.get_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        # 检查任务状态
        if task.status not in ['pending', 'failed']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot execute task with status: {task.status}"
            )
        
        # 使用任务调度器执行任务
        scheduler = TaskScheduler(db, user_id)
        success = scheduler.execute_task(task_id)
        
        if success:
            return BaseResponse(
                success=True,
                message="Task execution started"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to start task execution"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute task: {str(e)}"
        )

@router.post("/{task_id}/cancel", response_model=BaseResponse)
async def cancel_task(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """取消任务"""
    try:
        task_repo = PublishingTaskRepository(db)
        
        # 检查任务是否存在
        task = task_repo.get_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        # 检查任务状态
        if task.status not in ['pending', 'in_progress']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel task with status: {task.status}"
            )
        
        # 更新任务状态为已取消
        task_repo.update(task_id, {'status': 'cancelled'})
        
        return BaseResponse(
            success=True,
            message="Task cancelled successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}"
        )

@router.post("/bulk", response_model=BaseResponse)
async def bulk_task_action(
    action_data: BulkTaskAction,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """批量操作任务"""
    try:
        task_repo = PublishingTaskRepository(db, user_id)
        
        success_count = 0
        error_count = 0
        errors = []
        
        for task_id in action_data.task_ids:
            try:
                task = task_repo.get_by_id(task_id)
                if not task:
                    errors.append(f"Task {task_id} not found")
                    error_count += 1
                    continue
                
                if action_data.action == "delete":
                    if task.status == 'in_progress':
                        errors.append(f"Cannot delete running task {task_id}")
                        error_count += 1
                        continue
                    task_repo.delete(task_id)
                    
                elif action_data.action == "cancel":
                    if task.status not in ['pending', 'in_progress']:
                        errors.append(f"Cannot cancel task {task_id} with status {task.status}")
                        error_count += 1
                        continue
                    task_repo.update(task_id, {'status': 'cancelled'})
                    
                elif action_data.action == "execute":
                    if task.status not in ['pending', 'failed']:
                        errors.append(f"Cannot execute task {task_id} with status {task.status}")
                        error_count += 1
                        continue
                    scheduler = TaskScheduler(db, user_id)
                    scheduler.execute_task(task_id)
                
                success_count += 1
                
            except Exception as e:
                errors.append(f"Error processing task {task_id}: {str(e)}")
                error_count += 1
        
        message = f"Bulk action completed. Success: {success_count}, Errors: {error_count}"
        if errors:
            message += f". Errors: {'; '.join(errors[:5])}"  # 只显示前5个错误
        
        return BaseResponse(
            success=success_count > 0,
            message=message
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform bulk action: {str(e)}"
        )

@router.get("/{task_id}/logs", response_model=Dict[str, Any])
async def get_task_logs(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    limit: int = Query(50, description="Number of logs to return")
):
    """获取任务执行日志"""
    try:
        log_repo = PublishingLogRepository(db, user_id)
        
        # 获取任务相关的日志
        logs = log_repo.get_by_task_id(task_id, limit=limit)
        
        log_data = []
        for log in logs:
            log_data.append({
                "id": log.id,
                "level": log.level,
                "message": log.message,
                "status": log.status,
                "created_at": log.created_at,
                "metadata": log.metadata
            })
        
        return {
            "success": True,
            "logs": log_data,
            "total": len(log_data)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task logs: {str(e)}"
        )