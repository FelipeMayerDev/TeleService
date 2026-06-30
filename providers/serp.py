from random import randint
import json
import os
import time

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
                # Remove expired entries
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

    @staticmethod
    def search_image(image, limit=15, max_retries=3, use_cache=False):
        SerpProvider._load_cache()

        # Check cache
        if use_cache:
            cached = SerpProvider._cache.get(image)
            if cached:
                print(f"Image cache HIT for: {image}")
                return cached["url"]

        for attempt in range(max_retries):
            try:
                params = {
                    "engine": "google_images",
                    "q": image,
                    "num": limit,
                    "safe": "off",
                    "api_key": SERPAPI_API_KEY,
                }
                search = GoogleSearch(params)
                results = search.get_dict()
                images_results = results.get("images_results", [])
                if images_results:
                    random_number = randint(0, len(images_results) - 1)
                    url = images_results[random_number]["original"]
                    # Save to cache if enabled
                    if use_cache:
                        SerpProvider._cache[image] = {"url": url, "ts": time.time()}
                        SerpProvider._save_cache()
                        print(f"Image cache MISS for: {image} (saved to cache)")
                    return url
            except Exception:
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)
                continue
        return None
