#!/usr/bin/env bash
# BotEro 全部 Web 子应用服务管理脚本（systemd）
# 用法: ./botero-services.sh {start|stop|restart|status}
set -euo pipefail

SERVICES=(
  botero-gallery
  botero-guestbook
  botero-profile
  botero-trpg
  botero-alarms
  botero-activities
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
