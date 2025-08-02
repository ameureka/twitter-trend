import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database.models import (
    User, ApiKey, Project, ContentSource, 
    PublishingTask, PublishingLog, AnalyticsHourly
)


class TestUserModel:
    """用户模型测试类"""
    
    @pytest.mark.database
    def test_create_user_success(self, db_session):
        """测试创建用户成功"""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.created_at is not None
        assert user.updated_at is not None
    
    @pytest.mark.database
    def test_user_unique_username(self, db_session):
        """测试用户名唯一性约束"""
        user1 = User(
            username="testuser",
            email="test1@example.com",
            password_hash="hashed_password"
        )
        user2 = User(
            username="testuser",  # 重复用户名
            email="test2@example.com",
            password_hash="hashed_password"
        )
        
        db_session.add(user1)
        db_session.commit()
        
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    @pytest.mark.database
    def test_user_unique_email(self, db_session):
        """测试邮箱唯一性约束"""
        user1 = User(
            username="testuser1",
            email="test@example.com",
            password_hash="hashed_password"
        )
        user2 = User(
            username="testuser2",
            email="test@example.com",  # 重复邮箱
            password_hash="hashed_password"
        )
        
        db_session.add(user1)
        db_session.commit()
        
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    @pytest.mark.database
    def test_user_relationships(self, db_session, sample_user):
        """测试用户关系"""
        # 创建API密钥
        api_key = ApiKey(
            user_id=sample_user.id,
            key_name="test_key",
            key_value="test_api_key_value"
        )
        db_session.add(api_key)
        
        # 创建项目
        project = Project(
            user_id=sample_user.id,
            name="Test Project",
            path="/test/path"
        )
        db_session.add(project)
        db_session.commit()
        
        # 验证关系
        assert len(sample_user.api_keys) == 1
        assert len(sample_user.projects) == 1
        assert sample_user.api_keys[0].key_name == "test_key"
        assert sample_user.projects[0].name == "Test Project"


