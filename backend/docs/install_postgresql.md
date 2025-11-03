# Mac 安装 PostgreSQL

## 1. 安装 PostgreSQL

```bash
brew install postgresql
```

## 2. 启动 PostgreSQL

```bash
brew services start postgresql
```

## 3. 交互式终端连接 PostgreSQL

```bash
psql -U postgres
```

## 4. 创建用户

```sql
CREATE USER wuhonglei WITH PASSWORD 'xxxxxx';
```

## 5. 创建数据库

```sql
CREATE DATABASE ai_assistant_db;
```

## 6. 授予用户权限

```sql
GRANT ALL PRIVILEGES ON DATABASE ai_assistant_db TO wuhonglei;
```

## 7. 退出 PostgreSQL

```sql
\q
```
