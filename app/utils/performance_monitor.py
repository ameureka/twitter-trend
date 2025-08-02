"""性能监控模块

根据项目开发设计核心原则，提供系统性能监控和资源使用情况跟踪。
"""

import time
import psutil
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque, defaultdict
from contextlib import contextmanager
import json
from app.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    active_threads: int
    open_files: int
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class APIMetric:
    """API调用指标"""
    timestamp: datetime
    endpoint: str
    method: str
    status_code: int
    duration_ms: float
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class TaskMetric:
    """任务执行指标"""
    timestamp: datetime
    task_type: str
    task_id: int
    duration_ms: float
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, monitoring_interval: float = 60.0, max_history: int = 100):
        self.monitoring_interval = monitoring_interval
        self.max_history = max_history
        self.metrics_history: List[PerformanceMetrics] = []
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # 新增：API和任务指标存储
        self.api_metrics: deque = deque(maxlen=max_history * 10)  # API调用更频繁
        self.task_metrics: deque = deque(maxlen=max_history)
        self.counters = defaultdict(int)
        self.stats = defaultdict(list)
    
    def start_monitoring(self):
        """开始性能监控"""
        if self.is_monitoring:
            logger.warning("性能监控已在运行")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="PerformanceMonitor"
        )
        self.monitor_thread.start()
        logger.info(f"性能监控已启动，监控间隔: {self.monitoring_interval}秒")
    
    def stop_monitoring(self):
        """停止性能监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        
        logger.info("性能监控已停止")
    
    def _monitoring_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                metrics = self._collect_metrics()
                self._add_metrics(metrics)
                time.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"性能监控错误: {e}")
                time.sleep(self.monitoring_interval)
    
    def _collect_metrics(self) -> PerformanceMetrics:
        """收集性能指标"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024 * 1024)
            
            # 磁盘使用情况
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024 * 1024 * 1024)
            
            # 进程信息
            process = psutil.Process()
            active_threads = process.num_threads()
            open_files = len(process.open_files())
            
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                disk_usage_percent=disk_usage_percent,
                disk_free_gb=disk_free_gb,
                active_threads=active_threads,
                open_files=open_files
            )
            
        except Exception as e:
            logger.error(f"收集性能指标失败: {e}")
            # 返回默认值
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                disk_usage_percent=0.0,
                disk_free_gb=0.0,
                active_threads=0,
                open_files=0
            )
    
    def _add_metrics(self, metrics: PerformanceMetrics):
        """添加性能指标到历史记录"""
        with self._lock:
            self.metrics_history.append(metrics)
            
            # 保持历史记录在最大限制内
            if len(self.metrics_history) > self.max_history:
                self.metrics_history = self.metrics_history[-self.max_history:]
    
    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """获取当前性能指标"""
        if not self.is_monitoring:
            return self._collect_metrics()
        
        with self._lock:
            return self.metrics_history[-1] if self.metrics_history else None
    
    def get_metrics_summary(self, duration_minutes: int = 60) -> Dict[str, Any]:
        """获取指定时间段内的性能指标摘要"""
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        
        with self._lock:
            recent_metrics = [
                m for m in self.metrics_history 
                if m.timestamp >= cutoff_time
            ]
        
        if not recent_metrics:
            return {'error': '没有可用的性能数据'}
        
        # 计算统计信息
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        
        return {
            'period_minutes': duration_minutes,
            'sample_count': len(recent_metrics),
            'cpu': {
                'avg': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values)
            },
            'memory': {
                'avg': sum(memory_values) / len(memory_values),
                'max': max(memory_values),
                'min': min(memory_values),
                'current_used_mb': recent_metrics[-1].memory_used_mb
            },
            'disk': {
                'usage_percent': recent_metrics[-1].disk_usage_percent,
                'free_gb': recent_metrics[-1].disk_free_gb
            },
            'process': {
                'threads': recent_metrics[-1].active_threads,
                'open_files': recent_metrics[-1].open_files
            }
        }
    
    def check_resource_alerts(self) -> List[str]:
        """检查资源使用警告"""
        alerts = []
        current = self.get_current_metrics()
        
        if not current:
            return ['无法获取当前性能指标']
        
        # CPU使用率警告
        if current.cpu_percent > 80:
            alerts.append(f"CPU使用率过高: {current.cpu_percent:.1f}%")
        
        # 内存使用率警告
        if current.memory_percent > 85:
            alerts.append(f"内存使用率过高: {current.memory_percent:.1f}%")
        
        # 磁盘空间警告
        if current.disk_usage_percent > 90:
            alerts.append(f"磁盘使用率过高: {current.disk_usage_percent:.1f}%")
        elif current.disk_free_gb < 1.0:
            alerts.append(f"磁盘剩余空间不足: {current.disk_free_gb:.1f}GB")
        
        # 文件句柄警告
        if current.open_files > 100:
            alerts.append(f"打开文件数量较多: {current.open_files}")
        
        return alerts
    
    def record_api_call(self, endpoint: str, method: str, status_code: int, duration_ms: float, user_id: str = None):
        """记录API调用指标"""
        metric = APIMetric(
            timestamp=datetime.now(),
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            user_id=user_id
        )
        
        with self._lock:
            self.api_metrics.append(metric)
            
            # 更新计数器
            self.counters[f"api.calls.{endpoint}.{method}"] += 1
            self.counters[f"api.status.{status_code}"] += 1
            
            # 更新统计
            self.stats[f"api.response_time.{endpoint}"].append(duration_ms)
            if len(self.stats[f"api.response_time.{endpoint}"]) > 100:
                self.stats[f"api.response_time.{endpoint}"] = self.stats[f"api.response_time.{endpoint}"][-100:]
    
    def record_task_execution(self, task_type: str, task_id: int, duration_ms: float, success: bool, error_message: str = None):
        """记录任务执行指标"""
        metric = TaskMetric(
            timestamp=datetime.now(),
            task_type=task_type,
            task_id=task_id,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message
        )
        
        with self._lock:
            self.task_metrics.append(metric)
            
            # 更新计数器
            self.counters[f"task.executions.{task_type}"] += 1
            self.counters[f"task.{'success' if success else 'failure'}.{task_type}"] += 1
            
            # 更新统计
            self.stats[f"task.execution_time.{task_type}"].append(duration_ms)
            if len(self.stats[f"task.execution_time.{task_type}"]) > 100:
                self.stats[f"task.execution_time.{task_type}"] = self.stats[f"task.execution_time.{task_type}"][-100:]
    
    @contextmanager
    def measure_time(self, operation: str, tags: Dict[str, str] = None):
        """测量操作执行时间的上下文管理器"""
        start_time = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            # 可以根据需要记录到不同的指标中
            logger.debug(f"操作 {operation} 执行时间: {duration_ms:.2f}ms")
    
    def get_api_stats(self, hours: int = 24) -> Dict[str, Any]:
        """获取API统计信息"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            recent_api_metrics = [
                m for m in self.api_metrics 
                if m.timestamp >= cutoff_time
            ]
        
        if not recent_api_metrics:
            return {'error': '没有可用的API数据'}
        
        # 按端点分组统计
        endpoint_stats = defaultdict(lambda: {'count': 0, 'response_times': [], 'status_codes': []})
        
        for metric in recent_api_metrics:
            key = f"{metric.method} {metric.endpoint}"
            endpoint_stats[key]['count'] += 1
            endpoint_stats[key]['response_times'].append(metric.duration_ms)
            endpoint_stats[key]['status_codes'].append(metric.status_code)
        
        # 计算统计信息
        result = {}
        for endpoint, data in endpoint_stats.items():
            response_times = data['response_times']
            status_codes = data['status_codes']
            
            result[endpoint] = {
                'total_calls': data['count'],
                'avg_response_time': sum(response_times) / len(response_times),
                'max_response_time': max(response_times),
                'min_response_time': min(response_times),
                'success_rate': len([s for s in status_codes if 200 <= s < 300]) / len(status_codes) * 100,
                'error_rate': len([s for s in status_codes if s >= 400]) / len(status_codes) * 100
            }
        
        return result
    
    def get_task_stats(self, hours: int = 24) -> Dict[str, Any]:
        """获取任务统计信息"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            recent_task_metrics = [
                m for m in self.task_metrics 
                if m.timestamp >= cutoff_time
            ]
        
        if not recent_task_metrics:
            return {'error': '没有可用的任务数据'}
        
        # 按任务类型分组统计
        task_stats = defaultdict(lambda: {'count': 0, 'execution_times': [], 'successes': 0, 'failures': 0})
        
        for metric in recent_task_metrics:
            task_stats[metric.task_type]['count'] += 1
            task_stats[metric.task_type]['execution_times'].append(metric.duration_ms)
            if metric.success:
                task_stats[metric.task_type]['successes'] += 1
            else:
                task_stats[metric.task_type]['failures'] += 1
        
        # 计算统计信息
        result = {}
        for task_type, data in task_stats.items():
            execution_times = data['execution_times']
            total = data['count']
            
            result[task_type] = {
                'total_executions': total,
                'avg_execution_time': sum(execution_times) / len(execution_times),
                'max_execution_time': max(execution_times),
                'min_execution_time': min(execution_times),
                'success_rate': (data['successes'] / total) * 100,
                'failure_rate': (data['failures'] / total) * 100
            }
        
        return result
    
    def get_enhanced_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """获取增强的性能指标"""
        system_summary = self.get_metrics_summary(hours * 60)  # 转换为分钟
        api_stats = self.get_api_stats(hours)
        task_stats = self.get_task_stats(hours)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'time_range_hours': hours,
            'system_metrics': system_summary,
            'api_metrics': api_stats,
            'task_metrics': task_stats,
            'counters': dict(self.counters),
            'alerts': self.check_resource_alerts()
        }


