import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from app.core.content_generator import ContentGenerator


class TestContentGenerator:
    """内容生成器测试类"""
    
    @pytest.fixture
    def content_generator(self):
        """创建内容生成器实例"""
        return ContentGenerator()
    
    @pytest.fixture
    def sample_video_info(self):
        """示例视频信息"""
        return {
            "filename": "test_video_01.mp4",
            "title": "Amazing Test Video",
            "description": "This is a comprehensive test video showcasing various features and capabilities.",
            "tags": ["test", "video", "automation"],
            "duration": 45,
            "size_mb": 8.5
        }
    
    @pytest.fixture
    def sample_metadata(self):
        """示例元数据"""
        return {
            "batch_info": {
                "total_videos": 2,
                "language": "en",
                "created_at": "2024-01-01T00:00:00Z"
            },
            "videos": [
                {
                    "filename": "test_video_01.mp4",
                    "title": "First Test Video",
                    "description": "Description for first video",
                    "tags": ["test", "first"]
                },
                {
                    "filename": "test_video_02.mp4",
                    "title": "Second Test Video",
                    "description": "Description for second video",
                    "tags": ["test", "second"]
                }
            ]
        }
    
    @pytest.mark.unit
    def test_extract_content_info_from_json_success(self, content_generator, sample_metadata, tmp_path):
        """测试从JSON成功提取内容信息"""
        # 创建临时JSON文件
        json_file = tmp_path / "test_metadata.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(sample_metadata, f)
        
        # 测试提取第一个视频信息
        result = content_generator.extract_content_info_from_json(
            str(json_file), "test_video_01.mp4"
        )
        
        assert result is not None
        assert result["filename"] == "test_video_01.mp4"
        assert result["title"] == "First Test Video"
        assert result["description"] == "Description for first video"
        assert "test" in result["tags"]
        assert "first" in result["tags"]
    
    @pytest.mark.unit
    def test_extract_content_info_from_json_file_not_found(self, content_generator):
        """测试JSON文件不存在的情况"""
        result = content_generator.extract_content_info_from_json(
            "/nonexistent/path.json", "test_video.mp4"
        )
        assert result is None
    
    @pytest.mark.unit
    def test_extract_content_info_from_json_invalid_json(self, content_generator, tmp_path):
        """测试无效JSON文件"""
        # 创建无效JSON文件
        json_file = tmp_path / "invalid.json"
        json_file.write_text("invalid json content")
        
        result = content_generator.extract_content_info_from_json(
            str(json_file), "test_video.mp4"
        )
        assert result is None
    
    @pytest.mark.unit
    def test_extract_content_info_from_json_video_not_found(self, content_generator, sample_metadata, tmp_path):
        """测试视频在JSON中不存在"""
        json_file = tmp_path / "test_metadata.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(sample_metadata, f)
        
        result = content_generator.extract_content_info_from_json(
            str(json_file), "nonexistent_video.mp4"
        )
        assert result is None
    
    @pytest.mark.unit
    def test_apply_source_config_default(self, content_generator, sample_video_info):
        """测试应用默认源配置"""
        config = {}
        result = content_generator.apply_source_config(sample_video_info, config)
        
        # 默认配置应该保持原始信息不变
        assert result["title"] == sample_video_info["title"]
        assert result["description"] == sample_video_info["description"]
        assert result["tags"] == sample_video_info["tags"]
    
    @pytest.mark.unit
    def test_apply_source_config_with_overrides(self, content_generator, sample_video_info):
        """测试应用自定义源配置"""
        config = {
            "title_prefix": "[TEST] ",
            "title_suffix": " - Automated",
            "description_prefix": "Auto-generated: ",
            "additional_tags": ["automated", "generated"],
            "max_title_length": 50,
            "max_description_length": 100
        }
        
        result = content_generator.apply_source_config(sample_video_info, config)
        
        assert result["title"].startswith("[TEST] ")
        assert result["title"].endswith(" - Automated")
        assert result["description"].startswith("Auto-generated: ")
        assert "automated" in result["tags"]
        assert "generated" in result["tags"]
        assert len(result["title"]) <= 50
        assert len(result["description"]) <= 100
    
    @pytest.mark.unit
    def test_apply_source_config_title_truncation(self, content_generator):
        """测试标题截断功能"""
        long_title_info = {
            "title": "This is a very long title that exceeds the maximum length limit",
            "description": "Short description",
            "tags": ["test"]
        }
        
        config = {"max_title_length": 20}
        result = content_generator.apply_source_config(long_title_info, config)
        
        assert len(result["title"]) <= 20
        assert result["title"].endswith("...")
    
    @pytest.mark.unit
    def test_format_tweet_english(self, content_generator, sample_video_info):
        """测试英文推文格式化"""
        result = content_generator.format_tweet(sample_video_info, "en")
        
        assert isinstance(result, str)
        assert len(result) <= 280  # Twitter字符限制
        assert sample_video_info["title"] in result
        assert "#test" in result
        assert "#video" in result
        assert "#automation" in result
    
    @pytest.mark.unit
    def test_format_tweet_chinese(self, content_generator):
        """测试中文推文格式化"""
        chinese_info = {
            "title": "测试视频标题",
            "description": "这是一个测试视频的描述",
            "tags": ["测试", "视频"]
        }
        
        result = content_generator.format_tweet(chinese_info, "zh")
        
        assert isinstance(result, str)
        assert len(result) <= 280
        assert "🎬" in result  # 中文前缀
        assert "测试视频标题" in result
        assert "#测试" in result
        assert "#视频" in result
    
    @pytest.mark.unit
    def test_format_tweet_character_limit(self, content_generator):
        """测试推文字符限制"""
        long_content_info = {
            "title": "A" * 200,  # 很长的标题
            "description": "B" * 200,  # 很长的描述
            "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
        }
        
        result = content_generator.format_tweet(long_content_info, "en")
        
        assert len(result) <= 280
        assert "..." in result  # 应该有截断标记
    
    @pytest.mark.unit
    def test_generate_content_direct_mode(self, content_generator, sample_metadata, tmp_path):
        """测试直接模式内容生成"""
        # 创建临时JSON文件
        json_file = tmp_path / "test_metadata.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(sample_metadata, f)
        
        result = content_generator.generate_content(
            video_filename="test_video_01.mp4",
            metadata_path=str(json_file),
            language="en",
            use_ai_enhancement=False
        )
        
        assert result is not None
        assert isinstance(result, str)
        assert len(result) <= 280
        assert "First Test Video" in result
    
    @pytest.mark.unit
    def test_generate_content_ai_enhanced_mode(self, content_generator, sample_metadata, tmp_path, mock_gemini):
        """测试AI增强模式内容生成"""
        # 创建临时JSON文件
        json_file = tmp_path / "test_metadata.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(sample_metadata, f)
        
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel', return_value=mock_gemini):
            
            result = content_generator.generate_content(
                video_filename="test_video_01.mp4",
                metadata_path=str(json_file),
                language="en",
                use_ai_enhancement=True,
                gemini_api_key="test_api_key"
            )
        
        assert result is not None
        assert isinstance(result, str)
        assert len(result) <= 280
        # 应该包含AI生成的内容
        assert "Enhanced tweet content" in result or "AI magic" in result
    
    @pytest.mark.unit
    def test_generate_content_ai_enhancement_failure(self, content_generator, sample_metadata, tmp_path):
        """测试AI增强失败时的降级处理"""
        json_file = tmp_path / "test_metadata.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(sample_metadata, f)
        
        # Mock AI调用失败
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            mock_model = Mock()
            mock_model.generate_content.side_effect = Exception("API Error")
            mock_model_class.return_value = mock_model
            
            result = content_generator.generate_content(
                video_filename="test_video_01.mp4",
                metadata_path=str(json_file),
                language="en",
                use_ai_enhancement=True,
                gemini_api_key="test_api_key"
            )
        
        # 应该降级到直接模式
        assert result is not None
        assert isinstance(result, str)
        assert "First Test Video" in result
    
    @pytest.mark.unit
    def test_generate_content_missing_metadata(self, content_generator):
        """测试元数据文件缺失的情况"""
        result = content_generator.generate_content(
            video_filename="test_video.mp4",
            metadata_path="/nonexistent/path.json",
            language="en"
        )
        
        assert result is None
    
    @pytest.mark.unit
    def test_generate_content_empty_config(self, content_generator, sample_metadata, tmp_path):
        """测试空配置的内容生成"""
        json_file = tmp_path / "test_metadata.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(sample_metadata, f)
        
        result = content_generator.generate_content(
            video_filename="test_video_01.mp4",
            metadata_path=str(json_file),
            language="en",
            source_config={}
        )
        
        assert result is not None
        assert "First Test Video" in result
    
    @pytest.mark.unit
    def test_hashtag_formatting(self, content_generator):
        """测试标签格式化"""
        info = {
            "title": "Test Video",
            "description": "Test description",
            "tags": ["test tag", "multi word", "special-chars!", "normal"]
        }
        
        result = content_generator.format_tweet(info, "en")
        
        # 检查标签格式化
        assert "#testtag" in result or "#test_tag" in result
        assert "#multiword" in result or "#multi_word" in result
        assert "#normal" in result
        # 特殊字符应该被处理
        assert "#special-chars!" not in result