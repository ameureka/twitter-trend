#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移工具
提供数据库架构迁移、数据备份和恢复功能
"""

import sys
import os
import json
import shutil
import sqlite3
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from app.database.models import Base, User, Project, ContentSource, PublishingTask, PublishingLog
    from app.database.database import DatabaseManager
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import sessionmaker
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保项目依赖已正确安装")
    sys.exit(1)


class DatabaseMigrator:
    """数据库迁移器"""
    
    def __init__(self, db_path: str, backup_dir: Optional[str] = None):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir) if backup_dir else self.db_path.parent / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # 数据库连接
        self.db_url = f"sqlite:///{self.db_path}"
        self.engine = None
        self.session = None
        
        # 迁移历史
        self.migration_log = []
        
    def initialize_connection(self):
        """初始化数据库连接"""
        try:
            self.engine = create_engine(self.db_url, echo=False)
            Session = sessionmaker(bind=self.engine)
            self.session = Session()
            print(f"✅ 数据库连接成功: {self.db_path}")
        except Exception as e:
            raise Exception(f"数据库连接失败: {e}")
            
    def cleanup_connection(self):
        """清理数据库连接"""
        if self.session:
            self.session.close()
        if self.engine:
            self.engine.dispose()
            
    def create_backup(self, backup_name: Optional[str] = None) -> str:
        """创建数据库备份"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")
            
        # 生成备份文件名
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}.db"
            
        backup_path = self.backup_dir / backup_name
        
        print(f"📦 创建数据库备份...")
        print(f"   源文件: {self.db_path}")
        print(f"   备份文件: {backup_path}")
        
        try:
            # 使用SQLite的备份API进行在线备份
            source_conn = sqlite3.connect(str(self.db_path))
            backup_conn = sqlite3.connect(str(backup_path))
            
            source_conn.backup(backup_conn)
            
            source_conn.close()
            backup_conn.close()
            
            # 验证备份文件
            backup_size = backup_path.stat().st_size
            original_size = self.db_path.stat().st_size
            
            print(f"   ✅ 备份完成")
            print(f"   原始大小: {original_size:,} bytes")
            print(f"   备份大小: {backup_size:,} bytes")
            
            # 记录备份信息
            backup_info = {
                "timestamp": datetime.now().isoformat(),
                "backup_path": str(backup_path),
                "original_path": str(self.db_path),
                "original_size": original_size,
                "backup_size": backup_size,
                "status": "success"
            }
            
            self.migration_log.append({
                "action": "backup",
                "details": backup_info
            })
            
            return str(backup_path)
            
        except Exception as e:
            if backup_path.exists():
                backup_path.unlink()  # 删除失败的备份文件
            raise Exception(f"备份创建失败: {e}")
            
    def restore_backup(self, backup_path: str, confirm: bool = False) -> bool:
        """从备份恢复数据库"""
        backup_file = Path(backup_path)
        
        if not backup_file.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")
            
        if not confirm:
            print("⚠️  警告: 此操作将覆盖当前数据库！")
            print(f"   当前数据库: {self.db_path}")
            print(f"   备份文件: {backup_file}")
            response = input("确认恢复？(yes/no): ")
            if response.lower() != 'yes':
                print("❌ 恢复操作已取消")
                return False
                
        print(f"🔄 从备份恢复数据库...")
        
        try:
            # 关闭现有连接
            self.cleanup_connection()
            
            # 创建当前数据库的临时备份
            if self.db_path.exists():
                temp_backup = self.db_path.with_suffix('.temp_backup')
                shutil.copy2(self.db_path, temp_backup)
                print(f"   📦 创建临时备份: {temp_backup}")
            else:
                temp_backup = None
                
            # 恢复备份
            shutil.copy2(backup_file, self.db_path)
            print(f"   ✅ 数据库恢复完成")
            
            # 验证恢复的数据库
            self.initialize_connection()
            tables = self.get_table_info()
            print(f"   📊 恢复后表数量: {len(tables)}")
            
            # 删除临时备份
            if temp_backup and temp_backup.exists():
                temp_backup.unlink()
                print(f"   🗑️  删除临时备份")
                
            # 记录恢复信息
            self.migration_log.append({
                "action": "restore",
                "details": {
                    "timestamp": datetime.now().isoformat(),
                    "backup_source": str(backup_file),
                    "target_path": str(self.db_path),
                    "tables_count": len(tables),
                    "status": "success"
                }
            })
            
            return True
            
        except Exception as e:
            # 尝试恢复临时备份
            if temp_backup and temp_backup.exists():
                try:
                    shutil.copy2(temp_backup, self.db_path)
                    temp_backup.unlink()
                    print(f"   🔄 已恢复到原始状态")
                except:
                    pass
                    
            raise Exception(f"数据库恢复失败: {e}")
            
    def get_table_info(self) -> Dict[str, Any]:
        """获取数据库表信息"""
        if not self.engine:
            self.initialize_connection()
            
        inspector = inspect(self.engine)
        tables = {}
        
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            indexes = inspector.get_indexes(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            # 获取行数
            try:
                result = self.session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                row_count = result.scalar()
            except:
                row_count = 0
                
            tables[table_name] = {
                "columns": len(columns),
                "indexes": len(indexes),
                "foreign_keys": len(foreign_keys),
                "row_count": row_count,
                "column_details": [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col["nullable"],
                        "primary_key": col.get("primary_key", False)
                    }
                    for col in columns
                ]
            }
            
        return tables
        
    def check_schema_compatibility(self) -> Dict[str, Any]:
        """检查架构兼容性"""
        print("🔍 检查数据库架构兼容性...")
        
        try:
            # 获取当前数据库架构
            current_tables = self.get_table_info()
            
            # 获取模型定义的架构
            expected_tables = {
                "users": ["id", "username", "email", "role", "created_at", "updated_at"],
                "projects": ["id", "user_id", "name", "description", "folder_path", "is_active", "created_at", "updated_at"],
                "content_sources": ["id", "project_id", "source_type", "path_or_identifier", "total_items", "used_items", "last_scanned", "created_at", "updated_at"],
                "publishing_tasks": ["id", "project_id", "source_id", "media_path", "content_data", "scheduled_at", "status", "priority", "retry_count", "created_at", "updated_at"],
                "publishing_logs": ["id", "task_id", "status", "tweet_id", "tweet_content", "published_at", "error_message", "duration_seconds", "created_at"]
            }
            
            compatibility_report = {
                "compatible": True,
                "missing_tables": [],
                "extra_tables": [],
                "column_issues": {},
                "summary": {}
            }
            
            # 检查缺失的表
            for expected_table in expected_tables:
                if expected_table not in current_tables:
                    compatibility_report["missing_tables"].append(expected_table)
                    compatibility_report["compatible"] = False
                    
            # 检查多余的表
            for current_table in current_tables:
                if current_table not in expected_tables and not current_table.startswith("sqlite_"):
                    compatibility_report["extra_tables"].append(current_table)
                    
            # 检查列
            for table_name, expected_columns in expected_tables.items():
                if table_name in current_tables:
                    current_columns = [col["name"] for col in current_tables[table_name]["column_details"]]
                    missing_columns = [col for col in expected_columns if col not in current_columns]
                    extra_columns = [col for col in current_columns if col not in expected_columns]
                    
                    if missing_columns or extra_columns:
                        compatibility_report["column_issues"][table_name] = {
                            "missing": missing_columns,
                            "extra": extra_columns
                        }
                        if missing_columns:
                            compatibility_report["compatible"] = False
                            
            # 生成摘要
            compatibility_report["summary"] = {
                "total_tables": len(current_tables),
                "expected_tables": len(expected_tables),
                "missing_tables_count": len(compatibility_report["missing_tables"]),
                "extra_tables_count": len(compatibility_report["extra_tables"]),
                "tables_with_column_issues": len(compatibility_report["column_issues"])
            }
            
            # 打印报告
            if compatibility_report["compatible"]:
                print("   ✅ 数据库架构兼容")
            else:
                print("   ⚠️  发现架构兼容性问题")
                
            if compatibility_report["missing_tables"]:
                print(f"   ❌ 缺失表: {', '.join(compatibility_report['missing_tables'])}")
                
            if compatibility_report["extra_tables"]:
                print(f"   ℹ️  额外表: {', '.join(compatibility_report['extra_tables'])}")
                
            for table, issues in compatibility_report["column_issues"].items():
                if issues["missing"]:
                    print(f"   ❌ {table} 缺失列: {', '.join(issues['missing'])}")
                if issues["extra"]:
                    print(f"   ℹ️  {table} 额外列: {', '.join(issues['extra'])}")
                    
            return compatibility_report
            
        except Exception as e:
            raise Exception(f"架构兼容性检查失败: {e}")
            
    def migrate_to_latest(self, create_backup: bool = True) -> bool:
        """迁移到最新架构"""
        print("🚀 开始数据库迁移...")
        
        try:
            # 创建备份
            if create_backup:
                backup_path = self.create_backup()
                print(f"   📦 备份已创建: {backup_path}")
                
            # 检查当前架构
            compatibility = self.check_schema_compatibility()
            
            if compatibility["compatible"]:
                print("   ✅ 数据库架构已是最新版本")
                return True
                
            # 执行迁移
            print("   🔄 执行架构迁移...")
            
            # 创建所有表（如果不存在）
            Base.metadata.create_all(self.engine)
            
            # 再次检查兼容性
            post_migration_compatibility = self.check_schema_compatibility()
            
            if post_migration_compatibility["compatible"]:
                print("   ✅ 迁移完成，架构已更新")
                
                # 记录迁移信息
                self.migration_log.append({
                    "action": "migrate",
                    "details": {
                        "timestamp": datetime.now().isoformat(),
                        "pre_migration": compatibility["summary"],
                        "post_migration": post_migration_compatibility["summary"],
                        "backup_created": create_backup,
                        "status": "success"
                    }
                })
                
                return True
            else:
                raise Exception("迁移后架构仍不兼容")
                
        except Exception as e:
            print(f"   ❌ 迁移失败: {e}")
            
            # 记录失败信息
            self.migration_log.append({
                "action": "migrate",
                "details": {
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e),
                    "status": "failed"
                }
            })
            
            raise
            
    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份文件"""
        backups = []
        
        if not self.backup_dir.exists():
            return backups
            
        for backup_file in self.backup_dir.glob("*.db"):
            try:
                stat = backup_file.stat()
                backups.append({
                    "name": backup_file.name,
                    "path": str(backup_file),
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except Exception:
                continue
                
        # 按创建时间排序
        backups.sort(key=lambda x: x["created"], reverse=True)
        return backups
        
    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """清理旧备份文件"""
        backups = self.list_backups()
        
        if len(backups) <= keep_count:
            return 0
            
        to_delete = backups[keep_count:]
        deleted_count = 0
        
        print(f"🗑️  清理旧备份文件 (保留最新 {keep_count} 个)...")
        
        for backup in to_delete:
            try:
                Path(backup["path"]).unlink()
                print(f"   删除: {backup['name']}")
                deleted_count += 1
            except Exception as e:
                print(f"   删除失败 {backup['name']}: {e}")
                
        return deleted_count
        
    def export_migration_log(self, output_path: Optional[str] = None) -> str:
        """导出迁移日志"""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.backup_dir / f"migration_log_{timestamp}.json")
            
        log_data = {
            "database_path": str(self.db_path),
            "migration_timestamp": datetime.now().isoformat(),
            "operations": self.migration_log
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
            
        return output_path


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='数据库迁移工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 检查数据库架构兼容性
    python database_migrator.py --check
    
    # 迁移到最新架构
    python database_migrator.py --migrate
    
    # 创建备份
    python database_migrator.py --backup
    
    # 从备份恢复
    python database_migrator.py --restore backup_20241201_120000.db
    
    # 列出所有备份
    python database_migrator.py --list-backups
    
    # 清理旧备份
    python database_migrator.py --cleanup-backups --keep 5
        """
    )
    
    parser.add_argument(
        '--db-path',
        help='数据库文件路径'
    )
    
    parser.add_argument(
        '--backup-dir',
        help='备份目录路径'
    )
    
    parser.add_argument(
        '--check',
        action='store_true',
        help='检查数据库架构兼容性'
    )
    
    parser.add_argument(
        '--migrate',
        action='store_true',
        help='迁移到最新架构'
    )
    
    parser.add_argument(
        '--backup',
        action='store_true',
        help='创建数据库备份'
    )
    
    parser.add_argument(
        '--restore',
        metavar='BACKUP_FILE',
        help='从备份文件恢复数据库'
    )
    
    parser.add_argument(
        '--list-backups',
        action='store_true',
        help='列出所有备份文件'
    )
    
    parser.add_argument(
        '--cleanup-backups',
        action='store_true',
        help='清理旧备份文件'
    )
    
    parser.add_argument(
        '--keep',
        type=int,
        default=10,
        help='清理备份时保留的文件数量（默认: 10）'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='迁移时不创建备份'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制执行操作（跳过确认）'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='以JSON格式输出结果'
    )
    
    args = parser.parse_args()
    
    # 检查是否指定了操作
    operations = [args.check, args.migrate, args.backup, args.restore, args.list_backups, args.cleanup_backups]
    if not any(operations):
        parser.print_help()
        sys.exit(1)
        
    try:
        # 初始化迁移器
        db_path = args.db_path or str(project_root / "data" / "twitter_publisher.db")
        migrator = DatabaseMigrator(db_path, args.backup_dir)
        
        # 执行操作
        if args.check:
            migrator.initialize_connection()
            compatibility = migrator.check_schema_compatibility()
            
            if args.json:
                print(json.dumps(compatibility, indent=2, ensure_ascii=False))
            else:
                print("\n📊 架构兼容性报告:")
                print(f"   兼容性: {'✅ 兼容' if compatibility['compatible'] else '❌ 不兼容'}")
                print(f"   总表数: {compatibility['summary']['total_tables']}")
                print(f"   预期表数: {compatibility['summary']['expected_tables']}")
                
        elif args.migrate:
            migrator.initialize_connection()
            success = migrator.migrate_to_latest(create_backup=not args.no_backup)
            
            if args.json:
                print(json.dumps({"success": success}, indent=2))
                
        elif args.backup:
            backup_path = migrator.create_backup()
            
            if args.json:
                print(json.dumps({"backup_path": backup_path}, indent=2))
                
        elif args.restore:
            migrator.initialize_connection()
            success = migrator.restore_backup(args.restore, confirm=args.force)
            
            if args.json:
                print(json.dumps({"success": success}, indent=2))
                
        elif args.list_backups:
            backups = migrator.list_backups()
            
            if args.json:
                print(json.dumps(backups, indent=2, ensure_ascii=False))
            else:
                print("\n📦 备份文件列表:")
                if not backups:
                    print("   无备份文件")
                else:
                    for backup in backups:
                        size_mb = backup["size"] / (1024 * 1024)
                        print(f"   {backup['name']} ({size_mb:.1f}MB) - {backup['created']}")
                        
        elif args.cleanup_backups:
            deleted_count = migrator.cleanup_old_backups(args.keep)
            
            if args.json:
                print(json.dumps({"deleted_count": deleted_count}, indent=2))
            else:
                print(f"\n🗑️  已删除 {deleted_count} 个旧备份文件")
                
        # 导出迁移日志
        if migrator.migration_log:
            log_path = migrator.export_migration_log()
            if not args.json:
                print(f"\n📋 迁移日志已保存: {log_path}")
                
    except KeyboardInterrupt:
        print("\n⚠️  操作被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        sys.exit(1)
    finally:
        if 'migrator' in locals():
            migrator.cleanup_connection()


if __name__ == "__main__":
    main()