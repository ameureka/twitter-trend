#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔒 数据库锁超时处理管理器 - Phase 4.2
根据TWITTER_OPTIMIZATION_PLAN.md实现高级数据库锁管理机制

主要功能:
1. 智能锁检测与监控
2. 死锁预防与解决
3. 锁等待队列管理
4. 自适应重试策略
5. 连接池优化
6. 锁统计与分析
"""

import sqlite3
import threading
import time
import queue
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
from collections import defaultdict, deque
import random
import psutil

from app.utils.logger import get_logger

logger = get_logger(__name__)

class LockType(Enum):
    """锁类型枚举"""
    SHARED = "shared"          # 共享锁（读锁）
    EXCLUSIVE = "exclusive"    # 排他锁（写锁）
    RESERVED = "reserved"      # 保留锁
    PENDING = "pending"        # 待定锁
    DEFERRED = "deferred"      # 延迟锁

class LockState(Enum):
    """锁状态枚举"""
    WAITING = "waiting"        # 等待中
    ACQUIRED = "acquired"      # 已获取
    TIMEOUT = "timeout"        # 超时
    DEADLOCK = "deadlock"      # 死锁
    RELEASED = "released"      # 已释放
    FAILED = "failed"          # 失败

@dataclass
class LockRequest:
    """锁请求信息"""
    request_id: str
    connection_id: str
    lock_type: LockType
    table_name: Optional[str]
    request_time: datetime
    timeout_seconds: float
    priority: int = 1
    retry_count: int = 0
    max_retries: int = 3
    
    def is_expired(self) -> bool:
        """检查请求是否超时"""
        elapsed = (datetime.now() - self.request_time).total_seconds()
        return elapsed > self.timeout_seconds
    
    def __hash__(self):
        return hash(self.request_id)

@dataclass
class LockStatistics:
    """锁统计信息"""
    total_requests: int = 0
    successful_acquisitions: int = 0
    timeouts: int = 0
    deadlocks: int = 0
    retries: int = 0
    average_wait_time: float = 0.0
    peak_concurrent_locks: int = 0
    lock_type_distribution: Dict[str, int] = field(default_factory=dict)
    table_lock_distribution: Dict[str, int] = field(default_factory=dict)

@dataclass
class ConnectionInfo:
    """数据库连接信息"""
    connection_id: str
    connection: sqlite3.Connection
    created_at: datetime
    last_used: datetime
    in_use: bool = False
    transaction_active: bool = False
    lock_count: int = 0
    
    def is_idle(self, idle_timeout_seconds: int = 300) -> bool:
        """检查连接是否空闲"""
        if self.in_use:
            return False
        idle_time = (datetime.now() - self.last_used).total_seconds()
        return idle_time > idle_timeout_seconds

class DatabaseLockManager:
    """🔒 高级数据库锁管理器"""
    
    def __init__(self, db_path: str, config: Optional[Dict[str, Any]] = None):
        self.db_path = db_path
        self.config = config or {}
        
        # 配置参数
        self.max_connections = self.config.get('max_connections', 10)
        self.min_connections = self.config.get('min_connections', 2)
        self.default_timeout = self.config.get('default_timeout', 30)
        self.max_wait_time = self.config.get('max_wait_time', 60)
        self.deadlock_check_interval = self.config.get('deadlock_check_interval', 5)
        self.connection_idle_timeout = self.config.get('connection_idle_timeout', 300)
        
        # 重试策略参数
        self.base_retry_delay = self.config.get('base_retry_delay', 0.1)
        self.max_retry_delay = self.config.get('max_retry_delay', 5.0)
        self.retry_jitter = self.config.get('retry_jitter', 0.2)
        
        # 连接池
        self.connection_pool: Dict[str, ConnectionInfo] = {}
        self.available_connections: queue.Queue = queue.Queue()
        
        # 锁管理
        self.active_locks: Dict[str, LockRequest] = {}
        self.waiting_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.lock_wait_graph: Dict[str, List[str]] = defaultdict(list)  # 用于死锁检测
        
        # 统计信息
        self.statistics = LockStatistics()
        self.lock_history: deque = deque(maxlen=1000)  # 保留最近1000条锁记录
        
        # 线程同步
        self.manager_lock = threading.RLock()
        self.condition = threading.Condition(self.manager_lock)
        
        # 监控线程
        self.monitoring = False
        self.monitor_thread = None
        
        # 初始化连接池
        self._initialize_connection_pool()
        
        logger.info("🔒 数据库锁管理器已初始化")
        logger.info(f"  - 数据库路径: {self.db_path}")
        logger.info(f"  - 最大连接数: {self.max_connections}")
        logger.info(f"  - 默认超时: {self.default_timeout}秒")
    
    def _initialize_connection_pool(self):
        """初始化连接池"""
        try:
            for i in range(self.min_connections):
                conn_info = self._create_connection()
                if conn_info:
                    self.connection_pool[conn_info.connection_id] = conn_info
                    self.available_connections.put(conn_info.connection_id)
                    
            logger.info(f"🔒 连接池初始化完成，创建了 {self.min_connections} 个连接")
            
        except Exception as e:
            logger.error(f"🔒 连接池初始化失败: {e}")
    
    def _create_connection(self) -> Optional[ConnectionInfo]:
        """创建新的数据库连接"""
        try:
            connection_id = self._generate_connection_id()
            
            # 创建连接并设置优化参数
            conn = sqlite3.connect(self.db_path, timeout=self.default_timeout, check_same_thread=False)
            
            # 设置SQLite优化参数
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB
            conn.execute(f"PRAGMA busy_timeout={self.default_timeout * 1000}")  # 毫秒
            
            # 启用外键约束
            conn.execute("PRAGMA foreign_keys=ON")
            
            conn_info = ConnectionInfo(
                connection_id=connection_id,
                connection=conn,
                created_at=datetime.now(),
                last_used=datetime.now()
            )
            
            logger.debug(f"🔒 创建新连接: {connection_id}")
            return conn_info
            
        except Exception as e:
            logger.error(f"🔒 创建连接失败: {e}")
            return None
    
    def _generate_connection_id(self) -> str:
        """生成唯一的连接ID"""
        timestamp = datetime.now().isoformat()
        random_str = str(random.random())
        return hashlib.md5(f"{timestamp}_{random_str}".encode()).hexdigest()[:12]
    
    @contextmanager
    def acquire_connection(self, timeout: Optional[float] = None) -> sqlite3.Connection:
        """
        获取数据库连接（上下文管理器）
        
        Args:
            timeout: 超时时间（秒）
            
        Yields:
            sqlite3.Connection: 数据库连接
        """
        timeout = timeout or self.default_timeout
        connection_id = None
        
        try:
            # 尝试从池中获取连接
            connection_id = self._get_connection_from_pool(timeout)
            
            if not connection_id:
                raise TimeoutError(f"无法在 {timeout} 秒内获取数据库连接")
                
            with self.manager_lock:
                conn_info = self.connection_pool[connection_id]
                conn_info.in_use = True
                conn_info.last_used = datetime.now()
                
            yield conn_info.connection
            
        finally:
            # 释放连接回池
            if connection_id:
                self._release_connection_to_pool(connection_id)
    
    def _get_connection_from_pool(self, timeout: float) -> Optional[str]:
        """从池中获取连接"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # 尝试获取可用连接
                connection_id = self.available_connections.get(timeout=0.1)
                
                with self.manager_lock:
                    if connection_id in self.connection_pool:
                        conn_info = self.connection_pool[connection_id]
                        
                        # 检查连接是否有效
                        try:
                            conn_info.connection.execute("SELECT 1")
                            return connection_id
                        except:
                            # 连接无效，创建新连接
                            logger.warning(f"🔒 连接 {connection_id} 无效，创建新连接")
                            self._remove_connection(connection_id)
                            new_conn = self._create_connection()
                            if new_conn:
                                self.connection_pool[new_conn.connection_id] = new_conn
                                return new_conn.connection_id
                                
            except queue.Empty:
                # 检查是否可以创建新连接
                with self.manager_lock:
                    if len(self.connection_pool) < self.max_connections:
                        new_conn = self._create_connection()
                        if new_conn:
                            self.connection_pool[new_conn.connection_id] = new_conn
                            return new_conn.connection_id
                            
                # 等待一小段时间再重试
                time.sleep(0.1)
                
        return None
    
    def _release_connection_to_pool(self, connection_id: str):
        """释放连接回池"""
        with self.manager_lock:
            if connection_id in self.connection_pool:
                conn_info = self.connection_pool[connection_id]
                conn_info.in_use = False
                conn_info.last_used = datetime.now()
                
                # 回滚未提交的事务
                if conn_info.transaction_active:
                    try:
                        conn_info.connection.rollback()
                        conn_info.transaction_active = False
                    except:
                        pass
                        
                self.available_connections.put(connection_id)
    
    def _remove_connection(self, connection_id: str):
        """移除连接"""
        with self.manager_lock:
            if connection_id in self.connection_pool:
                conn_info = self.connection_pool[connection_id]
                try:
                    conn_info.connection.close()
                except:
                    pass
                del self.connection_pool[connection_id]
                logger.debug(f"🔒 移除连接: {connection_id}")
    
    def execute_with_retry(self, func: Callable, *args, max_retries: int = 3, **kwargs) -> Any:
        """
        带重试机制执行数据库操作
        
        Args:
            func: 要执行的函数
            max_retries: 最大重试次数
            *args, **kwargs: 函数参数
            
        Returns:
            函数执行结果
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                # 计算重试延迟
                if attempt > 0:
                    delay = self._calculate_retry_delay(attempt)
                    logger.info(f"🔒 重试第 {attempt} 次，延迟 {delay:.2f} 秒")
                    time.sleep(delay)
                    self.statistics.retries += 1
                    
                # 执行函数
                with self.acquire_connection() as conn:
                    result = func(conn, *args, **kwargs)
                    
                self.statistics.successful_acquisitions += 1
                return result
                
            except sqlite3.OperationalError as e:
                last_error = e
                error_msg = str(e).lower()
                
                if 'database is locked' in error_msg:
                    logger.warning(f"🔒 数据库锁定，尝试 {attempt + 1}/{max_retries + 1}")
                    self.statistics.timeouts += 1
                    
                elif 'deadlock' in error_msg:
                    logger.error(f"🔒 检测到死锁: {e}")
                    self.statistics.deadlocks += 1
                    self._handle_deadlock()
                    
                else:
                    logger.error(f"🔒 数据库操作错误: {e}")
                    raise
                    
            except Exception as e:
                logger.error(f"🔒 执行失败: {e}")
                raise
                
        # 所有重试都失败
        logger.error(f"🔒 所有重试都失败: {last_error}")
        raise last_error
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """计算重试延迟（指数退避 + 抖动）"""
        # 指数退避
        delay = min(self.base_retry_delay * (2 ** (attempt - 1)), self.max_retry_delay)
        
        # 添加随机抖动
        jitter = delay * self.retry_jitter * (2 * random.random() - 1)
        final_delay = max(0, delay + jitter)
        
        return final_delay
    
    def _handle_deadlock(self):
        """处理死锁情况"""
        logger.warning("🔒 开始死锁处理...")
        
        with self.manager_lock:
            # 检测死锁环
            deadlock_chains = self._detect_deadlock_cycles()
            
            if deadlock_chains:
                logger.warning(f"🔒 发现 {len(deadlock_chains)} 个死锁环")
                
                # 选择牺牲者（优先级最低的）
                for chain in deadlock_chains:
                    victim = self._select_deadlock_victim(chain)
                    if victim:
                        logger.warning(f"🔒 选择牺牲者: {victim}")
                        self._abort_lock_request(victim)
                        
            # 清理等待图
            self.lock_wait_graph.clear()
    
    def _detect_deadlock_cycles(self) -> List[List[str]]:
        """检测死锁环（使用DFS）"""
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: List[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.lock_wait_graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path.copy()):
                        return True
                elif neighbor in rec_stack:
                    # 找到环
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:]
                    cycles.append(cycle)
                    return True
                    
            rec_stack.remove(node)
            return False
            
        for node in list(self.lock_wait_graph.keys()):
            if node not in visited:
                dfs(node, [])
                
        return cycles
    
    def _select_deadlock_victim(self, chain: List[str]) -> Optional[str]:
        """选择死锁牺牲者"""
        if not chain:
            return None
            
        # 选择优先级最低或等待时间最短的
        victim = None
        min_priority = float('inf')
        
        for request_id in chain:
            if request_id in self.active_locks:
                lock_request = self.active_locks[request_id]
                if lock_request.priority < min_priority:
                    min_priority = lock_request.priority
                    victim = request_id
                    
        return victim
    
    def _abort_lock_request(self, request_id: str):
        """中止锁请求"""
        if request_id in self.active_locks:
            lock_request = self.active_locks[request_id]
            
            # 释放相关资源
            if lock_request.connection_id in self.connection_pool:
                conn_info = self.connection_pool[lock_request.connection_id]
                try:
                    conn_info.connection.rollback()
                except:
                    pass
                    
            # 从活动锁中移除
            del self.active_locks[request_id]
            
            # 记录到历史
            self._record_lock_event(lock_request, LockState.DEADLOCK)
    
    def acquire_table_lock(self, table_name: str, lock_type: LockType = LockType.EXCLUSIVE,
                          timeout: Optional[float] = None, priority: int = 1) -> bool:
        """
        获取表级锁
        
        Args:
            table_name: 表名
            lock_type: 锁类型
            timeout: 超时时间
            priority: 优先级
            
        Returns:
            bool: 是否成功获取锁
        """
        timeout = timeout or self.default_timeout
        request_id = self._generate_request_id()
        
        lock_request = LockRequest(
            request_id=request_id,
            connection_id=threading.current_thread().ident,
            lock_type=lock_type,
            table_name=table_name,
            request_time=datetime.now(),
            timeout_seconds=timeout,
            priority=priority
        )
        
        with self.manager_lock:
            # 检查是否可以立即获取锁
            if self._can_acquire_lock(lock_request):
                self.active_locks[request_id] = lock_request
                self._record_lock_event(lock_request, LockState.ACQUIRED)
                self.statistics.successful_acquisitions += 1
                return True
                
            # 加入等待队列
            self.waiting_queue.put((priority, lock_request))
            self._update_wait_graph(lock_request)
            
        # 等待锁
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self.condition:
                if request_id in self.active_locks:
                    return True
                    
                # 等待通知
                self.condition.wait(timeout=0.5)
                
        # 超时
        self._record_lock_event(lock_request, LockState.TIMEOUT)
        self.statistics.timeouts += 1
        return False
    
    def _can_acquire_lock(self, request: LockRequest) -> bool:
        """检查是否可以获取锁"""
        if request.lock_type == LockType.SHARED:
            # 共享锁：检查是否有排他锁
            for active_request in self.active_locks.values():
                if (active_request.table_name == request.table_name and
                    active_request.lock_type == LockType.EXCLUSIVE):
                    return False
        else:
            # 排他锁：检查是否有任何锁
            for active_request in self.active_locks.values():
                if active_request.table_name == request.table_name:
                    return False
                    
        return True
    
    def _update_wait_graph(self, request: LockRequest):
        """更新等待图（用于死锁检测）"""
        # 找出阻塞当前请求的锁
        blocking_requests = []
        
        for active_request in self.active_locks.values():
            if active_request.table_name == request.table_name:
                if (request.lock_type == LockType.EXCLUSIVE or
                    active_request.lock_type == LockType.EXCLUSIVE):
                    blocking_requests.append(active_request.request_id)
                    
        # 更新等待图
        if blocking_requests:
            self.lock_wait_graph[request.request_id] = blocking_requests
    
    def release_table_lock(self, request_id: str):
        """释放表级锁"""
        with self.manager_lock:
            if request_id in self.active_locks:
                lock_request = self.active_locks[request_id]
                del self.active_locks[request_id]
                
                self._record_lock_event(lock_request, LockState.RELEASED)
                
                # 通知等待线程
                self.condition.notify_all()
                
                # 处理等待队列
                self._process_waiting_queue()
    
    def _process_waiting_queue(self):
        """处理等待队列"""
        processed = []
        
        while not self.waiting_queue.empty():
            priority, lock_request = self.waiting_queue.get()
            
            if self._can_acquire_lock(lock_request):
                self.active_locks[lock_request.request_id] = lock_request
                self._record_lock_event(lock_request, LockState.ACQUIRED)
                self.condition.notify_all()
            else:
                processed.append((priority, lock_request))
                
        # 将未处理的请求放回队列
        for item in processed:
            self.waiting_queue.put(item)
    
    def _generate_request_id(self) -> str:
        """生成唯一的请求ID"""
        timestamp = datetime.now().isoformat()
        thread_id = threading.current_thread().ident
        random_str = str(random.random())
        return hashlib.md5(f"{timestamp}_{thread_id}_{random_str}".encode()).hexdigest()[:16]
    
    def _record_lock_event(self, request: LockRequest, state: LockState):
        """记录锁事件"""
        event = {
            'request_id': request.request_id,
            'table_name': request.table_name,
            'lock_type': request.lock_type.value,
            'state': state.value,
            'timestamp': datetime.now().isoformat(),
            'wait_time': (datetime.now() - request.request_time).total_seconds()
        }
        
        self.lock_history.append(event)
        
        # 更新统计
        self.statistics.total_requests += 1
        
        if request.lock_type.value not in self.statistics.lock_type_distribution:
            self.statistics.lock_type_distribution[request.lock_type.value] = 0
        self.statistics.lock_type_distribution[request.lock_type.value] += 1
        
        if request.table_name:
            if request.table_name not in self.statistics.table_lock_distribution:
                self.statistics.table_lock_distribution[request.table_name] = 0
            self.statistics.table_lock_distribution[request.table_name] += 1
            
        # 更新平均等待时间
        if state == LockState.ACQUIRED:
            wait_time = (datetime.now() - request.request_time).total_seconds()
            current_avg = self.statistics.average_wait_time
            current_count = self.statistics.successful_acquisitions
            new_avg = (current_avg * current_count + wait_time) / (current_count + 1)
            self.statistics.average_wait_time = new_avg
            
        # 更新峰值并发锁
        current_locks = len(self.active_locks)
        if current_locks > self.statistics.peak_concurrent_locks:
            self.statistics.peak_concurrent_locks = current_locks
    
    def start_monitoring(self):
        """启动监控线程"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("🔒 数据库锁监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            
        logger.info("🔒 数据库锁监控已停止")
    
    def _monitoring_loop(self):
        """监控循环"""
        logger.info("🔒 数据库锁监控循环启动")
        
        while self.monitoring:
            try:
                # 检测死锁
                with self.manager_lock:
                    if self.lock_wait_graph:
                        deadlock_chains = self._detect_deadlock_cycles()
                        if deadlock_chains:
                            logger.warning(f"🔒 检测到 {len(deadlock_chains)} 个潜在死锁")
                            self._handle_deadlock()
                            
                # 清理空闲连接
                self._cleanup_idle_connections()
                
                # 处理超时请求
                self._handle_timeout_requests()
                
                # 记录统计信息
                if self.statistics.total_requests > 0 and self.statistics.total_requests % 100 == 0:
                    self._log_statistics()
                    
                time.sleep(self.deadlock_check_interval)
                
            except Exception as e:
                logger.error(f"🔒 监控循环异常: {e}")
                time.sleep(1)
                
        logger.info("🔒 数据库锁监控循环结束")
    
    def _cleanup_idle_connections(self):
        """清理空闲连接"""
        with self.manager_lock:
            idle_connections = []
            
            for conn_id, conn_info in self.connection_pool.items():
                if conn_info.is_idle(self.connection_idle_timeout):
                    idle_connections.append(conn_id)
                    
            # 保留最小连接数
            removable_count = len(self.connection_pool) - self.min_connections
            
            for conn_id in idle_connections[:removable_count]:
                self._remove_connection(conn_id)
                logger.debug(f"🔒 清理空闲连接: {conn_id}")
    
    def _handle_timeout_requests(self):
        """处理超时的锁请求"""
        with self.manager_lock:
            timeout_requests = []
            
            # 检查等待队列中的超时请求
            temp_queue = []
            
            while not self.waiting_queue.empty():
                priority, request = self.waiting_queue.get()
                if request.is_expired():
                    timeout_requests.append(request)
                    self._record_lock_event(request, LockState.TIMEOUT)
                else:
                    temp_queue.append((priority, request))
                    
            # 重新填充队列
            for item in temp_queue:
                self.waiting_queue.put(item)
                
            if timeout_requests:
                logger.warning(f"🔒 处理了 {len(timeout_requests)} 个超时请求")
    
    def _log_statistics(self):
        """记录统计信息"""
        logger.info("🔒 数据库锁统计:")
        logger.info(f"  - 总请求数: {self.statistics.total_requests}")
        logger.info(f"  - 成功获取: {self.statistics.successful_acquisitions}")
        logger.info(f"  - 超时: {self.statistics.timeouts}")
        logger.info(f"  - 死锁: {self.statistics.deadlocks}")
        logger.info(f"  - 重试: {self.statistics.retries}")
        logger.info(f"  - 平均等待时间: {self.statistics.average_wait_time:.2f}秒")
        logger.info(f"  - 峰值并发锁: {self.statistics.peak_concurrent_locks}")
        logger.info(f"  - 当前活动锁: {len(self.active_locks)}")
        logger.info(f"  - 连接池大小: {len(self.connection_pool)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.manager_lock:
            return {
                'total_requests': self.statistics.total_requests,
                'successful_acquisitions': self.statistics.successful_acquisitions,
                'success_rate': self.statistics.successful_acquisitions / self.statistics.total_requests 
                                if self.statistics.total_requests > 0 else 0,
                'timeouts': self.statistics.timeouts,
                'deadlocks': self.statistics.deadlocks,
                'retries': self.statistics.retries,
                'average_wait_time': self.statistics.average_wait_time,
                'peak_concurrent_locks': self.statistics.peak_concurrent_locks,
                'current_active_locks': len(self.active_locks),
                'waiting_requests': self.waiting_queue.qsize(),
                'connection_pool_size': len(self.connection_pool),
                'lock_type_distribution': dict(self.statistics.lock_type_distribution),
                'table_lock_distribution': dict(self.statistics.table_lock_distribution)
            }
    
    def optimize_for_performance(self):
        """优化数据库性能设置"""
        try:
            with self.acquire_connection() as conn:
                # 分析数据库
                conn.execute("ANALYZE")
                
                # 重建索引
                conn.execute("REINDEX")
                
                # 清理数据库
                conn.execute("VACUUM")
                
                logger.info("🔒 数据库性能优化完成")
                
        except Exception as e:
            logger.error(f"🔒 性能优化失败: {e}")
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """获取系统指标"""
        try:
            # 获取系统资源使用情况
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # 获取SQLite特定指标
            sqlite_metrics = {}
            
            with self.acquire_connection() as conn:
                # 页面缓存统计
                result = conn.execute("PRAGMA page_count").fetchone()
                sqlite_metrics['page_count'] = result[0] if result else 0
                
                result = conn.execute("PRAGMA page_size").fetchone()
                sqlite_metrics['page_size'] = result[0] if result else 0
                
                result = conn.execute("PRAGMA cache_size").fetchone()
                sqlite_metrics['cache_size'] = result[0] if result else 0
                
                # WAL模式检查
                result = conn.execute("PRAGMA journal_mode").fetchone()
                sqlite_metrics['journal_mode'] = result[0] if result else 'unknown'
                
            return {
                'system': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_available_mb': memory.available / (1024 * 1024),
                    'disk_percent': disk.percent,
                    'disk_free_gb': disk.free / (1024 * 1024 * 1024)
                },
                'sqlite': sqlite_metrics,
                'lock_manager': self.get_statistics()
            }
            
        except Exception as e:
            logger.error(f"🔒 获取系统指标失败: {e}")
            return {}

# 全局实例（延迟初始化）
_database_lock_manager: Optional[DatabaseLockManager] = None

def get_database_lock_manager(db_path: str = "./data/twitter_publisher.db") -> DatabaseLockManager:
    """获取数据库锁管理器实例"""
    global _database_lock_manager
    
    if _database_lock_manager is None:
        _database_lock_manager = DatabaseLockManager(db_path)
        _database_lock_manager.start_monitoring()
        
    return _database_lock_manager

def execute_with_lock_protection(func: Callable, *args, **kwargs) -> Any:
    """
    便捷函数：使用锁保护执行数据库操作
    
    Args:
        func: 要执行的函数
        *args, **kwargs: 函数参数
        
    Returns:
        函数执行结果
    """
    manager = get_database_lock_manager()
    return manager.execute_with_retry(func, *args, **kwargs)