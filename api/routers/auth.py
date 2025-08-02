#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证相关API路由
处理API密钥管理和用户认证
"""

import os
import sys
from pathlib import Path
from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.dependencies import get_db, api_key_auth, get_current_user_id
from api.schemas import (
    BaseResponse, ErrorResponse, APIKeyRequest, APIKeyResponse
)

router = APIRouter()

@router.get("/auth/verify", response_model=BaseResponse)
async def verify_api_key(
    api_key: str = Depends(api_key_auth),
    user_id: int = Depends(get_current_user_id)
):
    """验证API密钥有效性"""
    return BaseResponse(
        success=True,
        message=f"API key is valid for user {user_id}"
    )

@router.get("/auth/user", response_model=dict)
async def get_current_user(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取当前用户信息"""
    try:
        from app.database.repository import UserRepository
        
        user_repo = UserRepository(db)
        user = user_repo.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            "success": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "twitter_username": user.twitter_username,
                "created_at": user.created_at,
                "is_active": user.is_active
            }
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user info: {str(e)}"
        )

@router.get("/auth/permissions", response_model=dict)
async def get_user_permissions(
    user_id: int = Depends(get_current_user_id)
):
    """获取用户权限信息"""
    # 在简化版本中，所有用户都有相同的权限
    # 在完整版本中，可以根据用户角色返回不同的权限
    permissions = {
        "can_view_dashboard": True,
        "can_manage_tasks": True,
        "can_manage_projects": True,
        "can_view_logs": True,
        "can_view_analytics": True,
        "can_manage_settings": True
    }
    
    return {
        "success": True,
        "permissions": permissions,
        "user_id": user_id
    }

# 注意：以下端点在简化版本中暂不实现，但保留接口定义
# 在完整版本中，需要实现API密钥的CRUD操作

@router.post("/auth/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    request: APIKeyRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """创建新的API密钥（暂未实现）"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="API key management not implemented in this version"
    )

@router.get("/auth/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取用户的API密钥列表（暂未实现）"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="API key management not implemented in this version"
    )

@router.delete("/auth/api-keys/{key_id}", response_model=BaseResponse)
async def delete_api_key(
    key_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """删除API密钥（暂未实现）"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="API key management not implemented in this version"
    )