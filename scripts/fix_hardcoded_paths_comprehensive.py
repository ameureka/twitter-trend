#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合路径修复脚本

解决问题一：致命的环境不匹配与硬编码路径

主要功能：
1. 分析数据库中的硬编码绝对路径问题
2. 将绝对路径转换为相对路径
3. 更新配置文件中的基础路径设置
4. 验证修复后的路径可用性

使用方法：
1. 分析模式：python scripts/fix_hardcoded_paths_comprehensive.py --analyze
2. 修复模式：python scripts/fix_hardcoded_paths_comprehensive.py --fix
3. 验证模式：python scripts/fix_hardcoded_paths_comprehensive.py --verify
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.db_manager import EnhancedDatabaseManager
from app.database.models import PublishingTask, ContentSource
from app.utils.enhanced_config import get_enhanced_config
from app.utils.logger import get_logger
from app.utils.path_manager import get_path_manager

logger = get_logger(__name__)

class ComprehensivePathFixer:
    """综合路径修复器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config = get_enhanced_config()
        self.db_manager = EnhancedDatabaseManager()
        self.session = self.db_manager.get_session()
        self.path_manager = get_path_manager()
        
        logger.info(f"项目根目录: {self.project_root}")
        logger.info(f"当前配置的project_base_path: {self.config.get('project_base_path', '未设置')}")
    
    def analyze_path_issues(self) -> Dict[str, Any]:
        """分析路径问题"""
        logger.info("开始分析数据库中的路径问题...")
        
        analysis = {
            'publishing_tasks': {
                'total': 0,
                'absolute_paths': 0,
                'relative_paths': 0,
                'invalid_paths': 0,
                'hardcoded_patterns': {},
                'samples': []
            },
            'content_sources': {
                'total': 0,
                'absolute_paths': 0,
                'relative_paths': 0,
                'invalid_paths': 0,
                'hardcoded_patterns': {},
                'samples': []
            },
            'config_issues': [],
            'recommendations': []
        }
        
        # 分析 publishing_tasks 表
        tasks = self.session.query(PublishingTask).all()
        analysis['publishing_tasks']['total'] = len(tasks)
        
        for task in tasks:
            if task.media_path:
                self._analyze_path(task.media_path, analysis['publishing_tasks'], 
                                 {'id': task.id, 'field': 'media_path'})
            
            # 分析 content_data 中的路径
            if task.content_data:
                try:
                    content_data = json.loads(task.content_data)
                    for key in ['metadata_path', 'file_path', 'video_path', 'audio_path']:
                        if key in content_data and content_data[key]:
                            self._analyze_path(content_data[key], analysis['publishing_tasks'],
                                             {'id': task.id, 'field': f'content_data.{key}'})
                except json.JSONDecodeError:
                    pass
        
        # 分析 content_sources 表
        sources = self.session.query(ContentSource).all()
        analysis['content_sources']['total'] = len(sources)
        
        for source in sources:
            if source.path_or_identifier:
                self._analyze_path(source.path_or_identifier, analysis['content_sources'],
                                 {'id': source.id, 'field': 'path_or_identifier'})
        
        # 分析配置问题
        self._analyze_config_issues(analysis)
        
        # 生成建议
        self._generate_recommendations(analysis)
        
        return analysis
    
    def _analyze_path(self, path: str, analysis_section: Dict, context: Dict):
        """分析单个路径"""
        if not path:
            analysis_section['invalid_paths'] += 1
            return
        
        path_obj = Path(path)
        
        if path_obj.is_absolute():
            analysis_section['absolute_paths'] += 1
            
            # 检测硬编码模式
            if '/Users/ameureka/Desktop/twitter-trend' in path:
                pattern = 'macos_dev_hardcoded'
            elif '/home/twitter-trend' in path:
                pattern = 'linux_server_hardcoded'
            elif '/tmp/' in path:
                pattern = 'temp_path'
            else:
                pattern = 'other_absolute'
            
            analysis_section['hardcoded_patterns'][pattern] = \
                analysis_section['hardcoded_patterns'].get(pattern, 0) + 1
        else:
            analysis_section['relative_paths'] += 1
        
        # 收集样本
        if len(analysis_section['samples']) < 10:
            analysis_section['samples'].append({
                'context': context,
                'path': path,
                'type': 'absolute' if path_obj.is_absolute() else 'relative'
            })
    
    def _analyze_config_issues(self, analysis: Dict):
        """分析配置问题"""
        config_issues = []
        
        # 检查 project_base_path 设置
        project_base_path = self.config.get('project_base_path')
        if not project_base_path:
            config_issues.append("配置文件中缺少 project_base_path 设置")
        elif project_base_path == '.':
            config_issues.append("project_base_path 设置为 '.'，建议设置为具体的项目路径")
        
        # 检查环境变量
        if not os.environ.get('TWITTER_TREND_BASE_PATH'):
            config_issues.append("缺少环境变量 TWITTER_TREND_BASE_PATH")
        
        analysis['config_issues'] = config_issues
    
    def _generate_recommendations(self, analysis: Dict):
        """生成修复建议"""
        recommendations = []
        
        # 基于分析结果生成建议
        if analysis['publishing_tasks']['absolute_paths'] > 0:
            recommendations.append(
                f"发现 {analysis['publishing_tasks']['absolute_paths']} 个发布任务包含硬编码绝对路径，需要转换为相对路径"
            )
        
        if analysis['content_sources']['absolute_paths'] > 0:
            recommendations.append(
                f"发现 {analysis['content_sources']['absolute_paths']} 个内容源包含硬编码绝对路径，需要转换为相对路径"
            )
        
        if analysis['config_issues']:
            recommendations.append("需要修复配置文件中的路径设置问题")
        
        # 环境适配建议
        recommendations.extend([
            "建议在配置文件中设置动态的 project_base_path",
            "建议使用环境变量区分开发环境和生产环境",
            "建议实施路径标准化策略，统一使用相对路径存储"
        ])
        
        analysis['recommendations'] = recommendations
    
    def fix_hardcoded_paths(self, dry_run: bool = True) -> Dict[str, Any]:
        """修复硬编码路径"""
        logger.info(f"开始修复硬编码路径 (dry_run={dry_run})...")
        
        result = {
            'publishing_tasks_fixed': 0,
            'content_sources_fixed': 0,
            'config_updated': False,
            'backup_created': False,
            'errors': []
        }
        
        try:
            # 1. 创建数据库备份
            if not dry_run:
                self._create_database_backup()
                result['backup_created'] = True
            
            # 2. 修复 publishing_tasks 表
            result['publishing_tasks_fixed'] = self._fix_publishing_tasks(dry_run)
            
            # 3. 修复 content_sources 表
            result['content_sources_fixed'] = self._fix_content_sources(dry_run)
            
            # 4. 更新配置文件
            if not dry_run:
                self._update_config_file()
                result['config_updated'] = True
            
            # 5. 提交数据库更改
            if not dry_run:
                self.session.commit()
                logger.info("数据库更改已提交")
            
        except Exception as e:
            logger.error(f"修复过程中出错: {str(e)}")
            if not dry_run:
                self.session.rollback()
            result['errors'].append(str(e))
            raise
        
        return result
    
    def _create_database_backup(self):
        """创建数据库备份"""
        db_path = self.path_manager.get_database_path()
        backup_path = db_path.parent / f"twitter_publisher_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        shutil.copy2(db_path, backup_path)
        logger.info(f"数据库备份已创建: {backup_path}")
    
    def _fix_publishing_tasks(self, dry_run: bool) -> int:
        """修复发布任务表中的路径"""
        fixed_count = 0
        
        tasks = self.session.query(PublishingTask).all()
        
        for task in tasks:
            modified = False
            
            # 修复 media_path
            if task.media_path and self._is_hardcoded_path(task.media_path):
                new_path = self._convert_to_relative_path(task.media_path)
                if new_path != task.media_path:
                    logger.info(f"任务 {task.id} media_path: {task.media_path} -> {new_path}")
                    if not dry_run:
                        task.media_path = new_path
                    modified = True
            
            # 修复 content_data 中的路径
            if task.content_data:
                try:
                    content_data = json.loads(task.content_data)
                    content_modified = False
                    
                    for key in ['metadata_path', 'file_path', 'video_path', 'audio_path']:
                        if key in content_data and content_data[key] and self._is_hardcoded_path(content_data[key]):
                            new_path = self._convert_to_relative_path(content_data[key])
                            if new_path != content_data[key]:
                                logger.info(f"任务 {task.id} {key}: {content_data[key]} -> {new_path}")
                                if not dry_run:
                                    content_data[key] = new_path
                                content_modified = True
                    
                    if content_modified:
                        if not dry_run:
                            task.content_data = json.dumps(content_data, ensure_ascii=False)
                        modified = True
                        
                except json.JSONDecodeError:
                    logger.warning(f"任务 {task.id} content_data 不是有效的 JSON")
            
            if modified:
                fixed_count += 1
        
        return fixed_count
    
    def _fix_content_sources(self, dry_run: bool) -> int:
        """修复内容源表中的路径"""
        fixed_count = 0
        
        sources = self.session.query(ContentSource).all()
        
        for source in sources:
            if source.path_or_identifier and self._is_hardcoded_path(source.path_or_identifier):
                new_path = self._convert_to_relative_path(source.path_or_identifier)
                if new_path != source.path_or_identifier:
                    logger.info(f"内容源 {source.id}: {source.path_or_identifier} -> {new_path}")
                    if not dry_run:
                        source.path_or_identifier = new_path
                    fixed_count += 1
        
        return fixed_count
    
    def _is_hardcoded_path(self, path: str) -> bool:
        """检查是否为硬编码路径"""
        hardcoded_patterns = [
            '/Users/ameureka/Desktop/twitter-trend',
            '/home/twitter-trend',
            '/data2/twitter-trend'
        ]
        
        return any(pattern in path for pattern in hardcoded_patterns)
    
    def _convert_to_relative_path(self, absolute_path: str) -> str:
        """将绝对路径转换为相对路径"""
        path_obj = Path(absolute_path)
        
        # 如果已经是相对路径，直接返回
        if not path_obj.is_absolute():
            return absolute_path
        
        # 查找项目根目录标识
        path_str = str(path_obj)
        
        # 处理不同的硬编码模式
        patterns = [
            '/Users/ameureka/Desktop/twitter-trend/',
            '/home/twitter-trend/',
            '/data2/twitter-trend/',
            '/Users/ameureka/Desktop/twitter-trend',
            '/home/twitter-trend',
            '/data2/twitter-trend'
        ]
        
        for pattern in patterns:
            if pattern in path_str:
                relative_part = path_str.replace(pattern, '').lstrip('/')
                if relative_part:
                    return relative_part
                else:
                    return '.'
        
        # 如果无法转换，尝试查找 'project' 目录
        parts = path_obj.parts
        try:
            project_index = parts.index('project')
            relative_parts = parts[project_index:]
            return str(Path(*relative_parts))
        except ValueError:
            pass
        
        # 最后尝试相对于项目根目录计算
        try:
            relative_path = path_obj.relative_to(self.project_root)
            return str(relative_path)
        except ValueError:
            logger.warning(f"无法转换为相对路径: {absolute_path}")
            return absolute_path
    
    def _update_config_file(self):
        """更新配置文件"""
        config_path = self.project_root / 'config' / 'enhanced_config.yaml'
        
        # 读取配置文件内容
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 更新 project_base_path
        if 'project_base_path: .' in content:
            content = content.replace('project_base_path: .', 'project_base_path: ./project')
            
            # 创建备份
            backup_path = config_path.with_suffix('.yaml.backup')
            shutil.copy2(config_path, backup_path)
            
            # 写入更新后的内容
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"配置文件已更新: {config_path}")
            logger.info(f"配置文件备份: {backup_path}")
    
    def verify_paths(self) -> Dict[str, Any]:
        """验证修复后的路径"""
        logger.info("验证修复后的路径...")
        
        verification = {
            'total_paths_checked': 0,
            'valid_paths': 0,
            'invalid_paths': 0,
            'missing_files': [],
            'success_rate': 0.0,
            'recommendations': []
        }
        
        # 获取当前的基础路径
        project_base_path = self.config.get('project_base_path', './project')
        if not Path(project_base_path).is_absolute():
            base_path = self.project_root / project_base_path
        else:
            base_path = Path(project_base_path)
        
        logger.info(f"使用基础路径: {base_path}")
        
        # 验证发布任务中的媒体路径
        tasks = self.session.query(PublishingTask).limit(20).all()  # 验证前20个任务
        
        for task in tasks:
            if task.media_path:
                verification['total_paths_checked'] += 1
                
                # 构建完整路径
                if Path(task.media_path).is_absolute():
                    full_path = Path(task.media_path)
                else:
                    full_path = base_path / task.media_path
                
                if full_path.exists():
                    verification['valid_paths'] += 1
                else:
                    verification['invalid_paths'] += 1
                    verification['missing_files'].append({
                        'task_id': task.id,
                        'media_path': task.media_path,
                        'full_path': str(full_path)
                    })
        
        # 计算成功率
        if verification['total_paths_checked'] > 0:
            verification['success_rate'] = (verification['valid_paths'] / verification['total_paths_checked']) * 100
        
        # 生成建议
        if verification['invalid_paths'] > 0:
            verification['recommendations'].append(
                f"发现 {verification['invalid_paths']} 个无效路径，建议检查文件是否存在或路径配置是否正确"
            )
        
        if verification['success_rate'] < 80:
            verification['recommendations'].append(
                "路径验证成功率较低，建议检查 project_base_path 配置和文件结构"
            )
        
        return verification
    
    def close(self):
        """关闭数据库连接"""
        if self.session:
            self.session.close()

def print_analysis_report(analysis: Dict[str, Any]):
    """打印分析报告"""
    print("\n" + "="*60)
    print("路径问题分析报告")
    print("="*60)
    
    # 发布任务分析
    pt = analysis['publishing_tasks']
    print(f"\n📋 发布任务 (publishing_tasks):")
    print(f"  总数: {pt['total']}")
    print(f"  绝对路径: {pt['absolute_paths']}")
    print(f"  相对路径: {pt['relative_paths']}")
    print(f"  无效路径: {pt['invalid_paths']}")
    
    if pt['hardcoded_patterns']:
        print(f"  硬编码模式:")
        for pattern, count in pt['hardcoded_patterns'].items():
            print(f"    {pattern}: {count}")
    
    # 内容源分析
    cs = analysis['content_sources']
    print(f"\n📁 内容源 (content_sources):")
    print(f"  总数: {cs['total']}")
    print(f"  绝对路径: {cs['absolute_paths']}")
    print(f"  相对路径: {cs['relative_paths']}")
    print(f"  无效路径: {cs['invalid_paths']}")
    
    if cs['hardcoded_patterns']:
        print(f"  硬编码模式:")
        for pattern, count in cs['hardcoded_patterns'].items():
            print(f"    {pattern}: {count}")
    
    # 配置问题
    if analysis['config_issues']:
        print(f"\n⚠️  配置问题:")
        for issue in analysis['config_issues']:
            print(f"  - {issue}")
    
    # 建议
    if analysis['recommendations']:
        print(f"\n💡 修复建议:")
        for i, rec in enumerate(analysis['recommendations'], 1):
            print(f"  {i}. {rec}")
    
    # 样本路径
    if pt['samples']:
        print(f"\n📝 样本路径 (发布任务):")
        for sample in pt['samples'][:5]:
            print(f"  {sample['context']['field']} (ID:{sample['context']['id']}): {sample['path']}")

def print_fix_report(result: Dict[str, Any]):
    """打印修复报告"""
    print("\n" + "="*60)
    print("路径修复报告")
    print("="*60)
    
    print(f"\n✅ 修复结果:")
    print(f"  发布任务修复数量: {result['publishing_tasks_fixed']}")
    print(f"  内容源修复数量: {result['content_sources_fixed']}")
    print(f"  配置文件已更新: {'是' if result['config_updated'] else '否'}")
    print(f"  数据库备份已创建: {'是' if result['backup_created'] else '否'}")
    
    if result['errors']:
        print(f"\n❌ 错误:")
        for error in result['errors']:
            print(f"  - {error}")

def print_verification_report(verification: Dict[str, Any]):
    """打印验证报告"""
    print("\n" + "="*60)
    print("路径验证报告")
    print("="*60)
    
    print(f"\n📊 验证结果:")
    print(f"  检查路径总数: {verification['total_paths_checked']}")
    print(f"  有效路径: {verification['valid_paths']}")
    print(f"  无效路径: {verification['invalid_paths']}")
    print(f"  成功率: {verification['success_rate']:.1f}%")
    
    if verification['missing_files']:
        print(f"\n❌ 缺失文件 (前5个):")
        for missing in verification['missing_files'][:5]:
            print(f"  任务 {missing['task_id']}: {missing['full_path']}")
    
    if verification['recommendations']:
        print(f"\n💡 建议:")
        for rec in verification['recommendations']:
            print(f"  - {rec}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='综合路径修复脚本')
    parser.add_argument('--analyze', action='store_true', help='分析路径问题')
    parser.add_argument('--fix', action='store_true', help='修复硬编码路径')
    parser.add_argument('--verify', action='store_true', help='验证修复后的路径')
    parser.add_argument('--dry-run', action='store_true', default=True, help='预览模式（默认）')
    
    args = parser.parse_args()
    
    # 如果没有指定操作，默认执行分析
    if not any([args.analyze, args.fix, args.verify]):
        args.analyze = True
    
    fixer = ComprehensivePathFixer()
    
    try:
        if args.analyze:
            analysis = fixer.analyze_path_issues()
            print_analysis_report(analysis)
        
        if args.fix:
            dry_run = args.dry_run and not args.fix
            result = fixer.fix_hardcoded_paths(dry_run=dry_run)
            print_fix_report(result)
        
        if args.verify:
            verification = fixer.verify_paths()
            print_verification_report(verification)
        
        print("\n" + "="*60)
        print("使用说明")
        print("="*60)
        print("1. 分析问题: python scripts/fix_hardcoded_paths_comprehensive.py --analyze")
        print("2. 预览修复: python scripts/fix_hardcoded_paths_comprehensive.py --fix --dry-run")
        print("3. 执行修复: python scripts/fix_hardcoded_paths_comprehensive.py --fix")
        print("4. 验证结果: python scripts/fix_hardcoded_paths_comprehensive.py --verify")
        
    except Exception as e:
        logger.error(f"脚本执行失败: {str(e)}")
        raise
    finally:
        fixer.close()

if __name__ == '__main__':
    main()