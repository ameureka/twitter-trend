#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强型任务调度器 - 优化的任务调度和执行管理

主要改进:
1. 智能重试机制
2. 任务优先级管理
3. 并发控制
4. 性能监控
5. 错误恢复
6. 资源管理
"""

import asyncio
import os
import time
import random
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import threading
from queue import PriorityQueue, Empty

from app.core.content_generator import ContentGenerator
from app.core.publisher import TwitterPublisher
from app.core.global_task_creator import GlobalTaskCreator
from app.database.repository import (
    ContentSourceRepository,
    ProjectRepository,
    PublishingLogRepository,
    PublishingTaskRepository,
)
from app.database.models import PublishingTask
from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config
from app.utils.path_manager import get_path_manager
from app.utils.dynamic_path_manager import get_dynamic_path_manager
from app.utils.performance_monitor import PerformanceMonitor
from app.utils.retry_handler import ErrorHandler
from app.utils.error_classifier import error_classifier, classify_and_handle_error
from app.utils.priority_calculator import priority_calculator, calculate_task_priority, get_priority_level
from app.utils.optimal_timing_predictor import optimal_timing_predictor, predict_best_publish_time
from app.utils.stuck_task_recovery import stuck_task_recovery_manager, detect_and_recover_stuck_tasks
from app.utils.database_lock_manager import get_database_lock_manager, execute_with_lock_protection
from app.utils.data_integrity_checker import get_data_integrity_checker, perform_integrity_check

logger = get_logger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    URGENT = 0


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class TaskExecution:
    """任务执行信息"""
    task_id: int
    priority: TaskPriority
    scheduled_time: datetime
    retry_count: int = 0
    last_error: Optional[str] = None
    
    def __lt__(self, other):
        """用于优先队列排序"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.scheduled_time < other.scheduled_time


