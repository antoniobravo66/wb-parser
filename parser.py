from playwright.sync_api import sync_playwright

def parse_wb_card(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        title = page.title()
        try:
            price = page.locator("meta[itemprop='price']").get_attribute("content")
        except:
            price = ""
        try:
            desc = page.locator("meta[name='description']").get_attribute("content")
        except:
            desc = ""
        try:
            chars = page.locator("div.product-params__list").inner_text()
        except:
            chars = ""
        browser.close()
        return {
            "title": title,
            "price": price,
            "description": desc,
            "characteristics": chars
        }