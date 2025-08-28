# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

* 你是 Claude
* 使用中文与用户交流
* 遵循 KISS 原则，非必要不要过度设计
* 实现简单可维护，不需要考虑太多防御性的边界条件
* 你需要逐步进行，通过多轮对话来完成需求，进行渐进式开发
* 在开始设计方案或实现代码之前，你需要进行充分的调研。如果有任何不明确的要求，请在继续之前向我确认
* 当你收到一个需求时，首先需要思考相关的方案，并请求我进行审核。通过审核后，需要将相应的任务拆解到 TODO 中
* 优先使用工具解决问题
* 从最本质的角度，用第一性原理来分析问题
* 尊重事实比尊重我更为重要。如果我犯错，请毫不犹豫地指正我，以便帮助我提高

## 项目概述

Z2API 是一个为 Z.AI API 提供 OpenAI 兼容接口的代理服务器，支持智能 cookie 池管理、内容过滤和灵活的响应模式控制。

### 核心功能

- **OpenAI SDK 完全兼容**: 无缝替换 OpenAI API，支持标准的 `/v1/chat/completions` 接口
- **智能 Cookie 池管理**: 支持多个 Z.AI JWT token 的轮换使用、自动故障转移和健康检查
- **灵活响应模式**: 支持流式和非流式两种响应模式，非流式模式下可选择隐藏 AI 思考过程
- **内容过滤**: 可选择性地过滤响应中的思考标签内容
- **Web 管理界面**: 提供直观的 Web 界面进行 Cookie 池管理和环境变量配置

## 常用开发命令

### 启动服务
```bash
# 直接启动服务
python main.py

# 使用环境配置启动
HOST=0.0.0.0 PORT=8000 python main.py
```

### Docker 部署
```bash
# 使用 Docker Compose（推荐）
docker-compose up -d

# 使用 Docker 直接运行
docker run -d -p 8000:8000 --env-file .env z2api

# 带有 Nginx 反向代理的部署
docker-compose --profile with-nginx up -d
```

### 依赖管理
```bash
# 安装依赖
pip install -r requirements.txt

# 查看已安装的包
pip list
```

### 测试和调试
```bash
# 健康检查
curl http://localhost:8000/health

# 测试 API 端点
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-z2api-key-2024" \
  -d '{"model": "GLM-4.5", "messages": [{"role": "user", "content": "Hello"}]}'

# 使用调试脚本（如果存在）
python debug_connection.py

# 测试管理 API
curl http://localhost:8000/api/cookies
curl http://localhost:8000/api/config

# 演示管理功能
python demo.py
python admin_test.py
```

### 日志查看
```bash
# Docker 日志
docker-compose logs -f z2api

# 直接运行时的日志（需要修改启动命令）
# 日志级别可通过 LOG_LEVEL 环境变量控制：DEBUG, INFO, WARNING, ERROR
```

## 代码架构

### 核心模块

- **main.py**: FastAPI 应用入口，包含路由、认证和应用生命周期管理
- **config.py**: 配置管理，处理环境变量和应用设置
- **proxy_handler.py**: 代理请求处理器，处理与 Z.AI API 的通信
- **cookie_manager.py**: Cookie 池管理器，负责 token 轮换、健康检查和故障转移
- **models.py**: Pydantic 数据模型，定义 OpenAI API 兼容的请求响应结构
- **admin_api.py**: 管理 API 端点，提供 Cookie 和配置的 RESTful 接口
- **static/admin.html**: Web 管理界面，提供直观的用户交互界面

### 请求处理流程

1. **认证验证** (`main.py:59-68`): 使用固定的 API Key 进行认证
2. **模型验证** (`main.py:96-101`): 验证请求的模型名称是否为 "GLM-4.5"
3. **Cookie 获取** (`cookie_manager.py:25-48`): 使用轮询算法获取可用的 Cookie
4. **请求转发** (`proxy_handler.py:168-196`): 将请求转换为 Z.AI API 格式并发送
5. **响应处理** (`proxy_handler.py:208-426`): 处理流式和非流式响应，进行内容转换

### 关键特性实现

#### Cookie 池管理

