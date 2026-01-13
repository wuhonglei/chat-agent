# CentOS 安装 PostgreSQL

根据搜索结果，我来为您提供在 CentOS 上安装和启动 PostgreSQL 的详细步骤：

## 安装 PostgreSQL

### 方法1：安装默认版本
```bash
# 更新系统包
sudo yum update

# 安装 PostgreSQL 服务器和附加组件
sudo yum install postgresql-server postgresql-contrib
```

### 方法2：安装特定版本（如 PostgreSQL 13）
```bash
# 对于 CentOS 8 使用 dnf
sudo dnf install -y postgresql13-server postgresql13-contrib

# 对于 CentOS 7 使用 yum
sudo yum install -y postgresql13-server postgresql13-contrib
```

## 初始化和配置

### 初始化数据库
```bash
# 对于默认版本
sudo postgresql-setup --initdb

# 对于特定版本（如 PostgreSQL 13）
sudo postgresql-13-setup initdb
```

## 启动 PostgreSQL 服务

### 启动服务
```bash
# 对于默认版本
sudo systemctl start postgresql
# 或
sudo systemctl start postgresql.service

# 对于特定版本
sudo systemctl start postgresql-13
```

### 设置开机自启
```bash
# 对于默认版本
sudo systemctl enable postgresql

# 对于特定版本
sudo systemctl enable postgresql-13
```

### 检查服务状态
```bash
sudo systemctl status postgresql
```

## 验证安装

### 切换到 postgres 用户
```bash
sudo -i -u postgres
```

### 连接到 PostgreSQL
```bash
psql
```

### 在 psql 中测试基本命令
```sql
SELECT version();
\q  -- 退出 psql
```

## 重要说明

1. **CentOS 版本差异**：
   - CentOS 7 使用 `yum`
   - CentOS 8 使用 `dnf`

2. **服务名称**：
   - 默认安装：`postgresql` 或 `postgresql.service`
   - 特定版本：`postgresql-版本号`（如 `postgresql-13`）

3. **初始化**：CentOS 不会自动初始化 PostgreSQL 数据库，必须手动执行 `postgresql-setup --initdb`

4. **防火墙**：如果需要远程访问，记得开放 5432 端口
   ```bash
   sudo firewall-cmd --add-port=5432/tcp --permanent
   sudo firewall-cmd --reload
   ```

完成这些步骤后，PostgreSQL 应该已经成功安装并运行在您的 CentOS 系统上了。

## 3. 交互式终端连接 PostgreSQL

```bash
sudo -u postgres psql
```

## 4. 创建用户

```sql
CREATE USER wuhonglei WITH PASSWORD 'xxxxxx';
```

## 5. 创建数据库

```sql
CREATE DATABASE ai_assistant_db OWNER wuhonglei;
```

**所有者权限:** 用户 wuhonglei 将获得对 ai_assistant_db 数据库的全部权限:
  - 完全控制权：可以创建、修改、删除数据库中的对象
  - 权限管理：可以授予其他用户访问权限
  - 模式管理：可以在数据库中创建和管理模式

## 6. 数据库连接
centos 上可以使用 `DataGrip`
