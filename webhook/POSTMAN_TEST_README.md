# Postman 测试 GitHub Webhook

## 快速开始

### 1. 启动你的 webhook 服务
```bash
# 开发环境
python3 main.py

# 或生产环境
./start.sh
```

### 2. Postman 配置

#### 请求设置
- **Method**: POST
- **URL**: `http://localhost:9000/postreceive`

#### Headers
```
X-Github-Event: create
X-Hub-Signature: sha1=37221bb0207e9326e7307d23ff7443e38c738320
Content-Type: application/json
```

#### 请求体
选择 **raw** → **JSON**，复制 `webhook_test_payload.json` 的完整内容。

### 3. 测试结果

发送请求后，你应该在控制台看到：
```
收到标签推送：v1.0.0，检查是否在 main 分支...
```

## 自定义测试

### 修改标签名称
在 `webhook_test_payload.json` 中修改 `"ref": "v1.0.0"` 为其他标签名。

### 修改仓库信息
更新 `repository.full_name` 和相关字段以匹配你的仓库。

### 生成新的签名
如果修改了 payload 或 secret，需要重新生成签名：

```bash
source .venv/bin/activate
python3 generate_signature.py
```

## 故障排除

1. **400 错误**: 检查签名是否正确
2. **500 错误**: 检查环境变量和文件路径
3. **忽略消息**: 检查 payload 中的 `ref_type` 是否为 "tag"

## 其他事件类型测试

你可以修改 `X-Github-Event` header 来测试其他事件：

- `push`: 代码推送
- `pull_request`: PR 操作
- `issues`: Issue 操作
- `release`: 发布操作

记得根据不同事件修改相应的 payload 结构。