class FunctionProfiler:
    """函数性能分析器"""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        
        if duration > 1.0:  # 超过1秒记录警告
            logger.warning(f"函数 {self.name} 执行时间较长: {duration:.2f}秒")
        else:
            logger.debug(f"函数 {self.name} 执行时间: {duration:.3f}秒")


def profile_function(name: str = None):
    """函数性能分析装饰器"""
    def decorator(func):
        function_name = name or func.__name__
        
        def wrapper(*args, **kwargs):
            with FunctionProfiler(function_name):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


class ResourceTracker:
    """资源使用跟踪器"""
    
    def __init__(self):
        self.start_metrics = None
        self.operation_name = None
    
    def start_tracking(self, operation_name: str):
        """开始跟踪资源使用"""
        self.operation_name = operation_name
        self.start_metrics = self._get_process_metrics()
        logger.debug(f"开始跟踪操作: {operation_name}")
    
    def stop_tracking(self) -> Dict[str, Any]:
        """停止跟踪并返回资源使用情况"""
        if not self.start_metrics:
            return {'error': '未开始跟踪'}
        
        end_metrics = self._get_process_metrics()
        
        result = {
            'operation': self.operation_name,
            'memory_delta_mb': end_metrics['memory_mb'] - self.start_metrics['memory_mb'],
            'cpu_time_delta': end_metrics['cpu_time'] - self.start_metrics['cpu_time'],
            'io_read_delta': end_metrics['io_read'] - self.start_metrics['io_read'],
            'io_write_delta': end_metrics['io_write'] - self.start_metrics['io_write']
        }
        
        logger.info(
            f"操作 {self.operation_name} 资源使用: "
            f"内存变化 {result['memory_delta_mb']:.1f}MB, "
            f"CPU时间 {result['cpu_time_delta']:.2f}s"
        )
        
        return result
    
    def _get_process_metrics(self) -> Dict[str, float]:
        """获取当前进程的资源使用指标"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            cpu_times = process.cpu_times()
            io_counters = process.io_counters()
            
            return {
                'memory_mb': memory_info.rss / (1024 * 1024),
                'cpu_time': cpu_times.user + cpu_times.system,
                'io_read': io_counters.read_bytes,
                'io_write': io_counters.write_bytes
            }
        except Exception as e:
            logger.error(f"获取进程指标失败: {e}")
            return {
                'memory_mb': 0.0,
                'cpu_time': 0.0,
                'io_read': 0,
                'io_write': 0
            }


# 全局性能监控器实例
_global_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


def start_global_monitoring():
    """启动全局性能监控"""
    monitor = get_performance_monitor()
    monitor.start_monitoring()


def stop_global_monitoring():
    """停止全局性能监控"""
    monitor = get_performance_monitor()
    monitor.stop_monitoring()


def get_system_health() -> Dict[str, Any]:
    """获取系统健康状态"""
    monitor = get_performance_monitor()
    current_metrics = monitor.get_current_metrics()
    alerts = monitor.check_resource_alerts()
    summary = monitor.get_metrics_summary(30)  # 最近30分钟
    
    return {
        'timestamp': datetime.now().isoformat(),
        'current_metrics': current_metrics.__dict__ if current_metrics else None,
        'alerts': alerts,
        'summary': summary,
        'status': 'healthy' if not alerts else 'warning'
    }