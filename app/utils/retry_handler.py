"""重试处理模块

根据项目开发设计核心原则，提供统一的错误处理和重试机制。
"""

import time
import functools
from typing import Callable, Any, Optional, Type, Tuple
from app.utils.logger import get_logger

logger = get_logger(__name__)

class RetryConfig:
    """重试配置"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0,
        exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.exceptions = exceptions


def retry_on_failure(
    config: Optional[RetryConfig] = None,
    log_attempts: bool = True
):
    """重试装饰器
    
    Args:
        config: 重试配置，如果为None则使用默认配置
        log_attempts: 是否记录重试尝试
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 1 and log_attempts:
                        logger.info(f"{func.__name__} 在第 {attempt} 次尝试后成功")
                    return result
                    
                except config.exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts:
                        if log_attempts:
                            logger.error(
                                f"{func.__name__} 在 {config.max_attempts} 次尝试后仍然失败: {e}"
                            )
                        break
                    
                    # 计算延迟时间
                    delay = min(
                        config.delay * (config.backoff_factor ** (attempt - 1)),
                        config.max_delay
                    )
                    
                    if log_attempts:
                        logger.warning(
                            f"{func.__name__} 第 {attempt} 次尝试失败: {e}，"
                            f"{delay:.1f}秒后重试"
                        )
                    
                    time.sleep(delay)
                
                except Exception as e:
                    # 不在重试异常列表中的异常直接抛出
                    if log_attempts:
                        logger.error(f"{func.__name__} 遇到不可重试的异常: {e}")
                    raise
            
            # 所有重试都失败了，抛出最后一个异常
            raise last_exception
        
        return wrapper
    return decorator


class CircuitBreaker:
    """熔断器模式实现"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if self.state == 'OPEN':
                if self._should_attempt_reset():
                    self.state = 'HALF_OPEN'
                    logger.info(f"熔断器进入半开状态: {func.__name__}")
                else:
                    raise Exception(f"熔断器开启，拒绝调用 {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
                
            except self.expected_exception as e:
                self._on_failure()
                raise
        
        return wrapper
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置熔断器"""
        return (
            self.last_failure_time is not None and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        """成功时的处理"""
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
            logger.info("熔断器重置为关闭状态")
        
        self.failure_count = 0
        self.last_failure_time = None
    
    def _on_failure(self):
        """失败时的处理"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"熔断器开启，失败次数: {self.failure_count}")


# 预定义的重试配置
API_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    delay=2.0,
    backoff_factor=2.0,
    max_delay=30.0,
    exceptions=(ConnectionError, TimeoutError)
)

DATABASE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    delay=0.5,
    backoff_factor=1.5,
    max_delay=10.0,
    exceptions=(Exception,)  # 数据库异常类型可能较多
)

FILE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    delay=1.0,
    backoff_factor=1.5,
    max_delay=5.0,
    exceptions=(OSError, IOError, PermissionError)
)


# 便捷装饰器
def retry_api_call(func: Callable) -> Callable:
    """API调用重试装饰器"""
    return retry_on_failure(API_RETRY_CONFIG)(func)


def retry_database_operation(func: Callable) -> Callable:
    """数据库操作重试装饰器"""
    return retry_on_failure(DATABASE_RETRY_CONFIG)(func)


def retry_file_operation(func: Callable) -> Callable:
    """文件操作重试装饰器"""
    return retry_on_failure(FILE_RETRY_CONFIG)(func)


class ErrorHandler:
    """统一错误处理器"""
    
    @staticmethod
    def handle_api_error(e: Exception, operation: str) -> str:
        """处理API错误"""
        error_msg = f"API操作失败 ({operation}): {str(e)}"
        logger.error(error_msg)
        
        # 根据错误类型提供具体的处理建议
        if "401" in str(e) or "Unauthorized" in str(e):
            error_msg += " - 请检查API密钥和权限"
        elif "429" in str(e) or "rate limit" in str(e).lower():
            error_msg += " - API调用频率超限，请稍后重试"
        elif "403" in str(e) or "Forbidden" in str(e):
            error_msg += " - 访问被禁止，请检查权限设置"
        
        return error_msg
    
    @staticmethod
    def handle_file_error(e: Exception, file_path: str, operation: str) -> str:
        """处理文件错误"""
        error_msg = f"文件操作失败 ({operation}): {file_path} - {str(e)}"
        logger.error(error_msg)
        
        # 根据错误类型提供具体的处理建议
        if isinstance(e, FileNotFoundError):
            error_msg += " - 文件或目录不存在"
        elif isinstance(e, PermissionError):
            error_msg += " - 权限不足，请检查文件权限"
        elif isinstance(e, OSError):
            error_msg += " - 系统错误，请检查磁盘空间和文件系统"
        
        return error_msg
    
    @staticmethod
    def handle_database_error(e: Exception, operation: str) -> str:
        """处理数据库错误"""
        error_msg = f"数据库操作失败 ({operation}): {str(e)}"
        logger.error(error_msg)
        
        # 根据错误类型提供具体的处理建议
        if "connection" in str(e).lower():
            error_msg += " - 数据库连接失败，请检查连接配置"
        elif "constraint" in str(e).lower():
            error_msg += " - 数据约束违反，请检查数据完整性"
        elif "timeout" in str(e).lower():
            error_msg += " - 操作超时，请检查数据库性能"
        
        return error_msg