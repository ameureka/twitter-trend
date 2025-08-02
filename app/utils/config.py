# app/utils/config.py

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from app.utils.logger import get_logger

logger = get_logger(__name__)

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = None, env_path: str = None):
        self.config_data = {}
        self.env_data = {}
        
        # 设置默认路径 - 使用pathlib提高跨平台兼容性
        if config_path is None:
            project_root = Path(__file__).parent.parent.parent
            config_path = str(project_root / 'config/enhanced_config.yaml')
        
        if env_path is None:
            project_root = Path(__file__).parent.parent.parent
            env_path = str(project_root / '.env')
        
        self.config_path = config_path
        self.env_path = env_path
        
        # 添加兼容性属性
        self.config_file_path = config_path
        self.env_file_path = env_path
        
        # 加载配置
        self.load_config()
        self.load_env()
    
    def load_config(self) -> bool:
        """加载YAML配置文件"""
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config_data = yaml.safe_load(f) or {}
                logger.info(f"配置文件加载成功: {self.config_path}")
                return True
            else:
                logger.warning(f"配置文件不存在: {self.config_path}")
                self.config_data = self._get_default_config()
                return False
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            self.config_data = self._get_default_config()
            return False
    
    def load_env(self) -> bool:
        """加载环境变量文件"""
        try:
            env_file = Path(self.env_path)
            if env_file.exists():
                load_dotenv(self.env_path)
                logger.info(f"环境变量文件加载成功: {self.env_path}")
                return True
            else:
                logger.warning(f"环境变量文件不存在: {self.env_path}")
                return False
        except Exception as e:
            logger.error(f"加载环境变量文件失败: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的嵌套键"""
        try:
            keys = key.split('.')
            value = self.config_data
            
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            
            return value
        except Exception as e:
            logger.error(f"获取配置值失败 {key}: {e}")
            return default
    
    def get_env(self, key: str, default: str = None) -> Optional[str]:
        """获取环境变量"""
        return os.getenv(key, default)
    
    def get_twitter_config(self) -> Dict[str, str]:
        """获取Twitter API配置"""
        return {
            'api_key': self.get_env('TWITTER_API_KEY'),
            'api_secret': self.get_env('TWITTER_API_SECRET'),
            'access_token': self.get_env('TWITTER_ACCESS_TOKEN'),
            'access_token_secret': self.get_env('TWITTER_ACCESS_TOKEN_SECRET')
        }
    
    def get_gemini_config(self) -> Dict[str, str]:
        """获取Gemini API配置"""
        return {
            'api_key': self.get_env('GEMINI_API_KEY')
        }
    
    def get_database_config(self) -> Dict[str, str]:
        """获取数据库配置"""
        # 延迟导入避免循环依赖
        from app.utils.path_manager import get_path_manager
        path_manager = get_path_manager()
        
        db_url = self.get_env('DATABASE_URL')
        if not db_url:
            # 使用路径管理器创建数据库URL
            db_path = self.get('database_path', './data/twitter_publisher.db')
            db_url = path_manager.create_database_url(db_path)
        
        return {'url': db_url}
    
    def validate_required_config(self) -> Dict[str, bool]:
        """验证必需的配置项"""
        validation_result = {
            'twitter_api_key': bool(self.get_env('TWITTER_API_KEY')),
            'twitter_api_secret': bool(self.get_env('TWITTER_API_SECRET')),
            'twitter_access_token': bool(self.get_env('TWITTER_ACCESS_TOKEN')),
            'twitter_access_token_secret': bool(self.get_env('TWITTER_ACCESS_TOKEN_SECRET')),
            'project_base_path': bool(self.get('project_base_path')),
            'config_file_exists': os.path.exists(self.config_path),
            'env_file_exists': os.path.exists(self.env_path)
        }
        
        # 检查项目目录是否存在
        project_path = self.get('project_base_path')
        if project_path:
            abs_project_path = Path(project_path).resolve()
            validation_result['project_directory_exists'] = abs_project_path.exists()
        else:
            validation_result['project_directory_exists'] = False
        
        return validation_result
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'project_base_path': './project',
            'logs': {
                'path': './logs/app.log',
                'level': 'INFO'
            },
            'scheduler': {
                'interval_minutes_min': 15,
                'interval_minutes_max': 30,
                'max_retries': 3
            },
            'publishing': {
                'default_language': 'en',
                'use_ai_enhancement': True
            },
            'database': {
                'path': './data/twitter_publisher.db'
            }
        }
    
    def save_config(self) -> bool:
        """保存配置到文件"""
        try:
            # 确保目录存在
            config_file = Path(self.config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config_data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"配置文件保存成功: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False
    
    def update_config(self, key: str, value: Any) -> bool:
        """更新配置值"""
        try:
            keys = key.split('.')
            config = self.config_data
            
            # 导航到目标位置
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            # 设置值
            config[keys[-1]] = value
            
            logger.info(f"配置更新成功: {key} = {value}")
            return True
        except Exception as e:
            logger.error(f"更新配置失败 {key}: {e}")
            return False
    
    def get_absolute_path(self, relative_path: str) -> str:
        """将相对路径转换为绝对路径"""
        # 延迟导入避免循环依赖
        from app.utils.path_manager import get_path_manager
        path_manager = get_path_manager()
        return str(path_manager.normalize_path(relative_path))
    
    def get_project_path(self) -> str:
        """获取项目基础路径的绝对路径"""
        # 延迟导入避免循环依赖
        from app.utils.path_manager import get_path_manager
        path_manager = get_path_manager()
        project_path = self.get('project_base_path', './project')
        return str(path_manager.get_project_path(project_path))
    
    def get_logs_path(self) -> str:
        """获取日志文件路径的绝对路径"""
        # 延迟导入避免循环依赖
        from app.utils.path_manager import get_path_manager
        path_manager = get_path_manager()
        log_path = self.get('logs.path', './logs/app.log')
        return str(path_manager.normalize_path(log_path))
    
    def print_config_summary(self):
        """打印配置摘要"""
        print("\n=== 配置摘要 ===")
        print(f"配置文件: {self.config_path}")
        print(f"环境文件: {self.env_path}")
        print(f"项目路径: {self.get_project_path()}")
        print(f"日志路径: {self.get_logs_path()}")
        print(f"默认语言: {self.get('publishing.default_language', 'en')}")
        print(f"AI增强: {self.get('publishing.use_ai_enhancement', True)}")
        print(f"发布间隔: {self.get('scheduler.interval_minutes_min', 15)}-{self.get('scheduler.interval_minutes_max', 30)}分钟")
        
        # 验证配置
        validation = self.validate_required_config()
        print("\n=== 配置验证 ===")
        for key, valid in validation.items():
            status = "✓" if valid else "✗"
            print(f"{status} {key}: {valid}")
        
        print("\n")

# 全局配置实例
_config_instance = None

def get_config() -> ConfigManager:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance

def init_config(config_path: Optional[str] = None, env_path: Optional[str] = None) -> ConfigManager:
    """初始化全局配置实例"""
    global _config_instance
    if config_path is None:
        # 默认配置文件路径
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config/enhanced_config.yaml')
    if env_path is None:
        # 默认环境变量文件路径
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    
    _config_instance = ConfigManager(config_path, env_path)
    return _config_instance