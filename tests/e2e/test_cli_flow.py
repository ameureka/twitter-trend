import pytest
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock

from app.main import cli
from app.database.models import User, Project, ContentSource, PublishingTask
from api.schemas import TaskStatusEnum


class TestCLICompleteWorkflow:
    """CLI完整工作流程端到端测试类"""
    
    @pytest.fixture
    def cli_runner(self):
        """创建CLI运行器"""
        return CliRunner()
    
    @pytest.fixture
    def temp_project_structure(self, tmp_path):
        """创建临时项目结构"""
        # 创建项目目录
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        # 创建视频文件
        video1 = project_dir / "video1.mp4"
        video1.write_bytes(b"fake video content 1" * 1000)  # 模拟较大文件
        
        video2 = project_dir / "video2.mov"
        video2.write_bytes(b"fake video content 2" * 800)
        
        # 创建子目录和视频
        subdir = project_dir / "subfolder"
        subdir.mkdir()
        video3 = subdir / "video3.avi"
        video3.write_bytes(b"fake video content 3" * 600)
        
        # 创建元数据文件
        metadata = {
            "title": "Test Project Videos",
            "description": "A collection of test videos",
            "tags": ["test", "automation", "cli"],
            "author": "Test User",
            "language": "en"
        }
        
        metadata_file = project_dir / "metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))
        
        # 创建中文元数据文件
        metadata_cn = {
            "title": "测试项目视频",
            "description": "测试视频集合",
            "tags": ["测试", "自动化", "命令行"],
            "author": "测试用户",
            "language": "zh"
        }
        
        metadata_cn_file = project_dir / "metadata_cn.json"
        metadata_cn_file.write_text(json.dumps(metadata_cn, indent=2, ensure_ascii=False))
        
        # 创建配置文件
        config = {
            "twitter": {
                "api_key": "test_api_key",
                "api_secret": "test_api_secret",
                "access_token": "test_access_token",
                "access_token_secret": "test_access_token_secret"
            },
            "ai": {
                "provider": "gemini",
                "api_key": "test_gemini_key",
                "model": "gemini-pro"
            },
            "publishing": {
                "schedule_interval": 3600,
                "max_retries": 3,
                "enable_ai_enhancement": True
            }
        }
        
        config_file = project_dir / "config.json"
        config_file.write_text(json.dumps(config, indent=2))
        
        return {
            'project_dir': str(project_dir),
            'video_files': [str(video1), str(video2), str(video3)],
            'metadata_files': [str(metadata_file), str(metadata_cn_file)],
            'config_file': str(config_file)
        }
    
    @pytest.fixture
    def mock_external_services(self):
        """模拟外部服务"""
        with patch('app.core.publisher.TwitterPublisher') as mock_publisher, \
             patch('app.core.content_generator.ContentGenerator') as mock_generator, \
             patch('tweepy.Client') as mock_tweepy:
            
            # 配置Twitter发布器
            mock_publisher_instance = Mock()
            mock_publisher_instance.verify_credentials.return_value = True
            mock_publisher_instance.publish_tweet.return_value = {
                'id': '1234567890',
                'text': 'Published tweet content',
                'created_at': datetime.utcnow().isoformat()
            }
            mock_publisher.return_value = mock_publisher_instance
            
            # 配置内容生成器
            mock_generator_instance = Mock()
            mock_generator_instance.generate_content.return_value = {
                'text': 'AI-enhanced tweet content with #hashtags',
                'hashtags': ['#ai', '#test'],
                'media_paths': []
            }
            mock_generator.return_value = mock_generator_instance
            
            # 配置Tweepy
            mock_tweepy_instance = Mock()
            mock_tweepy_instance.get_me.return_value = Mock(id='123456', username='testuser')
            mock_tweepy.return_value = mock_tweepy_instance
            
            yield {
                'publisher': mock_publisher_instance,
                'generator': mock_generator_instance,
                'tweepy': mock_tweepy_instance
            }
    
    @pytest.mark.e2e
    @pytest.mark.cli
    def test_complete_scan_and_publish_workflow(self, cli_runner, temp_project_structure, mock_external_services, db_session):
        """测试完整的扫描和发布工作流程"""
        project_dir = temp_project_structure['project_dir']
        
        # 1. 初始化用户
        result = cli_runner.invoke(cli, [
            'user', 'create',
            '--username', 'testuser',
            '--email', 'test@example.com',
            '--password', 'testpassword'
        ])
        assert result.exit_code == 0
        assert 'User created successfully' in result.output
        
        # 2. 创建API密钥
        result = cli_runner.invoke(cli, [
            'auth', 'create-key',
            '--username', 'testuser',
            '--name', 'test_key'
        ])
        assert result.exit_code == 0
        assert 'API key created' in result.output
        
        # 3. 扫描项目
        result = cli_runner.invoke(cli, [
            'project', 'scan',
            '--path', project_dir,
            '--name', 'CLI Test Project',
            '--username', 'testuser'
        ])
        assert result.exit_code == 0
        assert 'Project scanned successfully' in result.output
        assert 'video files found' in result.output
        
        # 4. 列出项目
        result = cli_runner.invoke(cli, [
            'project', 'list',
            '--username', 'testuser'
        ])
        assert result.exit_code == 0
        assert 'CLI Test Project' in result.output
        
        # 5. 创建发布任务
        result = cli_runner.invoke(cli, [
            'task', 'create',
            '--project-name', 'CLI Test Project',
            '--content', 'Test tweet from CLI',
            '--schedule', (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
            '--username', 'testuser'
        ])
        assert result.exit_code == 0
        assert 'Task created successfully' in result.output
        
        # 6. 列出任务
        result = cli_runner.invoke(cli, [
            'task', 'list',
            '--username', 'testuser'
        ])
        assert result.exit_code == 0
        assert 'Test tweet from CLI' in result.output
        
        # 7. 运行调度器
        result = cli_runner.invoke(cli, [
            'scheduler', 'run',
            '--once',
            '--username', 'testuser'
        ])
        assert result.exit_code == 0
        assert 'Scheduler executed' in result.output
        
        # 8. 检查任务状态
        result = cli_runner.invoke(cli, [
            'task', 'status',
            '--username', 'testuser'
        ])
        assert result.exit_code == 0
        # 任务应该已经被处理
    
    @pytest.mark.e2e
    @pytest.mark.cli
    def test_database_maintenance_workflow(self, cli_runner, temp_project_structure, db_session):
        """测试数据库维护工作流程"""
        project_dir = temp_project_structure['project_dir']
        
        # 1. 创建用户和项目数据
        result = cli_runner.invoke(cli, [
            'user', 'create',
            '--username', 'maintenanceuser',
            '--email', 'maintenance@example.com',
            '--password', 'password123'
        ])
        assert result.exit_code == 0
        
        result = cli_runner.invoke(cli, [
            'project', 'scan',
            '--path', project_dir,
            '--name', 'Maintenance Test Project',
            '--username', 'maintenanceuser'
        ])
        assert result.exit_code == 0
        
        # 2. 检查数据库状态
        result = cli_runner.invoke(cli, ['db', 'status'])
        assert result.exit_code == 0
        assert 'Database status' in result.output
        
        # 3. 备份数据库
        with tempfile.NamedTemporaryFile(suffix='.sql', delete=False) as backup_file:
            backup_path = backup_file.name
        
        try:
            result = cli_runner.invoke(cli, [
                'db', 'backup',
                '--output', backup_path
            ])
            assert result.exit_code == 0
            assert 'Database backed up' in result.output
            assert os.path.exists(backup_path)
            assert os.path.getsize(backup_path) > 0
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)
        
        # 4. 清理旧数据
        result = cli_runner.invoke(cli, [
            'db', 'cleanup',
            '--days', '30',
            '--dry-run'
        ])
        assert result.exit_code == 0
        assert 'Would clean up' in result.output or 'No old data found' in result.output
        
        # 5. 验证数据库完整性
        result = cli_runner.invoke(cli, ['db', 'verify'])
        assert result.exit_code == 0
        assert 'Database verification' in result.output
        
        # 6. 优化数据库
        result = cli_runner.invoke(cli, ['db', 'optimize'])
        assert result.exit_code == 0
        assert 'Database optimized' in result.output
    
    @pytest.mark.e2e
    @pytest.mark.cli
    def test_project_management_workflow(self, cli_runner, temp_project_structure, db_session):
        """测试项目管理工作流程"""
        project_dir = temp_project_structure['project_dir']
        
        # 1. 创建用户
        result = cli_runner.invoke(cli, [
            'user', 'create',
            '--username', 'projectuser',
            '--email', 'project@example.com',
            '--password', 'password123'
        ])
        assert result.exit_code == 0
        
        # 2. 扫描项目
        result = cli_runner.invoke(cli, [
            'project', 'scan',
            '--path', project_dir,
            '--name', 'Project Management Test',
            '--username', 'projectuser',
            '--description', 'A test project for management workflow'
        ])
        assert result.exit_code == 0
        
        # 3. 获取项目详情
        result = cli_runner.invoke(cli, [
            'project', 'info',
            '--name', 'Project Management Test',
            '--username', 'projectuser'
        ])
        assert result.exit_code == 0
        assert 'Project Management Test' in result.output
        assert 'A test project for management workflow' in result.output
        
        # 4. 更新项目
        result = cli_runner.invoke(cli, [
            'project', 'update',
            '--name', 'Project Management Test',
            '--description', 'Updated project description',
            '--username', 'projectuser'
        ])
        assert result.exit_code == 0
        assert 'Project updated' in result.output
        
        # 5. 重新扫描项目
        # 添加新文件
        new_video = Path(project_dir) / "new_video.mp4"
        new_video.write_bytes(b"new fake video content" * 500)
        
        result = cli_runner.invoke(cli, [
            'project', 'rescan',
            '--name', 'Project Management Test',
            '--username', 'projectuser'
        ])
        assert result.exit_code == 0
        assert 'Project rescanned' in result.output
        
        # 6. 列出内容源
        result = cli_runner.invoke(cli, [
            'project', 'content',
            '--name', 'Project Management Test',
            '--username', 'projectuser'
        ])
        assert result.exit_code == 0
        assert 'new_video.mp4' in result.output
        
        # 7. 导出项目数据
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as export_file:
            export_path = export_file.name
        
        try:
            result = cli_runner.invoke(cli, [
                'project', 'export',
                '--name', 'Project Management Test',
                '--output', export_path,
                '--username', 'projectuser'
            ])
            assert result.exit_code == 0
            assert 'Project exported' in result.output
            
            # 验证导出文件
            assert os.path.exists(export_path)
            with open(export_path, 'r') as f:
                export_data = json.load(f)
                assert export_data['name'] == 'Project Management Test'
                assert 'content_sources' in export_data
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)
        
        # 8. 停用项目
        result = cli_runner.invoke(cli, [
            'project', 'deactivate',
            '--name', 'Project Management Test',
            '--username', 'projectuser'
        ])
        assert result.exit_code == 0
        assert 'Project deactivated' in result.output
        
        # 9. 激活项目
        result = cli_runner.invoke(cli, [
            'project', 'activate',
            '--name', 'Project Management Test',
            '--username', 'projectuser'
        ])
        assert result.exit_code == 0
        assert 'Project activated' in result.output
    
    @pytest.mark.e2e
    @pytest.mark.cli
    def test_task_management_workflow(self, cli_runner, temp_project_structure, mock_external_services, db_session):
        """测试任务管理工作流程"""
        project_dir = temp_project_structure['project_dir']
        
        # 1. 设置用户和项目
        result = cli_runner.invoke(cli, [
            'user', 'create',
            '--username', 'taskuser',
            '--email', 'task@example.com',
            '--password', 'password123'
        ])
        assert result.exit_code == 0
        
        result = cli_runner.invoke(cli, [
            'project', 'scan',
            '--path', project_dir,
            '--name', 'Task Management Test',
            '--username', 'taskuser'
        ])
        assert result.exit_code == 0
        
        # 2. 创建多个任务
        for i in range(3):
            schedule_time = datetime.utcnow() + timedelta(hours=i+1)
            result = cli_runner.invoke(cli, [
                'task', 'create',
                '--project-name', 'Task Management Test',
                '--content', f'Task {i+1} content',
                '--schedule', schedule_time.isoformat(),
                '--priority', str(i+1),
                '--username', 'taskuser'
            ])
            assert result.exit_code == 0
        
        # 3. 列出所有任务
        result = cli_runner.invoke(cli, [
            'task', 'list',
            '--username', 'taskuser'
        ])
        assert result.exit_code == 0
        assert 'Task 1 content' in result.output
        assert 'Task 2 content' in result.output
        assert 'Task 3 content' in result.output
        
        # 4. 按状态筛选任务
        result = cli_runner.invoke(cli, [
            'task', 'list',
            '--status', 'pending',
            '--username', 'taskuser'
        ])
        assert result.exit_code == 0
        
        # 5. 更新任务
        result = cli_runner.invoke(cli, [
            'task', 'update',
            '--content', 'Task 1 content',  # 用于识别任务
            '--new-content', 'Updated task 1 content',
            '--priority', '1',
            '--username', 'taskuser'
        ])
        assert result.exit_code == 0
        assert 'Task updated' in result.output
        
        # 6. 手动执行任务
        result = cli_runner.invoke(cli, [
            'task', 'execute',
            '--content', 'Updated task 1 content',
            '--username', 'taskuser'
        ])
        assert result.exit_code == 0
        assert 'Task executed' in result.output
        
        # 7. 查看任务日志
        result = cli_runner.invoke(cli, [
            'task', 'logs',
            '--username', 'taskuser',
            '--limit', '10'
        ])
        assert result.exit_code == 0
        
        # 8. 批量操作任务
        result = cli_runner.invoke(cli, [
            'task', 'batch-update',
            '--status', 'pending',
            '--new-priority', '2',
            '--username', 'taskuser'
        ])
        assert result.exit_code == 0
        
        # 9. 删除任务
        result = cli_runner.invoke(cli, [
            'task', 'delete',
            '--content', 'Task 3 content',
            '--username', 'taskuser',
            '--confirm'
        ])
        assert result.exit_code == 0
        assert 'Task deleted' in result.output
    
    @pytest.mark.e2e
    @pytest.mark.cli
    def test_configuration_management_workflow(self, cli_runner, temp_project_structure):
        """测试配置管理工作流程"""
        config_file = temp_project_structure['config_file']
        
        # 1. 验证配置文件
        result = cli_runner.invoke(cli, [
            'config', 'validate',
            '--file', config_file
        ])
        assert result.exit_code == 0
        assert 'Configuration is valid' in result.output
        
        # 2. 显示配置
        result = cli_runner.invoke(cli, [
            'config', 'show',
            '--file', config_file
        ])
        assert result.exit_code == 0
        assert 'twitter' in result.output
        assert 'ai' in result.output
        
        # 3. 更新配置
        result = cli_runner.invoke(cli, [
            'config', 'set',
            '--file', config_file,
            '--key', 'publishing.schedule_interval',
            '--value', '7200'
        ])
        assert result.exit_code == 0
        assert 'Configuration updated' in result.output
        
        # 4. 获取配置值
        result = cli_runner.invoke(cli, [
            'config', 'get',
            '--file', config_file,
            '--key', 'publishing.schedule_interval'
        ])
        assert result.exit_code == 0
        assert '7200' in result.output
        
        # 5. 测试Twitter连接
        with patch('app.core.publisher.TwitterPublisher') as mock_publisher:
            mock_publisher_instance = Mock()
            mock_publisher_instance.verify_credentials.return_value = True
            mock_publisher.return_value = mock_publisher_instance
            
            result = cli_runner.invoke(cli, [
                'config', 'test-twitter',
                '--file', config_file
            ])
            assert result.exit_code == 0
            assert 'Twitter connection successful' in result.output
        
        # 6. 测试AI连接
        with patch('google.generativeai.GenerativeModel') as mock_ai:
            mock_ai_instance = Mock()
            mock_ai_instance.generate_content.return_value = Mock(
                text='Test AI response'
            )
            mock_ai.return_value = mock_ai_instance
            
            result = cli_runner.invoke(cli, [
                'config', 'test-ai',
                '--file', config_file
            ])
            assert result.exit_code == 0
            assert 'AI connection successful' in result.output
    
    @pytest.mark.e2e
    @pytest.mark.cli
    def test_analytics_and_reporting_workflow(self, cli_runner, temp_project_structure, mock_external_services, db_session):
        """测试分析和报告工作流程"""
        project_dir = temp_project_structure['project_dir']
        
        # 1. 设置用户和数据
        result = cli_runner.invoke(cli, [
            'user', 'create',
            '--username', 'analyticsuser',
            '--email', 'analytics@example.com',
            '--password', 'password123'
        ])
        assert result.exit_code == 0
        
        result = cli_runner.invoke(cli, [
            'project', 'scan',
            '--path', project_dir,
            '--name', 'Analytics Test Project',
            '--username', 'analyticsuser'
        ])
        assert result.exit_code == 0
        
        # 2. 创建和执行一些任务以生成数据
        result = cli_runner.invoke(cli, [
            'task', 'create',
            '--project-name', 'Analytics Test Project',
            '--content', 'Analytics test tweet',
            '--schedule', (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
            '--username', 'analyticsuser'
        ])
        assert result.exit_code == 0
        
        result = cli_runner.invoke(cli, [
            'scheduler', 'run',
            '--once',
            '--username', 'analyticsuser'
        ])
        assert result.exit_code == 0
        
        # 3. 生成用户报告
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as report_file:
            report_path = report_file.name
        
        try:
            result = cli_runner.invoke(cli, [
                'analytics', 'report',
                '--username', 'analyticsuser',
                '--output', report_path,
                '--format', 'json'
            ])
            assert result.exit_code == 0
            assert 'Report generated' in result.output
            
            # 验证报告文件
            assert os.path.exists(report_path)
            with open(report_path, 'r') as f:
                report_data = json.load(f)
                assert 'user' in report_data
                assert 'projects' in report_data
                assert 'tasks' in report_data
                assert 'analytics' in report_data
        finally:
            if os.path.exists(report_path):
                os.unlink(report_path)
        
        # 4. 显示统计信息
        result = cli_runner.invoke(cli, [
            'analytics', 'stats',
            '--username', 'analyticsuser',
            '--period', 'week'
        ])
        assert result.exit_code == 0
        assert 'Statistics' in result.output
        
        # 5. 显示性能指标
        result = cli_runner.invoke(cli, [
            'analytics', 'performance',
            '--username', 'analyticsuser'
        ])
        assert result.exit_code == 0
        assert 'Performance metrics' in result.output
    
    @pytest.mark.e2e
    @pytest.mark.cli
    def test_error_handling_and_recovery_workflow(self, cli_runner, temp_project_structure):
        """测试错误处理和恢复工作流程"""
        
        # 1. 测试无效用户操作
        result = cli_runner.invoke(cli, [
            'project', 'list',
            '--username', 'nonexistentuser'
        ])
        assert result.exit_code != 0
        assert 'User not found' in result.output or 'error' in result.output.lower()
        
        # 2. 测试无效项目路径
        result = cli_runner.invoke(cli, [
            'user', 'create',
            '--username', 'erroruser',
            '--email', 'error@example.com',
            '--password', 'password123'
        ])
        assert result.exit_code == 0
        
        result = cli_runner.invoke(cli, [
            'project', 'scan',
            '--path', '/nonexistent/path',
            '--name', 'Invalid Project',
            '--username', 'erroruser'
        ])
        assert result.exit_code != 0
        assert 'not found' in result.output or 'error' in result.output.lower()
        
        # 3. 测试重复用户创建
        result = cli_runner.invoke(cli, [
            'user', 'create',
            '--username', 'erroruser',  # 重复用户名
            '--email', 'error2@example.com',
            '--password', 'password123'
        ])
        assert result.exit_code != 0
        assert 'already exists' in result.output or 'error' in result.output.lower()
        
        # 4. 测试无效配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as invalid_config:
            invalid_config.write('{"invalid": json}')  # 无效JSON
            invalid_config_path = invalid_config.name
        
        try:
            result = cli_runner.invoke(cli, [
                'config', 'validate',
                '--file', invalid_config_path
            ])
            assert result.exit_code != 0
            assert 'invalid' in result.output.lower() or 'error' in result.output.lower()
        finally:
            os.unlink(invalid_config_path)
        
        # 5. 测试数据库连接错误恢复
        with patch('app.database.connection.get_db_session') as mock_db:
            mock_db.side_effect = Exception("Database connection failed")
            
            result = cli_runner.invoke(cli, [
                'project', 'list',
                '--username', 'erroruser'
            ])
            assert result.exit_code != 0
            assert 'database' in result.output.lower() or 'connection' in result.output.lower()
        
        # 6. 测试帮助和版本信息
        result = cli_runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'Usage:' in result.output
        
        result = cli_runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
    
    @pytest.mark.e2e
    @pytest.mark.cli
    @pytest.mark.slow
    def test_performance_and_scalability_workflow(self, cli_runner, tmp_path, db_session):
        """测试性能和可扩展性工作流程"""
        
        # 创建大型项目结构
        large_project_dir = tmp_path / "large_project"
        large_project_dir.mkdir()
        
        # 创建多个视频文件
        video_files = []
        for i in range(20):  # 创建20个视频文件
            video_file = large_project_dir / f"video_{i:03d}.mp4"
            video_file.write_bytes(b"fake video content" * (100 + i * 10))
            video_files.append(video_file)
        
        # 创建元数据
        metadata = {
            "title": "Large Project Test",
            "description": "A large project for performance testing",
            "tags": ["performance", "test", "large"]
        }
        metadata_file = large_project_dir / "metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))
        
        # 1. 创建用户
        result = cli_runner.invoke(cli, [
            'user', 'create',
            '--username', 'perfuser',
            '--email', 'perf@example.com',
            '--password', 'password123'
        ])
        assert result.exit_code == 0
        
        # 2. 测试大项目扫描性能
        import time
        start_time = time.time()
        
        result = cli_runner.invoke(cli, [
            'project', 'scan',
            '--path', str(large_project_dir),
            '--name', 'Large Performance Test',
            '--username', 'perfuser'
        ])
        
        scan_time = time.time() - start_time
        
        assert result.exit_code == 0
        assert 'Project scanned successfully' in result.output
        assert scan_time < 30.0, f"Project scan took too long: {scan_time}s"
        
        # 3. 测试批量任务创建
        start_time = time.time()
        
        for i in range(10):
            schedule_time = datetime.utcnow() + timedelta(minutes=i*5)
            result = cli_runner.invoke(cli, [
                'task', 'create',
                '--project-name', 'Large Performance Test',
                '--content', f'Performance test task {i}',
                '--schedule', schedule_time.isoformat(),
                '--username', 'perfuser'
            ])
            assert result.exit_code == 0
        
        task_creation_time = time.time() - start_time
        assert task_creation_time < 15.0, f"Task creation took too long: {task_creation_time}s"
        
        # 4. 测试大量数据列表性能
        start_time = time.time()
        
        result = cli_runner.invoke(cli, [
            'task', 'list',
            '--username', 'perfuser'
        ])
        
        list_time = time.time() - start_time
        
        assert result.exit_code == 0
        assert list_time < 5.0, f"Task listing took too long: {list_time}s"
        
        print(f"Performance test results:")
        print(f"  Project scan (20 files): {scan_time:.2f}s")
        print(f"  Task creation (10 tasks): {task_creation_time:.2f}s")
        print(f"  Task listing: {list_time:.2f}s")