FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# ffmpeg 为音视频转录预留;libpq 供 psycopg 运行
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# 先装依赖(利用 Docker 层缓存)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# 再拷源码
COPY . .
RUN uv sync --frozen && chmod +x deploy/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["deploy/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
