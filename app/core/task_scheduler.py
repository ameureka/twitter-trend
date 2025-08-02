# app/core/task_scheduler.py

import time
import random
import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.database import models
from app.database.repository import (
    ProjectRepository, PublishingTaskRepository, 
    PublishingLogRepository, AnalyticsRepository
)
from app.core.content_generator import ContentGenerator
from app.core.publisher import TwitterPublisher
from app.utils.logger import get_logger

logger = get_logger(__name__)

class TaskScheduler:
    def __init__(self, 
                 db_session: Session,
                 publisher: TwitterPublisher,
                 content_generator: ContentGenerator,
                 config: Dict[str, Any],
                 user_id: int = 1):
        self.session = db_session
        self.publisher = publisher
        self.content_generator = content_generator
        self.config = config
        self.user_id = user_id
        
        # 初始化仓库
        self.project_repo = ProjectRepository(db_session)
        self.task_repo = PublishingTaskRepository(db_session)
        self.log_repo = PublishingLogRepository(db_session)
        self.analytics_repo = AnalyticsRepository(db_session)
        
        # 调度配置
        scheduler_config = config.get('scheduler', {})
        self.interval_min = scheduler_config.get('interval_minutes_min', 15)
        self.interval_max = scheduler_config.get('interval_minutes_max', 30)
        
        # 任务管理配置
        task_config = config.get('task_management', {})
        self.max_retries = task_config.get('max_retries', 3)
        self.retry_backoff_base = task_config.get('retry_backoff_base', 2)
        self.stuck_task_timeout_hours = task_config.get('stuck_task_timeout_hours', 2)
        self.lock_timeout_minutes = task_config.get('lock_timeout_minutes', 30)
        self.batch_size = task_config.get('batch_size', 10)
        
        logger.info(f"任务调度器初始化完成，发布间隔: {self.interval_min}-{self.interval_max}分钟")

    def run_single_task(self, project_filter: str = None, language_filter: str = None) -> bool:
        """执行单个待处理任务。返回是否成功执行了任务。"""
        # 查找待处理的任务
        task = self._get_next_pending_task(project_filter, language_filter)
        
        if not task:
            logger.info("没有待处理的任务")
            return False
            
        logger.info(f"开始处理任务 ID: {task.id}, 媒体: {task.media_path}")
        
        # 更新任务状态为进行中
        self.task_repo.update(task.id, {
            'status': 'in_progress',
            'started_at': datetime.datetime.utcnow()
        })
        
        start_time = time.time()
        
        try:
            # 从content_data中获取元数据
            content_data = task.get_content_data()
            language = content_data.get('language', 'en')
            
            # 生成推文内容
            tweet_content, generation_time = self.content_generator.generate_tweet_from_data(
                content_data,
                task.media_path.split('/')[-1],  # 提取文件名
                language
            )
            
            logger.info(f"推文内容生成完成: {tweet_content[:50]}...")
            
            # 发布推文
            if task.media_path.endswith('.mp4'):
                tweet_info, upload_time = self.publisher.post_tweet_with_video(
                    tweet_content, task.media_path
                )
            else:
                # 假设是图片文件
                tweet_info, upload_time = self.publisher.post_tweet_with_images(
                    tweet_content, [task.media_path]
                )
            
            # 计算总耗时
            total_duration = int((time.time() - start_time) * 1000)
            
            # 更新任务状态为成功
            self.task_repo.update(task.id, {
                'status': 'success',
                'completed_at': datetime.datetime.utcnow(),
                'result': {
                    'tweet_id': tweet_info['tweet_id'],
                    'tweet_url': tweet_info['tweet_url']
                }
            })
            
            # 创建成功日志
            log_data = {
                'task_id': task.id,
                'published_at': datetime.datetime.utcnow(),
                'tweet_id': tweet_info['tweet_id'],
                'tweet_url': tweet_info['tweet_url'],
                'tweet_content': tweet_content,
                'status': 'success',
                'metrics': {
                    'content_generation_time': generation_time,
                    'media_upload_time': upload_time,
                    'total_duration': total_duration
                }
            }
            
            self.log_repo.create(log_data)
            
            # 记录分析数据
            self._record_analytics(task, 'success', total_duration)
            
            logger.info(f"任务 {task.id} 执行成功，推文URL: {tweet_info['tweet_url']}")
            
            # 设置下一个任务的调度时间
            self._schedule_next_task()
            
            return True
            
        except Exception as e:
            logger.error(f"任务 {task.id} 执行失败: {e}")
            
            # 处理失败情况
            self._handle_task_failure(task, str(e))
            
            return False

    def run_batch(self, limit: int = 5, project_filter: str = None, language_filter: str = None) -> Dict[str, int]:
        """批量执行任务。返回执行统计信息。"""
        stats = {'success': 0, 'failed': 0, 'skipped': 0}
        
        logger.info(f"开始批量执行任务，限制: {limit}个")
        
        for i in range(limit):
            try:
                success = self.run_single_task(project_filter, language_filter)
                
                if success:
                    stats['success'] += 1
                    
                    # 在任务之间添加随机延迟
                    if i < limit - 1:  # 不是最后一个任务
                        delay = random.randint(30, 120)  # 30-120秒随机延迟
                        logger.info(f"等待 {delay} 秒后执行下一个任务...")
                        time.sleep(delay)
                else:
                    stats['skipped'] += 1
                    break  # 没有更多任务了
                    
            except Exception as e:
                logger.error(f"批量执行中出现错误: {e}")
                stats['failed'] += 1
                
        logger.info(f"批量执行完成: {stats}")
        return stats

    def _get_next_pending_task(self, project_filter: str = None, language_filter: str = None) -> Optional[models.PublishingTask]:
        """获取下一个待处理的任务。"""
        filters = {
            'status': ['pending', 'retry'],
            'scheduled_before': datetime.datetime.utcnow()
        }
        
        # 应用过滤器
        if project_filter:
            project = self.project_repo.get_by_name_and_user(project_filter, self.user_id)
            if project:
                filters['project_id'] = project.id
            else:
                logger.warning(f"项目 '{project_filter}' 不存在")
                return None
                
        if language_filter:
            filters['language'] = language_filter
            
        # 获取下一个任务（按优先级和创建时间排序）
        tasks = self.task_repo.get_ready_tasks(filters, limit=1)
        
        return tasks[0] if tasks else None

    def _handle_task_failure(self, task: models.PublishingTask, error_message: str):
        """处理任务失败。"""
        retry_count = task.retry_count + 1
        
        # 判断是否应该重试
        should_retry = self._should_retry(error_message, retry_count)
        
        if should_retry:
            # 计算重试延迟（指数退避）
            retry_delay_minutes = self._calculate_retry_delay(retry_count)
            next_retry = datetime.datetime.utcnow() + datetime.timedelta(minutes=retry_delay_minutes)
            
            # 使用原子性更新
            log_data = {
                'task_id': task.id,
                'status': 'retry',
                'error_message': error_message,
                'duration_seconds': 0
            }
            
            success = self.task_repo.update_task_status_atomic(task.id, 'retry', log_data)
            
            if success:
                # 更新重试相关字段
                self.task_repo.update(task.id, {
                    'retry_count': retry_count,
                    'scheduled_at': next_retry,
                    'error_message': error_message
                })
                
                logger.info(f"任务 {task.id} 将在 {retry_delay_minutes} 分钟后重试（第 {retry_count} 次）")
            else:
                logger.error(f"任务 {task.id} 状态更新失败")
        else:
            # 最终失败
            log_data = {
                'task_id': task.id,
                'status': 'failed',
                'error_message': error_message,
                'duration_seconds': 0
            }
            
            success = self.task_repo.update_task_status_atomic(task.id, 'failed', log_data)
            
            if success:
                self.task_repo.update(task.id, {
                    'retry_count': retry_count,
                    'completed_at': datetime.datetime.utcnow(),
                    'error_message': error_message
                })
                
                logger.error(f"任务 {task.id} 最终失败，重试次数: {retry_count}")
        
        # 记录分析数据
        self._record_analytics(task, 'failed', 0)
    
    def _should_retry(self, error_message: str, retry_count: int) -> bool:
        """判断是否应该重试"""
        if retry_count > self.max_retries:
            return False
        
        return self._is_recoverable_error(error_message)
    
    def _calculate_retry_delay(self, retry_count: int) -> int:
        """计算重试延迟（分钟）"""
        # 指数退避：base_delay * (backoff_base ^ (retry_count - 1))
        base_delay = 30  # 基础延迟30分钟
        delay = base_delay * (self.retry_backoff_base ** (retry_count - 1))
        
        # 添加随机抖动（±20%）
        jitter = random.uniform(0.8, 1.2)
        delay = int(delay * jitter)
        
        # 限制最大延迟为4小时
        return min(delay, 240)

    def _is_recoverable_error(self, error_message: str) -> bool:
        """判断错误是否可恢复。"""
        recoverable_patterns = [
            'timeout',
            'connection',
            'network',
            'rate limit',
            'server error',
            '5xx',
            'temporary',
            'retry'
        ]
        
        error_lower = error_message.lower()
        
        for pattern in recoverable_patterns:
            if pattern in error_lower:
                return True
                
        # 不可恢复的错误模式
        permanent_patterns = [
            'unauthorized',
            'forbidden',
            'not found',
            'invalid',
            'malformed',
            'file not exist'
        ]
        
        for pattern in permanent_patterns:
            if pattern in error_lower:
                return False
                
        # 默认认为可恢复
        return True

    def _schedule_next_task(self):
        """为下一个任务设置调度时间。"""
        # 计算下一次发布的时间间隔
        interval_minutes = random.randint(self.interval_min, self.interval_max)
        jitter_minutes = random.randint(-2, 2)  # 添加小的随机抖动
        total_interval = max(1, interval_minutes + jitter_minutes)
        
        next_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=total_interval)
        
        logger.info(f"下一个任务将在 {total_interval} 分钟后执行（{next_time.strftime('%H:%M:%S')}）")

    def get_queue_status(self) -> Dict[str, Any]:
        """获取任务队列状态。"""
        return self.task_repo.get_queue_status()

    def reset_stuck_tasks(self):
        """重置卡住的任务（状态为in_progress但长时间未更新）。"""
        reset_count = self.task_repo.reset_stuck_tasks(timeout_hours=self.stuck_task_timeout_hours)
        
        if reset_count > 0:
            logger.info(f"重置了 {reset_count} 个卡住的任务（超时时间: {self.stuck_task_timeout_hours}小时）")
        
        return reset_count
    
    def _record_analytics(self, task: models.PublishingTask, status: str, duration: int):
        """记录分析数据。"""
        try:
            # 从content_data中获取language信息
            content_data = task.get_content_data()
            language = content_data.get('language', 'en')
            
            analytics_data = {
                'project_id': task.project_id,
                'language': language,
                'status': status,
                'duration_ms': duration,
                'retry_count': task.retry_count
            }
            
            self.analytics_repo.record_hourly_stats(analytics_data)
            
        except Exception as e:
            logger.error(f"记录分析数据失败: {e}")