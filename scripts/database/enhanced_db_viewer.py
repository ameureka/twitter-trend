#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版数据库查看器 - 统一的数据库查看和管理工具
整合了原有的多个查看脚本功能，提供更好的用户体验
"""

import sys
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from app.database.database import DatabaseManager
    from app.database.models import (
        User, ApiKey, Project, ContentSource, 
        PublishingTask, PublishingLog, AnalyticsHourly
    )
    from app.utils.path_manager import get_path_manager
    from sqlalchemy import create_engine, desc, asc, func, inspect
    from sqlalchemy.orm import sessionmaker
    ADVANCED_MODE = True
except ImportError as e:
    print(f"⚠️  高级模式不可用，使用基础SQLite模式: {e}")
    ADVANCED_MODE = False

class ViewMode(Enum):
    """查看模式枚举"""
    OVERVIEW = "overview"           # 概览
    TASKS = "tasks"                 # 任务详情
    PENDING = "pending"             # 待发布任务
    RECENT = "recent"               # 最近任务
    PROJECTS = "projects"           # 项目信息
    LOGS = "logs"                   # 发布日志
    ANALYTICS = "analytics"         # 分析数据
    HEALTH = "health"               # 健康检查
    INTERACTIVE = "interactive"     # 交互模式

@dataclass
class DatabaseStats:
    """数据库统计信息"""
    total_tasks: int = 0
    pending_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_projects: int = 0
    active_projects: int = 0
    total_users: int = 0
    total_logs: int = 0
    db_size_mb: float = 0.0
    last_activity: Optional[datetime] = None

class EnhancedDatabaseViewer:
    """增强版数据库查看器"""
    
    def __init__(self):
        self.db_manager = None
        self.session = None
        self.engine = None
        self.stats = DatabaseStats()
        self._initialize_database()
    
    def _initialize_database(self):
        """初始化数据库连接"""
        try:
            if ADVANCED_MODE:
                self.db_manager = DatabaseManager()
                self.session = self.db_manager.get_session()
                self.engine = self.db_manager.engine
            else:
                # 基础SQLite模式
                db_path = 'data/twitter_publisher.db'
                if os.path.exists(db_path):
                    self.db_path = db_path
                else:
                    print(f"❌ 数据库文件不存在: {db_path}")
                    sys.exit(1)
        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
            sys.exit(1)
    
    def _get_basic_stats(self) -> DatabaseStats:
        """获取基础统计信息（SQLite模式）"""
        stats = DatabaseStats()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [table[0] for table in cursor.fetchall()]
            
            if 'publishing_tasks' in tables:
                cursor.execute("SELECT COUNT(*) FROM publishing_tasks")
                stats.total_tasks = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE status = 'pending'")
                stats.pending_tasks = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE status = 'completed'")
                stats.completed_tasks = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE status = 'failed'")
                stats.failed_tasks = cursor.fetchone()[0]
            
            if 'projects' in tables:
                cursor.execute("SELECT COUNT(*) FROM projects")
                stats.total_projects = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM projects WHERE status = 'active'")
                stats.active_projects = cursor.fetchone()[0]
            
            if 'users' in tables:
                cursor.execute("SELECT COUNT(*) FROM users")
                stats.total_users = cursor.fetchone()[0]
            
            if 'publishing_logs' in tables:
                cursor.execute("SELECT COUNT(*) FROM publishing_logs")
                stats.total_logs = cursor.fetchone()[0]
            
            # 数据库文件大小
            if os.path.exists(self.db_path):
                stats.db_size_mb = os.path.getsize(self.db_path) / 1024 / 1024
            
            conn.close()
            
        except Exception as e:
            print(f"⚠️  获取统计信息失败: {e}")
        
        return stats
    
    def _get_advanced_stats(self) -> DatabaseStats:
        """获取高级统计信息（SQLAlchemy模式）"""
        stats = DatabaseStats()
        try:
            # 任务统计
            stats.total_tasks = self.session.query(PublishingTask).count()
            stats.pending_tasks = self.session.query(PublishingTask).filter(
                PublishingTask.status == 'pending'
            ).count()
            stats.completed_tasks = self.session.query(PublishingTask).filter(
                PublishingTask.status == 'completed'
            ).count()
            stats.failed_tasks = self.session.query(PublishingTask).filter(
                PublishingTask.status == 'failed'
            ).count()
            
            # 项目统计
            stats.total_projects = self.session.query(Project).count()
            stats.active_projects = self.session.query(Project).filter(
                Project.status == 'active'
            ).count()
            
            # 用户统计
            stats.total_users = self.session.query(User).count()
            
            # 日志统计
            stats.total_logs = self.session.query(PublishingLog).count()
            
            # 最后活动时间
            last_task = self.session.query(PublishingTask).order_by(
                desc(PublishingTask.updated_at)
            ).first()
            if last_task:
                stats.last_activity = last_task.updated_at
            
            # 数据库文件大小
            if self.db_manager and self.db_manager.db_path and self.db_manager.db_path.exists():
                stats.db_size_mb = self.db_manager.db_path.stat().st_size / 1024 / 1024
            
        except Exception as e:
            print(f"⚠️  获取高级统计信息失败: {e}")
        
        return stats
    
    def get_stats(self) -> DatabaseStats:
        """获取数据库统计信息"""
        if ADVANCED_MODE:
            self.stats = self._get_advanced_stats()
        else:
            self.stats = self._get_basic_stats()
        return self.stats
    
    def show_overview(self):
        """显示数据库概览"""
        print("\n" + "=" * 80)
        print("🗄️  Twitter 自动发布系统 - 数据库概览")
        print("=" * 80)
        print(f"📅 查看时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔧 运行模式: {'高级模式 (SQLAlchemy)' if ADVANCED_MODE else '基础模式 (SQLite)'}")
        
        stats = self.get_stats()
        
        print(f"\n📊 数据库统计")
        print("-" * 40)
        print(f"💾 数据库大小: {stats.db_size_mb:.2f} MB")
        print(f"👥 用户总数: {stats.total_users}")
        print(f"📁 项目总数: {stats.total_projects} (活跃: {stats.active_projects})")
        print(f"📝 任务总数: {stats.total_tasks}")
        print(f"⏳ 待发布: {stats.pending_tasks}")
        print(f"✅ 已完成: {stats.completed_tasks}")
        print(f"❌ 失败: {stats.failed_tasks}")
        print(f"📋 日志总数: {stats.total_logs}")
        
        if stats.last_activity:
            print(f"🕐 最后活动: {stats.last_activity}")
        
        # 计算完成率
        if stats.total_tasks > 0:
            completion_rate = (stats.completed_tasks / stats.total_tasks) * 100
            print(f"📈 完成率: {completion_rate:.1f}%")
        
        print("\n" + "=" * 80)
    
    def show_pending_tasks(self, limit: int = 10):
        """显示待发布任务"""
        print(f"\n⏳ 待发布任务 (最多显示 {limit} 个)")
        print("=" * 60)
        
        if ADVANCED_MODE:
            self._show_pending_tasks_advanced(limit)
        else:
            self._show_pending_tasks_basic(limit)
    
    def _show_pending_tasks_advanced(self, limit: int):
        """显示待发布任务（高级模式）"""
        try:
            tasks = self.session.query(PublishingTask).join(Project).filter(
                PublishingTask.status == 'pending'
            ).order_by(desc(PublishingTask.scheduled_at)).limit(limit).all()
            
            if not tasks:
                print("📭 没有待发布的任务")
                return
            
            for i, task in enumerate(tasks, 1):
                print(f"\n📋 任务 {i} (ID: {task.id})")
                print(f"   项目: {task.project.name if task.project else 'Unknown'}")
                print(f"   媒体: {Path(task.media_path).name if task.media_path else 'N/A'}")
                print(f"   优先级: {task.priority}")
                print(f"   计划时间: {task.scheduled_at}")
                
                # 计算时间差
                if task.scheduled_at:
                    now = datetime.now()
                    scheduled_naive = task.scheduled_at.replace(tzinfo=None) if task.scheduled_at.tzinfo else task.scheduled_at
                    time_diff = now - scheduled_naive
                    if time_diff.total_seconds() > 0:
                        print(f"   ⏰ 已过期: {time_diff}")
                    else:
                        print(f"   ⏳ 还有: {abs(time_diff)} 后执行")
                
                # 显示内容摘要
                if task.content_data:
                    try:
                        content = json.loads(task.content_data)
                        if content.get('title'):
                            print(f"   📝 标题: {content.get('title')[:50]}...")
                    except:
                        pass
                
                print("-" * 40)
        
        except Exception as e:
            print(f"❌ 查询待发布任务失败: {e}")
    
    def _show_pending_tasks_basic(self, limit: int):
        """显示待发布任务（基础模式）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, project_id, media_path, priority, scheduled_at, content_data
                FROM publishing_tasks 
                WHERE status = 'pending' 
                ORDER BY scheduled_at DESC 
                LIMIT ?
            """, (limit,))
            
            tasks = cursor.fetchall()
            
            if not tasks:
                print("📭 没有待发布的任务")
                return
            
            for i, task in enumerate(tasks, 1):
                task_id, project_id, media_path, priority, scheduled_at, content_data = task
                print(f"\n📋 任务 {i} (ID: {task_id})")
                print(f"   项目ID: {project_id}")
                print(f"   媒体: {Path(media_path).name if media_path else 'N/A'}")
                print(f"   优先级: {priority}")
                print(f"   计划时间: {scheduled_at}")
                
                # 显示内容摘要
                if content_data:
                    try:
                        content = json.loads(content_data)
                        if content.get('title'):
                            print(f"   📝 标题: {content.get('title')[:50]}...")
                    except:
                        pass
                
                print("-" * 40)
            
            conn.close()
        
        except Exception as e:
            print(f"❌ 查询待发布任务失败: {e}")
    
    def show_recent_tasks(self, limit: int = 10):
        """显示最近任务"""
        print(f"\n🕐 最近任务 (最多显示 {limit} 个)")
        print("=" * 60)
        
        if ADVANCED_MODE:
            self._show_recent_tasks_advanced(limit)
        else:
            self._show_recent_tasks_basic(limit)
    
    def _show_recent_tasks_advanced(self, limit: int):
        """显示最近任务（高级模式）"""
        try:
            tasks = self.session.query(PublishingTask).join(Project).order_by(
                desc(PublishingTask.created_at)
            ).limit(limit).all()
            
            if not tasks:
                print("📭 没有找到任务")
                return
            
            for i, task in enumerate(tasks, 1):
                status_emoji = {
                    'pending': '⏳',
                    'completed': '✅',
                    'failed': '❌',
                    'running': '🔄'
                }.get(task.status, '❓')
                
                print(f"\n{status_emoji} 任务 {i} (ID: {task.id})")
                print(f"   项目: {task.project.name if task.project else 'Unknown'}")
                print(f"   状态: {task.status}")
                print(f"   媒体: {Path(task.media_path).name if task.media_path else 'N/A'}")
                print(f"   创建时间: {task.created_at}")
                print(f"   更新时间: {task.updated_at}")
                print("-" * 40)
        
        except Exception as e:
            print(f"❌ 查询最近任务失败: {e}")
    
    def _show_recent_tasks_basic(self, limit: int):
        """显示最近任务（基础模式）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, project_id, status, media_path, created_at, updated_at
                FROM publishing_tasks 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            
            tasks = cursor.fetchall()
            
            if not tasks:
                print("📭 没有找到任务")
                return
            
            for i, task in enumerate(tasks, 1):
                task_id, project_id, status, media_path, created_at, updated_at = task
                
                status_emoji = {
                    'pending': '⏳',
                    'completed': '✅',
                    'failed': '❌',
                    'running': '🔄'
                }.get(status, '❓')
                
                print(f"\n{status_emoji} 任务 {i} (ID: {task_id})")
                print(f"   项目ID: {project_id}")
                print(f"   状态: {status}")
                print(f"   媒体: {Path(media_path).name if media_path else 'N/A'}")
                print(f"   创建时间: {created_at}")
                print(f"   更新时间: {updated_at}")
                print("-" * 40)
            
            conn.close()
        
        except Exception as e:
            print(f"❌ 查询最近任务失败: {e}")
    
    def show_task_details(self, task_id: int):
        """显示任务详细信息"""
        print(f"\n🔍 任务详细信息 (ID: {task_id})")
        print("=" * 60)
        
        if ADVANCED_MODE:
            self._show_task_details_advanced(task_id)
        else:
            self._show_task_details_basic(task_id)
    
    def _show_task_details_advanced(self, task_id: int):
        """显示任务详细信息（高级模式）"""
        try:
            task = self.session.query(PublishingTask).filter(
                PublishingTask.id == task_id
            ).first()
            
            if not task:
                print(f"❌ 未找到ID为 {task_id} 的任务")
                return
            
            print(f"📋 基本信息")
            print(f"   ID: {task.id}")
            print(f"   项目ID: {task.project_id}")
            print(f"   内容源ID: {task.source_id}")
            print(f"   状态: {task.status}")
            print(f"   优先级: {task.priority}")
            print(f"   重试次数: {task.retry_count}")
            print(f"   版本: {task.version}")
            
            print(f"\n📅 时间信息")
            print(f"   计划时间: {task.scheduled_at}")
            print(f"   创建时间: {task.created_at}")
            print(f"   更新时间: {task.updated_at}")
            
            print(f"\n📁 文件信息")
            print(f"   媒体路径: {task.media_path}")
            if task.media_path and Path(task.media_path).exists():
                file_size = Path(task.media_path).stat().st_size
                print(f"   文件大小: {file_size:,} 字节 ({file_size/1024/1024:.2f} MB)")
            
            # 显示内容数据
            print(f"\n📝 内容数据")
            if task.content_data:
                try:
                    content = json.loads(task.content_data)
                    for key, value in content.items():
                        if isinstance(value, str) and len(value) > 100:
                            print(f"   {key}: {value[:100]}...")
                        else:
                            print(f"   {key}: {value}")
                except Exception as e:
                    print(f"   解析失败: {e}")
                    print(f"   原始数据: {task.content_data[:200]}...")
            else:
                print("   无内容数据")
            
            # 显示关联信息
            if task.project:
                print(f"\n🏗️  关联项目")
                print(f"   名称: {task.project.name}")
                print(f"   描述: {task.project.description}")
                print(f"   状态: {task.project.status}")
            
            # 显示发布日志
            logs = self.session.query(PublishingLog).filter(
                PublishingLog.task_id == task_id
            ).order_by(desc(PublishingLog.published_at)).limit(3).all()
            
            if logs:
                print(f"\n📋 发布日志 (最近3条)")
                for log in logs:
                    print(f"   - {log.published_at}: {log.status}")
                    if log.tweet_id:
                        print(f"     推文ID: {log.tweet_id}")
                    if log.error_message:
                        print(f"     错误: {log.error_message}")
        
        except Exception as e:
            print(f"❌ 查询任务详情失败: {e}")
    
    def _show_task_details_basic(self, task_id: int):
        """显示任务详细信息（基础模式）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM publishing_tasks WHERE id = ?
            """, (task_id,))
            
            task = cursor.fetchone()
            
            if not task:
                print(f"❌ 未找到ID为 {task_id} 的任务")
                return
            
            # 获取列名
            cursor.execute("PRAGMA table_info(publishing_tasks)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # 创建字典
            task_dict = dict(zip(columns, task))
            
            print(f"📋 任务详细信息")
            for key, value in task_dict.items():
                if key == 'content_data' and value:
                    try:
                        content = json.loads(value)
                        print(f"   {key}:")
                        for k, v in content.items():
                            if isinstance(v, str) and len(v) > 100:
                                print(f"     {k}: {v[:100]}...")
                            else:
                                print(f"     {k}: {v}")
                    except:
                        print(f"   {key}: {value[:200]}...")
                else:
                    print(f"   {key}: {value}")
            
            conn.close()
        
        except Exception as e:
            print(f"❌ 查询任务详情失败: {e}")
    
    def show_projects(self):
        """显示项目信息"""
        print(f"\n🏗️  项目信息")
        print("=" * 60)
        
        if ADVANCED_MODE:
            self._show_projects_advanced()
        else:
            self._show_projects_basic()
    
    def _show_projects_advanced(self):
        """显示项目信息（高级模式）"""
        try:
            projects = self.session.query(Project).all()
            
            if not projects:
                print("📭 没有找到项目")
                return
            
            for project in projects:
                # 统计项目任务
                task_count = self.session.query(PublishingTask).filter(
                    PublishingTask.project_id == project.id
                ).count()
                
                pending_count = self.session.query(PublishingTask).filter(
                    PublishingTask.project_id == project.id,
                    PublishingTask.status == 'pending'
                ).count()
                
                print(f"\n📁 {project.name} (ID: {project.id})")
                print(f"   状态: {project.status}")
                print(f"   描述: {project.description}")
                print(f"   用户ID: {project.user_id}")
                print(f"   任务总数: {task_count} (待发布: {pending_count})")
                print(f"   创建时间: {project.created_at}")
                print("-" * 40)
        
        except Exception as e:
            print(f"❌ 查询项目信息失败: {e}")
    
    def _show_projects_basic(self):
        """显示项目信息（基础模式）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM projects")
            projects = cursor.fetchall()
            
            if not projects:
                print("📭 没有找到项目")
                return
            
            # 获取列名
            cursor.execute("PRAGMA table_info(projects)")
            columns = [col[1] for col in cursor.fetchall()]
            
            for project in projects:
                project_dict = dict(zip(columns, project))
                project_id = project_dict.get('id')
                
                # 统计任务数量
                cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE project_id = ?", (project_id,))
                task_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE project_id = ? AND status = 'pending'", (project_id,))
                pending_count = cursor.fetchone()[0]
                
                print(f"\n📁 {project_dict.get('name', 'Unknown')} (ID: {project_id})")
                print(f"   状态: {project_dict.get('status', 'Unknown')}")
                print(f"   描述: {project_dict.get('description', 'N/A')}")
                print(f"   任务总数: {task_count} (待发布: {pending_count})")
                print(f"   创建时间: {project_dict.get('created_at', 'Unknown')}")
                print("-" * 40)
            
            conn.close()
        
        except Exception as e:
            print(f"❌ 查询项目信息失败: {e}")
    
    def show_health_check(self):
        """显示健康检查信息"""
        print(f"\n🏥 数据库健康检查")
        print("=" * 60)
        
        try:
            if ADVANCED_MODE and hasattr(self.db_manager, 'check_database_health'):
                health_info = self.db_manager.check_database_health()
                for key, value in health_info.items():
                    print(f"   {key}: {value}")
            else:
                # 基础健康检查
                print(f"   数据库文件: {'✅ 存在' if os.path.exists(self.db_path) else '❌ 不存在'}")
                
                if os.path.exists(self.db_path):
                    file_size = os.path.getsize(self.db_path)
                    print(f"   文件大小: {file_size:,} 字节 ({file_size/1024/1024:.2f} MB)")
                    
                    # 检查表结构
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()
                    print(f"   表数量: {len(tables)}")
                    
                    for table in tables:
                        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                        count = cursor.fetchone()[0]
                        print(f"     - {table[0]}: {count} 条记录")
                    
                    conn.close()
        
        except Exception as e:
            print(f"❌ 健康检查失败: {e}")
    
    def interactive_mode(self):
        """交互模式"""
        print(f"\n🎮 交互模式")
        print("=" * 60)
        print("可用命令:")
        print("  1. overview    - 显示概览")
        print("  2. pending     - 显示待发布任务")
        print("  3. recent      - 显示最近任务")
        print("  4. projects    - 显示项目信息")
        print("  5. health      - 健康检查")
        print("  6. task <id>   - 显示任务详情")
        print("  7. help        - 显示帮助")
        print("  8. quit/exit   - 退出")
        print("-" * 60)
        
        while True:
            try:
                command = input("\n🔍 请输入命令: ").strip().lower()
                
                if command in ['quit', 'exit', 'q']:
                    print("👋 再见!")
                    break
                elif command == 'overview':
                    self.show_overview()
                elif command == 'pending':
                    self.show_pending_tasks()
                elif command == 'recent':
                    self.show_recent_tasks()
                elif command == 'projects':
                    self.show_projects()
                elif command == 'health':
                    self.show_health_check()
                elif command.startswith('task '):
                    try:
                        task_id = int(command.split()[1])
                        self.show_task_details(task_id)
                    except (IndexError, ValueError):
                        print("❌ 请提供有效的任务ID，例如: task 123")
                elif command == 'help':
                    print("\n📖 帮助信息:")
                    print("  - overview: 显示数据库概览和统计信息")
                    print("  - pending: 显示所有待发布的任务")
                    print("  - recent: 显示最近创建的任务")
                    print("  - projects: 显示所有项目信息")
                    print("  - health: 执行数据库健康检查")
                    print("  - task <id>: 显示指定ID的任务详细信息")
                    print("  - quit/exit: 退出交互模式")
                else:
                    print("❌ 未知命令，输入 'help' 查看可用命令")
            
            except KeyboardInterrupt:
                print("\n👋 再见!")
                break
            except Exception as e:
                print(f"❌ 执行命令时出错: {e}")
    
    def close(self):
        """关闭数据库连接"""
        try:
            if self.session:
                self.session.close()
            if self.db_manager:
                self.db_manager.close()
        except Exception as e:
            print(f"⚠️  关闭数据库连接时出错: {e}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="增强版数据库查看器 - 统一的数据库查看和管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python enhanced_db_viewer.py                    # 显示概览
  python enhanced_db_viewer.py --mode pending    # 显示待发布任务
  python enhanced_db_viewer.py --mode recent     # 显示最近任务
  python enhanced_db_viewer.py --mode projects   # 显示项目信息
  python enhanced_db_viewer.py --mode health     # 健康检查
  python enhanced_db_viewer.py --mode interactive # 交互模式
  python enhanced_db_viewer.py --task-id 123     # 显示任务详情
        """
    )
    
    parser.add_argument(
        '--mode', '-m',
        choices=[mode.value for mode in ViewMode],
        default=ViewMode.OVERVIEW.value,
        help='查看模式'
    )
    
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=10,
        help='显示记录数量限制 (默认: 10)'
    )
    
    parser.add_argument(
        '--task-id', '-t',
        type=int,
        help='查看指定任务ID的详细信息'
    )
    
    args = parser.parse_args()
    
    viewer = None
    try:
        viewer = EnhancedDatabaseViewer()
        
        if args.task_id:
            viewer.show_task_details(args.task_id)
        elif args.mode == ViewMode.OVERVIEW.value:
            viewer.show_overview()
        elif args.mode == ViewMode.PENDING.value:
            viewer.show_pending_tasks(args.limit)
        elif args.mode == ViewMode.RECENT.value:
            viewer.show_recent_tasks(args.limit)
        elif args.mode == ViewMode.PROJECTS.value:
            viewer.show_projects()
        elif args.mode == ViewMode.HEALTH.value:
            viewer.show_health_check()
        elif args.mode == ViewMode.INTERACTIVE.value:
            viewer.interactive_mode()
        else:
            print(f"❌ 不支持的模式: {args.mode}")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n👋 操作已取消")
    except Exception as e:
        print(f"❌ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if viewer:
            viewer.close()

if __name__ == "__main__":
    main()