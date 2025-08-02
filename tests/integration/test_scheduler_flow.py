import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from app.core.task_scheduler import TaskScheduler
from app.core.content_generator import ContentGenerator
from app.core.publisher import TwitterPublisher
from app.core.project_manager import ProjectManager
from app.database.models import User, Project, ContentSource, PublishingTask, PublishingLog
from app.database.repository import (
    PublishingTaskRepository, PublishingLogRepository, AnalyticsRepository
)
from api.schemas import TaskStatusEnum


class TestSchedulerFlowIntegration:
    """调度器流程集成测试类"""
    
    @pytest.fixture
    def mock_content_generator(self):
        """模拟内容生成器"""
        generator = Mock(spec=ContentGenerator)
        generator.generate_content.return_value = {
            'text': 'Generated tweet content',
            'hashtags': ['#test', '#ai'],
            'media_paths': []
        }
        return generator
    
    @pytest.fixture
    def mock_twitter_publisher(self):
        """模拟Twitter发布器"""
        publisher = Mock(spec=TwitterPublisher)
        publisher.publish_tweet.return_value = {
            'id': '1234567890',
            'text': 'Generated tweet content',
            'created_at': datetime.utcnow().isoformat()
        }
        return publisher
    
    @pytest.fixture
    def scheduler(self, db_session, mock_content_generator, mock_twitter_publisher):
        """创建任务调度器实例"""
        task_repo = PublishingTaskRepository(db_session)
        log_repo = PublishingLogRepository(db_session)
        analytics_repo = AnalyticsRepository(db_session)
        
        scheduler = TaskScheduler(
            task_repository=task_repo,
            log_repository=log_repo,
            analytics_repository=analytics_repo,
            content_generator=mock_content_generator,
            twitter_publisher=mock_twitter_publisher
        )
        return scheduler
    
    @pytest.fixture
    def sample_task(self, db_session, sample_user, sample_project, sample_content_source):
        """创建示例发布任务"""
        # 添加依赖数据到数据库
        db_session.add(sample_user)
        db_session.add(sample_project)
        db_session.add(sample_content_source)
        db_session.commit()
        
        task = PublishingTask(
            content_source_id=sample_content_source.id,
            scheduled_at=datetime.utcnow() - timedelta(minutes=5),  # 已到时间
            content='Original content',
            status="pending"
        )
        db_session.add(task)
        db_session.commit()
        
        return task
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_successful_task_execution_flow(self, scheduler, db_session, sample_task):
        """测试成功的任务执行流程"""
        # 执行任务
        result = await scheduler.execute_task(sample_task.id)
        
        # 验证执行结果
        assert result['success'] is True
        assert result['task_id'] == sample_task.id
        assert 'tweet_id' in result
        
        # 验证任务状态更新
        db_session.refresh(sample_task)
        assert sample_task.status == "success"
        
        # 验证发布日志创建
        logs = db_session.query(PublishingLog).filter_by(task_id=sample_task.id).all()
        assert len(logs) == 1
        assert logs[0].status == "success"
        assert logs[0].tweet_id == '1234567890'
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_failed_task_execution_flow(self, scheduler, db_session, sample_task, mock_twitter_publisher):
        """测试失败的任务执行流程"""
        # 模拟发布失败
        mock_twitter_publisher.publish_tweet.side_effect = Exception("Twitter API error")
        
        # 执行任务
        result = await scheduler.execute_task(sample_task.id)
        
        # 验证执行结果
        assert result['success'] is False
        assert result['task_id'] == sample_task.id
        assert 'error' in result
        
        # 验证任务状态更新
        db_session.refresh(sample_task)
        assert sample_task.status == "failed"
        
        # 验证错误日志创建
        logs = db_session.query(PublishingLog).filter_by(task_id=sample_task.id).all()
        assert len(logs) == 1
        assert logs[0].status == "failed"
        assert 'Twitter API error' in logs[0].error_message
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_task_execution_flow(self, scheduler, db_session, sample_user, sample_project, sample_content_source):
        """测试批量任务执行流程"""
        # 添加依赖数据
        db_session.add(sample_user)
        db_session.add(sample_project)
        db_session.add(sample_content_source)
        db_session.commit()
        
        # 创建多个任务
        tasks = []
        for i in range(3):
            task = PublishingTask(
                content_source_id=sample_content_source.id,
                scheduled_at=datetime.utcnow() - timedelta(minutes=i),
                content=f'Content {i}',
                status="pending"
            )
            db_session.add(task)
            tasks.append(task)
        
        db_session.commit()
        
        # 执行批量任务
        results = await scheduler.execute_batch_tasks(limit=5)
        
        # 验证执行结果
        assert len(results) == 3
        assert all(result['success'] for result in results)
        
        # 验证所有任务状态更新
        for task in tasks:
            db_session.refresh(task)
            assert task.status == "success"
        
        # 验证日志创建
        total_logs = db_session.query(PublishingLog).count()
        assert total_logs == 3
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scheduler_with_content_generation_flow(self, scheduler, db_session, sample_task, mock_content_generator):
        """测试包含内容生成的调度器流程"""
        # 配置内容生成器返回增强内容
        mock_content_generator.generate_content.return_value = {
            'text': 'AI-enhanced tweet content with #hashtags',
            'hashtags': ['#ai', '#enhanced'],
            'media_paths': ['/path/to/image.jpg']
        }
        
        # 执行任务
        result = await scheduler.execute_task(sample_task.id)
        
        # 验证内容生成器被调用
        mock_content_generator.generate_content.assert_called_once()
        
        # 验证执行结果
        assert result['success'] is True
        
        # 验证发布日志包含生成的内容
        logs = db_session.query(PublishingLog).filter_by(task_id=sample_task.id).all()
        assert len(logs) == 1
        log_data = logs[0].response_data
        assert 'AI-enhanced' in log_data.get('text', '')
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scheduler_retry_mechanism(self, scheduler, db_session, sample_task, mock_twitter_publisher):
        """测试调度器重试机制"""
        # 模拟前两次失败，第三次成功
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception(f"Attempt {call_count} failed")
            return {
                'id': '1234567890',
                'text': 'Success after retry',
                'created_at': datetime.utcnow().isoformat()
            }
        
        mock_twitter_publisher.publish_tweet.side_effect = side_effect
        
        # 配置重试参数
        scheduler.max_retries = 3
        scheduler.retry_delay = 0.1  # 快速重试用于测试
        
        # 执行任务
        result = await scheduler.execute_task_with_retry(sample_task.id)
        
        # 验证重试机制
        assert call_count == 3
        assert result['success'] is True
        assert result['retry_count'] == 2
        
        # 验证最终状态
        db_session.refresh(sample_task)
        assert sample_task.status == "success"
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scheduler_analytics_integration(self, scheduler, db_session, sample_task):
        """测试调度器与分析系统的集成"""
        # 执行任务
        result = await scheduler.execute_task(sample_task.id)
        
        # 验证分析数据更新
        analytics_repo = AnalyticsRepository(db_session)
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        # 获取当前小时的分析数据
        analytics = analytics_repo.get_hourly_stats(
            user_id=sample_task.content_source.project.user_id,
            start_time=current_hour,
            end_time=current_hour
        )
        
        assert len(analytics) == 1
        assert analytics[0].tweets_published == 1
        assert analytics[0].total_impressions >= 0  # 可能为0，取决于模拟数据
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scheduler_concurrent_execution(self, scheduler, db_session, sample_user, sample_project, sample_content_source):
        """测试调度器并发执行"""
        # 添加依赖数据
        db_session.add(sample_user)
        db_session.add(sample_project)
        db_session.add(sample_content_source)
        db_session.commit()
        
        # 创建多个任务
        tasks = []
        for i in range(5):
            task = PublishingTask(
                content_source_id=sample_content_source.id,
                scheduled_at=datetime.utcnow() - timedelta(minutes=i),
                content=f'Concurrent content {i}',
                status="pending"
            )
            db_session.add(task)
            tasks.append(task)
        
        db_session.commit()
        
        # 并发执行任务
        task_coroutines = [scheduler.execute_task(task.id) for task in tasks]
        results = await asyncio.gather(*task_coroutines, return_exceptions=True)
        
        # 验证所有任务都成功执行
        successful_results = [r for r in results if isinstance(r, dict) and r.get('success')]
        assert len(successful_results) == 5
        
        # 验证没有竞态条件
        for task in tasks:
            db_session.refresh(task)
            assert task.status == "success"
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scheduler_error_recovery(self, scheduler, db_session, sample_task, mock_twitter_publisher):
        """测试调度器错误恢复"""
        # 模拟网络错误
        mock_twitter_publisher.publish_tweet.side_effect = ConnectionError("Network error")
        
        # 执行任务
        result = await scheduler.execute_task(sample_task.id)
        
        # 验证错误处理
        assert result['success'] is False
        assert 'Network error' in result['error']
        
        # 验证任务可以重新调度
        db_session.refresh(sample_task)
        assert sample_task.status == "failed"
        
        # 修复网络问题并重新执行
        mock_twitter_publisher.publish_tweet.side_effect = None
        mock_twitter_publisher.publish_tweet.return_value = {
            'id': '1234567890',
            'text': 'Recovered tweet',
            'created_at': datetime.utcnow().isoformat()
        }
        
        # 重置任务状态
        sample_task.status = "pending"
        db_session.commit()
        
        # 重新执行
        result = await scheduler.execute_task(sample_task.id)
        
        # 验证恢复成功
        assert result['success'] is True
        db_session.refresh(sample_task)
        assert sample_task.status == "success"
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scheduler_task_prioritization(self, scheduler, db_session, sample_user, sample_project, sample_content_source):
        """测试调度器任务优先级"""
        # 添加依赖数据
        db_session.add(sample_user)
        db_session.add(sample_project)
        db_session.add(sample_content_source)
        db_session.commit()
        
        # 创建不同优先级的任务
        high_priority_task = PublishingTask(
            content_source_id=sample_content_source.id,
            scheduled_at=datetime.utcnow() - timedelta(hours=2),  # 更早的时间
            content='High priority content',
            status="pending",
            priority=1
        )
        
        low_priority_task = PublishingTask(
            content_source_id=sample_content_source.id,
            scheduled_at=datetime.utcnow() - timedelta(hours=1),
            content='Low priority content',
            status="pending",
            priority=3
        )
        
        db_session.add(high_priority_task)
        db_session.add(low_priority_task)
        db_session.commit()
        
        # 获取待处理任务（应该按优先级排序）
        task_repo = PublishingTaskRepository(db_session)
        pending_tasks = task_repo.get_pending_tasks(limit=10)
        
        # 验证高优先级任务排在前面
        assert len(pending_tasks) >= 2
        assert pending_tasks[0].priority <= pending_tasks[1].priority
        
        # 执行任务并验证执行顺序
        execution_order = []
        for task in pending_tasks[:2]:
            result = await scheduler.execute_task(task.id)
            if result['success']:
                execution_order.append(task.priority)
        
        # 验证高优先级任务先执行
        assert execution_order[0] <= execution_order[1]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scheduler_cleanup_and_maintenance(self, scheduler, db_session, sample_user, sample_project, sample_content_source):
        """测试调度器清理和维护功能"""
        # 添加依赖数据
        db_session.add(sample_user)
        db_session.add(sample_project)
        db_session.add(sample_content_source)
        db_session.commit()
        
        # 创建旧的已完成任务
        old_task = PublishingTask(
            content_source_id=sample_content_source.id,
            scheduled_at=datetime.utcnow() - timedelta(days=31),
            content='Old completed task',
            status="success",
            completed_at=datetime.utcnow() - timedelta(days=30)
        )
        db_session.add(old_task)
        
        # 创建旧的日志
        old_log = PublishingLog(
            task_id=old_task.id,
            status="success",
            tweet_id='old_tweet_123',
            created_at=datetime.utcnow() - timedelta(days=30)
        )
        db_session.add(old_log)
        db_session.commit()
        
        # 执行清理
        cleanup_result = await scheduler.cleanup_old_data(days_to_keep=7)
        
        # 验证清理结果
        assert cleanup_result['tasks_cleaned'] >= 1
        assert cleanup_result['logs_cleaned'] >= 1
        
        # 验证旧数据被删除
        remaining_old_tasks = db_session.query(PublishingTask).filter(
            PublishingTask.completed_at < datetime.utcnow() - timedelta(days=7)
        ).count()
        assert remaining_old_tasks == 0
        
        remaining_old_logs = db_session.query(PublishingLog).filter(
            PublishingLog.created_at < datetime.utcnow() - timedelta(days=7)
        ).count()
        assert remaining_old_logs == 0


