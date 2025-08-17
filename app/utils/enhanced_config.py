#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强型配置管理器 - 优化的配置加载、验证和管理

主要功能:
1. 多环境配置支持
2. 动态配置更新
3. 配置验证和类型检查
4. 配置热重载
5. 敏感信息加密
6. 配置版本管理
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from datetime import datetime
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from cryptography.fernet import Fernet
import base64

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConfigSchema:
    """配置模式定义"""
    required_fields: List[str] = field(default_factory=list)
    optional_fields: Dict[str, Any] = field(default_factory=dict)
    field_types: Dict[str, type] = field(default_factory=dict)
    validation_rules: Dict[str, callable] = field(default_factory=dict)


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件变化监听器"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(('.yaml', '.yml', '.json')):
            logger.info(f"配置文件已修改: {event.src_path}")
            self.config_manager._reload_config()


class EnhancedConfigManager:
    """增强型配置管理器"""
    
    def __init__(self, config_path: str = "config/enhanced_config.yaml", 
                 environment: str = None):
        self.config_path = Path(config_path)
        self.environment = environment or os.getenv('ENVIRONMENT', 'development')
        self.config_data = {}
        self.encrypted_fields = set()
        self.observers = []
        self.lock = threading.RLock()
        self.last_modified = None
        self.config_history = []
        
        # 配置模式
        self.schema = self._define_schema()
        
        # 加密密钥
        self.encryption_key = self._get_or_create_encryption_key()
        
        # 初始化配置
        self._load_config()
        
        # 启动文件监控
        if self.config_path.exists():
            self._start_file_monitoring()
            
    def _define_schema(self) -> ConfigSchema:
        """定义配置模式"""
        return ConfigSchema(
            required_fields=[
                'project_base_path',
                'database.path',
                'logging.path',
                'logging.level'
            ],
            optional_fields={
                'scheduler.interval': 30,
                'scheduler.max_retries': 3,
                'scheduler.max_workers': 3,
                'scheduler.batch_size': 5,
                'task.stuck_timeout': 300,
                'task.lock_timeout': 60,
                'publishing.default_language': 'zh',
                'publishing.ai_enhancement': True,
                'api.host': '127.0.0.1',
                'api.port': 8050,
                'api.debug': False
            },
            field_types={
                'project_base_path': str,
                'database.path': str,
                'logging.level': str,
                'scheduler.interval': int,
                'scheduler.max_retries': int,
                'scheduler.max_workers': int,
                'scheduler.batch_size': int,
                'task.stuck_timeout': int,
                'task.lock_timeout': int,
                'publishing.ai_enhancement': bool,
                'api.port': int,
                'api.debug': bool
            },
            validation_rules={
                'scheduler.interval': lambda x: x > 0,
                'scheduler.max_retries': lambda x: 0 <= x <= 10,
                'scheduler.max_workers': lambda x: 1 <= x <= 20,
                'scheduler.batch_size': lambda x: 1 <= x <= 100,
                'api.port': lambda x: 1024 <= x <= 65535,
                'logging.level': lambda x: x.upper() in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            }
        )
        
    def _get_or_create_encryption_key(self) -> Fernet:
        """获取或创建加密密钥"""
        # 新的密钥文件路径
        key_dir = Path('config/keys')
        key_file = key_dir / 'current.key'
        
        # 检查旧的密钥文件位置
        legacy_key_file = Path('.config_key')
        
        if key_file.exists():
            # 使用新位置的密钥
            with open(key_file, 'rb') as f:
                key = f.read()
        elif legacy_key_file.exists():
            # 迁移旧密钥到新位置
            key_dir.mkdir(parents=True, exist_ok=True)
            with open(legacy_key_file, 'rb') as f:
                key = f.read()
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)
            # 删除旧密钥文件
            os.remove(legacy_key_file)
        else:
            # 生成新密钥
            key_dir.mkdir(parents=True, exist_ok=True)
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)
            
        return Fernet(key)
        
    def _load_config(self):
        """加载配置文件"""
        try:
            with self.lock:
                if not self.config_path.exists():
                    logger.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
                    self.config_data = self._get_default_config()
                    self._save_config()
                    return
                    
                # 检查文件修改时间
                current_modified = self.config_path.stat().st_mtime
                if self.last_modified and current_modified == self.last_modified:
                    return
                    
                self.last_modified = current_modified
                
                # 读取配置文件
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    if self.config_path.suffix.lower() == '.json':
                        raw_config = json.load(f)
                    else:
                        raw_config = yaml.safe_load(f)
                        
                # 处理环境特定配置
                self.config_data = self._process_environment_config(raw_config)
                
                # 解密敏感字段
                self._decrypt_sensitive_fields()
                
                # 验证配置
                validation_result = self._validate_config()
                if not validation_result['valid']:
                    raise ValueError(f"配置验证失败: {validation_result['errors']}")
                    
                # 保存配置历史
                self._save_config_history()
                
                logger.info(f"配置加载成功，环境: {self.environment}")
                
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            if not self.config_data:
                # 如果没有可用配置，使用默认配置
                self.config_data = self._get_default_config()
                
    def _process_environment_config(self, raw_config: Dict[str, Any]) -> Dict[str, Any]:
        """处理环境特定配置"""
        config = raw_config.copy()
        
        # 处理环境覆盖
        env_key = f'environments.{self.environment}'
        if self._get_nested_value(raw_config, env_key):
            env_config = self._get_nested_value(raw_config, env_key)
            config = self._deep_merge(config, env_config)
            
        # 处理环境变量覆盖
        config = self._apply_env_overrides(config)
        
        return config
        
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """应用环境变量覆盖"""
        env_prefix = 'TWITTER_'
        
        for key, value in os.environ.items():
            if key.startswith(env_prefix):
                config_key = key[len(env_prefix):].lower().replace('_', '.')
                
                # 尝试转换类型
                converted_value = self._convert_env_value(value)
                self._set_nested_value(config, config_key, converted_value)
                
        return config
        
    def _convert_env_value(self, value: str) -> Any:
        """转换环境变量值类型"""
        # 布尔值
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
            
        # 数字
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
            
        # JSON
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
            
        # 字符串
        return value
        
    def _validate_config(self) -> Dict[str, Any]:
        """验证配置"""
        errors = []
        warnings = []
        
        # 检查必需字段
        for field in self.schema.required_fields:
            if not self._get_nested_value(self.config_data, field):
                errors.append(f"缺少必需字段: {field}")
                
        # 检查字段类型
        for field, expected_type in self.schema.field_types.items():
            value = self._get_nested_value(self.config_data, field)
            if value is not None and not isinstance(value, expected_type):
                errors.append(f"字段 {field} 类型错误，期望 {expected_type.__name__}，实际 {type(value).__name__}")
                
        # 检查验证规则
        for field, rule in self.schema.validation_rules.items():
            value = self._get_nested_value(self.config_data, field)
            if value is not None:
                try:
                    if not rule(value):
                        errors.append(f"字段 {field} 验证失败: {value}")
                except Exception as e:
                    errors.append(f"字段 {field} 验证异常: {e}")
                    
        # 检查路径是否存在
        path_fields = ['project_base_path', 'logging.path']
        for field in path_fields:
            path_value = self._get_nested_value(self.config_data, field)
            if path_value:
                path_obj = Path(path_value)
                if field == 'project_base_path' and not path_obj.exists():
                    warnings.append(f"项目路径不存在: {path_value}")
                elif field == 'logging.path':
                    log_dir = path_obj.parent if path_obj.suffix else path_obj
                    if not log_dir.exists():
                        warnings.append(f"日志目录不存在: {log_dir}")
                        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
        
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'project_base_path': './project',
            'database': {
                'path': './data/twitter_publisher.db',
                'backup_path': './data/backups'
            },
            'logging': {
                'path': './logs/app.log',
                'level': 'INFO',
                'max_size': '10MB',
                'backup_count': 5
            },
            'scheduler': {
                'interval': 30,
                'max_retries': 3,
                'max_workers': 3,
                'batch_size': 5,
                'backoff_factor': 2.0
            },
            'task': {
                'stuck_timeout': 300,
                'lock_timeout': 60,
                'max_retries': 3
            },
            'publishing': {
                'default_language': 'zh',
                'ai_enhancement': True,
                'rate_limit': {
                    'tweets_per_hour': 50,
                    'tweets_per_day': 300
                }
            },
            'api': {
                'host': '127.0.0.1',
                'port': 8050,
                'debug': False,
                'cors_origins': ['*']
            },
            'monitoring': {
                'enabled': True,
                'metrics_retention_days': 30,
                'alert_thresholds': {
                    'error_rate': 0.1,
                    'response_time': 5.0
                }
            }
        }
        
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        with self.lock:
            return self._get_nested_value(self.config_data, key, default)
            
    def get_env(self, key: str, default: Any = None) -> Any:
        """获取环境变量或配置值 - 修复缺失方法"""
        # 首先尝试从环境变量获取
        env_value = os.environ.get(key)
        if env_value is not None:
            return self._convert_env_value(env_value)
            
        # 如果环境变量不存在，尝试从配置获取
        # 将环境变量格式转换为配置键格式
        config_key = key.lower().replace('_', '.')
        config_value = self.get(config_key, default)
        
        # 如果配置也不存在，返回默认值
        return config_value if config_value is not None else default
            
    def set(self, key: str, value: Any, save: bool = True) -> bool:
        """设置配置值"""
        try:
            with self.lock:
                self._set_nested_value(self.config_data, key, value)
                
                if save:
                    self._save_config()
                    
                logger.info(f"配置已更新: {key} = {value}")
                return True
                
        except Exception as e:
            logger.error(f"设置配置失败: {e}")
            return False
            
    def update(self, updates: Dict[str, Any], save: bool = True) -> bool:
        """批量更新配置"""
        try:
            with self.lock:
                for key, value in updates.items():
                    self._set_nested_value(self.config_data, key, value)
                    
                if save:
                    self._save_config()
                    
                logger.info(f"批量更新配置完成: {len(updates)} 项")
                return True
                
        except Exception as e:
            logger.error(f"批量更新配置失败: {e}")
            return False
            
    def encrypt_field(self, key: str) -> bool:
        """加密敏感字段"""
        try:
            with self.lock:
                value = self._get_nested_value(self.config_data, key)
                if value is None:
                    return False
                    
                encrypted_value = self.encryption_key.encrypt(str(value).encode())
                encoded_value = base64.b64encode(encrypted_value).decode()
                
                self._set_nested_value(self.config_data, key, f"encrypted:{encoded_value}")
                self.encrypted_fields.add(key)
                
                logger.info(f"字段已加密: {key}")
                return True
                
        except Exception as e:
            logger.error(f"加密字段失败: {e}")
            return False
            
    def _decrypt_sensitive_fields(self):
        """解密敏感字段"""
        for key in list(self.encrypted_fields):
            try:
                value = self._get_nested_value(self.config_data, key)
                if isinstance(value, str) and value.startswith('encrypted:'):
                    encoded_value = value[10:]  # 移除 'encrypted:' 前缀
                    encrypted_value = base64.b64decode(encoded_value.encode())
                    decrypted_value = self.encryption_key.decrypt(encrypted_value).decode()
                    
                    self._set_nested_value(self.config_data, key, decrypted_value)
                    
            except Exception as e:
                logger.error(f"解密字段失败 {key}: {e}")
                
    def _save_config(self):
        """保存配置到文件"""
        try:
            # 创建配置副本用于保存（加密敏感字段）
            save_config = self.config_data.copy()
            
            for key in self.encrypted_fields:
                value = self._get_nested_value(save_config, key)
                if value and not str(value).startswith('encrypted:'):
                    encrypted_value = self.encryption_key.encrypt(str(value).encode())
                    encoded_value = base64.b64encode(encrypted_value).decode()
                    self._set_nested_value(save_config, key, f"encrypted:{encoded_value}")
                    
            # 保存到文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if self.config_path.suffix.lower() == '.json':
                    json.dump(save_config, f, indent=2, ensure_ascii=False)
                else:
                    yaml.dump(save_config, f, default_flow_style=False, 
                             allow_unicode=True, indent=2)
                             
            logger.debug(f"配置已保存到: {self.config_path}")
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            
    def _save_config_history(self):
        """保存配置历史"""
        try:
            history_entry = {
                'timestamp': datetime.now().isoformat(),
                'environment': self.environment,
                'config': self.config_data.copy()
            }
            
            self.config_history.append(history_entry)
            
            # 保持最近50个历史记录
            if len(self.config_history) > 50:
                self.config_history = self.config_history[-50:]
                
        except Exception as e:
            logger.error(f"保存配置历史失败: {e}")
            
    def _reload_config(self):
        """重新加载配置"""
        try:
            logger.info("重新加载配置文件")
            self._load_config()
            
            # 通知观察者
            for observer in self.observers:
                try:
                    observer(self.config_data)
                except Exception as e:
                    logger.error(f"通知配置观察者失败: {e}")
                    
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
            
    def add_observer(self, callback: callable):
        """添加配置变化观察者"""
        self.observers.append(callback)
        
    def remove_observer(self, callback: callable):
        """移除配置变化观察者"""
        if callback in self.observers:
            self.observers.remove(callback)
            
    def _start_file_monitoring(self):
        """启动文件监控"""
        try:
            observer = Observer()
            event_handler = ConfigFileHandler(self)
            observer.schedule(event_handler, str(self.config_path.parent), recursive=False)
            observer.start()
            
            logger.info(f"配置文件监控已启动: {self.config_path}")
            
        except Exception as e:
            logger.error(f"启动文件监控失败: {e}")
            
    def _get_nested_value(self, data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """获取嵌套字典值"""
        keys = key.split('.')
        current = data
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
                
        return current
        
    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any):
        """设置嵌套字典值"""
        keys = key.split('.')
        current = data
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            elif not isinstance(current[k], dict):
                # 如果现有值不是字典，将其转换为字典
                current[k] = {}
            current = current[k]
            
        current[keys[-1]] = value
        
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并字典"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
        
    def get_config_info(self) -> Dict[str, Any]:
        """获取配置信息"""
        return {
            'config_path': str(self.config_path),
            'environment': self.environment,
            'last_modified': self.last_modified,
            'encrypted_fields': list(self.encrypted_fields),
            'observers_count': len(self.observers),
            'history_count': len(self.config_history),
            'validation': self._validate_config()
        }


# 全局配置管理器实例
_config_manager = None
_config_lock = threading.Lock()


def get_enhanced_config(config_path: str = "config/enhanced_config.yaml", 
                       environment: str = None) -> EnhancedConfigManager:
    """获取增强型配置管理器实例"""
    global _config_manager
    
    with _config_lock:
        if _config_manager is None:
            _config_manager = EnhancedConfigManager(config_path, environment)
            
    return _config_manager


def reload_config():
    """重新加载配置"""
    global _config_manager
    
    with _config_lock:
        if _config_manager:
            _config_manager._reload_config()