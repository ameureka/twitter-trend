#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强型系统管理API路由 - 集成优化后的系统组件

主要功能:
1. 数据库管理接口
2. 增强型调度器控制
3. 配置管理接口
4. 错误监控和统计
5. 系统健康检查
6. 性能监控接口
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from app.database.db_manager import DatabaseManager
from app.core.enhanced_scheduler import EnhancedTaskScheduler, TaskPriority
from app.utils.enhanced_config import get_enhanced_config
from app.utils.error_handler import get_error_handler, ErrorSeverity, ErrorCategory
from app.utils.performance_monitor import PerformanceMonitor
from api.dependencies import get_current_user
from api.schemas import BaseResponse

router = APIRouter(prefix="/api/system", tags=["系统管理"])

# 全局组件实例
db_manager = DatabaseManager()
scheduler = EnhancedTaskScheduler()
config_manager = get_enhanced_config()
error_handler = get_error_handler()
performance_monitor = PerformanceMonitor()


# Pydantic模型
class DatabaseInitRequest(BaseModel):
    """数据库初始化请求"""
    force_reset: bool = Field(False, description="是否强制重置数据库")
    create_backup: bool = Field(True, description="是否创建备份")


class DatabaseCleanRequest(BaseModel):
    """数据库清理请求"""
    clean_tasks: bool = Field(True, description="是否清理已完成的任务")
    clean_logs: bool = Field(True, description="是否清理旧日志")
    days_to_keep: int = Field(30, description="保留多少天的数据")


class SchedulerControlRequest(BaseModel):
    """调度器控制请求"""
    action: str = Field(..., description="操作类型: start/stop/restart")
    config: Optional[Dict[str, Any]] = Field(None, description="配置参数")


class TaskScheduleRequest(BaseModel):
    """任务调度请求"""
    task_ids: Optional[List[int]] = Field(None, description="指定任务ID列表")
    priority: str = Field("normal", description="任务优先级")
    delay_seconds: int = Field(0, description="延迟执行秒数")
    limit: Optional[int] = Field(None, description="批量调度限制")


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    updates: Dict[str, Any] = Field(..., description="配置更新项")
    save_to_file: bool = Field(True, description="是否保存到文件")


# 数据库管理接口
@router.post("/database/initialize")
async def initialize_database(
    request: DatabaseInitRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """初始化数据库"""
    try:
        # 在后台执行数据库初始化
        def init_task():
            return db_manager.initialize_database(request.force_reset)
            
        background_tasks.add_task(init_task)
        
        return JSONResponse({
            "success": True,
            "message": "数据库初始化任务已启动",
            "data": {
                "force_reset": request.force_reset,
                "create_backup": request.create_backup
            }
        })
        
    except Exception as e:
        error_info = error_handler.handle_error(
            e, 
            context={"endpoint": "initialize_database", "user": current_user.username},
            category=ErrorCategory.DATABASE
        )
        raise HTTPException(status_code=500, detail=f"数据库初始化失败: {str(e)}")


@router.post("/database/clean")
async def clean_database(
    request: DatabaseCleanRequest,
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """清理数据库"""
    try:
        result = db_manager.clean_database(
            clean_tasks=request.clean_tasks,
            clean_logs=request.clean_logs,
            days_to_keep=request.days_to_keep
        )
        
        return JSONResponse({
            "success": result['success'],
            "message": result['message'],
            "data": result.get('details', {})
        })
        
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "clean_database", "user": current_user.username},
            category=ErrorCategory.DATABASE
        )
        raise HTTPException(status_code=500, detail=f"数据库清理失败: {str(e)}")


@router.post("/database/backup")
async def backup_database(
    backup_name: Optional[str] = None,
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """备份数据库"""
    try:
        result = db_manager.backup_database(backup_name)
        
        return JSONResponse({
            "success": result['success'],
            "message": result['message'],
            "data": {
                "backup_path": result.get('backup_path', '')
            }
        })
        
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "backup_database", "user": current_user.username},
            category=ErrorCategory.DATABASE
        )
        raise HTTPException(status_code=500, detail=f"数据库备份失败: {str(e)}")


@router.get("/database/stats")
async def get_database_stats(
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """获取数据库统计信息"""
    try:
        stats = db_manager.get_database_stats()
        
        return JSONResponse({
            "success": True,
            "message": "获取数据库统计成功",
            "data": stats
        })
        
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "get_database_stats", "user": current_user.username},
            category=ErrorCategory.DATABASE
        )
        raise HTTPException(status_code=500, detail=f"获取数据库统计失败: {str(e)}")


