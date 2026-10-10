import asyncio
from playwright.async_api import async_playwright

URL = "https://stock-vs-sales.preview.emergentagent.com"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={"width": 1920, "height": 800})
        await page.goto(URL, wait_until="domcontentloaded")
        await page.wait_for_selector('input[placeholder="Enter your username"]', timeout=20000)
        await page.fill('input[placeholder="Enter your username"]', 'admin')
        await page.fill('input[placeholder="Enter your password"]', 'admin123')
        await page.click('button:has-text("Sign In")')
        await page.wait_for_timeout(4000)
        await page.goto(f"{URL}/dead-items")
        await page.wait_for_selector('[data-testid="coverage-note"]', timeout=60000)
        print("coverage note:", (await page.locator('[data-testid="coverage-note"]').text_content()).strip())
        print("as-of input:", await page.locator('[data-testid="as-of-input"]').input_value())
        print("dead badge:", await page.locator('[data-testid="dead-count-badge"]').text_content())
        rc = await page.locator('[data-testid="review-count-badge"]').count()
        if rc:
            print("review badge:", await page.locator('[data-testid="review-count-badge"]').text_content())
        await page.wait_for_timeout(1000)
        await page.screenshot(path="/app/test_reports/dead_items_v3.png")
        print("SCREENSHOT OK")
        await b.close()

asyncio.run(main())
