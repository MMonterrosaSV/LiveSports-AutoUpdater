from playwright.sync_api import sync_playwright
import os
import re
from urllib.parse import urljoin

def extract_m3u8(url: str, headless: bool = True):
    candidates = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        def handle_response(response):
            response_url = response.url.lower()
            if (
                ".m3u8" in response_url
                or ("playlist" in response_url and "token=" in response_url)
                or "chunk.tvnow247.today" in response_url
            ):
                candidates.append(response.url)

        page.on("response", handle_response)

        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as e:
            print(f"  Warning: {e}")

        page.wait_for_timeout(8000)
        browser.close()

    if not candidates:
        return None

    clean = [u for u in candidates if not any(bad in u.lower() for bad in 
             ["ads", "advert", "tracker", "analytics", "pixel", "banner"])]

    if not clean:
        clean = candidates

    preferred = [u for u in clean if "chunk.tvnow247.today" in u or "token=" in u or ".m3u8" in u]
    best = max(preferred or clean, key=len)
    return best


def scrape_live_events():
    """Scrape soccer events from roxiestreams.info and return list of (name, m3u8)"""
    events = []  # list of (event_name, stream_url)

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
            print(f"  Failed to load soccer page: {e}")
            browser.close()
            return []

        # Get all event links
        links = page.query_selector_all("table#eventsTable tbody tr td a")
        event_list = []
        seen_urls = set()

        for link in links:
            name = link.inner_text().strip()
            href = link.get_attribute("href")
            if not name or not href:
                continue
            full_url = urljoin("https://roxiestreams.info", href)
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                event_list.append((name, full_url))

        print(f"  Found {len(event_list)} unique events")

        # Now visit each event page and extract m3u8
        for name, event_url in event_list:
            print(f"  → {name}")
            m3u8 = extract_m3u8(event_url)
            if m3u8:
                print(f"     Found stream")
                events.append((name, m3u8))
            else:
                print(f"     No stream found")

        browser.close()

    return events


# Fixed channels → (embed_url, group_title)
channels = {
    "Dazn La Liga": ("https://tvnow247.top/embed/dazn-laliga/", "Live Sports"),
    "M+ LA LIGA 1": ("https://tvnow247.top/embed/movistar-laliga/", "Live Sports"),
    "M+ CHAMPIONS LEAGUE 1": ("https://tvnow247.top/embed/movistar-liga-de-campeones/", "Live Sports"),
    "M+ DEPORTES 1": ("https://tvnow247.top/embed/movistar-deportes-4", "Live Sports"),
    "M+ DEPORTES 2": ("https://tvnow247.top/embed/movistar-deportes-2/", "Live Sports"),
    "M+": ("https://tvnow247.top/embed/movistar-supercopa-de-espana/", "Live Sports"),
    "TNT SPORTS 1 UK": ("https://tvnow247.top/embed/tnt-sports-1/", "Live Sports"),
    "ESPN DEPORTES": ("https://tvnow247.top/embed/espn-deportes/", "Live Sports"),
    "HBO USA": ("https://tvnow247.top/embed/hbo-usa/", "Live Sports"),
    "HBO 2": ("https://tvnow247.top/embed/hbo2-usa/", "Live Sports"),
}


def update_playlist():
    playlist_file = "LiveSports.m3u"

    # Preserve only tvg-id and tvg-logo
    existing = {}
    if os.path.exists(playlist_file):
        with open(playlist_file, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        current_meta = {}
        for line in lines:
            if line.startswith("#EXTINF:"):
                name = line.split(",")[-1].strip() if "," in line else ""
                tvg_id = re.search(r'tvg-id="([^"]*)"', line)
                tvg_logo = re.search(r'tvg-logo="([^"]*)"', line)
                current_meta = {
                    "name": name,
                    "tvg_id": tvg_id.group(1) if tvg_id else "",
                    "tvg_logo": tvg_logo.group(1) if tvg_logo else "",
                }
            elif line.startswith("http") and current_meta:
                current_meta["url"] = line.strip()
                existing[current_meta["name"]] = current_meta
                current_meta = {}

    content = "#EXTM3U\n#PLAYLIST:LIVE SPORTS\n"

    # 1. Fixed channels (Live Sports)
    for name, (embed_url, group_title) in channels.items():
        print(f"\nProcessing fixed channel: {name}")
        new_url = extract_m3u8(embed_url)

        prev = existing.get(name, {})
        tvg_id = prev.get("tvg_id", "")
        tvg_logo = prev.get("tvg_logo", "")
        old_url = prev.get("url", "https://example.com")

        final_url = new_url if new_url else old_url
        if new_url:
            print(f"  → Found: {new_url}")
        else:
            print("  → No stream found, keeping old URL")

        content += f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{tvg_logo}" group-title="{group_title}",{name}\n'
        content += f"{final_url}\n"

    # 2. Live Events from roxiestreams
    live_events = scrape_live_events()
    for name, stream_url in live_events:
        content += f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="Live Events",{name}\n'
        content += f"{stream_url}\n"

    with open(playlist_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nLiveSports.m3u updated!")
    print(f"  Fixed channels : {len(channels)}")
    print(f"  Live Events    : {len(live_events)}")
    return True


if __name__ == "__main__":
    print("Starting playlist update...")
    update_playlist()
    print("Done.")
