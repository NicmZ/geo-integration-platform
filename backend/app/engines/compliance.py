# -*- coding: utf-8 -*-
"""合规检测引擎：广告法极限词、宣称合规、引用来源、敏感词、事实性风险"""
import json
import re

# 规则库（rule_code, 类别, 严重度, 正则/词表, 建议）
RULES = [
    ("AD_EXTREME_01", "广告法", "high", r"(国家级|世界级|最高级|最佳|最好|最优秀|最强|最先进|全网最|销量第一|NO\.1|排名第一)",
     "《广告法》第九条禁用绝对化用语，请改为「行业领先」「表现优异」等描述性用语。"),
    ("AD_EXTREME_02", "广告法", "medium", r"(顶级|极品|万能|独家|首款|首创|独一无二|史无前例)",
     "极限化表述存在广告违法风险，建议补充依据或改为客观描述。"),
    ("AD_MEDICAL_01", "宣称合规", "high", r"(治愈|根治|药到病除|有效率\d+%|临床验证|无副作用|包治)",
     "医疗/功效宣称需相应资质，普通商品宣传禁止使用治疗类用语。"),
    ("AD_FINANCE_01", "宣称合规", "high", r"(稳赚|保本|零风险|翻倍|躺赚|高收益无风险)",
     "涉及收益承诺涉嫌违规，请删除收益保证类表述。"),
    ("FACT_SOURCE_01", "引用来源", "medium", r"(据统计|研究表明|专家表示|据调查)(?![^。]*来源)",
     "数据类断言缺少来源标注，请补充权威出处以提升 AI 引用可信度。"),
    ("SENSITIVE_01", "敏感词", "high", r"(赌博|色情|代开发票|办证|洗钱)",
     "包含敏感/违法词汇，必须删除。"),
    ("SENSITIVE_02", "敏感词", "medium", r"(微信群|加我微信|私信我|扫码关注)",
     "站外引流话术可能违反平台发布规范，建议弱化。"),
    ("QUALITY_FILL_01", "事实性", "low", r"(众所周知|毋庸置疑|毫无疑问)",
     "空洞强调语降低内容可信度与 AI 引用率，建议用事实与数据替代。"),
]

_SOURCE_HINT = re.compile(r"(来源[:：]|参考来源|http)", re.IGNORECASE)


def check_compliance(text: str) -> dict:
    """返回 {score, risk_level, summary, findings:[{rule_code,category,severity,fragment,suggestion}]}"""
    text = text or ""
    findings = []
    for code, category, severity, pattern, suggestion in RULES:
        for m in re.finditer(pattern, text):
            start = max(0, m.start() - 12)
            fragment = text[start:m.end() + 12].replace("\n", " ")
            findings.append({
                "rule_code": code, "category": category, "severity": severity,
                "fragment": "…" + fragment.strip() + "…", "suggestion": suggestion,
            })
            break  # 每条规则只记首处，避免刷屏

    penalty = {"high": 22.0, "medium": 10.0, "low": 4.0}
    score = 100.0
    for f in findings:
        score -= penalty.get(f["severity"], 5.0)
    if not _SOURCE_HINT.search(text):
        score -= 8.0
        findings.append({
            "rule_code": "FACT_SOURCE_02", "category": "引用来源", "severity": "medium",
            "fragment": "（全文）", "suggestion": "全文无任何来源标注，AI 平台难以引用；建议补充 2-3 条权威来源。",
        })
        score -= 0.0  # 已计入
    score = round(max(0.0, min(100.0, score)), 1)
    risk_level = "high" if score < 60 else ("medium" if score < 85 else "low")

    summary = "检测完成：风险等级 %s，得分 %.1f，共发现 %d 处风险点。" % (
        {"low": "低", "medium": "中", "high": "高"}[risk_level], score, len(findings))
    return {"score": score, "risk_level": risk_level, "summary": summary, "findings": findings}


def findings_json(findings):
    return json.dumps(findings, ensure_ascii=False)
