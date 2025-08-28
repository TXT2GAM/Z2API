## 原项目：https://github.com/LargeCupPanda/Z2API

### 安装步骤

## Docker部署
```bash
git clone https://github.com/TXT2GAM/Z2API.git
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

---


### 更新容器

```bash
cd Z2API

git pull origin main
# or
# git fetch origin && git reset --hard origin/main

pip install -r requirements.txt
docker build -t z2api:latest .
docker ps

#（将CONTAINER_ID替换为实际的容器ID）
docker stop Z2API_CONTAINER_ID
docker rm Z2API_CONTAINER_ID

docker run -d -p 8000:8000 --env-file .env z2api
```