# app/core/project_manager.py

import os
import json
import glob
import random
from typing import List, Optional, Dict, Any
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta

from app.database.models import User, Project, ContentSource, PublishingTask
from app.database.repository import (
    UserRepository, ProjectRepository, ContentSourceRepository, 
    PublishingTaskRepository
)
from app.utils.logger import get_logger
from app.utils.file_handler import get_media_files, get_file_hash
from app.utils.path_manager import get_path_manager
from app.utils.enhanced_config import get_enhanced_config

class ProjectManager:
    def __init__(self, db_session: Session, project_base_path: str, user_id: int = 1):
        self.session = db_session
        self.base_path = project_base_path
        self.user_id = user_id
        self.logger = get_logger(__name__)
        self.path_manager = get_path_manager()
        self.config = get_enhanced_config()
        
        # 获取调度配置
        scheduling_config = self.config.get('scheduling', {})
        self.optimal_hours = scheduling_config.get('optimal_hours', [9, 12, 15, 18, 21])
        
        # 初始化仓库
        self.user_repo = UserRepository(db_session)
        self.project_repo = ProjectRepository(db_session)
        self.content_source_repo = ContentSourceRepository(db_session)
        self.task_repo = PublishingTaskRepository(db_session)
    
    def _generate_distributed_schedule_times(self, count: int, days_ahead: int = 30) -> List[datetime]:
        """生成分散在未来几天的任务调度时间，遵循每日任务数量限制"""
        if count <= 0:
            return []
        
        # 获取调度配置
        scheduling_config = self.config.get('scheduling', {})
        daily_max_tasks = scheduling_config.get('daily_max_tasks', 6)
        daily_min_tasks = scheduling_config.get('daily_min_tasks', 5)
        
        schedule_times = []
        now = datetime.now()
        start_date = now.date()
        
        # 查询现有任务的日期分布
        existing_tasks_by_date = {}
        try:
            existing_tasks = self.task_repo.session.query(PublishingTask).filter(
                PublishingTask.status == 'pending',
                PublishingTask.scheduled_at >= now
            ).all()
            
            for task in existing_tasks:
                task_date = task.scheduled_at.date()
                existing_tasks_by_date[task_date] = existing_tasks_by_date.get(task_date, 0) + 1
        except Exception as e:
            self.logger.warning(f"查询现有任务失败: {e}")
        
        # 分配任务到不同日期
        current_day = 0
        tasks_assigned = 0
        
        while tasks_assigned < count and current_day < days_ahead:
            target_date = start_date + timedelta(days=current_day)
            
            # 检查该日期已有的任务数量
            existing_count = existing_tasks_by_date.get(target_date, 0)
            
            # 计算该日期还能分配的任务数量
            available_slots = max(0, daily_max_tasks - existing_count)
            
            if available_slots > 0:
                # 计算本日要分配的任务数量
                remaining_tasks = count - tasks_assigned
                tasks_for_today = min(available_slots, remaining_tasks)
                
                # 为该日期生成任务时间
                for i in range(tasks_for_today):
                    # 随机选择一个最佳时间段
                    optimal_hour = random.choice(self.optimal_hours)
                    
                    # 在该小时内随机选择分钟
                    minute = random.randint(0, 59)
                    second = random.randint(0, 59)
                    
                    # 构造时间点
                    scheduled_time = datetime.combine(target_date, datetime.min.time()).replace(
                        hour=optimal_hour,
                        minute=minute,
                        second=second,
                        microsecond=0
                    )
                    
                    # 确保时间不早于当前时间
                    if scheduled_time <= now:
                        scheduled_time = now + timedelta(minutes=random.randint(5, 60))
                    
                    schedule_times.append(scheduled_time)
                    tasks_assigned += 1
                
                # 更新该日期的任务计数
                existing_tasks_by_date[target_date] = existing_count + tasks_for_today
            
            current_day += 1
        
        # 如果还有未分配的任务，强制分配到后续日期
        if tasks_assigned < count:
            remaining = count - tasks_assigned
            self.logger.warning(f"有 {remaining} 个任务无法在 {days_ahead} 天内合理分配，将强制分配到后续日期")
            
            for i in range(remaining):
                target_date = start_date + timedelta(days=days_ahead + i // daily_max_tasks)
                optimal_hour = random.choice(self.optimal_hours)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                
                scheduled_time = datetime.combine(target_date, datetime.min.time()).replace(
                    hour=optimal_hour,
                    minute=minute,
                    second=second,
                    microsecond=0
                )
                
                schedule_times.append(scheduled_time)
        
        # 按时间排序
        schedule_times.sort()
        return schedule_times
    
    def scan_and_create_tasks(self, project_name: str, language: str, max_tasks_per_scan: int = None):
        """扫描指定项目，为新发现的媒体文件创建发布任务。
        
        Args:
            project_name: 项目名称
            language: 语言
            max_tasks_per_scan: 单次扫描最大创建任务数，如果为None则使用配置中的daily_max_tasks
        """
        self.logger.info(f"开始扫描项目: {project_name}, 语言: {language}")
        
        # 获取每日任务限制配置
        scheduling_config = self.config.get('scheduling', {})
        daily_max_tasks = scheduling_config.get('daily_max_tasks', 6)
        
        # 如果没有指定最大任务数，使用配置中的daily_max_tasks
        if max_tasks_per_scan is None:
            max_tasks_per_scan = daily_max_tasks
        
        self.logger.info(f"单次扫描最大创建任务数: {max_tasks_per_scan}")
        
        try:
            # 1. 在数据库中查找或创建项目记录
            project = self._get_or_create_project(project_name)

            # 2. 定义视频和元数据文件夹路径
            project_path = self.path_manager.normalize_path(Path(self.base_path) / project_name)
            video_dir = project_path / "output_video_music"
            json_dir = project_path / "uploader_json"

            if not video_dir.exists():
                self.logger.warning(f"视频目录不存在: {video_dir}")
                return 0
                
            if not json_dir.exists():
                self.logger.warning(f"JSON目录不存在: {json_dir}")
                return 0

            # 3. 收集所有需要创建的任务信息
            pending_tasks = []
            for video_file in video_dir.glob('*.mp4'):
                filename = video_file.name
                # 使用路径管理器标准化媒体文件路径
                media_path = str(self.path_manager.normalize_path(video_file))
                
                # 4. 查找对应的 JSON 元数据文件
                metadata_path = self._find_metadata_file(str(json_dir), filename, language)
                
                if not metadata_path:
                    self.logger.warning(f"未找到 {filename} 对应的 {language} 语言元数据文件")
                    continue
                
                # 5. 检查任务是否已存在
                existing_task = self.task_repo.session.query(PublishingTask).filter(
                    PublishingTask.project_id == project.id,
                    PublishingTask.media_path == media_path,
                    PublishingTask.status.in_(['pending', 'locked', 'in_progress', 'success'])
                ).first()
                
                if existing_task:
                    self.logger.debug(f"任务已存在，跳过: {filename} (状态: {existing_task.status})")
                    continue
                
                # 6. 获取内容源
                content_source = self._get_content_source(project.id, 'video', video_dir)
                
                # 7. 准备任务数据
                content_data = {
                    'metadata_path': metadata_path,
                    'language': language,
                    'status': 'pending',
                    'priority': 1,
                    'max_retries': 3
                }
                
                pending_tasks.append({
                    'filename': filename,
                    'project_id': project.id,
                    'source_id': content_source.id,
                    'media_path': media_path,
                    'content_data': content_data
                })
                
                # 限制单次扫描创建的任务数量
                if len(pending_tasks) >= max_tasks_per_scan:
                    self.logger.info(f"已达到单次扫描最大任务数限制 ({max_tasks_per_scan})，停止收集更多任务")
                    break
            
            # 8. 如果有待创建的任务，生成分散的调度时间
            new_tasks_count = 0
            if pending_tasks:
                # 生成分散的调度时间
                schedule_times = self._generate_distributed_schedule_times(len(pending_tasks))
                
                # 创建任务
                for i, task_info in enumerate(pending_tasks):
                    scheduled_at = schedule_times[i] if i < len(schedule_times) else datetime.now() + timedelta(minutes=i*5)
                    
                    task = self.task_repo.create_task(
                        project_id=task_info['project_id'],
                        source_id=task_info['source_id'],
                        media_path=task_info['media_path'],
                        content_data=task_info['content_data'],
                        scheduled_at=scheduled_at
                    )
                    
                    new_tasks_count += 1
                    self.logger.info(f"创建新任务: {task_info['filename']} (调度时间: {scheduled_at})")
            
            # 9. 更新项目扫描时间
            self.project_repo.update(project.id, {'last_scanned': datetime.utcnow()})
            
            self.logger.info(f"项目 '{project_name}' 扫描完成，创建了 {new_tasks_count} 个新任务")
            
            return new_tasks_count
            
        except SQLAlchemyError as e:
            self.session.rollback()
            self.logger.error(f"数据库操作失败: {e}")
            raise
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"扫描项目失败: {e}")
            raise

    def _get_or_create_project(self, name: str) -> Project:
        """根据名称获取或创建项目。"""
        try:
            project = self.project_repo.get_by_name_and_user(name, self.user_id)
            
            if not project:
                project_path = self.path_manager.normalize_path(Path(self.base_path) / name)
                if not project_path.exists():
                    raise ValueError(f"项目目录不存在: {project_path}")
                
                # 创建项目数据
                project_data = {
                    'name': name,
                    'description': f'自动创建的项目: {name}',
                    'user_id': self.user_id,
                    'status': 'active'
                }
                
                project = self.project_repo.create(project_data)
                self.logger.info(f"创建新项目: {name}")
                
                # 创建默认内容源
                self._create_default_content_sources(project.id, project_path)
                
            return project
            
        except Exception as e:
            self.logger.error(f"获取或创建项目失败: {e}")
            raise

    def _find_metadata_file(self, json_dir: str, video_filename: str, language: str) -> str or None:
        """查找与视频文件对应的元数据文件。"""
        try:
            # 从视频文件名中提取基础名称（去掉扩展名）
            base_name = Path(video_filename).stem
            json_dir_path = Path(json_dir)
            
            # 查找批量JSON文件（新格式）
            batch_patterns = [
                f"{language}_prompt_results_*.json",
                f"*_{language}_*.json",
                f"{language}_*.json"
            ]
            
            for pattern in batch_patterns:
                json_files = list(json_dir_path.glob(pattern))
                for json_file in json_files:
                    # 检查JSON文件中是否包含该媒体文件的元数据
                    if self._validate_metadata_file(str(json_file), video_filename):
                        return str(json_file)
            
            # 回退到单文件JSON格式（旧格式）
            patterns = [
                f"{language}_prompt_results_{base_name}.json",
                f"{language}_prompt_results.json",
                f"{base_name}_{language}.json",
                f"{base_name}.{language}.json",
                f"{base_name}-{language}.json",
                f"{base_name}.json"
            ]
            
            for pattern in patterns:
                metadata_path = json_dir_path / pattern
                if metadata_path.exists():
                    # 验证JSON文件是否包含视频信息
                    if self._validate_metadata_file(str(metadata_path), video_filename):
                        return str(metadata_path)
                        
            return None
            
        except Exception as e:
            self.logger.error(f"查找元数据文件失败: {e}")
            return None
        
    def _validate_metadata_file(self, metadata_path: str, video_filename: str) -> bool:
        """验证元数据文件是否包含指定视频的信息。"""
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 检查是否包含视频文件名作为键
            if video_filename in data:
                # 验证元数据结构
                metadata = data[video_filename]
                if isinstance(metadata, dict) and 'title' in metadata and 'description' in metadata:
                    return True
                
            # 检查是否包含不带扩展名的文件名作为键
            video_base = os.path.splitext(video_filename)[0]
            if video_base in data:
                # 验证元数据结构
                metadata = data[video_base]
                if isinstance(metadata, dict) and 'title' in metadata and 'description' in metadata:
                    return True
                
            return False
            
        except (json.JSONDecodeError, FileNotFoundError, UnicodeDecodeError) as e:
            self.logger.error(f"验证元数据文件失败 {metadata_path}: {e}")
            return False
            
    def get_project_stats(self, project_name: str = None) -> dict:
        """获取项目统计信息。"""
        try:
            if project_name:
                project = self.project_repo.get_by_name_and_user(project_name, self.user_id)
                if not project:
                    return {}
                return self.task_repo.get_project_stats(project.id)
            else:
                return self.task_repo.get_user_stats(self.user_id)
        except Exception as e:
            self.logger.error(f"获取项目统计失败: {e}")
            return {}
    
    def _create_default_content_sources(self, project_id: int, project_path: Path):
        """为项目创建默认内容源。"""
        try:
            # 视频内容源
            video_dir = project_path / "output_video_music"
            if video_dir.exists():
                video_source_data = {
                    'project_id': project_id,
                    'name': 'Video Files',
                    'source_type': 'video',
                    'path_or_identifier': str(video_dir),
                    'total_items': 0,
                    'used_items': 0
                }
                self.content_source_repo.create(video_source_data)
            
            # JSON元数据内容源
            json_dir = project_path / "uploader_json"
            if json_dir.exists():
                json_source_data = {
                    'project_id': project_id,
                    'name': 'JSON Metadata',
                    'source_type': 'metadata',
                    'path_or_identifier': str(json_dir),
                    'total_items': 0,
                    'used_items': 0
                }
                self.content_source_repo.create(json_source_data)
                
        except Exception as e:
            self.logger.error(f"创建默认内容源失败: {e}")
    
    def _get_content_source(self, project_id: int, source_type: str, path: Path) -> ContentSource:
        """获取或创建内容源。"""
        try:
            # 查找现有内容源
            content_sources = self.content_source_repo.get_by_project(project_id)
            for source in content_sources:
                if source.source_type == source_type and Path(source.path_or_identifier) == path:
                    return source
            
            # 创建新内容源
            source_data = {
                'project_id': project_id,
                'name': f'{source_type.title()} Source',
                'source_type': source_type,
                'path_or_identifier': str(path),
                'total_items': 0,
                'used_items': 0
            }
            
            return self.content_source_repo.create(source_data)
            
        except Exception as e:
            self.logger.error(f"获取内容源失败: {e}")
            raise