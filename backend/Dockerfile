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
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    /root/.local/bin/uv --version
ENV PATH="/root/.local/bin:${PATH}"

# Copy project files for dependency installation
COPY pyproject.toml .
COPY uv.lock .

# Install Python dependencies using uv with Chinese mirror
RUN uv pip install --system -e . --index-url https://mirrors.aliyun.com/pypi/simple/

# Copy application code
COPY alembic.ini .
COPY alembic ./alembic
COPY private_keys ./private_keys
COPY app ./app
COPY .env .

# Replace localhost with postgres service name in .env for Docker Compose networking
# In Docker Compose, services communicate using service names within the same network
RUN sed -i 's/localhost/postgres/g' .env && \
    echo "Updated .env for Docker Compose networking:" && \
    grep -E "(DATABASE_URL|REDIS_URL|PG_HOST|CHROMA_HOST)" .env || true

# Create data directory for runtime data
RUN mkdir -p /app/data/documents /app/data/vectordb /app/data/avatars

# Expose port
EXPOSE 8000

# Run the application (remove --reload for production)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]