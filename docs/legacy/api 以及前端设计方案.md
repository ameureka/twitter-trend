好的，我们来设计一套与现有后端逻辑解耦的 API 和前端界面方案。这个方案将遵循您的要求：功能简洁、模块化、不影响核心功能，并采用 Tailwind CSS 风格。

---

### **API 与前端界面设计方案**

#### **一、 核心设计原则**

1.  **完全解耦 (Decoupling)**: API 和前端将是独立的模块。核心发布逻辑 (`app/core`) 完全不知道 API 的存在。API 层通过调用核心模块的服务或直接与数据库交互来提供数据，但不包含核心业务逻辑本身。
2.  **轻量级与非侵入性**: 前端是一个简单的单页面应用 (SPA)，通过异步请求 (AJAX/Fetch) 与 API 交互。API 服务可以与核心的 CLI 应用并存，甚至可以由同一个 Python 进程在不同线程中提供服务。
3.  **API 优先 (API-First)**: 我们首先定义 API 的端点（Endpoints）和数据结构（Schemas），然后再构建前端来消费这些 API。这确保了前后端职责清晰。
4.  **安全性**: API 将通过之前设计的 `api_keys` 表进行认证，保护数据接口不被未授权访问。

#### **二、 模块化文件结构设计**

为了不影响现有项目，我们将新增 `api/` 和 `frontend/` 两个顶级目录。

```
twitter-auto-publisher/
├── app/
│   └── ... (核心发布逻辑，保持不变)
├── api/
│   ├── __init__.py
│   ├── main.py                # API 服务主入口 (FastAPI)
│   ├── dependencies.py        # 依赖注入 (如获取数据库会话, API Key认证)
│   ├── routers/               # 按功能划分路由
│   │   ├── __init__.py
│   │   ├── dashboard.py         # 仪表盘数据路由
│   │   ├── tasks.py             # 任务管理路由
│   │   └── projects.py          # 项目管理路由
│   └── schemas.py             # Pydantic 数据模型 (用于请求和响应)
│
├── frontend/
│   ├── dist/                  # 编译后的前端文件
│   │   ├── index.html
│   │   └── assets/
│   │       ├── index.css
│   │       └── index.js
│   ├── src/                   # 前端源代码 (例如使用 Vue, React 或原生 JS)
│   │   ├── components/
│   │   │   ├── Dashboard.js
│   │   │   ├── TaskList.js
│   │   │   └── ProjectSettings.js
│   │   ├── app.js
│   │   └── index.css
│   ├── package.json
│   ├── tailwind.config.js
│   └── ...
│
└── ... (其他项目文件)
```

#### **三、 API 设计 (使用 FastAPI)**

我们将使用 **FastAPI**，因为它性能高、开发快，并且能自动生成交互式 API 文档 (基于 OpenAPI/Swagger)。

**1. 技术栈**
*   **框架**: `FastAPI`
*   **数据验证**: `Pydantic` (FastAPI 内置)
*   **服务器**: `Uvicorn`

**2. API 端点 (Endpoints)**

---
**认证**: 所有请求都需要在 Header 中提供 `X-API-Key: <your_key>`。

---

**模块: `dashboard.py`**

*   **GET `/api/v1/dashboard/stats`**: 获取仪表盘的核心统计数据。
    *   **响应 (`schemas.DashboardStats`)**:
        ```json
        {
          "total_tasks": 1200,
          "pending_tasks": 50,
          "success_last_24h": 96,
          "failed_last_24h": 4,
          "avg_publish_time_seconds": 45.5,
          "projects_count": 5
        }
        ```

*   **GET `/api/v1/dashboard/hourly_activity`**: 获取最近 N 小时的发布活动数据，用于图表展示。
    *   **查询参数**: `hours=24`
    *   **响应 (List[`schemas.HourlyActivity`])**:
        ```json
        [
          { "hour": "2023-10-27T15:00:00Z", "successful": 4, "failed": 0 },
          { "hour": "2023-10-27T16:00:00Z", "successful": 5, "failed": 1 },
          ...
        ]
        ```

---
**模块: `tasks.py`**

