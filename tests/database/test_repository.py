import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app.database.repository import (
    UserRepository, ProjectRepository, ContentSourceRepository,
    PublishingTaskRepository, PublishingLogRepository, AnalyticsRepository
)
from app.database.models import (
    User, Project, ContentSource, PublishingTask, 
    PublishingLog, AnalyticsHourly
)


class TestUserRepository:
    """用户仓储测试类"""
    
    @pytest.fixture
    def user_repo(self, db_session):
        """创建用户仓储实例"""
        return UserRepository(db_session)
    
    @pytest.mark.database
    def test_create_user_success(self, user_repo):
        """测试创建用户成功"""
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password_hash": "hashed_password"
        }
        
        user = user_repo.create_user(**user_data)
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active is True
    
    @pytest.mark.database
    def test_get_user_by_id_success(self, user_repo, sample_user):
        """测试根据ID获取用户成功"""
        user = user_repo.get_user_by_id(sample_user.id)
        
        assert user is not None
        assert user.id == sample_user.id
        assert user.username == sample_user.username
    
    @pytest.mark.database
    def test_get_user_by_id_not_found(self, user_repo):
        """测试根据ID获取用户不存在"""
        user = user_repo.get_user_by_id(99999)
        
        assert user is None
    
    @pytest.mark.database
    def test_get_user_by_username_success(self, user_repo, sample_user):
        """测试根据用户名获取用户成功"""
        user = user_repo.get_user_by_username(sample_user.username)
        
        assert user is not None
        assert user.id == sample_user.id
        assert user.username == sample_user.username
    
    @pytest.mark.database
    def test_get_user_by_username_not_found(self, user_repo):
        """测试根据用户名获取用户不存在"""
        user = user_repo.get_user_by_username("nonexistent")
        
        assert user is None
    
    @pytest.mark.database
    def test_get_user_by_email_success(self, user_repo, sample_user):
        """测试根据邮箱获取用户成功"""
        user = user_repo.get_user_by_email(sample_user.email)
        
        assert user is not None
        assert user.id == sample_user.id
        assert user.email == sample_user.email
    
    @pytest.mark.database
    def test_update_user_success(self, user_repo, sample_user):
        """测试更新用户成功"""
        update_data = {
            "email": "newemail@example.com",
            "is_active": False
        }
        
        updated_user = user_repo.update_user(sample_user.id, **update_data)
        
        assert updated_user.email == "newemail@example.com"
        assert updated_user.is_active is False
        assert updated_user.updated_at > sample_user.updated_at
    
    @pytest.mark.database
    def test_delete_user_success(self, user_repo, sample_user):
        """测试删除用户成功"""
        user_id = sample_user.id
        result = user_repo.delete_user(user_id)
        
        assert result is True
        assert user_repo.get_user_by_id(user_id) is None
    
    @pytest.mark.database
    def test_list_users_with_pagination(self, user_repo, db_session):
        """测试分页获取用户列表"""
        # 创建多个用户
        for i in range(5):
            user = User(
                username=f"user{i}",
                email=f"user{i}@example.com",
                password_hash="hashed_password"
            )
            db_session.add(user)
        db_session.commit()
        
        # 测试分页
        users, total = user_repo.list_users(page=1, page_size=3)
        
        assert len(users) == 3
        assert total == 5
        
        # 测试第二页
        users_page2, _ = user_repo.list_users(page=2, page_size=3)
        assert len(users_page2) == 2


