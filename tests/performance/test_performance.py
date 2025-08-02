import pytest
import time
import psutil
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
import json
import tempfile
from pathlib import Path

from api.main import app
from app.core.project_manager import ProjectManager
from app.core.task_scheduler import TaskScheduler
from app.core.content_generator import ContentGenerator
from app.core.publisher import TwitterPublisher
from app.database.models import User, Project, ContentSource, PublishingTask
from app.database.repository import (
    UserRepository, ProjectRepository, ContentSourceRepository,
    PublishingTaskRepository, PublishingLogRepository
)


class TestPerformanceBenchmarks:
    """性能基准测试类"""
    
    @pytest.fixture
    def api_client(self):
        """创建API测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def performance_project_structure(self, tmp_path):
        """创建性能测试项目结构"""
        project_dir = tmp_path / "performance_project"
        project_dir.mkdir()
        
        # 创建大量视频文件
        video_files = []
        for i in range(100):  # 100个视频文件
            video_file = project_dir / f"video_{i:03d}.mp4"
            # 创建不同大小的文件
            file_size = 1000 + (i * 50)  # 从1KB到6KB
            video_file.write_bytes(b"fake video content" * file_size)
            video_files.append(str(video_file))
        
        # 创建子目录结构
        for j in range(10):
            subdir = project_dir / f"subdir_{j}"
            subdir.mkdir()
            for k in range(10):
                video_file = subdir / f"sub_video_{k}.mp4"
                video_file.write_bytes(b"sub video content" * 500)
                video_files.append(str(video_file))
        
        # 创建元数据文件
        metadata = {
            "title": "Performance Test Project",
            "description": "Large project for performance testing",
            "tags": ["performance", "test", "benchmark"],
            "author": "Performance Tester",
            "language": "en"
        }
        
        metadata_file = project_dir / "metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))
        
        return {
            'project_dir': str(project_dir),
            'video_files': video_files,
            'metadata_file': str(metadata_file),
            'total_files': len(video_files)
        }
    
    @pytest.fixture
    def mock_external_services_fast(self):
        """快速响应的外部服务模拟"""
        with patch('app.core.publisher.TwitterPublisher') as mock_publisher, \
             patch('app.core.content_generator.ContentGenerator') as mock_generator:
            
            # 配置快速响应的发布器
            mock_publisher_instance = Mock()
            mock_publisher_instance.verify_credentials.return_value = True
            mock_publisher_instance.publish_tweet.return_value = {
                'id': f'tweet_{int(time.time() * 1000)}',
                'text': 'Fast published tweet',
                'created_at': datetime.utcnow().isoformat()
            }
            mock_publisher.return_value = mock_publisher_instance
            
            # 配置快速响应的内容生成器
            mock_generator_instance = Mock()
            mock_generator_instance.generate_content.return_value = {
                'text': 'Fast generated content',
                'hashtags': ['#fast', '#test'],
                'media_paths': []
            }
            mock_generator.return_value = mock_generator_instance
            
            yield {
                'publisher': mock_publisher_instance,
                'generator': mock_generator_instance
            }
    
    def measure_memory_usage(self, func, *args, **kwargs):
        """测量函数执行时的内存使用情况"""
        process = psutil.Process()
        
        # 获取初始内存使用
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 执行函数
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # 获取峰值内存使用
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        return {
            'result': result,
            'execution_time': execution_time,
            'initial_memory_mb': initial_memory,
            'peak_memory_mb': peak_memory,
            'memory_increase_mb': memory_increase
        }
    
    @pytest.mark.performance
    @pytest.mark.slow
    def test_project_scanning_performance(self, performance_project_structure, db_session):
        """测试项目扫描性能"""
        project_dir = performance_project_structure['project_dir']
        expected_files = performance_project_structure['total_files']
        
        # 创建用户和项目管理器
        user_repo = UserRepository(db_session)
        project_repo = ProjectRepository(db_session)
        content_source_repo = ContentSourceRepository(db_session)
        
        user = user_repo.create(
            username="perfuser",
            email="perf@example.com",
            password_hash="hashed_password"
        )
        
        project_manager = ProjectManager(
            project_repo=project_repo,
            content_source_repo=content_source_repo
        )
        
        # 测量扫描性能
        def scan_project():
            return project_manager.scan_project(
                user_id=user.id,
                project_path=project_dir,
                project_name="Performance Test Project"
            )
        
        metrics = self.measure_memory_usage(scan_project)
        
        # 验证结果
        scan_result = metrics['result']
        assert scan_result['files_found'] == expected_files
        
        # 性能断言
        assert metrics['execution_time'] < 10.0, f"Scanning took too long: {metrics['execution_time']:.2f}s"
        assert metrics['memory_increase_mb'] < 100, f"Memory usage too high: {metrics['memory_increase_mb']:.2f}MB"
        
        print(f"\nProject Scanning Performance:")
        print(f"  Files scanned: {expected_files}")
        print(f"  Execution time: {metrics['execution_time']:.3f}s")
        print(f"  Memory increase: {metrics['memory_increase_mb']:.2f}MB")
        print(f"  Files per second: {expected_files / metrics['execution_time']:.1f}")
    
    @pytest.mark.performance
    def test_database_operations_performance(self, db_session):
        """测试数据库操作性能"""
        user_repo = UserRepository(db_session)
        project_repo = ProjectRepository(db_session)
        task_repo = PublishingTaskRepository(db_session)
        
        # 创建用户
        user = user_repo.create(
            username="dbperfuser",
            email="dbperf@example.com",
            password_hash="hashed_password"
        )
        
        # 创建项目
        project = project_repo.create(
            user_id=user.id,
            name="DB Performance Test",
            path="/test/path",
            description="Database performance testing"
        )
        
        # 测试批量任务创建性能
        def create_tasks_batch():
            tasks = []
            for i in range(1000):
                task_data = {
                    'project_id': project.id,
                    'content': f'Performance test task {i}',
                    'scheduled_time': datetime.utcnow() + timedelta(minutes=i),
                    'priority': (i % 3) + 1
                }
                tasks.append(task_data)
            
            # 批量创建
            created_tasks = []
            for task_data in tasks:
                task = task_repo.create(**task_data)
                created_tasks.append(task)
            
            return created_tasks
        
        metrics = self.measure_memory_usage(create_tasks_batch)
        created_tasks = metrics['result']
        
        assert len(created_tasks) == 1000
        assert metrics['execution_time'] < 5.0, f"Batch creation took too long: {metrics['execution_time']:.2f}s"
        
        # 测试批量查询性能
        def query_tasks_batch():
            # 分页查询
            all_tasks = []
            page_size = 100
            for offset in range(0, 1000, page_size):
                tasks = task_repo.get_by_user_id(
                    user_id=user.id,
                    limit=page_size,
                    offset=offset
                )
                all_tasks.extend(tasks)
            return all_tasks
        
        query_metrics = self.measure_memory_usage(query_tasks_batch)
        queried_tasks = query_metrics['result']
        
        assert len(queried_tasks) == 1000
        assert query_metrics['execution_time'] < 2.0, f"Batch query took too long: {query_metrics['execution_time']:.2f}s"
        
        print(f"\nDatabase Operations Performance:")
        print(f"  Batch creation (1000 tasks): {metrics['execution_time']:.3f}s")
        print(f"  Batch query (1000 tasks): {query_metrics['execution_time']:.3f}s")
        print(f"  Creation rate: {1000 / metrics['execution_time']:.1f} tasks/s")
        print(f"  Query rate: {1000 / query_metrics['execution_time']:.1f} tasks/s")
    
    @pytest.mark.performance
    def test_api_endpoint_performance(self, api_client, performance_project_structure, mock_external_services_fast, db_session):
        """测试API端点性能"""
        
        # 设置用户
        user_data = {
            "username": "apiperuser",
            "email": "apiperf@example.com",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        
        login_data = {
            "username": "apiperuser",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        api_key = response.json()["api_key"]
        headers = {"X-API-Key": api_key}
        
        # 测试项目创建性能
        project_data = {
            "name": "API Performance Test",
            "description": "API performance testing",
            "path": performance_project_structure['project_dir']
        }
        
        start_time = time.time()
        response = api_client.post("/api/v1/projects", json=project_data, headers=headers)
        project_creation_time = time.time() - start_time
        
        assert response.status_code == 201
        assert project_creation_time < 1.0, f"Project creation took too long: {project_creation_time:.3f}s"
        
        project_id = response.json()["id"]
        
        # 测试项目扫描性能
        start_time = time.time()
        response = api_client.post(f"/api/v1/projects/{project_id}/scan", headers=headers)
        scan_time = time.time() - start_time
        
        assert response.status_code == 200
        assert scan_time < 15.0, f"Project scan took too long: {scan_time:.3f}s"
        
        # 测试内容源列表性能
        start_time = time.time()
        response = api_client.get(f"/api/v1/projects/{project_id}/content-sources", headers=headers)
        list_time = time.time() - start_time
        
        assert response.status_code == 200
        assert list_time < 2.0, f"Content source listing took too long: {list_time:.3f}s"
        
        content_sources = response.json()["items"]
        
        # 测试批量任务创建性能
        task_creation_times = []
        for i in range(50):
            content_source = content_sources[i % len(content_sources)]
            task_data = {
                "content_source_id": content_source["id"],
                "content": f"API performance test task {i}",
                "scheduled_time": (datetime.utcnow() + timedelta(minutes=i)).isoformat(),
                "priority": (i % 3) + 1
            }
            
            start_time = time.time()
            response = api_client.post("/api/v1/tasks", json=task_data, headers=headers)
            creation_time = time.time() - start_time
            task_creation_times.append(creation_time)
            
            assert response.status_code == 201
            assert creation_time < 0.5, f"Task creation took too long: {creation_time:.3f}s"
        
        # 测试任务列表性能
        start_time = time.time()
        response = api_client.get("/api/v1/tasks?limit=100", headers=headers)
        task_list_time = time.time() - start_time
        
        assert response.status_code == 200
        assert task_list_time < 1.0, f"Task listing took too long: {task_list_time:.3f}s"
        
        avg_task_creation_time = sum(task_creation_times) / len(task_creation_times)
        
        print(f"\nAPI Endpoint Performance:")
        print(f"  Project creation: {project_creation_time:.3f}s")
        print(f"  Project scan ({len(content_sources)} files): {scan_time:.3f}s")
        print(f"  Content source listing: {list_time:.3f}s")
        print(f"  Average task creation: {avg_task_creation_time:.3f}s")
        print(f"  Task listing (50 items): {task_list_time:.3f}s")
    
    @pytest.mark.performance
    def test_concurrent_api_requests(self, api_client, performance_project_structure, mock_external_services_fast, db_session):
        """测试并发API请求性能"""
        
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
        project_data = {
            "name": "Concurrent Test Project",
            "description": "Concurrent testing",
            "path": performance_project_structure['project_dir']
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
            content_source = content_sources[index % len(content_sources)]
            task_data = {
                "content_source_id": content_source["id"],
                "content": f"Concurrent task {index}",
                "scheduled_time": (datetime.utcnow() + timedelta(minutes=index)).isoformat(),
                "priority": (index % 3) + 1
            }
            
            start_time = time.time()
            response = api_client.post("/api/v1/tasks", json=task_data, headers=headers)
            execution_time = time.time() - start_time
            
            return {
                'success': response.status_code == 201,
                'execution_time': execution_time,
                'status_code': response.status_code
            }
        
        # 测试不同并发级别
        concurrency_levels = [1, 5, 10, 20]
        results = {}
        
        for concurrency in concurrency_levels:
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(create_task, i) for i in range(concurrency * 5)]
                concurrent_results = [future.result() for future in as_completed(futures)]
            
            total_time = time.time() - start_time
            
            successful_requests = sum(1 for r in concurrent_results if r['success'])
            avg_response_time = sum(r['execution_time'] for r in concurrent_results) / len(concurrent_results)
            throughput = len(concurrent_results) / total_time
            
            results[concurrency] = {
                'total_requests': len(concurrent_results),
                'successful_requests': successful_requests,
                'success_rate': successful_requests / len(concurrent_results),
                'total_time': total_time,
                'avg_response_time': avg_response_time,
                'throughput': throughput
            }
            
            # 性能断言
            assert results[concurrency]['success_rate'] >= 0.8, f"Success rate too low at concurrency {concurrency}"
            assert results[concurrency]['avg_response_time'] < 2.0, f"Response time too high at concurrency {concurrency}"
        
        print(f"\nConcurrent API Request Performance:")
        for concurrency, metrics in results.items():
            print(f"  Concurrency {concurrency}:")
            print(f"    Success rate: {metrics['success_rate']:.1%}")
            print(f"    Avg response time: {metrics['avg_response_time']:.3f}s")
            print(f"    Throughput: {metrics['throughput']:.1f} req/s")
    
    @pytest.mark.performance
    def test_task_scheduler_performance(self, performance_project_structure, mock_external_services_fast, db_session):
        """测试任务调度器性能"""
        
        # 设置数据
        user_repo = UserRepository(db_session)
        project_repo = ProjectRepository(db_session)
        content_source_repo = ContentSourceRepository(db_session)
        task_repo = PublishingTaskRepository(db_session)
        log_repo = PublishingLogRepository(db_session)
        
        user = user_repo.create(
            username="scheduleruser",
            email="scheduler@example.com",
            password_hash="hashed_password"
        )
        
        project = project_repo.create(
            user_id=user.id,
            name="Scheduler Performance Test",
            path=performance_project_structure['project_dir'],
            description="Scheduler performance testing"
        )
        
        # 创建内容源
        content_sources = []
        for i in range(10):
            content_source = content_source_repo.create(
                project_id=project.id,
                file_path=f"/test/video_{i}.mp4",
                file_name=f"video_{i}.mp4",
                file_size=1024000,
                file_type="video/mp4"
            )
            content_sources.append(content_source)
        
        # 创建大量任务
        tasks = []
        for i in range(100):
            task = task_repo.create(
                project_id=project.id,
                content_source_id=content_sources[i % len(content_sources)].id,
                content=f"Scheduler performance test task {i}",
                scheduled_time=datetime.utcnow() - timedelta(minutes=i),  # 过期任务
                priority=(i % 3) + 1
            )
            tasks.append(task)
        
        # 创建调度器
        scheduler = TaskScheduler(
            task_repo=task_repo,
            log_repo=log_repo,
            content_generator=mock_external_services_fast['generator'],
            publisher=mock_external_services_fast['publisher']
        )
        
        # 测试批量任务执行性能
        def execute_pending_tasks():
            return scheduler.execute_pending_tasks(limit=50)
        
        metrics = self.measure_memory_usage(execute_pending_tasks)
        execution_results = metrics['result']
        
        # 验证结果
        assert len(execution_results) <= 50
        assert metrics['execution_time'] < 30.0, f"Task execution took too long: {metrics['execution_time']:.2f}s"
        
        # 测试任务检索性能
        def get_pending_tasks():
            return task_repo.get_pending_tasks(limit=100)
        
        retrieval_metrics = self.measure_memory_usage(get_pending_tasks)
        pending_tasks = retrieval_metrics['result']
        
        assert retrieval_metrics['execution_time'] < 1.0, f"Task retrieval took too long: {retrieval_metrics['execution_time']:.3f}s"
        
        print(f"\nTask Scheduler Performance:")
        print(f"  Task execution (50 tasks): {metrics['execution_time']:.3f}s")
        print(f"  Task retrieval (100 tasks): {retrieval_metrics['execution_time']:.3f}s")
        print(f"  Execution rate: {len(execution_results) / metrics['execution_time']:.1f} tasks/s")
        print(f"  Memory usage: {metrics['memory_increase_mb']:.2f}MB")
    
    @pytest.mark.performance
    @pytest.mark.slow
    def test_memory_leak_detection(self, api_client, performance_project_structure, mock_external_services_fast, db_session):
        """测试内存泄漏检测"""
        
        # 设置用户
        user_data = {
            "username": "memoryuser",
            "email": "memory@example.com",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        
        login_data = {
            "username": "memoryuser",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        api_key = response.json()["api_key"]
        headers = {"X-API-Key": api_key}
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        memory_samples = [initial_memory]
        
        # 执行重复操作
        for iteration in range(10):
            # 创建项目
            project_data = {
                "name": f"Memory Test Project {iteration}",
                "description": f"Memory testing iteration {iteration}",
                "path": performance_project_structure['project_dir']
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
            
            # 创建任务
            for i in range(20):
                content_source = content_sources[i % len(content_sources)]
                task_data = {
                    "content_source_id": content_source["id"],
                    "content": f"Memory test task {iteration}-{i}",
                    "scheduled_time": datetime.utcnow().isoformat(),
                    "priority": 1
                }
                
                response = api_client.post("/api/v1/tasks", json=task_data, headers=headers)
                assert response.status_code == 201
            
            # 删除项目（清理）
            response = api_client.delete(f"/api/v1/projects/{project_id}", headers=headers)
            assert response.status_code == 204
            
            # 记录内存使用
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_samples.append(current_memory)
            
            print(f"Iteration {iteration + 1}: Memory usage = {current_memory:.2f}MB")
        
        # 分析内存使用趋势
        final_memory = memory_samples[-1]
        memory_increase = final_memory - initial_memory
        
        # 计算内存增长趋势
        if len(memory_samples) > 5:
            recent_avg = sum(memory_samples[-5:]) / 5
            early_avg = sum(memory_samples[:5]) / 5
            trend_increase = recent_avg - early_avg
        else:
            trend_increase = memory_increase
        
        print(f"\nMemory Leak Detection:")
        print(f"  Initial memory: {initial_memory:.2f}MB")
        print(f"  Final memory: {final_memory:.2f}MB")
        print(f"  Total increase: {memory_increase:.2f}MB")
        print(f"  Trend increase: {trend_increase:.2f}MB")
        
        # 内存泄漏断言
        assert memory_increase < 50, f"Potential memory leak detected: {memory_increase:.2f}MB increase"
        assert trend_increase < 30, f"Memory usage trend concerning: {trend_increase:.2f}MB trend increase"
    
    @pytest.mark.performance
    def test_response_time_distribution(self, api_client, performance_project_structure, mock_external_services_fast, db_session):
        """测试响应时间分布"""
        
        # 设置用户
        user_data = {
            "username": "responsetimeuser",
            "email": "responsetime@example.com",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        
        login_data = {
            "username": "responsetimeuser",
            "password": "password123"
        }
        
        response = api_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        api_key = response.json()["api_key"]
        headers = {"X-API-Key": api_key}
        
        # 创建项目
        project_data = {
            "name": "Response Time Test Project",
            "description": "Response time testing",
            "path": performance_project_structure['project_dir']
        }
        
        response = api_client.post("/api/v1/projects", json=project_data, headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]
        
        # 扫描项目
        response = api_client.post(f"/api/v1/projects/{project_id}/scan", headers=headers)
        assert response.status_code == 200
        
        # 测试不同端点的响应时间
        endpoints = [
            ('GET', '/api/v1/projects'),
            ('GET', f'/api/v1/projects/{project_id}'),
            ('GET', f'/api/v1/projects/{project_id}/content-sources'),
            ('GET', '/api/v1/tasks'),
            ('GET', '/api/v1/dashboard/overview'),
        ]
        
        response_times = {}
        
        for method, endpoint in endpoints:
            times = []
            
            # 多次请求同一端点
            for _ in range(20):
                start_time = time.time()
                
                if method == 'GET':
                    response = api_client.get(endpoint, headers=headers)
                elif method == 'POST':
                    response = api_client.post(endpoint, headers=headers)
                
                response_time = time.time() - start_time
                times.append(response_time)
                
                assert response.status_code in [200, 201]
            
            # 计算统计信息
            times.sort()
            response_times[endpoint] = {
                'min': min(times),
                'max': max(times),
                'avg': sum(times) / len(times),
                'p50': times[len(times) // 2],
                'p95': times[int(len(times) * 0.95)],
                'p99': times[int(len(times) * 0.99)]
            }
        
        print(f"\nResponse Time Distribution:")
        for endpoint, stats in response_times.items():
            print(f"  {endpoint}:")
            print(f"    Min: {stats['min']:.3f}s")
            print(f"    Avg: {stats['avg']:.3f}s")
            print(f"    P50: {stats['p50']:.3f}s")
            print(f"    P95: {stats['p95']:.3f}s")
            print(f"    P99: {stats['p99']:.3f}s")
            print(f"    Max: {stats['max']:.3f}s")
            
            # 性能断言
            assert stats['p95'] < 1.0, f"P95 response time too high for {endpoint}: {stats['p95']:.3f}s"
            assert stats['avg'] < 0.5, f"Average response time too high for {endpoint}: {stats['avg']:.3f}s"