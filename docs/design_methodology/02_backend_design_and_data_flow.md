# 2. 后端设计与数据流

本文档深入探讨后端系统的架构设计、模块职责、数据流动路径以及与外部服务的交互方式。

## 2.1. 后端模块化架构

后端遵循分层架构，将不同职责的代码清晰地分离到独立的模块中，以实现高内聚、低耦合的设计目标。

-   **`api/main.py`**: 应用主入口。负责初始化 FastAPI 应用，加载中间件，并挂载所有功能路由（Routers）。
-   **`api/routers/`**: API 路由层。每个文件（如 `tasks.py`, `projects.py`, `logs.py`）定义了一组相关的 API 端点。该层负责处理 HTTP 请求、验证输入数据（通过 Pydantic 模型），并调用业务逻辑层的服务。它不包含任何业务逻辑，只做请求的派发和响应的格式化。
-   **`app/core/`**: 核心业务逻辑层。这里是系统核心功能的实现所在地，例如 `task_scheduler.py` 负责任务调度，`publisher.py` 负责与 Twitter API 交互，`content_generator.py` 负责调用 AI 生成内容。这些模块封装了复杂的业务规则。
-   **`app/database/`**: 数据访问层。包含 `database.py`（数据库连接和会话管理）、`models.py`（SQLAlchemy 的 ORM 模型定义）和 `repository.py`（封装了对数据库的 CRUD 操作）。业务逻辑层通过 Repository 与数据库交互，完全不接触底层的数据库会话和 SQL 语句。
-   **`app/utils/`**: 工具模块。提供项目范围内的通用功能，如日志记录 (`logger.py`)、配置加载 (`config.py`)、全局错误处理 (`error_handler.py`) 等。

## 2.2. 核心数据流

理解系统的核心数据流是掌握其工作原理的关键。以下是两个典型场景的数据流分析。

### 2.2.1. 场景一：创建一个新的发布任务

1.  **用户操作**: 用户在前端界面选择一个项目，点击“创建新任务”。
2.  **前端请求**: 前端 `tasks.js` 组件向后端发送 `POST /api/tasks/` 请求，请求体中包含项目 ID 等信息。
3.  **API 路由层**: `api/routers/tasks.py` 中的相应端点接收到请求。Pydantic 模型自动验证请求数据的有效性。
4.  **业务逻辑层**: 路由调用 `app/core/project_manager.py` 中的服务函数。该函数执行以下操作：
    a.  验证项目是否存在。
    b.  扫描项目目录，找到符合条件的媒体文件。
    c.  为新发现的媒体文件在数据库中创建任务记录（状态为 'pending'）。
5.  **数据访问层**: `project_manager` 通过 `app/database/repository.py` 提供的接口，将新的任务数据写入 `publishing_tasks` 表。
6.  **数据库**: SQLAlchemy 将 Python 对象转换为 SQL `INSERT` 语句，在 `twitter_publisher.db` 文件中创建新记录。
7.  **响应返回**: 任务创建成功后，API 层返回 `201 Created` 状态码和新创建任务的详细信息。
8.  **前端更新**: 前端接收到响应，动态更新任务列表，向用户展示新创建的任务。

### 2.2.2. 场景二：执行一个待发布的任务

1.  **系统调度**: `app/core/task_scheduler.py` 中的后台调度器（例如，基于 `apscheduler`）按预设频率（如每分钟）触发。
2.  **任务查询**: 调度器调用 `app/database/repository.py`，查询数据库中状态为 'pending' 且计划发布时间已到的任务。
3.  **内容生成**: 对于查询到的任务，调度器调用 `app/core/content_generator.py`。
    a.  `content_generator` 读取与任务关联的元数据（如 JSON 文件）。
    b.  如果需要，它会调用外部 AI API（如 Gemini）生成推文文本。
4.  **内容发布**: 获得推文文本和媒体文件路径后，调度器调用 `app/core/publisher.py`。
    a.  `publisher` 使用 `tweepy` 库连接到 Twitter API。
    b.  它首先上传媒体文件，然后发布带有文本和媒体引用的推文。
5.  **状态更新**: 发布完成后，`publisher` 返回发布结果（成功或失败）。调度器根据结果更新任务在数据库中的状态（'published' 或 'failed'），并记录详细的发布日志。
    a.  成功：更新 `publishing_tasks` 表中的 `status` 和 `published_at` 字段。
    b.  失败：更新 `status` 字段，并将错误信息写入 `publishing_logs` 表。
6.  **日志记录**: 整个过程中的关键步骤（任务开始、内容生成、发布尝试、最终结果）都被 `app/utils/logger.py` 记录到日志文件中。

## 2.3. 数据库设计

数据库是系统的“记忆”。我们通过 SQLAlchemy ORM 设计了清晰、规范化的数据模型。

-   **`PublishingTask` (`publishing_tasks` 表)**: 存储所有发布任务的核心信息。
    -   `id`: 主键。
    -   `project_id`: 关联到项目。
    -   `media_path`: 媒体文件的唯一路径，设有唯一约束防止重复。
    -   `status`: 任务状态 (e.g., `pending`, `processing`, `published`, `failed`)。
    -   `scheduled_at`: 计划发布时间。
    -   `published_at`: 实际发布时间。
    -   `tweet_id`: 发布成功后返回的推文 ID。
-   **`PublishingLog` (`publishing_logs` 表)**: 记录任务执行的详细日志。
    -   `id`: 主键。
    -   `task_id`: 关联到具体的任务。
    -   `level`: 日志级别 (e.g., `INFO`, `ERROR`)。
    -   `message`: 详细的日志信息，包含错误堆栈等。
    -   `created_at`: 日志创建时间。

这种设计将核心任务信息与过程日志分离，使得核心表保持高效，同时为问题排查提供了详尽的追溯数据。

## 2.4. 总结

后端系统通过分层和模块化的设计，实现了清晰的职责分离和高效的数据流动。以 API 为入口，业务逻辑为核心，数据库为基础，构建了一个健壮、可维护且易于扩展的服务端应用。这套设计不仅支撑了当前的功能需求，也为未来的发展奠定了坚实的基础。