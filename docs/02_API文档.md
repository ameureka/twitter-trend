# API文档

## 概述

本项目提供完整的RESTful API接口，支持前后端分离的设计。系统基于FastAPI框架构建，提供自动生成的OpenAPI文档和现代化的Web前端界面。

### API特性
- **框架**: FastAPI
- **认证**: API Key认证
- **文档**: 自动生成的OpenAPI文档
- **格式**: JSON数据交换
- **版本**: v1.0

## 认证机制

所有API请求需要在请求头中包含API密钥：

```bash
curl -H "X-API-Key: your_api_key" http://localhost:8050/api/v1/tasks
```

### 认证配置

在 `.env` 文件中配置API密钥：

```env
API_API_KEY=your_secure_api_key_here
```

## API端点

### 基础信息

- **基础URL**: `http://localhost:8050/api/v1`
- **内容类型**: `application/json`
- **字符编码**: `UTF-8`

### 认证相关

#### 验证API密钥
```http
GET /api/v1/auth/verify
```

**响应示例**:
```json
{
  "status": "success",
  "message": "API key is valid",
  "user_info": {
    "permissions": ["read", "write", "admin"]
  }
}
```

#### 获取当前用户信息
```http
GET /api/v1/auth/me
```

#### 获取用户权限
```http
GET /api/v1/auth/permissions
```

### 仪表板

#### 获取统计数据
```http
GET /api/v1/dashboard/stats
```

**响应示例**:
```json
{
  "total_tasks": 150,
  "pending_tasks": 12,
  "completed_tasks": 120,
  "failed_tasks": 18,
  "total_projects": 8,
  "success_rate": 87.0,
  "last_24h_tasks": 25
}
```

#### 系统健康检查
```http
GET /api/v1/dashboard/health
```

**响应示例**:
```json
{
  "status": "healthy",
  "database": "connected",
  "twitter_api": "accessible",
  "gemini_api": "accessible",
  "disk_space": "85%",
  "memory_usage": "45%",
  "uptime": "2 days, 14 hours"
}
```

#### 最近活动
```http
GET /api/v1/dashboard/recent-activity
```

#### 快速统计
```http
GET /api/v1/dashboard/quick-stats
```

### 任务管理

#### 获取任务列表
```http
GET /api/v1/tasks
```

**查询参数**:
- `page`: 页码 (默认: 1)
- `limit`: 每页数量 (默认: 20)
- `status`: 任务状态过滤
- `project_id`: 项目ID过滤
- `language`: 语言过滤

**响应示例**:
```json
{
  "tasks": [
    {
      "id": 1,
      "project_id": 1,
      "content_path": "/path/to/content.json",
      "media_path": "/path/to/video.mp4",
      "language": "en",
      "status": "pending",
      "priority": 1,
      "scheduled_time": "2024-01-01T12:00:00Z",
      "created_at": "2024-01-01T10:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "limit": 20,
  "pages": 8
}
```

#### 创建新任务
```http
POST /api/v1/tasks
```

**请求体**:
```json
{
  "project_id": 1,
  "content_path": "/path/to/content.json",
  "media_path": "/path/to/video.mp4",
  "language": "en",
  "priority": 1,
  "scheduled_time": "2024-01-01T12:00:00Z"
}
```

#### 获取任务详情
```http
GET /api/v1/tasks/{task_id}
```

#### 更新任务
```http
PUT /api/v1/tasks/{task_id}
```

#### 删除任务
```http
DELETE /api/v1/tasks/{task_id}
```

#### 执行任务
```http
POST /api/v1/tasks/{task_id}/execute
```

#### 取消任务
```http
POST /api/v1/tasks/{task_id}/cancel
```

#### 批量操作
```http
POST /api/v1/tasks/bulk-action
```

**请求体示例**:
```json
{
  "action": "update_status",
  "task_ids": [1, 2, 3],
  "status": "paused"
}
```

或

```json
{
  "action": "create",
  "project_ids": [1, 2, 3],
  "schedule_time": "2024-01-01T12:00:00Z"
}
```

#### 获取任务日志
```http
GET /api/v1/tasks/{task_id}/logs
```

### 项目管理

#### 获取项目列表
```http
GET /api/v1/projects
```

**响应示例**:
```json
{
  "projects": [
    {
      "id": 1,
      "name": "maker_music_chuangxinyewu",
      "path": "/path/to/project",
      "last_scan": "2024-01-01T10:00:00Z",
      "task_count": 25,
      "status": "active"
    }
  ],
  "total": 8
}
```

#### 创建新项目
```http
POST /api/v1/projects
```

**请求体**:
```json
{
  "name": "new_project",
  "path": "/path/to/project",
  "description": "项目描述"
}
```

#### 获取项目详情
```http
GET /api/v1/projects/{project_id}
```

#### 更新项目
```http
PUT /api/v1/projects/{project_id}
```

#### 删除项目
```http
DELETE /api/v1/projects/{project_id}
```

#### 扫描项目
```http
POST /api/v1/projects/scan
```

**请求体**:
```json
{
  "project_id": 1,
  "force_rescan": false
}
```

