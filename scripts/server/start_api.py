#!/usr/bin/env python3
# scripts/server/start_api.py - FastAPI Server Launcher

import sys
import os
import argparse
import signal
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def signal_handler(signum, frame):
    """优雅关闭信号处理"""
    print(f"\nAPI服务 {os.getpid()} 正在优雅关闭...")
    sys.exit(0)

def main():
    """启动FastAPI应用"""
    parser = argparse.ArgumentParser(description='启动Twitter自动发布系统API服务')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='API服务监听地址')
    parser.add_argument('--port', type=int, default=8050, help='API服务监听端口')
    parser.add_argument('--reload', action='store_true', help='开发模式下自动重载')
    parser.add_argument('--workers', type=int, default=1, help='工作进程数量')
    
    args = parser.parse_args()
    
    # 注册信号处理
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    print(f"FastAPI服务启动中...")
    print(f"PID: {os.getpid()}")
    print(f"监听地址: {args.host}:{args.port}")
    print(f"项目根目录: {project_root}")
    
    try:
        # 导入并启动uvicorn
        import uvicorn
        from api.main import app
        
        # 配置uvicorn
        uvicorn_config = {
            "app": app,
            "host": args.host,
            "port": args.port,
            "reload": args.reload,
            "workers": args.workers if not args.reload else 1,
            "log_level": "info",
            "access_log": True,
            "use_colors": True
        }
        
        print(f"FastAPI应用已加载，启动服务器...")
        print(f"API文档地址: http://{args.host}:{args.port}/api/docs")
        print(f"健康检查地址: http://{args.host}:{args.port}/api/health")
        
        # 启动服务
        uvicorn.run(**uvicorn_config)
        
    except ImportError as e:
        print(f"错误: 无法导入必要的模块 - {e}")
        print("请确保已安装所有依赖: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"启动API服务时发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()