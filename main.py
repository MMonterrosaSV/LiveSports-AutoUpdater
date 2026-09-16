from playwright.sync_api import sync_playwright
import os
import re
from urllib.parse import urlparse, parse_qs


def score_url(url: str) -> int:
    """Higher score = newer signed URL"""
    score = 0

    # live.tv247.site → e= parameter
    try:
        qs = parse_qs(urlparse(url).query)
        if "e" in qs:
            score = max(score, int(qs["e"][0]))
    except:
        pass

    # ftlly.com and similar → timestamps inside the token
    numbers = re.findall(r"(\d{10,})", url)
    if numbers:
        score = max(score, max(int(n) for n in numbers))

    score = score * 10 + len(url)
    return score


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

        page.wait_for_timeout(10000)  # extra time for the newest token
        browser.close()

    if not candidates:
        return None

    clean = [u for u in candidates if not any(bad in u.lower() for bad in
             ["ads", "advert", "tracker", "analytics", "pixel", "banner"])]

    if not clean:
        clean = candidates

    # Prefer known good domains, then newest signature
    preferred = [u for u in clean if any(x in u for x in ["live.tv247.site", "ftlly.com", "chunk.tvnow247.today", "token=", "m3u8"])]
    pool = preferred if preferred else clean

    best = max(pool, key=score_url)
    return best


channels = {
    "DAZN LA LIGA 1": "https://tvnow247.top/embed/dazn-laliga/",
    "M+ LA LIGA 1": "https://tvnow247.top/embed/movistar-laliga/",
    "M+ CHAMPIONS LEAGUE 1": "https://tvnow247.top/embed/movistar-liga-de-campeones/",
    "M+ DEPORTES 1": "https://tvnow247.top/embed/movistar-deportes-4",
    "M+ DEPORTES 2": "https://tvnow247.top/embed/movistar-deportes-2/",
    "M+": "https://tvnow247.top/embed/movistar-supercopa-de-espana/",
    "ESPN DEPORTES": "https://tvnow247.top/embed/espn-deportes/",
    "ESPN DEPORTES BACKUP 1": "https://w6.sportsonliine.click/channels/hd/hd6.php",
    "DSPORTS": "https://wsdeportes.net/?v=dsports",
    "DSPORTS BACKUP 1": "https://tvf90.com/online.php?stream=dsports",
    "TUDN MEXICO": "https://tvnow247.top/watch/tudn-mx/",
    "TUDN USA": "https://tvnow247.top/watch/tudn-usa/",
    "TUDN USA BACKUP": "https://wsdeportes.net/?v=tudnus",
    "TNT SPORTS 1": "https://tvnow247.top/embed/tnt-sports-1/",
    "TNT SPORTS 2": "https://tvnow247.top/watch/tnt-sports-2/",
    "TNT SPORTS 3": "https://tvnow247.top/watch/tnt-sports-3/",
    "SKY SPORTS PREMIER LEAGUE": "https://tvnow247.top/watch/sky-sports-premier-league/",
    "SKY SPORTS FOOTBALL": "https://tvnow247.top/watch/sky-sports-football/",
    "SKY SPORTS PLUS": "https://tvnow247.top/watch/sky-sports-plus/",
    "SKY SPORTS MAIN EVENT": "https://tvnow247.top/watch/sky-sports-main-event/",
    "FOX SPORTS 1": "https://tvf90.com/online.php?stream=foxsports1_usa",
    "FOX SPORTS 2": "https://tvf90.com/online.php?stream=foxsports2_usa",
}


def update_playlist():
    playlist_file = "LiveSports.m3u"

    # Read existing tags
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
                    "group_title": group_title.group(1) if group_title else ""
                }
            elif line.startswith("http") and current_meta:
                current_meta["url"] = line.strip()
                existing[current_meta["name"]] = current_meta
                current_meta = {}

    content = "#EXTM3U\n#PLAYLIST:LIVE SPORTS\n"

    for name, embed_url in channels.items():
        print(f"\nProcessing: {name}")
        new_url = extract_m3u8(embed_url)

        prev = existing.get(name, {})
        tvg_id = prev.get("tvg_id", "")
        tvg_logo = prev.get("tvg_logo", "")
        group_title = prev.get("group_title", "Live Sports")  # default group
        old_url = prev.get("url", "https://example.com")

        if new_url:
            print(f"  → Found: {new_url}")
            final_url = new_url
        else:
            print("  → No stream found, keeping old URL")
            final_url = old_url

        content += f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{tvg_logo}" group-title="{group_title}",{name}\n'
        content += f"{final_url}\n"

    with open(playlist_file, "w", encoding="utf-8") as f:
        f.write(content)

    print("\nLiveSports.m3u has been updated")
    return True


if __name__ == "__main__":
    print("Starting playlist update...")
    update_playlist()
    print("Done.")
