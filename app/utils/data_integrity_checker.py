#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 数据完整性检查器 - Phase 4.3
根据TWITTER_OPTIMIZATION_PLAN.md实现全面的数据完整性检查和自动修复机制

主要功能:
1. 数据一致性验证
2. 外键约束检查
3. 孤立记录检测
4. 数据冗余识别
5. 自动修复机制
6. 数据备份与恢复
7. 增量完整性检查
8. 实时监控与预警
"""

import sqlite3
import hashlib
import json
import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading
import time
import re

from app.utils.logger import get_logger

logger = get_logger(__name__)

class IntegrityIssueType(Enum):
    """完整性问题类型"""
    ORPHAN_RECORD = "orphan_record"              # 孤立记录
    MISSING_REFERENCE = "missing_reference"      # 缺失引用
    DUPLICATE_DATA = "duplicate_data"            # 重复数据
    INCONSISTENT_STATE = "inconsistent_state"    # 状态不一致
    INVALID_DATA = "invalid_data"                # 无效数据
    CORRUPTED_DATA = "corrupted_data"            # 损坏数据
    CONSTRAINT_VIOLATION = "constraint_violation" # 约束违反
    SCHEMA_MISMATCH = "schema_mismatch"          # 模式不匹配
    SEQUENCE_GAP = "sequence_gap"                # 序列间隙
    TIMESTAMP_ANOMALY = "timestamp_anomaly"      # 时间戳异常

class RepairStrategy(Enum):
    """修复策略"""
    AUTO_FIX = "auto_fix"                    # 自动修复
    MANUAL_REVIEW = "manual_review"          # 人工审查
    BACKUP_RESTORE = "backup_restore"        # 备份恢复
    CASCADE_DELETE = "cascade_delete"        # 级联删除
    DEFAULT_VALUE = "default_value"          # 默认值填充
    RECALCULATE = "recalculate"             # 重新计算
    IGNORE = "ignore"                        # 忽略

@dataclass
class IntegrityIssue:
    """完整性问题记录"""
    issue_id: str
    issue_type: IntegrityIssueType
    table_name: str
    record_id: Optional[Any]
    column_name: Optional[str]
    description: str
    severity: int  # 1-5, 5最严重
    detected_at: datetime
    repair_strategy: RepairStrategy
    repair_attempted: bool = False
    repair_successful: bool = False
    repair_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TableSchema:
    """表结构信息"""
    table_name: str
    columns: List[Dict[str, Any]]
    primary_keys: List[str]
    foreign_keys: List[Dict[str, Any]]
    indexes: List[Dict[str, Any]]
    constraints: List[Dict[str, Any]]
    row_count: int
    last_check: datetime

@dataclass
class IntegrityReport:
    """完整性检查报告"""
    check_id: str
    check_time: datetime
    duration_seconds: float
    tables_checked: int
    records_checked: int
    issues_found: List[IntegrityIssue]
    auto_fixed: int
    manual_required: int
    critical_issues: int
    recommendations: List[str]

class DataIntegrityChecker:
    """🔍 高级数据完整性检查器"""
    
    def __init__(self, db_path: str, config: Optional[Dict[str, Any]] = None):
        self.db_path = db_path
        self.config = config or {}
        
        # 配置参数
        self.check_interval = self.config.get('check_interval', 3600)  # 1小时
        self.auto_repair = self.config.get('auto_repair', True)
        self.backup_before_repair = self.config.get('backup_before_repair', True)
        self.max_repair_attempts = self.config.get('max_repair_attempts', 3)
        self.critical_severity_threshold = self.config.get('critical_severity_threshold', 4)
        
        # 表结构缓存
        self.schema_cache: Dict[str, TableSchema] = {}
        self.schema_cache_ttl = timedelta(hours=1)
        
        # 问题追踪
        self.active_issues: Dict[str, IntegrityIssue] = {}
        self.issue_history: List[IntegrityIssue] = []
        self.repair_history: List[Dict[str, Any]] = []
        
        # 检查规则
        self.integrity_rules = self._initialize_integrity_rules()
        
        # 修复策略映射
        self.repair_strategies = self._initialize_repair_strategies()
        
        # 监控状态
        self.monitoring = False
        self.monitor_thread = None
        self.last_check_time = None
        self.lock = threading.RLock()
        
        # 统计信息
        self.statistics = {
            'total_checks': 0,
            'total_issues': 0,
            'auto_fixed': 0,
            'manual_required': 0,
            'failed_repairs': 0,
            'check_duration_avg': 0.0
        }
        
        logger.info("🔍 数据完整性检查器已初始化")
        logger.info(f"  - 数据库路径: {self.db_path}")
        logger.info(f"  - 自动修复: {self.auto_repair}")
        logger.info(f"  - 检查间隔: {self.check_interval}秒")
    
    def _initialize_integrity_rules(self) -> Dict[str, List[Callable]]:
        """初始化完整性检查规则"""
        return {
            'publishing_tasks': [
                self._check_task_references,
                self._check_task_states,
                self._check_task_timestamps,
                self._check_task_duplicates
            ],
            'publishing_logs': [
                self._check_log_references,
                self._check_log_sequence,
                self._check_log_timestamps
            ],
            'projects': [
                self._check_project_references,
                self._check_project_constraints
            ],
            'content_sources': [
                self._check_source_references,
                self._check_source_paths
            ],
            'api_keys': [
                self._check_api_key_validity,
                self._check_api_key_expiration
            ],
            'analytics_hourly': [
                self._check_analytics_gaps,
                self._check_analytics_consistency
            ]
        }
    
    def _initialize_repair_strategies(self) -> Dict[IntegrityIssueType, Callable]:
        """初始化修复策略"""
        return {
            IntegrityIssueType.ORPHAN_RECORD: self._repair_orphan_record,
            IntegrityIssueType.MISSING_REFERENCE: self._repair_missing_reference,
            IntegrityIssueType.DUPLICATE_DATA: self._repair_duplicate_data,
            IntegrityIssueType.INCONSISTENT_STATE: self._repair_inconsistent_state,
            IntegrityIssueType.INVALID_DATA: self._repair_invalid_data,
            IntegrityIssueType.CORRUPTED_DATA: self._repair_corrupted_data,
            IntegrityIssueType.CONSTRAINT_VIOLATION: self._repair_constraint_violation,
            IntegrityIssueType.SCHEMA_MISMATCH: self._repair_schema_mismatch,
            IntegrityIssueType.SEQUENCE_GAP: self._repair_sequence_gap,
            IntegrityIssueType.TIMESTAMP_ANOMALY: self._repair_timestamp_anomaly
        }
    
    def perform_full_check(self) -> IntegrityReport:
        """
        执行全面的完整性检查
        
        Returns:
            IntegrityReport: 检查报告
        """
        logger.info("🔍 开始执行全面数据完整性检查...")
        
        check_id = self._generate_check_id()
        start_time = datetime.now()
        issues_found = []
        tables_checked = 0
        records_checked = 0
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # 刷新表结构缓存
                self._refresh_schema_cache(conn)
                
                # 对每个表执行检查
                for table_name, schema in self.schema_cache.items():
                    logger.info(f"🔍 检查表: {table_name}")
                    tables_checked += 1
                    
                    # 获取表记录数
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    row_count = cursor.fetchone()[0]
                    records_checked += row_count
                    
                    # 执行表特定的检查规则
                    if table_name in self.integrity_rules:
                        for rule_func in self.integrity_rules[table_name]:
                            try:
                                table_issues = rule_func(conn, table_name, schema)
                                issues_found.extend(table_issues)
                            except Exception as e:
                                logger.error(f"🔍 规则检查失败 {rule_func.__name__}: {e}")
                    
                    # 执行通用检查
                    generic_issues = self._perform_generic_checks(conn, table_name, schema)
                    issues_found.extend(generic_issues)
                
                # 执行跨表检查
                cross_table_issues = self._perform_cross_table_checks(conn)
                issues_found.extend(cross_table_issues)
                
            # 记录问题
            with self.lock:
                for issue in issues_found:
                    self.active_issues[issue.issue_id] = issue
                    self.issue_history.append(issue)
            
            # 自动修复
            auto_fixed = 0
            manual_required = 0
            critical_issues = 0
            
            if self.auto_repair and issues_found:
                logger.info(f"🔍 发现 {len(issues_found)} 个问题，开始自动修复...")
                
                for issue in issues_found:
                    if issue.severity >= self.critical_severity_threshold:
                        critical_issues += 1
                    
                    if issue.repair_strategy == RepairStrategy.AUTO_FIX:
                        if self._attempt_auto_repair(issue):
                            auto_fixed += 1
                        else:
                            manual_required += 1
                    else:
                        manual_required += 1
            
            # 生成建议
            recommendations = self._generate_recommendations(issues_found)
            
            # 创建报告
            duration = (datetime.now() - start_time).total_seconds()
            report = IntegrityReport(
                check_id=check_id,
                check_time=start_time,
                duration_seconds=duration,
                tables_checked=tables_checked,
                records_checked=records_checked,
                issues_found=issues_found,
                auto_fixed=auto_fixed,
                manual_required=manual_required,
                critical_issues=critical_issues,
                recommendations=recommendations
            )
            
            # 更新统计
            self._update_statistics(report)
            
            # 记录结果
            self._log_report(report)
            
            self.last_check_time = datetime.now()
            
            return report
            
        except Exception as e:
            logger.error(f"🔍 完整性检查失败: {e}")
            raise
    
    def _refresh_schema_cache(self, conn: sqlite3.Connection):
        """刷新表结构缓存"""
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        for table_row in tables:
            table_name = table_row[0]
            
            if table_name.startswith('sqlite_'):
                continue
            
            # 获取表信息
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [dict(row) for row in cursor.fetchall()]
            
            # 获取主键
            primary_keys = [col['name'] for col in columns if col['pk'] > 0]
            
            # 获取外键
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            foreign_keys = [dict(row) for row in cursor.fetchall()]
            
            # 获取索引
            cursor.execute(f"PRAGMA index_list({table_name})")
            indexes = [dict(row) for row in cursor.fetchall()]
            
            # 获取行数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            # 创建表结构对象
            schema = TableSchema(
                table_name=table_name,
                columns=columns,
                primary_keys=primary_keys,
                foreign_keys=foreign_keys,
                indexes=indexes,
                constraints=[],  # SQLite不直接提供约束信息
                row_count=row_count,
                last_check=datetime.now()
            )
            
            self.schema_cache[table_name] = schema
    
    def _check_task_references(self, conn: sqlite3.Connection, table_name: str, 
                              schema: TableSchema) -> List[IntegrityIssue]:
        """检查任务表引用完整性"""
        issues = []
        
        # 检查project_id引用
        cursor = conn.execute("""
            SELECT t.id, t.project_id 
            FROM publishing_tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE p.id IS NULL AND t.project_id IS NOT NULL
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.MISSING_REFERENCE,
                table_name=table_name,
                record_id=row[0],
                column_name='project_id',
                description=f"任务 {row[0]} 引用了不存在的项目 {row[1]}",
                severity=4,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.CASCADE_DELETE,
                metadata={'task_id': row[0], 'project_id': row[1]}
            )
            issues.append(issue)
        
        # 检查source_id引用
        cursor = conn.execute("""
            SELECT t.id, t.source_id 
            FROM publishing_tasks t
            LEFT JOIN content_sources s ON t.source_id = s.id
            WHERE s.id IS NULL AND t.source_id IS NOT NULL
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.MISSING_REFERENCE,
                table_name=table_name,
                record_id=row[0],
                column_name='source_id',
                description=f"任务 {row[0]} 引用了不存在的内容源 {row[1]}",
                severity=4,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.CASCADE_DELETE,
                metadata={'task_id': row[0], 'source_id': row[1]}
            )
            issues.append(issue)
        
        return issues
    
    def _check_task_states(self, conn: sqlite3.Connection, table_name: str,
                          schema: TableSchema) -> List[IntegrityIssue]:
        """检查任务状态一致性"""
        issues = []
        
        # 检查长时间处于运行状态的任务
        cursor = conn.execute("""
            SELECT id, status, updated_at
            FROM publishing_tasks
            WHERE status IN ('running', 'processing')
            AND datetime(updated_at) < datetime('now', '-1 hour')
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.INCONSISTENT_STATE,
                table_name=table_name,
                record_id=row[0],
                column_name='status',
                description=f"任务 {row[0]} 长时间处于 {row[1]} 状态",
                severity=3,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.AUTO_FIX,
                metadata={'task_id': row[0], 'status': row[1], 'updated_at': row[2]}
            )
            issues.append(issue)
        
        # 检查无效的状态值
        valid_states = ['pending', 'running', 'completed', 'failed', 'retry', 'cancelled']
        cursor = conn.execute(f"""
            SELECT id, status
            FROM publishing_tasks
            WHERE status NOT IN ({','.join(['?'] * len(valid_states))})
        """, valid_states)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.INVALID_DATA,
                table_name=table_name,
                record_id=row[0],
                column_name='status',
                description=f"任务 {row[0]} 的状态值无效: {row[1]}",
                severity=4,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.DEFAULT_VALUE,
                metadata={'task_id': row[0], 'invalid_status': row[1]}
            )
            issues.append(issue)
        
        return issues
    
    def _check_task_timestamps(self, conn: sqlite3.Connection, table_name: str,
                              schema: TableSchema) -> List[IntegrityIssue]:
        """检查任务时间戳一致性"""
        issues = []
        
        # 检查时间戳异常（更新时间早于创建时间）
        cursor = conn.execute("""
            SELECT id, created_at, updated_at
            FROM publishing_tasks
            WHERE datetime(updated_at) < datetime(created_at)
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.TIMESTAMP_ANOMALY,
                table_name=table_name,
                record_id=row[0],
                column_name='updated_at',
                description=f"任务 {row[0]} 的更新时间早于创建时间",
                severity=2,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.AUTO_FIX,
                metadata={'task_id': row[0], 'created_at': row[1], 'updated_at': row[2]}
            )
            issues.append(issue)
        
        # 检查未来时间戳
        cursor = conn.execute("""
            SELECT id, created_at
            FROM publishing_tasks
            WHERE datetime(created_at) > datetime('now')
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.TIMESTAMP_ANOMALY,
                table_name=table_name,
                record_id=row[0],
                column_name='created_at',
                description=f"任务 {row[0]} 的创建时间在未来",
                severity=3,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.AUTO_FIX,
                metadata={'task_id': row[0], 'created_at': row[1]}
            )
            issues.append(issue)
        
        return issues
    
    def _check_task_duplicates(self, conn: sqlite3.Connection, table_name: str,
                              schema: TableSchema) -> List[IntegrityIssue]:
        """检查任务重复"""
        issues = []
        
        # 检查相同媒体文件的重复任务
        cursor = conn.execute("""
            SELECT media_path, COUNT(*) as count, GROUP_CONCAT(id) as task_ids
            FROM publishing_tasks
            WHERE status IN ('pending', 'retry')
            GROUP BY media_path
            HAVING COUNT(*) > 1
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.DUPLICATE_DATA,
                table_name=table_name,
                record_id=None,
                column_name='media_path',
                description=f"发现 {row[1]} 个重复的待处理任务使用相同媒体: {row[0]}",
                severity=3,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.AUTO_FIX,
                metadata={'media_path': row[0], 'count': row[1], 'task_ids': row[2].split(',')}
            )
            issues.append(issue)
        
        return issues
    
    def _check_log_references(self, conn: sqlite3.Connection, table_name: str,
                             schema: TableSchema) -> List[IntegrityIssue]:
        """检查日志表引用完整性"""
        issues = []
        
        # 检查task_id引用
        cursor = conn.execute("""
            SELECT l.id, l.task_id
            FROM publishing_logs l
            LEFT JOIN publishing_tasks t ON l.task_id = t.id
            WHERE t.id IS NULL
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.ORPHAN_RECORD,
                table_name=table_name,
                record_id=row[0],
                column_name='task_id',
                description=f"日志 {row[0]} 引用了不存在的任务 {row[1]}",
                severity=2,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.CASCADE_DELETE,
                metadata={'log_id': row[0], 'task_id': row[1]}
            )
            issues.append(issue)
        
        return issues
    
    def _check_log_sequence(self, conn: sqlite3.Connection, table_name: str,
                           schema: TableSchema) -> List[IntegrityIssue]:
        """检查日志序列完整性"""
        issues = []
        
        # 检查ID序列间隙
        cursor = conn.execute("""
            SELECT id FROM publishing_logs ORDER BY id
        """)
        
        ids = [row[0] for row in cursor]
        if ids:
            expected_ids = set(range(min(ids), max(ids) + 1))
            actual_ids = set(ids)
            missing_ids = expected_ids - actual_ids
            
            if missing_ids:
                issue = IntegrityIssue(
                    issue_id=self._generate_issue_id(),
                    issue_type=IntegrityIssueType.SEQUENCE_GAP,
                    table_name=table_name,
                    record_id=None,
                    column_name='id',
                    description=f"日志ID序列存在 {len(missing_ids)} 个间隙",
                    severity=1,
                    detected_at=datetime.now(),
                    repair_strategy=RepairStrategy.IGNORE,
                    metadata={'missing_ids': list(missing_ids)[:10]}  # 只记录前10个
                )
                issues.append(issue)
        
        return issues
    
    def _check_log_timestamps(self, conn: sqlite3.Connection, table_name: str,
                             schema: TableSchema) -> List[IntegrityIssue]:
        """检查日志时间戳"""
        issues = []
        
        # 检查日志时间戳顺序
        cursor = conn.execute("""
            SELECT l1.id, l1.task_id, l1.published_at, l2.published_at
            FROM publishing_logs l1
            JOIN publishing_logs l2 ON l1.task_id = l2.task_id
            WHERE l1.id < l2.id 
            AND datetime(l1.published_at) > datetime(l2.published_at)
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.TIMESTAMP_ANOMALY,
                table_name=table_name,
                record_id=row[0],
                column_name='published_at',
                description=f"日志 {row[0]} 的时间戳顺序异常",
                severity=2,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.MANUAL_REVIEW,
                metadata={'log_id': row[0], 'task_id': row[1]}
            )
            issues.append(issue)
        
        return issues
    
    def _check_project_references(self, conn: sqlite3.Connection, table_name: str,
                                 schema: TableSchema) -> List[IntegrityIssue]:
        """检查项目表引用"""
        issues = []
        
        # 检查user_id引用
        cursor = conn.execute("""
            SELECT p.id, p.user_id
            FROM projects p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE u.id IS NULL
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.MISSING_REFERENCE,
                table_name=table_name,
                record_id=row[0],
                column_name='user_id',
                description=f"项目 {row[0]} 引用了不存在的用户 {row[1]}",
                severity=5,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.MANUAL_REVIEW,
                metadata={'project_id': row[0], 'user_id': row[1]}
            )
            issues.append(issue)
        
        return issues
    
    def _check_project_constraints(self, conn: sqlite3.Connection, table_name: str,
                                  schema: TableSchema) -> List[IntegrityIssue]:
        """检查项目约束"""
        issues = []
        
        # 检查项目名称唯一性（同一用户下）
        cursor = conn.execute("""
            SELECT user_id, name, COUNT(*) as count, GROUP_CONCAT(id) as project_ids
            FROM projects
            WHERE is_active = 1
            GROUP BY user_id, name
            HAVING COUNT(*) > 1
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.CONSTRAINT_VIOLATION,
                table_name=table_name,
                record_id=None,
                column_name='name',
                description=f"用户 {row[0]} 下存在 {row[2]} 个同名项目: {row[1]}",
                severity=3,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.MANUAL_REVIEW,
                metadata={'user_id': row[0], 'name': row[1], 'project_ids': row[3].split(',')}
            )
            issues.append(issue)
        
        return issues
    
    def _check_source_references(self, conn: sqlite3.Connection, table_name: str,
                                schema: TableSchema) -> List[IntegrityIssue]:
        """检查内容源引用"""
        issues = []
        
        # 检查project_id引用
        cursor = conn.execute("""
            SELECT s.id, s.project_id
            FROM content_sources s
            LEFT JOIN projects p ON s.project_id = p.id
            WHERE p.id IS NULL
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.MISSING_REFERENCE,
                table_name=table_name,
                record_id=row[0],
                column_name='project_id',
                description=f"内容源 {row[0]} 引用了不存在的项目 {row[1]}",
                severity=4,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.CASCADE_DELETE,
                metadata={'source_id': row[0], 'project_id': row[1]}
            )
            issues.append(issue)
        
        return issues
    
    def _check_source_paths(self, conn: sqlite3.Connection, table_name: str,
                           schema: TableSchema) -> List[IntegrityIssue]:
        """检查内容源路径有效性"""
        issues = []
        
        cursor = conn.execute("""
            SELECT id, folder_path
            FROM content_sources
            WHERE is_active = 1
        """)
        
        for row in cursor:
            source_id, folder_path = row
            
            # 检查路径是否存在
            if folder_path and not os.path.exists(folder_path):
                issue = IntegrityIssue(
                    issue_id=self._generate_issue_id(),
                    issue_type=IntegrityIssueType.INVALID_DATA,
                    table_name=table_name,
                    record_id=source_id,
                    column_name='folder_path',
                    description=f"内容源 {source_id} 的文件夹路径不存在: {folder_path}",
                    severity=3,
                    detected_at=datetime.now(),
                    repair_strategy=RepairStrategy.MANUAL_REVIEW,
                    metadata={'source_id': source_id, 'folder_path': folder_path}
                )
                issues.append(issue)
        
        return issues
    
    def _check_api_key_validity(self, conn: sqlite3.Connection, table_name: str,
                               schema: TableSchema) -> List[IntegrityIssue]:
        """检查API密钥有效性"""
        issues = []
        
        # 检查空的或无效的API密钥
        cursor = conn.execute("""
            SELECT id, key_name, key_value
            FROM api_keys
            WHERE is_active = 1
            AND (key_value IS NULL OR key_value = '' OR LENGTH(key_value) < 10)
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.INVALID_DATA,
                table_name=table_name,
                record_id=row[0],
                column_name='key_value',
                description=f"API密钥 {row[1]} (ID: {row[0]}) 无效或为空",
                severity=5,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.MANUAL_REVIEW,
                metadata={'key_id': row[0], 'key_name': row[1]}
            )
            issues.append(issue)
        
        return issues
    
    def _check_api_key_expiration(self, conn: sqlite3.Connection, table_name: str,
                                 schema: TableSchema) -> List[IntegrityIssue]:
        """检查API密钥过期"""
        issues = []
        
        # 检查过期的API密钥
        cursor = conn.execute("""
            SELECT id, key_name, expires_at
            FROM api_keys
            WHERE is_active = 1
            AND expires_at IS NOT NULL
            AND datetime(expires_at) < datetime('now')
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.INVALID_DATA,
                table_name=table_name,
                record_id=row[0],
                column_name='expires_at',
                description=f"API密钥 {row[1]} (ID: {row[0]}) 已过期",
                severity=4,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.AUTO_FIX,
                metadata={'key_id': row[0], 'key_name': row[1], 'expires_at': row[2]}
            )
            issues.append(issue)
        
        return issues
    
    def _check_analytics_gaps(self, conn: sqlite3.Connection, table_name: str,
                             schema: TableSchema) -> List[IntegrityIssue]:
        """检查分析数据间隙"""
        issues = []
        
        # 检查小时统计数据的连续性
        cursor = conn.execute("""
            SELECT 
                datetime(hour_timestamp) as hour,
                datetime(hour_timestamp, '+1 hour') as next_hour
            FROM analytics_hourly a1
            WHERE NOT EXISTS (
                SELECT 1 FROM analytics_hourly a2
                WHERE datetime(a2.hour_timestamp) = datetime(a1.hour_timestamp, '+1 hour')
            )
            AND datetime(hour_timestamp) < datetime('now', '-1 hour')
            ORDER BY hour_timestamp DESC
            LIMIT 10
        """)
        
        gaps = cursor.fetchall()
        if gaps:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.SEQUENCE_GAP,
                table_name=table_name,
                record_id=None,
                column_name='hour_timestamp',
                description=f"分析数据存在 {len(gaps)} 个时间间隙",
                severity=2,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.RECALCULATE,
                metadata={'gaps': [{'from': g[0], 'to': g[1]} for g in gaps[:5]]}
            )
            issues.append(issue)
        
        return issues
    
    def _check_analytics_consistency(self, conn: sqlite3.Connection, table_name: str,
                                   schema: TableSchema) -> List[IntegrityIssue]:
        """检查分析数据一致性"""
        issues = []
        
        # 检查负值统计
        cursor = conn.execute("""
            SELECT id, hour_timestamp, project_id
            FROM analytics_hourly
            WHERE tasks_completed < 0 
            OR tasks_failed < 0 
            OR total_engagement < 0
        """)
        
        for row in cursor:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.INVALID_DATA,
                table_name=table_name,
                record_id=row[0],
                column_name=None,
                description=f"分析记录 {row[0]} 包含负值统计数据",
                severity=3,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.RECALCULATE,
                metadata={'analytics_id': row[0], 'hour': row[1], 'project_id': row[2]}
            )
            issues.append(issue)
        
        return issues
    
    def _perform_generic_checks(self, conn: sqlite3.Connection, table_name: str,
                               schema: TableSchema) -> List[IntegrityIssue]:
        """执行通用检查"""
        issues = []
        
        # 检查NULL值在NOT NULL列中
        for column in schema.columns:
            if column.get('notnull') and column['name'] != 'id':
                cursor = conn.execute(f"""
                    SELECT id FROM {table_name} 
                    WHERE {column['name']} IS NULL
                    LIMIT 10
                """)
                
                null_records = cursor.fetchall()
                if null_records:
                    issue = IntegrityIssue(
                        issue_id=self._generate_issue_id(),
                        issue_type=IntegrityIssueType.CONSTRAINT_VIOLATION,
                        table_name=table_name,
                        record_id=None,
                        column_name=column['name'],
                        description=f"表 {table_name} 的列 {column['name']} 存在 {len(null_records)} 个NULL值",
                        severity=3,
                        detected_at=datetime.now(),
                        repair_strategy=RepairStrategy.DEFAULT_VALUE,
                        metadata={'record_ids': [r[0] for r in null_records]}
                    )
                    issues.append(issue)
        
        return issues
    
    def _perform_cross_table_checks(self, conn: sqlite3.Connection) -> List[IntegrityIssue]:
        """执行跨表检查"""
        issues = []
        
        # 检查孤立的任务（没有对应日志的已完成任务）
        cursor = conn.execute("""
            SELECT t.id
            FROM publishing_tasks t
            WHERE t.status = 'completed'
            AND NOT EXISTS (
                SELECT 1 FROM publishing_logs l
                WHERE l.task_id = t.id AND l.status = 'success'
            )
        """)
        
        orphan_tasks = cursor.fetchall()
        if orphan_tasks:
            issue = IntegrityIssue(
                issue_id=self._generate_issue_id(),
                issue_type=IntegrityIssueType.INCONSISTENT_STATE,
                table_name='publishing_tasks',
                record_id=None,
                column_name='status',
                description=f"发现 {len(orphan_tasks)} 个已完成但无成功日志的任务",
                severity=3,
                detected_at=datetime.now(),
                repair_strategy=RepairStrategy.AUTO_FIX,
                metadata={'task_ids': [t[0] for t in orphan_tasks[:10]]}
            )
            issues.append(issue)
        
        return issues
    
    def _attempt_auto_repair(self, issue: IntegrityIssue) -> bool:
        """尝试自动修复问题"""
        if not self.auto_repair:
            return False
        
        if issue.repair_strategy != RepairStrategy.AUTO_FIX:
            return False
        
        logger.info(f"🔍 尝试自动修复问题: {issue.issue_id}")
        
        # 备份数据
        if self.backup_before_repair:
            self._create_backup()
        
        # 根据问题类型选择修复策略
        if issue.issue_type in self.repair_strategies:
            repair_func = self.repair_strategies[issue.issue_type]
            
            try:
                success = repair_func(issue)
                
                # 记录修复结果
                issue.repair_attempted = True
                issue.repair_successful = success
                
                self._record_repair(issue, success)
                
                if success:
                    logger.info(f"🔍 成功修复问题: {issue.issue_id}")
                else:
                    logger.warning(f"🔍 修复失败: {issue.issue_id}")
                
                return success
                
            except Exception as e:
                logger.error(f"🔍 修复过程出错: {e}")
                issue.repair_error = str(e)
                return False
        
        return False
    
    def _repair_orphan_record(self, issue: IntegrityIssue) -> bool:
        """修复孤立记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if issue.repair_strategy == RepairStrategy.CASCADE_DELETE:
                    # 删除孤立记录
                    conn.execute(f"""
                        DELETE FROM {issue.table_name}
                        WHERE id = ?
                    """, (issue.record_id,))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"修复孤立记录失败: {e}")
        return False
    
    def _repair_missing_reference(self, issue: IntegrityIssue) -> bool:
        """修复缺失引用"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if issue.repair_strategy == RepairStrategy.CASCADE_DELETE:
                    # 删除引用无效的记录
                    conn.execute(f"""
                        DELETE FROM {issue.table_name}
                        WHERE id = ?
                    """, (issue.record_id,))
                    conn.commit()
                    return True
                elif issue.repair_strategy == RepairStrategy.DEFAULT_VALUE:
                    # 设置为NULL或默认值
                    conn.execute(f"""
                        UPDATE {issue.table_name}
                        SET {issue.column_name} = NULL
                        WHERE id = ?
                    """, (issue.record_id,))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"修复缺失引用失败: {e}")
        return False
    
    def _repair_duplicate_data(self, issue: IntegrityIssue) -> bool:
        """修复重复数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if 'task_ids' in issue.metadata:
                    # 保留最新的，删除其他的
                    task_ids = issue.metadata['task_ids']
                    if len(task_ids) > 1:
                        # 保留第一个
                        tasks_to_delete = task_ids[1:]
                        placeholders = ','.join(['?'] * len(tasks_to_delete))
                        conn.execute(f"""
                            DELETE FROM {issue.table_name}
                            WHERE id IN ({placeholders})
                        """, tasks_to_delete)
                        conn.commit()
                        return True
        except Exception as e:
            logger.error(f"修复重复数据失败: {e}")
        return False
    
    def _repair_inconsistent_state(self, issue: IntegrityIssue) -> bool:
        """修复不一致状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if issue.column_name == 'status':
                    # 重置为pending状态
                    conn.execute(f"""
                        UPDATE {issue.table_name}
                        SET status = 'pending', updated_at = datetime('now')
                        WHERE id = ?
                    """, (issue.record_id,))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"修复不一致状态失败: {e}")
        return False
    
    def _repair_invalid_data(self, issue: IntegrityIssue) -> bool:
        """修复无效数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if issue.repair_strategy == RepairStrategy.DEFAULT_VALUE:
                    # 根据列类型设置默认值
                    default_values = {
                        'status': 'pending',
                        'priority': 1,
                        'retry_count': 0,
                        'is_active': 1
                    }
                    
                    default_value = default_values.get(issue.column_name, '')
                    
                    conn.execute(f"""
                        UPDATE {issue.table_name}
                        SET {issue.column_name} = ?
                        WHERE id = ?
                    """, (default_value, issue.record_id))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"修复无效数据失败: {e}")
        return False
    
    def _repair_corrupted_data(self, issue: IntegrityIssue) -> bool:
        """修复损坏数据"""
        # 通常需要从备份恢复
        logger.warning(f"损坏数据需要从备份恢复: {issue}")
        return False
    
    def _repair_constraint_violation(self, issue: IntegrityIssue) -> bool:
        """修复约束违反"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if issue.column_name and issue.repair_strategy == RepairStrategy.DEFAULT_VALUE:
                    # 设置为NULL或默认值
                    conn.execute(f"""
                        UPDATE {issue.table_name}
                        SET {issue.column_name} = NULL
                        WHERE id = ?
                    """, (issue.record_id,))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"修复约束违反失败: {e}")
        return False
    
    def _repair_schema_mismatch(self, issue: IntegrityIssue) -> bool:
        """修复模式不匹配"""
        # 通常需要数据库迁移
        logger.warning(f"模式不匹配需要数据库迁移: {issue}")
        return False
    
    def _repair_sequence_gap(self, issue: IntegrityIssue) -> bool:
        """修复序列间隙"""
        # 序列间隙通常可以忽略
        if issue.repair_strategy == RepairStrategy.IGNORE:
            return True
        return False
    
    def _repair_timestamp_anomaly(self, issue: IntegrityIssue) -> bool:
        """修复时间戳异常"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if 'created_at' in issue.metadata and 'updated_at' in issue.metadata:
                    # 修正更新时间
                    conn.execute(f"""
                        UPDATE {issue.table_name}
                        SET updated_at = created_at
                        WHERE id = ?
                    """, (issue.record_id,))
                    conn.commit()
                    return True
                elif issue.column_name == 'created_at':
                    # 修正未来时间戳
                    conn.execute(f"""
                        UPDATE {issue.table_name}
                        SET created_at = datetime('now')
                        WHERE id = ?
                    """, (issue.record_id,))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"修复时间戳异常失败: {e}")
        return False
    
    def _create_backup(self):
        """创建数据库备份"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.dirname(self.db_path)
            backup_path = os.path.join(backup_dir, f"backup_{timestamp}.db")
            
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"🔍 创建数据库备份: {backup_path}")
            
            # 清理旧备份（保留最近10个）
            self._cleanup_old_backups(backup_dir)
            
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
    
    def _cleanup_old_backups(self, backup_dir: str):
        """清理旧备份"""
        try:
            backup_files = [
                f for f in os.listdir(backup_dir)
                if f.startswith('backup_') and f.endswith('.db')
            ]
            
            if len(backup_files) > 10:
                backup_files.sort()
                for old_backup in backup_files[:-10]:
                    os.remove(os.path.join(backup_dir, old_backup))
                    logger.debug(f"删除旧备份: {old_backup}")
                    
        except Exception as e:
            logger.error(f"清理旧备份失败: {e}")
    
    def _generate_recommendations(self, issues: List[IntegrityIssue]) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # 统计问题类型
        issue_types = defaultdict(int)
        severity_counts = defaultdict(int)
        
        for issue in issues:
            issue_types[issue.issue_type] += 1
            severity_counts[issue.severity] += 1
        
        # 根据问题类型生成建议
        if issue_types[IntegrityIssueType.MISSING_REFERENCE] > 0:
            recommendations.append("建议启用外键约束以防止引用完整性问题")
        
        if issue_types[IntegrityIssueType.DUPLICATE_DATA] > 0:
            recommendations.append("建议添加唯一索引以防止数据重复")
        
        if issue_types[IntegrityIssueType.TIMESTAMP_ANOMALY] > 0:
            recommendations.append("建议使用触发器自动维护时间戳字段")
        
        if issue_types[IntegrityIssueType.ORPHAN_RECORD] > 0:
            recommendations.append("建议定期清理孤立记录")
        
        # 根据严重性生成建议
        if severity_counts[5] > 0:
            recommendations.append("发现严重问题，建议立即进行人工审查")
        
        if severity_counts[4] > 5:
            recommendations.append("发现多个高严重性问题，建议进行全面的数据审计")
        
        # 通用建议
        if len(issues) > 50:
            recommendations.append("问题数量较多，建议增加检查频率")
        
        if self.statistics['failed_repairs'] > 10:
            recommendations.append("修复失败率较高，建议检查修复策略配置")
        
        return recommendations
    
    def _record_repair(self, issue: IntegrityIssue, success: bool):
        """记录修复操作"""
        repair_record = {
            'issue_id': issue.issue_id,
            'issue_type': issue.issue_type.value,
            'repair_time': datetime.now().isoformat(),
            'success': success,
            'repair_strategy': issue.repair_strategy.value,
            'metadata': issue.metadata
        }
        
        self.repair_history.append(repair_record)
        
        # 更新统计
        if success:
            self.statistics['auto_fixed'] += 1
        else:
            self.statistics['failed_repairs'] += 1
    
    def _update_statistics(self, report: IntegrityReport):
        """更新统计信息"""
        self.statistics['total_checks'] += 1
        self.statistics['total_issues'] += len(report.issues_found)
        
        # 更新平均检查时长
        current_avg = self.statistics['check_duration_avg']
        new_avg = (current_avg * (self.statistics['total_checks'] - 1) + 
                  report.duration_seconds) / self.statistics['total_checks']
        self.statistics['check_duration_avg'] = new_avg
    
    def _log_report(self, report: IntegrityReport):
        """记录检查报告"""
        logger.info("🔍 数据完整性检查报告:")
        logger.info(f"  - 检查ID: {report.check_id}")
        logger.info(f"  - 检查时间: {report.check_time}")
        logger.info(f"  - 耗时: {report.duration_seconds:.2f}秒")
        logger.info(f"  - 检查表数: {report.tables_checked}")
        logger.info(f"  - 检查记录数: {report.records_checked}")
        logger.info(f"  - 发现问题: {len(report.issues_found)}")
        logger.info(f"  - 自动修复: {report.auto_fixed}")
        logger.info(f"  - 需要人工: {report.manual_required}")
        logger.info(f"  - 严重问题: {report.critical_issues}")
        
        if report.recommendations:
            logger.info("  建议:")
            for rec in report.recommendations:
                logger.info(f"    - {rec}")
    
    def _generate_check_id(self) -> str:
        """生成检查ID"""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(f"check_{timestamp}".encode()).hexdigest()[:12]
    
    def _generate_issue_id(self) -> str:
        """生成问题ID"""
        timestamp = datetime.now().isoformat()
        random_str = str(time.time())
        return hashlib.md5(f"issue_{timestamp}_{random_str}".encode()).hexdigest()[:16]
    
    def start_monitoring(self):
        """启动监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("🔍 数据完整性监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("🔍 数据完整性监控已停止")
    
    def _monitoring_loop(self):
        """监控循环"""
        logger.info("🔍 数据完整性监控循环启动")
        
        while self.monitoring:
            try:
                # 执行定期检查
                if self._should_perform_check():
                    report = self.perform_full_check()
                    
                    # 如果发现严重问题，发送警报
                    if report.critical_issues > 0:
                        self._send_alert(report)
                
                time.sleep(60)  # 每分钟检查一次是否需要执行
                
            except Exception as e:
                logger.error(f"🔍 监控循环异常: {e}")
                time.sleep(60)
        
        logger.info("🔍 数据完整性监控循环结束")
    
    def _should_perform_check(self) -> bool:
        """判断是否应该执行检查"""
        if not self.last_check_time:
            return True
        
        elapsed = (datetime.now() - self.last_check_time).total_seconds()
        return elapsed >= self.check_interval
    
    def _send_alert(self, report: IntegrityReport):
        """发送警报"""
        logger.warning(f"🚨 数据完整性警报: 发现 {report.critical_issues} 个严重问题!")
        
        # 这里可以集成邮件、Slack等通知机制
        
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_checks': self.statistics['total_checks'],
            'total_issues': self.statistics['total_issues'],
            'auto_fixed': self.statistics['auto_fixed'],
            'manual_required': self.statistics['manual_required'],
            'failed_repairs': self.statistics['failed_repairs'],
            'check_duration_avg': self.statistics['check_duration_avg'],
            'active_issues': len(self.active_issues),
            'monitoring': self.monitoring,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None
        }

# 全局实例
_data_integrity_checker: Optional[DataIntegrityChecker] = None

def get_data_integrity_checker(db_path: str = "./data/twitter_publisher.db") -> DataIntegrityChecker:
    """获取数据完整性检查器实例"""
    global _data_integrity_checker
    
    if _data_integrity_checker is None:
        _data_integrity_checker = DataIntegrityChecker(db_path)
    
    return _data_integrity_checker

def perform_integrity_check(auto_repair: bool = True) -> IntegrityReport:
    """
    便捷函数：执行完整性检查
    
    Args:
        auto_repair: 是否自动修复
        
    Returns:
        IntegrityReport: 检查报告
    """
    checker = get_data_integrity_checker()
    checker.auto_repair = auto_repair
    return checker.perform_full_check()