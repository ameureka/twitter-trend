#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速数据库监控器 - 简化版数据库状态查看工具
专注于快速查看系统状态和关键指标
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class QuickDBMonitor:
    """快速数据库监控器"""
    
    def __init__(self, db_path: str = 'data/twitter_publisher.db'):
        self.db_path = db_path
        self.check_database()
    
    def check_database(self):
        """检查数据库是否存在"""
        if not os.path.exists(self.db_path):
            print(f"❌ 数据库文件不存在: {self.db_path}")
            sys.exit(1)
    
    def get_quick_stats(self) -> Dict:
        """获取快速统计信息"""
        stats = {
            'total_tasks': 0,
            'pending_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'running_tasks': 0,
            'total_projects': 0,
            'active_projects': 0,
            'db_size_mb': 0.0,
            'last_activity': None,
            'urgent_tasks': 0,
            'overdue_tasks': 0
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [table[0] for table in cursor.fetchall()]
            
            if 'publishing_tasks' in tables:
                # 任务统计
                cursor.execute("SELECT COUNT(*) FROM publishing_tasks")
                stats['total_tasks'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE status = 'pending'")
                stats['pending_tasks'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE status = 'completed'")
                stats['completed_tasks'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE status = 'failed'")
                stats['failed_tasks'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE status = 'running'")
                stats['running_tasks'] = cursor.fetchone()[0]
                
                # 紧急任务
                cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE priority = 'urgent' AND status = 'pending'")
                stats['urgent_tasks'] = cursor.fetchone()[0]
                
                # 过期任务
                cursor.execute("""
                    SELECT COUNT(*) FROM publishing_tasks 
                    WHERE status = 'pending' AND scheduled_at < datetime('now')
                """)
                stats['overdue_tasks'] = cursor.fetchone()[0]
                
                # 最后活动时间
                cursor.execute("SELECT MAX(updated_at) FROM publishing_tasks")
                last_activity = cursor.fetchone()[0]
                if last_activity:
                    stats['last_activity'] = last_activity
            
            if 'projects' in tables:
                cursor.execute("SELECT COUNT(*) FROM projects")
                stats['total_projects'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM projects WHERE status = 'active'")
                stats['active_projects'] = cursor.fetchone()[0]
            
            # 数据库文件大小
            stats['db_size_mb'] = os.path.getsize(self.db_path) / 1024 / 1024
            
            conn.close()
            
        except Exception as e:
            print(f"⚠️  获取统计信息失败: {e}")
        
        return stats
    
    def show_dashboard(self):
        """显示仪表板"""
        stats = self.get_quick_stats()
        
        print("\n" + "=" * 60)
        print("📊 Twitter 自动发布系统 - 快速监控仪表板")
        print("=" * 60)
        print(f"🕐 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💾 数据库大小: {stats['db_size_mb']:.2f} MB")
        
        # 任务状态概览
        print(f"\n📋 任务状态概览")
        print("-" * 30)
        total = stats['total_tasks']
        pending = stats['pending_tasks']
        completed = stats['completed_tasks']
        failed = stats['failed_tasks']
        running = stats['running_tasks']
        
        print(f"📝 总任务数: {total}")
        print(f"⏳ 待发布: {pending}")
        print(f"🔄 执行中: {running}")
        print(f"✅ 已完成: {completed}")
        print(f"❌ 失败: {failed}")
        
        # 计算百分比
        if total > 0:
            pending_pct = (pending / total) * 100
            completed_pct = (completed / total) * 100
            failed_pct = (failed / total) * 100
            
            print(f"\n📈 完成率: {completed_pct:.1f}%")
            print(f"📉 失败率: {failed_pct:.1f}%")
            print(f"⏸️  待处理率: {pending_pct:.1f}%")
        
        # 警告信息
        print(f"\n⚠️  警告信息")
        print("-" * 30)
        urgent = stats['urgent_tasks']
        overdue = stats['overdue_tasks']
        
        if urgent > 0:
            print(f"🚨 紧急任务: {urgent} 个")
        if overdue > 0:
            print(f"⏰ 过期任务: {overdue} 个")
        if urgent == 0 and overdue == 0:
            print("✅ 无紧急或过期任务")
        
        # 项目信息
        print(f"\n🏗️  项目信息")
        print("-" * 30)
        print(f"📁 总项目数: {stats['total_projects']}")
        print(f"🟢 活跃项目: {stats['active_projects']}")
        
        # 最后活动
        if stats['last_activity']:
            print(f"\n🕐 最后活动: {stats['last_activity']}")
        
        print("\n" + "=" * 60)
    
    def show_urgent_tasks(self, limit: int = 5):
        """显示紧急和过期任务"""
        print(f"\n🚨 紧急和过期任务 (最多显示 {limit} 个)")
        print("=" * 50)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 紧急任务
            cursor.execute("""
                SELECT id, project_id, priority, scheduled_at, content_data
                FROM publishing_tasks 
                WHERE status = 'pending' AND priority = 'urgent'
                ORDER BY scheduled_at ASC 
                LIMIT ?
            """, (limit,))
            
            urgent_tasks = cursor.fetchall()
            
            if urgent_tasks:
                print(f"\n🚨 紧急任务 ({len(urgent_tasks)} 个)")
                for i, task in enumerate(urgent_tasks, 1):
                    task_id, project_id, priority, scheduled_at, content_data = task
                    print(f"  {i}. 任务 {task_id} (项目 {project_id})")
                    print(f"     计划时间: {scheduled_at}")
                    
                    # 显示标题
                    if content_data:
                        try:
                            content = json.loads(content_data)
                            title = content.get('title', '')[:50]
                            if title:
                                print(f"     标题: {title}...")
                        except:
                            pass
            
            # 过期任务
            cursor.execute("""
                SELECT id, project_id, scheduled_at, content_data
                FROM publishing_tasks 
                WHERE status = 'pending' AND scheduled_at < datetime('now')
                ORDER BY scheduled_at ASC 
                LIMIT ?
            """, (limit,))
            
            overdue_tasks = cursor.fetchall()
            
            if overdue_tasks:
                print(f"\n⏰ 过期任务 ({len(overdue_tasks)} 个)")
                for i, task in enumerate(overdue_tasks, 1):
                    task_id, project_id, scheduled_at, content_data = task
                    print(f"  {i}. 任务 {task_id} (项目 {project_id})")
                    print(f"     计划时间: {scheduled_at}")
                    
                    # 计算过期时间
                    try:
                        scheduled = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                        overdue_time = datetime.now() - scheduled.replace(tzinfo=None)
                        print(f"     过期: {overdue_time}")
                    except:
                        pass
                    
                    # 显示标题
                    if content_data:
                        try:
                            content = json.loads(content_data)
                            title = content.get('title', '')[:50]
                            if title:
                                print(f"     标题: {title}...")
                        except:
                            pass
            
            if not urgent_tasks and not overdue_tasks:
                print("✅ 没有紧急或过期任务")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ 查询紧急任务失败: {e}")
    
    def show_recent_activity(self, hours: int = 24):
        """显示最近活动"""
        print(f"\n🕐 最近 {hours} 小时活动")
        print("=" * 40)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 最近完成的任务
            cursor.execute("""
                SELECT id, project_id, status, updated_at
                FROM publishing_tasks 
                WHERE updated_at > datetime('now', '-{} hours')
                AND status IN ('completed', 'failed')
                ORDER BY updated_at DESC 
                LIMIT 10
            """.format(hours))
            
            recent_tasks = cursor.fetchall()
            
            if recent_tasks:
                print(f"\n📋 最近完成/失败的任务 ({len(recent_tasks)} 个)")
                for task in recent_tasks:
                    task_id, project_id, status, updated_at = task
                    status_emoji = '✅' if status == 'completed' else '❌'
                    print(f"  {status_emoji} 任务 {task_id} (项目 {project_id}) - {updated_at}")
            else:
                print(f"📭 最近 {hours} 小时内没有完成的任务")
            
            # 统计最近活动
            cursor.execute("""
                SELECT status, COUNT(*) 
                FROM publishing_tasks 
                WHERE updated_at > datetime('now', '-{} hours')
                GROUP BY status
            """.format(hours))
            
            activity_stats = cursor.fetchall()
            
            if activity_stats:
                print(f"\n📊 最近 {hours} 小时统计")
                for status, count in activity_stats:
                    print(f"  {status}: {count} 个")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ 查询最近活动失败: {e}")
    
    def show_project_summary(self):
        """显示项目摘要"""
        print(f"\n🏗️  项目摘要")
        print("=" * 40)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
            if not cursor.fetchone():
                print("📭 项目表不存在")
                return
            
            cursor.execute("""
                SELECT p.id, p.name, p.status,
                       COUNT(t.id) as total_tasks,
                       SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END) as pending_tasks,
                       SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END) as completed_tasks
                FROM projects p
                LEFT JOIN publishing_tasks t ON p.id = t.project_id
                GROUP BY p.id, p.name, p.status
                ORDER BY total_tasks DESC
            """)
            
            projects = cursor.fetchall()
            
            if not projects:
                print("📭 没有找到项目")
                return
            
            for project in projects:
                project_id, name, status, total_tasks, pending_tasks, completed_tasks = project
                
                status_emoji = '🟢' if status == 'active' else '🔴'
                
                print(f"\n{status_emoji} {name} (ID: {project_id})")
                print(f"   状态: {status}")
                print(f"   总任务: {total_tasks or 0}")
                print(f"   待发布: {pending_tasks or 0}")
                print(f"   已完成: {completed_tasks or 0}")
                
                if total_tasks and total_tasks > 0:
                    completion_rate = ((completed_tasks or 0) / total_tasks) * 100
                    print(f"   完成率: {completion_rate:.1f}%")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ 查询项目摘要失败: {e}")
    
    def show_system_health(self):
        """显示系统健康状态"""
        print(f"\n🏥 系统健康检查")
        print("=" * 40)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查表结构
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [table[0] for table in cursor.fetchall()]
            
            expected_tables = ['users', 'projects', 'publishing_tasks', 'publishing_logs']
            
            print("📋 表结构检查")
            for table in expected_tables:
                if table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"  ✅ {table}: {count} 条记录")
                else:
                    print(f"  ❌ {table}: 表不存在")
            
            # 检查数据一致性
            print(f"\n🔍 数据一致性检查")
            
            # 检查孤立任务（没有对应项目的任务）
            if 'publishing_tasks' in tables and 'projects' in tables:
                cursor.execute("""
                    SELECT COUNT(*) FROM publishing_tasks t
                    LEFT JOIN projects p ON t.project_id = p.id
                    WHERE p.id IS NULL
                """)
                orphaned_tasks = cursor.fetchone()[0]
                
                if orphaned_tasks > 0:
                    print(f"  ⚠️  孤立任务: {orphaned_tasks} 个")
                else:
                    print(f"  ✅ 无孤立任务")
            
            # 检查空内容任务
            if 'publishing_tasks' in tables:
                cursor.execute("""
                    SELECT COUNT(*) FROM publishing_tasks 
                    WHERE content_data IS NULL OR content_data = ''
                """)
                empty_content_tasks = cursor.fetchone()[0]
                
                if empty_content_tasks > 0:
                    print(f"  ⚠️  空内容任务: {empty_content_tasks} 个")
                else:
                    print(f"  ✅ 所有任务都有内容")
            
            # 检查文件完整性
            print(f"\n📁 文件完整性检查")
            db_size = os.path.getsize(self.db_path)
            print(f"  💾 数据库大小: {db_size:,} 字节 ({db_size/1024/1024:.2f} MB)")
            
            if db_size < 1024:  # 小于1KB可能有问题
                print(f"  ⚠️  数据库文件过小，可能损坏")
            else:
                print(f"  ✅ 数据库文件大小正常")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ 系统健康检查失败: {e}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="快速数据库监控器 - 简化版数据库状态查看工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python quick_db_monitor.py                    # 显示仪表板
  python quick_db_monitor.py --urgent          # 显示紧急任务
  python quick_db_monitor.py --activity        # 显示最近活动
  python quick_db_monitor.py --projects        # 显示项目摘要
  python quick_db_monitor.py --health          # 系统健康检查
  python quick_db_monitor.py --all             # 显示所有信息
        """
    )
    
    parser.add_argument(
        '--urgent', '-u',
        action='store_true',
        help='显示紧急和过期任务'
    )
    
    parser.add_argument(
        '--activity', '-a',
        action='store_true',
        help='显示最近活动'
    )
    
    parser.add_argument(
        '--projects', '-p',
        action='store_true',
        help='显示项目摘要'
    )
    
    parser.add_argument(
        '--health',
        action='store_true',
        help='系统健康检查'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='显示所有信息'
    )
    
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='活动查看时间范围（小时，默认24）'
    )
    
    parser.add_argument(
        '--db-path',
        default='data/twitter_publisher.db',
        help='数据库文件路径'
    )
    
    args = parser.parse_args()
    
    try:
        monitor = QuickDBMonitor(args.db_path)
        
        if args.all:
            monitor.show_dashboard()
            monitor.show_urgent_tasks()
            monitor.show_recent_activity(args.hours)
            monitor.show_project_summary()
            monitor.show_system_health()
        elif args.urgent:
            monitor.show_urgent_tasks()
        elif args.activity:
            monitor.show_recent_activity(args.hours)
        elif args.projects:
            monitor.show_project_summary()
        elif args.health:
            monitor.show_system_health()
        else:
            # 默认显示仪表板
            monitor.show_dashboard()
    
    except KeyboardInterrupt:
        print("\n👋 操作已取消")
    except Exception as e:
        print(f"❌ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()