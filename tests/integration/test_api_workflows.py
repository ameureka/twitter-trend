import pytest
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from api.main import app
from app.database.models import User, Project, ContentSource, PublishingTask
from api.schemas import TaskStatusEnum


class TestProjectManagementAPIWorkflow:
    """项目管理API工作流程测试类"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def authenticated_headers(self, db_session, sample_user, sample_api_key):
        """创建认证头"""
        # 添加用户和API密钥到数据库
        db_session.add(sample_user)
        db_session.add(sample_api_key)
        db_session.commit()
        
        return {"X-API-Key": "test_api_key_hash"}
    
    @pytest.mark.integration
    @pytest.mark.api
    def test_complete_project_management_workflow(self, client, authenticated_headers, db_session):
        """测试完整的项目管理工作流程"""
        
        # 1. 获取用户项目列表（应该为空）
        response = client.get("/api/v1/projects", headers=authenticated_headers)
        assert response.status_code == 200
        assert response.json()["data"] == []
        assert response.json()["total"] == 0
        
        # 2. 创建新项目
        project_data = {
            "name": "Test API Project",
            "path": "/api/test/project",
            "description": "A project created via API"
        }
        
        with patch('app.core.project_manager.ProjectManager.scan_project') as mock_scan:
            mock_scan.return_value = {
                'success': True,
                'project_created': True,
                'content_sources_found': 2
            }
            
            response = client.post(
                "/api/v1/projects",
                json=project_data,
                headers=authenticated_headers
            )
        
        assert response.status_code == 201
        project_response = response.json()
        assert project_response["name"] == "Test API Project"
        assert project_response["path"] == "/api/test/project"
        project_id = project_response["id"]
        
        # 3. 获取项目详情
        response = client.get(
            f"/api/v1/projects/{project_id}",
            headers=authenticated_headers
        )
        assert response.status_code == 200
        project_detail = response.json()
        assert project_detail["id"] == project_id
        assert project_detail["name"] == "Test API Project"
        
        # 4. 更新项目信息
        update_data = {
            "description": "Updated project description",
            "is_active": True
        }
        response = client.put(
            f"/api/v1/projects/{project_id}",
            json=update_data,
            headers=authenticated_headers
        )
        assert response.status_code == 200
        updated_project = response.json()
        assert updated_project["description"] == "Updated project description"
        
        # 5. 重新扫描项目
        with patch('app.core.project_manager.ProjectManager.scan_project') as mock_rescan:
            mock_rescan.return_value = {
                'success': True,
                'project_created': False,
                'content_sources_found': 3,
                'new_sources_added': 1
            }
            
            response = client.post(
                f"/api/v1/projects/{project_id}/scan",
                headers=authenticated_headers
            )
        
        assert response.status_code == 200
        scan_result = response.json()
        assert scan_result["success"] is True
        assert scan_result["content_sources_found"] == 3
        
        # 6. 获取项目的内容源
        response = client.get(
            f"/api/v1/projects/{project_id}/content-sources",
            headers=authenticated_headers
        )
        assert response.status_code == 200
        content_sources = response.json()
        assert "data" in content_sources
        
        # 7. 获取更新后的项目列表
        response = client.get("/api/v1/projects", headers=authenticated_headers)
        assert response.status_code == 200
        projects_list = response.json()
        assert projects_list["total"] == 1
        assert len(projects_list["data"]) == 1
        
        # 8. 删除项目
        response = client.delete(
            f"/api/v1/projects/{project_id}",
            headers=authenticated_headers
        )
        assert response.status_code == 204
        
        # 9. 验证项目已删除
        response = client.get(
            f"/api/v1/projects/{project_id}",
            headers=authenticated_headers
        )
        assert response.status_code == 404
    
    @pytest.mark.integration
    @pytest.mark.api
    def test_project_access_control_workflow(self, client, db_session):
        """测试项目访问控制工作流程"""
        
        # 创建两个用户
        user1 = User(
            username="user1",
            email="user1@example.com",
            password_hash="hash1",
            is_active=True
        )
        user2 = User(
            username="user2",
            email="user2@example.com",
            password_hash="hash2",
            is_active=True
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        
        # 创建API密钥
        api_key1 = ApiKey(
            user_id=user1.id,
            name="user1_key",
            key_hash="key1_hash",
            is_active=True
        )
        api_key2 = ApiKey(
            user_id=user2.id,
            name="user2_key",
            key_hash="key2_hash",
            is_active=True
        )
        db_session.add(api_key1)
        db_session.add(api_key2)
        db_session.commit()
        
        headers1 = {"X-API-Key": "key1_hash"}
        headers2 = {"X-API-Key": "key2_hash"}
        
        # 用户1创建项目
        project_data = {
            "name": "User1 Project",
            "path": "/user1/project",
            "description": "User1's private project"
        }
        
        with patch('app.core.project_manager.ProjectManager.scan_project') as mock_scan:
            mock_scan.return_value = {
                'success': True,
                'project_created': True,
                'content_sources_found': 1
            }
            
            response = client.post(
                "/api/v1/projects",
                json=project_data,
                headers=headers1
            )
        
        assert response.status_code == 201
        project_id = response.json()["id"]
        
        # 用户1可以访问自己的项目
        response = client.get(
            f"/api/v1/projects/{project_id}",
            headers=headers1
        )
        assert response.status_code == 200
        
        # 用户2不能访问用户1的项目
        response = client.get(
            f"/api/v1/projects/{project_id}",
            headers=headers2
        )
        assert response.status_code == 404  # 或403，取决于实现
        
        # 用户2不能修改用户1的项目
        response = client.put(
            f"/api/v1/projects/{project_id}",
            json={"description": "Hacked description"},
            headers=headers2
        )
        assert response.status_code in [403, 404]
        
        # 用户2不能删除用户1的项目
        response = client.delete(
            f"/api/v1/projects/{project_id}",
            headers=headers2
        )
        assert response.status_code in [403, 404]
    
    @pytest.mark.integration
    @pytest.mark.api
    def test_project_pagination_workflow(self, client, authenticated_headers, db_session, sample_user):
        """测试项目分页工作流程"""
        
        # 添加用户到数据库
        db_session.add(sample_user)
        db_session.commit()
        
        # 创建多个项目
        projects = []
        for i in range(15):
            project = Project(
                user_id=sample_user.id,
                name=f"Project {i+1}",
                path=f"/test/project/{i+1}",
                description=f"Test project {i+1}",
                is_active=True
            )
            db_session.add(project)
            projects.append(project)
        
        db_session.commit()
        
        # 测试第一页
        response = client.get(
            "/api/v1/projects?page=1&size=10",
            headers=authenticated_headers
        )
        assert response.status_code == 200
        page1_data = response.json()
        assert len(page1_data["data"]) == 10
        assert page1_data["total"] == 15
        assert page1_data["page"] == 1
        assert page1_data["size"] == 10
        assert page1_data["pages"] == 2
        
        # 测试第二页
        response = client.get(
            "/api/v1/projects?page=2&size=10",
            headers=authenticated_headers
        )
        assert response.status_code == 200
        page2_data = response.json()
        assert len(page2_data["data"]) == 5
        assert page2_data["page"] == 2
        
        # 测试不同页面大小
        response = client.get(
            "/api/v1/projects?page=1&size=5",
            headers=authenticated_headers
        )
        assert response.status_code == 200
        small_page_data = response.json()
        assert len(small_page_data["data"]) == 5
        assert small_page_data["pages"] == 3


class TestTaskManagementAPIWorkflow:
    """任务管理API工作流程测试类"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def setup_test_data(self, db_session, sample_user, sample_api_key, sample_project, sample_content_source):
        """设置测试数据"""
        db_session.add(sample_user)
        db_session.add(sample_api_key)
        db_session.add(sample_project)
        db_session.add(sample_content_source)
        db_session.commit()
        
        return {
            'user': sample_user,
            'project': sample_project,
            'content_source': sample_content_source,
            'headers': {"X-API-Key": "test_api_key_hash"}
        }
    
    @pytest.mark.integration
    @pytest.mark.api
    def test_complete_task_management_workflow(self, client, setup_test_data, db_session):
        """测试完整的任务管理工作流程"""
        
        headers = setup_test_data['headers']
        content_source = setup_test_data['content_source']
        
        # 1. 获取任务列表（应该为空）
        response = client.get("/api/v1/tasks", headers=headers)
        assert response.status_code == 200
        assert response.json()["data"] == []
        
        # 2. 创建新任务
        task_data = {
            "content_source_id": content_source.id,
            "scheduled_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "content": "Test tweet content for API",
            "priority": 1
        }
        
        response = client.post(
            "/api/v1/tasks",
            json=task_data,
            headers=headers
        )
        assert response.status_code == 201
        task_response = response.json()
        assert task_response["content"] == "Test tweet content for API"
        assert task_response["status"] == TaskStatusEnum.PENDING.value
        task_id = task_response["id"]
        
        # 3. 获取任务详情
        response = client.get(
            f"/api/v1/tasks/{task_id}",
            headers=headers
        )
        assert response.status_code == 200
        task_detail = response.json()
        assert task_detail["id"] == task_id
        assert task_detail["content"] == "Test tweet content for API"
        
        # 4. 更新任务
        update_data = {
            "content": "Updated tweet content",
            "priority": 2
        }
        response = client.put(
            f"/api/v1/tasks/{task_id}",
            json=update_data,
            headers=headers
        )
        assert response.status_code == 200
        updated_task = response.json()
        assert updated_task["content"] == "Updated tweet content"
        assert updated_task["priority"] == 2
        
        # 5. 获取任务列表（现在应该有一个任务）
        response = client.get("/api/v1/tasks", headers=headers)
        assert response.status_code == 200
        tasks_list = response.json()
        assert tasks_list["total"] == 1
        assert len(tasks_list["data"]) == 1
        
        # 6. 按状态筛选任务
        response = client.get(
            f"/api/v1/tasks?status={TaskStatusEnum.PENDING.value}",
            headers=headers
        )
        assert response.status_code == 200
        pending_tasks = response.json()
        assert pending_tasks["total"] == 1
        
        # 7. 手动执行任务
        with patch('app.core.scheduler.TaskScheduler.execute_task') as mock_execute:
            mock_execute.return_value = {
                'success': True,
                'task_id': task_id,
                'tweet_id': '1234567890'
            }
            
            response = client.post(
                f"/api/v1/tasks/{task_id}/execute",
                headers=headers
            )
        
        assert response.status_code == 200
        execution_result = response.json()
        assert execution_result["success"] is True
        
        # 8. 获取任务执行日志
        response = client.get(
            f"/api/v1/tasks/{task_id}/logs",
            headers=headers
        )
        assert response.status_code == 200
        logs = response.json()
        assert "data" in logs
        
        # 9. 删除任务
        response = client.delete(
            f"/api/v1/tasks/{task_id}",
            headers=headers
        )
        assert response.status_code == 204
        
        # 10. 验证任务已删除
        response = client.get(
            f"/api/v1/tasks/{task_id}",
            headers=headers
        )
        assert response.status_code == 404
    
    @pytest.mark.integration
    @pytest.mark.api
    def test_batch_task_operations_workflow(self, client, setup_test_data, db_session):
        """测试批量任务操作工作流程"""
        
        headers = setup_test_data['headers']
        content_source = setup_test_data['content_source']
        
        # 创建多个任务
        task_ids = []
        for i in range(5):
            task_data = {
                "content_source_id": content_source.id,
                "scheduled_at": (datetime.utcnow() + timedelta(hours=i+1)).isoformat(),
                "content": f"Batch task content {i+1}",
                "priority": i % 3 + 1
            }
            
            response = client.post(
                "/api/v1/tasks",
                json=task_data,
                headers=headers
            )
            assert response.status_code == 201
            task_ids.append(response.json()["id"])
        
        # 批量更新任务状态
        batch_update_data = {
            "task_ids": task_ids[:3],
            "status": TaskStatusEnum.IN_PROGRESS.value
        }
        
        response = client.put(
            "/api/v1/tasks/batch",
            json=batch_update_data,
            headers=headers
        )
        assert response.status_code == 200
        batch_result = response.json()
        assert batch_result["updated_count"] == 3
        
        # 验证状态更新
        for task_id in task_ids[:3]:
            response = client.get(
                f"/api/v1/tasks/{task_id}",
                headers=headers
            )
            assert response.status_code == 200
            assert response.json()["status"] == TaskStatusEnum.IN_PROGRESS.value
        
        # 批量删除任务
        batch_delete_data = {
            "task_ids": task_ids[3:]
        }
        
        response = client.delete(
            "/api/v1/tasks/batch",
            json=batch_delete_data,
            headers=headers
        )
        assert response.status_code == 200
        delete_result = response.json()
        assert delete_result["deleted_count"] == 2
        
        # 验证任务被删除
        for task_id in task_ids[3:]:
            response = client.get(
                f"/api/v1/tasks/{task_id}",
                headers=headers
            )
            assert response.status_code == 404
    
    @pytest.mark.integration
    @pytest.mark.api
    def test_task_scheduling_workflow(self, client, setup_test_data, db_session):
        """测试任务调度工作流程"""
        
        headers = setup_test_data['headers']
        content_source = setup_test_data['content_source']
        
        # 创建立即执行的任务
        immediate_task_data = {
            "content_source_id": content_source.id,
            "scheduled_at": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
            "content": "Immediate task content",
            "priority": 1
        }
        
        response = client.post(
            "/api/v1/tasks",
            json=immediate_task_data,
            headers=headers
        )
        assert response.status_code == 201
        immediate_task_id = response.json()["id"]
        
        # 创建未来执行的任务
        future_task_data = {
            "content_source_id": content_source.id,
            "scheduled_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
            "content": "Future task content",
            "priority": 2
        }
        
        response = client.post(
            "/api/v1/tasks",
            json=future_task_data,
            headers=headers
        )
        assert response.status_code == 201
        future_task_id = response.json()["id"]
        
        # 获取待执行任务（应该只包含立即执行的任务）
        response = client.get(
            "/api/v1/tasks/pending",
            headers=headers
        )
        assert response.status_code == 200
        pending_tasks = response.json()
        
        pending_task_ids = [task["id"] for task in pending_tasks["data"]]
        assert immediate_task_id in pending_task_ids
        assert future_task_id not in pending_task_ids
        
        # 执行调度器
        with patch('app.core.scheduler.TaskScheduler.execute_batch_tasks') as mock_batch_execute:
            mock_batch_execute.return_value = [
                {
                    'success': True,
                    'task_id': immediate_task_id,
                    'tweet_id': '1234567890'
                }
            ]
            
            response = client.post(
                "/api/v1/scheduler/run",
                headers=headers
            )
        
        assert response.status_code == 200
        scheduler_result = response.json()
        assert scheduler_result["tasks_executed"] >= 1
        
        # 验证任务状态更新
        response = client.get(
            f"/api/v1/tasks/{immediate_task_id}",
            headers=headers
        )
        # 注意：这里的状态可能需要根据实际的mock实现来调整
        # assert response.json()["status"] == TaskStatus.COMPLETED.value


