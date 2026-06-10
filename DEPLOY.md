# 部署指南(Docker Compose · 阿里云香港)

目标:`https://dc.ezra76.com`(43.99.101.9),Docker Compose 运行
web / worker / PostgreSQL / Redis / Nginx,Let's Encrypt HTTPS。

## 架构

```
                 Internet
                    │ 443/80
              ┌─────▼─────┐
              │   nginx   │  TLS 终止、静态/媒体、反代
              └─────┬─────┘
        ┌───────────┼───────────┐
   ┌────▼────┐  ┌───▼────┐  ┌───▼───┐
   │  web    │  │ worker │  │  ...  │
   │gunicorn │  │ celery │
   └────┬────┘  └───┬────┘
        └─────┬─────┴───────┐
        ┌─────▼────┐  ┌─────▼────┐
        │ postgres │  │  redis   │
        └──────────┘  └──────────┘
```

## 首次部署步骤

```bash
# 0. 服务器装 Docker(若未装)
curl -fsSL https://get.docker.com | sh

# 1. 拉取代码
git clone https://github.com/openbible365-boop/DC.git /opt/dc
cd /opt/dc

# 2. 配置环境变量
cp .env.example .env
#   编辑 .env:生成 SECRET_KEY、设置强 POSTGRES_PASSWORD、填 CERTBOT_EMAIL
python3 -c "import secrets;print(secrets.token_urlsafe(50))"   # 生成 SECRET_KEY

# 3. 构建并启动(除 nginx 外)
docker compose build
docker compose up -d db redis web worker

# 4. 创建管理员
docker compose exec web python manage.py createsuperuser

# 5. 签发 HTTPS 证书并启动 nginx(确保 80/443 安全组已放行)
bash deploy/init-letsencrypt.sh

# 6. 完成 → 打开 https://dc.ezra76.com
```

## 日常运维

```bash
docker compose ps                      # 查看状态
docker compose logs -f web             # 看日志
git pull && docker compose up -d --build web worker   # 更新上线
docker compose exec web python manage.py migrate      # 手动迁移(一般自动)
docker compose exec db pg_dump -U dc dc > backup.sql  # 备份数据库
```

证书每 12 小时自动尝试续期(certbot 容器),无需手动。

## 阿里云安全组

需放行入方向:**80**(ACME 验证/跳转)、**443**(HTTPS)、**22**(SSH)。
