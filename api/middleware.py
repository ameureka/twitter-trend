#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API中间件模块
提供统一的错误处理、日志记录和安全中间件
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.utils.logger import get_logger
from app.utils.retry_handler import ErrorHandler

logger = get_logger(__name__)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """统一错误处理中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.error_handler = ErrorHandler()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成请求ID用于追踪
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        start_time = time.time()
        
        try:
            # 记录请求开始
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} - Started",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": request.client.host if request.client else None
                }
            )
            
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录请求完成
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} - "
                f"Completed {response.status_code} in {process_time:.3f}s",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time": process_time
                }
            )
            
            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            return response
            
        except HTTPException as e:
            # FastAPI HTTP异常
            process_time = time.time() - start_time
            
            logger.warning(
                f"[{request_id}] {request.method} {request.url.path} - "
                f"HTTP Exception {e.status_code}: {e.detail}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": e.status_code,
                    "error_detail": e.detail,
                    "process_time": process_time
                }
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": {
                        "code": e.status_code,
                        "message": e.detail,
                        "request_id": request_id,
                        "timestamp": time.time()
                    }
                },
                headers={"X-Request-ID": request_id}
            )
            
        except Exception as e:
            # 未预期的异常
            process_time = time.time() - start_time
            
            # 使用错误处理器获取友好的错误信息
            try:
                error_msg = self.error_handler.handle_api_error(e, f"{request.method} {request.url.path}")
            except Exception:
                error_msg = "An unexpected error occurred"
            
            logger.error(
                f"[{request_id}] {request.method} {request.url.path} - "
                f"Unhandled Exception: {str(e)}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "process_time": process_time
                },
                exc_info=True
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": 500,
                        "message": "Internal Server Error",
                        "detail": error_msg,
                        "request_id": request_id,
                        "timestamp": time.time()
                    }
                },
                headers={"X-Request-ID": request_id}
            )

class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # 记录请求信息
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_ip": request.client.host if request.client else None
            }
        )
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        # 记录响应信息
        logger.info(
            f"Response: {response.status_code} in {process_time:.3f}s",
            extra={
                "status_code": response.status_code,
                "process_time": process_time
            }
        )
        
        return response

class CORSMiddleware(BaseHTTPMiddleware):
    """CORS中间件"""
    
    def __init__(self, app: ASGIApp, allow_origins: list = None, allow_methods: list = None):
        super().__init__(app)
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 处理预检请求
        if request.method == "OPTIONS":
            response = Response()
        else:
            response = await call_next(request)
        
        # 添加CORS头
        origin = request.headers.get("origin")
        if origin and ("*" in self.allow_origins or origin in self.allow_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
        elif "*" in self.allow_origins:
            response.headers["Access-Control-Allow-Origin"] = "*"
        
        response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key"
        response.headers["Access-Control-Max-Age"] = "86400"
        
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全头中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # 添加安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https:;"
        )
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """简单的速率限制中间件"""
    
    def __init__(self, app: ASGIApp, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}  # 简单的内存存储，生产环境应使用Redis
        self.window_size = 60  # 1分钟窗口
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 获取客户端IP
        client_ip = request.client.host if request.client else "unknown"
        
        # 检查速率限制（简化实现）
        current_time = int(time.time())
        window_start = current_time - (current_time % self.window_size)
        
        key = f"{client_ip}:{window_start}"
        
        if key in self.request_counts:
            self.request_counts[key] += 1
        else:
            self.request_counts[key] = 1
            # 清理旧的计数
            old_keys = [k for k in self.request_counts.keys() 
                       if int(k.split(':')[1]) < window_start - self.window_size]
            for old_key in old_keys:
                del self.request_counts[old_key]
        
        if self.request_counts[key] > self.requests_per_minute:
            logger.warning(
                f"Rate limit exceeded for IP {client_ip}: "
                f"{self.request_counts[key]} requests in current window"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": 429,
                        "message": "Too Many Requests",
                        "detail": f"Rate limit of {self.requests_per_minute} requests per minute exceeded",
                        "retry_after": self.window_size - (current_time % self.window_size)
                    }
                },
                headers={
                    "Retry-After": str(self.window_size - (current_time % self.window_size)),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": str(max(0, self.requests_per_minute - self.request_counts[key])),
                    "X-RateLimit-Reset": str(window_start + self.window_size)
                }
            )
        
        response = await call_next(request)
        
        # 添加速率限制头
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.requests_per_minute - self.request_counts[key]))
        response.headers["X-RateLimit-Reset"] = str(window_start + self.window_size)
        
        return response