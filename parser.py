from playwright.sync_api import sync_playwright

def parse_wb_card(url):
    result = {
        "title": "",
        "price": "",
        "rating": "",
        "description": "",
        "characteristics": ""
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60000)

            # Название
            try:
                result["title"] = page.locator("h1").first.inner_text()
            except:
                result["title"] = ""

            # Цена
            try:
                price = page.locator("ins[itemprop='price']").first.inner_text()
                result["price"] = price.replace("₽", "").replace("\u2009", "").strip()
            except:
                result["price"] = ""

            # Рейтинг
            try:
                rating_text = page.locator("span.product-review__rating").first.inner_text()
                result["rating"] = rating_text.strip()
            except:
                result["rating"] = ""

            # Описание
            try:
                result["description"] = page.locator("div.collapsable__text").first.inner_text()
            except:
                result["description"] = ""

            # Характеристики
            try:
                characteristics = []
                items = page.locator("div.product-params__item")
                count = items.count()
                for i in range(count):
                    title = items.nth(i).locator("div.product-params__cell--title").inner_text()
                    value = items.nth(i).locator("div.product-params__cell--value").inner_text()
                    if title and value:
                        characteristics.append(f"{title} / {value}")
                result["characteristics"] = "::".join(characteristics)
            except:
                result["characteristics"] = ""

            browser.close()
    except Exception as e:
        result["error"] = str(e)

    return result
