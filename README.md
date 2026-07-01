# Img2Video - 生成式插画与动画平台

## 项目结构

```
prj/
├── backend/           # 后端 API 服务 (FastAPI)
│   ├── app/
│   │   ├── routers/   # API 路由
│   │   ├── services/  # 业务服务
│   │   ├── models.py  # 数据库模型
│   │   ├── schemas.py # Pydantic 模型
│   │   └── main.py    # 应用入口
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/          # 前端用户应用 (React + Vite)
│   ├── src/
│   ├── Dockerfile
│   └── nginx.conf
├── admin/             # 后台管理系统 (React + Vite)
│   ├── src/
│   ├── Dockerfile
│   └── nginx.conf
├── docker/            # 集成镜像配置文件（app.conf, start.sh, supervisor 等）
├── Dockerfile         # All-in-one 集成镜像 Dockerfile
├── docker-compose.yml # 一键部署编排配置
└── .env.example       # 环境变量示例
```

## 快速开始（一键部署）

### 前置条件

- Docker Engine 24+
- Docker Compose v2+

### 1. 环境配置

```bash
cd prj
cp .env.example .env
```

编辑 `.env` 文件，填入 AI API 密钥等必要配置：

```env
ANTHROPIC_BASE_URL=https://your-api-endpoint.com
ANTHROPIC_AUTH_TOKEN=your-auth-token
SECRET_KEY=your-super-secret-key
```

`PUBLIC_BASE_URL` 和其他配置已有默认值，首次部署通常无需修改。

### 2. 一键启动

```bash
docker-compose up -d
```

首次启动会自动完成以下操作：
- 构建 all-in-one 应用镜像（前端 + 管理后台 + 后端 API + Nginx 路由）
- 启动 PostgreSQL、Redis、MinIO 基础设施
- 初始化数据库表结构
- 创建 MinIO 存储桶
- 启动 Nginx 路径路由、Uvicorn API 服务、Celery 任务队列

### 3. 访问服务

| 服务 | 地址 |
|------|------|
| 用户前端 | http://your-server.com:8103/front |
| 后台管理 | http://your-server.com:8103/admin |
| API 文档 | http://your-server.com:8103/api/docs |
| MinIO 控制台 | http://your-server.com:8101 |

### 4. 创建管理员账号

```bash
# 注册普通用户
curl -X POST http://your-server.com:8103/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@example.com","password":"admin123"}'

# 提升为管理员
docker exec img2video-postgres psql -U postgres -d img2video \
  -c "UPDATE users SET is_admin = true WHERE username = 'admin';"
```

---

## 部署配置说明

将本项目的 `.env.example` 复制为 `.env` 后，需根据实际环境修改以下配置：

### 必须修改

| 变量 | 说明 | 示例 |
|------|------|------|
| `ANTHROPIC_BASE_URL` | AI 图像生成 API 地址 | `https://your-api-endpoint.com` |
| `ANTHROPIC_AUTH_TOKEN` | AI API 认证令牌 | `sk-your-token` |
| `SECRET_KEY` | JWT 签名密钥（生产环境务必更换为随机字符串） | 可用 `openssl rand -hex 32` 生成 |

### 按需修改

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PUBLIC_BASE_URL` | 公网可访问的应用地址（视频生成 API 需要） | `http://localhost:8103` |
| `MINIO_PUBLIC_ENDPOINT` | MinIO 控制台公网地址 | `localhost:8101` |
| `DATABASE_URL` | 数据库连接串（docker-compose 内置 PostgreSQL 时无需修改） | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis 连接串 | `redis://redis:6379/0` |

### 安全注意事项

> ⚠️ **`.env` 文件包含敏感信息，切勿提交到版本控制！** 本项目已通过 `.gitignore` 自动排除 `.env`。
>
> 生产部署前请务必：
> 1. 修改 `SECRET_KEY` 为强随机字符串
> 2. 修改 `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`（docker-compose.yml 中默认值为 `minioadmin`）
> 3. 更换 `POSTGRES_PASSWORD`（docker-compose.yml 中默认值为 `postgres`）
> 4. 确保 API 令牌（`ANTHROPIC_AUTH_TOKEN` 等）安全保管

---

## 服务架构

### 端口分配

应用服务遵循 **路径路由** 模式，统一通过 8103 端口访问，以路径前缀区分服务。

| 对外端口 | 服务 | 说明 |
|----------|------|------|
| 8101 | MinIO Console | 对象存储管理界面（HTTP） |
| 8103 | 应用入口 | 路径路由：`/front`、`/admin`、`/api` |

### 路径路由表

| 服务 | 路径 | HTTP 地址 |
|------|------|-----------|
| 前端应用 | `/front` | `http://host:8103/front` |
| 后台管理 | `/admin` | `http://host:8103/admin` |
| 后端 API | `/api/*` | `http://host:8103/api/docs` |
| 后端 API（外部） | `/back/*` | `http://host:8103/back/*`（映射到 `/api/*`）|

