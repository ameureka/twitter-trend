#!/bin/bash
# 停止增强版Twitter自动发布系统

echo "停止增强版Twitter自动发布系统..."

# 查找并终止进程
PIDFILE="twitter_publisher.pid"

if [ -f "$PIDFILE" ]; then
    PID=$(cat $PIDFILE)
    if ps -p $PID > /dev/null; then
        echo "终止进程 $PID..."
        kill -TERM $PID
        
        # 等待进程优雅退出
        for i in {1..30}; do
            if ! ps -p $PID > /dev/null; then
                echo "进程已优雅退出"
                rm -f $PIDFILE
                exit 0
            fi
            sleep 1
        done
        
        # 强制终止
        echo "强制终止进程..."
        kill -KILL $PID
        rm -f $PIDFILE
    else
        echo "进程不存在，清理PID文件"
        rm -f $PIDFILE
    fi
else
    echo "未找到PID文件，尝试通过进程名终止"
    pkill -f "main.py" || echo "未找到运行中的进程"
fi

echo "系统已停止"
