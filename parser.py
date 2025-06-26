from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import re

def parse_wb_card(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=60000)
            page.wait_for_selector('h1', timeout=15000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            title = soup.select_one("h1").text.strip() if soup.select_one("h1") else ""
            description = soup.select_one("meta[name='description']")["content"].strip() if soup.select_one("meta[name='description']") else ""
            price = ""
            price_tag = soup.select_one("ins.price-block__final-price")
            if price_tag:
                price = re.sub(r"[^\d]", "", price_tag.text.strip())

            chars = soup.select("div.product-params__item")
            characteristics = []
            for c in chars:
                name = c.select_one(".product-params__label")
                value = c.select_one(".product-params__value")
                if name and value:
                    n = name.text.strip()
                    v = value.text.strip()
                    characteristics.append(f"{n} / {v}")
            characteristics_str = "::".join(characteristics)

            return {
                "title": title,
                "price": price,
                "description": description,
                "characteristics": characteristics_str
            }
        except Exception as e:
            return {
                "title": "",
                "price": "",
                "description": "",
                "characteristics": "",
                "error": str(e)
            }
        finally:
            browser.close()