> 前端和管理后台为 SPA（单页应用），前端路由（如 `/front/login`）由 React Router 在浏览器端处理。
> 后端 API 文档位于 `/api/docs`，由 FastAPI 自动生成。

### 内部端口（容器内，不对外暴露）

| 服务 | 端口 | 说明 |
|------|------|------|
| Backend (uvicorn) | 8102 | FastAPI 应用服务 |
| MinIO S3 API | 9000 | 对象存储接口 |
| PostgreSQL | 5432 | 数据库 |
| Redis | 6379 | 缓存 / 消息队列 |

---

## 日常运维

### 查看日志

```bash
# 应用日志
docker-compose logs -f app

# 数据库日志
docker-compose logs -f postgres

# 查看 supervisor 内部进程日志
docker exec img2video-app cat /var/log/supervisor/backend.out.log
```

### 重启服务

```bash
# 仅重启应用（保留数据库）
docker-compose restart app

# 完全重建（含镜像重新构建）
docker-compose up -d --build
```

### 数据持久化

数据卷自动管理，停服不丢失数据：

```bash
docker-compose down          # 停止，保留数据
docker-compose down -v       # 停止并清除数据卷（谨慎）
```

---

## 故障排查（远程服务器）

以下命令在远程服务器上执行，用于诊断常见问题。

### 容器状态

```bash
# 查看所有容器运行状态
docker ps --filter name=img2video --format "table {{.Names}}\t{{.Status}}"

# 查看 app 容器完整日志
docker logs img2video-app --tail 50
```

### Nginx 诊断

```bash
# 检查 nginx 配置是否加载（含上传大小限制）
docker exec img2video-app sh -c "grep client_max /etc/nginx/sites-enabled/app"

# 检查 nginx 配置语法
docker exec img2video-app sh -c "nginx -t"

# 查看 nginx 启动/运行错误
docker exec img2video-app sh -c "cat /var/log/supervisor/nginx.err.log"
```

### 后端诊断

```bash
# 查看后端运行日志
docker exec img2video-app sh -c "cat /var/log/supervisor/backend.out.log"

# 查看后端错误日志
docker exec img2video-app sh -c "cat /var/log/supervisor/backend.err.log"

# 查看 Celery 任务队列日志
docker exec img2video-app sh -c "cat /var/log/supervisor/celery.err.log"
```

### 网络连通性

```bash
# 测试 app 到 postgres 的连接
docker exec img2video-app sh -c "python -c 'import socket; s=socket.create_connection((\"postgres\",5432),timeout=5); s.close(); print(\"postgres OK\")'"

# 测试 app 到 redis 的连接
docker exec img2video-app sh -c "python -c 'import socket; s=socket.create_connection((\"redis\",6379),timeout=5); s.close(); print(\"redis OK\")'"
```

### 上传测试（用 curl 模拟）

```bash
# 先获取登录 token
TOKEN=$(curl -s http://localhost:8103/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 测试上传（直接调后端，绕过 nginx，用于判断问题是否在 nginx）
curl -v -X POST http://localhost:8102/api/images/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.png"

# 测试上传（通过 nginx 路径路由）
curl -v -X POST http://localhost:8103/api/images/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.png"
```

### 常见问题与解决

| 问题 | 现象 | 排查 | 解决 |
|------|------|------|------|
| 图片上传失败 | 弹窗"上传失败"，浏览器控制台 413 | `grep client_max /etc/nginx/sites-enabled/app` | docker-compose.yml 中未更新镜像时需 `docker-compose up -d --build` |
| Nginx 无法启动 | 页面无法访问，容器不断重启 | `cat /var/log/supervisor/nginx.err.log` | 检查是否有 `getpwnam("nginx")` 错误，需重建镜像 |
| 后端无法连接数据库 | 页面加载卡住，API 返回 500 | `docker logs img2video-app` 查看 SQLAlchemy 错误 | 检查 postgres 容器是否 healthy，网络是否正常 |
| 前端白屏/404 | 访问 /front 显示空白或 404 | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8103/front/` | 检查构建时 `base: '/front'` 是否正确配置，重建前端 |

---

## 开发模式

### 后端

```bash
cd prj/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8102
```

### 前端

```bash
cd prj/frontend
npm install
npm run dev
```

### 管理后台

```bash
cd prj/admin
npm install
npm run dev
```

---

## 技术栈

- **后端**: FastAPI, SQLAlchemy, Celery, Redis
- **前端**: React 18, TypeScript, Ant Design, Zustand
- **存储**: PostgreSQL, MinIO
- **容器化**: Docker, Docker Compose, Nginx, Supervisor

---

## API 接口

### 认证接口
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户

### 图像接口
- `POST /api/images/upload` - 上传参考图
- `GET /api/images/reference` - 获取参考图列表
- `POST /api/images/generate` - 生成图像
- `POST /api/images/generate-video` - 生成视频

### 管理接口
- `GET /api/admin/dashboard` - 仪表盘统计
- `GET /api/admin/users` - 用户列表
- `PUT /api/admin/users/{id}` - 更新用户
- `GET /api/admin/tasks` - 任务列表
- `GET /api/admin/config` - 系统配置
