#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据生成器
灵活的测试数据生成工具，支持多种场景和配置
"""

import sys
import os
import json
import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from app.database.models import User, Project, ContentSource, PublishingTask, PublishingLog
    from app.database.repository import DatabaseRepository
    from app.database.database import DatabaseManager
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保项目依赖已正确安装")
    sys.exit(1)


class TestDataGenerator:
    """测试数据生成器"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.session = None
        self.db_repo = None
        
        # 预定义的测试数据模板
        self.user_templates = [
            {"username": "admin", "role": "admin", "email": "admin@example.com"},
            {"username": "editor", "role": "editor", "email": "editor@example.com"},
            {"username": "viewer", "role": "viewer", "email": "viewer@example.com"},
            {"username": "testuser", "role": "editor", "email": "test@example.com"}
        ]
        
        self.project_templates = [
            {
                "name": "科技资讯项目",
                "description": "专注于科技新闻和趋势的自动发布项目",
                "folder": "maker_music_chuangxinyewu"
            },
            {
                "name": "生活分享项目", 
                "description": "分享日常生活和实用技巧的内容项目",
                "folder": "maker_music_dongnanya"
            },
            {
                "name": "教育内容项目",
                "description": "教育相关内容的自动化发布项目",
                "folder": "maker_music_makerthins"
            },
            {
                "name": "娱乐媒体项目",
                "description": "娱乐和媒体内容的发布项目",
                "folder": "maker_music_voe3"
            }
        ]
        
        self.content_templates = [
            {
                "title": "人工智能的最新发展趋势",
                "content": "探讨2024年人工智能技术的重要突破和未来发展方向。#AI #科技 #未来",
                "hashtags": ["AI", "科技", "未来"],
                "language": "zh"
            },
            {
                "title": "健康生活小贴士",
                "content": "分享日常生活中简单易行的健康习惯，让生活更美好。#健康 #生活 #分享",
                "hashtags": ["健康", "生活", "分享"],
                "language": "zh"
            },
            {
                "title": "在线学习的有效方法",
                "content": "如何提高在线学习效率，掌握数字时代的学习技巧。#教育 #学习 #技巧",
                "hashtags": ["教育", "学习", "技巧"],
                "language": "zh"
            },
            {
                "title": "创意设计灵感分享",
                "content": "探索创意设计的无限可能，分享设计师的灵感来源。#设计 #创意 #艺术",
                "hashtags": ["设计", "创意", "艺术"],
                "language": "zh"
            },
            {
                "title": "科技产品评测",
                "content": "深度评测最新科技产品，为用户提供购买建议。#评测 #科技 #产品",
                "hashtags": ["评测", "科技", "产品"],
                "language": "zh"
            }
        ]
        
    def initialize_session(self):
        """初始化数据库会话"""
        self.db_manager.create_tables()
        self.session = self.db_manager.get_session()
        self.db_repo = DatabaseRepository(self.session)
        
    def cleanup_session(self):
        """清理数据库会话"""
        if self.session:
            self.session.close()
            
    def clear_existing_data(self, preserve_admin: bool = True):
        """清理现有测试数据"""
        print("🧹 清理现有测试数据...")
        
        try:
            # 按照外键依赖顺序删除
            self.session.query(PublishingLog).delete()
            self.session.query(PublishingTask).delete()
            self.session.query(ContentSource).delete()
            self.session.query(Project).delete()
            
            if not preserve_admin:
                self.session.query(User).delete()
            else:
                # 只删除非admin用户
                self.session.query(User).filter(User.username != 'admin').delete()
                
            self.session.commit()
            print("  ✅ 数据清理完成")
            
        except Exception as e:
            self.session.rollback()
            raise Exception(f"数据清理失败: {e}")
            
    def create_users(self, count: Optional[int] = None) -> List[User]:
        """创建测试用户"""
        print("👥 创建测试用户...")
        
        users = []
        templates_to_use = self.user_templates[:count] if count else self.user_templates
        
        for user_data in templates_to_use:
            # 检查用户是否已存在
            existing_user = self.session.query(User).filter(
                User.username == user_data["username"]
            ).first()
            
            if not existing_user:
                user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    role=user_data["role"]
                )
                self.session.add(user)
                self.session.flush()
                users.append(user)
                print(f"  ✅ 创建用户: {user.username} ({user.role})")
            else:
                users.append(existing_user)
                print(f"  ℹ️  用户已存在: {existing_user.username}")
                
        return users
        
    def create_projects(self, user: User, count: Optional[int] = None) -> List[Project]:
        """创建测试项目"""
        print("📁 创建测试项目...")
        
        projects = []
        templates_to_use = self.project_templates[:count] if count else self.project_templates
        
        for project_data in templates_to_use:
            # 检查项目是否已存在
            existing_project = self.session.query(Project).filter(
                Project.user_id == user.id,
                Project.name == project_data["name"]
            ).first()
            
            if not existing_project:
                project = Project(
                    user_id=user.id,
                    name=project_data["name"],
                    description=project_data["description"],
                    folder_path=project_data.get("folder", ""),
                    is_active=True
                )
                self.session.add(project)
                self.session.flush()
                projects.append(project)
                print(f"  ✅ 创建项目: {project.name}")
            else:
                projects.append(existing_project)
                print(f"  ℹ️  项目已存在: {existing_project.name}")
                
        return projects
        
    def create_content_sources(self, projects: List[Project]) -> List[ContentSource]:
        """创建内容源"""
        print("📄 创建内容源...")
        
        sources = []
        source_types = ["video", "metadata"]
        
        for project in projects:
            for source_type in source_types:
                if source_type == "video":
                    path = f"/project/{project.folder_path}/output_video_music/"
                else:
                    path = f"/project/{project.folder_path}/uploader_json/"
                    
                source = ContentSource(
                    project_id=project.id,
                    source_type=source_type,
                    path_or_identifier=path,
                    total_items=random.randint(50, 200),
                    used_items=random.randint(0, 50),
                    last_scanned=datetime.utcnow() - timedelta(hours=random.randint(1, 24))
                )
                self.session.add(source)
                self.session.flush()
                sources.append(source)
                print(f"  ✅ 创建内容源: {project.name} - {source_type}")
                
        return sources
        
    def create_tasks(self, projects: List[Project], sources: List[ContentSource], 
                    task_count: int = 50, status_distribution: Optional[Dict[str, float]] = None) -> List[PublishingTask]:
        """创建发布任务"""
        print(f"📋 创建 {task_count} 个发布任务...")
        
        # 默认状态分布
        if not status_distribution:
            status_distribution = {
                "pending": 0.7,
                "success": 0.2,
                "failed": 0.1
            }
            
        tasks = []
        statuses = list(status_distribution.keys())
        weights = list(status_distribution.values())
        
        # 获取实际的媒体文件
        media_files = self._get_media_files(projects)
        
        for i in range(task_count):
            # 随机选择项目和内容源
            project = random.choice(projects)
            video_sources = [s for s in sources if s.project_id == project.id and s.source_type == "video"]
            
            if not video_sources:
                continue
                
            source = random.choice(video_sources)
            
            # 随机选择内容模板
            content_template = random.choice(self.content_templates)
            
            # 随机选择媒体文件
            media_path = random.choice(media_files) if media_files else f"/project/{project.folder_path}/output_video_music/video_{i:03d}.mp4"
            
            # 随机选择状态
            status = random.choices(statuses, weights=weights)[0]
            
            # 创建任务
            scheduled_time = datetime.utcnow() + timedelta(
                hours=random.randint(-24, 72),
                minutes=random.randint(0, 59)
            )
            
            task = PublishingTask(
                project_id=project.id,
                source_id=source.id,
                media_path=media_path,
                content_data=json.dumps(content_template, ensure_ascii=False),
                scheduled_at=scheduled_time,
                status=status,
                priority=random.randint(0, 5),
                retry_count=random.randint(0, 3) if status == "failed" else 0
            )
            
            if status != "pending":
                task.updated_at = datetime.utcnow() - timedelta(
                    hours=random.randint(1, 48)
                )
                
            self.session.add(task)
            self.session.flush()
            tasks.append(task)
            
        print(f"  ✅ 创建了 {len(tasks)} 个任务")
        
        # 打印状态分布
        actual_distribution = {}
        for status in statuses:
            count = len([t for t in tasks if t.status == status])
            actual_distribution[status] = count
            
        print(f"  📊 状态分布: {actual_distribution}")
        
        return tasks
        
    def create_logs(self, tasks: List[PublishingTask]) -> List[PublishingLog]:
        """创建发布日志"""
        print("📊 创建发布日志...")
        
        logs = []
        
        for task in tasks:
            if task.status in ["success", "failed"]:
                log = PublishingLog(
                    task_id=task.id,
                    status=task.status,
                    tweet_id=f"tweet_{random.randint(100000, 999999)}" if task.status == "success" else None,
                    tweet_content=task.content_data if task.status == "success" else None,
                    published_at=task.updated_at or datetime.utcnow(),
                    error_message=None if task.status == "success" else self._get_random_error(),
                    duration_seconds=round(random.uniform(0.5, 5.0), 2)
                )
                self.session.add(log)
                logs.append(log)
                
        print(f"  ✅ 创建了 {len(logs)} 个日志记录")
        return logs
        
    def _get_media_files(self, projects: List[Project]) -> List[str]:
        """获取实际的媒体文件路径"""
        media_files = []
        project_base_path = project_root / "project"
        
        for project in projects:
            if project.folder_path:
                video_dir = project_base_path / project.folder_path / "output_video_music"
                if video_dir.exists():
                    for video_file in video_dir.glob("*.mp4"):
                        media_files.append(str(video_file))
                        
        return media_files[:50]  # 限制数量
        
    def _get_random_error(self) -> str:
        """获取随机错误消息"""
        errors = [
            "网络连接超时",
            "API限制达到上限",
            "认证失败",
            "媒体文件上传失败",
            "内容违反平台规则",
            "服务器内部错误",
            "文件格式不支持",
            "内容长度超出限制"
        ]
        return random.choice(errors)
        
    def generate_scenario_data(self, scenario: str) -> Dict[str, Any]:
        """生成特定场景的测试数据"""
        print(f"🎭 生成场景数据: {scenario}")
        
        scenarios = {
            "minimal": {
                "users": 1,
                "projects": 1,
                "tasks": 10,
                "status_distribution": {"pending": 1.0}
            },
            "basic": {
                "users": 2,
                "projects": 2,
                "tasks": 50,
                "status_distribution": {"pending": 0.8, "success": 0.2}
            },
            "full": {
                "users": None,  # 使用所有模板
                "projects": None,
                "tasks": 200,
                "status_distribution": {"pending": 0.6, "success": 0.3, "failed": 0.1}
            },
            "stress": {
                "users": None,
                "projects": None,
                "tasks": 1000,
                "status_distribution": {"pending": 0.5, "success": 0.4, "failed": 0.1}
            }
        }
        
        return scenarios.get(scenario, scenarios["basic"])
        
    def generate_test_data(self, scenario: str = "basic", clear_existing: bool = True) -> Dict[str, Any]:
        """生成测试数据"""
        print("🏭 开始生成测试数据...")
        print("=" * 60)
        
        try:
            self.initialize_session()
            
            # 清理现有数据
            if clear_existing:
                self.clear_existing_data()
                
            # 获取场景配置
            config = self.generate_scenario_data(scenario)
            
            # 创建用户
            users = self.create_users(config["users"])
            admin_user = next((u for u in users if u.username == "admin"), users[0])
            
            # 创建项目
            projects = self.create_projects(admin_user, config["projects"])
            
            # 创建内容源
            sources = self.create_content_sources(projects)
            
            # 创建任务
            tasks = self.create_tasks(
                projects, 
                sources, 
                config["tasks"], 
                config["status_distribution"]
            )
            
            # 创建日志
            logs = self.create_logs(tasks)
            
            # 提交所有更改
            self.session.commit()
            
            # 生成统计信息
            stats = {
                "scenario": scenario,
                "users_created": len(users),
                "projects_created": len(projects),
                "sources_created": len(sources),
                "tasks_created": len(tasks),
                "logs_created": len(logs),
                "generation_time": datetime.utcnow().isoformat()
            }
            
            print("\n" + "=" * 60)
            print("✅ 测试数据生成完成！")
            print("=" * 60)
            print(f"📊 场景: {scenario}")
            print(f"👥 用户: {stats['users_created']} 个")
            print(f"📁 项目: {stats['projects_created']} 个")
            print(f"📄 内容源: {stats['sources_created']} 个")
            print(f"📋 任务: {stats['tasks_created']} 个")
            print(f"📊 日志: {stats['logs_created']} 个")
            print("=" * 60)
            
            return stats
            
        except Exception as e:
            if self.session:
                self.session.rollback()
            raise Exception(f"测试数据生成失败: {e}")
        finally:
            self.cleanup_session()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='测试数据生成器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