*   **GET `/api/v1/tasks`**: 分页获取任务列表。
    *   **查询参数**: `page=1`, `per_page=20`, `status='pending'`, `project_id=1`
    *   **响应 (List[`schemas.Task`])**:
        ```json
        {
          "tasks": [
            {
              "id": 101,
              "project_name": "maker_music_chuangxinyewu",
              "media_path": "/path/to/video.mp4",
              "status": "pending",
              "scheduled_at": "2023-10-28T10:00:00Z",
              "priority": 0,
              "retry_count": 0
            }
          ],
          "pagination": { "total_items": 50, "total_pages": 3, "current_page": 1 }
        }
        ```

---
**模块: `projects.py`**

*   **GET `/api/v1/projects`**: 获取所有项目的列表和基本信息。
    *   **响应 (List[`schemas.Project`])**:
        ```json
        [
          {
            "id": 1,
            "name": "maker_music_chuangxinyewu",
            "description": "创新业务视频项目",
            "source_count": 2,
            "total_items": 100,
            "used_items": 20
          }
        ]
        ```

*   **GET `/api/v1/projects/{project_id}/settings`**: 获取单个项目的详细设置（模拟）。
    *   **响应 (`schemas.ProjectSettings`)**:
        ```json
        {
          "project_id": 1,
          "ai_enhancement_enabled": true,
          "publishing_interval_min": 15,
          "publishing_interval_max": 30,
          "target_languages": ["en", "cn"]
        }
        ```

**3. 示例代码 (`api/main.py` and `api/routers/dashboard.py`)**

```python
# api/main.py
from fastapi import FastAPI
from .routers import dashboard, tasks, projects

app = FastAPI(title="Twitter Auto Publisher API")

# 包含各个路由模块
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(tasks.router, prefix="/api/v1", tags=["Tasks"])
app.include_router(projects.router, prefix="/api/v1", tags=["Projects"])

@app.get("/")
def read_root():
    return {"message": "API is running. Go to /docs for documentation."}

# api/routers/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...app.database import models
from ..dependencies import get_db, api_key_auth
from .. import schemas

router = APIRouter(dependencies=[Depends(api_key_auth)])

@router.get("/dashboard/stats", response_model=schemas.DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    # ... 在这里编写从数据库查询并计算统计数据的逻辑 ...
    # 例如：
    total_tasks = db.query(models.PublishingTask).count()
    # ... 其他统计 ...
    return schemas.DashboardStats(total_tasks=total_tasks, ...)
```

#### **四、 前端界面设计 (使用原生 JS + Tailwind CSS)**

为保持轻量，我们不引入大型框架，只用原生 JavaScript 和 Tailwind CSS 构建一个简单的 SPA。

**1. 页面布局与组件**

页面将采用经典的“侧边栏 + 主内容区”布局。

*   **`index.html` (骨架)**:
    ```html
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Twitter Publisher Dashboard</title>
        <link href="/assets/index.css" rel="stylesheet">
    </head>
    <body class="bg-gray-100 font-sans">
        <div class="flex h-screen">
            <!-- Sidebar -->
            <aside class="w-64 bg-gray-800 text-white p-4">
                <h1 class="text-2xl font-bold mb-8">Publisher</h1>
                <nav id="main-nav">
                    <a href="#dashboard" class="block py-2.5 px-4 rounded transition duration-200 hover:bg-gray-700">Dashboard</a>
                    <a href="#tasks" class="block py-2.5 px-4 rounded transition duration-200 hover:bg-gray-700">Tasks</a>
                    <a href="#projects" class="block py-2.5 px-4 rounded transition duration-200 hover:bg-gray-700">Projects</a>
                </nav>
            </aside>
            <!-- Main Content -->
            <main id="main-content" class="flex-1 p-10 overflow-y-auto">
                <!-- 动态内容将在这里加载 -->
            </main>
        </div>
        <script src="/assets/index.js"></script>
    </body>
    </html>
    ```

