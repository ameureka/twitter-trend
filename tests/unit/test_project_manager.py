import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
from datetime import datetime

from app.core.project_manager import ProjectManager
from app.database.models import User, Project, ContentSource, PublishingTask


class TestProjectManager:
    """项目管理器测试类"""
    
    @pytest.fixture
    def project_manager(self, db_session):
        """创建项目管理器实例"""
        return ProjectManager(db_session)
    
    @pytest.fixture
    def sample_project_structure(self, tmp_path):
        """创建示例项目结构"""
        project_root = tmp_path / "test_projects"
        project_dir = project_root / "test_project"
        
        # 创建目录结构
        video_dir = project_dir / "output_video_music"
        json_dir = project_dir / "uploader_json"
        video_dir.mkdir(parents=True)
        json_dir.mkdir(parents=True)
        
        # 创建测试视频文件
        (video_dir / "video_01.mp4").write_bytes(b"fake video content 1")
        (video_dir / "video_02.mp4").write_bytes(b"fake video content 2")
        (video_dir / "video_03.avi").write_bytes(b"fake video content 3")
        
        # 创建测试元数据文件
        metadata = {
            "batch_info": {
                "total_videos": 3,
                "language": "en",
                "created_at": "2024-01-01T00:00:00Z"
            },
            "videos": [
                {
                    "filename": "video_01.mp4",
                    "title": "First Test Video",
                    "description": "Description for first video",
                    "tags": ["test", "first"]
                },
                {
                    "filename": "video_02.mp4",
                    "title": "Second Test Video",
                    "description": "Description for second video",
                    "tags": ["test", "second"]
                },
                {
                    "filename": "video_03.avi",
                    "title": "Third Test Video",
                    "description": "Description for third video",
                    "tags": ["test", "third"]
                }
            ]
        }
        
        metadata_file = json_dir / "en_prompt_results_batch.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f)
        
        return {
            "project_root": str(project_root),
            "project_dir": str(project_dir),
            "video_dir": str(video_dir),
            "json_dir": str(json_dir),
            "metadata_file": str(metadata_file)
        }
    
    @pytest.mark.unit
    def test_scan_projects_new_project(self, project_manager, sample_user, sample_project_structure):
        """测试扫描新项目"""
        result = project_manager.scan_projects(
            project_root=sample_project_structure["project_root"],
            user_id=sample_user.id,
            language="en"
        )
        
        assert "test_project" in result
        project_result = result["test_project"]
        
        assert project_result["status"] == "success"
        assert project_result["new_files"] == 3
        assert project_result["new_tasks"] == 3
        assert project_result["errors"] == []
        
        # 验证数据库中的记录
        project = project_manager.db_session.query(Project).filter_by(
            name="test_project", user_id=sample_user.id
        ).first()
        assert project is not None
        assert project.language == "en"
        
        # 验证内容源记录
        content_sources = project_manager.db_session.query(ContentSource).filter_by(
            project_id=project.id
        ).all()
        assert len(content_sources) == 3
        
        # 验证发布任务记录
        tasks = project_manager.db_session.query(PublishingTask).filter_by(
            project_id=project.id
        ).all()
        assert len(tasks) == 3
        assert all(task.status == "pending" for task in tasks)
    
    @pytest.mark.unit
    def test_scan_projects_existing_project_new_files(self, project_manager, sample_user, sample_project_structure, db_session):
        """测试扫描已存在项目的新文件"""
        # 先创建项目
        existing_project = Project(
            name="test_project",
            user_id=sample_user.id,
            language="en",
            project_path=sample_project_structure["project_dir"]
        )
        db_session.add(existing_project)
        db_session.commit()
        
        # 添加一个已存在的内容源
        existing_source = ContentSource(
            project_id=existing_project.id,
            file_path=str(Path(sample_project_structure["video_dir"]) / "video_01.mp4"),
            file_type="video",
            file_size=1000,
            metadata_path=sample_project_structure["metadata_file"]
        )
        db_session.add(existing_source)
        db_session.commit()
        
        # 扫描项目
        result = project_manager.scan_projects(
            project_root=sample_project_structure["project_root"],
            user_id=sample_user.id,
            language="en"
        )
        
        project_result = result["test_project"]
        assert project_result["status"] == "success"
        assert project_result["new_files"] == 2  # 只有2个新文件
        assert project_result["new_tasks"] == 2
    
    @pytest.mark.unit
    def test_scan_projects_no_metadata_file(self, project_manager, sample_user, tmp_path):
        """测试扫描没有元数据文件的项目"""
        # 创建只有视频文件的项目
        project_root = tmp_path / "test_projects"
        project_dir = project_root / "test_project"
        video_dir = project_dir / "output_video_music"
        video_dir.mkdir(parents=True)
        
        (video_dir / "video_01.mp4").write_bytes(b"fake video content")
        
        result = project_manager.scan_projects(
            project_root=str(project_root),
            user_id=sample_user.id,
            language="en"
        )
        
        project_result = result["test_project"]
        assert project_result["status"] == "error"
        assert "metadata file not found" in project_result["errors"][0].lower()
        assert project_result["new_files"] == 0
        assert project_result["new_tasks"] == 0
    
    @pytest.mark.unit
    def test_scan_projects_invalid_metadata_file(self, project_manager, sample_user, tmp_path):
        """测试扫描包含无效元数据文件的项目"""
        project_root = tmp_path / "test_projects"
        project_dir = project_root / "test_project"
        video_dir = project_dir / "output_video_music"
        json_dir = project_dir / "uploader_json"
        video_dir.mkdir(parents=True)
        json_dir.mkdir(parents=True)
        
        (video_dir / "video_01.mp4").write_bytes(b"fake video content")
        
        # 创建无效的JSON文件
        metadata_file = json_dir / "en_prompt_results_batch.json"
        metadata_file.write_text("invalid json content")
        
        result = project_manager.scan_projects(
            project_root=str(project_root),
            user_id=sample_user.id,
            language="en"
        )
        
        project_result = result["test_project"]
        assert project_result["status"] == "error"
        assert "invalid json" in project_result["errors"][0].lower()
    
    @pytest.mark.unit
    def test_scan_projects_no_video_files(self, project_manager, sample_user, tmp_path):
        """测试扫描没有视频文件的项目"""
        project_root = tmp_path / "test_projects"
        project_dir = project_root / "test_project"
        video_dir = project_dir / "output_video_music"
        json_dir = project_dir / "uploader_json"
        video_dir.mkdir(parents=True)
        json_dir.mkdir(parents=True)
        
        # 只创建元数据文件，没有视频文件
        metadata = {
            "batch_info": {"total_videos": 0, "language": "en"},
            "videos": []
        }
        metadata_file = json_dir / "en_prompt_results_batch.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f)
        
        result = project_manager.scan_projects(
            project_root=str(project_root),
            user_id=sample_user.id,
            language="en"
        )
        
        project_result = result["test_project"]
        assert project_result["status"] == "success"
        assert project_result["new_files"] == 0
        assert project_result["new_tasks"] == 0
    
    @pytest.mark.unit
    def test_scan_projects_multiple_projects(self, project_manager, sample_user, tmp_path):
        """测试扫描多个项目"""
        project_root = tmp_path / "test_projects"
        
        # 创建两个项目
        for project_name in ["project_a", "project_b"]:
            project_dir = project_root / project_name
            video_dir = project_dir / "output_video_music"
            json_dir = project_dir / "uploader_json"
            video_dir.mkdir(parents=True)
            json_dir.mkdir(parents=True)
            
            (video_dir / "video_01.mp4").write_bytes(b"fake video content")
            
            metadata = {
                "batch_info": {"total_videos": 1, "language": "en"},
                "videos": [{
                    "filename": "video_01.mp4",
                    "title": f"Video from {project_name}",
                    "description": f"Description for {project_name}",
                    "tags": ["test", project_name]
                }]
            }
            
            metadata_file = json_dir / "en_prompt_results_batch.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f)
        
        result = project_manager.scan_projects(
            project_root=str(project_root),
            user_id=sample_user.id,
            language="en"
        )
        
        assert len(result) == 2
        assert "project_a" in result
        assert "project_b" in result
        
        for project_name in ["project_a", "project_b"]:
            project_result = result[project_name]
            assert project_result["status"] == "success"
            assert project_result["new_files"] == 1
            assert project_result["new_tasks"] == 1
    
    @pytest.mark.unit
    def test_find_metadata_file_success(self, project_manager, sample_project_structure):
        """测试成功找到元数据文件"""
        metadata_file = project_manager.find_metadata_file(
            sample_project_structure["project_dir"], "en"
        )
        
        assert metadata_file is not None
        assert metadata_file == sample_project_structure["metadata_file"]
        assert Path(metadata_file).exists()
    
    @pytest.mark.unit
    def test_find_metadata_file_not_found(self, project_manager, tmp_path):
        """测试元数据文件不存在"""
        project_dir = tmp_path / "empty_project"
        project_dir.mkdir()
        
        metadata_file = project_manager.find_metadata_file(str(project_dir), "en")
        
        assert metadata_file is None
    
    @pytest.mark.unit
    def test_find_metadata_file_different_languages(self, project_manager, tmp_path):
        """测试不同语言的元数据文件"""
        project_dir = tmp_path / "multilang_project"
        json_dir = project_dir / "uploader_json"
        json_dir.mkdir(parents=True)
        
        # 创建不同语言的元数据文件
        languages = ["en", "zh", "ja", "es"]
        for lang in languages:
            metadata_file = json_dir / f"{lang}_prompt_results_batch.json"
            metadata_file.write_text('{"test": "data"}')
        
        # 测试每种语言
        for lang in languages:
            found_file = project_manager.find_metadata_file(str(project_dir), lang)
            assert found_file is not None
            assert f"{lang}_prompt_results_batch.json" in found_file
    
    @pytest.mark.unit
    def test_get_video_files_success(self, project_manager, sample_project_structure):
        """测试成功获取视频文件列表"""
        video_files = project_manager.get_video_files(sample_project_structure["video_dir"])
        
        assert len(video_files) == 3
        filenames = [Path(f).name for f in video_files]
        assert "video_01.mp4" in filenames
        assert "video_02.mp4" in filenames
        assert "video_03.avi" in filenames
    
    @pytest.mark.unit
    def test_get_video_files_empty_directory(self, project_manager, tmp_path):
        """测试空目录"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        video_files = project_manager.get_video_files(str(empty_dir))
        
        assert len(video_files) == 0
    
    @pytest.mark.unit
    def test_get_video_files_mixed_files(self, project_manager, tmp_path):
        """测试包含混合文件类型的目录"""
        mixed_dir = tmp_path / "mixed"
        mixed_dir.mkdir()
        
        # 创建各种文件
        (mixed_dir / "video.mp4").write_bytes(b"video")
        (mixed_dir / "video.avi").write_bytes(b"video")
        (mixed_dir / "video.mov").write_bytes(b"video")
        (mixed_dir / "image.jpg").write_bytes(b"image")
        (mixed_dir / "document.txt").write_bytes(b"text")
        (mixed_dir / "data.json").write_bytes(b"json")
        
        video_files = project_manager.get_video_files(str(mixed_dir))
        
        assert len(video_files) == 3
        extensions = [Path(f).suffix.lower() for f in video_files]
        assert ".mp4" in extensions
        assert ".avi" in extensions
        assert ".mov" in extensions
    
    @pytest.mark.unit
    def test_create_or_update_project_new(self, project_manager, sample_user, sample_project_structure):
        """测试创建新项目"""
        project = project_manager.create_or_update_project(
            name="new_project",
            user_id=sample_user.id,
            project_path=sample_project_structure["project_dir"],
            language="en"
        )
        
        assert project is not None
        assert project.name == "new_project"
        assert project.user_id == sample_user.id
        assert project.language == "en"
        assert project.project_path == sample_project_structure["project_dir"]
        
        # 验证数据库中的记录
        db_project = project_manager.db_session.query(Project).filter_by(
            name="new_project", user_id=sample_user.id
        ).first()
        assert db_project is not None
    
    @pytest.mark.unit
    def test_create_or_update_project_existing(self, project_manager, sample_user, sample_project_structure, db_session):
        """测试更新已存在项目"""
        # 先创建项目
        existing_project = Project(
            name="existing_project",
            user_id=sample_user.id,
            language="zh",
            project_path="/old/path"
        )
        db_session.add(existing_project)
        db_session.commit()
        original_id = existing_project.id
        
        # 更新项目
        updated_project = project_manager.create_or_update_project(
            name="existing_project",
            user_id=sample_user.id,
            project_path=sample_project_structure["project_dir"],
            language="en"
        )
        
        assert updated_project.id == original_id  # 应该是同一个项目
        assert updated_project.language == "en"  # 语言应该被更新
        assert updated_project.project_path == sample_project_structure["project_dir"]  # 路径应该被更新
    
    @pytest.mark.unit
    def test_create_content_source(self, project_manager, sample_project, sample_project_structure):
        """测试创建内容源"""
        video_file = str(Path(sample_project_structure["video_dir"]) / "video_01.mp4")
        
        content_source = project_manager.create_content_source(
            project_id=sample_project.id,
            file_path=video_file,
            metadata_path=sample_project_structure["metadata_file"]
        )
        
        assert content_source is not None
        assert content_source.project_id == sample_project.id
        assert content_source.file_path == video_file
        assert content_source.file_type == "video"
        assert content_source.metadata_path == sample_project_structure["metadata_file"]
        assert content_source.file_size > 0
    
    @pytest.mark.unit
    def test_create_publishing_task(self, project_manager, sample_content_source):
        """测试创建发布任务"""
        task = project_manager.create_publishing_task(
            content_source_id=sample_content_source.id,
            project_id=sample_content_source.project_id
        )
        
        assert task is not None
        assert task.content_source_id == sample_content_source.id
        assert task.project_id == sample_content_source.project_id
        assert task.status == "pending"
        assert task.scheduled_time is not None
    
    @pytest.mark.unit
    def test_scan_projects_permission_error(self, project_manager, sample_user):
        """测试扫描权限错误"""
        with patch('pathlib.Path.iterdir', side_effect=PermissionError("Permission denied")):
            result = project_manager.scan_projects(
                project_root="/restricted/path",
                user_id=sample_user.id,
                language="en"
            )
            
            assert len(result) == 0  # 应该返回空结果
    
    @pytest.mark.unit
    def test_scan_projects_database_error(self, project_manager, sample_user, sample_project_structure):
        """测试数据库错误处理"""
        with patch.object(project_manager.db_session, 'commit', side_effect=Exception("Database error")):
            result = project_manager.scan_projects(
                project_root=sample_project_structure["project_root"],
                user_id=sample_user.id,
                language="en"
            )
            
            project_result = result["test_project"]
            assert project_result["status"] == "error"
            assert "database error" in project_result["errors"][0].lower()
    
    @pytest.mark.unit
    def test_file_size_calculation(self, project_manager, tmp_path):
        """测试文件大小计算"""
        test_file = tmp_path / "test_video.mp4"
        test_content = b"fake video content" * 1000  # 创建较大的文件
        test_file.write_bytes(test_content)
        
        file_size = project_manager.get_file_size(str(test_file))
        
        assert file_size == len(test_content)
        assert file_size > 0
    
    @pytest.mark.unit
    def test_file_size_nonexistent_file(self, project_manager):
        """测试不存在文件的大小计算"""
        file_size = project_manager.get_file_size("/nonexistent/file.mp4")
        
        assert file_size == 0