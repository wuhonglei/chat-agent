# Postgres + pgvector 自建镜像（避免直连 Docker Hub 拉取 pgvector/pgvector 超时/denied）
# 基础镜像使用 postgres:16-alpine，多数镜像加速会缓存 library 镜像
ARG PG_MAJOR=16
FROM postgres:${PG_MAJOR}-alpine

ARG PGVECTOR_VERSION=0.8.1

RUN apk add --no-cache \
    build-base \
    git \
    postgresql16-dev \
    && git clone --branch v${PGVECTOR_VERSION} --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector \
    && make clean \
    && make \
    && make install \
    && cd / \
    && rm -rf /tmp/pgvector \
    && apk del build-base git postgresql16-dev
