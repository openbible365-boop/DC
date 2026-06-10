# 部署指南(与 ko-tts 共存 · Docker Compose)

目标:`https://dc.ezra76.com`(阿里云香港 43.99.101.9)。
该服务器已运行另一项目 **ko-tts**,其 **Caddy** 反代占用 80/443 并自动签发 HTTPS。
DC **不抢占 80/443**,而是接入 Caddy 网络,由 Caddy 把 `dc.ezra76.com` 反代到 DC 的 web 容器。

## 架构

```
                Internet 80/443
                      │
              ┌───────▼────────┐
              │  Caddy(ko-tts) │  自动 HTTPS,按域名分流
              └───┬────────┬───┘
       ac.ezra76 ─┘        └─ dc.ezra76.com → dc-web:8000
                                    │
                         ┌──────────▼──────────┐
                         │  DC web(gunicorn)   │  WhiteNoise 静态、Django 媒体
                         └────┬───────────┬─────┘
                       ┌──────▼───┐  ┌────▼────┐  ┌────────┐
                       │ postgres │  │  redis  │  │ worker │
                       └──────────┘  └─────────┘  └────────┘
```

## 首次部署

```bash
# 1. 拉取代码
sudo mkdir -p /opt/dc && sudo chown $USER:$USER /opt/dc
git clone https://github.com/openbible365-boop/DC.git /opt/dc
cd /opt/dc

# 2. 配置环境变量
cp .env.example .env
nano .env   # 生成 SECRET_KEY、设强 POSTGRES_PASSWORD
python3 -c "import secrets;print(secrets.token_urlsafe(50))"

# 3. 构建并启动(web 会自动迁移 + collectstatic)
docker compose up -d --build

# 4. 创建管理员
docker compose exec web python manage.py createsuperuser

# 5. 让 Caddy 反代 dc.ezra76.com
#    编辑 /opt/ko-tts/deploy/Caddyfile,追加:
#
#      dc.ezra76.com {
#          encode gzip
#          reverse_proxy dc-web:8000
#      }
#
#    然后热加载 Caddy(不影响 ac.ezra76.com):
docker exec ko-tts-caddy-1 caddy reload --config /etc/caddy/Caddyfile

# 6. 完成 → https://dc.ezra76.com(Caddy 自动签发证书)
```

## 日常运维

```bash
cd /opt/dc
docker compose ps
docker compose logs -f web
git pull && docker compose up -d --build   # 更新上线
docker compose exec db pg_dump -U dc dc > backup.sql   # 备份
```

## 说明

- DC 的容器只在内部网络与 ko-tts 网络通信,不监听公网端口。
- 静态文件由 WhiteNoise 在 web 容器内服务;用户上传的媒体由 Django 服务。
- worker(Celery)处理注释书自动拆分等异步任务。
