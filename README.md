# GEO Integration Platform — AI 搜索优化一站式平台

基于超算GEO（chaosuangeo.com）开源前后端协议 100% 兼容复刻的全量本地实现平台，
覆盖 **GEO 评估 → 合规检测 → AI 内容生产 → 全渠道发布** 全链路。

> 接口契约基准见 [docs/GEO_PROTOCOL.md](docs/GEO_PROTOCOL.md)：响应信封 `{code,msg,data}`、
> DRF 分页、Celery 任务状态查询协议、csg/v1 CPU 调度协议、5 类 action_type 计费映射均可直接对接原版前端。

## 功能总览

| 模块 | 能力 |
|---|---|
| GEO 评估 | 关键词批量导入/打标、7 大 AI 平台（deepseek/doubao/ernie/kimi/qwen/hunyuan/metaso）检测、引用率/提及率/情感/GEO 得分、看板与趋势 |
| 合规检测 | 广告法极限词/医疗宣称/收益承诺/敏感词/来源缺失 8 类规则、风险评分、付费解锁（COMPLIANCE_UNLOCK） |
| AI 内容生产 | 品牌知识库构建（kb_build）、GEO 友好文章生成（关键词密度可控）、内容管理 |
| 全渠道发布 | 11 个自媒体平台（小红书/公众号/头条/知乎/CSDN/百家号/掘金/搜狐/雪球/博客园/51CTO）、批量发布、任务重试/取消、媒体库渠道采购 |
| 计费中心 | fixed/multiplier 零售定价、原子扣款、GP 流水、会员套餐、支付沙箱 |
| CPU 调度器 | csg/v1 任务信封、Redis ZSET 优先队列（可降级 DB）、租户公平调度（DRF）、local/slurm 双执行器、task_usage 计量 |
| 辅助 | sk- 接入码管理、工单系统、浏览器插件通道（extension_monitor/social_publisher）、Partner 兼容层 |

## 目录结构

```
├── backend/               # FastAPI 后端（Python 3.7+，端口 8001）
│   ├── app/
│   │   ├── main.py        # 应用入口（建表/种子/路由/调度器启动）
│   │   ├── config.py      # 环境变量配置（pydantic-settings）
│   │   ├── models.py      # 31 张表 ORM（与 sql/schema.sql 对应）
│   │   ├── billing.py     # 原子扣款/流水/零售定价
│   │   ├── security.py    # JWT/sha256_crypt/图形验证码
│   │   ├── scheduler/     # csg/v1 调度器（core/local/slurm_worker/handlers）
│   │   ├── engines/       # 7 平台适配器/GEO评估/合规/内容生成/发布
│   │   └── routers/       # users/keywords/results/content/account_info/payment/feedback/extensions
│   ├── tests/smoke.py     # 端到端冒烟测试（32 项断言）
│   └── requirements.txt
├── frontend/              # Vue3 + Vite + Element Plus 管理台（端口 9527）
├── sql/schema.sql         # MySQL 完整建表脚本
├── deploy/
│   ├── docker-compose.yml # MySQL + Redis + API + Nginx 一键编排
│   ├── nginx.conf
│   └── slurm_api.sh       # 超算登录节点 API 作业脚本
└── docs/GEO_PROTOCOL.md   # 超算GEO 原生协议契约文档
```

## 一、本地快速跑通（Windows / Linux / macOS）

### 1. 启动后端

```bash
cd backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt        # Linux: venv/bin/pip
copy .env.example .env                               # 按需修改
venv\Scripts\python run.py                           # Linux: venv/bin/python run.py
```

默认 SQLite + 全引擎确定性 mock，**零外部依赖开箱即跑**。
验证：`curl http://127.0.0.1:8001/health` → `{"status":"ok",...}`

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev            # http://localhost:9527（/api 代理到 8001）
npm run build          # 生产构建到 dist/
```

注册任意账号（注册即送 100 元体验金），进入看板 → 批量导入关键词 → 一键检测 → 查看报告 → 生成内容 → 全渠道发布。

### 3. 端到端冒烟测试

```bash
# CAPTCHA_ENABLED=false 仅为测试放行验证码；生产保持默认 true
CAPTCHA_ENABLED=false venv/Scripts/python run.py    # 终端 1
venv/Scripts/python tests/smoke.py                  # 终端 2：32 项全 PASS
```

## 二、Docker Compose 一键部署

```bash
cd frontend && npm install && npm run build && cd ..   # 先构建前端静态资源
cd deploy
docker compose up -d --build
# 前端 http://localhost:9527   API http://localhost:8001/api/docs
# MySQL 已自动执行 sql/schema.sql 初始化
```

生产切换：`PAYMENT_SANDBOX=false`、`CAPTCHA_ENABLED=true`、修改 `SECRET_KEY`。

## 三、超算（Slurm 集群）部署跑通指南

### 架构

```
登录节点：uvicorn API（:8001）+ Nginx 静态前端
    │  EXECUTOR=slurm
    ▼
