import pytest
import time
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api.middleware import (
    RateLimitMiddleware,
    LoggingMiddleware,
    ErrorHandlingMiddleware,
    CORSMiddleware,
    SecurityHeadersMiddleware
)


class TestRateLimitMiddleware:
    """速率限制中间件测试类"""
    
    @pytest.fixture
    def app_with_rate_limit(self):
        """创建带速率限制的应用"""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        return app
    
    @pytest.mark.api
    def test_rate_limit_within_limit(self, app_with_rate_limit):
        """测试在速率限制内的请求"""
        client = TestClient(app_with_rate_limit)
        
        # 发送请求，应该成功
        response = client.get("/test")
        
        assert response.status_code == 200
        assert response.json() == {"message": "success"}
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
    
    @pytest.mark.api
    def test_rate_limit_exceeded(self):
        """测试超过速率限制"""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=2)  # 很低的限制
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        
        # 发送第一个请求，应该成功
        response1 = client.get("/test")
        assert response1.status_code == 200
        
        # 发送第二个请求，应该成功
        response2 = client.get("/test")
        assert response2.status_code == 200
        
        # 发送第三个请求，应该被限制
        response3 = client.get("/test")
        assert response3.status_code == 429
        assert "Rate limit exceeded" in response3.json()["detail"]
    
    @pytest.mark.api
    def test_rate_limit_different_ips(self):
        """测试不同IP的速率限制"""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=1)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        
        # 模拟不同IP的请求
        with patch('app.api.middleware.RateLimitMiddleware.get_client_ip') as mock_get_ip:
            # 第一个IP
            mock_get_ip.return_value = "192.168.1.1"
            response1 = client.get("/test")
            assert response1.status_code == 200
            
            # 第二个IP
            mock_get_ip.return_value = "192.168.1.2"
            response2 = client.get("/test")
            assert response2.status_code == 200
    
    @pytest.mark.api
    def test_rate_limit_reset_after_window(self):
        """测试时间窗口重置后的速率限制"""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=1)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        
        # 发送第一个请求
        response1 = client.get("/test")
        assert response1.status_code == 200
        
        # 模拟时间过去
        with patch('time.time', return_value=time.time() + 61):  # 61秒后
            response2 = client.get("/test")
            assert response2.status_code == 200
    
    @pytest.mark.api
    def test_rate_limit_headers(self, app_with_rate_limit):
        """测试速率限制响应头"""
        client = TestClient(app_with_rate_limit)
        
        response = client.get("/test")
        
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
        
        limit = int(response.headers["X-RateLimit-Limit"])
        remaining = int(response.headers["X-RateLimit-Remaining"])
        reset_time = int(response.headers["X-RateLimit-Reset"])
        
        assert limit == 60
        assert remaining <= limit
        assert reset_time > time.time()


