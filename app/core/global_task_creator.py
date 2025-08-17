#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局任务创建器 - 实现跨项目的每日任务总数限制

主要功能：
1. 全局任务数量控制 - 确保每日发布任务总数不超过配置限制
2. 按优先级分配任务配额 - 根据项目优先级分配每日任务数量
3. 智能任务调度 - 在最佳时间段内分布任务
4. 项目间负载均衡 - 避免单个项目占用过多资源
"""

import os
import sys
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 移除不存在的导入
from app.database.repository import ProjectRepository, PublishingTaskRepository, ContentSourceRepository
from app.database.models import Project, PublishingTask
from app.utils.enhanced_config import get_enhanced_config
from datetime import datetime, timedelta
import pytz
from app.core.content_generator import ContentGenerator

class GlobalTaskCreator:
    """全局任务创建器 - 实现跨项目的任务数量控制"""
    
    def __init__(self, config_path: str = None):
        """初始化全局任务创建器"""
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self.config = get_enhanced_config()
        
        # 初始化数据库管理器
        from app.database.db_manager import EnhancedDatabaseManager
        self.db_manager = EnhancedDatabaseManager()
        
        # 调度配置
        scheduling_config = self.config.get('scheduling', {})
        self.daily_max_tasks = scheduling_config.get('daily_max_tasks', 6)
        self.daily_min_tasks = scheduling_config.get('daily_min_tasks', 5)
        self.interval_hours = scheduling_config.get('interval_hours', 4)
        self.interval_minutes_min = scheduling_config.get('interval_minutes_min', 240)
        self.interval_minutes_max = scheduling_config.get('interval_minutes_max', 360)
        self.optimal_hours = scheduling_config.get('optimal_hours', [9, 12, 15, 18, 21])
        
        # 时区设置
        timezone_name = self.config.get('timezone', 'Asia/Shanghai')
        self.timezone = pytz.timezone(timezone_name)
        
        # 内容生成器
        self.content_generator = ContentGenerator()
        
        self.logger.info(f"全局任务创建器初始化完成 - 每日任务限制: {self.daily_min_tasks}-{self.daily_max_tasks}")
    
    def create_daily_tasks(self, force: bool = False) -> Dict[str, Any]:
        """创建每日任务 - 全局控制版本"""
        self.logger.info("开始创建每日任务（全局控制模式）")
        
        result = {
            'success': True,
            'total_tasks_created': 0,
            'projects_processed': 0,
            'project_details': [],
            'errors': []
        }
        
        try:
            with self.db_manager.get_session_context() as session:
                project_repo = ProjectRepository(session)
                task_repo = PublishingTaskRepository(session)
                
                # 1. 获取所有活跃项目（按优先级排序）
                active_projects = project_repo.get_active_projects_with_priority()
                
                if not active_projects:
                    self.logger.warning("没有找到活跃项目")
                    result['success'] = False
                    result['errors'].append("没有活跃项目")
                    return result
                
                self.logger.info(f"找到 {len(active_projects)} 个活跃项目")
                
                # 2. 计算今日已创建的任务数量
                today_start = datetime.now(self.timezone).replace(hour=0, minute=0, second=0, microsecond=0)
                tomorrow_start = today_start + timedelta(days=1)
                
                existing_tasks_count = self._count_existing_tasks_today(task_repo, today_start, tomorrow_start)
                self.logger.info(f"今日已存在任务数量: {existing_tasks_count}")
                
                # 3. 计算今日还需要创建的任务数量
                target_daily_tasks = random.randint(self.daily_min_tasks, self.daily_max_tasks)
                
                if force:
                    # 强制模式下，无论当前任务数量如何，都创建最少数量的任务
                    remaining_tasks = self.daily_min_tasks
                    self.logger.info(f"强制模式：当前已有 {existing_tasks_count} 个任务，强制创建 {remaining_tasks} 个新任务")
                else:
                    remaining_tasks = max(0, target_daily_tasks - existing_tasks_count)
                    
                    if remaining_tasks == 0:
                        self.logger.info(f"今日任务已达到目标数量 ({existing_tasks_count}/{target_daily_tasks})，无需创建新任务")
                        return result
                
                self.logger.info(f"今日目标任务数: {target_daily_tasks}, 还需创建: {remaining_tasks}")
                
                # 4. 按优先级分配任务配额
                project_quotas = self._allocate_task_quotas(active_projects, remaining_tasks)
                
                # 5. 为每个项目创建任务
                for project, quota in project_quotas.items():
                    if quota > 0:
                        project_result = self._create_tasks_for_project(
                            session, project, quota, today_start, tomorrow_start, force
                        )
                        
                        result['project_details'].append(project_result)
                        result['total_tasks_created'] += project_result['tasks_created']
                        result['projects_processed'] += 1
                        
                        if project_result['errors']:
                            result['errors'].extend(project_result['errors'])
                
                session.commit()
                
                self.logger.info(f"全局任务创建完成 - 总计创建 {result['total_tasks_created']} 个任务")
                
        except Exception as e:
            self.logger.error(f"创建每日任务时发生错误: {str(e)}", exc_info=True)
            result['success'] = False
            result['errors'].append(f"创建任务失败: {str(e)}")
        
        return result
    
    def _count_existing_tasks_today(self, task_repo: PublishingTaskRepository, 
                                   today_start: datetime, tomorrow_start: datetime) -> int:
        """统计今日已存在的任务数量"""
        try:
            # 查询今日已安排的所有任务（包括pending、in_progress、completed等状态）
            existing_tasks = task_repo.session.query(PublishingTask).filter(
                PublishingTask.scheduled_at >= today_start,
                PublishingTask.scheduled_at < tomorrow_start
            ).count()
            
            return existing_tasks
        except Exception as e:
            self.logger.error(f"统计今日任务数量时发生错误: {str(e)}")
            return 0
    
    def _allocate_task_quotas(self, projects: List[Project], total_tasks: int) -> Dict[Project, int]:
        """按优先级分配任务配额"""
        quotas = {}
        
        if not projects or total_tasks <= 0:
            return quotas
        
        # 计算优先级权重
        project_weights = []
        for project in projects:
            # 优先级越高权重越大，默认优先级为1
            priority = getattr(project, 'priority', 1) or 1
            weight = max(1, priority)  # 确保权重至少为1
            project_weights.append(weight)
        
        total_weight = sum(project_weights)
        
        # 按权重分配任务
        allocated_tasks = 0
        for i, project in enumerate(projects):
            if i == len(projects) - 1:  # 最后一个项目获得剩余所有任务
                quota = total_tasks - allocated_tasks
            else:
                # 按权重比例分配
                quota = int((project_weights[i] / total_weight) * total_tasks)
            
            quotas[project] = max(0, quota)  # 确保配额不为负数
            allocated_tasks += quota
            
            self.logger.info(f"项目 {project.name} (优先级: {getattr(project, 'priority', 1)}) 分配任务配额: {quota}")
        
        return quotas
    
    def _create_tasks_for_project(self, session, project: Project, quota: int, 
                                 today_start: datetime, tomorrow_start: datetime, force: bool = False) -> Dict[str, Any]:
        """为单个项目创建任务"""
        result = {
            'project_id': project.id,
            'project_name': project.name,
            'quota': quota,
            'tasks_created': 0,
            'tasks_skipped': 0,
            'errors': []
        }
        
        try:
            source_repo = ContentSourceRepository(session)
            task_repo = PublishingTaskRepository(session)
            
            # 获取项目的内容源
            content_sources = source_repo.list_project_sources(project.id)
            if not content_sources:
                error_msg = f"项目 {project.name} 没有可用的内容源"
                self.logger.warning(error_msg)
                result['errors'].append(error_msg)
                return result
            
            # 获取可用的媒体文件
            available_media = self._get_available_media_files(content_sources)
            self.logger.info(f"项目 {project.name} 获取到 {len(available_media)} 个可用媒体文件")
            if not available_media:
                error_msg = f"项目 {project.name} 没有可用的媒体文件"
                self.logger.warning(error_msg)
                result['errors'].append(error_msg)
                return result
            
            # 生成任务时间点
            task_times = self._generate_task_schedule_times(quota, today_start, tomorrow_start)
            self.logger.info(f"项目 {project.name} 生成了 {len(task_times)} 个任务时间点，配额: {quota}")
            self.logger.debug(f"任务时间点: {task_times}")
            
            # 创建任务
            for i, scheduled_time in enumerate(task_times):
                self.logger.debug(f"处理第 {i+1} 个任务，时间: {scheduled_time}")
                if i >= len(available_media):
                    self.logger.warning(f"项目 {project.name} 媒体文件不足，跳过剩余任务")
                    result['tasks_skipped'] += quota - i
                    break
                
                media_file = available_media[i]
                
                # 检查是否已存在相同的任务（force模式下跳过检查）
                if not force:
                    existing_task = task_repo.session.query(PublishingTask).filter(
                        PublishingTask.project_id == project.id,
                        PublishingTask.media_path == media_file['path'],
                        PublishingTask.status.in_(['pending', 'in_progress'])
                    ).first()
                    
                    if existing_task:
                        self.logger.debug(f"任务已存在，跳过: {media_file['path']}")
                        result['tasks_skipped'] += 1
                        continue
                else:
                    self.logger.debug(f"强制模式：跳过重复检查，使用媒体文件: {media_file['path']}")
                
                # 生成内容
                content_data = self._generate_task_content(media_file, project)
                
                # 在强制模式下，先删除可能存在的重复任务
                if force:
                    existing_task = task_repo.session.query(PublishingTask).filter(
                        PublishingTask.project_id == project.id,
                        PublishingTask.media_path == media_file['path']
                    ).first()
                    
                    if existing_task:
                        self.logger.debug(f"强制模式：删除现有任务 {existing_task.id} 以避免唯一约束冲突")
                        task_repo.session.delete(existing_task)
                        task_repo.session.flush()  # 确保删除操作立即生效
                
                # 创建任务
                task = task_repo.create_task(
                    project_id=project.id,
                    source_id=media_file['source_id'],
                    media_path=media_file['path'],
                    content_data=content_data,
                    scheduled_at=scheduled_time,
                    priority=getattr(project, 'priority', 1) or 1
                )
                
                result['tasks_created'] += 1
                self.logger.debug(f"为项目 {project.name} 创建任务: {task.id} (计划时间: {scheduled_time})")
            
        except Exception as e:
            error_msg = f"为项目 {project.name} 创建任务时发生错误: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            result['errors'].append(error_msg)
        
        return result
    
    def _get_available_media_files(self, content_sources) -> List[Dict[str, Any]]:
        """获取可用的媒体文件列表"""
        media_files = []
        
        self.logger.info(f"开始扫描 {len(content_sources)} 个内容源")
        
        for source in content_sources:
            self.logger.info(f"检查内容源: {source.source_type}, 路径: {source.path_or_identifier}, 激活状态: {source.is_active}")
            
            if not source.is_active:
                self.logger.info(f"跳过未激活的内容源: {source.path_or_identifier}")
                continue
            
            source_path = Path(source.path_or_identifier)
            if not source_path.exists():
                self.logger.warning(f"内容源路径不存在: {source_path}")
                continue
            
            self.logger.info(f"内容源路径存在: {source_path}")
            
            # 支持的媒体文件格式
            supported_formats = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov'}
            
            if source_path.is_file() and source_path.suffix.lower() in supported_formats:
                self.logger.info(f"找到单个媒体文件: {source_path}")
                media_files.append({
                    'source_id': source.id,
                    'path': str(source_path),
                    'type': 'image' if source_path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif'} else 'video'
                })
            elif source_path.is_dir():
                self.logger.info(f"扫描目录: {source_path}")
                file_count = 0
                for file_path in source_path.rglob('*'):
                    if file_path.is_file() and file_path.suffix.lower() in supported_formats:
                        file_count += 1
                        media_files.append({
                            'source_id': source.id,
                            'path': str(file_path),
                            'type': 'image' if file_path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif'} else 'video'
                        })
                self.logger.info(f"在目录 {source_path} 中找到 {file_count} 个媒体文件")
            else:
                self.logger.warning(f"内容源既不是文件也不是目录: {source_path}")
        
        # 随机打乱文件顺序
        random.shuffle(media_files)
        self.logger.info(f"总共找到 {len(media_files)} 个可用媒体文件")
        return media_files
    
    def _generate_task_schedule_times(self, count: int, start_time: datetime, end_time: datetime) -> List[datetime]:
        """生成任务调度时间点"""
        if count <= 0:
            return []
        
        schedule_times = []
        
        # 在最佳时间段内分布任务
        for i in range(count):
            # 选择一个最佳时间段
            optimal_hour = random.choice(self.optimal_hours)
            
            # 在该小时内随机选择分钟
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            
            # 构造时间点
            scheduled_time = start_time.replace(
                hour=optimal_hour,
                minute=minute,
                second=second,
                microsecond=0
            )
            
            # 确保时间在有效范围内
            if start_time <= scheduled_time < end_time:
                schedule_times.append(scheduled_time)
        
        # 按时间排序
        schedule_times.sort()
        
        # 如果时间点不足，补充一些随机时间
        while len(schedule_times) < count:
            random_time = start_time + timedelta(
                seconds=random.randint(0, int((end_time - start_time).total_seconds()))
            )
            if random_time not in schedule_times:
                schedule_times.append(random_time)
        
        return sorted(schedule_times[:count])
    
    def _generate_task_content(self, media_file: Dict[str, Any], project: Project) -> Dict[str, Any]:
        """生成任务内容"""
        try:
            # 从媒体文件路径推导元数据文件路径
            media_path = media_file['path']
            video_filename = os.path.basename(media_path)
            
            # 查找项目目录下的JSON文件
            project_dir = Path(media_path).parent.parent  # 从output_video_music回到项目根目录
            json_dir = project_dir / 'uploader_json'
            
            metadata_path = None
            if json_dir.exists():
                # 查找JSON文件
                json_files = list(json_dir.glob('*.json'))
                if json_files:
                    metadata_path = str(json_files[0])  # 使用第一个找到的JSON文件
            
            if metadata_path:
                # 使用内容生成器生成内容
                content = self.content_generator.generate_content(
                    video_filename=video_filename,
                    metadata_path=metadata_path,
                    language='zh',  # 默认中文
                    source_config=getattr(project, 'config', {}) or {}
                )
                
                if content:
                    return {
                        'text': content,
                        'hashtags': ['auto', 'content'],
                        'media_type': media_file['type'],
                        'generated_at': datetime.now().isoformat()
                    }
            
            # 如果没有找到JSON文件或内容生成失败，使用默认内容
            return {
                'text': f'自动发布内容 - {video_filename.split(".")[0]}',
                'hashtags': ['auto', 'content'],
                'media_type': media_file['type'],
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"生成内容时发生错误: {str(e)}")
            return {
                'text': f"自动发布内容 - {Path(media_file['path']).stem}",
                'hashtags': ['auto', 'content'],
                'media_type': media_file['type'],
                'generated_at': datetime.now().isoformat()
            }
    
    def preview_daily_tasks(self, force: bool = False) -> Dict[str, Any]:
        """预览每日任务创建计划 - 干运行模式"""
        self.logger.info("预览每日任务创建计划（干运行模式）")
        
        result = {
            'success': True,
            'created_count': 0,
            'total_today': 0,
            'project_allocations': {},
            'message': ''
        }
        
        try:
            with self.db_manager.get_session_context() as session:
                project_repo = ProjectRepository(session)
                task_repo = PublishingTaskRepository(session)
                
                # 1. 获取所有活跃项目（按优先级排序）
                active_projects = project_repo.get_active_projects_with_priority()
                
                if not active_projects:
                    result['success'] = False
                    result['message'] = "没有活跃项目"
                    return result
                
                # 2. 计算今日已创建的任务数量
                today_start = datetime.now(self.timezone).replace(hour=0, minute=0, second=0, microsecond=0)
                tomorrow_start = today_start + timedelta(days=1)
                
                existing_tasks_count = self._count_existing_tasks_today(task_repo, today_start, tomorrow_start)
                result['total_today'] = existing_tasks_count
                
                # 3. 计算今日还需要创建的任务数量
                target_daily_tasks = random.randint(self.daily_min_tasks, self.daily_max_tasks)
                
                if force:
                    # 强制模式下，无论当前任务数量如何，都创建最少数量的任务
                    remaining_tasks = self.daily_min_tasks
                    self.logger.info(f"强制模式：当前已有 {existing_tasks_count} 个任务，强制创建 {remaining_tasks} 个新任务")
                else:
                    remaining_tasks = max(0, target_daily_tasks - existing_tasks_count)
                    
                    if remaining_tasks == 0:
                        result['message'] = f"今日任务已达到目标数量 ({existing_tasks_count}/{target_daily_tasks})，无需创建新任务"
                        return result
                
                result['created_count'] = remaining_tasks
                
                # 4. 按优先级分配任务配额
                project_quotas = self._allocate_task_quotas(active_projects, remaining_tasks)
                
                # 5. 生成项目分配预览
                for project, quota in project_quotas.items():
                    if quota > 0:
                        result['project_allocations'][project.name] = quota
                
                result['message'] = f"计划创建 {remaining_tasks} 个任务，目标总数: {target_daily_tasks}"
                
        except Exception as e:
            self.logger.error(f"预览每日任务时发生错误: {str(e)}", exc_info=True)
            result['success'] = False
            result['message'] = f"预览失败: {str(e)}"
        
        return result
    
    def get_daily_task_summary(self) -> Dict[str, Any]:
        """获取每日任务摘要"""
        try:
            with self.db_manager.get_session_context() as session:
                task_repo = PublishingTaskRepository(session)
                project_repo = ProjectRepository(session)
                
                # 今日时间范围
                today_start = datetime.now(self.timezone).replace(hour=0, minute=0, second=0, microsecond=0)
                tomorrow_start = today_start + timedelta(days=1)
                
                # 统计今日任务
                today_tasks = task_repo.session.query(PublishingTask).filter(
                    PublishingTask.scheduled_at >= today_start,
                    PublishingTask.scheduled_at < tomorrow_start
                ).all()
                
                # 按项目分组统计
                project_stats = {}
                for task in today_tasks:
                    project_id = task.project_id
                    if project_id not in project_stats:
                        project = project_repo.get_project_by_id(project_id)
                        project_stats[project_id] = {
                            'project_name': project.name if project else f'Project-{project_id}',
                            'total': 0,
                            'pending': 0,
                            'in_progress': 0,
                            'completed': 0,
                            'failed': 0
                        }
                    
                    project_stats[project_id]['total'] += 1
                    project_stats[project_id][task.status] = project_stats[project_id].get(task.status, 0) + 1
                
                return {
                    'date': today_start.strftime('%Y-%m-%d'),
                    'total_tasks': len(today_tasks),
                    'target_range': f"{self.daily_min_tasks}-{self.daily_max_tasks}",
                    'project_stats': project_stats,
                    'active_projects': len(project_repo.get_active_projects())
                }
                
        except Exception as e:
            self.logger.error(f"获取每日任务摘要时发生错误: {str(e)}")
            return {'error': str(e)}


def main():
    """主函数 - 用于测试"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    creator = GlobalTaskCreator()
    
    # 获取当前摘要
    print("=== 当前每日任务摘要 ===")
    summary = creator.get_daily_task_summary()
    print(f"日期: {summary.get('date')}")
    print(f"总任务数: {summary.get('total_tasks')}")
    print(f"目标范围: {summary.get('target_range')}")
    print(f"活跃项目数: {summary.get('active_projects')}")
    
    # 创建新任务
    print("\n=== 创建每日任务 ===")
    result = creator.create_daily_tasks()
    print(f"创建结果: {result}")


if __name__ == '__main__':
    main()