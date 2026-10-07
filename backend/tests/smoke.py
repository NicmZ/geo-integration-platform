# -*- coding: utf-8 -*-
"""端到端冒烟测试（需服务端以 CAPTCHA_ENABLED=false 启动）：
注册→登录→profile→品牌→知识库任务→关键词→批量检测→结果→合规检测→解锁→内容生成→发布→流水→工单→支付"""
import json
import random
import sys
import time

import httpx

BASE = "http://127.0.0.1:8001"
c = httpx.Client(base_url=BASE, timeout=60)
_failed = []


def step(name, resp, expect_code=0):
    body = {}
    try:
        body = resp.json()
    except Exception:
        pass
    ok_ = resp.status_code == 200 and body.get("code") == expect_code
    print("[%s] %-28s http=%s code=%s" % ("PASS" if ok_ else "FAIL", name, resp.status_code, body.get("code", "?")))
    if not ok_:
        print("   body:", json.dumps(body, ensure_ascii=False)[:500])
        _failed.append(name)
    return body.get("data") or {}


def poll_task(headers, task_id, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = c.get("/api/celery_tasks/task-status/%s/" % task_id, headers=headers).json()
        d = r.get("data") or {}
        if d.get("status") in ("SUCCESS", "FAILURE"):
            return d
        time.sleep(1)
    return {"status": "TIMEOUT"}


print("== 1. 用户与认证 ==")
username = "smoke_%d" % random.randint(10000, 999999)
data = step("register", c.post("/api/users/register/", json={
    "username": username, "password": "smoke123456", "email": "s@t.cn"}))
TOKEN = data["token"]
H = {"Authorization": "Bearer " + TOKEN}
uid = data["user"]["id"]
print("   user_id=%s balance 初始赠送见 profile" % uid)

data = step("profile", c.get("/api/users/profile/", headers=H))
print("   balance=%s brands=%s" % (data.get("balance"), data.get("brands")))

step("my-token get", c.get("/api/users/my-token/", headers=H))
data = step("my-token reset", c.post("/api/users/my-token/", json={}, headers=H))
print("   geo_token=%s..." % data["token"][:12])

print("== 2. 品牌与知识库 ==")
data = step("company-profile put", c.put("/api/account_info/company-profile/", json={
    "company_name": "冒烟科技有限公司", "industry": "IT/互联网/电子"}, headers=H))
data = step("brand create", c.post("/api/account_info/brands/", json={
    "name": "冒烟品牌", "brand_type": "main", "description": "测试品牌，主打 GEO 优化服务"}, headers=H))
BRAND_ID = data["id"]
step("brand document add", c.post("/api/account_info/brands/%d/documents/" % BRAND_ID, json={
    "filename": "品牌手册.txt", "doc_type": "text",
    "content": "冒烟品牌成立于 2020 年，专注 AI 搜索优化，服务客户超过 500 家。"}, headers=H))

data = step("kb create-task", c.post("/api/account_info/knowledge-base/create-task/", json={
    "brand": BRAND_ID}, headers=H))
d = poll_task(H, data["task_id"])
print("   kb task: %s %s" % (d["status"], json.dumps(d.get("result", {}), ensure_ascii=False)[:120]))
if d["status"] != "SUCCESS":
    _failed.append("kb_build")

step("kb check", c.get("/api/account_info/knowledge-base/check/%d/" % BRAND_ID, headers=H))

print("== 3. 关键词与 GEO 检测 ==")
data = step("bulk-import", c.post("/api/keywords/bulk-import/", json={
    "keywords": ["AI搜索优化怎么样", "geo平台推荐", "内容营销工具"], "brand_id": BRAND_ID}, headers=H))
kw_ids = [k["id"] for k in data["keywords"]]
print("   imported=%s skipped=%s" % (data["created"], data["skipped"]))

data = step("batch checks", c.post("/api/keywords/checks/", json={
    "keywords": kw_ids, "engines": ["deepseek", "doubao", "qwen"]}, headers=H))
check_ids = [t["check_id"] for t in data["tasks"]]
task_ids = [t["task_id"] for t in data["tasks"]]
for t in task_ids:
    d = poll_task(H, t, timeout=90)
    if d["status"] != "SUCCESS":
        _failed.append("keyword_check:%s" % t)
print("   %d 个检测任务完成" % len(task_ids))

data = step("check detail", c.get("/api/keywords/checks/%s/" % check_ids[0], headers=H))
print("   geo_score=%s engines=%s" % (data.get("geo_score"), [r["engine"] for r in data.get("results", [])]))
step("dashboard", c.get("/api/keywords/dashboard/", headers=H))
step("dashboard trend", c.get("/api/keywords/dashboard/trend/?range=7days", headers=H))
step("engines list", c.get("/api/result/engines/", headers=H))

print("== 4. 合规检测与解锁 ==")
data = step("compliance submit", c.post("/api/keywords/compliance/", json={
    "keyword_id": kw_ids[0]}, headers=H))
report_id = data["report_id"]
poll_task(H, data["task_id"])
data = step("compliance detail(locked)", c.get("/api/keywords/compliance/%d/" % report_id, headers=H))
print("   score=%s risk=%s locked=%s" % (data.get("score"), data.get("risk_level"), data.get("locked")))
data = step("compliance unlock", c.post("/api/keywords/unlock/", json={"report_id": report_id}, headers=H))
print("   findings=%s balance_after=%s" % (len(data.get("findings", [])), data.get("balance_after")))

print("== 5. AI 内容生产 ==")
data = step("generate-content", c.post("/api/content/content/generate-content/", json={
    "title": "2026 年 AI 搜索优化完全指南", "keywords": ["AI搜索优化", "GEO"],
    "brand": [BRAND_ID], "length": 800, "summary": "面向品牌的 GEO 实操指南",
    "engine_platform_key": "deepseek"}, headers=H))
content_id = data["content_id"]
d = poll_task(H, data["task_id"], timeout=90)
print("   content task: %s %s" % (d["status"], json.dumps(d.get("result", {}), ensure_ascii=False)[:150]))
if d["status"] != "SUCCESS":
    _failed.append("content_generate")

data = step("content detail", c.get("/api/content/content/%d/" % content_id, headers=H))
print("   status=%s body_len=%s" % (data.get("status"), len(data.get("body", ""))))

print("== 6. 全渠道发布 ==")
data = step("publish bulk", c.post("/api/content/publish-tasks/bulk-publish/", json={
    "content_ids": [content_id], "platforms": ["xiaohongshu", "zhihu", "toutiao"]}, headers=H))
pt_ids = [t["id"] for t in data["tasks"]]
time.sleep(4)
data = step("publish tasks list", c.get("/api/content/publish-tasks/", headers=H))
print("   tasks=%s statuses=%s" % (data["count"], {t["status"] for t in data["results"]}))

print("== 7. 计费与支付 ==")
data = step("balance", c.get("/api/account_info/balance", headers=H))
print("   balance=%s" % data)
data = step("consumption-records", c.get("/api/account_info/consumption-records/", headers=H))
print("   records=%s first=%s" % (data["count"], data["results"][0]["record_id"] if data["results"] else None))
data = step("payment create(sandbox)", c.post("/api/payment/create/", json={
    "plan_type": "credits_50", "payment_method": "alipay"}, headers=H))
print("   order=%s status=%s balance_after=%s" % (data["order_no"], data["status"], data.get("balance_after")))
step("order status", c.get("/api/payment/status/%s/" % data["order_no"], headers=H))

print("== 8. 工单与扩展 ==")
data = step("ticket create", c.post("/api/feedback/feedbacks/", json={
    "title": "检测速度问题", "content": "批量检测时报错失败，希望优化", "category": "功能异常"}, headers=H))
tid = data["id"]
step("feedback analyze", c.post("/api/feedback/feedbacks/analyze/", json={
    "content": "批量检测时报错失败"}, headers=H))
step("ticket respond", c.post("/api/feedback/feedbacks/%d/respond/" % tid, json={
    "content": "已收到，正在排查"}, headers=H))
step("ticket close", c.post("/api/feedback/feedbacks/%d/close/" % tid, json={}, headers=H))
step("publisher-status", c.get("/api/extension_monitor/publisher-status/", headers=H))
step("social accounts", c.get("/api/social_publisher/accounts/", headers=H))
step("media_db", c.get("/api/media_db/media/?channel=C&page=1", headers=H))

print()
if _failed:
    print("FAILED:", _failed)
    sys.exit(1)
print("ALL SMOKE TESTS PASSED")
