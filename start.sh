#!/bin/bash
# ============================================
#  考研平台 一键启动/停止脚本
#  用法: ./start.sh [start|stop|restart|status]
# ============================================

VENV="/home/ubuntu/home/ENVS/kaoyan/bin/activate"
PROJECT_DIR="/home/ubuntu/home/vibe-coding/kaoyan"
PID_DIR="$PROJECT_DIR/.pids"
LOG_DIR="$PROJECT_DIR/.logs"

mkdir -p "$PID_DIR" "$LOG_DIR"

DJANGO_PID="$PID_DIR/django.pid"
CELERY_PID="$PID_DIR/celery.pid"

activate_venv() {
    source "$VENV"
}

start_django() {
    if [ -f "$DJANGO_PID" ] && kill -0 "$(cat "$DJANGO_PID")" 2>/dev/null; then
        echo "✅ Django 已在运行 (PID: $(cat "$DJANGO_PID"))"
    else
        echo "🚀 启动 Django 开发服务器..."
        cd "$PROJECT_DIR"
        activate_venv
        nohup python manage.py runserver 0.0.0.0:8327 > "$LOG_DIR/django.log" 2>&1 &
        echo $! > "$DJANGO_PID"
        sleep 1
        if kill -0 "$(cat "$DJANGO_PID")" 2>/dev/null; then
            echo "✅ Django 启动成功 (PID: $(cat "$DJANGO_PID"))  → http://localhost:8327"
        else
            echo "❌ Django 启动失败，查看日志: $LOG_DIR/django.log"
            rm -f "$DJANGO_PID"
        fi
    fi
}

start_celery() {
    if [ -f "$CELERY_PID" ] && kill -0 "$(cat "$CELERY_PID")" 2>/dev/null; then
        echo "✅ Celery Worker 已在运行 (PID: $(cat "$CELERY_PID"))"
    else
        echo "🚀 启动 Celery Worker..."
        cd "$PROJECT_DIR"
        activate_venv
        nohup celery -A kaoyan_project worker -l INFO -n kaoyan_worker@%h > "$LOG_DIR/celery.log" 2>&1 &
        echo $! > "$CELERY_PID"
        sleep 2
        if kill -0 "$(cat "$CELERY_PID")" 2>/dev/null; then
            echo "✅ Celery Worker 启动成功 (PID: $(cat "$CELERY_PID"))"
        else
            echo "❌ Celery Worker 启动失败，查看日志: $LOG_DIR/celery.log"
            rm -f "$CELERY_PID"
        fi
    fi
}

stop_django() {
    if [ -f "$DJANGO_PID" ]; then
        PID=$(cat "$DJANGO_PID")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            echo "🛑 Django 已停止 (PID: $PID)"
        else
            echo "⚠️  Django 进程已不存在"
        fi
        rm -f "$DJANGO_PID"
    else
        echo "⚠️  Django PID 文件不存在"
    fi
}

stop_celery() {
    if [ -f "$CELERY_PID" ]; then
        PID=$(cat "$CELERY_PID")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            echo "🛑 Celery Worker 已停止 (PID: $PID)"
        else
            echo "⚠️  Celery Worker 进程已不存在"
        fi
        rm -f "$CELERY_PID"
    else
        echo "⚠️  Celery Worker PID 文件不存在"
    fi
}

show_status() {
    echo "========== 服务状态 =========="
    if [ -f "$DJANGO_PID" ] && kill -0 "$(cat "$DJANGO_PID")" 2>/dev/null; then
        echo "✅ Django:      运行中 (PID: $(cat "$DJANGO_PID"))"
    else
        echo "❌ Django:      未运行"
    fi
    if [ -f "$CELERY_PID" ] && kill -0 "$(cat "$CELERY_PID")" 2>/dev/null; then
        echo "✅ Celery:      运行中 (PID: $(cat "$CELERY_PID"))"
    else
        echo "❌ Celery:      未运行"
    fi
    echo "==============================="
}

case "${1:-start}" in
    start)
        start_django
        start_celery
        echo ""
        show_status
        echo "💡 查看日志: tail -f $LOG_DIR/django.log | tail -f $LOG_DIR/celery.log"
        ;;
    stop)
        stop_celery
        stop_django
        echo ""
        show_status
        ;;
    restart)
        stop_celery
        stop_django
        sleep 1
        start_django
        start_celery
        echo ""
        show_status
        ;;
    status)
        show_status
        ;;
    log)
        echo "==== Django 日志 ===="
        tail -20 "$LOG_DIR/django.log" 2>/dev/null || echo "(无日志)"
        echo ""
        echo "==== Celery 日志 ===="
        tail -20 "$LOG_DIR/celery.log" 2>/dev/null || echo "(无日志)"
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|log}"
        echo "  start   - 启动 Django + Celery（默认）"
        echo "  stop    - 停止所有服务"
        echo "  restart - 重启所有服务"
        echo "  status  - 查看运行状态"
        echo "  log     - 查看最近日志"
        ;;
esac