# 🛠️ Scripts模块记忆 (Scripts Module Memory)

## 模块概述
系统维护、数据库管理、部署和分析的脚本集合。包含日常运维和故障排查的关键工具。

## 🏗️ 模块结构

### database/ - 数据库管理脚本
```
task_query.py [常用]
├── 查询任务状态
├── 统计任务分布
└── 导出任务报告

task_resetter.py [常用]
├── 重置失败任务
├── 清理锁定任务
└── 批量状态更新

enhanced_db_viewer.py [调试利器]
├── 交互式数据库浏览
├── 表结构查看
├── SQL查询执行
└── 数据导出

db_admin.py
├── 数据库备份/恢复
├── 表结构管理
└── 索引优化

task_redistributor.py [⚠️ 关键]
├── 任务时间重分配
├── 避峰填谷算法
└── 负载均衡

fix_timezone_and_scheduling.py [修复脚本]
├── 时区问题修复
├── 调度时间校正
└── UTC转换

check_publishing_tasks.py
├── 任务健康检查
├── 异常任务检测
└── 发布队列监控
```

### maintenance/ - 系统维护脚本
```
database_migrator.py [重要]
├── 数据库迁移
├── 版本升级
├── 备份管理
└── 回滚功能

config_key_manager.py
├── 配置加密/解密
├── 密钥轮换
└── 配置验证

db_health_check.py
├── 数据库健康检查
├── 性能分析
├── 索引分析
└── 空间使用

schema_migrator.py
├── 表结构迁移
├── 数据转换
└── 兼容性检查
```

### deployment/ - 部署脚本
```
system_deployer.py
├── 自动化部署
├── 环境检查
├── 依赖安装
└── 服务启动
```

### analysis/ - 分析工具
```
task_analyzer.py
├── 任务执行分析
├── 成功率统计
├── 性能分析
└── 趋势报告
```

### server/ - 服务启动脚本
```
start_api.py [⚠️ 关键启动文件]
├── API服务启动
├── 端口配置
└── 进程管理
```

## 🔴 关键问题定位

### 1. 路径硬编码遍布各脚本
**影响文件**: 
- `fix_hardcoded_paths_comprehensive.py`
- `setup_environment_paths.py`
- `fix_database_paths.py`

**问题代码示例**:
```python
# 多个脚本中存在
DB_PATH = "/Users/ameureka/Desktop/twitter-trend/data/"
PROJECT_ROOT = "/Users/ameureka/Desktop/twitter-trend"
```

**修复状态**: 
- ✅ 已有修复脚本
- ⚠️ 但新代码仍在引入硬编码

### 2. 数据库操作缺少事务控制
**位置**: `database/` 目录下多个脚本
```python
# 问题：直接commit，无rollback
session.add(task)
session.commit()  # 失败时数据不一致
```

### 3. 脚本缺少错误处理
**普遍问题**: 大部分脚本无try-catch
```python
# 常见问题
def main():
    db = connect()  # 连接失败会崩溃
    process_data()  # 无异常处理
```

## 📊 常用脚本使用指南

### 日常运维
```bash
# 1. 查看今日任务状态
python scripts/database/task_query.py --today

# 2. 重置失败任务
python scripts/database/task_resetter.py --status failed

# 3. 查看数据库健康状态
python scripts/maintenance/db_health_check.py

# 4. 备份数据库
python scripts/maintenance/database_migrator.py --backup
```

### 问题排查
```bash
# 1. 交互式数据库浏览
python scripts/database/enhanced_db_viewer.py

# 2. 检查发布队列
python scripts/database/check_publishing_tasks.py

# 3. 分析任务执行情况
python scripts/analysis/task_analyzer.py --last-7-days

# 4. 查看系统监控
python scripts/database/system_monitor.py
```

### 修复操作
```bash
# 1. 修复时区问题
python scripts/database/fix_timezone_and_scheduling.py

# 2. 修复路径问题
python scripts/fix_hardcoded_paths_comprehensive.py

# 3. 重新分配任务时间
python scripts/database/task_redistributor.py --redistribute

# 4. 强制解锁任务
python scripts/database/task_resetter.py --unlock-all
```

## 🎯 脚本优化建议

### 高优先级
1. **统一脚本框架**
   ```python
   # 建议创建基类
   class BaseScript:
       def __init__(self):
           self.setup_logging()
           self.load_config()
           self.connect_db()
       
       def run_safe(self):
           try:
               self.run()
           except Exception as e:
               self.handle_error(e)
   ```

2. **添加命令行参数解析**
   ```python
   import argparse
   parser = argparse.ArgumentParser()
   parser.add_argument('--dry-run', action='store_true')
   ```

3. **实现脚本日志**
   ```python
   logging.basicConfig(
       filename=f'logs/scripts/{script_name}.log',
       level=logging.INFO
   )
   ```

### 中优先级
1. **脚本执行权限管理**
2. **执行历史记录**
3. **脚本依赖检查**
4. **并发执行控制**

## 🔧 脚本开发规范

### 命名规范
- 功能脚本: `{action}_{target}.py` (如: `reset_tasks.py`)
- 修复脚本: `fix_{problem}.py` (如: `fix_timezone.py`)
- 检查脚本: `check_{target}.py` (如: `check_database.py`)

### 必要组件
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本说明文档
"""

import sys
import logging
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    """主函数"""
    pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n脚本被用户中断")
    except Exception as e:
        logging.error(f"脚本执行失败: {e}")
        sys.exit(1)
```

## 📝 重要脚本说明

### task_redistributor.py
**功能**: 智能重分配任务发布时间
**算法**: 避峰填谷 + 负载均衡
**使用场景**: 任务堆积、时间分布不均

### enhanced_db_viewer.py
**功能**: 交互式数据库管理工具
**特色**: 
- 彩色输出
- 表格展示
- SQL补全
**使用场景**: 数据查询、问题排查

### database_migrator.py
**功能**: 数据库版本管理
**支持**:
- 自动备份
- 版本升级
- 回滚操作
**使用场景**: 系统升级、数据迁移

## 🐛 已知问题

1. **脚本间依赖混乱**: 部分脚本相互调用，循环依赖
2. **配置读取不一致**: 有的读YAML，有的读.env
3. **数据库连接泄漏**: 部分脚本未正确关闭连接
4. **缺少单元测试**: 脚本功能无测试保障

## 更新记录
- 2025-08-16: 创建scripts模块记忆文档
- 标注：[⚠️] 关键文件 [🔴] 严重问题