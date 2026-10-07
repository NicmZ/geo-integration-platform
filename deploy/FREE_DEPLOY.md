# 免费服务器部署指南（客户可访问的 Demo）

> 目标：零成本让客户用手机 / PC 浏览器打开线上 Demo。
>
> 方案：**前端 Cloudflare Pages（免费、国内可达）+ 后端 Render Free（750 小时/月）**
>
> 全程不需要自己的服务器，只需要一个 GitHub 仓库和两个免费账号。

---

## 一、方案总览

| 组件 | 平台 | 免费额度 | 说明 |
|------|------|----------|------|
| 前端（Vue3 静态站） | Cloudflare Pages | 无限带宽、500 次/月构建 | `xxx.pages.dev` 域名，国内一般可直接访问 |
| 后端（FastAPI） | Render Free Web Service | 750 小时/月 | `xxx.onrender.com` 域名，15 分钟无流量休眠 |
| 数据库 | SQLite（内置） | — | 免费实例无持久盘，重启后数据重置（Demo 可接受） |

架构：

```
客户浏览器（手机/PC）
        │
        ▼
前端  https://geo-demo.pages.dev        ← Cloudflare Pages
        │  axios 请求 VITE_API_BASE
        ▼
后端  https://geo-demo-api.onrender.com ← Render Free（Docker 运行）
```

平台已支持跨域分离部署（CORS 全局开放、`VITE_API_BASE` 环境变量、Docker `PORT` 自适应），无需改代码。

---

## 二、准备：代码推到 GitHub

```bash
cd GEO_Integration_Platform
git init
git add .
git commit -m "GEO platform demo"
git remote add origin https://github.com/<你的用户名>/geo-integration-platform.git
git push -u origin main
```

> 提示：确保 `.gitignore` 包含 `node_modules/`、`dist/`、`*.db`、`__pycache__/`。

---

## 三、部署后端（Render Free）

1. 注册/登录 [render.com](https://render.com)（可用 GitHub 账号直接登录）。
2. 控制台点 **New → Web Service**，选择刚推送的 GitHub 仓库。
3. 配置：
   - **Name**：`geo-demo-api`（即最终域名 `geo-demo-api.onrender.com`）
   - **Region**：Singapore（离国内最近）
   - **Runtime**：`Docker`
   - **Root Directory**：`backend`（Dockerfile 在 backend/ 下）
   - **Instance Type**：`Free`
4. **Environment Variables** 添加：

   | Key | Value | 说明 |
   |-----|-------|------|
   | `EXECUTOR` | `local` | 本地线程池 CPU 调度 |
   | `CAPTCHA_ENABLED` | `false` | Demo 简化登录（可选） |
   | `PAYMENT_SANDBOX` | `true` | 沙箱支付 |
   | `SECRET_KEY` | `改成一串随机字符` | token 签名密钥 |
   | `ENGINE_MOCK` | `false` | 有 API Key 可填 false，否则 true |
   | `DEEPSEEK_API_KEY` 等 | 选填 | 7 个 AI 平台任一，缺省走确定性 mock |

   > `PORT` 不用填 —— Dockerfile 已写 `--port ${PORT:-8001}`，Render 自动注入。
5. 点 **Create Web Service**，等构建完成（首次约 3-5 分钟）。
6. 验证：浏览器打开 `https://geo-demo-api.onrender.com/api/users/captcha/`，返回 JSON 即成功。

**Free 档注意事项：**
- 15 分钟无流量自动休眠，下次访问需约 30-60 秒冷启动（前端请求超时为 60s，能扛住一次唤醒）。
- 免费实例无持久磁盘：SQLite 数据在重新部署/重启后重置。若想保数据，可在 Render 上再开一个免费 PostgreSQL 实例，把 `DATABASE_URL` 指过去（免费 PG 会在 30 天后过期，需手动续期）。

---

## 四、部署前端（Cloudflare Pages）

1. 注册/登录 [pages.cloudflare.com](https://pages.cloudflare.com)（GitHub 登录即可）。
2. **Create a project → Connect to Git**，选择仓库。
3. 构建配置：
   - **Project name**：`geo-demo`（最终域名 `geo-demo.pages.dev`）
   - **Framework preset**：`Vite`（没有就选 None 手填）
   - **Root directory**：`frontend`
   - **Build command**：`npm install --ignore-scripts && npm run build`
   - **Build output directory**：`dist`
4. **Environment variables**（Production + Preview 都加）：

   | Key | Value |
   |-----|-------|
   | `VITE_API_BASE` | `https://geo-demo-api.onrender.com` |

   > 注意末尾**不要**带 `/`。
5. 点 **Save and Deploy**，1-2 分钟后得到 `https://geo-demo.pages.dev`。

SPA 路由回退已内置：`frontend/public/_redirects`（`/* /index.html 200`）会随构建进入 dist，刷新子页面不会 404。

---

## 五、验收清单

- [ ] PC 浏览器打开 `https://geo-demo.pages.dev`，登录进入看板
- [ ] 手机浏览器打开同一地址：侧栏变为汉堡抽屉菜单，统计卡 2 列排布，图表随屏幕缩放
- [ ] 注册新账号 → 到账 ¥100 体验金（`REGISTER_GIFT_BALANCE`）
- [ ] 新建 GEO 评估任务 → 轮询到 SUCCESS，看板分数更新
- [ ] 合规检测 / 内容生成 / 一键发布 / 充值（沙箱）全流程可走通

---

## 六、备选方案

| 方案 | 前端 | 后端 | 适用场景 |
|------|------|------|----------|
| **主推：CF Pages + Render** | Cloudflare Pages | Render Free | 国内可达、配置简单 |
| Vercel + Render | Vercel（`vercel.com`） | Render Free | Vercel 免费额度更足，但国内访问不稳定 |
| 单容器：Hugging Face Spaces | 同容器内 FastAPI 挂载 dist 静态文件 | 同左 | 只想维护一个服务；缺点：`*.hf.space` 国内基本不可达 |
| Koyeb / Zeabur | 同类免费容器平台 | 同类 | Render 排队时的替代 |

单容器（HF Spaces / Zeabur）挂载静态文件的最小改法：在 `backend/app/main.py` 的路由注册后加

```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

并把 `frontend/dist` 拷贝为镜像内 `static/`，这样一个域名同时服务前后端，无需 CORS/VITE_API_BASE。

---

## 七、体验建议（发给客户）

```
Demo 地址：https://geo-demo.pages.dev
建议用手机或电脑浏览器直接打开（响应式适配）。
免费服务器冷启动较慢：若首次打开约 1 分钟无响应，属正常唤醒，刷新即可。
```
