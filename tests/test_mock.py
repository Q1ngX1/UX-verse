import re
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.async_api import async_playwright, expect

SITE = Path(__file__).resolve().parents[1] / "mock"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class MockSiteTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=SITE))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        self.addAsyncCleanup(self.playwright.stop)
        self.browser = await self.playwright.chromium.launch()
        self.addAsyncCleanup(self.browser.close)

    async def fill_contact(self, page):
        await page.get_by_label("Your name").fill("Sample Visitor")
        await page.get_by_label("Email").fill("visitor@example.com")
        await page.get_by_label("Message").fill("Please check the route access notes.")

    async def test_baseline_catalog_detail_saved_and_contact(self):
        page = await self.browser.new_page(viewport={"width": 1280, "height": 720})
        await page.goto(self.origin)
        await expect(page.get_by_role("heading", name="Find a trail worth the morning.")).to_be_visible()
        self.assertGreater(await page.locator(".hero img").evaluate("image => image.naturalWidth"), 0)
        await page.get_by_label("Find a route").fill("redwoods")
        await page.get_by_role("button", name="Search", exact=True).click()
        await expect(page.locator("#result-count")).to_have_text("2 routes")
        await page.get_by_label("Sort by").select_option("longest")
        await expect(page.locator("#results h3").first).to_have_text("Redwood Ridge")
        await page.get_by_label("Difficulty").select_option("Easy")
        await expect(page.locator("#result-count")).to_have_text("1 route")
        await page.get_by_role("link", name="Fern Creek Loop", exact=True).click()
        await expect(page.get_by_role("heading", name="Fern Creek Loop", exact=True)).to_be_visible()
        await page.get_by_role("button", name="Parking & access").click()
        await expect(page.get_by_role("heading", name="Parking & access")).to_be_visible()
        await page.get_by_role("button", name="Enlarge route photo").click()
        await expect(page.get_by_role("dialog")).to_be_visible()
        await page.keyboard.press("Escape")
        await expect(page.get_by_role("dialog")).to_be_hidden()
        await page.get_by_role("button", name="Save Fern Creek Loop").click()
        await expect(page.locator(".notice")).to_have_text("Fern Creek Loop saved.")
        await page.get_by_role("link", name="All routes").click()
        await expect(page.get_by_label("Search routes")).to_have_value("redwoods")
        await expect(page.get_by_label("Difficulty")).to_have_value("Easy")
        primary = page.get_by_role("navigation", name="Main navigation")
        await primary.get_by_role("link", name=re.compile("^Saved")).click()
        await page.reload()
        await expect(page.get_by_role("link", name="Fern Creek Loop", exact=True)).to_be_visible()
        await page.get_by_role("button", name="Remove Fern Creek Loop").click()
        await expect(page.get_by_role("heading", name="No routes saved yet")).to_be_visible()
        await primary.get_by_role("link", name="Field guide", exact=True).click()
        await page.get_by_text("Where can I find parking information?").click()
        await expect(page.get_by_text("Open a route and select Parking", exact=False)).to_be_visible()
        await page.get_by_role("link", name="Check seasonal access").click()
        self.assertTrue(page.url.endswith("#seasonal"))
        await page.get_by_role("link", name="Report a problem with a route").click()
        await page.get_by_role("button", name="Send message").click()
        await expect(page.get_by_label("Your name")).to_be_focused()
        await self.fill_contact(page)
        await page.get_by_role("button", name="Send message").click()
        await expect(page.get_by_role("button", name="Sending…")).to_be_disabled()
        await expect(page.locator("#feedback")).to_have_text("Thanks. Your demo message was received.")

    async def test_seeded_desktop_issues(self):
        page = await self.browser.new_page()
        await page.goto(self.origin + "/?scenario=issues")
        primary = page.get_by_role("navigation", name="Main navigation")
        await expect(primary.get_by_role("link", name="Saved")).to_have_count(0)
        await expect(page.get_by_role("navigation", name="Footer").get_by_role("link", name="Saved")).to_be_visible()
        await page.get_by_role("link", name="Browse all routes").click()
        await expect(page).to_have_url(re.compile(r"routes\.html\?scenario=issues$"))
        await page.locator("#results .card img").first.click(position={"x": 20, "y": 20})
        await expect(page.get_by_role("heading", name="Find a route")).to_be_visible()
        await page.get_by_label("Difficulty").select_option("Easy")
        await page.get_by_role("button", name="Clear filters").click()
        await expect(page.get_by_label("Difficulty")).to_have_value("Easy")
        await page.get_by_role("link", name="Fern Creek Loop", exact=True).click()
        await page.get_by_role("button", name="Parking & access").click()
        await expect(page.get_by_role("heading", name="What to bring")).to_be_visible()
        await page.get_by_role("link", name="All routes").click()
        await expect(page.get_by_role("heading", name="Find a trail worth the morning.")).to_be_visible()
        await primary.get_by_role("link", name="Field guide").click()
        async with page.expect_response(lambda response: "seasonal-access.html" in response.url) as pending:
            await page.get_by_role("link", name="Check seasonal access").click()
        self.assertEqual((await pending.value).status, 404)
        await page.go_back()
        await page.get_by_role("link", name="Report a problem with a route").click()
        await self.fill_contact(page)
        await page.get_by_role("button", name="Send message").click()
        await expect(page.get_by_role("button", name="Sending…")).to_be_disabled()
        await expect(page.get_by_role("button", name="Send message")).to_be_enabled()
        await expect(page.locator("#feedback")).to_be_empty()
        await expect(page.get_by_label("Message")).to_have_value("")

    async def test_mobile_navigation_and_seeded_footer_overlap(self):
        page = await self.browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        await page.goto(self.origin)
        self.assertEqual(await page.evaluate("document.documentElement.scrollWidth"), 390)
        primary = page.get_by_role("navigation", name="Main navigation")
        await expect(primary).to_be_hidden()
        await page.get_by_role("button", name="Menu").tap()
        await expect(primary.get_by_role("link", name="Saved", exact=True)).to_be_visible()
        await page.get_by_role("button", name="Menu").tap()
        await expect(primary).to_be_hidden()

        for variant in ("", "&scenario=issues"):
            await page.goto(self.origin + "/route.html?id=fern-creek" + variant)
            await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            contact = page.get_by_role("navigation", name="Footer").get_by_role("link", name="Contact")
            covered = await contact.evaluate("""link => {
                const bounds = link.getBoundingClientRect();
                const target = document.elementFromPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
                return Boolean(target && target.closest('.mobile-callout'));
            }""")
            self.assertEqual(covered, bool(variant))