计算节点：每个任务 sbatch 单 CPU 作业（--cpus-per-task 与信封 cpu_cores 对齐）
    └── python -m app.scheduler.slurm_worker <task_id>  # 计算节点直连 DB 执行并回写状态
```

### 步骤

1. **准备环境**（登录节点）：

```bash
module load python/3.10 anaconda/2023 2>/dev/null || true
# 离线环境可 pip download 到本地再安装
pip install -r backend/requirements.txt
mysql -u geo -p -h 127.0.0.1 < sql/schema.sql       # 或让管理员建库
```

2. **配置环境变量**（写入 `backend/.env` 或 export）：

```bash
export DATABASE_URL="mysql+pymysql://geo:geo123@127.0.0.1:3306/geo_platform?charset=utf8mb4"
export REDIS_URL="redis://127.0.0.1:6379/0"        # 可选，提升队列吞吐
export EXECUTOR=slurm
export SLURM_PARTITION=cpu                          # 集群实际分区名（sinfo 查看）
export SLURM_PYTHON=/usr/bin/python3                # 计算节点 python 路径
export SECRET_KEY=please-change-me
```

3. **启动 API 服务**（登录节点常驻，或按集群规矩提交长时作业）：

```bash
sbatch deploy/slurm_api.sh        # 方式 A：作为 Slurm 作业
# 或方式 B：nohup uvicorn app.main:app --host 0.0.0.0 --port 8001 &
```

4. **前端**：`npm run build` 后把 `frontend/dist` 交给集群 Nginx（配置见 `deploy/nginx.conf`，
   `/api/` 反代到 `登录节点IP:8001`）。

5. **验证调度链路**：页面提交一次关键词检测，观察：

```bash
squeue -u $USER                    # 能看到 geo_keyword_check 作业
curl -H "Authorization: Bearer <token>" \
     http://127.0.0.1:8001/api/celery_tasks/task-status/<task_id>/
# data.status: PENDING → STARTED → PROGRESS → SUCCESS
```

6. **计量与配额**：每次任务结束写 `task_usage`（cpu_seconds），
   `compute_nodes` 维护节点/分区视图；`TENANT_MAX_CONCURRENT` 控制单租户并发，实现 DRF 公平调度。

### 超算注意事项

- 计算节点通常**无外网**：`*_API_KEY` 真实 AI 引擎调用建议只在登录节点可用外网时启用，
  否则保持 mock 模式（确定性结果，链路完全可验证）。
- DB 需所有计算节点可达（ MySQL 服务地址用管理网 IP）；SQLite 仅适合单机模式。
- `SLURM_WORKDIR`（默认 `./slurm_jobs`）需在共享存储上，保证登录/计算节点路径一致。

## 四、原生协议兼容性

- 与超算GEO 前端/插件对接：API 路径、字段、信封 100% 一致（`/api/users/login/` 返回 `data.token`、
  `/api/celery_tasks/task-status/{id}/` 等），前端把 baseURL 指向本平台即可。
- 本平台作为上游：`POST /partners/issue-user-token/`（`X-Partner-Key`，默认 `pk-geo-local-partner`）
  可为第三方用户签发 `sk-` 接入码。

## 五、常用配置项（backend/.env）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | SQLite | 可切 MySQL/PG |
| `EXECUTOR` | local | `slurm` 切超算执行器 |
| `CPU_CONCURRENCY` | 4 | local 线程池 CPU 配额 |
| `TENANT_MAX_CONCURRENT` | 2 | 单租户并发上限（公平调度） |
| `REDIS_URL` | 空 | 配置后启用 Redis ZSET 优先队列 |
| `PAYMENT_SANDBOX` | true | true=订单自动确认到账 |
| `CAPTCHA_ENABLED` | true | 生产务必开启 |
| `*_API_KEY` | 空 | 七大 AI 平台密钥，缺失走确定性 mock |
| `PUBLISH_WEBHOOK_BASE` | 空 | 全渠道发布 webhook，缺失走 mock 成功 |
