import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time

from app.core.task_scheduler import TaskScheduler
from app.database.models import PublishingTask, PublishingLog, AnalyticsHourly


class TestTaskScheduler:
    """任务调度器测试类"""
    
    @pytest.fixture
    def task_scheduler(self, db_session):
        """创建任务调度器实例"""
        # 创建mock依赖
        mock_publisher = Mock()
        mock_content_generator = Mock()
        mock_config = {
            'scheduler': {
                'interval_minutes_min': 15,
                'interval_minutes_max': 30,
                'max_retries': 3
            }
        }
        
        return TaskScheduler(
            db_session=db_session,
            publisher=mock_publisher,
            content_generator=mock_content_generator,
            config=mock_config
        )
    
    @pytest.fixture
    def pending_task(self, db_session, sample_content_source):
        """创建待处理任务"""
        task = PublishingTask(
            source_id=sample_content_source.id,
            project_id=sample_content_source.project_id,
            media_path="/test/path/sample_video_01.mp4",
            content_data='{"title": "Test Video", "description": "Test description"}',
            status="pending",
            scheduled_at=datetime.utcnow() - timedelta(minutes=5),  # 已到执行时间
            created_at=datetime.utcnow()
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task
    
    @pytest.fixture
    def future_task(self, db_session, sample_content_source):
        """创建未来任务"""
        task = PublishingTask(
            source_id=sample_content_source.id,
            project_id=sample_content_source.project_id,
            media_path="/test/path/sample_video_02.mp4",
            content_data='{"title": "Future Video", "description": "Future description"}',
            status="pending",
            scheduled_at=datetime.utcnow() + timedelta(hours=1),  # 未到执行时间
            created_at=datetime.utcnow()
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task
    
    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        return {
            "twitter": {
                "api_key": "test_api_key",
                "api_secret": "test_api_secret",
                "access_token": "test_access_token",
                "access_token_secret": "test_access_token_secret"
            },
            "ai": {
                "gemini_api_key": "test_gemini_key",
                "use_ai_enhancement": True
            },
            "content": {
                "default_language": "en"
            }
        }
    
    @pytest.mark.unit
    def test_get_next_pending_task_success(self, task_scheduler, pending_task, future_task):
        """测试获取下一个待处理任务成功"""
        # Mock task_repo.get_ready_tasks方法
        task_scheduler.task_repo.get_ready_tasks = Mock(return_value=[pending_task])
        
        task = task_scheduler._get_next_pending_task()
        
        assert task is not None
        assert task.id == pending_task.id
        assert task.status == "pending"
    
    @pytest.mark.unit
    def test_get_queue_status(self, task_scheduler, db_session, sample_content_source):
        """测试获取队列状态"""
        # Mock get_queue_status方法
        mock_status = {'pending': 5, 'running': 1, 'completed': 10, 'failed': 2}
        task_scheduler.task_repo.get_queue_status = Mock(return_value=mock_status)
        
        # 测试获取队列状态
        status = task_scheduler.get_queue_status()
        
        assert isinstance(status, dict)
        # 验证状态包含必要信息
        assert 'pending' in str(status).lower() or 'total' in str(status).lower()
    
    @pytest.mark.unit
    def test_get_next_pending_task_no_tasks(self, task_scheduler):
        """测试没有待处理任务"""
        # Mock task_repo.get_ready_tasks方法返回空列表
        task_scheduler.task_repo.get_ready_tasks = Mock(return_value=[])
        
        result = task_scheduler._get_next_pending_task()
        
        assert result is None
    
    @pytest.mark.unit
    def test_run_single_task_success(self, task_scheduler, pending_task, tmp_path):
        """测试单个任务执行成功"""
        # 创建模拟视频文件和元数据文件
        video_file = tmp_path / "test_video.mp4"
        video_file.write_bytes(b"fake video content")
        
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text('{"title": "Test Video", "description": "Test Description"}')
        
        # 更新任务的文件路径
        pending_task.media_path = str(video_file)
        # 将元数据信息存储在content_data中
        content_data = {
            "title": "Test Video", 
            "description": "Test Description",
            "metadata_path": str(metadata_file),
            "language": "en"
        }
        pending_task.set_content_data(content_data)
        task_scheduler.session.commit()
        
        # Mock get_ready_tasks方法
        task_scheduler.task_repo.get_ready_tasks = Mock(return_value=[pending_task])
        
        # Mock repository update方法
        task_scheduler.task_repo.update = Mock()
        task_scheduler.log_repo.create = Mock()
        task_scheduler.analytics_repo.record_hourly_stats = Mock()
        
        # Mock外部依赖
        task_scheduler.content_generator.generate_tweet_from_data.return_value = ("Test tweet content #test", 1.5)
        task_scheduler.publisher.post_tweet_with_video.return_value = (
            {"tweet_id": "123456789", "tweet_url": "https://twitter.com/test/status/123456789"},
            2.5
        )
        
        # 执行任务
        result = task_scheduler.run_single_task()
        
        assert result is True
        
        # 验证mock调用
        task_scheduler.content_generator.generate_tweet_from_data.assert_called_once()
        task_scheduler.publisher.post_tweet_with_video.assert_called_once()
    
    @pytest.mark.unit
    def test_run_single_task_content_generation_failure(self, task_scheduler, pending_task, tmp_path):
        """测试内容生成失败"""
        # 创建模拟文件
        video_file = tmp_path / "test_video.mp4"
        video_file.write_bytes(b"fake video content")
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text('{"title": "Test Video"}')
        
        # 更新任务
        pending_task.media_path = str(video_file)
        # 将元数据信息存储在content_data中
        content_data = {
            "title": "Test Video",
            "metadata_path": str(metadata_file),
            "language": "en"
        }
        pending_task.set_content_data(content_data)
        task_scheduler.session.commit()
        
        # Mock get_ready_tasks方法
        task_scheduler.task_repo.get_ready_tasks = Mock(return_value=[pending_task])
        
        # Mock repository方法
        task_scheduler.task_repo.update = Mock()
        task_scheduler.log_repo.create = Mock()
        task_scheduler.analytics_repo.record_hourly_stats = Mock()
        
        # Mock内容生成失败
        task_scheduler.content_generator.generate_tweet_from_data.side_effect = Exception("Content generation failed")
        
        result = task_scheduler.run_single_task()
        
        assert result is False
    
    @pytest.mark.unit
    def test_run_single_task_publishing_failure(self, task_scheduler, pending_task, tmp_path):
        """测试发布失败"""
        # 创建模拟文件
        video_file = tmp_path / "test_video.mp4"
        video_file.write_bytes(b"fake video content")
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text('{"title": "Test Video"}')
        
        # 更新任务
        pending_task.media_path = str(video_file)
        # 将元数据信息存储在content_data中
        content_data = {
            "title": "Test Video",
            "metadata_path": str(metadata_file),
            "language": "en"
        }
        pending_task.set_content_data(content_data)
        task_scheduler.session.commit()
        
        # Mock get_ready_tasks方法
        task_scheduler.task_repo.get_ready_tasks = Mock(return_value=[pending_task])
        
        # Mock repository方法
        task_scheduler.task_repo.update = Mock()
        task_scheduler.log_repo.create = Mock()
        task_scheduler.analytics_repo.record_hourly_stats = Mock()
        
        # Mock成功的内容生成但失败的发布
        task_scheduler.content_generator.generate_tweet_from_data.return_value = ("Test tweet content", 1.0)
        task_scheduler.publisher.post_tweet_with_video.side_effect = Exception("Twitter API Error")
        
        result = task_scheduler.run_single_task()
        
        assert result is False
    
    @pytest.mark.unit
    def test_run_batch_success(self, task_scheduler):
        """测试批量执行任务"""
        # Mock成功执行
        with patch.object(task_scheduler, 'run_single_task', return_value=True) as mock_run:
            result = task_scheduler.run_batch(limit=3)
        
        assert result['success'] >= 0
        assert result['failed'] >= 0
        assert result['skipped'] >= 0
    
    @pytest.mark.unit
    def test_reset_stuck_tasks(self, task_scheduler):
        """测试重置卡住的任务"""
        # Mock repository方法
        task_scheduler.task_repo.reset_stuck_tasks = Mock(return_value=2)
        
        result = task_scheduler.reset_stuck_tasks()
        
        assert result == 2
        task_scheduler.task_repo.reset_stuck_tasks.assert_called_once()