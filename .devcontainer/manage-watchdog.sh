#!/bin/bash
# Manage AWS Credential Watchdog

WATCHDOG_SCRIPT="/workspaces/apply/.devcontainer/credential-watchdog.sh"
WATCHDOG_LOG="/tmp/aws-credential-watchdog.log"
WATCHDOG_PID_FILE="/tmp/aws-credential-watchdog.pid"

case "$1" in
    start)
        if pgrep -f "credential-watchdog.sh" > /dev/null; then
            echo "Watchdog is already running (PID: $(pgrep -f 'credential-watchdog.sh'))"
            exit 0
        fi
        echo "Starting AWS credential watchdog..."
        nohup "$WATCHDOG_SCRIPT" > "$WATCHDOG_LOG" 2>&1 &
        echo $! > "$WATCHDOG_PID_FILE"
        echo "Watchdog started (PID: $(cat $WATCHDOG_PID_FILE))"
        echo "View logs with: tail -f $WATCHDOG_LOG"
        ;;
    stop)
        if pkill -f "credential-watchdog.sh"; then
            echo "Watchdog stopped"
            rm -f "$WATCHDOG_PID_FILE"
        else
            echo "Watchdog is not running"
        fi
        ;;
    restart)
        $0 stop
        sleep 1
        $0 start
        ;;
    status)
        if pgrep -f "credential-watchdog.sh" > /dev/null; then
            PID=$(pgrep -f "credential-watchdog.sh")
            echo "Watchdog is running (PID: $PID)"
            echo "Last 10 log lines:"
            tail -10 "$WATCHDOG_LOG" 2>/dev/null || echo "No logs yet"
        else
            echo "Watchdog is not running"
            exit 1
        fi
        ;;
    logs)
        if [ -f "$WATCHDOG_LOG" ]; then
            tail -f "$WATCHDOG_LOG"
        else
            echo "No log file found at $WATCHDOG_LOG"
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the credential watchdog"
        echo "  stop    - Stop the credential watchdog"
        echo "  restart - Restart the credential watchdog"
        echo "  status  - Check watchdog status and show recent logs"
        echo "  logs    - Follow watchdog logs in real-time"
        exit 1
        ;;
esac
