# app/core/content_generator.py

import json
import os
import time
from typing import Dict, Any
from app.utils.logger import get_logger

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

logger = get_logger(__name__)

class ContentGenerator:
    def __init__(self, use_ai: bool = False, gemini_api_key: str = None):
        self.use_ai = use_ai and GEMINI_AVAILABLE
        
        if self.use_ai:
            if not gemini_api_key:
                logger.warning("未提供Gemini API密钥，将使用直接模式生成内容")
                self.use_ai = False
            else:
                try:
                    genai.configure(api_key=gemini_api_key)
                    self.model = genai.GenerativeModel('gemini-pro')
                    logger.info("Gemini AI模式已启用")
                except Exception as e:
                    logger.error(f"初始化Gemini失败: {e}")
                    self.use_ai = False
        
        if not self.use_ai:
            logger.info("使用直接模式生成内容")

    def generate_tweet(self, metadata_path: str, video_filename: str, language: str = 'en', 
                      content_source_type: str = 'video', content_source_config: Dict[str, Any] = None) -> tuple[str, int]:
        """从元数据文件生成推文。返回(推文内容, 生成耗时毫秒)"""
        start_time = time.time()
        
        # 详细调试日志
        logger.info(f"[CONTENT_GEN_DEBUG] 开始生成推文内容")
        logger.info(f"[CONTENT_GEN_DEBUG] 参数: metadata_path={metadata_path}")
        logger.info(f"[CONTENT_GEN_DEBUG] 参数: video_filename={video_filename}")
        logger.info(f"[CONTENT_GEN_DEBUG] 参数: language={language}")
        logger.info(f"[CONTENT_GEN_DEBUG] 参数: content_source_type={content_source_type}")
        logger.info(f"[CONTENT_GEN_DEBUG] 参数: content_source_config={content_source_config}")
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"[CONTENT_GEN_DEBUG] 成功读取元数据文件，数据键: {list(data.keys())}")
        except Exception as e:
            logger.error(f"[CONTENT_GEN_DEBUG] 读取元数据文件失败 {metadata_path}: {e}")
            raise ValueError(f"无法读取元数据文件: {e}")
        
        # 查找内容信息（支持不同类型的内容源）
        content_info = self._extract_content_info(data, video_filename, content_source_type)
        
        if not content_info:
            raise ValueError(f"在 {metadata_path} 中未找到 {video_filename} 的元数据")

        # 应用内容源特定的配置
        if content_source_config:
            content_info = self._apply_content_source_config(content_info, content_source_config)

        logger.info(f"[CONTENT_GEN_DEBUG] 提取的内容信息: {content_info}")
        logger.info(f"[CONTENT_GEN_DEBUG] 使用AI模式: {self.use_ai}")
        
        if self.use_ai:
            logger.info(f"[CONTENT_GEN_DEBUG] 使用Gemini AI生成内容")
            content = self._enhance_with_gemini(content_info, language, content_source_type)
        else:
            logger.info(f"[CONTENT_GEN_DEBUG] 使用直接模式生成内容")
            content = self._generate_from_json_directly(content_info, language, content_source_type)
            
        generation_time = int((time.time() - start_time) * 1000)
        logger.info(f"[CONTENT_GEN_DEBUG] 生成的推文内容: {content}")
        logger.info(f"[CONTENT_GEN_DEBUG] 内容生成完成，耗时: {generation_time}ms")
        
        return content, generation_time
    
    def generate_tweet_from_data(self, content_data: Dict[str, Any], media_filename: str, language: str = 'en', 
                                content_source_type: str = 'video', content_source_config: Dict[str, Any] = None) -> tuple[str, int]:
        """直接从content_data生成推文。返回(推文内容, 生成耗时毫秒)"""
        start_time = time.time()
        
        # 直接使用content_data作为content_info
        content_info = content_data.copy()
        
        # 应用内容源特定的配置
        if content_source_config:
            content_info = self._apply_content_source_config(content_info, content_source_config)

        if self.use_ai:
            content = self._enhance_with_gemini(content_info, language, content_source_type)
        else:
            content = self._generate_from_json_directly(content_info, language, content_source_type)
            
        generation_time = int((time.time() - start_time) * 1000)
        logger.info(f"内容生成完成，耗时: {generation_time}ms")
        
        return content, generation_time

    def extract_content_info_from_json(self, json_path: str, video_filename: str, language: str = 'en') -> Dict[str, Any] or None:
        """从JSON文件中提取指定视频的内容信息"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"读取JSON文件失败 {json_path}: {e}")
            return None
        
        # 获取视频ID（不含扩展名）
        video_id = os.path.splitext(video_filename)[0]
        
        # 检查是否是综合报告文件格式（包含results数组）
        if 'results' in data and isinstance(data['results'], list):
            for result in data['results']:
                if result.get('video_id') == video_id:
                    # 从markdown_content中提取信息
                    return self._extract_from_markdown_content(result, language)
        
        # 查找视频信息（原有格式）
        if 'videos' in data:
            for video in data['videos']:
                if video.get('filename') == video_filename:
                    return video
        
        # 直接查找
        return self._extract_content_info(data, video_filename)

    def _extract_from_markdown_content(self, result: Dict[str, Any], language: str = 'en') -> Dict[str, Any] or None:
        """从markdown内容中提取推文信息"""
        try:
            markdown_content = result.get('markdown_content', '')
            if not markdown_content:
                return None
            
            # 提取标题（从SEO优化文案部分）
            title_cn = ''
            title_en = ''
            description_cn = ''
            description_en = ''
            hashtags = []
            
            lines = markdown_content.split('\n')
            in_seo_section = False
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                # 检测SEO优化文案部分
                if '3.0 SEO优化文案' in line:
                    in_seo_section = True
                    continue
                elif in_seo_section and line.startswith('### **4.0'):
                    break
                
                if in_seo_section:
                    # 检查是否在titles部分
                    in_titles_section = False
                    in_descriptions_section = False
                    
                    # 向前查找最近的section标题
                    for j in range(i-1, -1, -1):
                        if 'titles' in lines[j].lower():
                            in_titles_section = True
                            break
                        elif 'descriptions' in lines[j].lower():
                            in_descriptions_section = True
                            break
                        elif 'hashtags' in lines[j].lower():
                            break
                    
                    # 提取中文标题
                    if '中文:' in line and in_titles_section:
                        title_cn = line.split('中文:')[1].strip()
                        # 移除hashtags部分
                        if '#' in title_cn:
                            title_cn = title_cn.split('#')[0].strip()
                    
                    # 提取英文标题
                    elif 'English:' in line and in_titles_section:
                        title_en = line.split('English:')[1].strip()
                        if '#' in title_en:
                            title_en = title_en.split('#')[0].strip()
                    
                    # 提取中文描述
                    elif '中文:' in line and in_descriptions_section:
                        description_cn = line.split('中文:')[1].strip()
                    
                    # 提取英文描述
                    elif 'English:' in line and in_descriptions_section:
                        description_en = line.split('English:')[1].strip()
                    
                    # 提取hashtags
                    elif 'hashtags' in line and '**hashtags' in line:
                        # 查找下一行的内容
                        if i + 1 < len(lines):
                            hashtag_line = lines[i + 1].strip()
                            # 提取所有hashtags
                            import re
                            hashtag_matches = re.findall(r'#\w+', hashtag_line)
                            hashtags.extend([tag.replace('#', '') for tag in hashtag_matches])
            
            # 根据language参数选择合适的title和description
            if language == 'en':
                # 英文模式：优先使用英文，如果没有则使用中文
                selected_title = title_en or title_cn
                selected_description = description_en or description_cn
            else:
                # 中文模式：优先使用中文，如果没有则使用英文
                selected_title = title_cn or title_en
                selected_description = description_cn or description_en
            
            # 构建返回的内容信息
            content_info = {
                'video_id': result.get('video_id', ''),
                'title': selected_title,
                'title_cn': title_cn,
                'title_en': title_en,
                'description': selected_description,
                'description_cn': description_cn,
                'description_en': description_en,
                'hashtags': hashtags,
                'status': result.get('status', 'unknown'),
                'processing_time': result.get('processing_time', 0)
            }
            
            return content_info
            
        except Exception as e:
            logger.error(f"从markdown内容提取信息失败: {e}")
            return None

    def apply_source_config(self, content_info: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """应用源配置到内容信息"""
        result = content_info.copy()
        
        # 处理标题
        if 'title' in result:
            title = result['title']
            if config.get('title_prefix'):
                title = config['title_prefix'] + title
            if config.get('title_suffix'):
                title = title + config['title_suffix']
            
            # 标题长度限制
            max_title_length = config.get('max_title_length')
            if max_title_length and len(title) > max_title_length:
                title = title[:max_title_length-3] + '...'
            
            result['title'] = title
        
        # 处理描述
        if 'description' in result:
            description = result['description']
            if config.get('description_prefix'):
                description = config['description_prefix'] + description
            
            # 描述长度限制
            max_desc_length = config.get('max_description_length')
            if max_desc_length and len(description) > max_desc_length:
                description = description[:max_desc_length-3] + '...'
            
            result['description'] = description
        
        # 处理标签
        if 'additional_tags' in config:
            existing_tags = result.get('tags', [])
            if isinstance(existing_tags, str):
                existing_tags = [existing_tags]
            elif not isinstance(existing_tags, list):
                existing_tags = []
            
            additional_tags = config['additional_tags']
            if isinstance(additional_tags, str):
                additional_tags = [additional_tags]
            
            result['tags'] = existing_tags + additional_tags
        
        return result

    def format_tweet(self, content_info: Dict[str, Any], language: str) -> str:
        """格式化推文内容"""
        title = content_info.get('title', '')
        description = content_info.get('description', '')
        tags = content_info.get('tags', [])
        
        # 处理标签
        if isinstance(tags, list):
            # 清理和格式化标签
            formatted_tags = []
            for tag in tags:
                if tag:
                    # 移除特殊字符，替换空格
                    clean_tag = ''.join(c for c in tag if c.isalnum() or c in ' -_')
                    clean_tag = clean_tag.replace(' ', '').replace('-', '').replace('_', '')
                    if clean_tag:
                        formatted_tags.append(f"#{clean_tag}")
            hashtag_str = ' '.join(formatted_tags)
        else:
            hashtag_str = str(tags) if tags else ''
        
        # 根据语言获取前缀
        if language == 'zh':
            prefix = '🎬 '
        elif language == 'ja':
            prefix = '🎬 '
        else:
            prefix = '🎬 '
        
        # 构建推文
        parts = []
        if prefix:
            parts.append(prefix.strip())
        
        if title:
            parts.append(title.strip())
        
        if description and description != title:
            # 计算可用空间
            used_length = len(prefix) + len(title) + len(hashtag_str) + 10  # 留一些缓冲
            available_length = 280 - used_length
            
            if available_length > 20:
                if len(description) > available_length:
                    description = description[:available_length-3] + '...'
                parts.append(description.strip())
        
        if hashtag_str:
            parts.append(hashtag_str)
        
        tweet_content = '\n\n'.join(parts).strip()
        
        # 确保不超过280字符
        if len(tweet_content) > 280:
            tweet_content = tweet_content[:277] + '...'
        
        return tweet_content

    def generate_content(self, video_filename: str, metadata_path: str, language: str = 'en', 
                        use_ai_enhancement: bool = False, gemini_api_key: str = None, 
                        source_config: Dict[str, Any] = None) -> str or None:
        """生成内容的统一接口"""
        try:
            # 提取内容信息
            content_info = self.extract_content_info_from_json(metadata_path, video_filename, language)
            if not content_info:
                return None
            
            # 应用源配置
            if source_config:
                content_info = self.apply_source_config(content_info, source_config)
            
            # 如果启用AI增强
            if use_ai_enhancement and gemini_api_key:
                # 临时启用AI模式
                original_use_ai = self.use_ai
                try:
                    if not self.use_ai:
                        genai.configure(api_key=gemini_api_key)
                        self.model = genai.GenerativeModel('gemini-pro')
                        self.use_ai = True
                    
                    return self._enhance_with_gemini(content_info, language)
                except Exception as e:
                    logger.error(f"AI增强失败，降级到直接模式: {e}")
                    return self.format_tweet(content_info, language)
                finally:
                    self.use_ai = original_use_ai
            else:
                return self.format_tweet(content_info, language)
                
        except Exception as e:
            logger.error(f"内容生成失败: {e}")
            return None

    def _extract_content_info(self, data: Dict[str, Any], filename: str, content_type: str = 'video') -> Dict[str, Any] or None:
        """从JSON数据中提取内容信息。"""
        # 尝试多种键名模式
        possible_keys = [
            filename,  # 完整文件名
            os.path.splitext(filename)[0],  # 不含扩展名
        ]
        
        for key in possible_keys:
            if key in data:
                return data[key]
                
        # 如果直接查找失败，尝试模糊匹配
        file_base = os.path.splitext(filename)[0]
        for key, value in data.items():
            if file_base in key or key in file_base:
                return value
                
        return None
    
    def _apply_content_source_config(self, content_info: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """应用内容源特定的配置。"""
        # 应用模板覆盖
        if 'title_template' in config and config['title_template']:
            content_info['title'] = config['title_template'].format(**content_info)
            
        if 'description_template' in config and config['description_template']:
            content_info['description'] = config['description_template'].format(**content_info)
            
        # 添加额外的标签
        if 'additional_hashtags' in config:
            existing_hashtags = content_info.get('hashtags', [])
            if isinstance(existing_hashtags, str):
                existing_hashtags = [existing_hashtags]
            elif not isinstance(existing_hashtags, list):
                existing_hashtags = []
                
            additional_hashtags = config['additional_hashtags']
            if isinstance(additional_hashtags, str):
                additional_hashtags = [additional_hashtags]
                
            content_info['hashtags'] = existing_hashtags + additional_hashtags
            
        return content_info

    def _generate_from_json_directly(self, info: Dict[str, Any], language: str, content_type: str = 'video') -> str:
        """直接从JSON组合推文。"""
        logger.info(f"[CONTENT_GEN_DEBUG] _generate_from_json_directly 开始")
        logger.info(f"[CONTENT_GEN_DEBUG] 输入参数 - info: {info}")
        logger.info(f"[CONTENT_GEN_DEBUG] 输入参数 - language: {language}")
        logger.info(f"[CONTENT_GEN_DEBUG] 输入参数 - content_type: {content_type}")
        
        title = info.get('title', '')
        description = info.get('description', '')
        hashtags = info.get('hashtags', [])
        keywords = info.get('keywords', [])
        
        logger.info(f"[CONTENT_GEN_DEBUG] 提取的字段 - title: {title}")
        logger.info(f"[CONTENT_GEN_DEBUG] 提取的字段 - description: {description}")
        logger.info(f"[CONTENT_GEN_DEBUG] 提取的字段 - hashtags: {hashtags}")
        logger.info(f"[CONTENT_GEN_DEBUG] 提取的字段 - keywords: {keywords}")
        
        # 处理hashtags
        if isinstance(hashtags, list):
            hashtag_str = ' '.join([f"#{tag.strip('#')}" for tag in hashtags if tag])
        else:
            hashtag_str = str(hashtags) if hashtags else ''
            
        logger.info(f"[CONTENT_GEN_DEBUG] 处理后的hashtag_str: {hashtag_str}")
            
        # 根据内容类型调整格式
        content_prefix = self._get_content_type_prefix(content_type, language)
        logger.info(f"[CONTENT_GEN_DEBUG] 获取的content_prefix: {content_prefix}")
        
        # 构建推文内容
        parts = []
        
        if content_prefix:
            parts.append(content_prefix)
        
        if title:
            parts.append(title.strip())
            
        if description and description != title:
            # 限制描述长度，为hashtags和前缀留空间
            prefix_length = len(content_prefix) + 2 if content_prefix else 0
            max_desc_length = 200 - len(title) - len(hashtag_str) - prefix_length - 10
            if len(description) > max_desc_length:
                description = description[:max_desc_length].rsplit(' ', 1)[0] + '...'
            parts.append(description.strip())
            
        if hashtag_str:
            parts.append(hashtag_str)
            
        tweet_content = '\n\n'.join(parts).strip()
        
        # 确保不超过Twitter字符限制（280字符）
        if len(tweet_content) > 280:
            # 优先保留标题和hashtags，压缩描述
            if title and hashtag_str:
                available_length = 280 - len(title) - len(hashtag_str) - prefix_length - 8
                if available_length > 20 and description:
                    compressed_desc = description[:available_length].rsplit(' ', 1)[0] + '...'
                    if content_prefix:
                        tweet_content = f"{content_prefix}\n\n{title}\n\n{compressed_desc}\n\n{hashtag_str}"
                    else:
                        tweet_content = f"{title}\n\n{compressed_desc}\n\n{hashtag_str}"
                else:
                    if content_prefix:
                        tweet_content = f"{content_prefix}\n\n{title}\n\n{hashtag_str}"
                    else:
                        tweet_content = f"{title}\n\n{hashtag_str}"
            else:
                tweet_content = tweet_content[:277] + '...'
                
        return tweet_content
    
    def _get_content_type_prefix(self, content_type: str, language: str) -> str:
        """根据内容类型和语言获取前缀。"""
        logger.info(f"[CONTENT_GEN_DEBUG] _get_content_type_prefix 调用")
        logger.info(f"[CONTENT_GEN_DEBUG] content_type: {content_type}, language: {language}")
        
        prefixes = {
            'video': {
                'en': '🎥 New Video:',
                'cn': '🎥 新视频：',
                'ja': '🎥 新しい動画：'
            },
            'article': {
                'en': '📝 Article:',
                'cn': '📝 文章：',
                'ja': '📝 記事：'
            },
            'image': {
                'en': '📸 Image:',
                'cn': '📸 图片：',
                'ja': '📸 画像：'
            },
            'audio': {
                'en': '🎵 Audio:',
                'cn': '🎵 音频：',
                'ja': '🎵 音声：'
            }
        }
        
        result = prefixes.get(content_type, {}).get(language, '')
        logger.info(f"[CONTENT_GEN_DEBUG] _get_content_type_prefix 返回: {result}")
        return result

    def _enhance_with_gemini(self, info: Dict[str, Any], language: str, content_type: str = 'video') -> str:
        """使用 Gemini API 生成更优的推文。"""
        title = info.get('title', 'N/A')
        description = info.get('description', 'N/A')
        keywords = info.get('keywords', [])
        hashtags = info.get('hashtags', [])
        
        # 根据内容类型调整提示词
        content_type_names = {
            'video': {'en': 'video', 'cn': '视频', 'ja': '動画'},
            'article': {'en': 'article', 'cn': '文章', 'ja': '記事'},
            'image': {'en': 'image', 'cn': '图片', 'ja': '画像'},
            'audio': {'en': 'audio', 'cn': '音频', 'ja': '音声'}
        }
        
        content_name = content_type_names.get(content_type, {}).get(language, content_type)
        
        # 构建语言特定的提示词
        if language == 'cn':
            prompt = f"""
