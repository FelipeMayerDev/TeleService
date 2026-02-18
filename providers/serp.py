from random import randint

from serpapi import GoogleSearch

from .config import SERPAPI_API_KEY


class SerpProvider:
    @staticmethod
    def search_image(image, limit=15):
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
        return None