class TestProjectRepository:
    """项目仓储测试类"""
    
    @pytest.fixture
    def project_repo(self, db_session):
        """创建项目仓储实例"""
        return ProjectRepository(db_session)
    
    @pytest.mark.database
    def test_create_project_success(self, project_repo, sample_user):
        """测试创建项目成功"""
        project_data = {
            "user_id": sample_user.id,
            "name": "Test Project",
            "path": "/test/project/path",
            "description": "Test description"
        }
        
        project = project_repo.create_project(**project_data)
        
        assert project.id is not None
        assert project.name == "Test Project"
        assert project.path == "/test/project/path"
        assert project.user_id == sample_user.id
    
    @pytest.mark.database
    def test_get_project_by_path_success(self, project_repo, sample_project):
        """测试根据路径获取项目成功"""
        project = project_repo.get_project_by_path(
            user_id=sample_project.user_id,
            path=sample_project.path
        )
        
        assert project is not None
        assert project.id == sample_project.id
        assert project.path == sample_project.path
    
    @pytest.mark.database
    def test_get_project_by_path_not_found(self, project_repo, sample_user):
        """测试根据路径获取项目不存在"""
        project = project_repo.get_project_by_path(
            user_id=sample_user.id,
            path="/nonexistent/path"
        )
        
        assert project is None
    
    @pytest.mark.database
    def test_list_user_projects(self, project_repo, sample_user, db_session):
        """测试获取用户项目列表"""
        # 创建多个项目
        for i in range(3):
            project = Project(
                user_id=sample_user.id,
                name=f"Project {i}",
                path=f"/test/project{i}"
            )
            db_session.add(project)
        db_session.commit()
        
        projects = project_repo.list_user_projects(sample_user.id)
        
        assert len(projects) == 3
        assert all(p.user_id == sample_user.id for p in projects)
    
    @pytest.mark.database
    def test_update_project_last_scan(self, project_repo, sample_project):
        """测试更新项目最后扫描时间"""
        scan_time = datetime.utcnow()
        
        updated_project = project_repo.update_project_last_scan(
            sample_project.id, scan_time
        )
        
        assert updated_project.last_scan_at == scan_time
    
    @pytest.mark.database
    def test_get_projects_for_scan(self, project_repo, sample_user, db_session):
        """测试获取需要扫描的项目"""
        # 创建需要扫描的项目（从未扫描过）
        never_scanned = Project(
            user_id=sample_user.id,
            name="Never Scanned",
            path="/never/scanned"
        )
        db_session.add(never_scanned)
        
        # 创建最近扫描过的项目
        recently_scanned = Project(
            user_id=sample_user.id,
            name="Recently Scanned",
            path="/recently/scanned",
            last_scan_at=datetime.utcnow() - timedelta(minutes=30)
        )
        db_session.add(recently_scanned)
        
        # 创建很久没扫描的项目
        old_scanned = Project(
            user_id=sample_user.id,
            name="Old Scanned",
            path="/old/scanned",
            last_scan_at=datetime.utcnow() - timedelta(hours=2)
        )
        db_session.add(old_scanned)
        db_session.commit()
        
        # 获取需要扫描的项目（1小时内没扫描过的）
        projects = project_repo.get_projects_for_scan(scan_interval_hours=1)
        
        project_names = [p.name for p in projects]
        assert "Never Scanned" in project_names
        assert "Old Scanned" in project_names
        assert "Recently Scanned" not in project_names


