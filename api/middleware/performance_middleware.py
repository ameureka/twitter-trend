#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API性能监控中间件 - 自动记录API调用的性能指标

主要功能:
1. 自动记录API响应时间
2. 记录HTTP状态码
3. 记录用户信息
4. 异常处理和错误记录
5. 性能警告
"""

import time
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.utils.performance_monitor import get_performance_monitor
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """性能监控中间件"""
    
    def __init__(self, app: ASGIApp, slow_request_threshold: float = 1000.0):
        """
        初始化性能监控中间件
        
        Args:
            app: ASGI应用
            slow_request_threshold: 慢请求阈值（毫秒）
        """
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
        self.performance_monitor = get_performance_monitor()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录性能指标"""
        start_time = time.time()
        
        # 获取请求信息
        method = request.method
        path = request.url.path
        user_id = None
        
        # 尝试获取用户信息（如果有认证）
        try:
            if hasattr(request.state, 'user'):
                user_id = getattr(request.state.user, 'id', None) or getattr(request.state.user, 'username', None)
        except Exception:
            pass
        
        # 处理请求
        response = None
        status_code = 500
        error_occurred = False
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            
        except Exception as e:
            error_occurred = True
            logger.error(f"API请求处理异常: {method} {path} - {str(e)}")
            
            # 返回错误响应
            response = JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "服务器内部错误",
                    "error": str(e)
                }
            )
            status_code = 500
        
        finally:
            # 计算响应时间
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            # 记录性能指标
            self.performance_monitor.record_api_call(
                endpoint=path,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
                user_id=str(user_id) if user_id else None
            )
            
            # 记录慢请求
            if duration_ms > self.slow_request_threshold:
                logger.warning(
                    f"慢请求检测: {method} {path} - {duration_ms:.2f}ms "
                    f"(阈值: {self.slow_request_threshold}ms)"
                )
            
            # 记录错误请求
            if error_occurred or status_code >= 400:
                logger.warning(
                    f"错误请求: {method} {path} - 状态码: {status_code}, "
                    f"响应时间: {duration_ms:.2f}ms"
                )
            
            # 添加性能头信息
            if response:
                response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
                response.headers["X-Request-ID"] = getattr(request.state, 'request_id', 'unknown')
        
        return response


def add_performance_middleware(app, slow_request_threshold: float = 1000.0):
    """添加性能监控中间件到FastAPI应用"""
    app.add_middleware(PerformanceMiddleware, slow_request_threshold=slow_request_threshold)
    logger.info(f"性能监控中间件已添加，慢请求阈值: {slow_request_threshold}ms")


# 请求ID中间件
class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求ID中间件 - 为每个请求生成唯一ID"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """为请求添加唯一ID"""
        import uuid
        
        # 生成请求ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        # 处理请求
        response = await call_next(request)
        
        # 添加请求ID到响应头
        response.headers["X-Request-ID"] = request_id
        
        return response


def add_request_id_middleware(app):
    """添加请求ID中间件到FastAPI应用"""
    app.add_middleware(RequestIDMiddleware)
    logger.info("请求ID中间件已添加")


# 性能监控装饰器
def monitor_api_performance(operation_name: str = None):
    """API性能监控装饰器"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            operation = operation_name or f"{func.__module__}.{func.__name__}"
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # 记录成功的操作
                logger.debug(f"API操作 {operation} 执行成功: {duration_ms:.2f}ms")
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # 记录失败的操作
                logger.error(f"API操作 {operation} 执行失败: {duration_ms:.2f}ms - {str(e)}")
                
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            operation = operation_name or f"{func.__module__}.{func.__name__}"
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # 记录成功的操作
                logger.debug(f"API操作 {operation} 执行成功: {duration_ms:.2f}ms")
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # 记录失败的操作
                logger.error(f"API操作 {operation} 执行失败: {duration_ms:.2f}ms - {str(e)}")
                
                raise
        
        # 检查函数是否是异步的
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 数据库操作监控装饰器
def monitor_database_operation(operation_type: str, table_name: str = None):
    """数据库操作监控装饰器"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            table = table_name or "unknown"
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # 记录数据库操作
                performance_monitor = get_performance_monitor()
                performance_monitor.record_database_operation(
                    operation=operation_type,
                    table=table,
                    duration_ms=duration_ms,
                    rows_affected=getattr(result, 'rowcount', 0) if hasattr(result, 'rowcount') else 0
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # 记录失败的数据库操作
                logger.error(f"数据库操作失败: {operation_type} {table} - {duration_ms:.2f}ms - {str(e)}")
                
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            table = table_name or "unknown"
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # 记录数据库操作
                performance_monitor = get_performance_monitor()
                performance_monitor.record_database_operation(
                    operation=operation_type,
                    table=table,
                    duration_ms=duration_ms,
                    rows_affected=getattr(result, 'rowcount', 0) if hasattr(result, 'rowcount') else 0
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # 记录失败的数据库操作
                logger.error(f"数据库操作失败: {operation_type} {table} - {duration_ms:.2f}ms - {str(e)}")
                
                raise
        
        # 检查函数是否是异步的
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator