# -*- coding: utf-8 -*-
"""移动端 + PC 双端 UI 实测（playwright + 系统 Edge）

用法: venv\\Scripts\\python.exe tests\\mobile_check.py
前置: 后端 :8001 (CAPTCHA_ENABLED=false)，前端 vite dev :9527
"""
import os
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:9527"
SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
os.makedirs(SHOTS, exist_ok=True)

results = []


def check(name, ok, note=""):
    results.append((name, bool(ok), note))
    print(("PASS " if ok else "FAIL ") + name + (" | " + note if note else ""))


def run():
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception:
            browser = p.chromium.launch(channel="chrome", headless=True)

        # ---------- 手机视口 375x812 ----------
        ctx = browser.new_context(viewport={"width": 375, "height": 812})
        page = ctx.new_page()
        page.goto(BASE + "/login", wait_until="networkidle", timeout=90000)
        page.screenshot(path=os.path.join(SHOTS, "01_login_mobile.png"))

        card = page.locator(".login-card")
        box = card.bounding_box()
        check("登录卡片适配手机宽度", box and box["width"] <= 375,
              "card width=%s" % (box and round(box["width"])))
        sw = page.evaluate("document.documentElement.scrollWidth")
        check("登录页无横向溢出", sw <= 376, "scrollWidth=%s" % sw)

        page.fill('input[placeholder="用户名"]', "browser_test1")
        page.fill('input[placeholder="密码"]', "test123456")
        page.click('button:has-text("登 录")')
        page.wait_for_url("**/dashboard", timeout=30000)
        page.wait_for_timeout(2500)  # 等图表渲染
        page.screenshot(path=os.path.join(SHOTS, "02_dashboard_mobile.png"), full_page=True)

        check("手机端汉堡菜单可见", page.locator(".burger").is_visible())
        check("手机端固定侧栏隐藏", page.locator(".el-aside").count() == 0)

        stats = page.locator(".el-statistic")
        check("看板统计卡数量=4", stats.count() == 4, "count=%s" % stats.count())
        # 2 列排布验证：第 1、2 卡同一行，第 3 卡换行
        cols = page.locator(".el-row").first.locator(".el-col")
        b0 = cols.nth(0).bounding_box()
        b1 = cols.nth(1).bounding_box()
        b2 = cols.nth(2).bounding_box()
        if b0 and b1 and b2:
            check("统计卡 2 列排布",
                  abs(b0["y"] - b1["y"]) < 4 and b2["y"] > b0["y"] + 10,
                  "y0=%s y1=%s y2=%s" % (round(b0["y"]), round(b1["y"]), round(b2["y"])))
        sw = page.evaluate("document.documentElement.scrollWidth")
        check("看板无横向溢出", sw <= 376, "scrollWidth=%s" % sw)
        check("趋势图已渲染(canvas)", page.locator("canvas").count() >= 1,
              "canvas=%s" % page.locator("canvas").count())

        # 抽屉菜单
        page.click(".burger")
        page.wait_for_selector(".el-drawer", state="visible", timeout=8000)
        page.screenshot(path=os.path.join(SHOTS, "03_drawer_mobile.png"))
        menu_text = page.locator(".el-drawer").inner_text()
        check("抽屉菜单含导航项", ("看板" in menu_text and "关键词" in menu_text),
              "items=%s" % menu_text.count("\n"))
        page.click('.el-drawer >> text=关键词')
        page.wait_for_url("**/keywords", timeout=15000)
        page.wait_for_timeout(800)
        check("抽屉点击后自动关闭", page.locator(".el-drawer").count() == 0
              or not page.locator(".el-drawer").is_visible())
        page.screenshot(path=os.path.join(SHOTS, "04_keywords_mobile.png"))
        ctx.close()

        # ---------- 桌面视口 1280x800 回归 ----------
        dctx = browser.new_context(viewport={"width": 1280, "height": 800})
        dpage = dctx.new_page()
        dpage.goto(BASE + "/login", wait_until="networkidle", timeout=90000)
        dpage.fill('input[placeholder="用户名"]', "browser_test1")
        dpage.fill('input[placeholder="密码"]', "test123456")
        dpage.click('button:has-text("登 录")')
        dpage.wait_for_url("**/dashboard", timeout=30000)
        dpage.wait_for_timeout(2000)
        dpage.screenshot(path=os.path.join(SHOTS, "05_dashboard_desktop.png"))
        check("PC 端固定侧栏恢复", dpage.locator(".el-aside").is_visible())
        check("PC 端无汉堡按钮", dpage.locator(".burger").count() == 0)
        dctx.close()
        browser.close()

    fails = [r for r in results if not r[1]]
    print("\n==== summary: %s passed, %s failed ====" % (
        len(results) - len(fails), len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    run()
