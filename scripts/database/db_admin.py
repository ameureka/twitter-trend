#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库管理员工具 - 统一的数据库管理和维护工具
整合所有数据库操作功能，提供完整的数据库管理解决方案
"""

import os
import sys
import sqlite3
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import argparse

class BackupType(Enum):
    """备份类型枚举"""
    FULL = "full"
    INCREMENTAL = "incremental"
    SCHEMA_ONLY = "schema_only"
    DATA_ONLY = "data_only"

class MaintenanceAction(Enum):
    """维护操作枚举"""
    VACUUM = "vacuum"
    REINDEX = "reindex"
    ANALYZE = "analyze"
    INTEGRITY_CHECK = "integrity_check"
    OPTIMIZE = "optimize"

@dataclass
class TableInfo:
    """表信息"""
    name: str
    row_count: int
    size_bytes: int
    last_modified: Optional[str] = None
    
    @property
    def size_mb(self) -> float:
        """大小(MB)"""
        return self.size_bytes / 1024 / 1024

@dataclass
class DatabaseInfo:
    """数据库信息"""
    file_path: str
    file_size: int
    table_count: int
    total_rows: int
    created_time: datetime
    modified_time: datetime
    version: str
    
    @property
    def size_mb(self) -> float:
        """大小(MB)"""
        return self.file_size / 1024 / 1024

class DatabaseAdmin:
    """数据库管理员"""
    
    def __init__(self, db_path: str = 'data/twitter_publisher.db'):
        self.db_path = db_path
        self.backup_dir = Path('backups')
        self.backup_dir.mkdir(exist_ok=True)
    
    def check_database_exists(self) -> bool:
        """检查数据库是否存在"""
        return os.path.exists(self.db_path)
    
    def get_database_info(self) -> Optional[DatabaseInfo]:
        """获取数据库基本信息"""
        if not self.check_database_exists():
            return None
        
        try:
            file_stat = os.stat(self.db_path)
            file_size = file_stat.st_size
            created_time = datetime.fromtimestamp(file_stat.st_ctime)
            modified_time = datetime.fromtimestamp(file_stat.st_mtime)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取表数量
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            # 获取总行数
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            total_rows = 0
            
            for table in tables:
                table_name = table[0]
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    total_rows += cursor.fetchone()[0]
                except:
                    pass
            
            # 获取SQLite版本
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
            
            conn.close()
            
            return DatabaseInfo(
                file_path=self.db_path,
                file_size=file_size,
                table_count=table_count,
                total_rows=total_rows,
                created_time=created_time,
                modified_time=modified_time,
                version=version
            )
            
        except Exception as e:
            print(f"❌ 获取数据库信息失败: {e}")
            return None
    
    def get_table_info(self) -> List[TableInfo]:
        """获取所有表信息"""
        if not self.check_database_exists():
            return []
        
        tables = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取所有表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            table_names = [row[0] for row in cursor.fetchall()]
            
            for table_name in table_names:
                try:
                    # 获取行数
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    row_count = cursor.fetchone()[0]
                    
                    # 估算表大小 (这是一个近似值)
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
                    sample_row = cursor.fetchone()
                    
                    if sample_row and row_count > 0:
                        # 估算每行大小
                        row_size = sum(len(str(col)) if col else 0 for col in sample_row)
                        estimated_size = row_size * row_count
                    else:
                        estimated_size = 0
                    
                    table_info = TableInfo(
                        name=table_name,
                        row_count=row_count,
                        size_bytes=estimated_size
                    )
                    tables.append(table_info)
                    
                except Exception as e:
                    print(f"⚠️  获取表 {table_name} 信息失败: {e}")
                    continue
            
            conn.close()
            
        except Exception as e:
            print(f"❌ 获取表信息失败: {e}")
        
        return tables
    
    def show_database_overview(self):
        """显示数据库概览"""
        print(f"\n🗄️  数据库概览")
        print("=" * 60)
        
        if not self.check_database_exists():
            print(f"❌ 数据库文件不存在: {self.db_path}")
            return
        
        db_info = self.get_database_info()
        if not db_info:
            print(f"❌ 无法获取数据库信息")
            return
        
        print(f"📁 文件路径: {db_info.file_path}")
        print(f"📊 文件大小: {db_info.file_size:,} 字节 ({db_info.size_mb:.2f} MB)")
        print(f"📋 表数量: {db_info.table_count}")
        print(f"📝 总记录数: {db_info.total_rows:,}")
        print(f"🕐 创建时间: {db_info.created_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🕑 修改时间: {db_info.modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔧 SQLite版本: {db_info.version}")
        
        # 显示表信息
        tables = self.get_table_info()
        if tables:
            print(f"\n📋 表详情")
            print("-" * 60)
            print(f"{'表名':<20} {'记录数':<10} {'大小(MB)':<10}")
            print("-" * 60)
            
            for table in sorted(tables, key=lambda t: t.row_count, reverse=True):
                print(f"{table.name:<20} {table.row_count:<10,} {table.size_mb:<10.2f}")
    
    def backup_database(self, backup_type: BackupType = BackupType.FULL, 
                       custom_name: Optional[str] = None) -> Optional[str]:
        """备份数据库"""
        if not self.check_database_exists():
            print(f"❌ 数据库文件不存在: {self.db_path}")
            return None
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if custom_name:
                backup_name = f"{custom_name}_{timestamp}"
            else:
                backup_name = f"backup_{backup_type.value}_{timestamp}"
            
            backup_path = self.backup_dir / f"{backup_name}.db"
            
            if backup_type == BackupType.FULL:
                # 完整备份
                shutil.copy2(self.db_path, backup_path)
                print(f"✅ 完整备份已创建: {backup_path}")
            
            elif backup_type == BackupType.SCHEMA_ONLY:
                # 仅备份结构
                conn_source = sqlite3.connect(self.db_path)
                conn_backup = sqlite3.connect(backup_path)
                
                # 获取所有表的创建语句
                cursor = conn_source.cursor()
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
                
                for row in cursor.fetchall():
                    if row[0]:  # 跳过None值
                        conn_backup.execute(row[0])
                
                conn_backup.commit()
                conn_source.close()
                conn_backup.close()
                print(f"✅ 结构备份已创建: {backup_path}")
            
            elif backup_type == BackupType.DATA_ONLY:
                # 仅备份数据 (需要先有结构)
                print(f"⚠️  数据备份需要目标数据库已有相同结构")
                return None
            
            return str(backup_path)
            
        except Exception as e:
            print(f"❌ 备份失败: {e}")
            return None
    
    def restore_database(self, backup_path: str, confirm: bool = False) -> bool:
        """恢复数据库"""
        if not os.path.exists(backup_path):
            print(f"❌ 备份文件不存在: {backup_path}")
            return False
        
        if not confirm:
            print(f"⚠️  此操作将覆盖当前数据库: {self.db_path}")
            response = input("确认恢复? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("❌ 恢复操作已取消")
                return False
        
        try:
            # 备份当前数据库
            if self.check_database_exists():
                current_backup = self.backup_database(BackupType.FULL, "pre_restore")
                if current_backup:
                    print(f"📋 当前数据库已备份至: {current_backup}")
            
            # 恢复数据库
            shutil.copy2(backup_path, self.db_path)
            print(f"✅ 数据库已从 {backup_path} 恢复")
            return True
            
        except Exception as e:
            print(f"❌ 恢复失败: {e}")
            return False
    
    def list_backups(self):
        """列出所有备份"""
        print(f"\n💾 备份列表")
        print("=" * 60)
        
        if not self.backup_dir.exists():
            print(f"📭 备份目录不存在: {self.backup_dir}")
            return
        
        backup_files = list(self.backup_dir.glob('*.db'))
        
        if not backup_files:
            print(f"📭 没有找到备份文件")
            return
        
        # 按修改时间排序
        backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        print(f"{'文件名':<30} {'大小(MB)':<10} {'创建时间':<20}")
        print("-" * 60)
        
        for backup_file in backup_files:
            stat = backup_file.stat()
            size_mb = stat.st_size / 1024 / 1024
            created_time = datetime.fromtimestamp(stat.st_ctime)
            
            print(f"{backup_file.name:<30} {size_mb:<10.2f} {created_time.strftime('%Y-%m-%d %H:%M:%S'):<20}")
    
    def maintenance(self, action: MaintenanceAction) -> bool:
        """执行数据库维护操作"""
        if not self.check_database_exists():
            print(f"❌ 数据库文件不存在: {self.db_path}")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"🔧 执行维护操作: {action.value}")
            
            if action == MaintenanceAction.VACUUM:
                print(f"📦 正在压缩数据库...")
                cursor.execute("VACUUM")
                print(f"✅ 数据库压缩完成")
            
            elif action == MaintenanceAction.REINDEX:
                print(f"📇 正在重建索引...")
                cursor.execute("REINDEX")
                print(f"✅ 索引重建完成")
            
            elif action == MaintenanceAction.ANALYZE:
                print(f"📊 正在分析数据库统计信息...")
                cursor.execute("ANALYZE")
                print(f"✅ 统计信息分析完成")
            
            elif action == MaintenanceAction.INTEGRITY_CHECK:
                print(f"🔍 正在检查数据库完整性...")
                cursor.execute("PRAGMA integrity_check")
                results = cursor.fetchall()
                
                if results and results[0][0] == 'ok':
                    print(f"✅ 数据库完整性检查通过")
                else:
                    print(f"⚠️  数据库完整性检查发现问题:")
                    for result in results:
                        print(f"  - {result[0]}")
            
            elif action == MaintenanceAction.OPTIMIZE:
                print(f"⚡ 正在优化数据库...")
                cursor.execute("PRAGMA optimize")
                print(f"✅ 数据库优化完成")
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ 维护操作失败: {e}")
            return False
    
    def export_data(self, table_name: str, output_format: str = 'json', 
                   output_file: Optional[str] = None, limit: Optional[int] = None) -> bool:
        """导出数据"""
        if not self.check_database_exists():
            print(f"❌ 数据库文件不存在: {self.db_path}")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                print(f"❌ 表 '{table_name}' 不存在")
                return False
            
            # 构建查询
            query = f"SELECT * FROM {table_name}"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # 获取列名
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            
            # 生成输出文件名
            if not output_file:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = f"{table_name}_export_{timestamp}.{output_format}"
            
            # 导出数据
            if output_format.lower() == 'json':
                data = []
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    data.append(row_dict)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            elif output_format.lower() == 'csv':
                import csv
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)  # 写入表头
                    writer.writerows(rows)
            
            elif output_format.lower() == 'sql':
                with open(output_file, 'w', encoding='utf-8') as f:
                    # 写入表结构
                    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                    create_sql = cursor.fetchone()[0]
                    f.write(f"{create_sql};\n\n")
                    
                    # 写入数据
                    for row in rows:
                        values = []
                        for value in row:
                            if value is None:
                                values.append('NULL')
                            elif isinstance(value, str):
                                escaped_value = value.replace("'", "''")
                                values.append(f"'{escaped_value}'")
                            else:
                                values.append(str(value))
                        
                        insert_sql = f"INSERT INTO {table_name} VALUES ({', '.join(values)});\n"
                        f.write(insert_sql)
            
            else:
                print(f"❌ 不支持的导出格式: {output_format}")
                return False
            
            conn.close()
            print(f"✅ 数据已导出至: {output_file} ({len(rows)} 条记录)")
            return True
            
        except Exception as e:
            print(f"❌ 导出失败: {e}")
            return False
    
    def import_data(self, table_name: str, input_file: str, 
                   input_format: str = 'json', replace: bool = False) -> bool:
        """导入数据"""
        if not self.check_database_exists():
            print(f"❌ 数据库文件不存在: {self.db_path}")
            return False
        
        if not os.path.exists(input_file):
            print(f"❌ 输入文件不存在: {input_file}")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                print(f"❌ 表 '{table_name}' 不存在")
                return False
            
            # 如果需要替换，先清空表
            if replace:
                cursor.execute(f"DELETE FROM {table_name}")
                print(f"🗑️  表 '{table_name}' 已清空")
            
            # 导入数据
            imported_count = 0
            
            if input_format.lower() == 'json':
                with open(input_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            columns = list(item.keys())
                            values = list(item.values())
                            placeholders = ','.join(['?' for _ in values])
                            
                            insert_sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
                            cursor.execute(insert_sql, values)
                            imported_count += 1
            
            elif input_format.lower() == 'csv':
                import csv
                with open(input_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        columns = list(row.keys())
                        values = list(row.values())
                        placeholders = ','.join(['?' for _ in values])
                        
                        insert_sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
                        cursor.execute(insert_sql, values)
                        imported_count += 1
            
            else:
                print(f"❌ 不支持的导入格式: {input_format}")
                return False
            
            conn.commit()
            conn.close()
            print(f"✅ 数据已导入: {imported_count} 条记录")
            return True
            
        except Exception as e:
            print(f"❌ 导入失败: {e}")
            return False
    
    def show_table_schema(self, table_name: str):
        """显示表结构"""
        if not self.check_database_exists():
            print(f"❌ 数据库文件不存在: {self.db_path}")
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                print(f"❌ 表 '{table_name}' 不存在")
                return
            
            print(f"\n📋 表结构: {table_name}")
            print("=" * 60)
            
            # 获取表信息
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            print(f"{'列名':<20} {'类型':<15} {'非空':<5} {'默认值':<15} {'主键':<5}")
            print("-" * 60)
            
            for col in columns:
                cid, name, col_type, notnull, default_value, pk = col
                notnull_str = "是" if notnull else "否"
                pk_str = "是" if pk else "否"
                default_str = str(default_value) if default_value is not None else ""
                
                print(f"{name:<20} {col_type:<15} {notnull_str:<5} {default_str:<15} {pk_str:<5}")
            
            # 获取索引信息
            cursor.execute(f"PRAGMA index_list({table_name})")
            indexes = cursor.fetchall()
            
            if indexes:
                print(f"\n📇 索引信息")
                print("-" * 40)
                for idx in indexes:
                    seq, name, unique, origin, partial = idx
                    unique_str = "唯一" if unique else "普通"
                    print(f"  {name} ({unique_str})")
                    
                    # 获取索引列
                    cursor.execute(f"PRAGMA index_info({name})")
                    idx_cols = cursor.fetchall()
                    col_names = [col[2] for col in idx_cols]
                    print(f"    列: {', '.join(col_names)}")
            
            # 获取外键信息
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            foreign_keys = cursor.fetchall()
            
            if foreign_keys:
                print(f"\n🔗 外键信息")
                print("-" * 40)
                for fk in foreign_keys:
                    id, seq, table, from_col, to_col, on_update, on_delete, match = fk
                    print(f"  {from_col} -> {table}.{to_col}")
                    print(f"    更新: {on_update}, 删除: {on_delete}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ 获取表结构失败: {e}")
    
    def execute_query(self, query: str, params: Optional[Tuple] = None, 
                     fetch_results: bool = True, limit: int = 100) -> Optional[List[Tuple]]:
        """执行自定义查询"""
        if not self.check_database_exists():
            print(f"❌ 数据库文件不存在: {self.db_path}")
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"🔍 执行查询: {query[:100]}{'...' if len(query) > 100 else ''}")
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch_results:
                if query.strip().upper().startswith('SELECT'):
                    results = cursor.fetchmany(limit)
                    
                    if results:
                        # 获取列名
                        column_names = [description[0] for description in cursor.description]
                        
                        print(f"\n📊 查询结果 (显示前 {len(results)} 条)")
                        print("-" * 60)
                        
                        # 显示表头
                        header = " | ".join(f"{col:<15}" for col in column_names)
                        print(header)
                        print("-" * len(header))
                        
                        # 显示数据
                        for row in results:
                            row_str = " | ".join(f"{str(val):<15}" for val in row)
                            print(row_str)
                        
                        # 检查是否还有更多结果
                        cursor.fetchone()
                        if cursor.fetchone():
                            print(f"\n... 还有更多结果 (使用 --limit 参数查看更多)")
                    else:
                        print(f"📭 查询无结果")
                    
                    return results
                else:
                    # 非SELECT查询
                    affected_rows = cursor.rowcount
                    conn.commit()
                    print(f"✅ 查询执行完成，影响 {affected_rows} 行")
                    return []
            else:
                conn.commit()
                print(f"✅ 查询执行完成")
                return []
            
        except Exception as e:
            print(f"❌ 查询执行失败: {e}")
            return None
        finally:
            conn.close()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="数据库管理员工具 - 统一的数据库管理和维护工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python db_admin.py --overview                           # 显示数据库概览
  python db_admin.py --backup full                       # 完整备份
  python db_admin.py --backup schema_only                # 仅备份结构
  python db_admin.py --restore backups/backup_xxx.db     # 恢复数据库
  python db_admin.py --list-backups                      # 列出备份
  python db_admin.py --maintenance vacuum                # 压缩数据库
  python db_admin.py --maintenance integrity_check       # 完整性检查
  python db_admin.py --export publishing_tasks json      # 导出表数据
  python db_admin.py --import publishing_tasks data.json # 导入表数据
  python db_admin.py --schema publishing_tasks           # 显示表结构
  python db_admin.py --query "SELECT * FROM users"       # 执行查询
        """
    )
    
    parser.add_argument(
        '--db-path',
        default='data/twitter_publisher.db',
        help='数据库文件路径'
    )
    
    parser.add_argument(
        '--overview', '-o',
        action='store_true',
        help='显示数据库概览'
    )
    
    parser.add_argument(
        '--backup', '-b',
        choices=[bt.value for bt in BackupType],
        help='备份数据库'
    )
    
    parser.add_argument(
        '--backup-name',
        help='自定义备份名称'
    )
    
    parser.add_argument(
        '--restore', '-r',
        help='从备份恢复数据库'
    )
    
    parser.add_argument(
        '--list-backups',
        action='store_true',
        help='列出所有备份'
    )
    
    parser.add_argument(
        '--maintenance', '-m',
        choices=[ma.value for ma in MaintenanceAction],
        help='执行维护操作'
    )
    
    parser.add_argument(
        '--export',
        help='导出表数据 (表名)'
    )
    
    parser.add_argument(
        '--import',
        dest='import_table',
        help='导入表数据 (表名)'
    )
    
    parser.add_argument(
        '--input-file',
        help='导入数据的输入文件'
    )
    
    parser.add_argument(
        '--output-file',
        help='导出数据的输出文件'
    )
    
    parser.add_argument(
        '--format',
        choices=['json', 'csv', 'sql'],
        default='json',
        help='导入/导出格式'
    )
    
    parser.add_argument(
        '--replace',
        action='store_true',
        help='导入时替换现有数据'
    )
    
    parser.add_argument(
        '--schema', '-s',
        help='显示表结构'
    )
    
    parser.add_argument(
        '--query', '-q',
        help='执行自定义查询'
    )
    
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=100,
        help='查询结果限制'
    )
    
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='跳过确认提示'
    )
    
    args = parser.parse_args()
    
    try:
        admin = DatabaseAdmin(args.db_path)
        
        if args.overview:
            admin.show_database_overview()
        
        elif args.backup:
            backup_type = BackupType(args.backup)
            admin.backup_database(backup_type, args.backup_name)
        
        elif args.restore:
            admin.restore_database(args.restore, args.confirm)
        
        elif args.list_backups:
            admin.list_backups()
        
        elif args.maintenance:
            action = MaintenanceAction(args.maintenance)
            admin.maintenance(action)
        
        elif args.export:
            admin.export_data(
                args.export, 
                args.format, 
                args.output_file, 
                args.limit
            )
        
        elif args.import_table:
            if not args.input_file:
                print("❌ 导入数据需要指定 --input-file")
                sys.exit(1)
            
            admin.import_data(
                args.import_table,
                args.input_file,
                args.format,
                args.replace
            )
        
        elif args.schema:
            admin.show_table_schema(args.schema)
        
        elif args.query:
            admin.execute_query(args.query, limit=args.limit)
        
        else:
            # 默认显示概览
            admin.show_database_overview()
    
    except KeyboardInterrupt:
        print("\n👋 操作已取消")
    except Exception as e:
        print(f"❌ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()