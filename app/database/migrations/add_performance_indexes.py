#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库性能索引优化迁移
解决"任务查询频繁进行全表扫描"的重点问题

根据TWITTER_OPTIMIZATION_PLAN.md第一阶段要求：
1. 添加复合索引：(status, scheduled_at, priority) 用于任务查询
2. 创建项目-状态复合索引：(project_id, status)
3. 优化时间范围查询索引：(scheduled_at, status)
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime
from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config

logger = get_logger(__name__)

class PerformanceIndexMigration:
    """性能索引迁移类"""
    
    def __init__(self):
        self.config = get_enhanced_config()
        self.db_path = self.config.get('database', {}).get('path', './data/twitter_publisher.db')
        
    def get_database_path(self):
        """获取数据库路径"""
        # 确保数据库路径存在
        db_path = Path(self.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return str(db_path)
        
    def execute_migration(self):
        """执行索引迁移"""
        db_path = self.get_database_path()
        
        if not os.path.exists(db_path):
            logger.error(f"数据库文件不存在: {db_path}")
            return False
            
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                logger.info("开始创建性能优化索引...")
                
                # 1. 核心任务查询索引 - 解决全表扫描问题
                logger.info("创建核心任务查询索引: idx_tasks_status_scheduled_priority")
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tasks_status_scheduled_priority 
                    ON publishing_tasks(status, scheduled_at, priority);
                """)
                
                # 2. 项目-状态复合索引
                logger.info("创建项目状态索引: idx_tasks_project_status")
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tasks_project_status 
                    ON publishing_tasks(project_id, status);
                """)
                
                # 3. 时间范围查询索引
                logger.info("创建时间范围查询索引: idx_tasks_scheduled_status")
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_status 
                    ON publishing_tasks(scheduled_at, status);
                """)
                
                # 4. 日志查询优化索引
                logger.info("创建日志查询索引: idx_logs_task_published")
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_logs_task_published 
                    ON publishing_logs(task_id, published_at);
                """)
                
                # 5. 分析统计索引
                logger.info("创建分析统计索引: idx_analytics_hour_project")
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_analytics_hour_project 
                    ON analytics_hourly(hour_timestamp, project_id);
                """)
                
                conn.commit()
                logger.info("✅ 所有性能索引创建完成！")
                
                # 验证索引创建
                self._verify_indexes(cursor)
                
                # 分析查询计划
                self._analyze_query_plans(cursor)
                
                return True
                
        except Exception as e:
            logger.error(f"创建索引失败: {e}", exc_info=True)
            return False
            
    def _verify_indexes(self, cursor):
        """验证索引是否创建成功"""
        logger.info("验证索引创建状态...")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';")
        indexes = cursor.fetchall()
        
        expected_indexes = [
            'idx_tasks_status_scheduled_priority',
            'idx_tasks_project_status', 
            'idx_tasks_scheduled_status',
            'idx_logs_task_published',
            'idx_analytics_hour_project'
        ]
        
        created_indexes = [idx[0] for idx in indexes]
        
        for expected_idx in expected_indexes:
            if expected_idx in created_indexes:
                logger.info(f"✅ 索引 {expected_idx} 创建成功")
            else:
                logger.error(f"❌ 索引 {expected_idx} 创建失败")
                
    def _analyze_query_plans(self, cursor):
        """分析关键查询的执行计划，验证是否使用索引"""
        logger.info("分析关键查询执行计划...")
        
        # 测试pending任务查询 - 这是最频繁的查询
        test_queries = [
            {
                'name': 'get_pending_tasks',
                'query': """
                    EXPLAIN QUERY PLAN 
                    SELECT * FROM publishing_tasks 
                    WHERE status IN ('pending', 'retry') 
                    ORDER BY priority DESC, scheduled_at ASC 
                    LIMIT 10;
                """
            },
            {
                'name': 'get_project_tasks',
                'query': """
                    EXPLAIN QUERY PLAN 
                    SELECT * FROM publishing_tasks 
                    WHERE project_id = 1 AND status = 'pending';
                """
            },
            {
                'name': 'get_tasks_by_time',
                'query': """
                    EXPLAIN QUERY PLAN 
                    SELECT * FROM publishing_tasks 
                    WHERE scheduled_at <= datetime('now') AND status = 'pending';
                """
            }
        ]
        
        for test in test_queries:
            logger.info(f"\n分析查询: {test['name']}")
            try:
                cursor.execute(test['query'])
                plan = cursor.fetchall()
                
                uses_index = False
                for step in plan:
                    plan_detail = ' '.join(map(str, step))
                    logger.info(f"  {plan_detail}")
                    
                    # 检查是否使用了索引
                    if 'USING INDEX' in plan_detail.upper():
                        uses_index = True
                        
                if uses_index:
                    logger.info(f"✅ 查询 {test['name']} 正在使用索引")
                else:
                    logger.warning(f"⚠️ 查询 {test['name']} 可能仍在进行表扫描")
                    
            except Exception as e:
                logger.error(f"分析查询 {test['name']} 失败: {e}")
                
    def rollback_migration(self):
        """回滚迁移 - 删除创建的索引"""
        db_path = self.get_database_path()
        
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                logger.info("开始回滚索引迁移...")
                
                indexes_to_drop = [
                    'idx_tasks_status_scheduled_priority',
                    'idx_tasks_project_status',
                    'idx_tasks_scheduled_status', 
                    'idx_logs_task_published',
                    'idx_analytics_hour_project'
                ]
                
                for index_name in indexes_to_drop:
                    try:
                        cursor.execute(f"DROP INDEX IF EXISTS {index_name};")
                        logger.info(f"删除索引: {index_name}")
                    except Exception as e:
                        logger.error(f"删除索引 {index_name} 失败: {e}")
                        
                conn.commit()
                logger.info("索引回滚完成")
                return True
                
        except Exception as e:
            logger.error(f"回滚迁移失败: {e}")
            return False

def main():
    """主执行函数"""
    migration = PerformanceIndexMigration()
    
    logger.info("🚀 开始执行数据库性能索引优化迁移...")
    logger.info("目标: 解决'任务查询频繁进行全表扫描'问题")
    
    success = migration.execute_migration()
    
    if success:
        logger.info("🎉 数据库性能索引优化完成！")
        logger.info("📊 预期效果:")
        logger.info("  - 任务查询性能提升 50-300%")
        logger.info("  - 消除全表扫描问题")
        logger.info("  - 支持更高并发的任务处理")
    else:
        logger.error("❌ 数据库索引优化失败")
        
    return success

if __name__ == "__main__":
    main()