#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库路径修复脚本

主要功能:
1. 修复数据库中的硬编码绝对路径
2. 将绝对路径转换为相对路径
3. 支持macOS和Linux路径格式转换
4. 备份原始数据库
"""

import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.logger import get_logger
from app.utils.path_manager import get_path_manager
from app.database.db_manager import EnhancedDatabaseManager

logger = get_logger(__name__)


class DatabasePathFixer:
    """数据库路径修复器"""
    
    def __init__(self):
        self.path_manager = get_path_manager()
        self.db_manager = EnhancedDatabaseManager()
        self.db_path = self.path_manager.get_database_path()
        
    def backup_database(self) -> str:
        """备份数据库"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.db_path.parent / f"twitter_publisher_backup_{timestamp}.db"
        
        try:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"数据库备份成功: {backup_path}")
            return str(backup_path)
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            raise
    
    def analyze_paths(self) -> Dict[str, Any]:
        """分析数据库中的路径问题"""
        analysis = {
            'total_tasks': 0,
            'problematic_paths': [],
            'path_patterns': {},
            'conversion_plan': []
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询所有任务的媒体路径
            cursor.execute("SELECT id, media_path FROM publishing_tasks")
            tasks = cursor.fetchall()
            
            analysis['total_tasks'] = len(tasks)
            
            for task_id, media_path in tasks:
                # 分析媒体路径
                if media_path:
                    path_info = self._analyze_single_path(media_path)
                    if path_info['needs_conversion']:
                        analysis['problematic_paths'].append({
                            'task_id': task_id,
                            'field': 'media_path',
                            'original_path': media_path,
                            'converted_path': path_info['converted_path'],
                            'pattern': path_info['pattern']
                        })
                        
                        pattern = path_info['pattern']
                        if pattern not in analysis['path_patterns']:
                            analysis['path_patterns'][pattern] = 0
                        analysis['path_patterns'][pattern] += 1
            
            conn.close()
            
            # 生成转换计划
            analysis['conversion_plan'] = self._generate_conversion_plan(analysis['problematic_paths'])
            
            return analysis
            
        except Exception as e:
            logger.error(f"路径分析失败: {e}")
            raise
    
    def _analyze_single_path(self, path: str) -> Dict[str, Any]:
        """分析单个路径"""
        result = {
            'needs_conversion': False,
            'pattern': 'unknown',
            'converted_path': path
        }
        
        # 检测项目路径模式（跨平台兼容）
        project_name = 'twitter-trend'
        if project_name in path:
            result['needs_conversion'] = True
            result['pattern'] = 'project_absolute_path'
            # 提取相对路径
            parts = path.split(project_name)
            if len(parts) > 1:
                relative_part = parts[1].lstrip('/').lstrip('\\')
                result['converted_path'] = relative_part
        
        # 检测其他绝对路径模式
        elif '/data2/twitter-trend' in path:
            result['needs_conversion'] = True
            result['pattern'] = 'linux_data2'
            parts = path.split('/data2/twitter-trend')
            if len(parts) > 1:
                relative_part = parts[1].lstrip('/')
                result['converted_path'] = relative_part
        
        # 检测其他可能的绝对路径
        elif path.startswith('/') and 'twitter-trend' in path:
            result['needs_conversion'] = True
            result['pattern'] = 'other_absolute'
            # 尝试提取相对路径
            for pattern in ['twitter-trend', 'twitter_trend']:
                if pattern in path:
                    parts = path.split(pattern)
                    if len(parts) > 1:
                        relative_part = parts[1].lstrip('/')
                        result['converted_path'] = relative_part
                        break
        
        return result
    
    def _generate_conversion_plan(self, problematic_paths: List[Dict]) -> List[Dict]:
        """生成转换计划"""
        plan = []
        
        # 按任务ID分组
        tasks_by_id = {}
        for item in problematic_paths:
            task_id = item['task_id']
            if task_id not in tasks_by_id:
                tasks_by_id[task_id] = {'task_id': task_id, 'updates': {}}
            
            tasks_by_id[task_id]['updates'][item['field']] = item['converted_path']
        
        # 转换为计划列表
        for task_info in tasks_by_id.values():
            plan.append(task_info)
        
        return plan
    
    def fix_paths(self, dry_run: bool = True) -> Dict[str, Any]:
        """修复数据库中的路径"""
        result = {
            'success': False,
            'backup_path': '',
            'total_updated': 0,
            'errors': []
        }
        
        try:
            # 分析路径问题
            analysis = self.analyze_paths()
            
            if not analysis['problematic_paths']:
                logger.info("没有发现需要修复的路径")
                result['success'] = True
                return result
            
            logger.info(f"发现 {len(analysis['problematic_paths'])} 个需要修复的路径")
            
            if not dry_run:
                # 备份数据库
                result['backup_path'] = self.backup_database()
                
                # 执行路径修复
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                try:
                    for plan_item in analysis['conversion_plan']:
                        task_id = plan_item['task_id']
                        updates = plan_item['updates']
                        
                        # 构建UPDATE语句
                        set_clauses = []
                        params = []
                        
                        for field, new_path in updates.items():
                            set_clauses.append(f"{field} = ?")
                            params.append(new_path)
                        
                        params.append(task_id)
                        
                        sql = f"UPDATE publishing_tasks SET {', '.join(set_clauses)} WHERE id = ?"
                        cursor.execute(sql, params)
                        
                        result['total_updated'] += 1
                        logger.info(f"更新任务 {task_id}: {updates}")
                    
                    conn.commit()
                    logger.info(f"路径修复完成，共更新 {result['total_updated']} 个任务")
                    
                except Exception as e:
                    conn.rollback()
                    raise e
                finally:
                    conn.close()
            else:
                logger.info("干运行模式，不会实际修改数据库")
                for plan_item in analysis['conversion_plan']:
                    logger.info(f"计划更新任务 {plan_item['task_id']}: {plan_item['updates']}")
            
            result['success'] = True
            
        except Exception as e:
            error_msg = f"路径修复失败: {e}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
        
        return result
    
    def validate_fixed_paths(self) -> Dict[str, Any]:
        """验证修复后的路径"""
        validation = {
            'total_tasks': 0,
            'valid_paths': 0,
            'invalid_paths': [],
            'success_rate': 0.0
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, media_path FROM publishing_tasks")
            tasks = cursor.fetchall()
            
            validation['total_tasks'] = len(tasks)
            
            for task_id, media_path in tasks:
                # 验证媒体路径
                if media_path:
                    full_path = self.path_manager.normalize_path(media_path)
                    if full_path.exists():
                        validation['valid_paths'] += 1
                    else:
                        validation['invalid_paths'].append({
                            'task_id': task_id,
                            'field': 'media_path',
                            'path': media_path,
                            'full_path': str(full_path)
                        })
            
            conn.close()
            
            total_paths = validation['total_tasks']  # 每个任务有1个路径
            if total_paths > 0:
                validation['success_rate'] = validation['valid_paths'] / total_paths * 100
            
        except Exception as e:
            logger.error(f"路径验证失败: {e}")
        
        return validation
    
    def print_analysis_report(self, analysis: Dict[str, Any]):
        """打印分析报告"""
        print("\n=== 数据库路径分析报告 ===")
        print(f"总任务数: {analysis['total_tasks']}")
        print(f"问题路径数: {len(analysis['problematic_paths'])}")
        
        if analysis['path_patterns']:
            print("\n路径模式分布:")
            for pattern, count in analysis['path_patterns'].items():
                print(f"  {pattern}: {count} 个")
        
        if analysis['conversion_plan']:
            print(f"\n转换计划: {len(analysis['conversion_plan'])} 个任务需要更新")
            
            # 显示前5个示例
            print("\n示例转换:")
            for i, item in enumerate(analysis['problematic_paths'][:5]):
                print(f"  任务 {item['task_id']} ({item['field']}):")
                print(f"    原路径: {item['original_path']}")
                print(f"    新路径: {item['converted_path']}")
                print()
        
        print("\n")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='数据库路径修复工具')
    parser.add_argument('--analyze', action='store_true', help='分析路径问题')
    parser.add_argument('--fix', action='store_true', help='修复路径问题')
    parser.add_argument('--validate', action='store_true', help='验证修复结果')
    parser.add_argument('--dry-run', action='store_true', help='干运行模式（不实际修改）')
    
    args = parser.parse_args()
    
    fixer = DatabasePathFixer()
    
    if args.analyze:
        print("正在分析数据库路径...")
        analysis = fixer.analyze_paths()
        fixer.print_analysis_report(analysis)
    
    elif args.fix:
        print("正在修复数据库路径...")
        result = fixer.fix_paths(dry_run=args.dry_run)
        
        if result['success']:
            print(f"路径修复完成！")
            if result['backup_path']:
                print(f"备份文件: {result['backup_path']}")
            print(f"更新任务数: {result['total_updated']}")
        else:
            print("路径修复失败:")
            for error in result['errors']:
                print(f"  {error}")
    
    elif args.validate:
        print("正在验证路径...")
        validation = fixer.validate_fixed_paths()
        
        print(f"\n=== 路径验证结果 ===")
        print(f"总任务数: {validation['total_tasks']}")
        print(f"有效路径数: {validation['valid_paths']}")
        print(f"无效路径数: {len(validation['invalid_paths'])}")
        print(f"成功率: {validation['success_rate']:.1f}%")
        
        if validation['invalid_paths']:
            print("\n无效路径:")
            for item in validation['invalid_paths'][:10]:  # 只显示前10个
                print(f"  任务 {item['task_id']} ({item['field']}): {item['path']}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()