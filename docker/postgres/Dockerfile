# PostgreSQL 18 + pgvector + zhparser（中文全文检索）
# 基于 pgvector 官方镜像编译安装 SCWS + zhparser；数据仍在 named volume，换镜像不丢库。
FROM pgvector/pgvector:pg18

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        git \
        wget \
        bzip2 \
        postgresql-server-dev-18 \
    && rm -rf /var/lib/apt/lists/*

# SCWS（zhparser 依赖）
WORKDIR /tmp
RUN wget -q http://www.xunsearch.com/scws/down/scws-1.2.3.tar.bz2 \
    && tar -xjf scws-1.2.3.tar.bz2 \
    && cd scws-1.2.3 \
    && ./configure --prefix=/usr/local \
    && make -j"$(nproc)" \
    && make install \
    && ldconfig \
    && cd /tmp \
    && rm -rf scws-1.2.3 scws-1.2.3.tar.bz2

# zhparser
RUN git clone --depth 1 https://github.com/amutu/zhparser.git \
    && cd zhparser \
    && make \
    && make install \
    && cd /tmp \
    && rm -rf zhparser \
    && apt-get purge -y --auto-remove build-essential git wget bzip2 postgresql-server-dev-18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER postgres
WORKDIR /
