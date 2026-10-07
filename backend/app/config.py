# -*- coding: utf-8 -*-
"""全局配置（pydantic BaseSettings，兼容 pydantic v1 / Python 3.7）"""
import os
from pydantic import BaseSettings


class Settings(BaseSettings):
    # ---- 基础 ----
    APP_NAME: str = "GEO Integration Platform"
    ENV: str = "dev"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    SECRET_KEY: str = "geo-platform-secret-change-me"
    TOKEN_EXPIRE_DAYS: int = 7

    # ---- 数据库：默认 SQLite，超算/生产切 MySQL/PG ----
    # MySQL 示例: mysql+pymysql://geo:geo123@127.0.0.1:3306/geo_platform?charset=utf8mb4
    DATABASE_URL: str = "sqlite:///./geo_platform.db"

    # ---- CPU 调度器 ----
    EXECUTOR: str = "local"            # local | slurm
    CPU_CONCURRENCY: int = 4           # local 线程池并发（CPU 配额）
    TENANT_MAX_CONCURRENT: int = 2     # 单租户最大并发任务（公平调度 DRF）
    REDIS_URL: str = ""                # 空=纯 DB 队列；配置后启用 Redis ZSET 优先队列
    # Slurm（超算模式）
    SLURM_PARTITION: str = "cpu"
    SLURM_ACCOUNT: str = ""
    SLURM_WORKDIR: str = "./slurm_jobs"
    SLURM_PYTHON: str = "python"       # 计算节点 python 解释器

    # ---- 计费 / 支付 ----
    PAYMENT_SANDBOX: bool = True       # 沙箱：创建订单自动确认到账
    REGISTER_GIFT_BALANCE: float = 100.0  # 注册赠送体验金（元）
    CAPTCHA_ENABLED: bool = True       # false 时注册/登录跳过图形验证码（仅测试环境）

    # ---- Partner 兼容层（本平台可被当作上游） ----
    PARTNER_KEY: str = "pk-geo-local-partner"

    # ---- AI 引擎适配器（任一缺失则该平台走确定性 mock） ----
    ENGINE_MOCK: bool = False          # True=强制全部 mock
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DOUBAO_API_KEY: str = ""
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    ERNIE_API_KEY: str = ""            # 文心一言（OpenAI 兼容网关）
    ERNIE_BASE_URL: str = "https://aip.baidubce.com/v1"
    KIMI_API_KEY: str = ""
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    HUNYUAN_API_KEY: str = ""
    HUNYUAN_BASE_URL: str = "https://api.hunyuan.cloud.tencent.com/v1"
    METASO_API_KEY: str = ""
    METASO_BASE_URL: str = "https://api.metaso.cn/v1"

    # ---- 全渠道发布 webhook（可选；缺省走 mock 成功） ----
    PUBLISH_WEBHOOK_BASE: str = ""

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        env_file_encoding = "utf-8"


settings = Settings()
