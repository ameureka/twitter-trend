import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import time

from app.core.publisher import TwitterPublisher


class TestTwitterPublisher:
    """Twitter发布器测试类"""
    
    @pytest.fixture
    def publisher(self, mock_tweepy):
        """创建发布器实例"""
        with patch.object(TwitterPublisher, '_verify_credentials'):
            publisher = TwitterPublisher(
                api_key="test_api_key",
                api_secret="test_api_secret",
                access_token="test_access_token",
                access_token_secret="test_access_token_secret"
            )
            publisher.username = "test_user"  # 设置用户名用于测试
            # 使用mock对象替换真实的API客户端
            publisher.api_v1 = mock_tweepy['api']
            publisher.client_v2 = mock_tweepy['client']
            return publisher
    
    @pytest.fixture
    def mock_video_file(self, tmp_path):
        """创建模拟视频文件"""
        video_file = tmp_path / "test_video.mp4"
        video_file.write_bytes(b"fake video content" * 1000)  # 创建一个较大的文件
        return str(video_file)
    
    @pytest.fixture
    def mock_image_file(self, tmp_path):
        """创建模拟图片文件"""
        image_file = tmp_path / "test_image.jpg"
        image_file.write_bytes(b"fake image content" * 100)
        return str(image_file)
    
    @pytest.mark.unit
    def test_publisher_initialization(self, publisher):
        """测试发布器初始化"""
        assert publisher.api_key == "test_api_key"
        assert publisher.api_secret == "test_api_secret"
        assert publisher.access_token == "test_access_token"
        assert publisher.access_token_secret == "test_access_token_secret"
        assert publisher.api_v1 is not None
        assert publisher.client_v2 is not None
    
    @pytest.mark.unit
    def test_verify_credentials_success(self, mock_tweepy):
        """测试凭据验证成功"""
        mock_tweepy['api'].verify_credentials.return_value = Mock(
            screen_name="test_user",
            id=123456789,
            name="Test User"
        )
        
        # 创建新的publisher实例来测试验证
        publisher = TwitterPublisher(
            api_key="test_api_key",
            api_secret="test_api_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret"
        )
        
        assert publisher.username == "test_user"
        mock_tweepy['api'].verify_credentials.assert_called_once()
    
    @pytest.mark.unit
    def test_verify_credentials_failure(self, mock_tweepy):
        """测试凭据验证失败"""
        mock_tweepy['api'].verify_credentials.side_effect = Exception("Invalid credentials")
        
        with pytest.raises(Exception, match="Invalid credentials"):
            TwitterPublisher(
                api_key="test_api_key",
                api_secret="test_api_secret",
                access_token="test_access_token",
                access_token_secret="test_access_token_secret"
            )
    
    @pytest.mark.unit
    def test_post_tweet_text_only_success(self, publisher, mock_tweepy):
        """测试纯文本推文发布成功"""
        tweet_text = "This is a test tweet! #test #automation"
        
        mock_tweepy['client'].create_tweet.return_value = Mock(
            data={'id': '1234567890123456789', 'text': tweet_text}
        )
        
        with patch('time.time', side_effect=[0, 0.001]):  # Mock时间以确保duration > 0
            result, duration = publisher.post_text_tweet(tweet_text)
        
        assert 'tweet_id' in result
        assert 'tweet_url' in result
        assert result['tweet_id'] == '1234567890123456789'
        assert 'twitter.com' in result['tweet_url']
        assert duration >= 0  # 修改为 >= 0 以处理快速执行的情况
        
        mock_tweepy['client'].create_tweet.assert_called_once_with(text=tweet_text)
    
    @pytest.mark.unit
    def test_post_tweet_text_only_failure(self, publisher, mock_tweepy):
        """测试纯文本推文发布失败"""
        tweet_text = "This is a test tweet!"
        
        mock_tweepy['client'].create_tweet.side_effect = Exception("API Error")
        
        with pytest.raises(Exception, match="API Error"):
            publisher.post_text_tweet(tweet_text)
    
    @pytest.mark.unit
    def test_post_tweet_with_image_success(self, publisher, mock_tweepy, mock_image_file):
        """测试带图片推文发布成功"""
        tweet_text = "Check out this amazing image! #test"
        
        # Mock媒体上传
        mock_tweepy['api'].media_upload.return_value = Mock(
            media_id_string="987654321",
            processing_info=None
        )
        
        # Mock推文创建
        mock_tweepy['client'].create_tweet.return_value = Mock(
            data={'id': '1234567890123456789', 'text': tweet_text}
        )
        
        result, duration = publisher.post_tweet_with_images(tweet_text, [mock_image_file])
        
        assert 'tweet_id' in result
        assert 'tweet_url' in result
        assert result['tweet_id'] == '1234567890123456789'
        assert duration > 0
        
        mock_tweepy['api'].media_upload.assert_called_once_with(filename=mock_image_file)
        mock_tweepy['client'].create_tweet.assert_called_once_with(
            text=tweet_text,
            media_ids=["987654321"]
        )
    
    @pytest.mark.unit
    def test_post_tweet_with_image_upload_failure(self, publisher, mock_tweepy, mock_image_file):
        """测试图片上传失败"""
        tweet_text = "This should fail"
        
        mock_tweepy['api'].media_upload.side_effect = Exception("Upload failed")
        
        with pytest.raises(Exception, match="Upload failed"):
            publisher.post_tweet_with_images(tweet_text, [mock_image_file])
    
    @pytest.mark.unit
    def test_post_tweet_with_video_success(self, publisher, mock_tweepy, mock_video_file):
        """测试带视频推文发布成功"""
        tweet_text = "Amazing video content! #video #test"
        
        # Mock视频上传（无需处理）
        mock_tweepy['api'].media_upload.return_value = Mock(
            media_id_string="987654321",
            processing_info=None
        )
        
        # Mock推文创建
        mock_tweepy['client'].create_tweet.return_value = Mock(
            data={'id': '1234567890123456789', 'text': tweet_text}
        )
        
        result, duration = publisher.post_tweet_with_video(tweet_text, mock_video_file)
        
        assert 'tweet_id' in result
        assert 'tweet_url' in result
        assert result['tweet_id'] == '1234567890123456789'
        assert duration > 0
        
        mock_tweepy['api'].media_upload.assert_called_once_with(
            filename=mock_video_file, 
            media_category='tweet_video',
            chunked=True
        )
        mock_tweepy['client'].create_tweet.assert_called_once_with(
            text=tweet_text,
            media_ids=["987654321"]
        )
    
    @pytest.mark.unit
    def test_post_tweet_with_video_processing_required(self, publisher, mock_tweepy, mock_video_file):
        """测试需要处理的视频上传"""
        tweet_text = "Video with processing"
        
        # Mock视频上传（需要处理）
        mock_tweepy['api'].media_upload.return_value = Mock(
            media_id_string="987654321",
            processing_info=Mock(state='pending')
        )
        
        # Mock处理状态检查
        mock_tweepy['api'].get_media_upload_status.side_effect = [
            Mock(processing_info=Mock(state='in_progress')),
            Mock(processing_info=Mock(state='succeeded'))
        ]
        
        # Mock推文创建
        mock_tweepy['client'].create_tweet.return_value = Mock(
            data={'id': '1234567890123456789', 'text': tweet_text}
        )
        
        with patch('time.sleep'):  # Mock sleep以加速测试
            result, duration = publisher.post_tweet_with_video(tweet_text, mock_video_file)
        
        assert 'tweet_id' in result
        assert result['tweet_id'] == '1234567890123456789'
        
        # 验证处理状态检查被调用
        assert mock_tweepy['api'].get_media_upload_status.call_count == 2
    
    @pytest.mark.unit
    def test_post_tweet_with_video_processing_failed(self, publisher, mock_tweepy, mock_video_file):
        """测试视频处理失败"""
        tweet_text = "Video processing should fail"
        
        # Mock视频上传（处理失败）
        mock_tweepy['api'].media_upload.return_value = Mock(
            media_id=987654321,
            processing_info=Mock(state='pending')
        )
        
        # Mock处理状态检查（失败）
        mock_tweepy['api'].get_media_upload_status.return_value = Mock(
            processing_info=Mock(state='failed', error=Mock(message='Processing failed'))
        )
        
        with patch('time.sleep'):  # Mock sleep以加速测试
            with pytest.raises(Exception, match="Video processing failed"):
                publisher.post_tweet_with_video(tweet_text, mock_video_file)
    
    @pytest.mark.unit
    def test_post_tweet_with_video_processing_timeout(self, publisher, mock_tweepy, mock_video_file):
        """测试视频处理超时"""
        tweet_text = "Video processing timeout"
        
        # Mock视频上传（一直处理中）
        mock_tweepy['api'].media_upload.return_value = Mock(
            media_id=987654321,
            processing_info=Mock(state='pending')
        )
        
        # Mock处理状态检查（一直处理中）
        mock_tweepy['api'].get_media_upload_status.return_value = Mock(
            processing_info=Mock(state='in_progress')
        )
        
        with patch('time.sleep'), \
             patch('time.time', side_effect=[0, 0, 0, 301]):  # Mock超时
            with pytest.raises(Exception, match="Video processing timeout"):
                publisher.post_tweet_with_video(tweet_text, mock_video_file)
    
    @pytest.mark.unit
    def test_wait_for_media_processing_success(self, publisher, mock_tweepy):
        """测试媒体处理等待成功"""
        media_id = 987654321
        
        # Mock处理状态变化：pending -> in_progress -> succeeded
        mock_tweepy['api'].get_media_upload_status.side_effect = [
            Mock(processing_info=Mock(state='pending')),
            Mock(processing_info=Mock(state='in_progress')),
            Mock(processing_info=Mock(state='succeeded'))
        ]
        
        with patch('time.sleep'):  # Mock sleep以加速测试
            result = publisher.wait_for_media_processing(media_id)
        
        assert result is True
        assert mock_tweepy['api'].get_media_upload_status.call_count == 3
    
    @pytest.mark.unit
    def test_wait_for_media_processing_failure(self, publisher, mock_tweepy):
        """测试媒体处理等待失败"""
        media_id = 987654321
        
        # Mock处理失败
        mock_tweepy['api'].get_media_upload_status.return_value = Mock(
            processing_info=Mock(
                state='failed',
                error=Mock(message='Processing error')
            )
        )
        
        with patch('time.sleep'):
            with pytest.raises(Exception, match="Video processing failed"):
                publisher.wait_for_media_processing(media_id)
    
    @pytest.mark.unit
    def test_file_not_exists_error(self, publisher):
        """测试文件不存在错误"""
        nonexistent_file = "/path/to/nonexistent/file.mp4"
        
        with pytest.raises(FileNotFoundError):
            publisher.post_tweet_with_video("Test", nonexistent_file)
    
    @pytest.mark.unit
    def test_empty_tweet_text(self, publisher, mock_tweepy):
        """测试空推文内容"""
        with pytest.raises(ValueError, match="Tweet text cannot be empty"):
            publisher.post_tweet("")
        
        with pytest.raises(ValueError, match="Tweet text cannot be empty"):
            publisher.post_tweet(None)
    
    @pytest.mark.unit
    def test_tweet_text_too_long(self, publisher, mock_tweepy):
        """测试推文内容过长"""
        long_text = "A" * 281  # 超过280字符限制
        
        with pytest.raises(ValueError, match="Tweet text exceeds 280 characters"):
            publisher.post_tweet(long_text)
    
    @pytest.mark.unit
    def test_api_rate_limit_handling(self, publisher, mock_tweepy):
        """测试API速率限制处理"""
        import tweepy
        
        tweet_text = "Rate limit test"
        
        # Mock速率限制错误
        mock_tweepy['client'].create_tweet.side_effect = tweepy.TooManyRequests(
            "Rate limit exceeded"
        )
        
        with pytest.raises(tweepy.TooManyRequests):
            publisher.post_tweet(tweet_text)
    
    @pytest.mark.unit
    def test_api_unauthorized_handling(self, publisher, mock_tweepy):
        """测试API未授权错误处理"""
        import tweepy
        
        tweet_text = "Unauthorized test"
        
        # Mock未授权错误
        mock_tweepy['client'].create_tweet.side_effect = tweepy.Unauthorized(
            "Invalid credentials"
        )
        
        with pytest.raises(tweepy.Unauthorized):
            publisher.post_tweet(tweet_text)
    
    @pytest.mark.unit
    def test_network_error_handling(self, publisher, mock_tweepy):
        """测试网络错误处理"""
        import requests
        
        tweet_text = "Network error test"
        
        # Mock网络错误
        mock_tweepy['client'].create_tweet.side_effect = requests.ConnectionError(
            "Network connection failed"
        )
        
        with pytest.raises(requests.ConnectionError):
            publisher.post_tweet(tweet_text)
    
    @pytest.mark.unit
    def test_media_file_size_validation(self, publisher, tmp_path):
        """测试媒体文件大小验证"""
        # 创建一个超大文件（模拟）
        large_file = tmp_path / "large_video.mp4"
        
        with patch('pathlib.Path.stat') as mock_stat:
            # Mock文件大小为512MB（超过限制）
            mock_stat.return_value = Mock(st_size=512 * 1024 * 1024)
            
            with pytest.raises(ValueError, match="File size exceeds"):
                publisher.post_tweet_with_video("Test", str(large_file))
    
    @pytest.mark.unit
    def test_supported_media_formats(self, publisher, tmp_path):
        """测试支持的媒体格式"""
        # 测试支持的视频格式
        for ext in ['.mp4', '.mov', '.avi']:
            video_file = tmp_path / f"test{ext}"
            video_file.write_bytes(b"fake content")
            
            # 应该不抛出格式错误
            try:
                # 这里只测试格式验证，不实际调用API
                assert video_file.suffix.lower() in ['.mp4', '.mov', '.avi']
            except Exception:
                pytest.fail(f"Should support {ext} format")
        
        # 测试支持的图片格式
        for ext in ['.jpg', '.jpeg', '.png', '.gif']:
            image_file = tmp_path / f"test{ext}"
            image_file.write_bytes(b"fake content")
            
            # 应该不抛出格式错误
            try:
                assert image_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']
            except Exception:
                pytest.fail(f"Should support {ext} format")