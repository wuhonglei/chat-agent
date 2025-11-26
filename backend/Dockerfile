FROM python:3.13.3-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency installation
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy project files for dependency installation
COPY pyproject.toml .
COPY uv.lock .

# Install Python dependencies
RUN uv pip install --system -e .

# Copy application code
COPY app ./app
COPY private_keys ./private_keys
COPY alembic ./alembic
COPY alembic.ini .

# Create data directory for runtime data
RUN mkdir -p /app/data/documents /app/data/vectordb /app/data/avatars

# Expose port
EXPOSE 8000

# Run the application (remove --reload for production)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]