*   **内容区组件 (由 JS 动态生成)**:

    1.  **Dashboard 组件 (`#dashboard`)**:
        *   **统计卡片**: 一排卡片显示核心统计数据 (Pending Tasks, Success 24h 等)。使用 `flexbox` 和 `grid` 布局，卡片有阴影、圆角等 Tailwind 效果。
        *   **活动图表**: 使用轻量级图表库（如 **`Chart.js`** 或 **`ApexCharts`**）渲染 `/api/v1/dashboard/hourly_activity` 返回的数据，展示发布频率。

    2.  **Tasks 列表组件 (`#tasks`)**:
        *   **过滤栏**: 包含状态选择 (`<select>`) 和项目选择 (`<select>`) 的下拉框。
        *   **任务表格**: 一个用 Tailwind CSS 美化过的表格 (`<table>`)，动态填充从 `/api/v1/tasks` 获取的数据。
        *   **状态徽章**: 任务状态字段使用不同颜色的 Tailwind 徽章（如 `bg-yellow-200 text-yellow-800` for 'pending'）。
        *   **分页控件**: 简单的“上一页”和“下一页”按钮。

    3.  **Projects 设置组件 (`#projects`)**:
        *   **项目列表**: 一个卡片列表，每个卡片代表一个项目，显示项目名称、描述和进度条（`used_items / total_items`）。
        *   **设置表单 (只读)**: 点击项目卡片，可以弹出一个模态框 (Modal) 或在下方展开一个区域，显示从 `/api/v1/projects/{id}/settings` 获取的只读参数。

**2. 核心 JavaScript 逻辑 (`src/app.js`)**

```javascript
// src/app.js

const API_BASE_URL = '/api/v1';
const API_KEY = 'YOUR_TEST_API_KEY'; // 在实际应用中，这应该通过登录或配置获取

const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
};

// --- API 调用函数 ---
async function fetchData(endpoint) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, { headers });
    if (!response.ok) throw new Error('Network response was not ok');
    return response.json();
}

// --- 渲染函数 ---
async function renderDashboard() {
    const stats = await fetchData('/dashboard/stats');
    const content = `
        <h2 class="text-3xl font-bold mb-6">Dashboard</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div class="bg-white p-6 rounded-lg shadow-md">
                <h3 class="text-gray-500">Pending Tasks</h3>
                <p class="text-3xl font-bold">${stats.pending_tasks}</p>
            </div>
            <!-- 其他卡片... -->
        </div>
        <div class="mt-8 bg-white p-6 rounded-lg shadow-md">
            <h3 class="font-bold mb-4">Hourly Activity</h3>
            <canvas id="activityChart"></canvas>
        </div>
    `;
    document.getElementById('main-content').innerHTML = content;
    // ... 调用图表库渲染 #activityChart
}

// --- 路由逻辑 ---
function handleRouting() {
    const hash = window.location.hash || '#dashboard';
    const mainContent = document.getElementById('main-content');
    mainContent.innerHTML = '<div class="text-center text-gray-500">Loading...</div>';

    switch (hash) {
        case '#dashboard':
            renderDashboard();
            break;
        case '#tasks':
            // renderTasks();
            break;
        // ... 其他路由
    }
}

// --- 初始化 ---
window.addEventListener('hashchange', handleRouting);
window.addEventListener('load', handleRouting);

```

#### **五、 运行与集成**

1.  **API 服务**: 可以通过 `uvicorn api.main:app --reload` 启动 API 服务。
2.  **前端开发**: 在 `frontend/` 目录运行 `npm install`，然后使用一个简单的开发服务器（如 `live-server`）来提供 `index.html`。
3.  **集成**: 为了简化部署，FastAPI 可以配置为同时提供静态文件服务。
    ```python
    # api/main.py
    from fastapi.staticfiles import StaticFiles

    # ... 其他代码 ...
    
    # 将前端编译后的 dist 目录挂载到根路径
    app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
    ```
    这样，启动 Uvicorn 后，访问服务器根 URL 就会显示前端界面，而对 `/api/...` 的请求则会被 FastAPI 处理。这种方式非常适合将整个应用打包成一个单独的服务。

这个设计方案提供了一个清晰、模块化且可行的路径，让您能够在不干扰核心功能的前提下，为系统增加一个现代化的监控和管理界面。