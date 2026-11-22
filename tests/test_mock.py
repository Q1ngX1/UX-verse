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

    async def test_catalog_map_filters_and_comparison(self):
        page = await self.browser.new_page()
        await page.goto(self.origin + "/routes.html")
        await expect(page.locator("#result-count")).to_have_text("15 routes")
        await page.get_by_role("button", name="Under an hour", exact=True).click()
        await expect(page.locator("#result-count")).to_have_text("4 routes")
        await page.get_by_label("Facilities", exact=True).select_option("Transit")
        await expect(page.locator("#result-count")).to_have_text("2 routes")
        await page.get_by_role("button", name="Map", exact=True).click()
        await expect(page.locator("#results")).to_be_hidden()
        await page.get_by_role("button", name="Show Ferry Point Stroll", exact=True).click()
        await expect(page.locator("#map-preview h3")).to_have_text("Ferry Point Stroll")
        await page.reload()
        await expect(page.locator("#map-view")).to_be_visible()
        await expect(page.get_by_label("Walking time")).to_have_value("60")
        await expect(page.get_by_label("Facilities", exact=True)).to_have_value("Transit")
        await page.get_by_role("button", name="Grid", exact=True).click()
        await page.get_by_role("button", name="Clear filters").click()
        for name in ("Cypress Headland", "Fern Creek Loop", "East Harbor Walk"):
            await page.get_by_role("button", name="Compare " + name, exact=True).click()
        await page.get_by_role("button", name="Compare Salt Point Bluff", exact=True).click()
        await expect(page.locator(".notice")).to_contain_text("up to 3 routes")
        await expect(page.locator("#compare-count")).to_have_text("3 of 3 routes selected")
        await page.get_by_role("button", name="Compare routes", exact=True).click()
        await expect(page.get_by_role("dialog")).to_be_visible()
        await expect(page.get_by_role("table")).to_contain_text("Cypress Headland")
        await expect(page.get_by_role("table")).to_contain_text("Fern Creek Loop")
        await page.set_viewport_size({"width": 320, "height": 740})
        await expect(page.locator(".mobile-comparisons")).to_be_visible()
        await expect(page.locator(".mobile-comparison-card")).to_have_count(3)
        self.assertLessEqual(await page.locator("#compare-dialog").evaluate("dialog => dialog.scrollWidth"), 320)
        await page.get_by_role("button", name="Close comparison").click()
        await page.set_viewport_size({"width": 1280, "height": 720})
        await page.get_by_role("button", name="Compare routes", exact=True).click()
        await page.keyboard.press("Escape")
        await expect(page.get_by_role("button", name="Compare routes", exact=True)).to_be_focused()
        await page.get_by_role("button", name="Clear", exact=True).click()
        await expect(page.locator("#compare-bar")).to_be_hidden()

    async def test_trail_finder_backtracking_and_filtered_results(self):
        page = await self.browser.new_page()
        await page.goto(self.origin)
        await page.get_by_role("button", name="Help me choose a trail").click()
        dialog = page.get_by_role("dialog", name="Where would you like to wander?")
        await expect(dialog).to_be_visible()
        await page.get_by_role("radio", name=re.compile("Under the trees")).check()
        await page.get_by_role("button", name="Continue", exact=True).click()
        await page.get_by_role("radio", name=re.compile("A slow morning")).check()
        await page.get_by_role("button", name="Back", exact=True).click()
        await expect(page.get_by_role("radio", name=re.compile("Under the trees"))).to_be_checked()
        await page.get_by_role("button", name="Continue", exact=True).click()
        await page.get_by_role("button", name="Continue", exact=True).click()
        await page.get_by_role("radio", name=re.compile("Keep it gentle")).check()
        await page.get_by_role("button", name="Find my trails").click()
        await expect(page.locator(".finder-results .card")).to_have_count(3)
        await page.get_by_role("button", name="Save Fern Creek Loop", exact=True).last.click()
        await expect(page.locator(".notice")).to_have_text("Fern Creek Loop saved.")
        await page.get_by_role("link", name="View all matches").click()
        await expect(page.get_by_label("Terrain")).to_have_value("Forest")
        await expect(page.get_by_label("Difficulty")).to_have_value("Easy")
        await expect(page.get_by_label("Walking time")).to_have_value("90")
        await expect(page.locator("#result-count")).to_have_text("3 routes")

    async def test_collections_journal_and_scenario_propagation(self):
        page = await self.browser.new_page()
        await page.goto(self.origin + "/collections.html?scenario=issues")
        await page.get_by_role("link", name=re.compile("For the slow mornings")).click()
        await expect(page).to_have_url(re.compile(r"scenario=issues"))
        await expect(page.locator(".grid .card")).to_have_count(4)
        await page.get_by_role("link", name="Plan this collection").click()
        await expect(page.locator(".itinerary li")).to_have_count(4)
        await expect(page).to_have_url(re.compile(r"planner.html\?scenario=issues$"))
        await page.goto(self.origin + "/journal.html?scenario=issues")
        await page.get_by_role("button", name="Trail notes", exact=True).click()
        await expect(page.locator("#story-count")).to_have_text("1 story")
        await page.get_by_role("link", name=re.compile("A small packing list")).click()
        await expect(page.get_by_role("heading", name="Think in layers")).to_be_visible()
        await page.get_by_role("link", name="Explore the collection", exact=True).click()
        await expect(page.get_by_role("heading", name="A little ocean air", exact=True)).to_be_visible()
        self.assertIn("scenario=issues", page.url)

    async def test_planner_persistence_reordering_removal_and_download(self):
        page = await self.browser.new_page()
        await page.goto(self.origin + "/planner.html?add=fern-creek")
        await expect(page.locator(".itinerary li")).to_have_count(1)
        await page.get_by_label("Add a route", exact=True).select_option("harbor-walk")
        await page.get_by_role("button", name="Add route", exact=True).click()
        await page.get_by_label("Adventure date").fill("2026-12-05")
        await page.get_by_label("Start time").fill("10:30")
        await page.get_by_label("Day notes").fill("Meet near the picnic area.")
        await page.get_by_label("Water bottle", exact=True).check()
        await page.get_by_role("button", name="Move East Harbor Walk earlier").click()
        await expect(page.locator(".itinerary h3").first).to_have_text("East Harbor Walk")
        await page.reload()
        await expect(page.locator(".itinerary h3").first).to_have_text("East Harbor Walk")
        await expect(page.get_by_label("Adventure date")).to_have_value("2026-12-05")
        await expect(page.get_by_label("Start time")).to_have_value("10:30")
        await expect(page.get_by_label("Day notes")).to_have_value("Meet near the picnic area.")
        await expect(page.get_by_label("Water bottle", exact=True)).to_be_checked()
        async with page.expect_download() as pending:
            await page.get_by_role("button", name="Download plan").click()
        download = await pending.value
        self.assertEqual(download.suggested_filename, "waymark-day-plan.txt")
        text = Path(await download.path()).read_text(encoding="utf-8")
        self.assertIn("Meet near the picnic area.", text)
        self.assertIn("[x] Water bottle", text)
        self.assertLess(text.index("East Harbor Walk"), text.index("Fern Creek Loop"))
        await page.get_by_role("button", name="Remove East Harbor Walk from plan").click()
        await expect(page.locator(".itinerary li")).to_have_count(1)
        await page.get_by_role("button", name="Clear routes", exact=True).click()
        await page.get_by_role("button", name="Keep routes").click()
        await expect(page.locator(".itinerary li")).to_have_count(1)
        await page.get_by_role("button", name="Clear routes", exact=True).click()
        await page.get_by_role("dialog").get_by_role("button", name="Clear routes", exact=True).click()
        await expect(page.get_by_role("heading", name="The day is yours.")).to_be_visible()
        await expect(page.get_by_label("Day notes")).to_have_value("Meet near the picnic area.")

    async def test_trail_notes_reviews_are_persisted_as_text(self):
        page = await self.browser.new_page()
        await page.goto(self.origin + "/route.html?id=fern-creek")
        await page.get_by_role("button", name="Lower footbridge", exact=True).click()
        await expect(page.locator("#waypoint-note")).to_contain_text("Lower footbridge")
        await page.get_by_label("Trail note", exact=True).fill("Bring a thermos.")
        await page.get_by_role("button", name="Save trail note").click()
        await page.get_by_role("button", name="Add a demo review").click()
        await page.get_by_label("Display name").fill("Sample <visitor>")
        await page.get_by_label("Your review", exact=True).fill('<img src=x onerror="window.injected=true">')
        await page.get_by_role("button", name="Post demo review").click()
        await expect(page.locator("#review-status")).to_contain_text("saved in this browser")
        await page.reload()
        await expect(page.get_by_label("Trail note", exact=True)).to_have_value("Bring a thermos.")
        await expect(page.locator("#reviews")).to_contain_text("Sample <visitor>")
        await expect(page.locator("#reviews img")).to_have_count(0)
        self.assertIsNone(await page.evaluate("window.injected"))
        await page.get_by_role("link", name="Add to day plan").click()
        await expect(page.locator(".itinerary h3")).to_have_text("Fern Creek Loop")

    async def test_pages_fit_phone_tablet_and_desktop_without_browser_errors(self):
        page = await self.browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        paths = ("/", "/routes.html", "/routes.html?view=map", "/collections.html", "/collections.html?id=slow-mornings", "/journal.html", "/journal.html?id=morning-ritual", "/planner.html?add=fern-creek", "/route.html?id=fern-creek", "/saved.html", "/guide.html", "/contact.html")
        for width in (320, 390, 768, 1280):
            await page.set_viewport_size({"width": width, "height": 844})
            for path in paths:
                with self.subTest(width=width, path=path):
                    await page.goto(self.origin + path)
                    await expect(page.locator("main h1")).to_be_visible()
                    self.assertLessEqual(await page.evaluate("document.documentElement.scrollWidth"), width)
                    broken = await page.locator("img").evaluate_all("images => images.filter(image => image.complete && !image.naturalWidth).length")
                    self.assertEqual(broken, 0)
        self.assertEqual(errors, [])
