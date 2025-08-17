# app/core/publisher.py

import time
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config
from app.utils.path_manager import get_path_manager
from app.utils.dynamic_path_manager import get_dynamic_path_manager

try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    tweepy = None

logger = get_logger(__name__)

class TwitterPublisher:
    def __init__(self, api_key: str, api_secret: str, access_token: str, access_token_secret: str):
        if not TWEEPY_AVAILABLE:
            raise ImportError("tweepy库未安装，请运行: pip install tweepy")
            
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        
        # 初始化路径管理器
        self.path_manager = get_path_manager()
        self.dynamic_path_manager = get_dynamic_path_manager()
        
        # 初始化Twitter API客户端
        try:
            # Twitter API v2 客户端
            self.client_v2 = tweepy.Client(
                consumer_key=api_key,
                consumer_secret=api_secret,
                access_token=access_token,
                access_token_secret=access_token_secret,
                wait_on_rate_limit=True
            )
            
            # Twitter API v1.1 用于媒体上传
            auth = tweepy.OAuth1UserHandler(
                api_key, api_secret, access_token, access_token_secret
            )
            self.api_v1 = tweepy.API(auth, wait_on_rate_limit=True)
            
            # 验证凭据
            self._verify_credentials()
            logger.info("Twitter API初始化成功")
            
        except Exception as e:
            logger.error(f"Twitter API初始化失败: {e}")
            raise

    def _verify_credentials(self):
        """验证Twitter API凭据"""
        try:
            user = self.api_v1.verify_credentials()
            if user:
                logger.info(f"Twitter API验证成功，用户: @{user.screen_name}")
                self.username = user.screen_name
            else:
                raise Exception("凭据验证失败")
        except Exception as e:
            logger.error(f"Twitter API凭据验证失败: {e}")
            raise

    def post_tweet_with_video(self, text: str, video_path: str) -> tuple[Dict[str, Any], int]:
        """上传视频并发布推文。返回(推文信息, 上传耗时毫秒)"""
        start_time = time.time()
        
        # 详细调试日志
        logger.info(f"[PUBLISHER_DEBUG] 开始发布推文")
        logger.info(f"[PUBLISHER_DEBUG] 推文内容: {text}")
        logger.info(f"[PUBLISHER_DEBUG] 视频路径: {video_path}")
        
        if not os.path.exists(video_path):
            logger.error(f"[PUBLISHER_DEBUG] 视频文件不存在: {video_path}")
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
            
        # 检查文件大小（Twitter视频限制512MB）
        file_size = os.path.getsize(video_path)
        max_size = 512 * 1024 * 1024  # 512MB
        logger.info(f"[PUBLISHER_DEBUG] 视频文件大小: {file_size / (1024*1024):.1f}MB")
        
        if file_size > max_size:
            logger.error(f"[PUBLISHER_DEBUG] 视频文件过大: {file_size / (1024*1024):.1f}MB，最大支持512MB")
            raise ValueError(f"视频文件过大: {file_size / (1024*1024):.1f}MB，最大支持512MB")
            
        logger.info(f"[PUBLISHER_DEBUG] 开始上传视频: {os.path.basename(video_path)} ({file_size / (1024*1024):.1f}MB)")
        
        try:
            # 使用动态路径管理器验证和解析视频路径
            validation_result = self.dynamic_path_manager.validate_media_file(video_path)
            logger.info(f"[PUBLISHER_DEBUG] 媒体文件验证结果: {validation_result}")
            
            if validation_result['is_hardcoded']:
                logger.warning(f"[PUBLISHER_DEBUG] 检测到硬编码路径: {video_path}")
                logger.info(f"[PUBLISHER_DEBUG] 转换为相对路径: {validation_result['converted_path']}")
            
            if not validation_result['exists']:
                error_msg = f"视频文件不存在: {validation_result['resolved_path']} (原路径: {video_path})"
                if validation_result['error']:
                    error_msg += f", 错误: {validation_result['error']}"
                logger.error(f"[PUBLISHER_DEBUG] {error_msg}")
                
                # 尝试通过文件名查找视频文件
                filename = os.path.basename(video_path)
                found_file = self.dynamic_path_manager.find_media_file(filename)
                
                if found_file:
                    logger.info(f"[PUBLISHER_DEBUG] 通过文件名找到视频文件: {found_file}")
                    normalized_path = found_file
                else:
                    raise FileNotFoundError(error_msg)
            else:
                # 使用验证通过的路径
                normalized_path = self.dynamic_path_manager.resolve_media_path(video_path)
                
            logger.info(f"[PUBLISHER_DEBUG] 最终使用路径: {normalized_path}")
            
            # 1. 上传媒体文件
            logger.info(f"[PUBLISHER_DEBUG] 开始调用Twitter API上传媒体")
            logger.info(f"[PUBLISHER_DEBUG] API参数 - filename: {str(normalized_path)}")
            logger.info(f"[PUBLISHER_DEBUG] API参数 - media_category: tweet_video")
            logger.info(f"[PUBLISHER_DEBUG] API参数 - chunked: True")
            
            media = self.api_v1.media_upload(
                filename=str(normalized_path),
                media_category='tweet_video',
                chunked=True  # 使用分块上传处理大文件
            )
            media_id = media.media_id_string
            logger.info(f"[PUBLISHER_DEBUG] 视频上传完成，media_id: {media_id}")
            
            # 2. 等待媒体处理完成
            logger.info(f"[PUBLISHER_DEBUG] 等待媒体处理完成")
            self._wait_for_media_processing(media_id)
            logger.info(f"[PUBLISHER_DEBUG] 媒体处理完成")
            
            # 3. 发布推文
            logger.info(f"[PUBLISHER_DEBUG] 开始调用Twitter API发布推文")
            logger.info(f"[PUBLISHER_DEBUG] 推文文本: {text}")
            logger.info(f"[PUBLISHER_DEBUG] 媒体ID: {media_id}")
            
            response = self.client_v2.create_tweet(
                text=text,
                media_ids=[media_id]
            )
            
            logger.info(f"[PUBLISHER_DEBUG] Twitter API响应: {response}")
            
            tweet_data = response.data
            tweet_info = {
                "tweet_id": tweet_data['id'],
                "tweet_url": f"https://twitter.com/{self.username}/status/{tweet_data['id']}",
                "text": text
            }
            
            upload_time = int((time.time() - start_time) * 1000)
            logger.info(f"[PUBLISHER_DEBUG] 推文发布成功，耗时: {upload_time}ms，URL: {tweet_info['tweet_url']}")
            logger.info(f"[PUBLISHER_DEBUG] 推文信息: {tweet_info}")
            
            return tweet_info, upload_time
            
        except tweepy.TooManyRequests as e:
            logger.error(f"API速率限制: {e}")
            raise
        except tweepy.Forbidden as e:
            logger.error(f"API权限错误: {e}")
            raise
        except tweepy.Unauthorized as e:
            logger.error(f"API认证错误: {e}")
            raise
        except Exception as e:
            logger.error(f"发布推文失败: {e}")
            raise

    def post_tweet_with_images(self, text: str, image_paths: list) -> tuple[Dict[str, Any], int]:
        """上传图片并发布推文。返回(推文信息, 上传耗时毫秒)"""
        start_time = time.time()
        
        if len(image_paths) > 4:
            raise ValueError("Twitter最多支持4张图片")
            
        media_ids = []
        
        try:
            # 上传所有图片
            for image_path in image_paths:
                # 验证并标准化图片路径
                if not self._validate_media_file(image_path):
                    raise FileNotFoundError(f"图片文件验证失败: {image_path}")
                
                normalized_path = self.path_manager.normalize_path(image_path)
                media = self.api_v1.media_upload(filename=str(normalized_path))
                media_ids.append(media.media_id_string)
                logger.info(f"图片上传完成: {normalized_path.name}")
            
            # 发布推文
            response = self.client_v2.create_tweet(
                text=text,
                media_ids=media_ids
            )
            
            tweet_data = response.data
            tweet_info = {
                "tweet_id": tweet_data['id'],
                "tweet_url": f"https://twitter.com/{self.username}/status/{tweet_data['id']}",
                "text": text
            }
            
            upload_time = int((time.time() - start_time) * 1000)
            logger.info(f"图片推文发布成功，耗时: {upload_time}ms")
            
            return tweet_info, upload_time
            
        except Exception as e:
            logger.error(f"发布图片推文失败: {e}")
            raise

    def post_text_tweet(self, text: str) -> tuple[Dict[str, Any], int]:
        """发布纯文本推文。返回(推文信息, 发布耗时毫秒)"""
        start_time = time.time()
        
        try:
            response = self.client_v2.create_tweet(text=text)
            
            tweet_data = response.data
            tweet_info = {
                "tweet_id": tweet_data['id'],
                "tweet_url": f"https://twitter.com/{self.username}/status/{tweet_data['id']}",
                "text": text
            }
            
            publish_time = int((time.time() - start_time) * 1000)
            logger.info(f"文本推文发布成功，耗时: {publish_time}ms")
            
            return tweet_info, publish_time
            
        except Exception as e:
            logger.error(f"发布文本推文失败: {e}")
            raise

    def _wait_for_media_processing(self, media_id: str, max_wait_time: int = 300):
        """等待媒体处理完成"""
        start_time = time.time()
        
        while True:
            try:
                media = self.api_v1.get_media_upload_status(media_id)
                
                if not hasattr(media, 'processing_info'):
                    # 没有处理信息，说明已经完成
                    logger.info("媒体处理完成")
                    break
                    
                processing_info = media.processing_info
                state = processing_info.get('state')
                
                if state == 'succeeded':
                    logger.info("媒体处理成功")
                    break
                elif state == 'failed':
                    error_msg = processing_info.get('error', {}).get('message', '未知错误')
                    raise Exception(f"Twitter媒体处理失败: {error_msg}")
                elif state == 'in_progress':
                    check_after = processing_info.get('check_after_secs', 5)
                    logger.info(f"媒体处理中，{check_after}秒后重试...")
                    time.sleep(check_after)
                else:
                    logger.warning(f"未知的处理状态: {state}")
                    time.sleep(5)
                    
                # 检查超时
                if time.time() - start_time > max_wait_time:
                    raise Exception(f"媒体处理超时（{max_wait_time}秒）")
                    
            except Exception as e:
                if "媒体处理" in str(e):
                    raise
                logger.warning(f"检查媒体状态时出错: {e}，继续等待...")
                time.sleep(5)

    def _validate_media_file(self, file_path: str) -> bool:
        """验证媒体文件"""
        try:
            # 使用动态路径管理器验证媒体文件
            validation_result = self.dynamic_path_manager.validate_media_file(file_path)
            
            if validation_result['is_hardcoded']:
                logger.warning(f"检测到硬编码路径: {file_path}")
                logger.info(f"转换为相对路径: {validation_result['converted_path']}")
            
            if validation_result['error']:
                logger.error(f"媒体文件验证错误: {validation_result['error']}")
                return False
            
            if not validation_result['exists']:
                logger.error(f"媒体文件不存在: {validation_result['resolved_path']} (原路径: {file_path})")
                
                # 尝试通过文件名查找媒体文件
                filename = os.path.basename(file_path)
                found_file = self.dynamic_path_manager.find_media_file(filename)
                
                if found_file:
                    logger.info(f"通过文件名找到媒体文件: {found_file}")
                    # 重新验证找到的文件
                    return self._validate_media_file(str(found_file))
                else:
                    return False
            
            if not validation_result['readable']:
                logger.error(f"媒体文件不可读: {validation_result['resolved_path']}")
                return False
            
            file_size = validation_result['size']
            if file_size == 0:
                logger.error(f"媒体文件为空: {validation_result['resolved_path']}")
                return False
            
            # 检查文件大小限制
            max_size = 512 * 1024 * 1024  # 512MB
            if file_size > max_size:
                logger.error(f"媒体文件过大: {validation_result['resolved_path']} ({file_size / 1024 / 1024:.1f}MB)")
                return False
            
            logger.debug(f"媒体文件验证通过: {file_path} -> {validation_result['resolved_path']}")
            return True
            
        except Exception as e:
            logger.error(f"验证媒体文件失败 {file_path}: {e}")
            return False

    def _get_media_type(self, file_path: str) -> str:
        """获取媒体文件类型"""
        try:
            path = Path(file_path)
            ext = path.suffix.lower()
            
            video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
            
            if ext in video_extensions:
                return 'video'
            elif ext in image_extensions:
                return 'image'
            else:
                return 'unknown'
                
        except Exception as e:
            logger.error(f"获取媒体类型失败 {file_path}: {e}")
            return 'unknown'

    def check_api_limits(self) -> Dict[str, Any]:
        """检查API限制状态"""
        try:
            # 获取速率限制状态
            limits = self.api_v1.get_rate_limit_status()
            
            # 提取关键限制信息
            tweet_limit = limits['resources']['statuses']['/statuses/update']
            media_limit = limits['resources']['media']['/media/upload']
            
            return {
                'tweet_remaining': tweet_limit['remaining'],
                'tweet_reset_time': tweet_limit['reset'],
                'media_remaining': media_limit['remaining'],
                'media_reset_time': media_limit['reset']
            }
        except Exception as e:
            logger.error(f"获取API限制状态失败: {e}")
            return {}