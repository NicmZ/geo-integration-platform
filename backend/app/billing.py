# -*- coding: utf-8 -*-
"""计费：零售定价、原子扣款、消费流水（协议 §4）"""
import threading
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import RetailPriceConfig, LocalConsumptionRecord, User

DEFAULT_PRICES = {
    # action_type: (price_mode, price_value)  —— 见 GEO_PROTOCOL §4
    "KEYWORD_CHECK": ("fixed", 10.0),
    "CONTENT_GENERATE": ("multiplier", 1.0),
    "CONTENT_PUBLISH": ("multiplier", 1.0),
    "BRAND_KNOWLEDGE": ("fixed", 10.0),
    "COMPLIANCE_UNLOCK": ("multiplier", 1.0),
}

_lock = threading.RLock()
_record_seq = {"n": 0}


def ensure_default_prices(db: Session):
    for action_type, (mode, value) in DEFAULT_PRICES.items():
        if not db.query(RetailPriceConfig).filter_by(action_type=action_type).first():
            db.add(RetailPriceConfig(action_type=action_type, price_mode=mode, price_value=value))
    db.commit()


def get_price(db: Session, action_type: str, standard_cost: float = 0.0) -> float:
    """零售价：fixed 取配置值；multiplier 取 标准价×系数（无标准价时退化为配置值×1）"""
    cfg = db.query(RetailPriceConfig).filter_by(action_type=action_type).first()
    if not cfg:
        return standard_cost or 0.0
    if cfg.price_mode == "fixed":
        return float(cfg.price_value)
    base = standard_cost if standard_cost > 0 else float(cfg.price_value)
    return round(base * float(cfg.price_value), 2)


def get_user_balance(db: Session, user_id: int) -> float:
    u = db.query(User).filter_by(id=user_id).first()
    return float(u.balance) if u else 0.0


def _fresh_balance_of(db: Session, user_id: int) -> float:
    """绕过 ORM 身份缓存，直读最新余额"""
    v = db.execute(text("SELECT balance FROM users WHERE id = :id"), {"id": user_id}).scalar()
    return round(float(v or 0.0), 2)


def charge(db: Session, user_id: int, action_type: str, amount: float,
           description: str = "", ref_id: str = "", record_type: str = "consume"):
    """原子扣款：单条 UPDATE 带余额条件（协议 §4）。成功返回 balance_after，失败返回 None"""
    if amount <= 0:
        return _fresh_balance_of(db, user_id)
    with _lock:
        res = db.execute(
            text("UPDATE users SET balance = balance - :c, local_balance = local_balance - :c "
                 "WHERE id = :id AND balance >= :c"),
            {"c": amount, "id": user_id},
        )
        if res.rowcount != 1:
            db.rollback()
            return None
        balance_after = _fresh_balance_of(db, user_id)
        rec = _next_record_id(db)
        db.add(LocalConsumptionRecord(
            record_id=rec, user_id=user_id, action_type=action_type, record_type=record_type,
            amount=round(amount, 2), balance_after=balance_after, status="success",
            description=description or action_type, ref_id=ref_id, created_at=datetime.utcnow(),
        ))
        db.commit()
        return balance_after


def credit(db: Session, user_id: int, amount: float, record_type: str = "recharge",
           description: str = "", ref_id: str = "", action_type: str = "RECHARGE"):
    """入账（充值/赠送/退款），amount>0"""
    with _lock:
        res = db.execute(
            text("UPDATE users SET balance = balance + :c, local_balance = local_balance + :c WHERE id = :id"),
            {"c": amount, "id": user_id},
        )
        if res.rowcount != 1:
            db.rollback()
            return None
        balance_after = _fresh_balance_of(db, user_id)
        rec = _next_record_id(db)
        db.add(LocalConsumptionRecord(
            record_id=rec, user_id=user_id, action_type=action_type, record_type=record_type,
            amount=round(amount, 2), balance_after=balance_after, status="success",
            description=description or record_type, ref_id=ref_id, created_at=datetime.utcnow(),
        ))
        db.commit()
        return balance_after


def _next_record_id(db: Session) -> str:
    """GP00000001 递增（进程锁内调用，SQLite/MySQL 均安全）"""
    with _lock:
        max_id = db.query(LocalConsumptionRecord).count()
        return "GP%08d" % (max_id + 1)


def rewrite_cost_fields(data: dict, cost: float, balance_after: float):
    """改写上游响应：cost/total_cost/balance_after/new_balance 覆盖为本地值，
    删除 old_balance/partner_cost/is_partner（隐藏进货价）—— 本地全量实现时直接构造"""
    if not isinstance(data, dict):
        return data
    data.pop("old_balance", None)
    data.pop("partner_cost", None)
    data.pop("is_partner", None)
    if "cost" in data:
        data["cost"] = cost
    if "total_cost" in data:
        data["total_cost"] = cost
    data["balance_after"] = balance_after
    data["new_balance"] = balance_after
    return data
