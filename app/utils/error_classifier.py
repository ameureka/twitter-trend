#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误分类器 - 智能重试策略
根据TWITTER_OPTIMIZATION_PLAN.md第三阶段要求实现

主要功能:
1. 区分错误类型的重试策略
2. API限制错误：延长重试间隔
3. 网络错误：快速重试
4. 内容错误：人工介入标记
"""

import re
from enum import Enum
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta
from app.utils.logger import get_logger

logger = get_logger(__name__)

class ErrorType(Enum):
    """错误类型枚举"""
    RATE_LIMIT = "rate_limit"      # API速率限制
    NETWORK = "network"            # 网络错误
    CONTENT = "content"            # 内容错误
    AUTH = "authentication"        # 认证错误
    MEDIA = "media"               # 媒体文件错误
    SYSTEM = "system"             # 系统错误
    UNKNOWN = "unknown"           # 未知错误

class RetryStrategy:
    """重试策略配置"""
    
    def __init__(self):
        # 根据优化计划配置重试策略
        self.strategies = {
            ErrorType.RATE_LIMIT: {
                'base_delay': 1800,      # 30分钟
                'max_retries': 3,
                'exponential_backoff': True,
                'max_delay': 7200,       # 2小时
                'human_intervention': False
            },
            ErrorType.NETWORK: {
                'base_delay': 120,       # 2分钟
                'max_retries': 5,
                'exponential_backoff': True,
                'max_delay': 600,        # 10分钟
                'human_intervention': False
            },
            ErrorType.CONTENT: {
                'base_delay': None,      # 不重试
                'max_retries': 0,
                'exponential_backoff': False,
                'max_delay': 0,
                'human_intervention': True  # 需要人工介入
            },
            ErrorType.AUTH: {
                'base_delay': 3600,      # 1小时
                'max_retries': 2,
                'exponential_backoff': False,
                'max_delay': 3600,
                'human_intervention': True
            },
            ErrorType.MEDIA: {
                'base_delay': 300,       # 5分钟
                'max_retries': 3,
                'exponential_backoff': True,
                'max_delay': 1800,       # 30分钟
                'human_intervention': False
            },
            ErrorType.SYSTEM: {
                'base_delay': 300,       # 5分钟
                'max_retries': 3,
                'exponential_backoff': True,
                'max_delay': 900,        # 15分钟
                'human_intervention': False
            },
            ErrorType.UNKNOWN: {
                'base_delay': 600,       # 10分钟
                'max_retries': 2,
                'exponential_backoff': True,
                'max_delay': 1800,       # 30分钟
                'human_intervention': False
            }
        }

class ErrorClassifier:
    """智能错误分类器"""
    
    def __init__(self):
        self.retry_strategy = RetryStrategy()
        
        # 错误模式匹配规则
        self.error_patterns = {
            ErrorType.RATE_LIMIT: [
                r'rate.?limit',
                r'too many requests',
                r'429',
                r'quota exceeded',
                r'limit exceeded',
                r'rate.*exceeded'
            ],
            ErrorType.NETWORK: [
                r'connection.*error',
                r'network.*error',
                r'timeout',
                r'connection.*reset',
                r'connection.*refused',
                r'dns.*error',
                r'socket.*error',
                r'http.*error.*5\d{2}',  # 5xx错误
                r'request.*timeout'
            ],
            ErrorType.CONTENT: [
                r'content.*too.*long',
                r'invalid.*content',
                r'duplicate.*content',
                r'character.*limit',
                r'text.*too.*long',
                r'content.*validation',
                r'inappropriate.*content',
                r'banned.*content'
            ],
            ErrorType.AUTH: [
                r'unauthorized',
                r'authentication.*failed',
                r'invalid.*credentials',
                r'access.*denied',
                r'forbidden',
                r'401',
                r'403',
                r'token.*expired',
                r'invalid.*token'
            ],
            ErrorType.MEDIA: [
                r'media.*error',
                r'file.*not.*found',
                r'invalid.*media',
                r'media.*too.*large',
                r'unsupported.*format',
                r'upload.*failed',
                r'media.*processing.*failed',
                r'file.*size.*exceeded'
            ],
            ErrorType.SYSTEM: [
                r'database.*error',
                r'internal.*error',
                r'system.*error',
                r'memory.*error',
                r'disk.*space',
                r'permission.*denied',
                r'file.*system.*error',
                r'任务执行超时',  # Phase 3.3: 超时错误支持
                r'execution.*timeout',
                r'task.*timeout'
            ]
        }
        
    def classify_error(self, error: Union[str, Exception]) -> ErrorType:
        """
        分类错误类型
        
        Args:
            error: 错误信息（字符串或异常对象）
            
        Returns:
            ErrorType: 错误类型
        """
        error_text = str(error).lower() if error else ""
        
        # 特殊处理常见异常类型
        if isinstance(error, Exception):
            exception_name = type(error).__name__.lower()
            
            # 网络相关异常
            if any(name in exception_name for name in ['connection', 'timeout', 'network', 'socket']):
                logger.debug(f"根据异常类型 {exception_name} 分类为网络错误")
                return ErrorType.NETWORK
                
            # 文件相关异常
            if any(name in exception_name for name in ['filenotfound', 'ioerror', 'oserror']):
                logger.debug(f"根据异常类型 {exception_name} 分类为媒体错误")
                return ErrorType.MEDIA
        
        # 模式匹配分类
        for error_type, patterns in self.error_patterns.items():
            for pattern in patterns:
                if re.search(pattern, error_text, re.IGNORECASE):
                    logger.debug(f"根据模式 '{pattern}' 分类为 {error_type.value}")
                    return error_type
        
        logger.debug(f"无法分类错误，归类为未知错误: {error_text[:100]}")
        return ErrorType.UNKNOWN
    
    def get_retry_config(self, error_type: ErrorType) -> Dict[str, Any]:
        """
        获取错误类型的重试配置
        
        Args:
            error_type: 错误类型
            
        Returns:
            Dict: 重试配置
        """
        return self.retry_strategy.strategies.get(error_type, self.retry_strategy.strategies[ErrorType.UNKNOWN])
    
    def calculate_retry_delay(self, error_type: ErrorType, attempt: int) -> Optional[int]:
        """
        计算重试延迟时间
        
        Args:
            error_type: 错误类型
            attempt: 重试次数（从1开始）
            
        Returns:
            Optional[int]: 延迟秒数，None表示不重试
        """
        config = self.get_retry_config(error_type)
        
        if config['base_delay'] is None or attempt > config['max_retries']:
            return None
            
        base_delay = config['base_delay']
        
        if config['exponential_backoff']:
            # 指数退避：delay = base_delay * (2 ^ (attempt - 1))
            delay = base_delay * (2 ** (attempt - 1))
            delay = min(delay, config['max_delay'])
        else:
            delay = base_delay
            
        logger.info(f"错误类型 {error_type.value} 第{attempt}次重试延迟: {delay}秒")
        return delay
    
    def should_retry(self, error_type: ErrorType, current_attempt: int) -> bool:
        """
        判断是否应该重试
        
        Args:
            error_type: 错误类型
            current_attempt: 当前重试次数
            
        Returns:
            bool: 是否应该重试
        """
        config = self.get_retry_config(error_type)
        
        if config['human_intervention']:
            logger.warning(f"错误类型 {error_type.value} 需要人工介入，不重试")
            return False
            
        should_retry = current_attempt < config['max_retries']
        logger.info(f"错误类型 {error_type.value} 当前尝试{current_attempt}次，最大{config['max_retries']}次，应该重试: {should_retry}")
        
        return should_retry
    
    def needs_human_intervention(self, error_type: ErrorType) -> bool:
        """
        判断是否需要人工介入
        
        Args:
            error_type: 错误类型
            
        Returns:
            bool: 是否需要人工介入
        """
        config = self.get_retry_config(error_type)
        return config.get('human_intervention', False)
    
    def get_next_retry_time(self, error_type: ErrorType, attempt: int) -> Optional[datetime]:
        """
        获取下次重试时间
        
        Args:
            error_type: 错误类型
            attempt: 重试次数
            
        Returns:
            Optional[datetime]: 下次重试时间，None表示不重试
        """
        delay = self.calculate_retry_delay(error_type, attempt)
        
        if delay is None:
            return None
            
        next_time = datetime.now() + timedelta(seconds=delay)
        logger.info(f"下次重试时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return next_time
    
    def analyze_error_stats(self, errors: list) -> Dict[str, Any]:
        """
        分析错误统计信息
        
        Args:
            errors: 错误列表
            
        Returns:
            Dict: 错误统计
        """
        if not errors:
            return {}
            
        error_counts = {}
        for error in errors:
            error_type = self.classify_error(error)
            error_counts[error_type.value] = error_counts.get(error_type.value, 0) + 1
            
        total_errors = len(errors)
        error_stats = {
            'total_errors': total_errors,
            'error_distribution': error_counts,
            'error_percentages': {
                error_type: (count / total_errors) * 100 
                for error_type, count in error_counts.items()
            }
        }
        
        return error_stats

# 全局实例
error_classifier = ErrorClassifier()

def classify_and_handle_error(error: Union[str, Exception], current_attempt: int = 1) -> Dict[str, Any]:
    """
    便捷函数：分类错误并返回处理建议
    
    Args:
        error: 错误信息
        current_attempt: 当前重试次数
        
    Returns:
        Dict: 错误处理建议
    """
    error_type = error_classifier.classify_error(error)
    
    return {
        'error_type': error_type.value,
        'should_retry': error_classifier.should_retry(error_type, current_attempt),
        'retry_delay': error_classifier.calculate_retry_delay(error_type, current_attempt),
        'next_retry_time': error_classifier.get_next_retry_time(error_type, current_attempt),
        'needs_human_intervention': error_classifier.needs_human_intervention(error_type),
        'retry_config': error_classifier.get_retry_config(error_type)
    }