class TestContentSourceRepository:
    """内容源仓储测试类"""
    
    @pytest.fixture
    def content_repo(self, db_session):
        """创建内容源仓储实例"""
        return ContentSourceRepository(db_session)
    
    @pytest.mark.database
    def test_create_content_source_success(self, content_repo, sample_project):
        """测试创建内容源成功"""
        content_data = {
            "project_id": sample_project.id,
            "file_path": "/test/video.mp4",
            "file_name": "video.mp4",
            "file_size": 1024000,
            "file_type": "video/mp4",
            "metadata_path": "/test/video.json",
            "language": "en"
        }
        
        content_source = content_repo.create_content_source(**content_data)
        
        assert content_source.id is not None
        assert content_source.file_path == "/test/video.mp4"
        assert content_source.file_name == "video.mp4"
        assert content_source.project_id == sample_project.id
    
    @pytest.mark.database
    def test_get_content_source_by_path_success(self, content_repo, sample_content_source):
        """测试根据路径获取内容源成功"""
        content_source = content_repo.get_content_source_by_path(
            sample_content_source.file_path
        )
        
        assert content_source is not None
        assert content_source.id == sample_content_source.id
        assert content_source.file_path == sample_content_source.file_path
    
    @pytest.mark.database
    def test_list_project_content_sources(self, content_repo, sample_project, db_session):
        """测试获取项目内容源列表"""
        # 创建多个内容源
        for i in range(3):
            content_source = ContentSource(
                project_id=sample_project.id,
                file_path=f"/test/video{i}.mp4",
                file_name=f"video{i}.mp4",
                file_size=1024000
            )
            db_session.add(content_source)
        db_session.commit()
        
        content_sources = content_repo.list_project_content_sources(sample_project.id)
        
        assert len(content_sources) == 3
        assert all(cs.project_id == sample_project.id for cs in content_sources)
    
    @pytest.mark.database
    def test_update_content_source_metadata(self, content_repo, sample_content_source):
        """测试更新内容源元数据"""
        metadata_path = "/new/metadata.json"
        language = "zh"
        
        updated_content = content_repo.update_content_source_metadata(
            sample_content_source.id,
            metadata_path=metadata_path,
            language=language
        )
        
        assert updated_content.metadata_path == metadata_path
        assert updated_content.language == language
    
    @pytest.mark.database
    def test_get_unpublished_content_sources(self, content_repo, sample_project, db_session):
        """测试获取未发布的内容源"""
        # 创建已发布的内容源
        published_content = ContentSource(
            project_id=sample_project.id,
            file_path="/test/published.mp4",
            file_name="published.mp4",
            file_size=1024000
        )
        db_session.add(published_content)
        db_session.commit()
        
        # 创建发布任务
        task = PublishingTask(
            project_id=sample_project.id,
            source_id=published_content.id,
            media_path="/test/published.mp4",
            content_data="{}",
            status="completed",
            scheduled_at=datetime.utcnow()
        )
        db_session.add(task)
        
        # 创建未发布的内容源
        unpublished_content = ContentSource(
            project_id=sample_project.id,
            file_path="/test/unpublished.mp4",
            file_name="unpublished.mp4",
            file_size=1024000
        )
        db_session.add(unpublished_content)
        db_session.commit()
        
        unpublished = content_repo.get_unpublished_content_sources(sample_project.id)
        
        assert len(unpublished) == 1
        assert unpublished[0].id == unpublished_content.id


