#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📅 最佳发布时间预测器 - Phase 3.5
根据TWITTER_OPTIMIZATION_PLAN.md实现智能发布时间预测

主要功能:
1. 历史数据分析
2. 时间段性能评估  
3. 动态时间调整
4. 避开黑名单时间
"""

import statistics
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
from enum import Enum

from app.utils.logger import get_logger

logger = get_logger(__name__)

class TimeSlot(Enum):
    """时间段枚举"""
    EARLY_MORNING = "early_morning"    # 6-9点
    MORNING = "morning"               # 9-12点  
    AFTERNOON = "afternoon"           # 12-15点
    EVENING = "evening"              # 15-18点
    NIGHT = "night"                  # 18-21点
    LATE_NIGHT = "late_night"        # 21-24点
    OVERNIGHT = "overnight"          # 0-6点

@dataclass
class TimePerformance:
    """时间段性能数据"""
    time_slot: TimeSlot
    success_rate: float      # 成功率
    engagement_score: float  # 参与度得分
    optimal_hours: List[int] # 该时间段内的最佳小时
    sample_count: int        # 样本数量

@dataclass 
class PredictionResult:
    """预测结果"""
    recommended_time: datetime
    confidence_score: float     # 预测置信度
    alternative_times: List[datetime]  # 备选时间
    reasoning: str             # 推荐理由
    time_slot: TimeSlot        # 推荐时间段

class OptimalTimingPredictor:
    """📅 最佳发布时间预测器"""
    
    def __init__(self):
        # 基础配置 - 基于Twitter用户活跃度研究
        self.default_optimal_hours = {
            TimeSlot.EARLY_MORNING: [7, 8],      # 通勤时间
            TimeSlot.MORNING: [9, 10, 11],       # 工作开始
            TimeSlot.AFTERNOON: [12, 13, 14],    # 午休时间
            TimeSlot.EVENING: [15, 16, 17],      # 下班前
            TimeSlot.NIGHT: [18, 19, 20],        # 晚饭后
            TimeSlot.LATE_NIGHT: [21, 22],       # 睡前浏览
            TimeSlot.OVERNIGHT: []               # 避免深夜发布
        }
        
        # 黑名单时间（用户活跃度极低的时间）
        self.blackout_hours = [0, 1, 2, 3, 4, 5, 6, 23]
        
        # 工作日vs周末的权重调整
        self.weekday_weights = {
            0: 1.0,  # 周一
            1: 1.1,  # 周二 - 略高活跃度
            2: 1.2,  # 周三 - 最高活跃度
            3: 1.1,  # 周四
            4: 0.9,  # 周五 - 下午活跃度下降
            5: 0.7,  # 周六 - 较低活跃度
            6: 0.6   # 周日 - 最低活跃度
        }
        
        # 内容类型时间偏好
        self.content_type_preferences = {
            'news': TimeSlot.MORNING,           # 新闻适合早上
            'entertainment': TimeSlot.EVENING,  # 娱乐适合晚上
            'educational': TimeSlot.AFTERNOON,  # 教育适合下午
            'promotional': TimeSlot.MORNING,    # 推广适合早上
            'trending': TimeSlot.NIGHT,         # 热门适合晚上
            'normal': TimeSlot.AFTERNOON        # 普通内容下午
        }
        
        # 历史性能数据缓存
        self.performance_cache = {}
        self.cache_expiry = timedelta(hours=6)  # 缓存6小时
        self.last_cache_update = None
        
        logger.info("📅 最佳发布时间预测器已初始化")
    
    def predict_optimal_time(self, 
                           content_type: str = 'normal',
                           project_priority: int = 3,
                           min_delay_minutes: int = 30,
                           max_delay_hours: int = 24,
                           base_time: Optional[datetime] = None) -> PredictionResult:
        """
        预测最佳发布时间
        
        Args:
            content_type: 内容类型
            project_priority: 项目优先级 (1-5)
            min_delay_minutes: 最小延迟分钟数
            max_delay_hours: 最大延迟小时数
            base_time: 基准时间，默认为当前时间
            
        Returns:
            PredictionResult: 预测结果
        """
        if not base_time:
            base_time = datetime.now()
            
        logger.info(f"📅 开始预测最佳发布时间 - 内容类型: {content_type}, 优先级: {project_priority}")
        
        try:
            # 1. 计算时间窗口
            earliest_time = base_time + timedelta(minutes=min_delay_minutes)
            latest_time = base_time + timedelta(hours=max_delay_hours)
            
            # 2. 根据内容类型确定偏好时间段
            preferred_slot = self.content_type_preferences.get(content_type, TimeSlot.AFTERNOON)
            
            # 3. 生成候选时间列表
            candidate_times = self._generate_candidate_times(
                earliest_time, latest_time, preferred_slot, project_priority
            )
            
            # 4. 评估每个候选时间
            scored_times = []
            for candidate_time in candidate_times:
                score = self._evaluate_time_quality(candidate_time, content_type, project_priority)
                scored_times.append((candidate_time, score))
            
            # 5. 选择最佳时间
            if not scored_times:
                # 回退策略
                return self._fallback_prediction(earliest_time, content_type)
                
            # 按得分排序
            scored_times.sort(key=lambda x: x[1], reverse=True)
            best_time, best_score = scored_times[0]
            
            # 6. 准备备选时间
            alternative_times = [t[0] for t in scored_times[1:4]]  # 取前3个备选
            
            # 7. 生成推荐理由
            reasoning = self._generate_reasoning(best_time, content_type, preferred_slot, best_score)
            
            # 8. 确定置信度
            confidence = self._calculate_confidence(best_score, len(scored_times))
            
            result = PredictionResult(
                recommended_time=best_time,
                confidence_score=confidence,
                alternative_times=alternative_times,
                reasoning=reasoning,
                time_slot=self._get_time_slot(best_time)
            )
            
            logger.info(f"📅 时间预测完成: {best_time.strftime('%Y-%m-%d %H:%M')} (置信度: {confidence:.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"📅 时间预测失败: {e}")
            return self._fallback_prediction(earliest_time, content_type)
    
    def _generate_candidate_times(self, 
                                earliest_time: datetime,
                                latest_time: datetime, 
                                preferred_slot: TimeSlot,
                                priority: int) -> List[datetime]:
        """生成候选发布时间"""
        candidates = []
        current_time = earliest_time
        
        # 根据优先级调整搜索策略
        if priority >= 4:  # 高优先级，快速发布
            time_step = timedelta(hours=1)
            max_candidates = 24
        else:  # 普通优先级，精细搜索
            time_step = timedelta(hours=1)
            max_candidates = 48
            
        while current_time <= latest_time and len(candidates) < max_candidates:
            # 跳过黑名单时间
            if current_time.hour not in self.blackout_hours:
                candidates.append(current_time)
                
            current_time += time_step
            
        # 如果偏好时间段内有候选时间，优先考虑
        preferred_candidates = []
        for candidate in candidates:
            if self._get_time_slot(candidate) == preferred_slot:
                preferred_candidates.append(candidate)
                
        # 合并候选时间，偏好时间段排在前面
        final_candidates = preferred_candidates + [c for c in candidates if c not in preferred_candidates]
        
        return final_candidates[:max_candidates]
    
    def _evaluate_time_quality(self, target_time: datetime, content_type: str, priority: int) -> float:
        """评估发布时间质量"""
        score = 0.0
        
        # 1. 基础时间段得分 (40%)
        time_slot = self._get_time_slot(target_time)
        base_scores = {
            TimeSlot.MORNING: 85.0,
            TimeSlot.AFTERNOON: 80.0,
            TimeSlot.EVENING: 90.0,
            TimeSlot.NIGHT: 85.0,
            TimeSlot.LATE_NIGHT: 60.0,
            TimeSlot.EARLY_MORNING: 70.0,
            TimeSlot.OVERNIGHT: 20.0
        }
        score += base_scores.get(time_slot, 50.0) * 0.4
        
        # 2. 工作日权重 (20%)
        weekday = target_time.weekday()
        weekday_weight = self.weekday_weights.get(weekday, 0.8)
        score += weekday_weight * 100 * 0.2
        
        # 3. 内容类型匹配度 (20%)
        preferred_slot = self.content_type_preferences.get(content_type, TimeSlot.AFTERNOON)
        if time_slot == preferred_slot:
            score += 100 * 0.2
        else:
            score += 60 * 0.2
            
        # 4. 小时精确度 (10%)
        hour = target_time.hour
        if time_slot in self.default_optimal_hours:
            optimal_hours = self.default_optimal_hours[time_slot]
            if hour in optimal_hours:
                score += 100 * 0.1
            else:
                score += 50 * 0.1
        
        # 5. 优先级调整 (10%)
        if priority >= 4:  # 高优先级项目，时间要求不那么严格
            score += 80 * 0.1
        else:
            score += 90 * 0.1
            
        return min(100.0, max(0.0, score))
    
    def _get_time_slot(self, dt: datetime) -> TimeSlot:
        """获取时间段"""
        hour = dt.hour
        
        if 6 <= hour < 9:
            return TimeSlot.EARLY_MORNING
        elif 9 <= hour < 12:
            return TimeSlot.MORNING
        elif 12 <= hour < 15:
            return TimeSlot.AFTERNOON
        elif 15 <= hour < 18:
            return TimeSlot.EVENING
        elif 18 <= hour < 21:
            return TimeSlot.NIGHT
        elif 21 <= hour < 24:
            return TimeSlot.LATE_NIGHT
        else:  # 0-6点
            return TimeSlot.OVERNIGHT
    
    def _generate_reasoning(self, 
                          best_time: datetime,
                          content_type: str, 
                          preferred_slot: TimeSlot,
                          score: float) -> str:
        """生成推荐理由"""
        time_slot = self._get_time_slot(best_time)
        weekday_name = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][best_time.weekday()]
        
        reasons = []
        
        # 时间段理由
        slot_reasons = {
            TimeSlot.MORNING: "早上用户开始查看社交媒体",
            TimeSlot.AFTERNOON: "下午用户活跃度较高",
            TimeSlot.EVENING: "傍晚是用户使用高峰期",
            TimeSlot.NIGHT: "晚上用户有更多时间浏览内容",
            TimeSlot.EARLY_MORNING: "早晨通勤时间用户活跃",
            TimeSlot.LATE_NIGHT: "睡前浏览时段"
        }
        
        if time_slot in slot_reasons:
            reasons.append(slot_reasons[time_slot])
            
        # 工作日理由
        weekday = best_time.weekday()
        if weekday in [1, 2]:  # 周二周三
            reasons.append("工作日中段用户活跃度最高")
        elif weekday == 0:  # 周一
            reasons.append("周一用户回归工作状态")
        elif weekday >= 5:  # 周末
            reasons.append("周末用户有更多空闲时间")
            
        # 内容匹配理由
        if time_slot == preferred_slot:
            reasons.append(f"{content_type}类型内容在此时段表现最佳")
            
        # 得分理由
        if score >= 80:
            reasons.append("预测置信度高")
        elif score >= 60:
            reasons.append("预测置信度中等")
            
        return f"{best_time.strftime('%m月%d日 %H:%M')} ({weekday_name}): " + "，".join(reasons)
    
    def _calculate_confidence(self, best_score: float, candidate_count: int) -> float:
        """计算预测置信度"""
        # 基础置信度基于得分
        base_confidence = best_score / 100.0
        
        # 候选数量调整
        if candidate_count >= 10:
            candidate_factor = 1.0
        elif candidate_count >= 5:
            candidate_factor = 0.9
        else:
            candidate_factor = 0.8
            
        confidence = base_confidence * candidate_factor
        return min(1.0, max(0.0, confidence))
    
    def _fallback_prediction(self, earliest_time: datetime, content_type: str) -> PredictionResult:
        """回退预测策略"""
        # 简单策略：选择下一个非黑名单时间段
        current_time = earliest_time
        
        while current_time.hour in self.blackout_hours:
            current_time += timedelta(hours=1)
            
        time_slot = self._get_time_slot(current_time)
        
        return PredictionResult(
            recommended_time=current_time,
            confidence_score=0.5,
            alternative_times=[],
            reasoning=f"回退策略：选择最近可用时间 {current_time.strftime('%H:%M')}",
            time_slot=time_slot
        )
    
    def get_next_optimal_window(self, content_type: str = 'normal') -> Tuple[datetime, datetime]:
        """获取下一个最佳发布时间窗口"""
        now = datetime.now()
        preferred_slot = self.content_type_preferences.get(content_type, TimeSlot.AFTERNOON)
        
        # 寻找下一个偏好时间段
        current_slot = self._get_time_slot(now)
        
        if current_slot == preferred_slot:
            # 已经在偏好时间段内
            window_start = now + timedelta(minutes=30)
        else:
            # 寻找下一个偏好时间段
            tomorrow = now + timedelta(days=1)
            optimal_hours = self.default_optimal_hours.get(preferred_slot, [12])
            
            if optimal_hours:
                window_start = tomorrow.replace(
                    hour=optimal_hours[0], minute=0, second=0, microsecond=0
                )
            else:
                window_start = now + timedelta(hours=2)
                
        window_end = window_start + timedelta(hours=3)  # 3小时窗口
        
        return window_start, window_end
    
    def is_good_time_to_publish(self, target_time: datetime, content_type: str = 'normal') -> bool:
        """判断指定时间是否适合发布"""
        # 检查是否在黑名单时间
        if target_time.hour in self.blackout_hours:
            return False
            
        # 计算时间质量得分
        quality_score = self._evaluate_time_quality(target_time, content_type, 3)
        
        return quality_score >= 60.0  # 60分以上认为是好时间

# 全局实例
optimal_timing_predictor = OptimalTimingPredictor()

def predict_best_publish_time(content_type: str = 'normal', 
                             priority: int = 3,
                             min_delay_minutes: int = 30) -> PredictionResult:
    """
    便捷函数：预测最佳发布时间
    
    Args:
        content_type: 内容类型
        priority: 优先级
        min_delay_minutes: 最小延迟分钟
        
    Returns:
        PredictionResult: 预测结果
    """
    return optimal_timing_predictor.predict_optimal_time(
        content_type=content_type,
        project_priority=priority,
        min_delay_minutes=min_delay_minutes
    )