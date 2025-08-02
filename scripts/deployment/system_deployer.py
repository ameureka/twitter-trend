#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统部署工具
自动化部署增强版Twitter自动发布系统
"""

import sys
import os
import json
import yaml
import shutil
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class SystemDeployer:
    """系统部署器"""
    
    def __init__(self, target_dir: Optional[str] = None, config_template: Optional[str] = None):
        self.project_root = project_root
        self.target_dir = Path(target_dir) if target_dir else self.project_root
        self.config_template = config_template
        
        # 部署日志
        self.deployment_log = []
        
        # 默认配置模板
        self.default_config = {
            "system": {
                "name": "Twitter Auto Publisher",
                "version": "2.0.0",
                "environment": "production",
                "debug": False,
                "timezone": "UTC"
            },
            "logging": {
                "level": "INFO",
                "path": "logs/app.log",
                "max_size": "10MB",
                "backup_count": 5,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "console_output": True
            },
            "database": {
                "type": "sqlite",
                "path": "data/twitter_publisher.db",
                "backup_enabled": True,
                "backup_interval": "daily",
                "backup_retention_days": 30
            },
            "scheduling": {
                "enabled": True,
                "check_interval": 60,
                "max_concurrent_tasks": 5,
                "task_timeout": 300,
                "retry_delay": 300
            },
            "retry": {
                "max_attempts": 3,
                "base_delay": 60,
                "max_delay": 3600,
                "exponential_backoff": True
            },
            "performance": {
                "cache_enabled": True,
                "cache_ttl": 3600,
                "batch_size": 10,
                "connection_pool_size": 5
            },
            "security": {
                "api_key_rotation": True,
                "rate_limit_enabled": True,
                "request_timeout": 30,
                "max_retries": 3
            },
            "publishing": {
                "default_priority": 3,
                "content_validation": True,
                "media_validation": True,
                "duplicate_detection": True,
                "scheduling_window": {
                    "start_hour": 8,
                    "end_hour": 22
                }
            },
            "twitter_api": {
                "api_key": "${TWITTER_API_KEY}",
                "api_secret": "${TWITTER_API_SECRET}",
                "access_token": "${TWITTER_ACCESS_TOKEN}",
                "access_token_secret": "${TWITTER_ACCESS_TOKEN_SECRET}",
                "bearer_token": "${TWITTER_BEARER_TOKEN}",
                "rate_limit": {
                    "tweets_per_hour": 50,
                    "tweets_per_day": 300
                }
            },
            "gemini_ai": {
                "api_key": "${GEMINI_API_KEY}",
                "model": "gemini-pro",
                "temperature": 0.7,
                "max_tokens": 1000,
                "timeout": 30
            },
            "notifications": {
                "enabled": True,
                "channels": {
                    "email": {
                        "enabled": False,
                        "smtp_server": "smtp.gmail.com",
                        "smtp_port": 587,
                        "username": "${EMAIL_USERNAME}",
                        "password": "${EMAIL_PASSWORD}",
                        "recipients": []
                    },
                    "webhook": {
                        "enabled": False,
                        "url": "${WEBHOOK_URL}",
                        "secret": "${WEBHOOK_SECRET}"
                    }
                },
                "events": {
                    "task_success": False,
                    "task_failure": True,
                    "system_error": True,
                    "daily_summary": True
                }
            },
            "analytics": {
                "enabled": True,
                "retention_days": 90,
                "metrics": {
                    "performance": True,
                    "usage": True,
                    "errors": True
                }
            },
            "api_server": {
                "enabled": True,
                "host": "0.0.0.0",
                "port": 8050,
                "workers": 1,
                "reload": False,
                "cors_enabled": True,
                "cors_origins": ["*"]
            },
            "monitoring": {
                "health_check_enabled": True,
                "health_check_interval": 300,
                "metrics_collection": True,
                "alert_thresholds": {
                    "error_rate": 0.1,
                    "response_time": 5.0,
                    "queue_size": 1000
                }
            }
        }
        
        # 必需的目录结构
        self.required_directories = [
            "data",
            "logs",
            "config",
            "project",
            "scripts",
            "scripts/management",
            "scripts/maintenance", 
            "scripts/development",
            "scripts/deployment",
            "scripts/server",
            "app",
            "app/core",
            "app/database",
            "app/services",
            "app/api",
            "docs",
            "tests"
        ]
        
        # 必需的文件
        self.required_files = [
            "requirements.txt",
            "README.md",
            ".env.example",
            ".gitignore"
        ]
        
    def log_step(self, step: str, status: str = "info", details: Any = None):
        """记录部署步骤"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "status": status,
            "details": details
        }
        self.deployment_log.append(log_entry)
        
        # 打印日志
        status_icons = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "progress": "🔄"
        }
        
        icon = status_icons.get(status, "📝")
        print(f"{icon} {step}")
        
        if details and status in ["error", "warning"]:
            print(f"   详情: {details}")
            
    def check_prerequisites(self) -> bool:
        """检查部署前提条件"""
        self.log_step("检查部署前提条件", "progress")
        
        issues = []
        
        # 检查Python版本
        python_version = sys.version_info
        if python_version < (3, 8):
            issues.append(f"Python版本过低: {python_version.major}.{python_version.minor}, 需要3.8+")
            
        # 检查必需的Python包
        required_packages = [
            "sqlalchemy",
            "fastapi",
            "uvicorn",
            "pydantic",
            "python-multipart",
            "aiofiles",
            "pyyaml"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing_packages.append(package)
                
        if missing_packages:
            issues.append(f"缺少Python包: {', '.join(missing_packages)}")
            
        # 检查目标目录权限
        if not os.access(self.target_dir, os.W_OK):
            issues.append(f"目标目录无写权限: {self.target_dir}")
            
        if issues:
            for issue in issues:
                self.log_step(f"前提条件检查失败: {issue}", "error")
            return False
            
        self.log_step("前提条件检查通过", "success")
        return True
        
    def create_directory_structure(self) -> bool:
        """创建目录结构"""
        self.log_step("创建目录结构", "progress")
        
        try:
            created_dirs = []
            
            for dir_path in self.required_directories:
                full_path = self.target_dir / dir_path
                if not full_path.exists():
                    full_path.mkdir(parents=True, exist_ok=True)
                    created_dirs.append(str(full_path))
                    
            if created_dirs:
                self.log_step(f"创建了 {len(created_dirs)} 个目录", "success", created_dirs)
            else:
                self.log_step("目录结构已存在", "info")
                
            return True
            
        except Exception as e:
            self.log_step("目录结构创建失败", "error", str(e))
            return False
            
    def generate_configuration(self, config_path: Optional[str] = None) -> bool:
        """生成配置文件"""
        self.log_step("生成配置文件", "progress")
        
        try:
            if not config_path:
                config_path = self.target_dir / "config" / "enhanced_config.yaml"
            else:
                config_path = Path(config_path)
                
            # 如果指定了配置模板，加载它
            if self.config_template and Path(self.config_template).exists():
                with open(self.config_template, 'r', encoding='utf-8') as f:
                    if self.config_template.endswith('.yaml') or self.config_template.endswith('.yml'):
                        config_data = yaml.safe_load(f)
                    else:
                        config_data = json.load(f)
                        
                # 合并默认配置
                config_data = self._merge_configs(self.default_config, config_data)
            else:
                config_data = self.default_config.copy()
                
            # 确保配置目录存在
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, indent=2)
                
            self.log_step(f"配置文件已生成: {config_path}", "success")
            
            # 生成环境变量示例文件
            env_example_path = self.target_dir / ".env.example"
            self._generate_env_example(env_example_path)
            
            return True
            
        except Exception as e:
            self.log_step("配置文件生成失败", "error", str(e))
            return False
            
    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """合并配置字典"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
                
        return result
        
    def _generate_env_example(self, env_path: Path):
        """生成环境变量示例文件"""
        env_content = """
