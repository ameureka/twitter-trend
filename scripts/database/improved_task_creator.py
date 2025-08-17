#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进的任务创建器 - 使用正确的时区调度逻辑

主要改进:
1. 正确的时区处理
2. 智能调度算法
3. 避免任务冲突
4. 最佳发布时间段
"""

import os
import sys
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.db_manager import EnhancedDatabaseManager
from app.database.repository import PublishingTaskRepository, ProjectRepository
from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config

logger = get_logger(__name__)

class ImprovedTaskCreator:
    """改进的任务创建器"""
    
    def __init__(self):
        self.config = get_enhanced_config()
        self.db_manager = EnhancedDatabaseManager()
        self.task_repo = PublishingTaskRepository(self.db_manager.get_session())
        self.project_repo = ProjectRepository(self.db_manager.get_session())
        
        # 时区配置
        self.timezone_offset = 8  # 北京时间 UTC+8
        
        # 最佳发布时间段（北京时间）
        self.optimal_hours = [
            (9, 11),   # 上午 9-11点
            (14, 16),  # 下午 2-4点  
            (19, 21)   # 晚上 7-9点
        ]
        
        # 调度配置 - 从配置文件读取
        scheduling_config = self.config.get('scheduling', {})
        self.min_interval_minutes = scheduling_config.get('interval_minutes_min', 240)  # 默认最小间隔4小时
        self.max_interval_minutes = scheduling_config.get('interval_minutes_max', 360)  # 默认最大间隔6小时
        self.max_daily_tasks = scheduling_config.get('daily_max_tasks', 6)              # 默认每日最大任务数
        self.min_daily_tasks = scheduling_config.get('daily_min_tasks', 5)              # 默认每日最小任务数
        self.blackout_hours = scheduling_config.get('blackout_hours', [0, 1, 2, 3, 4, 5, 6])  # 静默时间
        self.enable_smart_scheduling = scheduling_config.get('enable_smart_scheduling', True)  # 智能调度
        
        # 从配置文件读取最佳发布时间，如果没有配置则使用默认值
        optimal_hours_config = scheduling_config.get('optimal_hours', [9, 12, 15, 18, 21])
        # 将单个小时转换为时间段格式
        if optimal_hours_config and isinstance(optimal_hours_config[0], int):
            # 如果配置的是单个小时，转换为时间段
            self.optimal_hours = [(hour, hour + 1) for hour in optimal_hours_config]
        else:
            # 保持原有的时间段格式
            self.optimal_hours = [
                (9, 11),   # 上午 9-11点
                (14, 16),  # 下午 2-4点  
                (19, 21)   # 晚上 7-9点
            ]
        
    def create_tasks_for_project(self, project_name: str, media_files: List[str], 
                                content_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """为项目创建任务"""
        logger.info(f"开始为项目 '{project_name}' 创建任务...")
        
        try:
            # 获取项目
            project = self.project_repo.get_project_by_name(1, project_name)  # 假设用户ID为1
            if not project:
                return {
                    'success': False,
                    'message': f'项目 "{project_name}" 不存在',
                    'created_count': 0
                }
            
            # 检查现有任务数量
            existing_tasks = self.task_repo.get_ready_tasks(
                filters={'project_id': project.id, 'status': 'pending'},
                limit=None
            )
            
            logger.info(f"项目 '{project_name}' 现有 {len(existing_tasks)} 个待处理任务")
            
            # 计算起始调度时间
            start_time = self._calculate_start_time(existing_tasks)
            
            created_count = 0
            skipped_count = 0
            
            # 计算每日任务数量限制
            daily_task_limit = random.randint(self.min_daily_tasks, self.max_daily_tasks)
            logger.info(f"本次创建任务数量限制: {daily_task_limit} 条/天")
            
            # 限制创建的任务数量
            max_tasks_to_create = min(len(media_files), daily_task_limit * 7)  # 最多创建一周的任务
            
            for i, media_file in enumerate(media_files[:max_tasks_to_create]):
                # 检查任务是否已存在
                existing_task = self._check_task_exists(project.id, media_file)
                if existing_task:
                    logger.debug(f"任务已存在，跳过: {media_file}")
                    skipped_count += 1
                    continue
                
                # 计算调度时间
                scheduled_time = self._calculate_task_schedule_time(
                    start_time, 
                    len(existing_tasks) + created_count
                )
                
                # 创建任务
                task_content = content_data or self._generate_default_content(media_file)
                
                task = self.task_repo.create_task(
                    project_id=project.id,
                    source_id=1,  # 假设source_id为1
                    media_path=media_file,
                    content_data=task_content,
                    scheduled_at=scheduled_time,
                    priority=0
                )
                
                if task:
                    created_count += 1
                    beijing_time = scheduled_time + timedelta(hours=self.timezone_offset)
                    logger.info(f"创建任务 {task.id}: {Path(media_file).name} -> "
                              f"UTC: {scheduled_time.strftime('%m-%d %H:%M')}, "
                              f"北京: {beijing_time.strftime('%m-%d %H:%M')}")
                else:
                    logger.error(f"创建任务失败: {media_file}")
            
            # 如果有剩余文件未处理，记录信息
            remaining_files = len(media_files) - max_tasks_to_create
            if remaining_files > 0:
                logger.info(f"剩余 {remaining_files} 个文件未创建任务（受每日任务数量限制）")
            
            # 提交更改
            self.task_repo.session.commit()
            
            logger.info(f"任务创建完成: 新建 {created_count} 个，跳过 {skipped_count} 个")
            
            return {
                'success': True,
                'message': f'成功创建 {created_count} 个任务，跳过 {skipped_count} 个已存在任务',
                'created_count': created_count,
                'skipped_count': skipped_count,
                'project_name': project_name
            }
            
        except Exception as e:
            logger.error(f"创建任务失败: {e}")
            self.task_repo.session.rollback()
            return {
                'success': False,
                'message': f'创建任务失败: {str(e)}',
                'created_count': 0
            }
    
    def _calculate_start_time(self, existing_tasks: List) -> datetime:
        """计算起始调度时间"""
        if not existing_tasks:
            # 如果没有现有任务，从下一个最佳时间开始
            return self._get_next_optimal_time()
        
        # 找到最后一个任务的调度时间
        latest_task = max(existing_tasks, key=lambda t: t.scheduled_at)
        latest_time = latest_task.scheduled_at
        
        # 在最后任务时间基础上添加间隔
        next_time = latest_time + timedelta(minutes=random.randint(30, 60))
        
        # 确保在合理的时间段内
        return self._adjust_to_optimal_time(next_time)
    
    def _get_next_optimal_time(self) -> datetime:
        """获取下一个最佳发布时间"""
        # 使用timezone-aware datetime
        utc_now = datetime.now(timezone.utc)
        beijing_now = utc_now + timedelta(hours=self.timezone_offset)
        
        current_hour = beijing_now.hour
        current_date = beijing_now.date()
        
        # 查找今天剩余的最佳时间段
        for start_hour, end_hour in self.optimal_hours:
            if current_hour < start_hour:
                # 今天还有这个时间段
                target_hour = start_hour
                target_minute = random.randint(0, 30)
                
                beijing_time = datetime.combine(current_date, datetime.min.time()).replace(
                    hour=target_hour,
                    minute=target_minute,
                    second=0,
                    microsecond=0,
                    tzinfo=timezone(timedelta(hours=self.timezone_offset))
                )
                
                # 转换回UTC时间
                utc_time = beijing_time.astimezone(timezone.utc).replace(tzinfo=None)
                return utc_time
        
        # 如果今天没有合适的时间段，使用明天的第一个时间段
        tomorrow = current_date + timedelta(days=1)
        start_hour, end_hour = self.optimal_hours[0]
        target_hour = start_hour
        target_minute = random.randint(0, 30)
        
        beijing_time = datetime.combine(tomorrow, datetime.min.time()).replace(
            hour=target_hour,
            minute=target_minute,
            second=0,
            microsecond=0,
            tzinfo=timezone(timedelta(hours=self.timezone_offset))
        )
        
        # 转换回UTC时间
        utc_time = beijing_time.astimezone(timezone.utc).replace(tzinfo=None)
        return utc_time
    
    def _calculate_task_schedule_time(self, base_time: datetime, task_index: int) -> datetime:
        """计算任务的具体调度时间"""
        # 基础间隔时间
        base_interval = random.randint(self.min_interval_minutes, self.max_interval_minutes)
        
        # 为每个任务添加递增的时间间隔
        total_minutes = task_index * base_interval
        
        # 添加小的随机抖动（±5分钟）
        jitter_minutes = random.randint(-5, 5)
        total_minutes += jitter_minutes
        
        # 确保不小于0
        total_minutes = max(0, total_minutes)
        
        scheduled_time = base_time + timedelta(minutes=total_minutes)
        
        # 确保调度时间在合理的时间段内
        return self._adjust_to_optimal_time(scheduled_time)
    
    def _adjust_to_optimal_time(self, target_time: datetime) -> datetime:
        """调整到最佳时间段"""
        # 转换到北京时间检查
        beijing_time = target_time + timedelta(hours=self.timezone_offset)
        hour = beijing_time.hour
        
        # 如果在静默时间段，调整到下一个最佳时间
        if hour in self.blackout_hours:
            # 找到下一个非静默时间
            next_hour = hour
            while next_hour in self.blackout_hours:
                next_hour = (next_hour + 1) % 24
            
            # 如果跨天了，调整到第二天
            if next_hour <= hour:
                next_day = beijing_time.date() + timedelta(days=1)
                beijing_adjusted = datetime.combine(next_day, datetime.min.time()).replace(
                    hour=next_hour,
                    minute=random.randint(0, 30),
                    second=0,
                    microsecond=0
                )
            else:
                beijing_adjusted = beijing_time.replace(
                    hour=next_hour,
                    minute=random.randint(0, 30),
                    second=0,
                    microsecond=0
                )
            
            # 转换回UTC
            return beijing_adjusted - timedelta(hours=self.timezone_offset)
        
        return target_time
    
    def _check_task_exists(self, project_id: int, media_path: str) -> bool:
        """检查任务是否已存在"""
        existing_tasks = self.task_repo.get_ready_tasks(
            filters={
                'project_id': project_id,
                'media_path': media_path
            },
            limit=1
        )
        return len(existing_tasks) > 0
    
    def _generate_default_content(self, media_file: str) -> Dict[str, Any]:
        """生成默认内容数据"""
        file_name = Path(media_file).stem
        return {
            'text': f'🎵 {file_name} #music #trending',
            'hashtags': ['music', 'trending'],
            'media_type': 'video'
        }
    
    def preview_schedule(self, project_name: str, media_files: List[str], limit: int = 10) -> None:
        """预览调度计划"""
        logger.info(f"生成项目 '{project_name}' 的调度预览...")
        
        # 获取项目
        project = self.project_repo.get_project_by_name(1, project_name)
        if not project:
            print(f"❌ 项目 '{project_name}' 不存在")
            return
        
        # 获取现有任务
        existing_tasks = self.task_repo.get_ready_tasks(
            filters={'project_id': project.id, 'status': 'pending'},
            limit=None
        )
        
        # 计算起始时间
        start_time = self._calculate_start_time(existing_tasks)
        
        print(f"\n📅 项目 '{project_name}' 调度预览（前{min(limit, len(media_files))}个任务）:")
        print("=" * 80)
        print(f"现有待处理任务: {len(existing_tasks)} 个")
        print(f"起始调度时间: UTC {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"起始调度时间: 北京 {(start_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        for i, media_file in enumerate(media_files[:limit]):
            scheduled_time = self._calculate_task_schedule_time(
                start_time, 
                len(existing_tasks) + i
            )
            beijing_time = scheduled_time + timedelta(hours=self.timezone_offset)
            
            file_name = Path(media_file).name
            print(f"{i+1:2d}. {file_name[:40]:40s} | "
                  f"UTC: {scheduled_time.strftime('%m-%d %H:%M')} | "
                  f"北京: {beijing_time.strftime('%m-%d %H:%M')}")
        
        print("=" * 80)

def main():
    """主函数"""
    print("🚀 改进的Twitter任务创建器")
    print("=" * 50)
    
    creator = ImprovedTaskCreator()
    
    # 示例：为项目创建任务
    project_name = "maker_music_chuangxinyewu"
    media_files = [
        "test_video1.mp4",
        "test_video2.mp4",
        "test_video3.mp4",
        "test_video4.mp4",
        "test_video5.mp4"
    ]
    
    # 预览调度
    creator.preview_schedule(project_name, media_files)
    
    # 询问是否创建任务
    print("\n❓ 是否创建这些任务？(y/N): ", end="")
    response = input().strip().lower()
    
    if response in ['y', 'yes']:
        print("\n🚀 开始创建任务...")
        result = creator.create_tasks_for_project(project_name, media_files)
        
        if result['success']:
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result['message']}")
    else:
        print("❌ 取消创建任务")

if __name__ == "__main__":
    main()