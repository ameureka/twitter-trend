import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException, status, Header
from sqlalchemy.orm import Session
from pathlib import Path

from api.dependencies import (
    get_settings,
    get_database_manager,
    get_db,
    get_config,
    api_key_auth,
    optional_api_key_auth,
    get_current_user_id,
    get_pagination_params,
    APISettings
)
from app.database.models import User, ApiKey, Project


class TestAPISettings:
    """API设置测试类"""
    
    @pytest.mark.api
    def test_api_settings_default(self):
        """测试默认API设置"""
        settings = APISettings()
        
        assert settings.api_host == "127.0.0.1"
        assert settings.api_port == 8050
        assert settings.debug is False
        assert settings.api_key == "dev-api-key-12345"
        assert settings.config_file == "config/enhanced_config.yaml"
    
    @pytest.mark.api
    def test_api_settings_with_env(self):
        """测试环境变量配置"""
        with patch.dict('os.environ', {
            'API_API_HOST': '0.0.0.0',
            'API_API_PORT': '8050',
            'API_DEBUG': 'true',
            'API_API_KEY': 'test-key'
        }):
            settings = APISettings()
            
            assert settings.api_host == "0.0.0.0"
            assert settings.api_port == 8050
            assert settings.debug is True
            assert settings.api_key == "test-key"


class TestGetSettings:
    """获取设置测试类"""
    
    @pytest.mark.api
    def test_get_settings_cached(self):
        """测试设置缓存"""
        # 清除缓存
        get_settings.cache_clear()
        
        settings1 = get_settings()
        settings2 = get_settings()
        
        # 应该返回同一个实例（缓存）
        assert settings1 is settings2
    
    @pytest.mark.api
    def test_get_settings_type(self):
        """测试设置类型"""
        settings = get_settings()
        assert isinstance(settings, APISettings)


