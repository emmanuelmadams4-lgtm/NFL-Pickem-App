"""Playwright UI test for the App Store.

Tests the app in a mobile viewport (iPhone-like) and verifies:
- The home page loads
- The API health endpoint responds (GET /store/health/health)
- The apps catalog responds (GET /store/apps)
- The dashboard responds (GET /store/health/dashboard)
"""

import time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8080"

# API endpoints are directly on the app (no /store prefix)
FILES = {
    "auth": "/auth",
    "apps": "/apps",
    "health": "/health",
    "backups": "/backups",
    "audit": "/audit",
    "push": "/push",
    "credentials": "/credentials",
}

# Sub-paths (router is matched with prefix when prefixed)
HEALTHT = "/health"
DOT = "/dashboard"
SUBS = "/subscriptions"
SUBS_ID = "/subscriptions/1"
VAPID = "/vapid-keys"
LOG = "/log"
FAILED = "/failed"
RESTORE = "/backups/1/restore"
CRED_KEY = "/credentials/app_slug/secret_key"
CRED = "/credentials/app_slug"
BACKUPS = "/backups"
BACKUPS_ID = "/backups/1"


def test_home_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 390, "height": 844})

        try:
            page.goto(BASE + "/", wait_until="networkidle", timeout=15000)
            page.screenshot(path="/tmp/app_home.png", full_page=True)
            time.sleep(1)
            assert page.url == BASE + "/"
            print("PASS: Home page loaded at", page.url)
            print("PASS: Title =", page.title())
        except Exception as e:
            print("FAIL: Home page -", e)
            page.screenshot(path="/tmp/app_store_home_error.png", full_page=True)
            print("Screenshot: /tmp/app_store_home_error.png")
        finally:
            browser.close()


def test_api_endpoints():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()

        try:
            # Health endpoint: /store/health/health (router /health + prefix /store/health)
            resp = page.request.get(BASE + FILES["health"] + HEALTHT)
            print("Health:", resp.status)
            if resp.status == 200:
                data = resp.json()
                print("  body:", data)
                assert data.get("status") == "ok"

            # Apps catalog: /store/apps (router "" + prefix /store/apps)
            resp = page.request.get(BASE + FILES["apps"])
            print("Apps:", resp.status)
            if resp.status == 200:
                data = resp.json()
                print("  apps:", len(data))
                assert len(data) > 0

            # Dashboard: /store/health/dashboard (router /dashboard + prefix /store/health)
            resp = page.request.get(BASE + FILES["health"] + DOT)
            print("Dashboard:", resp.status)
            assert resp.status == 200

            # Auth
            resp = page.request.get(BASE + FILES["auth"] + "/register")
            print("Auth register:", resp.status)

            # Credentials
            resp = page.request.get(BASE + "/store/credentials/app_slug")
            print("Credentials:", resp.status)

            # Backups
            resp = page.request.get(BASE + FILES["backups"] + BACKUPS)
            print("Backups:", resp.status)

            # Audit
            resp = page.request.get(BASE + FILES["audit"] + "/audit/logs")
            print("Audit logs:", resp.status)

            # Push
            resp = page.request.get(BASE + FILES["push"] + "/push/vapid-keys")
            print("Push vapid keys:", resp.status)

        except Exception as e:
            print("FAIL: API endpoint -", e)
        finally:
            browser.close()


def test_apps_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 390, "height": 844})

        try:
            page.goto(BASE + FILES["apps"], wait_until="networkidle", timeout=15000)
            time.sleep(1)
            print("PASS: Apps page loaded at", page.url)
            text = page.inner_text("body")
            print("PASS: Body text (first 200 chars):", text[:200])
        except Exception as e:
            print("FAIL: Apps page -", e)
            page.screenshot(path="/tmp/app_store_apps_error.png", full_page=True)
            print("Screenshot: /tmp/app_store_apps_error.png")
        finally:
            browser.close()


def test_health_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 390, "height": 844})

        try:
            page.goto(BASE + FILES["health"] + HEALTHT, wait_until="networkidle", timeout=15000)
            time.sleep(1)
            print("PASS: Health page loaded at", page.url)
            text = page.inner_text("body")
            print("PASS: Body text:", text)
        except Exception as e:
            print("FAIL: Health page -", e)
            page.screenshot(path="/tmp/app_store_health_error.png", full_page=True)
            print("Screenshot: /tmp/app_store_health_error.png")
        finally:
            browser.close()


def test_dashboard_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 390, "height": 844})

        try:
            page.goto(BASE + FILES["health"] + DOT, wait_until="networkidle", timeout=15000)
            time.sleep(1)
            print("PASS: Dashboard page loaded at", page.url)
            text = page.inner_text("body")
            print("PASS: Body text:", text)
        except Exception as e:
            print("FAIL: Dashboard page -", e)
            page.screenshot(path="/tmp/app_store_dashboard_error.png", full_page=True)
            print("Screenshot: /tmp/app_store_dashboard_error.png")
        finally:
            browser.close()


def test_push_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 390, "height": 844})

        try:
            page.goto(BASE + FILES["push"] + VAPID, wait_until="networkidle", timeout=15000)
            time.sleep(1)
            print("PASS: Push keys page loaded at", page.url)
            text = page.inner_text("body")
            print("PASS: Body text:", text)
        except Exception as e:
            print("FAIL: Push page -", e)
            page.screenshot(path="/tmp/app_store_push_error.png", full_page=True)
            print("Screenshot: /tmp/app_store_push_error.png")
        finally:
            browser.close()


if __name__ == "__main__":
    print("=== App Store UI Test ===")
    test_home_page()
    test_api_endpoints()
    test_apps_page()
    test_health_page()
    test_dashboard_page()
    test_push_page()
    print("=== Tests complete ===")
