# 当前数据库表结构

本文档记录了当前实际数据库中的表结构定义，导出时间：2025-01-20

## 数据库版本管理表

### schema_version
```sql
CREATE TABLE schema_version (
    id INTEGER PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    applied_at DATETIME NOT NULL
);
```

## 核心业务表

### 1. users (用户表)
```sql
CREATE TABLE users (
    id INTEGER NOT NULL, 
    username VARCHAR(255) NOT NULL, 
    role VARCHAR(50) NOT NULL, 
    created_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (username)
);
```

### 2. api_keys (API密钥表)
```sql
CREATE TABLE api_keys (
    id INTEGER NOT NULL, 
    user_id INTEGER NOT NULL, 
    key_hash VARCHAR(255) NOT NULL, 
    permissions TEXT, 
    last_used DATETIME, 
    is_active BOOLEAN NOT NULL, 
    created_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (key_hash)
);
```

### 3. projects (项目表)
```sql
CREATE TABLE projects (
    id INTEGER NOT NULL, 
    user_id INTEGER NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    description TEXT, 
    created_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_user_project_name UNIQUE (user_id, name), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);
```

### 4. content_sources (内容源表)
```sql
CREATE TABLE content_sources (
    id INTEGER NOT NULL, 
    project_id INTEGER NOT NULL, 
    source_type VARCHAR(50) NOT NULL, 
    path_or_identifier TEXT NOT NULL, 
    total_items INTEGER, 
    used_items INTEGER, 
    last_scanned DATETIME, 
    created_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id)
);
```

### 5. publishing_tasks (发布任务表)
```sql
CREATE TABLE publishing_tasks (
    id INTEGER NOT NULL, 
    project_id INTEGER NOT NULL, 
    source_id INTEGER NOT NULL, 
    media_path TEXT NOT NULL, 
    content_data TEXT NOT NULL, 
    status VARCHAR(50) NOT NULL, 
    scheduled_at DATETIME NOT NULL, 
    priority INTEGER NOT NULL, 
    retry_count INTEGER NOT NULL, 
    version INTEGER NOT NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_project_media UNIQUE (project_id, media_path), 
    FOREIGN KEY(project_id) REFERENCES projects (id), 
    FOREIGN KEY(source_id) REFERENCES content_sources (id)
);
```

#### 索引
```sql
CREATE INDEX ix_tasks_project_status ON publishing_tasks (project_id, status);
CREATE INDEX ix_tasks_status_scheduled_priority ON publishing_tasks (status, scheduled_at, priority);
```

### 6. publishing_logs (发布日志表)
```sql
CREATE TABLE publishing_logs (
    id INTEGER NOT NULL, 
    task_id INTEGER NOT NULL, 
    tweet_id VARCHAR(255), 
    tweet_content TEXT, 
    published_at DATETIME NOT NULL, 
    status VARCHAR(50) NOT NULL, 
    error_message TEXT, 
    duration_seconds FLOAT, 
    PRIMARY KEY (id), 
    FOREIGN KEY(task_id) REFERENCES publishing_tasks (id)
);
```

### 7. analytics_hourly (小时分析数据表)
```sql
CREATE TABLE analytics_hourly (
    id INTEGER NOT NULL, 
    hour_timestamp DATETIME NOT NULL, 
    project_id INTEGER NOT NULL, 
    successful_tasks INTEGER NOT NULL, 
    failed_tasks INTEGER NOT NULL, 
    total_duration_seconds FLOAT, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_hour_project UNIQUE (hour_timestamp, project_id), 
    FOREIGN KEY(project_id) REFERENCES projects (id)
);
```

## 表结构说明

### 主要特点
1. **多用户支持**: 通过users表支持多用户系统
2. **API密钥管理**: 支持API访问控制
3. **项目管理**: 每个用户可以有多个项目
4. **内容源管理**: 每个项目可以有多个内容源
5. **任务调度**: 完整的发布任务管理
6. **日志记录**: 详细的发布日志
7. **数据分析**: 小时级别的统计数据

### 约束和索引
- 用户名唯一性约束
- 项目名在同一用户下唯一
- 任务的项目+媒体路径唯一性约束
- 小时分析数据的时间戳+项目唯一性约束
- 针对任务查询优化的复合索引

### 外键关系
- api_keys.user_id → users.id
- projects.user_id → users.id
- content_sources.project_id → projects.id
- publishing_tasks.project_id → projects.id
- publishing_tasks.source_id → content_sources.id
- publishing_logs.task_id → publishing_tasks.id
- analytics_hourly.project_id → projects.id