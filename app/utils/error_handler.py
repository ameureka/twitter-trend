#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误处理和监控模块 - 统一的异常处理、告警和系统监控

主要功能:
1. 统一异常处理
2. 错误分类和恢复策略
3. 告警通知机制
4. 系统健康监控
5. 错误统计和分析
6. 自动恢复机制
"""

import traceback
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
from collections import defaultdict, deque
import smtplib
from email.mime.text import MIMEText as MimeText
from email.mime.multipart import MIMEMultipart as MimeMultipart
import json
import requests

from app.utils.logger import get_logger
from app.utils.enhanced_config import get_enhanced_config

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误分类"""
    NETWORK = "network"
    DATABASE = "database"
    API = "api"
    FILE_SYSTEM = "file_system"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    """恢复动作"""
    RETRY = "retry"
    SKIP = "skip"
    RESTART = "restart"
    ALERT = "alert"
    MANUAL = "manual"


@dataclass
class ErrorInfo:
    """错误信息"""
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    exception_type: str
    traceback: str
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_action: Optional[RecoveryAction] = None
    retry_count: int = 0
    resolved: bool = False
    resolution_time: Optional[datetime] = None


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    condition: Callable[[List[ErrorInfo]], bool]
    severity: ErrorSeverity
    cooldown_minutes: int = 30
    last_triggered: Optional[datetime] = None
    enabled: bool = True


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.config = get_enhanced_config()
        self.error_history = deque(maxlen=1000)  # 保留最近1000个错误
        self.error_stats = defaultdict(int)
        self.alert_rules = []
        self.recovery_strategies = {}
        self.notification_channels = []
        self.lock = threading.RLock()
        
        # 初始化默认规则和策略
        self._setup_default_rules()
        self._setup_recovery_strategies()
        self._setup_notification_channels()
        
        # 启动监控线程
        self._start_monitoring()
        
    def handle_error(self, 
                    exception: Exception,
                    context: Dict[str, Any] = None,
                    severity: ErrorSeverity = None,
                    category: ErrorCategory = None) -> ErrorInfo:
        """
        处理错误
        
        Args:
            exception: 异常对象
            context: 错误上下文
            severity: 错误严重程度
            category: 错误分类
            
        Returns:
            错误信息对象
        """
        try:
            # 生成错误ID
            error_id = self._generate_error_id()
            
            # 自动分类和评估严重程度
            if category is None:
                category = self._classify_error(exception)
            if severity is None:
                severity = self._assess_severity(exception, category)
                
            # 创建错误信息
            error_info = ErrorInfo(
                error_id=error_id,
                timestamp=datetime.now(),
                severity=severity,
                category=category,
                message=str(exception),
                exception_type=type(exception).__name__,
                traceback=traceback.format_exc(),
                context=context or {}
            )
            
            # 记录错误
            self._record_error(error_info)
            
            # 执行恢复策略
            recovery_action = self._execute_recovery_strategy(error_info)
            error_info.recovery_action = recovery_action
            
            # 检查告警规则
            self._check_alert_rules()
            
            # 记录日志
            self._log_error(error_info)
            
            return error_info
            
        except Exception as e:
            logger.error(f"错误处理器自身异常: {e}", exc_info=True)
            # 返回基本错误信息
            return ErrorInfo(
                error_id="error_handler_failure",
                timestamp=datetime.now(),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.SYSTEM,
                message=f"错误处理器异常: {str(e)}",
                exception_type="ErrorHandlerException",
                traceback=traceback.format_exc()
            )
            
    def _classify_error(self, exception: Exception) -> ErrorCategory:
        """自动分类错误"""
        exception_name = type(exception).__name__
        exception_message = str(exception).lower()
        
        # 网络相关错误
        if any(keyword in exception_name.lower() for keyword in 
               ['connection', 'timeout', 'network', 'http', 'url']):
            return ErrorCategory.NETWORK
            
        # 数据库相关错误
        if any(keyword in exception_name.lower() for keyword in 
               ['database', 'sql', 'integrity', 'constraint']):
            return ErrorCategory.DATABASE
            
        # API相关错误
        if any(keyword in exception_message for keyword in 
               ['api', 'unauthorized', '401', '403', '404', '500']):
            return ErrorCategory.API
            
        # 文件系统错误
        if any(keyword in exception_name.lower() for keyword in 
               ['file', 'io', 'permission', 'notfound']):
            return ErrorCategory.FILE_SYSTEM
            
        # 认证错误
        if any(keyword in exception_message for keyword in 
               ['auth', 'token', 'credential', 'permission']):
            return ErrorCategory.AUTHENTICATION
            
        # 验证错误
        if any(keyword in exception_name.lower() for keyword in 
               ['validation', 'value', 'type', 'format']):
            return ErrorCategory.VALIDATION
            
        return ErrorCategory.UNKNOWN
        
    def _assess_severity(self, exception: Exception, category: ErrorCategory) -> ErrorSeverity:
        """评估错误严重程度"""
        exception_name = type(exception).__name__
        exception_message = str(exception).lower()
        
        # 关键系统错误
        if any(keyword in exception_name.lower() for keyword in 
               ['memory', 'system', 'fatal', 'critical']):
            return ErrorSeverity.CRITICAL
            
        # 数据库和认证错误通常比较严重
        if category in [ErrorCategory.DATABASE, ErrorCategory.AUTHENTICATION]:
            return ErrorSeverity.HIGH
            
        # 网络和API错误可能是临时的
        if category in [ErrorCategory.NETWORK, ErrorCategory.API]:
            if any(keyword in exception_message for keyword in 
                   ['timeout', 'temporary', 'retry']):
                return ErrorSeverity.MEDIUM
            else:
                return ErrorSeverity.HIGH
                
        # 验证错误通常不太严重
        if category == ErrorCategory.VALIDATION:
            return ErrorSeverity.LOW
            
        return ErrorSeverity.MEDIUM
        
    def _record_error(self, error_info: ErrorInfo):
        """记录错误"""
        with self.lock:
            self.error_history.append(error_info)
            
            # 更新统计
            self.error_stats['total'] += 1
            self.error_stats[f'severity_{error_info.severity.value}'] += 1
            self.error_stats[f'category_{error_info.category.value}'] += 1
            self.error_stats[f'type_{error_info.exception_type}'] += 1
            
    def _execute_recovery_strategy(self, error_info: ErrorInfo) -> Optional[RecoveryAction]:
        """执行恢复策略"""
        strategy_key = f"{error_info.category.value}_{error_info.severity.value}"
        
        if strategy_key in self.recovery_strategies:
            strategy = self.recovery_strategies[strategy_key]
            try:
                return strategy(error_info)
            except Exception as e:
                logger.error(f"执行恢复策略失败: {e}")
                
        return None
        
    def _setup_default_rules(self):
        """设置默认告警规则"""
        # 高频错误告警
        self.alert_rules.append(AlertRule(
            name="高频错误",
            condition=lambda errors: len([e for e in errors 
                                        if e.timestamp > datetime.now() - timedelta(minutes=5)]) > 10,
            severity=ErrorSeverity.HIGH,
            cooldown_minutes=15
        ))
        
        # 关键错误告警
        self.alert_rules.append(AlertRule(
            name="关键错误",
            condition=lambda errors: any(e.severity == ErrorSeverity.CRITICAL 
                                       for e in errors[-5:]),
            severity=ErrorSeverity.CRITICAL,
            cooldown_minutes=5
        ))
        
        # 数据库错误告警
        self.alert_rules.append(AlertRule(
            name="数据库错误",
            condition=lambda errors: len([e for e in errors 
                                        if e.category == ErrorCategory.DATABASE 
                                        and e.timestamp > datetime.now() - timedelta(minutes=10)]) > 3,
            severity=ErrorSeverity.HIGH,
            cooldown_minutes=20
        ))
        
    def _setup_recovery_strategies(self):
        """设置恢复策略"""
        # 网络错误 - 重试
        self.recovery_strategies[f"{ErrorCategory.NETWORK.value}_{ErrorSeverity.MEDIUM.value}"] = \
            lambda error: RecoveryAction.RETRY
        self.recovery_strategies[f"{ErrorCategory.NETWORK.value}_{ErrorSeverity.LOW.value}"] = \
            lambda error: RecoveryAction.RETRY
            
        # API错误 - 重试或跳过
        self.recovery_strategies[f"{ErrorCategory.API.value}_{ErrorSeverity.MEDIUM.value}"] = \
            lambda error: RecoveryAction.RETRY if "timeout" in error.message.lower() else RecoveryAction.SKIP
            
        # 数据库错误 - 告警
        self.recovery_strategies[f"{ErrorCategory.DATABASE.value}_{ErrorSeverity.HIGH.value}"] = \
            lambda error: RecoveryAction.ALERT
            
        # 关键错误 - 手动处理
        self.recovery_strategies[f"{ErrorCategory.SYSTEM.value}_{ErrorSeverity.CRITICAL.value}"] = \
            lambda error: RecoveryAction.MANUAL
            
    def _setup_notification_channels(self):
        """设置通知渠道"""
        config = self.config.get('monitoring', {}).get('notifications', {})
        
        # 邮件通知
        if config.get('email', {}).get('enabled', False):
            self.notification_channels.append(EmailNotifier(config['email']))
            
        # Webhook通知
        if config.get('webhook', {}).get('enabled', False):
            self.notification_channels.append(WebhookNotifier(config['webhook']))
            
        # 日志通知（默认启用）
        self.notification_channels.append(LogNotifier())
        
    def _check_alert_rules(self):
        """检查告警规则"""
        current_time = datetime.now()
        
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
                
            # 检查冷却时间
            if (rule.last_triggered and 
                current_time - rule.last_triggered < timedelta(minutes=rule.cooldown_minutes)):
                continue
                
            # 检查条件
            try:
                if rule.condition(list(self.error_history)):
                    self._trigger_alert(rule)
                    rule.last_triggered = current_time
            except Exception as e:
                logger.error(f"检查告警规则 {rule.name} 失败: {e}")
                
    def _trigger_alert(self, rule: AlertRule):
        """触发告警"""
        alert_data = {
            'rule_name': rule.name,
            'severity': rule.severity.value,
            'timestamp': datetime.now().isoformat(),
            'recent_errors': [{
                'error_id': e.error_id,
                'timestamp': e.timestamp.isoformat(),
                'severity': e.severity.value,
                'category': e.category.value,
                'message': e.message
            } for e in list(self.error_history)[-10:]]
        }
        
        # 发送通知
        for channel in self.notification_channels:
            try:
                channel.send_alert(alert_data)
            except Exception as e:
                logger.error(f"发送告警通知失败: {e}")
                
    def _log_error(self, error_info: ErrorInfo):
        """记录错误日志"""
        log_level = {
            ErrorSeverity.LOW: logger.info,
            ErrorSeverity.MEDIUM: logger.warning,
            ErrorSeverity.HIGH: logger.error,
            ErrorSeverity.CRITICAL: logger.critical
        }.get(error_info.severity, logger.error)
        
        log_level(
            f"错误处理 [{error_info.error_id}] "
            f"类型: {error_info.category.value} "
            f"严重程度: {error_info.severity.value} "
            f"消息: {error_info.message}"
        )
        
    def _generate_error_id(self) -> str:
        """生成错误ID"""
        import uuid
        return f"err_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        
    def _start_monitoring(self):
        """启动监控线程"""
        def monitor_loop():
            while True:
                try:
                    self._cleanup_old_errors()
                    self._update_health_metrics()
                    time.sleep(60)  # 每分钟检查一次
                except Exception as e:
                    logger.error(f"监控循环异常: {e}")
                    time.sleep(10)
                    
        threading.Thread(target=monitor_loop, daemon=True).start()
        
    def _cleanup_old_errors(self):
        """清理旧错误记录"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        with self.lock:
            # 清理24小时前的错误
            while (self.error_history and 
                   self.error_history[0].timestamp < cutoff_time):
                self.error_history.popleft()
                
    def _update_health_metrics(self):
        """更新健康指标"""
        try:
            recent_errors = [e for e in self.error_history 
                           if e.timestamp > datetime.now() - timedelta(hours=1)]
            
            metrics = {
                'error_rate_1h': len(recent_errors),
                'critical_errors_1h': len([e for e in recent_errors 
                                         if e.severity == ErrorSeverity.CRITICAL]),
                'error_categories': {}
            }
            
            # 统计错误分类
            for error in recent_errors:
                category = error.category.value
                if category not in metrics['error_categories']:
                    metrics['error_categories'][category] = 0
                metrics['error_categories'][category] += 1
                
            # 这里可以将指标发送到监控系统
            logger.debug(f"健康指标更新: {metrics}")
            
        except Exception as e:
            logger.error(f"更新健康指标失败: {e}")
            
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        with self.lock:
            recent_errors = [e for e in self.error_history 
                           if e.timestamp > datetime.now() - timedelta(hours=24)]
            
            return {
                'total_errors': len(self.error_history),
                'recent_24h': len(recent_errors),
                'by_severity': {
                    severity.value: len([e for e in recent_errors 
                                       if e.severity == severity])
                    for severity in ErrorSeverity
                },
                'by_category': {
                    category.value: len([e for e in recent_errors 
                                       if e.category == category])
                    for category in ErrorCategory
                },
                'alert_rules': len(self.alert_rules),
                'notification_channels': len(self.notification_channels)
            }
            
    def resolve_error(self, error_id: str, resolution_note: str = None) -> bool:
        """标记错误为已解决"""
        with self.lock:
            for error in self.error_history:
                if error.error_id == error_id:
                    error.resolved = True
                    error.resolution_time = datetime.now()
                    if resolution_note:
                        error.context['resolution_note'] = resolution_note
                    logger.info(f"错误 {error_id} 已标记为解决")
                    return True
        return False


class NotificationChannel:
    """通知渠道基类"""
    
    def send_alert(self, alert_data: Dict[str, Any]):
        """发送告警"""
        raise NotImplementedError


class EmailNotifier(NotificationChannel):
    """邮件通知器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    def send_alert(self, alert_data: Dict[str, Any]):
        """发送邮件告警"""
        try:
            msg = MimeMultipart()
            msg['From'] = self.config['from']
            msg['To'] = ', '.join(self.config['to'])
            msg['Subject'] = f"系统告警: {alert_data['rule_name']}"
            
            body = f"""
            告警规则: {alert_data['rule_name']}
            严重程度: {alert_data['severity']}
            触发时间: {alert_data['timestamp']}
            
            最近错误:
            """
            
            for error in alert_data['recent_errors']:
                body += f"\n- [{error['timestamp']}] {error['category']}: {error['message']}"
                
            msg.attach(MimeText(body, 'plain'))
            
            server = smtplib.SMTP(self.config['smtp_host'], self.config['smtp_port'])
            if self.config.get('use_tls', True):
                server.starttls()
            if self.config.get('username'):
                server.login(self.config['username'], self.config['password'])
                
            server.send_message(msg)
            server.quit()
            
            logger.info("邮件告警发送成功")
            
        except Exception as e:
            logger.error(f"发送邮件告警失败: {e}")


