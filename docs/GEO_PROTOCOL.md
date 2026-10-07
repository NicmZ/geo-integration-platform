# 超算GEO 原生协议参考（GEO_PROTOCOL v1）

> 本文档整理自超算GEO 开源前后端源码（`DeepSeekGEO/deepseek-geo` 前端、`DeepSeekGEO/geo-partner-backend` 后端），
> 是本平台复刻实现的接口契约基准。前后端所有路由、字段命名均与该协议保持一致，可直接对接原版前端或 DeepseekConnector 插件。

---

## 1. 总体架构

```
浏览器前端 (Vue Admin, :9527)
      │  Authorization: Bearer <本地JWT>
      ▼
接入后端 (FastAPI, :8001)  ── 本地：用户/余额/计费/工单/品牌资料
      │                        ── 计算任务：提交至 CPU 调度器
      ▼
CPU 算力调度器 (csg/v1 协议) ── 本地线程池执行器（单机）
      │                        ── Slurm 适配器（超算集群 sbatch/srun）
      ▼
GEO 引擎集群（7 大 AI 平台适配器 + 合规引擎 + 内容引擎 + 发布适配器）
```

- **前端**：vue-element-admin（Vue 2.6 + Element-UI 2.15 + ECharts 4），dev 端口 `9527`，API 前缀 `/api`。
- **后端**：FastAPI + SQLAlchemy 2.0 + pydantic-settings + python-jose + passlib(sha256_crypt) + sqladmin + httpx，端口 `8001`。
- **数据库**：默认 SQLite，生产 PostgreSQL/MySQL（`DATABASE_URL`）。
- **任务**：原生平台使用 Celery（任务状态查询 `/celery_tasks/task-status/{task_id}/`）；本复刻以自研 CPU 调度器兼容该查询协议。

## 2. 统一响应信封

```json
{ "code": 0, "msg": "", "data": { } }
```

- `code=0` 成功；非 0 失败，`msg` 为用户可读信息。
- 分页列表：`data = { "count": 100, "next": null, "previous": null, "results": [...] }`（DRF 风格）。
- 错误状态码：400/402/403 时后端对涉及「合作方/余额池/partner」的内部错误统一脱敏为
  `{"code":1,"msg":"当前服务繁忙，请稍后再试或联系客服","data":null}`。

## 3. 认证体系

| 层级 | 凭证 | 说明 |
|---|---|---|
| 本地用户 | JWT（HS256，`sub=user_id`，7 天有效） | 请求头 `Authorization: Bearer <jwt>`（兼容 `Token <jwt>` 前缀） |
| GEO 平台接入码 | `sk-` 开头 token | 后端经 Partner 协议为每个本地用户申请，存储于 `users.geo_token` |
| 合作方 | `pk-` 开头 Partner Key | 只存在于服务端 `X-Partner-Key` 头，永不下发浏览器 |

**Partner 协议（申请接入码）**

```
POST {GEO_API_BASE}/partners/issue-user-token/
Headers: X-Partner-Key: pk-xxx
Body:    {"third_party_user_id": "<本地用户唯一标识>"}
Resp:    {"data": {"token": "sk-..."}}        # 兼容顶层 {"token": "sk-..."}
```

- 用户首次调用 GEO 能力时自动申请；`POST /api/token/reset-token/` 强制重置，旧码失效。
- 上游 401 时自动重新申请 token 并重放一次。

## 4. 计费协议（action_type 与零售定价）

上游响应 `data.cost` 或 `data.total_cost` 表示**平台标准价**；接入后端按零售配置换算后扣减本地余额，
并**改写响应**：`cost / total_cost / balance_after / new_balance` 覆盖为本地值，删除
`old_balance / partner_cost / is_partner`（隐藏进货价）。余额不足则不扣费直接透传。

扣款为单条原子 UPDATE：`UPDATE users SET local_balance=local_balance-:cost WHERE id=:id AND local_balance>=:cost`。

| action_type | 功能 | 计价映射路径前缀 | 默认零售价 |
|---|---|---|---|
| KEYWORD_CHECK | 关键词检测 | `keywords/` | fixed ¥10 |
| CONTENT_GENERATE | 内容生成 | `content/generate` | multiplier ×1.0 |
| CONTENT_PUBLISH | 内容发布 | `content/publish-tasks/bulk-publish`、`report_info/publish` | multiplier ×1.0 |
| BRAND_KNOWLEDGE | 品牌知识库 | `account_info/brand` | fixed ¥10 |
| COMPLIANCE_UNLOCK | 检测结果解锁 | `keywords/compliance`、`keywords/unlock` | multiplier ×1.0 |