class TestApiKeyModel:
    """API密钥模型测试类"""
    
    @pytest.mark.database
    def test_create_api_key_success(self, db_session, sample_user):
        """测试创建API密钥成功"""
        api_key = ApiKey(
            user_id=sample_user.id,
            key_name="twitter_api",
            key_value="test_api_key_value",
            description="Twitter API Key"
        )
        db_session.add(api_key)
        db_session.commit()
        
        assert api_key.id is not None
        assert api_key.key_name == "twitter_api"
        assert api_key.key_value == "test_api_key_value"
        assert api_key.description == "Twitter API Key"
        assert api_key.is_active is True
        assert api_key.created_at is not None
    
    @pytest.mark.database
    def test_api_key_user_relationship(self, db_session, sample_user):
        """测试API密钥与用户关系"""
        api_key = ApiKey(
            user_id=sample_user.id,
            key_name="test_key",
            key_value="test_value"
        )
        db_session.add(api_key)
        db_session.commit()
        
        assert api_key.user.id == sample_user.id
        assert api_key.user.username == sample_user.username
    
    @pytest.mark.database
    def test_api_key_unique_constraint(self, db_session, sample_user):
        """测试API密钥唯一性约束"""
        api_key1 = ApiKey(
            user_id=sample_user.id,
            key_name="twitter_api",
            key_value="value1"
        )
        api_key2 = ApiKey(
            user_id=sample_user.id,
            key_name="twitter_api",  # 同一用户重复key_name
            key_value="value2"
        )
        
        db_session.add(api_key1)
        db_session.commit()
        
        db_session.add(api_key2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestProjectModel:
    """项目模型测试类"""
    
    @pytest.mark.database
    def test_create_project_success(self, db_session, sample_user):
        """测试创建项目成功"""
        project = Project(
            user_id=sample_user.id,
            name="Test Project",
            path="/test/project/path",
            description="Test project description"
        )
        db_session.add(project)
        db_session.commit()
        
        assert project.id is not None
        assert project.name == "Test Project"
        assert project.path == "/test/project/path"
        assert project.description == "Test project description"
        assert project.is_active is True
        assert project.created_at is not None
        assert project.updated_at is not None
    
    @pytest.mark.database
    def test_project_user_relationship(self, db_session, sample_user):
        """测试项目与用户关系"""
        project = Project(
            user_id=sample_user.id,
            name="Test Project",
            path="/test/path"
        )
        db_session.add(project)
        db_session.commit()
        
        assert project.user.id == sample_user.id
        assert project.user.username == sample_user.username
    
    @pytest.mark.database
    def test_project_unique_path_per_user(self, db_session, sample_user):
        """测试同一用户项目路径唯一性"""
        project1 = Project(
            user_id=sample_user.id,
            name="Project 1",
            path="/test/path"
        )
        project2 = Project(
            user_id=sample_user.id,
            name="Project 2",
            path="/test/path"  # 重复路径
        )
        
        db_session.add(project1)
        db_session.commit()
        
        db_session.add(project2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    @pytest.mark.database
    def test_project_relationships(self, db_session, sample_project):
        """测试项目关系"""
        # 创建内容源
        content_source = ContentSource(
            project_id=sample_project.id,
            file_path="/test/video.mp4",
            file_name="video.mp4",
            file_size=1024000
        )
        db_session.add(content_source)
        
        # 创建发布任务
        task = PublishingTask(
            project_id=sample_project.id,
            content_source_id=content_source.id,
            status="pending",
            scheduled_time=datetime.utcnow()
        )
        db_session.add(task)
        db_session.commit()
        
        # 验证关系
        assert len(sample_project.content_sources) == 1
        assert len(sample_project.publishing_tasks) == 1
        assert sample_project.content_sources[0].file_name == "video.mp4"
        assert sample_project.publishing_tasks[0].status == "pending"


class TestContentSourceModel:
    """内容源模型测试类"""
    
    @pytest.mark.database
    def test_create_content_source_success(self, db_session, sample_project):
        """测试创建内容源成功"""
        content_source = ContentSource(
            project_id=sample_project.id,
            file_path="/test/video.mp4",
            file_name="video.mp4",
            file_size=1024000,
            file_type="video/mp4",
            metadata_path="/test/video.json",
            language="en"
        )
        db_session.add(content_source)
        db_session.commit()
        
        assert content_source.id is not None
        assert content_source.file_path == "/test/video.mp4"
        assert content_source.file_name == "video.mp4"
        assert content_source.file_size == 1024000
        assert content_source.file_type == "video/mp4"
        assert content_source.metadata_path == "/test/video.json"
        assert content_source.language == "en"
        assert content_source.created_at is not None
    
    @pytest.mark.database
    def test_content_source_project_relationship(self, db_session, sample_project):
        """测试内容源与项目关系"""
        content_source = ContentSource(
            project_id=sample_project.id,
            file_path="/test/video.mp4",
            file_name="video.mp4",
            file_size=1024000
        )
        db_session.add(content_source)
        db_session.commit()
        
        assert content_source.project.id == sample_project.id
        assert content_source.project.name == sample_project.name
    
    @pytest.mark.database
    def test_content_source_unique_file_path(self, db_session, sample_project):
        """测试内容源文件路径唯一性"""
        content_source1 = ContentSource(
            project_id=sample_project.id,
            file_path="/test/video.mp4",
            file_name="video.mp4",
            file_size=1024000
        )
        content_source2 = ContentSource(
            project_id=sample_project.id,
            file_path="/test/video.mp4",  # 重复文件路径
            file_name="video_copy.mp4",
            file_size=1024000
        )
        
        db_session.add(content_source1)
        db_session.commit()
        
        db_session.add(content_source2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestPublishingTaskModel:
    """发布任务模型测试类"""
    
    @pytest.mark.database
    def test_create_publishing_task_success(self, db_session, sample_content_source):
        """测试创建发布任务成功"""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        task = PublishingTask(
            project_id=sample_content_source.project_id,
            content_source_id=sample_content_source.id,
            status="pending",
            scheduled_time=scheduled_time,
            priority=1
        )
        db_session.add(task)
        db_session.commit()
        
        assert task.id is not None
        assert task.status == "pending"
        assert task.scheduled_time == scheduled_time
        assert task.priority == 1
        assert task.retry_count == 0
        assert task.created_at is not None
    
    @pytest.mark.database
    def test_publishing_task_relationships(self, db_session, sample_content_source):
        """测试发布任务关系"""
        task = PublishingTask(
            project_id=sample_content_source.project_id,
            content_source_id=sample_content_source.id,
            status="pending",
            scheduled_time=datetime.utcnow()
        )
        db_session.add(task)
        db_session.commit()
        
        assert task.project.id == sample_content_source.project_id
        assert task.content_source.id == sample_content_source.id
        assert task.content_source.file_name == sample_content_source.file_name
    
    @pytest.mark.database
    def test_publishing_task_status_update(self, db_session, sample_content_source):
        """测试发布任务状态更新"""
        task = PublishingTask(
            project_id=sample_content_source.project_id,
            content_source_id=sample_content_source.id,
            status="pending",
            scheduled_time=datetime.utcnow()
        )
        db_session.add(task)
        db_session.commit()
        
        # 更新为完成状态
        task.status = "completed"
        task.completed_at = datetime.utcnow()
        db_session.commit()
        
        db_session.refresh(task)
        assert task.status == "completed"
        assert task.completed_at is not None
    
    @pytest.mark.database
    def test_publishing_task_error_handling(self, db_session, sample_content_source):
        """测试发布任务错误处理"""
        task = PublishingTask(
            project_id=sample_content_source.project_id,
            content_source_id=sample_content_source.id,
            status="pending",
            scheduled_time=datetime.utcnow()
        )
        db_session.add(task)
        db_session.commit()
        
        # 更新为失败状态
        task.status = "failed"
        task.error_message = "Twitter API Error"
        task.retry_count = 1
        task.completed_at = datetime.utcnow()
        db_session.commit()
        
        db_session.refresh(task)
        assert task.status == "failed"
        assert task.error_message == "Twitter API Error"
        assert task.retry_count == 1
        assert task.completed_at is not None


class TestPublishingLogModel:
    """发布日志模型测试类"""
    
    @pytest.mark.database
    def test_create_publishing_log_success(self, db_session, sample_publishing_task):
        """测试创建发布日志成功"""
        log = PublishingLog(
            task_id=sample_publishing_task.id,
            status="success",
            tweet_id="123456789",
            tweet_url="https://twitter.com/test/status/123456789",
            execution_time=2.5
        )
        db_session.add(log)
        db_session.commit()
        
        assert log.id is not None
        assert log.status == "success"
        assert log.tweet_id == "123456789"
        assert log.tweet_url == "https://twitter.com/test/status/123456789"
        assert log.execution_time == 2.5
        assert log.created_at is not None
    
    @pytest.mark.database
    def test_publishing_log_task_relationship(self, db_session, sample_publishing_task):
        """测试发布日志与任务关系"""
        log = PublishingLog(
            task_id=sample_publishing_task.id,
            status="success",
            execution_time=1.0
        )
        db_session.add(log)
        db_session.commit()
        
        assert log.task.id == sample_publishing_task.id
        assert log.task.status == sample_publishing_task.status
    
    @pytest.mark.database
    def test_publishing_log_failure(self, db_session, sample_publishing_task):
        """测试发布日志失败记录"""
        log = PublishingLog(
            task_id=sample_publishing_task.id,
            status="failed",
            error_message="Rate limit exceeded",
            execution_time=0.5
        )
        db_session.add(log)
        db_session.commit()
        
        assert log.status == "failed"
        assert log.error_message == "Rate limit exceeded"
        assert log.tweet_id is None
        assert log.tweet_url is None


class TestAnalyticsHourlyModel:
    """小时分析模型测试类"""
    
    @pytest.mark.database
    def test_create_analytics_hourly_success(self, db_session, sample_project):
        """测试创建小时分析记录成功"""
        hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        analytics = AnalyticsHourly(
            project_id=sample_project.id,
            hour=hour,
            successful_tasks=5,
            failed_tasks=1,
            total_execution_time=12.5
        )
        db_session.add(analytics)
        db_session.commit()
        
        assert analytics.id is not None
        assert analytics.hour == hour
        assert analytics.successful_tasks == 5
        assert analytics.failed_tasks == 1
        assert analytics.total_execution_time == 12.5
        assert analytics.created_at is not None
    
    @pytest.mark.database
    def test_analytics_hourly_project_relationship(self, db_session, sample_project):
        """测试小时分析与项目关系"""
        hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        analytics = AnalyticsHourly(
            project_id=sample_project.id,
            hour=hour,
            successful_tasks=1,
            failed_tasks=0,
            total_execution_time=2.0
        )
        db_session.add(analytics)
        db_session.commit()
        
        assert analytics.project.id == sample_project.id
        assert analytics.project.name == sample_project.name
    
    @pytest.mark.database
    def test_analytics_hourly_unique_constraint(self, db_session, sample_project):
        """测试小时分析唯一性约束"""
        hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        analytics1 = AnalyticsHourly(
            project_id=sample_project.id,
            hour=hour,
            successful_tasks=1,
            failed_tasks=0,
            total_execution_time=1.0
        )
        analytics2 = AnalyticsHourly(
            project_id=sample_project.id,
            hour=hour,  # 重复的项目ID和小时
            successful_tasks=2,
            failed_tasks=0,
            total_execution_time=2.0
        )
        
        db_session.add(analytics1)
        db_session.commit()
        
        db_session.add(analytics2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    @pytest.mark.database
    def test_analytics_hourly_update(self, db_session, sample_project):
        """测试小时分析记录更新"""
        hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        analytics = AnalyticsHourly(
            project_id=sample_project.id,
            hour=hour,
            successful_tasks=1,
            failed_tasks=0,
            total_execution_time=1.0
        )
        db_session.add(analytics)
        db_session.commit()
        
        # 更新统计数据
        analytics.successful_tasks += 2
        analytics.failed_tasks += 1
        analytics.total_execution_time += 3.5
        db_session.commit()
        
        db_session.refresh(analytics)
        assert analytics.successful_tasks == 3
        assert analytics.failed_tasks == 1
        assert analytics.total_execution_time == 4.5


class TestModelConstraints:
    """模型约束测试类"""
    
    @pytest.mark.database
    def test_foreign_key_constraints(self, db_session, sample_user):
        """测试外键约束"""
        # 尝试创建引用不存在用户的项目
        project = Project(
            user_id=99999,  # 不存在的用户ID
            name="Test Project",
            path="/test/path"
        )
        db_session.add(project)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    @pytest.mark.database
    def test_cascade_delete(self, db_session, sample_user):
        """测试级联删除"""
        # 创建项目和相关数据
        project = Project(
            user_id=sample_user.id,
            name="Test Project",
            path="/test/path"
        )
        db_session.add(project)
        db_session.commit()
        
        content_source = ContentSource(
            project_id=project.id,
            file_path="/test/video.mp4",
            file_name="video.mp4",
            file_size=1024000
        )
        db_session.add(content_source)
        db_session.commit()
        
        # 删除用户，应该级联删除项目和内容源
        db_session.delete(sample_user)
        db_session.commit()
        
        # 验证相关数据被删除
        assert db_session.query(Project).filter_by(id=project.id).first() is None
        assert db_session.query(ContentSource).filter_by(id=content_source.id).first() is None
    
    @pytest.mark.database
    def test_not_null_constraints(self, db_session, sample_user):
        """测试非空约束"""
        # 尝试创建没有必需字段的项目
        project = Project(
            user_id=sample_user.id,
            # name字段缺失
            path="/test/path"
        )
        db_session.add(project)
        
        with pytest.raises(IntegrityError):
            db_session.commit()