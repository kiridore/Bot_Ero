#!/usr/bin/env bash
# BotEro Web 服务管理脚本（systemd，单进程承载 6 子域）
# 用法: ./botero-services.sh {start|stop|restart|status}
set -euo pipefail

SERVICES=(
  botero-web
)

usage() {
  echo "用法: $0 {start|stop|restart|status}"
  exit 1
}

if [ $# -ne 1 ]; then
  usage
fi

case "$1" in
  start | stop | restart | status)
    systemctl "$1" "${SERVICES[@]}"
    ;;
  *)
    usage
    ;;
esac