你是一个专业的社交媒体营销专家，精通Twitter的运营。
请根据以下{content_name}的核心元素，创作一条吸引人的Twitter推文。
要求：语言风格自然，能吸引用户互动，并合理使用标签，字数控制在280字符以内。

{content_name}标题：{title}
{content_name}描述：{description}
核心关键词：{', '.join(keywords) if keywords else 'N/A'}
建议标签：{' '.join(hashtags) if hashtags else 'N/A'}

请生成中文推文内容：
"""
        elif language == 'ja':
            prompt = f"""
あなたはソーシャルメディアマーケティングの専門家で、Twitterの運営に精通しています。
以下の{content_name}の核心要素に基づいて、魅力的なTwitterツイートを作成してください。
要件：自然な言語スタイル、ユーザーのインタラクションを促進、適切なハッシュタグの使用、280文字以内。

{content_name}タイトル：{title}
{content_name}説明：{description}
キーワード：{', '.join(keywords) if keywords else 'N/A'}
推奨ハッシュタグ：{' '.join(hashtags) if hashtags else 'N/A'}

日本語のツイート内容を生成してください：
"""
        else:  # English
            prompt = f"""
You are a professional social media marketing expert specializing in Twitter operations.
Please create an engaging Twitter tweet based on the following {content_name} elements.
Requirements: Natural language style, encourage user interaction, appropriate use of hashtags, within 280 characters.

{content_name.title()} Title: {title}
{content_name.title()} Description: {description}
Keywords: {', '.join(keywords) if keywords else 'N/A'}
Suggested Hashtags: {' '.join(hashtags) if hashtags else 'N/A'}

Please generate English tweet content:
"""
        
        try:
            response = self.model.generate_content(prompt)
            generated_content = response.text.strip()
            
            # 确保生成的内容不超过280字符
            if len(generated_content) > 280:
                generated_content = generated_content[:277] + '...'
                
            return generated_content
            
        except Exception as e:
            logger.error(f"Gemini API调用失败: {e}")
            logger.info("回退到直接模式生成内容")
            return self._generate_from_json_directly(info, language, content_type)