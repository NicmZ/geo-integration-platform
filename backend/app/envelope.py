# -*- coding: utf-8 -*-
"""统一响应信封与 DRF 分页助手（协议 100% 兼容）"""
from urllib.parse import urlencode

from fastapi import Request


def ok(data=None, msg=""):
    return {"code": 0, "msg": msg, "data": data}


def err(msg="操作失败", code=1, data=None, status_code=200):
    return {"__status__": status_code, "body": {"code": code, "msg": msg, "data": data}}


def busy():
    """涉及合作方/余额池的内部错误统一脱敏（协议 §2）"""
    return {"__status__": 503, "body": {"code": 1, "msg": "当前服务繁忙，请稍后再试或联系客服", "data": None}}


def paginate(items, page: int, page_size: int, request: Request = None, path: str = None, extra_query: dict = None):
    """DRF 风格分页：{count, next, previous, results}"""
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    results = items[start:end]

    def _url(p):
        if request is None or path is None:
            return None
        q = dict(request.query_params)
        if extra_query:
            q.update(extra_query)
        q["page"] = p
        q["page_size"] = page_size
        return str(request.base_url).rstrip("/") + path + "?" + urlencode(q)

    return {
        "count": total,
        "next": _url(page + 1) if end < total else None,
        "previous": _url(page - 1) if page > 1 else None,
        "results": results,
    }