# 调度器管理接口
@router.post("/scheduler/control")
async def control_scheduler(
    request: SchedulerControlRequest,
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """控制调度器"""
    try:
        if request.action == "start":
            result = scheduler.start()
        elif request.action == "stop":
            result = scheduler.stop()
        elif request.action == "restart":
            stop_result = scheduler.stop()
            if stop_result['success']:
                result = scheduler.start()
            else:
                result = stop_result
        else:
            raise ValueError(f"不支持的操作: {request.action}")
            
        return JSONResponse({
            "success": result['success'],
            "message": result['message'],
            "data": result.get('config', {})
        })
        
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "control_scheduler", "action": request.action, "user": current_user.username},
            category=ErrorCategory.SYSTEM
        )
        raise HTTPException(status_code=500, detail=f"调度器控制失败: {str(e)}")


@router.post("/scheduler/schedule")
async def schedule_tasks(
    request: TaskScheduleRequest,
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """调度任务"""
    try:
        # 解析优先级
        priority_map = {
            "low": TaskPriority.LOW,
            "normal": TaskPriority.NORMAL,
            "high": TaskPriority.HIGH,
            "urgent": TaskPriority.URGENT
        }
        priority = priority_map.get(request.priority.lower(), TaskPriority.NORMAL)
        
        if request.task_ids:
            # 调度指定任务
            scheduled_count = 0
            for task_id in request.task_ids:
                if scheduler.schedule_task(task_id, priority, request.delay_seconds):
                    scheduled_count += 1
                    
            result = {
                "success": True,
                "scheduled_count": scheduled_count,
                "total_requested": len(request.task_ids)
            }
        else:
            # 批量调度
            result = scheduler.schedule_batch(request.limit)
            
        return JSONResponse({
            "success": result['success'],
            "message": f"任务调度完成，调度了 {result.get('scheduled_count', 0)} 个任务",
            "data": result
        })
        
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "schedule_tasks", "user": current_user.username},
            category=ErrorCategory.BUSINESS_LOGIC
        )
        raise HTTPException(status_code=500, detail=f"任务调度失败: {str(e)}")


@router.get("/scheduler/stats")
async def get_scheduler_stats(
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """获取调度器统计信息"""
    try:
        stats = scheduler.get_stats()
        
        return JSONResponse({
            "success": True,
            "message": "获取调度器统计成功",
            "data": stats
        })
        
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "get_scheduler_stats", "user": current_user.username},
            category=ErrorCategory.SYSTEM
        )
        raise HTTPException(status_code=500, detail=f"获取调度器统计失败: {str(e)}")


# 配置管理接口
@router.get("/config")
async def get_config(
    key: Optional[str] = None,
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """获取配置"""
    try:
        if key:
            value = config_manager.get(key)
            data = {key: value}
        else:
            data = config_manager.config_data
            
        return JSONResponse({
            "success": True,
            "message": "获取配置成功",
            "data": data
        })
        
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "get_config", "key": key, "user": current_user.username},
            category=ErrorCategory.SYSTEM
        )
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.post("/config/update")
async def update_config(
    request: ConfigUpdateRequest,
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """更新配置"""
    try:
        success = config_manager.update(request.updates, request.save_to_file)
        
        if success:
            return JSONResponse({
                "success": True,
                "message": f"配置更新成功，更新了 {len(request.updates)} 项",
                "data": {
                    "updated_keys": list(request.updates.keys()),
                    "saved_to_file": request.save_to_file
                }
            })
        else:
            raise Exception("配置更新失败")
            
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "update_config", "updates": request.updates, "user": current_user.username},
            category=ErrorCategory.SYSTEM
        )
        raise HTTPException(status_code=500, detail=f"配置更新失败: {str(e)}")


@router.get("/config/info")
async def get_config_info(
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """获取配置信息"""
    try:
        info = config_manager.get_config_info()
        
        return JSONResponse({
            "success": True,
            "message": "获取配置信息成功",
            "data": info
        })
        
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "get_config_info", "user": current_user.username},
            category=ErrorCategory.SYSTEM
        )
        raise HTTPException(status_code=500, detail=f"获取配置信息失败: {str(e)}")