# Twitter API 配置
TWITTER_API_KEY=your_twitter_api_key_here
TWITTER_API_SECRET=your_twitter_api_secret_here
TWITTER_ACCESS_TOKEN=your_twitter_access_token_here
TWITTER_ACCESS_TOKEN_SECRET=your_twitter_access_token_secret_here
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here

# Gemini AI 配置
GEMINI_API_KEY=your_gemini_api_key_here

# 邮件通知配置（可选）
EMAIL_USERNAME=your_email@example.com
EMAIL_PASSWORD=your_email_password

# Webhook 通知配置（可选）
WEBHOOK_URL=https://your-webhook-url.com/notify
WEBHOOK_SECRET=your_webhook_secret

# 数据库配置（可选，默认使用SQLite）
DATABASE_URL=sqlite:///data/twitter_publisher.db

# 系统配置
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
""".strip()
        
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
            
        self.log_step(f"环境变量示例文件已生成: {env_path}", "success")
        
    def copy_application_files(self) -> bool:
        """复制应用程序文件"""
        self.log_step("复制应用程序文件", "progress")
        
        try:
            # 如果目标目录就是项目根目录，跳过复制
            if self.target_dir.resolve() == self.project_root.resolve():
                self.log_step("目标目录为项目根目录，跳过文件复制", "info")
                return True
                
            # 需要复制的目录
            dirs_to_copy = ["app", "scripts"]
            
            # 需要复制的文件
            files_to_copy = [
                "requirements.txt",
                "README.md",
                "main.py"
            ]
            
            copied_items = []
            
            # 复制目录
            for dir_name in dirs_to_copy:
                source_dir = self.project_root / dir_name
                target_dir = self.target_dir / dir_name
                
                if source_dir.exists():
                    if target_dir.exists():
                        shutil.rmtree(target_dir)
                    shutil.copytree(source_dir, target_dir)
                    copied_items.append(f"目录: {dir_name}")
                    
            # 复制文件
            for file_name in files_to_copy:
                source_file = self.project_root / file_name
                target_file = self.target_dir / file_name
                
                if source_file.exists():
                    shutil.copy2(source_file, target_file)
                    copied_items.append(f"文件: {file_name}")
                    
            if copied_items:
                self.log_step(f"复制了 {len(copied_items)} 个项目", "success", copied_items)
            else:
                self.log_step("没有文件需要复制", "info")
                
            return True
            
        except Exception as e:
            self.log_step("应用程序文件复制失败", "error", str(e))
            return False
            
    def install_dependencies(self, use_venv: bool = True) -> bool:
        """安装依赖包"""
        self.log_step("安装依赖包", "progress")
        
        try:
            requirements_file = self.target_dir / "requirements.txt"
            
            if not requirements_file.exists():
                self.log_step("requirements.txt 文件不存在", "warning")
                return True
                
            # 构建pip安装命令
            if use_venv:
                # 检查是否在虚拟环境中
                if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
                    pip_cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
                else:
                    self.log_step("建议在虚拟环境中安装依赖", "warning")
                    pip_cmd = [sys.executable, "-m", "pip", "install", "--user", "-r", str(requirements_file)]
            else:
                pip_cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
                
            # 执行安装
            result = subprocess.run(
                pip_cmd,
                cwd=self.target_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.log_step("依赖包安装成功", "success")
                return True
            else:
                self.log_step("依赖包安装失败", "error", result.stderr)
                return False
                
        except Exception as e:
            self.log_step("依赖包安装过程出错", "error", str(e))
            return False
            
    def initialize_database(self) -> bool:
        """初始化数据库"""
        self.log_step("初始化数据库", "progress")
        
        try:
            # 导入数据库相关模块
            sys.path.insert(0, str(self.target_dir))
            
            from app.database.database import DatabaseManager
            from app.database.models import Base
            
            # 创建数据库管理器
            db_path = self.target_dir / "data" / "twitter_publisher.db"
            db_url = f"sqlite:///{db_path}"
            
            db_manager = DatabaseManager(db_url)
            db_manager.create_tables()
            
            self.log_step(f"数据库初始化成功: {db_path}", "success")
            return True
            
        except Exception as e:
            self.log_step("数据库初始化失败", "error", str(e))
            return False
            
    def create_startup_scripts(self) -> bool:
        """创建启动脚本"""
        self.log_step("创建启动脚本", "progress")
        
        try:
            scripts_created = []
            
            # 创建主启动脚本
            start_script_content = f"""#!/bin/bash
