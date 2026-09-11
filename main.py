from playwright.sync_api import sync_playwright
import os

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

        page.wait_for_timeout(7000)
        browser.close()

    if not candidates:
        return None

    clean = [u for u in candidates if not any(bad in u.lower() for bad in 
             ["ads", "advert", "tracker", "analytics", "pixel", "banner"])]

    if not clean:
        clean = candidates

    preferred = [u for u in clean if "chunk.tvnow247.today" in u or "token=" in u]
    best = max(preferred or clean, key=len)
    return best


channels = {
    "Dazn La Liga": "https://tvnow247.top/embed/dazn-laliga/",
    "M+ LA LIGA 1": "https://tvnow247.top/embed/movistar-laliga/",
    "M+ CHAMPIONS LEAGUE 1": "https://tvnow247.top/embed/movistar-liga-de-campeones/",
    "M+ DEPORTES 1": "https://tvnow247.top/embed/movistar-deportes-4",
    "M+ DEPORTES 2": "https://tvnow247.top/embed/movistar-deportes-2/",
    "M+": "https://tvnow247.top/embed/movistar-supercopa-de-espana/",
    "TNT SPORTS 1 UK": "https://tvnow247.top/embed/tnt-sports-1/",
    "ESPN DEPORTES": "https://tvnow247.top/embed/espn-deportes/",
    "HBO USA": "https://tvnow247.top/embed/hbo-usa/",
    "HBO 2": "https://tvnow247.top/embed/hbo2-usa/",
    "Dazn La Liga zLive": "https://zlive.st/watch/auto-dazn-laliga",
}


def update_playlist():
    playlist_file = "LiveSports.m3u"

    content = "#EXTM3U\n#PLAYLIST:LIVE SPORTS\n"

    # Keep old URLs if the file already exists
    existing_urls = {}
    if os.path.exists(playlist_file):
        with open(playlist_file, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        current_name = None
        for line in lines:
            if line.startswith("#EXTINF:"):
                if "," in line:
                    current_name = line.split(",")[-1].strip()
            elif current_name and line.startswith("http"):
                existing_urls[current_name] = line.strip()
                current_name = None

    for name, embed_url in channels.items():
        print(f"\nProcessing: {name}")
        new_url = extract_m3u8(embed_url)

        if new_url:
            print(f"  → Found: {new_url}")
            final_url = new_url
        else:
            print("  → No stream found, keeping old URL")
            final_url = existing_urls.get(name, "https://example.com")

        content += f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="LIVE SPORTS",{name}\n'
        content += f"{final_url}\n"

    with open(playlist_file, "w", encoding="utf-8") as f:
        f.write(content)

    print("\nLiveSports.m3u has been updated")
    return True


if __name__ == "__main__":
    print("Starting playlist update...")
    update_playlist()
    print("Done.")
