#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twitter自动发布系统 API 服务主入口
使用FastAPI框架提供RESTful API接口
"""

import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.routers import dashboard, tasks, projects, auth, logs
from api.dependencies import get_settings
from api.middleware import (
    ErrorHandlingMiddleware, 
    SecurityHeadersMiddleware, 
    RateLimitMiddleware
)

# 创建FastAPI应用实例
app = FastAPI(
    title="Twitter Auto Publisher API",
    description="Twitter自动发布系统的RESTful API接口",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# 配置CORS中间件（必须在其他中间件之前）
settings = get_settings()
# 临时允许所有来源以解决开发环境的CORS问题
allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 添加自定义中间件（按执行顺序）
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
# 暂时禁用速率限制以便测试
# app.add_middleware(RateLimitMiddleware, requests_per_minute=120)  # 每分钟120请求

@app.get("/api")
def api_root():
    """API根路径"""
    return {
        "message": "Twitter Auto Publisher API is running",
        "version": "1.0.0",
        "docs": "/api/docs",
        "redoc": "/api/redoc"
    }

@app.get("/api/health")
def health_check():
    """健康检查端点（无需认证）"""
    try:
        # 简单的数据库连接测试
        from api.dependencies import get_database_manager
        db_manager = get_database_manager()
        session = db_manager.get_session()
        session.execute("SELECT 1")
        session.close()
        db_status = "healthy"
    except Exception as e:
        db_status = "unhealthy"
    
    return {
        "status": "healthy", 
        "service": "twitter-auto-publisher-api",
        "database": db_status,
        "version": "1.0.0"
    }

# 包含各个路由模块（注意顺序：具体路由在前，参数化路由在后）
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(projects.router, prefix="/api", tags=["Projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])

# 挂载前端静态文件（如果存在）
frontend_dist = project_root / "frontend"
if frontend_dist.exists():
    # 挂载前端资源目录
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    
    src_dir = frontend_dist / "src"
    if src_dir.exists():
        app.mount("/src", StaticFiles(directory=str(src_dir)), name="src")

@app.get("/")
def root():
    """根路径直接返回前端页面"""
    if frontend_dist.exists():
        from fastapi.responses import FileResponse
        return FileResponse(str(frontend_dist / "index.html"))
    else:
        return {
            "message": "欢迎使用 Twitter 自动发布系统",
            "service": "Twitter Auto Publisher",
            "version": "1.0.0",
            "status": "running",
            "endpoints": {
                "api_docs": "/api/docs",
                "api_redoc": "/api/redoc",
                "health_check": "/api/health",
                "api_root": "/api"
            }
        }

# 异常处理
@app.exception_handler(404)
def not_found_handler(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=404,
        content={"error": "Not Found", "message": "The requested resource was not found"}
    )

@app.exception_handler(500)
def internal_error_handler(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": "An internal server error occurred"}
    )

if __name__ == "__main__":
    import uvicorn
    
    # 获取配置
    settings = get_settings()
    
    # 启动服务器
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )