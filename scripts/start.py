#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统启动脚本
集成配置验证、依赖检查和服务启动
"""

import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.enhanced_config import get_enhanced_config
from app.utils.config_validator import ConfigValidator
from app.utils.logger import setup_logger, get_logger

def check_dependencies():
    """检查系统依赖"""
    logger = get_logger(__name__)
    
    try:
        # 检查Python版本
        if sys.version_info < (3, 8):
            logger.error(f"Python版本过低: {sys.version}，需要Python 3.8+")
            return False
        
        # 检查必需的包
        package_mapping = {
            'fastapi': 'fastapi',
            'uvicorn': 'uvicorn', 
            'sqlalchemy': 'sqlalchemy',
            'tweepy': 'tweepy',
            'google-generativeai': 'google.generativeai',
            'pyyaml': 'yaml',
            'python-dotenv': 'dotenv',
            'requests': 'requests',
            'psutil': 'psutil',
            'click': 'click',
            'pydantic': 'pydantic'
        }
        
        missing_packages = []
        for package_name, import_name in package_mapping.items():
            try:
                __import__(import_name)
            except ImportError:
                missing_packages.append(package_name)
        
        if missing_packages:
            logger.error(f"缺少必需的包: {', '.join(missing_packages)}")
            logger.info("请运行: pip install -r requirements.txt")
            return False
        
        logger.info("依赖检查通过")
        return True
        
    except Exception as e:
        logger.error(f"依赖检查失败: {e}")
        return False

def validate_configuration():
    """验证配置"""
    logger = get_logger(__name__)
    
    try:
        config = get_enhanced_config()
        validator = ConfigValidator()
        
        result = validator.validate_all()
        
        if not result['valid']:
            logger.error("配置验证失败:")
            for error in result['errors']:
                logger.error(f"  - {error}")
            
            if result['warnings']:
                logger.warning("配置警告:")
                for warning in result['warnings']:
                    logger.warning(f"  - {warning}")
            
            return False
        
        if result['warnings']:
            logger.warning("配置警告:")
            for warning in result['warnings']:
                logger.warning(f"  - {warning}")
        
        logger.info("配置验证通过")
        return True
        
    except Exception as e:
        logger.error(f"配置验证失败: {e}")
        return False

def initialize_database():
    """初始化数据库"""
    logger = get_logger(__name__)
    
    try:
        from app.database.database import DatabaseManager
        config = get_enhanced_config()
        db_config = config.get_database_config()
        db_url = db_config['url']
        
        if not db_url.startswith('sqlite:///'):
            db_url = f"sqlite:///{config.get_absolute_path(db_url)}"
        
        db_manager = DatabaseManager(db_url)
        db_manager.create_tables()
        
        # 确保默认用户存在
        with db_manager.get_session_context() as session:
            from app.database.repository import UserRepository
            user_repo = UserRepository(session)
            
            if not user_repo.get_user_by_username('admin'):
                user_repo.create({
                    'username': 'admin',
                    'role': 'admin'
                })
                logger.info("创建默认管理员用户")
        
        logger.info("数据库初始化完成")
        return True
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return False

def start_api_server(host='127.0.0.1', port=8050, reload=False):
    """启动API服务器"""
    logger = get_logger(__name__)
    
    try:
        import uvicorn
        
        logger.info(f"启动API服务器: http://{host}:{port}")
        
        uvicorn.run(
            "api.main:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info",
            access_log=True
        )
        
    except Exception as e:
        logger.error(f"API服务器启动失败: {e}")
        return False

def start_scheduler():
    """启动任务调度器"""
    import random
    import time
    logger = get_logger(__name__)
    
    try:
        from app.core.task_scheduler import TaskScheduler
        from app.core.publisher import TwitterPublisher
        from app.core.content_generator import ContentGenerator
        from app.database.database import DatabaseManager
        config = get_enhanced_config()
        db_config = config.get_database_config()
        db_url = db_config['url']
        
        if not db_url.startswith('sqlite:///'):
            db_url = f"sqlite:///{config.get_absolute_path(db_url)}"
        
        db_manager = DatabaseManager(db_url)
        
        with db_manager.get_session_context() as session:
            # 初始化发布器和内容生成器
            import os
            publisher = TwitterPublisher(
                api_key=os.getenv('TWITTER_API_KEY'),
                api_secret=os.getenv('TWITTER_API_SECRET'),
                access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
                access_token_secret=os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            )
            content_generator = ContentGenerator(
                use_ai=True,
                gemini_api_key=os.getenv('GEMINI_API_KEY')
            )
            
            scheduler = TaskScheduler(
                db_session=session,
                publisher=publisher,
                content_generator=content_generator,
                config=config,
                user_id=1
            )
            
            logger.info("启动任务调度器")
            
            # 连续运行调度器
            while True:
                try:
                    # 执行单个任务
                    success = scheduler.run_single_task()
                    
                    if success:
                        logger.info("任务执行成功，等待下一个调度周期")
                    else:
                        logger.info("没有待处理任务，等待新任务")
                    
                    # 等待下一个调度周期（15-30分钟）
                    wait_minutes = random.randint(15, 30)
                    logger.info(f"等待 {wait_minutes} 分钟后执行下一个任务")
                    time.sleep(wait_minutes * 60)
                    
                except KeyboardInterrupt:
                    logger.info("收到停止信号，正在关闭调度器")
                    break
                except Exception as e:
                    logger.error(f"调度器运行出错: {e}")
                    # 出错后等待5分钟再重试
                    time.sleep(300)
        
    except KeyboardInterrupt:
        logger.info("任务调度器已停止")
    except Exception as e:
        logger.error(f"任务调度器启动失败: {e}")
        return False

def scan_projects():
    """扫描项目并创建任务"""
    logger = get_logger(__name__)
    
    try:
        from app.core.project_manager import ProjectManager
        from app.database.database import DatabaseManager
        config = get_enhanced_config()
        db_config = config.get_database_config()
        db_url = db_config['url']
        
        if not db_url.startswith('sqlite:///'):
            db_url = f"sqlite:///{config.get_absolute_path(db_url)}"
        
        db_manager = DatabaseManager(db_url)
        
        with db_manager.get_session_context() as session:
            project_base_path = config.get_project_path()
            project_manager = ProjectManager(session, project_base_path)
            
            logger.info(f"扫描项目目录: {project_base_path}")
            
            # 扫描指定项目（这里假设扫描maker_music_chuangxinyewu项目）
            project_name = "maker_music_chuangxinyewu"
            language = "en"
            
            new_tasks_count = project_manager.scan_and_create_tasks(project_name, language)
            
            logger.info(f"扫描完成: 为项目 '{project_name}' 创建了 {new_tasks_count} 个新任务")
        
        return True
        
    except Exception as e:
        logger.error(f"项目扫描失败: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Twitter自动发布系统启动脚本")
    parser.add_argument('command', choices=['api', 'scheduler', 'scan', 'validate'], 
                       help='要执行的命令')
    parser.add_argument('--host', default='127.0.0.1', help='API服务器主机地址')
    parser.add_argument('--port', type=int, default=8050, help='API服务器端口')
    parser.add_argument('--reload', action='store_true', help='启用自动重载（开发模式）')
    parser.add_argument('--skip-validation', action='store_true', help='跳过配置验证')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 设置日志
    log_level = 'DEBUG' if args.verbose else 'INFO'
    setup_logger(log_level=log_level)
    logger = get_logger(__name__)
    
    logger.info("=" * 60)
    logger.info("Twitter自动发布系统启动")
    logger.info("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        logger.error("依赖检查失败，程序退出")
        sys.exit(1)
    
    # 验证配置（除非跳过）
    if not args.skip_validation:
        if not validate_configuration():
            logger.error("配置验证失败，程序退出")
            sys.exit(1)
    
    # 初始化数据库
    if args.command in ['api', 'scheduler', 'scan']:
        if not initialize_database():
            logger.error("数据库初始化失败，程序退出")
            sys.exit(1)
    
    # 执行命令
    try:
        if args.command == 'api':
            start_api_server(args.host, args.port, args.reload)
        elif args.command == 'scheduler':
            start_scheduler()
        elif args.command == 'scan':
            if scan_projects():
                logger.info("项目扫描完成")
            else:
                sys.exit(1)
        elif args.command == 'validate':
            logger.info("配置验证完成")
        
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        sys.exit(1)
    
    logger.info("程序正常退出")

if __name__ == "__main__":
    main()