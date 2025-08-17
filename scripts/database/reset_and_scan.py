#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库重置和项目扫描脚本
重构版本，提供更好的错误处理和日志记录
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.db_manager import EnhancedDatabaseManager
from app.core.project_manager import ProjectManager
from app.utils.logger import setup_logger, get_logger
from app.utils.enhanced_config import get_enhanced_config


class DatabaseResetError(Exception):
    """数据库重置错误"""
    pass


class ProjectScanError(Exception):
    """项目扫描错误"""
    pass


class DatabaseResetManager:
    """数据库重置管理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or get_enhanced_config()
        self.logger = get_logger('database_reset')
        self.db_manager = None
        
    def initialize(self) -> bool:
        """初始化数据库管理器"""
        try:
            # 获取数据库路径
            db_path = self.config.get('database', {}).get('path', 'data/twitter_publisher.db')
            if not os.path.isabs(db_path):
                db_path = project_root / db_path
            
            # 确保数据目录存在
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            # 初始化数据库管理器
            self.db_manager = EnhancedDatabaseManager()
            init_result = self.db_manager.initialize_database()
            
            if not init_result['success']:
                raise DatabaseResetError(f"数据库初始化失败: {init_result['message']}")
            
            self.logger.info("数据库管理器初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            raise DatabaseResetError(f"初始化失败: {e}")
    
    def clear_database_content(self) -> Dict[str, Any]:
        """清空数据库内容（保留表结构）"""
        try:
            self.logger.info("开始清空数据库内容...")
            
            session = self.db_manager.get_session()
            try:
                from app.database.models import (
                    PublishingTask, PublishingLog, ContentSource, 
                    Project, AnalyticsHourly
                )
                
                # 按依赖关系顺序删除
                tables_to_clear = [
                    (PublishingLog, "发布日志"),
                    (AnalyticsHourly, "分析数据"),
                    (PublishingTask, "发布任务"),
                    (ContentSource, "内容源"),
                    (Project, "项目")
                ]
                
                cleared_counts = {}
                for model_class, name in tables_to_clear:
                    count = session.query(model_class).count()
                    if count > 0:
                        session.query(model_class).delete()
                        cleared_counts[name] = count
                        self.logger.info(f"清空 {name}: {count} 条记录")
                
                session.commit()
            finally:
                session.close()
                
            self.logger.info("数据库内容清空完成")
            return {
                'success': True,
                'cleared_counts': cleared_counts,
                'message': '数据库内容清空成功'
            }
            
        except Exception as e:
            self.logger.error(f"清空数据库失败: {e}")
            raise DatabaseResetError(f"清空数据库失败: {e}")
    
    def ensure_admin_user(self) -> Dict[str, Any]:
        """确保管理员用户存在"""
        try:
            session = self.db_manager.get_session()
            try:
                from app.database.models import User
                
                # 检查是否存在管理员用户
                admin_user = session.query(User).filter_by(username='admin').first()
                
                if not admin_user:
                    # 创建管理员用户
                    admin_user = User(
                        username='admin',
                        role='admin'
                    )
                    session.add(admin_user)
                    session.commit()
                    self.logger.info("创建管理员用户成功")
                    return {
                        'success': True,
                        'created': True,
                        'user_id': admin_user.id
                    }
                else:
                    self.logger.info("管理员用户已存在")
                    return {
                        'success': True,
                        'created': False,
                        'user_id': admin_user.id
                    }
            finally:
                session.close()
                    
        except Exception as e:
            self.logger.error(f"确保管理员用户失败: {e}")
            raise DatabaseResetError(f"确保管理员用户失败: {e}")
    
    def get_project_folders(self, base_path: str) -> List[str]:
        """获取项目文件夹列表"""
        try:
            base_path = Path(base_path)
            if not base_path.exists():
                raise ProjectScanError(f"项目基础路径不存在: {base_path}")
            
            project_folders = []
            for item in base_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    # 检查是否包含必要的子目录
                    video_dir = item / "output_video_music"
                    json_dir = item / "uploader_json"
                    
                    if video_dir.exists() and json_dir.exists():
                        project_folders.append(item.name)
                        self.logger.info(f"发现有效项目文件夹: {item.name}")
                    else:
                        self.logger.warning(f"跳过无效项目文件夹: {item.name} (缺少必要子目录)")
            
            if not project_folders:
                raise ProjectScanError(f"在 {base_path} 中未找到有效的项目文件夹")
            
            self.logger.info(f"共发现 {len(project_folders)} 个有效项目文件夹")
            return project_folders
            
        except Exception as e:
            self.logger.error(f"获取项目文件夹失败: {e}")
            raise ProjectScanError(f"获取项目文件夹失败: {e}")
    
    def scan_projects(self, project_folders: List[str], base_path: str, user_id: int) -> Dict[str, Any]:
        """扫描项目并创建任务"""
        try:
            self.logger.info("开始扫描项目并创建任务...")
            
            session = self.db_manager.get_session()
            try:
                project_manager = ProjectManager(session, base_path, user_id=user_id)
                
                scan_results = {
                    'total_projects': len(project_folders),
                    'successful_projects': 0,
                    'failed_projects': 0,
                    'total_tasks_created': 0,
                    'project_details': {},
                    'errors': []
                }
                
                for project_name in project_folders:
                    try:
                        self.logger.info(f"扫描项目: {project_name}")
                        
                        # 扫描单个项目，设置较大的max_tasks_per_scan以创建更多任务
                        new_tasks_count = project_manager.scan_and_create_tasks(project_name, "en", max_tasks_per_scan=100)
                        
                        scan_results['successful_projects'] += 1
                        scan_results['total_tasks_created'] += new_tasks_count
                        scan_results['project_details'][project_name] = {
                            'status': 'success',
                            'tasks_created': new_tasks_count
                        }
                        
                        self.logger.info(f"项目 '{project_name}' 扫描完成，创建了 {new_tasks_count} 个任务")
                        
                    except Exception as e:
                        error_msg = f"扫描项目 '{project_name}' 失败: {e}"
                        self.logger.error(error_msg)
                        
                        scan_results['failed_projects'] += 1
                        scan_results['project_details'][project_name] = {
                            'status': 'failed',
                            'error': str(e)
                        }
                        scan_results['errors'].append(error_msg)
                
                # 提交事务
                session.commit()
                self.logger.info("任务创建事务已提交")
                
                return scan_results
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"扫描项目失败: {e}")
            raise ProjectScanError(f"扫描项目失败: {e}")
    
    def reset_and_scan(self, project_base_path: str = None) -> Dict[str, Any]:
        """完整的重置和扫描流程"""
        start_time = datetime.now()
        
        try:
            # 1. 初始化
            self.initialize()
            
            # 2. 清空数据库内容
            clear_result = self.clear_database_content()
            
            # 3. 确保管理员用户存在
            admin_result = self.ensure_admin_user()
            user_id = admin_result['user_id']
            
            # 4. 获取项目文件夹
            if not project_base_path:
                project_base_path = self.config.get('projects', {}).get('base_path', 'project')
                if not os.path.isabs(project_base_path):
                    project_base_path = project_root / project_base_path
            
            project_folders = self.get_project_folders(project_base_path)
            
            # 5. 扫描项目并创建任务
            scan_results = self.scan_projects(project_folders, project_base_path, user_id)
            
            # 6. 计算总耗时
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 7. 汇总结果
            final_result = {
                'success': True,
                'duration_seconds': duration,
                'database_cleared': clear_result['cleared_counts'],
                'admin_user': {
                    'created': admin_result['created'],
                    'user_id': admin_result['user_id']
                },
                'scan_results': scan_results,
                'summary': {
                    'total_projects': scan_results['total_projects'],
                    'successful_projects': scan_results['successful_projects'],
                    'failed_projects': scan_results['failed_projects'],
                    'total_tasks_created': scan_results['total_tasks_created']
                }
            }
            
            self.logger.info("=" * 60)
            self.logger.info("数据库重置和项目扫描完成！")
            self.logger.info(f"总耗时: {duration:.2f} 秒")
            self.logger.info(f"总项目数: {scan_results['total_projects']}")
            self.logger.info(f"成功项目数: {scan_results['successful_projects']}")
            self.logger.info(f"失败项目数: {scan_results['failed_projects']}")
            self.logger.info(f"总任务创建数: {scan_results['total_tasks_created']}")
            self.logger.info("=" * 60)
            
            return final_result
            
        except Exception as e:
            self.logger.error(f"重置和扫描流程失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'duration_seconds': (datetime.now() - start_time).total_seconds()
            }


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='数据库重置和项目扫描工具')
    parser.add_argument('--project-path', help='项目文件夹路径')
    parser.add_argument('--config-file', help='配置文件路径')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='日志级别')
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logger(log_level=args.log_level)
    logger = get_logger('main')
    
    try:
        # 创建重置管理器
        reset_manager = DatabaseResetManager()
        
        # 执行重置和扫描
        result = reset_manager.reset_and_scan(args.project_path)
        
        if result['success']:
            logger.info("操作成功完成")
            sys.exit(0)
        else:
            logger.error(f"操作失败: {result['error']}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()