# Twitter Auto Publisher 启动脚本

cd "{self.target_dir}"

# 激活虚拟环境（如果存在）
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 启动应用
python main.py --mode scheduler
"""
            
            start_script_path = self.target_dir / "start.sh"
            with open(start_script_path, 'w', encoding='utf-8') as f:
                f.write(start_script_content)
            start_script_path.chmod(0o755)
            scripts_created.append("start.sh")
            
            # 创建API服务器启动脚本
            api_script_content = f"""#!/bin/bash
# Twitter Auto Publisher API服务器启动脚本

cd "{self.target_dir}"

# 激活虚拟环境（如果存在）
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 启动API服务器
python scripts/server/start_api.py
"""
            
            api_script_path = self.target_dir / "start_api.sh"
            with open(api_script_path, 'w', encoding='utf-8') as f:
                f.write(api_script_content)
            api_script_path.chmod(0o755)
            scripts_created.append("start_api.sh")
            
            # 创建停止脚本
            stop_script_content = """#!/bin/bash
# Twitter Auto Publisher 停止脚本

# 查找并终止相关进程
pkill -f "main.py"
pkill -f "start_api.py"

echo "Twitter Auto Publisher 已停止"
"""
            
            stop_script_path = self.target_dir / "stop.sh"
            with open(stop_script_path, 'w', encoding='utf-8') as f:
                f.write(stop_script_content)
            stop_script_path.chmod(0o755)
            scripts_created.append("stop.sh")
            
            self.log_step(f"启动脚本已创建: {', '.join(scripts_created)}", "success")
            return True
            
        except Exception as e:
            self.log_step("启动脚本创建失败", "error", str(e))
            return False
            
    def generate_documentation(self) -> bool:
        """生成部署文档"""
        self.log_step("生成部署文档", "progress")
        
        try:
            docs_dir = self.target_dir / "docs"
            docs_dir.mkdir(exist_ok=True)
            
            # 生成部署指南
            deployment_guide = f"""
