#!/usr/bin/env python3
"""
启用SQLite WAL模式 - 提升并发性能
根据TWITTER_OPTIMIZATION_PLAN.md数据库引擎升级要求
"""

import sqlite3
import os

def enable_wal_mode():
    """启用WAL模式提升并发性能"""
    
    db_path = "./data/twitter_publisher.db"
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    print("🚀 启用SQLite WAL模式...")
    print("🎯 目标: 提升数据库并发性能，支持更多工作线程")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 检查当前journal模式
            cursor.execute("PRAGMA journal_mode;")
            current_mode = cursor.fetchone()[0]
            print(f"📊 当前journal模式: {current_mode}")
            
            if current_mode.upper() == 'WAL':
                print("✅ WAL模式已启用")
                return True
            
            # 启用WAL模式
            print("🔧 启用WAL模式...")
            cursor.execute("PRAGMA journal_mode=WAL;")
            new_mode = cursor.fetchone()[0]
            
            if new_mode.upper() == 'WAL':
                print("✅ WAL模式启用成功")
                
                # 设置其他WAL相关优化
                print("🔧 配置WAL优化参数...")
                
                # 同步模式为NORMAL，平衡性能和安全性
                cursor.execute("PRAGMA synchronous=NORMAL;")
                print("✅ 设置同步模式为NORMAL")
                
                # 设置WAL自动检查点
                cursor.execute("PRAGMA wal_autocheckpoint=1000;")
                print("✅ 设置WAL自动检查点为1000页")
                
                # 设置缓存大小
                cursor.execute("PRAGMA cache_size=10000;")
                print("✅ 设置缓存大小为10000页")
                
                # 启用内存映射
                cursor.execute("PRAGMA mmap_size=268435456;")  # 256MB
                print("✅ 启用内存映射(256MB)")
                
                conn.commit()
                
                print("\n🎉 数据库WAL模式配置完成！")
                print("📈 预期效果:")
                print("  - 读写并发性能大幅提升")
                print("  - 支持5个工作线程同时操作")
                print("  - 减少数据库锁竞争")
                
                return True
            else:
                print(f"❌ WAL模式启用失败，当前模式: {new_mode}")
                return False
                
    except Exception as e:
        print(f"❌ 启用WAL模式失败: {e}")
        return False

def check_wal_status():
    """检查WAL模式状态"""
    db_path = "./data/twitter_publisher.db"
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print("\n📊 数据库配置状态:")
            
            # 检查journal模式
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            print(f"  Journal模式: {journal_mode}")
            
            # 检查同步模式
            cursor.execute("PRAGMA synchronous;")
            sync_mode = cursor.fetchone()[0]
            sync_names = {0: 'OFF', 1: 'NORMAL', 2: 'FULL', 3: 'EXTRA'}
            print(f"  同步模式: {sync_names.get(sync_mode, sync_mode)}")
            
            # 检查缓存大小
            cursor.execute("PRAGMA cache_size;")
            cache_size = cursor.fetchone()[0]
            print(f"  缓存大小: {cache_size}页")
            
            # 检查WAL自动检查点
            cursor.execute("PRAGMA wal_autocheckpoint;")
            wal_checkpoint = cursor.fetchone()[0]
            print(f"  WAL检查点: {wal_checkpoint}页")
            
            return True
            
    except Exception as e:
        print(f"❌ 检查数据库状态失败: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Phase 2: 数据库并发性能优化")
    
    success = enable_wal_mode()
    
    if success:
        check_wal_status()
        print("\n🏆 Phase 2 完成: 数据库并发性能已优化！")
    else:
        print("\n💥 Phase 2 失败: WAL模式启用失败")