#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
媒体文件路径修复脚本

问题描述:
- 数据库中的媒体文件路径包含硬编码的绝对路径
- 开发环境路径: /Users/ameureka/Desktop/twitter-trend/project/...
- 服务器环境路径: /home/twitter-trend/project/...
- 导致部署后媒体文件无法找到

解决方案:
- 将绝对路径转换为相对路径（相对于项目根目录）
- 使用配置文件中的 project_base_path 动态拼接完整路径
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.db_manager import EnhancedDatabaseManager
from app.database.models import PublishingTask
from app.utils.enhanced_config import get_enhanced_config
from app.utils.logger import get_logger

logger = get_logger(__name__)

class MediaPathFixer:
    """媒体路径修复器"""
    
    def __init__(self):
        self.config = get_enhanced_config()
        self.db_manager = EnhancedDatabaseManager()
        self.session = self.db_manager.get_session()
        
        # 获取项目根目录
        self.project_root = Path(__file__).parent.parent.parent
        logger.info(f"项目根目录: {self.project_root}")
        
    def analyze_current_paths(self) -> Dict[str, Any]:
        """分析当前数据库中的路径情况"""
        logger.info("开始分析当前数据库中的媒体路径...")
        
        # 获取所有任务的媒体路径
        tasks = self.session.query(PublishingTask.id, PublishingTask.media_path).all()
        
        analysis = {
            'total_tasks': len(tasks),
            'absolute_paths': 0,
            'relative_paths': 0,
            'invalid_paths': 0,
            'path_patterns': {},
            'sample_paths': []
        }
        
        for task_id, media_path in tasks:
            if not media_path:
                analysis['invalid_paths'] += 1
                continue
                
            path_obj = Path(media_path)
            
            # 检查是否为绝对路径
            if path_obj.is_absolute():
                analysis['absolute_paths'] += 1
                
                # 分析路径模式
                if '/Users/' in media_path:
                    pattern = 'macos_dev'
                elif '/home/' in media_path:
                    pattern = 'linux_server'
                else:
                    pattern = 'other_absolute'
                    
                analysis['path_patterns'][pattern] = analysis['path_patterns'].get(pattern, 0) + 1
            else:
                analysis['relative_paths'] += 1
                analysis['path_patterns']['relative'] = analysis['path_patterns'].get('relative', 0) + 1
            
            # 收集样本路径
            if len(analysis['sample_paths']) < 5:
                analysis['sample_paths'].append({
                    'task_id': task_id,
                    'path': media_path,
                    'type': 'absolute' if path_obj.is_absolute() else 'relative'
                })
        
        return analysis
    
    def convert_to_relative_path(self, absolute_path: str) -> str:
        """将绝对路径转换为相对路径"""
        path_obj = Path(absolute_path)
        
        # 如果已经是相对路径，直接返回
        if not path_obj.is_absolute():
            return absolute_path
        
        # 查找 'project' 目录在路径中的位置
        parts = path_obj.parts
        try:
            project_index = parts.index('project')
            # 从 'project' 开始构建相对路径
            relative_parts = parts[project_index:]
            relative_path = str(Path(*relative_parts))
            return relative_path
        except ValueError:
            # 如果路径中没有 'project' 目录，尝试其他方法
            logger.warning(f"路径中未找到 'project' 目录: {absolute_path}")
            
            # 尝试从项目根目录计算相对路径
            try:
                relative_path = path_obj.relative_to(self.project_root)
                return str(relative_path)
            except ValueError:
                logger.error(f"无法转换为相对路径: {absolute_path}")
                return absolute_path
    
    def fix_media_paths(self, dry_run: bool = True) -> Dict[str, Any]:
        """修复媒体文件路径"""
        logger.info(f"开始修复媒体文件路径 (dry_run={dry_run})...")
        
        # 获取所有需要修复的任务
        tasks = self.session.query(PublishingTask).filter(
            PublishingTask.media_path.like('/%')  # 绝对路径以 '/' 开头
        ).all()
        
        result = {
            'total_tasks_to_fix': len(tasks),
            'successfully_fixed': 0,
            'failed_to_fix': 0,
            'conversions': []
        }
        
        for task in tasks:
            try:
                old_path = task.media_path
                new_path = self.convert_to_relative_path(old_path)
                
                conversion = {
                    'task_id': task.id,
                    'old_path': old_path,
                    'new_path': new_path,
                    'status': 'success'
                }
                
                if not dry_run:
                    task.media_path = new_path
                    result['successfully_fixed'] += 1
                else:
                    result['successfully_fixed'] += 1
                
                result['conversions'].append(conversion)
                
                if len(result['conversions']) <= 10:  # 只记录前10个转换示例
                    logger.info(f"任务 {task.id}: {old_path} -> {new_path}")
                
            except Exception as e:
                logger.error(f"修复任务 {task.id} 路径时出错: {str(e)}")
                result['failed_to_fix'] += 1
                result['conversions'].append({
                    'task_id': task.id,
                    'old_path': task.media_path,
                    'new_path': None,
                    'status': 'failed',
                    'error': str(e)
                })
        
        if not dry_run:
            try:
                self.session.commit()
                logger.info("数据库更改已提交")
            except Exception as e:
                self.session.rollback()
                logger.error(f"提交数据库更改时出错: {str(e)}")
                raise
        
        return result
    
    def verify_paths_after_fix(self) -> Dict[str, Any]:
        """验证修复后的路径"""
        logger.info("验证修复后的路径...")
        
        # 重新分析路径
        analysis = self.analyze_current_paths()
        
        # 检查文件是否存在
        project_base_path = Path(self.config.get('project_base_path', './project'))
        if not project_base_path.is_absolute():
            project_base_path = self.project_root / project_base_path
        
        verification = {
            'analysis': analysis,
            'file_existence_check': {
                'total_checked': 0,
                'existing_files': 0,
                'missing_files': 0,
                'missing_file_samples': []
            }
        }
        
        # 检查前10个文件是否存在
        tasks = self.session.query(PublishingTask.media_path).limit(10).all()
        
        for (media_path,) in tasks:
            if not media_path:
                continue
                
            verification['file_existence_check']['total_checked'] += 1
            
            # 构建完整路径
            if Path(media_path).is_absolute():
                full_path = Path(media_path)
            else:
                full_path = project_base_path / media_path
            
            if full_path.exists():
                verification['file_existence_check']['existing_files'] += 1
            else:
                verification['file_existence_check']['missing_files'] += 1
                if len(verification['file_existence_check']['missing_file_samples']) < 5:
                    verification['file_existence_check']['missing_file_samples'].append(str(full_path))
        
        return verification
    
    def close(self):
        """关闭数据库连接"""
        if self.session:
            self.session.close()

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='修复数据库中的媒体文件路径')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='只分析不修改（默认）')
    parser.add_argument('--fix', action='store_true',
                       help='实际执行修复')
    parser.add_argument('--verify', action='store_true',
                       help='验证修复后的路径')
    
    args = parser.parse_args()
    
    fixer = MediaPathFixer()
    
    try:
        # 1. 分析当前路径情况
        print("\n=== 当前路径分析 ===")
        analysis = fixer.analyze_current_paths()
        print(f"总任务数: {analysis['total_tasks']}")
        print(f"绝对路径: {analysis['absolute_paths']}")
        print(f"相对路径: {analysis['relative_paths']}")
        print(f"无效路径: {analysis['invalid_paths']}")
        print(f"路径模式: {analysis['path_patterns']}")
        
        print("\n样本路径:")
        for sample in analysis['sample_paths']:
            print(f"  任务 {sample['task_id']} ({sample['type']}): {sample['path']}")
        
        # 2. 执行修复（根据参数决定是否实际修复）
        if args.fix:
            print("\n=== 执行路径修复 ===")
            result = fixer.fix_media_paths(dry_run=False)
        else:
            print("\n=== 路径修复预览 (dry-run) ===")
            result = fixer.fix_media_paths(dry_run=True)
        
        print(f"需要修复的任务数: {result['total_tasks_to_fix']}")
        print(f"成功修复: {result['successfully_fixed']}")
        print(f"修复失败: {result['failed_to_fix']}")
        
        if result['conversions']:
            print("\n转换示例:")
            for conv in result['conversions'][:5]:  # 只显示前5个
                if conv['status'] == 'success':
                    print(f"  任务 {conv['task_id']}: {conv['old_path']} -> {conv['new_path']}")
                else:
                    print(f"  任务 {conv['task_id']}: 失败 - {conv.get('error', '未知错误')}")
        
        # 3. 验证修复结果
        if args.verify or args.fix:
            print("\n=== 修复结果验证 ===")
            verification = fixer.verify_paths_after_fix()
            
            analysis_after = verification['analysis']
            print(f"修复后 - 绝对路径: {analysis_after['absolute_paths']}")
            print(f"修复后 - 相对路径: {analysis_after['relative_paths']}")
            
            file_check = verification['file_existence_check']
            print(f"\n文件存在性检查 (前10个文件):")
            print(f"  检查文件数: {file_check['total_checked']}")
            print(f"  存在文件数: {file_check['existing_files']}")
            print(f"  缺失文件数: {file_check['missing_files']}")
            
            if file_check['missing_file_samples']:
                print("  缺失文件示例:")
                for missing_file in file_check['missing_file_samples']:
                    print(f"    {missing_file}")
        
        print("\n=== 使用说明 ===")
        print("1. 首次运行: python fix_media_paths.py (预览模式)")
        print("2. 确认无误后: python fix_media_paths.py --fix (实际修复)")
        print("3. 验证结果: python fix_media_paths.py --verify")
        
    except Exception as e:
        logger.error(f"脚本执行出错: {str(e)}")
        raise
    finally:
        fixer.close()

if __name__ == '__main__':
    main()