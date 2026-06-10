#!/bin/sh
set -e

# 等待数据库就绪
if [ -n "$POSTGRES_HOST" ]; then
  echo "等待 PostgreSQL ($POSTGRES_HOST:${POSTGRES_PORT:-5432}) ..."
  until python -c "import socket,sys; s=socket.socket(); s.settimeout(2); s.connect(('$POSTGRES_HOST', int('${POSTGRES_PORT:-5432}')))" 2>/dev/null; do
    sleep 1
  done
fi

# 仅 web 容器执行迁移与静态收集(由 RUN_MIGRATIONS 控制,避免 worker 重复跑)
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "执行数据库迁移 ..."
  python manage.py migrate --noinput
  echo "收集静态文件 ..."
  python manage.py collectstatic --noinput
fi

exec "$@"