class WebhookNotifier(NotificationChannel):
    """Webhook通知器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    def send_alert(self, alert_data: Dict[str, Any]):
        """发送Webhook告警"""
        try:
            response = requests.post(
                self.config['url'],
                json=alert_data,
                headers=self.config.get('headers', {}),
                timeout=10
            )
            response.raise_for_status()
            
            logger.info("Webhook告警发送成功")
            
        except Exception as e:
            logger.error(f"发送Webhook告警失败: {e}")


class LogNotifier(NotificationChannel):
    """日志通知器"""
    
    def send_alert(self, alert_data: Dict[str, Any]):
        """记录告警日志"""
        logger.warning(
            f"系统告警触发: {alert_data['rule_name']} "
            f"严重程度: {alert_data['severity']} "
            f"最近错误数: {len(alert_data['recent_errors'])}"
        )


# 全局错误处理器实例
_error_handler = None
_error_handler_lock = threading.Lock()


def get_error_handler() -> ErrorHandler:
    """获取错误处理器实例"""
    global _error_handler
    
    with _error_handler_lock:
        if _error_handler is None:
            _error_handler = ErrorHandler()
            
    return _error_handler


def handle_error(exception: Exception, 
                context: Dict[str, Any] = None,
                severity: ErrorSeverity = None,
                category: ErrorCategory = None) -> ErrorInfo:
    """处理错误的便捷函数"""
    return get_error_handler().handle_error(exception, context, severity, category)


def error_handler_decorator(category: ErrorCategory = None, 
                          severity: ErrorSeverity = None,
                          reraise: bool = True):
    """错误处理装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = {
                    'function': func.__name__,
                    'args': str(args)[:200],
                    'kwargs': str(kwargs)[:200]
                }
                handle_error(e, context, severity, category)
                if reraise:
                    raise
                return None
        return wrapper
    return decorator