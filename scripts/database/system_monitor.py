#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统监控器 - 实时监控Twitter发布系统的运行状态
提供系统健康检查、性能监控和实时状态显示
"""

import os
import sys
import sqlite3
import json
import psutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum

class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

@dataclass
class SystemMetrics:
    """系统指标"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    process_count: int
    uptime: timedelta
    load_average: Tuple[float, float, float]
    
@dataclass
class DatabaseMetrics:
    """数据库指标"""
    file_size: int
    table_count: int
    total_tasks: int
    pending_tasks: int
    completed_tasks: int
    failed_tasks: int
    recent_activity: int
    
@dataclass
class ProcessInfo:
    """进程信息"""
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_percent: float
    create_time: datetime
    cmdline: List[str]
    
    @property
    def uptime(self) -> timedelta:
        """进程运行时间"""
        return datetime.now() - self.create_time

class SystemMonitor:
    """系统监控器"""
    
    def __init__(self, db_path: str = 'data/twitter_publisher.db'):
        self.db_path = db_path
        self.start_time = datetime.now()
    
    def get_system_metrics(self) -> SystemMetrics:
        """获取系统指标"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            process_count = len(psutil.pids())
            
            # 系统启动时间
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            # 负载平均值 (仅在Unix系统上可用)
            try:
                load_avg = os.getloadavg()
            except (OSError, AttributeError):
                load_avg = (0.0, 0.0, 0.0)
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_percent=disk.percent,
                process_count=process_count,
                uptime=uptime,
                load_average=load_avg
            )
        except Exception as e:
            print(f"❌ 获取系统指标失败: {e}")
            return SystemMetrics(0, 0, 0, 0, timedelta(), (0, 0, 0))
    
    def get_database_metrics(self) -> Optional[DatabaseMetrics]:
        """获取数据库指标"""
        if not os.path.exists(self.db_path):
            return None
        
        try:
            # 文件大小
            file_size = os.path.getsize(self.db_path)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 表数量
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            # 任务统计
            cursor.execute("SELECT COUNT(*) FROM publishing_tasks")
            total_tasks = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE status = 'pending'")
            pending_tasks = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE status = 'completed'")
            completed_tasks = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM publishing_tasks WHERE status = 'failed'")
            failed_tasks = cursor.fetchone()[0]
            
            # 最近24小时活动
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()
            cursor.execute(
                "SELECT COUNT(*) FROM publishing_logs WHERE published_at > ?",
                (yesterday,)
            )
            recent_activity = cursor.fetchone()[0]
            
            conn.close()
            
            return DatabaseMetrics(
                file_size=file_size,
                table_count=table_count,
                total_tasks=total_tasks,
                pending_tasks=pending_tasks,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                recent_activity=recent_activity
            )
            
        except Exception as e:
            print(f"❌ 获取数据库指标失败: {e}")
            return None
    
    def find_related_processes(self) -> List[ProcessInfo]:
        """查找相关进程"""
        processes = []
        keywords = ['python', 'twitter', 'publisher', 'scheduler', 'main.py', 'api.py']
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 
                                           'memory_percent', 'create_time', 'cmdline']):
                try:
                    proc_info = proc.info
                    cmdline = ' '.join(proc_info.get('cmdline', []))
                    
                    # 检查是否为相关进程
                    is_related = False
                    for keyword in keywords:
                        if keyword.lower() in cmdline.lower() or keyword.lower() in proc_info['name'].lower():
                            is_related = True
                            break
                    
                    if is_related:
                        process_info = ProcessInfo(
                            pid=proc_info['pid'],
                            name=proc_info['name'],
                            status=proc_info['status'],
                            cpu_percent=proc_info.get('cpu_percent', 0.0),
                            memory_percent=proc_info.get('memory_percent', 0.0),
                            create_time=datetime.fromtimestamp(proc_info['create_time']),
                            cmdline=proc_info.get('cmdline', [])
                        )
                        processes.append(process_info)
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
        except Exception as e:
            print(f"❌ 查找进程失败: {e}")
        
        return processes
    
    def check_system_health(self) -> Tuple[HealthStatus, List[str]]:
        """检查系统健康状态"""
        issues = []
        status = HealthStatus.HEALTHY
        
        try:
            # 检查系统资源
            metrics = self.get_system_metrics()
            
            if metrics.cpu_percent > 90:
                issues.append(f"CPU使用率过高: {metrics.cpu_percent:.1f}%")
                status = HealthStatus.CRITICAL
            elif metrics.cpu_percent > 70:
                issues.append(f"CPU使用率较高: {metrics.cpu_percent:.1f}%")
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
            
            if metrics.memory_percent > 90:
                issues.append(f"内存使用率过高: {metrics.memory_percent:.1f}%")
                status = HealthStatus.CRITICAL
            elif metrics.memory_percent > 80:
                issues.append(f"内存使用率较高: {metrics.memory_percent:.1f}%")
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
            
            if metrics.disk_percent > 95:
                issues.append(f"磁盘空间不足: {metrics.disk_percent:.1f}%")
                status = HealthStatus.CRITICAL
            elif metrics.disk_percent > 85:
                issues.append(f"磁盘空间较少: {metrics.disk_percent:.1f}%")
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
            
            # 检查数据库
            if not os.path.exists(self.db_path):
                issues.append("数据库文件不存在")
                status = HealthStatus.CRITICAL
            else:
                db_metrics = self.get_database_metrics()
                if db_metrics:
                    if db_metrics.failed_tasks > db_metrics.completed_tasks * 0.1:
                        issues.append(f"失败任务比例过高: {db_metrics.failed_tasks}/{db_metrics.total_tasks}")
                        if status == HealthStatus.HEALTHY:
                            status = HealthStatus.WARNING
                    
                    if db_metrics.recent_activity == 0 and db_metrics.pending_tasks > 0:
                        issues.append("系统可能已停止工作 (有待处理任务但无最近活动)")
                        status = HealthStatus.CRITICAL
            
            # 检查相关进程
            processes = self.find_related_processes()
            if not processes:
                issues.append("未找到相关运行进程")
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
            
            # 检查配置文件
            config_files = ['enhanced_config.yaml', 'config.yaml']
            config_exists = any(os.path.exists(f) for f in config_files)
            if not config_exists:
                issues.append("配置文件不存在")
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
            
        except Exception as e:
            issues.append(f"健康检查失败: {e}")
            status = HealthStatus.UNKNOWN
        
        return status, issues
    
    def show_dashboard(self, refresh_interval: int = 0):
        """显示系统仪表板"""
        try:
            while True:
                # 清屏 (仅在终端中)
                if refresh_interval > 0:
                    os.system('clear' if os.name == 'posix' else 'cls')
                
                print("🖥️  Twitter发布系统监控仪表板")
                print("=" * 60)
                print(f"📅 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 系统健康状态
                health_status, issues = self.check_system_health()
                status_icons = {
                    HealthStatus.HEALTHY: "✅",
                    HealthStatus.WARNING: "⚠️",
                    HealthStatus.CRITICAL: "❌",
                    HealthStatus.UNKNOWN: "❓"
                }
                
                print(f"\n🏥 系统健康: {status_icons[health_status]} {health_status.value.upper()}")
                if issues:
                    for issue in issues:
                        print(f"  ⚠️  {issue}")
                
                # 系统指标
                metrics = self.get_system_metrics()
                print(f"\n📊 系统指标")
                print(f"  🖥️  CPU: {metrics.cpu_percent:.1f}%")
                print(f"  🧠 内存: {metrics.memory_percent:.1f}%")
                print(f"  💾 磁盘: {metrics.disk_percent:.1f}%")
                print(f"  📈 负载: {metrics.load_average[0]:.2f}, {metrics.load_average[1]:.2f}, {metrics.load_average[2]:.2f}")
                print(f"  ⏱️  系统运行时间: {metrics.uptime}")
                print(f"  🔢 进程数: {metrics.process_count}")
                
                # 数据库指标
                db_metrics = self.get_database_metrics()
                if db_metrics:
                    print(f"\n🗄️  数据库指标")
                    print(f"  📁 文件大小: {db_metrics.file_size:,} 字节 ({db_metrics.file_size/1024/1024:.2f} MB)")
                    print(f"  📋 表数量: {db_metrics.table_count}")
                    print(f"  📝 总任务: {db_metrics.total_tasks}")
                    print(f"  ⏳ 待处理: {db_metrics.pending_tasks}")
                    print(f"  ✅ 已完成: {db_metrics.completed_tasks}")
                    print(f"  ❌ 失败: {db_metrics.failed_tasks}")
                    print(f"  🔄 24h活动: {db_metrics.recent_activity}")
                    
                    if db_metrics.total_tasks > 0:
                        success_rate = (db_metrics.completed_tasks / db_metrics.total_tasks) * 100
                        print(f"  📈 成功率: {success_rate:.1f}%")
                else:
                    print(f"\n🗄️  数据库: ❌ 无法访问")
                
                # 相关进程
                processes = self.find_related_processes()
                print(f"\n🔄 相关进程 ({len(processes)}个)")
                if processes:
                    for proc in processes[:5]:  # 只显示前5个
                        print(f"  📍 PID {proc.pid}: {proc.name} ({proc.status})")
                        print(f"     CPU: {proc.cpu_percent:.1f}% | 内存: {proc.memory_percent:.1f}% | 运行时间: {proc.uptime}")
                        if proc.cmdline:
                            cmd = ' '.join(proc.cmdline)
                            if len(cmd) > 60:
                                cmd = cmd[:60] + "..."
                            print(f"     命令: {cmd}")
                else:
                    print(f"  ❌ 未找到相关进程")
                
                # 最近日志
                self._show_recent_logs(5)
                
                if refresh_interval <= 0:
                    break
                
                print(f"\n🔄 {refresh_interval}秒后自动刷新... (按 Ctrl+C 退出)")
                time.sleep(refresh_interval)
                
        except KeyboardInterrupt:
            print("\n👋 监控已停止")
    
    def _show_recent_logs(self, limit: int = 5):
        """显示最近日志"""
        try:
            if not os.path.exists(self.db_path):
                return
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT published_at, status, task_id, tweet_id, error_message
                FROM publishing_logs 
                ORDER BY published_at DESC 
                LIMIT ?
            """, (limit,))
            
            logs = cursor.fetchall()
            
            if logs:
                print(f"\n📋 最近日志 ({len(logs)}条)")
                for log in logs:
                    published_at, status, task_id, tweet_id, error_message = log
                    status_icon = "✅" if status == "success" else "❌"
                    print(f"  {status_icon} {published_at}: 任务{task_id} - {status}")
                    if tweet_id:
                        print(f"     推文ID: {tweet_id}")
                    if error_message:
                        error_short = error_message[:50] + "..." if len(error_message) > 50 else error_message
                        print(f"     错误: {error_short}")
            
            conn.close()
            
        except Exception as e:
            print(f"\n📋 最近日志: ❌ 获取失败 ({e})")
    
    def show_process_details(self):
        """显示进程详细信息"""
        processes = self.find_related_processes()
        
        print(f"\n🔄 相关进程详细信息")
        print("=" * 80)
        
        if not processes:
            print("❌ 未找到相关进程")
            return
        
        for i, proc in enumerate(processes, 1):
            print(f"\n{i}. 进程 {proc.pid} - {proc.name}")
            print(f"   状态: {proc.status}")
            print(f"   CPU: {proc.cpu_percent:.1f}%")
            print(f"   内存: {proc.memory_percent:.1f}%")
            print(f"   启动时间: {proc.create_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   运行时间: {proc.uptime}")
            
            if proc.cmdline:
                print(f"   命令行: {' '.join(proc.cmdline)}")
            
            # 获取更多进程信息
            try:
                process = psutil.Process(proc.pid)
                print(f"   工作目录: {process.cwd()}")
                print(f"   打开文件数: {len(process.open_files())}")
                print(f"   网络连接数: {len(process.connections())}")
                
                # 内存详情
                memory_info = process.memory_info()
                print(f"   内存详情: RSS={memory_info.rss:,} VMS={memory_info.vms:,}")
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print(f"   ⚠️  无法获取详细信息")
            
            print("-" * 60)
    
    def show_performance_report(self):
        """显示性能报告"""
        print(f"\n📈 系统性能报告")
        print("=" * 60)
        print(f"📅 报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 系统指标
        metrics = self.get_system_metrics()
        print(f"\n🖥️  系统资源使用")
        print(f"  CPU使用率: {metrics.cpu_percent:.1f}%")
        print(f"  内存使用率: {metrics.memory_percent:.1f}%")
        print(f"  磁盘使用率: {metrics.disk_percent:.1f}%")
        print(f"  系统负载: {metrics.load_average[0]:.2f} (1分钟)")
        print(f"  系统运行时间: {metrics.uptime}")
        
        # 数据库性能
        db_metrics = self.get_database_metrics()
        if db_metrics:
            print(f"\n🗄️  数据库性能")
            print(f"  数据库大小: {db_metrics.file_size/1024/1024:.2f} MB")
            print(f"  任务处理效率: {db_metrics.completed_tasks}/{db_metrics.total_tasks} ({(db_metrics.completed_tasks/db_metrics.total_tasks*100):.1f}%)")
            print(f"  失败率: {db_metrics.failed_tasks}/{db_metrics.total_tasks} ({(db_metrics.failed_tasks/db_metrics.total_tasks*100):.1f}%)")
            print(f"  24小时活动: {db_metrics.recent_activity} 次")
        
        # 进程性能
        processes = self.find_related_processes()
        if processes:
            print(f"\n🔄 进程性能")
            total_cpu = sum(p.cpu_percent for p in processes)
            total_memory = sum(p.memory_percent for p in processes)
            print(f"  相关进程数: {len(processes)}")
            print(f"  总CPU使用: {total_cpu:.1f}%")
            print(f"  总内存使用: {total_memory:.1f}%")
            
            # 最耗资源的进程
            if processes:
                cpu_top = max(processes, key=lambda p: p.cpu_percent)
                memory_top = max(processes, key=lambda p: p.memory_percent)
                print(f"  CPU最高: PID {cpu_top.pid} ({cpu_top.cpu_percent:.1f}%)")
                print(f"  内存最高: PID {memory_top.pid} ({memory_top.memory_percent:.1f}%)")
        
        # 健康状态
        health_status, issues = self.check_system_health()
        print(f"\n🏥 健康状态: {health_status.value.upper()}")
        if issues:
            print(f"  发现问题:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print(f"  ✅ 系统运行正常")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="系统监控器 - 实时监控Twitter发布系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python system_monitor.py                    # 显示系统仪表板
  python system_monitor.py --dashboard       # 显示仪表板
  python system_monitor.py --watch 30        # 每30秒刷新仪表板
  python system_monitor.py --health          # 健康检查
  python system_monitor.py --processes       # 显示进程详情
  python system_monitor.py --performance     # 性能报告
        """
    )
    
    parser.add_argument(
        '--dashboard', '-d',
        action='store_true',
        help='显示系统仪表板'
    )
    
    parser.add_argument(
        '--watch', '-w',
        type=int,
        metavar='SECONDS',
        help='自动刷新间隔(秒)'
    )
    
    parser.add_argument(
        '--health',
        action='store_true',
        help='执行健康检查'
    )
    
    parser.add_argument(
        '--processes', '-p',
        action='store_true',
        help='显示进程详细信息'
    )
    
    parser.add_argument(
        '--performance',
        action='store_true',
        help='显示性能报告'
    )
    
    parser.add_argument(
        '--db-path',
        default='data/twitter_publisher.db',
        help='数据库文件路径'
    )
    
    args = parser.parse_args()
    
    try:
        monitor = SystemMonitor(args.db_path)
        
        if args.health:
            status, issues = monitor.check_system_health()
            print(f"🏥 系统健康状态: {status.value.upper()}")
            if issues:
                print("发现的问题:")
                for issue in issues:
                    print(f"  - {issue}")
            else:
                print("✅ 系统运行正常")
        
        elif args.processes:
            monitor.show_process_details()
        
        elif args.performance:
            monitor.show_performance_report()
        
        elif args.watch:
            monitor.show_dashboard(args.watch)
        
        else:
            # 默认显示仪表板
            monitor.show_dashboard()
    
    except KeyboardInterrupt:
        print("\n👋 监控已停止")
    except Exception as e:
        print(f"❌ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()