import json
import os
import time
from random import choice

import requests
from serpapi import GoogleSearch

from .config import SERPAPI_API_KEY

CACHE_FILE = "/app/database.sqlite/image_cache.json"
CACHE_TTL = 86400 * 7  # 7 days


class SerpProvider:
    _cache: dict = {}
    _cache_loaded = False

    @classmethod
    def _load_cache(cls):
        if cls._cache_loaded:
            return
        cls._cache_loaded = True
        try:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    cls._cache = json.load(f)
                now = time.time()
                cls._cache = {
                    k: v for k, v in cls._cache.items() if now - v["ts"] < CACHE_TTL
                }
        except Exception:
            cls._cache = {}

    @classmethod
    def _save_cache(cls):
        try:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            with open(CACHE_FILE, "w") as f:
                json.dump(cls._cache, f)
        except Exception:
            pass

    # --- Provider chain ---

    @staticmethod
    def _serpapi_search(query, limit=15):
        """SerpAPI Google Images — primary, paid quota."""
        params = {
            "engine": "google_images",
            "q": query,
            "num": limit,
            "safe": "off",
            "api_key": SERPAPI_API_KEY,
        }
        results = GoogleSearch(params).get_dict()
        images = results.get("images_results", [])
        return [r["original"] for r in images if r.get("original")]

    @staticmethod
    def _openverse_search(query, limit=15):
        """Openverse — free, no key, mature=true disables safesearch."""
        resp = requests.get(
            "https://api.openverse.org/v1/images/",
            params={"q": query, "page_size": limit, "mature": "true"},
            timeout=10,
        )
        resp.raise_for_status()
        return [r["url"] for r in resp.json().get("results", []) if r.get("url")]

    @staticmethod
    def _wikimedia_search(query, limit=15):
        """Wikimedia Commons — free, no key, no safesearch."""
        resp = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrnamespace": "6",
                "gsrsearch": query,
                "gsrlimit": limit,
                "prop": "imageinfo",
                "iiprop": "url",
            },
            timeout=10,
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        return [
            p["imageinfo"][0]["url"]
            for p in pages.values()
            if p.get("imageinfo") and p["imageinfo"][0].get("url")
        ]

    @staticmethod
    def search_image(image, limit=15, max_retries=3, use_cache=False):
        """Search images across multiple providers. Returns URL or None.

        Chain: SerpAPI → Openverse → Wikimedia. First non-empty wins.
        """
        SerpProvider._load_cache()

        if use_cache:
            cached = SerpProvider._cache.get(image)
            if cached:
                print(f"Image cache HIT for: {image}")
                return cached["url"]

        for provider in (
            SerpProvider._serpapi_search,
            SerpProvider._openverse_search,
            SerpProvider._wikimedia_search,
        ):
            try:
                urls = provider(image, limit)
                if urls:
                    url = choice(urls)
                    if use_cache:
                        SerpProvider._cache[image] = {"url": url, "ts": time.time()}
                        SerpProvider._save_cache()
                        print(f"Image cache MISS for: {image} (saved to cache)")
                    return url
            except Exception as e:
                print(f"{provider.__name__} failed: {e}")

        return None