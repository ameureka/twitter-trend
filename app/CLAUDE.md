# 📦 App模块记忆 (App Module Memory)

## 模块概述
这是系统的核心应用模块，包含所有业务逻辑、数据库操作和工具函数。

## 🏗️ 模块结构

### core/ - 核心业务逻辑
```
content_generator.py
├── ContentGenerator类
│   ├── generate_tweet_content() - AI生成推文内容
│   ├── _call_gemini_api() - 调用Google Gemini API
│   └── _format_content() - 格式化生成内容
│
enhanced_scheduler.py  
├── EnhancedTaskScheduler类 [⚠️ 重点关注]
│   ├── start() - 启动调度器
│   ├── _process_pending_tasks() - 处理待执行任务
│   ├── _execute_task() - 执行单个任务
│   └── _handle_task_failure() - 任务失败处理
│
publisher.py
├── TwitterPublisher类
│   ├── publish_media_with_text() - 发布带媒体的推文
│   ├── _upload_media() - 上传媒体文件
│   └── _post_tweet() - 发送推文
│
task_scheduler.py [⚠️ 遗留代码]
└── 旧版调度器，与enhanced_scheduler功能重复
```

### database/ - 数据访问层
```
models.py
├── User - 用户模型
├── ApiKey - API密钥模型
├── Project - 项目模型 [核心]
├── ContentSource - 内容源模型
├── PublishingTask - 发布任务模型 [核心]
├── PublishingLog - 发布日志模型
└── AnalyticsHourly - 小时统计模型

db_manager.py
├── EnhancedDatabaseManager类
│   ├── initialize_database() - 初始化数据库
│   ├── create_task() - 创建任务
│   ├── get_pending_tasks() - 获取待处理任务
│   └── update_task_status() - 更新任务状态

repository.py
└── 数据仓储模式实现
```

### utils/ - 工具模块
```
enhanced_config.py
├── get_enhanced_config() - 获取配置
└── ConfigManager类 - 配置管理器

logger.py
├── setup_logger() - 设置日志
└── get_logger() - 获取日志器

path_manager.py [⚠️ 问题源]
├── 路径硬编码问题集中地
└── 需要重构为动态路径

error_handler.py
├── ErrorHandler类
└── 全局异常处理

performance_monitor.py
├── PerformanceMonitor类
└── 系统性能监控
```

## 🔴 关键问题定位

### 1. 路径硬编码问题
**位置**: `utils/path_manager.py`, `utils/dynamic_path_manager.py`
```python
# 问题代码示例
MEDIA_PATH = "/Users/ameureka/Desktop/xxx"  # 硬编码路径
```
**影响**: 跨环境部署失败
**修复方案**: 使用相对路径 + 配置文件

### 2. 时区处理混乱
**位置**: `core/enhanced_scheduler.py` line 145-180
```python
# 问题：混用UTC和本地时间
scheduled_time = datetime.now()  # 本地时间
task.scheduled_at  # UTC时间存储
```
**影响**: 任务调度时间错误
**修复方案**: 统一使用UTC，显示时转换

### 3. 数据库并发问题
**位置**: `database/db_manager.py` line 234-267
```python
# SQLite在高并发下的锁问题
# SQLITE_BUSY错误频发
```
**影响**: 任务执行失败
**修复方案**: 
- 实现重试机制
- 使用WAL模式
- 考虑迁移到PostgreSQL

### 4. 内存泄漏
**位置**: `core/enhanced_scheduler.py`
```python
# 疑似问题：任务列表无限增长
self.processed_tasks.append(task)  # 从不清理
```
**影响**: 长时间运行内存占用增长
**修复方案**: 定期清理历史数据

## 📊 性能瓶颈

### 数据库查询
- `get_pending_tasks()` 无索引全表扫描
- 建议添加复合索引：(status, scheduled_at, priority)

### 文件IO
- 媒体文件上传未使用异步IO
- 大文件处理阻塞主线程

## 🔧 重构建议

### 高优先级
1. **抽取配置管理器**: 统一管理所有配置
2. **路径管理重构**: 消除所有硬编码路径
3. **时区处理统一**: 建立时区处理工具类
4. **添加单元测试**: 当前测试覆盖率<30%

### 中优先级
1. **分离调度器逻辑**: 解耦调度和执行
2. **实现连接池**: 数据库连接池管理
3. **异步IO改造**: 文件操作异步化
4. **日志系统优化**: 结构化日志 + 日志轮转

### 低优先级
1. **代码风格统一**: 使用Black格式化
2. **类型注解完善**: 添加类型提示
3. **文档补充**: 添加docstring

## 🎯 快速定位指南

### 查找任务执行失败原因
1. 查看 `logs/main.log` 中的ERROR级别日志
2. 检查 `enhanced_scheduler.py` 的 `_handle_task_failure()` 方法
3. 查询数据库 `publishing_logs` 表的error_message字段

### 调试调度器问题
1. 在 `enhanced_scheduler.py` line 156 设置断点
2. 查看 `_process_pending_tasks()` 方法的执行流程
3. 检查任务的scheduled_at时间是否正确

### 数据库锁问题排查
1. 启用SQLite日志：`PRAGMA journal_mode=WAL;`
2. 监控 `db_manager.py` 的数据库操作耗时
3. 检查是否有长事务未提交

## 更新记录
- 2025-08-16: 创建app模块记忆文档
- 问题标注：[⚠️] 需要立即关注的问题
- 问题标注：[🔴] 严重问题