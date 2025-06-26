from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re

def parse_card(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=60000)
            page.wait_for_selector("h1", timeout=10000)
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            title = soup.select_one("h1")
            title = title.get_text(strip=True) if title else ""

            price = ""
            price_tag = soup.select_one("ins.price-block__final-price")
            if price_tag:
                price = re.sub(r"\D", "", price_tag.get_text(strip=True))

            desc = soup.select_one("meta[name='description']")
            description = desc["content"].strip() if desc and desc.get("content") else ""

            char_blocks = soup.select("div.product-params__item")
            characteristics = []
            for block in char_blocks:
                name = block.select_one(".product-params__label")
                value = block.select_one(".product-params__value")
                if name and value:
                    n = name.get_text(strip=True)
                    v = value.get_text(strip=True)
                    characteristics.append(f"{n} / {v}")
            char_string = "::".join(characteristics)

            return {
                "title": title,
                "price": price,
                "description": description,
                "characteristics": char_string
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