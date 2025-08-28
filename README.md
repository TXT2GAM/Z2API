## 原项目：https://github.com/LargeCupPanda/Z2API

### 安装步骤

```bash
git clone https://github.com/TEXT2GAM/Z2API.git
cd Z2API

pip install -r requirements.txt

cp .env.example .env
# 编辑 .env （可部署后在前端修改）

docker build -t z2api .

docker run -d -p 8000:8000 --env-file .env z2api

# or 部署到3000端口
# docker run -d -p 3000:8000 --env-file .env z2api
```

### 前端管理

https://0.0.0.0:8000/admin
