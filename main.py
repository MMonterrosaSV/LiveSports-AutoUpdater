from playwright.sync_api import sync_playwright
import os
import re


def extract_all_m3u8(url: str, headless: bool = True):
    """Return a list of ALL valid m3u8 URLs found"""
    candidates = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        def handle_response(response):
            u = response.url
            if (
                ".m3u8" in u.lower()
                or ("playlist" in u.lower() and "token=" in u.lower())
                or "chunk.tvnow247.today" in u.lower()
                or "live.tv247.site" in u.lower()
                or "ftlly.com" in u.lower()
            ):
                candidates.append(u)

        page.on("response", handle_response)

        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as e:
            print(f"  Warning: {e}")

        page.wait_for_timeout(10000)
        browser.close()

    if not candidates:
        return []

    # Remove obvious junk
    clean = [u for u in candidates if not any(bad in u.lower() for bad in
             ["ads", "advert", "tracker", "analytics", "pixel", "banner"])]

    if not clean:
        clean = candidates

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for u in clean:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    return unique


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

    # Read existing tags (only for tvg-id / tvg-logo / group-title)
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
                group_title = re.search(r'group-title="([^"]*)"', line)

                current_meta = {
                    "name": name,
                    "tvg_id": tvg_id.group(1) if tvg_id else "",
                    "tvg_logo": tvg_logo.group(1) if tvg_logo else "",
                    "group_title": group_title.group(1) if group_title else "Live Sports"
                }
            elif line.startswith("http") and current_meta:
                # We only keep the tags, not the old URLs
                existing[current_meta["name"]] = current_meta
                current_meta = {}

    content = "#EXTM3U\n#PLAYLIST:LIVE SPORTS\n"

    for name, embed_url in channels.items():
        print(f"\nProcessing: {name}")
        urls = extract_all_m3u8(embed_url)

        prev = existing.get(name, {})
        tvg_id = prev.get("tvg_id", "")
        tvg_logo = prev.get("tvg_logo", "")
        group_title = prev.get("group_title", "Live Sports")

        if urls:
            print(f"  → Found {len(urls)} stream(s)")
            for u in urls:
                print(f"     {u}")
                content += f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{tvg_logo}" group-title="{group_title}",{name}\n'
                content += f"{u}\n"
        else:
            print("  → No stream found")
            # Optional: keep a placeholder so the channel name still appears
            # content += f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{tvg_logo}" group-title="{group_title}",{name}\n'
            # content += "https://example.com\n"

    with open(playlist_file, "w", encoding="utf-8") as f:
        f.write(content)

    print("\nLiveSports.m3u has been updated")
    return True


if __name__ == "__main__":
    print("Starting playlist update...")
    update_playlist()
    print("Done.")
