# Z2API 前端管理功能

本文档介绍了新添加的前端管理功能，包括 Cookie 池管理和环境变量配置。

## 🎯 功能特性

### 🍪 Cookie 管理
- **批量添加/删除**: 支持一行一个的批量 Cookie 管理
- **状态监控**: 实时显示 Cookie 总数、失败数量和可用数量
- **在线测试**: 可以单独测试每个 Cookie 的有效性
- **自动刷新**: 支持刷新 Cookie 状态，实时查看统计信息

### ⚙️ 环境变量配置
- **实时编辑**: 修改服务器配置项，如 API Key、日志级别、端口等
- **即时生效**: 配置修改后立即生效，无需重启服务
- **配置重载**: 支持重新加载所有配置，重置 Cookie 管理器状态

## 🚀 使用方法

### 启动服务

```bash
# 启动 Z2API 服务
python main.py

# 或使用 Docker
docker-compose up -d
```

### 访问管理界面

打开浏览器访问:
```
http://localhost:8000/admin
```

## 📋 管理界面功能

### Cookie 管理

#### 1. 添加 Cookie
- 在文本框中输入 Z.AI Cookie，一行一个
- 格式示例:
  ```
  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...token1
  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...token2
  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...token3
  ```
- 点击 "💾 保存 Cookie" 按钮提交

#### 2. 测试 Cookie
- 在 "测试 Cookie" 输入框中输入要测试的 Cookie
- 点击 "🔄 测试 Cookie" 按钮
- 等待测试结果显示

#### 3. 监控状态
- 查看 "总 Cookie 数"、"失败 Cookie 数"、"可用 Cookie 数"
- 点击 "🔄 刷新状态" 按钮更新统计信息

#### 4. 清空 Cookie
- 点击 "🗑️ 清空 Cookie" 按钮
- 确认后删除所有 Cookie

### 环境变量配置

#### 支持的配置项:

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| **API Key** | 外部认证密钥 | `sk-z2api-key-2024` |
| **服务器地址** | 服务监听地址 | `0.0.0.0` |
| **端口** | 服务端口 | `8000` |
| **日志级别** | 日志详细程度 | `INFO` |
| **显示思考标签** | 非流式响应是否显示思考过程 | `false` |
| **默认流式模式** | 默认使用流式响应 | `false` |
| **每分钟最大请求数** | 速率限制 | `60` |
| **自动刷新令牌** | 自动刷新失效令牌 | `false` |
| **刷新检查间隔** | 令牌检查间隔(秒) | `3600` |

#### 操作步骤:
1. 修改需要调整的配置项
2. 点击 "💾 保存配置" 按钮
3. 系统会显示保存成功的信息

#### 高级操作:
- **重载服务配置**: 点击 "🔄 重载服务" 按钮，会重新初始化 Cookie 管理器
- **刷新界面**: 点击 "🔄 刷新配置" 按钮，重新获取当前配置

## 🔧 API 接口

### Cookie 管理 API

#### 获取 Cookie 列表
```bash
GET /api/cookies

Response:
{
    "cookies": ["cookie1", "cookie2", ...],
    "count": 3,
    "failed_count": 1,
    "failed_cookies": ["failed_cookie"]
}
```

#### 批量更新 Cookie
```bash
POST /api/cookies
Content-Type: application/json

Request Body:
{
    "cookies": ["cookie1", "cookie2", ...]
}

Response:
{
    "message": "成功更新 3 个 Cookie",
    "cookies": ["cookie1", "cookie2", ...]
}
```

#### 清空 Cookie
```bash
DELETE /api/cookies

Response:
{
    "message": "已清空所有 Cookie"
}
```

#### 测试单个 Cookie
```bash
POST /api/cookies/test
Content-Type: application/json

Request Body:
{
    "cookie": "your_cookie_here"
}

Response:
{
    "cookie": "eyJhbG...",
    "is_valid": true,
    "message": "Cookie 有效"
}
```

### 配置管理 API

#### 获取配置
```bash
GET /api/config

Response:
{
    "api_key": "sk-z2api-key-2024",
    "show_think_tags": false,
    "default_stream": false,
    "log_level": "INFO",
    "max_requests_per_minute": 60,
    "port": 8000,
    "host": "0.0.0.0",
    "auto_refresh_tokens": false,
    "refresh_check_interval": 3600
}
```