# Twitter Auto Publisher 部署指南

## 系统要求

- Python 3.8+
- 至少 1GB 可用磁盘空间
- 网络连接（用于API调用）

## 部署信息

- 部署时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 部署目录: {self.target_dir}
- 配置文件: config/enhanced_config.yaml
- 数据库: data/twitter_publisher.db
- 日志目录: logs/

## 快速启动

### 1. 配置环境变量

复制 `.env.example` 为 `.env` 并填入你的API密钥：

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的Twitter API和Gemini AI密钥
```

### 2. 启动系统

```bash
# 启动调度器
./start.sh

# 或启动API服务器
./start_api.sh
```

### 3. 停止系统

```bash
./stop.sh
```

## 管理命令

### 系统状态检查

```bash
python main.py --mode management --stats
```

### 任务查询

```bash
python main.py --mode management --query --status pending
```

### 数据库管理

```bash
# 检查数据库健康状态
python scripts/maintenance/db_health_check.py

# 创建数据库备份
python scripts/maintenance/database_migrator.py --backup

# 生成测试数据
python scripts/development/test_data_generator.py --scenario basic
```

## 配置说明

主配置文件位于 `config/enhanced_config.yaml`，包含以下主要部分：

- `system`: 系统基本设置
- `database`: 数据库配置
- `twitter_api`: Twitter API设置
- `gemini_ai`: Gemini AI配置
- `scheduling`: 任务调度设置
- `logging`: 日志配置
- `notifications`: 通知设置

## 故障排除

### 常见问题

1. **API密钥错误**
   - 检查 `.env` 文件中的API密钥是否正确
   - 确认Twitter API权限设置

2. **数据库连接失败**
   - 检查 `data/` 目录权限
   - 运行数据库健康检查

3. **任务不执行**
   - 检查调度器是否运行
   - 查看日志文件 `logs/app.log`

### 日志查看

```bash
# 查看最新日志
tail -f logs/app.log

