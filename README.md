## 原项目：https://github.com/LargeCupPanda/Z2API

## 安装步骤

### 方法1：Docker部署
```bash
git clone https://github.com/TXT2GAM/Z2API.git
cd Z2API

cp .env.example .env

# 编辑 .env （可部署后在前端修改）
# nano .env

docker build -t z2api .

docker run -d -p 8000:8000 --env-file .env z2api

# or 部署到3000端口
# docker run -d -p 3000:8000 --env-file .env z2api
```

---

### 方法2：Docker Compose部署

```bash
git clone https://github.com/TXT2GAM/Z2API.git
cd Z2API

cp .env.example .env

# 编辑 .env （可部署后在前端修改）
# nano .env
# nano docker-compose.yml

docker compose up -d
```

#### 更新容器

```bash
cd Z2API

git pull origin main
# or
# git fetch origin && git reset --hard origin/main

docker compose down
docker compose pull
docker compose up -d
```

---

### 前端管理

https://0.0.0.0:8000/admin

---