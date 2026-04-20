"""
Last.fm to Discord Webhook Integration
Monitors currently playing Last.fm track and sends updates to Discord webhook.
"""

import logging
import os
import re
import signal
import sys
import time
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional, Dict, Any

import requests
from colorthief import ColorThief
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_USERNAME = os.getenv("LASTFM_USERNAME")
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "30"))  # default 30s
LOW_CPU_MODE = os.getenv("LOW_CPU_MODE", "false").lower() in ("1", "true", "yes")

# Constants
FALLBACK_EMBED_COLOR = 0xFFFFFF
MAX_RETRIES = 3
RETRY_DELAY = 5

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("webhook_discord.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Global state
last_track_id: Optional[str] = None
lastfm_profile: Optional[Dict[str, str]] = None
COLOR_CACHE: Dict[str, int] = {}
running = True

def validate_config() -> None:
    required_vars = ["DISCORD_WEBHOOK_URL"]
    optional_vars = ["LASTFM_API_KEY", "LASTFM_USERNAME"]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    missing_optional = [var for var in optional_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )
        sys.exit(1)

    if missing_optional:
        logger.warning(
            "Last.fm integration will be disabled because the following optional variables are missing: "
            f"{', '.join(missing_optional)}"
        )

def signal_handler(signum: int, frame: Any) -> None:
    global running
    logger.info("\nShutting down gracefully...")
    running = False
    sys.exit(0)

def normalize_lastfm_image_url(image_url: str, target_size: str = "0x0") -> str:
    if not image_url:
        return ""
    if target_size in image_url:
        return image_url
    return re.sub(r"/\d+x\d+\/", f"/{target_size}/", image_url)

def get_lastfm_image_url(images: list[dict]) -> str:
    if not images:
        return ""
    for size in ("mega", "extralarge", "large", "medium", "small"):
        for image in images:
            if image.get("size") == size:
                url = image.get("#text", "")
                if url:
                    return normalize_lastfm_image_url(url)
    for image in images:
        url = image.get("#text", "")
        if url:
            return normalize_lastfm_image_url(url)
    return ""

def get_dominant_color(image_url: str) -> int:
    if not image_url:
        return FALLBACK_EMBED_COLOR
    if image_url in COLOR_CACHE:
        return COLOR_CACHE[image_url]
    quality = 10 if LOW_CPU_MODE else 1
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        image_file = BytesIO(response.content)
        color_thief = ColorThief(image_file)
        r, g, b = color_thief.get_color(quality=quality)
        color_value = (r << 16) + (g << 8) + b
        COLOR_CACHE[image_url] = color_value
        return color_value
    except Exception as e:
        logger.warning(f"Failed to extract dominant color: {e}")
        return FALLBACK_EMBED_COLOR

def get_total_scrobbles() -> Optional[str]:
    if not LASTFM_API_KEY or not LASTFM_USERNAME:
        return None
    try:
        response = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "user.getInfo",
                "user": LASTFM_USERNAME,
                "api_key": LASTFM_API_KEY,
                "format": "json",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("user", {}).get("playcount")
    except Exception as e:
        logger.warning(f"Failed to fetch Last.fm scrobbles: {e}")
        return None

def get_lastfm_profile() -> Optional[Dict[str, str]]:
    if not LASTFM_API_KEY or not LASTFM_USERNAME:
        return None
    try:
        response = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "user.getInfo",
                "user": LASTFM_USERNAME,
                "api_key": LASTFM_API_KEY,
                "format": "json",
            },
            timeout=10,
        )
        response.raise_for_status()
        user = response.json().get("user", {})
        image_url = get_lastfm_image_url(user.get("image", []))
        return {
            "name": user.get("realname") or user.get("name") or LASTFM_USERNAME,
            "url": user.get("url", f"https://www.last.fm/user/{LASTFM_USERNAME}"),
            "avatar": image_url,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch Last.fm profile: {e}")
        return None

def get_lastfm_current_track() -> Optional[Dict[str, Any]]:
    if not LASTFM_API_KEY or not LASTFM_USERNAME:
        return None
    try:
        response = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "user.getrecenttracks",
                "user": LASTFM_USERNAME,
                "api_key": LASTFM_API_KEY,
                "format": "json",
                "limit": 1,
            },
            timeout=10,
        )
        response.raise_for_status()
        tracks = response.json().get("recenttracks", {}).get("track", [])
        if not tracks:
            return None
        track = tracks[0]
        if track.get("@attr", {}).get("nowplaying") != "true":
            return None
        artist_name = track.get("artist", {}).get("#text", "Unknown Artist")
        track_name = track.get("name", "Unknown Track")
        album_name = track.get("album", {}).get("#text", "Unknown Album")
        image_url = get_lastfm_image_url(track.get("image", []))
        track_url = track.get("url", "")
        return {
            "item": {
                "id": f"lastfm-{artist_name}-**{track_name}**".replace(" ", "_").lower(),
                "name": track_name,
                "artists": [{"name": artist_name}],
                "album": {"name": album_name, "images": [{"url": image_url}]},
                "external_urls": {"lastfm": track_url},
            }
        }
    except Exception as e:
        logger.warning(f"Failed to fetch current track: {e}")
        return None

