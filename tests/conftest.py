import os
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from click.testing import CliRunner

# 设置测试环境变量
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LOG_LEVEL"] = "ERROR"

from app.database.models import Base, User, Project, ContentSource, PublishingTask, PublishingLog, ApiKey
from app.database.database import DatabaseManager
from api.main import app
from app.main import cli


@pytest.fixture(scope="session")
def db_engine():
    """创建测试数据库引擎"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    # 使用内存SQLite数据库进行测试
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.create_tables()
    
    session = db_manager.get_session()
    
    try:
        yield session
    finally:
        session.close()
        db_manager.close()


@pytest.fixture
def test_client(db_session):
    """创建测试API客户端"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    from api.dependencies import get_db
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def runner():
    """创建CLI测试运行器"""
    return CliRunner()


@pytest.fixture
def temp_project_dir():
    """创建临时项目目录"""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir) / "test_project"
        project_dir.mkdir()
        
        # 创建标准项目结构
        (project_dir / "output_video_music").mkdir()
        (project_dir / "uploader_json").mkdir()
        
        yield str(project_dir)


@pytest.fixture
def sample_metadata():
    """示例元数据"""
    return {
        "batch_info": {
            "total_videos": 1,
            "language": "en",
            "created_at": "2024-01-01T00:00:00Z"
        },
        "videos": [
            {
                "filename": "sample_video_01.mp4",
                "title": "Test Video Title",
                "description": "This is a test video description for automated testing.",
                "tags": ["test", "automation", "video"],
                "duration": 30,
                "size_mb": 5.2,
                "created_at": "2024-01-01T00:00:00Z"
            }
        ]
    }


@pytest.fixture
def sample_user(db_session):
    """创建示例用户"""
    user = User(
        username="testuser",
        role="admin",
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_project(db_session, sample_user):
    """创建示例项目"""
    project = Project(
        name="test_project",
        description="Test project for automated testing",
        user_id=sample_user.id,
        created_at=datetime.utcnow()
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def sample_api_key(db_session, sample_user):
    """创建示例API密钥"""
    api_key = ApiKey(
        user_id=sample_user.id,
        key_hash="test_key_hash",
        name="Test API Key",
        created_at=datetime.utcnow()
    )
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)
    return api_key


@pytest.fixture
def mock_tweepy():
    """Mock Tweepy API"""
    with patch('tweepy.API') as mock_api_class, \
         patch('tweepy.Client') as mock_client_class:
        
        # Mock API v1.1 (用于媒体上传)
        mock_api = Mock()
        mock_api.verify_credentials.return_value = Mock(
            screen_name="test_user",
            id=123456789
        )
        mock_api.media_upload.return_value = Mock(
            media_id=987654321,
            processing_info=None
        )
        mock_api.get_media_upload_status.return_value = Mock(
            processing_info=Mock(state="succeeded")
        )
        mock_api_class.return_value = mock_api
        
        # Mock Client v2 (用于发推)
        mock_client = Mock()
        mock_client.create_tweet.return_value = Mock(
            data={'id': '1234567890123456789', 'text': 'Test tweet'}
        )
        mock_client_class.return_value = mock_client
        
        yield {
            'api': mock_api,
            'client': mock_client,
            'api_class': mock_api_class,
            'client_class': mock_client_class
        }


@pytest.fixture
def mock_gemini():
    """Mock Google Gemini API"""
    with patch('google.generativeai.GenerativeModel') as mock_model_class:
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Enhanced tweet content with AI magic! #AI #Test"
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        yield mock_model


@pytest.fixture
def mock_file_operations():
    """Mock文件操作"""
    with patch('pathlib.Path.exists') as mock_exists, \
         patch('pathlib.Path.is_file') as mock_is_file, \
         patch('pathlib.Path.stat') as mock_stat:
        
        mock_exists.return_value = True
        mock_is_file.return_value = True
        mock_stat.return_value = Mock(st_size=1024*1024*5)  # 5MB
        
        yield {
            'exists': mock_exists,
            'is_file': mock_is_file,
            'stat': mock_stat
        }


@pytest.fixture
def auth_headers(sample_api_key):
    """认证头信息"""
    return {"X-API-Key": "test_key"}


@pytest.fixture(autouse=True)
def setup_test_environment():
    """自动设置测试环境"""
    # 确保测试环境变量
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    
    # Mock外部依赖
    with patch('app.utils.logger.setup_logger') as mock_logger:
        mock_logger.return_value = Mock()
        yield


@pytest.fixture
def sample_content_source(db_session, sample_project):
    """创建示例内容源"""
    content_source = ContentSource(
        project_id=sample_project.id,
        source_type="local_folder",
        path_or_identifier="/test/path/sample_video_01.mp4",
        total_items=1,
        used_items=0,
        created_at=datetime.utcnow()
    )
    db_session.add(content_source)
    db_session.commit()
    db_session.refresh(content_source)
    return content_source


@pytest.fixture
def sample_publishing_task(db_session, sample_content_source):
    """创建示例发布任务"""
    task = PublishingTask(
        source_id=sample_content_source.id,
        project_id=sample_content_source.project_id,
        media_path="/test/path/sample_video_01.mp4",
        content_data='{"title": "Test Video", "description": "Test description"}',
        status="pending",
        scheduled_at=datetime.utcnow() + timedelta(hours=1),
        created_at=datetime.utcnow()
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


# 测试数据清理
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """测试后清理数据"""
    yield
    # 测试完成后的清理工作
    # 这里可以添加额外的清理逻辑