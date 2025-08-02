import pytest
import asyncio
import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient

from api.main import app
from app.database.models import User, Project, ContentSource, PublishingTask, PublishingLog
from api.schemas import TaskStatusEnum
from app.core.project_manager import ProjectManager
from app.core.task_scheduler import TaskScheduler
from app.core.content_generator import ContentGenerator
from app.core.publisher import TwitterPublisher


class TestCompleteSystemIntegration:
    """完整系统集成端到端测试类"""
    
    @pytest.fixture
    def api_client(self):
        """创建API测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def system_project_structure(self, tmp_path):
        """创建系统测试项目结构"""
        # 创建多个项目目录
        projects = {}
        
        for i in range(3):
            project_name = f"system_project_{i+1}"
            project_dir = tmp_path / project_name
            project_dir.mkdir()
            
            # 创建视频文件
            videos = []
            for j in range(5):
                video_file = project_dir / f"video_{j+1}.mp4"
                video_file.write_bytes(b"fake video content" * (100 + j * 20))
                videos.append(str(video_file))
            
            # 创建元数据文件
            metadata = {
                "title": f"System Test Project {i+1}",
                "description": f"Description for project {i+1}",
                "tags": [f"tag{i+1}", "system", "test"],
                "author": f"Author {i+1}",
                "language": "en" if i % 2 == 0 else "zh"
            }
            
            metadata_file = project_dir / "metadata.json"
            metadata_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
            
            projects[project_name] = {
                'dir': str(project_dir),
                'videos': videos,
                'metadata': str(metadata_file),
                'metadata_content': metadata
            }
        
        return projects
    
    @pytest.fixture
    def mock_all_external_services(self):
        """模拟所有外部服务"""
        with patch('app.core.publisher.TwitterPublisher') as mock_publisher, \
             patch('app.core.content_generator.ContentGenerator') as mock_generator, \
             patch('tweepy.Client') as mock_tweepy, \
             patch('google.generativeai.GenerativeModel') as mock_gemini:
            
            # 配置Twitter发布器
            mock_publisher_instance = Mock()
            mock_publisher_instance.verify_credentials.return_value = True
            mock_publisher_instance.publish_tweet.return_value = {
                'id': f'tweet_{int(time.time())}',
                'text': 'Published tweet content',
                'created_at': datetime.utcnow().isoformat(),
                'metrics': {
                    'retweet_count': 5,
                    'like_count': 15,
                    'reply_count': 2
                }
            }
            mock_publisher_instance.upload_media.return_value = {
                'media_id': f'media_{int(time.time())}',
                'size': 1024000,
                'processing_info': {'state': 'succeeded'}
            }
            mock_publisher.return_value = mock_publisher_instance
            
            # 配置内容生成器
            mock_generator_instance = Mock()
            mock_generator_instance.generate_content.return_value = {
                'text': 'AI-enhanced tweet content with #hashtags and emojis 🚀',
                'hashtags': ['#ai', '#test', '#automation'],
                'media_paths': [],
                'language': 'en',
                'sentiment': 'positive'
            }
            mock_generator.return_value = mock_generator_instance
            
            # 配置Tweepy
            mock_tweepy_instance = Mock()
            mock_tweepy_instance.get_me.return_value = Mock(
                id='123456789',
                username='testuser',
                name='Test User',
                followers_count=1000,
                following_count=500
            )
            mock_tweepy.return_value = mock_tweepy_instance
            
            # 配置Gemini AI
            mock_gemini_instance = Mock()
            mock_response = Mock()
            mock_response.text = 'Enhanced content with AI improvements'
            mock_gemini_instance.generate_content.return_value = mock_response
            mock_gemini.return_value = mock_gemini_instance
            
            yield {
                'publisher': mock_publisher_instance,
                'generator': mock_generator_instance,
                'tweepy': mock_tweepy_instance,
                'gemini': mock_gemini_instance
            }
    
    @pytest.mark.e2e
    @pytest.mark.system
    def test_complete_user_journey(self, api_client, system_project_structure, mock_all_external_services, db_session):
        """测试完整的用户使用流程"""
        
        # 1. 用户注册
        user_data = {
            "username": "systemuser",
            "email": "system@example.com",
            "password": "securepassword123"
        }
        
        response = api_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        user_info = response.json()
        assert user_info["username"] == "systemuser"
        
        # 2. 用户登录
        login_data = {
            "username": "systemuser",
            "password": "securepassword123"
        }
        
        response = api_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        auth_info = response.json()
        api_key = auth_info["api_key"]
        
        headers = {"X-API-Key": api_key}
        
        # 3. 创建多个项目
        project_ids = []
        for project_name, project_info in system_project_structure.items():
            project_data = {
                "name": project_info['metadata_content']['title'],
                "description": project_info['metadata_content']['description'],
                "path": project_info['dir'],
                "language": project_info['metadata_content']['language']
            }
            
            response = api_client.post("/api/v1/projects", json=project_data, headers=headers)
            assert response.status_code == 201
            project = response.json()
            project_ids.append(project["id"])
        
        # 4. 验证项目列表
        response = api_client.get("/api/v1/projects", headers=headers)
        assert response.status_code == 200
        projects = response.json()
        assert len(projects["items"]) == 3
        
        # 5. 扫描项目内容
        for project_id in project_ids:
            response = api_client.post(f"/api/v1/projects/{project_id}/scan", headers=headers)
            assert response.status_code == 200
            scan_result = response.json()
            assert scan_result["files_found"] > 0
        
        # 6. 获取内容源
        all_content_sources = []
        for project_id in project_ids:
            response = api_client.get(f"/api/v1/projects/{project_id}/content-sources", headers=headers)
            assert response.status_code == 200
            content_sources = response.json()
            all_content_sources.extend(content_sources["items"])
        
        assert len(all_content_sources) >= 15  # 3 projects * 5 videos each
        
        # 7. 创建发布任务
        task_ids = []
        for i, content_source in enumerate(all_content_sources[:10]):  # 只为前10个创建任务
            task_data = {
                "content_source_id": content_source["id"],
                "content": f"Test tweet for content {i+1}",
                "scheduled_time": (datetime.utcnow() + timedelta(minutes=i*10)).isoformat(),
                "priority": (i % 3) + 1,
                "enable_ai_enhancement": i % 2 == 0
            }
            
            response = api_client.post("/api/v1/tasks", json=task_data, headers=headers)
            assert response.status_code == 201
            task = response.json()
            task_ids.append(task["id"])
        
        # 8. 验证任务列表
        response = api_client.get("/api/v1/tasks", headers=headers)
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks["items"]) == 10
        
        # 9. 执行一些任务
        executed_tasks = 0
        for task_id in task_ids[:5]:  # 执行前5个任务
            response = api_client.post(f"/api/v1/tasks/{task_id}/execute", headers=headers)
            if response.status_code == 200:
                executed_tasks += 1
        
        assert executed_tasks > 0
        
        # 10. 检查任务日志
        response = api_client.get("/api/v1/tasks/logs", headers=headers)
        assert response.status_code == 200
        logs = response.json()
        assert len(logs["items"]) >= executed_tasks
        
        # 11. 获取分析数据
        response = api_client.get("/api/v1/dashboard/overview", headers=headers)
        assert response.status_code == 200
        overview = response.json()
        assert overview["total_projects"] == 3
        assert overview["total_tasks"] == 10
        
        # 12. 获取性能指标
        response = api_client.get("/api/v1/dashboard/performance", headers=headers)
        assert response.status_code == 200
        performance = response.json()
        assert "success_rate" in performance
        assert "average_execution_time" in performance
        
        # 13. 更新项目状态
        for project_id in project_ids[:2]:  # 停用前两个项目
            update_data = {"status": "inactive"}
            response = api_client.patch(f"/api/v1/projects/{project_id}", json=update_data, headers=headers)
            assert response.status_code == 200
        
        # 14. 验证项目状态更新
        response = api_client.get("/api/v1/projects", headers=headers)
        assert response.status_code == 200
        projects = response.json()
        inactive_count = sum(1 for p in projects["items"] if p["status"] == "inactive")
        assert inactive_count == 2
        
        # 15. 清理 - 删除一些任务
        for task_id in task_ids[-3:]:  # 删除最后3个任务
            response = api_client.delete(f"/api/v1/tasks/{task_id}", headers=headers)
            assert response.status_code == 204
        
        # 16. 验证最终状态
        response = api_client.get("/api/v1/tasks", headers=headers)
        assert response.status_code == 200
        final_tasks = response.json()
        assert len(final_tasks["items"]) == 7  # 10 - 3 deleted
    
    @pytest.mark.e2e
    @pytest.mark.system
    def test_concurrent_operations(self, api_client, system_project_structure, mock_all_external_services, db_session):
        """测试并发操作"""
        
        # 设置用户
        user_data = {
            "username": "concurrentuser",
            "email": "concurrent@example.com",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        
        login_data = {
            "username": "concurrentuser",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        api_key = response.json()["api_key"]
        headers = {"X-API-Key": api_key}
        
        # 创建项目
        project_info = list(system_project_structure.values())[0]
        project_data = {
            "name": "Concurrent Test Project",
            "description": "Project for concurrent testing",
            "path": project_info['dir']
        }
        
        response = api_client.post("/api/v1/projects", json=project_data, headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]
        
        # 扫描项目
        response = api_client.post(f"/api/v1/projects/{project_id}/scan", headers=headers)
        assert response.status_code == 200
        
        # 获取内容源
        response = api_client.get(f"/api/v1/projects/{project_id}/content-sources", headers=headers)
        assert response.status_code == 200
        content_sources = response.json()["items"]
        
        # 并发创建任务
        def create_task(index):
            task_data = {
                "content_source_id": content_sources[index % len(content_sources)]["id"],
                "content": f"Concurrent task {index}",
                "scheduled_time": (datetime.utcnow() + timedelta(minutes=index)).isoformat(),
                "priority": (index % 3) + 1
            }
            
            response = api_client.post("/api/v1/tasks", json=task_data, headers=headers)
            return response.status_code == 201
        
        # 使用线程池并发创建任务
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_task, i) for i in range(20)]
            results = [future.result() for future in as_completed(futures)]
        
        successful_creations = sum(results)
        assert successful_creations >= 15  # 至少75%成功
        
        # 验证任务数量
        response = api_client.get("/api/v1/tasks", headers=headers)
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks["items"]) == successful_creations
        
        # 并发执行任务
        task_ids = [task["id"] for task in tasks["items"][:10]]
        
        def execute_task(task_id):
            response = api_client.post(f"/api/v1/tasks/{task_id}/execute", headers=headers)
            return response.status_code == 200
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(execute_task, task_id) for task_id in task_ids]
            execution_results = [future.result() for future in as_completed(futures)]
        
        successful_executions = sum(execution_results)
        assert successful_executions >= 5  # 至少50%成功
    
    @pytest.mark.e2e
    @pytest.mark.system
    def test_error_recovery_and_resilience(self, api_client, system_project_structure, db_session):
        """测试错误恢复和系统弹性"""
        
        # 设置用户
        user_data = {
            "username": "resilienceuser",
            "email": "resilience@example.com",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        
        login_data = {
            "username": "resilienceuser",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        api_key = response.json()["api_key"]
        headers = {"X-API-Key": api_key}
        
        # 1. 测试无效项目路径的处理
        invalid_project_data = {
            "name": "Invalid Project",
            "description": "This project has an invalid path",
            "path": "/nonexistent/path/to/project"
        }
        
        response = api_client.post("/api/v1/projects", json=invalid_project_data, headers=headers)
        assert response.status_code == 400  # 应该返回错误
        
        # 2. 创建有效项目
        project_info = list(system_project_structure.values())[0]
        valid_project_data = {
            "name": "Resilience Test Project",
            "description": "Project for resilience testing",
            "path": project_info['dir']
        }
        
        response = api_client.post("/api/v1/projects", json=valid_project_data, headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]
        
        # 3. 测试外部服务失败的处理
        with patch('app.core.publisher.TwitterPublisher') as mock_publisher:
            # 模拟Twitter API失败
            mock_publisher_instance = Mock()
            mock_publisher_instance.verify_credentials.side_effect = Exception("Twitter API Error")
            mock_publisher.return_value = mock_publisher_instance
            
            # 扫描项目应该仍然成功
            response = api_client.post(f"/api/v1/projects/{project_id}/scan", headers=headers)
            assert response.status_code == 200
        
        # 4. 获取内容源
        response = api_client.get(f"/api/v1/projects/{project_id}/content-sources", headers=headers)
        assert response.status_code == 200
        content_sources = response.json()["items"]
        
        # 5. 创建任务
        task_data = {
            "content_source_id": content_sources[0]["id"],
            "content": "Resilience test task",
            "scheduled_time": datetime.utcnow().isoformat(),
            "priority": 1
        }
        
        response = api_client.post("/api/v1/tasks", json=task_data, headers=headers)
        assert response.status_code == 201
        task_id = response.json()["id"]
        
        # 6. 测试任务执行失败的处理
        with patch('app.core.publisher.TwitterPublisher') as mock_publisher:
            # 模拟发布失败
            mock_publisher_instance = Mock()
            mock_publisher_instance.verify_credentials.return_value = True
            mock_publisher_instance.publish_tweet.side_effect = Exception("Publishing failed")
            mock_publisher.return_value = mock_publisher_instance
            
            response = api_client.post(f"/api/v1/tasks/{task_id}/execute", headers=headers)
            # 任务执行应该返回成功，但内部会记录失败
            assert response.status_code == 200
        
        # 7. 检查任务状态和日志
        response = api_client.get(f"/api/v1/tasks/{task_id}", headers=headers)
        assert response.status_code == 200
        task = response.json()
        # 任务状态应该反映失败
        assert task["status"] in ["failed", "pending"]  # 可能会重试
        
        # 8. 测试数据库事务回滚
        with patch('app.database.repositories.PublishingTaskRepository.update_status') as mock_update:
            # 模拟数据库更新失败
            mock_update.side_effect = Exception("Database error")
            
            # 创建另一个任务
            task_data_2 = {
                "content_source_id": content_sources[0]["id"],
                "content": "Another test task",
                "scheduled_time": datetime.utcnow().isoformat(),
                "priority": 1
            }
            
            response = api_client.post("/api/v1/tasks", json=task_data_2, headers=headers)
            # 即使数据库操作失败，API也应该优雅处理
            # 可能返回500错误，但不应该崩溃
            assert response.status_code in [201, 500]
        
        # 9. 验证系统仍然可用
        response = api_client.get("/api/v1/projects", headers=headers)
        assert response.status_code == 200
        
        response = api_client.get("/api/v1/tasks", headers=headers)
        assert response.status_code == 200
    
    @pytest.mark.e2e
    @pytest.mark.system
    @pytest.mark.slow
    def test_performance_under_load(self, api_client, system_project_structure, mock_all_external_services, db_session):
        """测试负载下的系统性能"""
        
        # 设置用户
        user_data = {
            "username": "loaduser",
            "email": "load@example.com",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        
        login_data = {
            "username": "loaduser",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        api_key = response.json()["api_key"]
        headers = {"X-API-Key": api_key}
        
        # 创建多个项目
        project_ids = []
        for i, (project_name, project_info) in enumerate(system_project_structure.items()):
            project_data = {
                "name": f"Load Test Project {i+1}",
                "description": f"Load testing project {i+1}",
                "path": project_info['dir']
            }
            
            start_time = time.time()
            response = api_client.post("/api/v1/projects", json=project_data, headers=headers)
            creation_time = time.time() - start_time
            
            assert response.status_code == 201
            assert creation_time < 2.0, f"Project creation took too long: {creation_time}s"
            
            project_ids.append(response.json()["id"])
        
        # 扫描所有项目
        scan_times = []
        for project_id in project_ids:
            start_time = time.time()
            response = api_client.post(f"/api/v1/projects/{project_id}/scan", headers=headers)
            scan_time = time.time() - start_time
            scan_times.append(scan_time)
            
            assert response.status_code == 200
            assert scan_time < 5.0, f"Project scan took too long: {scan_time}s"
        
        # 获取所有内容源
        all_content_sources = []
        for project_id in project_ids:
            start_time = time.time()
            response = api_client.get(f"/api/v1/projects/{project_id}/content-sources", headers=headers)
            fetch_time = time.time() - start_time
            
            assert response.status_code == 200
            assert fetch_time < 1.0, f"Content source fetch took too long: {fetch_time}s"
            
            content_sources = response.json()["items"]
            all_content_sources.extend(content_sources)
        
        # 批量创建任务
        task_creation_times = []
        for i in range(50):  # 创建50个任务
            content_source = all_content_sources[i % len(all_content_sources)]
            task_data = {
                "content_source_id": content_source["id"],
                "content": f"Load test task {i+1}",
                "scheduled_time": (datetime.utcnow() + timedelta(minutes=i)).isoformat(),
                "priority": (i % 3) + 1
            }
            
            start_time = time.time()
            response = api_client.post("/api/v1/tasks", json=task_data, headers=headers)
            creation_time = time.time() - start_time
            task_creation_times.append(creation_time)
            
            assert response.status_code == 201
            assert creation_time < 1.0, f"Task creation took too long: {creation_time}s"
        
        # 测试列表性能
        start_time = time.time()
        response = api_client.get("/api/v1/tasks?limit=100", headers=headers)
        list_time = time.time() - start_time
        
        assert response.status_code == 200
        assert list_time < 2.0, f"Task listing took too long: {list_time}s"
        
        tasks = response.json()["items"]
        assert len(tasks) == 50
        
        # 测试分页性能
        start_time = time.time()
        response = api_client.get("/api/v1/tasks?limit=10&offset=20", headers=headers)
        pagination_time = time.time() - start_time
        
        assert response.status_code == 200
        assert pagination_time < 1.0, f"Pagination took too long: {pagination_time}s"
        
        # 测试搜索性能
        start_time = time.time()
        response = api_client.get("/api/v1/tasks?status=pending", headers=headers)
        search_time = time.time() - start_time
        
        assert response.status_code == 200
        assert search_time < 1.5, f"Search took too long: {search_time}s"
        
        # 输出性能统计
        print(f"\nPerformance test results:")
        print(f"  Average project scan time: {sum(scan_times)/len(scan_times):.3f}s")
        print(f"  Average task creation time: {sum(task_creation_times)/len(task_creation_times):.3f}s")
        print(f"  Task listing time (50 items): {list_time:.3f}s")
        print(f"  Pagination time: {pagination_time:.3f}s")
        print(f"  Search time: {search_time:.3f}s")
    
    @pytest.mark.e2e
    @pytest.mark.system
    def test_data_consistency_and_integrity(self, api_client, system_project_structure, mock_all_external_services, db_session):
        """测试数据一致性和完整性"""
        
        # 设置用户
        user_data = {
            "username": "consistencyuser",
            "email": "consistency@example.com",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        
        login_data = {
            "username": "consistencyuser",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        api_key = response.json()["api_key"]
        headers = {"X-API-Key": api_key}
        
        # 创建项目
        project_info = list(system_project_structure.values())[0]
        project_data = {
            "name": "Consistency Test Project",
            "description": "Project for consistency testing",
            "path": project_info['dir']
        }
        
        response = api_client.post("/api/v1/projects", json=project_data, headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]
        
        # 扫描项目
        response = api_client.post(f"/api/v1/projects/{project_id}/scan", headers=headers)
        assert response.status_code == 200
        scan_result = response.json()
        files_found = scan_result["files_found"]
        
        # 验证内容源数量与扫描结果一致
        response = api_client.get(f"/api/v1/projects/{project_id}/content-sources", headers=headers)
        assert response.status_code == 200
        content_sources = response.json()["items"]
        assert len(content_sources) == files_found
        
        # 创建任务并验证关联关系
        task_data = {
            "content_source_id": content_sources[0]["id"],
            "content": "Consistency test task",
            "scheduled_time": datetime.utcnow().isoformat(),
            "priority": 1
        }
        
        response = api_client.post("/api/v1/tasks", json=task_data, headers=headers)
        assert response.status_code == 201
        task = response.json()
        task_id = task["id"]
        
        # 验证任务与内容源的关联
        assert task["content_source_id"] == content_sources[0]["id"]
        
        # 执行任务
        response = api_client.post(f"/api/v1/tasks/{task_id}/execute", headers=headers)
        assert response.status_code == 200
        
        # 验证任务状态更新
        response = api_client.get(f"/api/v1/tasks/{task_id}", headers=headers)
        assert response.status_code == 200
        updated_task = response.json()
        assert updated_task["status"] in ["completed", "failed"]
        
        # 验证日志记录
        response = api_client.get("/api/v1/tasks/logs", headers=headers)
        assert response.status_code == 200
        logs = response.json()["items"]
        
        # 应该有对应的日志记录
        task_logs = [log for log in logs if log["task_id"] == task_id]
        assert len(task_logs) > 0
        
        # 验证分析数据更新
        response = api_client.get("/api/v1/dashboard/overview", headers=headers)
        assert response.status_code == 200
        overview = response.json()
        assert overview["total_projects"] >= 1
        assert overview["total_tasks"] >= 1
        
        # 删除项目并验证级联删除
        response = api_client.delete(f"/api/v1/projects/{project_id}", headers=headers)
        assert response.status_code == 204
        
        # 验证相关数据被删除
        response = api_client.get(f"/api/v1/projects/{project_id}/content-sources", headers=headers)
        assert response.status_code == 404  # 项目不存在
        
        response = api_client.get(f"/api/v1/tasks/{task_id}", headers=headers)
        assert response.status_code == 404  # 任务应该被删除
        
        # 验证概览数据更新
        response = api_client.get("/api/v1/dashboard/overview", headers=headers)
        assert response.status_code == 200
        updated_overview = response.json()
        assert updated_overview["total_projects"] == 0
        assert updated_overview["total_tasks"] == 0
    
    @pytest.mark.e2e
    @pytest.mark.system
    def test_security_and_access_control(self, api_client, system_project_structure, db_session):
        """测试安全性和访问控制"""
        
        # 创建两个用户
        user1_data = {
            "username": "securityuser1",
            "email": "security1@example.com",
            "password": "password123"
        }
        
        user2_data = {
            "username": "securityuser2",
            "email": "security2@example.com",
            "password": "password123"
        }
        
        # 注册用户
        response = api_client.post("/api/v1/auth/register", json=user1_data)
        assert response.status_code == 201
        
        response = api_client.post("/api/v1/auth/register", json=user2_data)
        assert response.status_code == 201
        
        # 用户1登录
        login_data1 = {
            "username": "securityuser1",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/login", json=login_data1)
        assert response.status_code == 200
        api_key1 = response.json()["api_key"]
        headers1 = {"X-API-Key": api_key1}
        
        # 用户2登录
        login_data2 = {
            "username": "securityuser2",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/login", json=login_data2)
        assert response.status_code == 200
        api_key2 = response.json()["api_key"]
        headers2 = {"X-API-Key": api_key2}
        
        # 用户1创建项目
        project_info = list(system_project_structure.values())[0]
        project_data = {
            "name": "Security Test Project",
            "description": "Project for security testing",
            "path": project_info['dir']
        }
        
        response = api_client.post("/api/v1/projects", json=project_data, headers=headers1)
        assert response.status_code == 201
        project_id = response.json()["id"]
        
        # 用户2尝试访问用户1的项目（应该失败）
        response = api_client.get(f"/api/v1/projects/{project_id}", headers=headers2)
        assert response.status_code == 403  # 禁止访问
        
        # 用户2尝试列出项目（应该只看到自己的项目）
        response = api_client.get("/api/v1/projects", headers=headers2)
        assert response.status_code == 200
        projects = response.json()["items"]
        assert len(projects) == 0  # 用户2没有项目
        
        # 用户1可以访问自己的项目
        response = api_client.get(f"/api/v1/projects/{project_id}", headers=headers1)
        assert response.status_code == 200
        
        # 扫描项目并创建内容源
        response = api_client.post(f"/api/v1/projects/{project_id}/scan", headers=headers1)
        assert response.status_code == 200
        
        response = api_client.get(f"/api/v1/projects/{project_id}/content-sources", headers=headers1)
        assert response.status_code == 200
        content_sources = response.json()["items"]
        
        # 用户1创建任务
        task_data = {
            "content_source_id": content_sources[0]["id"],
            "content": "Security test task",
            "scheduled_time": datetime.utcnow().isoformat(),
            "priority": 1
        }
        
        response = api_client.post("/api/v1/tasks", json=task_data, headers=headers1)
        assert response.status_code == 201
        task_id = response.json()["id"]
        
        # 用户2尝试访问用户1的任务（应该失败）
        response = api_client.get(f"/api/v1/tasks/{task_id}", headers=headers2)
        assert response.status_code == 403  # 禁止访问
        
        # 用户2尝试执行用户1的任务（应该失败）
        response = api_client.post(f"/api/v1/tasks/{task_id}/execute", headers=headers2)
        assert response.status_code == 403  # 禁止访问
        
        # 测试无效API密钥
        invalid_headers = {"X-API-Key": "invalid_key"}
        response = api_client.get("/api/v1/projects", headers=invalid_headers)
        assert response.status_code == 401  # 未授权
        
        # 测试没有API密钥
        response = api_client.get("/api/v1/projects")
        assert response.status_code == 401  # 未授权
        
        # 测试SQL注入防护
        malicious_project_data = {
            "name": "'; DROP TABLE projects; --",
            "description": "Malicious project",
            "path": project_info['dir']
        }
        
        response = api_client.post("/api/v1/projects", json=malicious_project_data, headers=headers1)
        # 应该正常处理，不会执行SQL注入
        assert response.status_code in [201, 400]  # 创建成功或验证失败
        
        # 验证数据库完整性
        response = api_client.get("/api/v1/projects", headers=headers1)
        assert response.status_code == 200  # 数据库应该仍然正常