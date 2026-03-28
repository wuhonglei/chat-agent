# bookworm-slim (glibc)：vite-plus 在 alpine/musl 上依赖可选原生包 @voidzero-dev/vite-plus-linux-x64-musl，
# npm ci 常漏装导致 vp build 报错；glibc 镜像使用 linux-x64-gnu 绑定，更稳定。
FROM node:25-bookworm-slim AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm config set registry https://registry.npmmirror.com && \
    npm ci

# Copy source files
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 3000

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
