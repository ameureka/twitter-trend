#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态路径管理器

解决问题一：致命的环境不匹配与硬编码路径

主要功能：
1. 运行时动态解析媒体文件路径
2. 根据当前环境自动选择正确的基础路径
3. 提供统一的路径转换和验证接口
4. 支持开发环境和生产环境的无缝切换

设计原则：
- 数据库存储相对路径
- 运行时动态拼接完整路径
- 环境感知的路径解析
- 向后兼容现有硬编码路径
"""

import os
import platform
from pathlib import Path
from typing import Optional, Union, Dict, Any
from functools import lru_cache

from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config

logger = get_logger(__name__)

class DynamicPathManager:
    """动态路径管理器"""
    
    def __init__(self):
        self.config = get_enhanced_config()
        self._base_path_cache = None
        self._environment_cache = None
        
        # 环境检测模式
        self.auto_detect_environment = True
        
        # 硬编码路径模式（用于识别和转换）
        self.hardcoded_patterns = {
            'macos_dev': '/Users/ameureka/Desktop/twitter-trend',
            'linux_prod': '/home/twitter-trend',
            'linux_data2': '/data2/twitter-trend'
        }
        
        logger.info(f"动态路径管理器初始化完成")
        logger.info(f"当前系统: {platform.system()}")
        logger.info(f"当前工作目录: {os.getcwd()}")
    
    @property
    def current_environment(self) -> str:
        """获取当前环境"""
        if self._environment_cache is None:
            self._environment_cache = self._detect_environment()
        return self._environment_cache
    
    @property
    def base_path(self) -> Path:
        """获取当前环境的基础路径"""
        if self._base_path_cache is None:
            self._base_path_cache = self._determine_base_path()
        return self._base_path_cache
    
    def _detect_environment(self) -> str:
        """检测当前运行环境"""
        # 优先使用环境变量
        env_var = os.environ.get('TWITTER_TREND_ENV')
        if env_var in ['development', 'production']:
            logger.info(f"从环境变量检测到环境: {env_var}")
            return env_var
        
        # 从配置文件检测
        config_env = self.config.get('environment')
        if config_env in ['development', 'production']:
            logger.info(f"从配置文件检测到环境: {config_env}")
            return config_env
        
        # 自动检测
        current_path = os.getcwd()
        system = platform.system()
        
        # 开发环境指标
        dev_indicators = [
            '/Users/' in current_path,  # macOS用户目录
            'Desktop' in current_path,  # 桌面开发
            system == 'Darwin'  # macOS系统
        ]
        
        # 生产环境指标
        prod_indicators = [
            '/home/' in current_path,  # Linux用户目录
            '/data2/' in current_path,  # 生产服务器路径
            system == 'Linux'  # Linux系统
        ]
        
        dev_score = sum(dev_indicators)
        prod_score = sum(prod_indicators)
        
        if dev_score > prod_score:
            detected_env = 'development'
        elif prod_score > dev_score:
            detected_env = 'production'
        else:
            # 默认根据系统判断
            detected_env = 'development' if system == 'Darwin' else 'production'
        
        logger.info(f"自动检测环境: {detected_env} (开发:{dev_score}, 生产:{prod_score})")
        return detected_env
    
    def _determine_base_path(self) -> Path:
        """确定基础路径"""
        # 优先使用环境变量
        env_base_path = os.environ.get('TWITTER_TREND_BASE_PATH')
        if env_base_path and Path(env_base_path).exists():
            logger.info(f"使用环境变量基础路径: {env_base_path}")
            return Path(env_base_path)
        
        # 根据环境确定基础路径
        if self.current_environment == 'development':
            # 开发环境：优先使用当前项目目录
            candidates = [
                Path.cwd(),  # 当前工作目录
                Path(__file__).parent.parent.parent,  # 项目根目录
                Path('/Users/ameureka/Desktop/twitter-trend')  # 默认开发路径
            ]
        else:
            # 生产环境：使用生产路径
            candidates = [
                Path('/home/twitter-trend'),
                Path('/data2/twitter-trend'),
                Path.cwd()  # 当前工作目录作为后备
            ]
        
        # 选择第一个存在的路径
        for candidate in candidates:
            if candidate.exists() and (candidate / 'app').exists():
                logger.info(f"选择基础路径: {candidate}")
                return candidate
        
        # 如果都不存在，使用当前工作目录
        fallback = Path.cwd()
        logger.warning(f"使用后备基础路径: {fallback}")
        return fallback
    
    def resolve_media_path(self, path_or_identifier: str) -> Path:
        """解析媒体文件路径
        
        Args:
            path_or_identifier: 可能是相对路径、绝对路径或标识符
            
        Returns:
            解析后的完整路径
        """
        if not path_or_identifier:
            raise ValueError("路径不能为空")
        
        path_obj = Path(path_or_identifier)
        
        # 如果是绝对路径
        if path_obj.is_absolute():
            # 检查是否为硬编码路径
            if self._is_hardcoded_path(path_or_identifier):
                # 转换为相对路径后重新解析
                relative_path = self._convert_hardcoded_to_relative(path_or_identifier)
                return self.resolve_media_path(relative_path)
            else:
                # 直接使用绝对路径
                return path_obj
        
        # 相对路径：基于当前环境的基础路径解析
        resolved_path = self.base_path / path_obj
        
        logger.debug(f"路径解析: {path_or_identifier} -> {resolved_path}")
        return resolved_path
    
    def _is_hardcoded_path(self, path: str) -> bool:
        """检查是否为硬编码路径"""
        return any(pattern in path for pattern in self.hardcoded_patterns.values())
    
    def _convert_hardcoded_to_relative(self, hardcoded_path: str) -> str:
        """将硬编码路径转换为相对路径"""
        for pattern_name, pattern in self.hardcoded_patterns.items():
            if pattern in hardcoded_path:
                # 移除硬编码前缀，获取相对部分
                relative_part = hardcoded_path.replace(pattern, '').lstrip('/')
                if relative_part:
                    logger.debug(f"硬编码路径转换: {hardcoded_path} -> {relative_part}")
                    return relative_part
                else:
                    return '.'
        
        # 如果无法转换，尝试查找 'project' 目录
        path_obj = Path(hardcoded_path)
        parts = path_obj.parts
        try:
            project_index = parts.index('project')
            relative_parts = parts[project_index:]
            relative_path = str(Path(*relative_parts))
            logger.debug(f"通过project目录转换: {hardcoded_path} -> {relative_path}")
            return relative_path
        except ValueError:
            pass
        
        logger.warning(f"无法转换硬编码路径: {hardcoded_path}")
        return hardcoded_path
    
    def validate_media_file(self, path_or_identifier: str) -> Dict[str, Any]:
        """验证媒体文件
        
        Args:
            path_or_identifier: 媒体文件路径或标识符
            
        Returns:
            验证结果字典
        """
        result = {
            'original_path': path_or_identifier,
            'resolved_path': None,
            'exists': False,
            'readable': False,
            'size': 0,
            'is_hardcoded': False,
            'converted_path': None,
            'valid': False,
            'error': None
        }
        
        try:
            # 检查是否为硬编码路径
            result['is_hardcoded'] = self._is_hardcoded_path(path_or_identifier)
            
            # 解析路径
            resolved_path = self.resolve_media_path(path_or_identifier)
            result['resolved_path'] = str(resolved_path)
            
            # 如果是硬编码路径，记录转换后的相对路径
            if result['is_hardcoded']:
                result['converted_path'] = self._convert_hardcoded_to_relative(path_or_identifier)
            
            # 检查文件存在性
            result['exists'] = resolved_path.exists()
            
            if result['exists']:
                result['readable'] = os.access(resolved_path, os.R_OK)
                result['size'] = resolved_path.stat().st_size
                # 文件存在且可读则认为有效
                result['valid'] = result['readable'] and result['size'] > 0
            else:
                # 如果文件不存在，尝试通过文件名搜索
                found_files = self._find_files_by_name(Path(path_or_identifier).name)
                if found_files:
                    # 使用找到的第一个文件
                    found_path = Path(found_files[0])
                    result['resolved_path'] = str(found_path)
                    result['exists'] = found_path.exists()
                    if result['exists']:
                        result['readable'] = os.access(found_path, os.R_OK)
                        result['size'] = found_path.stat().st_size
                        result['valid'] = result['readable'] and result['size'] > 0
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"媒体文件验证失败: {path_or_identifier}, 错误: {e}")
        
        return result
    
    def get_project_relative_path(self, absolute_path: Union[str, Path]) -> str:
        """获取相对于项目根目录的相对路径
        
        Args:
            absolute_path: 绝对路径
            
        Returns:
            相对路径字符串
        """
        path_obj = Path(absolute_path)
        
        if not path_obj.is_absolute():
            return str(path_obj)
        
        try:
            # 尝试相对于基础路径计算
            relative_path = path_obj.relative_to(self.base_path)
            return str(relative_path)
        except ValueError:
            # 如果无法计算相对路径，尝试硬编码转换
            if self._is_hardcoded_path(str(path_obj)):
                return self._convert_hardcoded_to_relative(str(path_obj))
            else:
                logger.warning(f"无法转换为相对路径: {absolute_path}")
                return str(path_obj)
    
    def ensure_project_directory(self, relative_path: str) -> Path:
        """确保项目目录存在
        
        Args:
            relative_path: 相对路径
            
        Returns:
            完整的目录路径
        """
        full_path = self.base_path / relative_path
        full_path.mkdir(parents=True, exist_ok=True)
        return full_path
    
    @lru_cache(maxsize=128)
    def get_media_search_paths(self) -> list[Path]:
        """获取媒体文件搜索路径列表
        
        Returns:
            按优先级排序的搜索路径列表
        """
        search_paths = []
        
        # 1. 项目目录
        project_dir = self.base_path / 'project'
        if project_dir.exists():
            search_paths.append(project_dir)
        
        # 2. 常见的媒体输出目录
        common_media_dirs = [
            'output_video_music',
            'outputs',
            'media',
            'videos',
            'audio'
        ]
        
        for media_dir in common_media_dirs:
            media_path = self.base_path / media_dir
            if media_path.exists():
                search_paths.append(media_path)
        
        # 3. 递归搜索项目目录下的媒体目录
        if project_dir.exists():
            for subdir in project_dir.rglob('*'):
                if subdir.is_dir() and any(keyword in subdir.name.lower() 
                                         for keyword in ['output', 'media', 'video', 'audio']):
                    search_paths.append(subdir)
        
        logger.debug(f"媒体搜索路径: {[str(p) for p in search_paths]}")
        return search_paths
    
    def find_media_file(self, filename: str) -> Optional[Path]:
        """在搜索路径中查找媒体文件
        
        Args:
            filename: 文件名
            
        Returns:
            找到的文件路径，如果未找到则返回None
        """
        search_paths = self.get_media_search_paths()
        
        for search_path in search_paths:
            # 直接查找
            file_path = search_path / filename
            if file_path.exists():
                logger.info(f"找到媒体文件: {file_path}")
                return file_path
            
            # 递归查找
            for found_file in search_path.rglob(filename):
                if found_file.is_file():
                    logger.info(f"递归找到媒体文件: {found_file}")
                    return found_file
        
        logger.warning(f"未找到媒体文件: {filename}")
        return None
    
    def _find_files_by_name(self, filename: str) -> list[str]:
        """通过文件名查找文件（内部方法）
        
        Args:
            filename: 文件名
            
        Returns:
            找到的文件路径列表
        """
        found_files = []
        search_paths = self.get_media_search_paths()
        
        for search_path in search_paths:
            # 直接查找
            file_path = search_path / filename
            if file_path.exists():
                found_files.append(str(file_path))
            
            # 递归查找
            for found_file in search_path.rglob(filename):
                if found_file.is_file():
                    found_files.append(str(found_file))
        
        # 去重
        found_files = list(set(found_files))
        logger.debug(f"通过文件名 '{filename}' 找到文件: {found_files}")
        return found_files
    
    def get_environment_info(self) -> Dict[str, Any]:
        """获取环境信息
        
        Returns:
            环境信息字典
        """
        return {
            'environment': self.current_environment,
            'base_path': str(self.base_path),
            'system': platform.system(),
            'working_directory': os.getcwd(),
            'config_project_base_path': self.config.get('project_base_path'),
            'env_vars': {
                'TWITTER_TREND_BASE_PATH': os.environ.get('TWITTER_TREND_BASE_PATH'),
                'TWITTER_TREND_ENV': os.environ.get('TWITTER_TREND_ENV'),
                'TWITTER_TREND_PROJECT_PATH': os.environ.get('TWITTER_TREND_PROJECT_PATH')
            },
            'hardcoded_patterns': self.hardcoded_patterns
        }
    
    def clear_cache(self):
        """清除缓存"""
        self._base_path_cache = None
        self._environment_cache = None
        self.get_media_search_paths.cache_clear()
        logger.info("路径管理器缓存已清除")

# 全局实例
_dynamic_path_manager = None

def get_dynamic_path_manager() -> DynamicPathManager:
    """获取动态路径管理器实例"""
    global _dynamic_path_manager
    if _dynamic_path_manager is None:
        _dynamic_path_manager = DynamicPathManager()
    return _dynamic_path_manager

def resolve_media_path(path_or_identifier: str) -> Path:
    """便捷函数：解析媒体路径"""
    return get_dynamic_path_manager().resolve_media_path(path_or_identifier)

def validate_media_file(path_or_identifier: str) -> Dict[str, Any]:
    """便捷函数：验证媒体文件"""
    return get_dynamic_path_manager().validate_media_file(path_or_identifier)

def find_media_file(filename: str) -> Optional[Path]:
    """便捷函数：查找媒体文件"""
    return get_dynamic_path_manager().find_media_file(filename)