- **轮询调度** (`cookie_manager.py:25-48`): 使用 `current_index` 实现 round-robin 负载均衡
- **故障转移** (`cookie_manager.py:50-54`): 失败的 Cookie 会被标记并跳过
- **自动恢复** (`cookie_manager.py:130-151`): 后台任务定期检查失败 Cookie 的健康状态
- **健康检查** (`cookie_manager.py:63-128`): 发送测试请求验证 Cookie 有效性

#### 响应模式控制

- **流式响应** (`proxy_handler.py:268-277`): 实时转发 Z.AI 的流式响应
- **非流式响应** (`proxy_handler.py:278-307`): 聚合所有流式块，返回完整响应
- **内容过滤** (`proxy_handler.py:40-97`): 根据 `SHOW_THINK_TAGS` 设置移除或转换思考标签

#### 模型映射

- **入站** (`config.py:20-21`): OpenAI 格式的 `"GLM-4.5"` 模型名
- **出站** (`config.py:16-17`): Z.AI API 格式的 `"0727-360B-API"` 模型名
- **映射逻辑** (`proxy_handler.py:105-110`): 请求发送前转换模型名称

### 环境配置

### 必需配置
- `Z_AI_COOKIES`: Z.AI 的 JWT 令牌，多个用逗号分隔

### 重要配置选项
- `API_KEY`: 外部认证密钥 (默认: `sk-z2api-key-2024`)
- `SHOW_THINK_TAGS`: 非流式响应中是否显示思考标签 (默认: `false`)
- `DEFAULT_STREAM`: 默认是否使用流式响应 (默认: `false`)
- `LOG_LEVEL`: 日志级别 (DEBUG, INFO, WARNING, ERROR)

### 响应模式说明

| 模式 | 参数 | 思考内容过滤 | 适用场景 |
|------|------|-------------|----------|
| 非流式 | `stream=false` | ✅ 支持 `SHOW_THINK_TAGS` | 简洁回答，API 集成 |
| 流式 | `stream=true` | ❌ 忽略 `SHOW_THINK_TAGS` | 实时交互，聊天界面 |

### 技术栈

- **Web 框架**: FastAPI + Uvicorn
- **HTTP 客户端**: httpx (支持 HTTP/2 和流式响应)
- **数据验证**: Pydantic 2.x
- **异步处理**: asyncio
- **容器化**: Docker + Docker Compose
- **反向代理**: Nginx (可选)
- **前端技术**: 原生 HTML5 + CSS3 + JavaScript (ES6+)
- **环境配置**: python-dotenv

### 重要注意事项

1. **内容过滤仅对非流式响应生效**: 流式响应 (`stream=true`) 会忽略 `SHOW_THINK_TAGS` 设置
2. **Cookie 健康检查**: 后台每 10 分钟检查一次失败的 Cookie，避免频繁的健康检查请求
3. **流式响应处理**: 使用 `response.aiter_text(chunk_size=1024)` 实现真正的实时流式处理
4. **模型名称转换**: 入站使用 "GLM-4.5"，出站转换为 "0727-360B-API"
5. **安全认证**: 使用固定 API Key，配置在 `config.py:24`

### 开发调试

- 启用详细日志: `LOG_LEVEL=DEBUG`
- 使用调试脚本: `python debug_connection.py` (如果存在)
- 查看 Cookie 状态: 检查日志中的 Cookie 管理器信息
- 测试健康检查: 访问 `/health` 端点

### 管理界面

访问 `http://localhost:8000/admin` 使用以下功能:

- **Cookie 管理**: 批量添加、删除、测试 Z.AI tokens
- **配置管理**: 实时修改环境变量配置
- **状态监控**: 查看 Cookie 健康状态和统计信息

#### 管理端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/admin` | GET | Web 管理界面 |
| `/api/cookies` | GET | 获取 Cookie 列表和状态 |
| `/api/cookies` | POST | 批量更新 Cookie |
| `/api/cookies` | DELETE | 清空所有 Cookie |
| `/api/cookies/test` | POST | 测试单个 Cookie |
| `/api/config` | GET | 获取当前配置 |
| `/api/config` | PUT | 更新配置 |
| `/api/config/reload` | POST | 重载服务配置 |