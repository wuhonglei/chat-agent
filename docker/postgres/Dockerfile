# Postgres + pgvector 自建镜像（避免直连 Docker Hub 拉取 pgvector/pgvector 超时/denied）
# 使用 Debian 基础镜像：Alpine 仓库暂无 postgresql18-dev，bookworm 有 postgresql-server-dev-18
ARG PG_MAJOR=18
FROM postgres:${PG_MAJOR}-bookworm

ARG PG_MAJOR
ARG PGVECTOR_VERSION=0.8.1

RUN apt-get update \
    && apt-mark hold locales \
    && apt-get install -y --no-install-recommends build-essential git postgresql-server-dev-${PG_MAJOR} \
    && git clone --branch v${PGVECTOR_VERSION} --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector \
    && make clean \
    && make OPTFLAGS="" \
    && make install \
    && mkdir -p /usr/share/doc/pgvector \
    && cp LICENSE README.md /usr/share/doc/pgvector \
    && cd / \
    && rm -rf /tmp/pgvector \
    && apt-get remove -y build-essential git postgresql-server-dev-${PG_MAJOR} \
    && apt-get autoremove -y \
    && apt-mark unhold locales \
    && rm -rf /var/lib/apt/lists/*
