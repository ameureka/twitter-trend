#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目管理相关API路由
处理项目的CRUD操作和设置管理
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
    BaseResponse, PaginatedResponse, ProjectCreate, ProjectUpdate, 
    Project, ProjectSettings, ContentSourceCreate, ContentSource, PaginationInfo
)
from app.database.repository import (
    ProjectRepository, ContentSourceRepository, PublishingTaskRepository
)

router = APIRouter()

@router.get("/projects/stats", response_model=Dict[str, Any])
async def get_project_stats(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    days: int = Query(30, description="Number of days for statistics")
):
    """获取项目统计信息"""
    try:
        project_repo = ProjectRepository(db)
        task_repo = PublishingTaskRepository(db)
        
        # 获取用户的所有项目
        projects = project_repo.list_user_projects(user_id)
        
        project_stats = []
        total_projects = len(projects)
        total_tasks = 0
        total_completed = 0
        total_failed = 0
        
        for project in projects:
            # 获取每个项目的统计
            project_task_stats = task_repo.get_project_stats(project.id)
            project_total = sum(project_task_stats.values())
            project_completed = project_task_stats.get('success', 0)
            project_failed = project_task_stats.get('failed', 0)
            
            total_tasks += project_total
            total_completed += project_completed
            total_failed += project_failed
            
            project_stats.append({
                "id": project.id,
                "name": project.name,
                "total_tasks": project_total,
                "completed_tasks": project_completed,
                "failed_tasks": project_failed,
                "success_rate": round((project_completed / project_total * 100) if project_total > 0 else 0, 2)
            })
        
        overall_success_rate = round((total_completed / total_tasks * 100) if total_tasks > 0 else 0, 2)
        
        return {
            "success": True,
            "stats": {
                "total_projects": total_projects,
                "total_tasks": total_tasks,
                "completed_tasks": total_completed,
                "failed_tasks": total_failed,
                "overall_success_rate": overall_success_rate,
                "project_breakdown": project_stats
            },
            "period_days": days
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project stats: {str(e)}"
        )

@router.get("/projects", response_model=PaginatedResponse[Project])
async def list_projects(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    pagination: Dict[str, int] = Depends(get_pagination_params),
    is_active: Optional[bool] = Query(None, description="Filter by active status")
):
    """获取项目列表"""
    try:
        project_repo = ProjectRepository(db)
        
        # 构建过滤条件
        filters = {}
        if is_active is not None:
            filters['is_active'] = is_active
        
        # 获取项目列表
        projects, total = project_repo.get_paginated(
            user_id=user_id,
            page=pagination['page'],
            page_size=pagination['per_page'],
            filters=filters
        )
        
        # 转换为响应格式
        project_details = []
        for project in projects:
            # 获取项目统计信息
            task_repo = PublishingTaskRepository(db)
            total_tasks = task_repo.count_by_project(project.id)
            active_tasks = task_repo.count_by_project_and_status(project.id, 'in_progress')
            
            project_detail = Project(
                id=project.id,
                user_id=project.user_id,
                name=project.name,
                description=project.description,
                base_path="",  # 使用默认值，因为数据库模型中没有此字段
                default_language="en",  # 使用默认值，因为数据库模型中没有此字段
                is_active=project.status == 'active',  # 使用status字段判断是否活跃
                source_count=len(project.content_sources) if project.content_sources else 0,
                total_tasks=total_tasks,
                pending_tasks=0,
                success_tasks=0,
                failed_tasks=0,
                created_at=project.created_at,
                updated_at=project.updated_at
            )
            project_details.append(project_detail)
        
        pagination_info = PaginationInfo(
            total_items=total,
            total_pages=(total + pagination['per_page'] - 1) // pagination['per_page'],
            current_page=pagination['page'],
            per_page=pagination['per_page'],
            has_next=pagination['page'] < (total + pagination['per_page'] - 1) // pagination['per_page'],
            has_prev=pagination['page'] > 1
        )
        
        return PaginatedResponse[Project](
            pagination=pagination_info,
            data=project_details
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list projects: {str(e)}"
        )

