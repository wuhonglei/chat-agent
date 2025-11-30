FROM python:3.13.3-slim

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

# Install system dependencies with retry mechanism
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv for faster dependency installation
# 使用 pip 安装（推荐用于云服务器，利用阿里云镜像加速）
# 使用 pip 安装 uv，配合阿里云 PyPI 镜像源，在国内云服务器上速度更快
RUN pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ uv && \
    uv --version

# Copy project files for dependency installation
COPY pyproject.toml .
COPY uv.lock .

# Install Python dependencies using uv with Chinese mirror
RUN uv pip install --system -e . --index-url https://mirrors.aliyun.com/pypi/simple/

# Copy application code
COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# Copy startup script
COPY start.sh ./start.sh

# Make startup script executable
RUN chmod +x /app/start.sh

# Create data directory for runtime data
RUN mkdir -p /app/data/documents /app/data/vectordb /app/data/avatars

# Expose port
EXPOSE 8000

# Run the application with auto-migration (start.sh will handle migration before starting)
CMD ["/app/start.sh"]