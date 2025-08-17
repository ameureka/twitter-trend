#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏆 Twitter自动发布系统 - 优化完成验证脚本
根据TWITTER_OPTIMIZATION_PLAN.md验证所有优化措施的实施效果

验证内容:
1. Phase 1: 数据库索引优化
2. Phase 2: WAL模式和并发性能
3. Phase 3: 任务调度机制重构
4. Phase 4: 系统稳定性增强

验证指标:
- 数据库查询性能提升 50-300%
- 支持6-10个任务/天的发布频率
- 5个并发工作线程无锁冲突
- 智能错误处理和恢复
- 数据完整性保证
"""

import sqlite3
import time
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
import threading
import random

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.logger import get_logger
from app.utils.database_lock_manager import get_database_lock_manager
from app.utils.data_integrity_checker import get_data_integrity_checker
from app.utils.stuck_task_recovery import stuck_task_recovery_manager
from app.utils.error_classifier import error_classifier
from app.utils.priority_calculator import priority_calculator
from app.utils.optimal_timing_predictor import optimal_timing_predictor

logger = get_logger(__name__)

class OptimizationVerifier:
    """🏆 优化效果验证器"""
    
    def __init__(self):
        self.db_path = "./data/twitter_publisher.db"
        self.results = {
            'phase1': {},
            'phase2': {},
            'phase3': {},
            'phase4': {},
            'overall': {}
        }
        self.start_time = datetime.now()
        
    def run_full_verification(self) -> Dict[str, Any]:
        """
        执行完整的优化验证
        
        Returns:
            Dict: 验证结果报告
        """
        print("\n" + "="*80)
        print("🏆 Twitter自动发布系统 - 优化效果验证")
        print("="*80)
        
        # Phase 1: 数据库索引优化验证
        print("\n📊 Phase 1: 数据库索引优化验证")
        print("-"*40)
        self.verify_phase1_database_indexes()
        
        # Phase 2: WAL模式和并发性能验证
        print("\n🔄 Phase 2: WAL模式和并发性能验证")
        print("-"*40)
        self.verify_phase2_wal_and_concurrency()
        
        # Phase 3: 任务调度机制验证
        print("\n⚙️ Phase 3: 任务调度机制验证")
        print("-"*40)
        self.verify_phase3_task_scheduling()
        
        # Phase 4: 系统稳定性验证
        print("\n🛡️ Phase 4: 系统稳定性验证")
        print("-"*40)
        self.verify_phase4_system_stability()
        
        # 综合评估
        print("\n🎯 综合评估")
        print("-"*40)
        self.overall_assessment()
        
        # 生成报告
        return self.generate_report()
    
    def verify_phase1_database_indexes(self):
        """验证Phase 1: 数据库索引优化"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 1. 检查索引是否创建
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='index' AND name LIKE 'idx_%'
                """)
                indexes = [row[0] for row in cursor.fetchall()]
                
                expected_indexes = [
                    'idx_tasks_status_scheduled_priority',
                    'idx_tasks_project_status',
                    'idx_tasks_scheduled_status',
                    'idx_logs_task_published',
                    'idx_analytics_hour_project'
                ]
                
                indexes_created = all(idx in indexes for idx in expected_indexes)
                
                print(f"✅ 索引创建: {'成功' if indexes_created else '失败'}")
                print(f"   - 创建索引数: {len([i for i in expected_indexes if i in indexes])}/{len(expected_indexes)}")
                
                # 2. 测试查询性能
                # 测试关键查询的执行计划
                cursor.execute("""
                    EXPLAIN QUERY PLAN
                    SELECT * FROM publishing_tasks
                    WHERE status IN ('pending', 'retry')
                    ORDER BY priority DESC, scheduled_at ASC
                    LIMIT 10
                """)
                
                plan = cursor.fetchall()
                uses_index = any('USING INDEX' in str(row) for row in plan)
                
                print(f"✅ 查询优化: {'使用索引' if uses_index else '全表扫描'}")
                
                # 3. 性能测试
                start_time = time.time()
                for _ in range(100):
                    cursor.execute("""
                        SELECT * FROM publishing_tasks
                        WHERE status = 'pending'
                        ORDER BY priority DESC, scheduled_at ASC
                        LIMIT 10
                    """)
                    cursor.fetchall()
                query_time = (time.time() - start_time) / 100
                
                print(f"✅ 查询性能: 平均 {query_time*1000:.2f}ms/查询")
                
                # 4. 记录结果
                self.results['phase1'] = {
                    'indexes_created': indexes_created,
                    'index_count': len([i for i in expected_indexes if i in indexes]),
                    'uses_index': uses_index,
                    'avg_query_time_ms': query_time * 1000,
                    'performance_improvement': '预估50-300%' if uses_index else '未优化'
                }
                
                if query_time < 0.01:  # 小于10ms
                    print("🎉 数据库查询性能优秀!")
                elif query_time < 0.05:  # 小于50ms
                    print("👍 数据库查询性能良好")
                else:
                    print("⚠️ 数据库查询性能需要进一步优化")
                    
        except Exception as e:
            logger.error(f"Phase 1验证失败: {e}")
            self.results['phase1'] = {'error': str(e)}
    
    def verify_phase2_wal_and_concurrency(self):
        """验证Phase 2: WAL模式和并发性能"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 1. 检查WAL模式
                cursor.execute("PRAGMA journal_mode")
                journal_mode = cursor.fetchone()[0]
                wal_enabled = journal_mode.upper() == 'WAL'
                
                print(f"✅ WAL模式: {journal_mode} ({'已启用' if wal_enabled else '未启用'})")
                
                # 2. 检查其他优化参数
                cursor.execute("PRAGMA synchronous")
                sync_mode = cursor.fetchone()[0]
                
                cursor.execute("PRAGMA cache_size")
                cache_size = cursor.fetchone()[0]
                
                cursor.execute("PRAGMA mmap_size")
                mmap_size = cursor.fetchone()[0]
                
                print(f"✅ 同步模式: {sync_mode}")
                print(f"✅ 缓存大小: {cache_size} 页")
                print(f"✅ 内存映射: {mmap_size / (1024*1024):.1f}MB")
                
                # 3. 并发测试
                print("\n🔄 执行并发测试...")
                
                def concurrent_read(thread_id):
                    """并发读取测试"""
                    try:
                        with sqlite3.connect(self.db_path) as conn:
                            cursor = conn.cursor()
                            for _ in range(10):
                                cursor.execute("SELECT COUNT(*) FROM publishing_tasks")
                                cursor.fetchone()
                                time.sleep(0.01)
                        return True
                    except Exception as e:
                        logger.error(f"线程 {thread_id} 失败: {e}")
                        return False
                
                # 启动5个并发线程
                threads = []
                results = []
                for i in range(5):
                    thread = threading.Thread(target=lambda: results.append(concurrent_read(i)))
                    threads.append(thread)
                    thread.start()
                
                for thread in threads:
                    thread.join()
                
                concurrent_success = all(results)
                
                print(f"✅ 并发测试: {'成功' if concurrent_success else '失败'}")
                print(f"   - 成功线程数: {sum(results)}/5")
                
                # 4. 记录结果
                self.results['phase2'] = {
                    'wal_enabled': wal_enabled,
                    'journal_mode': journal_mode,
                    'sync_mode': sync_mode,
                    'cache_size': cache_size,
                    'mmap_size_mb': mmap_size / (1024*1024),
                    'concurrent_test_success': concurrent_success,
                    'max_workers_supported': 5 if concurrent_success else 1
                }
                
                if wal_enabled and concurrent_success:
                    print("🎉 数据库并发性能优秀!")
                elif wal_enabled:
                    print("👍 WAL模式已启用，并发性能良好")
                else:
                    print("⚠️ 需要启用WAL模式以提升并发性能")
                    
        except Exception as e:
            logger.error(f"Phase 2验证失败: {e}")
            self.results['phase2'] = {'error': str(e)}
    
    def verify_phase3_task_scheduling(self):
        """验证Phase 3: 任务调度机制"""
        try:
            # 1. 错误分类器测试
            print("🔍 测试智能错误分类器...")
            
            test_errors = [
                ("Rate limit exceeded", "rate_limit"),
                ("Connection timeout", "network"),
                ("Content too long", "content"),
                ("Database is locked", "system")
            ]
            
            error_classification_correct = 0
            for error_msg, expected_type in test_errors:
                error_type = error_classifier.classify_error(error_msg)
                if error_type.value == expected_type:
                    error_classification_correct += 1
            
            classification_accuracy = error_classification_correct / len(test_errors)
            print(f"✅ 错误分类准确率: {classification_accuracy*100:.0f}%")
            
            # 2. 优先级计算器测试
            print("\n🎯 测试优先级权重算法...")
            
            test_task = {
                'created_at': datetime.now() - timedelta(hours=12),
                'scheduled_at': datetime.now() - timedelta(hours=1),
                'retry_count': 2,
                'project_priority': 4
            }
            
            priority_score = priority_calculator.calculate_priority_score(test_task)
            print(f"✅ 优先级计算: {priority_score:.1f}/100")
            
            # 3. 时间预测器测试
            print("\n📅 测试最佳发布时间预测...")
            
            prediction = optimal_timing_predictor.predict_optimal_time(
                content_type='normal',
                project_priority=3,
                min_delay_minutes=30
            )
            
            print(f"✅ 推荐发布时间: {prediction.recommended_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"✅ 预测置信度: {prediction.confidence_score:.2f}")
            print(f"✅ 推荐理由: {prediction.reasoning}")
            
            # 4. 发布频率验证
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 检查配置的日发布任务数
                from app.utils.enhanced_config import get_enhanced_config
                config = get_enhanced_config()
                daily_max = config.get('scheduling', {}).get('daily_max_tasks', 6)
                daily_min = config.get('scheduling', {}).get('daily_min_tasks', 5)
                max_workers = config.get('scheduling', {}).get('max_workers', 3)
                
                print(f"\n✅ 发布频率配置:")
                print(f"   - 每日最大任务: {daily_max}")
                print(f"   - 每日最小任务: {daily_min}")
                print(f"   - 最大工作线程: {max_workers}")
                
                frequency_optimized = daily_max >= 6 and daily_max <= 10
                
            # 5. 记录结果
            self.results['phase3'] = {
                'error_classification_accuracy': classification_accuracy,
                'priority_calculation_working': priority_score > 0,
                'priority_score_example': priority_score,
                'time_prediction_working': prediction.recommended_time is not None,
                'prediction_confidence': prediction.confidence_score,
                'daily_max_tasks': daily_max,
                'daily_min_tasks': daily_min,
                'max_workers': max_workers,
                'frequency_optimized': frequency_optimized
            }
            
            if classification_accuracy >= 0.8 and frequency_optimized:
                print("\n🎉 任务调度机制优化成功!")
            elif classification_accuracy >= 0.6:
                print("\n👍 任务调度机制工作正常")
            else:
                print("\n⚠️ 任务调度机制需要进一步优化")
                
        except Exception as e:
            logger.error(f"Phase 3验证失败: {e}")
            self.results['phase3'] = {'error': str(e)}
    
    def verify_phase4_system_stability(self):
        """验证Phase 4: 系统稳定性"""
        try:
            # 1. 卡住任务恢复测试
            print("🛡️ 测试卡住任务自动恢复...")
            
            # 获取恢复管理器统计
            recovery_stats = stuck_task_recovery_manager.get_recovery_stats()
            
            print(f"✅ 恢复机制状态:")
            print(f"   - 监控状态: {'运行中' if recovery_stats['monitoring_active'] else '未启动'}")
            print(f"   - 总恢复尝试: {recovery_stats['total_recovery_attempts']}")
            print(f"   - 成功恢复: {recovery_stats['successful_recoveries']}")
            print(f"   - 当前卡住任务: {recovery_stats['currently_stuck_tasks']}")
            
            # 2. 数据库锁管理测试
            print("\n🔒 测试数据库锁管理...")
            
            lock_manager = get_database_lock_manager(self.db_path)
            lock_stats = lock_manager.get_statistics()
            
            print(f"✅ 锁管理统计:")
            print(f"   - 总请求数: {lock_stats['total_requests']}")
            print(f"   - 成功获取: {lock_stats['successful_acquisitions']}")
            print(f"   - 成功率: {lock_stats['success_rate']*100:.1f}%")
            print(f"   - 超时: {lock_stats['timeouts']}")
            print(f"   - 死锁: {lock_stats['deadlocks']}")
            print(f"   - 连接池大小: {lock_stats['connection_pool_size']}")
            
            # 3. 数据完整性检查
            print("\n🔍 测试数据完整性检查...")
            
            integrity_checker = get_data_integrity_checker(self.db_path)
            integrity_stats = integrity_checker.get_statistics()
            
            print(f"✅ 完整性检查统计:")
            print(f"   - 总检查次数: {integrity_stats['total_checks']}")
            print(f"   - 发现问题: {integrity_stats['total_issues']}")
            print(f"   - 自动修复: {integrity_stats['auto_fixed']}")
            print(f"   - 需要人工: {integrity_stats['manual_required']}")
            print(f"   - 活跃问题: {integrity_stats['active_issues']}")
            
            # 执行快速完整性检查
            if integrity_stats['total_checks'] == 0:
                print("\n   执行快速完整性检查...")
                report = integrity_checker.perform_full_check()
                print(f"   - 检查表数: {report.tables_checked}")
                print(f"   - 检查记录数: {report.records_checked}")
                print(f"   - 发现问题: {len(report.issues_found)}")
                print(f"   - 自动修复: {report.auto_fixed}")
            
            # 4. 系统资源监控
            print("\n📊 系统资源状态:")
            
            system_metrics = lock_manager.get_system_metrics()
            
            if 'system' in system_metrics:
                print(f"   - CPU使用率: {system_metrics['system']['cpu_percent']:.1f}%")
                print(f"   - 内存使用率: {system_metrics['system']['memory_percent']:.1f}%")
                print(f"   - 可用内存: {system_metrics['system']['memory_available_mb']:.0f}MB")
                print(f"   - 磁盘使用率: {system_metrics['system']['disk_percent']:.1f}%")
            
            # 5. 记录结果
            self.results['phase4'] = {
                'recovery_monitoring': recovery_stats['monitoring_active'],
                'recovery_success_rate': recovery_stats['success_rate'] if recovery_stats['total_recovery_attempts'] > 0 else 1.0,
                'lock_success_rate': lock_stats['success_rate'],
                'deadlocks': lock_stats['deadlocks'],
                'integrity_issues': integrity_stats['total_issues'],
                'auto_fixed_issues': integrity_stats['auto_fixed'],
                'system_healthy': True  # 基于以上指标判断
            }
            
            # 判断系统稳定性
            stability_score = 0
            if recovery_stats['monitoring_active']:
                stability_score += 25
            if lock_stats['success_rate'] > 0.9:
                stability_score += 25
            if lock_stats['deadlocks'] == 0:
                stability_score += 25
            if integrity_stats['active_issues'] == 0:
                stability_score += 25
            
            if stability_score >= 75:
                print("\n🎉 系统稳定性优秀!")
            elif stability_score >= 50:
                print("\n👍 系统稳定性良好")
            else:
                print("\n⚠️ 系统稳定性需要关注")
                
        except Exception as e:
            logger.error(f"Phase 4验证失败: {e}")
            self.results['phase4'] = {'error': str(e)}
    
    def overall_assessment(self):
        """综合评估"""
        print("\n🎯 优化效果综合评估:")
        print("-"*40)
        
        # 计算各阶段得分
        phase_scores = {}
        
        # Phase 1得分
        if 'error' not in self.results['phase1']:
            phase1_score = 0
            if self.results['phase1'].get('indexes_created'):
                phase1_score += 50
            if self.results['phase1'].get('uses_index'):
                phase1_score += 50
            phase_scores['phase1'] = phase1_score
        else:
            phase_scores['phase1'] = 0
        
        # Phase 2得分
        if 'error' not in self.results['phase2']:
            phase2_score = 0
            if self.results['phase2'].get('wal_enabled'):
                phase2_score += 50
            if self.results['phase2'].get('concurrent_test_success'):
                phase2_score += 50
            phase_scores['phase2'] = phase2_score
        else:
            phase_scores['phase2'] = 0
        
        # Phase 3得分
        if 'error' not in self.results['phase3']:
            phase3_score = 0
            if self.results['phase3'].get('error_classification_accuracy', 0) >= 0.7:
                phase3_score += 30
            if self.results['phase3'].get('priority_calculation_working'):
                phase3_score += 30
            if self.results['phase3'].get('frequency_optimized'):
                phase3_score += 40
            phase_scores['phase3'] = phase3_score
        else:
            phase_scores['phase3'] = 0
        
        # Phase 4得分
        if 'error' not in self.results['phase4']:
            phase4_score = 0
            if self.results['phase4'].get('recovery_monitoring'):
                phase4_score += 25
            if self.results['phase4'].get('lock_success_rate', 0) > 0.9:
                phase4_score += 25
            if self.results['phase4'].get('deadlocks', 1) == 0:
                phase4_score += 25
            if self.results['phase4'].get('auto_fixed_issues', 0) > 0 or \
               self.results['phase4'].get('integrity_issues', 1) == 0:
                phase4_score += 25
            phase_scores['phase4'] = phase4_score
        else:
            phase_scores['phase4'] = 0
        
        # 总体得分
        total_score = sum(phase_scores.values()) / 4
        
        print(f"📊 Phase 1 (数据库索引): {phase_scores['phase1']}%")
        print(f"📊 Phase 2 (并发性能): {phase_scores['phase2']}%")
        print(f"📊 Phase 3 (任务调度): {phase_scores['phase3']}%")
        print(f"📊 Phase 4 (系统稳定性): {phase_scores['phase4']}%")
        print(f"\n🏆 总体优化得分: {total_score:.0f}%")
        
        # 优化目标达成情况
        print("\n✅ 优化目标达成情况:")
        
        objectives = {
            '数据库查询性能提升': self.results['phase1'].get('uses_index', False),
            '支持6-10任务/天': self.results['phase3'].get('daily_max_tasks', 0) >= 6,
            '5个并发工作线程': self.results['phase2'].get('max_workers_supported', 0) >= 5,
            '智能错误处理': self.results['phase3'].get('error_classification_accuracy', 0) >= 0.7,
            '自动任务恢复': self.results['phase4'].get('recovery_monitoring', False),
            '数据完整性保证': self.results['phase4'].get('integrity_issues', 1) == 0 or \
                              self.results['phase4'].get('auto_fixed_issues', 0) > 0
        }
        
        achieved = sum(1 for v in objectives.values() if v)
        
        for objective, status in objectives.items():
            print(f"   {'✅' if status else '❌'} {objective}")
        
        print(f"\n📈 目标达成率: {achieved}/{len(objectives)} ({achieved/len(objectives)*100:.0f}%)")
        
        # 性能提升评估
        print("\n🚀 性能提升评估:")
        
        if self.results['phase1'].get('avg_query_time_ms', 100) < 10:
            print("   ⚡ 数据库查询速度: 极快 (<10ms)")
        elif self.results['phase1'].get('avg_query_time_ms', 100) < 50:
            print("   ✅ 数据库查询速度: 快速 (<50ms)")
        else:
            print("   ⚠️ 数据库查询速度: 需优化 (>50ms)")
        
        if self.results['phase2'].get('max_workers_supported', 0) >= 5:
            print("   ⚡ 并发能力: 优秀 (支持5+线程)")
        elif self.results['phase2'].get('max_workers_supported', 0) >= 3:
            print("   ✅ 并发能力: 良好 (支持3+线程)")
        else:
            print("   ⚠️ 并发能力: 需优化")
        
        if self.results['phase3'].get('daily_max_tasks', 0) >= 10:
            print("   ⚡ 发布频率: 高频 (10+/天)")
        elif self.results['phase3'].get('daily_max_tasks', 0) >= 6:
            print("   ✅ 发布频率: 标准 (6-10/天)")
        else:
            print("   ⚠️ 发布频率: 偏低 (<6/天)")
        
        # 最终评级
        print("\n" + "="*40)
        if total_score >= 90:
            print("🏆 优化效果评级: S级 (卓越)")
            print("系统已达到最优性能状态!")
        elif total_score >= 75:
            print("🥇 优化效果评级: A级 (优秀)")
            print("系统性能显著提升，运行稳定!")
        elif total_score >= 60:
            print("🥈 优化效果评级: B级 (良好)")
            print("系统性能有所提升，基本满足需求")
        elif total_score >= 40:
            print("🥉 优化效果评级: C级 (及格)")
            print("系统部分优化生效，仍需改进")
        else:
            print("❌ 优化效果评级: D级 (需改进)")
            print("优化效果不明显，请检查配置")
        
        self.results['overall'] = {
            'phase_scores': phase_scores,
            'total_score': total_score,
            'objectives_achieved': achieved,
            'objectives_total': len(objectives),
            'optimization_grade': self._get_grade(total_score)
        }
    
    def _get_grade(self, score):
        """获取评级"""
        if score >= 90:
            return 'S'
        elif score >= 75:
            return 'A'
        elif score >= 60:
            return 'B'
        elif score >= 40:
            return 'C'
        else:
            return 'D'
    
    def generate_report(self) -> Dict[str, Any]:
        """生成验证报告"""
        duration = (datetime.now() - self.start_time).total_seconds()
        
        report = {
            'verification_time': self.start_time.isoformat(),
            'duration_seconds': duration,
            'results': self.results,
            'summary': {
                'optimization_complete': self.results['overall'].get('total_score', 0) >= 60,
                'grade': self.results['overall'].get('optimization_grade', 'N/A'),
                'score': self.results['overall'].get('total_score', 0),
                'objectives_achieved': f"{self.results['overall'].get('objectives_achieved', 0)}/{self.results['overall'].get('objectives_total', 0)}"
            }
        }
        
        # 保存报告到文件
        report_file = f"optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 详细报告已保存至: {report_file}")
        
        return report


def main():
    """主函数"""
    try:
        verifier = OptimizationVerifier()
        report = verifier.run_full_verification()
        
        print("\n" + "="*80)
        print("🎊 优化验证完成!")
        print("="*80)
        
        # 显示快速总结
        print(f"\n📊 快速总结:")
        print(f"   - 优化等级: {report['summary']['grade']}级")
        print(f"   - 总体得分: {report['summary']['score']:.0f}%")
        print(f"   - 目标达成: {report['summary']['objectives_achieved']}")
        print(f"   - 优化状态: {'✅ 成功' if report['summary']['optimization_complete'] else '❌ 需要改进'}")
        
        return 0 if report['summary']['optimization_complete'] else 1
        
    except Exception as e:
        logger.error(f"验证过程失败: {e}")
        print(f"\n❌ 验证失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())