class TestPublishingTaskRepository:
    """发布任务仓储测试类"""
    
    @pytest.fixture
    def task_repo(self, db_session):
        """创建发布任务仓储实例"""
        return PublishingTaskRepository(db_session)
    
    @pytest.mark.database
    def test_create_publishing_task_success(self, task_repo, sample_content_source):
        """测试创建发布任务成功"""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        task_data = {
            "project_id": sample_content_source.project_id,
            "source_id": sample_content_source.id,
            "media_path": "/test/media.mp4",
            "content_data": "{}",
            "status": "pending",
            "scheduled_at": scheduled_time,
            "priority": 1
        }
        
        task = task_repo.create_publishing_task(**task_data)
        
        assert task.id is not None
        assert task.status == "pending"
        assert task.scheduled_at == scheduled_time
        assert task.priority == 1
    
    @pytest.mark.database
    def test_get_pending_tasks(self, task_repo, sample_content_source, db_session):
        """测试获取待处理任务"""
        # 创建待处理任务（已到时间）
        pending_task = PublishingTask(
            project_id=sample_content_source.project_id,
            source_id=sample_content_source.id,
            media_path="/test/path.mp4",
            content_data="{}",
            status="pending",
            scheduled_at=datetime.utcnow() - timedelta(minutes=5)
        )
        db_session.add(pending_task)
        
        # 创建未来任务
        future_task = PublishingTask(
            project_id=sample_content_source.project_id,
            source_id=sample_content_source.id,
            media_path="/test/path2.mp4",
            content_data="{}",
            status="pending",
            scheduled_at=datetime.utcnow() + timedelta(hours=1)
        )
        db_session.add(future_task)
        
        # 创建已完成任务
        completed_task = PublishingTask(
            project_id=sample_content_source.project_id,
            source_id=sample_content_source.id,
            media_path="/test/path3.mp4",
            content_data="{}",
            status="completed",
            scheduled_at=datetime.utcnow() - timedelta(minutes=10)
        )
        db_session.add(completed_task)
        db_session.commit()
        
        pending_tasks = task_repo.get_pending_tasks(limit=10)
        
        assert len(pending_tasks) == 1
        assert pending_tasks[0].id == pending_task.id
    
    @pytest.mark.database
    def test_update_task_status(self, task_repo, sample_publishing_task):
        """测试更新任务状态"""
        task_repo.update_task_status(
            sample_publishing_task.id,
            status="completed",
            error_message=None
        )
        
        task_repo.db_session.refresh(sample_publishing_task)
        assert sample_publishing_task.status == "completed"
        assert sample_publishing_task.completed_at is not None
    
    @pytest.mark.database
    def test_get_failed_tasks_for_retry(self, task_repo, sample_content_source, db_session):
        """测试获取可重试的失败任务"""
        # 创建可重试的失败任务
        retryable_task = PublishingTask(
            project_id=sample_content_source.project_id,
            source_id=sample_content_source.id,
            media_path="/test/retry.mp4",
            content_data="{}",
            status="failed",
            retry_count=1,
            scheduled_at=datetime.utcnow() - timedelta(hours=1)
        )
        db_session.add(retryable_task)
        
        # 创建重试次数过多的任务
        max_retry_task = PublishingTask(
            project_id=sample_content_source.project_id,
            source_id=sample_content_source.id,
            media_path="/test/maxretry.mp4",
            content_data="{}",
            status="failed",
            retry_count=5,  # 超过最大重试次数
            scheduled_at=datetime.utcnow() - timedelta(hours=1)
        )
        db_session.add(max_retry_task)
        db_session.commit()
        
        failed_tasks = task_repo.get_failed_tasks_for_retry(max_retry_count=3)
        
        assert len(failed_tasks) == 1
        assert failed_tasks[0].id == retryable_task.id
    
    @pytest.mark.database
    def test_get_project_task_stats(self, task_repo, sample_project, sample_content_source, db_session):
        """测试获取项目任务统计"""
        # 创建不同状态的任务
        statuses = ["pending", "completed", "failed", "completed", "pending"]
        for i, status in enumerate(statuses):
            task = PublishingTask(
                project_id=sample_project.id,
                source_id=sample_content_source.id,
                media_path=f"/test/stats{i}.mp4",
                content_data="{}",
                status=status,
                scheduled_at=datetime.utcnow()
            )
            db_session.add(task)
        db_session.commit()
        
        stats = task_repo.get_project_task_stats(sample_project.id)
        
        assert stats["total"] == 5
        assert stats["pending"] == 2
        assert stats["completed"] == 2
        assert stats["failed"] == 1


