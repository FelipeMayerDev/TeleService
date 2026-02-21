from random import randint

from serpapi import GoogleSearch
import time

from .config import SERPAPI_API_KEY


class SerpProvider:
    @staticmethod
    def search_image(image, limit=15, max_retries=3):
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
                    return images_results[random_number]["original"]
            except Exception:
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)
                continue
        return None