class TestLoggingMiddleware:
    """日志中间件测试类"""
    
    @pytest.fixture
    def app_with_logging(self):
        """创建带日志的应用"""
        app = FastAPI()
        app.add_middleware(LoggingMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        @app.get("/error")
        async def error_endpoint():
            raise HTTPException(status_code=500, detail="Internal error")
        
        return app
    
    @pytest.mark.api
    def test_logging_successful_request(self, app_with_logging, caplog):
        """测试成功请求的日志记录"""
        client = TestClient(app_with_logging)
        
        with caplog.at_level("INFO"):
            response = client.get("/test")
        
        assert response.status_code == 200
        
        # 检查日志记录
        log_records = [record for record in caplog.records if "GET /test" in record.message]
        assert len(log_records) >= 1
        
        log_message = log_records[0].message
        assert "GET /test" in log_message
        assert "200" in log_message
        assert "ms" in log_message  # 响应时间
    
    @pytest.mark.api
    def test_logging_error_request(self, app_with_logging, caplog):
        """测试错误请求的日志记录"""
        client = TestClient(app_with_logging)
        
        with caplog.at_level("ERROR"):
            response = client.get("/error")
        
        assert response.status_code == 500
        
        # 检查错误日志
        error_records = [record for record in caplog.records if record.levelname == "ERROR"]
        assert len(error_records) >= 1
        
        error_message = error_records[0].message
        assert "GET /error" in error_message
        assert "500" in error_message
    
    @pytest.mark.api
    def test_logging_request_body(self):
        """测试请求体日志记录"""
        app = FastAPI()
        app.add_middleware(LoggingMiddleware, log_request_body=True)
        
        @app.post("/test")
        async def test_endpoint(data: dict):
            return {"received": data}
        
        client = TestClient(app)
        
        with patch('app.api.middleware.logger') as mock_logger:
            response = client.post("/test", json={"key": "value"})
            
            assert response.status_code == 200
            
            # 验证日志调用
            mock_logger.info.assert_called()
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
            
            # 应该有包含请求体的日志
            body_logs = [log for log in log_calls if "key" in log and "value" in log]
            assert len(body_logs) > 0
    
    @pytest.mark.api
    def test_logging_sensitive_data_filtering(self):
        """测试敏感数据过滤"""
        app = FastAPI()
        app.add_middleware(LoggingMiddleware, log_request_body=True)
        
        @app.post("/test")
        async def test_endpoint(data: dict):
            return {"received": "ok"}
        
        client = TestClient(app)
        
        with patch('app.api.middleware.logger') as mock_logger:
            response = client.post("/test", json={
                "username": "testuser",
                "password": "secret123",
                "api_key": "sk-1234567890"
            })
            
            assert response.status_code == 200
            
            # 验证敏感数据被过滤
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
            sensitive_logs = [log for log in log_calls if "secret123" in log or "sk-1234567890" in log]
            assert len(sensitive_logs) == 0
            
            # 但应该有过滤后的日志
            filtered_logs = [log for log in log_calls if "[FILTERED]" in log]
            assert len(filtered_logs) > 0


class TestErrorHandlingMiddleware:
    """错误处理中间件测试类"""
    
    @pytest.fixture
    def app_with_error_handling(self):
        """创建带错误处理的应用"""
        app = FastAPI()
        app.add_middleware(ErrorHandlingMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        @app.get("/http-error")
        async def http_error_endpoint():
            raise HTTPException(status_code=404, detail="Not found")
        
        @app.get("/unexpected-error")
        async def unexpected_error_endpoint():
            raise ValueError("Unexpected error")
        
        @app.get("/validation-error")
        async def validation_error_endpoint(param: int):
            return {"param": param}
        
        return app
    
    @pytest.mark.api
    def test_error_handling_success(self, app_with_error_handling):
        """测试成功请求不受影响"""
        client = TestClient(app_with_error_handling)
        
        response = client.get("/test")
        
        assert response.status_code == 200
        assert response.json() == {"message": "success"}
    
    @pytest.mark.api
    def test_error_handling_http_exception(self, app_with_error_handling):
        """测试HTTP异常处理"""
        client = TestClient(app_with_error_handling)
        
        response = client.get("/http-error")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"
    
    @pytest.mark.api
    def test_error_handling_unexpected_error(self, app_with_error_handling):
        """测试意外错误处理"""
        client = TestClient(app_with_error_handling)
        
        response = client.get("/unexpected-error")
        
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
        assert "error_id" in response.json()  # 应该有错误ID用于追踪
    
    @pytest.mark.api
    def test_error_handling_validation_error(self, app_with_error_handling):
        """测试验证错误处理"""
        client = TestClient(app_with_error_handling)
        
        response = client.get("/validation-error?param=invalid")
        
        assert response.status_code == 422
        assert "validation error" in response.json()["detail"].lower()
    
    @pytest.mark.api
    def test_error_handling_with_logging(self, app_with_error_handling, caplog):
        """测试错误处理与日志记录"""
        client = TestClient(app_with_error_handling)
        
        with caplog.at_level("ERROR"):
            response = client.get("/unexpected-error")
        
        assert response.status_code == 500
        
        # 检查错误日志
        error_records = [record for record in caplog.records if record.levelname == "ERROR"]
        assert len(error_records) >= 1
        
        error_message = error_records[0].message
        assert "Unexpected error" in error_message
    
    @pytest.mark.api
    def test_error_handling_custom_error_response(self):
        """测试自定义错误响应格式"""
        app = FastAPI()
        app.add_middleware(ErrorHandlingMiddleware, include_traceback=True)
        
        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Custom error")
        
        client = TestClient(app)
        
        response = client.get("/error")
        
        assert response.status_code == 500
        response_data = response.json()
        
        assert "detail" in response_data
        assert "error_id" in response_data
        assert "timestamp" in response_data
        assert "traceback" in response_data  # 因为include_traceback=True


class TestCORSMiddleware:
    """CORS中间件测试类"""
    
    @pytest.fixture
    def app_with_cors(self):
        """创建带CORS的应用"""
        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["https://example.com", "https://app.example.com"],
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["*"]
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        @app.post("/test")
        async def test_post_endpoint():
            return {"message": "posted"}
        
        return app
    
    @pytest.mark.api
    def test_cors_allowed_origin(self, app_with_cors):
        """测试允许的源"""
        client = TestClient(app_with_cors)
        
        response = client.get("/test", headers={
            "Origin": "https://example.com"
        })
        
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "https://example.com"
        assert response.headers["Access-Control-Allow-Credentials"] == "true"
    
    @pytest.mark.api
    def test_cors_disallowed_origin(self, app_with_cors):
        """测试不允许的源"""
        client = TestClient(app_with_cors)
        
        response = client.get("/test", headers={
            "Origin": "https://malicious.com"
        })
        
        assert response.status_code == 200  # 请求仍然成功
        assert "Access-Control-Allow-Origin" not in response.headers
    
    @pytest.mark.api
    def test_cors_preflight_request(self, app_with_cors):
        """测试预检请求"""
        client = TestClient(app_with_cors)
        
        response = client.options("/test", headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        })
        
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "https://example.com"
        assert "POST" in response.headers["Access-Control-Allow-Methods"]
        assert "Content-Type" in response.headers["Access-Control-Allow-Headers"]
    
    @pytest.mark.api
    def test_cors_no_origin_header(self, app_with_cors):
        """测试没有Origin头的请求"""
        client = TestClient(app_with_cors)
        
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response.headers


class TestSecurityHeadersMiddleware:
    """安全头中间件测试类"""
    
    @pytest.fixture
    def app_with_security_headers(self):
        """创建带安全头的应用"""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        return app
    
    @pytest.mark.api
    def test_security_headers_added(self, app_with_security_headers):
        """测试安全头被添加"""
        client = TestClient(app_with_security_headers)
        
        response = client.get("/test")
        
        assert response.status_code == 200
        
        # 检查安全头
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        
        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        
        assert "Strict-Transport-Security" in response.headers
        assert "max-age=" in response.headers["Strict-Transport-Security"]
        
        assert "Content-Security-Policy" in response.headers
        assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    
    @pytest.mark.api
    def test_security_headers_custom_config(self):
        """测试自定义安全头配置"""
        app = FastAPI()
        app.add_middleware(
            SecurityHeadersMiddleware,
            csp_policy="default-src 'self' 'unsafe-inline'",
            hsts_max_age=31536000
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "'unsafe-inline'" in response.headers["Content-Security-Policy"]
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]


class TestMiddlewareIntegration:
    """中间件集成测试类"""
    
    @pytest.fixture
    def app_with_all_middleware(self):
        """创建包含所有中间件的应用"""
        app = FastAPI()
        
        # 添加所有中间件（注意顺序）
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(CORSMiddleware, allow_origins=["*"])
        app.add_middleware(ErrorHandlingMiddleware)
        app.add_middleware(LoggingMiddleware)
        app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")
        
        return app
    
    @pytest.mark.api
    def test_middleware_stack_success(self, app_with_all_middleware):
        """测试中间件栈成功处理"""
        client = TestClient(app_with_all_middleware)
        
        response = client.get("/test", headers={
            "Origin": "https://example.com"
        })
        
        assert response.status_code == 200
        assert response.json() == {"message": "success"}
        
        # 验证各个中间件的效果
        assert "X-Content-Type-Options" in response.headers  # SecurityHeaders
        assert "Access-Control-Allow-Origin" in response.headers  # CORS
        assert "X-RateLimit-Limit" in response.headers  # RateLimit
    
    @pytest.mark.api
    def test_middleware_stack_error_handling(self, app_with_all_middleware, caplog):
        """测试中间件栈错误处理"""
        client = TestClient(app_with_all_middleware)
        
        with caplog.at_level("ERROR"):
            response = client.get("/error")
        
        assert response.status_code == 500
        
        # 验证错误被正确处理和记录
        error_records = [record for record in caplog.records if record.levelname == "ERROR"]
        assert len(error_records) >= 1
        
        # 验证安全头仍然被添加
        assert "X-Content-Type-Options" in response.headers
    
    @pytest.mark.api
    def test_middleware_order_matters(self):
        """测试中间件顺序的重要性"""
        app1 = FastAPI()
        app1.add_middleware(ErrorHandlingMiddleware)
        app1.add_middleware(RateLimitMiddleware, requests_per_minute=1)
        
        app2 = FastAPI()
        app2.add_middleware(RateLimitMiddleware, requests_per_minute=1)
        app2.add_middleware(ErrorHandlingMiddleware)
        
        @app1.get("/test")
        @app2.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        client1 = TestClient(app1)
        client2 = TestClient(app2)
        
        # 两个应用都应该正常工作，但中间件的执行顺序不同
        response1 = client1.get("/test")
        response2 = client2.get("/test")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # 验证速率限制头的存在
        assert "X-RateLimit-Limit" in response1.headers
        assert "X-RateLimit-Limit" in response2.headers


class TestMiddlewarePerformance:
    """中间件性能测试类"""
    
    @pytest.mark.api
    @pytest.mark.slow
    def test_middleware_performance_impact(self):
        """测试中间件对性能的影响"""
        import time
        
        # 无中间件的应用
        app_no_middleware = FastAPI()
        
        @app_no_middleware.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # 有中间件的应用
        app_with_middleware = FastAPI()
        app_with_middleware.add_middleware(SecurityHeadersMiddleware)
        app_with_middleware.add_middleware(LoggingMiddleware)
        app_with_middleware.add_middleware(RateLimitMiddleware, requests_per_minute=1000)
        
        @app_with_middleware.get("/test")
        async def test_endpoint_with_middleware():
            return {"message": "success"}
        
        client_no_middleware = TestClient(app_no_middleware)
        client_with_middleware = TestClient(app_with_middleware)
        
        # 测试无中间件的性能
        start_time = time.time()
        for _ in range(100):
            response = client_no_middleware.get("/test")
            assert response.status_code == 200
        no_middleware_time = time.time() - start_time
        
        # 测试有中间件的性能
        start_time = time.time()
        for _ in range(100):
            response = client_with_middleware.get("/test")
            assert response.status_code == 200
        with_middleware_time = time.time() - start_time
        
        # 中间件的开销应该是合理的（不超过2倍）
        performance_ratio = with_middleware_time / no_middleware_time
        assert performance_ratio < 2.0, f"Middleware overhead too high: {performance_ratio}x"