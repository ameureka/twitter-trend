#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ 卡住任务自动恢复管理器 - Phase 4.1
根据TWITTER_OPTIMIZATION_PLAN.md实现智能任务恢复机制

主要功能:
1. 智能检测卡住任务
2. 多策略恢复机制
3. 恢复历史追踪
4. 预防性监控
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import threading
import time

from app.utils.logger import get_logger

logger = get_logger(__name__)

class StuckReason(Enum):
    """卡住原因枚举"""
    TIMEOUT = "timeout"                    # 执行超时
    DEADLOCK = "deadlock"                 # 数据库死锁
    RESOURCE_LOCK = "resource_lock"       # 资源锁定
    WORKER_CRASH = "worker_crash"         # 工作线程崩溃
    MEMORY_LEAK = "memory_leak"           # 内存泄漏
    NETWORK_HANG = "network_hang"         # 网络挂起
    UNKNOWN = "unknown"                   # 未知原因

class RecoveryStrategy(Enum):
    """恢复策略枚举"""
    RESET_PENDING = "reset_pending"       # 重置为待处理
    FORCE_RETRY = "force_retry"          # 强制重试
    ESCALATE_PRIORITY = "escalate_priority" # 提升优先级
    MANUAL_INTERVENTION = "manual_intervention" # 人工介入
    ABORT_TASK = "abort_task"            # 终止任务

@dataclass
class StuckTaskInfo:
    """卡住任务信息"""
    task_id: int
    stuck_since: datetime
    stuck_duration_minutes: float
    last_update: datetime
    status: str
    retry_count: int
    suspected_reason: StuckReason
    recovery_attempts: int = 0
    
@dataclass
class RecoveryAction:
    """恢复操作记录"""
    task_id: int
    action_time: datetime
    strategy: RecoveryStrategy
    reason: StuckReason
    success: bool
    error_message: Optional[str] = None

