-- 数据库初始化脚本
-- 此脚本会在 PostgreSQL 容器首次启动时自动执行
-- 注意：用户和数据库已由 Docker 环境变量自动创建

-- 设置时区
SET timezone = 'Asia/Shanghai';

-- 创建常用扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID 生成
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- 文本相似度搜索
CREATE EXTENSION IF NOT EXISTS "btree_gin";      -- GIN 索引优化

-- 设置默认搜索路径
ALTER DATABASE ai_assistant_db SET search_path TO public;

-- 创建应用特定的配置
-- 可以在这里添加应用需要的表、索引、函数等

-- 输出初始化完成信息
SELECT 
    current_database() as database_name,
    current_user as current_user,
    version() as postgres_version,
    'Database initialization completed successfully' AS status;
