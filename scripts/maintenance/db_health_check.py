#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库健康检查工具
全面的数据库连接、性能和数据完整性检查工具
"""

import os
import sys
import time
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from sqlalchemy import create_engine, text, inspect
    from sqlalchemy.orm import sessionmaker
    from app.database.models import User, Project, ContentSource, PublishingTask, PublishingLog
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保已安装所需依赖: pip install sqlalchemy")
    sys.exit(1)


class DatabaseHealthChecker:
    """数据库健康检查器"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(project_root / "data" / "twitter_publisher.db")
        self.db_url = f"sqlite:///{self.db_path}"
        self.engine = None
        self.session = None
        self.results = {
            'connection': False,
            'tables': False,
            'data_integrity': False,
            'performance': False,
            'issues': [],
            'warnings': [],
            'stats': {}
        }
        
    def check_file_system(self) -> bool:
        """检查文件系统状态"""
        print("🔍 检查文件系统...")
        
        try:
            # 检查数据库文件是否存在
            if not os.path.exists(self.db_path):
                self.results['issues'].append(f"数据库文件不存在: {self.db_path}")
                return False
                
            # 检查文件权限
            if not os.access(self.db_path, os.R_OK):
                self.results['issues'].append(f"数据库文件不可读: {self.db_path}")
                return False
                
            if not os.access(self.db_path, os.W_OK):
                self.results['warnings'].append(f"数据库文件不可写: {self.db_path}")
                
            # 检查文件大小
            file_size = os.path.getsize(self.db_path)
            self.results['stats']['file_size_mb'] = round(file_size / 1024 / 1024, 2)
            
            # 检查文件修改时间
            mtime = os.path.getmtime(self.db_path)
            last_modified = datetime.fromtimestamp(mtime)
            self.results['stats']['last_modified'] = last_modified.isoformat()
            
            print(f"  ✅ 文件存在: {self.db_path}")
            print(f"  📊 文件大小: {self.results['stats']['file_size_mb']} MB")
            print(f"  🕒 最后修改: {last_modified}")
            
            return True
            
        except Exception as e:
            self.results['issues'].append(f"文件系统检查失败: {e}")
            return False
            
    def check_sqlite_connection(self) -> bool:
        """检查SQLite直接连接"""
        print("\n🔍 检查SQLite直接连接...")
        
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            cursor = conn.cursor()
            
            # 检查数据库完整性
            cursor.execute("PRAGMA integrity_check;")
            integrity_result = cursor.fetchone()[0]
            
            if integrity_result != "ok":
                self.results['issues'].append(f"数据库完整性检查失败: {integrity_result}")
                return False
                
            # 获取数据库信息
            cursor.execute("PRAGMA user_version;")
            user_version = cursor.fetchone()[0]
            self.results['stats']['user_version'] = user_version
            
            cursor.execute("PRAGMA page_size;")
            page_size = cursor.fetchone()[0]
            self.results['stats']['page_size'] = page_size
            
            cursor.execute("PRAGMA page_count;")
            page_count = cursor.fetchone()[0]
            self.results['stats']['page_count'] = page_count
            
            # 获取表列表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            self.results['stats']['tables'] = tables
            
            conn.close()
            
            print(f"  ✅ SQLite连接成功")
            print(f"  📊 用户版本: {user_version}")
            print(f"  📄 页面大小: {page_size} bytes")
            print(f"  📚 页面数量: {page_count}")
            print(f"  🗂️  表数量: {len(tables)}")
            
            return True
            
        except Exception as e:
            self.results['issues'].append(f"SQLite连接失败: {e}")
            return False
            
    def check_sqlalchemy_connection(self) -> bool:
        """检查SQLAlchemy连接"""
        print("\n🔍 检查SQLAlchemy连接...")
        
        try:
            self.engine = create_engine(self.db_url, echo=False)
            
            # 测试连接
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                test_value = result.scalar()
                
                if test_value != 1:
                    self.results['issues'].append("SQLAlchemy连接测试失败")
                    return False
                    
            # 创建会话
            Session = sessionmaker(bind=self.engine)
            self.session = Session()
            
            print(f"  ✅ SQLAlchemy连接成功")
            print(f"  🔗 数据库URL: {self.db_url}")
            
            return True
            
        except Exception as e:
            self.results['issues'].append(f"SQLAlchemy连接失败: {e}")
            return False
            
    def check_table_structure(self) -> bool:
        """检查表结构"""
        print("\n🔍 检查表结构...")
        
        if not self.engine:
            self.results['issues'].append("无法检查表结构：数据库连接未建立")
            return False
            
        try:
            inspector = inspect(self.engine)
            
            # 期望的表
            expected_tables = {
                'users', 'projects', 'content_sources', 
                'publishing_tasks', 'publishing_logs', 'analytics_hourly'
            }
            
            # 实际的表
            actual_tables = set(inspector.get_table_names())
            
            # 检查缺失的表
            missing_tables = expected_tables - actual_tables
            if missing_tables:
                self.results['issues'].append(f"缺失表: {', '.join(missing_tables)}")
                return False
                
            # 检查额外的表
            extra_tables = actual_tables - expected_tables
            if extra_tables:
                self.results['warnings'].append(f"额外的表: {', '.join(extra_tables)}")
                
            # 检查每个表的列
            table_info = {}
            for table_name in expected_tables:
                if table_name in actual_tables:
                    columns = inspector.get_columns(table_name)
                    table_info[table_name] = {
                        'column_count': len(columns),
                        'columns': [col['name'] for col in columns]
                    }
                    
            self.results['stats']['table_info'] = table_info
            
            print(f"  ✅ 表结构检查完成")
            print(f"  📊 期望表数: {len(expected_tables)}")
            print(f"  📊 实际表数: {len(actual_tables)}")
            
            for table_name, info in table_info.items():
                print(f"  📋 {table_name}: {info['column_count']} 列")
                
            return True
            
        except Exception as e:
            self.results['issues'].append(f"表结构检查失败: {e}")
            return False
            
    def check_data_integrity(self) -> bool:
        """检查数据完整性"""
        print("\n🔍 检查数据完整性...")
        
        if not self.session:
            self.results['issues'].append("无法检查数据完整性：数据库会话未建立")
            return False
            
        try:
            # 统计各表的记录数
            stats = {}
            
            # 用户表
            user_count = self.session.query(User).count()
            stats['users'] = user_count
            
            # 项目表
            project_count = self.session.query(Project).count()
            stats['projects'] = project_count
            
            # 内容源表
            source_count = self.session.query(ContentSource).count()
            stats['content_sources'] = source_count
            
            # 任务表
            task_count = self.session.query(PublishingTask).count()
            stats['publishing_tasks'] = task_count
            
            # 日志表
            log_count = self.session.query(PublishingLog).count()
            stats['publishing_logs'] = log_count
            
            self.results['stats']['record_counts'] = stats
            
            # 检查数据一致性
            issues_found = False
            
            # 检查孤立的任务（没有对应项目的任务）
            orphaned_tasks = self.session.query(PublishingTask).filter(
                ~PublishingTask.project_id.in_(
                    self.session.query(Project.id)
                )
            ).count()
            
            if orphaned_tasks > 0:
                self.results['issues'].append(f"发现 {orphaned_tasks} 个孤立任务")
                issues_found = True
                
            # 检查孤立的日志（没有对应任务的日志）
            orphaned_logs = self.session.query(PublishingLog).filter(
                ~PublishingLog.task_id.in_(
                    self.session.query(PublishingTask.id)
                )
            ).count()
            
            if orphaned_logs > 0:
                self.results['issues'].append(f"发现 {orphaned_logs} 个孤立日志")
                issues_found = True
                
            # 检查任务状态分布
            task_status_stats = {}
            if task_count > 0:
                from sqlalchemy import func
                status_results = self.session.query(
                    PublishingTask.status,
                    func.count(PublishingTask.id)
                ).group_by(PublishingTask.status).all()
                
                for status, count in status_results:
                    task_status_stats[status] = count
                    
            self.results['stats']['task_status'] = task_status_stats
            
            print(f"  ✅ 数据完整性检查完成")
            print(f"  👥 用户数: {user_count}")
            print(f"  📁 项目数: {project_count}")
            print(f"  📄 内容源数: {source_count}")
            print(f"  📋 任务数: {task_count}")
            print(f"  📊 日志数: {log_count}")
            
            if task_status_stats:
                print(f"  📈 任务状态分布:")
                for status, count in task_status_stats.items():
                    print(f"    - {status}: {count}")
                    
            return not issues_found
            
        except Exception as e:
            self.results['issues'].append(f"数据完整性检查失败: {e}")
            return False
            
    def check_performance(self) -> bool:
        """检查数据库性能"""
        print("\n🔍 检查数据库性能...")
        
        if not self.session:
            self.results['issues'].append("无法检查性能：数据库会话未建立")
            return False
            
        try:
            performance_stats = {}
            
            # 测试简单查询性能
            start_time = time.time()
            user_count = self.session.query(User).count()
            query_time = time.time() - start_time
            performance_stats['simple_query_ms'] = round(query_time * 1000, 2)
            
            # 测试复杂查询性能
            start_time = time.time()
            complex_result = self.session.query(PublishingTask).join(Project).limit(100).all()
            complex_query_time = time.time() - start_time
            performance_stats['complex_query_ms'] = round(complex_query_time * 1000, 2)
            
            # 检查性能阈值
            if performance_stats['simple_query_ms'] > 1000:  # 1秒
                self.results['warnings'].append(f"简单查询较慢: {performance_stats['simple_query_ms']}ms")
                
            if performance_stats['complex_query_ms'] > 5000:  # 5秒
                self.results['warnings'].append(f"复杂查询较慢: {performance_stats['complex_query_ms']}ms")
                
            self.results['stats']['performance'] = performance_stats
            
            print(f"  ✅ 性能检查完成")
            print(f"  ⚡ 简单查询: {performance_stats['simple_query_ms']}ms")
            print(f"  ⚡ 复杂查询: {performance_stats['complex_query_ms']}ms")
            
            return True
            
        except Exception as e:
            self.results['issues'].append(f"性能检查失败: {e}")
            return False
            
    def run_full_check(self) -> Dict[str, Any]:
        """运行完整的健康检查"""
        print("🏥 开始数据库健康检查...")
        print("=" * 60)
        
        # 文件系统检查
        self.results['connection'] = self.check_file_system()
        
        if self.results['connection']:
            # SQLite连接检查
            self.results['connection'] = self.check_sqlite_connection()
            
        if self.results['connection']:
            # SQLAlchemy连接检查
            self.results['connection'] = self.check_sqlalchemy_connection()
            
        if self.results['connection']:
            # 表结构检查
            self.results['tables'] = self.check_table_structure()
            
        if self.results['connection'] and self.results['tables']:
            # 数据完整性检查
            self.results['data_integrity'] = self.check_data_integrity()
            
            # 性能检查
            self.results['performance'] = self.check_performance()
            
        return self.results
        
    def print_summary(self):
        """打印检查结果摘要"""
        print("\n" + "=" * 60)
        print("🏥 数据库健康检查报告")
        print("=" * 60)
        
        # 总体状态
        overall_health = (
            self.results['connection'] and 
            self.results['tables'] and 
            self.results['data_integrity'] and 
            self.results['performance']
        )
        
        status_icon = "✅" if overall_health else "❌"
        status_text = "健康" if overall_health else "有问题"
        print(f"\n{status_icon} 总体状态: {status_text}")
        
        # 各项检查结果
        checks = [
            ('连接检查', self.results['connection']),
            ('表结构检查', self.results['tables']),
            ('数据完整性检查', self.results['data_integrity']),
            ('性能检查', self.results['performance'])
        ]
        
        print("\n📋 检查项目:")
        for check_name, result in checks:
            icon = "✅" if result else "❌"
            print(f"  {icon} {check_name}")
            
        # 问题列表
        if self.results['issues']:
            print("\n❌ 发现的问题:")
            for issue in self.results['issues']:
                print(f"  • {issue}")
                
        # 警告列表
        if self.results['warnings']:
            print("\n⚠️  警告:")
            for warning in self.results['warnings']:
                print(f"  • {warning}")
                
        # 统计信息
        if self.results['stats']:
            print("\n📊 统计信息:")
            stats = self.results['stats']
            
            if 'file_size_mb' in stats:
                print(f"  📁 文件大小: {stats['file_size_mb']} MB")
                
            if 'record_counts' in stats:
                print(f"  📋 记录统计:")
                for table, count in stats['record_counts'].items():
                    print(f"    - {table}: {count}")
                    
            if 'performance' in stats:
                perf = stats['performance']
                print(f"  ⚡ 性能指标:")
                print(f"    - 简单查询: {perf['simple_query_ms']}ms")
                print(f"    - 复杂查询: {perf['complex_query_ms']}ms")
                
        print("\n" + "=" * 60)
        
    def cleanup(self):
        """清理资源"""
        if self.session:
            self.session.close()
            

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='数据库健康检查工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 基本健康检查
    python db_health_check.py
    
    # 指定数据库文件
    python db_health_check.py --db-path /path/to/database.db
    
    # 只检查连接
    python db_health_check.py --quick
        """
    )
    
    parser.add_argument(
        '--db-path',
        help='数据库文件路径'
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='快速检查（仅检查连接）'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='以JSON格式输出结果'
    )
    
    args = parser.parse_args()
    
    # 创建健康检查器
    checker = DatabaseHealthChecker(args.db_path)
    
    try:
        if args.quick:
            # 快速检查
            checker.check_file_system()
            checker.check_sqlite_connection()
            checker.check_sqlalchemy_connection()
        else:
            # 完整检查
            checker.run_full_check()
            
        if args.json:
            import json
            print(json.dumps(checker.results, indent=2, ensure_ascii=False))
        else:
            checker.print_summary()
            
        # 根据结果设置退出码
        if checker.results['issues']:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n⚠️  检查被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        sys.exit(1)
    finally:
        checker.cleanup()


if __name__ == "__main__":
    main()