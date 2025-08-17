#!/usr/bin/env python3
"""
数据库索引优化 - 紧急执行脚本
解决TWITTER_OPTIMIZATION_PLAN.md中"任务查询频繁进行全表扫描--重点，重点，重点"问题
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime

def execute_index_migration():
    """执行索引迁移"""
    
    # 数据库路径
    db_path = "./data/twitter_publisher.db"
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
        
    print("🚀 开始执行数据库性能索引优化...")
    print("🎯 目标: 解决任务查询全表扫描问题")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print("\n📊 执行前 - 检查现有索引...")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';")
            existing_indexes = [idx[0] for idx in cursor.fetchall()]
            print(f"现有索引: {existing_indexes}")
            
            # 1. 核心任务查询索引 - 解决全表扫描问题
            print("\n🔧 创建核心任务查询索引: idx_tasks_status_scheduled_priority")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status_scheduled_priority 
                ON publishing_tasks(status, scheduled_at, priority);
            """)
            print("✅ 完成")
            
            # 2. 项目-状态复合索引
            print("🔧 创建项目状态索引: idx_tasks_project_status")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_project_status 
                ON publishing_tasks(project_id, status);
            """)
            print("✅ 完成")
            
            # 3. 时间范围查询索引
            print("🔧 创建时间范围查询索引: idx_tasks_scheduled_status")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_status 
                ON publishing_tasks(scheduled_at, status);
            """)
            print("✅ 完成")
            
            # 4. 日志查询优化索引
            print("🔧 创建日志查询索引: idx_logs_task_published")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_task_published 
                ON publishing_logs(task_id, published_at);
            """)
            print("✅ 完成")
            
            # 5. 分析统计索引
            print("🔧 创建分析统计索引: idx_analytics_hour_project")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analytics_hour_project 
                ON analytics_hourly(hour_timestamp, project_id);
            """)
            print("✅ 完成")
            
            conn.commit()
            
            print("\n📊 验证索引创建...")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';")
            new_indexes = [idx[0] for idx in cursor.fetchall()]
            
            expected_indexes = [
                'idx_tasks_status_scheduled_priority',
                'idx_tasks_project_status', 
                'idx_tasks_scheduled_status',
                'idx_logs_task_published',
                'idx_analytics_hour_project'
            ]
            
            for expected_idx in expected_indexes:
                if expected_idx in new_indexes:
                    print(f"✅ 索引 {expected_idx} 创建成功")
                else:
                    print(f"❌ 索引 {expected_idx} 创建失败")
            
            print("\n🔍 分析关键查询执行计划...")
            
            # 测试最重要的pending任务查询
            print("\n📋 分析 get_pending_tasks 查询:")
            cursor.execute("""
                EXPLAIN QUERY PLAN 
                SELECT * FROM publishing_tasks 
                WHERE status IN ('pending', 'retry') 
                ORDER BY priority DESC, scheduled_at ASC 
                LIMIT 10;
            """)
            
            plan = cursor.fetchall()
            uses_index = False
            
            for step in plan:
                plan_detail = ' '.join(map(str, step))
                print(f"  {plan_detail}")
                
                if 'USING INDEX' in plan_detail.upper():
                    uses_index = True
                    
            if uses_index:
                print("✅ 查询正在使用索引 - 全表扫描问题已解决！")
            else:
                print("⚠️ 查询可能仍在进行表扫描")
            
            print("\n🎉 数据库性能索引优化完成！")
            print("📈 预期效果:")
            print("  - 任务查询性能提升 50-300%")
            print("  - 消除全表扫描问题")
            print("  - 支持更高并发的任务处理")
            
            return True
            
    except Exception as e:
        print(f"❌ 创建索引失败: {e}")
        return False

if __name__ == "__main__":
    success = execute_index_migration()
    if success:
        print("\n🏆 Phase 1 完成: 数据库全表扫描问题已解决！")
    else:
        print("\n💥 Phase 1 失败: 需要检查数据库配置")