class TestProjectManagerIntegration:
    """项目管理器集成测试类"""
    
    @pytest.fixture
    def project_manager(self, db_session):
        """创建项目管理器实例"""
        from app.database.repository import ProjectRepository, ContentSourceRepository
        
        project_repo = ProjectRepository(db_session)
        content_source_repo = ContentSourceRepository(db_session)
        
        return ProjectManager(
            project_repository=project_repo,
            content_source_repository=content_source_repo
        )
    
    @pytest.fixture
    def temp_project_dir(self, tmp_path):
        """创建临时项目目录"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        # 创建视频文件
        video_file = project_dir / "video1.mp4"
        video_file.write_bytes(b"fake video content")
        
        # 创建元数据文件
        metadata_file = project_dir / "metadata.json"
        metadata_file.write_text('''{
    "title": "Test Video",
    "description": "A test video",
    "tags": ["test", "video"]
}''')
        
        return str(project_dir)
    
    @pytest.mark.integration
    def test_complete_project_scan_flow(self, project_manager, db_session, sample_user, temp_project_dir):
        """测试完整的项目扫描流程"""
        # 添加用户到数据库
        db_session.add(sample_user)
        db_session.commit()
        
        # 扫描项目
        result = project_manager.scan_project(
            user_id=sample_user.id,
            project_path=temp_project_dir,
            project_name="Test Project"
        )
        
        # 验证扫描结果
        assert result['success'] is True
        assert result['project_created'] is True
        assert result['content_sources_found'] >= 1
        
        # 验证项目被创建
        from app.database.repository import ProjectRepository
        project_repo = ProjectRepository(db_session)
        projects = project_repo.get_by_user_id(sample_user.id)
        assert len(projects) == 1
        assert projects[0].name == "Test Project"
        assert projects[0].path == temp_project_dir
        
        # 验证内容源被创建
        project = projects[0]
        assert len(project.content_sources) >= 1
        
        video_source = next(
            (cs for cs in project.content_sources if cs.file_name == "video1.mp4"),
            None
        )
        assert video_source is not None
        assert video_source.metadata is not None
    
    @pytest.mark.integration
    def test_project_rescan_flow(self, project_manager, db_session, sample_user, temp_project_dir):
        """测试项目重新扫描流程"""
        # 添加用户到数据库
        db_session.add(sample_user)
        db_session.commit()
        
        # 首次扫描
        result1 = project_manager.scan_project(
            user_id=sample_user.id,
            project_path=temp_project_dir,
            project_name="Test Project"
        )
        assert result1['success'] is True
        
        # 添加新的视频文件
        import os
        new_video_path = os.path.join(temp_project_dir, "video2.mp4")
        with open(new_video_path, 'wb') as f:
            f.write(b"another fake video content")
        
        # 重新扫描
        result2 = project_manager.scan_project(
            user_id=sample_user.id,
            project_path=temp_project_dir,
            project_name="Test Project"
        )
        
        # 验证重新扫描结果
        assert result2['success'] is True
        assert result2['project_created'] is False  # 项目已存在
        assert result2['content_sources_found'] >= 2  # 找到新文件
        
        # 验证新内容源被添加
        from app.database.repository import ProjectRepository
        project_repo = ProjectRepository(db_session)
        projects = project_repo.get_by_user_id(sample_user.id)
        project = projects[0]
        
        video_files = [cs.file_name for cs in project.content_sources]
        assert "video1.mp4" in video_files
        assert "video2.mp4" in video_files
    
    @pytest.mark.integration
    def test_project_manager_with_scheduler_integration(self, project_manager, db_session, sample_user, temp_project_dir, mock_content_generator, mock_twitter_publisher):
        """测试项目管理器与调度器的集成"""
        # 添加用户到数据库
        db_session.add(sample_user)
        db_session.commit()
        
        # 扫描项目
        scan_result = project_manager.scan_project(
            user_id=sample_user.id,
            project_path=temp_project_dir,
            project_name="Integration Test Project"
        )
        assert scan_result['success'] is True
        
        # 创建发布任务
        from app.database.repository import ProjectRepository, PublishingTaskRepository
        project_repo = ProjectRepository(db_session)
        task_repo = PublishingTaskRepository(db_session)
        
        projects = project_repo.get_by_user_id(sample_user.id)
        project = projects[0]
        content_source = project.content_sources[0]
        
        task = PublishingTask(
            content_source_id=content_source.id,
            scheduled_at=datetime.utcnow() - timedelta(minutes=5),
            content='Integration test content',
            status="pending"
        )
        db_session.add(task)
        db_session.commit()
        
        # 创建调度器并执行任务
        from app.database.repository import PublishingLogRepository, AnalyticsRepository
        log_repo = PublishingLogRepository(db_session)
        analytics_repo = AnalyticsRepository(db_session)
        
        scheduler = TaskScheduler(
            task_repository=task_repo,
            log_repository=log_repo,
            analytics_repository=analytics_repo,
            content_generator=mock_content_generator,
            twitter_publisher=mock_twitter_publisher
        )
        
        # 执行任务
        import asyncio
        result = asyncio.run(scheduler.execute_task(task.id))
        
        # 验证集成结果
        assert result['success'] is True
        
        # 验证任务状态
        db_session.refresh(task)
        assert task.status == "success"
        
        # 验证日志创建
        logs = log_repo.get_by_task_id(task.id)
        assert len(logs) == 1
        assert logs[0].status == "success"