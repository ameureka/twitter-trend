#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径管理器 - 跨平台路径处理和动态路径解析

主要功能:
1. 跨平台路径转换
2. 动态路径解析
3. 相对路径和绝对路径处理
4. 项目根目录自动检测
"""

import os
import platform
from pathlib import Path
from typing import Union, Optional, Dict, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PathManager:
    """跨平台路径管理器"""
    
    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        self.system = platform.system().lower()
        self.project_root = self._detect_project_root(project_root)
        self.path_mappings = self._init_path_mappings()
        
        logger.info(f"路径管理器初始化完成 - 系统: {self.system}, 项目根目录: {self.project_root}")
    
    def _detect_project_root(self, provided_root: Optional[Union[str, Path]] = None) -> Path:
        """自动检测项目根目录"""
        if provided_root:
            root = Path(provided_root).resolve()
            if root.exists():
                return root
        
        # 从当前文件位置向上查找项目根目录
        current = Path(__file__).parent
        while current.parent != current:
            # 查找标识文件
            markers = ['config', 'app', 'requirements.txt', '.git', 'deploy_twitter.sh']
            if any((current / marker).exists() for marker in markers):
                return current
            current = current.parent
        
        # 如果找不到，使用当前工作目录
        return Path.cwd()
    
    def _init_path_mappings(self) -> Dict[str, str]:
        """初始化路径映射配置"""
        return {
            'data': 'data',
            'logs': 'logs', 
            'config': 'config',
            'project': 'project',
            'scripts': 'scripts',
            'app': 'app',
            'api': 'api'
        }
    
    def normalize_path(self, path: Union[str, Path]) -> Path:
        """标准化路径，处理跨平台兼容性"""
        try:
            path_obj = Path(path)
            
            # 如果是绝对路径，检查是否需要转换
            if path_obj.is_absolute():
                return self._convert_absolute_path(path_obj)
            
            # 相对路径直接相对于项目根目录
            return (self.project_root / path_obj).resolve()
            
        except Exception as e:
            logger.error(f"路径标准化失败 {path}: {e}")
            return Path(path)
    
    def _convert_absolute_path(self, path: Path) -> Path:
        """转换绝对路径，处理不同操作系统间的路径差异"""
        path_str = str(path)
        
        # 检测项目路径模式（跨平台兼容）
        project_name = 'twitter-trend'
        if project_name in path_str:
            # 提取项目相对路径
            parts = path_str.split(project_name)
            if len(parts) > 1:
                relative_part = parts[1].lstrip('/').lstrip('\\')
                if relative_part:
                    return self.project_root / relative_part
                else:
                    return self.project_root
        
        # 检测Linux路径模式
        if '/data2/twitter-trend' in path_str:
            parts = path_str.split('/data2/twitter-trend')
            if len(parts) > 1:
                relative_part = parts[1].lstrip('/')
                if relative_part:
                    return self.project_root / relative_part
                else:
                    return self.project_root
        
        # 检测其他可能的项目路径模式
        for pattern in ['twitter-trend', 'twitter_trend']:
            if pattern in path_str:
                parts = path_str.split(pattern)
                if len(parts) > 1:
                    relative_part = parts[1].lstrip('/')
                    if relative_part:
                        return self.project_root / relative_part
                    else:
                        return self.project_root
        
        # 如果无法识别模式，返回原路径
        return path
    
    def get_project_path(self, relative_path: str = '') -> Path:
        """获取项目路径"""
        if relative_path:
            return self.project_root / relative_path
        return self.project_root
    
    def get_data_path(self, filename: str = '') -> Path:
        """获取数据目录路径"""
        data_dir = self.project_root / self.path_mappings['data']
        data_dir.mkdir(exist_ok=True)
        if filename:
            return data_dir / filename
        return data_dir
    
    def get_logs_path(self, filename: str = '') -> Path:
        """获取日志目录路径"""
        logs_dir = self.project_root / self.path_mappings['logs']
        logs_dir.mkdir(exist_ok=True)
        if filename:
            return logs_dir / filename
        return logs_dir
    
    def get_config_path(self, filename: str = '') -> Path:
        """获取配置目录路径"""
        config_dir = self.project_root / self.path_mappings['config']
        if filename:
            return config_dir / filename
        return config_dir
    
    def get_database_path(self, db_name: str = 'twitter_publisher.db') -> Path:
        """获取数据库文件路径"""
        return self.get_data_path(db_name)
    
    def convert_media_path(self, media_path: str) -> Path:
        """转换媒体文件路径"""
        return self.normalize_path(media_path)
    
    def ensure_directory(self, path: Union[str, Path]) -> Path:
        """确保目录存在"""
        path_obj = self.normalize_path(path)
        path_obj.mkdir(parents=True, exist_ok=True)
        return path_obj
    
    def is_valid_path(self, path: Union[str, Path]) -> bool:
        """检查路径是否有效"""
        try:
            normalized_path = self.normalize_path(path)
            return normalized_path.exists()
        except Exception:
            return False
    
    def get_relative_path(self, absolute_path: Union[str, Path], base_path: Optional[Union[str, Path]] = None) -> Path:
        """获取相对路径"""
        try:
            abs_path = Path(absolute_path)
            base = Path(base_path) if base_path else self.project_root
            return abs_path.relative_to(base)
        except ValueError:
            # 如果无法计算相对路径，返回原路径
            return Path(absolute_path)
    
    def create_database_url(self, db_path: Optional[Union[str, Path]] = None) -> str:
        """创建数据库URL"""
        if db_path:
            path = self.normalize_path(db_path)
        else:
            path = self.get_database_path()
        
        # 确保数据库目录存在
        path.parent.mkdir(parents=True, exist_ok=True)
        
        return f"sqlite:///{path}"
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        return {
            'system': self.system,
            'project_root': str(self.project_root),
            'cwd': str(Path.cwd()),
            'path_separator': os.sep,
            'path_mappings': self.path_mappings
        }
    
    def validate_project_structure(self) -> Dict[str, bool]:
        """验证项目结构"""
        required_dirs = ['app', 'config', 'data', 'logs']
        results = {}
        
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            results[dir_name] = dir_path.exists()
            
            # 如果不存在，尝试创建
            if not results[dir_name] and dir_name in ['data', 'logs']:
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    results[dir_name] = True
                    logger.info(f"创建目录: {dir_path}")
                except Exception as e:
                    logger.error(f"创建目录失败 {dir_path}: {e}")
        
        return results


# 全局路径管理器实例
_path_manager_instance = None


def get_path_manager() -> PathManager:
    """获取全局路径管理器实例"""
    global _path_manager_instance
    if _path_manager_instance is None:
        _path_manager_instance = PathManager()
    return _path_manager_instance


def init_path_manager(project_root: Optional[Union[str, Path]] = None) -> PathManager:
    """初始化全局路径管理器实例"""
    global _path_manager_instance
    _path_manager_instance = PathManager(project_root)
    return _path_manager_instance