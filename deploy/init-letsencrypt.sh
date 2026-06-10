#!/bin/bash
# 首次签发 Let's Encrypt 证书的引导脚本。
# 用法:在服务器项目目录执行  bash deploy/init-letsencrypt.sh
set -e

DOMAIN="dc.ezra76.com"
EMAIL="${CERTBOT_EMAIL:-}"      # 可在 .env 设 CERTBOT_EMAIL,或运行前 export
COMPOSE="docker compose"

if [ -z "$EMAIL" ]; then
  read -rp "请输入用于 Let's Encrypt 的邮箱: " EMAIL
fi

echo "### 1/5 创建占位证书,让 nginx 能先启动 ..."
$COMPOSE run --rm --entrypoint "\
  sh -c 'mkdir -p /etc/letsencrypt/live/$DOMAIN && \
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout /etc/letsencrypt/live/$DOMAIN/privkey.pem \
    -out /etc/letsencrypt/live/$DOMAIN/fullchain.pem \
    -subj /CN=localhost'" certbot

echo "### 2/5 启动 nginx ..."
$COMPOSE up -d nginx

echo "### 3/5 删除占位证书 ..."
$COMPOSE run --rm --entrypoint "\
  rm -rf /etc/letsencrypt/live/$DOMAIN \
  /etc/letsencrypt/archive/$DOMAIN \
  /etc/letsencrypt/renewal/$DOMAIN.conf" certbot

echo "### 4/5 通过 webroot 验证签发正式证书 ..."
$COMPOSE run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    --email $EMAIL -d $DOMAIN \
    --rsa-key-size 2048 --agree-tos --no-eff-email --force-renewal" certbot

echo "### 5/5 重载 nginx ..."
$COMPOSE exec nginx nginx -s reload

echo "✅ 完成。证书已签发,HTTPS 已就绪:https://$DOMAIN"
