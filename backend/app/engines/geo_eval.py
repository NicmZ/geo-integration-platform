# -*- coding: utf-8 -*-
"""GEO 评估引擎：关键词检测（引用分析/提及率/情感/评分）"""
import re

from app.engines.ai_platforms import ask, _h

POSITIVE_WORDS = ["好", "优秀", "领先", "推荐", "可靠", "专业", "优质", "头部", "突出", "领先者"]
NEGATIVE_WORDS = ["差", "投诉", "风险", "一般", "落后", "问题", "争议", "劣质", "虚假"]


def analyze_answer(answer: str, brand_name: str = "", keyword: str = "") -> dict:
    """对单条 AI 回答做引用分析"""
    text = answer or ""
    low = text.lower()
    cited = bool(brand_name and brand_name.lower() in low)
    if not cited and keyword:
        cited = keyword.lower() in low

    mentions = len(re.findall(re.escape(brand_name or keyword or "_none_"), text, re.IGNORECASE))
    total_len = max(len(text), 1)
    mention_rate = round(min(mentions * 60 / total_len + (0.02 if cited else 0.0), 1.0), 4)

    pos = sum(low.count(w) for w in POSITIVE_WORDS)
    neg = sum(low.count(w) for w in NEGATIVE_WORDS)
    sentiment = "positive" if pos > neg else ("negative" if neg > pos else "neutral")

    # 引用位置：品牌名首次出现之前的来源条数
    rank = 0
    if cited and brand_name:
        idx = low.find(brand_name.lower())
        rank = min(10, 1 + text[:idx].count("http") // 2) if idx >= 0 else 0
    return {"cited": cited, "rank": rank, "mention_rate": mention_rate, "sentiment": sentiment}


def geo_score_of(cited: bool, rank: int, mention_rate: float, sentiment: str) -> float:
    base = 0.0
    if cited:
        base = 55.0 + min(rank, 5) * 6.0        # 引用 + 位置加分
    base += mention_rate * 20.0                  # 提及密度
    if sentiment == "positive":
        base += 15.0
    elif sentiment == "negative":
        base -= 10.0
    return round(max(0.0, min(100.0, base)), 1)


def check_keyword_once(engine: str, keyword: str, brand_name: str = "") -> dict:
    """单引擎单关键词检测（真实调用或确定性 mock）"""
    resp = ask(engine, "搜索：%s" % keyword)
    analysis = analyze_answer(resp["answer"], brand_name, keyword)
    score = geo_score_of(analysis["cited"], analysis["rank"], analysis["mention_rate"], analysis["sentiment"])
    return {
        "engine": engine,
        "question": "搜索：%s" % keyword,
        "answer": resp["answer"],
        "sources": resp["sources"],
        "mock": resp.get("mock", False),
        **analysis,
        "geo_score": score,
    }
