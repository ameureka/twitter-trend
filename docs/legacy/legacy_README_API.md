# Twitter自动发布系统 - API版本

## 概述

本项目已重构为API化架构，支持前后端分离的设计。系统提供了完整的RESTful API接口和现代化的Web前端界面。

## 架构设计

### 后端 (API)
- **框架**: FastAPI
- **数据库**: SQLite (可扩展到PostgreSQL/MySQL)
- **认证**: API Key认证
- **文档**: 自动生成的OpenAPI文档

### 前端
- **技术栈**: 原生JavaScript + Tailwind CSS + Alpine.js
- **架构**: 单页应用 (SPA)
- **组件**: 模块化组件设计

## 项目结构

```
twitter-trend/
├── api/                    # API后端
│   ├── __init__.py
│   ├── main.py            # FastAPI主应用
│   ├── dependencies.py   # 依赖注入
│   ├── schemas.py         # Pydantic数据模型
│   └── routers/           # API路由
│       ├── __init__.py
│       ├── auth.py        # 认证相关
│       ├── dashboard.py   # 仪表板
│       ├── tasks.py       # 任务管理
│       └── projects.py    # 项目管理
├── frontend/              # Web前端
│   ├── index.html         # 主页面
│   ├── js/
│   │   ├── api.js         # API客户端
│   │   ├── app.js         # 主应用
│   │   └── components/    # 页面组件
│   │       ├── dashboard.js
│   │       ├── tasks.js
│   │       └── projects.js
│   └── css/               # 样式文件
├── app/                   # 原有核心逻辑
│   ├── main.py           # CLI入口(已扩展API支持)
│   ├── core/             # 核心功能
│   ├── models/           # 数据模型
│   └── ...
├── start_api.sh          # API启动脚本
├── scripts/
│   └── server/
│       └── start_api.py  # API启动器
└── requirements.txt      # 依赖包
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

复制环境配置文件：
```bash
cp .env.example .env
```

编辑 `.env` 文件，配置必要的参数：
```env
# 数据库配置
DATABASE_URL=sqlite:///./data/app.db

# API配置
API_HOST=127.0.0.1
API_PORT=8050
API_SECRET_KEY=your-secret-key-here

# Twitter API配置
TWITTER_API_KEY=your-api-key
TWITTER_API_SECRET=your-api-secret
# ... 其他配置
```

### 3. 启动API服务

#### 方法一：使用启动脚本（推荐）
```bash
./start_api.sh
```

#### 方法二：使用Python命令
```bash
python -m app.main api
```

#### 方法三：使用专用启动器
```bash
python scripts/server/start_api.py
```

### 4. 访问应用

- **Web界面**: http://localhost:8080
- **API文档**: http://localhost:8050/docs
- **ReDoc文档**: http://localhost:8050/redoc

## API接口

### 认证
- `GET /auth/verify` - 验证API密钥
- `GET /auth/me` - 获取当前用户信息
- `GET /auth/permissions` - 获取用户权限

### 仪表板
- `GET /dashboard/stats` - 获取统计数据
- `GET /dashboard/health` - 系统健康检查
- `GET /dashboard/recent-activity` - 最近活动
- `GET /dashboard/quick-stats` - 快速统计

### 任务管理
- `GET /tasks` - 获取任务列表
- `POST /tasks` - 创建新任务
- `GET /tasks/{task_id}` - 获取任务详情
- `PUT /tasks/{task_id}` - 更新任务
- `DELETE /tasks/{task_id}` - 删除任务
- `POST /tasks/{task_id}/execute` - 执行任务
- `POST /tasks/{task_id}/cancel` - 取消任务
- `POST /tasks/bulk-action` - 批量操作
- `GET /tasks/{task_id}/logs` - 获取任务日志

### 项目管理
- `GET /projects` - 获取项目列表
- `POST /projects` - 创建新项目
- `GET /projects/{project_id}` - 获取项目详情
- `PUT /projects/{project_id}` - 更新项目
- `DELETE /projects/{project_id}` - 删除项目
- `GET /projects/{project_id}/settings` - 获取项目设置
- `PUT /projects/{project_id}/settings` - 更新项目设置
- `GET /projects/{project_id}/sources` - 获取内容源
- `POST /projects/{project_id}/sources` - 添加内容源
- `GET /projects/{project_id}/analytics` - 获取项目分析

## 启动选项

### 命令行参数
```bash
python -m app.main api --help
```

选项：
- `--host`: API服务器地址 (默认: 127.0.0.1)
- `--port`: API服务器端口 (默认: 8050)
- `--debug`: 启用调试模式

### 启动脚本选项
```bash
./start_api.sh --help
```

选项：
- `-h, --host HOST`: API服务器地址
- `-p, --port PORT`: API服务器端口
- `-d, --debug`: 启用调试模式
- `-e, --env-file FILE`: 环境变量文件路径

## 开发模式

启用调试模式以获得更好的开发体验：

```bash
# 使用启动脚本
./start_api.sh -d

# 或使用命令行
python -m app.main api --debug
```

调试模式特性：
- 自动重载代码变更
- 详细的错误信息
- 增强的日志输出

## 生产部署

### 使用Gunicorn
```bash
pip install gunicorn
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### 使用Docker
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["python", "-m", "app.main", "api", "--host", "0.0.0.0"]
```

## 兼容性

### CLI模式
原有的CLI功能完全保留，可以继续使用：

```bash
# 扫描项目
python -m app.main scan --project myproject

# 发布内容
python -m app.main publish --project myproject

# 查看状态
python -m app.main status

# 健康检查
python -m app.main health
```

### 数据库
- 使用相同的数据库结构
- 无需数据迁移
- 支持CLI和API并行使用

## 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   # 查看端口占用
   lsof -i :8080
   
   # 使用其他端口
   ./start_api.sh -p 8080
   ```

2. **依赖包缺失**
   ```bash
   pip install -r requirements.txt
   ```

3. **数据库连接失败**
   - 检查数据库文件路径
   - 确认数据库文件权限
   - 查看日志获取详细错误信息

4. **API密钥认证失败**
   - 检查环境变量配置
   - 确认API密钥格式正确
   - 查看认证相关日志

### 日志查看

```bash
# 查看应用日志
tail -f logs/app.log

# 查看API访问日志
tail -f logs/api.log
```

## 贡献

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。