class TestPublishingLogRepository:
    """发布日志仓储测试类"""
    
    @pytest.fixture
    def log_repo(self, db_session):
        """创建发布日志仓储实例"""
        return PublishingLogRepository(db_session)
    
    @pytest.mark.database
    def test_create_publishing_log_success(self, log_repo, sample_publishing_task):
        """测试创建发布日志成功"""
        log_data = {
            "task_id": sample_publishing_task.id,
            "status": "success",
            "tweet_id": "123456789",
            "tweet_url": "https://twitter.com/test/status/123456789",
            "duration_seconds": 2.5
        }
        
        log = log_repo.create_publishing_log(**log_data)
        
        assert log.id is not None
        assert log.status == "success"
        assert log.tweet_id == "123456789"
        assert log.duration_seconds == 2.5
    
    @pytest.mark.database
    def test_get_task_logs(self, log_repo, sample_publishing_task, db_session):
        """测试获取任务日志"""
        # 创建多个日志
        for i in range(3):
            log = PublishingLog(
                task_id=sample_publishing_task.id,
                status="success" if i % 2 == 0 else "failed",
                duration_seconds=float(i + 1)
            )
            db_session.add(log)
        db_session.commit()
        
        logs = log_repo.get_task_logs(sample_publishing_task.id)
        
        assert len(logs) == 3
        assert all(log.task_id == sample_publishing_task.id for log in logs)
    
    @pytest.mark.database
    def test_get_project_logs_with_pagination(self, log_repo, sample_project, sample_publishing_task, db_session):
        """测试分页获取项目日志"""
        # 创建多个日志
        for i in range(5):
            log = PublishingLog(
                task_id=sample_publishing_task.id,
                status="success",
                execution_time=float(i + 1)
            )
            db_session.add(log)
        db_session.commit()
        
        logs, total = log_repo.get_project_logs(
            sample_project.id, page=1, page_size=3
        )
        
        assert len(logs) == 3
        assert total == 5
    
    @pytest.mark.database
    def test_cleanup_old_logs(self, log_repo, sample_publishing_task, db_session):
        """测试清理旧日志"""
        # 创建旧日志
        old_log = PublishingLog(
            task_id=sample_publishing_task.id,
            status="success"
        )
        old_log.created_at = datetime.utcnow() - timedelta(days=31)
        db_session.add(old_log)
        
        # 创建新日志
        new_log = PublishingLog(
            task_id=sample_publishing_task.id,
            status="success"
        )
        db_session.add(new_log)
        db_session.commit()
        
        deleted_count = log_repo.cleanup_old_logs(days=30)
        
        assert deleted_count == 1
        
        # 验证只有新日志保留
        remaining_logs = log_repo.db_session.query(PublishingLog).all()
        assert len(remaining_logs) == 1
        assert remaining_logs[0].id == new_log.id