#### 更新配置
```bash
PUT /api/config
Content-Type: application/json

Request Body:
{
    "log_level": "DEBUG",
    "show_think_tags": true,
    "max_requests_per_minute": 100
}

Response:
{
    "message": "已更新配置: log_level, show_think_tags, max_requests_per_minute",
    "updated_fields": ["log_level", "show_think_tags", max_requests_per_minute]
}
```

#### 重载配置
```bash
POST /api/config/reload

Response:
{
    "message": "配置已重新加载"
}
```

## 🧪 测试脚本

项目包含几个测试脚本用于验证功能:

### 1. 功能演示脚本
```bash
python demo.py
```
展示所有管理功能的完整使用流程。

### 2. API 测试脚本
```bash
python admin_test.py
```
快速测试所有 API 端点的连通性。

## 🎨 界面特性

### 响应式设计
- 桌面端: 双栏布局，Cookie 和配置管理并排显示
- 移动端: 单栏布局，自动适应小屏幕

### 用户体验
- **实时反馈**: 操作完成后立即显示结果通知
- **数据验证**: 输入数据自动验证，防止无效操作
- **状态指示**: 清晰的颜色编码（绿色=成功，红色=错误，橙色=警告）
- **确认对话框**: 危险操作（如清空 Cookie）需要二次确认

### 视觉设计
- 现代化渐变色彩方案
- 卡片式布局，信息层次清晰
- 悬停效果和过渡动画
- 图标辅助，提升识别度

## 📋 使用示例

### 场景1: 配置新的 Z.AI 代理

1. 访问 http://localhost:8000/admin
2. 复制从 chat.z.ai 获取的多个 JWT token
3. 在 Cookie 管理区域的文本框中粘贴，一行一个
4. 点击 "💾 保存 Cookie"
5. 检查状态区域确认已添加的 Cookie 数量
6. 可选: 点击 "🔄 测试 Cookie" 验证单个 token 有效性

### 场景2: 调整响应模式

1. 在环境变量配置区域
2. 设置 "显示思考标签" 为 "是" （希望看到 AI 思考过程）
3. 设置 "默认流式模式" 为 "否" （用于 API 集成）
4. 点击 "💾 保存配置"
5. 配置立即生效，新的请求将使用新设置

### 场景3: 监控和维护

1. 定期访问管理界面
2. 查看 Cookie 状态，关注失败 Cookie 数量
3. 如果有失败 Cookie，考虑获取新的 token 替换
4. 调整日志级别为 "DEBUG" 进行问题排查
5. 维护完成后恢复为 "INFO" 级别

## 🔐 安全考虑

### 访问控制
- 管理界面目前对所有访问开放，建议在生产环境中添加访问控制
- 独立部署时可考虑使用网络防火墙限制访问
- 可集成 Nginx 的 basic auth 或 OAuth 进行认证

### 数据安全
- Cookie 在前端显示时会进行截断处理，保护敏感信息
- 环境变量修改会同步到 .env 文件，确保权限设置正确
- 建议定期备份重要的配置文件

## 🐛 故障排除

### 常见问题

#### 1. 管理界面无法访问
```bash
# 检查服务状态
curl http://localhost:8000/health

# 检查日志
docker-compose logs z2api
```

#### 2. Cookie 保存失败
- 确保输入的 Cookie 格式正确
- 检查 .env 文件是否有写入权限
- 查看服务器控制台错误日志

#### 3. 配置更改不生效
- 确认点击了保存按钮
- 检查配置值格式是否正确
- 尝试点击 "🔄 重载服务" 强制重载

#### 4. 测试 Cookie 失败
- 确认输入的是完整有效的 JWT token
- 检查网络连接是否正常
- 验证 token 是否已过期

### 调试技巧

#### 启用详细日志
1. 在管理界面中设置日志级别为 "DEBUG"
2. 保存配置
3. 查看服务器控制台输出的详细日志

#### 重置配置
1. 备份当前的 .env 文件
2. 从 .env.example 复制新配置
3. 修改必要的配置项
4. 重启服务

#### 恢复服务
```bash
# 停止服务
docker-compose down

# 重启服务
docker-compose up -d

# 查看日志
docker-compose logs -f z2api
```

## 📚 相关文档

- [README.md](./README.md) - 项目主要文档
- [DOacker.md](./DOacker.md) - Docker 部署指南
- [CLAUDE.md](./CLAUDE.md) - 开发指南
- [.env.example](./.env.example) - 配置示例

---

🎉 恭喜！现在您可以通过直观的 Web 界面管理 Z2API 服务的所有重要配置了！