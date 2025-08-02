import pytest
import tempfile
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.database.models import Base, User, ApiKey, Project, ContentSource, PublishingTask, PublishingLog, AnalyticsHourly
from app.database.repository import (
    UserRepository, ProjectRepository, ContentSourceRepository,
    PublishingTaskRepository, PublishingLogRepository, AnalyticsRepository
)
from api.schemas import TaskStatusEnum


class TestDatabaseOperationsIntegration:
    """数据库操作集成测试类"""
    
    @pytest.fixture
    def real_db_engine(self):
        """创建真实的SQLite数据库引擎"""
        # 创建临时数据库文件
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)
        
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(engine)
        
        yield engine
        
        # 清理
        engine.dispose()
        os.unlink(db_path)
    
    @pytest.fixture
    def real_db_session(self, real_db_engine):
        """创建真实的数据库会话"""
        SessionLocal = sessionmaker(bind=real_db_engine)
        session = SessionLocal()
        
        yield session
        
        session.close()
    
    @pytest.fixture
    def repositories(self, real_db_session):
        """创建所有仓库实例"""
        return {
            'user': UserRepository(real_db_session),
            'project': ProjectRepository(real_db_session),
            'content_source': ContentSourceRepository(real_db_session),
            'publishing_task': PublishingTaskRepository(real_db_session),
            'publishing_log': PublishingLogRepository(real_db_session),
            'analytics': AnalyticsRepository(real_db_session)
        }
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_complete_user_workflow(self, repositories, real_db_session):
        """测试完整的用户工作流程"""
        user_repo = repositories['user']
        
        # 1. 创建用户
        user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password_hash': 'hashed_password',
            'is_active': True
        }
        user = user_repo.create(user_data)
        real_db_session.commit()
        
        assert user.id is not None
        assert user.username == 'testuser'
        
        # 2. 创建API密钥
        api_key = ApiKey(
            user_id=user.id,
            name='test_key',
            key_hash='hashed_key',
            is_active=True
        )
        real_db_session.add(api_key)
        real_db_session.commit()
        
        # 3. 验证用户和API密钥关系
        retrieved_user = user_repo.get_by_id(user.id)
        assert len(retrieved_user.api_keys) == 1
        assert retrieved_user.api_keys[0].name == 'test_key'
        
        # 4. 更新用户信息
        updated_user = user_repo.update(user.id, {'email': 'updated@example.com'})
        real_db_session.commit()
        
        assert updated_user.email == 'updated@example.com'
        
        # 5. 删除用户（级联删除API密钥）
        user_repo.delete(user.id)
        real_db_session.commit()
        
        assert user_repo.get_by_id(user.id) is None
        assert real_db_session.query(ApiKey).filter_by(user_id=user.id).first() is None
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_complete_project_workflow(self, repositories, real_db_session, sample_user):
        """测试完整的项目工作流程"""
        project_repo = repositories['project']
        content_source_repo = repositories['content_source']
        
        # 添加用户到数据库
        real_db_session.add(sample_user)
        real_db_session.commit()
        
        # 1. 创建项目
        project_data = {
            'user_id': sample_user.id,
            'name': 'Test Project',
            'path': '/path/to/project',
            'description': 'A test project',
            'is_active': True
        }
        project = project_repo.create(project_data)
        real_db_session.commit()
        
        assert project.id is not None
        assert project.name == 'Test Project'
        
        # 2. 添加内容源
        content_source_data = {
            'project_id': project.id,
            'file_path': '/path/to/video.mp4',
            'file_name': 'video.mp4',
            'file_size': 1024000,
            'metadata': {'title': 'Test Video', 'duration': 120}
        }
        content_source = content_source_repo.create(content_source_data)
        real_db_session.commit()
        
        # 3. 验证项目和内容源关系
        retrieved_project = project_repo.get_by_id(project.id)
        assert len(retrieved_project.content_sources) == 1
        assert retrieved_project.content_sources[0].file_name == 'video.mp4'
        
        # 4. 更新项目最后扫描时间
        now = datetime.utcnow()
        updated_project = project_repo.update_last_scan(project.id, now)
        real_db_session.commit()
        
        assert updated_project.last_scan_at == now
        
        # 5. 获取用户的所有项目
        user_projects = project_repo.get_by_user_id(sample_user.id)
        assert len(user_projects) == 1
        assert user_projects[0].id == project.id
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_complete_publishing_workflow(self, repositories, real_db_session, sample_user):
        """测试完整的发布工作流程"""
        project_repo = repositories['project']
        content_source_repo = repositories['content_source']
        task_repo = repositories['publishing_task']
        log_repo = repositories['publishing_log']
        analytics_repo = repositories['analytics']
        
        # 添加用户到数据库
        real_db_session.add(sample_user)
        real_db_session.commit()
        
        # 1. 创建项目和内容源
        project = project_repo.create({
            'user_id': sample_user.id,
            'name': 'Publishing Test',
            'path': '/path/to/project',
            'is_active': True
        })
        real_db_session.commit()
        
        content_source = content_source_repo.create({
            'project_id': project.id,
            'file_path': '/path/to/video.mp4',
            'file_name': 'video.mp4',
            'file_size': 1024000,
            'metadata': {'title': 'Test Video'}
        })
        real_db_session.commit()
        
        # 2. 创建发布任务
        task_data = {
            'content_source_id': content_source.id,
            'scheduled_at': datetime.utcnow() + timedelta(hours=1),
            'content': 'Test tweet content',
            'status': "pending"
        }
        task = task_repo.create(task_data)
        real_db_session.commit()
        
        # 3. 获取待处理任务
        pending_tasks = task_repo.get_pending_tasks(limit=10)
        assert len(pending_tasks) == 1
        assert pending_tasks[0].id == task.id
        
        # 4. 更新任务状态为处理中
        task_repo.update_status(task.id, "locked")
        real_db_session.commit()
        
        # 5. 记录发布日志
        log_data = {
            'task_id': task.id,
            'status': "success",
            'tweet_id': '1234567890',
            'response_data': {'id': '1234567890', 'text': 'Test tweet content'}
        }
        log = log_repo.create(log_data)
        real_db_session.commit()
        
        # 6. 更新任务状态为完成
        task_repo.update_status(task.id, "success")
        real_db_session.commit()
        
        # 7. 更新分析数据
        hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        analytics_repo.update_hourly_stats(
            user_id=sample_user.id,
            hour=hour,
            tweets_published=1,
            total_impressions=100,
            total_engagements=10
        )
        real_db_session.commit()
        
        # 8. 验证完整工作流程
        completed_task = task_repo.get_by_id(task.id)
        assert completed_task.status == "success"
        
        task_logs = log_repo.get_by_task_id(task.id)
        assert len(task_logs) == 1
        assert task_logs[0].status == "success"
        
        analytics = analytics_repo.get_hourly_stats(sample_user.id, hour, hour)
        assert len(analytics) == 1
        assert analytics[0].tweets_published == 1
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_database_constraints_and_relationships(self, real_db_session, sample_user):
        """测试数据库约束和关系"""
        real_db_session.add(sample_user)
        real_db_session.commit()
        
        # 1. 测试唯一约束
        duplicate_user = User(
            username=sample_user.username,  # 重复用户名
            email='different@example.com',
            password_hash='hash'
        )
        real_db_session.add(duplicate_user)
        
        with pytest.raises(IntegrityError):
            real_db_session.commit()
        
        real_db_session.rollback()
        
        # 2. 测试外键约束
        invalid_project = Project(
            user_id=99999,  # 不存在的用户ID
            name='Invalid Project',
            path='/invalid/path'
        )
        real_db_session.add(invalid_project)
        
        with pytest.raises(IntegrityError):
            real_db_session.commit()
        
        real_db_session.rollback()
        
        # 3. 测试级联删除
        project = Project(
            user_id=sample_user.id,
            name='Test Project',
            path='/test/path'
        )
        real_db_session.add(project)
        real_db_session.commit()
        
        content_source = ContentSource(
            project_id=project.id,
            file_path='/test/video.mp4',
            file_name='video.mp4',
            file_size=1024
        )
        real_db_session.add(content_source)
        real_db_session.commit()
        
        # 删除项目应该级联删除内容源
        real_db_session.delete(project)
        real_db_session.commit()
        
        assert real_db_session.query(ContentSource).filter_by(project_id=project.id).first() is None
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_transaction_rollback(self, repositories, real_db_session, sample_user):
        """测试事务回滚"""
        user_repo = repositories['user']
        project_repo = repositories['project']
        
        real_db_session.add(sample_user)
        real_db_session.commit()
        
        try:
            # 开始事务
            project1 = project_repo.create({
                'user_id': sample_user.id,
                'name': 'Project 1',
                'path': '/path/1',
                'is_active': True
            })
            
            project2 = project_repo.create({
                'user_id': sample_user.id,
                'name': 'Project 2',
                'path': '/path/1',  # 重复路径，应该失败
                'is_active': True
            })
            
            # 这应该失败并回滚整个事务
            real_db_session.commit()
            
        except IntegrityError:
            real_db_session.rollback()
        
        # 验证没有项目被创建
        projects = project_repo.get_by_user_id(sample_user.id)
        assert len(projects) == 0
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_complex_queries_and_joins(self, repositories, real_db_session, sample_user):
        """测试复杂查询和连接"""
        project_repo = repositories['project']
        content_source_repo = repositories['content_source']
        task_repo = repositories['publishing_task']
        
        real_db_session.add(sample_user)
        real_db_session.commit()
        
        # 创建测试数据
        project = project_repo.create({
            'user_id': sample_user.id,
            'name': 'Complex Query Test',
            'path': '/complex/path',
            'is_active': True
        })
        real_db_session.commit()
        
        # 创建多个内容源
        for i in range(3):
            content_source = content_source_repo.create({
                'project_id': project.id,
                'file_path': f'/path/video{i}.mp4',
                'file_name': f'video{i}.mp4',
                'file_size': 1024 * (i + 1),
                'metadata': {'title': f'Video {i}'}
            })
            
            # 为每个内容源创建任务
            task_repo.create({
                'content_source_id': content_source.id,
                'scheduled_at': datetime.utcnow() + timedelta(hours=i),
                'content': f'Tweet content {i}',
                'status': "pending" if i < 2 else "success"
            })
        
        real_db_session.commit()
        
        # 测试复杂查询：获取用户的所有待处理任务
        pending_tasks = real_db_session.query(PublishingTask).join(
            ContentSource
        ).join(
            Project
        ).filter(
            Project.user_id == sample_user.id,
            PublishingTask.status == "pending"
        ).all()
        
        assert len(pending_tasks) == 2
        
        # 测试聚合查询：统计用户的内容源数量
        content_count = real_db_session.query(ContentSource).join(
            Project
        ).filter(
            Project.user_id == sample_user.id
        ).count()
        
        assert content_count == 3
        
        # 测试分组查询：按状态统计任务数量
        task_stats = real_db_session.query(
            PublishingTask.status,
            real_db_session.query(PublishingTask).filter(
                PublishingTask.status == PublishingTask.status
            ).count().label('count')
        ).join(
            ContentSource
        ).join(
            Project
        ).filter(
            Project.user_id == sample_user.id
        ).group_by(
            PublishingTask.status
        ).all()
        
        status_counts = {status: count for status, count in task_stats}
        assert status_counts.get("pending", 0) == 2
        assert status_counts.get("success", 0) == 1
    
    @pytest.mark.integration
    @pytest.mark.database
    @pytest.mark.slow
    def test_database_performance(self, repositories, real_db_session, sample_user):
        """测试数据库性能"""
        import time
        
        project_repo = repositories['project']
        content_source_repo = repositories['content_source']
        
        real_db_session.add(sample_user)
        real_db_session.commit()
        
        # 创建大量测试数据
        start_time = time.time()
        
        projects = []
        for i in range(10):
            project = project_repo.create({
                'user_id': sample_user.id,
                'name': f'Performance Test Project {i}',
                'path': f'/performance/path/{i}',
                'is_active': True
            })
            projects.append(project)
        
        real_db_session.commit()
        
        # 为每个项目创建内容源
        for project in projects:
            for j in range(10):
                content_source_repo.create({
                    'project_id': project.id,
                    'file_path': f'/performance/video_{project.id}_{j}.mp4',
                    'file_name': f'video_{project.id}_{j}.mp4',
                    'file_size': 1024 * j,
                    'metadata': {'title': f'Performance Video {j}'}
                })
        
        real_db_session.commit()
        
        creation_time = time.time() - start_time
        
        # 测试查询性能
        start_time = time.time()
        
        user_projects = project_repo.get_by_user_id(sample_user.id)
        assert len(user_projects) == 10
        
        for project in user_projects:
            content_sources = content_source_repo.get_by_project_id(project.id)
            assert len(content_sources) == 10
        
        query_time = time.time() - start_time
        
        # 性能断言（这些值可能需要根据实际环境调整）
        assert creation_time < 5.0, f"Data creation took too long: {creation_time}s"
        assert query_time < 2.0, f"Query took too long: {query_time}s"
        
        print(f"Performance test results:")
        print(f"  Data creation: {creation_time:.2f}s")
        print(f"  Query execution: {query_time:.2f}s")
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_concurrent_access(self, real_db_engine, sample_user):
        """测试并发访问"""
        import threading
        import time
        
        SessionLocal = sessionmaker(bind=real_db_engine)
        
        # 添加用户到数据库
        session = SessionLocal()
        session.add(sample_user)
        session.commit()
        session.close()
        
        results = []
        errors = []
        
        def create_project(thread_id):
            """在单独的线程中创建项目"""
            try:
                session = SessionLocal()
                project_repo = ProjectRepository(session)
                
                project = project_repo.create({
                    'user_id': sample_user.id,
                    'name': f'Concurrent Project {thread_id}',
                    'path': f'/concurrent/path/{thread_id}',
                    'is_active': True
                })
                session.commit()
                
                results.append(project.id)
                session.close()
                
            except Exception as e:
                errors.append(str(e))
        
        # 启动多个线程
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_project, args=(i,))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证结果
        assert len(errors) == 0, f"Concurrent access errors: {errors}"
        assert len(results) == 5, f"Expected 5 projects, got {len(results)}"
        assert len(set(results)) == 5, "Duplicate project IDs detected"
        
        # 验证数据库中的数据
        session = SessionLocal()
        project_repo = ProjectRepository(session)
        user_projects = project_repo.get_by_user_id(sample_user.id)
        assert len(user_projects) == 5
        session.close()