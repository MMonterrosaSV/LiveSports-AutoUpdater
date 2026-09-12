from playwright.sync_api import sync_playwright
import os
import re
from urllib.parse import urljoin

def extract_m3u8_from_page(page, url: str):
    """Extract m3u8 using an already open page"""
    candidates = []

    def handle_response(response):
        response_url = response.url.lower()
        if (
            ".m3u8" in response_url
            or ("playlist" in response_url and "token=" in response_url)
            or "chunk.tvnow247.today" in response_url
            or "tv247.site" in response_url
        ):
            candidates.append(response.url)

    page.on("response", handle_response)

    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(8000)
    except Exception as e:
        print(f"  Warning: {e}")

    page.remove_listener("response", handle_response)

    if not candidates:
        return None

    clean = [u for u in candidates if not any(bad in u.lower() for bad in 
             ["ads", "advert", "tracker", "analytics", "pixel", "banner"])]

    if not clean:
        clean = candidates

    preferred = [u for u in clean if "chunk.tvnow247.today" in u or "token=" in u or ".m3u8" in u or "tv247.site" in u]
    best = max(preferred or clean, key=len)
    return best


def extract_m3u8(url: str, headless: bool = True):
    """Standalone version for fixed channels"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        result = extract_m3u8_from_page(page, url)
        browser.close()
        return result


def scrape_live_events():
    """Scrape soccer events from roxiestreams.info"""
    events = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("\nScraping soccer events from roxiestreams.info ...")
        try:
            page.goto("https://roxiestreams.info/soccer", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  Failed to load
