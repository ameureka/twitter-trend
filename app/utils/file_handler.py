# app/utils/file_handler.py

import os
import json
import hashlib
import shutil
from typing import Dict, List, Any, Optional
from pathlib import Path
from app.utils.logger import get_logger
from app.utils.path_manager import get_path_manager

logger = get_logger(__name__)
path_manager = get_path_manager()

def ensure_directory_exists(path: str) -> bool:
    """确保目录存在，如果不存在则创建"""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败 {path}: {e}")
        return False

def get_file_hash(file_path: str) -> Optional[str]:
    """计算文件的MD5哈希值"""
    try:
        normalized_path = path_manager.normalize_path(file_path)
        hash_md5 = hashlib.md5()
        with open(normalized_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希失败 {file_path}: {e}")
        return None

def get_file_size_mb(file_path: str) -> float:
    """获取文件大小（MB）"""
    try:
        normalized_path = path_manager.normalize_path(file_path)
        size_bytes = normalized_path.stat().st_size
        return size_bytes / (1024 * 1024)
    except Exception as e:
        logger.error(f"获取文件大小失败 {file_path}: {e}")
        return 0.0

def is_video_file(file_path: str) -> bool:
    """判断是否为视频文件"""
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
    return Path(file_path).suffix.lower() in video_extensions

def is_image_file(file_path: str) -> bool:
    """判断是否为图片文件"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
    return Path(file_path).suffix.lower() in image_extensions

def load_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    """安全地加载JSON文件"""
    try:
        normalized_path = path_manager.normalize_path(file_path)
        with open(normalized_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.debug(f"成功加载JSON文件: {file_path} -> {normalized_path}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON格式错误 {file_path}: {e}")
        return None
    except FileNotFoundError:
        logger.error(f"文件不存在: {file_path}")
        return None
    except Exception as e:
        logger.error(f"加载JSON文件失败 {file_path}: {e}")
        return None

def save_json_file(data: Dict[str, Any], file_path: str) -> bool:
    """安全地保存JSON文件"""
    try:
        # 使用路径管理器标准化路径
        normalized_path = path_manager.normalize_path(file_path)
        
        # 确保目录存在
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(normalized_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"成功保存JSON文件: {file_path} -> {normalized_path}")
        return True
    except Exception as e:
        logger.error(f"保存JSON文件失败 {file_path}: {e}")
        return False

def find_files_by_pattern(directory: str, pattern: str, recursive: bool = False) -> List[str]:
    """根据模式查找文件"""
    try:
        # 使用路径管理器标准化目录路径
        normalized_dir = path_manager.normalize_path(directory)
        
        if not normalized_dir.exists():
            logger.warning(f"目录不存在: {directory} -> {normalized_dir}")
            return []
        
        if recursive:
            files = list(normalized_dir.rglob(pattern))
        else:
            files = list(normalized_dir.glob(pattern))
        
        # 返回绝对路径字符串
        return [str(f.resolve()) for f in files if f.is_file()]
    except Exception as e:
        logger.error(f"查找文件失败 {directory}/{pattern}: {e}")
        return []

def get_media_files(directory: str) -> Dict[str, List[str]]:
    """获取目录中的所有媒体文件"""
    result = {
        'videos': [],
        'images': [],
        'other': []
    }
    
    try:
        # 使用路径管理器标准化目录路径
        normalized_dir = path_manager.normalize_path(directory)
        
        if not normalized_dir.exists():
            logger.warning(f"目录不存在: {directory} -> {normalized_dir}")
            return result
        
        for file_path in normalized_dir.iterdir():
            if file_path.is_file():
                file_str = str(file_path)
                if is_video_file(file_str):
                    result['videos'].append(file_str)
                elif is_image_file(file_str):
                    result['images'].append(file_str)
                else:
                    result['other'].append(file_str)
        
        # 按文件名排序
        for category in result:
            result[category].sort()
            
        logger.debug(f"扫描目录 {directory}: 视频 {len(result['videos'])} 个，图片 {len(result['images'])} 个")
        
    except Exception as e:
        logger.error(f"扫描媒体文件失败 {directory}: {e}")
    
    return result

def validate_file_access(file_path: str, check_read: bool = True, check_write: bool = False) -> bool:
    """验证文件访问权限"""
    try:
        # 使用路径管理器标准化路径
        normalized_path = path_manager.normalize_path(file_path)
        
        if not normalized_path.exists():
            logger.error(f"文件不存在: {file_path} -> {normalized_path}")
            return False
        
        if check_read and not os.access(str(normalized_path), os.R_OK):
            logger.error(f"文件无读取权限: {file_path} -> {normalized_path}")
            return False
        
        if check_write and not os.access(str(normalized_path), os.W_OK):
            logger.error(f"文件无写入权限: {file_path} -> {normalized_path}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"验证文件访问权限失败 {file_path}: {e}")
        return False

def clean_filename(filename: str) -> str:
    """清理文件名，移除不安全字符"""
    import re
    
    # 移除或替换不安全字符
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # 移除连续的下划线
    cleaned = re.sub(r'_+', '_', cleaned)
    
    # 移除开头和结尾的下划线和空格
    cleaned = cleaned.strip('_ ')
    
    return cleaned

def get_relative_path(file_path: str, base_path: str) -> str:
    """获取相对于基础路径的相对路径"""
    try:
        file_path_obj = Path(file_path)
        base_path_obj = Path(base_path)
        return str(file_path_obj.relative_to(base_path_obj))
    except Exception as e:
        logger.error(f"计算相对路径失败: {e}")
        return file_path

def backup_file(file_path: str, backup_suffix: str = '.bak') -> Optional[str]:
    """备份文件"""
    try:
        source_path = Path(file_path)
        if not source_path.exists():
            logger.error(f"要备份的文件不存在: {file_path}")
            return None
        
        backup_path = source_path.with_suffix(source_path.suffix + backup_suffix)
        
        # 如果备份文件已存在，添加时间戳
        if backup_path.exists():
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = source_path.with_suffix(f".{timestamp}{backup_suffix}")
        
        shutil.copy2(source_path, backup_path)
        
        logger.info(f"文件备份成功: {backup_path}")
        return str(backup_path)
        
    except Exception as e:
        logger.error(f"备份文件失败 {file_path}: {e}")
        return None