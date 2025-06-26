from playwright.sync_api import sync_playwright

def parse_card(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=15000)

            title = page.locator('h1').first.text_content() or ""
            price = page.locator("ins[itemprop='price']").first.text_content() or ""
            description = page.locator("div#description div").first.text_content() or ""

            # Характеристики — таблица
            chars = []
            rows = page.locator("div[data-link='product.characteristics'] tr")
            for i in range(rows.count()):
                name = rows.nth(i).locator("td:nth-child(1)").text_content() or ""
                value = rows.nth(i).locator("td:nth-child(2)").text_content() or ""
                if name and value:
                    chars.append(f"{name.strip()} / {value.strip()}")
            characteristics = "::".join(chars)

            return {
                "title": title.strip(),
                "price": price.strip(),
                "description": description.strip(),
                "characteristics": characteristics
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            browser.close()
