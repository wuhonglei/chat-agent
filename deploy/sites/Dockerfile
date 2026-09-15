# 纯 nginx 静态站网关：不跑 FastAPI/gateway，按 Host 里的 slug 直接提供 backend/data/sites/{slug}/current
# 只读挂载数据目录，无 Redis；对不上的 Host 一律 404，绝不 fallback 到某个站
FROM nginx:alpine

# 覆盖 conf.d/default.conf（沿用 stock nginx.conf 的 http 层：sendfile/mime 等）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
