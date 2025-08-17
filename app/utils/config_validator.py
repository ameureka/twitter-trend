"""配置验证模块

根据项目开发设计核心原则，提供配置验证和健康检查功能。
"""

import os
from typing import Dict, List, Any, Optional
from pathlib import Path
from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config
from app.utils.path_manager import get_path_manager

logger = get_logger(__name__)

class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        self.config = get_enhanced_config()
        self.errors = []
        self.warnings = []
    
    def validate_all(self) -> Dict[str, Any]:
        """执行全面的配置验证"""
        self.errors.clear()
        self.warnings.clear()
        
        # 验证基础配置
        self._validate_basic_config()
        
        # 验证路径配置
        self._validate_paths()
        
        # 验证API配置
        self._validate_api_configs()
        
        # 验证数据库配置
        self._validate_database_config()
        
        # 验证日志配置
        self._validate_logging_config()
        
        return {
            'valid': len(self.errors) == 0,
            'errors': self.errors,
            'warnings': self.warnings,
            'summary': self._generate_summary()
        }
    
    def _validate_basic_config(self):
        """验证基础配置"""
        try:
            # 检查必需的配置文件
            config_files = [
                self.config.config_file_path,
                self.config.env_file_path
            ]
            
            for config_file in config_files:
                if not Path(config_file).exists():
                    self.errors.append(f"配置文件不存在: {config_file}")
            
            # 检查默认语言
            default_language = self.config.get('default_language', 'en')
            supported_languages = ['en', 'zh', 'es', 'fr', 'de', 'ja', 'ko']
            if default_language not in supported_languages:
                self.warnings.append(f"不支持的默认语言: {default_language}")
            
        except Exception as e:
            self.errors.append(f"基础配置验证失败: {e}")
    
    def _validate_paths(self):
        """验证路径配置"""
        try:
            # 验证项目基础路径
            project_base_path = self.config.get('project_base_path')
            if not project_base_path:
                self.errors.append("未配置项目基础路径 (project_base_path)")
            else:
                # 使用路径管理器正确解析相对路径
                path_manager = get_path_manager()
                resolved_path = path_manager.get_project_path(project_base_path)
                
                if not resolved_path.exists():
                    self.errors.append(f"项目基础路径不存在: {project_base_path} (解析为: {resolved_path})")
                elif not resolved_path.is_dir():
                    self.errors.append(f"项目基础路径不是目录: {project_base_path} (解析为: {resolved_path})")
                elif not os.access(resolved_path, os.R_OK):
                    self.errors.append(f"项目基础路径无读取权限: {project_base_path} (解析为: {resolved_path})")
            
            # 验证日志目录
            log_dir = self.config.get('logging', {}).get('log_dir', 'logs')
            log_path = Path(log_dir)
            if not log_path.exists():
                try:
                    log_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"创建日志目录: {log_dir}")
                except Exception as e:
                    self.errors.append(f"无法创建日志目录 {log_dir}: {e}")
            
        except Exception as e:
            self.errors.append(f"路径配置验证失败: {e}")
    
    def _validate_api_configs(self):
        """验证API配置"""
        try:
            # 验证Twitter API配置
            twitter_config = self.config.get_twitter_config()
            required_twitter_keys = [
                'api_key', 'api_secret', 'access_token', 'access_token_secret'
            ]
            
            for key in required_twitter_keys:
                if not twitter_config.get(key):
                    self.errors.append(f"缺少Twitter API配置: {key}")
            
            # 验证Gemini API配置（如果启用AI增强）
            ai_enhancement = self.config.get('ai_enhancement', {}).get('enabled', False)
            if ai_enhancement:
                gemini_config = self.config.get_gemini_config()
                if not gemini_config.get('api_key'):
                    self.errors.append("启用AI增强但缺少Gemini API密钥")
            
        except Exception as e:
            self.errors.append(f"API配置验证失败: {e}")
    
    def _validate_database_config(self):
        """验证数据库配置"""
        try:
            db_config = self.config.get_database_config()
            db_url = db_config.get('url')
            
            if not db_url:
                self.errors.append("缺少数据库URL配置")
            elif db_url.startswith('sqlite:///'):
                # SQLite数据库路径验证
                db_path = db_url.replace('sqlite:///', '')
                db_file = Path(db_path)
                db_dir = db_file.parent
                
                if not db_dir.exists():
                    try:
                        db_dir.mkdir(parents=True, exist_ok=True)
                        logger.info(f"创建数据库目录: {db_dir}")
                    except Exception as e:
                        self.errors.append(f"无法创建数据库目录 {db_dir}: {e}")
            
        except Exception as e:
            self.errors.append(f"数据库配置验证失败: {e}")
    
    def _validate_logging_config(self):
        """验证日志配置"""
        try:
            logging_config = self.config.get('logging', {})
            
            # 验证日志级别
            log_level = logging_config.get('level', 'INFO')
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if log_level not in valid_levels:
                self.warnings.append(f"无效的日志级别: {log_level}")
            
            # 验证日志文件大小限制
            max_bytes = logging_config.get('max_bytes', 10485760)  # 10MB
            if max_bytes < 1024 * 1024:  # 小于1MB
                self.warnings.append(f"日志文件大小限制过小: {max_bytes} bytes")
            
        except Exception as e:
            self.errors.append(f"日志配置验证失败: {e}")
    
    def _generate_summary(self) -> str:
        """生成验证摘要"""
        if len(self.errors) == 0 and len(self.warnings) == 0:
            return "配置验证通过，所有设置正常"
        
        summary_parts = []
        if self.errors:
            summary_parts.append(f"发现 {len(self.errors)} 个错误")
        if self.warnings:
            summary_parts.append(f"发现 {len(self.warnings)} 个警告")
        
        return "配置验证完成: " + ", ".join(summary_parts)
    
    def validate_project_structure(self, project_path: str) -> Dict[str, Any]:
        """验证项目结构"""
        errors = []
        warnings = []
        
        try:
            project_path_obj = Path(project_path)
            if not project_path_obj.exists():
                errors.append(f"项目路径不存在: {project_path}")
                return {'valid': False, 'errors': errors, 'warnings': warnings}
            
            # 检查必需的目录结构
            required_dirs = ['output_video_music', 'uploader_json']
            for dir_name in required_dirs:
                dir_path = project_path_obj / dir_name
                if not dir_path.exists():
                    warnings.append(f"缺少目录: {dir_name}")
                elif not dir_path.is_dir():
                    errors.append(f"路径不是目录: {dir_name}")
            
            # 检查文件权限
            if not os.access(project_path_obj, os.R_OK):
                errors.append(f"项目目录无读取权限: {project_path}")
            
        except Exception as e:
            errors.append(f"项目结构验证失败: {e}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }


def validate_config() -> Dict[str, Any]:
    """全局配置验证函数"""
    validator = ConfigValidator()
    return validator.validate_all()


def validate_project(project_path: str) -> Dict[str, Any]:
    """全局项目验证函数"""
    validator = ConfigValidator()
    return validator.validate_project_structure(project_path)