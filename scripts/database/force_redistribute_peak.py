#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强制重新分布峰值时段任务脚本

该脚本专门用于处理特定时段（如09:00）的高密度任务，
将其强制分散到其他时段以实现更均匀的分布。
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pytz
import random
from typing import List, Dict, Tuple, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.repository import PublishingTaskRepository
from app.database.models import PublishingTask
from app.database.database import DatabaseManager
from app.utils.enhanced_config import get_enhanced_config
from sqlalchemy import func

class ForcePeakRedistributor:
    """峰值时段任务重新分布器"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 默认数据库路径
            db_path = project_root / 'data' / 'twitter_publisher.db'
        
        # 数据库连接
        db_url = f'sqlite:///{db_path}'
        self.db_manager = DatabaseManager(db_url)
        self.db_manager.create_tables()
        self.session = self.db_manager.get_session()
        
        # 初始化仓库
        self.task_repo = PublishingTaskRepository(self.session)
        
        # 从配置文件读取参数
        scheduling_config = get_enhanced_config().get('scheduling', {})
        self.blackout_hours = scheduling_config.get('blackout_hours', [0, 1, 2, 3, 4, 5, 6])
        self.min_interval_minutes = scheduling_config.get('interval_minutes_min', 180)
        
        print(f"配置信息: 静默时间={self.blackout_hours}, 最小间隔={self.min_interval_minutes}分钟")
    
    def get_peak_hour_tasks(self, target_hour: int = 9) -> List[Dict]:
        """获取指定小时的所有待发布任务"""
        # 使用SQLAlchemy查询
        tasks = self.session.query(PublishingTask).filter(
            PublishingTask.status == 'pending',
            func.strftime('%H', func.datetime(PublishingTask.scheduled_at, '+8 hours')) == f'{target_hour:02d}'
        ).order_by(PublishingTask.priority.desc(), PublishingTask.scheduled_at.asc()).all()
        
        result = []
        for task in tasks:
            result.append({
                'id': task.id,
                'scheduled_at': task.scheduled_at,
                'content_data': task.content_data,
                'priority': task.priority
            })
        
        return result
    
    def get_available_target_hours(self) -> List[int]:
        """获取可用的目标时段（避开静默时间）"""
        all_hours = list(range(24))
        available_hours = [h for h in all_hours if h not in self.blackout_hours]
        return available_hours
    
    def get_hour_task_count(self, hour: int) -> int:
        """获取指定小时的任务数量"""
        count = self.session.query(PublishingTask).filter(
            PublishingTask.status == 'pending',
            func.strftime('%H', func.datetime(PublishingTask.scheduled_at, '+8 hours')) == f'{hour:02d}'
        ).count()
        
        return count
    
    def find_best_target_hours(self, exclude_hour: int = 9) -> List[Tuple[int, int]]:
        """找到最佳的目标时段（任务数量最少的时段）"""
        available_hours = self.get_available_target_hours()
        if exclude_hour in available_hours:
            available_hours.remove(exclude_hour)
        
        hour_counts = []
        for hour in available_hours:
            count = self.get_hour_task_count(hour)
            hour_counts.append((hour, count))
        
        # 按任务数量排序，优先选择任务少的时段
        hour_counts.sort(key=lambda x: x[1])
        return hour_counts
    
    def redistribute_peak_tasks(self, peak_hour: int = 9, target_count: int = 25, dry_run: bool = False):
        """强制重新分布峰值时段的任务"""
        print(f"\n开始强制重新分布 {peak_hour}:00 时段的任务...")
        
        # 获取峰值时段的所有任务
        peak_tasks = self.get_peak_hour_tasks(peak_hour)
        current_count = len(peak_tasks)
        
        print(f"当前 {peak_hour}:00 时段有 {current_count} 个任务")
        print(f"目标: 减少到 {target_count} 个任务")
        
        if current_count <= target_count:
            print("任务数量已经在目标范围内，无需重新分布")
            return {'moved': 0, 'skipped': current_count}
        
        # 计算需要移动的任务数量
        tasks_to_move_count = current_count - target_count
        print(f"需要移动 {tasks_to_move_count} 个任务")
        
        # 获取最佳目标时段
        target_hours = self.find_best_target_hours(exclude_hour=peak_hour)
        print(f"\n可用目标时段: {[(h, c) for h, c in target_hours[:10]]}")
        
        if not target_hours:
            print("没有可用的目标时段")
            return {'moved': 0, 'skipped': current_count}
        
        # 选择要移动的任务（优先移动优先级较低的任务）
        tasks_to_move = sorted(peak_tasks, key=lambda x: (x['priority'], x['scheduled_at']))[:tasks_to_move_count]
        
        moved_count = 0
        skipped_count = 0
        
        for i, task in enumerate(tasks_to_move):
            # 循环选择目标时段，优先选择任务少的时段
            target_hour_info = target_hours[i % len(target_hours)]
            target_hour = target_hour_info[0]
            
            # 解析原始时间
            original_time = task['scheduled_at']
            if isinstance(original_time, str):
                original_time = datetime.fromisoformat(original_time.replace('Z', '+00:00'))
            
            # 计算新的时间（保持同一天，只改变小时）
            beijing_tz = pytz.timezone('Asia/Shanghai')
            if original_time.tzinfo is None:
                original_time = pytz.utc.localize(original_time)
            beijing_time = original_time.astimezone(beijing_tz)
            
            # 创建新的时间（同一天，新的小时，随机分钟）
            new_minute = random.randint(0, 59)
            new_second = random.randint(0, 59)
            
            new_beijing_time = beijing_time.replace(
                hour=target_hour,
                minute=new_minute,
                second=new_second
            )
            
            # 转换回UTC
            new_scheduled_at = new_beijing_time.astimezone(pytz.UTC)
            
            if not dry_run:
                try:
                    # 更新任务时间
                    task_obj = self.task_repo.get_by_id(task['id'])
                    if task_obj:
                        # 确保new_scheduled_at是datetime对象
                        if isinstance(new_scheduled_at, str):
                            new_scheduled_at = datetime.fromisoformat(new_scheduled_at.replace('Z', '+00:00'))
                        
                        task_obj.scheduled_at = new_scheduled_at
                        task_obj.updated_at = datetime.utcnow()
                        self.session.commit()
                        moved_count += 1
                        
                        if moved_count % 50 == 0:
                            print(f"已移动 {moved_count} 个任务...")
                    else:
                        print(f"任务 {task['id']} 不存在")
                        skipped_count += 1
                        
                except Exception as e:
                    print(f"移动任务 {task['id']} 失败: {e}")
                    self.session.rollback()
                    skipped_count += 1
            else:
                print(f"[预览] 任务 {task['id']}: {peak_hour}:00 -> {target_hour}:00")
                moved_count += 1
        
        print(f"\n重新分布完成: 移动了 {moved_count} 个任务，跳过了 {skipped_count} 个任务")
        return {'moved': moved_count, 'skipped': skipped_count}
    
    def analyze_distribution(self):
        """分析当前任务分布"""
        # 使用SQLAlchemy查询
        results = self.session.query(
            func.strftime('%H', func.datetime(PublishingTask.scheduled_at, '+8 hours')).label('hour'),
            func.count().label('count')
        ).filter(
            PublishingTask.status == 'pending'
        ).group_by(
            func.strftime('%H', func.datetime(PublishingTask.scheduled_at, '+8 hours'))
        ).order_by('hour').all()
        
        print("\n当前任务分布（北京时间）:")
        print("=" * 40)
        for hour, count in results:
            status = "⚠️" if count > 30 else "✅" if count <= 20 else "🔶"
            print(f"{hour}:00 - {count:2d} 个任务 {status}")

def main():
    redistributor = ForcePeakRedistributor()
    
    print("强制峰值时段任务重新分布工具")
    print("=" * 50)
    
    # 先分析当前分布
    redistributor.analyze_distribution()
    
    print("\n选择操作:")
    print("1. 预览重新分布 (不实际修改)")
    print("2. 执行重新分布")
    print("3. 仅分析当前分布")
    
    choice = input("\n请选择 (1-3): ").strip()
    
    if choice == '1':
        redistributor.redistribute_peak_tasks(dry_run=True)
    elif choice == '2':
        redistributor.redistribute_peak_tasks(dry_run=False)
        print("\n重新分布后的任务分布:")
        redistributor.analyze_distribution()
    elif choice == '3':
        pass  # 已经分析过了
    else:
        print("无效选择")

if __name__ == '__main__':
    main()