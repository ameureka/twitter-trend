#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务重新分布器 - 优化高密度时段的任务分布

主要功能:
1. 识别高密度时段的任务
2. 将任务重新分布到低密度时段
3. 保持合理的发布间隔
4. 避免静默时间段
"""

import os
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.db_manager import EnhancedDatabaseManager
from app.database.repository import PublishingTaskRepository
from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config

logger = get_logger(__name__)

class TaskRedistributor:
    """任务重新分布器"""
    
    def __init__(self):
        self.config = get_enhanced_config()
        self.db_manager = EnhancedDatabaseManager()
        self.task_repo = PublishingTaskRepository(self.db_manager.get_session())
        
        # 从配置文件读取调度参数
        scheduling_config = self.config.get('scheduling', {})
        self.blackout_hours = scheduling_config.get('blackout_hours', [0, 1, 2, 3, 4, 5, 6])
        self.min_interval_minutes = scheduling_config.get('interval_minutes_min', 180)
        self.max_interval_minutes = scheduling_config.get('interval_minutes_max', 300)
        
        # 时区配置
        self.timezone_offset = 8  # 北京时间 UTC+8
        
        # 定义高密度阈值
        self.high_density_threshold = 15  # 超过15个任务的时段视为高密度
        
    def analyze_task_distribution(self) -> Dict[int, int]:
        """分析当前任务分布"""
        logger.info("分析当前任务时间分布...")
        
        # 获取所有待发布任务
        pending_tasks = self.task_repo.get_ready_tasks(
            filters={'status': 'pending'},
            limit=None
        )
        
        # 按小时统计任务分布
        hour_distribution = defaultdict(int)
        for task in pending_tasks:
            # 转换为北京时间
            beijing_time = task.scheduled_at + timedelta(hours=self.timezone_offset)
            hour = beijing_time.hour
            hour_distribution[hour] += 1
        
        logger.info(f"总待发布任务数: {len(pending_tasks)}")
        
        # 显示分布情况
        for hour in sorted(hour_distribution.keys()):
            count = hour_distribution[hour]
            status = "⚠️ 高密度" if count > self.high_density_threshold else ""
            logger.info(f"{hour:02d}:00 - {count} 个任务 {status}")
        
        return dict(hour_distribution)
    
    def identify_redistribution_candidates(self) -> Tuple[List, List[int]]:
        """识别需要重新分布的任务和目标时段"""
        logger.info("识别需要重新分布的任务...")
        
        # 获取当前分布
        hour_distribution = self.analyze_task_distribution()
        
        # 找出高密度时段
        high_density_hours = [hour for hour, count in hour_distribution.items() 
                             if count > self.high_density_threshold]
        
        # 找出低密度时段（排除静默时间）
        low_density_hours = []
        for hour in range(24):
            if (hour not in self.blackout_hours and 
                hour_distribution.get(hour, 0) < 15):  # 少于15个任务的时段
                low_density_hours.append(hour)
        
        logger.info(f"高密度时段: {high_density_hours}")
        logger.info(f"可用低密度时段: {low_density_hours}")
        
        # 获取高密度时段的任务
        candidates = []
        for hour in high_density_hours:
            # 获取该时段的任务
            hour_tasks = self._get_tasks_by_hour(hour)
            # 计算需要移动的任务数量（更激进的分散策略）
            # 针对极高密度时段进行更激进的分散
            task_count = len(hour_tasks)
            if task_count > 100:
                # 超过100个任务，移动80%
                move_count = int(task_count * 0.8)
            elif task_count > 50:
                # 超过50个任务，移动70%
                move_count = int(task_count * 0.7)
            elif task_count > 30:
                # 超过30个任务，移动2/3
                move_count = int(task_count * 2 / 3)
            else:
                # 否则移动一半
                move_count = task_count // 2
            # 随机选择要移动的任务
            tasks_to_move = random.sample(hour_tasks, min(move_count, len(hour_tasks)))
            candidates.extend(tasks_to_move)
        
        logger.info(f"找到 {len(candidates)} 个需要重新分布的任务")
        
        return candidates, low_density_hours
    
    def _get_tasks_by_hour(self, target_hour: int) -> List:
        """获取指定小时的任务"""
        all_tasks = self.task_repo.get_ready_tasks(
            filters={'status': 'pending'},
            limit=None
        )
        
        hour_tasks = []
        for task in all_tasks:
            beijing_time = task.scheduled_at + timedelta(hours=self.timezone_offset)
            if beijing_time.hour == target_hour:
                hour_tasks.append(task)
        
        return hour_tasks
    
    def redistribute_tasks(self, dry_run: bool = True) -> Dict[str, int]:
        """重新分布任务 - 增强版分散策略"""
        logger.info(f"开始任务重新分布 (dry_run={dry_run})...")
        
        # 获取当前分布情况
        current_distribution = self.analyze_task_distribution()
        
        # 多轮分布，确保充分分散
        total_moved = 0
        total_skipped = 0
        max_rounds = 3  # 最多执行3轮分布
        
        for round_num in range(max_rounds):
            logger.info(f"执行第 {round_num + 1} 轮分布...")
            
            candidates, target_hours = self.identify_redistribution_candidates()
            
            if not candidates or not target_hours:
                logger.info(f"第 {round_num + 1} 轮：没有需要重新分布的任务或没有可用的目标时段")
                break
            
            moved_count = 0
            skipped_count = 0
            
            # 按优先级排序候选任务，优先移动低优先级任务
            candidates.sort(key=lambda x: getattr(x, 'priority', 5), reverse=True)
            
            for task in candidates:
                try:
                    # 智能选择目标时段 - 优先选择任务数量最少的时段
                    target_hour = self._select_optimal_target_hour(target_hours, current_distribution)
                    
                    # 计算新的调度时间
                    new_scheduled_time = self._calculate_new_schedule_time(task.scheduled_at, target_hour)
                    
                    if dry_run:
                        logger.info(f"[DRY RUN] 任务 {task.id}: {task.scheduled_at} -> {new_scheduled_time}")
                    else:
                        # 更新任务调度时间
                        success = self.task_repo.update(task.id, {'scheduled_at': new_scheduled_time})
                        if success:
                            logger.info(f"任务 {task.id} 已重新调度: {new_scheduled_time}")
                            # 更新本地分布统计
                            old_hour = (task.scheduled_at + timedelta(hours=self.timezone_offset)).hour
                            current_distribution[old_hour] = current_distribution.get(old_hour, 0) - 1
                            current_distribution[target_hour] = current_distribution.get(target_hour, 0) + 1
                        else:
                            raise Exception("数据库更新失败")
                    
                    moved_count += 1
                    
                    # 如果目标时段任务数达到合理水平，从候选列表中移除
                    if current_distribution.get(target_hour, 0) >= 15:
                        if target_hour in target_hours:
                            target_hours.remove(target_hour)
                    
                    # 如果没有可用目标时段，提前结束本轮
                    if not target_hours:
                        logger.info("所有目标时段已达到合理密度，结束本轮分布")
                        break
                        
                except Exception as e:
                    logger.error(f"重新分布任务 {task.id} 失败: {e}")
                    skipped_count += 1
            
            total_moved += moved_count
            total_skipped += skipped_count
            
            logger.info(f"第 {round_num + 1} 轮完成: 移动 {moved_count} 个，跳过 {skipped_count} 个")
            
            # 如果本轮移动的任务很少，说明分布已经相对均匀
            if moved_count < 10:
                logger.info("任务分布已相对均匀，提前结束")
                break
        
        logger.info(f"任务重新分布完成: 总共移动 {total_moved} 个，跳过 {total_skipped} 个")
        
        return {'moved': total_moved, 'skipped': total_skipped}
    
    def _select_optimal_target_hour(self, target_hours: List[int], current_distribution: Dict[int, int]) -> int:
        """智能选择最优目标时段"""
        if not target_hours:
            raise ValueError("没有可用的目标时段")
        
        # 按当前任务数量排序，优先选择任务最少的时段
        sorted_hours = sorted(target_hours, key=lambda h: current_distribution.get(h, 0))
        
        # 在任务数量最少的几个时段中随机选择，增加随机性
        min_count = current_distribution.get(sorted_hours[0], 0)
        optimal_hours = [h for h in sorted_hours if current_distribution.get(h, 0) <= min_count + 2]
        
        return random.choice(optimal_hours)
    
    def _calculate_new_schedule_time(self, original_time: datetime, target_hour: int) -> datetime:
        """计算新的调度时间"""
        # 转换为北京时间
        beijing_time = original_time + timedelta(hours=self.timezone_offset)
        
        # 保持同一天，只改变小时
        new_beijing_time = beijing_time.replace(
            hour=target_hour,
            minute=random.randint(0, 59),
            second=random.randint(0, 59)
        )
        
        # 转换回UTC
        new_utc_time = new_beijing_time - timedelta(hours=self.timezone_offset)
        
        return new_utc_time
    
    def preview_redistribution(self) -> None:
        """预览重新分布效果"""
        logger.info("=== 任务重新分布预览 ===")
        
        # 显示当前分布
        logger.info("\n当前任务分布:")
        current_distribution = self.analyze_task_distribution()
        
        # 执行干运行
        logger.info("\n执行重新分布预览...")
        result = self.redistribute_tasks(dry_run=True)
        
        logger.info(f"\n预览结果: 计划移动 {result['moved']} 个任务")
        
        return result

def main():
    """主函数"""
    redistributor = TaskRedistributor()
    
    print("=== Twitter 任务重新分布器 ===")
    print("1. 预览重新分布")
    print("2. 执行重新分布")
    print("3. 仅分析当前分布")
    
    choice = input("请选择操作 (1-3): ").strip()
    
    if choice == '1':
        redistributor.preview_redistribution()
    elif choice == '2':
        confirm = input("确认执行任务重新分布？这将修改数据库中的任务调度时间 (y/N): ").strip().lower()
        if confirm == 'y':
            result = redistributor.redistribute_tasks(dry_run=False)
            print(f"\n重新分布完成: 移动了 {result['moved']} 个任务")
            
            # 显示新的分布
            print("\n重新分布后的任务分布:")
            redistributor.analyze_task_distribution()
        else:
            print("操作已取消")
    elif choice == '3':
        redistributor.analyze_task_distribution()
    else:
        print("无效选择")

if __name__ == "__main__":
    main()