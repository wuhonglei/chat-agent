# SSL 证书配置指南（容器内 Nginx 方案）

## 方案说明

此方案使用容器内的 Nginx 直接处理 HTTPS，无需宿主机 Nginx。

## 前置要求

1. 域名已解析到服务器 IP
2. 服务器已开放 80 和 443 端口

## 证书获取（Let's Encrypt）

### 方法一：使用 certbot 在宿主机获取证书

```bash
# 安装 certbot
sudo yum install certbot -y  # CentOS
# 或
sudo apt-get install certbot -y  # Ubuntu

# 获取证书（使用 standalone 模式，需要先停止容器）
docker-compose down

# 获取证书
sudo certbot certonly --standalone -d chat.wuhonglei.cn

# 证书位置通常在：
# /etc/letsencrypt/live/chat.wuhonglei.cn/fullchain.pem
# /etc/letsencrypt/live/chat.wuhonglei.cn/privkey.pem
```

### 方法二：使用 certbot 容器获取证书

```bash
# 创建证书目录
mkdir -p ssl certbot/www

# 使用 certbot 容器获取证书（需要先停止前端容器）
docker-compose stop frontend

# 运行 certbot 容器
docker run -it --rm \
  -v $(pwd)/certbot/www:/var/www/certbot \
  -v $(pwd)/ssl:/etc/letsencrypt \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  -d chat.wuhonglei.cn

# 复制证书到 ssl 目录
sudo cp /etc/letsencrypt/live/chat.wuhonglei.cn/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/chat.wuhonglei.cn/privkey.pem ./ssl/
sudo chmod 644 ./ssl/fullchain.pem
sudo chmod 600 ./ssl/privkey.pem
```

## 配置证书路径

1. 创建证书目录：
```bash
mkdir -p ssl certbot/www
```

2. 将证书文件放置到 `ssl/` 目录：
```bash
# 如果证书在 /etc/letsencrypt/live/chat.wuhonglei.cn/
sudo cp /etc/letsencrypt/live/chat.wuhonglei.cn/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/chat.wuhonglei.cn/privkey.pem ./ssl/
sudo chmod 644 ./ssl/fullchain.pem
sudo chmod 600 ./ssl/privkey.pem
```

## 启动服务

```bash
docker-compose up -d
```

## 证书自动续期

Let's Encrypt 证书有效期为 90 天，需要定期续期。

### 设置自动续期任务

创建续期脚本 `renew-cert.sh`：

```bash
#!/bin/bash
# 续期证书
certbot renew --quiet

# 复制新证书到项目目录
cp /etc/letsencrypt/live/chat.wuhonglei.cn/fullchain.pem ./ssl/
cp /etc/letsencrypt/live/chat.wuhonglei.cn/privkey.pem ./ssl/
chmod 644 ./ssl/fullchain.pem
chmod 600 ./ssl/privkey.pem

# 重启前端容器以加载新证书
docker-compose restart frontend
```

添加到 crontab（每月执行一次）：

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每月 1 号凌晨 3 点执行）
0 3 1 * * /path/to/renew-cert.sh
```

## 方案对比

### 容器内 Nginx 方案（当前方案）

**优点：**
- ✅ 架构简单，只需一个 Nginx
- ✅ 减少一层代理，性能略好
- ✅ 配置集中，易于管理

**缺点：**
- ❌ 证书更新需要重启容器
- ❌ 容器直接暴露到公网，安全风险稍高
- ❌ 证书管理需要在宿主机操作

### 宿主机 Nginx 方案（原方案）

**优点：**
- ✅ 证书更新无需重启应用容器
- ✅ 容器不直接暴露，更安全
- ✅ 可以统一管理多个服务的 SSL

**缺点：**
- ❌ 需要维护两层 Nginx 配置
- ❌ 架构稍复杂

## 验证 HTTPS

```bash
# 检查证书
curl -I https://chat.wuhonglei.cn

# 或使用浏览器访问
# https://chat.wuhonglei.cn
```

