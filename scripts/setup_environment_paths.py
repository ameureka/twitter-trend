#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境路径配置脚本

解决问题一：致命的环境不匹配与硬编码路径

主要功能：
1. 检测当前运行环境（macOS开发环境 vs Linux生产环境）
2. 自动配置适合当前环境的基础路径
3. 设置环境变量和配置文件
4. 验证路径配置的正确性

使用方法：
1. 自动检测并配置：python scripts/setup_environment_paths.py
2. 强制指定环境：python scripts/setup_environment_paths.py --env production
3. 验证配置：python scripts/setup_environment_paths.py --verify
"""

import os
import sys
import yaml
import argparse
import platform
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.logger import get_logger

logger = get_logger(__name__)

class EnvironmentPathSetup:
    """环境路径配置器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_path = self.project_root / 'config' / 'enhanced_config.yaml'
        
        # 环境检测规则
        self.environment_patterns = {
            'development': {
                'indicators': [
                    '/Users/',  # macOS用户目录
                    'Desktop',  # 桌面开发
                    platform.system() == 'Darwin'  # macOS系统
                ],
                'base_paths': [
                    '/Users/ameureka/Desktop/twitter-trend',
                    str(self.project_root)
                ]
            },
            'production': {
                'indicators': [
                    '/home/',  # Linux用户目录
                    '/data2/',  # 生产服务器路径
                    platform.system() == 'Linux'  # Linux系统
                ],
                'base_paths': [
                    '/home/twitter-trend',
                    '/data2/twitter-trend'
                ]
            }
        }
        
        logger.info(f"项目根目录: {self.project_root}")
        logger.info(f"当前系统: {platform.system()}")
        logger.info(f"当前工作目录: {os.getcwd()}")
    
    def detect_environment(self) -> str:
        """自动检测当前环境"""
        current_path = str(self.project_root)
        
        # 检查开发环境指标
        dev_score = 0
        for indicator in self.environment_patterns['development']['indicators']:
            if isinstance(indicator, bool):
                if indicator:
                    dev_score += 1
            elif isinstance(indicator, str) and indicator in current_path:
                dev_score += 1
        
        # 检查生产环境指标
        prod_score = 0
        for indicator in self.environment_patterns['production']['indicators']:
            if isinstance(indicator, bool):
                if indicator:
                    prod_score += 1
            elif isinstance(indicator, str) and indicator in current_path:
                prod_score += 1
        
        # 根据得分判断环境
        if dev_score > prod_score:
            detected_env = 'development'
        elif prod_score > dev_score:
            detected_env = 'production'
        else:
            # 默认根据系统类型判断
            detected_env = 'development' if platform.system() == 'Darwin' else 'production'
        
        logger.info(f"环境检测结果: {detected_env} (开发环境得分: {dev_score}, 生产环境得分: {prod_score})")
        return detected_env
    
    def get_optimal_base_path(self, environment: str) -> str:
        """获取最优的基础路径"""
        base_paths = self.environment_patterns[environment]['base_paths']
        
        # 优先使用存在的路径
        for base_path in base_paths:
            if Path(base_path).exists():
                logger.info(f"找到存在的基础路径: {base_path}")
                return base_path
        
        # 如果都不存在，使用当前项目根目录
        fallback_path = str(self.project_root)
        logger.warning(f"预定义路径都不存在，使用当前项目根目录: {fallback_path}")
        return fallback_path
    
    def setup_environment(self, environment: Optional[str] = None) -> Dict[str, Any]:
        """设置环境配置"""
        if environment is None:
            environment = self.detect_environment()
        
        logger.info(f"开始配置 {environment} 环境...")
        
        result = {
            'environment': environment,
            'base_path': None,
            'config_updated': False,
            'env_vars_set': False,
            'project_structure_verified': False,
            'errors': []
        }
        
        try:
            # 1. 确定基础路径
            base_path = self.get_optimal_base_path(environment)
            result['base_path'] = base_path
            
            # 2. 更新配置文件
            self._update_config_file(environment, base_path)
            result['config_updated'] = True
            
            # 3. 设置环境变量
            self._set_environment_variables(environment, base_path)
            result['env_vars_set'] = True
            
            # 4. 验证项目结构
            self._verify_project_structure(base_path)
            result['project_structure_verified'] = True
            
            logger.info(f"环境配置完成: {environment}")
            
        except Exception as e:
            error_msg = f"环境配置失败: {str(e)}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
            raise
        
        return result
    
    def _update_config_file(self, environment: str, base_path: str):
        """更新配置文件"""
        logger.info(f"更新配置文件: {self.config_path}")
        
        # 读取当前配置
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 更新环境相关配置
        config['environment'] = environment
        
        # 设置项目基础路径
        if environment == 'development':
            # 开发环境使用相对路径
            config['project_base_path'] = './project'
        else:
            # 生产环境使用绝对路径
            project_dir = Path(base_path) / 'project'
            config['project_base_path'] = str(project_dir)
        
        # 添加环境特定配置
        if 'path_config' not in config:
            config['path_config'] = {}
        
        config['path_config'].update({
            'base_path': base_path,
            'environment': environment,
            'auto_configured': True,
            'configured_at': str(Path(__file__).stat().st_mtime)
        })
        
        # 创建备份
        backup_path = self.config_path.with_suffix('.yaml.backup')
        if not backup_path.exists():
            import shutil
            shutil.copy2(self.config_path, backup_path)
            logger.info(f"配置文件备份已创建: {backup_path}")
        
        # 写入更新后的配置
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        logger.info(f"配置文件已更新: project_base_path = {config['project_base_path']}")
    
    def _set_environment_variables(self, environment: str, base_path: str):
        """设置环境变量"""
        env_vars = {
            'TWITTER_TREND_BASE_PATH': base_path,
            'TWITTER_TREND_ENV': environment,
            'TWITTER_TREND_PROJECT_PATH': str(Path(base_path) / 'project')
        }
        
        for var_name, var_value in env_vars.items():
            os.environ[var_name] = var_value
            logger.info(f"环境变量已设置: {var_name} = {var_value}")
        
        # 创建环境变量配置文件
        env_file_path = self.project_root / '.env'
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.write(f"# Twitter Trend 环境配置\n")
            f.write(f"# 自动生成于环境配置脚本\n\n")
            for var_name, var_value in env_vars.items():
                f.write(f"{var_name}={var_value}\n")
        
        logger.info(f"环境变量配置文件已创建: {env_file_path}")
    
    def _verify_project_structure(self, base_path: str):
        """验证项目结构"""
        logger.info("验证项目结构...")
        
        base_path_obj = Path(base_path)
        required_dirs = [
            'project',
            'config',
            'app',
            'logs',
            'data'
        ]
        
        missing_dirs = []
        for dir_name in required_dirs:
            dir_path = base_path_obj / dir_name
            if not dir_path.exists():
                missing_dirs.append(str(dir_path))
        
        if missing_dirs:
            logger.warning(f"缺少以下目录: {missing_dirs}")
            # 创建缺少的目录
            for missing_dir in missing_dirs:
                Path(missing_dir).mkdir(parents=True, exist_ok=True)
                logger.info(f"已创建目录: {missing_dir}")
        else:
            logger.info("项目结构验证通过")
    
    def verify_configuration(self) -> Dict[str, Any]:
        """验证当前配置"""
        logger.info("验证当前环境配置...")
        
        verification = {
            'environment_detected': self.detect_environment(),
            'config_file_exists': self.config_path.exists(),
            'config_valid': False,
            'env_vars_set': False,
            'project_structure_valid': False,
            'path_accessibility': {},
            'recommendations': []
        }
        
        try:
            # 验证配置文件
            if verification['config_file_exists']:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                
                verification['config_valid'] = True
                verification['current_config'] = {
                    'environment': config.get('environment'),
                    'project_base_path': config.get('project_base_path'),
                    'path_config': config.get('path_config', {})
                }
            
            # 验证环境变量
            env_vars = ['TWITTER_TREND_BASE_PATH', 'TWITTER_TREND_ENV']
            verification['env_vars_set'] = all(os.environ.get(var) for var in env_vars)
            verification['current_env_vars'] = {var: os.environ.get(var) for var in env_vars}
            
            # 验证路径可访问性
            if verification['config_valid']:
                project_base_path = config.get('project_base_path')
                if project_base_path:
                    if not Path(project_base_path).is_absolute():
                        full_path = self.project_root / project_base_path
                    else:
                        full_path = Path(project_base_path)
                    
                    verification['path_accessibility'] = {
                        'project_base_path': str(full_path),
                        'exists': full_path.exists(),
                        'readable': full_path.exists() and os.access(full_path, os.R_OK),
                        'writable': full_path.exists() and os.access(full_path, os.W_OK)
                    }
            
            # 生成建议
            if not verification['config_valid']:
                verification['recommendations'].append("配置文件无效或不存在，建议运行环境配置")
            
            if not verification['env_vars_set']:
                verification['recommendations'].append("环境变量未设置，建议运行环境配置")
            
            if verification['path_accessibility'].get('exists') is False:
                verification['recommendations'].append("项目路径不存在，建议检查配置或重新运行环境配置")
            
        except Exception as e:
            logger.error(f"配置验证失败: {str(e)}")
            verification['error'] = str(e)
        
        return verification

