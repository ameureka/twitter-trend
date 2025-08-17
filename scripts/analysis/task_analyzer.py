#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务分析器
提供详细的任务分布分析和统计功能
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.models import Project, PublishingTask, ContentSource, User
from app.database.db_manager import EnhancedDatabaseManager
from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config


class TaskAnalyzer:
    """任务分析器"""
    
    def __init__(self, db_manager: EnhancedDatabaseManager = None):
        self.db_manager = db_manager or EnhancedDatabaseManager()
        self.logger = get_logger('task_analyzer')
        self.config = get_enhanced_config()
    
    def get_basic_statistics(self, session: Session) -> Dict[str, Any]:
        """获取基础统计信息"""
        try:
            stats = {
                'total_tasks': session.query(PublishingTask).count(),
                'total_projects': session.query(Project).count(),
                'total_sources': session.query(ContentSource).count(),
                'total_users': session.query(User).count()
            }
            
            self.logger.debug(f"基础统计: {stats}")
            return stats
            
        except Exception as e:
            self.logger.error(f"获取基础统计失败: {e}")
            return {}
    
    def analyze_task_status(self, session: Session) -> List[Dict[str, Any]]:
        """分析任务状态分布"""
        try:
            status_stats = session.query(
                PublishingTask.status,
                func.count(PublishingTask.id)
            ).group_by(PublishingTask.status).all()
            
            total_tasks = session.query(PublishingTask).count()
            
            result = []
            for status, count in status_stats:
                percentage = (count / total_tasks * 100) if total_tasks > 0 else 0
                result.append({
                    'status': status,
                    'count': count,
                    'percentage': round(percentage, 1)
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"分析任务状态失败: {e}")
            return []
    
    def analyze_project_distribution(self, session: Session) -> List[Dict[str, Any]]:
        """分析项目任务分布"""
        try:
            project_stats = session.query(
                Project.name,
                func.count(PublishingTask.id)
            ).join(PublishingTask).group_by(Project.name).all()
            
            total_tasks = session.query(PublishingTask).count()
            
            result = []
            for project_name, task_count in project_stats:
                percentage = (task_count / total_tasks * 100) if total_tasks > 0 else 0
                result.append({
                    'project_name': project_name,
                    'task_count': task_count,
                    'percentage': round(percentage, 1)
                })
            
            # 按任务数量排序
            result.sort(key=lambda x: x['task_count'], reverse=True)
            return result
            
        except Exception as e:
            self.logger.error(f"分析项目分布失败: {e}")
            return []
    
    def analyze_content_sources(self, session: Session) -> List[Dict[str, Any]]:
        """分析内容源信息"""
        try:
            sources = session.query(ContentSource).all()
            result = []
            
            for source in sources:
                # 获取关联的任务数量
                task_count = session.query(PublishingTask).filter(
                    PublishingTask.source_id == source.id
                ).count()
                
                # 获取项目信息
                project = session.query(Project).filter(
                    Project.id == source.project_id
                ).first()
                
                result.append({
                    'id': source.id,
                    'project_name': project.name if project else 'Unknown',
                    'source_type': source.source_type,
                    'path': source.path_or_identifier,
                    'total_items': source.total_items,
                    'used_items': source.used_items,
                    'associated_tasks': task_count,
                    'last_scanned': source.last_scanned.isoformat() if source.last_scanned else None,
                    'created_at': source.created_at.isoformat() if source.created_at else None
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"分析内容源失败: {e}")
            return []
    
    def analyze_media_files(self, session: Session) -> Dict[str, Any]:
        """分析媒体文件类型"""
        try:
            tasks_with_media = session.query(PublishingTask.media_path).all()
            
            file_extensions = {}
            total_files = 0
            
            for (media_path,) in tasks_with_media:
                if media_path:
                    ext = Path(media_path).suffix.lower()
                    file_extensions[ext] = file_extensions.get(ext, 0) + 1
                    total_files += 1
            
            # 转换为百分比
            result = []
            for ext, count in sorted(file_extensions.items()):
                percentage = (count / total_files * 100) if total_files > 0 else 0
                result.append({
                    'extension': ext or '无扩展名',
                    'count': count,
                    'percentage': round(percentage, 1)
                })
            
            return {
                'total_files': total_files,
                'extensions': result
            }
            
        except Exception as e:
            self.logger.error(f"分析媒体文件失败: {e}")
            return {'total_files': 0, 'extensions': []}
    
    def analyze_task_timeline(self, session: Session) -> Dict[str, Any]:
        """分析任务创建时间线"""
        try:
            # 获取最早和最晚的任务
            earliest_task = session.query(PublishingTask).order_by(
                PublishingTask.created_at.asc()
            ).first()
            
            latest_task = session.query(PublishingTask).order_by(
                PublishingTask.created_at.desc()
            ).first()
            
            result = {
                'earliest_task': None,
                'latest_task': None,
                'time_span': None,
                'creation_rate': None
            }
            
            if earliest_task and latest_task:
                result['earliest_task'] = earliest_task.created_at.isoformat()
                result['latest_task'] = latest_task.created_at.isoformat()
                
                time_diff = latest_task.created_at - earliest_task.created_at
                result['time_span'] = str(time_diff)
                
                # 计算创建速率（任务/秒）
                total_tasks = session.query(PublishingTask).count()
                if time_diff.total_seconds() > 0:
                    rate = total_tasks / time_diff.total_seconds()
                    result['creation_rate'] = f"{rate:.2f} 任务/秒"
            
            return result
            
        except Exception as e:
            self.logger.error(f"分析任务时间线失败: {e}")
            return {}
    
    def analyze_priority_distribution(self, session: Session) -> List[Dict[str, Any]]:
        """分析任务优先级分布"""
        try:
            priority_stats = session.query(
                PublishingTask.priority,
                func.count(PublishingTask.id)
            ).group_by(PublishingTask.priority).all()
            
            total_tasks = session.query(PublishingTask).count()
            
            result = []
            for priority, count in priority_stats:
                percentage = (count / total_tasks * 100) if total_tasks > 0 else 0
                result.append({
                    'priority': priority,
                    'count': count,
                    'percentage': round(percentage, 1)
                })
            
            # 按优先级排序
            result.sort(key=lambda x: x['priority'], reverse=True)
            return result
            
        except Exception as e:
            self.logger.error(f"分析优先级分布失败: {e}")
            return []
    
    def analyze_content_data_structure(self, session: Session, sample_size: int = 5) -> List[Dict[str, Any]]:
        """分析内容数据结构"""
        try:
            tasks_with_content = session.query(PublishingTask).filter(
                PublishingTask.content_data.isnot(None)
            ).limit(sample_size).all()
            
            result = []
            for task in tasks_with_content:
                try:
                    content_data = json.loads(task.content_data) if task.content_data else {}
                    
                    # 提取关键信息
                    sample_info = {
                        'task_id': task.id,
                        'media_file': Path(task.media_path).name if task.media_path else None,
                        'content_fields': list(content_data.keys()) if content_data else [],
                        'has_title': 'title' in content_data,
                        'has_description': 'description' in content_data,
                        'title_preview': None,
                        'description_preview': None
                    }
                    
                    # 添加预览文本
                    if 'title' in content_data:
                        title = content_data['title']
                        sample_info['title_preview'] = title[:50] + '...' if len(title) > 50 else title
                    
                    if 'description' in content_data:
                        desc = content_data['description']
                        sample_info['description_preview'] = desc[:100] + '...' if len(desc) > 100 else desc
                    
                    result.append(sample_info)
                    
                except json.JSONDecodeError:
                    result.append({
                        'task_id': task.id,
                        'error': '内容数据解析失败'
                    })
            
            return result
            
        except Exception as e:
            self.logger.error(f"分析内容数据结构失败: {e}")
            return []
    
    def get_recent_tasks(self, session: Session, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的任务"""
        try:
            recent_tasks = session.query(PublishingTask).join(Project).order_by(
                PublishingTask.created_at.desc()
            ).limit(limit).all()
            
            result = []
            for task in recent_tasks:
                result.append({
                    'id': task.id,
                    'project_name': task.project.name if task.project else 'Unknown',
                    'status': task.status,
                    'priority': task.priority,
                    'media_file': Path(task.media_path).name if task.media_path else None,
                    'created_at': task.created_at.isoformat() if task.created_at else None
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取最近任务失败: {e}")
            return []
    
    def generate_comprehensive_report(self, detailed: bool = True) -> Dict[str, Any]:
        """生成综合分析报告"""
        try:
            with self.db_manager.get_session_context() as session:
                report = {
                    'generated_at': datetime.now().isoformat(),
                    'basic_statistics': self.get_basic_statistics(session),
                    'task_status_analysis': self.analyze_task_status(session),
                    'project_distribution': self.analyze_project_distribution(session),
                    'priority_distribution': self.analyze_priority_distribution(session),
                    'media_file_analysis': self.analyze_media_files(session),
                    'task_timeline': self.analyze_task_timeline(session),
                    'recent_tasks': self.get_recent_tasks(session)
                }
                
                if detailed:
                    report.update({
                        'content_sources': self.analyze_content_sources(session),
                        'content_data_samples': self.analyze_content_data_structure(session),
                        'distribution_logic_summary': self._get_distribution_logic_summary()
                    })
                
                return report
                
        except Exception as e:
            self.logger.error(f"生成综合报告失败: {e}")
            return {'error': str(e)}
    
    def _get_distribution_logic_summary(self) -> Dict[str, Any]:
        """获取分布逻辑总结"""
        return {
            'task_creation_logic': [
                "基于项目文件夹自动扫描",
                "每个视频文件对应一个发布任务",
                "任务内容来自JSON元数据文件"
            ],
            'project_structure': {
                'video_folder': 'output_video_music/',
                'metadata_folder': 'uploader_json/'
            },
            'task_properties': {
                'default_status': 'pending',
                'default_priority': 0,
                'unique_constraint': 'project_id + media_path'
            },
            'content_source_management': [
                "每个项目有两个内容源: video 和 metadata",
                "内容源记录文件路径和使用统计",
                "支持动态扫描和更新"
            ]
        }
    
    def print_report(self, report: Dict[str, Any], format_type: str = 'text'):
        """打印报告"""
        if format_type == 'json':
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return
        
        # 文本格式输出
        print("=" * 80)
        print("任务分布详细分析报告")
        print("=" * 80)
        
        # 基础统计
        stats = report.get('basic_statistics', {})
        print(f"\n=== 基础统计 ===")
        print(f"总任务数: {stats.get('total_tasks', 0)}")
        print(f"总项目数: {stats.get('total_projects', 0)}")
        print(f"总内容源数: {stats.get('total_sources', 0)}")
        print(f"总用户数: {stats.get('total_users', 0)}")
        
        # 任务状态分析
        status_analysis = report.get('task_status_analysis', [])
        if status_analysis:
            print(f"\n=== 任务状态分析 ===")
            for item in status_analysis:
                print(f"{item['status']}: {item['count']} 个任务 ({item['percentage']}%)")
        
        # 项目分布
        project_dist = report.get('project_distribution', [])
        if project_dist:
            print(f"\n=== 项目任务分布 ===")
            for item in project_dist:
                print(f"{item['project_name']}: {item['task_count']} 个任务 ({item['percentage']}%)")
        
        # 优先级分布
        priority_dist = report.get('priority_distribution', [])
        if priority_dist:
            print(f"\n=== 任务优先级分布 ===")
            for item in priority_dist:
                print(f"优先级 {item['priority']}: {item['count']} 个任务 ({item['percentage']}%)")
        
        # 媒体文件分析
        media_analysis = report.get('media_file_analysis', {})
        if media_analysis.get('extensions'):
            print(f"\n=== 媒体文件类型分析 ===")
            print(f"总文件数: {media_analysis['total_files']}")
            for item in media_analysis['extensions']:
                print(f"{item['extension']}: {item['count']} 个文件 ({item['percentage']}%)")
        
        # 时间线分析
        timeline = report.get('task_timeline', {})
        if timeline.get('earliest_task'):
            print(f"\n=== 任务创建时间分析 ===")
            print(f"最早任务: {timeline['earliest_task']}")
            print(f"最晚任务: {timeline['latest_task']}")
            print(f"时间跨度: {timeline['time_span']}")
            if timeline.get('creation_rate'):
                print(f"创建速率: {timeline['creation_rate']}")
        
        # 最近任务
        recent_tasks = report.get('recent_tasks', [])
        if recent_tasks:
            print(f"\n=== 最近创建的任务 ===")
            for task in recent_tasks[:5]:  # 只显示前5个
                print(f"ID: {task['id']}, 项目: {task['project_name']}, "
                      f"状态: {task['status']}, 优先级: {task['priority']}, "
                      f"创建时间: {task['created_at']}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='任务分析工具')
    parser.add_argument('--detailed', action='store_true', help='生成详细报告')
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='输出格式')
    parser.add_argument('--output', help='输出文件路径')
    
    args = parser.parse_args()
    
    try:
        # 创建分析器
        analyzer = TaskAnalyzer()
        
        # 生成报告
        report = analyzer.generate_comprehensive_report(detailed=args.detailed)
        
        if 'error' in report:
            print(f"分析失败: {report['error']}")
            sys.exit(1)
        
        # 输出报告
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                if args.format == 'json':
                    json.dump(report, f, indent=2, ensure_ascii=False)
                else:
                    # 重定向标准输出到文件
                    import contextlib
                    with contextlib.redirect_stdout(f):
                        analyzer.print_report(report, args.format)
            print(f"报告已保存到: {args.output}")
        else:
            analyzer.print_report(report, args.format)
        
    except Exception as e:
        print(f"程序执行失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()