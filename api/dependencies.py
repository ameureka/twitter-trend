#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API依赖注入模块
提供数据库会话、认证、配置等依赖项
"""

import os
import sys
from typing import Generator, Optional
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from pydantic_settings import BaseSettings, SettingsConfigDict

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.database import DatabaseManager
from app.utils.config import ConfigManager

class APISettings(BaseSettings):
    """API配置设置"""
    
    # API服务配置
    api_host: str = "127.0.0.1"
    api_port: int = 8050
    debug: bool = False
    
    # 数据库配置
    database_url: Optional[str] = None
    
    # 认证配置
    api_key: str = "dev-api-key-12345"  # 默认开发用密钥
    
    # 项目配置
    config_file: str = "config/enhanced_config.yaml"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="API_",
        extra="allow"  # 允许额外的字段
    )

@lru_cache()
def get_settings() -> APISettings:
    """获取API配置设置（缓存）"""
    return APISettings()

# 全局数据库管理器实例
_db_manager: Optional[DatabaseManager] = None

def get_database_manager() -> DatabaseManager:
    """获取数据库管理器实例"""
    global _db_manager
    
    if _db_manager is None:
        settings = get_settings()
        
        # 如果没有指定数据库URL，使用默认路径
        if settings.database_url:
            db_url = settings.database_url
        else:
            # 直接使用默认数据库路径
            default_db_path = project_root / "data" / "twitter_publisher.db"
            db_url = f"sqlite:///{default_db_path}"
        
        _db_manager = DatabaseManager(db_url)
    
    return _db_manager

def get_db() -> Generator[Session, None, None]:
    """获取数据库会话"""
    db_manager = get_database_manager()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()

def get_config() -> ConfigManager:
    """获取应用配置"""
    settings = get_settings()
    return ConfigManager(settings.config_file)

async def api_key_auth(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """API密钥认证"""
    settings = get_settings()
    
    # 在开发模式下，允许使用默认密钥
    valid_keys = [settings.api_key]
    
    # 如果是生产环境，可以从数据库或环境变量读取更多密钥
    if not settings.debug:
        # TODO: 从数据库的api_keys表读取有效密钥
        pass
    
    if x_api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return x_api_key

async def optional_api_key_auth(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Optional[str]:
    """可选的API密钥认证（用于公开端点）"""
    if x_api_key is None:
        return None
    
    try:
        return await api_key_auth(x_api_key)
    except HTTPException:
        return None

def get_current_user_id(api_key: str = Depends(api_key_auth)) -> int:
    """获取当前用户ID（基于API密钥）"""
    # 在简化版本中，我们使用默认用户ID
    # 在完整版本中，应该根据API密钥查询对应的用户
    return 1

def get_pagination_params(
    page: int = 1,
    per_page: int = 20,
    max_per_page: int = 100
) -> dict:
    """获取分页参数"""
    if page < 1:
        page = 1
    
    if per_page < 1:
        per_page = 20
    elif per_page > max_per_page:
        per_page = max_per_page
    
    offset = (page - 1) * per_page
    
    return {
        "page": page,
        "per_page": per_page,
        "offset": offset,
        "limit": per_page
    }