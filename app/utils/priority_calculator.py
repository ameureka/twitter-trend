#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 优先级权重算法 - Phase 3.4
根据TWITTER_OPTIMIZATION_PLAN.md实现智能优先级计算

主要功能:
1. 多因素权重计算
2. 动态优先级调整
3. 时间敏感性分析
4. 项目重要性评估
"""

import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

from app.utils.logger import get_logger

logger = get_logger(__name__)

class PriorityFactor(Enum):
    """优先级影响因素"""
    TIME_URGENCY = "time_urgency"        # 时间紧急性
    RETRY_COUNT = "retry_count"          # 重试次数
    PROJECT_PRIORITY = "project_priority" # 项目优先级
    TASK_AGE = "task_age"               # 任务年龄
    SCHEDULE_DELAY = "schedule_delay"    # 调度延迟
    CONTENT_TYPE = "content_type"       # 内容类型
    
@dataclass
class PriorityWeights:
    """优先级权重配置"""
    time_urgency: float = 0.3      # 时间紧急性权重
    retry_count: float = 0.25      # 重试次数权重  
    project_priority: float = 0.2  # 项目优先级权重
    task_age: float = 0.15         # 任务年龄权重
    schedule_delay: float = 0.07   # 调度延迟权重
    content_type: float = 0.03     # 内容类型权重
    
    def normalize(self):
        """归一化权重，确保总和为1.0"""
        total = (self.time_urgency + self.retry_count + self.project_priority + 
                self.task_age + self.schedule_delay + self.content_type)
        
        if total > 0:
            factor = 1.0 / total
            self.time_urgency *= factor
            self.retry_count *= factor
            self.project_priority *= factor
            self.task_age *= factor
            self.schedule_delay *= factor
            self.content_type *= factor

class PriorityCalculator:
    """🎯 智能优先级计算器"""
    
    def __init__(self, weights: Optional[PriorityWeights] = None):
        self.weights = weights or PriorityWeights()
        self.weights.normalize()
        
        # 配置参数
        self.max_priority_score = 100.0
        self.min_priority_score = 1.0
        
        # 时间段配置（小时）
        self.optimal_hours = [9, 12, 15, 18, 21]  # 最佳发布时间
        self.blackout_hours = [0, 1, 2, 3, 4, 5, 6]  # 禁止发布时间
        
        logger.info("🎯 优先级权重算法已初始化")
        logger.debug(f"权重配置: {self.weights}")
    
    def calculate_priority_score(self, task_data: Dict[str, Any]) -> float:
        """
        计算任务优先级得分
        
        Args:
            task_data: 任务数据字典，包含以下字段：
                - created_at: 任务创建时间
                - scheduled_at: 计划执行时间
                - retry_count: 重试次数
                - project_id: 项目ID
                - project_priority: 项目优先级 (1-5)
                - content_type: 内容类型
                
        Returns:
            float: 优先级得分 (1.0-100.0)
        """
        try:
            current_time = datetime.now()
            
            # 1. 时间紧急性得分
            urgency_score = self._calculate_time_urgency(
                task_data.get('scheduled_at'), current_time
            )
            
            # 2. 重试次数得分  
            retry_score = self._calculate_retry_score(
                task_data.get('retry_count', 0)
            )
            
            # 3. 项目优先级得分
            project_score = self._calculate_project_score(
                task_data.get('project_priority', 3)
            )
            
            # 4. 任务年龄得分
            age_score = self._calculate_age_score(
                task_data.get('created_at'), current_time
            )
            
            # 5. 调度延迟得分
            delay_score = self._calculate_schedule_delay_score(
                task_data.get('scheduled_at'), current_time
            )
            
            # 6. 内容类型得分
            content_score = self._calculate_content_type_score(
                task_data.get('content_type', 'normal')
            )
            
            # 计算加权总分
            total_score = (
                urgency_score * self.weights.time_urgency +
                retry_score * self.weights.retry_count +
                project_score * self.weights.project_priority +
                age_score * self.weights.task_age +
                delay_score * self.weights.schedule_delay +
                content_score * self.weights.content_type
            )
            
            # 确保得分在有效范围内
            final_score = max(self.min_priority_score, 
                            min(self.max_priority_score, total_score))
            
            logger.debug(f"🎯 任务优先级计算详情:")
            logger.debug(f"  - 时间紧急性: {urgency_score:.2f} (权重: {self.weights.time_urgency:.2f})")
            logger.debug(f"  - 重试次数: {retry_score:.2f} (权重: {self.weights.retry_count:.2f})")
            logger.debug(f"  - 项目优先级: {project_score:.2f} (权重: {self.weights.project_priority:.2f})")
            logger.debug(f"  - 任务年龄: {age_score:.2f} (权重: {self.weights.task_age:.2f})")
            logger.debug(f"  - 调度延迟: {delay_score:.2f} (权重: {self.weights.schedule_delay:.2f})")
            logger.debug(f"  - 内容类型: {content_score:.2f} (权重: {self.weights.content_type:.2f})")
            logger.debug(f"  - 最终得分: {final_score:.2f}")
            
            return final_score
            
        except Exception as e:
            logger.error(f"🎯 优先级计算失败: {e}")
            return 50.0  # 返回中等优先级
    
    def _calculate_time_urgency(self, scheduled_at: Optional[datetime], 
                              current_time: datetime) -> float:
        """计算时间紧急性得分"""
        if not scheduled_at:
            return 50.0  # 中等紧急性
            
        # 计算距离计划执行时间的差值
        time_diff = (scheduled_at - current_time).total_seconds()
        
        if time_diff <= 0:
            # 已经过期，极高优先级
            overdue_hours = abs(time_diff) / 3600
            return min(100.0, 90.0 + overdue_hours * 2)
        
        # 根据时间差计算紧急性
        hours_until_execution = time_diff / 3600
        
        if hours_until_execution <= 1:
            return 95.0  # 1小时内执行
        elif hours_until_execution <= 3:
            return 80.0  # 3小时内执行
        elif hours_until_execution <= 6:
            return 65.0  # 6小时内执行
        elif hours_until_execution <= 12:
            return 45.0  # 12小时内执行
        elif hours_until_execution <= 24:
            return 30.0  # 24小时内执行
        else:
            return 15.0  # 超过24小时
    
    def _calculate_retry_score(self, retry_count: int) -> float:
        """计算重试次数得分 - 重试次数越多优先级越高"""
        if retry_count == 0:
            return 20.0  # 首次执行
        elif retry_count == 1:
            return 60.0  # 第一次重试
        elif retry_count == 2:
            return 80.0  # 第二次重试
        else:
            return 95.0  # 多次重试，优先处理
    
    def _calculate_project_score(self, project_priority: int) -> float:
        """计算项目优先级得分"""
        # 项目优先级 1-5，5为最高
        priority_map = {
            1: 20.0,  # 低优先级项目
            2: 35.0,  # 较低优先级
            3: 50.0,  # 中等优先级
            4: 75.0,  # 高优先级
            5: 90.0   # 最高优先级
        }
        
        return priority_map.get(project_priority, 50.0)
    
    def _calculate_age_score(self, created_at: Optional[datetime], 
                           current_time: datetime) -> float:
        """计算任务年龄得分 - 任务越老优先级越高"""
        if not created_at:
            return 50.0
            
        age_hours = (current_time - created_at).total_seconds() / 3600
        
        if age_hours <= 1:
            return 10.0  # 新任务
        elif age_hours <= 6:
            return 25.0  # 6小时内
        elif age_hours <= 12:
            return 45.0  # 半天内
        elif age_hours <= 24:
            return 65.0  # 一天内
        elif age_hours <= 48:
            return 80.0  # 两天内
        else:
            return 95.0  # 超过两天，优先处理
    
    def _calculate_schedule_delay_score(self, scheduled_at: Optional[datetime],
                                      current_time: datetime) -> float:
        """计算调度延迟得分 - 延迟越多优先级越高"""
        if not scheduled_at:
            return 50.0
            
        delay_minutes = (current_time - scheduled_at).total_seconds() / 60
        
        if delay_minutes <= 0:
            return 20.0  # 还没到时间
        elif delay_minutes <= 30:
            return 40.0  # 延迟30分钟内
        elif delay_minutes <= 60:
            return 60.0  # 延迟1小时内
        elif delay_minutes <= 180:
            return 80.0  # 延迟3小时内
        else:
            return 95.0  # 严重延迟
    
    def _calculate_content_type_score(self, content_type: str) -> float:
        """计算内容类型得分"""
        content_priority = {
            'urgent': 90.0,      # 紧急内容
            'trending': 80.0,    # 热门内容
            'scheduled': 60.0,   # 定时内容
            'normal': 50.0,      # 普通内容
            'promotional': 30.0  # 推广内容
        }
        
        return content_priority.get(content_type.lower(), 50.0)
    
    def is_optimal_time(self, target_time: datetime) -> bool:
        """判断是否为最佳发布时间"""
        hour = target_time.hour
        return hour in self.optimal_hours
    
    def is_blackout_time(self, target_time: datetime) -> bool:
        """判断是否为禁止发布时间"""
        hour = target_time.hour
        return hour in self.blackout_hours
    
    def get_next_optimal_time(self, base_time: Optional[datetime] = None) -> datetime:
        """获取下一个最佳发布时间"""
        if not base_time:
            base_time = datetime.now()
            
        # 从当前时间开始寻找下一个最佳时间
        current_hour = base_time.hour
        
        # 寻找今天剩余的最佳时间
        for optimal_hour in self.optimal_hours:
            if optimal_hour > current_hour:
                next_time = base_time.replace(
                    hour=optimal_hour, minute=0, second=0, microsecond=0
                )
                return next_time
        
        # 如果今天没有剩余的最佳时间，使用明天的第一个最佳时间
        tomorrow = base_time + timedelta(days=1)
        next_time = tomorrow.replace(
            hour=self.optimal_hours[0], minute=0, second=0, microsecond=0
        )
        
        return next_time
    
    def adjust_priority_for_time(self, base_score: float, target_time: datetime) -> float:
        """根据目标时间调整优先级得分"""
        if self.is_blackout_time(target_time):
            return base_score * 0.1  # 禁止时间大幅降低优先级
        elif self.is_optimal_time(target_time):
            return base_score * 1.2  # 最佳时间小幅提升优先级
        else:
            return base_score  # 普通时间不调整

# 全局实例
priority_calculator = PriorityCalculator()

def calculate_task_priority(task_data: Dict[str, Any]) -> float:
    """
    便捷函数：计算任务优先级得分
    
    Args:
        task_data: 任务数据字典
        
    Returns:
        float: 优先级得分
    """
    return priority_calculator.calculate_priority_score(task_data)

def get_priority_level(score: float) -> str:
    """
    根据得分获取优先级级别描述
    
    Args:
        score: 优先级得分
        
    Returns:
        str: 优先级级别
    """
    if score >= 80:
        return "URGENT"
    elif score >= 60:
        return "HIGH"
    elif score >= 40:
        return "NORMAL"
    elif score >= 20:
        return "LOW"
    else:
        return "VERY_LOW"