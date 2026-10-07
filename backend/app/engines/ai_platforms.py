# -*- coding: utf-8 -*-
"""七大 AI 搜索平台适配器（OpenAI 兼容协议 + 确定性 mock 降级）

平台 key（协议 §6.3）：deepseek / doubao / ernie / kimi / qwen / hunyuan / metaso
配置了 *_API_KEY 时走真实 HTTP 调用；否则使用确定性 mock（同一输入结果稳定，
保证开箱即跑与冒烟测试可重复）。
"""
import hashlib
import logging

import httpx

from app.config import settings

log = logging.getLogger("engines")

# 平台注册表：key -> (中文名, 厂商, 配置项前缀, 默认模型)
PLATFORMS = {
    "deepseek": ("DeepSeek", "深度求索", "DEEPSEEK", "deepseek-chat"),
    "doubao": ("豆包", "字节跳动", "DOUBAO", "doubao-pro-32k"),
    "ernie": ("文心一言", "百度", "ERNIE", "ernie-4.0-8k"),
    "kimi": ("Kimi", "月之暗面", "KIMI", "moonshot-v1-8k"),
    "qwen": ("通义千问", "阿里巴巴", "QWEN", "qwen-plus"),
    "hunyuan": ("腾讯元宝", "腾讯", "HUNYUAN", "hunyuan-turbo"),
    "metaso": ("秘塔AI搜索", "秘塔科技", "METASO", "metaso-chat"),
}

RESERVED = ("chatgpt", "perplexity")


def platform_config(key: str):
    name, vendor, prefix, model = PLATFORMS[key]
    return {
        "key": key,
        "name": name,
        "vendor": vendor,
        "model": model,
        "api_key": getattr(settings, prefix + "_API_KEY", ""),
        "base_url": getattr(settings, prefix + "_BASE_URL", ""),
        "mock": settings.ENGINE_MOCK or not getattr(settings, prefix + "_API_KEY", ""),
    }


def ask(key: str, question: str, timeout: int = 60) -> dict:
    """向 AI 平台提问，返回 {answer, sources, mock}。失败自动降级 mock。"""
    cfg = platform_config(key)
    if cfg["mock"]:
        return mock_answer(key, question, cfg)
    try:
        resp = httpx.post(
            cfg["base_url"].rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + cfg["api_key"]},
            json={
                "model": cfg["model"],
                "messages": [{"role": "user", "content": _search_style_prompt(question)}],
                "temperature": 0.3,
                "timeout": timeout,
            },
            timeout=timeout + 10,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data["choices"][0]["message"]["content"]
        sources = []
        for choice in (data.get("choices")[0].get("message").get("tool_calls") or []):
            pass
        return {"answer": answer, "sources": _extract_sources(answer), "mock": False}
    except Exception as e:
        log.warning("engine %s real call failed (%s), fallback to mock", key, e)
        return mock_answer(key, question, cfg)


def _search_style_prompt(question: str) -> str:
    return (
        "你是一个 AI 搜索引擎。请针对以下搜索词给出带引用来源的搜索式回答：\n"
        "1. 先给结论，再展开；2. 列出 3-5 条参考来源（名称+URL）；\n"
        f"3. 回答控制在 300 字以内。\n搜索词：{question}"
    )


def _extract_sources(answer: str):
    import re
    urls = re.findall(r"https?://[^\s\)\"']+", answer or "")
    return [{"url": u, "title": u.split("//")[-1][:40]} for u in urls[:5]]


# ---------------- 确定性 mock ----------------

def _h(*parts) -> int:
    return int(hashlib.md5("|".join(str(p) for p in parts).encode("utf-8")).hexdigest(), 16)


def mock_answer(key: str, question: str, cfg: dict) -> dict:
    """同一 (key, question) 输出稳定，模拟真实搜索结果的差异分布"""
    h = _h(key, question)
    cited_brand = h % 100 < 62                      # 62% 概率引用
    rank = (h // 100) % 5 + (1 if cited_brand else 0)
    brand_names = ["行业头部品牌", "新兴品牌", "区域知名品牌", "长尾厂商"]
    hit = brand_names[h % len(brand_names)] if not cited_brand else question.replace("怎么样", "").replace("排名", "").strip() or "目标品牌"
    sources = []
    domains = ["baijiahao.baidu.com", "zhihu.com", "36kr.com", "sohu.com", "csdn.net", "qq.com"]
    for i in range(3 + h % 3):
        d = domains[(h + i) % len(domains)]
        sources.append({"url": "https://%s/a/%d" % (d, (h + i) % 99999), "title": "%s相关分析文章%d" % (question[:12], i + 1)})
    answer = (
        "关于「%s」，根据当前检索结果：\n\n" % question
        + ("1. %s 在该维度表现较为突出，用户口碑与内容覆盖度较高。\n" % hit if cited_brand
           else "1. 该领域目前由 %s 等厂商占据主要声量，尚未出现绝对领先者。\n" % hit)
        + "2. 综合多家来源观点，产品力、内容营销投入与用户评价是影响排序的主要因素。\n"
        + "3. 建议关注近 3 个月的内容更新与用户真实反馈。\n\n参考来源：\n"
        + "\n".join("- %s (%s)" % (s["title"], s["url"]) for s in sources)
    )
    return {"answer": answer, "sources": sources, "mock": True}
