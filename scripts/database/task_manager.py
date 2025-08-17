#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务管理器 - 专业的发布任务查看和管理工具
提供高级的任务筛选、排序和管理功能
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class SortBy(Enum):
    """排序方式枚举"""
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    SCHEDULED_AT = "scheduled_at"
    PRIORITY = "priority"
    STATUS = "status"
    PROJECT_ID = "project_id"

@dataclass
class TaskFilter:
    """任务筛选条件"""
    status: Optional[List[str]] = None
    priority: Optional[List[str]] = None
    project_id: Optional[List[int]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    overdue_only: bool = False
    has_media: Optional[bool] = None
    keyword: Optional[str] = None

@dataclass
class TaskInfo:
    """任务信息"""
    id: int
    project_id: int
    source_id: Optional[int]
    status: str
    priority: str
    media_path: Optional[str]
    content_data: Optional[str]
    scheduled_at: Optional[str]
    created_at: str
    updated_at: str
    retry_count: int = 0
    version: int = 1
    
    @property
    def is_overdue(self) -> bool:
        """检查任务是否过期"""
        if not self.scheduled_at or self.status != 'pending':
            return False
        try:
            scheduled = datetime.fromisoformat(self.scheduled_at.replace('Z', '+00:00'))
            return datetime.now() > scheduled.replace(tzinfo=None)
        except:
            return False
    
    @property
    def content_title(self) -> str:
        """获取内容标题"""
        if not self.content_data:
            return "无标题"
        try:
            content = json.loads(self.content_data)
            return content.get('title', '无标题')[:50]
        except:
            return "解析失败"
    
    @property
    def media_filename(self) -> str:
        """获取媒体文件名"""
        if not self.media_path:
            return "无媒体"
        return Path(self.media_path).name
    
    @property
    def time_until_scheduled(self) -> Optional[timedelta]:
        """计算距离计划时间的时间差"""
        if not self.scheduled_at:
            return None
        try:
            scheduled = datetime.fromisoformat(self.scheduled_at.replace('Z', '+00:00'))
            return scheduled.replace(tzinfo=None) - datetime.now()
        except:
            return None

class TaskManager:
    """任务管理器"""
    
    def __init__(self, db_path: str = 'data/twitter_publisher.db'):
        self.db_path = db_path
        self.check_database()
    
    def check_database(self):
        """检查数据库是否存在"""
        if not os.path.exists(self.db_path):
            print(f"❌ 数据库文件不存在: {self.db_path}")
            sys.exit(1)
    
    def get_tasks(self, 
                  filter_obj: Optional[TaskFilter] = None,
                  sort_by: SortBy = SortBy.CREATED_AT,
                  ascending: bool = False,
                  limit: Optional[int] = None,
                  offset: int = 0) -> List[TaskInfo]:
        """获取任务列表"""
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 构建查询
            query = "SELECT * FROM publishing_tasks"
            conditions = []
            params = []
            
            if filter_obj:
                # 状态筛选
                if filter_obj.status:
                    placeholders = ','.join(['?' for _ in filter_obj.status])
                    conditions.append(f"status IN ({placeholders})")
                    params.extend(filter_obj.status)
                
                # 优先级筛选
                if filter_obj.priority:
                    placeholders = ','.join(['?' for _ in filter_obj.priority])
                    conditions.append(f"priority IN ({placeholders})")
                    params.extend(filter_obj.priority)
                
                # 项目筛选
                if filter_obj.project_id:
                    placeholders = ','.join(['?' for _ in filter_obj.project_id])
                    conditions.append(f"project_id IN ({placeholders})")
                    params.extend(filter_obj.project_id)
                
                # 日期范围筛选
                if filter_obj.date_from:
                    conditions.append("created_at >= ?")
                    params.append(filter_obj.date_from.isoformat())
                
                if filter_obj.date_to:
                    conditions.append("created_at <= ?")
                    params.append(filter_obj.date_to.isoformat())
                
                # 过期任务筛选
                if filter_obj.overdue_only:
                    conditions.append("status = 'pending' AND scheduled_at < datetime('now')")
                
                # 媒体文件筛选
                if filter_obj.has_media is not None:
                    if filter_obj.has_media:
                        conditions.append("media_path IS NOT NULL AND media_path != ''")
                    else:
                        conditions.append("(media_path IS NULL OR media_path = '')")
                
                # 关键词搜索
                if filter_obj.keyword:
                    conditions.append("(content_data LIKE ? OR media_path LIKE ?)")
                    keyword_pattern = f"%{filter_obj.keyword}%"
                    params.extend([keyword_pattern, keyword_pattern])
            
            # 添加条件
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            # 排序
            order_direction = "ASC" if ascending else "DESC"
            query += f" ORDER BY {sort_by.value} {order_direction}"
            
            # 分页
            if limit:
                query += f" LIMIT {limit}"
            if offset > 0:
                query += f" OFFSET {offset}"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 获取列名
            cursor.execute("PRAGMA table_info(publishing_tasks)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # 转换为TaskInfo对象
            tasks = []
            for row in rows:
                task_dict = dict(zip(columns, row))
                task = TaskInfo(
                    id=task_dict.get('id'),
                    project_id=task_dict.get('project_id'),
                    source_id=task_dict.get('source_id'),
                    status=task_dict.get('status'),
                    priority=task_dict.get('priority'),
                    media_path=task_dict.get('media_path'),
                    content_data=task_dict.get('content_data'),
                    scheduled_at=task_dict.get('scheduled_at'),
                    created_at=task_dict.get('created_at'),
                    updated_at=task_dict.get('updated_at'),
                    retry_count=task_dict.get('retry_count', 0),
                    version=task_dict.get('version', 1)
                )
                tasks.append(task)
            
            conn.close()
            return tasks
            
        except Exception as e:
            print(f"❌ 查询任务失败: {e}")
            return []
    
    def get_task_by_id(self, task_id: int) -> Optional[TaskInfo]:
        """根据ID获取任务"""
        tasks = self.get_tasks(limit=1)
        for task in tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_task_statistics(self, filter_obj: Optional[TaskFilter] = None) -> Dict[str, Any]:
        """获取任务统计信息"""
        tasks = self.get_tasks(filter_obj)
        
        stats = {
            'total': len(tasks),
            'by_status': {},
            'by_priority': {},
            'by_project': {},
            'overdue_count': 0,
            'with_media_count': 0,
            'retry_count': 0,
            'avg_retry_count': 0.0
        }
        
        if not tasks:
            return stats
        
        # 按状态统计
        for task in tasks:
            stats['by_status'][task.status] = stats['by_status'].get(task.status, 0) + 1
            stats['by_priority'][task.priority] = stats['by_priority'].get(task.priority, 0) + 1
            stats['by_project'][task.project_id] = stats['by_project'].get(task.project_id, 0) + 1
            
            if task.is_overdue:
                stats['overdue_count'] += 1
            
            if task.media_path:
                stats['with_media_count'] += 1
            
            stats['retry_count'] += task.retry_count
        
        stats['avg_retry_count'] = stats['retry_count'] / len(tasks) if tasks else 0
        
        return stats
    
    def show_task_list(self, 
                       filter_obj: Optional[TaskFilter] = None,
                       sort_by: SortBy = SortBy.CREATED_AT,
                       ascending: bool = False,
                       limit: int = 20,
                       show_details: bool = False):
        """显示任务列表"""
        
        tasks = self.get_tasks(filter_obj, sort_by, ascending, limit)
        
        if not tasks:
            print("📭 没有找到符合条件的任务")
            return
        
        print(f"\n📋 任务列表 (共 {len(tasks)} 个)")
        print("=" * 80)
        
        for i, task in enumerate(tasks, 1):
            # 状态图标
            status_icons = {
                'pending': '⏳',
                'running': '🔄',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '🚫',
                'retrying': '🔁'
            }
            
            # 优先级图标
            priority_icons = {
                'low': '🔵',
                'normal': '🟡',
                'high': '🟠',
                'urgent': '🔴'
            }
            
            status_icon = status_icons.get(task.status, '❓')
            priority_icon = priority_icons.get(task.priority, '⚪')
            
            # 过期标记
            overdue_mark = '⏰' if task.is_overdue else ''
            
            print(f"\n{i:2d}. {status_icon} {priority_icon} 任务 {task.id} {overdue_mark}")
            print(f"    项目: {task.project_id} | 状态: {task.status} | 优先级: {task.priority}")
            print(f"    标题: {task.content_title}")
            print(f"    媒体: {task.media_filename}")
            
            if task.scheduled_at:
                print(f"    计划: {task.scheduled_at}")
                time_diff = task.time_until_scheduled
                if time_diff:
                    if time_diff.total_seconds() > 0:
                        print(f"    剩余: {time_diff}")
                    else:
                        print(f"    过期: {abs(time_diff)}")
            
            if task.retry_count > 0:
                print(f"    重试: {task.retry_count} 次")
            
            if show_details:
                print(f"    创建: {task.created_at}")
                print(f"    更新: {task.updated_at}")
                if task.content_data:
                    try:
                        content = json.loads(task.content_data)
                        if content.get('description'):
                            desc = content.get('description', '')[:100]
                            print(f"    描述: {desc}...")
                    except:
                        pass
            
            print("-" * 60)
    
    def show_task_statistics_report(self, filter_obj: Optional[TaskFilter] = None):
        """显示任务统计报告"""
        stats = self.get_task_statistics(filter_obj)
        
        print(f"\n📊 任务统计报告")
        print("=" * 50)
        print(f"📝 总任务数: {stats['total']}")
        
        if stats['total'] == 0:
            print("📭 没有任务数据")
            return
        
        # 状态分布
        print(f"\n📈 状态分布")
        print("-" * 30)
        for status, count in stats['by_status'].items():
            percentage = (count / stats['total']) * 100
            print(f"  {status}: {count} ({percentage:.1f}%)")
        
        # 优先级分布
        print(f"\n🎯 优先级分布")
        print("-" * 30)
        for priority, count in stats['by_priority'].items():
            percentage = (count / stats['total']) * 100
            print(f"  {priority}: {count} ({percentage:.1f}%)")
        
        # 项目分布
        print(f"\n🏗️  项目分布 (前10个)")
        print("-" * 30)
        sorted_projects = sorted(stats['by_project'].items(), key=lambda x: x[1], reverse=True)[:10]
        for project_id, count in sorted_projects:
            percentage = (count / stats['total']) * 100
            print(f"  项目 {project_id}: {count} ({percentage:.1f}%)")
        
        # 其他统计
        print(f"\n📋 其他统计")
        print("-" * 30)
        print(f"⏰ 过期任务: {stats['overdue_count']}")
        print(f"📁 有媒体文件: {stats['with_media_count']}")
        print(f"🔁 总重试次数: {stats['retry_count']}")
        print(f"📊 平均重试次数: {stats['avg_retry_count']:.2f}")
    
    def show_task_details(self, task_id: int):
        """显示任务详细信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取任务信息
            cursor.execute("SELECT * FROM publishing_tasks WHERE id = ?", (task_id,))
            task_row = cursor.fetchone()
            
            if not task_row:
                print(f"❌ 未找到ID为 {task_id} 的任务")
                return
            
            # 获取列名
            cursor.execute("PRAGMA table_info(publishing_tasks)")
            columns = [col[1] for col in cursor.fetchall()]
            task_dict = dict(zip(columns, task_row))
            
            task = TaskInfo(**{k: v for k, v in task_dict.items() if k in TaskInfo.__annotations__})
            
            print(f"\n🔍 任务详细信息 (ID: {task_id})")
            print("=" * 60)
            
            # 基本信息
            print(f"📋 基本信息")
            print(f"  ID: {task.id}")
            print(f"  项目ID: {task.project_id}")
            print(f"  内容源ID: {task.source_id}")
            print(f"  状态: {task.status}")
            print(f"  优先级: {task.priority}")
            print(f"  重试次数: {task.retry_count}")
            print(f"  版本: {task.version}")
            
            # 时间信息
            print(f"\n📅 时间信息")
            print(f"  计划时间: {task.scheduled_at}")
            print(f"  创建时间: {task.created_at}")
            print(f"  更新时间: {task.updated_at}")
            
            if task.scheduled_at:
                time_diff = task.time_until_scheduled
                if time_diff:
                    if time_diff.total_seconds() > 0:
                        print(f"  距离执行: {time_diff}")
                    else:
                        print(f"  已过期: {abs(time_diff)}")
            
            # 文件信息
            print(f"\n📁 文件信息")
            print(f"  媒体路径: {task.media_path or '无'}")
            if task.media_path and Path(task.media_path).exists():
                file_size = Path(task.media_path).stat().st_size
                print(f"  文件大小: {file_size:,} 字节 ({file_size/1024/1024:.2f} MB)")
                print(f"  文件类型: {Path(task.media_path).suffix}")
            elif task.media_path:
                print(f"  ⚠️  文件不存在")
            
            # 内容信息
            print(f"\n📝 内容信息")
            if task.content_data:
                try:
                    content = json.loads(task.content_data)
                    for key, value in content.items():
                        if isinstance(value, str):
                            if len(value) > 200:
                                print(f"  {key}: {value[:200]}...")
                            else:
                                print(f"  {key}: {value}")
                        else:
                            print(f"  {key}: {value}")
                except Exception as e:
                    print(f"  解析失败: {e}")
                    print(f"  原始数据: {task.content_data[:300]}...")
            else:
                print(f"  无内容数据")
            
            # 获取项目信息
            cursor.execute("SELECT name, description, status FROM projects WHERE id = ?", (task.project_id,))
            project_row = cursor.fetchone()
            if project_row:
                print(f"\n🏗️  关联项目")
                print(f"  名称: {project_row[0]}")
                print(f"  描述: {project_row[1]}")
                print(f"  状态: {project_row[2]}")
            
            # 获取发布日志
            cursor.execute("""
                SELECT published_at, status, tweet_id, error_message 
                FROM publishing_logs 
                WHERE task_id = ? 
                ORDER BY published_at DESC 
                LIMIT 5
            """, (task_id,))
            logs = cursor.fetchall()
            
            if logs:
                print(f"\n📋 发布日志 (最近5条)")
                for log in logs:
                    published_at, status, tweet_id, error_message = log
                    print(f"  - {published_at}: {status}")
                    if tweet_id:
                        print(f"    推文ID: {tweet_id}")
                    if error_message:
                        print(f"    错误: {error_message}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ 查询任务详情失败: {e}")
    
    def search_tasks(self, keyword: str, limit: int = 20):
        """搜索任务"""
        filter_obj = TaskFilter(keyword=keyword)
        print(f"\n🔍 搜索结果: '{keyword}'")
        self.show_task_list(filter_obj, limit=limit)
    
    def show_overdue_tasks(self, limit: int = 20):
        """显示过期任务"""
        filter_obj = TaskFilter(overdue_only=True)
        print(f"\n⏰ 过期任务")
        self.show_task_list(filter_obj, limit=limit, show_details=True)
    
    def show_urgent_tasks(self, limit: int = 20):
        """显示紧急任务"""
        filter_obj = TaskFilter(priority=['urgent'])
        print(f"\n🚨 紧急任务")
        self.show_task_list(filter_obj, limit=limit, show_details=True)
    
    def show_failed_tasks(self, limit: int = 20):
        """显示失败任务"""
        filter_obj = TaskFilter(status=['failed'])
        print(f"\n❌ 失败任务")
        self.show_task_list(filter_obj, limit=limit, show_details=True)

def main():
    """主函数"""
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser(
        description="任务管理器 - 专业的发布任务查看和管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python task_manager.py                           # 显示所有任务
  python task_manager.py --status pending         # 显示待发布任务
  python task_manager.py --priority urgent        # 显示紧急任务
  python task_manager.py --overdue                # 显示过期任务
  python task_manager.py --failed                 # 显示失败任务
  python task_manager.py --project 1,2,3          # 显示指定项目任务
  python task_manager.py --search "关键词"         # 搜索任务
  python task_manager.py --task-id 123            # 显示任务详情
  python task_manager.py --stats                  # 显示统计报告
  python task_manager.py --sort scheduled_at      # 按计划时间排序
        """
    )
    
    parser.add_argument(
        '--status', '-s',
        help='按状态筛选 (pending,running,completed,failed,cancelled)'
    )
    
    parser.add_argument(
        '--priority', '-p',
        help='按优先级筛选 (low,normal,high,urgent)'
    )
    
    parser.add_argument(
        '--project',
        help='按项目ID筛选 (用逗号分隔多个ID)'
    )
    
    parser.add_argument(
        '--overdue',
        action='store_true',
        help='只显示过期任务'
    )
    
    parser.add_argument(
        '--failed',
        action='store_true',
        help='只显示失败任务'
    )
    
    parser.add_argument(
        '--urgent',
        action='store_true',
        help='只显示紧急任务'
    )
    
    parser.add_argument(
        '--search',
        help='搜索关键词'
    )
    
    parser.add_argument(
        '--task-id', '-t',
        type=int,
        help='显示指定任务详情'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='显示统计报告'
    )
    
    parser.add_argument(
        '--sort',
        choices=[sort.value for sort in SortBy],
        default=SortBy.CREATED_AT.value,
        help='排序方式'
    )
    
    parser.add_argument(
        '--asc',
        action='store_true',
        help='升序排列'
    )
    
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=20,
        help='显示记录数量限制'
    )
    
    parser.add_argument(
        '--details',
        action='store_true',
        help='显示详细信息'
    )
    
    parser.add_argument(
        '--db-path',
        default='data/twitter_publisher.db',
        help='数据库文件路径'
    )
    
    args = parser.parse_args()
    
    try:
        manager = TaskManager(args.db_path)
        
        # 构建筛选条件
        filter_obj = TaskFilter()
        
        if args.status:
            filter_obj.status = args.status.split(',')
        
        if args.priority:
            filter_obj.priority = args.priority.split(',')
        
        if args.project:
            filter_obj.project_id = [int(pid) for pid in args.project.split(',')]
        
        if args.overdue:
            filter_obj.overdue_only = True
        
        if args.search:
            filter_obj.keyword = args.search
        
        # 快捷筛选
        if args.failed:
            filter_obj.status = ['failed']
        
        if args.urgent:
            filter_obj.priority = ['urgent']
        
        # 排序方式
        sort_by = SortBy(args.sort)
        
        # 执行操作
        if args.task_id:
            manager.show_task_details(args.task_id)
        elif args.stats:
            manager.show_task_statistics_report(filter_obj)
        else:
            manager.show_task_list(
                filter_obj=filter_obj,
                sort_by=sort_by,
                ascending=args.asc,
                limit=args.limit,
                show_details=args.details
            )
    
    except KeyboardInterrupt:
        print("\n👋 操作已取消")
    except Exception as e:
        print(f"❌ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()