class TestAnalyticsRepository:
    """分析仓储测试类"""
    
    @pytest.fixture
    def analytics_repo(self, db_session):
        """创建分析仓储实例"""
        return AnalyticsRepository(db_session)
    
    @pytest.mark.database
    def test_update_hourly_analytics_new_record(self, analytics_repo, sample_project):
        """测试更新小时分析（新记录）"""
        hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        analytics_repo.update_hourly_analytics(
            project_id=sample_project.id,
            hour_timestamp=hour,
            successful_tasks=1,
            failed_tasks=0,
            total_duration_seconds=2.5
        )
        
        analytics = analytics_repo.db_session.query(AnalyticsHourly).filter_by(
            project_id=sample_project.id,
            hour_timestamp=hour
        ).first()
        
        assert analytics is not None
        assert analytics.successful_tasks == 1
        assert analytics.failed_tasks == 0
        assert analytics.total_duration_seconds == 2.5
    
    @pytest.mark.database
    def test_update_hourly_analytics_existing_record(self, analytics_repo, sample_project, db_session):
        """测试更新小时分析（已存在记录）"""
        hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        # 创建已存在的记录
        existing_analytics = AnalyticsHourly(
            project_id=sample_project.id,
            hour_timestamp=hour,
            successful_tasks=2,
            failed_tasks=1,
            total_duration_seconds=5.0
        )
        db_session.add(existing_analytics)
        db_session.commit()
        
        # 更新记录
        analytics_repo.update_hourly_analytics(
            project_id=sample_project.id,
            hour_timestamp=hour,
            successful_tasks=1,
            failed_tasks=0,
            total_duration_seconds=2.5
        )
        
        db_session.refresh(existing_analytics)
        assert existing_analytics.successful_tasks == 3  # 2 + 1
        assert existing_analytics.failed_tasks == 1      # 1 + 0
        assert existing_analytics.total_duration_seconds == 7.5  # 5.0 + 2.5
    
    @pytest.mark.database
    def test_get_project_analytics_summary(self, analytics_repo, sample_project, db_session):
        """测试获取项目分析摘要"""
        # 创建多个小时的分析数据
        base_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        for i in range(24):  # 24小时数据
            hour = base_hour - timedelta(hours=i)
            analytics = AnalyticsHourly(
                project_id=sample_project.id,
                hour_timestamp=hour,
                successful_tasks=i + 1,
                failed_tasks=i % 3,
                total_duration_seconds=float((i + 1) * 2)
            )
            db_session.add(analytics)
        db_session.commit()
        
        # 获取最近24小时摘要
        summary = analytics_repo.get_project_analytics_summary(
            sample_project.id,
            hours=24
        )
        
        assert summary["total_successful"] == sum(range(1, 25))  # 1+2+...+24
        assert summary["total_failed"] == sum(i % 3 for i in range(24))
        assert summary["total_duration_seconds"] == sum((i + 1) * 2 for i in range(24))
        assert summary["average_duration_seconds"] > 0
    
    @pytest.mark.database
    def test_get_hourly_analytics_data(self, analytics_repo, sample_project, db_session):
        """测试获取小时分析数据"""
        # 创建测试数据
        base_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        for i in range(5):
            hour = base_hour - timedelta(hours=i)
            analytics = AnalyticsHourly(
                project_id=sample_project.id,
                hour_timestamp=hour,
                successful_tasks=i + 1,
                failed_tasks=i,
                total_duration_seconds=float((i + 1) * 1.5)
            )
            db_session.add(analytics)
        db_session.commit()
        
        # 获取数据
        analytics_data = analytics_repo.get_hourly_analytics_data(
            sample_project.id,
            start_time=base_hour - timedelta(hours=4),
            end_time=base_hour + timedelta(hours=1)
        )
        
        assert len(analytics_data) == 5
        assert all(a.project_id == sample_project.id for a in analytics_data)
        
        # 验证按时间排序
        for i in range(len(analytics_data) - 1):
            assert analytics_data[i].hour_timestamp >= analytics_data[i + 1].hour_timestamp
    
    @pytest.mark.database
    def test_cleanup_old_analytics(self, analytics_repo, sample_project, db_session):
        """测试清理旧分析数据"""
        base_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        # 创建旧数据
        old_analytics = AnalyticsHourly(
            project_id=sample_project.id,
            hour_timestamp=base_hour - timedelta(days=91),  # 91天前
            successful_tasks=1,
            failed_tasks=0,
            total_duration_seconds=1.0
        )
        db_session.add(old_analytics)
        
        # 创建新数据
        new_analytics = AnalyticsHourly(
            project_id=sample_project.id,
            hour_timestamp=base_hour,
            successful_tasks=1,
            failed_tasks=0,
            total_duration_seconds=1.0
        )
        db_session.add(new_analytics)
        db_session.commit()
        
        # 清理90天前的数据
        deleted_count = analytics_repo.cleanup_old_analytics(days=90)
        
        assert deleted_count == 1
        
        # 验证只有新数据保留
        remaining_analytics = analytics_repo.db_session.query(AnalyticsHourly).all()
        assert len(remaining_analytics) == 1
        assert remaining_analytics[0].id == new_analytics.id


class TestRepositoryErrorHandling:
    """仓储错误处理测试类"""
    
    @pytest.mark.database
    def test_database_connection_error(self, db_session):
        """测试数据库连接错误处理"""
        user_repo = UserRepository(db_session)
        
        # 模拟数据库连接错误
        with patch.object(db_session, 'add', side_effect=Exception("Database connection error")):
            with pytest.raises(Exception) as exc_info:
                user_repo.create_user(
                    username="testuser",
                    email="test@example.com",
                    password_hash="hashed_password"
                )
            
            assert "Database connection error" in str(exc_info.value)
    
    @pytest.mark.database
    def test_transaction_rollback(self, db_session):
        """测试事务回滚"""
        user_repo = UserRepository(db_session)
        
        # 模拟提交时出错
        with patch.object(db_session, 'commit', side_effect=Exception("Commit failed")):
            with pytest.raises(Exception):
                user_repo.create_user(
                    username="testuser",
                    email="test@example.com",
                    password_hash="hashed_password"
                )
            
            # 验证没有创建用户
            users = db_session.query(User).filter_by(username="testuser").all()
            assert len(users) == 0