#### 获取项目任务
```http
GET /api/v1/projects/{project_id}/tasks
```

#### 获取项目设置
```http
GET /api/v1/projects/{project_id}/settings
```

#### 更新项目设置
```http
PUT /api/v1/projects/{project_id}/settings
```

#### 获取内容源
```http
GET /api/v1/projects/{project_id}/sources
```

#### 添加内容源
```http
POST /api/v1/projects/{project_id}/sources
```

#### 获取项目分析
```http
GET /api/v1/projects/{project_id}/analytics
```

### 系统管理

#### 系统信息
```http
GET /api/v1/system/info
```

#### 重启系统
```http
POST /api/v1/system/restart
```

### 数据库管理

#### 初始化数据库
```http
POST /api/v1/database/initialize
```

#### 清理数据库
```http
POST /api/v1/database/clean
```

#### 备份数据库
```http
POST /api/v1/database/backup
```

#### 数据库统计
```http
GET /api/v1/database/stats
```

### 调度器管理

#### 启动调度器
```http
POST /api/v1/scheduler/start
```

#### 停止调度器
```http
POST /api/v1/scheduler/stop
```

#### 重启调度器
```http
POST /api/v1/scheduler/restart
```

#### 调度器状态
```http
GET /api/v1/scheduler/status
```

#### 调度器统计
```http
GET /api/v1/scheduler/stats
```

### 配置管理

#### 获取配置
```http
GET /api/v1/config
```

#### 更新配置
```http
PUT /api/v1/config
```

#### 重载配置
```http
POST /api/v1/config/reload
```

#### 配置信息
```http
GET /api/v1/config/info
```

### 性能监控

#### 获取性能指标
```http
GET /api/v1/monitoring/metrics
```

#### 获取告警信息
```http
GET /api/v1/monitoring/alerts
```

#### 健康状态
```http
GET /api/v1/monitoring/health
```

### 错误管理

#### 错误统计
```http
GET /api/v1/errors/stats
```

#### 最近错误
```http
GET /api/v1/errors/recent
```

#### 解决错误
```http
POST /api/v1/errors/{error_id}/resolve
```

## 状态码

### 成功状态码
- `200 OK`: 请求成功
- `201 Created`: 资源创建成功
- `204 No Content`: 请求成功，无返回内容

### 客户端错误
- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: 认证失败
- `403 Forbidden`: 权限不足
- `404 Not Found`: 资源不存在
- `409 Conflict`: 资源冲突
- `422 Unprocessable Entity`: 请求格式正确但语义错误

### 服务器错误
- `500 Internal Server Error`: 服务器内部错误
- `502 Bad Gateway`: 网关错误
- `503 Service Unavailable`: 服务不可用

## 错误响应格式

```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "参数 'project_id' 是必需的",
    "details": {
      "field": "project_id",
      "value": null
    }
  },
  "timestamp": "2024-01-01T12:00:00Z",
  "path": "/api/v1/tasks"
}
```

## 分页响应格式

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "pages": 8,
    "has_next": true,
    "has_prev": false
  }
}
```

## 使用示例

### JavaScript/Fetch

```javascript
// 获取任务列表
const response = await fetch('/api/v1/tasks', {
  headers: {
    'X-API-Key': 'your_api_key',
    'Content-Type': 'application/json'
  }
});
const data = await response.json();

// 创建新任务
const newTask = await fetch('/api/v1/tasks', {
  method: 'POST',
  headers: {
    'X-API-Key': 'your_api_key',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    project_id: 1,
    content_path: '/path/to/content.json',
    media_path: '/path/to/video.mp4',
    language: 'en'
  })
});
```

### Python/Requests

```python
import requests

headers = {
    'X-API-Key': 'your_api_key',
    'Content-Type': 'application/json'
}

# 获取任务列表
response = requests.get('http://localhost:8050/api/v1/tasks', headers=headers)
tasks = response.json()

# 创建新任务
new_task_data = {
    'project_id': 1,
    'content_path': '/path/to/content.json',
    'media_path': '/path/to/video.mp4',
    'language': 'en'
}
response = requests.post('http://localhost:8050/api/v1/tasks', 
                        json=new_task_data, headers=headers)
```

### cURL

```bash
# 获取任务列表
curl -H "X-API-Key: your_api_key" \
     http://localhost:8050/api/v1/tasks

# 创建新任务
curl -X POST \
     -H "X-API-Key: your_api_key" \
     -H "Content-Type: application/json" \
     -d '{
       "project_id": 1,
       "content_path": "/path/to/content.json",
       "media_path": "/path/to/video.mp4",
       "language": "en"
     }' \
     http://localhost:8080/api/v1/tasks
```

## 在线文档

启动服务后，可以通过以下地址查看交互式API文档：

- **Swagger UI**: http://localhost:8050/docs
- **ReDoc**: http://localhost:8050/redoc
- **OpenAPI Schema**: http://localhost:8050/openapi.json

---

**下一步**: 查看 [系统架构](03_系统架构.md) 了解详细的技术架构设计。