def print_setup_report(result: Dict[str, Any]):
    """打印配置报告"""
    print("\n" + "="*60)
    print("环境配置报告")
    print("="*60)
    
    print(f"\n🌍 环境信息:")
    print(f"  检测到的环境: {result['environment']}")
    print(f"  基础路径: {result['base_path']}")
    
    print(f"\n✅ 配置结果:")
    print(f"  配置文件已更新: {'是' if result['config_updated'] else '否'}")
    print(f"  环境变量已设置: {'是' if result['env_vars_set'] else '否'}")
    print(f"  项目结构已验证: {'是' if result['project_structure_verified'] else '否'}")
    
    if result['errors']:
        print(f"\n❌ 错误:")
        for error in result['errors']:
            print(f"  - {error}")

def print_verification_report(verification: Dict[str, Any]):
    """打印验证报告"""
    print("\n" + "="*60)
    print("环境配置验证报告")
    print("="*60)
    
    print(f"\n🌍 环境检测:")
    print(f"  当前环境: {verification['environment_detected']}")
    
    print(f"\n📋 配置状态:")
    print(f"  配置文件存在: {'是' if verification['config_file_exists'] else '否'}")
    print(f"  配置文件有效: {'是' if verification['config_valid'] else '否'}")
    print(f"  环境变量已设置: {'是' if verification['env_vars_set'] else '否'}")
    
    if 'current_config' in verification:
        print(f"\n⚙️  当前配置:")
        config = verification['current_config']
        print(f"  环境: {config.get('environment', '未设置')}")
        print(f"  项目基础路径: {config.get('project_base_path', '未设置')}")
    
    if 'current_env_vars' in verification:
        print(f"\n🔧 环境变量:")
        for var, value in verification['current_env_vars'].items():
            print(f"  {var}: {value or '未设置'}")
    
    if verification['path_accessibility']:
        print(f"\n📁 路径可访问性:")
        path_info = verification['path_accessibility']
        print(f"  路径: {path_info['project_base_path']}")
        print(f"  存在: {'是' if path_info['exists'] else '否'}")
        print(f"  可读: {'是' if path_info['readable'] else '否'}")
        print(f"  可写: {'是' if path_info['writable'] else '否'}")
    
    if verification['recommendations']:
        print(f"\n💡 建议:")
        for rec in verification['recommendations']:
            print(f"  - {rec}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='环境路径配置脚本')
    parser.add_argument('--env', choices=['development', 'production'], 
                       help='强制指定环境类型')
    parser.add_argument('--verify', action='store_true', 
                       help='验证当前配置')
    
    args = parser.parse_args()
    
    setup = EnvironmentPathSetup()
    
    try:
        if args.verify:
            verification = setup.verify_configuration()
            print_verification_report(verification)
        else:
            result = setup.setup_environment(args.env)
            print_setup_report(result)
        
        print("\n" + "="*60)
        print("使用说明")
        print("="*60)
        print("1. 自动配置环境: python scripts/setup_environment_paths.py")
        print("2. 指定开发环境: python scripts/setup_environment_paths.py --env development")
        print("3. 指定生产环境: python scripts/setup_environment_paths.py --env production")
        print("4. 验证当前配置: python scripts/setup_environment_paths.py --verify")
        print("\n配置完成后，请重启应用程序以使配置生效。")
        
    except Exception as e:
        logger.error(f"脚本执行失败: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()