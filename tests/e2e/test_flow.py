import os
import re
import sys
import subprocess
import time
import threading
import signal
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

from playwright.sync_api import sync_playwright, expect


BASE_DIR = Path(__file__).resolve().parent.parent.parent
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "latexgenius.settings")
sys.path.insert(0, str(BASE_DIR))


SERVER_URL = "http://localhost:9000"


def new_page(browser):
    page = browser.new_page()
    page.route(re.compile(r"(fonts\.googleapis|fonts\.gstatic|www\.google-\w+\.com|googletagmanager|gtag)"), lambda route: route.abort())
    return page


class TestUserFlow:
    proc = None
    username = ""
    password = "PlaywrightTest123!"

    @classmethod
    def setup_class(cls):
        import string
        import random
        suffix = "".join(random.choices(string.ascii_lowercase, k=6))
        cls.username = f"pw-test-{suffix}@example.com"
        cls.proc = subprocess.Popen(
            [sys.executable, "manage.py", "runserver", "0.0.0.0:9000", "--noreload"],
            cwd=BASE_DIR,
        )
        for _ in range(30):
            try:
                urlopen(SERVER_URL, timeout=2)
                return
            except URLError:
                time.sleep(1)
        raise RuntimeError("Django server failed to start")

    @classmethod
    def teardown_class(cls):
        if cls.proc:
            cls.proc.terminate()
            cls.proc.wait()
            time.sleep(1)

    def test_01_landing_page(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = new_page(browser)
            page.goto(SERVER_URL, wait_until="domcontentloaded", timeout=60000)

            expect(page).to_have_title(re.compile("LatexGenius"))
            heading = page.locator("h1")
            expect(heading).to_be_visible()
            expect(heading).to_contain_text("LaTeX")

            get_started = page.get_by_role("link", name="Get Started", exact=True)
            expect(get_started).to_be_visible()

            nav_features = page.locator("nav a").filter(has_text="Features")
            expect(nav_features).to_be_visible()

            nav_templates = page.locator("nav a").filter(has_text="Templates")
            expect(nav_templates).to_be_visible()

            page.close()
            browser.close()

    def test_02_signup_and_redirect_to_dashboard(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = new_page(browser)
            page.goto(f"{SERVER_URL}/signup/", wait_until="domcontentloaded", timeout=60000)

            expect(page.locator("h2")).to_contain_text("Create Account")

            page.fill("input#name", "Playwright Test")
            page.fill("input#email", self.username)
            page.fill("input#password", self.password)
            page.locator("button[type='submit']").click()

            page.wait_for_url(f"{SERVER_URL}/dashboard/**", wait_until="domcontentloaded")
            expect(page).to_have_url(re.compile("/dashboard/"))

            welcome = page.locator("text=Welcome back")
            expect(welcome).to_be_visible(timeout=10000)

            page.close()
            browser.close()

    def test_03_create_new_project_from_dashboard(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = new_page(browser)
            page.goto(f"{SERVER_URL}/login/", wait_until="domcontentloaded", timeout=60000)
            page.fill("input#username", self.username)
            page.fill("input#password", self.password)
            page.locator("button[type='submit']").click()
            page.wait_for_url(f"{SERVER_URL}/dashboard/**", wait_until="domcontentloaded")

            new_project_btn = page.locator("a").filter(has_text="New Project")
            expect(new_project_btn).to_be_visible()
            new_project_btn.first.click()

            page.wait_for_url(f"{SERVER_URL}/editor/**", wait_until="domcontentloaded")
            expect(page.locator("body")).to_be_visible()

            page.close()
            browser.close()

    def test_04_login_page_elements(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = new_page(browser)
            page.goto(f"{SERVER_URL}/login/", wait_until="domcontentloaded", timeout=60000)

            expect(page).to_have_title(re.compile("Login"))
            expect(page.locator("h1")).to_contain_text("LaTeXGenius")
            expect(page.locator("input#username")).to_be_visible()
            expect(page.locator("input#password")).to_be_visible()
            expect(page.locator("a").filter(has_text="Create an account")).to_be_visible()

            page.close()
            browser.close()

    def test_05_templates_page(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = new_page(browser)
            page.goto(f"{SERVER_URL}/templates/", wait_until="domcontentloaded", timeout=60000)

            expect(page).to_have_title(re.compile("Template|LatexGenius"))
            page.close()
            browser.close()

    def test_06_pricing_page(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = new_page(browser)
            page.goto(f"{SERVER_URL}/pricing/", wait_until="domcontentloaded", timeout=60000)
            page.close()
            browser.close()

    def test_07_documentation_page(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = new_page(browser)
            page.goto(f"{SERVER_URL}/documentation/", wait_until="domcontentloaded", timeout=60000)
            page.close()
            browser.close()

    def test_08_logout(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = new_page(browser)
            page.goto(f"{SERVER_URL}/login/", wait_until="domcontentloaded", timeout=60000)
            page.fill("input#username", self.username)
            page.fill("input#password", self.password)
            page.locator("button[type='submit']").click()
            page.wait_for_url(f"{SERVER_URL}/dashboard/**", wait_until="domcontentloaded")

            page.goto(f"{SERVER_URL}/logout/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_url(SERVER_URL + "/")
            expect(page.locator("h1")).to_contain_text("LaTeX")

            login_btn = page.locator("nav a").filter(has_text="Get Started")
            expect(login_btn).to_be_visible()

            page.close()
            browser.close()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