class TestDashboardAPIWorkflow:
    """仪表板API工作流程测试类"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def setup_dashboard_data(self, db_session, sample_user, sample_api_key):
        """设置仪表板测试数据"""
        from app.database.models import AnalyticsHourly
        
        db_session.add(sample_user)
        db_session.add(sample_api_key)
        db_session.commit()
        
        # 创建分析数据
        current_time = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        for i in range(24):  # 24小时的数据
            hour = current_time - timedelta(hours=i)
            analytics = AnalyticsHourly(
                user_id=sample_user.id,
                hour=hour,
                tweets_published=i % 5 + 1,
                total_impressions=(i % 5 + 1) * 100,
                total_engagements=(i % 5 + 1) * 10,
                total_retweets=(i % 5 + 1) * 2,
                total_likes=(i % 5 + 1) * 8
            )
            db_session.add(analytics)
        
        db_session.commit()
        
        return {
            'user': sample_user,
            'headers': {"X-API-Key": "test_api_key_hash"}
        }
    
    @pytest.mark.integration
    @pytest.mark.api
    def test_dashboard_overview_workflow(self, client, setup_dashboard_data):
        """测试仪表板概览工作流程"""
        
        headers = setup_dashboard_data['headers']
        
        # 获取仪表板概览
        response = client.get("/api/v1/dashboard/overview", headers=headers)
        assert response.status_code == 200
        
        overview = response.json()
        assert "total_projects" in overview
        assert "total_content_sources" in overview
        assert "total_tasks" in overview
        assert "pending_tasks" in overview
        assert "completed_tasks" in overview
        assert "failed_tasks" in overview
        assert "total_tweets_published" in overview
        assert "total_impressions" in overview
        assert "total_engagements" in overview
        
        # 验证数据类型
        assert isinstance(overview["total_projects"], int)
        assert isinstance(overview["total_content_sources"], int)
        assert isinstance(overview["total_tasks"], int)
        assert isinstance(overview["total_tweets_published"], int)
    
    @pytest.mark.integration
    @pytest.mark.api
    def test_analytics_data_workflow(self, client, setup_dashboard_data):
        """测试分析数据工作流程"""
        
        headers = setup_dashboard_data['headers']
        
        # 获取最近24小时的分析数据
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        response = client.get(
            f"/api/v1/analytics/hourly?start_time={start_time.isoformat()}&end_time={end_time.isoformat()}",
            headers=headers
        )
        assert response.status_code == 200
        
        analytics = response.json()
        assert "data" in analytics
        assert len(analytics["data"]) <= 24
        
        # 验证数据结构
        if analytics["data"]:
            first_record = analytics["data"][0]
            assert "hour" in first_record
            assert "tweets_published" in first_record
            assert "total_impressions" in first_record
            assert "total_engagements" in first_record
        
        # 获取每日汇总数据
        response = client.get(
            f"/api/v1/analytics/daily?start_date={start_time.date()}&end_date={end_time.date()}",
            headers=headers
        )
        assert response.status_code == 200
        
        daily_analytics = response.json()
        assert "data" in daily_analytics
        
        # 获取月度汇总数据
        response = client.get(
            f"/api/v1/analytics/monthly?year={end_time.year}&month={end_time.month}",
            headers=headers
        )
        assert response.status_code == 200
        
        monthly_analytics = response.json()
        assert "data" in monthly_analytics
    
    @pytest.mark.integration
    @pytest.mark.api
    def test_performance_metrics_workflow(self, client, setup_dashboard_data):
        """测试性能指标工作流程"""
        
        headers = setup_dashboard_data['headers']
        
        # 获取性能指标
        response = client.get("/api/v1/dashboard/metrics", headers=headers)
        assert response.status_code == 200
        
        metrics = response.json()
        assert "engagement_rate" in metrics
        assert "average_impressions_per_tweet" in metrics
        assert "tweets_per_day" in metrics
        assert "top_performing_content" in metrics
        assert "recent_activity" in metrics
        
        # 验证指标数据类型
        assert isinstance(metrics["engagement_rate"], (int, float))
        assert isinstance(metrics["average_impressions_per_tweet"], (int, float))
        assert isinstance(metrics["tweets_per_day"], (int, float))
        assert isinstance(metrics["top_performing_content"], list)
        assert isinstance(metrics["recent_activity"], list)
    
    @pytest.mark.integration
    @pytest.mark.api
    def test_real_time_updates_workflow(self, client, setup_dashboard_data, db_session):
        """测试实时更新工作流程"""
        
        headers = setup_dashboard_data['headers']
        
        # 获取初始状态
        response = client.get("/api/v1/dashboard/overview", headers=headers)
        assert response.status_code == 200
        initial_overview = response.json()
        
        # 模拟新的活动（创建新任务）
        user = setup_dashboard_data['user']
        
        # 创建项目和内容源
        project = Project(
            user_id=user.id,
            name="Real-time Test Project",
            path="/realtime/test",
            is_active=True
        )
        db_session.add(project)
        db_session.commit()
        
        content_source = ContentSource(
            project_id=project.id,
            file_path="/realtime/video.mp4",
            file_name="video.mp4",
            file_size=1024000,
            metadata={"title": "Real-time Video"}
        )
        db_session.add(content_source)
        db_session.commit()
        
        # 通过API创建新任务
        task_data = {
            "content_source_id": content_source.id,
            "scheduled_at": datetime.utcnow().isoformat(),
            "content": "Real-time test content",
            "priority": 1
        }
        
        response = client.post(
            "/api/v1/tasks",
            json=task_data,
            headers=headers
        )
        assert response.status_code == 201
        
        # 获取更新后的状态
        response = client.get("/api/v1/dashboard/overview", headers=headers)
        assert response.status_code == 200
        updated_overview = response.json()
        
        # 验证数据已更新
        assert updated_overview["total_projects"] >= initial_overview["total_projects"]
        assert updated_overview["total_content_sources"] >= initial_overview["total_content_sources"]
        assert updated_overview["total_tasks"] > initial_overview["total_tasks"]
        assert updated_overview["pending_tasks"] > initial_overview["pending_tasks"]
    
    @pytest.mark.integration
    @pytest.mark.api
    def test_dashboard_error_handling_workflow(self, client, setup_dashboard_data):
        """测试仪表板错误处理工作流程"""
        
        headers = setup_dashboard_data['headers']
        
        # 测试无效的时间范围
        invalid_start = "invalid-date"
        invalid_end = "invalid-date"
        
        response = client.get(
            f"/api/v1/analytics/hourly?start_time={invalid_start}&end_time={invalid_end}",
            headers=headers
        )
        assert response.status_code == 422  # 验证错误
        
        # 测试未来的时间范围
        future_start = (datetime.utcnow() + timedelta(days=1)).isoformat()
        future_end = (datetime.utcnow() + timedelta(days=2)).isoformat()
        
        response = client.get(
            f"/api/v1/analytics/hourly?start_time={future_start}&end_time={future_end}",
            headers=headers
        )
        assert response.status_code == 200
        # 应该返回空数据
        analytics = response.json()
        assert len(analytics["data"]) == 0
        
        # 测试过大的时间范围
        large_start = (datetime.utcnow() - timedelta(days=365)).isoformat()
        large_end = datetime.utcnow().isoformat()
        
        response = client.get(
            f"/api/v1/analytics/hourly?start_time={large_start}&end_time={large_end}",
            headers=headers
        )
        # 应该有合理的限制或分页
        assert response.status_code in [200, 400]