`retail_price_config.price_mode`：`fixed`（固定元）/ `multiplier`（标准价×系数）。
本地拦截路径（不走上游）：`users/`、`account_info/balance`、`account_info/records`、`payment/`、`feedback/`。

## 5. 品牌 ID 翻译协议（本地 brand_id ↔ 平台 brand_id）

本地 `brands.main_brand_id` 缓存平台侧 ID；为空时执行同步：

1. `PUT {GEO_API_BASE}/account_info/company-profile/`（body `{"company_name": ...}`）
2. `POST {GEO_API_BASE}/account_info/brands/`（品牌全量字段）→ `data.id`
3. 失败（如同名品牌已存在）→ `GET /account_info/brands/` 在 `data.results` 中按 `name` 匹配取 `id`
4. 写回 `main_brand_id`

需翻译的场景：

- 路径 `account_info/knowledge-base/brand/{local_id}/...` → 重写为平台 ID
- `POST account_info/knowledge-base/create-task/` body `{"brand": local_id}` → 平台 ID
- `POST content/content/generate-content/` body `{"brand": [local_id...]}` → [平台 ID...]
- `PUT/PATCH content/content/{id}` body 剥离 `created_by` 字段

## 6. 全量 API 路径清单（本平台 100% 本地实现）

### 6.1 用户与账号 `/api/users/`
`GET captcha/` · `POST register/` · `POST login/` · `POST logout/` · `GET profile/` ·
`POST sms_code/` · `POST check_phone/` · `GET my-token/` · `POST my-token/`（重置）

- 登录响应：`data={token, user:{id,username,email,is_vip}}`
- profile：`data={id,username,email,is_vip,vip_expires_at,balance,local_balance,company,company_profile,brands:[{id,name,brand_type}]}`
- captcha：`data={captcha_image(base64), captcha_token, require_case_sensitive:false}`（4 位，去 O/0/I/1，TTL 5min）
- my-token：`data={token:"sk-...", created_at}`

### 6.2 关键词/GEO 评估 `/api/keywords/`
`GET keyword-library/` · `GET|POST tags/` · `DELETE tags/{id}/` · `POST bulk-import/` ·
`GET|PATCH|DELETE keywords/{id}/` · `POST keywords/{id}/check/` · `POST keywords/{id}/recheck/` ·
`GET keywords/{id}/checks/` · `POST checks/`（批量提交 `{keywords:[], engines:[]}`）·
`GET checks/{check_id}/status/` · `GET checks/{check_id}/` · `GET dashboard/` ·
`GET dashboard/trend/?range=7days|30days` · `GET dashboard/recent/?limit=` ·
`GET dashboard/best-practices/?limit=` · `GET keyword-center/` ·
`POST batch-operations/` · `GET export/`（blob）· `POST compliance/` · `POST unlock/`

### 6.3 AI 引擎与报告
`GET result/engines/` · `GET result/engines/configs/` · `GET result/engines/choices/` ·
`GET report_info/ai-search-results/` · `POST report_info/publish`（计费 CONTENT_PUBLISH）

**七大 AI 平台 key**：`deepseek`、`doubao`（豆包）、`ernie`（文心一言）、`kimi`、
`qwen`（通义千问）、`hunyuan`（腾讯元宝）、`metaso`（秘塔AI）；`chatgpt`/`perplexity` 预留。

### 6.4 内容中心 `/api/content/`
`GET|POST content/` · `GET|PUT|DELETE content/{id}/` · `POST content/generate-content/` ·
`POST content/upload-image/` · `GET media-platforms/` · `GET|POST publish-tasks/` ·
`GET|DELETE publish-tasks/{id}/` · `POST publish-tasks/{id}/cancel/` · `POST publish-tasks/{id}/retry/` ·
`POST publish-tasks/bulk-publish/`（计费 CONTENT_PUBLISH）· `POST publish-tasks/export/`

- generate-content 请求：`{title, keywords:[], brand:[local_id], cost, length, summary, category, engine_platform_key, special_requirements}`
- publish-tasks 列表中每个 task 含 `cost`，列表返回时统一按零售价改写。

