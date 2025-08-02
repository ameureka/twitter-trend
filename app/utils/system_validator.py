#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统验证模块
提供全面的系统验证功能，包括配置、依赖、权限等检查
"""

import os
import sys
import importlib
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SystemValidator:
    """系统验证器"""
    
    def __init__(self):
        self.validation_results = {
            'python_version': {'valid': False, 'details': ''},
            'dependencies': {'valid': False, 'details': [], 'missing': []},
            'permissions': {'valid': False, 'details': []},
            'environment': {'valid': False, 'details': []},
            'file_structure': {'valid': False, 'details': []}
        }
    
    def validate_python_version(self, min_version: tuple = (3, 8)) -> bool:
        """验证Python版本"""
        try:
            current_version = sys.version_info[:2]
            is_valid = current_version >= min_version
            
            self.validation_results['python_version'] = {
                'valid': is_valid,
                'details': f"当前版本: {'.'.join(map(str, current_version))}, 最低要求: {'.'.join(map(str, min_version))}"
            }
            
            return is_valid
        except Exception as e:
            logger.error(f"Python版本检查失败: {e}")
            self.validation_results['python_version'] = {
                'valid': False,
                'details': f"检查失败: {e}"
            }
            return False
    
    def validate_dependencies(self, required_packages: List[str]) -> bool:
        """验证依赖包"""
        missing_packages = []
        available_packages = []
        
        for package in required_packages:
            try:
                # 尝试导入包
                if '.' in package:
                    # 处理子模块
                    module_name = package.split('.')[0]
                else:
                    module_name = package
                
                importlib.import_module(module_name)
                available_packages.append(package)
            except ImportError:
                missing_packages.append(package)
            except Exception as e:
                logger.warning(f"检查包 {package} 时出错: {e}")
                missing_packages.append(package)
        
        is_valid = len(missing_packages) == 0
        
        self.validation_results['dependencies'] = {
            'valid': is_valid,
            'details': available_packages,
            'missing': missing_packages
        }
        
        return is_valid
    
    def validate_file_permissions(self, paths: List[str]) -> bool:
        """验证文件权限"""
        permission_issues = []
        
        for path_str in paths:
            path = Path(path_str)
            
            try:
                if path.exists():
                    # 检查读权限
                    if not os.access(path, os.R_OK):
                        permission_issues.append(f"无读权限: {path}")
                    
                    # 如果是目录，检查写权限
                    if path.is_dir() and not os.access(path, os.W_OK):
                        permission_issues.append(f"无写权限: {path}")
                    
                    # 如果是文件，检查写权限
                    if path.is_file() and not os.access(path, os.W_OK):
                        permission_issues.append(f"无写权限: {path}")
                else:
                    # 检查父目录的写权限
                    parent = path.parent
                    if parent.exists() and not os.access(parent, os.W_OK):
                        permission_issues.append(f"无法在父目录创建文件: {parent}")
            
            except Exception as e:
                permission_issues.append(f"权限检查失败 {path}: {e}")
        
        is_valid = len(permission_issues) == 0
        
        self.validation_results['permissions'] = {
            'valid': is_valid,
            'details': permission_issues
        }
        
        return is_valid
    
    def validate_environment_variables(self, required_vars: List[str], optional_vars: List[str] = None) -> bool:
        """验证环境变量"""
        missing_required = []
        missing_optional = []
        available_vars = []
        
        # 检查必需的环境变量
        for var in required_vars:
            if os.getenv(var):
                available_vars.append(var)
            else:
                missing_required.append(var)
        
        # 检查可选的环境变量
        if optional_vars:
            for var in optional_vars:
                if os.getenv(var):
                    available_vars.append(var)
                else:
                    missing_optional.append(var)
        
        is_valid = len(missing_required) == 0
        
        details = []
        if available_vars:
            details.append(f"已配置: {', '.join(available_vars)}")
        if missing_required:
            details.append(f"缺少必需变量: {', '.join(missing_required)}")
        if missing_optional:
            details.append(f"缺少可选变量: {', '.join(missing_optional)}")
        
        self.validation_results['environment'] = {
            'valid': is_valid,
            'details': details
        }
        
        return is_valid
    
    def validate_file_structure(self, required_files: List[str], required_dirs: List[str]) -> bool:
        """验证文件结构"""
        missing_files = []
        missing_dirs = []
        existing_items = []
        
        # 检查必需文件
        for file_path in required_files:
            path = Path(file_path)
            if path.exists() and path.is_file():
                existing_items.append(f"文件: {file_path}")
            else:
                missing_files.append(file_path)
        
        # 检查必需目录
        for dir_path in required_dirs:
            path = Path(dir_path)
            if path.exists() and path.is_dir():
                existing_items.append(f"目录: {dir_path}")
            else:
                missing_dirs.append(dir_path)
        
        is_valid = len(missing_files) == 0 and len(missing_dirs) == 0
        
        details = []
        if existing_items:
            details.extend(existing_items)
        if missing_files:
            details.append(f"缺少文件: {', '.join(missing_files)}")
        if missing_dirs:
            details.append(f"缺少目录: {', '.join(missing_dirs)}")
        
        self.validation_results['file_structure'] = {
            'valid': is_valid,
            'details': details
        }
        
        return is_valid
    
    def validate_system_resources(self) -> bool:
        """验证系统资源"""
        try:
            import psutil
            
            # 检查可用内存（至少512MB）
            memory = psutil.virtual_memory()
            available_mb = memory.available / (1024 * 1024)
            memory_ok = available_mb >= 512
            
            # 检查磁盘空间（至少1GB）
            disk = psutil.disk_usage('/')
            free_gb = disk.free / (1024 * 1024 * 1024)
            disk_ok = free_gb >= 1
            
            # 检查CPU核心数
            cpu_count = psutil.cpu_count()
            cpu_ok = cpu_count >= 1
            
            is_valid = memory_ok and disk_ok and cpu_ok
            
            details = [
                f"可用内存: {available_mb:.1f}MB ({'✅' if memory_ok else '❌'})",
                f"可用磁盘: {free_gb:.1f}GB ({'✅' if disk_ok else '❌'})",
                f"CPU核心: {cpu_count} ({'✅' if cpu_ok else '❌'})"
            ]
            
            self.validation_results['system_resources'] = {
                'valid': is_valid,
                'details': details
            }
            
            return is_valid
            
        except ImportError:
            logger.warning("psutil未安装，跳过系统资源检查")
            return True
        except Exception as e:
            logger.error(f"系统资源检查失败: {e}")
            return False
    
    def run_full_validation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """运行完整的系统验证"""
        validation_config = config.get('validation', {})
        
        # Python版本检查
        min_python = tuple(validation_config.get('min_python_version', [3, 8]))
        self.validate_python_version(min_python)
        
        # 依赖包检查
        required_packages = validation_config.get('required_packages', [
            'click', 'sqlalchemy', 'tweepy', 'google.generativeai',
            'pyyaml', 'python-dotenv', 'psutil'
        ])
        self.validate_dependencies(required_packages)
        
        # 环境变量检查
        required_env = validation_config.get('required_env_vars', [])
        optional_env = validation_config.get('optional_env_vars', [
            'TWITTER_API_KEY', 'TWITTER_API_SECRET',
            'TWITTER_ACCESS_TOKEN', 'TWITTER_ACCESS_TOKEN_SECRET',
            'GEMINI_API_KEY'
        ])
        self.validate_environment_variables(required_env, optional_env)
        
        # 文件权限检查
        check_paths = validation_config.get('check_paths', [
            './config/enhanced_config.yaml', './logs', './data'
        ])
        self.validate_file_permissions(check_paths)
        
        # 文件结构检查
        required_files = validation_config.get('required_files', [
            './app/main.py', './app/core/__init__.py'
        ])
        required_dirs = validation_config.get('required_dirs', [
            './app', './app/core', './app/utils', './app/database'
        ])
        self.validate_file_structure(required_files, required_dirs)
        
        # 系统资源检查
        self.validate_system_resources()
        
        # 计算总体验证结果
        all_valid = all(
            result['valid'] for result in self.validation_results.values()
        )
        
        return {
            'overall_valid': all_valid,
            'results': self.validation_results,
            'summary': self._generate_summary()
        }
    
    def _generate_summary(self) -> Dict[str, Any]:
        """生成验证摘要"""
        passed = sum(1 for result in self.validation_results.values() if result['valid'])
        total = len(self.validation_results)
        
        failed_checks = [
            check_name for check_name, result in self.validation_results.items()
            if not result['valid']
        ]
        
        return {
            'passed_checks': passed,
            'total_checks': total,
            'success_rate': (passed / total) * 100 if total > 0 else 0,
            'failed_checks': failed_checks
        }


def validate_system(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """系统验证的便捷函数"""
    validator = SystemValidator()
    
    if config is None:
        # 使用默认配置
        config = {
            'validation': {
                'min_python_version': [3, 8],
                'required_packages': [
                    'click', 'sqlalchemy', 'tweepy', 'google.generativeai',
                    'pyyaml', 'python-dotenv', 'psutil'
                ],
                'required_env_vars': [],
                'optional_env_vars': [
                    'TWITTER_API_KEY', 'TWITTER_API_SECRET',
                    'TWITTER_ACCESS_TOKEN', 'TWITTER_ACCESS_TOKEN_SECRET',
                    'GEMINI_API_KEY'
                ],
                'check_paths': ['./config/enhanced_config.yaml', './logs', './data'],
                'required_files': ['./app/main.py'],
                'required_dirs': ['./app', './app/core', './app/utils', './app/database']
            }
        }
    
    return validator.run_full_validation(config)