class StuckTaskRecoveryManager:
    """🛡️ 卡住任务自动恢复管理器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # 配置参数
        self.stuck_timeout_minutes = self.config.get('stuck_timeout_minutes', 10)  # 10分钟超时
        self.max_recovery_attempts = self.config.get('max_recovery_attempts', 3)   # 最大恢复尝试
        self.recovery_check_interval = self.config.get('recovery_check_interval', 120)  # 2分钟检查一次
        
        # 各种超时阈值
        self.timeouts = {
            'running': 300,      # 运行状态超时（5分钟）
            'processing': 600,   # 处理状态超时（10分钟）
            'uploading': 900,    # 上传状态超时（15分钟）
        }
        
        # 恢复策略配置
        self.recovery_strategies = {
            StuckReason.TIMEOUT: [RecoveryStrategy.RESET_PENDING, RecoveryStrategy.FORCE_RETRY],
            StuckReason.DEADLOCK: [RecoveryStrategy.RESET_PENDING, RecoveryStrategy.ESCALATE_PRIORITY],
            StuckReason.RESOURCE_LOCK: [RecoveryStrategy.RESET_PENDING, RecoveryStrategy.FORCE_RETRY],
            StuckReason.WORKER_CRASH: [RecoveryStrategy.RESET_PENDING, RecoveryStrategy.ESCALATE_PRIORITY],
            StuckReason.MEMORY_LEAK: [RecoveryStrategy.RESET_PENDING, RecoveryStrategy.MANUAL_INTERVENTION],
            StuckReason.NETWORK_HANG: [RecoveryStrategy.FORCE_RETRY, RecoveryStrategy.RESET_PENDING],
            StuckReason.UNKNOWN: [RecoveryStrategy.RESET_PENDING, RecoveryStrategy.MANUAL_INTERVENTION]
        }
        
        # 运行状态
        self.recovery_history: List[RecoveryAction] = []
        self.stuck_tasks_cache: Dict[int, StuckTaskInfo] = {}
        self.is_monitoring = False
        self.monitor_thread = None
        self.lock = threading.Lock()
        
        logger.info("🛡️ 卡住任务自动恢复管理器已初始化")
        logger.info(f"  - 超时阈值: {self.stuck_timeout_minutes}分钟")
        logger.info(f"  - 最大恢复尝试: {self.max_recovery_attempts}次")
    
    def detect_stuck_tasks(self, db_manager) -> List[StuckTaskInfo]:
        """
        检测卡住的任务
        
        Args:
            db_manager: 数据库管理器
            
        Returns:
            List[StuckTaskInfo]: 卡住的任务列表
        """
        stuck_tasks = []
        current_time = datetime.now()
        
        try:
            session = db_manager.get_session()
            
            # 查询可能卡住的任务
            from app.database.repository import PublishingTaskRepository
            task_repo = PublishingTaskRepository(session)
            
            # 查找长时间处于运行状态的任务
            potentially_stuck = task_repo.get_tasks_by_status(['running', 'processing'])
            
            for task in potentially_stuck:
                if not task.updated_at:
                    continue
                    
                stuck_duration = (current_time - task.updated_at).total_seconds() / 60
                timeout_threshold = self.timeouts.get(task.status, self.stuck_timeout_minutes * 60) / 60
                
                if stuck_duration > timeout_threshold:
                    # 分析卡住原因
                    suspected_reason = self._analyze_stuck_reason(task, stuck_duration)
                    
                    stuck_info = StuckTaskInfo(
                        task_id=task.id,
                        stuck_since=task.updated_at,
                        stuck_duration_minutes=stuck_duration,
                        last_update=task.updated_at,
                        status=task.status,
                        retry_count=task.retry_count or 0,
                        suspected_reason=suspected_reason,
                        recovery_attempts=self._get_recovery_attempts(task.id)
                    )
                    
                    stuck_tasks.append(stuck_info)
                    
                    # 更新缓存
                    with self.lock:
                        self.stuck_tasks_cache[task.id] = stuck_info
                        
        except Exception as e:
            logger.error(f"🛡️ 检测卡住任务失败: {e}")
        finally:
            db_manager.remove_session()
            
        if stuck_tasks:
            logger.warning(f"🛡️ 检测到 {len(stuck_tasks)} 个卡住的任务")
            
        return stuck_tasks
    
    def _analyze_stuck_reason(self, task, stuck_duration_minutes: float) -> StuckReason:
        """分析任务卡住的可能原因"""
        # 基于时间和状态分析
        if stuck_duration_minutes > 30:  # 超过30分钟
            if task.status == 'running':
                return StuckReason.TIMEOUT
            elif task.status == 'processing':
                return StuckReason.RESOURCE_LOCK
        elif stuck_duration_minutes > 15:  # 15-30分钟
            if task.retry_count > 2:
                return StuckReason.NETWORK_HANG
            else:
                return StuckReason.DEADLOCK
        else:  # 10-15分钟
            return StuckReason.TIMEOUT
            
        return StuckReason.UNKNOWN
    
    def recover_stuck_task(self, stuck_info: StuckTaskInfo, db_manager) -> bool:
        """
        恢复单个卡住的任务
        
        Args:
            stuck_info: 卡住任务信息
            db_manager: 数据库管理器
            
        Returns:
            bool: 恢复是否成功
        """
        task_id = stuck_info.task_id
        
        logger.info(f"🛡️ 开始恢复卡住任务 {task_id}")
        logger.info(f"  - 卡住时长: {stuck_info.stuck_duration_minutes:.1f}分钟")
        logger.info(f"  - 疑似原因: {stuck_info.suspected_reason.value}")
        logger.info(f"  - 恢复尝试: {stuck_info.recovery_attempts}")
        
        # 检查是否超过最大恢复尝试次数
        if stuck_info.recovery_attempts >= self.max_recovery_attempts:
            logger.error(f"🛡️ 任务 {task_id} 超过最大恢复尝试次数，需要人工介入")
            return self._escalate_to_manual_intervention(stuck_info, db_manager)
            
        # 选择恢复策略
        strategies = self.recovery_strategies.get(
            stuck_info.suspected_reason, 
            [RecoveryStrategy.RESET_PENDING]
        )
        
        strategy = strategies[min(stuck_info.recovery_attempts, len(strategies) - 1)]
        
        try:
            success = self._execute_recovery_strategy(strategy, stuck_info, db_manager)
            
            # 记录恢复操作
            recovery_action = RecoveryAction(
                task_id=task_id,
                action_time=datetime.now(),
                strategy=strategy,
                reason=stuck_info.suspected_reason,
                success=success
            )
            
            with self.lock:
                self.recovery_history.append(recovery_action)
                if success:
                    # 恢复成功，从缓存中移除
                    self.stuck_tasks_cache.pop(task_id, None)
                else:
                    # 恢复失败，增加尝试次数
                    if task_id in self.stuck_tasks_cache:
                        self.stuck_tasks_cache[task_id].recovery_attempts += 1
                        
            if success:
                logger.info(f"🛡️ 任务 {task_id} 恢复成功，策略: {strategy.value}")
            else:
                logger.error(f"🛡️ 任务 {task_id} 恢复失败，策略: {strategy.value}")
                
            return success
            
        except Exception as e:
            logger.error(f"🛡️ 恢复任务 {task_id} 时发生异常: {e}")
            return False
    
    def _execute_recovery_strategy(self, strategy: RecoveryStrategy, 
                                 stuck_info: StuckTaskInfo, db_manager) -> bool:
        """执行具体的恢复策略"""
        task_id = stuck_info.task_id
        
        try:
            session = db_manager.get_session()
            from app.database.repository import PublishingTaskRepository, PublishingLogRepository
            task_repo = PublishingTaskRepository(session)
            log_repo = PublishingLogRepository(session)
            
            if strategy == RecoveryStrategy.RESET_PENDING:
                # 重置为待处理状态
                task_repo.update(task_id, {
                    'status': 'pending',
                    'updated_at': datetime.now()
                })
                
                log_repo.create_log(
                    task_id=task_id,
                    status="recovered",
                    error_message=f"从卡住状态恢复: {stuck_info.suspected_reason.value}"
                )
                
            elif strategy == RecoveryStrategy.FORCE_RETRY:
                # 强制重试
                task_repo.update(task_id, {
                    'status': 'retry',
                    'retry_count': stuck_info.retry_count + 1,
                    'updated_at': datetime.now()
                })
                
                log_repo.create_log(
                    task_id=task_id,
                    status="force_retry",
                    error_message=f"强制重试恢复: {stuck_info.suspected_reason.value}"
                )
                
            elif strategy == RecoveryStrategy.ESCALATE_PRIORITY:
                # 提升优先级并重置
                task_repo.update(task_id, {
                    'status': 'pending',
                    'priority': min((stuck_info.retry_count or 0) + 1, 5),
                    'updated_at': datetime.now()
                })
                
                log_repo.create_log(
                    task_id=task_id,
                    status="priority_escalated",
                    error_message=f"优先级提升恢复: {stuck_info.suspected_reason.value}"
                )
                
            elif strategy == RecoveryStrategy.MANUAL_INTERVENTION:
                # 标记为需要人工介入
                task_repo.update(task_id, {
                    'status': 'failed',
                    'error_message': f"需要人工介入: {stuck_info.suspected_reason.value}",
                    'updated_at': datetime.now()
                })
                
                log_repo.create_log(
                    task_id=task_id,
                    status="manual_intervention_required",
                    error_message=f"需要人工介入: {stuck_info.suspected_reason.value}"
                )
                
            elif strategy == RecoveryStrategy.ABORT_TASK:
                # 终止任务
                task_repo.update(task_id, {
                    'status': 'cancelled',
                    'error_message': f"自动终止: {stuck_info.suspected_reason.value}",
                    'updated_at': datetime.now()
                })
                
                log_repo.create_log(
                    task_id=task_id,
                    status="auto_cancelled",
                    error_message=f"自动终止: {stuck_info.suspected_reason.value}"
                )
                
            session.commit()
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"🛡️ 执行恢复策略失败: {e}")
            return False
        finally:
            db_manager.remove_session()
    
    def _escalate_to_manual_intervention(self, stuck_info: StuckTaskInfo, db_manager) -> bool:
        """升级到人工介入"""
        logger.warning(f"🛡️ 任务 {stuck_info.task_id} 升级到人工介入")
        
        # 执行人工介入策略
        return self._execute_recovery_strategy(
            RecoveryStrategy.MANUAL_INTERVENTION, stuck_info, db_manager
        )
    
    def _get_recovery_attempts(self, task_id: int) -> int:
        """获取任务的恢复尝试次数"""
        with self.lock:
            if task_id in self.stuck_tasks_cache:
                return self.stuck_tasks_cache[task_id].recovery_attempts
                
        # 从历史记录中统计
        attempts = 0
        cutoff_time = datetime.now() - timedelta(hours=24)  # 只统计24小时内的尝试
        
        for action in self.recovery_history:
            if action.task_id == task_id and action.action_time > cutoff_time:
                attempts += 1
                
        return attempts
    
    def start_monitoring(self, db_manager):
        """启动监控线程"""
        if self.is_monitoring:
            logger.warning("🛡️ 恢复监控已在运行")
            return
            
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop, 
            args=(db_manager,), 
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info("🛡️ 卡住任务监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            
        logger.info("🛡️ 卡住任务监控已停止")
    
    def _monitoring_loop(self, db_manager):
        """监控循环"""
        logger.info("🛡️ 卡住任务监控循环启动")
        
        while self.is_monitoring:
            try:
                # 检测卡住的任务
                stuck_tasks = self.detect_stuck_tasks(db_manager)
                
                # 恢复卡住的任务
                for stuck_info in stuck_tasks:
                    if self.is_monitoring:  # 检查是否还在监控
                        self.recover_stuck_task(stuck_info, db_manager)
                        
                # 清理过期的历史记录
                self._cleanup_history()
                
                # 等待下次检查
                time.sleep(self.recovery_check_interval)
                
            except Exception as e:
                logger.error(f"🛡️ 监控循环异常: {e}")
                time.sleep(30)  # 异常时短暂休眠
                
        logger.info("🛡️ 卡住任务监控循环结束")
    
    def _cleanup_history(self):
        """清理过期的历史记录"""
        cutoff_time = datetime.now() - timedelta(days=7)  # 保留7天记录
        
        with self.lock:
            self.recovery_history = [
                action for action in self.recovery_history 
                if action.action_time > cutoff_time
            ]
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """获取恢复统计信息"""
        with self.lock:
            total_attempts = len(self.recovery_history)
            successful_attempts = sum(1 for action in self.recovery_history if action.success)
            
            # 按原因分组统计
            reason_stats = {}
            for action in self.recovery_history:
                reason = action.reason.value
                if reason not in reason_stats:
                    reason_stats[reason] = {'total': 0, 'success': 0}
                reason_stats[reason]['total'] += 1
                if action.success:
                    reason_stats[reason]['success'] += 1
                    
            # 按策略分组统计
            strategy_stats = {}
            for action in self.recovery_history:
                strategy = action.strategy.value
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {'total': 0, 'success': 0}
                strategy_stats[strategy]['total'] += 1
                if action.success:
                    strategy_stats[strategy]['success'] += 1
                    
            return {
                'total_recovery_attempts': total_attempts,
                'successful_recoveries': successful_attempts,
                'success_rate': successful_attempts / total_attempts if total_attempts > 0 else 0,
                'currently_stuck_tasks': len(self.stuck_tasks_cache),
                'reason_breakdown': reason_stats,
                'strategy_breakdown': strategy_stats,
                'monitoring_active': self.is_monitoring
            }

# 全局实例
stuck_task_recovery_manager = StuckTaskRecoveryManager()

def detect_and_recover_stuck_tasks(db_manager) -> Dict[str, Any]:
    """
    便捷函数：检测并恢复卡住的任务
    
    Args:
        db_manager: 数据库管理器
        
    Returns:
        Dict: 恢复结果统计
    """
    stuck_tasks = stuck_task_recovery_manager.detect_stuck_tasks(db_manager)
    
    if not stuck_tasks:
        return {'stuck_count': 0, 'recovered_count': 0}
        
    recovered_count = 0
    for stuck_info in stuck_tasks:
        if stuck_task_recovery_manager.recover_stuck_task(stuck_info, db_manager):
            recovered_count += 1
            
    return {
        'stuck_count': len(stuck_tasks),
        'recovered_count': recovered_count,
        'recovery_rate': recovered_count / len(stuck_tasks) if stuck_tasks else 0
    }