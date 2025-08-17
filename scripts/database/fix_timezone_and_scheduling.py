#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复时区问题和任务调度逻辑

问题分析:
1. 任务创建时scheduled_at使用datetime.utcnow()，但没有考虑最佳发布时间
2. 所有任务都被设置为立即执行（当前UTC时间），导致大量过期任务
3. 缺少时区转换和最佳发布时间段的逻辑
4. 没有实现任务间隔分布，所有任务同时创建导致冲突

修复方案:
1. 实现智能调度算法，考虑最佳发布时间段
2. 添加时区转换逻辑
3. 实现任务间隔分布，避免同时发布
4. 更新现有过期任务的调度时间
"""

import os
import sys
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.db_manager import EnhancedDatabaseManager
from app.database.repository import PublishingTaskRepository
from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config

logger = get_logger(__name__)

class TaskSchedulingFixer:
    """任务调度修复器"""
    
    def __init__(self):
        self.config = get_enhanced_config()
        self.db_manager = EnhancedDatabaseManager()
        self.task_repo = PublishingTaskRepository(self.db_manager.get_session())
        
        # 时区配置
        self.timezone_offset = 8  # 北京时间 UTC+8
        
        # 最佳发布时间段（北京时间）
        self.optimal_hours = [
            (9, 11),   # 上午 9-11点
            (14, 16),  # 下午 2-4点  
            (19, 21)   # 晚上 7-9点
        ]
        
        # 调度配置 - 每天5-8条发布频率
        self.min_interval_minutes = 180  # 最小间隔3小时 (24小时/8条 = 3小时)
        self.max_interval_minutes = 288  # 最大间隔4.8小时 (24小时/5条 = 4.8小时)
        
    def fix_all_tasks(self) -> dict:
        """修复所有任务的调度时间"""
        logger.info("开始修复任务调度时间...")
        
        try:
            # 获取所有待处理的任务
            pending_tasks = self.task_repo.get_ready_tasks(
                filters={'status': 'pending'},
                limit=None
            )
            
            logger.info(f"找到 {len(pending_tasks)} 个待处理任务")
            
            if not pending_tasks:
                return {
                    'success': True,
                    'message': '没有需要修复的任务',
                    'fixed_count': 0
                }
            
            # 按项目分组任务
            tasks_by_project = {}
            for task in pending_tasks:
                project_name = task.project.name if task.project else 'unknown'
                if project_name not in tasks_by_project:
                    tasks_by_project[project_name] = []
                tasks_by_project[project_name].append(task)
            
            fixed_count = 0
            
            # 为每个项目的任务重新调度
            for project_name, tasks in tasks_by_project.items():
                logger.info(f"正在修复项目 '{project_name}' 的 {len(tasks)} 个任务")
                
                # 获取起始时间（下一个最佳时间段）
                start_time = self._get_next_optimal_time()
                
                # 为任务分配调度时间
                for i, task in enumerate(tasks):
                    # 计算这个任务的调度时间
                    scheduled_time = self._calculate_task_schedule_time(start_time, i)
                    
                    # 更新任务
                    success = self.task_repo.update(task.id, {
                        'scheduled_at': scheduled_time,
                        'updated_at': datetime.utcnow()
                    })
                    
                    if success:
                        fixed_count += 1
                        logger.debug(f"任务 {task.id} 调度时间已更新为: {scheduled_time}")
                    else:
                        logger.error(f"更新任务 {task.id} 失败")
            
            # 提交更改
            self.task_repo.session.commit()
            
            logger.info(f"任务调度修复完成，共修复 {fixed_count} 个任务")
            
            return {
                'success': True,
                'message': f'成功修复 {fixed_count} 个任务的调度时间',
                'fixed_count': fixed_count,
                'projects': list(tasks_by_project.keys())
            }
            
        except Exception as e:
            logger.error(f"修复任务调度时间失败: {e}")
            self.task_repo.session.rollback()
            return {
                'success': False,
                'message': f'修复失败: {str(e)}',
                'fixed_count': 0
            }
    
    def _get_next_optimal_time(self) -> datetime:
        """获取下一个最佳发布时间"""
        # 获取当前北京时间
        utc_now = datetime.utcnow()
        beijing_now = utc_now + timedelta(hours=self.timezone_offset)
        
        current_hour = beijing_now.hour
        current_date = beijing_now.date()
        
        # 查找今天剩余的最佳时间段
        for start_hour, end_hour in self.optimal_hours:
            if current_hour < start_hour:
                # 今天还有这个时间段
                target_hour = start_hour
                target_minute = random.randint(0, 30)  # 在时间段开始的前30分钟内
                
                beijing_time = datetime.combine(current_date, datetime.min.time()).replace(
                    hour=target_hour,
                    minute=target_minute,
                    second=0,
                    microsecond=0
                )
                
                # 转换回UTC时间
                utc_time = beijing_time - timedelta(hours=self.timezone_offset)
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
            microsecond=0
        )
        
        # 转换回UTC时间
        utc_time = beijing_time - timedelta(hours=self.timezone_offset)
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
        
        # 确保调度时间在合理的时间段内（避免深夜发布）
        return self._adjust_to_optimal_time(scheduled_time)
    
    def _adjust_to_optimal_time(self, target_time: datetime) -> datetime:
        """调整到最佳时间段"""
        # 转换到北京时间检查
        beijing_time = target_time + timedelta(hours=self.timezone_offset)
        hour = beijing_time.hour
        
        # 如果在深夜时间段（23点-6点），调整到第二天早上
        if hour >= 23 or hour < 6:
            # 调整到第二天早上9点
            next_day = beijing_time.date() + timedelta(days=1)
            beijing_adjusted = datetime.combine(next_day, datetime.min.time()).replace(
                hour=9,
                minute=random.randint(0, 30),
                second=0,
                microsecond=0
            )
            
            # 转换回UTC
            return beijing_adjusted - timedelta(hours=self.timezone_offset)
        
        return target_time
    
    def show_scheduling_preview(self, limit: int = 10) -> None:
        """显示调度预览"""
        logger.info("生成调度预览...")
        
        # 获取一些待处理任务作为示例
        pending_tasks = self.task_repo.get_ready_tasks(
            filters={'status': 'pending'},
            limit=limit
        )
        
        if not pending_tasks:
            print("没有待处理的任务")
            return
        
        print(f"\n📅 调度预览（前{len(pending_tasks)}个任务）:")
        print("=" * 80)
        
        start_time = self._get_next_optimal_time()
        
        for i, task in enumerate(pending_tasks):
            scheduled_time = self._calculate_task_schedule_time(start_time, i)
            beijing_time = scheduled_time + timedelta(hours=self.timezone_offset)
            
            print(f"{i+1:2d}. 任务 {task.id:3d} | {Path(task.media_path).name[:30]:30s} | "
                  f"UTC: {scheduled_time.strftime('%m-%d %H:%M')} | "
                  f"北京: {beijing_time.strftime('%m-%d %H:%M')}")
        
        print("=" * 80)
        print(f"起始时间: UTC {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"起始时间: 北京 {(start_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    """主函数"""
    print("🔧 Twitter任务调度修复工具")
    print("=" * 50)
    
    fixer = TaskSchedulingFixer()
    
    # 显示当前问题
    print("\n📊 当前问题分析:")
    pending_tasks = fixer.task_repo.get_ready_tasks(
        filters={'status': 'pending'},
        limit=None
    )
    
    if pending_tasks:
        expired_count = 0
        now = datetime.utcnow()
        
        for task in pending_tasks:
            if task.scheduled_at < now:
                expired_count += 1
        
        print(f"   总待处理任务: {len(pending_tasks)}")
        print(f"   已过期任务: {expired_count}")
        print(f"   过期比例: {expired_count/len(pending_tasks)*100:.1f}%")
        
        # 显示调度预览
        fixer.show_scheduling_preview(10)
        
        # 询问是否执行修复
        print("\n❓ 是否执行修复？(y/N): ", end="")
        response = input().strip().lower()
        
        if response in ['y', 'yes']:
            print("\n🚀 开始执行修复...")
            result = fixer.fix_all_tasks()
            
            if result['success']:
                print(f"✅ {result['message']}")
                print(f"📈 修复的项目: {', '.join(result.get('projects', []))}")
            else:
                print(f"❌ {result['message']}")
        else:
            print("❌ 取消修复操作")
    else:
        print("   没有待处理的任务")

if __name__ == "__main__":
    main()