场景说明:
    minimal  - 最小数据集 (1用户, 1项目, 10任务)
    basic    - 基础数据集 (2用户, 2项目, 50任务)
    full     - 完整数据集 (所有用户和项目, 200任务)
    stress   - 压力测试数据集 (所有用户和项目, 1000任务)

示例:
    # 生成基础测试数据
    python test_data_generator.py
    
    # 生成最小测试数据
    python test_data_generator.py --scenario minimal
    
    # 生成完整测试数据（不清理现有数据）
    python test_data_generator.py --scenario full --no-clear
    
    # 生成压力测试数据
    python test_data_generator.py --scenario stress
        """
    )
    
    parser.add_argument(
        '--scenario',
        choices=['minimal', 'basic', 'full', 'stress'],
        default='basic',
        help='测试数据场景（默认: basic）'
    )
    
    parser.add_argument(
        '--no-clear',
        action='store_true',
        help='不清理现有数据'
    )
    
    parser.add_argument(
        '--db-path',
        help='数据库文件路径'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='以JSON格式输出统计信息'
    )
    
    args = parser.parse_args()
    
    try:
        # 初始化数据库管理器
        db_path = args.db_path or str(project_root / "data" / "twitter_publisher.db")
        db_url = f"sqlite:///{db_path}"
        db_manager = DatabaseManager(db_url)
        
        # 创建测试数据生成器
        generator = TestDataGenerator(db_manager)
        
        # 生成测试数据
        stats = generator.generate_test_data(
            scenario=args.scenario,
            clear_existing=not args.no_clear
        )
        
        # 输出结果
        if args.json:
            print(json.dumps(stats, indent=2, ensure_ascii=False))
            
    except KeyboardInterrupt:
        print("\n⚠️  生成被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()