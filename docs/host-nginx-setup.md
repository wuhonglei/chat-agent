# 宿主机 Nginx 配置指南（2层架构）

## 架构说明

当前采用 **2层 Nginx 架构**：
- **宿主机 Nginx**：处理 SSL/TLS、外部访问（80/443）
- **容器内 Nginx**：处理静态文件、API 代理、React 路由（3000）

```
外网 → 宿主机 Nginx (80/443) → 容器内 Nginx (3000) → 后端服务
```

## 安装宿主机 Nginx

### CentOS/RHEL
```bash
sudo yum install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx
```

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx
```

## 配置 Nginx

### 1. 复制配置文件

```bash
# 复制示例配置到 Nginx 配置目录
sudo cp nginx-proxy.conf.example /etc/nginx/sites-available/chat.wuhonglei.cn

# 创建软链接（Ubuntu/Debian）
sudo ln -s /etc/nginx/sites-available/chat.wuhonglei.cn /etc/nginx/sites-enabled/

# CentOS/RHEL 直接放在 conf.d 目录
sudo cp nginx-proxy.conf.example /etc/nginx/conf.d/chat.wuhonglei.cn.conf
```

### 2. 编辑配置文件

根据实际情况修改 `/etc/nginx/sites-available/chat.wuhonglei.cn` 或 `/etc/nginx/conf.d/chat.wuhonglei.cn.conf`：

- 确认 `server_name` 为你的域名
- 确认 `proxy_pass` 指向 `http://127.0.0.1:3000`
- 确认 SSL 证书路径正确

### 3. 测试配置

```bash
# 测试 Nginx 配置语法
sudo nginx -t

# 如果测试通过，重载配置
sudo systemctl reload nginx
```

## SSL 证书配置（Let's Encrypt）

### 1. 安装 Certbot

```bash
# CentOS/RHEL
sudo yum install certbot python3-certbot-nginx -y

# Ubuntu/Debian
sudo apt-get install certbot python3-certbot-nginx -y
```

### 2. 获取证书

**方法一：使用 Certbot 自动配置（推荐）**

```bash
# Certbot 会自动配置 Nginx
sudo certbot --nginx -d chat.wuhonglei.cn
```

**方法二：手动获取证书**

```bash
# 先停止 Nginx（如果使用 standalone 模式）
sudo systemctl stop nginx

# 获取证书
sudo certbot certonly --standalone -d chat.wuhonglei.cn

# 启动 Nginx
sudo systemctl start nginx

# 然后手动编辑 Nginx 配置文件，添加 SSL 配置
```

### 3. 证书自动续期

Let's Encrypt 证书有效期为 90 天，需要定期续期。

```bash
# 测试续期
sudo certbot renew --dry-run

# 设置自动续期（Certbot 会自动创建 systemd timer 或 cron 任务）
# 通常 Certbot 安装时会自动配置，无需手动设置
```

Certbot 会自动配置续期任务，证书到期前会自动续期。

## 验证配置

### 1. 检查服务状态

```bash
# 检查 Nginx 状态
sudo systemctl status nginx

# 检查容器状态
docker-compose ps
```

### 2. 测试访问

```bash
# 测试 HTTP（应该重定向到 HTTPS）
curl -I http://chat.wuhonglei.cn

# 测试 HTTPS
curl -I https://chat.wuhonglei.cn

# 或在浏览器访问
# https://chat.wuhonglei.cn
```

### 3. 检查日志

```bash
# 查看 Nginx 访问日志
sudo tail -f /var/log/nginx/chat.wuhonglei.cn.access.log

# 查看 Nginx 错误日志
sudo tail -f /var/log/nginx/chat.wuhonglei.cn.error.log

# 查看容器日志
docker-compose logs -f frontend
```

## 常见问题

### 1. 502 Bad Gateway

**原因**：宿主机 Nginx 无法连接到容器内的 Nginx

**解决**：
- 确认容器正在运行：`docker-compose ps`
- 确认端口映射正确：`docker-compose.yml` 中 `127.0.0.1:3000:3000`
- 测试容器内 Nginx：`curl http://127.0.0.1:3000`

### 2. SSL 证书错误

**原因**：证书路径不正确或证书文件不存在

**解决**：
- 检查证书路径：`ls -la /etc/letsencrypt/live/chat.wuhonglei.cn/`
- 确认 Nginx 配置中的证书路径正确
- 重新获取证书：`sudo certbot --nginx -d chat.wuhonglei.cn`

### 3. 无法访问

**原因**：防火墙未开放端口

**解决**：
```bash
# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

# Ubuntu/Debian (ufw)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

## 配置优化建议

### 1. 性能优化

在宿主机 Nginx 配置中添加：

```nginx
# 启用 HTTP/2
listen 443 ssl http2;

# 启用缓存
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=10g inactive=60m;

# 在 location / 中添加
proxy_cache my_cache;
proxy_cache_valid 200 60m;
```

### 2. 安全加固

```nginx
# 隐藏 Nginx 版本
server_tokens off;

# 限制请求大小
client_max_body_size 100M;

# 限制连接数
limit_conn_zone $binary_remote_addr zone=conn_limit_per_ip:10m;
limit_conn conn_limit_per_ip 10;
```

## 维护命令

```bash
# 重载 Nginx 配置（无需重启，零停机）
sudo nginx -t && sudo systemctl reload nginx

# 查看 Nginx 配置
sudo nginx -T

# 检查端口占用
sudo netstat -tlnp | grep nginx
```

## 总结

2层架构的优势：
- ✅ 证书更新只需 `nginx -s reload`，无需重启容器
- ✅ 容器不直接暴露，更安全
- ✅ 可以统一管理多个服务
- ✅ 日志集中管理

配置完成后，你的服务将通过 `https://chat.wuhonglei.cn` 对外提供服务。