def get_current_track() -> Optional[Dict[str, Any]]:
    return get_lastfm_current_track()

def send_discord_webhook(payload: dict) -> bool:
    max_attempts = 5
    attempt = 0

    while attempt < max_attempts:
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)

            if response.status_code == 429:
                retry_after = 1
                # cek kalau header Retry-After ada
                if "Retry-After" in response.headers:
                    retry_after = float(response.headers["Retry-After"])
                else:
                    try:
                        # coba parse JSON kalau ada
                        retry_after = response.json().get("retry_after", 1)
                    except ValueError:
                        # JSON kosong atau invalid, pakai default 1 detik
                        pass
                logger.warning(f"Rate limited by Discord. Retrying in {retry_after} seconds...")
                time.sleep(retry_after)
                attempt += 1
                continue

            response.raise_for_status()
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to send Discord webhook: {e}")
            attempt += 1
            time.sleep(2)

    logger.error("Failed to send webhook after multiple attempts.")
    return False

def process_track(data: Dict[str, Any]) -> None:
    global last_track_id
    if not data or not data.get("item"):
        return
    item = data["item"]
    track_id = item.get("id")
    if not track_id or track_id == last_track_id:
        return
    try:
        artist_name = item["artists"][0]["name"]
        track_name = item["name"]
        album_name = item["album"]["name"]
        album_images = item["album"]["images"]
        album_art = album_images[0]["url"] if album_images else ""
        album_art = normalize_lastfm_image_url(album_art) if album_art else ""
        color_image_url = album_images[-1]["url"] if album_images else album_art
        embed_color = get_dominant_color(color_image_url)
        total_scrobbles = get_total_scrobbles()

        author_url = f"https://www.last.fm/user/{LASTFM_USERNAME}" if LASTFM_API_KEY and LASTFM_USERNAME else None
        display_name = lastfm_profile["name"] if lastfm_profile and lastfm_profile.get("name") else LASTFM_USERNAME
        author_name = f"Now playing - {display_name}"
        author = {"name": author_name}
        if author_url:
            author["url"] = author_url
        if lastfm_profile and lastfm_profile.get("avatar"):
            author["icon_url"] = lastfm_profile["avatar"]

        description_text = f"**{artist_name}** • *{album_name}*"

        embed = {
            "color": embed_color,
            "author": author,
            "title": f"**{track_name}**",
            "url": item["external_urls"].get("lastfm", ""),
            "description": description_text,
            "thumbnail": {"url": album_art},
            "footer": {"text": f"{total_scrobbles} total scrobbles"},
        }

        payload = {"embeds": [embed]}
        if send_discord_webhook(payload):
            logger.info(f"Now playing: {artist_name} - **{track_name}**")
            last_track_id = track_id

    except Exception as e:
        logger.error(f"Error processing track: {e}")

def main() -> None:
    global lastfm_profile, running
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    validate_config()
    if LASTFM_API_KEY and LASTFM_USERNAME:
        lastfm_profile = get_lastfm_profile()
    logger.info("Starting Last.fm → Discord Webhook")
    logger.info(f"Polling interval: {POLLING_INTERVAL} seconds")
    while running:
        try:
            data = get_current_track()
            process_track(data)
            sleep_time = POLLING_INTERVAL if data else POLLING_INTERVAL * 2
            time.sleep(sleep_time)
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            time.sleep(RETRY_DELAY)

if __name__ == "__main__":
    main()