@router.get("/projects/{project_id}", response_model=Project)
async def get_project(
    project_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取单个项目详情"""
    try:
        project_repo = ProjectRepository(db)
        project = project_repo.get_project_by_id(project_id)
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # 获取项目统计信息
        task_repo = PublishingTaskRepository(db)
        total_tasks = task_repo.count_by_project(project.id)
        active_tasks = task_repo.count_by_project_and_status(project.id, 'in_progress')
        
        return Project(
            id=project.id,
            user_id=project.user_id,
            name=project.name,
            description=project.description,
            base_path="",  # 使用默认值，因为数据库模型中没有此字段
            default_language="en",  # 使用默认值，因为数据库模型中没有此字段
            is_active=project.status == 'active',  # 使用status字段判断是否活跃
            source_count=len(project.content_sources) if project.content_sources else 0,
            total_tasks=total_tasks,
            pending_tasks=0,
            success_tasks=0,
            failed_tasks=0,
            created_at=project.created_at,
            updated_at=project.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project: {str(e)}"
        )

@router.post("/projects", response_model=Project)
async def create_project(
    project_data: ProjectCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """创建新项目"""
    try:
        project_repo = ProjectRepository(db)
        
        # 检查项目名称是否已存在
        existing_project = project_repo.get_by_name(project_data.name)
        if existing_project:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project name already exists"
            )
        
        # 创建项目
        project = project_repo.create({
            'name': project_data.name,
            'description': project_data.description,
            'config': project_data.config or {},
            'is_active': project_data.is_active
        })
        
        return Project(
            id=project.id,
            user_id=project.user_id,
            name=project.name,
            description=project.description,
            base_path=project.base_path or "",
            default_language=project.default_language or "en",
            is_active=project.is_active,
            source_count=0,
            total_tasks=0,
            pending_tasks=0,
            success_tasks=0,
            failed_tasks=0,
            created_at=project.created_at,
            updated_at=project.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}"
        )

@router.put("/projects/{project_id}", response_model=Project)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """更新项目"""
    try:
        project_repo = ProjectRepository(db)
        
        # 检查项目是否存在
        existing_project = project_repo.get_project_by_id(project_id)
        if not existing_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # 如果更新名称，检查是否与其他项目重复
        if project_data.name and project_data.name != existing_project.name:
            name_conflict = project_repo.get_by_name(project_data.name)
            if name_conflict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Project name already exists"
                )
        
        # 准备更新数据
        update_data = {}
        if project_data.name is not None:
            update_data['name'] = project_data.name
        if project_data.description is not None:
            update_data['description'] = project_data.description
        if project_data.config is not None:
            update_data['config'] = project_data.config
        if project_data.is_active is not None:
            update_data['is_active'] = project_data.is_active
        
        # 更新项目
        project = project_repo.update(project_id, update_data)
        
        # 获取项目统计信息
        task_repo = PublishingTaskRepository(db)
        total_tasks = task_repo.count_by_project(project.id)
        active_tasks = task_repo.count_by_project_and_status(project.id, 'in_progress')
        
        return Project(
            id=project.id,
            user_id=project.user_id,
            name=project.name,
            description=project.description,
            base_path=project.base_path or "",
            default_language=project.default_language or "en",
            is_active=project.is_active,
            source_count=len(project.content_sources) if project.content_sources else 0,
            total_tasks=total_tasks,
            pending_tasks=0,
            success_tasks=0,
            failed_tasks=0,
            created_at=project.created_at,
            updated_at=project.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project: {str(e)}"
        )

@router.delete("/projects/{project_id}", response_model=BaseResponse)
async def delete_project(
    project_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """删除项目"""
    try:
        project_repo = ProjectRepository(db)
        task_repo = PublishingTaskRepository(db)
        
        # 检查项目是否存在
        existing_project = project_repo.get_project_by_id(project_id)
        if not existing_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # 检查是否有运行中的任务
        active_tasks = task_repo.count_by_project_and_status(project_id, 'in_progress')
        if active_tasks > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete project with running tasks"
            )
        
        # 删除项目（级联删除相关的任务和内容源）
        project_repo.delete(project_id)
        
        return BaseResponse(
            success=True,
            message="Project deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}"
        )

@router.get("/projects/{project_id}/settings", response_model=ProjectSettings)
async def get_project_settings(
    project_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取项目设置"""
    try:
        project_repo = ProjectRepository(db)
        project = project_repo.get_project_by_id(project_id)
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        return ProjectSettings(
            id=project.id,
            name=project.name,
            description=project.description,
            config=project.config or {},
            is_active=project.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project settings: {str(e)}"
        )

@router.put("/projects/{project_id}/settings", response_model=ProjectSettings)
async def update_project_settings(
    project_id: int,
    settings: ProjectSettings,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """更新项目设置"""
    try:
        project_repo = ProjectRepository(db)
        
        # 检查项目是否存在
        existing_project = project_repo.get_by_id(project_id)
        if not existing_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # 更新项目设置
        project = project_repo.update(project_id, {
            'name': settings.name,
            'description': settings.description,
            'config': settings.config,
            'is_active': settings.is_active
        })
        
        return ProjectSettings(
            id=project.id,
            name=project.name,
            description=project.description,
            config=project.config or {},
            is_active=project.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project settings: {str(e)}"
        )

# 内容源管理相关端点

@router.get("/projects/{project_id}/content-sources", response_model=List[ContentSource])
async def list_project_content_sources(
    project_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取项目的内容源列表"""
    try:
        project_repo = ProjectRepository(db)
        source_repo = ContentSourceRepository(db)
        
        # 检查项目是否存在
        project = project_repo.get_project_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # 获取项目的内容源
        sources = source_repo.get_by_project_id(project_id)
        
        source_details = []
        for source in sources:
            source_detail = ContentSource(
                id=source.id,
                project_id=source.project_id,
                content_type=source.content_type,
                source_path=source.source_path or "",
                metadata_path=source.metadata_path or "",
                config=source.config or {},
                is_active=source.is_active,
                created_at=source.created_at,
                updated_at=source.updated_at
            )
            source_details.append(source_detail)
        
        return source_details
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list content sources: {str(e)}"
        )

@router.post("/projects/{project_id}/content-sources", response_model=ContentSource)
async def create_content_source(
    project_id: int,
    source_data: ContentSourceCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """为项目创建内容源"""
    try:
        project_repo = ProjectRepository(db)
        source_repo = ContentSourceRepository(db)
        
        # 检查项目是否存在
        project = project_repo.get_project_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # 检查内容源名称是否在项目中已存在
        existing_source = source_repo.get_by_project_and_name(project_id, source_data.name)
        if existing_source:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content source name already exists in this project"
            )
        
        # 创建内容源
        source = source_repo.create({
            'project_id': project_id,
            'name': source_data.name,
            'source_type': source_data.source_type,
            'config': source_data.config or {},
            'is_active': source_data.is_active
        })
        
        return ContentSource(
            id=source.id,
            project_id=source.project_id,
            content_type=source.content_type,
            source_path=source.source_path or "",
            metadata_path=source.metadata_path or "",
            config=source.config or {},
            is_active=source.is_active,
            created_at=source.created_at,
            updated_at=source.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create content source: {str(e)}"
        )

@router.get("/projects/{project_id}/analytics", response_model=Dict[str, Any])
async def get_project_analytics(
    project_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    days: int = Query(30, description="Number of days for analytics")
):
    """获取项目分析数据"""
    try:
        project_repo = ProjectRepository(db)
        task_repo = PublishingTaskRepository(db)
        
        # 检查项目是否存在
        project = project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # 获取项目分析数据
        from datetime import timedelta
        start_date = datetime.now() - timedelta(days=days)
        
        # 任务统计
        total_tasks = task_repo.count_by_project(project_id)
        completed_tasks = task_repo.count_by_project_and_status(project_id, 'success')
        failed_tasks = task_repo.count_by_project_and_status(project_id, 'failed')
        
        # 成功率
        success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # 最近活动
        recent_tasks = task_repo.get_recent_by_project(project_id, limit=10)
        
        return {
            "success": True,
            "analytics": {
                "project_id": project_id,
                "project_name": project.name,
                "period_days": days,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "success_rate": round(success_rate, 2),
                "recent_tasks": [
                    {
                        "id": task.id,
                        "status": task.status,
                        "created_at": task.created_at,
                        "content_type": task.content_type
                    }
                    for task in recent_tasks
                ]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project analytics: {str(e)}"
        )