# 查看错误日志
grep ERROR logs/app.log
```

## 更新和维护

### 系统更新

1. 停止系统: `./stop.sh`
2. 备份数据库: `python scripts/maintenance/database_migrator.py --backup`
3. 更新代码
4. 重启系统: `./start.sh`

### 定期维护

- 定期清理旧日志文件
- 备份数据库
- 监控系统性能
- 更新API密钥（如需要）

## 支持

如遇问题，请检查：
1. 系统日志 (`logs/app.log`)
2. 配置文件设置
3. 网络连接状态
4. API密钥有效性
"""
            
            deployment_guide_path = docs_dir / "deployment_guide.md"
            with open(deployment_guide_path, 'w', encoding='utf-8') as f:
                f.write(deployment_guide)
                
            self.log_step(f"部署文档已生成: {deployment_guide_path}", "success")
            return True
            
        except Exception as e:
            self.log_step("部署文档生成失败", "error", str(e))
            return False
            
    def run_deployment_tests(self) -> bool:
        """运行部署测试"""
        self.log_step("运行部署测试", "progress")
        
        try:
            test_results = []
            
            # 测试1: 配置文件加载
            try:
                config_path = self.target_dir / "config" / "enhanced_config.yaml"
                with open(config_path, 'r', encoding='utf-8') as f:
                    yaml.safe_load(f)
                test_results.append(("配置文件加载", True, None))
            except Exception as e:
                test_results.append(("配置文件加载", False, str(e)))
                
            # 测试2: 数据库连接
            try:
                sys.path.insert(0, str(self.target_dir))
                from app.database.database import DatabaseManager
                
                db_path = self.target_dir / "data" / "twitter_publisher.db"
                db_url = f"sqlite:///{db_path}"
                db_manager = DatabaseManager(db_url)
                
                session = db_manager.get_session()
                session.close()
                test_results.append(("数据库连接", True, None))
            except Exception as e:
                test_results.append(("数据库连接", False, str(e)))
                
            # 测试3: 主模块导入
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "main", 
                    self.target_dir / "main.py"
                )
                main = importlib.util.module_from_spec(spec)
                test_results.append(("主模块导入", True, None))
            except Exception as e:
                test_results.append(("主模块导入", False, str(e)))
                
            # 统计测试结果
            passed_tests = sum(1 for _, success, _ in test_results if success)
            total_tests = len(test_results)
            
            # 打印测试结果
            for test_name, success, error in test_results:
                status = "success" if success else "error"
                self.log_step(f"测试 {test_name}: {'通过' if success else '失败'}", status, error)
                
            if passed_tests == total_tests:
                self.log_step(f"所有测试通过 ({passed_tests}/{total_tests})", "success")
                return True
            else:
                self.log_step(f"部分测试失败 ({passed_tests}/{total_tests})", "warning")
                return False
                
        except Exception as e:
            self.log_step("部署测试执行失败", "error", str(e))
            return False
            
    def export_deployment_log(self, output_path: Optional[str] = None) -> str:
        """导出部署日志"""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.target_dir / "logs" / f"deployment_log_{timestamp}.json")
            
        log_data = {
            "deployment_info": {
                "target_directory": str(self.target_dir),
                "deployment_time": datetime.now().isoformat(),
                "deployer_version": "2.0.0"
            },
            "deployment_steps": self.deployment_log
        }
        
        # 确保日志目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
            
        return output_path
        
    def deploy(self, 
              skip_dependencies: bool = False,
              skip_tests: bool = False,
              config_only: bool = False) -> bool:
        """执行完整部署"""
        self.log_step("开始系统部署", "info")
        self.log_step("=" * 60, "info")
        
        try:
            # 检查前提条件
            if not self.check_prerequisites():
                return False
                
            # 创建目录结构
            if not self.create_directory_structure():
                return False
                
            # 生成配置文件
            if not self.generate_configuration():
                return False
                
            # 如果只生成配置，到此结束
            if config_only:
                self.log_step("配置文件生成完成", "success")
                return True
                
            # 复制应用程序文件
            if not self.copy_application_files():
                return False
                
            # 安装依赖包
            if not skip_dependencies:
                if not self.install_dependencies():
                    self.log_step("依赖安装失败，但继续部署", "warning")
                    
            # 初始化数据库
            if not self.initialize_database():
                return False
                
            # 创建启动脚本
            if not self.create_startup_scripts():
                return False
                
            # 生成文档
            if not self.generate_documentation():
                self.log_step("文档生成失败，但继续部署", "warning")
                
            # 运行部署测试
            if not skip_tests:
                if not self.run_deployment_tests():
                    self.log_step("部署测试失败，但部署可能仍然可用", "warning")
                    
            self.log_step("=" * 60, "info")
            self.log_step("系统部署完成！", "success")
            self.log_step("=" * 60, "info")
            
            # 显示后续步骤
            self.log_step("后续步骤:", "info")
            self.log_step("1. 复制 .env.example 为 .env 并配置API密钥", "info")
            self.log_step("2. 运行 ./start.sh 启动系统", "info")
            self.log_step("3. 查看 docs/deployment_guide.md 获取详细说明", "info")
            
            return True
            
        except Exception as e:
            self.log_step("部署过程出现错误", "error", str(e))
            return False
        finally:
            # 导出部署日志
            try:
                log_path = self.export_deployment_log()
                self.log_step(f"部署日志已保存: {log_path}", "info")
            except:
                pass


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Twitter Auto Publisher 系统部署工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
    # 完整部署到当前目录
    python system_deployer.py
    
    # 部署到指定目录
    python system_deployer.py --target /path/to/deployment/directory
    
    # 只生成配置文件
    python system_deployer.py --config-only
    
    # 使用自定义配置模板
    python system_deployer.py --config-template my_config.yaml
    
    # 跳过依赖安装和测试
    python system_deployer.py --skip-dependencies --skip-tests
        """
    )
    
    parser.add_argument(
        '--target',
        help='部署目标目录（默认: 当前项目目录）'
    )
    
    parser.add_argument(
        '--config-template',
        help='配置模板文件路径'
    )
    
    parser.add_argument(
        '--config-only',
        action='store_true',
        help='只生成配置文件'
    )
    
    parser.add_argument(
        '--skip-dependencies',
        action='store_true',
        help='跳过依赖包安装'
    )
    
    parser.add_argument(
        '--skip-tests',
        action='store_true',
        help='跳过部署测试'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制执行部署（覆盖现有文件）'
    )
    
    args = parser.parse_args()
    
    try:
        # 创建部署器
        deployer = SystemDeployer(
            target_dir=args.target,
            config_template=args.config_template
        )
        
        # 执行部署
        success = deployer.deploy(
            skip_dependencies=args.skip_dependencies,
            skip_tests=args.skip_tests,
            config_only=args.config_only
        )
        
        if success:
            print("\n🎉 部署成功完成！")
            sys.exit(0)
        else:
            print("\n❌ 部署失败")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  部署被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 部署过程出现错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()