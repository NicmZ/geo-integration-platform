# -*- coding: utf-8 -*-
"""完整 ORM 模型（31 表，与 sql/schema.sql 一一对应）"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, Integer, String, Text, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from app.database import Base


def uid() -> str:
    return str(uuid.uuid4())


def now():
    return datetime.utcnow()


# ============ 用户与账号 ============

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), default="")
    phone = Column(String(20), default="")
    password_hash = Column(String(256), nullable=False)
    is_vip = Column(Boolean, default=False)
    vip_expires_at = Column(DateTime, nullable=True)
    balance = Column(Float, default=0.0)          # 充值余额（元）
    local_balance = Column(Float, default=0.0)    # 合作方池余额（镜像 balance，协议兼容字段）
    geo_token = Column(String(80), default="", index=True)  # sk- 接入码
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    company_profile = relationship("CompanyProfile", back_populates="user", uselist=False)


class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    company_name = Column(String(128), default="")
    industry = Column(String(64), default="")
    website = Column(String(256), default="")
    contact = Column(String(64), default="")
    logo = Column(String(512), default="")
    description = Column(Text, default="")
    updated_at = Column(DateTime, default=now, onupdate=now)

    user = relationship("User", back_populates="company_profile")


class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    brand_type = Column(String(16), default="main")   # main | sub | competitor
    description = Column(Text, default="")
    main_brand_id = Column(String(64), default="")    # 平台侧品牌 ID 缓存（本地全量实现时留空）
    created_at = Column(DateTime, default=now)

    documents = relationship("BrandDocument", back_populates="brand", cascade="all,delete-orphan")


class BrandDocument(Base):
    __tablename__ = "brand_documents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False, index=True)
    filename = Column(String(256), default="")
    doc_type = Column(String(32), default="text")     # text | pdf | url
    content = Column(Text, default="")
    status = Column(String(16), default="ready")      # ready | parsing | failed
    created_at = Column(DateTime, default=now)

    brand = relationship("Brand", back_populates="documents")


class KeywordSetting(Base):
    __tablename__ = "keyword_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), index=True)
    settings = Column(Text, default="{}")             # JSON：监控引擎/频率/告警阈值等
    updated_at = Column(DateTime, default=now, onupdate=now)


# ============ 关键词与 GEO 评估 ============

class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True, index=True)
    keyword = Column(String(256), nullable=False)
    category = Column(String(64), default="")
    priority = Column(Integer, default=0)
    status = Column(String(16), default="pending")    # pending | checking | checked | failed
    geo_score = Column(Float, default=0.0)            # 最近一次综合 GEO 得分
    last_check_id = Column(String(64), default="")
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class KeywordTag(Base):
    __tablename__ = "keyword_tags"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(64), nullable=False)
    color = Column(String(16), default="#409EFF")
    created_at = Column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_tag_user_name"),)


class KeywordTagMap(Base):
    __tablename__ = "keyword_tag_maps"
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("keyword_tags.id"), nullable=False, index=True)
    __table_args__ = (UniqueConstraint("keyword_id", "tag_id", name="uq_kw_tag"),)


class CheckTask(Base):
    __tablename__ = "check_tasks"
    id = Column(String(64), primary_key=True, default=uid)   # uuid，对前端即 task_id
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=True, index=True)
    batch_no = Column(String(64), default="", index=True)
    engines = Column(Text, default="[]")              # JSON: ["deepseek", ...]
    status = Column(String(16), default="PENDING")    # 同调度器状态机
    progress = Column(Integer, default=0)
    error = Column(Text, default="")
    scheduler_task_id = Column(String(64), default="", index=True)
    created_at = Column(DateTime, default=now)
    finished_at = Column(DateTime, nullable=True)

    results = relationship("CheckResult", back_populates="task", cascade="all,delete-orphan")


class CheckResult(Base):
    __tablename__ = "check_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), ForeignKey("check_tasks.id"), nullable=False, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=False, index=True)
    engine = Column(String(32), nullable=False, index=True)
    cited = Column(Boolean, default=False)            # 品牌/关键词是否被 AI 引用
    rank = Column(Integer, default=0)                 # 引用位置（0=未引用）
    mention_rate = Column(Float, default=0.0)         # 提及率 0-1
    sentiment = Column(String(16), default="neutral") # positive | neutral | negative
    geo_score = Column(Float, default=0.0)            # 单引擎得分 0-100
    answer = Column(Text, default="")                 # AI 回答快照
    sources = Column(Text, default="[]")              # JSON 引用来源
    checked_at = Column(DateTime, default=now)

    task = relationship("CheckTask", back_populates="results")


class ComplianceReport(Base):
    __tablename__ = "compliance_reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=True)
    score = Column(Float, default=0.0)
    risk_level = Column(String(16), default="low")    # low | medium | high
    summary = Column(Text, default="")
    locked = Column(Boolean, default=True)            # 详情需付费解锁（COMPLIANCE_UNLOCK）
    scheduler_task_id = Column(String(64), default="", index=True)
    created_at = Column(DateTime, default=now)


class ComplianceFinding(Base):
    __tablename__ = "compliance_findings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey("compliance_reports.id"), nullable=False, index=True)
    rule_code = Column(String(32), default="")
    category = Column(String(32), default="")         # 广告法 | 宣称合规 | 引用来源 | 敏感词 | 事实性
    severity = Column(String(16), default="low")      # low | medium | high
    fragment = Column(Text, default="")
    suggestion = Column(Text, default="")


class Engine(Base):
    """七大 AI 搜索平台注册表"""
    __tablename__ = "engines"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(32), unique=True, nullable=False)
    name = Column(String(64), default="")
    vendor = Column(String(64), default="")
    enabled = Column(Boolean, default=True)
    weight = Column(Float, default=1.0)
    order = Column(Integer, default=0)
    config = Column(Text, default="{}")


class AiSearchResult(Base):
    __tablename__ = "ai_search_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=False, index=True)
    engine = Column(String(32), nullable=False, index=True)
    question = Column(Text, default="")
    answer = Column(Text, default="")
    sources = Column(Text, default="[]")
    rank = Column(Integer, default=0)
    cited = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)


# ============ 知识库 ============

class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False, index=True)
    title = Column(String(256), default="")
    content = Column(Text, default="")
    status = Column(String(16), default="draft")      # draft | published
    version = Column(Integer, default=1)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class KbVersion(Base):
    __tablename__ = "kb_versions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    version_no = Column(Integer, default=1)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=now)


class KbTask(Base):
    __tablename__ = "kb_tasks"
    id = Column(String(64), primary_key=True, default=uid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False, index=True)
    task_type = Column(String(32), default="build")   # build | restore
    status = Column(String(16), default="PENDING")
    progress = Column(Integer, default=0)
    result = Column(Text, default="{}")
    error = Column(Text, default="")
    scheduler_task_id = Column(String(64), default="", index=True)
    created_at = Column(DateTime, default=now)
    finished_at = Column(DateTime, nullable=True)


# ============ 内容与发布 ============

class Content(Base):
    __tablename__ = "contents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    title = Column(String(256), default="")
    keywords = Column(Text, default="[]")             # JSON
    category = Column(String(64), default="")
    length = Column(Integer, default=1200)            # 目标字数
    summary = Column(Text, default="")
    body = Column(Text, default="")
    engine_key = Column(String(32), default="deepseek")
    special_requirements = Column(Text, default="")
    status = Column(String(16), default="generating") # generating | draft | ready | failed
    cover_url = Column(String(512), default="")
    images = Column(Text, default="[]")
    cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class MediaPlatform(Base):
    """11 个自媒体发布平台注册表"""
    __tablename__ = "media_platforms"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(32), unique=True, nullable=False)
    name = Column(String(64), default="")
    icon = Column(String(256), default="")
    enabled = Column(Boolean, default=True)
    supports_images = Column(Boolean, default=True)
    api_type = Column(String(32), default="extension")  # extension | official | manual
    order = Column(Integer, default=0)


class MediaChannel(Base):
    """媒体库渠道（媒体采购，2 万+渠道的本地样例表）"""
    __tablename__ = "media_channels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_key = Column(String(32), default="", index=True)
    channel_name = Column(String(128), default="")
    category = Column(String(32), default="")          # C 综合门户 / V 垂直 / X 新媒体…
    account = Column(String(128), default="")
    followers = Column(Integer, default=0)
    price = Column(Float, default=0.0)                 # 单次刊例价（元）
    status = Column(String(16), default="active")
    channel_url = Column(String(512), default="")


class PublishTask(Base):
    __tablename__ = "publish_tasks"
    id = Column(String(64), primary_key=True, default=uid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False, index=True)
    platform_key = Column(String(32), nullable=False, index=True)
    account_id = Column(Integer, nullable=True)
    status = Column(String(16), default="pending")    # pending | publishing | success | failed | cancelled
    cost = Column(Float, default=0.0)
    publish_url = Column(String(512), default="")
    error = Column(Text, default="")
    scheduled_at = Column(DateTime, nullable=True)
    scheduler_task_id = Column(String(64), default="", index=True)
    created_at = Column(DateTime, default=now)
    finished_at = Column(DateTime, nullable=True)


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    platform_key = Column(String(32), nullable=False)
    account_name = Column(String(128), default="")
    avatar = Column(String(512), default="")
    cookie_status = Column(String(16), default="valid")   # valid | expired | none
    is_auto_mode = Column(Boolean, default=False)
    last_heartbeat = Column(DateTime, nullable=True)
    enabled = Column(Boolean, default=True)


class SocialPublishTask(Base):
    """浏览器插件采集通道的发布任务（extension_monitor / social_publisher）"""
    __tablename__ = "social_publish_tasks"
    id = Column(String(64), primary_key=True, default=uid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False)
    platform_key = Column(String(32), nullable=False)
    account_id = Column(Integer, nullable=True)
    status = Column(String(16), default="pending")
    result_url = Column(String(512), default="")
    created_at = Column(DateTime, default=now)


# ============ 计费与订单 ============

class RetailPriceConfig(Base):
    __tablename__ = "retail_price_config"
    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(32), unique=True, nullable=False)
    price_mode = Column(String(16), default="fixed")   # fixed | multiplier
    price_value = Column(Float, default=0.0)           # fixed=元；multiplier=系数
    updated_at = Column(DateTime, default=now, onupdate=now)


class LocalConsumptionRecord(Base):
    __tablename__ = "local_consumption_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(String(32), unique=True, nullable=False)  # GP00000001
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action_type = Column(String(32), default="")
    record_type = Column(String(32), default="consume")  # consume | recharge | refund | gift
    amount = Column(Float, default=0.0)
    balance_after = Column(Float, default=0.0)
    status = Column(String(16), default="success")
    description = Column(String(256), default="")
    ref_id = Column(String(64), default="")
    created_at = Column(DateTime, default=now)


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String(64), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_type = Column(String(32), default="monthly")  # monthly | quarterly | yearly | credits_100
    payment_method = Column(String(32), default="alipay")
    amount = Column(Float, default=0.0)
    status = Column(String(16), default="pending")     # pending | paid | failed | refunded
    credits = Column(Float, default=0.0)               # 到账余额（元）
    paid_at = Column(DateTime, nullable=True)
    raw = Column(Text, default="{}")
    created_at = Column(DateTime, default=now)


# ============ 工单 ============

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticket_no = Column(String(32), unique=True, default="")
    title = Column(String(256), default="")
    content = Column(Text, default="")
    category = Column(String(32), default="other")
    priority = Column(String(16), default="normal")
    status = Column(String(16), default="open")        # open | processing | responded | closed
    ai_analysis = Column(Text, default="{}")
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class TicketResponse(Base):
    __tablename__ = "ticket_responses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    responder_id = Column(Integer, nullable=True)
    responder_type = Column(String(16), default="admin")  # user | admin | ai
    content = Column(Text, default="")
    created_at = Column(DateTime, default=now)


# ============ CPU 调度器 ============

class SchedulerTask(Base):
    """csg/v1 任务信封的持久化 + Celery 兼容状态机"""
    __tablename__ = "scheduler_tasks"
    id = Column(String(64), primary_key=True, default=uid)   # uuid
    task_type = Column(String(32), nullable=False, index=True)
    status = Column(String(16), default="PENDING", index=True)  # PENDING/STARTED/PROGRESS/SUCCESS/FAILURE
    priority = Column(Integer, default=5)
    cpu_cores = Column(Integer, default=1)
    timeout_s = Column(Integer, default=600)
    max_retry = Column(Integer, default=2)
    attempts = Column(Integer, default=0)
    payload = Column(Text, default="{}")
    result = Column(Text, default="{}")
    progress = Column(Integer, default=0)
    error = Column(Text, default="")
    tenant = Column(String(64), default="", index=True)
    executor = Column(String(16), default="local")     # local | slurm
    slurm_job_id = Column(String(32), default="")
    created_at = Column(DateTime, default=now, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class TaskUsage(Base):
    """任务计量（cpu_seconds）"""
    __tablename__ = "task_usage"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), index=True)
    tenant = Column(String(64), default="", index=True)
    task_type = Column(String(32), default="")
    cores = Column(Integer, default=1)
    cpu_seconds = Column(Float, default=0.0)
    queued_s = Column(Float, default=0.0)
    run_s = Column(Float, default=0.0)
    finished_at = Column(DateTime, default=now)


class ComputeNode(Base):
    """计算节点注册表（本地节点 / 超算分区）"""
    __tablename__ = "compute_nodes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String(128), default="")
    partition = Column(String(64), default="local")
    state = Column(String(32), default="idle")         # idle | running | drained
    cores_total = Column(Integer, default=0)
    cores_used = Column(Integer, default=0)
    mem_gb = Column(Integer, default=0)
    updated_at = Column(DateTime, default=now, onupdate=now)


# 常用索引
Index("ix_check_results_kw_engine", CheckResult.keyword_id, CheckResult.engine)
Index("ix_publish_tasks_user_status", PublishTask.user_id, PublishTask.status)