### 6.5 账户信息 `/api/account_info/`
`GET industries/` · `GET|PUT|PATCH company-profile/` · `GET|POST brands/` ·
`GET|PUT|PATCH|DELETE brands/{id}/` · `GET|POST brands/{id}/documents/` · `DELETE brands/{id}/documents/{doc_id}/` ·
`GET|PUT brands/{id}/keyword-settings/` · `GET|POST knowledge-base/` · `GET|PUT|DELETE knowledge-base/{id}/` ·
`GET knowledge-base/brand/{brand_id}/` · `POST knowledge-base/create-task/` ·
`PUT knowledge-base/{id}/publish/` · `GET knowledge-base/{id}/history/` · `POST knowledge-base/{id}/restore/` ·
`GET knowledge-base/check/{brand_id}/` · `GET knowledge-base/brand/{brand_id}/tasks/` ·
`GET knowledge-base/user-tasks/` · `GET default-knowledge-content/` ·
`GET balance` · `GET records` · `GET consumption-records/`（`data={count,next,previous,results}`，
每条含 `record_id:"GP00000001"、record_type、amount、balance_after、status:"success"、description、created_at`）

### 6.6 任务状态（原生 Celery 兼容）
`GET celery_tasks/task-status/{task_id}/` → `data={task_id, status, progress, result}`，
status ∈ `PENDING / STARTED / PROGRESS / SUCCESS / FAILURE`。

### 6.7 计费与支付
`GET account_info/consumption-records/`（见上）· `POST payment/create/`（`{plan_type, payment_method}` → 订单）·
`GET payment/status/{order_no}/` · 支付回调 `POST payment/alipay/notify/`、`POST payment/wechat/notify/`（可选配置）

### 6.8 工单与插件通道
`GET|POST feedback/feedbacks/` · `GET feedback/my-feedbacks/` · `GET|PUT|DELETE feedback/feedbacks/{id}/` ·
`POST feedback/feedbacks/analyze/` · `POST feedback/feedbacks/{id}/respond/` ·
`POST feedback/feedbacks/{id}/close/` · `GET feedback/feedbacks/{id}/responses/`
`GET extension_monitor/publisher-status/` → `data={online,is_auto_mode,last_heartbeat}`
`GET social_publisher/accounts/` · `POST social_publisher/publish/create/`（`{content_ids, target_accounts}`）·
`GET social_publisher/tasks/` · `POST social_publisher/tasks/{id}/retry/` · `POST content_center/save-temp/`
`GET media_db/media/?channel=C`（媒体库，`data={items,total,page,page_size}`，2万+渠道）

## 7. CPU 算力调度协议（csg/v1，本平台扩展）

为在超算环境运行，任务队列层定义 csg/v1 任务信封，业务路由只产出信封，执行器可替换：

```json
{
  "protocol": "csg/v1",
  "task_id": "uuid4",
  "task_type": "keyword_check | compliance_check | content_generate | kb_build | publish_dispatch",
  "priority": 5,
  "cpu_cores": 1,
  "timeout_s": 600,
  "max_retry": 2,
  "payload": { },
  "tenant": "user_id",
  "reply_to": "db"
}
```

- **队列**：Redis ZSET（分数 = priority*1e10 + ts，小者先出）或 DB 表 `scheduler_tasks`（无 Redis 时降级）。
- **状态机**：`PENDING → STARTED → PROGRESS → SUCCESS | FAILURE`，与 Celery 状态查询协议兼容。
- **执行器**：`local`（进程内线程池，CPU 配额 = min(并发数, cpu_cores)）、`slurm`（每任务 `sbatch` 一个 CPU 作业，`--cpus-per-task` 与 `cpu_cores` 对齐，超算登录节点提交、计算节点执行）。
- **计量**：任务结束写 `task_usage`（cpu_seconds），供计费与配额。
- **公平调度**：按租户权重轮询（DRF），防止单用户占满 CPU。

## 8. 数据库表清单

`users` · `company_profiles` · `brands` · `brand_documents` · `keyword_settings` ·
`keywords` · `keyword_tags` · `keyword_tag_maps` · `check_tasks` · `check_results` ·
`compliance_reports` · `compliance_findings` · `engines` · `ai_search_results` ·
`knowledge_bases` · `kb_versions` · `kb_tasks` · `contents` · `media_platforms` ·
`media_channels` · `publish_tasks` · `social_accounts` · `social_publish_tasks` ·
`retail_price_config` · `local_consumption_records` · `orders` · `tickets` · `ticket_responses` ·
`scheduler_tasks` · `task_usage` · `compute_nodes`

完整字段见 `backend/sql/schema.sql`（MySQL 版）与 SQLAlchemy 模型。
