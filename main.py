from playwright.sync_api import sync_playwright
import os
import re
from urllib.parse import urljoin, urlparse, parse_qs


def score_url(url: str) -> int:
    """
    Higher score = newer / better signed URL.
    Works for live.tv247.site (e= parameter) and ftlly.com tokens.
    """
    score = 0

    # 1. live.tv247.site → use e= parameter
    try:
        qs = parse_qs(urlparse(url).query)
        if "e" in qs:
            score = max(score, int(qs["e"][0]))
    except:
        pass

    # 2. ftlly.com (and similar) → extract large timestamp numbers from the token
    numbers = re.findall(r"(\d{10,})", url)
    if numbers:
        score = max(score, max(int(n) for n in numbers))

    # 3. slight preference for longer URLs
    score = score * 10 + len(url)

    return score


def extract_m3u8_from_page(page, url: str):
    """Extract the best m3u8 using an already open page"""
    candidates = []

    def handle_response(response):
        u = response.url
        if any(x in u for x in ["live.tv247.site", "ftlly.com"]) and ".m3u8" in u:
            candidates.append(u)
        elif ".m3u8" in u.lower() or ("playlist" in u.lower() and "token=" in u.lower()):
            candidates.append(u)

    page.on("response", handle_response)

    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(10000)  # wait for the newest signed URL
    except Exception as e:
        print(f"  Warning: {e}")

    try:
        page.remove_listener("response", handle_response)
    except:
        pass

    if not candidates:
        return None

    # Prefer known good domains first
    preferred = [u for u in candidates if "live.tv247.site" in u or "ftlly.com" in u]
    pool = preferred if preferred else candidates

    # Pick the newest signed URL
    best = max(pool, key=score_url)
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
            print(f"  Failed to load soccer page: {e}")
            browser.close()
            return []

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

        for name, event_url in event_list:
            print(f"  → {name}")
            m3u8 = extract_m3u8_from_page(page, event_url)
            if m3u8:
                print(f"     Found stream")
                events.append((name, m3u8))
            else:
                print(f"     No stream found")

        browser.close()

    return events


# Fixed channels → (embed_url, group_title)
channels = {
    "DAZN LA LIGA 1": "https://tvnow247.top/embed/dazn-laliga/",
    "M+ LA LIGA 1": "https://tvnow247.top/embed/movistar-laliga/",
    "M+ CHAMPIONS LEAGUE 1": "https://tvnow247.top/embed/movistar-liga-de-campeones/",
    "M+ DEPORTES 1": "https://tvnow247.top/embed/movistar-deportes-4",
    "M+ DEPORTES 2": "https://tvnow247.top/embed/movistar-deportes-2/",
    "M+": "https://tvnow247.top/embed/movistar-supercopa-de-espana/",
    "ESPN DEPORTES": "https://tvnow247.top/embed/espn-deportes/",
    "Dsports": "https://futbollibretv.net.pe/en-vivo/directv-sports",
    "TUDN MEXICO": "https://tvnow247.top/watch/tudn-mx/",
    "TUDN USA": "https://tvnow247.top/watch/tudn-usa/",
    "TNT SPORTS 1": "https://tvnow247.top/embed/tnt-sports-1/",
    "TNT SPORTS 2": "https://tvnow247.top/watch/tnt-sports-2/",
    "TNT SPORTS 3": "https://tvnow247.top/watch/tnt-sports-3/",
    "SKY SPORTS PREMIER LEAGUE": "https://tvnow247.top/watch/sky-sports-premier-league/",
    "SKY SPORTS FOOTBALL": "https://tvnow247.top/watch/sky-sports-football/",
    "SKY SPORTS PLUS": "https://tvnow247.top/watch/sky-sports-plus/",
    "SKY SPORTS MAIN EVENT": "https://tvnow247.top/watch/sky-sports-main-event/",
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

    # 1. Fixed channels
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







