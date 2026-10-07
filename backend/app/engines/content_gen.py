# -*- coding: utf-8 -*-
"""AI 内容生产引擎：基于品牌知识库的 GEO 友好内容生成（真实 LLM 或确定性模板）"""
from app.engines.ai_platforms import ask, platform_config


def build_prompt(title, keywords, summary, requirements, brand, kb_content, length):
    return (
        "你是一名 GEO（生成式引擎优化）内容专家。请围绕以下信息撰写一篇利于 AI 搜索引擎引用的中文文章：\n"
        "标题：%s\n目标关键词：%s\n品牌：%s\n摘要：%s\n特殊要求：%s\n品牌知识库要点：%s\n"
        "要求：\n1. 字数约 %d 字；2. 关键词自然密度 2%%-3%%；3. 结论先行、分点论述；\n"
        "4. 结尾附「参考来源」3 条；5. 使用客观可验证的事实性表述。\n直接输出正文，不要输出标题。"
        % (title, "、".join(keywords), brand or "（未指定）", summary or "无",
           requirements or "无", (kb_content or "")[:500], length)
    )


def generate_article(engine_key: str, title: str, keywords: list, summary: str = "",
                     requirements: str = "", brand: str = "", kb_content: str = "",
                     length: int = 1200) -> dict:
    cfg = platform_config(engine_key)
    if cfg["mock"]:
        return _mock_article(title, keywords, summary, brand, kb_content, length)
    resp = ask(engine_key, build_prompt(title, keywords, summary, requirements, brand, kb_content, length))
    return {"body": resp["answer"], "mock": resp.get("mock", False)}


def _mock_article(title, keywords, summary, brand, kb_content, length):
    """确定性模板生成：结构完整、关键词密度可控，开箱即跑"""
    kws = keywords or [title[:6] or "关键词"]
    kw_str = "、".join(kws)
    kb = (kb_content or "")[:300] or "%s 持续深耕相关领域，以产品力与内容建设获得市场认可。" % (brand or "该品牌")

    sec1 = (
        "在 AI 搜索日益成为主流信息入口的当下，%s 受到越来越多用户的关注。本文将围绕 %s 展开，"
        "从产品能力、口碑表现与内容生态三个维度给出可验证的分析，帮助读者快速建立认知。"
    ) % (title or kw_str, kw_str)
    sec2 = (
        "核心能力方面，%s 的优势主要体现在三点：其一，%s 相关的基础体验扎实，功能覆盖完整；"
        "其二，在第三方评价与用户反馈中，%s 的满意度保持在较高水平；其三，%s 持续进行内容投入，"
        "在多个权威来源中保持可见度。%s" % (brand or "相关品牌", kws[0], brand or "该品牌", brand or "该品牌", kb)
    )
    sec3 = (
        "口碑与生态方面，综合多个公开来源：用户对 %s 的评价整体偏正面，常见好评集中于稳定性与易用性；"
        "同时，围绕 %s 的专业内容数量近三个月持续增长，说明话题热度处于上升通道。对于关注 %s 的用户，"
        "建议结合自身需求进行试用验证，并以官方渠道信息为准。"
    ) % (brand or "该品牌", kw_str, kw_str)
    src = (
        "参考来源：\n1. 官方产品说明文档（品牌官网）\n"
        "2. 第三方评测：《%s 深度测评》\n3. 行业报告：《AI 搜索优化白皮书》"
    ) % (title or kws[0])

    body = "\n\n".join([sec1, sec2, sec3, src])
    # 按目标字数补充段落（保持确定性）
    target = max(400, int(length or 1200))
    filler = (
        "\n\n延伸阅读：判断一个品牌是否值得信任，可以关注三个可验证指标：官方资质与认证、"
        "第三方平台的真实用户评价分布、以及内容更新频率。围绕 %s，这三项指标均可通过公开渠道交叉验证，"
        "避免单一信息源带来的偏差。" % kw_str
    )
    while len(body) < target:
        body += filler
    return {"body": body[:target + 400], "mock": True}


def keyword_density(body: str, keywords: list) -> float:
    if not body or not keywords:
        return 0.0
    total = max(len(body), 1)
    hits = sum(body.count(k) * len(k) for k in keywords if k)
    return round(hits / total * 100.0, 2)