@router.post("/config/reload")
async def reload_config(
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """重新加载配置"""
    try:
        config_manager._reload_config()
        
        return JSONResponse({
            "success": True,
            "message": "配置重新加载成功",
            "data": {
                "reload_time": datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "reload_config", "user": current_user.username},
            category=ErrorCategory.SYSTEM
        )
        raise HTTPException(status_code=500, detail=f"配置重新加载失败: {str(e)}")


# 错误监控接口
@router.get("/errors/stats")
async def get_error_stats(
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """获取错误统计"""
    try:
        stats = error_handler.get_error_stats()
        
        return JSONResponse({
            "success": True,
            "message": "获取错误统计成功",
            "data": stats
        })
        
    except Exception as e:
        # 这里不使用error_handler，避免递归
        raise HTTPException(status_code=500, detail=f"获取错误统计失败: {str(e)}")


@router.get("/errors/recent")
async def get_recent_errors(
    limit: int = 50,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """获取最近错误"""
    try:
        recent_errors = list(error_handler.error_history)[-limit:]
        
        # 过滤条件
        if severity:
            recent_errors = [e for e in recent_errors if e.severity.value == severity]
        if category:
            recent_errors = [e for e in recent_errors if e.category.value == category]
            
        # 转换为字典格式
        error_data = []
        for error in recent_errors:
            error_data.append({
                "error_id": error.error_id,
                "timestamp": error.timestamp.isoformat(),
                "severity": error.severity.value,
                "category": error.category.value,
                "message": error.message,
                "exception_type": error.exception_type,
                "retry_count": error.retry_count,
                "resolved": error.resolved,
                "recovery_action": error.recovery_action.value if error.recovery_action else None
            })
            
        return JSONResponse({
            "success": True,
            "message": f"获取最近 {len(error_data)} 个错误",
            "data": {
                "errors": error_data,
                "total_count": len(error_handler.error_history),
                "filtered_count": len(error_data)
            }
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取最近错误失败: {str(e)}")


@router.post("/errors/{error_id}/resolve")
async def resolve_error(
    error_id: str,
    resolution_note: Optional[str] = None,
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """标记错误为已解决"""
    try:
        success = error_handler.resolve_error(error_id, resolution_note)
        
        if success:
            return JSONResponse({
                "success": True,
                "message": f"错误 {error_id} 已标记为解决",
                "data": {
                    "error_id": error_id,
                    "resolved_by": current_user.username,
                    "resolution_time": datetime.now().isoformat()
                }
            })
        else:
            raise HTTPException(status_code=404, detail=f"错误 {error_id} 不存在")
            
    except HTTPException:
        raise
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "resolve_error", "error_id": error_id, "user": current_user.username},
            category=ErrorCategory.SYSTEM
        )
        raise HTTPException(status_code=500, detail=f"标记错误解决失败: {str(e)}")


# 性能监控接口
@router.get("/performance/metrics")
async def get_performance_metrics(
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """获取性能指标"""
    try:
        metrics = performance_monitor.get_metrics()
        
        return JSONResponse({
            "success": True,
            "message": "获取性能指标成功",
            "data": metrics
        })
        
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "get_performance_metrics", "user": current_user.username},
            category=ErrorCategory.SYSTEM
        )
        raise HTTPException(status_code=500, detail=f"获取性能指标失败: {str(e)}")


# 系统健康检查
@router.get("/health")
async def health_check() -> JSONResponse:
    """系统健康检查"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        # 检查数据库
        try:
            db_stats = db_manager.get_database_stats()
            health_status["components"]["database"] = {
                "status": "healthy",
                "details": db_stats
            }
        except Exception as e:
            health_status["components"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
            
        # 检查调度器
        try:
            scheduler_stats = scheduler.get_stats()
            health_status["components"]["scheduler"] = {
                "status": "healthy" if scheduler_stats["is_running"] else "stopped",
                "details": scheduler_stats
            }
            if not scheduler_stats["is_running"]:
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["components"]["scheduler"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
            
        # 检查错误率
        try:
            error_stats = error_handler.get_error_stats()
            recent_errors = error_stats.get("recent_24h", 0)
            critical_errors = error_stats.get("by_severity", {}).get("critical", 0)
            
            if critical_errors > 0:
                health_status["status"] = "unhealthy"
            elif recent_errors > 100:
                health_status["status"] = "degraded"
                
            health_status["components"]["error_monitoring"] = {
                "status": "healthy",
                "recent_errors": recent_errors,
                "critical_errors": critical_errors
            }
        except Exception as e:
            health_status["components"]["error_monitoring"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            
        return JSONResponse({
            "success": True,
            "message": f"系统状态: {health_status['status']}",
            "data": health_status
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"健康检查失败: {str(e)}",
                "data": {
                    "status": "unhealthy",
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)
                }
            }
        )


# 系统信息接口
@router.get("/info")
async def get_system_info(
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """获取系统信息"""
    try:
        import platform
        import psutil
        import sys
        
        system_info = {
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor()
            },
            "python": {
                "version": sys.version,
                "executable": sys.executable
            },
            "resources": {
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                }
            },
            "application": {
                "config_path": str(config_manager.config_path),
                "environment": config_manager.environment,
                "database_path": config_manager.get('database.path'),
                "project_path": config_manager.get('project_base_path')
            }
        }
        
        return JSONResponse({
            "success": True,
            "message": "获取系统信息成功",
            "data": system_info
        })
        
    except Exception as e:
        error_info = error_handler.handle_error(
            e,
            context={"endpoint": "get_system_info", "user": current_user.username},
            category=ErrorCategory.SYSTEM
        )
        raise HTTPException(status_code=500, detail=f"获取系统信息失败: {str(e)}")