class TestGetDatabaseManager:
    """数据库管理器测试类"""
    
    @pytest.mark.api
    def test_get_database_manager_default(self):
        """测试获取默认数据库管理器"""
        with patch('api.dependencies.DatabaseManager') as mock_db_manager:
            mock_instance = Mock()
            mock_db_manager.return_value = mock_instance
            
            manager = get_database_manager()
            
            assert manager == mock_instance
            mock_db_manager.assert_called_once()
    
    @pytest.mark.api
    def test_get_database_manager_with_url(self):
        """测试使用指定URL的数据库管理器"""
        with patch('api.dependencies.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.database_url = "sqlite:///test.db"
            mock_get_settings.return_value = mock_settings
            
            with patch('api.dependencies.DatabaseManager') as mock_db_manager:
                mock_instance = Mock()
                mock_db_manager.return_value = mock_instance
                
                manager = get_database_manager()
                
                assert manager == mock_instance
                mock_db_manager.assert_called_once_with("sqlite:///test.db")
    
    @pytest.mark.api
    def test_get_database_manager_singleton(self):
        """测试数据库管理器单例模式"""
        # 重置全局变量
        import api.dependencies
        api.dependencies._db_manager = None
        
        with patch('api.dependencies.DatabaseManager') as mock_db_manager:
            mock_instance = Mock()
            mock_db_manager.return_value = mock_instance
            
            manager1 = get_database_manager()
            manager2 = get_database_manager()
            
            # 应该返回同一个实例
            assert manager1 is manager2
            # DatabaseManager只应该被调用一次
            mock_db_manager.assert_called_once()


class TestGetDB:
    """数据库会话测试类"""
    
    @pytest.mark.api
    def test_get_db_generator(self):
        """测试数据库会话生成器"""
        mock_session = Mock()
        mock_manager = Mock()
        mock_manager.get_session.return_value.__enter__.return_value = mock_session
        mock_manager.get_session.return_value.__exit__.return_value = None
        
        with patch('api.dependencies.get_database_manager', return_value=mock_manager):
            db_generator = get_db()
            db = next(db_generator)
            
            assert db == mock_session
            mock_manager.get_session.assert_called_once()
    
    @pytest.mark.api
    def test_get_db_cleanup(self):
        """测试数据库会话清理"""
        mock_session = Mock()
        mock_context_manager = Mock()
        mock_context_manager.__enter__.return_value = mock_session
        mock_context_manager.__exit__.return_value = None
        
        mock_manager = Mock()
        mock_manager.get_session.return_value = mock_context_manager
        
        with patch('api.dependencies.get_database_manager', return_value=mock_manager):
            db_generator = get_db()
            db = next(db_generator)
            
            # 模拟生成器结束
            try:
                db_generator.close()
            except GeneratorExit:
                pass
            
            # 验证上下文管理器被正确使用
            mock_context_manager.__enter__.assert_called_once()


class TestGetConfig:
    """配置获取测试类"""
    
    @pytest.mark.api
    def test_get_config(self):
        """测试获取配置"""
        with patch('api.dependencies.ConfigManager') as mock_config_manager:
            mock_instance = Mock()
            mock_config_manager.return_value = mock_instance
            
            with patch('api.dependencies.get_settings') as mock_get_settings:
                mock_settings = Mock()
                mock_settings.config_file = "test_config.yaml"
                mock_get_settings.return_value = mock_settings
                
                config = get_config()
                
                assert config == mock_instance
                mock_config_manager.assert_called_once_with("test_config.yaml")


class TestAPIKeyAuth:
    """API密钥认证测试类"""
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_api_key_auth_success(self):
        """测试API密钥认证成功"""
        with patch('api.dependencies.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.api_key = "valid-key"
            mock_settings.debug = False
            mock_get_settings.return_value = mock_settings
            
            result = await api_key_auth("valid-key")
            assert result == "valid-key"
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_api_key_auth_invalid(self):
        """测试API密钥认证失败"""
        with patch('api.dependencies.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.api_key = "valid-key"
            mock_settings.debug = False
            mock_get_settings.return_value = mock_settings
            
            with pytest.raises(HTTPException) as exc_info:
                await api_key_auth("invalid-key")
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid API key" in exc_info.value.detail
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_api_key_auth_debug_mode(self):
        """测试调试模式下的API密钥认证"""
        with patch('api.dependencies.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.api_key = "dev-key"
            mock_settings.debug = True
            mock_get_settings.return_value = mock_settings
            
            result = await api_key_auth("dev-key")
            assert result == "dev-key"


class TestOptionalAPIKeyAuth:
    """可选API密钥认证测试类"""
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_optional_api_key_auth_none(self):
        """测试无API密钥"""
        result = await optional_api_key_auth(None)
        assert result is None
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_optional_api_key_auth_valid(self):
        """测试有效API密钥"""
        with patch('api.dependencies.api_key_auth') as mock_auth:
            mock_auth.return_value = "valid-key"
            
            result = await optional_api_key_auth("valid-key")
            assert result == "valid-key"
            mock_auth.assert_called_once_with("valid-key")
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_optional_api_key_auth_invalid(self):
        """测试无效API密钥"""
        with patch('api.dependencies.api_key_auth') as mock_auth:
            mock_auth.side_effect = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
            
            result = await optional_api_key_auth("invalid-key")
            assert result is None


class TestGetCurrentUserID:
    """获取当前用户ID测试类"""
    
    @pytest.mark.api
    def test_get_current_user_id(self):
        """测试获取当前用户ID"""
        user_id = get_current_user_id("valid-api-key")
        assert user_id == 1  # 默认用户ID


class TestGetPaginationParams:
    """分页参数测试类"""
    
    @pytest.mark.api
    def test_get_pagination_params_default(self):
        """测试默认分页参数"""
        params = get_pagination_params()
        
        assert params["page"] == 1
        assert params["per_page"] == 20
        assert params["offset"] == 0
        assert params["limit"] == 20
    
    @pytest.mark.api
    def test_get_pagination_params_custom(self):
        """测试自定义分页参数"""
        params = get_pagination_params(page=3, per_page=10)
        
        assert params["page"] == 3
        assert params["per_page"] == 10
        assert params["offset"] == 20  # (3-1) * 10
        assert params["limit"] == 10
    
    @pytest.mark.api
    def test_get_pagination_params_validation(self):
        """测试分页参数验证"""
        # 测试页码最小值
        params = get_pagination_params(page=0)
        assert params["page"] == 1  # 自动修正为1
        
        # 测试页面大小最小值
        params = get_pagination_params(per_page=0)
        assert params["per_page"] == 20  # 自动修正为默认值
        
        # 测试页面大小最大值
        params = get_pagination_params(per_page=200, max_per_page=100)
        assert params["per_page"] == 100  # 限制为最大值
    
    @pytest.mark.api
    def test_get_pagination_params_edge_cases(self):
        """测试分页参数边界情况"""
        # 测试负数页码
        params = get_pagination_params(page=-1)
        assert params["page"] == 1
        
        # 测试负数页面大小
        params = get_pagination_params(per_page=-10)
        assert params["per_page"] == 20
        
        # 测试大页码
        params = get_pagination_params(page=1000, per_page=50)
        assert params["offset"] == 49950  # (1000-1) * 50