#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API服务启动脚本
增强版API服务器启动工具，支持多种配置选项和监控功能
"""

import os
import sys
import argparse
import signal
import time
from pathlib import Path
from typing import Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import uvicorn
except ImportError:
    print("❌ 错误: 未安装uvicorn，请运行: pip install uvicorn")
    sys.exit(1)


class APIServerManager:
    """API服务器管理器"""
    
    def __init__(self):
        self.server_process = None
        self.is_running = False
        
    def setup_signal_handlers(self):
        """设置信号处理器"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        print(f"\n收到信号 {signum}，正在关闭服务器...")
        self.stop_server()
        
    def validate_environment(self) -> bool:
        """验证运行环境"""
        # 检查必要的目录
        required_dirs = [
            project_root / "api",
            project_root / "app",
            project_root / "config"
        ]
        
        for dir_path in required_dirs:
            if not dir_path.exists():
                print(f"❌ 错误: 缺少必要目录 {dir_path}")
                return False
                
        # 检查API主文件
        api_main = project_root / "api" / "main.py"
        if not api_main.exists():
            print(f"❌ 错误: 缺少API主文件 {api_main}")
            return False
            
        return True
        
    def check_port_availability(self, host: str, port: int) -> bool:
        """检查端口是否可用"""
        import socket
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                return result != 0  # 0表示端口被占用
        except Exception:
            return False
            
    def start_server(self, host: str, port: int, debug: bool = False, 
                    workers: int = 1, reload: bool = False) -> None:
        """启动API服务器"""
        
        # 验证环境
        if not self.validate_environment():
            sys.exit(1)
            
        # 检查端口
        if not self.check_port_availability(host, port):
            print(f"❌ 错误: 端口 {port} 已被占用")
            sys.exit(1)
            
        # 设置环境变量
        os.environ.setdefault('PYTHONPATH', str(project_root))
        
        # 配置日志级别
        log_level = "debug" if debug else "info"
        
        print("🚀 启动API服务器...")
        print(f"📍 地址: http://{host}:{port}")
        print(f"🔧 调试模式: {'启用' if debug else '禁用'}")
        print(f"🔄 热重载: {'启用' if reload else '禁用'}")
        print(f"👥 工作进程: {workers}")
        print(f"📁 项目根目录: {project_root}")
        print(f"📊 日志级别: {log_level}")
        print("-" * 50)
        
        # 设置信号处理
        self.setup_signal_handlers()
        
        try:
            self.is_running = True
            
            # 启动服务器
            uvicorn.run(
                "api.main:app",
                host=host,
                port=port,
                reload=reload,
                reload_dirs=[str(project_root)] if reload else None,
                log_level=log_level,
                access_log=True,
                workers=workers if not reload else 1,  # reload模式下只能用1个worker
                loop="auto",
                http="auto"
            )
            
        except KeyboardInterrupt:
            print("\n⚠️  服务器被用户中断")
        except Exception as e:
            print(f"❌ 服务器启动失败: {e}")
            sys.exit(1)
        finally:
            self.is_running = False
            print("✅ 服务器已关闭")
            
    def stop_server(self):
        """停止服务器"""
        if self.is_running:
            self.is_running = False
            print("🛑 正在停止服务器...")
            
    def health_check(self, host: str, port: int) -> bool:
        """健康检查"""
        import requests
        
        try:
            response = requests.get(f"http://{host}:{port}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Twitter自动发布系统 API服务器启动工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 基本启动
    python start_api.py
    
    # 开发模式（热重载）
    python start_api.py --debug --reload
    
    # 生产模式（多进程）
    python start_api.py --host 0.0.0.0 --port 8050 --workers 4
    
    # 健康检查
    python start_api.py --health-check
        """
    )
    
    parser.add_argument(
        '--host',
        default=os.getenv('API_HOST', '127.0.0.1'),
        help='服务器主机地址（默认: 127.0.0.1）'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.getenv('API_PORT', 8050)),
        help='服务器端口（默认: 8050）'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        default=os.getenv('DEBUG', 'false').lower() == 'true',
        help='启用调试模式'
    )
    
    parser.add_argument(
        '--reload',
        action='store_true',
        help='启用热重载（开发模式）'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='工作进程数量（默认: 1）'
    )
    
    parser.add_argument(
        '--health-check',
        action='store_true',
        help='执行健康检查'
    )
    
    args = parser.parse_args()
    
    # 创建服务器管理器
    server_manager = APIServerManager()
    
    # 健康检查模式
    if args.health_check:
        print(f"🔍 检查服务器健康状态: http://{args.host}:{args.port}")
        if server_manager.health_check(args.host, args.port):
            print("✅ 服务器运行正常")
            sys.exit(0)
        else:
            print("❌ 服务器无响应")
            sys.exit(1)
    
    # 启动服务器
    server_manager.start_server(
        host=args.host,
        port=args.port,
        debug=args.debug,
        workers=args.workers,
        reload=args.reload
    )


if __name__ == "__main__":
    main()