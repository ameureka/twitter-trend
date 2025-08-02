# 4. 数据库设计与 ORM 使用方法论

本文档详细阐述了项目的数据库设计方案、选择 SQLAlchemy 作为对象关系映射（ORM）工具的理由，以及在项目中实践数据访问的最佳方法。

## 4.1. 数据库选型：SQLite

在项目初期，我们选择了 SQLite 作为主要的数据库引擎。这是一个经过深思熟虑的决策，主要基于以下几点考量：

1.  **简易性与零管理成本**: SQLite 是一个无服务器的数据库引擎。它不需要独立的服务器进程，数据库本身只是一个单一的文件（`twitter_publisher.db`）。这极大地简化了开发环境的搭建、应用的部署以及日常的维护工作。

2.  **便携性与备份**: 由于数据库就是一个文件，备份和恢复操作变得极其简单，只需复制文件即可。这对于需要快速迁移或进行数据快照的场景非常有利。

3.  **性能满足需求**: 对于本项目的并发量和数据规模（中小型管理系统），SQLite 的性能完全足够。它的读写速度非常快，尤其是在单用户或低并发场景下。

4.  **通过 ORM 规避其局限性**: 我们通过 SQLAlchemy ORM 抽象了数据库的直接交互。这意味着，如果未来系统规模扩大，需要迁移到更强大的数据库（如 PostgreSQL 或 MySQL），我们只需要修改数据库连接字符串和少量方言特定的代码，而无需重写大量的业务逻辑和数据查询代码。

## 4.2. 数据模型设计 (SQLAlchemy Models)

我们在 `app/database/models.py` 中定义了所有的数据模型。这些模型是 Python 类，它们映射到数据库中的表结构。

### 4.2.1. `PublishingTask` 模型 (`publishing_tasks` 表)

这是系统的核心模型，代表了一个独立的发布任务。

```python
class PublishingTask(Base):
    __tablename__ = 'publishing_tasks'

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, index=True, nullable=False)
    media_path = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default='pending', index=True)
    scheduled_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)
    tweet_id = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)

    # Relationships
    logs = relationship("PublishingLog", back_populates="task")
```

**设计亮点**: 
-   **`media_path` 的唯一约束**: 从数据库层面保证了同一个媒体文件不会被重复创建任务，这是防止重复发布的根本性措施。
-   **索引 (`index=True`)**: 在经常用于查询条件的字段（如 `status`, `project_id`）上建立索引，大幅提升查询性能。
-   **详细的状态与时间戳**: `status`, `scheduled_at`, `published_at` 字段清晰地记录了任务的生命周期。
-   **错误追踪**: `error_message` 和 `retry_count` 为实现健壮的重试和错误排查机制提供了数据支持。
-   **关系 (`relationship`)**: 定义了与 `PublishingLog` 的一对多关系，方便地通过任务对象访问其所有相关的日志记录。

### 4.2.2. `PublishingLog` 模型 (`publishing_logs` 表)

该模型用于记录与每个任务相关的详细操作日志。

```python
class PublishingLog(Base):
    __tablename__ = 'publishing_logs'

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey('publishing_tasks.id'))
    level = Column(String, index=True)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    task = relationship("PublishingTask", back_populates="logs")
```

**设计亮点**:
-   **外键约束 (`ForeignKey`)**: 确保了每一条日志都必须关联到一个真实存在的任务，保证了数据的完整性。
-   **日志级别 (`level`)**: 允许对日志进行分类查询，例如，可以快速筛选出所有 `ERROR` 级别的日志进行分析。
-   **`Text` 类型**: `message` 字段使用 `Text` 类型，可以存储非常长的日志信息，如完整的 API 错误响应或堆栈跟踪。

## 4.3. 数据访问层 (Repository Pattern)

为了将业务逻辑与数据访问逻辑彻底解耦，我们引入了仓储模式（Repository Pattern）。

-   **实现**: `app/database/repository.py`
-   **理念**: Repository 封装了对数据模型的所有 CRUD（创建、读取、更新、删除）操作。业务逻辑层（如 `task_scheduler.py`）不直接与 SQLAlchemy 的 `Session` 对象交互，而是调用 Repository 提供的方法，如 `repository.create_task(...)` 或 `repository.get_task_by_status(...)`。

**为什么使用仓储模式？**

1.  **单一职责原则**: Repository 的唯一职责就是数据持久化。业务逻辑层则专注于实现业务规则，两者各司其职。
2.  **代码更清晰、可读性更高**: 业务代码读起来更像是自然语言（“获取待处理任务”），而不是一堆数据库查询语法。
3.  **易于测试**: 在进行单元测试时，我们可以轻松地用一个“模拟（Mock）”的 Repository 来替换真实的数据库 Repository。这样，我们就可以在不访问真实数据库的情况下测试业务逻辑，使得测试更快、更可靠。
4.  **集中管理查询逻辑**: 所有与 `PublishingTask` 相关的查询都集中在 `TaskRepository` 中。如果需要优化某个查询，我们只需要修改这一个地方，而不用在整个代码库中去寻找散落的查询语句。

**示例**: 

```python
# 在业务逻辑层中 (Good Practice)
def process_pending_tasks():
    tasks = task_repo.get_tasks_by_status('pending')
    for task in tasks:
        # ... process task

# 反面教材 (Bad Practice - 直接在业务逻辑中使用 Session)
def process_pending_tasks_bad():
    db = SessionLocal()
    try:
        tasks = db.query(PublishingTask).filter(PublishingTask.status == 'pending').all()
        for task in tasks:
            # ... process task
    finally:
        db.close()
```

## 4.4. 总结

项目的数据库设计遵循“简单、实用、可扩展”的原则。通过选择 SQLite 和 SQLAlchemy ORM，我们获得了一个开发迅速、维护简单的持久化方案。精心设计的数据模型保证了数据的完整性和查询效率。而仓储模式的引入，则从架构层面提升了代码的模块化程度、可测试性和长期可维护性，是整个后端设计的关键一环。