class EnhancedTaskScheduler:
    """增强型任务调度器"""
    
    def __init__(self, db_manager=None, content_generator=None, publisher=None):
        self.config = get_enhanced_config()
        self.path_manager = get_path_manager()
        self.dynamic_path_manager = get_dynamic_path_manager()
        
        # 如果提供了数据库管理器，使用它来获取session
        if db_manager:
            self.db_manager = db_manager
            # 使用数据库管理器的session
            session = db_manager.get_session()
            self.task_repo = PublishingTaskRepository(session)
            self.log_repo = PublishingLogRepository(session)
            self.project_repo = ProjectRepository(session)
            self.content_source_repo = ContentSourceRepository(session)
        else:
            # 兼容性：如果没有提供数据库管理器，尝试创建默认的
            from app.database.db_manager import EnhancedDatabaseManager
            self.db_manager = EnhancedDatabaseManager()
            session = self.db_manager.get_session()
            self.task_repo = PublishingTaskRepository(session)
            self.log_repo = PublishingLogRepository(session)
            self.project_repo = ProjectRepository(session)
            self.content_source_repo = ContentSourceRepository(session)
        
        # 使用提供的组件或创建默认的
        self.content_generator = content_generator or ContentGenerator()
        self.publisher = publisher or TwitterPublisher()
        self.performance_monitor = PerformanceMonitor()
        self.error_handler = ErrorHandler()
        
        # 🎯 Phase 3: 集成智能错误分类器
        self.error_classifier = error_classifier
        logger.info("✅ 智能错误分类器已集成到调度器")
        
        # 🎯 Phase 3.4: 集成优先级权重算法
        self.priority_calculator = priority_calculator
        logger.info("✅ 优先级权重算法已集成到调度器")
        
        # 📅 Phase 3.5: 集成最佳发布时间预测器
        self.timing_predictor = optimal_timing_predictor
        logger.info("✅ 最佳发布时间预测器已集成到调度器")
        
        # 🛡️ Phase 4.1: 集成卡住任务自动恢复管理器
        self.stuck_recovery_manager = stuck_task_recovery_manager
        logger.info("✅ 卡住任务自动恢复管理器已集成到调度器")
        
        # 🔒 Phase 4.2: 集成数据库锁管理器
        db_path = self.config.get('database', {}).get('path', './data/twitter_publisher.db')
        self.lock_manager = get_database_lock_manager(db_path)
        logger.info("✅ 数据库锁管理器已集成到调度器")
        
        # 🔍 Phase 4.3: 集成数据完整性检查器
        self.integrity_checker = get_data_integrity_checker(db_path)
        logger.info("✅ 数据完整性检查器已集成到调度器")
        
        # 初始化全局任务创建器
        self.global_task_creator = GlobalTaskCreator(self.db_manager)
        
        # 调度器配置
        scheduler_config = self.config.get('scheduling', {})
        self.max_workers = scheduler_config.get('max_workers', 5)
        self.batch_size = scheduler_config.get('batch_size', 3)
        self.check_interval = scheduler_config.get('check_interval', 60)
        self.max_retries = scheduler_config.get('max_retries', 3)
        self.stuck_task_timeout = scheduler_config.get('stuck_task_timeout', 300)
        
        # ⏰ Phase 3.3: 任务超时保护配置
        self.task_timeout_minutes = scheduler_config.get('task_timeout_minutes', 5)
        self.task_timeout_seconds = self.task_timeout_minutes * 60
        logger.info(f"⏰ 任务超时保护已启用: {self.task_timeout_minutes} 分钟")
        
        # 每日任务数量配置
        self.daily_min_tasks = scheduler_config.get('daily_min_tasks', 5)
        self.daily_max_tasks = scheduler_config.get('daily_max_tasks', 6)
        
        # 运行状态
        self.is_running = False
        self.executor = None
        self.task_queue = PriorityQueue()
        self.running_tasks = {}
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'retried': 0,
            'start_time': None
        }
        
        # 线程锁
        self.lock = threading.Lock() # 用于保护调度器内部状态
        self.db_write_lock = threading.Lock() # 用于保护数据库写入
        
    def start(self) -> Dict[str, Any]:
        """
        启动调度器
        
        Returns:
            启动结果信息
        """
        if self.is_running:
            return {
                'success': False,
                'message': '调度器已在运行中'
            }
            
        try:
            self.is_running = True
            self.stats['start_time'] = datetime.now()
            self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
            
            # 启动主调度循环
            threading.Thread(target=self._scheduler_loop, daemon=True).start()
            
            # 启动监控线程
            threading.Thread(target=self._monitor_loop, daemon=True).start()
            
            # 🛡️ Phase 4.1: 启动卡住任务恢复监控
            self.stuck_recovery_manager.start_monitoring(self.db_manager)
            
            logger.info(f"增强型任务调度器启动成功，最大工作线程: {self.max_workers}")
            
            return {
                'success': True,
                'message': '调度器启动成功',
                'config': {
                    'max_workers': self.max_workers,
                    'batch_size': self.batch_size,
                    'check_interval': self.check_interval
                }
            }
            
        except Exception as e:
            self.is_running = False
            logger.error(f"调度器启动失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'调度器启动失败: {str(e)}'
            }
            
    def stop(self) -> Dict[str, Any]:
        """
        停止调度器
        
        Returns:
            停止结果信息
        """
        if not self.is_running:
            return {
                'success': False,
                'message': '调度器未在运行'
            }
            
        try:
            self.is_running = False
            
            # 🛡️ Phase 4.1: 停止卡住任务恢复监控
            self.stuck_recovery_manager.stop_monitoring()
            
            # 等待正在执行的任务完成
            if self.executor:
                self.executor.shutdown(wait=True, timeout=60)
                
            # 清理运行状态
            self._cleanup_running_tasks()
            
            logger.info("增强型任务调度器已停止")
            
            return {
                'success': True,
                'message': '调度器已停止',
                'stats': self.get_stats()
            }
            
        except Exception as e:
            logger.error(f"调度器停止失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'调度器停止失败: {str(e)}'
            }
            
    def schedule_task(self, task_id: int, priority: TaskPriority = TaskPriority.NORMAL,
                     delay_seconds: int = 0) -> bool:
        """
        调度单个任务
        
        Args:
            task_id: 任务ID
            priority: 任务优先级
            delay_seconds: 延迟执行秒数
            
        Returns:
            是否成功调度
        """
        try:
            scheduled_time = datetime.now() + timedelta(seconds=delay_seconds)
            
            task_execution = TaskExecution(
                task_id=task_id,
                priority=priority,
                scheduled_time=scheduled_time
            )
            
            self.task_queue.put(task_execution)
            logger.info(f"任务 {task_id} 已调度，优先级: {priority.name}")
            
            return True
            
        except Exception as e:
            logger.error(f"调度任务 {task_id} 失败: {e}")
            return False
            
    def schedule_batch(self, limit: int = None) -> Dict[str, Any]:
        """
        批量调度待处理任务
        
        Args:
            limit: 最大调度数量
            
        Returns:
            调度结果信息
        """
        try:
            # 获取待处理任务
            pending_tasks = self.task_repo.get_pending_tasks(
                limit=limit or self.batch_size
            )
            
            scheduled_count = 0
            for task in pending_tasks:
                # 根据任务属性确定优先级
                priority = self._determine_task_priority(task)
                
                if self.schedule_task(task.id, priority):
                    scheduled_count += 1
                    
            logger.info(f"批量调度完成，调度了 {scheduled_count} 个任务")
            
            return {
                'success': True,
                'scheduled_count': scheduled_count,
                'total_pending': len(pending_tasks)
            }
            
        except Exception as e:
            logger.error(f"批量调度失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'批量调度失败: {str(e)}'
            }
            
    def get_stats(self) -> Dict[str, Any]:
        """
        获取调度器统计信息
        
        Returns:
            统计信息
        """
        stats = self.stats.copy()
        
        # 添加运行时信息
        stats['is_running'] = self.is_running
        stats['queue_size'] = self.task_queue.qsize()
        stats['running_tasks_count'] = len(self.running_tasks)
        
        if stats['start_time']:
            stats['uptime_seconds'] = (datetime.now() - stats['start_time']).total_seconds()
            
        # 添加性能指标
        stats['performance'] = self.performance_monitor.get_metrics()
        
        return stats
        
    def _scheduler_loop(self):
        """主调度循环"""
        logger.info("调度器主循环启动")
        
        while self.is_running:
            try:
                # 处理队列中的任务
                self._process_task_queue()
                
                # 检查卡住的任务
                self._check_stuck_tasks()
                
                # 自动调度新任务 - 使用全局任务创建器
                if self.task_queue.qsize() < self.batch_size:
                    try:
                        # 使用全局任务创建器创建每日任务
                        result = self.global_task_creator.create_daily_tasks()
                        if result.get('success'):
                            logger.info(f"全局任务创建器创建了 {result.get('created_count', 0)} 个任务")
                            # 调度新创建的任务
                            self.schedule_batch()
                        else:
                            logger.warning(f"全局任务创建器未创建新任务: {result.get('message', '未知原因')}")
                    except Exception as e:
                        logger.error(f"全局任务创建器执行失败: {e}", exc_info=True)
                        # 如果全局任务创建器失败，回退到原有的调度方式
                        self.schedule_batch()
                    
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"调度循环异常: {e}", exc_info=True)
                time.sleep(5)  # 异常时短暂休眠
                
        logger.info("调度器主循环结束")
        
    def _process_task_queue(self):
        """⏰ Phase 3.3: 处理任务队列（包含超时保护）"""
        available_workers = self.max_workers - len(self.running_tasks)
        
        # 检查运行中任务的超时情况
        self._check_task_timeouts()
        
        for _ in range(min(available_workers, self.task_queue.qsize())):
            try:
                # 获取下一个任务（非阻塞）
                task_execution = self.task_queue.get_nowait()
                
                # 检查是否到了执行时间
                if datetime.now() < task_execution.scheduled_time:
                    # 重新放回队列
                    self.task_queue.put(task_execution)
                    break
                    
                # 提交任务执行（带超时保护）
                future = self.executor.submit(self._execute_task_with_timeout, task_execution)
                
                with self.lock:
                    self.running_tasks[task_execution.task_id] = {
                        'future': future,
                        'start_time': datetime.now(),
                        'task_execution': task_execution,
                        'timeout_seconds': self.task_timeout_seconds
                    }
                    
            except Empty:
                break
            except Exception as e:
                logger.error(f"处理任务队列异常: {e}")
    
    def _check_task_timeouts(self):
        """⏰ 检查任务超时情况"""
        current_time = datetime.now()
        timed_out_tasks = []
        
        with self.lock:
            for task_id, task_info in self.running_tasks.items():
                start_time = task_info['start_time']
                timeout_seconds = task_info.get('timeout_seconds', self.task_timeout_seconds)
                
                elapsed_time = (current_time - start_time).total_seconds()
                
                if elapsed_time > timeout_seconds:
                    logger.warning(f"⏰ 任务 {task_id} 执行超时: {elapsed_time:.1f}s > {timeout_seconds}s")
                    timed_out_tasks.append((task_id, task_info))
                    
        # 处理超时任务
        for task_id, task_info in timed_out_tasks:
            self._handle_task_timeout(task_id, task_info)
    
    def _handle_task_timeout(self, task_id: int, task_info: Dict[str, Any]):
        """⏰ 处理任务超时"""
        try:
            future = task_info['future']
            task_execution = task_info['task_execution']
            elapsed_time = (datetime.now() - task_info['start_time']).total_seconds()
            
            logger.error(f"⏰ 强制取消超时任务 {task_id} (运行时间: {elapsed_time:.1f}s)")
            
            # 尝试取消任务
            future.cancel()
            
            # 从运行任务列表中移除
            with self.lock:
                self.running_tasks.pop(task_id, None)
                
            # 创建超时错误消息
            timeout_error = f"任务执行超时 ({elapsed_time:.1f}s > {self.task_timeout_seconds}s)"
            
            # 使用错误分类器处理超时错误
            session = self.db_manager.get_session()
            try:
                task_repo = PublishingTaskRepository(session)
                log_repo = PublishingLogRepository(session)
                
                # 处理超时失败
                self._handle_task_failure(task_execution, timeout_error, task_repo, log_repo)
                session.commit()
                
            except Exception as db_error:
                logger.error(f"处理超时任务数据库操作失败: {db_error}")
                session.rollback()
            finally:
                self.db_manager.remove_session()
                
        except Exception as e:
            logger.error(f"处理任务超时异常: {e}")
    
    def _execute_task_with_timeout(self, task_execution: TaskExecution) -> Dict[str, Any]:
        """⏰ 带超时保护的任务执行包装器"""
        task_id = task_execution.task_id
        
        try:
            # 使用超时执行任务
            logger.info(f"⏰ 开始执行任务 {task_id} (超时限制: {self.task_timeout_seconds}s)")
            result = self._execute_task(task_execution)
            
            # 清理运行状态
            with self.lock:
                self.running_tasks.pop(task_id, None)
                
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"⏰ 任务 {task_id} 执行异常: {error_msg}")
            
            # 清理运行状态
            with self.lock:
                self.running_tasks.pop(task_id, None)
                
            return {
                'success': False,
                'task_id': task_id,
                'error': error_msg,
                'timeout_protected': True
            }
                
    def _execute_task(self, task_execution: TaskExecution, task_repo: PublishingTaskRepository, 
                      log_repo: PublishingLogRepository, content_source_repo: ContentSourceRepository) -> Dict[str, Any]:
        """
        执行单个任务（使用提供的仓库实例）
        
        Args:
            task_execution: 任务执行信息
            task_repo: 任务仓库实例
            log_repo: 日志仓库实例
            content_source_repo: 内容源仓库实例
            
        Returns:
            执行结果
        """
        task_id = task_execution.task_id
        start_time = time.time()
        
        try:
            # 获取任务详情
            task = task_repo.get_by_id(task_id)
            
            if not task:
                raise ValueError(f"任务 {task_id} 不存在")
            
            # 检查任务状态
            if task.status not in ['pending', 'retry']:
                raise ValueError(f"任务 {task_id} 状态不正确: {task.status}")
            
            # 更新任务状态为运行中
            task_repo.update(task_id, {'status': TaskStatus.RUNNING.value})
            
            # 记录开始执行日志
            log_repo.create_log(
                task_id=task_id,
                status="running"
            )
            
            # 获取内容源信息
            logger.info(f"[SCHEDULER_DEBUG] 获取内容源信息，source_id: {task.source_id}")
            content_source = content_source_repo.get_source_by_id(task.source_id)
            logger.info(f"[SCHEDULER_DEBUG] 内容源信息: {content_source}")
            if not content_source:
                logger.error(f"[SCHEDULER_DEBUG] 内容源 {task.source_id} 不存在")
                raise ValueError(f"内容源 {task.source_id} 不存在")
            
            # 使用动态路径管理器处理媒体文件路径
            import os
            logger.info(f"[SCHEDULER_DEBUG] 原始媒体路径: {task.media_path}")
            
            # 验证媒体文件
            validation_result = self.dynamic_path_manager.validate_media_file(task.media_path)
            logger.info(f"[SCHEDULER_DEBUG] 媒体文件验证结果: {validation_result}")
            
            if validation_result['is_hardcoded']:
                logger.warning(f"[SCHEDULER_DEBUG] 检测到硬编码路径: {task.media_path}")
                logger.info(f"[SCHEDULER_DEBUG] 转换为相对路径: {validation_result['converted_path']}")
            
            if not validation_result['exists']:
                error_msg = f"媒体文件不存在: {validation_result['resolved_path']} (原路径: {task.media_path})"
                if validation_result['error']:
                    error_msg += f", 错误: {validation_result['error']}"
                
                logger.error(f"[SCHEDULER_DEBUG] {error_msg}")
                
                # 尝试通过文件名查找媒体文件
                filename = os.path.basename(task.media_path)
                found_file = self.dynamic_path_manager.find_media_file(filename)
                
                if found_file:
                    logger.info(f"[SCHEDULER_DEBUG] 通过文件名找到媒体文件: {found_file}")
                    media_file_path = found_file
                    media_file = str(media_file_path)
                else:
                    # 立即停止任务流程并记录为失败
                    task_repo.update(task_id, {
                        'status': TaskStatus.FAILED.value,
                        'updated_at': datetime.now()
                    })
                    
                    # 记录失败日志
                    log_repo.create_log(
                        task_id=task_id,
                        status="failed",
                        error_message=error_msg,
                        duration_seconds=time.time() - start_time
                    )
                    
                    raise FileNotFoundError(error_msg)
            else:
                # 使用验证通过的路径
                media_file_path = self.dynamic_path_manager.resolve_media_path(task.media_path)
                media_file = str(media_file_path)
                logger.info(f"[SCHEDULER_DEBUG] 解析后媒体路径: {media_file}")
            
            # 查找对应的JSON元数据文件
            media_dir = os.path.dirname(media_file)
            media_name = os.path.splitext(os.path.basename(media_file))[0]
            metadata_file = os.path.join(media_dir, f"{media_name}.json")
            logger.info(f"[SCHEDULER_DEBUG] 查找元数据文件: {metadata_file}")
            
            # 如果单独的JSON文件不存在，尝试查找outputs目录中的综合报告文件
            if not os.path.exists(metadata_file):
                logger.info(f"[SCHEDULER_DEBUG] 单独JSON文件不存在，查找outputs目录")
                outputs_dir = os.path.join(media_dir, "outputs")
                logger.info(f"[SCHEDULER_DEBUG] outputs目录: {outputs_dir}")
                if os.path.exists(outputs_dir):
                    # 查找stage3_final_report文件
                    for file in os.listdir(outputs_dir):
                        if file.startswith("stage3_final_report") and file.endswith(".json"):
                            metadata_file = os.path.join(outputs_dir, file)
                            logger.info(f"[SCHEDULER_DEBUG] 找到stage3报告文件: {metadata_file}")
                            break
            
            # 如果outputs目录中也没有找到，尝试查找uploader_json目录中的en_prompt_results文件
            if not os.path.exists(metadata_file):
                logger.info(f"[SCHEDULER_DEBUG] outputs目录中未找到，查找uploader_json目录")
                # 获取项目根目录（media_dir的上级目录）
                project_dir = os.path.dirname(media_dir)
                uploader_json_dir = os.path.join(project_dir, "uploader_json")
                logger.info(f"[SCHEDULER_DEBUG] uploader_json目录: {uploader_json_dir}")
                if os.path.exists(uploader_json_dir):
                    # 查找en_prompt_results文件
                    for file in os.listdir(uploader_json_dir):
                        if file.startswith("en_prompt_results") and file.endswith(".json"):
                            metadata_file = os.path.join(uploader_json_dir, file)
                            logger.info(f"[SCHEDULER_DEBUG] 找到en_prompt_results文件: {metadata_file}")
                            break
            
            if not os.path.exists(metadata_file):
                logger.error(f"[SCHEDULER_DEBUG] 元数据文件不存在: {metadata_file}")
                raise FileNotFoundError(f"元数据文件不存在: {metadata_file}")
            
            logger.info(f"[SCHEDULER_DEBUG] 最终使用的元数据文件: {metadata_file}")
            
            # 生成内容
            logger.info(f"[SCHEDULER_DEBUG] 任务 {task_id} 开始生成内容")
            logger.info(f"[SCHEDULER_DEBUG] 媒体路径: {task.media_path}")
            logger.info(f"[SCHEDULER_DEBUG] 元数据文件: {metadata_file}")
            logger.info(f"[SCHEDULER_DEBUG] 视频文件名: {os.path.basename(media_file)}")
            
            content_result = self.content_generator.generate_content(
                video_filename=os.path.basename(media_file),
                metadata_path=metadata_file,
                language='en'  # 明确指定使用英文
            )
            
            logger.info(f"[SCHEDULER_DEBUG] 内容生成器返回结果: {content_result}")
            
            # 包装返回结果以保持兼容性
            if content_result:
                content_result = {
                    'success': True,
                    'content': content_result,
                    'message': '内容生成成功'
                }
            else:
                content_result = {
                    'success': False,
                    'content': None,
                    'message': '内容生成失败'
                }
            
            logger.info(f"[SCHEDULER_DEBUG] 任务 {task_id} 内容生成完成，结果: {content_result.get('success', False)}")
            logger.info(f"[SCHEDULER_DEBUG] 生成的内容: {content_result.get('content')}")
            
            if not content_result['success']:
                logger.error(f"[SCHEDULER_DEBUG] 内容生成失败: {content_result['message']}")
                raise Exception(f"内容生成失败: {content_result['message']}")
                
            # 发布到Twitter
            logger.info(f"[SCHEDULER_DEBUG] 任务 {task_id} 开始发布到Twitter")
            logger.info(f"[SCHEDULER_DEBUG] 发布内容: {content_result['content']}")
            logger.info(f"[SCHEDULER_DEBUG] 发布媒体路径: {task.media_path}")
            
            publish_result = self._publish_to_twitter(
                content_result['content'],
                task.media_path
            )
            
            logger.info(f"[SCHEDULER_DEBUG] 任务 {task_id} 发布完成，结果: {publish_result.get('success', False)}")
            logger.info(f"[SCHEDULER_DEBUG] 发布结果详情: {publish_result}")
            
            if not publish_result['success']:
                logger.error(f"[SCHEDULER_DEBUG] 发布失败: {publish_result['message']}")
                raise Exception(f"发布失败: {publish_result['message']}")
                
            # 更新任务状态为完成
            task_repo.update(task_id, {
                'status': TaskStatus.COMPLETED.value,
                'updated_at': datetime.now()
            })
            
            # 记录成功日志
            log_repo.create_log(
                task_id=task_id,
                status="success",
                tweet_id=publish_result.get('tweet_id'),
                duration_seconds=time.time() - start_time
            )
            
            # 更新统计
            with self.lock:
                self.stats['total_processed'] += 1
                self.stats['successful'] += 1
                
            logger.info(f"任务 {task_id} 执行成功")
            
            return {
                'success': True,
                'task_id': task_id,
                'execution_time': time.time() - start_time
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"任务 {task_id} 执行失败: {error_msg}")
            
            # 处理重试逻辑
            should_retry = self._handle_task_failure(
                task_execution, error_msg, task_repo, log_repo
            )
            
            # 更新统计
            with self.lock:
                self.stats['total_processed'] += 1
                if should_retry:
                    self.stats['retried'] += 1
                else:
                    self.stats['failed'] += 1
                    
            return {
                'success': False,
                'task_id': task_id,
                'error': error_msg,
                'retry_scheduled': should_retry
            }
            
        finally:
            # 清理运行状态
            with self.lock:
                self.running_tasks.pop(task_id, None)
                
    def _handle_task_failure(self, task_execution: TaskExecution, error_msg: str, 
                           task_repo: PublishingTaskRepository, log_repo: PublishingLogRepository) -> bool:
        """
        🎯 Phase 3: 智能错误处理 - 使用错误分类器决定重试策略
        
        Args:
            task_execution: 任务执行信息
            error_msg: 错误消息
            task_repo: 任务仓库实例
            log_repo: 日志仓库实例
            
        Returns:
            是否安排了重试
        """
        task_id = task_execution.task_id
        
        try:
            # 🧠 使用智能错误分类器分析错误
            error_analysis = classify_and_handle_error(error_msg, task_execution.retry_count + 1)
            error_type = error_analysis['error_type']
            should_retry = error_analysis['should_retry']
            retry_delay = error_analysis['retry_delay']
            needs_human = error_analysis['needs_human_intervention']
            
            logger.info(f"🔍 任务 {task_id} 错误分析结果:")
            logger.info(f"  - 错误类型: {error_type}")
            logger.info(f"  - 应该重试: {should_retry}")
            logger.info(f"  - 重试延迟: {retry_delay}秒")
            logger.info(f"  - 需要人工介入: {needs_human}")
            
            if needs_human:
                logger.warning(f"⚠️ 任务 {task_id} 需要人工介入: {error_type}")
                # 标记为需要人工介入的失败
                task_repo.update(task_id, {
                    'status': 'failed',
                    'error_type': error_type,
                    'updated_at': datetime.now()
                })
                
                log_repo.create_log(
                    task_id=task_id,
                    status="failed",
                    error_message=f"[{error_type}] {error_msg} - 需要人工介入"
                )
                
                return False
                
            if not should_retry or retry_delay is None:
                logger.info(f"❌ 任务 {task_id} 达到重试限制或不适合重试")
                # 标记为最终失败
                task_repo.update(task_id, {
                    'status': 'failed',
                    'error_type': error_type,
                    'updated_at': datetime.now()
                })
                
                log_repo.create_log(
                    task_id=task_id,
                    status="failed",
                    error_message=f"[{error_type}] {error_msg}"
                )
                
                return False
                
            # 🔄 安排智能重试
            logger.info(f"🔄 任务 {task_id} 将在 {retry_delay} 秒后重试 (类型: {error_type})")
            
            # 更新任务状态为重试中
            task_repo.update(task_id, {
                'status': 'retry',
                'error_type': error_type,
                'updated_at': datetime.now()
            })
            
            # 记录智能重试日志
            log_repo.create_log(
                task_id=task_id,
                status="retry",
                error_message=f"[{error_type}] 智能重试 #{task_execution.retry_count + 1}: {error_msg}"
            )
            
            # 安排重试任务
            retry_execution = TaskExecution(
                task_id=task_id,
                priority=task_execution.priority,
                scheduled_time=datetime.now() + timedelta(seconds=retry_delay),
                retry_count=task_execution.retry_count + 1,
                last_error=error_msg
            )
            
            self.task_queue.put(retry_execution)
            
            return True
            
        except Exception as e:
            logger.error(f"🔥 智能错误处理异常: {e}")
            # 回退到简单重试逻辑
            return self._fallback_retry_logic(task_execution, error_msg, task_repo, log_repo)
    
    def optimize_task_timing(self, task: PublishingTask) -> datetime:
        """
        📅 Phase 3.5: 使用时间预测器优化任务执行时间
        
        Args:
            task: 发布任务
            
        Returns:
            datetime: 优化后的执行时间
        """
        try:
            # 获取任务属性
            content_type = getattr(task, 'content_type', 'normal')
            project_priority = getattr(task, 'project_priority', 3)
            
            # 计算最小延迟（避免过于频繁发布）
            last_publish_time = self._get_last_publish_time(task.project_id)
            min_delay_minutes = 30  # 默认30分钟间隔
            
            if last_publish_time:
                time_since_last = (datetime.now() - last_publish_time).total_seconds() / 60
                if time_since_last < 180:  # 3小时内有发布
                    min_delay_minutes = max(30, 180 - int(time_since_last))
                    
            # 使用时间预测器预测最佳时间
            prediction = self.timing_predictor.predict_optimal_time(
                content_type=content_type,
                project_priority=project_priority,
                min_delay_minutes=min_delay_minutes,
                max_delay_hours=24  # 最多延迟24小时
            )
            
            logger.info(f"📅 任务 {task.id} 时间优化:")
            logger.info(f"  - 原计划时间: {task.scheduled_at}")
            logger.info(f"  - 优化后时间: {prediction.recommended_time}")
            logger.info(f"  - 置信度: {prediction.confidence_score:.2f}")
            logger.info(f"  - 推荐理由: {prediction.reasoning}")
            
            # 如果是高优先级任务且时间紧急，跳过优化
            if project_priority >= 4 and task.scheduled_at:
                time_diff = (datetime.now() - task.scheduled_at).total_seconds() / 3600
                if abs(time_diff) <= 1:  # 1小时内的紧急任务
                    logger.info(f"📅 任务 {task.id} 为紧急任务，跳过时间优化")
                    return task.scheduled_at or datetime.now()
                    
            return prediction.recommended_time
            
        except Exception as e:
            logger.error(f"📅 任务 {task.id} 时间优化失败: {e}")
            # 回退到原时间或当前时间
            return task.scheduled_at or datetime.now()
    
    def _get_last_publish_time(self, project_id: int) -> Optional[datetime]:
        """获取项目最后发布时间"""
        try:
            session = self.db_manager.get_session()
            log_repo = PublishingLogRepository(session)
            
            # 查询最近的成功发布记录
            recent_log = log_repo.get_recent_successful_publish(project_id)
            if recent_log:
                return recent_log.published_at
                
        except Exception as e:
            logger.error(f"获取最后发布时间失败: {e}")
        finally:
            self.db_manager.remove_session()
            
        return None
    
    def schedule_task_with_timing_optimization(self, task_id: int, 
                                             priority: TaskPriority = TaskPriority.NORMAL) -> bool:
        """
        📅 带时间优化的任务调度
        
        Args:
            task_id: 任务ID
            priority: 任务优先级
            
        Returns:
            是否成功调度
        """
        try:
            # 获取任务信息
            session = self.db_manager.get_session()
            task_repo = PublishingTaskRepository(session)
            task = task_repo.get_by_id(task_id)
            
            if not task:
                logger.error(f"任务 {task_id} 不存在")
                return False
                
            # 优化执行时间
            optimized_time = self.optimize_task_timing(task)
            
            # 更新任务的调度时间
            task_repo.update(task_id, {'scheduled_at': optimized_time})
            session.commit()
            
            # 创建任务执行对象
            task_execution = TaskExecution(
                task_id=task_id,
                priority=priority,
                scheduled_time=optimized_time
            )
            
            self.task_queue.put(task_execution)
            logger.info(f"📅 任务 {task_id} 已优化调度至 {optimized_time.strftime('%Y-%m-%d %H:%M')}")
            
            return True
            
        except Exception as e:
            logger.error(f"📅 带时间优化的任务调度失败: {e}")
            return False
        finally:
            self.db_manager.remove_session()
    
    def _fallback_retry_logic(self, task_execution: TaskExecution, error_msg: str,
                             task_repo: PublishingTaskRepository, log_repo: PublishingLogRepository) -> bool:
        """
        回退重试逻辑 - 当错误分类器失败时使用
        
        Args:
            task_execution: 任务执行信息
            error_msg: 错误消息
            task_repo: 任务仓库实例
            log_repo: 日志仓库实例
            
        Returns:
            是否安排了重试
        """
        task_id = task_execution.task_id
        
        logger.warning(f"🔄 任务 {task_id} 使用简单重试逻辑")
        
        # 检查是否应该重试
        if task_execution.retry_count >= self.max_retries:
            # 标记为最终失败
            task_repo.update(task_id, {
                'status': 'failed',
                'updated_at': datetime.now()
            })
            
            log_repo.create_log(
                task_id=task_id,
                status="failed",
                error_message=error_msg
            )
            
            return False
            
        # 计算重试延迟 - 简单指数退避
        retry_delay = min(60 * (2 ** task_execution.retry_count), 300)  # 最大5分钟
        
        # 更新任务状态为重试中
        task_repo.update(task_id, {
            'status': 'retry',
            'updated_at': datetime.now()
        })
        
        # 记录重试日志
        log_repo.create_log(
            task_id=task_id,
            status="retry",
            error_message=f"简单重试 #{task_execution.retry_count + 1}: {error_msg}"
        )
        
        # 安排重试
        retry_execution = TaskExecution(
            task_id=task_id,
            priority=task_execution.priority,
            scheduled_time=datetime.now() + timedelta(seconds=retry_delay),
            retry_count=task_execution.retry_count + 1,
            last_error=error_msg
        )
        
        self.task_queue.put(retry_execution)
        
        return True
            
    def _determine_task_priority(self, task: PublishingTask) -> TaskPriority:
        """
        🎯 Phase 3.4: 使用智能优先级权重算法确定任务优先级
        
        Args:
            task: 发布任务
            
        Returns:
            任务优先级
        """
        try:
            # 构建任务数据字典
            task_data = {
                'created_at': task.created_at,
                'scheduled_at': task.scheduled_at,
                'retry_count': task.retry_count or 0,
                'project_id': task.project_id,
                'project_priority': getattr(task, 'project_priority', 3),  # 默认中等优先级
                'content_type': getattr(task, 'content_type', 'normal')
            }
            
            # 使用优先级计算器计算得分
            priority_score = self.priority_calculator.calculate_priority_score(task_data)
            priority_level = get_priority_level(priority_score)
            
            # 根据得分映射到TaskPriority枚举
            if priority_score >= 80:
                task_priority = TaskPriority.URGENT
            elif priority_score >= 60:
                task_priority = TaskPriority.HIGH
            elif priority_score >= 40:
                task_priority = TaskPriority.NORMAL
            else:
                task_priority = TaskPriority.LOW
                
            logger.debug(f"🎯 任务 {task.id} 优先级计算: 得分={priority_score:.2f}, 级别={priority_level}, 枚举={task_priority.name}")
            
            return task_priority
            
        except Exception as e:
            logger.error(f"🎯 任务 {task.id} 优先级计算失败: {e}")
            # 回退到简单逻辑
            return self._simple_priority_fallback(task)
    
    def _simple_priority_fallback(self, task: PublishingTask) -> TaskPriority:
        """简单优先级回退逻辑"""
        # 根据重试次数调整优先级
        if task.retry_count > 2:
            return TaskPriority.LOW
        elif task.retry_count > 0:
            return TaskPriority.NORMAL
            
        # 根据创建时间调整优先级
        age_hours = (datetime.now() - task.created_at).total_seconds() / 3600
        if age_hours > 24:
            return TaskPriority.HIGH
        elif age_hours > 12:
            return TaskPriority.NORMAL
            
        return TaskPriority.NORMAL
        
    def _check_stuck_tasks(self):
        """检查并恢复卡住的任务（在独立的会话中运行）"""
        session = self.db_manager.get_session()
        try:
            task_repo = PublishingTaskRepository(session)
            log_repo = PublishingLogRepository(session)

            stuck_tasks = task_repo.get_stuck_tasks(
                self.stuck_task_timeout
            )

            if stuck_tasks:
                with self.db_write_lock:
                    for task in stuck_tasks:
                        logger.warning(f"发现卡住的任务 {task.id}，正在恢复...")
                        task_repo.update(task.id, {'status': TaskStatus.PENDING.value})
                        log_repo.create_log(
                            task_id=task.id,
                            status="stuck_recovered"
                        )
                    session.commit()
        except Exception as e:
            logger.error(f"检查卡住任务时出错: {e}", exc_info=True)
            with self.db_write_lock:
                session.rollback()
        finally:
            self.db_manager.remove_session()

    def _execute_task(self, task_execution: TaskExecution) -> Dict[str, Any]:
        """
        执行单个任务
        
        Args:
            task_execution: 任务执行信息
            
        Returns:
            执行结果
        """
        task_id = task_execution.task_id
        start_time = time.time()
        
        # 详细调试日志
        logger.info(f"[SCHEDULER_DEBUG] 开始执行任务 {task_id}")
        logger.info(f"[SCHEDULER_DEBUG] 任务执行信息: {task_execution}")
        
        session = self.db_manager.get_session()
        task_repo = PublishingTaskRepository(session)
        log_repo = PublishingLogRepository(session)
        content_source_repo = ContentSourceRepository(session)

        try:
            with self.db_write_lock:
                # 获取任务详情
                task = task_repo.get_by_id(task_id)
                logger.info(f"[SCHEDULER_DEBUG] 获取到任务: {task}")
                
                if not task:
                    logger.error(f"[SCHEDULER_DEBUG] 任务 {task_id} 不存在")
                    raise ValueError(f"任务 {task_id} 不存在")
                
                logger.info(f"[SCHEDULER_DEBUG] 任务状态: {task.status}")
                logger.info(f"[SCHEDULER_DEBUG] 任务内容数据: {task.content_data}")
                logger.info(f"[SCHEDULER_DEBUG] 任务媒体路径: {task.media_path}")
                
                # 🛠️ 智能任务状态检查和恢复
                if task.status not in ['pending', 'retry']:
                    if task.status == 'running':
                        # 检查是否是卡住的任务 - 如果运行时间超过阈值，重置状态
                        task_stuck_timeout = self.config.get('task.stuck_timeout', 300)  # 5分钟
                        
                        if task.updated_at:
                            time_since_update = (datetime.now() - task.updated_at).total_seconds()
                            if time_since_update > task_stuck_timeout:
                                logger.warning(f"[SCHEDULER_DEBUG] 任务 {task_id} 已运行{time_since_update:.0f}秒，超过阈值{task_stuck_timeout}秒，重置为待执行状态")
                                task_repo.update(task_id, {'status': 'pending'})
                                session.commit()
                            else:
                                logger.info(f"[SCHEDULER_DEBUG] 任务 {task_id} 正在运行中(已运行{time_since_update:.0f}秒)，跳过执行")
                                return {'success': False, 'reason': 'task_already_running', 'running_time': time_since_update}
                        else:
                            # 如果没有更新时间，直接重置为待执行
                            logger.warning(f"[SCHEDULER_DEBUG] 任务 {task_id} 状态为running但无更新时间，重置为待执行状态")
                            task_repo.update(task_id, {'status': 'pending'})
                            session.commit()
                    else:
                        logger.error(f"[SCHEDULER_DEBUG] 任务 {task_id} 状态不正确: {task.status}")
                        raise ValueError(f"任务 {task_id} 状态不正确: {task.status}")
                
                # 更新任务状态为运行中
                logger.info(f"[SCHEDULER_DEBUG] 更新任务状态为运行中")
                task_repo.update(task_id, {'status': 'running'})
                session.commit()

            # ... aqiure lock ...

            # 记录开始执行日志
            # log_repo.create_log(
            #     task_id=task_id,
            #     status="running"
            # )
            
            # 获取内容源信息
            content_source = content_source_repo.get_source_by_id(task.source_id)
            if not content_source:
                raise ValueError(f"内容源 {task.source_id} 不存在")
            
            # 构造元数据文件路径
            import os
            # 使用路径管理器标准化媒体文件路径
            media_file_path = self.path_manager.normalize_path(task.media_path)
            media_file = str(media_file_path)
            
            if not media_file_path.exists():
                raise FileNotFoundError(f"媒体文件不存在: {media_file} (原路径: {task.media_path})")
            
            # 查找对应的JSON元数据文件
            media_dir = os.path.dirname(media_file)
            media_name = os.path.splitext(os.path.basename(media_file))[0]
            metadata_file = os.path.join(media_dir, f"{media_name}.json")
            
            # 如果单独的JSON文件不存在，尝试查找outputs目录中的综合报告文件
            if not os.path.exists(metadata_file):
                outputs_dir = os.path.join(media_dir, "outputs")
                if os.path.exists(outputs_dir):
                    # 查找stage3_final_report文件
                    for file in os.listdir(outputs_dir):
                        if file.startswith("stage3_final_report") and file.endswith(".json"):
                            metadata_file = os.path.join(outputs_dir, file)
                            break
            
            # 如果仍然没有找到，尝试查找uploader_json目录中的en_prompt_results文件
            if not os.path.exists(metadata_file):
                # 获取项目根目录
                project_root = os.path.dirname(media_dir)
                uploader_json_dir = os.path.join(project_root, "uploader_json")
                if os.path.exists(uploader_json_dir):
                    # 查找en_prompt_results文件
                    for file in os.listdir(uploader_json_dir):
                        if file.startswith("en_prompt_results") and file.endswith(".json"):
                            metadata_file = os.path.join(uploader_json_dir, file)
                            break
            
            if not os.path.exists(metadata_file):
                raise FileNotFoundError(f"元数据文件不存在: {metadata_file}")
            
            # 生成内容
            logger.info(f"任务 {task_id} 开始生成内容，媒体路径: {task.media_path}，元数据: {metadata_file}")
            content_result = self.content_generator.generate_content(
                video_filename=os.path.basename(media_file),
                metadata_path=metadata_file,
                language='en'  # 明确指定使用英文
            )
            
            # 包装返回结果以保持兼容性
            if content_result:
                content_result = {
                    'success': True,
                    'content': content_result,
                    'message': '内容生成成功'
                }
            else:
                content_result = {
                    'success': False,
                    'content': None,
                    'message': '内容生成失败'
                }
            
            logger.info(f"任务 {task_id} 内容生成完成，结果: {content_result.get('success', False)}")
            
            if not content_result['success']:
                raise Exception(f"内容生成失败: {content_result['message']}")
                
            # 发布到Twitter
            logger.info(f"任务 {task_id} 开始发布到Twitter")
            publish_result = self._publish_to_twitter(
                content_result['content'],
                task.media_path
            )
            logger.info(f"任务 {task_id} 发布完成，结果: {publish_result.get('success', False)}")
            
            if not publish_result['success']:
                raise Exception(f"发布失败: {publish_result['message']}")
            
            with self.db_write_lock:
                # 更新任务状态为完成
                task_repo.update(task_id, {
                    'status': 'completed',
                    'updated_at': datetime.now()
                })
                
                # 记录成功日志
                log_repo.create_log(
                    task_id=task_id,
                    status="success",
                    tweet_id=publish_result.get('tweet_id'),
                    tweet_content=publish_result.get('tweet_text'),
                    duration_seconds=time.time() - start_time
                )
                session.commit()

            # 更新统计
            with self.lock:
                self.stats['total_processed'] += 1
                self.stats['successful'] += 1
                
            logger.info(f"任务 {task_id} 执行成功")
            
            return {
                'success': True,
                'task_id': task_id,
                'execution_time': time.time() - start_time
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"任务 {task_id} 执行失败: {error_msg}")
            
            try:
                with self.db_write_lock:
                    session.rollback()
                    # 处理重试逻辑
                    task = task_repo.get_by_id(task_id)
                    if task and task.retry_count < self.max_retries:
                        # 标记为重试
                        task_repo.update(task_id, {
                            'status': 'retry',
                            'retry_count': task.retry_count + 1
                        })
                        logger.info(f"任务 {task_id} 将在稍后重试 (尝试次数: {task.retry_count + 1})")
                    else:
                        # 标记为失败
                        task_repo.update(task_id, {'status': 'failed'})
                        logger.error(f"任务 {task_id} 已达到最大重试次数，标记为失败")
                    
                    # 记录失败日志
                    log_repo.create_log(
                        task_id=task_id,
                        status="failed",
                        error_message=error_msg,
                        duration_seconds=time.time() - start_time
                    )
                    session.commit()
            except Exception as db_error:
                logger.error(f"更新任务 {task_id} 失败状态时出错: {db_error}")
                # 即使数据库更新失败，也要继续执行统计更新

            # 更新统计
            with self.lock:
                self.stats['total_processed'] += 1
                self.stats['failed'] += 1
            
            return {
                'success': False,
                'task_id': task_id,
                'error': error_msg
            }
        finally:
            self.db_manager.remove_session()

                
    def _publish_to_twitter(self, content, media_path: str) -> dict:
        """发布内容到Twitter"""
        try:
            logger.info(f"[SCHEDULER_PUBLISH_DEBUG] 开始发布到Twitter")
            logger.info(f"[SCHEDULER_PUBLISH_DEBUG] 原始内容: {content}")
            logger.info(f"[SCHEDULER_PUBLISH_DEBUG] 媒体路径: {media_path}")
            
            # 获取推文文本
            if isinstance(content, dict):
                tweet_text = content.get('text', '')
                logger.info(f"[SCHEDULER_PUBLISH_DEBUG] 从字典提取推文文本: {tweet_text}")
            elif isinstance(content, str):
                tweet_text = content
                logger.info(f"[SCHEDULER_PUBLISH_DEBUG] 直接使用字符串作为推文文本: {tweet_text}")
            else:
                tweet_text = str(content) if content else ''
                logger.info(f"[SCHEDULER_PUBLISH_DEBUG] 转换为字符串的推文文本: {tweet_text}")
                
            if not tweet_text:
                logger.error(f"[SCHEDULER_PUBLISH_DEBUG] 推文内容为空")
                raise ValueError("推文内容为空")
                
            # 严格检查媒体文件存在性和类型
            if not media_path or not os.path.exists(media_path):
                logger.error(f"[SCHEDULER_PUBLISH_DEBUG] 媒体文件不存在或路径为空: {media_path}")
                raise FileNotFoundError(f"媒体文件不存在或路径为空: {media_path}")
                
            file_ext = os.path.splitext(media_path)[1].lower()
            logger.info(f"[SCHEDULER_PUBLISH_DEBUG] 媒体文件扩展名: {file_ext}")
            
            if file_ext in ['.mp4', '.mov', '.avi', '.mkv']:
                # 视频文件 - 这是我们期望的媒体类型
                logger.info(f"[SCHEDULER_PUBLISH_DEBUG] 发布视频推文")
                tweet_info, upload_time = self.publisher.post_tweet_with_video(
                    tweet_text, media_path
                )
            elif file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
                # 图片文件
                logger.info(f"[SCHEDULER_PUBLISH_DEBUG] 发布图片推文")
                tweet_info, upload_time = self.publisher.post_tweet_with_images(
                    tweet_text, [media_path]
                )
            else:
                # 不支持的文件类型，直接失败而不是降级
                logger.error(f"[SCHEDULER_PUBLISH_DEBUG] 不支持的媒体文件类型: {file_ext}")
                raise ValueError(f"不支持的媒体文件类型: {file_ext}，期望的类型: .mp4, .mov, .avi, .mkv, .jpg, .jpeg, .png, .gif")
            
            logger.info(f"[SCHEDULER_PUBLISH_DEBUG] 发布成功，推文信息: {tweet_info}")
            logger.info(f"[SCHEDULER_PUBLISH_DEBUG] 上传时间: {upload_time}")
                
            return {
                'success': True,
                'tweet_id': tweet_info.get('tweet_id'),
                'tweet_url': tweet_info.get('tweet_url'),
                'tweet_text': tweet_text,
                'upload_time': upload_time,
                'message': '发布成功'
            }
            
        except Exception as e:
            logger.error(f"[SCHEDULER_PUBLISH_DEBUG] Twitter发布失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'发布失败: {e}'
            }
            
    def _cleanup_running_tasks(self):
        """清理运行中的任务"""
        with self.lock:
            for task_id, task_info in self.running_tasks.items():
                try:
                    task_info['future'].cancel()
                    self.task_repo.update(task_id, {'status': TaskStatus.PENDING.value})
                except Exception as e:
                    logger.error(f"清理任务 {task_id} 失败: {e}")
                    
            self.running_tasks.clear()
            
    def _monitor_loop(self):
        """监控循环"""
        logger.info("调度器监控循环启动")
        
        while self.is_running:
            try:
                # 记录性能指标
                self.performance_monitor.record_metric(
                    'scheduler_queue_size', 
                    self.task_queue.qsize()
                )
                
                self.performance_monitor.record_metric(
                    'scheduler_running_tasks', 
                    len(self.running_tasks)
                )
                
                # 检查系统资源
                self._check_system_resources()
                
                time.sleep(60)  # 每分钟检查一次
                
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                time.sleep(10)
                
        logger.info("调度器监控循环结束")
        
    def _check_system_resources(self):
        """检查系统资源"""
        try:
            import psutil
            
            # 检查内存使用
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > 90:
                logger.warning(f"系统内存使用率过高: {memory_percent}%")
                
            # 检查CPU使用
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                logger.warning(f"系统CPU使用率过高: {cpu_percent}%")
                
        except ImportError:
            # psutil未安装，跳过资源检查
            pass
        except Exception as e:
            logger.error(f"检查系统资源失败: {e}")
            
    def _execute_task_wrapper(self, task_execution: TaskExecution):
        """
        包装 _execute_task，为每个任务创建独立的数据库会话和事务。
        """
        try:
            # 直接调用新的 _execute_task 方法，它已经包含了完整的数据库会话管理
            result = self._execute_task(task_execution)
            return result

        except Exception as e:
            logger.error(f"任务 {task_execution.task_id} 在包装器中发生严重错误: {e}", exc_info=True)
            return {
                'success': False,
                'task_id': task_execution.task_id,
                'error': f"Wrapper exception: {str(e)}"
            }

    def run_batch(self, limit: int = 10, project_filter: str = None, 
                  language_filter: str = None) -> Dict[str, Any]:
        """使用线程池并行运行一个批次的任务。

        Args:
            limit: 本批次最大任务数
            project_filter: 项目过滤器
            language_filter: 语言过滤器

        Returns:
            批次处理结果总结
        """
        logger.info(f"开始运行批处理，最多处理 {limit} 个任务...")

        session = self.db_manager.get_session()
        try:
            task_repo = PublishingTaskRepository(session)
            filters = {'status': ['pending', 'retry']}
            if project_filter:
                # 假设 project_filter 是项目名称，需要先查询到项目ID
                project_repo = ProjectRepository(session)
                # 注意：这里假设用户ID为1，实际应用中需要动态获取
                project = project_repo.get_by_name_and_user(name=project_filter, user_id=1)
                if project:
                    filters['project_id'] = project.id
                else:
                    logger.warning(f"未找到项目 '{project_filter}'，将忽略此过滤器。")
            if language_filter:
                filters['language'] = language_filter

            pending_tasks = task_repo.get_ready_tasks(filters=filters, limit=limit)

            if not pending_tasks:
                logger.info("没有待处理的任务。")
                return {
                    'success': True,
                    'processed': 0, 
                    'successful': 0, 
                    'failed': 0, 
                    'message': '没有待处理的任务'
                }

            successful_count = 0
            failed_count = 0

            with ThreadPoolExecutor(max_workers=1) as executor:
                task_executions = [
                    TaskExecution(
                        task_id=task.id, 
                        priority=self._determine_task_priority(task), 
                        scheduled_time=datetime.now()
                    ) for task in pending_tasks
                ]
                
                future_to_task = {executor.submit(self._execute_task_wrapper, te): te for te in task_executions}
                
                for future in as_completed(future_to_task):
                    task_execution = future_to_task[future]
                    try:
                        result = future.result()
                        if result and result.get('success'):
                            successful_count += 1
                        else:
                            failed_count += 1
                    except Exception as exc:
                        logger.error(f'任务 {task_execution.task_id} 生成了异常: {exc}', exc_info=True)
                        failed_count += 1

            processed_count = len(pending_tasks)
            logger.info(f"批处理完成。共处理 {processed_count} 个任务，成功 {successful_count} 个，失败 {failed_count} 个。")

            return {
                'success': True,
                'processed': processed_count,
                'successful': successful_count,
                'failed': failed_count,
                'message': f'批处理完成: 处理 {processed_count} 个任务，成功 {successful_count} 个，失败 {failed_count} 个'
            }
        finally:
            self.db_manager.remove_session()