# Python 3.12：依赖 wheel 成熟稳定，与本地/CI 常用运行时一致
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Configure timezone and locale
ENV TZ=Asia/Shanghai
ENV DEBIAN_FRONTEND=noninteractive

# Configure apt to use Aliyun mirror for better connectivity in China
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources || \
    echo "deb https://mirrors.aliyun.com/debian/ bookworm main" > /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian/ bookworm-updates main" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian-security/ bookworm-security main" >> /etc/apt/sources.list

# Install system dependencies (Python build tools + Node 20 LTS runtime for agent skills)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    bash \
    gcc \
    g++ \
    git \
    curl \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g pnpm --registry=https://registry.npmmirror.com \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Validate required runtimes for agent skill command execution
RUN bash --version && \
    python --version && \
    node --version && \
    npm --version && \
    pnpm --version

# Install uv for faster dependency installation
# 使用 pip 安装（推荐用于云服务器，利用阿里云镜像加速）
# 使用 pip 安装 uv，配合阿里云 PyPI 镜像源，在国内云服务器上速度更快
RUN pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ uv && \
    uv --version

# Copy project files for dependency installation
COPY pyproject.toml .
COPY uv.lock .

# Install Python dependencies using uv with Chinese mirror
# 从 lockfile 导出 requirements.txt 并安装所有依赖（包括 nacos-sdk-python）
# 这样可以确保所有在 uv.lock 中的依赖都被正确安装
RUN uv export --format requirements.txt --all-packages > /tmp/requirements.txt && \
    uv pip install --system -r /tmp/requirements.txt --index-url https://mirrors.aliyun.com/pypi/simple/ && \
    rm /tmp/requirements.txt

# Copy application code
COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY skills ./skills

# Copy startup script
COPY start.sh ./start.sh

# Make startup script executable
RUN chmod +x /app/start.sh

# Expose port
EXPOSE 8000

# Run the application with auto-migration (start.sh will handle migration before starting)
CMD ["/app/start.sh"]
