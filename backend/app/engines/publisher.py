# -*- coding: utf-8 -*-
"""全渠道发布适配器：11 个自媒体平台（extension 插件采集 / official API / manual），webhook 可配"""
import hashlib
import logging

import httpx

from app.config import settings

log = logging.getLogger("publisher")

MEDIA_PLATFORMS = [
    # key, 名称, 是否支持图文, api_type
    ("xiaohongshu", "小红书", True, "extension"),
    ("wechat", "微信公众号", True, "official"),
    ("toutiao", "今日头条", True, "official"),
    ("zhihu", "知乎", True, "extension"),
    ("csdn", "CSDN", True, "official"),
    ("baijiahao", "百家号", True, "extension"),
    ("juejin", "掘金", True, "official"),
    ("sohu", "搜狐号", True, "extension"),
    ("xueqiu", "雪球", False, "extension"),
    ("cnblogs", "博客园", True, "official"),
    ("cto51", "51CTO", True, "official"),
]


def publish_one(platform_key: str, title: str, body: str, cover_url: str = "", account: str = "") -> dict:
    """单平台发布。配置 PUBLISH_WEBHOOK_BASE 时走真实 webhook，否则确定性 mock 成功。

    webhook 约定：POST {base}/{platform_key}  body={title,body,cover_url,account}
    响应 {"ok": true, "url": "..."} 视为成功。
    """
    base = settings.PUBLISH_WEBHOOK_BASE
    if base:
        try:
            resp = httpx.post(
                base.rstrip("/") + "/" + platform_key,
                json={"title": title, "body": body[:20000], "cover_url": cover_url, "account": account},
                timeout=30,
            )
            data = resp.json()
            if data.get("ok"):
                return {"success": True, "url": data.get("url", "")}
            return {"success": False, "error": data.get("error", "webhook 返回失败")}
        except Exception as e:
            log.warning("publish webhook %s failed: %s", platform_key, e)
            return {"success": False, "error": str(e)}
    # mock：确定性生成稿件链接
    h = hashlib.md5((platform_key + title).encode("utf-8")).hexdigest()[:10]
    url = "https://%s.example-publish.cn/%s/%s" % (platform_key, account or "official", h)
    return {"success": True, "url": url, "mock": True}
